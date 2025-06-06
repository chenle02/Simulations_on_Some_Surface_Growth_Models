#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 07:07:59 PM EST 2024
#

import matplotlib.pyplot as plt
import numpy as np
import joblib
from scipy.stats import t
import matplotlib.colors as mcolors
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from tetris_ballistic.tetris_ballistic import obtain_images, make_darker


# ------------------------------
# Parameters for the script
# ------------------------------
# 1. Confidence level for 95% CI
# 2. Whether include 95% CI in the plot
# 4. List of stickiness to include


def plotfluctuations(with_ci: bool = False) -> None:
    """
    This is function to plot all fluctuations for different stickiness and
    type_value. The function will save the plots as png images.

    """
    stickiness = ["sticky", "nonsticky", "combined"]
    confidence = 0.95
    for stick in stickiness:
        # Load the fluctuations_dict
        fluctuations_dict = joblib.load("fluctuations_dict.joblib")

        for percentage, widths in fluctuations_dict.items():
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

                combined_fluctuations = []  # To store all fluctuations up to min_length for calculating mean and CI
                number_path = 0

                for fluctuation in fluctuations:
                    number_path += 1
                    combined_fluctuations.append(fluctuation[:min_length])
                    plt.plot(np.arange(1, len(fluctuation) + 1),
                             fluctuation,
                             linestyle='-',
                             color=color,
                             alpha=0.2)

                combined_fluctuations_array = np.array(combined_fluctuations)

                # Calculate mean curve
                mean_curve = np.mean(combined_fluctuations_array, axis=0)

                darker_color = make_darker(color, factor=0.5)  # Make it 50% darker
                plt.plot(np.arange(1, min_length + 1),
                         mean_curve,
                         color=darker_color,
                         linestyle='-',
                         linewidth=1.8,
                         label=f"Mean {width_value}")

                # Calculate 95% CI curve
                if with_ci:
                    sem_curve = np.std(combined_fluctuations_array, axis=0, ddof=1)
                    df = number_path - 1  # Degrees of freedom
                    # ci_margin = t.ppf((1 + confidence) / 2., df) * sem_log_curve / np.sqrt(number_path)  # Calculate the 95% CI
                    ci_margin = t.ppf((1 + confidence) / 2., df) * sem_curve
                    plt.plot(np.arange(1, min_length + 1),
                             mean_curve + ci_margin,
                             color=darker_color,
                             linewidth=1.2,
                             linestyle='--',
                             label="95% CI Upper")
                    plt.plot(np.arange(1, min_length + 1),
                             mean_curve - ci_margin,
                             color=darker_color,
                             linestyle='--',
                             linewidth=1.2,
                             label="95% CI Lower")

            plt.xlabel('step or time')
            plt.ylabel('fluctuation')
            plt.title(f'Fluctuations{" with 95% CI" if with_ci else ""} for {percentage}% of nonsticky for combined piece 19')
            plt.legend(loc='upper left')

            # Optionally add images
            images = obtain_images("piece_19", "combined")
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

            filename = f"combined_original{'_CI' if with_ci else ''}_combined_percentage_{percentage}.png"
            plt.savefig(filename)
            plt.close()


if __name__ == "__main__":
    # plotfluctuations(with_ci=True)
    plotfluctuations(with_ci=False)
