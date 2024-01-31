#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 03:03:00 PM EST 2024
#

import click
import os

# from ..Visualize_RD import visualize_simulation
# from tetris_ballistic.Visualize_RD import visualize_simulation
from Visualize_RD import visualize_simulation
# ... other subcommands if any ...


@click.group()
def cli():
    """
    Your CLI Tool Description
    """
    pass


@click.command()
@click.option('-f', '--file', required=True, type=str, help="Path to the substrate")
@click.option('-t', '--title', default="", type=str, help="Title of the plot (default: None)")
@click.option('-r', '--rate', type=int, help="Rate per frame (default: 4)")
@click.option('-e', '--envelop', is_flag=True, help="Show the top envelope (default: False)")
@click.option('-a', '--average', is_flag=True, help="Show the average height (default: False)")
@click.option('-p', '--play', is_flag=True, help="Play the video after generation (default: False)")
def visualize(file, title, rate, envelop, average, play):
    """
    Visualize the decomposition of particles on a substrate.
    """
    # Assuming visualize_simulation is a function that creates the video
    video_filename = visualize_simulation(file, title, rate, envelop, average)

    if play:
        os.system(f"mpv --loop=inf {video_filename}")


cli.add_command(visualize)


def main():
    """
    This is the main function
    """
    pass


if __name__ == '__main__':
    cli()
