import numpy as np
# import argparse
# import subprocess
# import matplotlib.pyplot as plt
import random


def Piece_Selection():  # This gives the 2x1 case
    choice = np.random.randint(2, size=2)
    # This function chooses the piece that will be dropped. The piece is chosen by a random integer
    # between 0 and 1. 0 corresponds to the horizontal piece, 1 corresponds to the vertical piece,
    # The second digit corresponds to the pivot point. 0 corresponds to the left pivot point, 1
    # corresponds to the right pivot point. The function returns the choice as a list of two
    # integers. We can safely ignore the pivot when working with the vertical piece.
    return choice


def Random_Deposition_2x1(width, height, steps):
    substrate = np.zeros((height, width))
    topmost = height - 1
    i = 0

    while i < steps:
        position = random.randint(0, width)
        choice = Piece_Selection()

        if choice[0] == 0 and choice[1] == 0:  # Horizontal piece, left pivot. As in, the nonpivot is on the right.
            if position != width:  # Checks if the piece is in the right boundary
                landing_row = np.minimum(np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position + 1] == 0)))
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position + 1] = i + 1
                i += 1
            else:
                continue

        if choice[0] == 0 and choice[1] == 1:  # Horizontal piece, right pivot. As in, the nonpivot is on the left.
            if position != 0:  # Need to fix this, can't compare numpy array to int.
                landing_row = np.minimum(np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position - 1] == 0)))
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position - 1] = i + 1
                i += 1
            else:
                continue

        if choice[0] == 1:  # Vertical piece. We can safely ignore the pivot and we also don't need to check boundary conditions
            landing_row = np.max(np.where(substrate[:, position] == 0))
            substrate[landing_row, position] = i + 1
            substrate[landing_row - 1, position] = i + 1  # This places a block above the first one

        if landing_row < topmost:
            topmost = landing_row

        if (steps + 1) % 200 == 0:
            print(f"Step: {steps + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(f"Stopped at step {steps + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f'Substrate_domino_{width}x{height}_Particles={steps}.txt'
    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
    print(f"{outputfile} saved!")
    return outputfile


Random_Deposition_2x1(50, 50, 50)
