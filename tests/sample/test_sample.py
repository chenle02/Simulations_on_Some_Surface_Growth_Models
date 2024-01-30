#!/usr/bin/env python3
import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_load_config():
    """
    This is a test function for the method save_config().
    """
    output_file = "test_sample_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=12, width=16, height=20)
        for i in range(100):
            TB.Sample_Tetris()
