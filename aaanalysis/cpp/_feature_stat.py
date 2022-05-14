"""
This is a script for ...
"""
import multiprocessing as mp
import os
from itertools import repeat
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.utils import check_array
from scipy import stats
from statsmodels.stats.multitest import multipletests
import warnings

from aaanalysis.cpp._split import SplitRange
import aaanalysis.cpp as ut


# I Helper Functions
# Check functions
def check_feat_matrix(X=None, y=None):
    """Check if X (feature matrix) and y (class labels) are not None and match"""
    if X is None:
        raise ValueError("'X' should not be None")
    check_array(X)    # Default checking function from sklearn

    if len(y) != X.shape[0]:
        raise ValueError(f"'y' (labels) does not match to 'X' (feature matrix)")


def check_split_type(split_type=None):
    """Check if split_type is valid"""
    list_split_types = [ut.STR_SEGMENT, ut.STR_PATTERN, ut.STR_PERIODIC_PATTERN]
    if split_type not in list_split_types:
        raise ValueError("'split_type' should be one of following: {}".format(list_split_types))


def check_p_cor(p_cor=None):
    """Check if p value correction method exists"""
    list_p_cor = ["bonferroni", "holm", "simes-hochberg", "fdr_bh"]
    if not (p_cor is None or p_cor in list_p_cor):
        raise ValueError("'p_cor' should be None or one of following: {}".format(list_p_cor))


# Ranking value functions
def _splitting(df_parts=None, split_type=None, split_type_args=None):
    """Split all given parts from df_parts. The split is given by its split_type
     (Segment, Pattern, or PeriodicPattern) and its arguments (split_kwargs)."""
    ut.check_df_parts(df_parts=df_parts)
    check_split_type(split_type=split_type)
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


def splitting(df_parts=None, split_kws=None):
    """Combine Part + Split

    Parameters
    ----------
    df_parts: pd.DataFrame
            DataFrame with sequence parts.
    split_kws: dict with kwargs for splitting

    Returns
    -------
    splittings: sequence fragments generated by applying splits on given sequence parts
    list_labels_ps: list with labels for Part-Split combination
    """
    list_parts_splits = []
    list_labels_ps = []
    for split_type in split_kws:
        split_type_args = split_kws[split_type]
        part_splits, labels_ps = _splitting(df_parts=df_parts,
                                            split_type=split_type,
                                            split_type_args=split_type_args)
        list_parts_splits.append(part_splits)
        list_labels_ps.extend(labels_ps)
    splittings = np.concatenate(list_parts_splits, axis=1)
    return splittings, list_labels_ps


def _pre_filtering_info(list_scales, dict_all_scales, labels_ps, splittings, accept_gaps, mask_0, mask_1, verbose):
    """Compute ranking value defined as abs(mean_dif) - std(test), where mean_dif is the difference
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
        vf_scale = ut.get_vf_scale(dict_scale=dict_scale, accept_gaps=accept_gaps)
        # TODO check missing values in ML
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)    # Filter numpy warning: "Mean of emtpy slice"
            X = np.round(vf_scale(splittings), 5)
        # Ranking infos
        abs_mean_dif[start:end] = abs(np.mean(X[mask_1], axis=0) - np.mean(X[mask_0], axis=0))
        std_test[start:end] = np.std(X[mask_1], axis=0)
    return abs_mean_dif, std_test, feat_names


# P-value adjustment
def _p_correction(p_vals=None, p_cor="fdr_bh"):
    """Correct p-values"""
    # Exclude nan from list of corrected p-values
    p_vals_without_na = [p for p in p_vals if str(p) != "nan"]
    p_corrected_without_na = list(multipletests(p_vals_without_na, method=p_cor)[1])
    # Include nan in list of corrected p-values
    p_corrected = []
    i = 0
    for p in p_vals:
        if str(p) != "nan":
            p_corrected.append(p_corrected_without_na[i])
            i += 1
        else:
            p_corrected.append(np.nan)
    return p_corrected


# II Main Functions
class SequenceFeatureStatistics:
    """Class for statistical analysis of sequence features. Methods are used for CPP algorithm"""

    @staticmethod
    def pre_filtering_info(df_parts=None, split_kws=None, df_scales=None, y=None,
                           accept_gaps=False, verbose=True):
        """Get n best features in descending order based on the abs(mean(group1) - mean(group0),
        where group 1 is the target group

        Parameters
        ----------
        df_parts: pd.DataFrame
            DataFrame with sequence parts.
        split_kws: dict, default=SequenceFeature.get_split_kws
            Nested dictionary with parameter dictionary for each chosen split_type.
        df_scales: pd.DataFrame, default=SequenceFeature.load_scales
            DataFrame with default amino acid scales.
        y: array-like, shape (n_samples)
            Class labels for samples in df_parts.
        accept_gaps: bool, default=False
            Whether to accept missing values by enabling omitting for computations (if True).
        verbose: bool, default=True
            Whether to print progress information about the algorithm (if True).

        Returns
        -------
        abs_mean_dif: array-like, shape (n_features)
            Absolute mean differences of feature values between samples of two groups.
        std_test: array-like, shape (n_features)
            Standard deviations of feature values in test group.
        feat_names: list of strings
            Names of all possible features for combination of Parts, Splits, and Scales.
        """
        # Input (df_parts, split_kws, df_scales, y) checked in main method (CPP.run())
        mask_0 = [True if x == 0 else False for x in y]
        mask_1 = [True if x == 1 else False for x in y]
        splittings, labels_ps = splitting(split_kws=split_kws, df_parts=df_parts)
        list_scales = list(df_scales)
        dict_all_scales = {col: dict(zip(df_scales.index.to_list(), df_scales[col])) for col in list_scales}
        # Multiprocessing for filtering of features
        n_processes = min([os.cpu_count(), len(list_scales)])
        scale_chunks = np.array_split(list_scales, n_processes)
        args = zip(scale_chunks, repeat(dict_all_scales), repeat(labels_ps), repeat(splittings),
                   repeat(accept_gaps), repeat(mask_0), repeat(mask_1), repeat(verbose))
        with mp.get_context("spawn").Pool(processes=n_processes) as pool:
            result = pool.starmap(_pre_filtering_info, args)
        abs_mean_dif = np.concatenate([x[0] for x in result])
        std_test = np.concatenate([x[1] for x in result])
        feat_names = np.concatenate([x[2] for x in result])
        return abs_mean_dif, std_test, feat_names

    # Summary and test statistics for feature matrix based on classification by labels
    @staticmethod
    def _mean_dif(X=None, y=None):
        """ Get mean difference for values in X (feature matrix) based on y (labels)

        Parameters
        ----------
        X: array-like or sparse matrix, shape (n_samples, n_features)
            Feature values of samples.
        y: array-like, shape (n_samples)
            Class labels for samples in X.

        Returns
        -------
        mean_difs: array-like, shape (n_features)
            Mean differences of feature values between samples of two groups.
        """
        mask_0 = [True if x == 0 else False for x in y]
        mask_1 = [True if x == 1 else False for x in y]
        mean_difs = np.mean(X[mask_1], axis=0) - np.mean(X[mask_0], axis=0)
        return mean_difs

    @staticmethod
    def _std(X=None, y=None, group=1):
        """Get standard deviation (std) for data sets points with group label

        Parameters
        ----------
        X: array-like or sparse matrix, shape (n_samples, n_features)
            Feature values of samples.
        y: array-like, shape (n_samples)
            Class labels for samples in X.
        group: integer, default=1
            Class/Group label.

        Returns
        -------
        group_std: array-like, shape (n_features)
            Standard deviations of feature values in specified group.
        """
        if group not in y:
            raise ValueError("'group' must be in 'y'")
        mask = [True if x == group else False for x in y]
        group_std = np.std(X[mask], axis=0)
        return group_std

    @staticmethod
    def _auc(X=None, y=None):
        """Get adjusted Area Under the Receiver Operating Characteristic Curve (ROC AUC)
        comparing, for each feature, groups (given by y (labels)) by feature values in X (feature matrix).

        Parameters
        ----------
        X: array-like or sparse matrix, shape (n_samples, n_features)
            Feature values of samples.
        y: array-like, shape (n_samples)
            Class labels for samples in X.

        Returns
        -------
        auc: array-like, shape (n_features)
            Scores of adjusted ROC AUC analysis (-0.5 to 0.5) for each featue.

        Notes
        -----
        Adjusted AUC ranges from -0.5 to 0.5 meaning that all feature values in the negative resp. positive
            class are higher. An AUC=0 means that the feature values
        """
        # Multiprocessing for AUC computation
        auc = np.apply_along_axis((lambda x: roc_auc_score(y, x) - 0.5), 0, X)
        auc = np.round(auc, 3)
        return auc

    @staticmethod
    def _mean_stat(X=None, y=None, parametric=False, p_cor=None):
        """Statistical comparison of central tendency between two groups for each feature.

        Parameters
        ----------
        X: array-like or sparse matrix, shape (n_samples, n_features)
            Feature values of samples.
        y: array-like, shape (n_samples)
            Class labels for samples in X.
        parametric: bool, default=True
            Whether to use ttest (parametric) or Mann-Whitney test (non-parametric) for p-value computation.
        p_cor: string, default=None
            Name of method to be used for p-value adjustment (e.g., bh_fdr for Benjamini-Hochberg method).

        Returns
        -------
        p_vals: array-like, shape (n_features)
            P-values of statical comparison between two groups for each feature.
        p-str: string
            Name of method used for p-value calculation.
        """
        mask_0 = [True if x == 0 else False for x in y]
        mask_1 = [True if x == 1 else False for x in y]
        if parametric:
            p_vals = stats.ttest_ind(X[mask_1], X[mask_0], nan_policy="omit")[1]
            p_str = "p_val_ttest_indep"
        else:
            t = lambda x1, x2: stats.mannwhitneyu(x1, x2, alternative="two-sided")[1]   # Test statistic
            c = lambda x1, x2: np.mean(x1) != np.mean(x2) or np.std(x1) != np.std(x2)   # Test condition
            p_vals = np.round([t(col[mask_1], col[mask_0]) if c(col[mask_1], col[mask_0]) else 1
                              for col in X.T], 10)
            p_str = "p_val_mann_whitney"
        if p_cor is not None:
            p_vals = _p_correction(p_vals=p_vals, p_cor=p_cor)
            p_str = "p_val_" + p_cor
        return p_vals, p_str

    def add_stat(self, df=None, X=None, y=None, parametric=False):
        """Add summary statistics of feature matrix (X) for given labels (y) to df, where p-values
        are calculated via a parametric or non-parametric test.

        Parameters
        ----------
        df: pd.DataFrame
            Feature DataFrame to add statistics.
        X: array-like or sparse matrix, shape (n_samples, n_features)
            Feature values of samples.
        y: array-like, shape (n_samples)
            Class labels for samples in X.
        parametric: bool, default=False
            Whether to use parametric (T-test) or non-parametric (U-test) test for p-value computation.
        Returns
        -------
        df: pd.DataFrame
            Feature DataFrame including statistics for comparing two given groups.
        """
        df = df.copy()
        columns_input = list(df)
        check_feat_matrix(X=X, y=y)
        df[ut.COL_ABS_AUC] = abs(self._auc(X=X, y=y))
        df[ut.COL_MEAN_DIF] = self._mean_dif(X=X, y=y)
        if ut.COL_ABS_MEAN_DIF not in list(df):
            df[ut.COL_ABS_MEAN_DIF] = abs(self._mean_dif(X=X, y=y))
        df[ut.COL_STD_TEST] = self._std(X=X, y=y, group=1)
        df[ut.COL_STD_REF] = self._std(X=X, y=y, group=0)
        p_val, p_str = self._mean_stat(X=X, y=y, parametric=parametric)
        df[p_str] = p_val
        p_val, p_str_fdr = self._mean_stat(X=X, y=y, parametric=parametric, p_cor="fdr_bh")
        df[p_str_fdr] = p_val
        cols_stat = [ut.COL_ABS_AUC, ut.COL_ABS_MEAN_DIF, ut.COL_MEAN_DIF,
                     ut.COL_STD_TEST, ut.COL_STD_REF,
                     p_str, p_str_fdr]
        cols_in = [x for x in columns_input if x not in cols_stat and x != ut.COL_FEATURE]
        columns = [ut.COL_FEATURE] + cols_in + cols_stat
        df = df[columns]
        cols_round = [x for x in cols_stat if x not in [p_str, p_str_fdr]]
        df[cols_round] = df[cols_round].round(6)
        return df

