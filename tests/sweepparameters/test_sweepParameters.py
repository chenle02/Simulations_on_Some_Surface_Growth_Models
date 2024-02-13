#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed 31 Jan 2024 10:15:03 PM CST
#


import pytest
import contextlib
import numpy as np
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_SweepParameters():
    """
    This script is used to sweep the parameters of the Tetris Ballistic simultaions.
    """
    output_file = "test_SweepParameters_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        ListRandomSeeds = [10 ** i for i in range(8)]
        ListWidth = [50, 100, 200, 500, 1000, 2000, 5000, 10000]
        # ListHeight = [w * 1.2 for w in ListWidth]
        # ListSteps = [w * w for w in ListWidth]
        ListDensities = []

        EnptyDensity = {'Piece-0': [0, 0],
                        'Piece-1': [0, 0],
                        'Piece-2': [0, 0],
                        'Piece-3': [0, 0],
                        'Piece-4': [0, 0],
                        'Piece-5': [0, 0],
                        'Piece-6': [0, 0],
                        'Piece-7': [0, 0],
                        'Piece-8': [0, 0],
                        'Piece-9': [0, 0],
                        'Piece-10': [0, 0],
                        'Piece-11': [0, 0],
                        'Piece-12': [0, 0],
                        'Piece-13': [0, 0],
                        'Piece-14': [0, 0],
                        'Piece-15': [0, 0],
                        'Piece-16': [0, 0],
                        'Piece-17': [0, 0],
                        'Piece-18': [0, 0],
                        'Piece-19': [0, 0]}
        StickyList = [[1, 0], [0, 1], [1, 1]]
        for w in ListWidth:
            for seed in ListRandomSeeds:
                for piece_id in range(20):
                    for sticky in StickyList:
                        sticky_str = f"{sticky[0]}-{sticky[1]}"  # Format the sticky pair as a string
                        config_filename = f'config_Piece-{piece_id}_sticky={sticky_str}_w={w}_seed={seed}.yaml'
                        print(f"Config file: {config_filename}")
                        WorkingDensity = EnptyDensity.copy()
                        WorkingDensity['Piece-' + str(piece_id)] = [1, 0]
                        TB = Tetris_Ballistic(density=WorkingDensity,
                                              width=int(w),
                                              height=int(w * 1.2),
                                              steps=int(w * w),
                                              seed=seed)
                        TB.save_config(config_filename)
