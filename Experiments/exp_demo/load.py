#!/usr/bin/env python3

import os
import sys
from multiprocessing import Pool
from joblib import dump
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic, load_density_from_config

joblibfile = "config_piece_0_sticky_w=50_seed=1510.joblib"

TB = Tetris_Ballistic.load_simulation(joblibfile)
# print("First the detailed information")
# TB.PrintStatus()

print("Now brief information")
TB.PrintStatus(brief=True)
title = joblibfile.replace(".joblib", "").replace("_", " ").replace("config piece", "Piece id=")
videofile = joblibfile.replace(".joblib", "_equal.mp4")
TB.resize(new_height=60)

print("Resized information")
TB.PrintStatus(brief=True)
TB.Substrate2PNG(image_filename="substrate.png")

TB.visualize_simulation(plot_title=title,
                        video_filename=videofile,
                        envelop=True,
                        show_average=True,
                        aspect="equal")

# TB.visualize_simulation(plot_title=title,
#                         video_filename=videofile,
#                         envelop=False,
#                         show_average=False,
#                         aspect="equal")

print("Now count holes")
TB.count_holes_stack()
