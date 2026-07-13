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
from itertools import chain
from multiprocessing import Pool

from tetris_ballistic.retrieve_default_configs import configs_dir
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc
from tetris_ballistic.run_artifacts import execute_managed_run, resolve_engine_route
from tetris_ballistic.tetris_ballistic import load_density_from_config


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

    This function runs a single instance of the Tetris Ballistic simulation,
    publishes its configuration and result through the managed manifest-last
    writer, and generates a derived visualization of the outcome.
    """
    # Extract parameters
    w, seed, config_name, density, current_iteration = params

    basename = os.path.basename(config_name).replace(".yaml", "")
    joblib_filename = f'{basename}_w={w}_seed={seed}.joblib'
    config_filename = f'{basename}_w={w}_seed={seed}.yaml'
    fig_filename = f'{basename}_w={w}_seed={seed}.png'
    log_file_path = f'{basename}_w={w}_seed={seed}.log'

    logger = DualLogger(log_file_path, mode='a')
    previous_stdout = sys.stdout
    sys.stdout = logger
    try:
        height = int(round(w * ratio))
        steps = int(round(ratio * w * w))

        def render_derived_figure(simulation):
            title = basename.replace("_", " ").replace("config", "Config: ")
            list_images = simulation.list_tetromino_images()
            if len(list_images) > 10:
                print("Too many images to display: ", len(list_images))
                list_images = None
            else:
                print("List Images: ", list_images)
            simulation.ShowData(
                fig_filename=fig_filename,
                custom_text=title,
                images=list_images,
            )

        result = execute_managed_run(
            joblib_path=joblib_filename,
            config_path=config_filename,
            width=w,
            height=height,
            steps=steps,
            seed=seed,
            density=density,
            engine_route=resolve_engine_route(density),
            semantic_context={
                "config_basename": basename,
                "density_state_order": ["nonsticky", "sticky"],
                "percentage_semantics": "encoded_by_effective_density",
                "producer": "sweep_parameters-v1",
            },
            before_publish=render_derived_figure,
            on_start=lambda: print(f"Running simulation: {joblib_filename}"),
        )
        if result.reused:
            print(f"Skipping verified completed simulation: {joblib_filename}")
            return

        print(f"Finished simulation: {joblib_filename}")
        if current_iteration > 0:
            progress = (current_iteration / total_iterations) * 100
            progress_message = f"Progress: {progress:.2f}% Completed simulation: {joblib_filename}"
            log_progress(progress_message)
    finally:
        sys.stdout = previous_stdout
        logger.close()


def log_progress(progress_message):
    with open("simulation_progress.log", "a") as log_file:
        log_file.write(progress_message + "\n")


def sweep_parameters(list_width=[50, 100, 200],
                     list_random_seeds=[10 * i for i in range(10)],
                     config_patterns=["*piece_19_sticky.yaml", "*piece_19_nonsticky.yaml", "*piece_0*.yaml"],
                     config_dir=None,
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
        config_dir (str): Directory containing configuration files for simulations. If not provided, the default directory is used.
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
    configs = list(chain(*(rdc(pattern=pattern, dir=config_dir, verbose=False) for pattern in config_patterns)))
    print("List of configs: ")
    for i, config in enumerate(configs):
        print(f"{i}: {config}")

    # Generate all combinations of parameters
    if config_dir is None:
        config_dir = configs_dir

    param_combinations = [
        (w,
         seed,
         os.path.basename(config),
         load_density_from_config(os.path.join(config_dir, config))
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
    ListWidth = [50, 100, 150]
    ListRandomSeeds = [10 * i for i in range(10)]
    config_patterns = ["*.yaml"]
    sweep_parameters(list_width=ListWidth,
                     list_random_seeds=ListRandomSeeds,
                     config_patterns=config_patterns)
