#!/usr/bin/env python3
from tetris_ballistic.sweep_parameters import sweep_parameters as sp
from tetris_ballistic.data_analysis_utilities import insert_joblibs

ListWidth = [150]
ListRandomSeeds = [60]
config_patterns = ["config_*98.yaml"]
sp(list_width=ListWidth,
   list_random_seeds=ListRandomSeeds,
   config_dir="configs",
   config_patterns=config_patterns)
