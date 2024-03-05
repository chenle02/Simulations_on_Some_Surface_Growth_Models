#!/usr/bin/env python3

from tetris_ballistic.data_analysis_utilities import retrieve_fluctuations

pattern = "../../Experiments/exp10/*w=50*.joblib"
retrieve_fluctuations(pattern,
                      verbose=True,
                      output_filename="fluctuations_exp10_w50.joblib")
