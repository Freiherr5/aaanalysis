"""
This is a script for the backend of the CPP.run() method.

This is the key algorithm of CPP and for AAanalysis.
"""
import os
import numpy as np
import pandas as pd
import multiprocessing as mp
from itertools import repeat
import warnings

import aaanalysis.utils as ut
from .utils_feature import get_vf_scale, get_feature_matrix_, post_check_vf_scale
from ._utils_feature_stat import add_stat_
from ._split import SplitRange


# I Helper functions
def _get_splits(df_parts=None, split_type=None, split_type_args=None):
    """Split all given parts from df_parts. The split is given by its split_type
     (Segment, Pattern, or PeriodicPattern) and its arguments (split_kwargs)."""
    list_parts = list(df_parts)
    spr = SplitRange()
    f = getattr(spr, split_type.lower())
    if split_type_args is not None:
        f_splitr = lambda x: f(seq=x, **split_type_args)
        labels_s = getattr(spr, "labels_" + split_type.lower())(**split_type_args)
    else:
        f_splitr = lambda x: f(seq=x)   # Using default arguments
        labels_s = getattr(spr, "labels_" + split_type.lower())()
    # Combine part and split to get sequence splits
    part_splits = np.empty([len(df_parts), len(labels_s) * len(list_parts)], dtype=object)
    labels_ps = []  # Part Split labels
    for i, p in enumerate(list_parts):
        labels_ps.extend(["{}-{}".format(p.upper(), s) for s in labels_s])
        for j, seq in enumerate(df_parts[p]):
            part_splits[j, i*len(labels_s):(i+1)*len(labels_s)] = f_splitr(seq)
    return part_splits, labels_ps


# Pre-filtering and filtering
def _splitting(df_parts=None, split_kws=None):
    """Combine Part + Split.
    Returns:
        part_split: sequence fragments generated by applying splits on given sequence parts
        list_labels_ps: list with labels for Part-Split combination
    """
    list_parts_splits = []
    list_labels_ps = []
    for split_type in split_kws:
        split_type_args = split_kws[split_type]
        part_splits, labels_ps = _get_splits(df_parts=df_parts,
                                             split_type=split_type,
                                             split_type_args=split_type_args)
        list_parts_splits.append(part_splits)
        list_labels_ps.extend(labels_ps)
    part_split = np.concatenate(list_parts_splits, axis=1)
    return part_split, list_labels_ps


def _pre_filtering_info(list_scales, dict_all_scales, labels_ps, part_split, accept_gaps, mask_0, mask_1, verbose):
    """Compute abs(mean_dif) and std(test) to rank features, where mean_dif is the difference
    between the means of the test and the reference protein groups for a feature"""
    feat_names = np.empty((len(list_scales) * len(labels_ps)), dtype=object)
    abs_mean_dif = np.empty((len(list_scales) * len(labels_ps)))
    std_test = np.empty((len(list_scales) * len(labels_ps)))
    for i, scale in enumerate(list_scales):
        if verbose:
            ut.print_progress(i=i, n=len(list_scales))
        dict_scale = dict_all_scales[scale]
        start, end = i*len(labels_ps), (i+1)*len(labels_ps)
        # Feature names
        feat_names[start:end] = ["{}-{}".format(ps, scale) for ps in labels_ps]
        # Feature matrix
        vf_scale = get_vf_scale(dict_scale=dict_scale, accept_gaps=accept_gaps)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)    # Filter numpy warning: "Mean of emtpy slice"
            X = np.round(vf_scale(part_split), 5)
        if accept_gaps:
            post_check_vf_scale(feature_values=X)
        # Ranking infos
        abs_mean_dif[start:end] = abs(np.mean(X[mask_1], axis=0) - np.mean(X[mask_0], axis=0))
        std_test[start:end] = np.std(X[mask_1], axis=0)
    return abs_mean_dif, std_test, feat_names


def _filtering_info(df=None, df_scales=None, check_cat=True):
    """Get datasets structures for filtering, two dictionaries with feature to scale category resp.
    feature positions and one datasets frame with paired pearson correlations of all scales"""
    if check_cat:
        dict_c = dict(zip(df[ut.COL_FEATURE], df["category"]))
    else:
        dict_c = dict()
    dict_p = dict(zip(df[ut.COL_FEATURE], [set(x) for x in df["positions"]]))
    df_cor = df_scales.corr()
    return dict_c, dict_p, df_cor


# II Main functions
# Filtering methods
def pre_filtering_info(df_parts=None, split_kws=None, df_scales=None, labels=None, label_test=1, label_ref=0,
                       accept_gaps=False, verbose=True, n_jobs=None):
    """Get n best features in descending order based on the abs(mean(group1) - mean(group0),
    where group 1 is the target group"""
    # Input (df_parts, split_kws, df_scales, y) checked in main method (CPP.run())
    mask_ref = [x == label_ref for x in labels]
    mask_test = [x == label_test for x in labels]
    part_split, labels_ps = _splitting(split_kws=split_kws, df_parts=df_parts)
    list_scales = list(df_scales)
    dict_all_scales = {col: dict(zip(df_scales.index.to_list(), df_scales[col])) for col in list_scales}
    # Feature filtering
    if n_jobs == 1:
        # Run in a single process
        args = [list_scales, dict_all_scales, labels_ps, part_split, accept_gaps, mask_ref, mask_test, verbose]
        abs_mean_dif, std_test, feat_names = _pre_filtering_info(*args)
    else:
        # Run in multiple processes
        n_jobs = min([os.cpu_count(), len(list_scales)])
        scale_chunks = np.array_split(list_scales, n_jobs)
        args = zip(scale_chunks, repeat(dict_all_scales), repeat(labels_ps), repeat(part_split), repeat(accept_gaps),
                   repeat(mask_ref), repeat(mask_test), repeat(verbose))
        with mp.get_context("spawn").Pool(processes=n_jobs) as pool:
            result = pool.starmap(_pre_filtering_info, args)
        abs_mean_dif = np.concatenate([x[0] for x in result])
        std_test = np.concatenate([x[1] for x in result])
        feat_names = np.concatenate([x[2] for x in result])
    return abs_mean_dif, std_test, feat_names

def pre_filtering(features=None, abs_mean_dif=None, std_test=None, max_std_test=0.2, n=10000):
    """CPP pre-filtering based on thresholds."""
    df = pd.DataFrame(zip(features, abs_mean_dif, std_test),
                      columns=[ut.COL_FEATURE, ut.COL_ABS_MEAN_DIF, ut.COL_STD_TEST])
    df = df[df[ut.COL_STD_TEST] <= max_std_test]
    df = df.sort_values(by=ut.COL_ABS_MEAN_DIF, ascending=False).head(n)
    return df


def filtering(df=None, df_scales=None, max_overlap=0.5, max_cor=0.5, n_filter=100, check_cat=True):
    """CPP filtering algorithm based on redundancy reduction in descending order of absolute AUC."""
    dict_c, dict_p, df_cor = _filtering_info(df=df, df_scales=df_scales, check_cat=check_cat)
    df = df.sort_values(by=[ut.COL_ABS_AUC, ut.COL_ABS_MEAN_DIF], ascending=False).copy().reset_index(drop=True)
    list_feat = list(df[ut.COL_FEATURE])
    list_top_feat = [list_feat.pop(0)]  # List with best feature
    for feat in list_feat:
        add_flag = True
        # Stop condition for limit
        if len(list_top_feat) == n_filter:
            break
        # Compare features with all top features (added if low overlap & weak correlation or different category)
        for top_feat in list_top_feat:
            # If check_cat is False, the categories are not compared and only the position and correlation are checked
            if not check_cat or dict_c[feat] == dict_c[top_feat]:
                # Remove if feat positions high overlap or subset
                pos, top_pos = dict_p[feat], dict_p[top_feat]
                overlap = len(top_pos.intersection(pos))/len(top_pos.union(pos))
                if overlap >= max_overlap or pos.issubset(top_pos):
                    # Remove if high pearson correlation
                    scale, top_scale = feat.split("-")[2], top_feat.split("-")[2]
                    cor = df_cor[top_scale][scale]
                    if cor > max_cor:
                        add_flag = False
        if add_flag:
            list_top_feat.append(feat)
    df_top_feat = df[df[ut.COL_FEATURE].isin(list_top_feat)]
    return df_top_feat


# Adder methods for CPP analysis (used in run method)
def add_stat(df_feat=None, df_parts=None, df_scales=None, labels=None, parametric=False, accept_gaps=False,
             label_test=1, label_ref=0, n_jobs=None):
        """
        Add summary statistics for each feature to DataFrame.

        Notes
        -----
        P-values are calculated Mann-Whitney U test (non-parametric) or T-test (parametric) as implemented in SciPy.
        For multiple hypothesis correction, the Benjamini-Hochberg FDR correction is applied on all given features
        as implemented in SciPy.
        """
        # Add feature statistics
        features = list(df_feat[ut.COL_FEATURE])
        X = get_feature_matrix_(features=features,
                                df_parts=df_parts,
                                df_scales=df_scales,
                                accept_gaps=accept_gaps,
                                n_jobs=n_jobs)
        df_feat = add_stat_(df=df_feat, X=X, labels=labels, parametric=parametric,
                            label_test=label_test, label_ref=label_ref)
        return df_feat
