"""
This is a script for frontend of the setting plot legend.
The backend is in general utility module to provide function to remaining AAanalysis modules.
"""
from typing import Optional, List, Dict, Union, Tuple
from matplotlib import pyplot as plt
from aaanalysis import utils as ut
import matplotlib.lines as mlines
import warnings

# I Helper functions
def marker_has(marker, val=None):
    if isinstance(marker, str):
        return marker == val
    elif marker is None:
        return False
    elif isinstance(marker, list):
        return any([x == val for x in marker])
    else:
        raise ValueError(f"'marker' ({marker}) is wrong")

def marker_has_no(marker, val=None):
    if isinstance(marker, str):
        return marker != val
    elif marker is None:
        return False
    elif isinstance(marker, list):
        return any([x != val for x in marker])
    else:
        raise ValueError(f"'marker' ({marker}) is wrong")


# Checking functions for list inputs
def check_list_cat(dict_color=None, list_cat=None):
    """Ensure items in list_cat are keys in dict_color and match in length."""
    if not list_cat:
        return list(dict_color.keys())
    if not all(elem in dict_color for elem in list_cat):
        missing_keys = [elem for elem in list_cat if elem not in dict_color]
        raise ValueError(f"The following keys in 'list_cat' are not in 'dict_colors': {', '.join(missing_keys)}")
    if len(dict_color) != len(list_cat):
        raise ValueError(
            f"Length must match between 'list_cat' ({len(list_cat)}) and 'dict_colors' ({len(dict_color)}).")
    return list_cat


def check_labels(list_cat=None, labels=None):
    """Validate labels and match their length to list_cat."""
    if labels is None:
        labels = list_cat
    if len(list_cat) != len(labels):
        raise ValueError(f"Length must match of 'labels' ({len(labels)}) and categories ({len(list_cat)}).")
    return labels


# Checking functions for inputs that can be list or single values (redundancy accepted for better user communication)
def check_hatches(marker=None, hatch=None, list_cat=None):
    """Check validity of list_hatche."""
    valid_hatches = ['/', '\\', '|', '-', '+', 'x', 'o', 'O', '.', '*']
    # Check if hatch is valid
    if isinstance(hatch, str):
        if hatch not in valid_hatches:
            raise ValueError(f"'hatch' ('{hatch}') must be one of following: {valid_hatches}")
    if isinstance(hatch, list):
        wrong_hatch = [x for x in hatch if x not in valid_hatches]
        if len(wrong_hatch) != 0:
            raise ValueError(
                f"'hatch' contains wrong values ('{wrong_hatch}')! Should be one of following: {valid_hatches}")
        if len(hatch) != len(list_cat):
            raise ValueError(f"Length must match of 'hatch' ({hatch}) and categories ({list_cat}).")  # Check if hatch can be chosen
    # Warn for parameter conflicts
    if marker_has_no(marker, val=None) and hatch:
        warnings.warn(f"'hatch' can only be applied to the default marker, set 'marker=None'.", UserWarning)
    # Create hatch list
    list_hatch = [hatch] * len(list_cat) if not isinstance(hatch, list) else hatch
    return list_hatch


def check_marker(marker=None, list_cat=None, lw=0):
    """Check validity of markers"""
    # Add '-' for line and None for default marker
    valid_markers = [None, "-"] + list(mlines.Line2D.markers.keys())
    # Check if marker is valid
    if not isinstance(marker, list) and marker not in valid_markers:
        raise ValueError(f"'marker' ('{marker}') must be one of following: {valid_markers}")
    if isinstance(marker, list):
        wrong_markers = [x for x in marker if x not in valid_markers]
        if len(wrong_markers) != 0:
            raise ValueError(f"'marker' contains wrong values  ('{wrong_markers}'). Should be one of following: {valid_markers}")
        if len(marker) != len(list_cat):
            raise ValueError(f"Length must match of 'marker' ({marker}) and categories ({list_cat}).")
    # Warn for parameter conflicts
    if marker_has(marker, val="-") and lw <= 0:
        warnings.warn(f"Marker lines ('-') are only shown if 'lw' ({lw}) is > 0.", UserWarning)
    # Create marker list
    list_marker = [marker] * len(list_cat) if not isinstance(marker, list) else marker
    return list_marker


def check_marker_size(marker_size=None, list_cat=None):
    """Check size of markers"""
    # Check if marker_size is valid
    if isinstance(marker_size, (int, float)):
        ut.check_number_range(name='marker_size', val=marker_size, min_val=0, accept_none=True, just_int=False)
    elif isinstance(marker_size, list):
        for i in marker_size:
            ut.check_number_range(name='marker_size', val=i, min_val=0, accept_none=True, just_int=False)
    elif isinstance(marker_size, list) and len(marker_size) != len(list_cat):
        raise ValueError(f"Length must match of 'marker_size' (marker_size) and categories ({list_cat}).")
    else:
        raise ValueError(f"'marker_size' has wrong data type: {type(marker_size)}")
    # Create marker_size list
    list_marker_size = [marker_size] * len(list_cat) if not isinstance(marker_size, list) else marker_size
    return list_marker_size


def check_linestyle(linestyle=None, list_cat=None, marker=None):
    """Check validity of linestyle."""
    _lines = ['-', '--', '-.', ':', ]
    _names = ["solid", "dashed", "dashed-doted", "dotted"]
    valid_mls = _lines + _names
    # Check if marker_linestyle is valid
    if isinstance(linestyle, list):
        wrong_mls = [x for x in linestyle if x not in valid_mls]
        if len(wrong_mls) != 0:
            raise ValueError(
                f"'marker_linestyle' contains wrong values ('{wrong_mls}')! Should be one of following: {valid_mls}")
        if len(linestyle) != len(list_cat):
            raise ValueError(f"Length must match of 'marker_linestyle' ({linestyle}) and categories ({list_cat}).")
    # Check if marker_linestyle is conflicting with other settings
    if isinstance(linestyle, str):
        if linestyle not in valid_mls:
            raise ValueError(f"'marker_linestyle' ('{linestyle}') must be one of following: {_lines},"
                             f" or corresponding names: {_names} ")
    # Warn for parameter conflicts
    if linestyle is not None and marker_has_no(marker, val="-"):
        warnings.warn(f"'linestyle' ({linestyle}) is only applicable to marker lines ('-'), not to '{marker}'.", UserWarning)
    # Create list_marker_linestyle list
    list_marker_linestyle = [linestyle] * len(list_cat) if not isinstance(linestyle, list) else linestyle
    return list_marker_linestyle


# II Main function
def plot_legend(ax: Optional[plt.Axes] = None,
                # Categories and colors
                dict_color: Dict[str, str] = None,
                list_cat: Optional[List[str]] = None,
                labels: Optional[List[str]] = None,
                # Position and Layout
                loc: Union[str, int] = "upper left",
                loc_out: bool = False,
                y: Optional[Union[int, float]] = None,
                x: Optional[Union[int, float]] = None,
                ncol: int = 3,
                labelspacing: Union[int, float] = 0.2,
                columnspacing: Union[int, float] = 1.0,
                handletextpad: Union[int, float] = 0.8,
                handlelength: Union[int, float] = 2.0,
                # Font and Style
                fontsize: Optional[Union[int, float]] = None,
                fontsize_title: Optional[Union[int, float]] = None,
                weight_font: str = "normal",
                weight_title: str = "normal",
                # Marker, Lines, and Area
                marker: Optional[Union[str, int, list]] = None,
                marker_size: Union[int, float, List[Union[int, float]]] = 10,
                lw: Union[int, float] = 0,
                linestyle: Optional[Union[str, list]] = None,
                edgecolor: Optional[str] = None,
                hatch: Optional[Union[str, List[str]]] = None,
                hatchcolor: str = "white",
                # Title
                title: Optional[str] = None,
                title_align_left: bool = True,
                **kwargs
                ) -> Union[plt.Axes, Tuple[List, List[str]]]:
    """
    Sets an independently customizable plot legend.

    Legends can be flexibly adjusted based categories and colors provided in ``dict_color`` dictionary.
    This functions comprises the most convenient settings for ``func:`matplotlib.pyplot.legend``.

    Parameters
    ----------
    ax : plt.Axes, optional
        The axes to attach the legend to. If not provided, the current axes will be used.
    dict_color : dict, optional
        A dictionary mapping categories to colors.
    list_cat : list of strings, optional
        List of categories to include in the legend (keys of ``dict_color``).
    labels : list of strings, optional
        Legend labels corresponding to given categories.
    loc : int or str
        Location for the legend.
    loc_out : bool, default=False
        If ``True``, sets automatically ``x=0`` and ``y=-0.25`` if they are ``None``.
    y : int or float, optional
        The y-coordinate for the legend's anchor point.
    x : int or float, optional
        The x-coordinate for the legend's anchor point.
    ncol : int, default=1
        Number of columns in the legend, at least 1.
    labelspacing : int or float, default=0.2
        Vertical spacing between legend items.
    columnspacing : int or float, default=1.0
        Horizontal spacing between legend columns.
    handletextpad : int or float, default=0.8
        Horizontal spacing between legend handle (marker) and label.
    handlelength : int or float, default=2.0
        Length of legend handle.
    fontsize : int or float, optional
        Font size for the legend text.
    fontsize_title : inf or float, optional
        Font size for the legend title.
    weight_font : str, default='normal'
        Weight of the font.
    weight_title : str, default='normal'
        Font weight for the legend title.
    marker : str, int, or list, optional
        Handle marker for legend items. Lines ('-') only visible if ``lw>0``.
    marker_size : int, float, or list, optional
        Marker size for legend items.
    lw : int or float, default=0
        Line width for legend items. If negative, corners are rounded.
    linestyle : str or list, optional
        Style of line. Only applied to lines (``marker='-'``).
    edgecolor : str, optional
        Edge color of legend items. Not applicable to lines.
    hatch : str or list, optional
        Filling pattern for default marker. Only applicable when ``marker=None``.
    hatchcolor : str, default='white'
        Hatch color of legend items. Only applicable when ``marker=None``.
    title : str, optional
        Legend title.
    title_align_left : bool, default=True
        Whether to align the title to the left.
    **kwargs
        Further key word arguments for :attr:`matplotlib.axes.Axes.legend`.

    Returns
    -------
    ax
        Axes on which legend is applied to.

    Notes
    -----
    Markers can be None (default), lines ('-') or one of the `matplotlib markers
    <https://matplotlib.org/stable/api/markers_api.html>`_.

    See Also
    --------
    * More examples in `Plotting Prelude <plotting_prelude.html>`_.
    * `Linestyles of markers <https://matplotlib.org/stable/gallery/lines_bars_and_markers/linestyles.html>`_.
    * `Hatches <https://matplotlib.org/stable/gallery/shapes_and_collections/hatch_style_reference.html>`_, which are filling patterns.
    * :class:`matplotlib.lines.Line2D` for available marker shapes and line properties.
    * :class:`matplotlib.axes.Axes`, which is the core object in matplotlib.
    * :func:`matplotlib.pyplot.gca` to get the current Axes instance.

    Examples
    --------
    .. include:: examples/plot_legend.rst
    """
    # Check input
    ut.check_ax(ax=ax, accept_none=True)
    if ax is None:
        ax = plt.gca()
    ut.check_dict(name="dict_color", val=dict_color, accept_none=False)
    list_cat = check_list_cat(dict_color=dict_color, list_cat=list_cat)
    labels = check_labels(list_cat=list_cat, labels=labels)

    ut.check_bool(name="title_align_left", val=title_align_left)
    ut.check_bool(name="loc_out", val=loc_out)

    ut.check_number_range(name="ncol", val=ncol, min_val=1, accept_none=True, just_int=True)
    ut.check_number_val(name="x", val=x, accept_none=True, just_int=False)
    ut.check_number_val(name="y", val=y, accept_none=True, just_int=False)
    ut.check_number_val(name="lw", val=lw, accept_none=True, just_int=False)

    args_non_neg = {"labelspacing": labelspacing, "columnspacing": columnspacing,
                    "handletextpad": handletextpad, "handlelength": handlelength,
                    "fontsize": fontsize, "fontsize_legend": fontsize_title}
    for key in args_non_neg:
        ut.check_number_range(name=key, val=args_non_neg[key], min_val=0, accept_none=True, just_int=False)

    marker = check_marker(marker=marker, list_cat=list_cat, lw=lw)
    hatch = check_hatches(marker=marker, hatch=hatch, list_cat=list_cat)
    linestyle = check_linestyle(linestyle=linestyle, list_cat=list_cat, marker=marker)
    marker_size = check_marker_size(marker_size, list_cat=list_cat)
    # Create new legend
    ax = ut.plot_legend_(ax=ax, dict_color=dict_color, list_cat=list_cat, labels=labels,
                         loc=loc, loc_out=loc_out, y=y, x=x, ncol=ncol,
                         labelspacing=labelspacing, columnspacing=columnspacing,
                         handletextpad=handletextpad, handlelength=handlelength,
                         fontsize=fontsize, fontsize_title=fontsize_title,
                         weight_font=weight_font, weight_title=weight_title,
                         marker=marker, marker_size=marker_size, lw=lw, linestyle=linestyle, edgecolor=edgecolor,
                         hatch=hatch, hatchcolor=hatchcolor, title=title, title_align_left=title_align_left, **kwargs)
    return ax
