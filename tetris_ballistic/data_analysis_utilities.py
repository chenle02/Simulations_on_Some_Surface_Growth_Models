#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Mon Mar  4 01:49:06 PM EST 2024
#

"""

This module consists of utility functions for data analysis of the Tetris
Ballistic model. It includes functionality to generate visualizations of the
data, and to perform statistical analysis on the data.

Author:
    Le Chen (chenle02@gmail.com / le.chen@auburn.edu)
"""

import numpy as np
import joblib
import glob
import re
import os
from scipy import stats
import matplotlib.pyplot as plt
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic, load_density_from_config
# from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir
import sqlite3


def retrieve_fluctuations(pattern: str,
                          output_filename: str = None,
                          verbose: bool = False):
    """
    aaa

    """

    # Use glob to find files matching the pattern
    files = glob.glob(pattern)

    if verbose:
        print(f"pattern = {pattern}")
        print(f"Number of matches = {len(files)}")
        for item, file in enumerate(files):
            print(f"File {item}: {file}")
        print("\n")

    if len(files) == 0:
        raise ValueError(f"No file found for the pattern: {pattern}")

    # Load the data from the joblib files
    list_of_fluctuations = []
    list_of_len = []
    for file in files:
        TB = Tetris_Ballistic.load_simulation(file)
        fl = TB.Fluctuation[:TB.FinalSteps]
        list_of_fluctuations.append(fl)
        list_of_len.append(len(fl))

    min_len = min(list_of_len)
    max_len = max(list_of_len)
    ave_len = np.mean(list_of_len)
    print(f"min_len = {min_len}, max_len = {max_len} and ave_len = {ave_len}")

    result_array = np.zeros((len(list_of_fluctuations), min_len))
    for i, array in enumerate(list_of_fluctuations):
        length = min(min_len, array.size)
        result_array[i, :length] = array[:length]

    print(result_array.shape)

    if output_filename is not None:
        joblib.dump(result_array, output_filename)

    return result_array


def create_database(db_name: str = "simulation_results.db",
                    table_name: str = "Simulations") -> None:
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Create a table
    sql_command = f'''CREATE TABLE IF NOT EXISTS {table_name}
                (id INTEGER PRIMARY KEY,
                type TEXT,
                sticky TEXT,
                width INT,
                random_seed INT,
                final_steps INT,
                fluctuation BLOB,
                slope REAL)'''

    c.execute(sql_command)

    # Commit the changes and close the connection to the database
    conn.commit()
    conn.close()


def insert_joblibs(pattern: str = "*.joblib",
                   table_name: str = "Simulations",
                   verbose: bool = True):
    """
    Add the joblib files to the database table.
    """
    # Connect to the database
    conn = sqlite3.connect("simulation_results.db")
    c = conn.cursor()

    # Create a table if not exists
    sql_command = f'''CREATE TABLE IF NOT EXISTS {table_name}
                (id INTEGER PRIMARY KEY,
                type TEXT,
                sticky TEXT,
                width INT,
                random_seed INT,
                final_steps INT,
                fluctuation BLOB,
                slope REAL)'''

    c.execute(sql_command)

    # Use glob to find files matching the pattern
    files = glob.glob(pattern)

    if verbose:
        print(f"pattern = {pattern}")
        print(f"Number of matches = {len(files)}")
        for item, file in enumerate(files):
            print(f"File {item}: {file}")
        print("\n")

    if len(files) == 0:
        raise ValueError(f"No file found for the pattern: {pattern}")

    # Regex pattern to match filename and extract components
    pattern_parse = r'config_(?P<type>piece_\d+|type_\d+|piece_all)_(?P<sticky>sticky|nonsticky|combined)_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'

    # Load the data from the joblib files
    list_of_fluctuations = []
    list_of_len = []
    for file in files:
        basename = os.path.basename(file)
        match = re.match(pattern_parse, basename)
        if match:
            data = match.groupdict()
            type_ = data['type']
            sticky = data['sticky']
            width = int(data['width'])
            random_seed = int(data['seed'])

            TB = Tetris_Ballistic.load_simulation(file)
            fl = TB.Fluctuation[:TB.FinalSteps]

            final_steps = TB.FinalSteps
            slope = 0.0

            list_of_fluctuations.append(fl)
            list_of_len.append(len(fl))

            # Convert the fluctuation array to a binary format
            fluctuation_blob = sqlite3.Binary(fl.tobytes())

            # Insert the data into the table
            c.execute(f'''INSERT INTO {table_name} (type, sticky, width, random_seed, final_steps, fluctuation, slope)
                          VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (type_, sticky, width, random_seed, final_steps, fluctuation_blob, slope))

            if verbose:
                print(f"Matched file: {file} and added the entry to the database.")

    if verbose and len(list_of_len) > 0:
        min_len = min(list_of_len)
        max_len = max(list_of_len)
        ave_len = np.mean(list_of_len)
        print(f"min_len = {min_len}, max_len = {max_len} and ave_len = {ave_len}")

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

    return list_of_fluctuations, list_of_len

# Debug and example usage
if __name__ == "__main__":
    pattern = "../Experiments/exp10/*w=50*.joblib"
    retrieve_fluctuations(pattern, verbose=True, output_filename="fluctuations_w=50.joblib")

    # pattern = "../Experiments/exp10/*w=100*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
    #
    # pattern = "../Experiments/exp10/*_sticky_*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
    #
    # pattern = "../Experiments/exp10/*_nonsticky_*.joblib"
    # retrieve_fluctuations(pattern, verbose=True)
