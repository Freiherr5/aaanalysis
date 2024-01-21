"""
This is a script for the backend of the ShapExplainer.fit() method.
"""
import numpy as np
import shap

import aaanalysis.utils as ut


LIST_VERBOSE_SHAP_EXPLAINERS = [shap.KernelExplainer]


# I Helper Functions
def _get_background_data(X, explainer_class=None, n_background_data=None):
    """Sample background data for Kernel explainer"""
    X = X.copy()
    if explainer_class == shap.KernelExplainer and n_background_data is not None:
        # Summarize background data using k-means if specified
        background_data = shap.kmeans(X, n_background_data)
    else:
        background_data = X
    return background_data


def _get_shap_values(shap_output, class_index=1):
    """Retrieve SHAP values for the specified class index from SHAP output."""
    # For other types of SHAP outputs (like those from specific explainers)
    if isinstance(shap_output, list) and len(shap_output) > class_index:
        shap_values = shap_output[class_index]
    else:
        shap_values = shap_output
    return shap_values


def _compute_shap_values(X, labels, model_class=None, model_kwargs=None,
                         explainer_class=None, explainer_kwargs=None,
                         class_index=1, n_background_data=None):
    """Fit a model and compute SHAP values using the provided SHAP Explainer."""
    # Fit the model
    model = model_class(**model_kwargs).fit(X, labels)
    # Instantiate explainer class
    if explainer_class in [shap.KernelExplainer, shap.DeepExplainer, shap.GradientExplainer]:
        background_data = _get_background_data(X, explainer_class=explainer_class, n_background_data=n_background_data)
        model_input = model.predict_proba if hasattr(model, 'predict_proba') else model.predict
        explainer = explainer_class(model_input, background_data, **explainer_kwargs)
    elif explainer_class == shap.LinearExplainer:
        explainer = explainer_class(model, X, **explainer_kwargs)
    else:
        explainer = explainer_class(model, **explainer_kwargs)

    # Compute SHAP values
    if 'y' in explainer.shap_values.__code__.co_varnames:
        shap_output = explainer.shap_values(X, y=labels)
    else:
        shap_output = explainer.shap_values(X)

    # Process SHAP values
    shap_values = _get_shap_values(shap_output, class_index=class_index)

    # Handle expected value for classification models
    expected_value = explainer.expected_value
    if not np.isscalar(expected_value):
        expected_value = expected_value[class_index] if len(expected_value) > class_index else expected_value[-1]
    return shap_values, expected_value


def _aggregate_shap_values(X, labels=None, list_model_classes=None, list_model_kwargs=None,
                           explainer_class=None, explainer_kwargs=None,
                           class_index=1, n_background_data=None):
    """Aggregate SHAP values across multiple models."""
    n_samples, n_features = X.shape
    n_models = len(list_model_classes)
    shap_values_rounds = np.empty(shape=(n_samples, n_features, n_models))
    list_expected_value = []
    for i, model_class in enumerate(list_model_classes):
        model_kwargs = list_model_kwargs[i]
        args = dict(model_class=model_class, model_kwargs=model_kwargs,
                    explainer_class=explainer_class, explainer_kwargs=explainer_kwargs,
                    class_index=class_index, n_background_data=n_background_data)
        shap_values, expected_value = _compute_shap_values(X, labels=labels, **args)
        shap_values_rounds[:, :, i] = shap_values
        list_expected_value.append(expected_value)
    shap_values = np.mean(shap_values_rounds, axis=2)
    exp_val = np.mean(list_expected_value)
    return shap_values, exp_val

import sys

# II Main Functions
def monte_carlo_shap_estimation(X, labels=None, list_model_classes=None, list_model_kwargs=None,
                                explainer_class=None, explainer_kwargs=None, n_rounds=5,
                                is_selected=None, fuzzy_labeling=False, verbose=False,
                                class_index=1, n_background_data=None):
    """Compute Monte Carlo estimates of SHAP values for multiple models and feature selections."""
    n_samples, n_features = X.shape
    n_selection_rounds = len(is_selected)
    mc_shap_values = np.zeros(shape=(n_samples, n_features, n_rounds, n_selection_rounds))
    list_expected_value = []
    if verbose:
        ut.print_start_progress(start_message=f"ShapExplainer starts Monte Carlo estimation of shap values over {n_rounds} rounds.")
    for i in range(n_rounds):
        for j, selected_features in enumerate(is_selected):
            if verbose:
                pct_progress = j / len(is_selected)
                add_new_line = explainer_class in LIST_VERBOSE_SHAP_EXPLAINERS
                ut.print_progress(i=i+pct_progress, n=n_rounds, add_new_line=add_new_line)
            # Adjust fuzzy labels (labels between 0 and 1, e.g., 0.5 -> 50% 1 and 50% 0)
            if fuzzy_labeling:
                threshold = (j * (i + 1)) / (n_rounds * n_selection_rounds)
                labels_ = [x if x in [0, 1] else int(x >= threshold) for x in labels]
            else:
                labels_ = labels
            X_selected = X[:, selected_features]
            args = dict(list_model_classes=list_model_classes,list_model_kwargs=list_model_kwargs,
                        explainer_class=explainer_class, explainer_kwargs=explainer_kwargs,
                        class_index=class_index, n_background_data=n_background_data)
            _shap_values, _exp_val = _aggregate_shap_values(X_selected, labels=labels_, **args)
            mc_shap_values[:, selected_features, i, j] = _shap_values
            list_expected_value.append(_exp_val)
    # Averaging over rounds and selections
    if verbose:
        ut.print_end_progress(end_message=f"ShapExplainer finished Monte Carlo estimation and saved results.")
    shap_values = np.mean(mc_shap_values, axis=(2, 3))
    exp_val = np.mean(list_expected_value)
    return shap_values, exp_val
