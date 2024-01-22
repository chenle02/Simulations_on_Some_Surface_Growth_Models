#!/usr/bin/env python3
"""

This module simulates the surface growth by Tetris pieces. It includes
functions to generate random Tetris pieces, calculate their landing positions
on a substrate, and simulate a game of Tetris for a given number of steps and a
defined grid size.

https://en.wikipedia.org/wiki/Tetromino

By Le Chen, Mauricio Montes and Ian Ruau

"""

import numpy as np
import random
# import argparse


class Tetris_Ballistic:
    def __init__(self, grid_size=[15, 15], steps=30):
        """
        Initializes the Tetris_Ballistic simulation.

        Args:
            grid_size (tuple): The size of the grid (width, height).
            steps (int): The number of steps to simulate.
        """
        self.grid_size = grid_size
        self.steps = steps
        self.width, self.height = grid_size
        self.substrate = np.zeros(grid_size)  # Example initialization

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
        return choice

    def Initialize_Substrate(self):
        """
        Initializes the substrate manually.
        """
        self.substrate[11, 3] = 11
        self.substrate[12, 3] = 11
        self.substrate[13, 3] = 11
        self.substrate[14, 0] = 11
        self.substrate[14, 1] = 0
        self.substrate[14, 3] = 11
        self.substrate[14, 6] = 11
        self.substrate[15, 0] = 11
        self.substrate[15, 1] = 0
        self.substrate[15, 2] = 11
        self.substrate[15, 3] = 11
        self.substrate[15, 4] = 11
        self.substrate[15, 5] = 11
        self.substrate[15, 6] = 11
        self.substrate[12, 2] = 11
        self.substrate[10, 6] = 0
        self.substrate[10, 5] = 0
        self.substrate[10, 4] = 0
        self.substrate[10, 3] = 11

        self.substrate[6, 6] = 31
        self.substrate[6, 3] = 31
        self.substrate[6, 2] = 31
        self.substrate[6, 1] = 31
        self.substrate[6, 2] = 31
        self.substrate[6, 7] = 31
        self.substrate[6, 0] = 31
        print(self.substrate)

    def ffnz(self, column):
        """
        Finds the first non-zero entry in the specified column of the
        substrate.

        This method scans the column from top to bottom (starting from index 0)
        and returns the index of the first non-zero entry. If all entries in
        the column are zero, a special value (indicating this condition) is
        returned.

        Args:
            column (int): The column index in the substrate to search in. It should
                        be within the range of the substrate's columns.

        Returns:
            int: The index of the first non-zero entry in the specified column. If the
                column contains only zeros, returns the value of self.height,
                which indicates that no non-zero entry was found.
        """
        i = 0
        flag = self.height
        while (flag == self.height) and (i < self.height):
            if self.substrate[i, column] == 0:
                i = i + 1
            else:
                flag = i
        return flag

    def place_O(self, position, landing_row, i):
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
        self.substrate[landing_row - 1, position] = i
        self.substrate[landing_row - 2, position] = i
        self.substrate[landing_row - 1, position + 1] = i
        self.substrate[landing_row - 2, position + 1] = i

    def Update_O(self, i, rot=0):
        """
        Updates the substrate with a square piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece. By symmetry, all rotation will be treated as
                00
                10

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 2)

        next = i

        landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 else self.height
        landing_row_pivot = self.ffnz(position)
        landing_row_right = self.ffnz(position + 1) if position < self.width - 1 else self.height
        landing_row_outright = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height

        # Find minimum landing row
        landing_row = min(
            landing_row_outleft,
            landing_row_pivot,
            landing_row_right,
            landing_row_outright)

        if landing_row < 2:
            return -1

        # Place square based on the minimum landing row
        next = i + 1
        self.place_O(position, landing_row, next)

        return next

    def Test_O(self):
        """
        This is a test function for the square piece.
        """
        i = 0
        steps = 30
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            self.substrate = np.zeros((self.height, self.width))
            while i < steps:
                i = self.Update_O(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_I(self, position, landing_row, i, rot=0):
        """
        Place a square with pivot at the bottom left corner on the substrate:
            1000
            or
            0
            0
            0
            1
        Args:
            position (int): The position of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece; 0 and 2 for horizontal, 1 and 3 for vertical.

        Return:
            None
        """
        if rot in [0, 2]:
            # Horizontal
            self.substrate[landing_row - 1, position] = i
            self.substrate[landing_row - 1, position + 1] = i
            self.substrate[landing_row - 1, position + 2] = i
            self.substrate[landing_row - 1, position + 3] = i
        elif rot in [1, 3]:
            # Vertical
            self.substrate[landing_row - 1, position] = i
            self.substrate[landing_row - 2, position] = i
            self.substrate[landing_row - 3, position] = i
            self.substrate[landing_row - 4, position] = i

    def Update_I(self, i, rot=0):
        """
        Updates the substrate with a line piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.
                + rot = 0
                    1000
                + rot = 1
                    0
                    0
                    0
                    1
                + rot = 2
                    0001
                + rot = 3
                    1
                    0
                    0
                    0

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i

        match rot:
            case 0 | 2:
                position = random.randint(0, self.width - 4)

                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_right1 = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2  = self.ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_right3  = self.ffnz(position + 3) if position < self.width - 3 else self.height
                landing_row_outright  = self.ffnz(position + 4) + 1 if position < self.width - 4 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right1,
                    landing_row_right2,
                    landing_row_right3,
                    landing_row_outright)

                if landing_row < 1:
                    return -1

                next = i + 1
                place_I(position, landing_row, next, rot=0)

            case 1 | 3:
                position = random.randint(0, width - 1)

                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 4:
                    return -1

                next = i + 1
                place_I(position, landing_row, next, rot=0)

        return next

    def Test_I(self):
        """
        This is a test function for the Line piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_I(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_L(self, position, landing_row, i, rot=0):
        """
        Place an L with pivot at the corner.
        + rot = 0
            0
            0
            10
        + rot = 1
            0
            001
        + rot = 2
            01
            0
            0
        + rot = 3
            100
            0
        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        global substrate

        match rot:
            case 0:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 3, position] = i
                substrate[landing_row - 1, position + 1] = i
            case 1:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 1, position - 2] = i
                substrate[landing_row - 2, position] = i
            case 2:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row + 0, position] = i
                substrate[landing_row + 1, position] = i
            case 3:
                substrate[landing_row - 1, position] = i
                substrate[landing_row, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row - 1, position + 2] = i

    def Update_L(self, i, rot=0):
        """
        Updates the substrate with an L piece.
        + rot = 0
            0
            0
            10
        + rot = 1
            0
            001
        + rot = 2
            01
            0
            0
        + rot = 3
            100
            0

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        global substrate
        [width, height] = substrate.shape

        next = i
        match rot:
            case 0:
                position = random.randint(0, width - 2)

                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 0 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_right  = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright  = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_L(position, landing_row, next, rot=0)
            case 1:
                position = random.randint(2, width - 1)

                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_left1  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_left2  = self.ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft  = self.ffnz(position - 3) + 1 if position > 3 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_left1,
                    landing_row_left2,
                    landing_row_outright)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_L(position, landing_row, next, rot=0)
            case 2:
                position = random.randint(1, width - 1)

                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outleft1  = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_outleft2  = self.ffnz(position - 2) + 3 if position > 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft1,
                    landing_row_outleft2,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_L(position, landing_row - 2, next, rot=0)
            case 3:
                position = random.randint(0, width - 3)

                landing_row_outright  = self.ffnz(position + 3) + 2 if position < self.width - 3 else self.height
                landing_row_right1  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_right2  = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright,
                    landing_row_right1,
                    landing_row_right2)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_L(position, landing_row - 1, next, rot=0)

        return next

    def Test_L(self):
        """
        This is a test function for the L piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_L(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_J(self, position, landing_row, i, rot=0):
        """
        Place a J with pivot at the corner.
        + rot = 0
            0
            0
            01
        + rot = 1
            001
            0
        + rot = 2
            10
            0
            0
        + rot = 3
            0
            100

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        global substrate

        match rot:
            case 0:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 3, position] = i
                substrate[landing_row - 1, position - 1] = i
            case 1:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 1, position - 2] = i
                substrate[landing_row - 0, position] = i
            case 2:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row + 0, position] = i
                substrate[landing_row + 1, position] = i
            case 3:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row - 1, position + 2] = i

    def Update_J(self, i, rot=0):
        """
        Updates the substrate with a J piece.
        + rot = 0
            0
            0
            01
        + rot = 1
            001
            0
        + rot = 2
            10
            0
            0
        + rot = 3
            0
            100

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        global substrate
        [width, height] = substrate.shape
        position = random.randint(0, width - 1)

        next = i
        match rot:
            case 0:
                position = random.randint(1, width - 1)

                landing_row_outleft  = self.ffnz(position - 2) + 1 if position > 2 else self.height
                landing_row_left  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_J(position, landing_row, next, rot=0)
            case 1:
                position = random.randint(2, width - 1)

                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_left1  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_left2  = self.ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft  = self.ffnz(position - 3) + 2 if position > 3 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_left1,
                    landing_row_left2,
                    landing_row_outright)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_J(position, landing_row - 1, next, rot=0)
            case 2:
                position = random.randint(0, width - 2)

                landing_row_outright1  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright2  = self.ffnz(position + 2) + 3 if position < self.width - 2 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright1,
                    landing_row_outright2)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_J(position, landing_row - 2, next, rot=0)
            case 3:
                position = random.randint(0, width - 3)

                landing_row_outright  = self.ffnz(position + 3) + 1 if position < self.width - 3 else self.height
                landing_row_right1  = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2  = self.ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright,
                    landing_row_right1,
                    landing_row_right2)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_J(position, landing_row, next, rot=0)

        return next

    def Test_J(self):
        """
        This is a test function for the J piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_J(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_T(self, position, landing_row, i, rot=0):
        """
        Place a T with pivot at the center:
        + rot = 0
            010
            0
        + rot = 1
            0
            10
            0
        + rot = 2
            0
            010
        + rot = 3
            0
            01
            0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        global substrate

        match rot:
            case 0:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 0, position] = i
            case 1:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 0, position] = i
                substrate[landing_row - 1, position + 1] = i
            case 2:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 2, position] = i
            case 3:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 0, position] = i

    def Update_T(self, i, rot=0):
        """
        Updates the substrate with a T piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        global substrate
        [width, height] = substrate.shape

        next = i
        match rot:
            case 0:
                position = random.randint(1, width - 2)

                landing_row_outleft  = self.ffnz(position - 2) + 2 if position > 2 else self.height
                landing_row_left  = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_right  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright  = self.ffnz(position + 2) + 2 if position < self.width - 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_T(position, landing_row - 1, next, rot=0)
            case 1:
                position = random.randint(0, width - 2)

                landing_row_outright  = self.ffnz(position + 2) + 2 if position < self.width - 2 else self.height
                landing_row_right  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outleft  = self.ffnz(position - 1) + 1 if position > 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_T(position, landing_row - 1, next, rot=0)
            case 2:
                position = random.randint(1, width - 2)

                landing_row_outright  = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height
                landing_row_right  = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_left  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft  = self.ffnz(position - 2) + 1 if position > 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_T(position, landing_row, next, rot=0)
            case 3:
                position = random.randint(1, width - 1)

                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_left  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft  = self.ffnz(position - 2) + 1 if position > 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_T(position, landing_row - 1, next, rot=0)

        return next

    def Test_T(self):
        """
        This is a test function for the J piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_T(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_S(self, position, landing_row, i, rot=0):
        """
        Place an S with pivot given as follows:
        + rot = 0 or 2
            00
        01
        + rot = 1 or 3
            0
            01
            0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        global substrate

        match rot:
            case 0 | 2:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 2, position + 1] = i
                substrate[landing_row - 2, position] = i
            case 1 | 3:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 0, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 2, position - 1] = i

    def Update_S(self, i, rot=0):
        """
        Updates the substrate with an S piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            numpy.ndarray: The updated substrate.
        """
        global substrate
        [width, height] = substrate.shape

        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, width - 2)

                landing_row_outleft  = self.ffnz(position - 2) + 1 if position > 2 else self.height
                landing_row_left  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outright1  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright2  = self.ffnz(position + 2) + 2 if position < self.width - 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright1,
                    landing_row_outright2)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_S(position, landing_row, next, rot=0)
            case 1 | 3:
                position = random.randint(1, width - 1)

                landing_row_outleft2  = self.ffnz(position - 2) + 2 if position > 2 else self.height
                landing_row_outleft1  = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_outright  = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft1,
                    landing_row_outleft2,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_S(position, landing_row - 1, next, rot=0)

        return next

    def Test_S(self):
        """
        This is a test function for the S piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_S(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def place_Z(self, position, landing_row, i, rot=0):
        """
        Place a Z with pivot given as follows:
        + rot = 0 or 2
        00
            10
        + rot = 1 or 3
            0
            01
            0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        global substrate

        match rot:
            case 0 | 2:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 1, position + 1] = i
                substrate[landing_row - 2, position - 1] = i
                substrate[landing_row - 2, position] = i
            case 1 | 3:
                substrate[landing_row - 1, position] = i
                substrate[landing_row - 2, position] = i
                substrate[landing_row - 1, position - 1] = i
                substrate[landing_row - 0, position - 1] = i

    def Update_Z(self, i, rot=0):
        """
        Updates the substrate with a Z piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            numpy.ndarray: The updated substrate.
        """
        global substrate
        [width, height] = substrate.shape

        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, width - 2)

                landing_row_outleft2  = self.ffnz(position - 2) + 2 if position > 2 else self.height
                landing_row_outleft1  = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position)
                landing_row_right  = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright  = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft2,
                    landing_row_outleft1,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 2:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_Z(position, landing_row, next, rot=0)
            case 1 | 3:
                position = random.randint(1, width - 1)

                landing_row_outleft  = self.ffnz(position - 2) + 1 if position > 2 else self.height
                landing_row_left  = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot  = self.ffnz(position) + 1
                landing_row_outright  = self.ffnz(position + 1) + 2 if position < self.width - 1 else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                place_Z(position, landing_row - 1, next, rot=0)

        return next

    def Test_Z(self):
        """
        This is a test function for the Z piece.
        """
        i = 0
        steps = 30
        global substrate
        for rot in range(4):
            print("Test rotation ", rot=0)
            # Reset the substrate
            substrate = np.zeros((height, width))
            while i < steps:
                i = Update_Z(i, rot=0)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")


# Example usage
tetris_simulator = Tetris_Ballistic(grid_size=(10, 20), steps=100)
tetris_simulator.simulate()


def Tetris_Ballistic_backup(steps):
    """
    This function simulates the Tetris Decomposition model on a substrate.

    Args:
        steps  (int): The steps to simulate.

    Return:
        None (print the final substrate)
    """
    global substrate
    [width, height] = substrate.shape

    # my_list = [0, 1, 4, 5, 6]
    my_list = [0, 1, 2, 3, 4, 5, 6]
    """
    + 0 :  the square;
    + 1 :  the line;
    + 2 :  the L;
    + 3 :  the J;
    + 4 :  the T;
    + 5 :  the S;
    + 6 :  the Z.
    """
    rotation_list = [0, 1, 2, 3]
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
                i = Update_O(i, choice[1])
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

        if i == -1:
            print("Game Over, reach the top")
            break

    print(self.substrate)


Tetris_Ballistic(30)
