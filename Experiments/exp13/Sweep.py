#!/usr/bin/env python3
"""Parameter sweep launcher for experiment 13."""

from tetris_ballistic.sweep_parameters import sweep_parameters as sp
from tetris_ballistic.data_analysis_utilities import insert_joblibs

ListWidth = [50, 80, 100, 150, 200]
ListRandomSeeds = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
config_patterns = ["*.yaml"]
sp(list_width=ListWidth,
   list_random_seeds=ListRandomSeeds,
   config_dir="configs",
   config_patterns=config_patterns)

# After running simulations, insert results (including slope) into the DB
print("Inserting simulation results into database...")
insert_joblibs(pattern="config_*_w=*_*seed=*.joblib")
print("Done.")
