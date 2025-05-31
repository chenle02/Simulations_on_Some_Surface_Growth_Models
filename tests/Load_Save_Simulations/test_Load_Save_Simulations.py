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
    output_file = "test_Load_Save_Simulations_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        print("First save the simulation")
        # Use fewer steps for faster testing
        TB = Tetris_Ballistic(seed=42, width=100, height=200, steps=60)
        TB.Simulate()
        TB.PrintStatus()
        joblib_filename = "TB.Joblib"
        TB.save_simulation(joblib_filename)
        TB.PrintStatus(brief=True)
        TB.Substrate2PNG(frame_id=200)
        # TB.visualize_simulation(video_filename="a.mp4")

        print("Now load the simulation")
        TB2 = Tetris_Ballistic.load_simulation(joblib_filename)
        TB2.PrintStatus(brief=True)
        TB2.Substrate2PNG(frame_id=201)
