#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 07:07:59 PM EST 2024
#

import matplotlib.pyplot as plt
import numpy as np
import joblib
from scipy.stats import sem, t
import matplotlib.colors as mcolors


def make_darker(color, factor=0.5):
    """
    Make a color darker.

    :param color: Original color in a format recognized by matplotlib (e.g., name, hex).
    :param factor: Factor by which to darken the color (0 to 1, where 0 is no change and 1 is black).
    :return: Darker color as a hex string.
    """
    # Convert the original color to RGB
    rgb_original = mcolors.to_rgb(color)

    # Calculate the new color by interpolating towards black
    rgb_darker = [max(0, c * (1 - factor)) for c in rgb_original]

    # Convert the darker color back to hex format for plotting
    return mcolors.to_hex(rgb_darker)

# Load the fluctuations_dict
fluctuations_dict = joblib.load('fluctuations_dict.joblib')

# Confidence level for 95% CI
confidence = 0.95

for type_value, widths in fluctuations_dict.items():
    plt.figure(figsize=(10, 6))  # Create a new figure for each type_value

    # Get the current color cycle from plt.rcParams
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    color_index = 0

    for width_value, fluctuations in widths.items():
        color = color_cycle[color_index % len(color_cycle)]  # Cycle through colors
        color_index += 1  # Move to next color for next width_value

        # Determine the minimal length across all fluctuations for this type_value
        min_length = min(len(fluctuation) for fluctuation in fluctuations)

        combined_log_fluctuations = []  # To store all fluctuations up to min_length for calculating mean and CI
        log_time = np.log10(np.arange(1, min_length + 1)) - (3 / 2) * np.log10(width_value)
        number_path = 0
        for fluctuation in fluctuations:
            number_path += 1
            log_fluctuation_trimmed = np.log10(fluctuation[:min_length]) - (3 / 2) * np.log10(width_value)
            combined_log_fluctuations.append(log_fluctuation_trimmed)  # Add trimmed fluctuation for mean and CI calculation
            plt.plot(log_time,
                     log_fluctuation_trimmed,
                     linestyle='-',
                     color=color,
                     alpha=0.2)

        combined_log_fluctuations_array = np.array(combined_log_fluctuations)

        # Calculate mean and SEM for each position up to the minimal length
        mean_log_curve = np.mean(combined_log_fluctuations_array, axis=0)
        sem_log_curve = np.std(combined_log_fluctuations_array, axis=0, ddof=1)
        df = number_path - 1  # Degrees of freedom
        # ci_margin = t.ppf((1 + confidence) / 2., df) * sem_log_curve / np.sqrt(number_path)  # Calculate the 95% CI
        ci_margin = t.ppf((1 + confidence) / 2., df) * sem_log_curve

        darker_color = make_darker(color, factor=0.5)  # Make it 50% darker
        plt.plot(log_time,
                 mean_log_curve,
                 color=darker_color,
                 linestyle='-',
                 linewidth=1.8,
                 label=f"Mean {width_value}")
        plt.plot(log_time,
                 mean_log_curve + ci_margin,
                 color=darker_color,
                 linewidth=1.8,
                 linestyle='--',
                 label="95% CI Upper")
        plt.plot(log_time,
                 mean_log_curve - ci_margin,
                 color=darker_color,
                 linestyle='--',
                 linewidth=1.8,
                 label="95% CI Lower")

    plt.xlabel('Log10(Transformed X)')
    plt.ylabel('Log10(Transformed Y)')
    plt.title(f'Log-Log Plot with 95% CI for Type {type_value}')
    plt.legend(loc='upper left')

    filename = f'combined_loglog_plot_CI_type_{type_value}.png'
    plt.savefig(filename)
    plt.close()