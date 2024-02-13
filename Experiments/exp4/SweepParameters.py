#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed 31 Jan 2024 10:15:03 PM CST
#

"""
This script is used to sweep the parameters of the Tetris Ballistic simultaions.
"""

import os
from multiprocessing import Pool
from joblib import dump, load
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def simulate(params, total_iterations):
    # Extract parameters
    w, seed, piece_id, sticky, current_iteration = params

    sticky_str = f"{sticky[0]}-{sticky[1]}"
    joblib_filename = f'config_Piece-{piece_id}_sticky={sticky_str}_w={w}_seed={seed}.joblib'
    config_filename = f'config_Piece-{piece_id}_sticky={sticky_str}_w={w}_seed={seed}.yaml'
    fig_filename = f'config_Piece-{piece_id}_sticky={sticky_str}_w={w}_seed={seed}.png'

    # Check if this simulation has already been completed
    if os.path.exists(joblib_filename):
        print(f"Skipping completed simulation: {joblib_filename}")
        return

    print(f"Running simulation: {joblib_filename}")
    WorkingDensity = EmptyDensity.copy()
    WorkingDensity['Piece-' + str(piece_id)] = sticky
    TB = Tetris_Ballistic(density=WorkingDensity,
                          width=int(w),
                          height=int(w * 1.5),
                          steps=int(w * w),
                          seed=seed)

    # Check if this config file has already been saved
    if not os.path.exists(config_filename):
        print(f"Save the config file: {config_filename}")
        TB.save_config(config_filename)

    TB.Simulate()
    # TB.ComputeSlope()
    TB.ShowData(fig_filename=fig_filename)
    # Replace the following line with the actual method to save your simulation
    dump(TB, joblib_filename)  # Assuming you're serializing the entire TB object for simplicity

    print(f"Finished simulation: {joblib_filename}")

    # Log progress
    progress = (current_iteration / total_iterations) * 100
    progress_message = f"Progress: {progress:.2f}% Completed simulation: {joblib_filename}"
    log_progress(progress_message)


def log_progress(progress_message):
    with open("simulation_progress.log", "a") as log_file:
        log_file.write(progress_message + "\n")


if __name__ == "__main__":
    EmptyDensity = {'Piece-0': [0, 0],
                    'Piece-1': [0, 0],
                    'Piece-2': [0, 0],
                    'Piece-3': [0, 0],
                    'Piece-4': [0, 0],
                    'Piece-5': [0, 0],
                    'Piece-6': [0, 0],
                    'Piece-7': [0, 0],
                    'Piece-8': [0, 0],
                    'Piece-9': [0, 0],
                    'Piece-10': [0, 0],
                    'Piece-11': [0, 0],
                    'Piece-12': [0, 0],
                    'Piece-13': [0, 0],
                    'Piece-14': [0, 0],
                    'Piece-15': [0, 0],
                    'Piece-16': [0, 0],
                    'Piece-17': [0, 0],
                    'Piece-18': [0, 0],
                    'Piece-19': [0, 0]}

    StickyList = [[1, 0], [0, 1], [1, 1]]
    ListRandomSeeds = [10 * i for i in range(6)]
    ListWidth = [50, 100, 200]

    # Generate all combinations of parameters
    param_combinations = [(w, seed, piece_id, sticky) for w in ListWidth for seed in ListRandomSeeds for piece_id in range(20) for sticky in StickyList]

    total_iterations = len(param_combinations)
    param_combinations_with_progress = [(w, seed, piece_id, sticky, idx + 1) for idx, (w, seed, piece_id, sticky) in enumerate(param_combinations)]

    # Use multiprocessing Pool to run simulations in parallel
    with Pool() as pool:
        # Note: Modify the simulate function to accept the total_iterations parameter if needed
        pool.starmap(simulate, [(params, total_iterations) for params in param_combinations_with_progress])
