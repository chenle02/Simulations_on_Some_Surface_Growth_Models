#!/usr/bin/env python3

import os
import numpy as np
import joblib
import glob
import matplotlib.pyplot as plt
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import argparse

# Create the parser
parser = argparse.ArgumentParser(description='Analyze Tetris Ballistic simulations.')

# Add the arguments
parser.add_argument('--width', type=int, required=True, help='Specify the width')
parser.add_argument('--piece_id', type=int, required=True, help='Specify the piece ID')
parser.add_argument('--type', choices=['sticky', 'non-sticky', 'combined'], required=True, help='Specify the type: sticky, non-sticky, or combined')
parser.add_argument('--output_filename', type=str, required=True, help='Specify the output filename for the plot')

# Parse the arguments
args = parser.parse_args()

# Adjust the pattern to match files in the folder based on the new arguments
pattern = f"./config_piece_{args.piece_id}_{args.type}_w={args.width}*.joblib"

# Use glob to find files matching the pattern
files = glob.glob(pattern)

TBs = []
logfluctuations = []
MaxStep = 0
# Loop over the files and load them
for file_path in files:
    TB = Tetris_Ballistic.load_simulation(file_path)
    if TB.FinalSteps > MaxStep:
        MaxStep = TB.FinalSteps
    TBs.append(TB)
    fl = np.log10(np.trim_zeros(TB.Fluctuation))
    logfluctuations.append(fl)

# Create a single figure and axis for plotting
fig, ax = plt.subplots(figsize=(10, 6))

logtime = np.log10(np.array(range(1, MaxStep + 1)))

# Iterate over the list of arrays and plot each one on the same axis
for i, arr in enumerate(logfluctuations):
    ax.plot(logtime[:len(arr)], arr, label=f'Simulation {i+1}')

ax.plot(logtime, 1 / 3 * logtime, label="Slope 1/3", linestyle="--", color="red", linewidth=6)
ax.plot(logtime, 1 / 2 * logtime, label="Slope 1/2", linestyle="-.", color="blue", linewidth=6)

# Set titles and labels
ax.set_title('Logarithmic Fluctuations Over Time')
ax.set_xlabel('Log Time')
ax.set_ylabel('Log Fluctuations')

# Saving the plot to the specified output filename
plt.tight_layout()
plt.savefig(args.output_filename)
# Optionally, you can also display the plot with plt.show(), but typically for scripts it's either/or.
# plt.show()
