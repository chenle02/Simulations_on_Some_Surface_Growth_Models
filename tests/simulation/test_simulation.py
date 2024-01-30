#!/usr/bin/env python3
import pytest
import contextlib
import os
import glob
import joblib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_simulation():
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
            video_name = os.path.splitext(os.path.basename(config_file))[0] + '.mp4'
            video_path = os.path.join(output_directory, video_name)

            # Initialize Tetris_Ballistic with the config file
            TB = Tetris_Ballistic(config_file=config_file)

            # Run the simulation
            TB.Simulate()

            # Visualize the simulation and generate the video
            TB.visualize_simulation(video_filename=video_path)

            # Save class data (optional)
            data_path = os.path.join(output_directory, os.path.basename(config_file).replace('.yaml', '.joblib'))
            joblib.dump(TB, data_path)

            # Add your validation checks here (if any)

        # # Cleanup: Remove created files (if necessary)
        # for file in os.listdir(output_directory):
        #     os.remove(os.path.join(output_directory, file))
