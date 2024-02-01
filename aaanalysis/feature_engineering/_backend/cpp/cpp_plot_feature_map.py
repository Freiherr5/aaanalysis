"""
This is a script for the backend of the CPPPlot.feature_map method.
"""
import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
import warnings

import aaanalysis.utils as ut

from ._utils_cpp_plot_elements import PlotElements
from ._utils_cpp_plot_positions import PlotPartPositions
from ._utils_cpp_plot_map import plot_heatmap_


# Add feature importance plot elements
def plot_feat_importance_bars(ax=None, df=None, top_pcp=None,
                              label=ut.LABEL_FEAT_IMPORT, col_imp=None,
                              titlesize=12, labelsize=12, top_pcp_size=12,
                              top_pcp_weight="bold"):
    """Display a horizontal bar plot for feature importance sorted by categories."""
    col_start = "pos_start"
    col_subcat_lower = "subcat_lower"
    plt.sca(ax)
    df[col_start] = [int(x.split(",")[0]) if "," in x else int(x) for x in df[ut.COL_POSITION]]
    df[col_subcat_lower] = [x.lower() for x in df[ut.COL_SUBCAT]]
    df = df.sort_values(by=[ut.COL_CAT, col_subcat_lower, col_start, col_imp],
                        ascending=[True, True, True, False])
    df_imp = df[[ut.COL_SUBCAT, col_imp]].groupby(by=ut.COL_SUBCAT).sum()
    dict_imp = dict(zip(df_imp.index, df_imp[col_imp]))
    # Case non-sensitive sorted list of subcat
    list_subcat = list(
        df.sort_values(by=[ut.COL_CAT, ut.COL_SUBCAT], key=lambda x: x.str.lower())[ut.COL_SUBCAT].drop_duplicates())
    list_imp = [dict_imp[x] for x in list_subcat]
    ax.barh(list_subcat, list_imp, color="tab:gray", edgecolor="white", align="edge")
    plt.xlabel(label, size=titlesize, weight="bold", ha="center")
    ax.xaxis.set_label_position('top')
    # Add annotations
    top_pcp = max(list_imp)/2 if top_pcp is None else top_pcp
    for i, val in enumerate(list_imp):
        if val >= top_pcp:
            plt.text(val, i+0.45, f"{round(val, 1)}% ",
                     va="center", ha="right",
                     weight=top_pcp_weight,
                     color="white",
                     size=top_pcp_size)
    # Adjust ticks
    ax.tick_params(axis='y', which='both', length=0, labelsize=0)
    ax.tick_params(axis='x', which='both', labelsize=labelsize, pad=-1)
    sns.despine(ax=ax, bottom=True, top=False)
    plt.xlim(0, max(list_imp))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        plt.tight_layout()


# TODO adjust 3 th by args
def add_feat_importance_map(ax=None, df_feat=None, df_cat=None, start=None, args_len=None,
                            col_cat=None, col_imp=None, normalize=False):
    """Overlay feature importance symbols on the heatmap based on the importance values."""
    pp = PlotPartPositions(**args_len, start=start)
    df_pos = pp.get_df_pos(df_feat=df_feat.copy(), df_cat=df_cat,
                           col_cat=col_cat, col_val=col_imp,
                           value_type="sum", normalize=normalize)
    _df = pd.melt(df_pos.reset_index(), id_vars="index")
    _df.columns = [ut.COL_SUBCAT, ut.COL_POSITION, col_imp]
    _list_sub_cat = _df[ut.COL_SUBCAT].unique()
    for i, sub_cat in enumerate(_list_sub_cat):
        _dff = _df[_df[ut.COL_SUBCAT] == sub_cat]
        for pos, val in enumerate(_dff[col_imp]):
            _symbol = "■"
            color = "black"
            size = 7 if val >= 1 else (5 if val >= 0.5 else 3)
            _args_symbol = dict(ha="center", va="center", color=color, size=size)
            if val >= 0.2:
                ax.text(pos + 0.5, i + 0.5, _symbol, **_args_symbol)


def add_feat_importance_legend(ax=None, legend_imp_xy=None, label=None, fontsize_title=None, fontsize=None):
    """Add a custom legend indicating the meaning of feature importance symbols."""
    if legend_imp_xy is not None:
        x, y = legend_imp_xy
    else:
        x = 1.25
        y = 0
    # Define the sizes for the legend markers
    list_labels = ["  >0.2%", "  >0.5%", "  >1.0%"]
    list_sizes = [3, 5, 7]
    # Create the legend handles manually
    legend_handles = [
        plt.Line2D([0], [0], marker='s', color='w', label=label,
                   markersize=size, markerfacecolor='black', linewidth=0)
        for label, size in zip(list_labels, list_sizes)]
    # Create the second legend
    ax.legend(handles=legend_handles,
              title=label,
              loc='lower left',
              bbox_to_anchor=(x, y),
              frameon=False,
              title_fontsize=fontsize_title,
              fontsize=fontsize,
              labelspacing=0.25,
              columnspacing=0, handletextpad=0, handlelength=0,
              borderpad=0)


# II Main Functions
def plot_feature_map(df_feat=None, df_cat=None,
                     col_cat="subcategory", col_val="mean_dif", col_imp="feat_importance",
                     normalize=False,
                     name_test="TEST", name_ref="REF",
                     figsize=(8, 8),
                     start=1, tmd_len=20, jmd_n_len=10, jmd_c_len=10,
                     tmd_seq=None, jmd_n_seq=None, jmd_c_seq=None,
                     tmd_color="mediumspringgreen", jmd_color="blue",
                     tmd_seq_color="black", jmd_seq_color="white",
                     seq_size=None,
                     fontsize_tmd_jmd=None, weight_tmd_jmd="normal",
                     fontsize_labels=12, fontsize_annotations=11,
                     add_xticks_pos=False,
                     grid_linewidth=0.01, grid_linecolor=None,
                     border_linewidth=2,
                     facecolor_dark=False, vmin=None, vmax=None,
                     cmap=None, cmap_n_colors=101,
                     cbar_pct=True, cbar_kws=None,
                     dict_color=None, legend_kws=None,
                     xtick_size=11.0, xtick_width=2.0, xtick_length=5.0,
                     ytick_size=None):
    """Create a comprehensive feature map with a heatmap, feature importance bars, and custom legends."""
    # Get fontsize
    pe = PlotElements()
    fs_labels, fs_annotations = pe.adjust_fontsize(fontsize_labels=fontsize_labels,
                                                   fontsize_annotations=fontsize_annotations)
    # Group arguments
    args_seq = dict(jmd_n_seq=jmd_n_seq, tmd_seq=tmd_seq, jmd_c_seq=jmd_c_seq)
    args_len = dict(tmd_len=tmd_len, jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len)
    args_part_color = dict(tmd_color=tmd_color, jmd_color=jmd_color)
    args_seq_color = dict(tmd_seq_color=tmd_seq_color, jmd_seq_color=jmd_seq_color)
    args_fs = dict(seq_size=seq_size,
                   fontsize_labels=fs_labels,
                   fontsize_tmd_jmd=fontsize_tmd_jmd)
    args_xtick = dict(xtick_size=xtick_size, xtick_width=xtick_width, xtick_length=xtick_length)

    # Plot
    width, height = figsize
    width_ratio = [6, min(1*height/width, 1)]
    fig, axes = plt.subplots(figsize=figsize,
                             nrows=1, ncols=2,
                             sharey=True,
                             gridspec_kw={'width_ratios': width_ratio, "wspace": 0},
                             layout="constrained")

    # Set color bar and legend arguments
    label_cbar = f"Feature value\n{name_test} - {name_ref}"
    _cbar_kws, cbar_ax = pe.adjust_cbar_kws(fig=fig,
                                            cbar_kws=cbar_kws,
                                            cbar_xywh=None,
                                            label=label_cbar,
                                            fontsize_labels=fs_labels)

    n_cat = len(set(df_feat[ut.COL_CAT]))
    _legend_kws = pe.adjust_cat_legend_kws(legend_kws=legend_kws,
                                           n_cat=n_cat,
                                           legend_xy=None,
                                           fontsize_labels=fs_labels)

    # Plot feat importance bars
    label_bars_imp = "Cumulative feature\n  importance [%]"
    plot_feat_importance_bars(ax=axes[1], df=df_feat.copy(),
                              titlesize=fs_annotations,
                              labelsize=fs_annotations,
                              top_pcp_size=fs_annotations-2,
                              top_pcp_weight="bold",
                              col_imp=col_imp,
                              label=label_bars_imp)

    # Plot heatmap
    ax = plot_heatmap_(df_feat=df_feat, df_cat=df_cat,
                       col_cat=col_cat, col_val=col_val,
                       normalize=normalize,
                       ax=axes[0], figsize=figsize,
                       start=start, **args_len, **args_seq,
                       **args_part_color, **args_seq_color,
                       **args_fs, weight_tmd_jmd=weight_tmd_jmd,
                       add_xticks_pos=add_xticks_pos,
                       grid_linewidth=grid_linewidth, grid_linecolor=grid_linecolor,
                       border_linewidth=border_linewidth,
                       facecolor_dark=facecolor_dark, vmin=vmin, vmax=vmax,
                       cmap=cmap, cmap_n_colors=cmap_n_colors,
                       cbar_ax=cbar_ax, cbar_pct=cbar_pct, cbar_kws=_cbar_kws,
                       dict_color=dict_color, legend_kws=_legend_kws,
                       **args_xtick, ytick_size=ytick_size)

    # Add feature position title
    label_feat_pos = ("                  Feature                  \n"
                      "Scale (subcategory)  +  Positions                 ")
    plt.title(label_feat_pos, x=0, weight="bold", fontsize=fs_annotations)


    # Add feature importance map
    add_feat_importance_map(df_feat=df_feat, df_cat=df_cat,
                            col_cat=col_cat, col_imp=col_imp,
                            normalize=normalize,
                            ax=ax, start=start, args_len=args_len)

    label_feat_imp = "Feature importance"
    add_feat_importance_legend(ax=cbar_ax,
                               legend_imp_xy=None,
                               label=label_feat_imp,
                               fontsize_title=fs_labels,
                               fontsize=fs_annotations)


    return fig, ax
