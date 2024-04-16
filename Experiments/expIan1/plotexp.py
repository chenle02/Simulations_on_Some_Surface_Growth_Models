#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

import numpy as np
# import joblib
# import os
# import glob
# import re
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
# import matplotlib.pyplot as plt
# from shapely.geometry import LineString

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
print("Compute the slope first...")
for piece_id in range(19):
    list_of_slopes[piece_id] = {}
    for sticky in stickiness:
        list_of_slopes[piece_id][sticky] = {}
        for seed in seeds:
            file = f'config_Piece-{piece_id}_sticky={sticky}_w=200_seed={seed}.joblib'
            #  print('file=', file)
            TB = Tetris_Ballistic.load_simulation(file)
            list_of_slopes[piece_id][sticky][seed] = {}
            for threshold in thresholds:
                s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=threshold)
                list_of_slopes[piece_id][sticky][seed][threshold] = s

print("Collecting the slope first...")
values = []
piece_id = 0
sticky = "0-1"
threshold = 0.6

for seed in seeds:
    values.append(list_of_slopes[piece_id][sticky][seed][threshold])

print(f"Values: {values}")

# for piece_id in range(19):
#     for sticky in stickiness:
#         for threshold in thresholds:
#             # Simulate a dataset of n=100 numbers, for example, random numbers from a normal distribution
#             data = list_of_slopes[piece_id][sticky][:][threshold]
#             print(f"Data= {data}")
#
#             # Calculate the mean
#             mean = np.mean(data)
#
#             # Calculate the standard deviation
#             std_dev = np.std(data)
#
#             # Calculate the standard error of the mean
#             sem = std_dev / np.sqrt(len(data))
#
#             print(f"Piece {piece_id} and sticky configuration {sticky} and threshold {threshold}:")
#             print(f"Mean of the dataset: {mean:.2f}")
#             print(f"Standard Deviation of the dataset: {std_dev:.2f}")
#             print(f"Standard Error of the Mean: {sem:.2f}")
