#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 07:07:59 PM EST 2024
#

import matplotlib.pyplot as plt
import numpy as np
import joblib
from scipy.stats import linregress
from scipy.stats import t
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from tetris_ballistic.tetris_ballistic import obtain_images, make_darker


def loglogplot_stat(number_of_segments: int = 10, with_ci: bool = False) -> None:
    """
    This function creates log-log plots for the fluctuations of the width values.
    """
    confidence = 0.95
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

            combined_log_fluctuations = []  # To store all fluctuations up to min_length for calculating mean and CI
            number_path = 0

            for fluctuation in fluctuations:
                number_path += 1
                log_time = np.log10(np.arange(1, len(fluctuation) + 1)) - (3 / 2) * np.log10(width_value)
                log_fluctuation_trimmed = np.log10(fluctuation[:min_length]) - (1 / 2) * np.log10(width_value)
                combined_log_fluctuations.append(log_fluctuation_trimmed)  # Add trimmed fluctuation for mean and CI calculation
                plt.plot(log_time,
                         np.log10(fluctuation) - (1 / 2) * np.log10(width_value),
                         linestyle='-',
                         color=color,
                         alpha=0.2)

            combined_log_fluctuations_array = np.array(combined_log_fluctuations)

            # Calculate mean curve
            mean_log_curve = np.mean(combined_log_fluctuations_array, axis=0)
            log_time = np.log10(np.arange(1, min_length + 1)) - (3 / 2) * np.log10(width_value)

            darker_color = make_darker(color, factor=0.5)  # Make it 50% darker
            plt.plot(log_time,
                     mean_log_curve,
                     color=darker_color,
                     linestyle='-',
                     linewidth=1.8,
                     label=f"Mean {width_value}")

            # Compute the slope of the mean curve
            segment_indices = np.round(np.linspace(0, len(log_time), number_of_segments + 1)).astype(int)  # 11 endpoints for 10 segments
            print(f"Segment indices: {segment_indices}")

            for i in range(len(segment_indices) - 2):  # -2 ensures we look at pairs of segments
                start_idx = segment_indices[i]
                end_idx = segment_indices[i + 2]  # +2 to include the next segment fully

                seg_log_time = log_time[start_idx:end_idx]
                seg_mean_log_curve = mean_log_curve[start_idx:end_idx]

                slope, intercept, r_value, p_value, std_err = linregress(seg_log_time, seg_mean_log_curve)

                # # Determine the position for the slope label
                # # mid_point_index = len(seg_log_time) // 2  # Mid-point of segment
                # text_x = log_time[segment_indices[i + 1]]
                # # text_y = reg_line[mid_point_index] + (reg_line.max() - reg_line.min()) * 0.2  # Slightly above the line
                # text_y = mean_log_curve[mid_point_index]
                #

                # Example values
                log_time_length = len(log_time)  # Assuming log_time is already defined

                # Calculate the total range in a logarithmic sense
                total_range = np.log10(log_time_length)

                # Generate segment boundaries in the log scale
                segment_boundaries_log = np.logspace(0, total_range, num=number_of_segments + 1, base=10)

                # Map to integer indices (round down to ensure we stay within bounds)
                segment_indices = np.unique(np.floor(segment_boundaries_log).astype(int))

                # Ensure the last index is included
                segment_indices[-1] = min(segment_indices[-1], log_time_length - 1)

                # # Calculating regression line values
                # reg_line = intercept + slope * seg_log_time
                #
                # # Plotting the regression line
                # plt.plot(seg_log_time, reg_line, linestyle=':', color='red')

                # Calculate the mid-point x-coordinate for text placement
                text_x = (seg_log_time[0] + seg_log_time[-1]) / 2
                # Calculate the corresponding y-value on the regression line for text placement
                text_y = intercept + slope * text_x

                # Adding the slope number as text on the plot
                # plt.text(text_x,
                #          text_y,
                #          f"{slope:.2f}",
                #          horizontalalignment='center',
                #          color=darker_color,
                #          fontsize=9)
                plt.text(text_x, text_y, f"{slope:.2f}",
                         horizontalalignment='center',
                         color=make_darker(color, factor=0.8),
                         fontsize=9,
                         fontweight='bold',
                         rotation=0,
                         bbox=dict(facecolor='white',
                                   alpha=0.2,
                                   edgecolor='none',
                                   boxstyle='round,pad=0.2'))

                print(f"Segment {i+1}-{i+2}: Slope={slope}, R^2={r_value**2}")

            # Calculate 95% CI curve
            if with_ci:
                sem_log_curve = np.std(combined_log_fluctuations_array, axis=0, ddof=1)
                df = number_path - 1  # Degrees of freedom
                # ci_margin = t.ppf((1 + confidence) / 2., df) * sem_log_curve / np.sqrt(number_path)  # Calculate the 95% CI
                ci_margin = t.ppf((1 + confidence) / 2., df) * sem_log_curve
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
        min_log_fluc = 1.01 * combined_log_fluctuations_array.min()
        log_time = np.log10(np.arange(1, global_min_length + 1))
        plt.plot(log_time - (3 / 2) * np.log10(max_width_value),
                 1 / 3 * log_time + min_log_fluc,
                 label="Slope 1/3",
                 linestyle="-.",
                 color="red")
        plt.plot(log_time - (3 / 2) * np.log10(max_width_value),
                 1 / 2 * log_time + min_log_fluc,
                 label="Slope 1/2",
                 linestyle="--",
                 color="blue")
        plt.plot(log_time - (3 / 2) * np.log10(max_width_value),
                 2 / 3 * log_time + min_log_fluc,
                 label="Slope 2/3",
                 linestyle="-.",
                 color="red")

        plt.xlabel(r'Log$_{10}$(Step) - $\frac{3}{2}$ Log$_{10}$(Width)')
        plt.ylabel(r'Log$_{10}$(Fluctuation) - $\frac{1}{2}$ Log$_{10}$(Width)')
        plt.title(f'Log-Log plots{" with 95% CI" if with_ci else ""} for {percentage}% of nonsticky for combined piece 19')
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

        filename = f"combined_loglog_plot{'_CI' if with_ci else ''}_combined_percentage_{percentage}.png"
        plt.savefig(filename)
        plt.close()


if __name__ == "__main__":
    loglogplot_stat(number_of_segments=10, with_ci=False)
