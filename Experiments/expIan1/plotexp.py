#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

# import numpy as np
# import joblib
# import os
import glob
# import re
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import matplotlib.pyplot as plt
from shapely.geometry import LineString

# Regex pattern to match filename and extract components
# pattern_parse = r'config_(?P<type>piece_\d+)_sticky_(?P<percentage>percentage_\d+)_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'
# pattern = 'config_Piece-4_sticky=1-0_w=200_seed=*.joblib'

# Initialize the fluctuations dictionary
# fluctuations_dict = {}
# files = glob.glob(pattern)

stickiness = ['1-0', '0-1', '1-1']
seeds = [0, 10, 20, 30, 40, 50]
thresholds = [.2, .3, .4, .5, .6, .7, .8, .9, 1]
list_of_slopes = {}
for piece_id in range(20):
    list_of_slopes[piece_id] = {}
    for sticky in stickiness:
        list_of_slopes[piece_id][sticky] = {}
        for seed in seeds:
            file = f'config_Piece-{piece_id}_sticky={sticky}_w=200_seed={seed}.joblib'
            print('file=', file)
            TB = Tetris_Ballistic.load_simulation(file)
            list_of_slopes[piece_id][sticky][seed] = {}
            for threshold in thresholds:
                s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=threshold)
                list_of_slopes[piece_id][sticky][seed][threshold] = s
