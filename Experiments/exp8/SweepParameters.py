#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Mon Feb 19 10:30:05 PM EST 2024
#

"""
This script is used to sweep the parameters of the Tetris Ballistic simultaions.
"""
from tetris_ballistic.sweep_parameters import sweep_parameters as SP

ListWidth = [50, 100, 200, 500, 1000, 1500]
ListRandomSeeds = [10 * i for i in range(20)]
config_patterns = ["*piece_19_sticky.yaml",
                   "*piece_19_nonsticky.yaml",
                   "*piece_0*.yaml"]
SP(list_width=ListWidth,
   list_random_seeds=ListRandomSeeds,
   config_patterns=config_patterns,
   ratio=10)
