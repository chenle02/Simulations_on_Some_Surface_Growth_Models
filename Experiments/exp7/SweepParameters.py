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
from joblib import dump
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic, load_density_from_config


def simulate(params, total_iterations):
    # Extract parameters
    w, seed, config_name, density, current_iteration = params

    basename = os.path.basename(config_name).replace(".yaml", "")
    joblib_filename = f'{basename}_w={w}_seed={seed}.joblib'
    config_filename = f'{basename}_w={w}_seed={seed}.yaml'
    fig_filename = f'{basename}_w={w}_seed={seed}.png'

    # Check if this simulation has already been completed
    if os.path.exists(joblib_filename):
        print(f"Skipping completed simulation: {joblib_filename}")
        return

    print(f"Running simulation: {joblib_filename}")

    TB = Tetris_Ballistic(width=w,
                          height=w * 10,
                          steps=10 * w * w,
                          seed=seed,
                          density=density)

    # Check if this config file has already been saved
    if not os.path.exists(config_filename):
        print(f"Save the config file: {config_filename}")
        TB.save_config(config_filename)

    TB.Simulate()
    # TB.ComputeSlope()
    title = basename.replace("_", " ")
    title = title.replace("config", "Config: ")
    list_images = TB.list_tetromino_images()
    if len(list_images) > 10:
        print("Too many images to display: ", len(list_images))
        list_images = None
    else:
        print("List Images: ", list_images)

    TB.ShowData(fig_filename=fig_filename,
                custom_text=title,
                images=list_images)

    dump(TB, joblib_filename)

    print(f"Finished simulation: {joblib_filename}")

    # Log progress
    progress = (current_iteration / total_iterations) * 100
    progress_message = f"Progress: {progress:.2f}% Completed simulation: {joblib_filename}"
    log_progress(progress_message)


def log_progress(progress_message):
    with open("simulation_progress.log", "a") as log_file:
        log_file.write(progress_message + "\n")


if __name__ == "__main__":
    ListWidth = [100, 200, 500, 800, 1200]
    ListRandomSeeds = [10 * i for i in range(10)]
    configs = [f for f in os.listdir("../../tetris_ballistic/configs/") if f.endswith(".yaml")]
    # densities = [{os.path.basename(f): load_density_from_config(f"../../tetris_ballistic/configs/{f}")} for f in configs]

    # Generate all combinations of parameters
    param_combinations = [
        (w,
         seed,
         os.path.basename(config),
         load_density_from_config(f"../../tetris_ballistic/configs/{config}"))
        for w in ListWidth
        for seed in ListRandomSeeds
        for config in configs
    ]

    total_iterations = len(param_combinations)
    param_combinations_with_progress = [
        (w, seed, config_name, density, idx + 1)
        for idx, (w, seed, config_name, density) in enumerate(param_combinations)
    ]

    # Use multiprocessing Pool to run simulations in parallel
    with Pool() as pool:
        # Note: Modify the simulate function to accept the total_iterations parameter if needed
        pool.starmap(simulate, [(params, total_iterations) for params in param_combinations_with_progress])
