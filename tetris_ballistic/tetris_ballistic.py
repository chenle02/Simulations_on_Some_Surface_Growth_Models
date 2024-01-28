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
import yaml
from RD_CLI import Envelop, interface_width


class Tetris_Ballistic:
    def __init__(self, width=16, height=32, steps=30, seed=None, config_file=None):
        """
        Initializes the Tetris_Ballistic simulation.

        Args:
            grid_size (tuple): The size of the grid (width, height).
            steps (int): The number of steps to simulate.
            seed (int, optional): The seed for random number generation. If None, randomness is not controlled.
            config_file (str, optional): The path to the YAML configuration file to be loaded (default None). The values set in the configuration file will override the default values.
        """
        if config_file is not None and self.load_config(config_file):
            # Configuration successfully loaded by load_config
            print(f"Configure file {config_file} loaded successfully.")
            self.steps = int(self.config_data['steps'])
            self.width = int(self.config_data['width'])
            self.height = int(self.config_data['height'])
            self.seed = self.config_data['seed']
        else:
            # Set default configuration if no file is provided or if load_config fails
            print("No configure file, uniform distribution is set.")
            self.config_data = {f"Key-{i + 1}": 1 for i in range(38)}
            self.steps = steps
            self.width = width
            self.height = height
            if seed is not None:
                random.seed(seed)
                np.random.seed(seed)

        self.substrate = np.zeros((self.height, self.width))
        self.PieceMap = [[-1, -1] for _ in range(19)]
        self.PieceMap[0] = [0, 0]
        self.PieceMap[1] = [1, 0]
        self.PieceMap[2] = [1, 1]
        self.PieceMap[3] = [2, 0]
        self.PieceMap[4] = [2, 1]
        self.PieceMap[5] = [2, 2]
        self.PieceMap[6] = [2, 3]
        self.PieceMap[7] = [3, 0]
        self.PieceMap[8] = [3, 1]
        self.PieceMap[9] = [3, 2]
        self.PieceMap[10] = [3, 3]
        self.PieceMap[11] = [4, 0]
        self.PieceMap[12] = [4, 1]
        self.PieceMap[13] = [4, 2]
        self.PieceMap[14] = [4, 3]
        self.PieceMap[15] = [5, 0]
        self.PieceMap[16] = [5, 1]
        self.PieceMap[17] = [6, 0]
        self.PieceMap[18] = [6, 1]

    def load_config(self, filename):
        """
        Loads configuration data from a specified YAML file into the
        `config_data` attribute.

            This method attempts to open and read the contents of the YAML file
            specified by `filename`. It then validates whether the file
            contains exactly 38 entries. If the file does not meet this
            requirement, a ValueError is raised. In case of a successful load,
            the configuration data is stored in the `config_data` attribute of
            the class instance.

        Parameters:
        filename (str): The path to the YAML configuration file to be loaded.

        Returns:
        bool: True if the file is successfully loaded and contains the correct number of entries, False otherwise.

        Raises:
        yaml.YAMLError: If there is an error parsing the YAML file.

        """
        try:
            with open(filename, 'r') as file:
                raw_data = yaml.safe_load(file)
                if isinstance(raw_data, dict):
                    self.config_data = {k: float(v) for k, v in raw_data.items()}
                    print(f"Loaded: {self.config_data}")
                    return True
                else:
                    print(f"Fail to load from {filename}")
                    return False
        except FileNotFoundError:
            print(f"File not found: {filename}")
            return False
        except ValueError as ve:
            print(f"Value error in configuration file: {ve}")
            return False
        except yaml.YAMLError as exc:
            print(f"Error in configuration file: {exc}")
            return False

    def reset(self):
        """
        Resets the substrate to all zeros.
        """
        self.substrate = np.zeros((self.height, self.width))
        print("Substrate has been reset to all zeros.")

    def Sample_Tetris(self):
        """
        Samples a Tetris piece given the probability distribution specified in the configuration file.

        Returns:
            numpy.ndarray: A 2-element array:
            the first element is the piece type (0-6);
            the second element is the orientation (0-3).

        """
        # Normalize the vector
        probabilities = np.array([self.config_data[f"Key-{i+1}"] for i in range(38)])

        # Normalize the vector
        normalized_probabilities = probabilities / np.sum(probabilities)

        # Use normalized probabilities for sampling
        sample = np.random.choice(38, size=1, p=normalized_probabilities)

        print(f"Sampled: {sample}")
        return sample

    def Test_WhichPiece(self):
        print(self.PieceMap[0])
        print(self.PieceMap[1])
        print(self.PieceMap[2])
        print(self.PieceMap[3])
        print(self.PieceMap[4])
        print(self.PieceMap[5])
        print(self.PieceMap[6])
        print(self.PieceMap[7])
        print(self.PieceMap[8])
        print(self.PieceMap[9])
        print(self.PieceMap[10])
        print(self.PieceMap[11])
        print(self.PieceMap[12])
        print(self.PieceMap[13])
        print(self.PieceMap[14])
        print(self.PieceMap[15])
        print(self.PieceMap[16])
        print(self.PieceMap[17])
        print(self.PieceMap[18])

    def Tetris_Choice(self):
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
        # Check if the column index is within the valid range
        if column < 0 or column >= self.width:
            print("Column index is out of bounds")
            raise ValueError("Column index is out of bounds")

        i = 0
        flag = self.height
        while (flag == self.height) and (i < self.height):
            if self.substrate[i, column] == 0:
                i = i + 1
            else:
                flag = i

        return flag

    def Place_O(self, position, landing_row, i):
        """
        Place a square with pivot at the bottom left corner on the :

           - 00
           - 10

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

    def Update_O(self, i, sticky=True):
        """
        Updates the substrate with a square piece.

           - 00
           - 10

        Args:
            i (int): The step number.
            sticky (bool): Whether the piece is sticky or not.

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 2)

        next = i

        landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height
        landing_row_pivot = self.ffnz(position)
        landing_row_right = self.ffnz(position + 1) if position < self.width - 1 else self.height
        landing_row_outright = self.ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

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
        self.Place_O(position, landing_row, next)
        # print(self.substrate)
        # input("")

        return next

    def Test_O(self):
        """
        This is a test function for the square piece.
        """
        for rot in range(4):
            print("O piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_O(i, sticky=False)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_I(self, position, landing_row, i, rot=0):
        """
        Place a square with pivot at the bottom left corner on the substrate:
           - 1000
        or
           - 0
           - 0
           - 0
           - 0
           - 1
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

    def Update_I(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a line piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

               + rot = 0
                  - 1000
               + rot = 1
                  - 0
                  - 0
                  - 0
                  - 1
               + rot = 2
                  - 0001
               + rot = 3
                  - 1
                  - 0
                  - 0
                  - 0

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i

        match rot:
            case 0 | 2:
                position = random.randint(0, self.width - 4)

                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_right1 = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2 = self.ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_right3 = self.ffnz(position + 3) if position < self.width - 3 else self.height
                landing_row_outright = self.ffnz(position + 4) + 1 if position < self.width - 4 and sticky else self.height

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
                self.Place_I(position, landing_row, next, rot)

            case 1 | 3:
                position = random.randint(0, self.width - 1)

                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 4:
                    return -1

                next = i + 1
                self.Place_I(position, landing_row, next, rot)

        return next

    def Test_I(self):
        """
        This is a test function for the Line piece.
        """
        for rot in range(4):
            print("I piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_I(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_L(self, position, landing_row, i, rot=0):
        """
        Place an L with pivot at the corner.

        + rot = 0
           - 0
           - 0
           - 10
        + rot = 1
           - XX0
           - 001
        + rot = 2
           - 10
           - 0
           - 0
        + rot = 3
           - 100
           - 0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        match rot:
            case 0:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 3, position] = i
                self.substrate[landing_row - 1, position + 1] = i
            case 1:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 1, position - 2] = i
                self.substrate[landing_row - 2, position] = i
            case 2:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row + 0, position] = i
                self.substrate[landing_row + 1, position] = i
            case 3:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row - 1, position + 2] = i

    def Update_L(self, i, rot=0, sticky=True):
        """
        Updates the substrate with an L piece.

        + rot = 0
           - 0
           - 0
           - 10
        + rot = 1
           - XX0
           - 001
        + rot = 2
           - 10
           - 0
           - 0
        + rot = 3
           - 100
           - 0

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0:
                position = random.randint(0, self.width - 2)

                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 0 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_right = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright = self.ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

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
                self.Place_L(position, landing_row, next, rot)
            case 1:
                position = random.randint(2, self.width - 1)

                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_left1 = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_left2 = self.ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft = self.ffnz(position - 3) + 1 if position > 3 and sticky else self.height

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
                self.Place_L(position, landing_row, next, rot)
            case 2:
                position = random.randint(1, self.width - 1)

                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outleft1 = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_outleft2 = self.ffnz(position - 2) + 3 if position > 2 and sticky else self.height

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
                self.Place_L(position, landing_row - 2, next, rot)
            case 3:
                position = random.randint(0, self.width - 3)

                landing_row_outright = self.ffnz(position + 3) + 2 if position < self.width - 3 and sticky else self.height
                landing_row_right1 = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_right2 = self.ffnz(position + 2) + 1 if position < self.width - 2 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height

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
                self.Place_L(position, landing_row - 1, next, rot)

        return next

    def Test_L(self):
        """
        This is a test function for the L piece.
        """
        for rot in range(4):
            print("L piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_L(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_J(self, position, landing_row, i, rot=0):
        """
        Place a J with pivot at the corner.

        + rot = 0
           - X0
           - X0
           - 01
        + rot = 1
           - 001
           - XX0
        + rot = 2
           - 10
           - 0
           - 0
        + rot = 3
           - 0
           - 100

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        match rot:
            case 0:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 3, position] = i
                self.substrate[landing_row - 1, position - 1] = i
            case 1:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 1, position - 2] = i
                self.substrate[landing_row - 0, position] = i
            case 2:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row + 0, position] = i
                self.substrate[landing_row + 1, position] = i
            case 3:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row - 1, position + 2] = i

    def Update_J(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a J piece.

        + rot = 0
           - X0
           - X0
           - 01
        + rot = 1
           - 001
           - XX0
        + rot = 2
           - 10
           - 0
           - 0
        + rot = 3
           - 0
           - 100

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 1)

        next = i
        match rot:
            case 0:
                position = random.randint(1, self.width - 1)

                landing_row_outleft = self.ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

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
                self.Place_J(position, landing_row, next, rot)
            case 1:
                position = random.randint(2, self.width - 1)

                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_left1 = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_left2 = self.ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft = self.ffnz(position - 3) + 2 if position > 3 and sticky else self.height

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
                self.Place_J(position, landing_row - 1, next, rot)
            case 2:
                position = random.randint(0, self.width - 2)

                landing_row_outright1 = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_outright2 = self.ffnz(position + 2) + 3 if position < self.width - 2 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height

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
                self.Place_J(position, landing_row - 2, next, rot)
            case 3:
                position = random.randint(0, self.width - 3)

                landing_row_outright = self.ffnz(position + 3) + 1 if position < self.width - 3 and sticky else self.height
                landing_row_right1 = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2 = self.ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height

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
                self.Place_J(position, landing_row, next, rot)

        return next

    def Test_J(self):
        """
        This is a test function for the J piece.
        """
        for rot in range(4):
            print("J piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_J(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_T(self, position, landing_row, i, rot=0):
        """
        Place a T with pivot at the center:

        + rot = 0
           - 010
           - X0X
        + rot = 1
           - 0
           - 10
           - 0
        + rot = 2
           - X0
           - 010
        + rot = 3
           - 0
           - 01
           - 0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        match rot:
            case 0:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 0, position] = i
            case 1:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 0, position] = i
                self.substrate[landing_row - 1, position + 1] = i
            case 2:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 2, position] = i
            case 3:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 0, position] = i

    def Update_T(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a T piece.

        + rot = 0
           - 010
           - X0X
        + rot = 1
           - 0
           - 10
           - 0
        + rot = 2
           - X0
           - 010
        + rot = 3
           - 0
           - 01
           - 0

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0:
                position = random.randint(1, self.width - 2)

                landing_row_outleft = self.ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_left = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_right = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright = self.ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height

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
                self.Place_T(position, landing_row - 1, next, rot)
            case 1:
                position = random.randint(0, self.width - 2)

                landing_row_outright = self.ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height
                landing_row_right = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outleft = self.ffnz(position - 1) + 1 if position > 1 and sticky else self.height

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
                self.Place_T(position, landing_row - 1, next, rot)
            case 2:
                position = random.randint(1, self.width - 2)

                landing_row_outright = self.ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height
                landing_row_right = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_left = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft = self.ffnz(position - 2) + 1 if position > 2 and sticky else self.height

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
                self.Place_T(position, landing_row, next, rot)
            case 3:
                position = random.randint(1, self.width - 1)

                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_left = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft = self.ffnz(position - 2) + 1 if position > 2 and sticky else self.height

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
                self.Place_T(position, landing_row - 1, next, rot)

        return next

    def Test_T(self):
        """
        This is a test function for the T piece.
        """
        for rot in range(4):
            print("T piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_T(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_S(self, position, landing_row, i, rot=0):
        """
        Place an S with pivot given as follows:

        + rot = 0 or 2
           - X00
           - 01
        + rot = 1 or 3
           - 0
           - 01
           - X0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        match rot:
            case 0 | 2:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 2, position + 1] = i
                self.substrate[landing_row - 2, position] = i
            case 1 | 3:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 0, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 2, position - 1] = i

    def Update_S(self, i, rot=0, sticky=True):
        """
        Updates the substrate with an S piece.

        + rot = 0 or 2
           - X00
           - 01
        + rot = 1 or 3
           - 0
           - 01
           - X0

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, self.width - 2)

                landing_row_outleft = self.ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outright1 = self.ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright2 = self.ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height

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
                self.Place_S(position, landing_row, next, rot)
            case 1 | 3:
                position = random.randint(1, self.width - 1)

                landing_row_outleft2 = self.ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_outleft1 = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_outright = self.ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

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
                self.Place_S(position, landing_row - 1, next, rot)

        return next

    def Test_S(self):
        """
        This is a test function for the S piece.
        """
        for rot in range(4):
            print("S piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_S(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Place_Z(self, position, landing_row, i, rot=0):
        """
        Place a Z with pivot given as follows:

        + rot = 0 or 2
           - 00
           - X10
        + rot = 1 or 3
           - X0
           - 01
           - 0

        Args:
            position (int): The position or column of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.
            rot (int): The rotation of the piece as described above.

        Return:
            None
        """
        match rot:
            case 0 | 2:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 1, position + 1] = i
                self.substrate[landing_row - 2, position - 1] = i
                self.substrate[landing_row - 2, position] = i
            case 1 | 3:
                self.substrate[landing_row - 1, position] = i
                self.substrate[landing_row - 2, position] = i
                self.substrate[landing_row - 1, position - 1] = i
                self.substrate[landing_row - 0, position - 1] = i

    def Update_Z(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a Z piece.

        + rot = 0 or 2
           - 00
           - X10
        + rot = 1 or 3
           - X0
           - 01
           - 0

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece.

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, self.width - 2)

                landing_row_outleft2 = self.ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_outleft1 = self.ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self.ffnz(position)
                landing_row_right = self.ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright = self.ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

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
                self.Place_Z(position, landing_row, next, rot)
            case 1 | 3:
                position = random.randint(1, self.width - 1)

                landing_row_outleft = self.ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self.ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self.ffnz(position) + 1
                landing_row_outright = self.ffnz(position + 1) + 2 if position < self.width - 1 and sticky else self.height

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
                self.Place_Z(position, landing_row - 1, next, rot)

        return next

    def Test_Z(self):
        """
        This is a test function for the Z piece.
        """
        for rot in range(4):
            print("Z piece, Test rotation ", rot)
            self.reset()
            i = 0
            while i < self.steps:
                i = self.Update_Z(i, rot)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            print(self.substrate)
            input("")

    def Test_All(self):
        """
        This function simulates the Tetris Decomposition model on a substrate.

        Args:
            steps  (int): The steps to simulate.

        Return:
            None (print the final substrate)
        """
        # my_list = [0, 1, 4, 5, 6]
        print("Test all pieces now ...")
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
        self.reset()
        i = 0
        while i < self.steps:
            choice = [random.choice(my_list), random.choice(rotation_list)]
            match choice[0]:
                case 0: i = self.Update_O(i)
                case 1: i = self.Update_I(i, choice[1])
                case 2: i = self.Update_L(i, choice[1])
                case 3: i = self.Update_J(i, choice[1])
                case 4: i = self.Update_T(i, choice[1])
                case 5: i = self.Update_S(i, choice[1])
                case 6: i = self.Update_Z(i, choice[1])
                case _: print("Wrong Choice of the Pieces")

            if i == -1:
                print("Game Over, reach the top")
                break

        print(self.substrate)

        def WhichPiece(self, id):
            """
            Determines the board position of a chess piece based on its unique identifier.

            This method takes an integer 'id' as input, representing the unique identifier of a chess piece.
            It returns the position of the piece on the chessboard if the identifier is valid (between 0 and 37, inclusive).
            If the identifier is not valid, it prints an error message and returns a list containing [-1, -1].

            Args:
                id (int): A unique identifier for a chess piece, expected to be in the range of 0 to 37.

            Returns:
                list: A two-element list representing the position of the piece on the chessboard. Each element is an integer.
                    If the id is invalid, it returns [-1, -1].

            Note:
                The chessboard positions are mapped in the `PieceMap` attribute of the class. This method looks up the
                position in `PieceMap` based on the provided id.
            """
            if id < 38 and id >= 0:
                return self.PieceMap[id]
            else:
                print("Wrong ID")
                return [-1, -1]


# Example usage
# tetris_simulator = Tetris_Ballistic(width=10, height=20, steps=1000, seed=42)
# tetris_simulator = Tetris_Ballistic(width=10, height=20, steps=1000, seed=42)
# tetris_simulator.Test_WhichPiece()

# tetris_simulator.Test_All()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator = Tetris_Ballistic(config_file="config.yaml")
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Sample_Tetris()
# tetris_simulator.Test_O()
# tetris_simulator.Test_I()
# tetris_simulator.Test_L()
# tetris_simulator.Test_J()
# tetris_simulator.Test_T()
# tetris_simulator.Test_S()
# tetris_simulator.Test_Z()
# tetris_simulator.Test_All()
