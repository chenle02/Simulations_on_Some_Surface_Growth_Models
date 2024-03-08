#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_T():
    """
    This is a test function for the piece 14.
    """
    output_file = "test_piece_14_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(config_file="./config_piece_14_nonsticky.yaml")
        TB.Simulate()
        TB.visualize_simulation(plot_title="Piece 14, nonsticky",
                                rate=4,
                                video_filename="simulation_piece_14_nonsticky.mp4",
                                envelop=True,
                                show_average=True,
                                aspect="auto")

        TB = Tetris_Ballistic(config_file="./config_piece_14_sticky.yaml")
        TB.Simulate()
        TB.visualize_simulation(plot_title="Piece 14, sticky",
                                rate=4,
                                video_filename="simulation_piece_14_sticky.mp4",
                                envelop=True,
                                show_average=True,
                                aspect="auto")
