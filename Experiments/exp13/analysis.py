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
pattern_parse = r'config_(?P<type>piece_\d+)_combined_(?P<percentage>percentage_\d+)_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'

# Initialize the fluctuations dictionary
fluctuations_dict = {}


# Generate numbers from 5 to 95 in steps of 5
percentages = list(range(5, 100, 5))
percentages += [98, 99]

# Process files for each percentage
for percentage in percentages:
    # Ensure the dictionary for this percentage is initialized
    formatted_percentage = str(percentage).zfill(2)
    fluctuations_dict[formatted_percentage] = {}
    print(f"Working on percentage files with percentage = {formatted_percentage}...")
    pattern = f"*_percentage_{formatted_percentage}_*.joblib"
    files = glob.glob(pattern)

    for file in files:
        print(f"Add file: {file}")
        basename = os.path.basename(file)
        match = re.match(pattern_parse, basename)
        if match:
            data = match.groupdict()
            width = int(data['width'])

            # Load simulation from file
            TB = Tetris_Ballistic.load_simulation(file)
            fl = TB.Fluctuation[:TB.FinalSteps]

            # Initialize the list for this width if it does not exist
            if width not in fluctuations_dict[formatted_percentage]:
                fluctuations_dict[formatted_percentage][width] = []

            # Append fluctuation data
            fluctuations_dict[formatted_percentage][width].append(fl)

# Saving the complete fluctuations dictionary to disk
print("Saving fluctuations_dict to disk...")
joblib.dump(fluctuations_dict, "fluctuations_dict.joblib")
