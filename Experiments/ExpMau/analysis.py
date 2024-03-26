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

file='config_type_6_sticky_w=75_seed=50.joblib'

dic_me = {}


fl =[]
# Load simulation from file
TB = Tetris_Ballistic.load_simulation(file)
print(TB.count_holes_stack())

dic_me[file] = TB.count_holes_stack()


# Saving the complete fluctuations dictionary to disk
print("Saving hole counting to disk...")
joblib.dump(dic_me, "holes_counted.joblib")
