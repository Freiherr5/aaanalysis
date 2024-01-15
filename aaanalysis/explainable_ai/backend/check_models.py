"""
This is a script for common check function for the explainable AI models.
"""
import numpy as np
import aaanalysis.utils as ut

def check_match_list_model_classes_kwargs(list_model_classes=None, list_model_kwargs=None):
    """Check length match of list_model_classes and list_model_kwargs"""
    n_models = len(list_model_classes)
    n_args = len(list_model_kwargs)
    if n_models != n_args:
        raise ValueError(f"Length of 'list_model_kwargs' (n={n_args}) should match to 'list_model_classes' (n{n_models}")


def check_match_labels_X(labels=None, X=None):
    """Check if labels binary classification task labels"""
    n_samples = X.shape[0]
    labels = ut.check_labels(labels=labels, len_requiered=n_samples)
    unique_labels = set(labels)
    if len(unique_labels) != 2:
        raise ValueError(f"'labels' should contain 2 unique labels ({unique_labels})")
    # The higher label is considered as the positive (test) class
    label_test = list(sorted(unique_labels))[1]
    labels = np.asarray([1 if x == label_test else 0 for x in labels])
    return labels


def check_match_X_is_selected(X=None, is_selected=None):
    """Check if length of X and feature selection mask (is_selected) matches"""
    n_features = X.shape[1]
    n_feat_is_selected = len(is_selected[0])
    if n_features != n_feat_is_selected:
        raise ValueError(f"Number of features from 'X' ({n_features}) does not match "
                         f"with 'is_selected' attribute ({n_feat_is_selected})")


