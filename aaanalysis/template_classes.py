"""
This is a script for creating template Wrapper and Tool classes used in the AAanalysis library
"""
from abc import ABC, abstractmethod


class Tool(ABC):
    """Tool class for specialized tasks.

    This class provides a framework for standalone utilities focusing on specialized tasks,
    such as feature engineering or data pre-processing. The `.run` method is intended for
    executing the main logic of the tool, while `.eval` is for evaluation of the tool's output.

    Subclasses should provide concrete implementations for the `run` and `eval` methods.
    """

    @abstractmethod
    def run(self):
        """Execute the main logic of the tool.

        This method should be overridden by subclasses to implement the main functionality.

        Raises:
        NotImplementedError: If the method is not implemented by the subclass.
        """
        raise NotImplementedError

    @abstractmethod
    def eval(self):
        """Evaluate the output generated by the tool."""
        raise NotImplementedError


class Wrapper(ABC):
    """Wrapper class for extending models from libraries like scikit-learn."""

    @abstractmethod
    def __init__(self):
        # Model attributes to be implemented by wrapper class
        self._model_class = None
        self.model = None
        self.model_kwargs = None

    @abstractmethod
    def fit(self, *args, **kwargs):
        """Fit the model with data."""

    @abstractmethod
    def eval(self, *args, **kwargs):
        """Evaluate the model."""
        raise NotImplementedError
