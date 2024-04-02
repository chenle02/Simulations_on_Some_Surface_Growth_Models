#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

import numpy as np
import joblib
import os
import glob
import re
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

# Regex pattern to match filename and extract components
pattern_parse = r'config_(?P<type>piece_\d+)_combined_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'
width =75
pattern = f"*_w={width}*.joblib"

files = glob.glob(pattern)
dic_me = {}
height = 50
TB = Tetris_Ballistic.load_simulation(files[3])
print("The width is:", TB.width)
frame_id = TB.substrate[height, :]
frame_id = int( (np.min(frame_id[np.nonzero(frame_id)])) )

print(f"At height {height}, the frame id is {frame_id}")

print("With",TB.count_holes_stack(frame_id), "holes in the substrate at that height")

height_list = []

hole_hist = {}

interval = 10

steps = TB.height // interval

test_list = []

test_hist = {}

for i in range(interval):
    test_list.append(min(int(i*steps), TB.height-1))

for i in range(interval):
    test_hist[test_list[i]] = TB.count_holes_stack(test_list[i])

for i in range(10):
    height_list.append(min(int(TB.height*(1/(i+1))), TB.height-1))

height_list.reverse()

for i in range(10):
    hole_hist[height_list[i]] = TB.count_holes_stack(height_list[i])


print(height_list)
print(hole_hist)

print(" --- ")

print(test_list)
print(test_hist)

#for file in files:


#    fl =[]
    # Load simulation from file
#    TB = Tetris_Ballistic.load_simulation(file)

#    dic_me[file] = [TB.count_holes_stack(TB.FinalSteps // 3), TB.count_holes_stack(int(TB.FinalSteps * (2/3))), TB.count_holes_stack()]



# Saving the complete fluctuations dictionary to disk
#print("Saving hole counting to disk...")
#joblib.dump(dic_me, "holes_counted.joblib")
