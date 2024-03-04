#!/usr/bin/env python3

import pytest
import contextlib
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc


def test_retreive_default_configs():
    """
    This is a test function for retrieving default configs.
    """
    output_file = "test_retreive_default_configs_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        print("1. Here is all configs")
        rdc(verbose=True)

        print("\n\n2. Here is the piece d = 14:")
        rdc(pattern="*piece_14_*.yaml")

        print("\n\n3. Here is config for the piece id = 19 and sticky:")
        rdc(pattern="*piece_19_sticky.yaml")

# config_piece_0_combined.yaml
# config_piece_0_nonsticky.yaml
# config_piece_0_sticky.yaml
# config_piece_10_combined.yaml
# config_piece_10_nonsticky.yaml
# config_piece_10_sticky.yaml
# config_piece_11_combined.yaml
# config_piece_11_nonsticky.yaml
# config_piece_11_sticky.yaml
# config_piece_12_combined.yaml
# config_piece_12_nonsticky.yaml
# config_piece_12_sticky.yaml
# config_piece_13_combined.yaml
# config_piece_13_nonsticky.yaml
# config_piece_13_sticky.yaml
# config_piece_14_combined.yaml
# config_piece_14_nonsticky.yaml
# config_piece_14_sticky.yaml
# config_piece_15_combined.yaml
# config_piece_15_nonsticky.yaml
# config_piece_15_sticky.yaml
# config_piece_16_combined.yaml
# config_piece_16_nonsticky.yaml
# config_piece_16_sticky.yaml
# config_piece_17_combined.yaml
# config_piece_17_nonsticky.yaml
# config_piece_17_sticky.yaml
# config_piece_18_combined.yaml
# config_piece_18_nonsticky.yaml
# config_piece_18_sticky.yaml
# config_piece_19_combined.yaml
# config_piece_19_nonsticky.yaml
# config_piece_19_sticky.yaml
# config_piece_1_combined.yaml
# config_piece_1_nonsticky.yaml
# config_piece_1_sticky.yaml
# config_piece_2_combined.yaml
# config_piece_2_nonsticky.yaml
# config_piece_2_sticky.yaml
# config_piece_3_combined.yaml
# config_piece_3_nonsticky.yaml
# config_piece_3_sticky.yaml
# config_piece_4_combined.yaml
# config_piece_4_nonsticky.yaml
# config_piece_4_sticky.yaml
# config_piece_5_combined.yaml
# config_piece_5_nonsticky.yaml
# config_piece_5_sticky.yaml
# config_piece_6_combined.yaml
# config_piece_6_nonsticky.yaml
# config_piece_6_sticky.yaml
# config_piece_7_combined.yaml
# config_piece_7_nonsticky.yaml
# config_piece_7_sticky.yaml
# config_piece_8_combined.yaml
# config_piece_8_nonsticky.yaml
# config_piece_8_sticky.yaml
# config_piece_9_combined.yaml
# config_piece_9_nonsticky.yaml
# config_piece_9_sticky.yaml
# config_piece_all_combined.yaml
# config_piece_all_nonsticky.yaml
# config_piece_all_sticky.yaml
# config_type_1_combined.yaml
# config_type_1_nonsticky.yaml
# config_type_1_sticky.yaml
# config_type_2_combined.yaml
# config_type_2_nonsticky.yaml
# config_type_2_sticky.yaml
# config_type_3_combined.yaml
# config_type_3_nonsticky.yaml
# config_type_3_sticky.yaml
# config_type_4_combined.yaml
# config_type_4_nonsticky.yaml
# config_type_4_sticky.yaml
# config_type_5_combined.yaml
# config_type_5_nonsticky.yaml
# config_type_5_sticky.yaml
# config_type_6_combined.yaml
# config_type_6_nonsticky.yaml
# config_type_6_sticky.yaml
