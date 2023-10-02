"""
This is a script for three main steps of the AAclust algorithm and further helper functions.

AAclust algorithm steps
1. Estimate lower bound for n_clusters
2. Optimization of n_clusters
3. Merge clusters

"""
import pandas as pd
import numpy as np
from collections import OrderedDict
from sklearn.metrics.pairwise import pairwise_distances

import aaanalysis.utils as ut


# I Helper Functions
def _cluster_center(X):
    """Compute cluster center (i.e., arithmetical mean over all data points/observations of a cluster)"""
    return X.mean(axis=0)[np.newaxis, :]


def compute_centers(X, labels=None):
    """Obtain cluster centers and their labels"""
    center_labels = list(OrderedDict.fromkeys(labels))
    list_masks = [[True if i == label else False for i in labels] for label in center_labels]
    centers = np.concatenate([_cluster_center(X[mask]) for mask in list_masks]).round(3)
    return centers, np.array(center_labels)


def _cluster_medoid(X):
    """Obtain cluster medoids (i.e., scale closest to cluster center used as representative scale for a cluster)"""
    # Create new array with cluster center and given array
    center_X = np.concatenate([_cluster_center(X), X], axis=0)
    # Get index for scale with the highest correlation with cluster center
    ind_max = np.corrcoef(center_X)[0, 1:].argmax()
    return ind_max


def compute_medoids(X, labels=None):
    """Obtain cluster medoids and their labels"""
    unique_labels = list(OrderedDict.fromkeys(labels))
    list_masks = [[True if i == label else False for i in labels] for label in unique_labels]
    list_ind_max = [_cluster_medoid(X[mask]) for mask in list_masks]
    indices = np.array(range(0, len(labels)))
    medoid_ind = [indices[m][i] for m, i in zip(list_masks, list_ind_max)]
    medoid_labels = np.array([labels[i] for i in medoid_ind])
    medoids = np.array([X[i, :] for i in medoid_ind])
    return medoids, medoid_labels, medoid_ind


# Compute minimum correlation on center or all scales
def min_cor_center(X):
    """Get minimum for correlation of all columns with cluster center, defined as the mean values
    for each amino acid over all scales."""
    # Create new matrix including cluster center
    center_X = np.concatenate([_cluster_center(X), X], axis=0)
    # Get minimum correlation with mean values
    min_cor = np.corrcoef(center_X)[0, ].min()
    return min_cor


def min_cor_all(X):
    """Get minimum for pair-wise correlation of all columns in given matrix."""
    # Get minimum correlations minimum/ maximum distance for pair-wise comparisons
    min_cor = np.corrcoef(X).min()
    return min_cor


def get_min_cor(X, labels=None, on_center=True):
    """Compute minimum pair-wise correlation or correlation with cluster center for each cluster label
    and return minimum of obtained cluster minimums."""
    f = min_cor_center if on_center else min_cor_all
    if labels is None:
        return f(X)
    # Minimum correlations for each cluster (with center or all scales)
    unique_labels = list(OrderedDict.fromkeys(labels))
    list_masks = [[True if i == label else False for i in labels] for label in unique_labels]
    list_min_cor = [f(X[mask]) for mask in list_masks]
    # Minimum for all clusters
    min_cor = min(list_min_cor)
    return min_cor


# Get maximum distance on center or all scales
def get_max_dist(X, on_center=True, metric="euclidean"):
    """"""
    # Maximum distance for cluster
    if on_center:
        # Create new matrix including cluster center
        center_X = np.concatenate([_cluster_center(X), X], axis=0)
        # Get maximum distance with mean values
        max_dist = pairwise_distances(center_X, metric=metric)[0, ].max()
    else:
        # Get maximum distance for pair-wise comparisons
        max_dist = pairwise_distances(X, metric=metric).max()
    return max_dist


# II Main Functions
# 1. Step (Estimation of n clusters)
@ut.catch_convergence_warning()
def _estimate_lower_bound_n_clusters(X, model=None, model_kwargs=None, min_th=0.6, on_center=True, verbose=True):
    """
    Estimate the lower bound of the number of clusters (k).

    This function estimates the lower bound of the number of clusters by testing a range
    between 10% and 90% of all observations, incrementing in 10% steps.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Feature matrix where `n_samples` is the number of samples and `n_features` is the number of features.
    model : callable, optional
        k-based clustering model to use.
    model_kwargs : dict, optional
        Dictionary of keyword arguments to pass to the clustering model.
    min_th : float, optional, default = 0.6
        Minimum threshold of within-cluster Pearson correlation required for a valid clustering.
    on_center : bool, optional, default = True
        Whether the minimum correlation is computed for all observations within a cluster
        or just for the cluster center.
    verbose : bool, optional, default = False
        A flag to enable or disable verbose outputs.

    Returns
    -------
    n_clusters : int
        Estimated lower bound for the number of clusters (k).
    """
    if verbose:
        ut.print_out("1. Estimation of lower bound of k (number of clusters)", end="")
    f = lambda c: get_min_cor(X, labels=model(n_clusters=c, **model_kwargs).fit(X).labels_, on_center=on_center)
    # Create range between 10% and 90% of all scales (10% steps) as long as minimum correlation is lower than threshold
    n_samples, n_features = X.shape
    nclust_mincor = [(1, f(1))]
    step_number = 40
    for i in range(1, step_number, 1):
        n_clusters = max(1, int(n_samples*i/step_number))    # n cluster in 2.5% steps
        min_cor = f(n_clusters)
        if min_cor < min_th:   # Save only lower bounds
            nclust_mincor.append((n_clusters, min_cor))
        else:
            break
    # Select second highest lower bound (highest lower bound is faster but might surpass true bound)
    nclust_mincor.sort(key=lambda x: x[0], reverse=True)
    n_clusters = nclust_mincor[1][0] if len(nclust_mincor) > 1 else nclust_mincor[0][0]  # Otherwise, only existing one
    if verbose:
        ut.print_out(f": k={n_clusters}")
    return n_clusters

def estimate_lower_bound_n_clusters(X, model=None, model_kwargs=None, min_th=0.6, on_center=True, verbose=True):
    """Wrapper for _estimate_lower_bound_n_clusters to catch convergence warnings"""
    try:
        n_clusters = _estimate_lower_bound_n_clusters(X, model=model, model_kwargs=model_kwargs,
                                                      min_th=min_th, on_center=on_center,
                                                      verbose=verbose)
    except ut.ClusteringConvergenceException as e:
        n_clusters = e.distinct_clusters
    return n_clusters


# 2. Step (Optimization of n clusters)
@ut.catch_convergence_warning()
def _optimize_n_clusters(X, model=None, model_kwargs=None, n_clusters=None, min_th=0.5, on_center=True, verbose=True):
    """
    Optimize the number of clusters using a recursive algorithm.

    This function performs clustering in a recursive manner (through a while loop) to ensure
    that the minimum within-cluster correlation is achieved for all clusters. It is an efficiency
    optimized version of a step-wise algorithm where the `n_clusters` is incrementally increased
    until a stop condition is met.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Feature matrix where `n_samples` is the number of samples and `n_features` is the number of features.
    model : callable, optional
        k-based clustering model to use.
    model_kwargs : dict, optional
        Dictionary of keyword arguments to pass to the clustering model.
    n_clusters : int, optional
        Estimated number of clusters (k).
    min_th : float, optional, default = 0.5
        Minimum threshold of within-cluster Pearson correlation required for a valid clustering.
    on_center : bool, optional, default = True
        Whether the minimum correlation is computed for all observations within a cluster
        or just for the cluster center.
    verbose : bool, optional, default = False
        A flag to enable or disable verbose outputs.

    Returns
    -------
    n_clusters : int
        Optimized number of clusters (k) after the recursive clustering.
    """
    if verbose:
        objective_fct = "min_cor_center" if on_center else "min_cor_all"
        ut.print_out(f"2. Optimization of k by recursive clustering ({objective_fct}, min_th={min_th})", end="")

    n_samples, n_features = X.shape
    f = lambda c: get_min_cor(X, labels=model(n_clusters=c, **model_kwargs).fit(X).labels_, on_center=on_center)
    min_cor = f(n_clusters)
    # Recursive optimization of n_clusters via step-wise increase starting from lower bound
    step = max(1, min(int(n_samples/10), 5))    # Step size between 1 and 5
    while min_cor < min_th and n_clusters < n_samples:    # Stop condition of clustering
        n_clusters = min(n_clusters+step, n_samples) # Maximum of n_samples is allowed
        min_cor = f(n_clusters)
        # Exceeding of threshold -> Conservative adjustment of clustering parameters to meet true optimum
        if min_cor >= min_th and step != 1:
            n_clusters = max(1, n_clusters - step * 2)
            step = 1
            min_cor = f(n_clusters)
    if verbose:
        ut.print_out(f": k={n_clusters}")
    return n_clusters


def optimize_n_clusters(X, model=None, model_kwargs=None, n_clusters=None, min_th=0.5, on_center=True, verbose=True):
    """Wrapper for _optimize_n_clusters to catch convergence warnings"""
    try:
        n_clusters = _optimize_n_clusters(X, model=model, model_kwargs=model_kwargs,
                                          n_clusters=n_clusters, min_th=min_th, on_center=on_center,
                                          verbose=verbose)
    except ut.ClusteringConvergenceException as e:
        n_clusters = e.distinct_clusters
    return n_clusters


# 3. Step (Merging)
def _get_min_cor_cluster(X, labels=None, label_cluster=None, on_center=True):
    """Get min_cor for single cluster"""
    mask = [l == label_cluster for l in labels]
    min_cor = get_min_cor(X[mask], on_center=on_center)
    return min_cor


def _get_quality_measure(X, metric=None, labels=None, label_cluster=None, on_center=True):
    """Get quality measure single cluster given by feature matrix X, labels, and label of cluster"""
    mask = [l == label_cluster for l in labels]
    if metric == ut.METRIC_CORRELATION:
        return get_min_cor(X[mask], on_center=on_center)
    else:
        return get_max_dist(X[mask], on_center=on_center, metric=metric)


def _get_best_cluster(dict_clust_qm=None, metric=None):
    """Get cluster with the best quality measure: either highest minimum Pearson correlation
    or lowest distance measure"""
    if metric == ut.METRIC_CORRELATION:
        return max(dict_clust_qm, key=dict_clust_qm.get)
    else:
        return min(dict_clust_qm, key=dict_clust_qm.get)


def merge_clusters(X, n_max=5, labels=None, min_th=0.5, on_center=True, metric="correlation", verbose=True):
    """
    Merge small clusters into other clusters optimizing a given quality measure.

    This function merges clusters with sizes less than or equal to `n_max` into other clusters
    based on a specified quality measure (Pearson correlation or a distance metric).
    Merging is conducted only if the new assignment meets a minimum within-cluster Pearson
    correlation threshold defined by `min_th`.

    Parameters
    ----------
    X : array-like, shape (n_samples, n_features)
        Feature matrix where `n_samples` is the number of samples and `n_features` is the number of features.
    n_max : int, optional, default = 5
        Maximum cluster size for small clusters to be considered for merging.
    labels : array-like, shape (n_samples,), optional
        Initial cluster labels for observations.
    min_th : float, optional, default = 0.5
        Minimum threshold of within-cluster Pearson correlation required for merging.
    on_center : bool, optional, default = True
        Whether the minimum correlation is computed for all observations within a cluster
        or just for the cluster center.
    metric : str, optional, default = 'correlation'
        Quality measure used to optimize merging. Can be 'correlation' for maximum correlation
        or any valid distance metric like 'euclidean' for minimum distance.
    verbose : bool, optional, default = False
        A flag to enable or disable verbose outputs.

    Returns
    -------
    labels : array-like, shape (n_samples,)
        Cluster labels for observations after merging.
    """
    if verbose:
        ut.print_out("3. Cluster merging (optional)", end="")
    unique_labels = list(OrderedDict.fromkeys(labels))
    for n in range(1, n_max):
        s_clusters = [x for x in unique_labels if labels.count(x) == n]   # Smallest clusters
        b_clusters = [x for x in unique_labels if labels.count(x) > n]    # Bigger clusters (all others)
        # Assign scales from smaller clusters to cluster by optimizing for quality measure
        for s_clust in s_clusters:
            dict_clust_qm = {}  # Cluster to quality measure
            for b_clust in b_clusters:
                labels_ = [x if x != s_clust else b_clust for x in labels]
                args = dict(labels=labels_, label_cluster=b_clust, on_center=on_center)
                min_cor = _get_min_cor_cluster(X, **args)
                if min_cor >= min_th:
                    dict_clust_qm[b_clust] = _get_quality_measure(X, **args, metric=metric)
            if len(dict_clust_qm) > 0:
                b_clust_best = _get_best_cluster(dict_clust_qm=dict_clust_qm, metric=metric)
                labels = [x if x != s_clust else b_clust_best for x in labels]
    # Update labels (cluster labels are given in descending order of cluster size)
    sorted_labels = pd.Series(labels).value_counts().index  # sorted in descending order of size
    dict_update = {label: i for label, i in zip(sorted_labels, range(0, len(set(labels))))}
    labels = [dict_update[label] for label in labels]
    if verbose:
        ut.print_out(f": k={len(set(labels))}")
    return labels

