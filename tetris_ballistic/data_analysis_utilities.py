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
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir


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
        print(f"Files found: {files}")


# Debug and example usage
if __name__ == "__main__":
    retrieve_fluctuations("../Experiments/exp10/*w=50*.joblib", verbose=True)
