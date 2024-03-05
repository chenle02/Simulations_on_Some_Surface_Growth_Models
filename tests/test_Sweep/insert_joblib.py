#!/usr/bin/env python3

from tetris_ballistic.data_analysis_utilities import retrieve_fluctuations, insert_joblibs
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

pattern = "*.joblib"
insert_joblibs(pattern, verbose=True, table_name="test_sweep")
