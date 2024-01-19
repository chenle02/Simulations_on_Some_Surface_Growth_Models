#!/usr/bin/env python3
"""

This module simulates the surface growth by Tetris pieces. It includes
functions to generate random Tetris pieces, calculate their landing positions
on a substrate, and simulate a game of Tetris for a given number of steps and a
defined grid size.

By Ian Ruau (iir0001@auburn.edu) and Mauricio Montes (mauricio.montes@auburn.edu)
Date: 12/2023

"""

import numpy as np  # {{{
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
    choice = np.random.randint(0, [7, 4])
    return choice  # }}}


# Prebuilt config, Global variable substrate {{{
height = 15
width = 15
substrate = np.zeros((height, width))

i = 0
steps = 20


def Initialize_Substrate():
    substrate[11, 3] = 11
    substrate[12, 3] = 11
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
    substrate[12, 2] = 11
    substrate[10, 6] = 0
    substrate[10, 5] = 0
    substrate[10, 4] = 0
    substrate[10, 3] = 11

    substrate[6, 6] = 31
    substrate[6, 3] = 31
    substrate[6, 2] = 31
    substrate[6, 1] = 31
    substrate[6, 2] = 31
    substrate[6, 7] = 31
    substrate[6, 0] = 31
    print(substrate)  # }}}


def ffnz(matrix, height, column):  # {{{
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
    return flag  # }}}


def Tetris_Ballistic(width, height, steps):
    """
    This function simulates the Tetris Decomposition model on a substrate.

    Args:
        width (int):  The with of the matrix.
        height (int): The height of the matrix.
        steps  (int): The steps to simulate.

    Returns:
        string : Filename of the output file.
    """
    # my_list = [0, 1, 4, 5, 6]
    my_list = [0]
    """
    + 0 :  the square;
    + 1 :  the line;
    + 2 :  the L;
    + 3 :  the J;
    + 4 :  the T;
    + 5 :  the S;
    + 6 :  the Z.
    """
    rotation_list = [1]
    """
    + 0 is the original orientation;
    + 1 is the 90 degree rotation;
    + 2 is the 180 degree rotation;
    + 3 is the 270 degree rotation.
    """
    i = 0
    print("i:", i, "steps:", steps)
    while i < steps:
        choice = [random.choice(my_list), random.choice(rotation_list)]

        match choice[0]:
            case 0:
                # Square case
                i = Update_Q(i, choice[1])
                print(i)
            case 1:
                # Line case
                i = Update_I(i, choice[1])
            case 2:
                # L case
                i = Update_L(i, choice[1])
            case 3:
                # J case
                i = Update_J(i, choice[1])
            case 4:
                # T case
                i = Update_T(i, choice[1])
            case 5:
                # S case
                i = Update_S(i, choice[1])
            case 6:
                # Z case
                i = Update_Z(i, choice[1])
            case _:
                # Error
                print("Wrong Choice of the Pieces")

    print(substrate)


def place_Q(position, landing_row, i):
    """
    Place a square with pivot at the bottom left corner on the global substrate:
        00
        10
    Args:
        position (int): The position of the pivot.
        landing_row (int): The landing row of the pivot.
        i (int): The step number.

    Return:
        None
    """
    global substrate
    substrate[landing_row - 1, position] = i
    substrate[landing_row - 2, position] = i
    substrate[landing_row - 1, position + 1] = i
    substrate[landing_row - 2, position + 1] = i


def Update_Q(i, rot):
    """
    Updates the substrate with a square piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.
            + rot = 0
                10
                00
            + rot = 1
                00
                10
            + rot = 2
                00
                01
            + rot = 3
                01
                00

    Returns:
        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
            + If it returns the same value as the input, it means it cannot find a landing position.
    """
    # print("Update a square piece")
    global substrate
    [width, height] = substrate.shape
    position = random.randint(0, width - 1)

    # Reduce all four rotation cases to to case rot = 1
    if rot in [2, 3]:
        position -= 1
    elif rot not in [0, 1]:
        print("Wrong rotation value")
        return i

    # Check the two boundaries
    if position < 0 or position > width - 2:
        print("Discard the piece due to the boundary")
        return i

    next = i

    landing_row_outleft = ffnz(substrate, height, position - 1) + 1 if position > 0 else height
    landing_row_pivot = ffnz(substrate, height, position)
    landing_row_right = ffnz(substrate, height, position + 1)
    landing_row_outright = ffnz(substrate, height, position + 2) + 1 if position < width - 2 else height

    # Find minimum landing row
    landing_row = min(
        landing_row_outleft,
        landing_row_pivot,
        landing_row_right,
        landing_row_outright)

    print("Step:", i, "position:", position, "landing_row:", landing_row)

    if landing_row < 3:
        next = -1
    else:
        # Place square based on the minimum landing row
        next = i + 1
        place_Q(position, landing_row, next)

    return next


def Test_Q():
    """
    This is a test function for the square piece.
    """
    i = 0
    steps = 30
    global substrate
    for rot in range(4):
        print("Test rotation ", rot)
        while i < steps:
            i = Update_Q(i, rot)
            if i == -1:
                print("Game Over, reached to the top")
                break
        print(substrate)
        input("")


Test_Q()


def Update_I(i, rot):
    """
    Updates the substrate with a line piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update a line piece")
    return next


def Update_L(i, rot):
    """
    Updates the substrate with an L piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update an L piece")
    return next


def Update_J(i, rot):
    """
    Updates the substrate with a J piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update an L piece")
    return next


def Update_T(i, rot):
    """
    Updates the substrate with a T piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update a T piece")
    return next


def Update_S(i, rot):
    """
    Updates the substrate with an S piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update an S piece")
    return next


def Update_Z(i, rot):
    """
    Updates the substrate with a Z piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece.

    Returns:
        numpy.ndarray: The updated substrate.
    """
    global substrate
    next = i
    print("Update a Z piece")
    return next


# Tetris_Ballistic(width, height, steps)


