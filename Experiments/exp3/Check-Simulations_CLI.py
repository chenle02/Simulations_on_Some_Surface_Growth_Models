#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Thu 01 Feb 2024 01:43:11 PM CST
#

import argparse
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import joblib


def load_tetris_simulation(width, piece_id, sticky, nonsticky, seed):
    joblib_filename = f"./config_Piece-{piece_id}_sticky={nonsticky}-{sticky}_w={width}_seed={seed}.joblib"
    TB = Tetris_Ballistic.load_simulation(joblib_filename)
    print(f"Now the slopes are: \n {TB.log_time_slopes}")
    print(f"This is for the simulation: {joblib_filename}")
    TB.Substrate2PNG(envelop=True, show_average=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load Tetris Ballistic Simulation.')

    parser.add_argument('-w', '--width', type=int, required=True, help='Width of the grid')
    parser.add_argument('-p', '--piece_id', type=int, required=True, help='ID of the piece')
    parser.add_argument('-st', '--sticky', type=int, required=True, help='Sticky values as two integers')
    parser.add_argument('-ns', '--nonsticky', type=int, required=True, help='Sticky values as two integers')
    parser.add_argument('-s', '--seed', type=int, required=True, help='Seed for the simulation')

    args = parser.parse_args()

    TB2 = load_tetris_simulation(width=args.width,
                                 piece_id=args.piece_id,
                                 sticky=args.sticky,
                                 nonsticky=args.nonsticky,
                                 seed=args.seed)
