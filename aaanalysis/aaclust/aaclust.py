"""
This is a script for the AAclust clustering wrapper method.
"""
import numpy as np
from typing import Type
from typing import Optional, Dict, Union, List, Tuple
import inspect
from inspect import isclass
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.base import ClusterMixin
from sklearn.exceptions import ConvergenceWarning
import warnings

from aaanalysis.aaclust._aaclust_bic import bic_score
import aaanalysis.utils as ut
from aaanalysis.aaclust._aaclust import (estimate_lower_bound_n_clusters, optimize_n_clusters, merge_clusters,
                                         compute_centers, compute_medoids)
from aaanalysis.aaclust._aaclust_statics import compute_correlation, name_clusters
from aaanalysis.template_classes import Wrapper

# I Helper Functions
# Check parameter functions
def check_mode_class(model_class=None):
    """"""
    # Check if model_class is actually a class and not an instance
    if not isclass(model_class):
        raise ValueError(f"'{model_class}' is not a model class. Please provide a valid model class.")
    # Check if model is callable
    if not callable(getattr(model_class, "__call__", None)):
        raise ValueError(f"'{model_class}' is not a callable model.")
    return model_class

def check_model_kwargs(model_class=None, model_kwargs=None):
    """
    Check if the provided model has 'n_clusters' as a parameter.
    Filter the model_kwargs to only include keys that are valid parameters for the model.
    """
    model_kwargs = model_kwargs or {}
    if model_class is None:
        raise ValueError("'model_class' must be provided.")
    list_model_args = list(inspect.signature(model_class).parameters.keys())
    # Check if 'n_clusters' is a parameter of the model
    if "n_clusters" not in list_model_args:
        error = f"'n_clusters' should be an argument in the given 'model' ({model_class})."
        raise ValueError(error)
    # Filter model_kwargs to only include valid parameters for the model
    not_valid_kwargs = [x for x in model_kwargs if x not in list_model_args]
    if len(not_valid_kwargs):
        raise ValueError(f"'model_kwargs' contains non valid arguments: {not_valid_kwargs}")
    return model_kwargs


def check_merge_metric(merge_metric=None):
    """"""
    if merge_metric is not None and merge_metric not in ut.LIST_METRICS:
        error = f"'merge_metric' should be None or one of following: {ut.LIST_METRICS}"
        raise ValueError(error)


# Check parameter matching functions
def check_match_X_names(X=None, names=None, accept_none=True):
    """"""
    if accept_none and names is None:
        return
    n_samples, n_features = X.shape
    if n_samples != len(names):
        raise ValueError(f"n_samples does not match for 'X' ({len(X)}) and 'names' ({len(names)}).")


def check_match_X_n_clusters(X=None, n_clusters=None, accept_none=True):
    """"""
    if accept_none and n_clusters is None:
        return
    n_samples, n_features = X.shape
    n_unique_samples = len(set(map(tuple, X)))
    if n_samples < n_clusters:
        raise ValueError(f"n_samples={n_samples} (in 'X') should be >= 'n_clusters' ({n_clusters})")
    if n_unique_samples < n_clusters:
        raise ValueError(f"'n_clusters' ({n_clusters}) should be >= n_unique_samples={n_unique_samples} (in 'X').")


# Post check functions
def post_check_n_clusters(n_clusters_actual=None, n_clusters=None):
    """Check if n_clusters set properly"""
    if n_clusters is not None and n_clusters_actual < n_clusters:
        warnings.warn(f"'n_clusters' was reduced from {n_clusters} to {n_clusters_actual} "
                      f"during AAclust algorithm.", ConvergenceWarning)


# II Main Functions
class AAclust(Wrapper):
    """
    A k-optimized clustering wrapper for selecting redundancy-reduced sets of numerical scales.

    AAclust uses clustering models that require a pre-defined number of clusters (k, set by ``n_clusters``),
    such as k-means or other `scikit-learn clustering models <https://scikit-learn.org/stable/modules/clustering.html>`_.
    AAclust optimizes the value of k by utilizing Pearson correlation and then selects a representative sample ('medoid')
    for each cluster closest to the center, resulting in a redundancy-reduced sample set. See [Breimann23a]_.

    Parameters
    ----------
    model_class
        A clustering model class with ``n_clusters`` parameter. This class will be instantiated during the ``fit`` method.
    model_kwargs
        Keyword arguments to pass to the selected clustering model.
    verbose
        If ``True``, verbose outputs are enabled.

    Attributes
    ----------
    model : object
        The instantiated clustering model object after calling the ``fit`` method.
    n_clusters : int
        Number of clusters obtained by AAclust.
    labels_ : `array-like, shape (n_samples, )`
        Cluster labels in the order of samples in ``X``.
    centers_ : `array-like, shape (n_clusters, n_features)`
        Average scale values corresponding to each cluster.
    center_labels_ : `array-like, shape (n_clusters, )`
        Cluster labels for each cluster center.
    medoids_ : `array-like, shape (n_clusters, n_features)`
        Representative samples, one for each cluster.
    medoid_labels_ :  `array-like, shape (n_clusters, )`
        Cluster labels for each medoid.
    is_medoid_ : `array-like, shape (n_samples, )`
        Array indicating samples being medoids (1) or not (0). Same order as ``labels_``.
    medoid_names_ : list
        Names of the medoids. Set if ``names`` is provided to ``fit``.

    Notes
    -----
    * All attributes are set during ``.fit`` and can be directly accessed.
    * AAclust is designed primarily for amino acid scales but can be used for any set of numerical indices.

    See Also
    --------
    * Scikit-learn `clustering model classes <https://scikit-learn.org/stable/modules/clustering.html>`_.

    """
    def __init__(self,
                 model_class: Type[ClusterMixin] = KMeans,
                 model_kwargs: Optional[Dict] = None,
                 verbose: bool = False):
        # Model parameters
        model_class = check_mode_class(model_class=model_class)
        if model_kwargs is None and model_class is KMeans:
            model_kwargs = dict(n_init="auto")
        model_kwargs = check_model_kwargs(model_class=model_class, model_kwargs=model_kwargs)
        self.model_class = model_class
        self._model_kwargs = model_kwargs
        self._verbose = ut.check_verbose(verbose)
        # Output parameters (set during model fitting)
        self.model : Optional[ClusterMixin] = None
        self.n_clusters: Optional[int] = None
        self.labels_: Optional[ut.ArrayLike1D] = None
        self.centers_: Optional[ut.ArrayLike1D] = None
        self.center_labels_: Optional[ut.ArrayLike1D] = None
        self.medoids_: Optional[ut.ArrayLike1D] = None
        self.medoid_labels_: Optional[ut.ArrayLike1D] = None
        self.is_medoid_: Optional[ut.ArrayLike1D] = None
        self.medoid_names_: Optional[List[str]] = None

    @ut.catch_runtime_warnings()
    def fit(self,
            X: ut.ArrayLike2D,
            n_clusters: Optional[int] = None,
            on_center: bool = True,
            min_th: float = 0,
            merge_metric: Union[str, None] = "euclidean",
            names: Optional[List[str]] = None) -> "AAclust":
        """
        Applies AAclust algorithm to feature matrix (``X``).

        AAclust determines the optimal number of clusters, k, without pre-specification. It partitions data (``X``) into
        clusters by maximizing the within-cluster Pearson correlation beyond the ``min_th`` threshold. The quality of
        clustering is either based on the minimum Pearson correlation of all members (``on_center=False``) or between
        the cluster center and its members (``on_center=True``), using either the 'min_cor_all' or 'min_cor_center'
        function, respectively, as described in [Breimann23a]_.

        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        n_clusters
            Pre-defined number of clusters. If provided, k is not optimized. Must be 0 > n_clusters > n_samples.
        min_th
            Pearson correlation threshold for clustering (between 0 and 1).
        on_center
            If ``True``, ``min_th`` is applied to the cluster center. Otherwise, to all cluster members.
        merge_metric
            Metric used as similarity measure for optional cluster merging:

             - ``None``: No merging is performed
             - ``correlation``: Pearson correlation
             - ``euclidean``: Euclidean distance
             - ``manhattan``: Manhattan distance
             - ``cosine``: Cosine distance

        names
            Sample names. If provided, sets :attr:`AAclust.medoid_names_` attribute.

        Returns
        -------
        AAclust
            The fitted instance of the AAclust class, allowing direct attribute access.

        Notes
        -----
        - Sets all attributes of the :class:`aanalysis.AAclust` class.

        - The AAclust algorithm consists of three main steps:
            1. Estimate the lower bound of k.
            2. Refine k (recursively) using the chosen quality metric.
            3. Optionally, merge smaller clusters as directed by the ``merge_metric``.

        - A representative scale (medoid) closest to each cluster center is selected for redundancy reduction.

        See Also
        --------
        * :func:`sklearn.metrics.pairwise_distances` were used as distances for merging.

        Warnings
        --------
        * All RuntimeWarnings during the AAclust algorithm are caught and bundled into one RuntimeWarning.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        ut.check_list(name="names", val=names, accept_none=True)
        ut.check_number_range(name="mint_th", val=min_th, min_val=0, max_val=1, just_int=False, accept_none=False)
        ut.check_number_range(name="n_clusters", val=n_clusters, min_val=1, just_int=True, accept_none=True)
        check_merge_metric(merge_metric=merge_metric)
        ut.check_bool(name="on_center", val=on_center)

        check_match_X_n_clusters(X=X, n_clusters=n_clusters, accept_none=True)
        check_match_X_names(X=X, names=names, accept_none=True)

        args = dict(model=self.model_class, model_kwargs=self._model_kwargs, min_th=min_th, on_center=on_center,
                    verbose=self._verbose)

        # Clustering using given clustering models
        if n_clusters is not None:
            self.model = self.model_class(n_clusters=n_clusters, **self._model_kwargs)
            labels = self.model.fit(X).labels_.tolist()

        # Clustering using AAclust algorithm
        else:
            # Step 1.: Estimation of lower bound of k (number of clusters)
            n_clusters_lb = estimate_lower_bound_n_clusters(X, **args)
            # Step 2. Optimization of k by recursive clustering
            n_clusters = optimize_n_clusters(X, n_clusters=n_clusters_lb, **args)
            self.model = self.model_class(n_clusters=n_clusters, **self._model_kwargs)
            labels = self.model.fit(X).labels_.tolist()
            # Step 3. Cluster merging (optional)
            if merge_metric is not None:
                labels = merge_clusters(X, labels=labels, min_th=min_th, on_center=on_center,
                                        metric=merge_metric, verbose=self._verbose)
                n_clusters = len(set(labels))

        # Obtain cluster centers and medoids
        medoids, medoid_labels, medoid_ind = compute_medoids(X, labels=labels)
        centers, center_labels = compute_centers(X, labels=labels)

        # Save results in output parameters
        post_check_n_clusters(n_clusters_actual=len(set(labels)), n_clusters=n_clusters)
        self.n_clusters = len(set(labels))
        self.labels_ = np.array(labels)
        self.centers_ = centers
        self.center_labels_ = center_labels
        self.medoids_ = medoids     # Representative scales
        self.medoid_labels_ = medoid_labels
        self.is_medoid_ = np.array([i in medoid_ind for i in range(0, len(labels))])
        if names is not None:
            self.medoid_names_ =  [names[i] for i in medoid_ind]
        return self

    @staticmethod
    @ut.catch_runtime_warnings()
    def eval(X: ut.ArrayLike2D,
             labels:ut.ArrayLike1D = None
             ) -> Tuple[float, float, float]:
        """Evaluates the quality of clustering using three established measures.

        Clustering quality is quantified using:

            - ``BIC`` (Bayesian Information Criterion): Reflects the goodness of fit for the clustering while accounting for
              the number of clusters and parameters. The BIC value can range from negative infinity to positive infinity.
              A higher BIC indicates superior clustering quality.
            - ``CH`` (Calinski-Harabasz Index): Represents the ratio of between-cluster dispersion mean to the within-cluster dispersion.
              The CH value ranges from 0 to positive infinity. A higher CH score suggests better-defined clustering.
            - ``SC`` (Silhouette Coefficient): Evaluates the proximity of each data point in one cluster to the points in the neighboring clusters.
              The SC score lies between -1 and 1. A value closer to 1 implies better clustering.


        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        labels : `array-like, shape (n_samples, )`
            Cluster labels for each sample in ``X``.

        Returns
        -------
        BIC : float
            BIC value for clustering.
        CH : float
            CH value for clustering.
        SC : float
            SC value for clustering.

        Notes
        -----
        BIC was modified to align with the SC and CH, so that higher values signify better clustering
        contrary to conventional BIC implementation favoring lower values. See [Breimann23a]_.

        See Also
        --------
        * :func:`sklearn.metrics.calinski_harabasz_score`.
        * :func:`sklearn.metrics.silhouette_score`.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        labels = ut.check_labels(labels=labels)
        ut.check_match_X_labels(X=X, labels=labels)
        # Bayesian Information Criterion
        BIC = bic_score(X, labels)
        # Calinski-Harabasz Index
        CH = calinski_harabasz_score(X, labels)
        if np.isnan(CH):
            CH = 0
            warnings.warn("CH was set to 0 because sklearn.metric.calinski_harabasz_score returned NaN.", RuntimeWarning)
        # Silhouette Coefficient
        SC = silhouette_score(X, labels)
        if np.isnan(SC):
            SC = -1
            warnings.warn("SC was set to -1 because sklearn.metric.silhouette_score returned NaN.", RuntimeWarning)
        return BIC, CH, SC

    @staticmethod
    def name_clusters(X: ut.ArrayLike2D,
                      labels: ut.ArrayLike1D = None,
                      names: List[str] = None
                      ) -> List[str]:
        """
        Assigns names to clusters based on the frequency of names.

        Names with higher frequency are prioritized. If a name is already assigned to a cluster,
        or the cluster contains one sample, its name is set to 'unclassified'.

        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        labels : `array-like, shape (n_samples, )`
            Cluster labels for each sample in ``X``.
        names
            List of scale names corresponding to each sample.

        Returns
        -------
        cluster_names : list
            A list of renamed clusters based on names.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        labels = ut.check_labels(labels=labels)
        ut.check_list(name="names", val=names, accept_none=False)
        ut.check_match_X_labels(X=X, labels=labels)
        check_match_X_names(X=X, names=names, accept_none=False)
        # Get cluster names
        cluster_names = name_clusters(X, labels=labels, names=names)
        return cluster_names

    @staticmethod
    def comp_centers(X: ut.ArrayLike2D,
                     labels: ut.ArrayLike1D = None
                     ) -> Tuple[ut.ArrayLike1D, ut.ArrayLike1D]:
        """
        Computes the center of each cluster based on the given labels.

        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        labels : `array-like, shape (n_samples, )`
            Cluster labels for each sample in ``X``.

        Returns
        -------
        centers : `array-like, shape (n_clusters, )`
            The computed center for each cluster.
        center_labels : `array-like, shape (n_clusters, )`
            The labels associated with each computed center.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        labels = ut.check_labels(labels=labels)
        ut.check_match_X_labels(X=X, labels=labels)
        # Get cluster centers
        centers, center_labels = compute_centers(X, labels=labels)
        return centers, center_labels

    @staticmethod
    def comp_medoids(X: ut.ArrayLike2D,
                     labels: ut.ArrayLike1D = None
                     ) -> Tuple[ut.ArrayLike1D, ut.ArrayLike1D]:
        """
        Computes the medoid of each cluster based on the given labels.

        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        labels : `array-like, shape (n_samples, )`
            Cluster labels for each sample in ``X``.

        Returns
        -------
        medoids : `array-like, shape (n_clusters, )`
            The medoid for each cluster.
        medoid_labels : `array-like, shape (n_clusters, )`
            The labels corresponding to each medoid.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        labels = ut.check_labels(labels=labels)
        ut.check_match_X_labels(X=X, labels=labels)
        # Get cluster medoids
        medoids, medoid_labels, _ = compute_medoids(X, labels=labels)
        return medoids, medoid_labels

    @staticmethod
    def comp_correlation(X: ut.ArrayLike2D,
                         X_ref: ut.ArrayLike2D,
                         labels: ut.ArrayLike1D = None,
                         labels_ref: ut.ArrayLike1D = None,
                         n: int = 3,
                         positive: bool = True,
                         on_center: bool = False
                         ) -> List[str]:
        """
        Computes the Pearson correlation of given data with reference data.

        Parameters
        ----------
        X : `array-like, shape (n_samples, n_features)`
            Feature matrix. Rows correspond to scales and columns to amino acids.
        X_ref : `array-like, shape (n_samples, n_features)`
            Feature matrix of reference data.
        labels : `array-like, shape (n_samples, )`
            Cluster labels for each sample in ``X``.
        labels_ref  : `array-like, shape (n_samples, )`
            Cluster labels for the reference data.
        n
            Number of top centers to consider based on correlation strength.
        positive
            If True, considers positive correlations. Else, negative correlations.
        on_center
            If True, correlation is computed with cluster centers. Otherwise, with all cluster members.

        Returns
        -------
        list_top_center_name_corr : list
            Names and correlations of centers having the strongest (positive/negative) correlation with test data samples.

        See Also
        --------
        * :func:`numpy.corrcoe` was used to compute the correlation.
        """
        # Check input
        X = ut.check_X(X=X)
        ut.check_X_unique_samples(X=X)
        labels = ut.check_labels(labels=labels)
        ut.check_match_X_labels(X=X, labels=labels)
        X = ut.check_X(X=X_ref)
        ut.check_X_unique_samples(X=X_ref)
        labels = ut.check_labels(labels=labels_ref)
        ut.check_match_X_labels(X=X_ref, labels=labels_ref)
        ut.check_number_range(name="n", val=n, min_val=2)
        # Get correlations
        list_top_center_name_corr = compute_correlation(X, X_ref, labels=labels, labels_ref=labels_ref,
                                                        n=n, positive=positive, on_center=on_center)
        return list_top_center_name_corr

    @staticmethod
    def comp_coverage(names=None, names_ref=None):
        """Computes coverage of """

