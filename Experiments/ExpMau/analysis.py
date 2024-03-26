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

for file in files:


    fl =[]
    # Load simulation from file
    TB = Tetris_Ballistic.load_simulation(file)

    dic_me[file] = [TB.count_holes_stack(TB.FinalSteps // 3), TB.count_holes_stack(int(TB.FinalSteps * (2/3))), TB.count_holes_stack()]


# Saving the complete fluctuations dictionary to disk
print("Saving hole counting to disk...")
joblib.dump(dic_me, "holes_counted.joblib")
