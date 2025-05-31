#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:54:15 AM EST 2024
#

import matplotlib.pyplot as plt
import numpy as np
import joblib
import glob
import os
# Process each fluctuations_*_dict.joblib file (one per stickiness category)
fluctuation_files = sorted(glob.glob('fluctuations_*_dict.joblib'))
if not fluctuation_files:
    print('No fluctuation joblib files found.')
for filepath in fluctuation_files:
    filename = os.path.basename(filepath)
    prefix = 'fluctuations_'
    suffix = '_dict.joblib'
    if not (filename.startswith(prefix) and filename.endswith(suffix)):
        continue
    stickiness = filename[len(prefix):-len(suffix)]
    print(f'Processing stickiness: {stickiness}')
    fluctuations_dict = joblib.load(filepath)
    # Iterate over each type_value from the database and its widths mapping
    for type_value, widths in fluctuations_dict.items():
        print(f' About to Log-Log Plot for stickiness {stickiness}, type {type_value}')
        plt.figure(figsize=(10, 6))
        unique_widths = sorted(widths.keys())
        colormap = plt.cm.viridis
        # Plot each width's fluctuation curves
        for idx, width_value in enumerate(unique_widths):
            fluctuations = widths[width_value]
            print(f'  Type: {type_value}, Width: {width_value}, # paths: {len(fluctuations)}')
            color = colormap(idx / max(len(unique_widths)-1, 1))
            # Plot each individual fluctuation path
            for path_idx, fluctuation in enumerate(fluctuations):
                if len(fluctuation) > 0:
                    x = np.arange(1, len(fluctuation) + 1)
                    x_data = np.log10(x)
                    y_data = np.log10(fluctuation)
                    x_off = x_data - (3/2) * np.log10(width_value)
                    y_off = y_data - (1/2) * np.log10(width_value)
                    # Label only the first path for each width to show in legend
                    label = f'Width {width_value}' if path_idx == 0 else ''
                    plt.plot(x_off, y_off, linestyle='-', color=color, alpha=0.2, label=label)
        plt.xlabel('Log10(Transformed X) - 3/2 Log10(Width)')
        plt.ylabel('Log10(Transformed Y) - 1/2 Log10(Width)')
        plt.title(f'Log-Log Plot for {stickiness} type {type_value}')
        plt.legend(loc='best')
        out_fname = f'loglog_plot_{stickiness}_{type_value}.png'
        plt.savefig(out_fname)
        plt.close()
