#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

import numpy as np
# import joblib
import os
# import glob
# import re
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import matplotlib.pyplot as plt
from shapely.geometry import LineString

# Regex pattern to match filename and extract components
# pattern_parse = r'config_(?P<type>piece_\d+)_combined_(?P<percentage>percentage_\d+)_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'

# Initialize the fluctuations dictionary
fluctuations_dict = {}


# Generate numbers from 5 to 95 in steps of 5
# percentages = list(range(5, 100, 5))
# percentages += [98, 99]

# Process files for each percentage
# for percentage in percentages:
# Ensure the dictionary for this percentage is initialized
#     formatted_percentage = str(percentage).zfill(2)
#     fluctuations_dict[formatted_percentage] = {}
#     print(f"Working on percentage files with percentage = {formatted_percentage}...")
#     pattern = f"*_percentage_{formatted_percentage}_*.joblib"
#     files = glob.glob(pattern)
file = 'config_Piece-9_sticky=0-1_w=200_seed=50.joblib'
print(f"Add file: {file}")
basename = os.path.basename(file)
# match = re.match(pattern_parse, basename)
# data = match.groupdict()
# width = int(data['width'])
width = 200
# Load simulation from file
TB = Tetris_Ballistic.load_simulation(file)
alpha = 0.1
beta = 0.9

# slope = TB.ComputeSlope_fine(low_threshold=0.01, high_threshold=0.1)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.2)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.3)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.4)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.5)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.6)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.7)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.8)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.9)
slope = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=1)
print(f'Slope = {slope}')
# logfl = np.log10(fl)
# maxfl = np.max(logfl)
# alphaline = np.full((fl.size), alpha * maxfl)  # Horizontal line at alpha level
# betaline = np.full((fl.size), beta * maxfl)  # Horizontal line at beta level
# print('Maximum is ', maxfl)
# print('Fluctuation vector size= ', fl.size)
# slope1 = np.polyfit(np.log10(range(1, fl.size)), np.log10(fl[1:fl.size]), 1)
# slope2 = np.polyfit(np.log10(range(100, int(10**3.5))), np.log10(fl[100:int(10**3.5)]), 1)
# s1 = (np.log10(fl[100]) - np.log10(fl[1])) / (2 - 0)
# s2 = (np.log10(fl[int(10**3.5)] - np.log10(fl[100]))) / (3.5 - 2)
# print('First slope = ', s1)
# print('Second slope = ', s2)
# print(slope1)
# print(slope2)
# plt.plot(np.log10(range(fl.size)), logfl)
# plt.plot(np.log10(range(fl.size)), alphaline)
# plt.plot(np.log10(range(fl.size)), betaline)
# alphagraph = LineString(np.column_stack((np.log10(range(fl.size)), alphaline)))
# betagraph = LineString(np.column_stack((np.log10(range(fl.size)), betaline)))
# logflgraph = LineString(np.column_stack((np.log10(range(fl.size)), logfl)))
# intersection_af = alphagraph.intersection(logflgraph)
# intersection_bf = betagraph.intersection(logflgraph)

# flag = False
# i = 1
# while (not flag) or (i != fl.size):
#     i += 1
#     aline = np.full(i, alpha * maxfl)
#     agraph = LineString(np.column_stack((np.log10(range(i)), aline)))
#    for j in range(i):
#         flline[j] = np.log10(fl[j])
#     intersection_afl = agraph.intersection(flline)
#    print('Inter=', intersection_afl)

# idx = np.argwhere(np.diff(np.sign(alphaline - logfl))).flatten()
# print('idx=', idx)
# plt.plot(alphaline[idx], logfl[idx], 'ro')

# if intersection_af.geom_type == 'MultiPoint':
#     plt.plot(*LineString(intersection_af).xy, 'o')
# elif intersection_af.geom_type == 'Point':
#     plt.plot(*intersection_af.xy, 'o')
# if intersection_bf.geom_type == 'MultiPoint':
#    plt.plot(*LineString(intersection_bf).xy, 'o')
# elif intersection_bf.geom_type == 'Point':
#    plt.plot(*intersection_bf.xy, 'o')
# plt.axhline(y=maxfl, color='g')  # Line at maximum
# plt.axhline(y=beta * maxfl, color='g')  #  Line at beta % level
# plt.axhline(y=alpha * maxfl, color='g')  #  Line at alpha % level
# plt.axvline(x=2, color='b')
# plt.axvline(x=3.5, color='r')
# plt.axhline(y=np.log10(fl[100]), color='b')
# plt.axhline(y=np.log10(fl[int(10**3.5)]), color='r')
# x1, y1 = [0, 2], [np.log10(fl[1]), np.log10(fl[100])]
# x2, y2 = [2, 3.5], [np.log10(fl[100]), np.log10(fl[int(10**3.5)])]
# plt.plot(x1, y1, x2, y2)
# plt.axis('scaled')
# plt.show()
