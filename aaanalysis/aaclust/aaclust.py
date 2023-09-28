"""
This is a script for the AAclust clustering wrapper method.
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from typing import Optional, Callable, Dict, Union, List
import inspect

import aaanalysis.utils as ut
from aaanalysis.aaclust._aaclust import estimate_lower_bound_n_clusters, optimize_n_clusters, merge_clusters
from aaanalysis.aaclust._aaclust_statics import compute_centers, compute_medoids, compute_corr
from aaanalysis.aaclust._aaclust_name_clusters import name_clusters


# I Helper Functions
# Check functions
def check_model(model=None, model_kwargs=None, except_None=True):
    """"""
    if except_None:
        return model_kwargs
    list_model_args = list(inspect.signature(model).parameters.keys())
    if "n_clusters" not in list_model_args:
        error = f"'n_clusters' should be argument in given clustering 'model' ({model})."
        raise ValueError(error)
    model_kwargs = {x: model_kwargs[x] for x in model_kwargs if x in list_model_args}
    return model_kwargs

def check_merge_metric(merge_metric=None):
    """"""
    if merge_metric is not None and merge_metric not in ut.LIST_METRICS:
        error = f"'merge_metric' should be None or one of following: {ut.LIST_METRICS}"
        raise ValueError(error)

def check_feat_matrix_n_clust_match(X=None, n_clusters=None):
    """"""
    n_samples, n_features = X.shape
    if n_samples <= n_clusters:
        raise ValueError(f"'X' must contain more samples ({n_samples}) then 'n_clusters' ({n_clusters})")


# II Main Functions
# TODO check, interface, testing, simplifying (Remove functions if not needed)
class AAclust:
    """
    A k-optimized clustering wrapper for selecting redundancy-reduced sets of numerical scales.

    AAclust is designed primarily for amino acid scales but can be used for any set of numerical indices.
    It uses clustering models like from the `scikit-learn clustering model <https://scikit-learn.org/stable/modules/clustering.html>`_
    that require a pre-defined number of clusters (k). Utilizing Pearson correlation as similarity measure.
    AAclust optimizes the value of k, selects a representative sample ('medoid')for each cluster closest to
    the center, resulting in a redundancy-reduced sample set.

    Parameters
    ----------
    model
        A clustering model with ``n_clusters`` parameter.
    model_kwargs
        Keyword arguments to pass to the selected clustering model.
    verbose
        If ``True``, verbose outputs are enabled.

    Attributes
    ----------
    n_clusters
        Number of clusters obtained by AAclust.
    labels_
        Cluster labels in the order of samples in the feature matrix.
    centers_
        Average scale values corresponding to each cluster.
    center_labels_
        Cluster labels for each cluster center.
    medoids_
        Representative samples (one for each cluster center).
    medoid_labels_
        Cluster labels for each medoid.
    medoid_ind_
        Indices of the chosen medoids within the original dataset.
    """
    def __init__(self,
                 model: Optional[Callable] = None,
                 model_kwargs: Optional[Dict] = None,
                 verbose: bool = False):
        # Model parameters
        self.model = model or KMeans
        model_kwargs = check_model(model=self.model, model_kwargs=model_kwargs or {})
        self._model_kwargs = model_kwargs
        self._verbose = ut.check_verbose(verbose)
        # Output parameters (set during model fitting)
        self.n_clusters: Optional[int] = None
        self.labels_: Optional[ut.ArrayLikeInt] = None
        self.centers_: Optional[ut.ArrayLikeFloat] = None
        self.center_labels_: Optional[ut.ArrayLikeInt] = None
        self.medoids_: Optional[ut.ArrayLikeAny] = None
        self.medoid_labels_: Optional[ut.ArrayLikeInt] = None
        self.medoid_ind_: Optional[ut.ArrayLikeInt] = None

    def fit(self,
            X: ut.ArrayLikeFloat,
            names: Optional[List[str]] = None,
            on_center: bool = True,
            min_th: float = 0,
            merge_metric: Union[str, None] = "euclidean",
            n_clusters: Optional[int] = None
            ) -> Optional[List[str]]:
        """
        Fit the AAclust model on the data, optimizing cluster formation using Pearson correlation.

        AAclust determines the optimal number of clusters, k, without pre-specification. It partitions data(X) into
        clusters by maximizing the within-cluster Pearson correlation beyond the 'min_th' threshold. The quality of
        clustering is either based on the minimum Pearson correlation of all members ('min_cor all') or between
        the cluster center and its members ('min_cor center'), governed by `on_center`.

        The clustering undergoes three stages:
        1. Estimate the lower bound of k.
        2. Refine k using the chosen quality metric.
        3. Optionally, merge smaller clusters, as directed by `merge_metric`.

        Finally, a representative scale (medoid) closest to each cluster center is chosen for redundancy reduction.

        Parameters
        ----------
        X
            Feature matrix of shape (n_samples, n_features).
        names
            Sample names. If provided, returns names of the medoids.
        on_center
            If ``True``, the correlation threshold is applied to the cluster center. Otherwise, it's applied to all cluster members.
        min_th
            Pearson correlation threshold for clustering (between 0 and 1).
        merge_metric
            Metric used for optional cluster merging. Can be "euclidean", "pearson", or None (no merging).
        n_clusters
            Pre-defined number of clusters. If provided, AAclust uses this instead of optimizing k.

        Returns
        -------
        names_medoid
            Names of the medoids, if ``names`` is provided.

        Notes
        -----
        Set all attributes within the :class:`aanalysis.AAclust` class.

        """
        # Check input
        ut.check_number_range(name="mint_th", val=min_th, min_val=0, max_val=1, just_int=False, accept_none=False)
        X, names = ut.check_feat_matrix(X=X, y=names)
        check_merge_metric(merge_metric=merge_metric)
        check_feat_matrix_n_clust_match(X=X, n_clusters=n_clusters)
        args = dict(model=self.model, model_kwargs=self._model_kwargs, min_th=min_th, on_center=on_center,
                    verbose=self._verbose)
        
        # Clustering using given clustering models
        if n_clusters is not None:
            labels = self.model(n_clusters=n_clusters, **self._model_kwargs).fit(X).labels_.tolist()
        
        # Clustering using AAclust algorithm
        else:
            # Step 1.: Estimation of lower bound of k (number of clusters)
            n_clusters_lb = estimate_lower_bound_n_clusters(X, **args)
            # Step 2. Optimization of k by recursive clustering
            n_clusters = optimize_n_clusters(X, n_clusters=n_clusters_lb, **args)
            labels = self.model(n_clusters=n_clusters, **self._model_kwargs).fit(X).labels_.tolist()
            # Step 3. Cluster merging (optional)
            if merge_metric is not None:
                labels = merge_clusters(X, labels=labels, min_th=min_th, on_center=on_center, metric=merge_metric)

        # Obtain cluster centers and medoids
        medoids, medoid_labels, medoid_ind = compute_medoids(X, labels=labels)
        centers, center_labels = compute_centers(X, labels=labels)
        
        # Save results in output parameters
        self.n_clusters = len(set(labels))
        self.labels_ = np.array(labels)
        self.centers_ = centers
        self.center_labels_ = center_labels
        self.medoids_ = medoids     # Representative scales
        self.medoid_labels_ = medoid_labels
        self.medoid_ind_ = medoid_ind   # Index of medoids
        
        # Return labels of medoid if y is given
        if names is not None:
            names_medoid = [names[i] for i in medoid_ind]
            return names_medoid

    def evaluate(self):
        """Evaluate one or more results"""
        # TODO add evaluation function

    def name_clusters(self, names=None):
        """
        Assigns names to clusters based on scale names and their frequency.

        This method renames clusters based on the names of the scales in each cluster, with priority given to the
        most frequent scales. If the name is already used or does not exist, it defaults to 'name_unclassified'.

        Parameters
        ----------
        names : list, optional
            List of scale names corresponding to each sample.

        Returns
        -------
        cluster_names : list
            A list of renamed clusters based on scale names.
        """
        # Check input
        ut.check_list(name='names', val=names)
        # Get internal values set during fit
        labels = self.labels_
        dict_medoids = dict(zip(self.medoid_labels_, self.medoid_ind_))
        # Obtain cluster names
        cluster_names = name_clusters(names=names, labels=labels, dict_medoids=dict_medoids)
        return cluster_names

    @staticmethod
    def compute_centers(X, labels=None):
        """
        Computes the center of each cluster based on the given labels.

        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            Feature matrix where `n_samples` is the number of samples and `n_features` is the number of features.
        labels : list or array-like, optional
            Cluster labels for each sample in X.

        Returns
        -------
        centers : array-like
            The computed center for each cluster.
        center_labels : array-like
            The labels associated with each computed center.
        """
        centers, center_labels = compute_centers(X, labels=labels)
        return centers, center_labels

    @staticmethod
    def compute_medoids(X, labels=None):
        """
        Computes the medoid of each cluster based on the given labels.

        Parameters
        ----------
         X : array-like, shape (n_samples, n_features)
            Feature matrix where `n_samples` is the number of samples and `n_features` is the number of features.
        labels : list or array-like, optional
            Cluster labels for each sample in X.

        Returns
        -------
        medoids : array-like
            The medoid for each cluster.
        medoid_labels : array-like
            The labels corresponding to each medoid.
        medoid_ind : array-like
            Indexes of medoids within the original data.
        """
        medoids, medoid_labels, medoid_ind = compute_medoids(X, labels=labels)
        return medoids, medoid_labels, medoid_ind

    @staticmethod
    def compute_corr(X, X_ref, labels=None, labels_ref=None, n=3, positive=True, on_center=False, except_unclassified=True):
        """
        Computes the correlation of given data with reference data.

        The reference data are typically the cluster centers or cluster medoids.

        Parameters
        ----------
        X : array-like
            Test feature matrix.
        X_ref : array-like
            Reference feature matrix.
        labels : list or array-like, optional
            Cluster labels for the test data.
        labels_ref : list or array-like, optional
            Cluster labels for the reference data.
        n : int, default = 3
            Number of top centers to consider based on correlation strength.
        positive : bool, default = True
            If True, considers positive correlations. Else, negative correlations.
        on_center : bool, default = False
            If True, correlation is computed with cluster centers. Otherwise, with all cluster members.

        Returns
        -------
        list_top_center_name_corr : list of str
            Names and correlations of centers having strongest (positive/negative) correlation with test data samples.
        """
        # Check input
        X, labels = ut.check_feat_matrix(X=X, y=labels)
        X_ref, labels_ref = ut.check_feat_matrix(X=X_ref, y=labels_ref)
        list_top_center_name_corr = compute_corr(X, X_ref, labels=labels, labels_ref=labels_ref,
                                                 n=n, positive=positive, on_center=on_center,
                                                 except_unclassified=except_unclassified)
        return list_top_center_name_corr

    @staticmethod
    def compute_coverage(names=None, names_ref=None):
        """Compute coverage of """

