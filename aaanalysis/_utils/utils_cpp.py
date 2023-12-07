"""
This is a script with utility functions and settings for CPP project.
"""
import numpy as np
import matplotlib.pyplot as plt

import aaanalysis as aa
import aaanalysis._utils.check_type as ut_check

# Settings
# TODO move to feature engineering
# Default Split names
STR_SEGMENT = "Segment"
STR_PATTERN = "Pattern"
STR_PERIODIC_PATTERN = "PeriodicPattern"

# DEFAULT Signs
STR_AA_GAP = "-"

# Default column names for cpp analysis
LIST_ALL_PARTS = ["tmd", "tmd_e", "tmd_n", "tmd_c", "jmd_n", "jmd_c", "ext_c", "ext_n",
                  "tmd_jmd", "jmd_n_tmd_n", "tmd_c_jmd_c", "ext_n_tmd_n", "tmd_c_ext_c"]
LIST_PARTS = ["tmd", "jmd_n_tmd_n", "tmd_c_jmd_c"]

SPLIT_DESCRIPTION = "\n a) {}(i-th,n_split)" \
                    "\n b) {}(N/C,p1,p2,...,pn)" \
                    "\n c) {}(N/C,i+step1/step2,start)" \
                    "\nwith i-th<=n_split, and p1<p2<...<pn," \
                    "\nwhere all numbers should be non-negative integers, and N/C means N or C."\
    .format(STR_SEGMENT, STR_PATTERN, STR_PERIODIC_PATTERN)

# TODO to CPP backend (after testing of CPP is finished)
# II Main Functions
# General check functions
def check_y_categorical(df=None, y=None):
    """Check if y in df"""
    list_cat_columns = [col for col, data_type in zip(list(df), df.dtypes)
                        if data_type != float and "position" not in col]# and col != "feature"]
    if y not in list_cat_columns:
        raise ValueError(f"'y' ({y}) should be one of following columns with categorical values "
                         f"of 'df': {list_cat_columns}")


def check_labels_(labels=None, df=None, name_df=None):
    """Check if y not None and just containing 0 and 1"""
    if labels is None:
        raise ValueError("'labels' should not be None")
    if set(labels) == {0} or set(labels) == {1}:
        raise ValueError(f"'labels' contain just one class {set(labels)}.")
    if set(labels) != {0, 1}:
        wrong_labels = [x for x in set(labels) if x not in [0, 1]]
        raise ValueError(f"'labels' should only contain 0 and 1 as class labels and not following: {wrong_labels}")
    if df is not None:
        if len(labels) != len(df):
            raise ValueError(f"'labels' does not match with '{name_df}'")


# Sequence check function
def _check_seq(seq, len_, name_seq, name_len):
    """Check sequence with should be rather flexible to except various types,
    such as strings, lists, or numpy arrays"""
    if seq is None:
        return len_
    else:
        if len_ is not None:
            # Waring sequence length doesn't match the corresponding length parameter
            if len(seq) < len_:
                raise ValueError(f"The length of {name_seq} ({len(seq)}) should be >= {name_len} ({len_}).")
        return len(seq)


def _check_ext_len(jmd_n_len=None, jmd_c_len=None, ext_len=None):
    """"""
    if ext_len is not None and ext_len != 0:
        if jmd_n_len is None:
            raise ValueError(f"'jmd_n_len' should not be None if 'ext_len' ({ext_len}) is given")
        if jmd_c_len is None:
            raise ValueError(f"'jmd_c_len' should not be None if 'ext_len' ({ext_len}) is given")
        if jmd_n_len is not None and ext_len > jmd_n_len:
            raise ValueError(f"'ext_len' ({ext_len}) must be <= length of jmd_n ({jmd_n_len})")
        if jmd_c_len is not None and ext_len > jmd_c_len:
            raise ValueError(f"'ext_len' ({ext_len}) must be <= length of jmd_c ({jmd_c_len})")


def check_args_len(tmd_len=None, jmd_n_len=None, jmd_c_len=None,
                   tmd_seq=None, jmd_n_seq=None, jmd_c_seq=None, accept_tmd_none=False):
    """Check length parameters and if they are matching with sequences if provided"""
    ext_len = aa.options["ext_len"]
    # Check lengths
    tmd_seq_given = tmd_seq is not None or accept_tmd_none  # If tmd_seq is given, tmd_len can be None
    ut_check.check_number_range(name="tmd_len", val=tmd_len, accept_none=tmd_seq_given, min_val=1, just_int=True)
    ut_check.check_number_range(name="jmd_n_len", val=jmd_n_len, accept_none=True, min_val=0, just_int=True)
    ut_check.check_number_range(name="jmd_c_len", val=jmd_c_len, accept_none=True, min_val=0, just_int=True)
    ut_check.check_number_range(name="ext_len", val=ext_len, min_val=0, accept_none=True, just_int=True)
    # Check if lengths and sequences match (any sequence is excepted, strings, lists, arrays)
    tmd_len = _check_seq(tmd_seq, tmd_len, "tmd_seq", "tmd_len")
    jmd_n_len = _check_seq(jmd_n_seq, jmd_n_len, "jmd_n_seq", "jmd_n_len")
    jmd_c_len = _check_seq(jmd_c_seq, jmd_c_len, "jmd_c_seq", "jmd_c_len")
    # Check if lengths are matching
    _check_ext_len(jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len, ext_len=ext_len)
    args_len = dict(tmd_len=tmd_len, jmd_n_len=jmd_n_len, jmd_c_len=jmd_c_len)
    return args_len


# Part check functions
def check_list_parts(list_parts=None, all_parts=False):
    """Check if parts from list_parts are columns of df_seq"""
    if list_parts is None:
        list_parts = LIST_ALL_PARTS if all_parts else LIST_PARTS
    if type(list_parts) is str:
        list_parts = [list_parts]
    if type(list_parts) != list:
        raise ValueError(f"'list_parts' must be list with selection of following parts: {LIST_ALL_PARTS}")
    # Check for invalid parts
    wrong_parts = [x for x in list_parts if x not in LIST_ALL_PARTS]
    if len(wrong_parts) > 0:
        str_part = "part" if len(wrong_parts) == 1 else "parts"
        error = f"{wrong_parts} not valid {str_part}.\n  Select from following parts: {LIST_ALL_PARTS}"
        raise ValueError(error)
    return list_parts


# Split check functions
# TODO check if can be simplified
def check_split_kws(split_kws=None, accept_none=True):
    """Check if argument dictionary for splits is a valid input"""
    # Split dictionary with data types
    split_kws_types = {STR_SEGMENT: dict(n_split_min=int, n_split_max=int),
                       STR_PATTERN: dict(steps=list, n_min=int, n_max=int, len_max=int),
                       STR_PERIODIC_PATTERN: dict(steps=list)}
    if accept_none and split_kws is None:
        return None     # Skip check
    if not isinstance(split_kws, dict):
        raise ValueError("'split_kws' should be type dict (not {})".format(type(split_kws)))
    # Check if split_kws contains wrong split_types
    split_types = [STR_SEGMENT, STR_PATTERN, STR_PERIODIC_PATTERN]
    wrong_split_types = [x for x in split_kws if x not in split_types]
    if len(wrong_split_types) > 0:
        error = "Following keys are invalid: {}." \
                "\n  'split_kws' should have following structure: {}.".format(wrong_split_types, split_kws_types)
        raise ValueError(error)
    if len(split_kws) == 0:
        raise ValueError("'split_kws' should be not empty")
    # Check if arguments are valid and have valid type
    for split_type in split_kws:
        for arg in split_kws[split_type]:
            if arg not in split_kws_types[split_type]:
                error = "'{}' arg in '{}' of 'split_kws' is invalid." \
                        "\n  'split_kws' should have following structure: {}.".format(arg, split_type, split_kws_types)
                raise ValueError(error)
            arg_val = split_kws[split_type][arg]
            arg_type = type(arg_val)
            target_arg_type = split_kws_types[split_type][arg]
            if target_arg_type != arg_type:
                error = "Type of '{}':'{}' ({}) should be {}".format(arg, arg_val, arg_type, target_arg_type)
                raise ValueError(error)
            if arg_type is list:
                wrong_type = [x for x in arg_val if type(x) is not int]
                if len(wrong_type) > 0:
                    error = "All list elements ({}) of '{}' should have type int.".format(arg_val, arg)
                    raise ValueError(error)
    # Check Segment
    if STR_SEGMENT in split_kws:
        segment_args = split_kws[STR_SEGMENT]
        if segment_args["n_split_min"] > segment_args["n_split_max"]:
            raise ValueError("For '{}', 'n_split_min' should be smaller or equal to 'n_split_max'".format(STR_SEGMENT))
    # Check Pattern
    if STR_PATTERN in split_kws:
        pattern_args = split_kws[STR_PATTERN]
        if pattern_args["n_min"] > pattern_args["n_max"]:
            raise ValueError("For '{}', 'n_min' should be smaller or equal to 'n_max'".format(STR_PATTERN))
        if pattern_args["steps"] != sorted(pattern_args["steps"]):
            raise ValueError("For '{}', 'steps' should be ordered in ascending order.".format(STR_PATTERN))
        if pattern_args["steps"][0] >= pattern_args["len_max"]:
            raise ValueError("For '{}', 'len_max' should be greater than the smallest step in 'steps'.".format(STR_PATTERN))
    # Check PeriodicPattern
    if STR_PERIODIC_PATTERN in split_kws:
        ppattern_args = split_kws[STR_PERIODIC_PATTERN]
        if ppattern_args["steps"] != sorted(ppattern_args["steps"]):
            raise ValueError("For '{}', 'steps' should be ordered in ascending order.".format(STR_PERIODIC_PATTERN))


def check_split(split=None):
    """Check split and convert split name to split type and split arguments"""
    if type(split) is not str:
        raise ValueError("'split' must have type 'str'")
    split = split.replace(" ", "")  # remove whitespace
    try:
        # Check Segment
        if STR_SEGMENT in split:
            split_type = STR_SEGMENT
            i_th, n_split = [int(x) for x in split.split("(")[1].replace(")", "").split(",")]
            # Check if values non-negative integers
            for name, val in zip(["i_th", "n_split"], [i_th, n_split]):
                ut_check.check_number_range(name=name, val=val, just_int=True)
            # Check if i-th and n_split are valid
            if i_th > n_split:
                raise ValueError
            split_kwargs = dict(i_th=i_th, n_split=n_split)
        # Check PeriodicPattern
        elif STR_PERIODIC_PATTERN in split:
            split_type = STR_PERIODIC_PATTERN
            start = split.split("i+")[1].replace(")", "").split(",")
            step1, step2 = [int(x) for x in start.pop(0).split("/")]
            start = int(start[0])
            # Check if values non-negative integers
            for name, val in zip(["start", "step1", "step2"], [start, step1, step2]):
                ut_check.check_number_range(name=name, val=val, just_int=True)
            # Check if terminus valid
            terminus = split.split("i+")[0].split("(")[1].replace(",", "")
            if terminus not in ["N", "C"]:
                raise ValueError
            split_kwargs = dict(terminus=terminus, step1=step1, step2=step2, start=start)
        # Check pattern
        elif STR_PATTERN in split:
            split_type = STR_PATTERN
            list_pos = split.split("(")[1].replace(")", "").split(",")
            terminus = list_pos.pop(0)
            # Check if values non-negative integers
            list_pos = [int(x) for x in list_pos]
            for val in list_pos:
                name = "pos" + str(val)
                ut_check.check_number_range(name=name, val=val, just_int=True)
            # Check if terminus valid
            if terminus not in ["N", "C"]:
                raise ValueError
            # Check if arguments are in order
            if not sorted(list_pos) == list_pos:
                raise ValueError
            split_kwargs = dict(terminus=terminus, list_pos=list_pos)
        else:
            raise ValueError
        return split_type, split_kwargs
    except:
        error = "Wrong split annotation for '{}'. Splits should be denoted as follows:".format(split, SPLIT_DESCRIPTION)
        raise ValueError(error)
