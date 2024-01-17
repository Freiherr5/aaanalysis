"""This is a script for scikit-learn model specific check functions"""
import inspect
from inspect import isclass

# Helper functions


# Main functions
def check_mode_class(model_class=None, name_model_class="model_class"):
    """Check if the provided object is a class and callable, typically used for validating model classes."""
    # Check if model_class is actually a class and not an instance
    if not isclass(model_class):
        raise ValueError(f"'{name_model_class}' ('{model_class}') is not a model class. Please provide a valid model class.")
    # Check if model is callable
    if not callable(getattr(model_class, "__call__", None)):
        raise ValueError(f"'{name_model_class}' ('{model_class}') is not a callable model.")


def check_model_kwargs(model_class=None, model_kwargs=None, name_model_class="model_class",
                       param_to_check=None, method_to_check=None, attribute_to_check=None,
                       random_state=None):
    """
    Check if the provided model class contains specific parameters and methods. Filters 'model_kwargs' to include only
    valid parameters for the model class.

    Parameters:
        model_class: The class of the model to check.
        model_kwargs: A dictionary of keyword arguments for the model.
        name_model_class: Name of model class for model class kwargs
        param_to_check: A specific parameter to check in the model class.
        method_to_check: A specific method to check in the model class.
        attribute_to_check: A specific attribute to check in model class
        random_state: random state

    Returns:
        model_kwargs: A filtered dictionary of model_kwargs containing only valid parameters for the model class.
    """
    model_kwargs = model_kwargs or {}
    if model_class is None:
        raise ValueError(f"'{name_model_class}' must be provided.")
    valid_args = list(inspect.signature(model_class).parameters.keys())
    # Check if 'param_to_check' is a parameter of the model
    if param_to_check is not None and param_to_check not in valid_args:
        raise ValueError(f"'{param_to_check}' should be an argument in the given '{name_model_class}' ({model_class}).")
    # Check if 'method_to_check' is a method of the model
    if method_to_check is not None and not hasattr(model_class, method_to_check):
        raise ValueError(f"'{method_to_check}' should be a method in the given '{name_model_class}' ({model_class}).")
    # Check if 'attribute_to_check' is an attribute of the model
    if attribute_to_check is not None and not hasattr(model_class, attribute_to_check):
        raise ValueError(f"'{attribute_to_check}' should be an attribute in the given '{name_model_class}' ({model_class}).")
    # Check if model_kwargs contain invalid parameters for the model
    invalid_kwargs = [x for x in model_kwargs if x not in valid_args]
    if len(invalid_kwargs):
        raise ValueError(f"'model_kwargs' (for '{model_class}') contains invalid arguments: {invalid_kwargs}")
    if "random_state" not in model_kwargs and "random_state" in valid_args:
        model_kwargs.update(dict(random_state=random_state))
    return model_kwargs


