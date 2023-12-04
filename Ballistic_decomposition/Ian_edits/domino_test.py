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


# choice = np.random.randint(2, size=2)
# substrate = np.zeros((8, 8))
# choice[0] = 1
# choice[1] = 1
# substrate[3, 3] = 11
# substrate[4, 3] = 11
# substrate[5, 3] = 11
# substrate[6, 0] = 11
# substrate[6, 1] = 0
# substrate[6, 3] = 11
# substrate[6, 6] = 11
# substrate[7, 0] = 11
# substrate[7, 1] = 0
# substrate[7, 2] = 11
# substrate[7, 3] = 11
# substrate[7, 4] = 11
# substrate[7, 5] = 11
# substrate[7, 6] = 11
# substrate[4, 2] = 11
# substrate[2, 6] = 11
# print(substrate)


def ffnz(
    matrix, height, column
):  # ffnz Finds the First NonZero entry in a fixed column
    i = 0
    flag = height
    while (flag == height) and (i < height):
        if matrix[i, column] == 0:
            i = i + 1
        else:
            flag = i
    return flag


# print('first nonzero in column 0', ffnz(substrate, 8, 0))
# print('first nonzero in column 1', ffnz(substrate, 8, 1))
# print('first nonzero in column 2', ffnz(substrate, 8, 2))
# print('first nonzero in column 3', ffnz(substrate, 8, 3))
# print('first nonzero in column 4', ffnz(substrate, 8, 4))
# print('first nonzero in column 5', ffnz(substrate, 8, 5))
# print('first nonzero in column 6', ffnz(substrate, 8, 6))
# print('first nonzero in column 7', ffnz(substrate, 8, 7))


def Random_Deposition_2x1(width, height, steps):
    substrate = np.zeros((height, width))
    topmost = height - 1
    i = 0

    while i < steps:
        position = random.randint(0, width - 1)
        choice = Piece_Selection()
        # position = 5

        if (
            choice[0] == 0 and choice[1] == 0
        ):  # Horizontal piece, left pivot. As in, the nonpivot is on the right.
            if position != (width - 1):  # Checks if the piece is in the right boundary
                landing_row = np.minimum(
                    ffnz(substrate, height, position) - 1,
                    ffnz(substrate, height, position + 1) - 1,
                )
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position + 1] = i + 1
                i += 1
            else:
                continue

        if (
            choice[0] == 0 and choice[1] == 1
        ):  # Horizontal piece, right pivot. As in, the nonpivot is on the left.
            if position != 0:
                landing_row = np.minimum(
                    ffnz(substrate, height, position - 1) - 1,
                    ffnz(substrate, height, position) - 1,
                )
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position - 1] = i + 1
                i += 1
            else:
                continue

        if (
            choice[0] == 1
        ):  # Vertical piece. We can safely ignore the pivot and we also don't need to check boundary conditions
            landing_row = ffnz(substrate, height, position) - 1
            substrate[landing_row, position] = i + 1
            substrate[landing_row - 1, position] = (
                i + 1
            )  # This places a block above the first one
            i += 1

        if landing_row < topmost:
            topmost = landing_row

        if (steps + 1) % 200 == 0:
            print(f"Step: {steps + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(f"Stopped at step {i + 1}, Level at {height - topmost + 1}/{height}")
            break

    # outputfile = f'Substrate_domino_{width}x{height}_Particles={steps}.txt'
    # np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
    # print(f"{outputfile} saved!")
    # return outputfile
    return print(substrate)


# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())
# print(Piece_Selection())

Random_Deposition_2x1(15, 15, 100)
