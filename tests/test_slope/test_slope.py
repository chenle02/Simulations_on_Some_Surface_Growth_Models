#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_T():
    """
    This is a test function for ComputeSlpoes() method in Tetris_Ballistic class.
    """
    output_file = "test_piece_slope.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(config_file="./config_piece_14_nonsticky.yaml")
        TB.Simulate()
        # print(f"Fluctuation {TB.Fluctuation}")
        s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.99)
        print(f"Piece 14, non-sticky: slope = {s}\n\n")

        TB = Tetris_Ballistic(config_file="./config_piece_14_sticky.yaml")
        TB.Simulate()
        # print(f"Fluctuation {TB.Fluctuation}")
        s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.99)
        print(f"Piece 14, sticky: slope = {s}")
