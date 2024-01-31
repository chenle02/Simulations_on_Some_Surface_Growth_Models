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
import re
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import imageio
import os
import joblib
from functools import partial
# from RD_CLI import Envelop, interface_width
np.set_printoptions(threshold=np.inf)  # Make sure that print() displays the entire array


class Tetris_Ballistic:
    """
    Tetris_Ballistic class
    ----------------------


    The class can be initialized in two ways:

    - using a configuration file
    - using the arguments of the constructor

    If config_file is not None, the configuration data is loaded from the
    specified YAML file. Otherwise, the default configuration is used. By
    default, all pieces are sticky.

    Args:
        width (int): The width of the game grid. Default is 16.
        height (int): The height of the game grid. Default is 32.
        steps (int): The number of steps to simulate. Default is 30.
        seed (int, optional): The seed for random number generation. If None, randomness is not controlled.
        config_file (str, optional): The path to a YAML configuration file to be loaded. If None, default configuration is used.

    Example:
        >>> TB1 = Tetris_Ballistic(width=10, height=20, steps=100, seed=42)
        >>> TB2 = Tetris_Ballistic(config_file="config.yaml")

        The config.yaml file takes the following form:

        .. code-block:: yaml
            :caption: **Example YAML configuration file**

            width: 10
            height: 42
            steps: 90
            seed: 42
            Piece-0:  [4,  1]
            Piece-1:  [4,  1]
            Piece-2:  [2,  1]
            Piece-3:  [11, 1]
            Piece-4:  [1,  1]
            Piece-5:  [1,  1]
            Piece-6:  [1,  1]
            Piece-7:  [11, 1]
            Piece-8:  [1,  1]
            Piece-9:  [1,  1]
            Piece-10: [1,  1]
            Piece-11: [11, 1]
            Piece-12: [1,  1]
            Piece-13: [2,  1]
            Piece-14: [1,  1]
            Piece-15: [11, 1]
            Piece-16: [1,  1]
            Piece-17: [1,  1]
            Piece-18: [1,  1]
            Piece-19: [0,  0]
    """

    def __init__(self,
                 width=16,
                 height=32,
                 steps=30,
                 seed=None,
                 config_file=None):
        self.set_seed(seed)  # Set initial seed

        if config_file is not None and self.load_config(config_file):
            # Configuration successfully loaded by load_config
            print(f"Configure file {config_file} loaded successfully.")
            self.steps = int(self.config_data['steps'])
            self.width = int(self.config_data['width'])
            self.height = int(self.config_data['height'])
            self.seed = self.config_data['seed']
            self.set_seed(self.config_data.get('seed', None))  # Set seed from config if available
        else:
            # Set default configuration if no file is provided or if load_config fails
            print("No configure file, uniform distribution is set.")
            self.config_data = {f"Piece-{i}": [0, 1] for i in range(19)}
            self.config_data["Piece-19"] = [0, 1]  # 1x1 piece
            self.config_data["steps"] = steps
            self.steps = steps
            self.config_data["width"] = width
            self.width = width
            self.config_data["height"] = height
            self.height = height
            self.config_data["seed"] = seed
            self.seed = seed

        self.FinalSteps = self.steps  # This is the final step number
        self.substrate = np.zeros((self.height, self.width))
        self.PieceMap = [[-1, -1] for _ in range(20)]
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
        self.PieceMap[19] = [7, 0]  # 1x1 piece

        self.HeightDynamics = np.zeros((self.steps, self.width))
        self.Fluctuation = np.zeros((self.steps))
        self.AvergeHeight = np.zeros((self.steps))
        self.log_time_slopes = None
        self.UpdateCall = [
            _create_partial(self.Update_O, rot=0, sticky=False),  _create_partial(self.Update_O, rot=0, sticky=True),    # 0
            _create_partial(self.Update_I, rot=0, sticky=False),  _create_partial(self.Update_I, rot=0, sticky=True),    # 1
            _create_partial(self.Update_I, rot=1, sticky=False),  _create_partial(self.Update_I, rot=1, sticky=True),    # 2
            _create_partial(self.Update_L, rot=0, sticky=False),  _create_partial(self.Update_L, rot=0, sticky=True),    # 3
            _create_partial(self.Update_L, rot=1, sticky=False),  _create_partial(self.Update_L, rot=1, sticky=True),    # 4
            _create_partial(self.Update_L, rot=2, sticky=False),  _create_partial(self.Update_L, rot=2, sticky=True),    # 5
            _create_partial(self.Update_L, rot=3, sticky=False),  _create_partial(self.Update_L, rot=3, sticky=True),    # 6
            _create_partial(self.Update_J, rot=0, sticky=False),  _create_partial(self.Update_J, rot=0, sticky=True),    # 7
            _create_partial(self.Update_J, rot=1, sticky=False),  _create_partial(self.Update_J, rot=1, sticky=True),    # 8
            _create_partial(self.Update_J, rot=2, sticky=False),  _create_partial(self.Update_J, rot=2, sticky=True),    # 9
            _create_partial(self.Update_J, rot=3, sticky=False),  _create_partial(self.Update_J, rot=3, sticky=True),    # 10
            _create_partial(self.Update_T, rot=0, sticky=False),  _create_partial(self.Update_T, rot=0, sticky=True),    # 11
            _create_partial(self.Update_T, rot=1, sticky=False),  _create_partial(self.Update_T, rot=1, sticky=True),    # 12
            _create_partial(self.Update_T, rot=2, sticky=False),  _create_partial(self.Update_T, rot=2, sticky=True),    # 13
            _create_partial(self.Update_T, rot=3, sticky=False),  _create_partial(self.Update_T, rot=3, sticky=True),    # 14
            _create_partial(self.Update_S, rot=0, sticky=False),  _create_partial(self.Update_S, rot=0, sticky=True),    # 15
            _create_partial(self.Update_S, rot=1, sticky=False),  _create_partial(self.Update_S, rot=1, sticky=True),    # 16
            _create_partial(self.Update_Z, rot=0, sticky=False),  _create_partial(self.Update_Z, rot=0, sticky=True),    # 17
            _create_partial(self.Update_Z, rot=1, sticky=False),  _create_partial(self.Update_Z, rot=1, sticky=True),    # 18
            _create_partial(self.Update_1x1, rot=0, sticky=False), _create_partial(self.Update_1x1, rot=0, sticky=True)  # 19
        ]

    def set_seed(self, seed):
        """
        Set the seed for random number generation
        -----------------------------------------

        This method sets the seed for both the built-in random module and
        numpy's random module. It ensures that the seed is either a valid
        integer or None. If None is provided, the seed is set to a random value
        based on system time or another source of randomness.

        :param seed: Seed value to set for random number generation. If None, a random seed is used.
        :type seed: int or None

        :raises ValueError: If the seed is not an integer or None.
        """
        if seed is not None:
            try:
                seed = int(seed)
            except ValueError:
                raise ValueError("Seed must be an integer or None")

        random.seed(seed)
        np.random.seed(seed)

    def load_config(self, filename):
        """
        Load config file manually
        --------------------------

        Loads configuration data from a specified YAML file into the
        `config_data` attribute.

        This method opens and reads the contents of the YAML file specified by
        `filename`. It expects the file to contain a mix of single-value
        entries and lists (specifically for 'Piece-x' entries) as follows:

        .. code-block:: yaml
           :caption: **Example YAML configuration file**

           width: 10
           height: 42
           steps: 90
           seed: 42
           Piece-0:  [4,  1]
           Piece-1:  [4,  1]
           Piece-2:  [2,  1]
           Piece-3:  [11, 1]
           Piece-4:  [1,  1]
           Piece-5:  [1,  1]
           Piece-6:  [1,  1]
           Piece-7:  [11, 1]
           Piece-8:  [1,  1]
           Piece-9:  [1,  1]
           Piece-10: [1,  1]
           Piece-11: [11, 1]
           Piece-12: [1,  1]
           Piece-13: [2,  1]
           Piece-14: [1,  1]
           Piece-15: [11, 1]
           Piece-16: [1,  1]
           Piece-17: [1,  1]
           Piece-18: [1,  1]
           Piece-19: [0,  0]

        The method stores these entries in the `config_data` attribute of the
        class instance. Single-value entries are converted to floats, while
        'Piece-x' entries are stored as lists of two floats, among which the
        first entry refers to the frequency of the non-sticky piece and the
        second entry refers to the frequency of the sticky piece.

        If the file does not contain exactly 24 entries, a ValueError is
        raised.

        Args:
            filename (str): The path to the YAML configuration file to be loaded.

        Returns:
            bool: True if the file is successfully loaded and contains the correct number of entries, False otherwise.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            ValueError: If the file does not contain exactly 23 entries.
            yaml.YAMLError: If there is an error parsing the YAML file.
        """
        try:
            with open(filename, 'r') as file:
                raw_data = yaml.safe_load(file)

                if isinstance(raw_data, dict):
                    # Processing the data
                    self.config_data = {}
                    for k, v in raw_data.items():
                        if k.startswith("Piece-"):
                            self.config_data[k] = v  # Store list as-is for pieces
                        else:
                            self.config_data[k] = float(v)  # Convert other values to float

                    # Check for the total number of entries
                    if len(self.config_data) != 24:
                        raise ValueError("Incorrect number of entries in the configuration file.")

                    print(f"Loaded: {self.config_data}")
                    return True
                else:
                    print(f"Failed to load from {filename}")
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

    def save_config(self, filename):
        """
        Save configure file to a YAML file
        ----------------------------------

        This method writes the contents of the `config_data` attribute into a
        YAML file specified by `filename`. The file will contain both
        single-value entries and lists, similar to the expected format in the
        `load_config` method.

        Args:
            filename (str): The path to the YAML configuration file to be saved.

        Returns:
            None
        """
        def _extract_number(key):
            """
            Extracts the numeric part from the key.
            """
            if key.startswith("Piece-"):
                match = re.search(r'(\d+)$', key)
                return int(match.group()) if match else 0
            else:
                return float('inf')

        def _represent_none(dumper, _):
            """
            Custom representer for formatting None in YAML as 'None'.
            """
            # return dumper.represent_scalar('tag:yaml.org,2002:null', 'None')
            return dumper.represent_scalar('tag:yaml.org,2002:str', 'None')

        def _represent_list(dumper, data):
            """
            Custom representer for formatting lists in YAML.
            """
            return dumper.represent_sequence(u'tag:yaml.org,2002:seq', data, flow_style=True)

        try:
            with open(filename, 'w') as file:
                # Add custom list representer to the YAML dumper
                yaml.add_representer(type(None), _represent_none)
                yaml.add_representer(list, _represent_list)

                # Handle None values correctly
                formatted_data = {k: v if v is not None else None for k, v in self.config_data.items()}

                # Separate the 'Piece-' entries from the rest
                piece_data = {k: v for k, v in formatted_data.items() if k.startswith("Piece-")}
                other_data = {k: v for k, v in formatted_data.items() if not k.startswith("Piece-")}

                # Sort the 'Piece-' entries by their numeric value
                sorted_piece_data = dict(sorted(piece_data.items(), key=lambda item: _extract_number(item[0])))

                # Combine the sorted data
                combined_data = {**other_data, **sorted_piece_data}

                yaml.dump(combined_data, file, sort_keys=False, default_flow_style=False)
                print(f"Configuration saved to {filename}")

        except Exception as e:
            print(f"Failed to save configuration: {e}")

    def reset(self):
        """
        Reset the status of the simulation
        ----------------------------------

        Reset the following attributes:

        - self.substrate
        - self.FinalSteps
        - self.HeightDynamics
        - self.Fluctuation
        - self.AvergeHeight
        - self.log_time_slopes

        Returns:
            None
        """
        self.substrate = np.zeros((self.height, self.width))
        self.FinalSteps = self.steps
        self.HeightDynamics = np.zeros((self.steps, self.width))
        self.Fluctuation = np.zeros((self.steps))
        self.AvergeHeight = np.zeros((self.steps))
        self.log_time_slopes = None
        print("Substrate along with all statistics have been reset to all zeros.")

    def Sample_Tetris(self, verbose=False):
        """
        Sampling the Tetris piece according to the configuration file
        -------------------------------------------------------------

        Samples a Tetris piece given the probability distribution specified in
        the configuration file.

        There are 7 types Tetris pieces (type_id):

        + 0 :  the square;
        + 1 :  the line;
        + 2 :  the L;
        + 3 :  the J;
        + 4 :  the T;
        + 5 :  the S;
        + 6 :  the Z.

        We add the 1x1 piece as the 8th piece.

        + 7 :  the 1x1.

        There are 4 orientations for each piece (rot):

        - 0 is the original orientation;
        - 1 is the 90 degree rotation;
        - 2 is the 180 degree rotation;
        - 3 is the 270 degree rotation.

        There are 19 pieces in total (piece_id) given below:

        ================  ===============================
        Piece_id          (type_id, rot)
        ================  ===============================
        0                 (0, 0) (0, 1) (0, 2) (0, 3)
        1                 (1, 0) (1, 2)
        2                 (1, 1) (1, 3)
        3                 (2, 0)
        4                 (2, 1)
        5                 (2, 2)
        6                 (2, 3)
        7                 (3, 0)
        8                 (3, 1)
        9                 (3, 2)
        10                (3, 3)
        11                (4, 0)
        12                (4, 1)
        13                (4, 2)
        14                (4, 3)
        15                (5, 0) (5, 2)
        16                (5, 1) (5, 3)
        17                (6, 0) (6, 2)
        18                (6, 1) (6, 3)
        19                (7, 0) (7, 1) (7, 2) (7, 3)
        ================  ===============================


        Args:
            verbose (bool): Whether to print the sampled piece or not. (Default: False)
        Returns:
            Update (callable): The function to be called to update the substrate.
            Piece_id (int): The Id of the piece (0-19).
            Type_id (int): The ID of the sampled piece (0-6).
            rot (int): rotation of the sampled piece (0-3).
            Sticky (bool): Whether the sampled piece is sticky or not.
        """
        # Normalize the vector
        probabilities = np.array([self.config_data[f"Piece-{i}"] for i in range(20)])

        # Flatten the matrix to a 1D array for sampling
        flattened_probabilities = probabilities.flatten()

        # Normalize the flattened vector
        normalized_probabilities = flattened_probabilities / np.sum(flattened_probabilities)

        # Use normalized probabilities for sampling
        sample_index = np.random.choice(40, p=normalized_probabilities)

        # Convert flat index back to 2D index
        Piece_id = sample_index // 2  # integer division to get row index
        column = sample_index % 2  # modulo to get column index
        if column == 0:
            Sticky = False
        else:
            Sticky = True

        Type_id, rot = self.PieceMap[Piece_id]

        if verbose:
            print(f"Sampled (Type_id, rot, Sticky, Update_Function): ({Type_id}, {rot}, {Sticky}), {self.UpdateCall[sample_index].__name__}")

        Update = self.UpdateCall[sample_index]

        return Update, Type_id, rot, Sticky

    def Simulate(self):
        """
        Start the simulation
        --------------------

        Return:
            None
        """
        self.reset()
        i = 0
        while i < self.steps:
            Update, *_ = self.Sample_Tetris()
            i = Update(i)
            if i == -1:
                print("Game Over, reach the top")
                break
        self.ComputeSlope()
        self.PrintStatus(brief=True)

    def _ffnz(self, column):
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

    def _Place_O(self, position, landing_row, i):
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

    def Update_O(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a square piece.

           - 00
           - 10

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece. (No use, just be consistent with the others)
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 2)

        next = i

        landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height
        landing_row_pivot = self._ffnz(position)
        landing_row_right = self._ffnz(position + 1) if position < self.width - 1 else self.height
        landing_row_outright = self._ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

        # Find minimum landing row
        landing_row = min(
            landing_row_outleft,
            landing_row_pivot,
            landing_row_right,
            landing_row_outright)

        if landing_row < 2:
            self.FinalSteps = i
            return -1

        # Place square based on the minimum landing row
        next = i + 1
        self._Place_O(position, landing_row, next)
        # print(self.substrate)
        # input("")
        self._UpdateStatus(i)

        return next

    def _Place_I(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

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

                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_right1 = self._ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2 = self._ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_right3 = self._ffnz(position + 3) if position < self.width - 3 else self.height
                landing_row_outright = self._ffnz(position + 4) + 1 if position < self.width - 4 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right1,
                    landing_row_right2,
                    landing_row_right3,
                    landing_row_outright)

                if landing_row < 1:
                    self.FinalSteps = i
                    return -1

                next = i + 1
                self._Place_I(position, landing_row, next, rot)

            case 1 | 3:
                position = random.randint(0, self.width - 1)

                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 4:
                    self.FinalSteps = i
                    return -1

                next = i + 1
                self._Place_I(position, landing_row, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_L(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0:
                position = random.randint(0, self.width - 2)

                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 0 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_right = self._ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright = self._ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_L(position, landing_row, next, rot)
            case 1:
                position = random.randint(2, self.width - 1)

                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_left1 = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_left2 = self._ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft = self._ffnz(position - 3) + 1 if position > 3 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_left1,
                    landing_row_left2,
                    landing_row_outright)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_L(position, landing_row, next, rot)
            case 2:
                position = random.randint(1, self.width - 1)

                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outleft1 = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height
                landing_row_outleft2 = self._ffnz(position - 2) + 3 if position > 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft1,
                    landing_row_outleft2,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_L(position, landing_row - 2, next, rot)
            case 3:
                position = random.randint(0, self.width - 3)

                landing_row_outright = self._ffnz(position + 3) + 2 if position < self.width - 3 and sticky else self.height
                landing_row_right1 = self._ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_right2 = self._ffnz(position + 2) + 1 if position < self.width - 2 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright,
                    landing_row_right1,
                    landing_row_right2)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_L(position, landing_row - 1, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_J(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 1)

        next = i
        match rot:
            case 0:
                position = random.randint(1, self.width - 1)

                landing_row_outleft = self._ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_J(position, landing_row, next, rot)
            case 1:
                position = random.randint(2, self.width - 1)

                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_left1 = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_left2 = self._ffnz(position - 2) if position > 2 else self.height
                landing_row_outleft = self._ffnz(position - 3) + 2 if position > 3 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_left1,
                    landing_row_left2,
                    landing_row_outright)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_J(position, landing_row - 1, next, rot)
            case 2:
                position = random.randint(0, self.width - 2)

                landing_row_outright1 = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_outright2 = self._ffnz(position + 2) + 3 if position < self.width - 2 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright1,
                    landing_row_outright2)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_J(position, landing_row - 2, next, rot)
            case 3:
                position = random.randint(0, self.width - 3)

                landing_row_outright = self._ffnz(position + 3) + 1 if position < self.width - 3 and sticky else self.height
                landing_row_right1 = self._ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_right2 = self._ffnz(position + 2) if position < self.width - 2 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_outright,
                    landing_row_right1,
                    landing_row_right2)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_J(position, landing_row, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_T(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0:
                position = random.randint(1, self.width - 2)

                landing_row_outleft = self._ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_left = self._ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_right = self._ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright = self._ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_T(position, landing_row - 1, next, rot)
            case 1:
                position = random.randint(0, self.width - 2)

                landing_row_outright = self._ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height
                landing_row_right = self._ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_T(position, landing_row - 1, next, rot)
            case 2:
                position = random.randint(1, self.width - 2)

                landing_row_outright = self._ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height
                landing_row_right = self._ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_left = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft = self._ffnz(position - 2) + 1 if position > 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_T(position, landing_row, next, rot)
            case 3:
                position = random.randint(1, self.width - 1)

                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_left = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_outleft = self._ffnz(position - 2) + 1 if position > 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_T(position, landing_row - 1, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_S(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, self.width - 2)

                landing_row_outleft = self._ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outright1 = self._ffnz(position + 1) + 1 if position < self.width - 1 else self.height
                landing_row_outright2 = self._ffnz(position + 2) + 2 if position < self.width - 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright1,
                    landing_row_outright2)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_S(position, landing_row, next, rot)
            case 1 | 3:
                position = random.randint(1, self.width - 1)

                landing_row_outleft2 = self._ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_outleft1 = self._ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft1,
                    landing_row_outleft2,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_S(position, landing_row - 1, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_Z(self, position, landing_row, i, rot=0):
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
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        next = i
        match rot:
            case 0 | 2:
                position = random.randint(1, self.width - 2)

                landing_row_outleft2 = self._ffnz(position - 2) + 2 if position > 2 and sticky else self.height
                landing_row_outleft1 = self._ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_pivot = self._ffnz(position)
                landing_row_right = self._ffnz(position + 1) if position < self.width - 1 else self.height
                landing_row_outright = self._ffnz(position + 2) + 1 if position < self.width - 2 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft2,
                    landing_row_outleft1,
                    landing_row_pivot,
                    landing_row_right,
                    landing_row_outright)

                if landing_row < 2:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_Z(position, landing_row, next, rot)
            case 1 | 3:
                position = random.randint(1, self.width - 1)

                landing_row_outleft = self._ffnz(position - 2) + 1 if position > 2 and sticky else self.height
                landing_row_left = self._ffnz(position - 1) if position > 1 else self.height
                landing_row_pivot = self._ffnz(position) + 1
                landing_row_outright = self._ffnz(position + 1) + 2 if position < self.width - 1 and sticky else self.height

                # Find minimum landing row
                landing_row = min(
                    landing_row_outleft,
                    landing_row_left,
                    landing_row_pivot,
                    landing_row_outright)

                if landing_row < 3:
                    self.FinalSteps = i
                    return -1

                # Place square based on the minimum landing row
                next = i + 1
                self._Place_Z(position, landing_row - 1, next, rot)

        self._UpdateStatus(i)
        return next

    def _Place_1x1(self, position, landing_row, i):
        """
        Place a 1x1 piece.

        Args:
            position (int): The position of the pivot.
            landing_row (int): The landing row of the pivot.
            i (int): The step number.

        Return:
            None
        """
        self.substrate[landing_row - 1, position] = i

    def Update_1x1(self, i, rot=0, sticky=True):
        """
        Updates the substrate with a 1x1 piece.

        Args:
            i (int): The step number.
            rot (int): The rotation of the piece. (No use, just be consistent with the others)
            sticky (bool): Whether the piece is sticky or not. (Default: True)

        Returns:
            int: The particle ID or the step number that has been placed in this step.
                + If the value is -1, it means it reaches to the top.
        """
        position = random.randint(0, self.width - 1)

        next = i

        landing_row_outleft = self._ffnz(position - 1) + 1 if position > 1 and sticky else self.height
        landing_row_pivot = self._ffnz(position)
        landing_row_outright = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self.height

        # Find minimum landing row
        landing_row = min(
            landing_row_outleft,
            landing_row_pivot,
            landing_row_outright)

        if landing_row < 2:
            self.FinalSteps = i
            return -1

        # Place square based on the minimum landing row
        next = i + 1
        self._Place_1x1(position, landing_row, next)
        # print(self.substrate)
        # input("")

        self._UpdateStatus(i)
        return next

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

    def _UpdateStatus(self, step):
        """
        Compute the top envelope of a substrate.

        This function calculates the highest particle position in each column
        of the substrate. Update the both HeightDynamics and Fluctuation
        attributes of the substrate.

        Args:
            step (int): The step number of the substrate.
        Returns:
            None
        """
        top_envelope = np.zeros(self.width)
        for pos in range(self.width):
            if np.any(self.substrate[:, pos] > 0):  # If there's any nonzero value in the column
                top_envelope[pos] = np.argmax(self.substrate[:, pos] > 0) - 1
            else:
                top_envelope[pos] = self.height - 1

        self.HeightDynamics[step] = top_envelope
        average = np.mean(top_envelope)
        self.AvergeHeight[step] = average

        self.Fluctuation[step] = 0
        for pos in range(self.width):
            self.Fluctuation[step] += np.power(top_envelope[pos] - average, 2) / self.width
        self.Fluctuation[step] = np.sqrt(self.Fluctuation[step])

    def count_holes(self):
        """
        Counts the number of holes in the substrate
        --------------------------------------------

        A hole is defined as a collection of zero entries in the substrate that
        has a boundary of nonzero entries surrounding it.

        Args:
            substrate (numpy.ndarray): The substrate to count the holes in.

        Returns:
            int: The number of holes in the substrate.
        """
        def depth_first_search(row, col):
            # Checking boundaries and if cell is a 0
            if 0 <= row < len(substrate_copy) and 0 <= col < len(substrate_copy[0]) and substrate_copy[row][col] == 0:
                substrate_copy[row][col] = -1
                depth_first_search(row + 1, col)
                depth_first_search(row - 1, col)
                depth_first_search(row, col + 1)
                depth_first_search(row, col - 1)

        hole_counter = 0
        substrate_copy = self.substrate.copy()

        for i in range(len(substrate_copy)):
            for j in range(len(substrate_copy[0])):
                if substrate_copy[i][j] == 0:
                    depth_first_search(i, j)
                    hole_counter += 1

        return hole_counter

    def count_holes_stack(self, frame_id=None, verbose=False):
        """
        Counts the number of holes in the substrate
        --------------------------------------------

        A hole is defined as a collection of zero entries in the substrate that
        has a boundary of nonzero entries surrounding it.

        Args:
           frame_id (int): The frame id to count the holes in. If None, the last farm will be used.
           verbose (bool): Whether to print out the result.

        Returns:
            int: The number of holes in the substrate.
        """
        if self.substrate.size == 0:
            return 0

        vis_substrate = np.copy(self.substrate)
        if frame_id is None:
            frame_id = self.FinalSteps  # Use self.FinalSteps if frame_id is not provided
        else:
            # filter out the values greater than the current frame_id
            vis_substrate[self.substrate > frame_id] = 0

        visited = np.zeros_like(vis_substrate, dtype=bool)

        def dfs_stack(r, c):
            stack = [(r, c)]
            while stack:
                r, c = stack.pop()
                if r < 0 or c < 0 or r >= self.height or c >= self.width or visited[r][c] or vis_substrate[r][c] != 0:
                    continue
                visited[r][c] = True
                # Add adjacent cells to stack
                stack.append((r + 1, c))
                stack.append((r - 1, c))
                stack.append((r, c + 1))
                stack.append((r, c - 1))

        hole_count = 0
        for r in range(self.height):
            for c in range(self.width):
                if vis_substrate[r][c] == 0 and not visited[r][c]:
                    dfs_stack(r, c)
                    hole_count += 1

        if verbose:
            print(f"Hole count: {hole_count} at the end of step {frame_id}.")

        return hole_count

    def PrintStatus(self, brief=False):
        """
        Print the step/status of the class
        ----------------------------------

        This function prints out the status of the substrate.

        Args:
            brief (bool): Whether to print out the substrate, height dynamics, average height, and Fluctuation or not.
        Returns:
            None
        """
        print("------------------------\n")
        print("Status of the substrate:")
        print(f"Width:  {self.width}")
        print(f"Height: {self.height}")
        print(f"Steps: {self.steps}")
        print(f"Final Steps: {self.FinalSteps}")
        print(f"Seed: {self.seed}")

        if not brief:
            print(f"Substrate:\n {self.substrate}")
            print(f"Height Dynamics:\n {self.HeightDynamics}")
            print(f"Average Height:\n {self.AvergeHeight}")
            print(f"Fluctuation:\n {self.Fluctuation}")

        print(f"Log-time vs slopes:\n {self.log_time_slopes}")

    def ComputeSlope(self):
        """
        Compute the slope of the substrate
        ----------------------------------

        This function computes the slope of the substrate and returns
        a 2-D array with log_time and corresponding slopes.

        The computation starts from the 1/10 of the total steps and we sample
        at most 100 points.

        Return: None
        """
        time = np.array(range(1, self.FinalSteps + 1))
        quarter_length = len(time) // 10
        step_size = max(1, (len(time) - quarter_length) // 100)
        num_samples = len(range(quarter_length, len(time), step_size))

        # Initialize an empty 2D array for log_times and slopes
        self.log_time_slopes = np.empty((num_samples, 2))

        print("Computing the slopes now...")

        total_iterations = len(range(quarter_length, len(time), step_size))
        for i, end in enumerate(range(quarter_length, len(time), step_size)):
            current_time = time[:end]
            current_interface = self.Fluctuation[:end]

            # Calculate the progress percentage
            progress_percentage = ((i + 1) / total_iterations) * 100

            # Print the progress
            print(f"Progress: {progress_percentage:.2f}%", end='\r')

            log_time = np.log(current_time[-1])
            log_interface = np.log(current_interface)

            slope, _ = np.polyfit(np.log(current_time), log_interface, 1)

            self.log_time_slopes[i] = [log_time, slope]

    def visualize_simulation(self,
                             plot_title="",
                             rate=4,
                             video_filename="simulation.gif",
                             envelop=False,
                             show_average=False):
        """
        Visualize the particle deposition simulation and generate a video
        -----------------------------------------------------------------

        This function visualizes the deposition process as an animation. It can
        accept either the path to a substrate data file or the substrate data
        directly as a NumPy array. When a filename is provided as a string, it
        loads the substrate data from the file. The function supports
        visualizing the top envelope and average height of the deposited
        particles. The final output is saved as an gif video file.

        Parameters
        ----------
        plot_title : str, optional (default: "")
            The title of the plot.
        rate : int, optional (default: 4)
            The frame rate for the video.
        video_filename : str, optional (default: "simulation.gif")
            The output video filename (mp4 or gif).
        envelop : bool, optional (default: False)
            Flag to indicate whether to show the top envelope.
        show_average : bool, optional (default: False)
            Flag to indicate whether to show the average height.

        Returns
        -------
            None
        """
        extension = os.path.splitext(video_filename)[1]
        if extension not in [".gif", ".mp4"]:
            raise ValueError(f"Unsupported video format: {extension}")

        steps = self.FinalSteps

        # Create a custom colormap with gray as the background color
        colors = [(0.8, 0.8, 0.8)] + [plt.cm.viridis(i) for i in range(plt.cm.viridis.N)]
        custom_colormap = mcolors.LinearSegmentedColormap.from_list(
            "custom", colors, N=steps + 1
        )

        # Visualization setup
        # Adjust the width and height as needed
        fig, ax = plt.subplots(figsize=(12, 8))
        frames = []

        # steps = 100  # for debug only
        # Simulation
        for step in range(1, steps + 1):
            # Create a copy of the substrate for visualization
            vis_substrate = np.copy(self.substrate)

            # Replace values greater than the current step with 0
            vis_substrate[vis_substrate > step] = 0

            # Visualize the current state and save as a frame
            ax.clear()
            ax.imshow(
                vis_substrate,
                cmap=custom_colormap,
                aspect="auto",
                norm=mcolors.Normalize(vmin=0, vmax=steps),
            )

            if envelop:
                # Compute and plot the top envelope
                ax.plot(range(self.width),
                        self.HeightDynamics[step],
                        color="red",
                        linewidth=2)

            if show_average:
                # print(f"Average height: {average}")
                ax.axhline(y=self.AvergeHeight[step],
                           color="black",
                           linewidth=2)

            ax.set_title(f"{plot_title} - Particle: {step}")

            # Relabel the y-axis
            ax.set_yticks(np.arange(0, self.height, self.height // 5))
            ax.set_yticklabels(np.arange(self.height, 0, -self.height // 5))

            ax.set_ylabel("Height",
                          rotation=90,
                          labelpad=20,
                          verticalalignment="center")
            ax.set_xlabel("Substrate", labelpad=8)
            ax.set_xticks(np.arange(0, self.width, self.width // 5))

            # Convert the plot to an image and append to frames
            fig.canvas.draw()
            image = np.frombuffer(fig.canvas.tostring_rgb(), dtype="uint8")
            image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            frames.append(image)

            if step % 100 == 0:
                print(f"Step: {step} / {steps}")

        match extension:
            case ".gif":
                duration = 1000 / rate
                imageio.mimsave(video_filename, frames, duration=duration)
            case ".mp4":
                imageio.mimsave(video_filename, frames, fps=rate)

    def Substrate2PNG(self,
                      plot_title="",
                      frame_id=None,
                      image_filename=None,
                      envelop=False,
                      show_average=False):
        """
        Convert the current substrate to a PNG file
        -------------------------------------------

        Parameters
        ----------
        plot_title : str, optional (default: "")
            The title of the plot.
        frame_id : int, optional (default: None)
            The frame number to be saved. If the value is None, then the frame_id is set to be self.FinalSteps.
        image_filename : str, optional (default: None)
            The file name of the output png image file. If the value is None, then the filename is set to be frame_{frame_id}.png.
        envelop : bool, optional (default: False)
            Flag to indicate whether to show the top envelope.
        show_average : bool, optional (default: False)
            Flag to indicate whether to show the average height.

        Returns
        -------
            None
        """
        vis_substrate = np.copy(self.substrate)
        if frame_id is None:
            frame_id = self.FinalSteps  # Use self.FinalSteps if frame_id is not provided
        else:
            # filter out the values greater than the current frame_id
            vis_substrate[self.substrate > frame_id] = 0

        if image_filename is None:
            image_filename = f"frame_{frame_id}.png"  # Dynamically set the filename

        steps = frame_id

        # Create a custom colormap with gray as the background color
        colors = [(0.8, 0.8, 0.8)] + [plt.cm.viridis(i) for i in range(plt.cm.viridis.N)]
        custom_colormap = mcolors.LinearSegmentedColormap.from_list("custom", colors, N=steps + 1)

        # Visualization setup
        fig, ax = plt.subplots(figsize=(12, 8))

        # Visualize the final state
        ax.imshow(vis_substrate, cmap=custom_colormap, aspect="auto", norm=mcolors.Normalize(vmin=0, vmax=steps))

        if envelop:
            # Compute and plot the top envelope
            ax.plot(range(self.width),
                    self.HeightDynamics[frame_id],
                    color="red",
                    linewidth=2)

        if show_average:
            # print(f"Average height: {average}")
            ax.axhline(y=self.AvergeHeight[frame_id],
                       color="black",
                       linewidth=2)

        ax.set_title(f"{plot_title}")

        # Adjust labels and ticks as needed
        ax.set_ylabel("Height", rotation=90, labelpad=20, verticalalignment="center")
        ax.set_xlabel("Substrate", labelpad=8)

        # Save the final frame as a PNG image
        plt.savefig(image_filename)
        plt.close()

    def save_simulation(self, filename="TB.joblib"):
        """
        Dump the class instance to a file using joblib.

        Args:
            - filename: str, the path to the file where to dump the class instance. (Default: "TB.joblib")

        Returns:
            None
        """
        joblib.dump(self, filename)
        print(f"Data dumped to {filename}")

    @staticmethod
    def load_simulation(filename):
        """
        Load a Tetris_Ballistic class instance from a file using joblib.

        Args:
            - filename: str, the path to the file from which to load the class instance.

        Returns:
            - The loaded Tetris_Ballistic class instance.

        Example:

        >>> tetris_simulator = Tetris_Ballistic.load_simulation("TB.joblib")

        """
        return joblib.load(filename)


def _create_partial(func, *args, **kwargs):
    """
    Creates a partial function from the given function, with pre-specified
    positional and keyword arguments.

    This function uses `functools.partial` to create a new function with some
    of the arguments of the original function pre-filled. It is useful for
    creating a version of a function that has the same behavior with fixed
    values for certain arguments. The name of the new function is modified to
    include the original function's name along with the pre-specified arguments
    for easy identification.

    Args:
        func (Callable): The original function to be partially applied.
        *args: Variable length argument list representing positional arguments to be pre-applied to the function.
        **kwargs: Arbitrary keyword arguments representing keyword arguments to be pre-applied to the function.

    Returns:
        Callable: A new partial function with pre-applied arguments.
    """
    partial_func = partial(func, *args, **kwargs)
    partial_func.__name__ = f"{func.__name__} args={args} kwargs={kwargs}"
    return partial_func

# Example usage
# tetris_simulator = Tetris_Ballistic(width=10, height=20, steps=1000, seed=42)
# tetris_simulator = Tetris_Ballistic(width=10, height=20, steps=10, seed=42)
# tetris_simulator.save_config("save_config.yaml")
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
# tetris_simulator.Test_All()
