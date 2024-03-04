#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Mon Mar  4 01:49:06 PM EST 2024
#

"""

This module consists of utility functions for data analysis of the Tetris
Ballistic model. It includes functionality to generate visualizations of the
data, and to perform statistical analysis on the data.

Author:
    Le Chen (chenle02@gmail.com / le.chen@auburn.edu)
"""

import numpy as np
import joblib
import glob
from scipy import stats
import matplotlib.pyplot as plt
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic, load_density_from_config
# from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir


def retrieve_fluctuations(pattern: str,
                          output_filename: str = None,
                          verbose: bool = False):
    """
    aaa

    """

    # pattern = f"./config_piece_{piece_id}_{type_}_w={width}*.joblib"

    # Use glob to find files matching the pattern
    files = glob.glob(pattern)

    if verbose:
        print(f"pattern = {pattern}")
        print(f"Number of matches = {len(files)}")
        for item, file in enumerate(files):
            print(f"File {item}: {file}")
        print("\n")

    if len(files) == 0:
        raise ValueError(f"No file found for the pattern: {pattern}")

    # Load the data from the files
    for file in files:
        data = joblib.load(file)
        TB = Tetris_Ballistic.load_simulation(file)
        print(TB)
        print("\n")

# Debug and example usage
if __name__ == "__main__":
    pattern = "../Experiments/exp10/*w=50*.joblib"
    retrieve_fluctuations(pattern, verbose=True)

    # pattern = "../Experiments/exp10/*w=100*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
    #
    # pattern = "../Experiments/exp10/*_sticky_*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
    #
    # pattern = "../Experiments/exp10/*_nonsticky_*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
