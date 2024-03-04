"""
This module is used to perform parameter sweep simulations for the Tetris
Ballistic model. It includes functionality to run simulations in parallel, save
results, and generate visualizations of the data.

Attributes:
    package_dir (str): Directory of the package.
    configs_dir (str): Directory containing configuration files for simulations.

Author:
    Le Chen (chenle02@gmail.com / le.chen@auburn.edu)
"""

import os
import sys
from multiprocessing import Pool
from joblib import dump
from itertools import chain
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic, load_density_from_config
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir


class DualLogger:
    """
    A logger that duplicates output to both the console and a log file.

    Attributes:
        terminal (IO): The original ``sys.stdout``.
        log (File): The file object for the log file.

    Args:
        filepath (str): Path to the log file.
        mode (str): The mode in which the log file is opened.
    """
    def __init__(self, filepath, mode='a'):
        self.terminal = sys.stdout
        self.log = open(filepath, mode)

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):  # This flush method is needed for python 3 compatibility.
        # This flushes the stream to the file, but not the terminal
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def simulate(params, ratio: float, total_iterations: int):
    """
    Run one simulation with the specified parameters.

    Args:
        params (tuple): Simulation parameters including width, seed, config name, density, and current iteration.
            If the current iteration is 0, no progress will be logged.
        ratio (float): The height/width ratio of the simulation grid.
        total_iterations (int): The total number of iterations/simulations to be performed.

    This function runs a single instance of the Tetris Ballistic simulation
    with the given parameters, saves the simulation configuration, results, and
    generates a visualization of the simulation outcome.
    """
    # Extract parameters
    w, seed, config_name, density, current_iteration = params

    basename = os.path.basename(config_name).replace(".yaml", "")
    joblib_filename = f'{basename}_w={w}_seed={seed}.joblib'
    config_filename = f'{basename}_w={w}_seed={seed}.yaml'
    fig_filename = f'{basename}_w={w}_seed={seed}.png'
    log_file_path = f'{basename}_w={w}_seed={seed}.log'

    sys.stdout = DualLogger(log_file_path, mode='a')

    # Check if this simulation has already been completed
    if os.path.exists(joblib_filename):
        print(f"Skipping completed simulation: {joblib_filename}")
        return

    print(f"Running simulation: {joblib_filename}")

    TB = Tetris_Ballistic(width=w,
                          height=w * ratio,
                          steps=ratio * w * w,
                          seed=seed,
                          density=density)

    # Check if this config file has already been saved
    if not os.path.exists(config_filename):
        print(f"Save the config file: {config_filename}")
        TB.save_config(config_filename)

    TB.Simulate()
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
    if current_iteration > 0:
        progress = (current_iteration / total_iterations) * 100
        progress_message = f"Progress: {progress:.2f}% Completed simulation: {joblib_filename}"
        log_progress(progress_message)

    sys.stdout.close()  # Assuming sys.stdout was set to an instance of DualLogger
    sys.stdout = sys.__stdout__


def log_progress(progress_message):
    with open("simulation_progress.log", "a") as log_file:
        log_file.write(progress_message + "\n")


def sweep_parameters(list_width=[50, 100, 200],
                     list_random_seeds=[10 * i for i in range(10)],
                     config_patterns=["*piece_19_sticky.yaml", "*piece_19_nonsticky.yaml", "*piece_0*.yaml"],
                     ratio=10):
    """
    Conducts a parameter sweep for Tetris Ballistic simulations across various
    configurations, grid sizes, and seeds.

    This function organizes simulations to be executed in parallel, optimizing
    the runtime for extensive simulation sets. It generates all combinations of
    provided parameters, runs each simulation with its specific configuration,
    and logs the outcomes.

    Args:
        list_width (List[int]): Grid widths to be used in the simulations. The height is determined by the given ratio.
        list_random_seeds (List[int]): Seed values for the random number generator, ensuring diverse simulation outcomes.
        config_patterns (List[str]): Filename patterns for configuration files, used to select specific simulation configurations from the configs directory.
        ratio (float): The height-to-width ratio of the simulation grid. Used to compute the grid's height from its width.

    The function first retrieves configuration filenames matching the given
    patterns, then prints and iterates over these configurations to generate
    all parameter combinations. For each parameter set, it runs the simulation,
    saves the results, and visualizes the data. Progress is tracked and logged
    to monitor the simulation process.

    The multiprocessing library is utilized to run simulations concurrently,
    significantly reducing the total processing time when dealing with numerous
    simulations.
    """
    configs = list(chain(*(rdc(pattern=pattern, verbose=False) for pattern in config_patterns)))
    print("List of configs: ")
    for i, config in enumerate(configs):
        print(f"{i}: {config}")

    # Generate all combinations of parameters
    param_combinations = [
        (w,
         seed,
         os.path.basename(config),
         load_density_from_config(os.path.join(configs_dir, config))
         )
        for w in list_width
        for seed in list_random_seeds
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
        pool.starmap(simulate, [(params, ratio, total_iterations) for params in param_combinations_with_progress])


# Sample usage
if __name__ == "__main__":
    ListWidth = [50, 100]
    ListRandomSeeds = [10 * i for i in range(10)]
    config_patterns = ["*piece_19_sticky.yaml",
                       "*piece_19_nonsticky.yaml",
                       "*piece_0*.yaml"]
    sweep_parameters(list_width=ListWidth,
                     list_random_seeds=ListRandomSeeds,
                     config_patterns=config_patterns)
