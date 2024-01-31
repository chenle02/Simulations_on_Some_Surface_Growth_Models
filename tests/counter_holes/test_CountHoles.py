#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 02:17:33 PM EST 2024
#

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_CountHoles():
    """
    This is a test function for the square piece.
    """
    output_file = "test_CountHoles_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=42, width=100, height=200, steps=20000)
        TB.Simulate()
        TB.PrintStatus()
        TB.visualize_simulation(video_filename="a.mp4")
        holes = TB.count_holes()
        # holes = 1
        print("The number of holes is: ", holes)
