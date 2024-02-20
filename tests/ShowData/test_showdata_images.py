#!/usr/bin/env python3
import pytest
import os
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_showdata():
    """
    This is a test function for the method save_config().
    """
    output_file = "test_showdata_images.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        # Go through the folder ../../tetris_ballistic/configs/ for all yaml
        # files and for each of them, create a Tetris_Ballistic object. For
        # each object, call the method ShowData() and save the figure.
        for file in ["../../tetris_ballistic/configs/" + f for f in os.listdir("../../tetris_ballistic/configs/") if f.endswith(".yaml")]:
            basename = os.path.basename(file)
            TB = Tetris_Ballistic(config_file=file)
            TB.width = 50
            TB.height = 150
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
