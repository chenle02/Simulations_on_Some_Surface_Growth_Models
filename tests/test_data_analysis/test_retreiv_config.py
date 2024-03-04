#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc
from tetris_ballistic.retrieve_default_configs import configs_dir
from tetris_ballistic.data_analysis_utitilies import retrieve_fluctuations

def test_retreive_default_configs():
    """
    This is a test function for data_analysis_utilities.py
    """
    output_file = "test_data_analysis_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        pattern = "../../Experiments/exp10/*w=50*.joblib"
        retrieve_fluctuations(pattern, verbose=True)
