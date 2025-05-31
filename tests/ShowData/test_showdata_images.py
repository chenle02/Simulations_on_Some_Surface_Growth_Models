#!/usr/bin/env python3
import pytest
import os
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
from tetris_ballistic.retrieve_default_configs import configs_dir


def test_showdata():
    """
    This is a test function for the method save_config().
    """
    output_file = "test_showdata_images.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        # Go through the folder ../../tetris_ballistic/configs/ for all yaml
        # files and for each of them, create a Tetris_Ballistic object. For
        # each object, call the method ShowData() and save the figure.
        # Iterate over YAML config files in the package's configs directory
        for file in [os.path.join(configs_dir, f) for f in os.listdir(configs_dir) if f.endswith(".yaml")]:
            basename = os.path.basename(file)
            TB = Tetris_Ballistic(config_file=file)
            TB.width = 50
            TB.height = 150
            # Reduce number of steps for faster testing
            TB.steps = 20
            TB.Simulate()
            output_image = basename.replace(".yaml", ".png")
            title = basename.replace(".yaml", "")
            title = title.replace("_", " ")
            title = title.replace("config", "Config: ")
            list_images = TB.list_tetromino_images()
            if len(list_images) > 10:
                list_images = None
            TB.ShowData(fig_filename=output_image,
                        custom_text=title,
                        images=list_images)
