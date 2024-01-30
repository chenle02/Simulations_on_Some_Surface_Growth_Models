#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 02:17:33 PM EST 2024
#

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_1x1():
    """
    This is a test function for the square piece.
    """
    output_file = "test_1x1_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=42)

        print("First, the sticky case of 1x1 piece:")
        TB.reset()
        i = 0
        while i < TB.steps:
            i = TB.Update_1x1(i, sticky=True)
            if i == -1:
                print("Game Over, reach the top")
                break
        TB.ComputeSlope()
        TB.PrintStatus()
        # print(TB.substrate)
        # print(TB.HeightDynamics)

        print("Second, the non-sticky case of 1x1 piece:")
        TB.reset()
        i = 0
        while i < TB.steps:
            i = TB.Update_1x1(i, sticky=False)
            if i == -1:
                print("Game Over, reach the top")
                break
        TB.ComputeSlope()
        TB.PrintStatus()
        # print(TB.substrate)
        # print(TB.HeightDynamics)
