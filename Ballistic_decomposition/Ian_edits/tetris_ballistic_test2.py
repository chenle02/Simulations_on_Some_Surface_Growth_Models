"""
abc
This module simulates the surface growth by Tetris pieces. It includes
functions to generate random Tetris pieces, calculate their landing positions
on a substrate, and simulate a game of Tetris for a given number of steps and a
defined grid size.

By Ian Ruau (iir0001@auburn.edu) and Mauricio Montes (mauricio.montes@auburn.edu)
Date: 12/2023

"""

import numpy as np
import random
import argparse

# from RD_CLI import Interface_width


def Tetris_Choice():
    """
    Randomly selects a Tetris piece and its orientation.

    There are 7 Tetris pieces:

    + 0 :  the square;
    + 1 :  the line;
    + 2 :  the L;
    + 3 :  the J;
    + 4 :  the T;
    + 5 :  the S;
    + 6 :  the Z.

    There are 4 orientations for each piece:

    - 0 is the original orientation;
    - 1 is the 90 degree rotation;
    - 2 is the 180 degree rotation;
    - 3 is the 270 degree rotation.

    Returns:

        numpy.ndarray: A 2-element array:
        the first element is the piece type (0-6);
        the second element is the orientation (0-3).



    **To-Do's**

    + Add input file to specify the probability of each piece.

    """
    choice = np.random.randint(1, [7, 4])
    return choice


def ffnz(matrix, height, column):
    """
    Finds the first non-zero entry in a specified column of a matrix.

    Args:
        matrix (numpy.ndarray): The matrix to search.
        height (int): The height of the matrix.
        column (int): The column index to search in.

    Returns:
        int: The index of the first non-zero entry.
    """
    i = 0
    flag = height
    while (flag == height) and (i < height):
        if matrix[i, column] == 0:
            i = i + 1
        else:
            flag = i
    return flag


height = 16
width = 8
steps = 1

substrate = np.zeros((height, width))

substrate[7, 0] = 0
substrate[6, 1] = 0
substrate[0, 2] = 0
substrate[2, 3] = 0
substrate[3, 4] = 0
substrate[1, 5] = 0
substrate[10, 3] = 11

substrate[8, 7] = 11
substrate[13, 3] = 11
substrate[14, 0] = 11
substrate[14, 1] = 0
substrate[14, 3] = 11
substrate[14, 6] = 11
substrate[15, 0] = 11
substrate[15, 1] = 0
substrate[15, 2] = 11
substrate[15, 3] = 11
substrate[15, 4] = 11
substrate[15, 5] = 11
substrate[15, 6] = 11
substrate[0, 5] = 0
substrate[5, 6] = 0
substrate[3, 7] = 0
substrate[10, 5] = 11
print(substrate)


def Tetris_Ballistic(width, height, steps):
    """
    This function simulates the Tetris Decomposition model on a substrate.

    Args:
        width  (int): The width of the substrate.
        height (int): The height of the matrix.
        steps  (int): The steps to simulate.

    Returns:
        string : Filename of the output file.
    """
    i = 0
    topmost = height - 1
    while i < steps:
        choice = [2, 3]

        # 0. Square Piece{{{
        if choice[0] == 0 and (
            choice[1] == 0 or choice[1] == 1
        ):  # Square, check right boundary
            # position = random.randint(0, width - 1)
            position = 4
            if position != (width - 1):
                if position == 0:
                    # landing_row_outleft = ffnz(susbtrate, height, position - 1),
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)
                    print(landing_row_pivot, landing_row_right, landing_row_outright)

                    if (landing_row_outright < landing_row_pivot) and (
                        landing_row_outright < landing_row_right
                    ):
                        landing_row = landing_row_outright
                        print(landing_row)
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1

                        i += 1

                        print(substrate)

                    elif (landing_row_pivot <= landing_row_right) and (
                        landing_row_pivot <= landing_row_outright
                    ):
                        landing_row = landing_row_pivot
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

                    elif (landing_row_right < landing_row_pivot) and (
                        landing_row_right < landing_row_outright
                    ):
                        landing_row = landing_row_right
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

                elif position == width - 2:
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    # landing_row_outright = ffnz(substrate, height, position + 2)

                    if (landing_row_outleft < landing_row_pivot) and (
                        landing_row_outleft < landing_row_right
                    ):
                        landing_row = landing_row_outleft
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position] = i + 1

                        i += 1
                        print(substrate)

                    if (landing_row_pivot <= landing_row_right) and (
                        landing_row_pivot <= landing_row_outleft
                    ):
                        landing_row = landing_row_pivot
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

                    if (landing_row_right < landing_row_pivot) and (
                        landing_row_right < landing_row_outleft
                    ):
                        landing_row = landing_row_right
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

                else:
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)

                    landing_row = min(
                        landing_row_outleft,
                        landing_row_pivot,
                        landing_row_right,
                        landing_row_outright,
                    )

                    if (
                        landing_row_outleft < landing_row_pivot
                        and landing_row_outleft < landing_row_right
                        and landing_row_outleft <= landing_row_outright
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        landing_row_outright < landing_row_pivot
                        and landing_row_outright < landing_row_right
                        and landing_row_outright < landing_row_outleft
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        landing_row_pivot <= landing_row_right
                        and landing_row_pivot <= landing_row_outleft
                        and landing_row_pivot <= landing_row_outright
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        landing_row_right < landing_row_pivot
                        and landing_row_right < landing_row_outleft
                        and landing_row_right < landing_row_outright
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1

                        i += 1

                        print(substrate)

            else:
                continue

        if choice[0] == 0 and (
            choice[1] == 2 or choice[1] == 3
        ):  # Square, check left boundary
            position = random.randint(0, width - 1)
            if position != 0:
                landing_row = (
                    min(
                        ffnz(substrate, height, position),
                        ffnz(substrate, height, position - 1),
                    )
                    - 1
                )

                substrate[landing_row - 1, position] = i + 1
                substrate[landing_row, position] = i + 1
                substrate[landing_row - 1, position - 1] = i + 1
                substrate[landing_row, position - 1] = i + 1

                i += 1
            else:
                continue

        # 1. Line Piece
        if choice[0] == 1 and (
            choice[1] == 0 or choice[1] == 2
        ):  # Vertical, check ceiling case
            position = random.randint(0, width - 1)
            landing_row = ffnz(substrate, height, position) - 1
            if landing_row >= 3:
                substrate[landing_row, position] = i + 1
                substrate[landing_row - 1, position] = i + 1
                substrate[landing_row - 2, position] = i + 1
                substrate[landing_row - 3, position] = i + 1
                i += 1
            else:
                break

        if (
            choice[0] == 1 and choice[1] == 1
        ):  # Line with right pivot, check left boundary
            position = random.randint(0, width - 1)
            if position - 3 >= 0:
                landing_row = (
                    min(
                        ffnz(substrate, height, position),
                        ffnz(substrate, height, position - 1),
                        ffnz(substrate, height, position - 2),
                        ffnz(substrate, height, position - 3),
                    )
                    - 1
                )
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position - 1] = i + 1
                substrate[landing_row, position - 2] = i + 1
                substrate[landing_row, position - 3] = i + 1

                i += 1
            else:
                continue

        if (
            choice[0] == 1 and choice[1] == 3
        ):  # Line with left pivot, check right boundary
            position = random.randint(0, width - 1)
            if position + 3 <= width - 1:
                landing_row = (
                    min(
                        ffnz(substrate, height, position),
                        ffnz(substrate, height, position + 1),
                        ffnz(substrate, height, position + 2),
                        ffnz(substrate, height, position + 3),
                    )
                    - 1
                )

                substrate[landing_row, position] = i + 1
                substrate[landing_row, position + 1] = i + 1
                substrate[landing_row, position + 2] = i + 1
                substrate[landing_row, position + 3] = i + 1

                i += 1
            else:
                continue  # }}}

        # 2. L Case
        if choice[0] == 2 and choice[1] == 0:  # L case upright, check right boundary
            # position = random.randint(0, width - 1)
            position = 2
            if position != (width - 1):
                if position == 0:
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)
                    print(landing_row_pivot, landing_row_right, landing_row_outright)

                    if (
                        min(
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                            landing_row_outright,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_outright < landing_row_pivot) and (
                            landing_row_outright < landing_row_right
                        ):
                            landing_row = landing_row_outright
                            print(landing_row)
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        elif (landing_row_pivot <= landing_row_right) and (
                            landing_row_pivot <= landing_row_outright
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1

                            i += 1

                            print(substrate)

                        elif (landing_row_right <= landing_row_pivot) and (
                            landing_row_right <= landing_row_outright
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

                elif position == width - 2:
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    # print(landing_row_pivot, landing_row_right, landing_row_outleft)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border

                        if (landing_row_outleft < landing_row_pivot) and (
                            landing_row_outleft < landing_row_right
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (landing_row_pivot <= landing_row_right) and (
                            landing_row_pivot <= landing_row_outleft
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_right < landing_row_pivot) and (
                            landing_row_right <= landing_row_outleft
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue
                else:  # Here the piece falls not at the borders
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)

                    landing_row = min(
                        landing_row_outleft,
                        landing_row_pivot,
                        landing_row_right,
                        landing_row_outright,
                    )

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                            landing_row_outright,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outleft < landing_row_pivot)
                            and (landing_row_outleft < landing_row_right)
                            and (landing_row_outleft <= landing_row_outright)
                        ):
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_outright < landing_row_pivot)
                            and (landing_row_outright < landing_row_right)
                            and (landing_row_outright < landing_row_outleft)
                        ):
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_right)
                            and (landing_row_pivot <= landing_row_outleft)
                            and (landing_row_pivot <= landing_row_outright)
                        ):
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right < landing_row_pivot)
                            and (landing_row_right <= landing_row_outleft)
                            and (landing_row_right <= landing_row_outright)
                        ):
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

            else:
                continue

        if choice[0] == 2 and choice[1] == 1:  # L case laying down, check left boundary
            # position = random.randint(0, width - 1)
            position = 3
            if position != 0 and position != 1:
                if position == 2:
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    print(
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                        landing_row_right,
                    )

                    if (
                        min(
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                            landing_row_right,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border
                        if (
                            (landing_row_right < landing_row_pivot)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_outleft)
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position - 2] = i + 1

                            i += 1

                            print(substrate)
                        if (
                            (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                            and (landing_row_outleft <= landing_row_right)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                            and (landing_row_left <= landing_row_right)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot < landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                elif position == width - 1:
                    landing_row_outoutleft = ffnz(substrate, height, position - 3)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    print(
                        landing_row_outoutleft,
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                    )

                    if (
                        min(
                            landing_row_outoutleft,
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border
                        if (
                            (landing_row_outoutleft < landing_row_outleft)
                            and (landing_row_outoutleft < landing_row_left)
                            and (landing_row_outoutleft < landing_row_pivot)
                        ):
                            landing_row = landing_row_outoutleft
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_outleft <= landing_row_outoutleft)
                            and (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outoutleft)
                            and (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot < landing_row_outoutleft)
                            and (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot <= landing_row_left)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                else:  # Here the piece falls not at the borders
                    landing_row_outoutleft = ffnz(substrate, height, position - 3)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)

                    landing_row = min(
                        landing_row_outoutleft,
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                        landing_row_right,
                    )

                    if (
                        min(
                            landing_row_outoutleft,
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                            landing_row_right,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outoutleft < landing_row_outleft)
                            and (landing_row_outoutleft < landing_row_left)
                            and (landing_row_outoutleft < landing_row_pivot)
                            and (landing_row_outoutleft <= landing_row_right)
                        ):
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_outleft <= landing_row_outoutleft)
                            and (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                            and (landing_row_outleft <= landing_row_right)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outoutleft)
                            and (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                            and (landing_row_left <= landing_row_pivot)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_outoutleft)
                            and (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot < landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right < landing_row_outoutleft)
                            and (landing_row_right < landing_row_outleft)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_pivot)
                        ):
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

            else:
                continue

        if choice[0] == 2 and choice[1] == 2:  # L case with long part on the right.
            # position = random.randint(0, width - 1)
            position = 4
            if position != 0:
                if position == 1:  # Here the piece falls on the left side
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    print(landing_row_left, landing_row_pivot, landing_row_right)

                    if (
                        min(landing_row_left, landing_row_pivot - 1, landing_row_right)
                        >= 2
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_left < landing_row_pivot) and (
                            landing_row_left < landing_row_right
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)
                        if (landing_row_pivot <= landing_row_left) and (
                            landing_row_pivot <= landing_row_right
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_right <= landing_row_left) and (
                            landing_row_right < landing_row_pivot
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                elif position == width - 1:  # Here the piece falls on the right side
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    print(landing_row_outleft, landing_row_left, landing_row_pivot)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_left - 2,
                            landing_row_pivot - 3,
                        )
                        >= 0
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_outleft < landing_row_left - 1) and (
                            landing_row_outleft < landing_row_pivot - 2
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row + 1, position] = i + 1
                            substrate[landing_row + 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_left <= landing_row_outleft + 1) and (
                            landing_row_left < landing_row_pivot
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_pivot <= landing_row_outleft + 2) and (
                            landing_row_pivot <= landing_row_left
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                else:  # Here the piece falls not at the borders
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_left - 2,
                            landing_row_pivot - 3,
                            landing_row_right - 2,
                        )
                        >= 0
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outleft < landing_row_left - 1)
                            and (landing_row_outleft < landing_row_pivot - 2)
                            and (landing_row_outleft < landing_row_right - 1)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row + 1, position] = i + 1
                            substrate[landing_row + 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outleft + 1)
                            and (landing_row_left < landing_row_pivot)
                            and (landing_row_left <= landing_row_right)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_outleft + 2)
                            and (landing_row_pivot <= landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right <= landing_row_outleft + 1)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_pivot)
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                    else:
                        continue

            else:
                continue

        if choice[0] == 2 and choice[1] == 3:  # L case long part on top
            position = width - 4
            # print('position = ', position)
            if position == 0:  # The piece falls on the left border
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                landing_row_outright = ffnz(substrate, height, position + 3)
                landing_row = min(
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )
                print(
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )

                if (
                    min(
                        landing_row_outright,
                        landing_row_right - 1,
                        landing_row_pivot - 2,
                        landing_row_right2 - 1,
                    )
                    >= 0
                ):  # This prevents the piece to overpass the upper border
                    if (
                        (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                        and (landing_row_pivot <= landing_row_outright + 2)
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1

                        print(substrate)
                    if (
                        (landing_row_right < landing_row_pivot + 1)
                        and (landing_row_right <= landing_row_right2)
                        and (landing_row_right <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 < landing_row_right)
                        and (landing_row_right2 <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_outright < landing_row_pivot - 2)
                        and (landing_row_outright < landing_row_right - 1)
                        and (landing_row_outright < landing_row_right2 - 1)
                    ):
                        substrate[landing_row, position + 2] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row + 1, position] = i + 1

                        i += 1

                        print(substrate)

            elif position == width - 3:  # Here the piece falls in the right border
                landing_row_outleft = ffnz(substrate, height, position - 1)
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                print(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                )

                if (
                    min(
                        landing_row_outleft,
                        landing_row_pivot - 1,
                        landing_row_right,
                        landing_row_right2,
                    )
                    >= 1
                ):  # This prevents the piece to overpass the upper border
                    if (
                        (landing_row_outleft <= landing_row_pivot - 1)
                        and (landing_row_outleft <= landing_row_right)
                        and (landing_row_outleft <= landing_row_right2)
                    ):
                        landing_row = landing_row_outleft
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_pivot <= landing_row_outleft)
                        and (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                    ):
                        landing_row = landing_row_pivot
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right < landing_row_outleft)
                        and (landing_row_right < landing_row_pivot - 1)
                        and (landing_row_right <= landing_row_right2)
                    ):
                        landing_row = landing_row_right
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_outleft)
                        and (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 <= landing_row_right - 1)
                    ):
                        landing_row = landing_row_right2
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

            else:  # Here the piece falls not at the borders
                landing_row_outleft = ffnz(substrate, height, position - 1)
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                landing_row_outright = ffnz(substrate, height, position + 3)

                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )

                if (
                    min(
                        landing_row_outleft - 1,
                        landing_row_pivot - 2,
                        landing_row_right - 1,
                        landing_row_right2 - 1,
                        landing_row_outright,
                    )
                    >= 0
                ):  # This prevents the piece to overpass the upper border

                    if (
                        (landing_row_outleft <= landing_row_pivot - 1)
                        and (landing_row_outleft <= landing_row_right)
                        and (landing_row_outleft <= landing_row_right2)
                        and (landing_row_outleft <= landing_row_outright + 1)
                    ):
                        landing_row = landing_row_outleft
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        (landing_row_pivot <= landing_row_outleft)
                        and (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                        and (landing_row_pivot <= landing_row_outright + 2)
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        (landing_row_right < landing_row_outleft)
                        and (landing_row_right < landing_row_pivot - 1)
                        and (landing_row_right <= landing_row_right2)
                        and (landing_row_right <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_outleft)
                        and (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 < landing_row_right)
                        and (landing_row_right2 <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_outright < landing_row_outleft - 1)
                        and (landing_row_outright < landing_row_pivot - 2)
                        and (landing_row_outright < landing_row_right)
                        and (landing_row_outright < landing_row_right2)
                    ):
                        substrate[landing_row + 1, position] = i + 1
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row, position + 2] = i + 1

                        i += 1

                        print(substrate)
                    else:
                        continue

        else:
            continue

        # 3. J Piece
        if choice[0] == 3 and choice[1] == 0:  # J case with long piece on the left
            position = random.randint(0, width - 1)
            if position != (width - 1):
                if position == 0:
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)
                    print(landing_row_pivot, landing_row_right, landing_row_outright)

                    if (
                        min(
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                            landing_row_outright,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_outright < landing_row_pivot) and (
                            landing_row_outright < landing_row_right
                        ):
                            landing_row = landing_row_outright
                            print(landing_row)
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        elif (landing_row_pivot <= landing_row_right) and (
                            landing_row_pivot <= landing_row_outright
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1

                            i += 1

                            print(substrate)

                        elif (landing_row_right <= landing_row_pivot) and (
                            landing_row_right <= landing_row_outright
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

                elif position == width - 2:
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    # print(landing_row_pivot, landing_row_right, landing_row_outleft)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border

                        if (landing_row_outleft < landing_row_pivot) and (
                            landing_row_outleft < landing_row_right
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (landing_row_pivot <= landing_row_right) and (
                            landing_row_pivot <= landing_row_outleft
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_right < landing_row_pivot) and (
                            landing_row_right <= landing_row_outleft
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue
                else:  # Here the piece falls not at the borders
                    landing_row_outleft = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_outright = ffnz(substrate, height, position + 2)

                    landing_row = min(
                        landing_row_outleft,
                        landing_row_pivot,
                        landing_row_right,
                        landing_row_outright,
                    )

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_pivot - 1,
                            landing_row_right - 1,
                            landing_row_outright,
                        )
                        >= 2
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outleft < landing_row_pivot)
                            and (landing_row_outleft < landing_row_right)
                            and (landing_row_outleft <= landing_row_outright)
                        ):
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_outright < landing_row_pivot)
                            and (landing_row_outright < landing_row_right)
                            and (landing_row_outright < landing_row_outleft)
                        ):
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position + 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_right)
                            and (landing_row_pivot <= landing_row_outleft)
                            and (landing_row_pivot <= landing_row_outright)
                        ):
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right < landing_row_pivot)
                            and (landing_row_right <= landing_row_outleft)
                            and (landing_row_right <= landing_row_outright)
                        ):
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 1, position + 1] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

            else:
                continue

        if choice[0] == 3 and choice[1] == 1:  # J case with long piece on the top
            # position = random.randint(0, width - 1)
            position = 3
            if position != 0 and position != 1:
                if position == 2:
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    print(
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                        landing_row_right,
                    )

                    if (
                        min(
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                            landing_row_right,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border
                        if (
                            (landing_row_right < landing_row_pivot)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_outleft)
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position - 2] = i + 1

                            i += 1

                            print(substrate)
                        if (
                            (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                            and (landing_row_outleft <= landing_row_right)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                            and (landing_row_left <= landing_row_right)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot < landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                elif position == width - 1:
                    landing_row_outoutleft = ffnz(substrate, height, position - 3)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    print(
                        landing_row_outoutleft,
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                    )

                    if (
                        min(
                            landing_row_outoutleft,
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border
                        if (
                            (landing_row_outoutleft < landing_row_outleft)
                            and (landing_row_outoutleft < landing_row_left)
                            and (landing_row_outoutleft < landing_row_pivot)
                        ):
                            landing_row = landing_row_outoutleft
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_outleft <= landing_row_outoutleft)
                            and (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outoutleft)
                            and (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot < landing_row_outoutleft)
                            and (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot <= landing_row_left)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                else:  # Here the piece falls not at the borders
                    landing_row_outoutleft = ffnz(substrate, height, position - 3)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)

                    landing_row = min(
                        landing_row_outoutleft,
                        landing_row_outleft,
                        landing_row_left,
                        landing_row_pivot,
                        landing_row_right,
                    )

                    if (
                        min(
                            landing_row_outoutleft,
                            landing_row_outleft - 1,
                            landing_row_left - 1,
                            landing_row_pivot - 1,
                            landing_row_right,
                        )
                        >= 1
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outoutleft < landing_row_outleft)
                            and (landing_row_outoutleft < landing_row_left)
                            and (landing_row_outoutleft < landing_row_pivot)
                            and (landing_row_outoutleft <= landing_row_right)
                        ):
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_outleft <= landing_row_outoutleft)
                            and (landing_row_outleft <= landing_row_left)
                            and (landing_row_outleft <= landing_row_pivot)
                            and (landing_row_outleft <= landing_row_right)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outoutleft)
                            and (landing_row_left < landing_row_outleft)
                            and (landing_row_left <= landing_row_pivot)
                            and (landing_row_left <= landing_row_pivot)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_outoutleft)
                            and (landing_row_pivot < landing_row_outleft)
                            and (landing_row_pivot < landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            substrate[landing_row - 1, position - 2] = i + 1
                            substrate[landing_row - 1, position - 1] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right < landing_row_outoutleft)
                            and (landing_row_right < landing_row_outleft)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_pivot)
                        ):
                            substrate[landing_row, position - 2] = i + 1
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1

                            i += 1

                            print(substrate)
                    else:
                        continue

            else:
                continue

        if choice[0] == 3 and choice[1] == 2:  # J case with long part on the left.
            # position = random.randint(0, width - 1)
            position = 4
            if position != 0:
                if position == 1:  # Here the piece falls on the left side
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    print(landing_row_left, landing_row_pivot, landing_row_right)

                    if (
                        min(landing_row_left, landing_row_pivot - 1, landing_row_right)
                        >= 2
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_left < landing_row_pivot) and (
                            landing_row_left < landing_row_right
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)
                        if (landing_row_pivot <= landing_row_left) and (
                            landing_row_pivot <= landing_row_right
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_right <= landing_row_left) and (
                            landing_row_right < landing_row_pivot
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                elif position == width - 1:  # Here the piece falls on the right side
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    print(landing_row_outleft, landing_row_left, landing_row_pivot)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_left - 2,
                            landing_row_pivot - 3,
                        )
                        >= 0
                    ):  # This prevents the piece to overpass the upper border
                        if (landing_row_outleft < landing_row_left - 1) and (
                            landing_row_outleft < landing_row_pivot - 2
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row + 1, position] = i + 1
                            substrate[landing_row + 2, position] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_left <= landing_row_outleft + 1) and (
                            landing_row_left < landing_row_pivot
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (landing_row_pivot <= landing_row_outleft + 2) and (
                            landing_row_pivot <= landing_row_left
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                else:  # Here the piece falls not at the borders
                    landing_row_outleft = ffnz(substrate, height, position - 2)
                    landing_row_left = ffnz(substrate, height, position - 1)
                    landing_row_pivot = ffnz(substrate, height, position)
                    landing_row_right = ffnz(substrate, height, position + 1)

                    if (
                        min(
                            landing_row_outleft,
                            landing_row_left - 2,
                            landing_row_pivot - 3,
                            landing_row_right - 2,
                        )
                        >= 0
                    ):  # This prevents the piece to overpass the upper border

                        if (
                            (landing_row_outleft < landing_row_left - 1)
                            and (landing_row_outleft < landing_row_pivot - 2)
                            and (landing_row_outleft < landing_row_right - 1)
                        ):
                            landing_row = landing_row_outleft
                            substrate[landing_row, position - 1] = i + 1
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row + 1, position] = i + 1
                            substrate[landing_row + 2, position] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_left <= landing_row_outleft + 1)
                            and (landing_row_left < landing_row_pivot)
                            and (landing_row_left <= landing_row_right)
                        ):
                            landing_row = landing_row_left
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1
                            print(substrate)

                        if (
                            (landing_row_pivot <= landing_row_outleft + 2)
                            and (landing_row_pivot <= landing_row_left)
                            and (landing_row_pivot <= landing_row_right)
                        ):
                            landing_row = landing_row_pivot
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 3, position] = i + 1
                            substrate[landing_row - 3, position - 1] = i + 1

                            i += 1

                            print(substrate)

                        if (
                            (landing_row_right <= landing_row_outleft + 1)
                            and (landing_row_right < landing_row_left)
                            and (landing_row_right < landing_row_pivot)
                        ):
                            landing_row = landing_row_right
                            substrate[landing_row, position] = i + 1
                            substrate[landing_row - 1, position] = i + 1
                            substrate[landing_row - 2, position] = i + 1
                            substrate[landing_row - 2, position - 1] = i + 1

                            i += 1

                            print(substrate)

                    else:
                        continue

            else:
                continue

        if choice[0] == 2 and choice[1] == 3:  # J case long part on the bottom
            position = width - 4
            # print('position = ', position)
            if position == 0:  # The piece falls on the left border
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                landing_row_outright = ffnz(substrate, height, position + 3)
                landing_row = min(
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )
                print(
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )

                if (
                    min(
                        landing_row_outright,
                        landing_row_right - 1,
                        landing_row_pivot - 2,
                        landing_row_right2 - 1,
                    )
                    >= 0
                ):  # This prevents the piece to overpass the upper border
                    if (
                        (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                        and (landing_row_pivot <= landing_row_outright + 2)
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1

                        print(substrate)
                    if (
                        (landing_row_right < landing_row_pivot + 1)
                        and (landing_row_right <= landing_row_right2)
                        and (landing_row_right <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 < landing_row_right)
                        and (landing_row_right2 <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_outright < landing_row_pivot - 2)
                        and (landing_row_outright < landing_row_right - 1)
                        and (landing_row_outright < landing_row_right2 - 1)
                    ):
                        substrate[landing_row, position + 2] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row + 1, position] = i + 1

                        i += 1

                        print(substrate)

            elif position == width - 3:  # Here the piece falls in the right border
                landing_row_outleft = ffnz(substrate, height, position - 1)
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                print(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                )

                if (
                    min(
                        landing_row_outleft,
                        landing_row_pivot - 1,
                        landing_row_right,
                        landing_row_right2,
                    )
                    >= 1
                ):  # This prevents the piece to overpass the upper border
                    if (
                        (landing_row_outleft <= landing_row_pivot - 1)
                        and (landing_row_outleft <= landing_row_right)
                        and (landing_row_outleft <= landing_row_right2)
                    ):
                        landing_row = landing_row_outleft
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_pivot <= landing_row_outleft)
                        and (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                    ):
                        landing_row = landing_row_pivot
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right < landing_row_outleft)
                        and (landing_row_right < landing_row_pivot - 1)
                        and (landing_row_right <= landing_row_right2)
                    ):
                        landing_row = landing_row_right
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_outleft)
                        and (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 <= landing_row_right - 1)
                    ):
                        landing_row = landing_row_right2
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

            else:  # Here the piece falls not at the borders
                landing_row_outleft = ffnz(substrate, height, position - 1)
                landing_row_pivot = ffnz(substrate, height, position)
                landing_row_right = ffnz(substrate, height, position + 1)
                landing_row_right2 = ffnz(substrate, height, position + 2)
                landing_row_outright = ffnz(substrate, height, position + 3)

                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_right2,
                    landing_row_outright,
                )

                if (
                    min(
                        landing_row_outleft - 1,
                        landing_row_pivot - 2,
                        landing_row_right - 1,
                        landing_row_right2 - 1,
                        landing_row_outright,
                    )
                    >= 0
                ):  # This prevents the piece to overpass the upper border

                    if (
                        (landing_row_outleft <= landing_row_pivot - 1)
                        and (landing_row_outleft <= landing_row_right)
                        and (landing_row_outleft <= landing_row_right2)
                        and (landing_row_outleft <= landing_row_outright + 1)
                    ):
                        landing_row = landing_row_outleft
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        (landing_row_pivot <= landing_row_outleft)
                        and (landing_row_pivot <= landing_row_right + 1)
                        and (landing_row_pivot <= landing_row_right2 + 1)
                        and (landing_row_pivot <= landing_row_outright + 2)
                    ):
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 2, position] = i + 1
                        substrate[landing_row - 2, position + 1] = i + 1
                        substrate[landing_row - 2, position + 2] = i + 1

                        i += 1
                        print(substrate)

                    if (
                        (landing_row_right < landing_row_outleft)
                        and (landing_row_right < landing_row_pivot - 1)
                        and (landing_row_right <= landing_row_right2)
                        and (landing_row_right <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_right2 < landing_row_outleft)
                        and (landing_row_right2 < landing_row_pivot - 1)
                        and (landing_row_right2 < landing_row_right)
                        and (landing_row_right2 <= landing_row_outright + 1)
                    ):
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row - 1, position] = i + 1
                        substrate[landing_row - 1, position + 1] = i + 1
                        substrate[landing_row - 1, position + 2] = i + 1

                        i += 1

                        print(substrate)

                    if (
                        (landing_row_outright < landing_row_outleft - 1)
                        and (landing_row_outright < landing_row_pivot - 2)
                        and (landing_row_outright < landing_row_right)
                        and (landing_row_outright < landing_row_right2)
                    ):
                        substrate[landing_row + 1, position] = i + 1
                        substrate[landing_row, position] = i + 1
                        substrate[landing_row, position + 1] = i + 1
                        substrate[landing_row, position + 2] = i + 1

                        i += 1

                        print(substrate)
                    else:
                        continue

        else:
            continue

        # 4. T Piece
        if (
            choice[0] == 4 and choice[1] == 0
        ):  # T case long part on top, check left and right boundaries
            position = random.randint(0, width - 1)
            # position = 7
            if (position != width - 1) and (position != 0):
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_center = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(
                    landing_row_right, landing_row_left, landing_row_center
                )

                if (landing_row_left < landing_row_center) and (
                    landing_row_left <= landing_row_right
                ):
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left, position + 1] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1

                    i += 1
                elif (landing_row_center <= landing_row_left) and (
                    landing_row_center <= landing_row_right
                ):
                    substrate[landing_row_center, position] = i + 1
                    substrate[landing_row_center - 1, position - 1] = i + 1
                    substrate[landing_row_center - 1, position] = i + 1
                    substrate[landing_row_center - 1, position + 1] = i + 1
                    i += 1
                elif (landing_row_right <= landing_row_left) and (
                    landing_row_right < landing_row_center
                ):
                    substrate[landing_row_right, position - 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    i += 1

                else:
                    continue
            else:
                continue

        if (
            choice[0] == 4 and choice[1] == 1
        ):  # T case long part on the left, check right boundary
            position = random.randint(0, width - 1)
            # position = 7
            if position != width - 1:
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_right, landing_row_left)

                if min(landing_row_right, landing_row_left) < 2:
                    break

                elif landing_row_right < landing_row_left:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1

                    i += 1
                elif landing_row_right >= landing_row_left:
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left - 2, position] = i + 1
                    substrate[landing_row_left - 1, position + 1] = i + 1
                    i += 1
                else:
                    continue

        if (
            choice[0] == 4 and choice[1] == 2
        ):  # T case long part on the bottom, check left and right boundaries
            position = random.randint(0, width - 1)
            # position = 4
            if (position != 0) and (position != width - 1):
                # Pass function through here
                landing_row = (
                    min(
                        ffnz(substrate, height, position),
                        ffnz(substrate, height, position + 1),
                        ffnz(substrate, height, position - 1),
                    )
                    - 1
                )

                if landing_row >= 1:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row, position + 1] = i + 1
                    substrate[landing_row, position - 1] = i + 1
                    substrate[landing_row - 1, position] = i + 1

                    i += 1
                else:
                    break
            else:
                continue

        if (
            choice[0] == 4 and choice[1] == 3
        ):  # T case long part on the right, check left boundary
            position = random.randint(0, width - 1)
            # position = 7
            if position != 0:
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_right = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_right, landing_row_left)

                if min(landing_row_right, landing_row_left) < 2:
                    break

                elif landing_row_right > landing_row_left:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1

                    i += 1
                elif landing_row_right <= landing_row_left:
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 2, position] = i + 1
                    substrate[landing_row_right - 1, position - 1] = i + 1
                    i += 1
                else:
                    continue
            else:
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_right = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_right, landing_row_left)
                continue

        # 5. S Piece
        if choice[0] == 5 and (
            choice[1] == 0 or choice[1] == 2
        ):  # S case laying down, check left and right boundary
            position = random.randint(0, width - 1)
            if (
                position + 1 <= width - 1 and position - 1 >= 0
            ):  # Check left and right bdy
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(
                    landing_row_pivot, landing_row_right, landing_row_left
                )

                if landing_row <= 2:
                    break

                if (
                    landing_row_pivot < landing_row_right
                    and landing_row_pivot <= landing_row_left
                ):
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot, position - 1] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot - 1, position + 1] = i + 1
                    i += 1

                elif (
                    landing_row_right < landing_row_pivot
                    and landing_row_right < landing_row_left
                ):
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    substrate[landing_row_right + 1, position - 1] = i + 1
                    i += 1

            else:
                continue

        if (
            choice[0] == 5 and choice[1] == 1
        ):  # S case standing up, pivot on the right, check left boundary SEE Z CASE
            position = random.randint(0, width - 1)
            if position - 1 >= 0:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_left - 1:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot - 1, position - 1] = i + 1
                    substrate[landing_row_pivot - 2, position - 1] = i + 1
                    i += 1

                elif landing_row_left + 1 < landing_row_pivot:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1
                    i += 1
            else:
                continue

        if (
            choice[0] == 5 and choice[1] == 3
        ):  # S case standing up, pivot on the left, check right boundary SEE Z CASE
            position = random.randint(0, width - 1)
            if position + 1 <= width - 1:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_right:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot, position + 1] = i + 1
                    substrate[landing_row_pivot + 1, position + 1] = i + 1
                    i += 1

                elif landing_row_right <= landing_row_pivot:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position + 1] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 2, position] = i + 1
                    i += 1
            else:
                continue

        # 6. Z Case
        if choice[0] == 6 and (
            choice[1] == 0 or choice[1] == 2
        ):  # Z case laying down, check left and right boundary
            position = random.randint(0, width - 1)
            if (
                position + 1 <= width - 1 and position - 1 >= 0
            ):  # Check left and right bdy
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(
                    landing_row_pivot, landing_row_right, landing_row_left
                )

                if landing_row <= 2:
                    break

                if (
                    landing_row_pivot < landing_row_left
                    and landing_row_pivot <= landing_row_right
                ):
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot, position + 1] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot - 1, position - 1] = i + 1
                    i += 1

                elif (
                    landing_row_left < landing_row_pivot
                    and landing_row_left < landing_row_right
                ):
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1
                    substrate[landing_row_left + 1, position + 1] = i + 1
                    i += 1

                elif (
                    landing_row_right <= landing_row_pivot
                    and landing_row_right < landing_row_left
                ):
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 1, position - 1] = i + 1
                    i += 1

            else:
                continue

        if (
            choice[0] == 6 and choice[1] == 1
        ):  # Z case standing up, pivot on the right, check left boundary SEE S CASE
            position = random.randint(0, width - 1)
            if position - 1 >= 0:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_left <= landing_row_pivot:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position - 1] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left - 2, position] = i + 1
                    i += 1

                elif landing_row_pivot < landing_row_left:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot, position - 1] = i + 1
                    substrate[landing_row_pivot + 1, position - 1] = i + 1
                    i += 1
            else:
                continue

        if (
            choice[0] == 6 and choice[1] == 3
        ):  # Z case standing up, pivot on the left, check right boundary SEE S CASE
            position = random.randint(0, width - 1)
            if position + 1 <= width - 1:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right)

                if landing_row <= 2:
                    break

                if landing_row_pivot <= landing_row_right:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot - 1, position + 1] = i + 1
                    substrate[landing_row_pivot - 2, position + 1] = i + 1
                    i += 1

                elif landing_row_right < landing_row_pivot:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    i += 1
            else:
                continue

        if landing_row < topmost:
            topmost = landing_row

        if (steps + 1) % 200 == 0:
            print(f"Step: {steps + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.05 or topmost <= 2:
            print(f"Stopped at step {steps + 1}, Level at {height - topmost}/{height}")
            break


#    outputfile = f"Tetris_Substrate_{width}x{height}_Particles={steps}.txt"
#    np.savetxt(outputfile, substrate, fmt="%d", delimiter=",")
#    print(f"{outputfile} saved!")
#    return outputfile


def main():
    """

    To use the script from terminal, the following options are expected:

    -w, --width    : Width of the substrate (default: 100)
    -e, --height   : Maximum height of the substrate (default: 60)
    -s, --steps    : Number of particles to drop (default: 5000)

    It returns:

    1. A text file representing the substrate state.

    Example:

        .. code-block:: bash

            > ptyhon3 tetris_complete.py -w 100 -e 60 -s 5000

        In this example, the script will simulate Tetris Decomposition on a
        substrate of size 100x60 for 5000 steps.
    """

    parser = argparse.ArgumentParser(
        description="""

    Simulate Random Deposition on a substrate.
    Outputs: 1. Substrate_WIDTHxHEIGHT_Particles=STEPS_[Relaxed/BD].txt
                A text file for the substrate.
             2. Statistical figures, loglog plot for the interface width and the estimated slope.

    Author: Ian Ruau and Mauricio Mountes
    Date: 2023-12-01


                                     """,
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


#    args = parser.parse_args()

# Outputfile = Tetris_RD(args.width, args.height, args.steps)
# print("Computing the interface width...")
# interface_width(Outputfile)

Tetris_Ballistic(width, height, steps)
