#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 07:07:59 PM EST 2024
#

import matplotlib.pyplot as plt
import numpy as np
import joblib
import os
from scipy.stats import t
import matplotlib.colors as mcolors
# from tetris_ballistic.image_loader import TetrominoImageLoader as TIL
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir


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


# Confidence level for 95% CI
confidence = 0.95
with_ci = False

stickiness = ["sticky", "nonsticky", "combined"]
for stick in stickiness:
    # Load the fluctuations_dict
    fluctuations_dict = joblib.load(f"fluctuations_{stick}_dict.joblib")

    for type_value, widths in fluctuations_dict.items():
        plt.figure(figsize=(10, 6))  # Create a new figure for each type_value
        fig, ax = plt.subplots(figsize=(10, 5))  # Use fig for the figure reference

        # Get the current color cycle from plt.rcParams
        color_cycle = plt.rcParams['axes.prop_cycle'].by_key()['color']
        color_index = 0

        global_min_length = 0

        for width_value, fluctuations in widths.items():
            color = color_cycle[color_index % len(color_cycle)]  # Cycle through colors
            color_index += 1  # Move to next color for next width_value

            # Determine the minimal length across all fluctuations for this type_value
            min_length = min(len(fluctuation) for fluctuation in fluctuations)
            if min_length > global_min_length:
                global_min_length = min_length

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

            if with_ci:
                plt.plot(log_time,
                         mean_log_curve + ci_margin,
                         color=darker_color,
                         linewidth=1.2,
                         linestyle='--',
                         label="95% CI Upper")
                plt.plot(log_time,
                         mean_log_curve - ci_margin,
                         color=darker_color,
                         linestyle='--',
                         linewidth=1.2,
                         label="95% CI Lower")

        max_width_value = max(widths.keys())
        min_log_fluc = 1.0 * combined_log_fluctuations_array.min()
        log_time = np.log10(np.arange(1, global_min_length + 1))
        plt.plot(log_time - (3 / 2) * np.log10(max_width_value), 1 / 3 * log_time + min_log_fluc, label="Slope 1/3", linestyle="--", color="red")
        plt.plot(log_time - (3 / 2) * np.log10(max_width_value), 1 / 2 * log_time + min_log_fluc, label="Slope 1/2", linestyle="-.", color="blue")

        plt.xlabel(r'Log$_{10}$(Step) - $\frac{3}{2}$ Log$_{10}$(Width)')
        plt.ylabel(r'Log$_{10}$(Fluctuation) - $\frac{1}{2}$ Log$_{10}$(Width)')
        plt.title(f'Log-Log Plot with 95% CI for {stick} {type_value}')
        plt.legend(loc='upper left')

        # Optionally add images
        config = rdc(pattern=f"config_{type_value}_{stick}.yaml")[0]
        print(f"config: {config}")
        TB = Tetris_Ballistic(config_file=os.path.join(configs_dir, config))
        images = TB.list_tetromino_images()
        n_images = len(images)

        if n_images < 10:
            # Define the spread of the images. This value can be adjusted based on your visual preference.
            spread = 0.05
            start_x = 0.6 - spread * (n_images - 1) / 2  # Adjust starting x-position based on the number of images

            for index, img_filename in enumerate(images):
                img = plt.imread(img_filename)
                imagebox = OffsetImage(img, zoom=0.2)
                # Calculate the x position for each image to be spread out
                x_position = start_x + index * spread
                ab = AnnotationBbox(imagebox, (x_position, 0.12), frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        filename = f'combined_loglog_plot_CI_type_{stick}_{type_value}.png'
        plt.savefig(filename)
        plt.close()
