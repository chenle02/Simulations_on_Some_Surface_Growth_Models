#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Thu Mar  7 06:56:50 PM EST 2024
#

from tetris_ballistic.data_analysis_utilities import generate_animations

parterns = ["*percentage_05_w=50_seed=10.joblib","*percentage_50_w=50_seed=10.joblib", "*percentage_9*_w=50_seed=10.joblib"]
generate_animations(parterns)
