#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Sun Oct 22 08:51:34 PM EDT 2023
#

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import imageio
import argparse
import os
# from . import Envelop
# from tetris_ballistic.RD_CLI import Envelop
# from .RD_CLI import Envelop
from RD_CLI import Envelop


def visualize_simulation(substrate_source,
                         plot_title="",
                         rate=4,
                         envelop=False,
                         show_average=False):
    """
    Visualize the particle deposition simulation and generate a video.

    This function visualizes the deposition process as an animation. It can
    accept either the path to a substrate data file or the substrate data
    directly as a NumPy array. When a filename is provided as a string, it
    loads the substrate data from the file. The function supports visualizing
    the top envelope and average height of the deposited particles. The final
    output is saved as an mp4 video file.

    Parameters
    ----------
    substrate_source : str or numpy.ndarray
        The source of the substrate data. This can be either a string
        specifying the path to the substrate data file, or the substrate data
        itself as a NumPy array.
    plot_title : str, optional (default: "")
        The title of the plot.
    rate : int, optional (default: 4)
        The frame rate for the video.
    envelop : bool, optional (default: False)
        Flag to indicate whether to show the top envelope.
    show_average : bool, optional (default: False)
        Flag to indicate whether to show the average height.

    Returns
    -------
    str
        The filename of the generated mp4 video.
    """
    # Load substrate
    if isinstance(substrate_source, str):
        filename = substrate_source
        substrate = np.loadtxt(filename, delimiter=",")
    else:
        substrate = substrate_source

    # Parameters
    height, width = substrate.shape
    print(f"Height: {height}, Width: {width}")
    steps = int(np.max(substrate))

    # Create a custom colormap with gray as the background color
    colors = [(0.8, 0.8, 0.8)] + [plt.cm.viridis(i)
                                  for i in range(plt.cm.viridis.N)]
    custom_colormap = mcolors.LinearSegmentedColormap.from_list(
        "custom", colors, N=steps + 1
    )

    # Visualization setup
    # Adjust the width and height as needed
    fig, ax = plt.subplots(figsize=(12, 8))
    frames = []

    # steps = 100  # for debug only
    # Simulation
    for step in range(1, steps + 1):
        # Create a copy of the substrate for visualization
        vis_substrate = np.copy(substrate)

        # Replace values greater than the current step with 0
        vis_substrate[vis_substrate > step] = 0

        # Visualize the current state and save as a frame
        ax.clear()
        ax.imshow(
            vis_substrate,
            cmap=custom_colormap,
            aspect="auto",
            norm=mcolors.Normalize(vmin=0, vmax=steps),
        )

        top_envelope = Envelop(vis_substrate)

        if envelop:
            # Compute and plot the top envelope
            ax.plot(range(width), top_envelope, color="red", linewidth=2)

        if show_average:
            average = np.mean(top_envelope)
            # print(f"Average height: {average}")
            ax.axhline(y=average, color="black", linewidth=2)

        ax.set_title(f"{plot_title} - Particle: {step}")

        # Relabel the y-axis
        ax.set_yticks(np.arange(0, height, height // 5))
        ax.set_yticklabels(np.arange(height, 0, -height // 5))

        ax.set_ylabel("Height", rotation=90, labelpad=20,
                      verticalalignment="center")
        ax.set_xlabel("Substrate", labelpad=8)
        ax.set_xticks(np.arange(0, width, width // 5))

        # Convert the plot to an image and append to frames
        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.tostring_rgb(), dtype="uint8")
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        frames.append(image)

        if step % 100 == 0:
            print(f"Step: {step} / {steps}")

    # Save frames as an MP4 video with the same base filename
    video_filename = os.path.splitext(filename)[0] + ".mp4"
    imageio.mimsave(video_filename, frames, fps=rate)
    return video_filename


def main():
    """
    Main function to execute the particle deposition visualization script.

        This script visualizes the process of particle deposition based on the
        data from a substrate simulation. It generates a video showing the
        evolution of the deposition over time. The script offers several
        command-line options to customize the visualization, such as showing
        the top envelope, the average height, and adjusting the video playback
        rate.

    Options:

    + -f, --file      : Required. Path to the substrate file containing simulation data.
    + -t, --title     : Optional. Title of the plot. If not provided, no title is displayed.
    + -r, --rate      : Optional. Frame rate for the video. Default is 4 frames per second.
    + -e, --envelop   : Optional. Flag to display the top envelope of the deposition. Default is False.
    + -a, --average   : Optional. Flag to display the average height of the deposition. Default is False.
    + -p, --play      : Optional. Flag to automatically play the video after generation. Default is False.

    Example:

    .. code-block:: bash

        > python3 Visualize_RD.py -f substrate.txt -t "Simulation Title" -r 10 --envelop --average --play

    This command will run the script on 'substrate.txt', set a title, use a frame rate of 10 fps,
    and display both the top envelope and average height in the visualization.
    """

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-f", "--file",
        type=str, required=True,
        help="Path to the substrate"
    )
    parser.add_argument(
        "-t", "--title",
        type=str, default="", help="Title of the plot (default: None)"
    )
    parser.add_argument(
        "-r", "--rate",
        type=int,
        help="Rate per frame (default: 4)"
    )
    parser.add_argument(
        "-e", "--envelop",
        action="store_true",
        help="Show the top envelop (default: False)",
    )
    parser.add_argument(
        "-a", "--average",
        action="store_true",
        help="Show the average height (default: False)",
    )
    parser.add_argument(
        "-p", "--play",
        action="store_true",
        help="Play the video after generation (default: False)",
    )
    args = parser.parse_args()

    video_filename = visualize_simulation(
        args.file, args.title, args.rate, args.envelop, args.average
    )

    if args.play:
        os.system(f"mpv --loop=inf {video_filename}")


if __name__ == "__main__":
    main()
