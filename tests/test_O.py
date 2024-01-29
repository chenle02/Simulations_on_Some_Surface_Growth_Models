#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 02:17:33 PM EST 2024
#

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_O():
    """
    This is a test function for the square piece.
    """
    output_file = "test_O_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=42)

        print("First, the sticky case:")
        for rot in range(4):
            print("O piece, Test rotation ", rot)
            TB.reset()
            i = 0
            while i < TB.steps:
                i = TB.Update_O(i, sticky=True)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.ComputeSlope()
            TB.PrintStatus()

        print("Second, the non-sticky case:")
        for rot in range(4):
            print("O piece, Test rotation ", rot)
            TB.reset()
            i = 0
            while i < TB.steps:
                i = TB.Update_O(i, sticky=False)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.ComputeSlope()
            TB.PrintStatus()
