#!/usr/bin/env python3

import pytest
import contextlib
import os
from tetris_ballistic.SweepParameters import SweepParameters


def test_resize():
    """
    This is a test function for the square piece.
    """
    output_file = "test_resize_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):
        ListWidth = [50, 80]
        ListRandomSeeds = [10, 20]
        config_patterns = ["*piece_19_sticky.yaml",
                           "*piece_19_nonsticky.yaml",
                           "*piece_0*.yaml"]
        SweepParameters(list_width=ListWidth,
                        list_random_seeds=ListRandomSeeds,
                        config_patterns=config_patterns)