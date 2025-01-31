"""
This is a script for the frontend of the SeqMutPlot class
"""
import aaanalysis.utils as ut


# I Helper Functions
# Check functions


# II Main Functions
class SeqMutPlot:
    """
    UNDER CONSTRUCTION - Plotting class for ``SeqMut`` (Sequence Mutator).
    """
    def __init__(self, verbose=False, df_scales=None):
        self._verbose = ut.check_verbose(verbose)
        self.df_scales = df_scales

    # Main method
    def mutation_landscape(self):
        """"""