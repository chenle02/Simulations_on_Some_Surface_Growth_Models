#!/usr/bin/env python3
import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_load_config():
    """
    This is a test function for the method save_config().
    """
    output_file = "test_save_config_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=12, width=16, height=20)
        # TB = Tetris_Ballistic(seed=None, width=16, height=20)
        TB.save_config("test_save_config.yaml")

        TB.config_data["seed"] = None
        TB.config_data["Piece-19"] = [10, 90]
        # TB = Tetris_Ballistic(seed=None)
        TB.save_config("test_save_config_with_None.yaml")
