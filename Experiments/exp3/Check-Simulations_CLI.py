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

    parser = argparse.ArgumentParser(
        description=main.__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=100,
        help="Width of the substrate (default: 100)",
    )
    parser.add_argument(
        "-e",
        "--height",
        type=int,
        default=60,
        help="Maximum height of the substrate (default: 60)",
    )
    parser.add_argument(
        "-s",
        "--steps",
        type=int,
        default=5000,
        help="Number of particles to drop (default: 5000)",
    )
    parser.add_argument(
        "-r",
        "--relax",
        action="store_true",
        help="Surface Relaxation: go to the nearest lowest neighbor (default: False)",
    )
    parser.add_argument(
        "-b",
        "--BD",
        action="store_true",
        help="Ballistic decomposition (default: False)",
    )
    parser.add_argument(
        "-m",
        "--movie",
        action="store_true",
        help="Generate the mp4 movie (default: False)",
    )
    args = parser.parse_args()

    Outputfile = ""
    if args.relax:
        Title = "Random Decomposition with Surface Relaxation"
        Outputfile = Random_Deposition_Surface_Relaxation(
            args.width, args.height, args.steps
        )
        print(Title)
    elif args.BD:
        Title = "Ballistic Decomposition"
        Outputfile = Ballistic_Deposition(args.width, args.height, args.steps)
        print(Title)
    else:
        Title = "Random Decomposition"
        Outputfile = Random_Deposition(args.width, args.height, args.steps)
        print(Title)

    print("Computing the interface width...")
    interface_width(Outputfile)

