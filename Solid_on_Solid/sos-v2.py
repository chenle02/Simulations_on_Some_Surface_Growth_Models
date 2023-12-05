#!/usr/bin/env python3
# Created at Tue Dec  5 12:30:10 PM EST 2023

import argparse
import numpy as np


def run_simulation(width, steps, prob_deposition):
    """
    Run the solid-on-solid model simulation.

    :param width: Width of the grid.
    :param steps: Number of simulation steps.
    :param prob_deposition: Probability of deposition.
    :return: A numpy array of the simulation grid after 'steps' iterations.
    """
    prob_absorption = 1 - prob_deposition
    grid = np.zeros((steps, width), dtype=int)

    for step in range(steps):
        for position in range(width):
            # Implement the deposition and absorption logic here
            # For example:
            # if np.random.random() < prob_deposition:
            #     grid[step, position] += 1
            # elif np.random.random() < prob_absorption:
            #     grid[step, position] = max(0, grid[step, position] - 1)
            pass

    return grid


def main():
    parser = argparse.ArgumentParser(description="Solid-on-Solid Model Simulation")
    parser.add_argument('-w', '--width', type=int, default=10, help='Width of the grid')
    parser.add_argument('-s', '--steps', type=int, default=10, help='Number of simulation steps')
    parser.add_argument('prob_deposition', type=float, help='Probability of deposition')

    args = parser.parse_args()

    simulation_result = run_simulation(args.width, args.steps, args.prob_deposition)
    print(simulation_result)


if __name__ == "__main__":
    main()
