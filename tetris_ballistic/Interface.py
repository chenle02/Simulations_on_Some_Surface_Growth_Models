#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Sun Oct 22 08:51:34 PM EDT 2023
#

import numpy as np
import matplotlib.pyplot as plt
import argparse
from . import Envelop


def interface_width(filename, plot_title, reference_slope):
    # Main function to visualize the simulation
    # Load substrate from file
    substrate = np.loadtxt(filename, delimiter=",")

    # Parameters
    height, width = substrate.shape
    print(f"Height: {height}, Width: {width}")
    steps = int(np.max(substrate))
    interface = np.zeros(steps)

    # Compute the interface width
    for step in range(1, steps + 1):
        # Create a copy of the substrate for visualization
        vis_substrate = np.copy(substrate)

        # Replace values greater than the current step with 0
        vis_substrate[vis_substrate > step] = 0

        top_envelope = Envelop(vis_substrate)
        average = np.mean(top_envelope)

        interface[step - 1] = 0
        for pos in range(width):
            interface[step - 1] += np.power(top_envelope[pos] - average, 2) / width
        interface[step - 1] = np.sqrt(interface[step - 1])

    # Assuming 'time' is your x-axis data and 'interface' is your y-axis data
    time = np.array(range(1, steps + 1))
    quarter_length = len(time) // 4  # Compute the one-fourth point

    slopes = []

    # Loop from one-fourth of t to all t
    for end in range(quarter_length, len(time) + 1):
        current_time = time[:end]
        current_interface = interface[:end]

        log_time = np.log(current_time)
        log_interface = np.log(current_interface)

        # Fit a linear regression to the log-log data of the current window
        slope, _ = np.polyfit(log_time, log_interface, 1)
        slopes.append(slope)

    # Convert slopes to a numpy array for further processing if needed
    slopes = np.array(slopes)

    # Create side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # First plot: log-log plot of the interface width
    ax1.loglog(time, interface, "-o", label="Interface Width")
    ax1.set_xlabel("Log of Time (log(t)")
    ax1.set_ylabel("Interface Width in log")
    ax1.set_title("Log-Log plot of Interface Width vs Time")
    ax1.grid(True)

    # Second plot: slopes
    ax2.plot(time[quarter_length - 1 :], slopes, "-o", label="Computed Slopes")
    # ax2.axhline(y=reference_slope, color='r', linestyle='--', label=f'Reference Slope {reference_slope}')
    ax2.axhline(y=1 / 2, color="r", linestyle="--", label="Reference Slope 1/2")
    ax2.axhline(y=1 / 3, color="r", linestyle="--", label="Reference Slope 1/3")
    ax2.axhline(y=1 / 4, color="r", linestyle="--", label="Reference Slope 1/4")
    ax2.set_xlabel("Time (t)")
    ax2.set_ylabel("Slope")
    ax2.set_title("Slope of the log-log plot as a function of log(t)")
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(filename.replace(".txt", ".png"), dpi=300)
    # plt.show()

    return interface


def main():
    parser = argparse.ArgumentParser(
        description="""

    Plot the interface width
    Input: Substrate text file, produced by RD_CLI.py
    Output: mp4 video

    Author: Le Chen (le.chen@auburn.edu, chenle02@gmail.com)
    Date: 2023-10-22


                                     """,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-f", "--file", type=str, required=True, help="Path to the substrate"
    )
    parser.add_argument(
        "-t", "--title", type=str, default="", help="Title of the plot (default: None)"
    )
    parser.add_argument(
        "-s",
        "--slope",
        type=float,
        default=0.333,
        help="Additional line on the log-lot plot (default: 0.333)",
    )
    args = parser.parse_args()

    interface_width(args.file, args.title, args.slope)


if __name__ == "__main__":
    main()
