#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Mon Feb 19 02:57:07 PM EST 2024
#

import yaml
import os
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

# Ensure that PyYAML uses a custom representer for lists to keep them inline
yaml.add_representer(list,
                     lambda dumper, data: dumper.represent_sequence(u'tag:yaml.org,2002:seq', data, flow_style=True))

# Basic configuration structure
base_config = {
    "steps": 12000,
    "width": 100,
    "height": 300,
    "seed": 12,
}

# Define the states for each piece
piece_states = {
    "nonsticky": [1, 0],
    "sticky": [0, 1],
    "combined": [1, 1],
}

# Mapping from piece_id to type_id
piece_to_type_mapping = {
    0: 0,   # O-piece
    1: 1,   # I-piece, horizontal
    2: 1,   # I-piece, vertical
    3: 2,   # L-piece, Up
    4: 2,   # L-piece, Left
    5: 2,   # L-piece, Down
    6: 2,   # L-piece, Right
    7: 3,   # J-piece, Up
    8: 3,   # J-piece, Left
    9: 3,   # J-piece, Down
    10: 3,  # J-piece, Right
    11: 4,  # T-piece, Up
    12: 4,  # T-piece, Left
    13: 4,  # T-piece, Down
    14: 4,  # T-piece, Right
    15: 5,  # S-piece, Horizontal
    16: 5,  # S-piece, Vertical
    17: 6,  # Z-piece, Horizontal
    18: 6,  # Z-piece, Vertical
    19: 7,  # 1x1-piece
}

config_dir = "../configs"


def generate_based_Type_ID():
    os.makedirs(config_dir, exist_ok=True)

    # Iterate through each type_id
    for type_id in range(8):
        density = {}
        for state_name, state_value in piece_states.items():
            # config = base_config.copy()
            # Set the specified state for all pieces of the current type_id
            for piece_id, current_type_id in piece_to_type_mapping.items():
                if current_type_id == type_id:
                    density[f"Piece-{piece_id}"] = state_value
                else:
                    # Set other pieces to a default nonsticky state
                    density[f"Piece-{piece_id}"] = [0, 0]

            TB = Tetris_Ballistic(width=base_config["width"],
                                  height=base_config["height"],
                                  steps=base_config["steps"],
                                  seed=base_config["seed"],
                                  density=density)

            # Save the configuration to a file
            file_path = os.path.join(config_dir, f"config_type_{type_id}_{state_name}.yaml")
            TB.save_config(file_path)


def generate_based_Piece_ID():
    os.makedirs(config_dir, exist_ok=True)

    # Iterate through each piece_id
    for piece_id in range(20):

        for state_name, state_value in piece_states.items():
            density = {}
            for i in range(20):
                # Apply the specified state only to the current piece_id, others as nonsticky by default
                density[f"Piece-{i}"] = state_value if i == piece_id else [0, 0]

            TB = Tetris_Ballistic(width=base_config["width"],
                                  height=base_config["height"],
                                  steps=base_config["steps"],
                                  seed=base_config["seed"],
                                  density=density)

            # Save the configuration to a file
            file_path = os.path.join(config_dir, f"config_piece_{piece_id}_{state_name}.yaml")
            TB.save_config(file_path)


def generate_All_Pieces():
    os.makedirs(config_dir, exist_ok=True)

    # Iterate through each piece_id
    for state_name, state_value in piece_states.items():
        density = {}
        for piece_id in range(19):
            density[f"Piece-{piece_id}"] = state_value

        density["Piece-19"] = [0, 0]

        TB = Tetris_Ballistic(width=base_config["width"],
                              height=base_config["height"],
                              steps=base_config["steps"],
                              seed=base_config["seed"],
                              density=density)

        # Save the configuration to a file
        file_path = os.path.join(config_dir, f"config_piece_all_{state_name}.yaml")
        TB.save_config(file_path)


print("1. Generate all configure files for each individual piece based on Piece_ID (0 -- 19). ")
generate_based_Piece_ID()
print("2. Generate all configure files for each individual type based on Type_ID (0 -- 7). ")
generate_based_Type_ID()
print("3. Generate all configure files with all pieces.")
generate_All_Pieces()
