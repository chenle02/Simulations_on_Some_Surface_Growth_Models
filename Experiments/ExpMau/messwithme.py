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
print(TB)

