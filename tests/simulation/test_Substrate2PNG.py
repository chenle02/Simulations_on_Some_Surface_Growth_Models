#!/usr/bin/env python3
import pytest
import contextlib
import os
import glob
import joblib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_load_simulation_data_and_Substrate2PNG():
    """
    Loads simulation data from .joblib files in a specified directory and save the last frame to PNG files.
    """
    input_directory = "."  # Directory containing .joblib files

    output_file = "test_Substrate2PNG_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        # Ensure the input directory exists
        if not os.path.exists(input_directory):
            print(f"Directory '{input_directory}' does not exist.")
            return

        # Load all joblib files in the input directory
        for joblib_file in glob.glob(os.path.join(input_directory, '*.joblib')):
            TB = joblib.load(joblib_file)

            experiment_name = joblib_file.replace('config_', '').replace('_', ' ').replace('.joblib', '').replace('./', '')
            print(f"Experiment name {experiment_name} from {joblib_file}")
            frame_id = int(2 * TB.FinalSteps / 3)
            hole_count = TB.count_holes_stack(frame_id)
            TB.Substrate2PNG(image_filename=joblib_file.replace('.joblib', '.png'),
                             plot_title=f"{experiment_name} with {hole_count} holes at step No. {frame_id}",
                             envelop=True,
                             show_average=True,
                             frame_id=frame_id)
