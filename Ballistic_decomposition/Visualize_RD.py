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


def visualize_simulation(filename, plot_title, rate, envelop, show_average):
    # Main function to visualize the simulation
    # Load substrate from file
    substrate = np.loadtxt(filename, delimiter=',')

    # Parameters
    height, width = substrate.shape
    print(f"Height: {height}, Width: {width}")
    steps = int(np.max(substrate))

    # Create a custom colormap with gray as the background color
    colors = [(0.8, 0.8, 0.8)] + [plt.cm.viridis(i) for i in range(plt.cm.viridis.N)]
    custom_colormap = mcolors.LinearSegmentedColormap.from_list("custom", colors, N=steps + 1)

    # Visualization setup
    fig, ax = plt.subplots(figsize=(12, 8))  # Adjust the width and height as needed
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
        ax.imshow(vis_substrate, cmap=custom_colormap, aspect='auto', norm=mcolors.Normalize(vmin=0, vmax=steps))

        top_envelope = Envelop(vis_substrate)

        if envelop:
            # Compute and plot the top envelope
            ax.plot(range(width), top_envelope, color='red', linewidth=2)

        if show_average:
            average = np.mean(top_envelope)
            # print(f"Average height: {average}")
            ax.axhline(y=average, color='black', linewidth=2)

        ax.set_title(f"{plot_title} - Particle: {step}")

        # Relabel the y-axis
        ax.set_yticks(np.arange(0, height, height // 5))
        ax.set_yticklabels(np.arange(height, 0, -height // 5))

        ax.set_ylabel("Height", rotation=90, labelpad=20, verticalalignment='center')
        ax.set_xlabel("Substrate", labelpad=8)
        ax.set_xticks(np.arange(0, width, width // 5))

        # Convert the plot to an image and append to frames
        fig.canvas.draw()
        image = np.frombuffer(fig.canvas.tostring_rgb(), dtype='uint8')
        image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
        frames.append(image)

        if step % 100 == 0:
            print(f"Step: {step} / {steps}")

    # Save frames as an MP4 video with the same base filename
    video_filename = os.path.splitext(filename)[0] + '.mp4'
    imageio.mimsave(video_filename, frames, fps=rate)
    return video_filename


def Envelop(substrate):
    # Compute the envelop of the substrate
    height, width = substrate.shape
    top_envelope = np.zeros(width)
    for pos in range(width):
        if np.any(substrate[:, pos] > 0):  # If there's any nonzero value in the column
            top_envelope[pos] = np.argmax(substrate[:, pos] > 0) - 3
        else:
            top_envelope[pos] = height - 2
    return top_envelope


def main():
    parser = argparse.ArgumentParser(description="""

    Visualization the decomposition of particles on a substrate
    Input: Substrate text file, produced by RD_CLI.py
    Output: mp4 video

    Author: Le Chen (le.chen@auburn.edu, chenle02@gmail.com)
    Date: 2023-10-22


                                     """, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-f", "--file", type=str, required=True, help="Path to the substrate")
    parser.add_argument("-t", "--title", type=str, default="", help="Title of the plot (default: None)")
    parser.add_argument("-r", "--rate", type=int, help="Rate per frame (default: 4)")
    parser.add_argument("-e", "--envelop", action="store_true", help="Show the top envelop (default: False)")
    parser.add_argument("-a", "--average", action="store_true", help="Show the average height (default: False)")
    parser.add_argument("-p", "--play", action="store_true", help="Play the video after generation (default: False)")
    args = parser.parse_args()

    video_filename = visualize_simulation(args.file, args.title, args.rate, args.envelop, args.average)

    if args.play:
        os.system(f"mpv --loop=inf {video_filename}")


if __name__ == "__main__":
    main()