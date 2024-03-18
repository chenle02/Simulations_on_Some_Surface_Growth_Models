#!/usr/bin/env python3
from tetris_ballistic.data_analysis_utilities import insert_joblibs

# stickiness = ["sticky", "nonsticky", "combined"]
stickiness = ["combined"]
for stick in stickiness:
    pattern = f"*_{stick}_*.joblib"
    insert_joblibs(pattern,
                   verbose=True,
                   table_name=f"{stick}",)
