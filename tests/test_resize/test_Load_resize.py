#!/usr/bin/env python3

import pytest
import contextlib
import os
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_resize():
    """
    This is a test function for the square piece.
    """
    output_file = "test_resize_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        joblib_filename = "TB.Joblib"
        if joblib_filename not in os.listdir():
            print("First save the simulation")
            TB = Tetris_Ballistic(seed=42, width=100, height=400, steps=600)
            TB.Simulate()
            TB.PrintStatus()
            TB.save_simulation(joblib_filename)
            TB.PrintStatus(brief=True)
            TB.visualize_simulation(video_filename="TB.mp4")

        print("Now load the simulation")
        TB2 = Tetris_Ballistic.load_simulation(joblib_filename)
        TB2.resize(new_height=100)
        TB2.PrintStatus(brief=True)
        TB2.visualize_simulation(video_filename="TB2.mp4",
                                 envelop=True,
                                 show_average=True)
