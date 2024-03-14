#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_T():
    """
    This is a test function for the piece 9 nonsticky.
    """
    output_file = "test_piece_9-5_nonsticky_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):
        piece_id_list = {5, 9}
        for piece_id in piece_id_list:
            TB = Tetris_Ballistic(config_file=f"./config_piece_{piece_id}_nonsticky.yaml")
            TB.Simulate()
            TB.visualize_simulation(plot_title=f"Piece {piece_id}, nonsticky",
                                    rate=4,
                                    video_filename=f"simulation_piece_{piece_id}_nonsticky.mp4",
                                    envelop=True,
                                    show_average=True,
                                    aspect="auto")
