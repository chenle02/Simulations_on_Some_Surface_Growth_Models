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

            experiment_name = os.path.splitext(os.path.basename(config_file))[0].replace('config_', '').replace('_', ' ')
            print(f"Running experiment: {experiment_name}")

            # Filename for the saved simulation
            joblib_file = os.path.join(output_directory, os.path.basename(config_file).replace('.yaml', '.joblib'))

            if os.path.exists(joblib_file):
                print(f"Simulation already exists: {joblib_file}")
                # Initialize Tetris_Ballistic with the config file
                print("Find the simulation file and load it now")
                TB = joblib.load(joblib_file)
            else:
                print("Do not find the simulation file, run the simulation now")
                TB = Tetris_Ballistic(config_file=config_file)
                # Run the simulation
                TB.Simulate()
                joblib.dump(TB, joblib_file)

            if os.path.exists(video_path):
                print(f"Video already exists: {video_path}")
            else:
                print("Generate the simulation again")
                # Visualize the simulation and generate the video
                TB.visualize_simulation(video_filename=video_path,
                                        plot_title=experiment_name,
                                        rate=4,
                                        envelop=True,
                                        show_average=True)
