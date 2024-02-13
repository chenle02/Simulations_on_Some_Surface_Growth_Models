#!/usr/bin/env python3
import pytest
import contextlib
import os
import glob
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_SampleDist():
    """
    Test function for the Simulate() method of the Tetris_Ballistic class.
    This test runs simulations with various configurations and optionally validates the results.
    """
    output_file = "test_simulation_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        config_directory = "."  # Directory containing YAML files
        output_directory = "."  # Directory for saving outputs

        # Ensure the output directory exists
        os.makedirs(config_directory, exist_ok=True)

        for config_file in glob.glob(os.path.join(config_directory, '*.yaml')):

            experiment_name = os.path.splitext(os.path.basename(config_file))[0].replace('config_', '').replace('_', ' ')
            print(f"Running experiment: {experiment_name}")

            TB = Tetris_Ballistic(config_file=config_file)
            # Run the simulation
            TB.Simulate()
            TB.PrintStatus()
