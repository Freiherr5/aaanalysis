"""
This is a script for the backend of the dPULearn.compare_sets_negatives() method.
"""
import pandas as pd
import numpy as np


# I Helper Functions


# II Main Functions
def compare_sets_negatives_(list_labels=None, names=None, df_seq=None, return_upset_data=None):
    """Create DataFrame for comparing sets of identified negatives"""
    combined_negatives = set()
    for labels in list_labels:
        negatives = set(np.where(labels == 0)[0])
        combined_negatives.update(negatives)
    data = {}
    names = [f'set_{i}' for i in enumerate(list_labels)] if names is None else names
    for name, labels in zip(names, list_labels):
        data[name] = [(index in combined_negatives and labels[index] == 0) for index in range(len(labels))]
    df = pd.DataFrame(data)
    # Filter samples that are never identified as negatives
    mask = np.asarray(df.sum(axis=1) != 0)
    if not return_upset_data:
        if df_seq is not None:
            df = pd.concat([df_seq, df], axis=1)
        df_neg_comp = df[mask]
        return df_neg_comp
    # Create UpsetPlot data
    df = df[list(reversed(list(df)))][mask]
    upset_data = df.groupby(list(df.columns)).size()
    return upset_data


