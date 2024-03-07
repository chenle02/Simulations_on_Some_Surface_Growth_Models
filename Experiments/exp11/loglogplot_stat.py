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

# Load the fluctuations_dict
fluctuations_dict = joblib.load('fluctuations_dict.joblib')

# Confidence level for 95% CI
confidence = 0.95

for type_value, widths in fluctuations_dict.items():
    plt.figure(figsize=(10, 6))  # Create a new figure for each type_value

    # Determine the minimal length across all fluctuations for this type_value
    min_length = min(len(fluctuation) for width in widths.values() for fluctuation in width)

    combined_fluctuations = []  # To store all fluctuations up to min_length for calculating mean and CI

    # Get the current color cycle from plt.rcParams
    color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
    color_index = 0

    # Initialize a set to keep track of widths already added to the legend
    added_widths = set()


    for width_value, fluctuations in widths.items():
        color = color_cycle[color_index % len(color_cycle)]  # Cycle through colors
        color_index += 1  # Move to next color for next width_value

        # Generate a label for the width only if it hasn't been added to the legend yet
        label = f'Width {width_value}' if width_value not in added_widths else None
        added_widths.add(width_value)  # Mark this width as added

        for fluctuation in fluctuations:
            fluctuation_trimmed = fluctuation[:min_length]  # Trim fluctuation to min_length
            combined_fluctuations.append(fluctuation_trimmed)  # Add trimmed fluctuation for mean and CI calculation
            plt.plot(np.log10(np.arange(1, min_length + 1)), np.log10(fluctuation_trimmed), linestyle='-', color=color, alpha=0.5)

    combined_fluctuations_array = np.array(combined_fluctuations)

    # Calculate mean and SEM for each position up to the minimal length
    mean_curve = np.mean(combined_fluctuations_array, axis=0)
    sem_curve = sem(combined_fluctuations_array, axis=0)
    df = len(combined_fluctuations_array) - 1  # Degrees of freedom
    ci_margin = t.ppf((1 + confidence) / 2., df) * sem_curve  # Calculate the 95% CI

    x_data = np.log10(np.arange(1, min_length + 1))
    plt.plot(x_data, np.log10(mean_curve), color='black', linestyle='-', label='Mean')
    plt.plot(x_data, np.log10(mean_curve + ci_margin), color='black', linestyle='--', label='95% CI Upper')
    plt.plot(x_data, np.log10(mean_curve - ci_margin), color='black', linestyle='--', label='95% CI Lower')
    plt.legend(title="Width Values",
               bbox_to_anchor=(0.75, 1),
               loc='lower right')

    plt.xlabel('Log10(Transformed X)')
    plt.ylabel('Log10(Transformed Y)')
    plt.title(f'Log-Log Plot with 95% CI for Type {type_value}')

    filename = f'combined_loglog_plot_CI_type_{type_value}.png'
    plt.savefig(filename)
    plt.close()
