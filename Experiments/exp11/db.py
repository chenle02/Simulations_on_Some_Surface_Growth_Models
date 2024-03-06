#!/usr/bin/env python3
from tetris_ballistic.data_analysis_utilities import insert_joblibs

# Generate the sqlite database
pattern = "*.joblib"
insert_joblibs(pattern,
               verbose=True,
               table_name="Simulations")
