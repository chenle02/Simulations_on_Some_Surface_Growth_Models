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




TB = Tetris_Ballistic.load_simulation('holes_counted.joblib')

keys_with_value_1 =[]


for key, value in TB.items():
    if value == 1:
        keys_with_value_1.append(key)

# Print the keys with value 1
print("Dictionary entries with value 1:")
for key in keys_with_value_1:
    print(key)


print(TB)

