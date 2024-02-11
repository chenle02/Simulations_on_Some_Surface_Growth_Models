#!/usr/bin/env python3
import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_showdata():
    """
    This is a test function for the method save_config().
    """
    output_file = "test_showdata.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=12, width=200, height=300, steps=12000)
        # TB = Tetris_Ballistic(seed=None, width=16, height=20)
        TB.save_config("test_save_config.yaml")
        TB.Simulate()
        print("First show data without save the figure file")
        TB.ShowData()
        print("Then save the figure")
        TB.ShowData("Figure.png")
