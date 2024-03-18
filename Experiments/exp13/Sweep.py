#!/usr/bin/env python3
from tetris_ballistic.sweep_parameters import sweep_parameters as sp
from tetris_ballistic.data_analysis_utilities import insert_joblibs

ListWidth = [50, 80, 100, 150]
ListRandomSeeds = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
# config_patterns = ["*piece_19_sticky.yaml",
#                    "*piece_19_nonsticky.yaml",
#                    "*piece_0*.yaml",
#                    "*type_1*.yaml",
#                    "*type_2*.yaml",
#                    "*type_3*.yaml",
#                    "*type_4*.yaml",
#                    "*type_5*.yaml",
#                    "*type_6*.yaml"]
config_patterns = ["*.yaml"]
sp(list_width=ListWidth,
   list_random_seeds=ListRandomSeeds,
   config_dir="configs",
   config_patterns=config_patterns)
