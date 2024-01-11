"""
This is a script for utility feature functions for CPP and SequenceFeature objects and backend.
"""
import os
import numpy as np
from itertools import repeat
import multiprocessing as mp
import pandas as pd

from ._part import create_parts
from ._split import Split
import aaanalysis.utils as ut


# I Helper Functions
# DEV: Run exceptionally in backend because error might only be caused internally
def pre_check_vf_scale(part_split=None):
    """Check for the presence of a specific gap string in the sequence."""
    # Join the elements of part_split into a single string
    combined_string = "".join(part_split)
    # Check if ut.STR_AA_GAP is in the combined string
    if ut.STR_AA_GAP in combined_string:
        raise ValueError("Some input sequences contain gaps ('-').")

def post_check_vf_scale(feature_values=None):
    """Check if feature_values/X does contain nans due to gaps"""
    if np.isnan(feature_values).any():
        raise ValueError("Some input sequences result in NaN feature values most likely due to gaps ('-').")


def get_vf_scale(dict_scale=None, accept_gaps=False):
    """Vectorized function to calculate the mean for a feature"""
    if not accept_gaps:
        # Vectorized scale function
        vf_scale = np.vectorize(lambda x: np.mean([dict_scale[a] for a in x]))
    else:
        # Except NaN derived from 'X' in sequence if not just 'X' in sequence (3x slower)
        def get_mean_excepting_nan(x):
            vals = np.array([dict_scale.get(a, np.NaN) for a in x])
            return vals
        vf_scale = np.vectorize(lambda x: np.nanmean(get_mean_excepting_nan(x)))
    return vf_scale


def _get_split_info(split=None):
    """Parse split information"""
    split = split.replace(" ", "")  # remove whitespace
    # Check Segment
    if ut.STR_SEGMENT in split:
        split_type = ut.STR_SEGMENT
        i_th, n_split = [int(x) for x in split.split("(")[1].replace(")", "").split(",")]
        split_kwargs = dict(i_th=i_th, n_split=n_split)
    # Check PeriodicPattern
    elif ut.STR_PERIODIC_PATTERN in split:
        split_type = ut.STR_PERIODIC_PATTERN
        start = split.split("i+")[1].replace(")", "").split(",")
        step1, step2 = [int(x) for x in start.pop(0).split("/")]
        start = int(start[0])
        terminus = split.split("i+")[0].split("(")[1].replace(",", "")
        split_kwargs = dict(terminus=terminus, step1=step1, step2=step2, start=start)
    # Check pattern
    else:
        split_type = ut.STR_PATTERN
        list_pos = split.split("(")[1].replace(")", "").split(",")
        terminus = list_pos.pop(0)
        list_pos = [int(x) for x in list_pos]
        split_kwargs = dict(terminus=terminus, list_pos=list_pos)
    return split_type, split_kwargs


# Get positions
def _get_dict_part_pos(tmd_len=20, jmd_n_len=10, jmd_c_len=10, start=1):
    """Get dictionary for part to positions."""
    jmd_n = list(range(0, jmd_n_len))
    tmd = list(range(jmd_n_len, tmd_len+jmd_n_len))
    jmd_c = list(range(jmd_n_len + tmd_len, jmd_n_len + tmd_len + jmd_c_len))
    # Change int to string and adjust length
    jmd_n = [i + start for i in jmd_n]
    tmd = [i + start for i in tmd]
    jmd_c = [i + start for i in jmd_c]
    dict_part_pos = ut.get_dict_part_seq(tmd=tmd, jmd_n=jmd_n, jmd_c=jmd_c)
    return dict_part_pos


def _get_positions(dict_part_pos=None, features=None, as_str=True):
    """Get list of positions for given feature names."""
    sp = Split(type_str=False)
    list_pos = []
    for feat_id in features:
        part, split, scale = feat_id.split("-")
        split_type, split_kwargs = _get_split_info(split=split)
        f_split = getattr(sp, split_type.lower())
        pos = sorted(f_split(seq=dict_part_pos[part.lower()], **split_kwargs))
        if as_str:
            pos = str(pos).replace("[", "").replace("]", "").replace(" ", "")
        list_pos.append(pos)
    return list_pos


# Get df positions
def _get_df_pos_long(df=None, col_cat="category", col_value=None):
    """Get """
    if col_value is None:
        df_feat = df[[ut.COL_FEATURE, col_cat]].set_index(ut.COL_FEATURE)
    else:
        df_feat = df[[ut.COL_FEATURE, col_cat, col_value]].set_index(ut.COL_FEATURE)
    # Columns = scale categories, rows = features
    df_pos_long = pd.DataFrame(df[ut.COL_POSITION].str.split(",").tolist())
    df_pos_long.index = df[ut.COL_FEATURE]
    df_pos_long = df_pos_long.stack().reset_index(level=1).drop("level_1", axis=1).rename({0: ut.COL_POSITION}, axis=1)
    df_pos_long = df_pos_long.join(df_feat)
    df_pos_long[ut.COL_POSITION] = df_pos_long[ut.COL_POSITION].astype(int)
    return df_pos_long


# Get feature matrix
def _get_dict_all_scales(df_scales=None):
    """Get nested dictionary where each scale is a key for an amino acid scale value dictionary"""
    dict_all_scales = {col: dict(zip(df_scales.index.to_list(), df_scales[col])) for col in list(df_scales)}
    return dict_all_scales


def _feature_value(df_parts=None, split=None, dict_scale=None, accept_gaps=False):
    """Helper function to create feature values for feature matrix"""
    sp = Split()
    # Get vectorized split function
    split_type, split_kwargs = _get_split_info(split=split)
    f_split = getattr(sp, split_type.lower())
    # Vectorize split function using anonymous function
    vf_split = np.vectorize(lambda x: f_split(seq=x, **split_kwargs))
    # Get vectorized scale function
    vf_scale = get_vf_scale(dict_scale=dict_scale, accept_gaps=accept_gaps)
    # Combine part split and scale to get feature values
    part_split = vf_split(df_parts)
    if not accept_gaps:
        pre_check_vf_scale(part_split=part_split)
    feature_value = np.round(vf_scale(part_split), 5)  # feature values
    if accept_gaps:
        post_check_vf_scale(feature_values=feature_value)
    return feature_value


def _feature_matrix(features, dict_all_scales, df_parts, accept_gaps):
    """Helper function to create feature matrix via multiple processing"""
    X = np.empty([len(df_parts), len(features)])
    for i, feat_name in enumerate(features):
        part, split, scale = feat_name.split("-")
        dict_scale = dict_all_scales[scale]
        X[:, i] = _feature_value(split=split,
                                 dict_scale=dict_scale,
                                 df_parts=df_parts[part.lower()],
                                 accept_gaps=accept_gaps)
    return X


# II Main Functions
def get_part_positions(start=1, tmd_len=20, jmd_n_len=10, jmd_c_len=10):
    """Get part positions"""
    jmd_n = list(range(start, jmd_n_len + start))
    tmd = list(range(jmd_n_len + start, jmd_n_len + tmd_len + start))
    jmd_c = list(range(jmd_n_len + tmd_len + start, jmd_n_len + tmd_len + jmd_c_len + start))
    return jmd_n, tmd, jmd_c


def get_list_parts(features=None):
    """Get list of parts to cover all features"""
    features = [features] if type(features) is str else features
    # Features are PART-SPLIT-SCALE combinations
    list_parts = list(set([x.split("-")[0].lower() for x in features]))
    return list_parts


def get_df_parts_(df_seq=None, list_parts=None, jmd_n_len=None, jmd_c_len=None):
    """Create DataFrame with sequence parts"""
    pos_based = set(ut.COLS_SEQ_POS).issubset(set(df_seq))
    dict_parts = {}
    for i, row in df_seq.iterrows():
        entry = row[ut.COL_ENTRY]
        if jmd_c_len is not None and jmd_n_len is not None and pos_based:
            seq, tmd_start, tmd_stop = row[ut.COLS_SEQ_POS].values
            jmd_n, tmd, jmd_c = create_parts(seq=seq, tmd_start=tmd_start, tmd_stop=tmd_stop,
                                             jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len)
        else:
            jmd_n, tmd, jmd_c = row[ut.COLS_SEQ_PARTS].values
        dict_part_seq = ut.get_dict_part_seq(tmd=tmd, jmd_n=jmd_n, jmd_c=jmd_c)
        dict_part_seq = {part: dict_part_seq[part] for part in list_parts}
        dict_parts[entry] = dict_part_seq
    df_parts = pd.DataFrame.from_dict(dict_parts).T
    # DEV: the following line sorts index if list_parts contains just one element
    # df_parts = pd.DataFrame.from_dict(dict_parts, orient="index")
    return df_parts


def remove_entries_with_gaps_(df_parts=None):
    """Remove rows where any cell contains '-'"""
    df_parts = df_parts[~df_parts.map(lambda x: '-' in str(x)).any(axis=1)]
    return df_parts


def get_positions_(features=None, start=1, tmd_len=20, jmd_n_len=10, jmd_c_len=10):
    """Create list with positions for given feature names"""
    features = [features] if type(features) is str else features
    dict_part_pos = _get_dict_part_pos(tmd_len=tmd_len, jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len, start=start)
    feat_positions = _get_positions(dict_part_pos=dict_part_pos, features=features)
    return feat_positions


def get_amino_acids_(features=None, tmd_seq="", jmd_n_seq="", jmd_c_seq=""):
    """Create amino acid segments/patterns for features"""
    features = [features] if type(features) is str else features
    pos = get_positions_(features=features, tmd_len=len(tmd_seq), jmd_n_len=len(jmd_n_seq),
                         jmd_c_len=len(jmd_c_seq), start=0)
    seq = jmd_n_seq + tmd_seq + jmd_c_seq
    f_seg = lambda x: "".join([seq[int(p)] for p in x.split(",")])
    f_pat = lambda x: "-".join([seq[int(p)] for p in x.split(",")])
    feat_aa = [f_seg(pos) if "Segment" in feat else f_pat(pos) for feat, pos in zip(features, pos)]
    return feat_aa


def get_feature_matrix_(features=None, df_parts=None, df_scales=None, accept_gaps=False, n_jobs=None):
    """Create feature matrix for given feature ids and sequence parts."""
    features = [features] if type(features) is str else features
    dict_all_scales = _get_dict_all_scales(df_scales=df_scales)
    # Convert features to list if needed
    features = features.to_list() if isinstance(features, pd.Series) else features
    # Feature creation
    if n_jobs == 1:
        # Run in a single process
        feat_matrix = _feature_matrix(features, dict_all_scales, df_parts, accept_gaps)
    else:
        # Run in multiple processes
        if n_jobs is None:
            # Optimize n_jobs that each core processes a minimum of 10 features
            n_jobs = min([os.cpu_count(), max([int(len(features)/10), 1])])
        feat_chunks = np.array_split(features, n_jobs)
        args = zip(feat_chunks, repeat(dict_all_scales), repeat(df_parts), repeat(accept_gaps))
        with mp.get_context("spawn").Pool(processes=n_jobs) as pool:
            result = pool.starmap(_feature_matrix, args)
        feat_matrix = np.concatenate(result, axis=1)
    return feat_matrix


def get_df_pos_(df_feat=None, col_cat="category", col_value=None, value_type="count", start=None, stop=None):
    """Get df with aggregated values for each combination of column values and positions"""
    df_feat = df_feat.copy()
    list_y_cat = sorted(set(df_feat[col_cat]))
    normalize_for_pos = value_type != "mean"
    if normalize_for_pos:
        df_feat[col_value] = df_feat[col_value] / [len(x.split(",")) for x in df_feat[ut.COL_POSITION]]
    # Get df with features for each position
    df_pos_long = _get_df_pos_long(df=df_feat, col_cat=col_cat, col_value=col_value)
    # Get dict with values of categories for each position
    dict_pos_val = {p: [] for p in range(start, stop+1)}
    dict_cat_val = {c: 0 for c in list_y_cat}
    for p in dict_pos_val:
        if value_type == "count":
            dict_val = dict(df_pos_long[df_pos_long[ut.COL_POSITION] == p][col_cat].value_counts())
        elif value_type == "mean":
            dict_val = dict(df_pos_long[df_pos_long[ut.COL_POSITION] == p].groupby(col_cat).mean()[col_value])
        elif value_type == "sum":
            dict_val = dict(df_pos_long[df_pos_long[ut.COL_POSITION] == p].groupby(col_cat).sum()[col_value])
        else:
            dict_val = dict(df_pos_long[df_pos_long[ut.COL_POSITION] == p].groupby(col_cat).std()[col_value])
        dict_pos_val[p] = {**dict_cat_val, **dict_val}
    # Get df with values (e.g., counts) of each category and each position
    df_pos = pd.DataFrame(dict_pos_val)
    df_pos = df_pos.T[list_y_cat].T     # Filter and order categories
    return df_pos


def get_df_pos_parts_(df_pos=None, value_type="sum", start=1, tmd_len=20, jmd_n_len=10, jmd_c_len=10, list_parts=None):
    """Get df with aggregated values for each combination of column values and sequence parts."""
    jmd_n, tmd, jmd_c = get_part_positions(start=start, jmd_n_len=jmd_n_len, tmd_len=tmd_len, jmd_c_len=jmd_c_len)
    dict_part_pos = ut.get_dict_part_seq(tmd=tmd, jmd_n=jmd_n, jmd_c=jmd_c)
    if value_type == "sum":
        list_df = [df_pos[dict_part_pos[part]].sum(axis=1) for part in list_parts]
    elif value_type == "mean":
        list_df = [df_pos[dict_part_pos[part]].mean(axis=1) for part in list_parts]
    elif value_type == "count":
        list_df = [df_pos[dict_part_pos[part]].value_counts() for part in list_parts]
    else:
        list_df = [df_pos[dict_part_pos[part]].std(axis=1) for part in list_parts]
    df_pos = pd.concat(list_df, axis=1)
    df_pos.columns = list_parts
    return df_pos


def add_scale_info_(df_feat=None, df_cat=None):
    """Add scale information to DataFrame (scale categories, sub categories, and scale names)."""
    # Add scale categories
    df_cat = df_cat.copy()
    i = df_feat.columns.get_loc(ut.COL_FEATURE)
    for col in [ut.COL_SCALE_DES, ut.COL_SCALE_NAME, ut.COL_SUBCAT, ut.COL_CAT]:
        if col in list(df_feat):
            df_feat.drop(col, inplace=True, axis=1)
        dict_cat = dict(zip(df_cat[ut.COL_SCALE_ID], df_cat[col]))
        vals = [dict_cat[s.split("-")[2]] for s in df_feat[ut.COL_FEATURE]]
        df_feat.insert(i + 1, col, vals)
    return df_feat