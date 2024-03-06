#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:54:15 AM EST 2024
#

import joblib
import matplotlib.pyplot as plt
import numpy as np

fluctuations_dict = joblib.load('fluctuations_dict.joblib')

for type_value, widths in fluctuations_dict.items():
    plt.figure(figsize=(10, 6))  # Create a new figure for each type_value

    # Prepare a list of unique widths and a colormap
    unique_widths = sorted(widths.keys())
    colormap = plt.cm.viridis  # You can choose any available colormap

    for width_value, fluctuations in widths.items():
        print(f'Type: {type_value}, Width: {width_value}, Number of Fluctuations: {len(fluctuations)}')

        # Determine the color for this width
        color_index = unique_widths.index(width_value) / len(unique_widths)
        color = colormap(color_index)

        for fluctuation in fluctuations:
            # Here, fluctuation is a list; the length might vary
            print(f'  Fluctuation Length: {len(fluctuation)}')

            if len(fluctuation) > 0:  # Ensure there's data to plot
                # Generate x_data based on the length of the current fluctuation list
                print(f"Fluctuation: {fluctuation}")
                x_data = np.log10(np.arange(1, len(fluctuation) + 1))
                y_data = np.array(np.log10(fluctuation))  # Convert fluctuation list to array for log10
                # y_data = np.log10(np.maximum(fluctuation, np.finfo(float).tiny))

                # Apply offsets to x_data and y_data for plotting
                x_data_offset = x_data - (3 / 2) * np.log10(width_value)
                y_data_offset = y_data - (1 / 2) * np.log10(width_value)

                plt.plot(x_data_offset, y_data_offset, linestyle='-', color=color, alpha=0.5, label=f'Width {width_value}' if width_value == unique_widths[0] else "")

    plt.xlabel('Log10(Transformed X) - 3/2 Log10(Width)')
    plt.ylabel('Log10(Transformed Y) - 1/2 Log10(Width)')
    plt.title(f'Log-Log Plot for Type {type_value}')

    filename = f'loglog_plot_type_{type_value}.png'
    plt.savefig(filename)
    plt.close()  # Close the figure to free memory
    break
