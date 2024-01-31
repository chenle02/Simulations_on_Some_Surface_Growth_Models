#!/usr/bin/env python3
import pytest
import contextlib
import os
import glob
import joblib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def load_simulation_data():
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

        for joblib_file in glob.glob(os.path.join(input_directory, '*.joblib')):
            TB = joblib.load(joblib_file)

            # Now 'loaded_data' contains the object that was saved in the file
            # You can do something with this object, such as inspecting it or calling its methods
            print(f"Loaded data from {joblib_file}")
            hole_count = TB.count_holes_stack()
            TB.Substrate2PNG(image_filename=joblib_file.replace('.joblib', '.png'),
                             plot_title=f"Holes: {hole_count}")


# Example usage
load_simulation_data()
