#!/usr/bin/env python3
#
# Make sure install the package first by running:
# `pip3 install -e .`
# from the root directory of the package
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Sun Jan 28 10:38:55 PM EST 2024
#

from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_1x1():
    """
    This is a test function for the square piece.
    """
    # output_file = "test_1x1_500x500_output.txt"

    TB = Tetris_Ballistic(seed=42, width=200, height=200, steps=40000)

    print("\n\nFirst, the sticky case of 1x1 piece:")
    TB.reset()
    i = 0
    while i < TB.steps:
        i = TB.Update_1x1(i, sticky=True)

        # Calculate and display the progress
        progress_percentage = (i / TB.steps) * 100
        print(f"Progress: {progress_percentage:.2f}%", end='\r')

        if i == -1:
            print("Game Over, reach the top")
            break
    TB.ComputeSlope()
    TB.PrintStatus(brief=True)
    # print(TB.substrate)
    # print(TB.HeightDynamics)

    print("\n\nSecond, the non-sticky case of 1x1 piece:")
    TB.reset()
    i = 0
    while i < TB.steps:
        i = TB.Update_1x1(i, sticky=False)

        # Calculate and display the progress
        progress_percentage = (i / TB.steps) * 100
        print(f"Progress: {progress_percentage:.2f}%", end='\r')

        if i == -1:
            print("Game Over, reach the top")
            break
    TB.ComputeSlope()
    TB.PrintStatus(brief=True)
    # print(TB.substrate)
    # print(TB.HeightDynamics)


test_1x1()
