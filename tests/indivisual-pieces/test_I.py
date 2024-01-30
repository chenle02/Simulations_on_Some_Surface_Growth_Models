#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_I():
    """
    This is a test function for the Line piece.
    """
    output_file = "test_I_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=42)

        print("First, the sticky case:")
        for rot in range(4):
            print("I piece, Test rotation ", rot)
            TB.reset()
            i = 0
            while i < TB.steps:
                i = TB.Update_I(i, rot, sticky=True)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.ComputeSlope()
            TB.PrintStatus()

        print("Second, the non-sticky case:")
        for rot in range(4):
            print("I piece, Test rotation ", rot)
            TB.reset()
            i = 0
            while i < TB.steps:
                i = TB.Update_I(i, rot, sticky=False)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.ComputeSlope()
            TB.PrintStatus()
