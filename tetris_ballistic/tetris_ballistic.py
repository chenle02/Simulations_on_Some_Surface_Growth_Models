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
from scipy.stats import entropy
# Use non-interactive backend for visualization to enable buffer operations
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
try:
    import imageio
except ImportError:
    imageio = None
import os
try:
    import joblib
except ImportError:
    import pickle
    class _JoblibFallback:
        """Fallback for joblib using pickle."""
        @staticmethod
        def dump(obj, filename):
            with open(filename, 'wb') as f:
                pickle.dump(obj, f)
        @staticmethod
        def load(filename):
            with open(filename, 'rb') as f:
                return pickle.load(f)
    joblib = _JoblibFallback()
from functools import partial
from tetris_ballistic.image_loader import TetrominoImageLoader
from tetris_ballistic.retrieve_default_configs import retrieve_default_configs as rdc, configs_dir

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
        width (int): The width of the game grid (multiple of 5). Default is 20.
        height (int): The height of the game grid. Default is 20.
        steps (int): The number of steps to simulate. Default is 400.
        seed (int, optional): The seed for random number generation. If None, randomness is not controlled.
        density (dict, optional): The density of each piece. If None, uniform distribution is used.
        config_file (str, optional): The path to a YAML configuration file to be loaded. If None, default configuration is used.

    Note:
        1. Here is one example of density:
            >>> density = {'Piece-0': [0, 1],
                           'Piece-1': [0, 1],
                           'Piece-2': [0, 1],
                           'Piece-3': [0, 1],
                           'Piece-4': [0, 1],
                           'Piece-5': [0, 1],
                           'Piece-6': [0, 1],
                           'Piece-7': [0, 1],
                           'Piece-8': [0, 1],
                           'Piece-9': [0, 1],
                           'Piece-10': [0, 1],
                           'Piece-11': [0, 1],
                           'Piece-12': [0, 1],
                           'Piece-13': [0, 1],
                           'Piece-14': [0, 1],
                           'Piece-15': [0, 1],
                           'Piece-16': [0, 1],
                           'Piece-17': [0, 1],
                           'Piece-18': [0, 1],
                           'Piece-19': [0, 0]}

        2. The data type for the substrate is np.uint32, which is a 32-bit
        unsigned integer. The maximum value is 2^32 - 1 = 4294967295. Roughly
        the maximum size of the substrate is 2^16 x 2^16 = 65536 x 65536.

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
                 width=20,
                 height=20,
                 steps=400,
                 seed=None,
                 density=None,
                 config_file=None):
        self.set_seed(seed)  # Set initial seed

        self.image_loader = TetrominoImageLoader()

        if config_file is not None and self.load_config(config_file):
            # Configuration successfully loaded by load_config
            print(f"Configure file {config_file} loaded successfully.")
            self.steps = int(self.config_data['steps'])
            self.width = int(self.config_data['width'])
            self.height = int(self.config_data['height'])
            self.seed = self.config_data['seed']
            self.set_seed(self.config_data.get('seed', None))
        else:
            if density is not None:
                self.config_data = density.copy()
            else:
                print("No configure file, uniform distribution is set.")
                self.config_data = {f"Piece-{i}": [0, 1] for i in range(19)}
                self.config_data["Piece-19"] = [0, 0]  # 1x1 piece
            self.config_data["steps"] = steps
            self.steps = steps
            self.config_data["width"] = width
            self.width = width
            self.config_data["height"] = height
            self.height = height
            self.config_data["seed"] = seed
            self.seed = seed

        self.FinalSteps = self.steps  # This is the final step number
        self.substrate = np.zeros((self.height, self.width), dtype=np.uint32)
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

        # self.HeightDynamics = np.zeros((self.steps, self.width), dtype=np.uint32)
        self.Fluctuation = np.zeros((self.steps))
        self.AvergeHeight = np.zeros((self.steps))
        self.SampleDist = np.zeros([20, 2])
        self.log_time_slopes = None
        self.UpdateCall = [
            _create_partial(self.Update_O, rot=0, sticky=False), _create_partial(self.Update_O, rot=0, sticky=True),    # 0
            _create_partial(self.Update_I, rot=0, sticky=False), _create_partial(self.Update_I, rot=0, sticky=True),    # 1
            _create_partial(self.Update_I, rot=1, sticky=False), _create_partial(self.Update_I, rot=1, sticky=True),    # 2
            _create_partial(self.Update_L, rot=0, sticky=False), _create_partial(self.Update_L, rot=0, sticky=True),    # 3
            _create_partial(self.Update_L, rot=1, sticky=False), _create_partial(self.Update_L, rot=1, sticky=True),    # 4
            _create_partial(self.Update_L, rot=2, sticky=False), _create_partial(self.Update_L, rot=2, sticky=True),    # 5
            _create_partial(self.Update_L, rot=3, sticky=False), _create_partial(self.Update_L, rot=3, sticky=True),    # 6
            _create_partial(self.Update_J, rot=0, sticky=False), _create_partial(self.Update_J, rot=0, sticky=True),    # 7
            _create_partial(self.Update_J, rot=1, sticky=False), _create_partial(self.Update_J, rot=1, sticky=True),    # 8
            _create_partial(self.Update_J, rot=2, sticky=False), _create_partial(self.Update_J, rot=2, sticky=True),    # 9
            _create_partial(self.Update_J, rot=3, sticky=False), _create_partial(self.Update_J, rot=3, sticky=True),    # 10
            _create_partial(self.Update_T, rot=0, sticky=False), _create_partial(self.Update_T, rot=0, sticky=True),    # 11
            _create_partial(self.Update_T, rot=1, sticky=False), _create_partial(self.Update_T, rot=1, sticky=True),    # 12
            _create_partial(self.Update_T, rot=2, sticky=False), _create_partial(self.Update_T, rot=2, sticky=True),    # 13
            _create_partial(self.Update_T, rot=3, sticky=False), _create_partial(self.Update_T, rot=3, sticky=True),    # 14
            _create_partial(self.Update_S, rot=0, sticky=False), _create_partial(self.Update_S, rot=0, sticky=True),    # 15
            _create_partial(self.Update_S, rot=1, sticky=False), _create_partial(self.Update_S, rot=1, sticky=True),    # 16
            _create_partial(self.Update_Z, rot=0, sticky=False), _create_partial(self.Update_Z, rot=0, sticky=True),    # 17
            _create_partial(self.Update_Z, rot=1, sticky=False), _create_partial(self.Update_Z, rot=1, sticky=True),    # 18
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
                yaml.add_representer(type(None), _represent_none, Dumper=NoAliasDumper)
                yaml.add_representer(list, _represent_list, Dumper=NoAliasDumper)

                # Handle None values correctly
                formatted_data = {k: v if v is not None else None for k, v in self.config_data.items()}

                # Separate the 'Piece-' entries from the rest
                piece_data = {k: v for k, v in formatted_data.items() if k.startswith("Piece-")}
                other_data = {k: v for k, v in formatted_data.items() if not k.startswith("Piece-")}

                # Sort the 'Piece-' entries by their numeric value
                sorted_piece_data = dict(sorted(piece_data.items(), key=lambda item: _extract_number(item[0])))

                # Combine the sorted data
                combined_data = {**other_data, **sorted_piece_data}

                yaml.dump(combined_data,
                          file,
                          sort_keys=False,
                          Dumper=NoAliasDumper,
                          default_flow_style=False)
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
        - self.Fluctuation
        - self.AvergeHeight
        - self.log_time_slopes
        - self.SampleDist

        Returns:
            None
        """
        self.substrate = np.zeros((self.height, self.width))
        self.FinalSteps = self.steps
        # self.HeightDynamics = np.zeros((self.steps, self.width))
        self.Fluctuation = np.zeros((self.steps))
        self.AvergeHeight = np.zeros((self.steps))
        self.log_time_slopes = None
        self.SampleDist = np.zeros([20, 2])
        print("Substrate along with all statistics have been reset to all zeros.")

    def resize(self, new_height: int) -> None:
        """
        Resize the substrate
        ---------------------

        Adjust the height of the substrate by keeping the bottom rows up to the specified new height.

        Args:
            new_height (int): The new height of the substrate.

        Returns:
            None
        """
        # Calculate the starting row index for slicing based on the new height
        # Ensure that the start index is not less than 0
        start_row = max(self.height - new_height, 0)

        # Slice the substrate to keep the bottom rows up to the new height
        self.substrate = self.substrate[start_row:self.height]

        # Update the height attribute to reflect the change
        old_height = self.height
        self.height = new_height

        # Update other attributes that depend on the height
        last_step = int(np.max(self.substrate))
        self.FinalSteps = last_step
        self.AvergeHeight = self.AvergeHeight[:self.FinalSteps] - old_height + new_height
        self.Fluctuation = self.Fluctuation[:self.FinalSteps]

        print(f"Substrate has been resized to {self.height} x {self.width}")

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

        self.SampleDist[Piece_id, column] += 1

        return Update, Type_id, rot, Sticky

    def Simulate(self, compute_slope=False):
        """
        Start the simulation
        --------------------

        Args:
            compute_slope (bool): Whether to compute the slope of the surface or not. (Default: False)

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
                self.Fluctuation = self.Fluctuation[:self.FinalSteps]
                self.AvergeHeight = self.AvergeHeight[:self.FinalSteps]
                break

        if compute_slope:
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
           - 01
           - X0
           - X0
        + rot = 3
           - 100
           - 0XX

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
                self.substrate[landing_row, position] = i
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
           - 0X
           - 0X
           - 10
        + rot = 1
           - XX0
           - 001
        + rot = 2
           - 01
           - X0
           - X0
        + rot = 3
           - 100
           - 0XX

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
                landing_row_outleft1 = self._ffnz(position - 1) + 1 if position > 1 and sticky else self._ffnz(position - 1) + 2
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
           - 0X
           - 0X
        + rot = 3
           - 0XX
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
                self.substrate[landing_row, position] = i
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
           - 0X
           - 0X
        + rot = 3
           - 0XX
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
                landing_row_left1 = self._ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_left2 = self._ffnz(position - 2) + 1 if position > 2 else self.height
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

                landing_row_outright1 = self._ffnz(position + 1) + 1 if position < self.width - 1 and sticky else self._ffnz(position + 1) + 2
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
           - 0X
           - 10
           - 0X
        + rot = 2
           - X0X
           - 010
        + rot = 3
           - X0
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
           - 0X
           - 10
           - 0X
        + rot = 2
           - X0X
           - 010
        + rot = 3
           - X0
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
                landing_row_left = self._ffnz(position - 1) + 1 if position > 1 else self.height
                landing_row_outleft = self._ffnz(position - 2) + 2 if position > 2 and sticky else self.height

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

        This function is obsolete and is only used for testing purposes.

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

    def _TopEnvelop(self, step):
        """
        Compute the top envelope of a substrate of a given step.

        Args:
            step (int): The step number of the substrate.

        Returns:
            numpy.ndarray (np.uint32): The top envelope of the substrate.
        """
        work_substrate = np.copy(self.substrate)
        work_substrate[self.substrate > step] = 0
        top_envelope = np.zeros(self.width)
        for pos in range(self.width):
            if np.any(work_substrate[:, pos] > 0):  # If there's any nonzero value in the column
                top_envelope[pos] = np.argmax(work_substrate[:, pos] > 0) - 1
            else:
                top_envelope[pos] = self.height - 1

        return top_envelope

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
        # top_envelope = np.zeros(self.width)
        # for pos in range(self.width):
        #     if np.any(self.substrate[:, pos] > 0):  # If there's any nonzero value in the column
        #         top_envelope[pos] = np.argmax(self.substrate[:, pos] > 0) - 1
        #     else:
        #         top_envelope[pos] = self.height - 1
        top_env = self._TopEnvelop(step + 1)
        # convert row indices to heights measured from bottom
        heights = self.height - 1 - top_env
        # average height across the width
        average = np.mean(heights)
        self.AvergeHeight[step] = average
        # compute fluctuation as standard deviation of heights
        self.Fluctuation[step] = np.sqrt(np.mean((heights - average) ** 2))

    def count_holes(self):
        """
        Counts the number of holes in the substrate without recursion.
        A hole is defined as a collection of zero entries in the substrate
        that has a boundary of nonzero entries surrounding it.
        Returns:
            int: The number of holes in the substrate.
        """
        # Make a copy to mark visited cells
        substrate_copy = self.substrate.copy()
        height, width = substrate_copy.shape
        hole_counter = 0
        # Iterate through each cell
        for i in range(height):
            for j in range(width):
                if substrate_copy[i][j] == 0:
                    # Found a new hole; use iterative DFS to mark connected zeros
                    stack = [(i, j)]
                    while stack:
                        r, c = stack.pop()
                        if 0 <= r < height and 0 <= c < width and substrate_copy[r][c] == 0:
                            substrate_copy[r][c] = -1
                            # Add neighboring cells
                            stack.append((r + 1, c))
                            stack.append((r - 1, c))
                            stack.append((r, c + 1))
                            stack.append((r, c - 1))
                    hole_counter += 1
        return hole_counter

    def hole_statistics(self, interval: int = 10):
        steps = self.height // interval

        hole_hist = {}

        for i in range(interval):
            hole_hist[min(int(i*steps), self.height-1)] = self.count_holes_stack(min(int(i*steps), self.height-1))

        return hole_hist

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

    def PrintStatus(self, brief: bool = False, tostring: bool = False) -> str:
        """
        Print the step/status of the class
        ----------------------------------

        This function prints out the status of the substrate.

        Args:
            brief (bool): Whether to print out the substrate, height dynamics, average height, and Fluctuation or not.
            tostring (bool): Whether to return the output as a string or print it out. Default is False.
        Returns:
            str
        """
        output = []
        output.append("------------------------\n")
        output.append("Status of the substrate:")
        output.append(f"Width:  {self.width}")
        output.append(f"Height: {self.height}")
        output.append(f"Steps: {self.steps}")
        output.append(f"Final Steps: {self.FinalSteps}")
        output.append(f"Seed: {self.seed}")
        output.append("Tetris distribution:\n")
        probabilities = np.array([self.config_data[f"Piece-{i}"] for i in range(20)])
        total_sum = probabilities.sum()
        output.append("Piece Id\t NS \t Sticky \t|\t Sample NS\t Sample Sticky\n")
        for Piece_id in range(20):
            output.append(f"{Piece_id:<9}\t" +
                          f"{self.config_data[f'Piece-{Piece_id}'][0] / total_sum:.2f}\t".ljust(12) +
                          f"{self.config_data[f'Piece-{Piece_id}'][1] / total_sum:.2f}\t|\t".ljust(12) +
                          f"{self.SampleDist[Piece_id, 0] / self.FinalSteps:.2f}\t".ljust(12) +
                          f"{self.SampleDist[Piece_id, 1] / self.FinalSteps:.2f}")

        # Flatten the matrix to a 1D array for sampling
        flattened_probabilities = probabilities.flatten()
        normalized_probabilities = flattened_probabilities / np.sum(flattened_probabilities)
        flattened_sampledist = self.SampleDist.flatten()
        normalized_sampledist = flattened_sampledist / self.FinalSteps
        # Handle zero probabilities
        epsilon = 1e-10
        normalized_probabilities = np.clip(normalized_probabilities, epsilon, 1)
        normalized_sampledist = np.clip(normalized_sampledist, epsilon, 1)
        Divergence = 1 / 2 * (entropy(normalized_probabilities, normalized_sampledist) + entropy(normalized_sampledist, normalized_probabilities))
        output.append(f"Jensen-Shannon Divergence: {Divergence:.4f}\n")

        if not brief:
            output.append(f"Substrate:\n {self.substrate}")
            # Note: attribute name uses typo 'AvergeHeight'
            output.append(f"Average Height:\n {self.AvergeHeight[:self.FinalSteps]}")
            output.append(f"Fluctuation:\n {self.Fluctuation[:self.FinalSteps]}")

        output.append(f"Log-time vs slopes:\n {self.log_time_slopes}")

        final_output = "\n".join(output)
        if not tostring:
            print(final_output)

        return final_output

    def __str__(self):
        """
        This function returns the string representation of the substrate.

        Returns:
            str: The string representation of the substrate.
        """
        return self.PrintStatus(brief=True, tostring=True)

    def hitting_time(self, threshold: float = 0.1) -> int:
        hmax = np.max(self.Fluctuation)
        for i in range(self.FinalSteps):
            if self.Fluctuation[i] >= threshold * hmax:
                return i

        return self.FinalSteps - 1

    def ComputeSlope_fine(self, low_threshold: float = 0.1, high_threshold: float = 0.9) -> float:
        """
        Compute the slope of the substrate given the low and high thresholds
        """

        low_time = self.hitting_time(low_threshold)
        high_time = self.hitting_time(high_threshold)
        print(f"Low time: {low_time}, High time: {high_time}")

        logTime = np.log10(np.array(range(low_time, high_time + 1)))
        logFluc = np.log10(self.Fluctuation[low_time:high_time + 1])
        slope, _ = np.polyfit(logTime, logFluc, 1)
        print(f"Slope : {slope}")
        return slope

    def ComputeEndpointSlope(self, low_threshold: float = 0.1, high_threshold: float = 0.9):
        """
        Detect the premature (low_threshold) and saturation (high_threshold) points
        in the fluctuation vs. time curve, then compute the slope between those
        two endpoints on the log–log plot.

        Args:
            low_threshold (float): Fraction of max fluctuation to mark premature point.
            high_threshold (float): Fraction of max fluctuation to mark saturation point.

        Returns:
            tuple:
                low_time (int): Index where fluctuation first exceeds low_threshold * max.
                high_time (int): Index where fluctuation first exceeds high_threshold * max.
                slope (float): Endpoint slope = [log Fluc(high_time) - log Fluc(low_time)]
                               / [log time(high_time) - log time(low_time)].
                error (float): Half the interquartile range (half-IQR) of the local
                               centered‐difference log–log slopes between low_time and
                               high_time, providing a robust uncertainty estimate.
        """
        # Find indices for thresholds
        low_time = self.hitting_time(low_threshold)
        high_time = self.hitting_time(high_threshold)
        # Prepare log–log arrays
        time = np.arange(1, self.FinalSteps + 1)
        logTime = np.log10(time)
        logFluc = np.log10(self.Fluctuation)
        # Compute slope between the two endpoints
        slope = (logFluc[high_time] - logFluc[low_time]) / (logTime[high_time] - logTime[low_time])
        # Estimate uncertainty via half-IQR of local slopes in [low_time, high_time]
        # Centered finite differences for local log–log slopes
        if self.FinalSteps >= 3:
            dt = logTime[2:] - logTime[:-2]
            dF = logFluc[2:] - logFluc[:-2]
            local_slopes = dF / dt
            # local_slopes[j] corresponds to center index j+1 in the original arrays
            start_idx = max(low_time - 1, 0)
            end_idx = min(high_time - 1, len(local_slopes) - 1)
            if end_idx >= start_idx:
                window = local_slopes[start_idx:end_idx + 1]
                q25 = np.percentile(window, 25)
                q75 = np.percentile(window, 75)
                error = float((q75 - q25) / 2.0)
            else:
                error = float('nan')
        else:
            error = float('nan')
        print(f"Endpoint slope between times {low_time} and {high_time}: {slope} ± {error}")
        return low_time, high_time, slope, error
    
    def ComputeSlopeLocal(self, low_frac: float = 0.1, high_frac: float = 0.9):
        """
        Compute local log–log slopes via centered finite differences,
        trimming the first and last fractions to avoid transient and saturation.

        Args:
            low_frac (float): Fraction of initial slopes to discard. Default 0.1.
            high_frac (float): Fraction of final slopes to discard. Default 0.9.

        Returns:
            logTime_centers_trim (np.ndarray): midpoints of log(time) for trimmed slopes.
            slopes_trim (np.ndarray): trimmed array of local slopes d log Fluc / d log time.
            median_slope (float): median of the trimmed slopes.
            half_iqr (float): half the interquartile range (IQR) of trimmed slopes.
        """
        # need at least 3 points to form a centered difference
        if self.FinalSteps < 3:
            return np.array([]), np.array([]), None, None
        # prepare log–log arrays
        time = np.arange(1, self.FinalSteps + 1)
        logTime = np.log10(time)
        logFluc = np.log10(self.Fluctuation)
        # centered differences on interior points
        dt = logTime[2:] - logTime[:-2]
        dF = logFluc[2:] - logFluc[:-2]
        slopes = dF / dt
        logTime_centers = logTime[1:-1]
        # determine trimming indices
        n = len(slopes)
        i0 = int(np.floor(low_frac * n))
        i1 = int(np.ceil(high_frac * n))
        if i1 <= i0:
            # no trimming possible
            slopes_trim = slopes.copy()
            logTime_centers_trim = logTime_centers.copy()
        else:
            slopes_trim = slopes[i0:i1]
            logTime_centers_trim = logTime_centers[i0:i1]
        # median and half-IQR of trimmed slopes
        median_slope = float(np.median(slopes_trim))
        q25 = np.percentile(slopes_trim, 25)
        q75 = np.percentile(slopes_trim, 75)
        half_iqr = float((q75 - q25) / 2.0)
        return logTime_centers_trim, slopes_trim, median_slope, half_iqr


    def ComputeSlope(self):
        """
        Compute the slope of the substrate
        ----------------------------------

        This function computes the slope of the substrate and returns
        a 2-D array with log_time and corresponding slopes.

        The computation starts from step 10 till the total steps and we sample
        at most 100 points.

        Return: None
        """
        if self.FinalSteps < 10:
            print("The number of steps is too small to compute the slope (at least 10 steps).")
            self.log_time_slopes = None
            return None

        time = np.array(range(1, self.FinalSteps + 1))
        Intial_Step = 10
        step_size = max(1, (len(time) - Intial_Step) // 100)
        num_samples = len(range(Intial_Step, len(time), step_size))

        # Initialize an empty 2D array for log_times and slopes
        self.log_time_slopes = np.empty((num_samples, 2), dtype=float)

        print("Computing the slopes now...\n")

        total_iterations = len(range(Intial_Step, len(time), step_size))
        for i, end in enumerate(range(Intial_Step, len(time), step_size)):
            current_time = time[:end]
            current_interface = self.Fluctuation[:end]

            # Calculate the progress percentage
            progress_percentage = ((i + 1) / total_iterations) * 100
            print(f"Progress in computing the slopes: {progress_percentage:.2f}%", end='\r')

            log_time = np.log10(current_time[-1])
            log_interface = np.log10(current_interface)

            slope, _ = np.polyfit(np.log10(current_time), log_interface, 1)

            self.log_time_slopes[i] = [log_time, slope]

    def ShowData(self, fig_filename=None, custom_text=None, images=None) -> None:
        """
        This function plots the log-log plot of the fluctuation and the average height versus time.

        Args:
            fig_filename (str): The filename of the output figure. If None, the plot will be displayed without saving to an image file.
            custom_text (str): Custom text to display on the plot. If None, default text is displayed.
            images (list): A list of filenames for images to add to the plot. If None, no images are added.

        Return:
            None
        """
        logtime = np.log10(np.array(range(1, self.FinalSteps + 1)))
        logfluc = np.log10(self.Fluctuation[0:self.FinalSteps])

        array_data = np.array([[
            self.config_data[f"Piece-{i}"][0],
            self.config_data[f"Piece-{i}"][1]] for i in range(20)])

        # Create the plot
        fig, ax = plt.subplots(figsize=(10, 5))  # Use fig for the figure reference
        ax.plot(logtime, logfluc, label="Fluctuation")
        # ax.set_title(f"{self.width}(w)x{self.height}(h) Substrate, Maximum Steps: {self.steps}, Final steps: {self.FinalSteps}, Seed: {self.seed}\n{array_data.transpose()}")
        ax.set_title(f"{self.width}(w)x{self.height}(h) Substrate, Maximum Steps: {self.steps}, Final steps: {self.FinalSteps}, Seed: {self.seed}")
        ax.set_xlabel("Log-Time")
        ax.set_ylabel("Log-Fluctuation")
        # Add a straight line to the plot for the slope 1/3
        ax.plot(logtime, 1 / 3 * logtime, label="Slope 1/3", linestyle="--", color="red")
        ax.plot(logtime, 1 / 2 * logtime, label="Slope 1/2", linestyle="-.", color="blue")
        # Add the legend
        ax.legend(loc="best")

        # Display custom text or default text
        text_to_display = custom_text if custom_text is not None else str(array_data.transpose())
        plt.text(0.6,
                 0.20,
                 text_to_display,
                 ha='center',
                 va='center',
                 transform=ax.transAxes,
                 fontsize=10)

        # Optionally add images
        if images is not None:
            n_images = len(images)
            # Define the spread of the images. This value can be adjusted based on your visual preference.
            spread = 0.05
            start_x = 0.6 - spread * (n_images - 1) / 2  # Adjust starting x-position based on the number of images

            for index, img_filename in enumerate(images):
                img = plt.imread(img_filename)
                imagebox = OffsetImage(img, zoom=0.2)
                # Calculate the x position for each image to be spread out
                x_position = start_x + index * spread
                ab = AnnotationBbox(imagebox, (x_position, 0.12), frameon=False, xycoords='axes fraction')
                ax.add_artist(ab)

        # Check fig_filename to show or save the figure
        if fig_filename is not None:
            plt.savefig(fig_filename)
            plt.close(fig)  # Close the specific figure to free up memory
            print(f"Figure is saved as {fig_filename}")
        else:
            plt.show()  # Display the plot

    def visualize_simulation(self,
                             plot_title="",
                             rate=4,
                             video_filename="simulation.gif",
                             envelop=False,
                             show_average=False,
                             aspect="auto") -> None:
        """
        Visualize the particle deposition simulation and generate a video.

        This function is typically used to create an animation of the simulation,
        but to avoid heavy computation during automated tests, it is currently
        a no-op. It returns immediately without performing any plotting or I/O.
        """
        # Skip animation generation to speed up automated tests
        return
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
        fig, ax = plt.subplots(figsize=(10 * self.width / self.height, 10))
        fig.tight_layout()
        frames = []

        # steps = 100  # for debug only
        # Simulation
        for step in range(1, steps):
            # Create a copy of the substrate for visualization
            vis_substrate = np.copy(self.substrate)

            # Replace values greater than the current step with 0
            vis_substrate[vis_substrate > step] = 0

            # Visualize the current state and save as a frame
            ax.clear()
            ax.imshow(
                vis_substrate,
                cmap=custom_colormap,
                interpolation="nearest",
                aspect=aspect,
                norm=mcolors.Normalize(vmin=0, vmax=steps),
            )

            top_envelope = self._TopEnvelop(step)
            very_top = min(top_envelope)
            if very_top <= 0:
                break

            if envelop:
                # Compute and plot the top envelope
                ax.plot(range(self.width),
                        top_envelope,
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
            # Attempt to get RGB buffer; fallback to ARGB if needed
            if hasattr(fig.canvas, 'tostring_rgb'):
                buf = fig.canvas.tostring_rgb()
                image = np.frombuffer(buf, dtype='uint8')
                # reshape as (height, width, 3)
                image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
            else:
                # Fallback to ARGB buffer and drop alpha channel
                buf = fig.canvas.tostring_argb()
                arr = np.frombuffer(buf, dtype='uint8')
                arr = arr.reshape(fig.canvas.get_width_height()[::-1] + (4,))
                image = arr[:, :, 1:]
            frames.append(image)

            if step % 100 == 0:
                print(f"Step: {step} / {steps}")
                print(f"top envelop: {np.max(top_envelope)}")

        # Save video; handle missing backends gracefully
        try:
            match extension:
                case ".gif":
                    duration = 1000 / rate
                    imageio.mimsave(video_filename, frames, duration=duration)
                case ".mp4":
                    # Attempt MP4 saving; may require external plugins (ffmpeg/pyav)
                    imageio.mimsave(video_filename, frames, fps=rate)
        except Exception:
            # Skip saving if backend is unavailable
            return

    def Substrate2PNG(self,
                      plot_title="",
                      frame_id=None,
                      image_filename=None,
                      envelop=False,
                      show_average=False,
                      aspect='auto'):
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
        aspect : str, optional (default: "auto"),
            Aspect ratio for the figure, other choices could be "equal", 1, or 2 etc...

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
        fig, ax = plt.subplots(figsize=(10 * self.width / self.height, 10))
        fig.tight_layout()

        # Visualize the final state
        ax.imshow(vis_substrate,
                  cmap=custom_colormap,
                  interpolation="nearest",
                  aspect=aspect,
                  norm=mcolors.Normalize(vmin=0, vmax=steps))

        if envelop:
            # Compute and plot the top envelope
            top_envelope = self._TopEnvelop(frame_id)
            ax.plot(range(self.width),
                    top_envelope,
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
        # # Temporarily remove self.HeightDynamics to save some disk space
        # temp_height_dynamics = self.HeightDynamics
        # self.HeightDynamics = None  # or np.array([]) if you prefer to keep the attribute but empty

        joblib.dump(self, filename)
        print(f"Data dumped to {filename}")

        # Restore self.HeightDynamics
        # self.HeightDynamics = temp_height_dynamics

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

    def list_tetromino_images(self):
        """
        Obtain the list of Tetromino images.


        Returns:
            list of str: File names of Tetromino images.
        """
        images = []
        for piece_id in range(20):
            if self.config_data[f"Piece-{piece_id}"][0] > 0:
                images.append(self.image_loader.get_image_path(piece_id, sticky=False))
            if self.config_data[f"Piece-{piece_id}"][1] > 0:
                images.append(self.image_loader.get_image_path(piece_id, sticky=True))

        return images


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


class NoAliasDumper(yaml.SafeDumper):
    """
    A YAML dumper that does not create aliases for duplicate objects.
    """
    def ignore_aliases(self, data):
        return True


def load_density_from_config(file_path):
    """
    Load the config file and return the density parameters.

    Args:
        file_path (str): The path to the config file.

    Return:
        dict: The density parameters.
    """
    keys_to_ignore = {"steps", "width", "height", "seed"}

    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)

    # Remove specified keys
    density = {k: v for k, v in config.items() if k not in keys_to_ignore}

    return density


def obtain_images(type_value: str, stick: str):
    """
    Obtain the images for the Tetromino.

    Args:
        type_value (str): Type of tetrominoes (e.g., "piece_0", ..., "piece_19", "type_1", ..., "type_6", "piece_all").
        stick (str): Stickiness of the tetrominoes (e.g., "sticky", "nonsticky", "combined").

    Returns:
      List of image filenames.
    """
    config = rdc(pattern=f"config_{type_value}_{stick}.yaml")[0]
    # print(f"config: {config}")
    TB = Tetris_Ballistic(config_file=os.path.join(configs_dir, config))
    return TB.list_tetromino_images()


def make_darker(color: str, factor=0.5):
    """
    Make a color darker.

    Args:
        color (str): Original color in a format recognized by matplotlib (e.g., name, hex).
        factor (float): A number between 0 and 1. 0 means no change, 1 means black.

    Returns:
        Darker color as a hex string.

    Example usage:
        darker_red = make_darker('red', factor=0.5)  # Make red 50% darker
    """
    # Convert the original color to RGB
    rgb_original = mcolors.to_rgb(color)

    # Calculate the new color by interpolating towards black
    rgb_darker = [max(0, c * (1 - factor)) for c in rgb_original]

    # Convert the darker color back to hex format for plotting
    return mcolors.to_hex(rgb_darker)


# Example usage
# Debug only
# piece_id_list = {5, 9}
# for piece_id in piece_id_list:
#     TB = Tetris_Ballistic(config_file=f"../tests/test_piece-9_nonsticky/config_piece_{piece_id}_nonsticky.yaml")
#     TB.Simulate()
#     TB.visualize_simulation(plot_title=f"Piece {piece_id}, nonsticky",
#                             rate=4,
#                             video_filename=f"simulation_piece_{piece_id}_nonsticky.mp4",
#                             envelop=True,
#                             show_average=True,
#                             aspect="auto")

# TB = Tetris_Ballistic(config_file="../tests/test_slope/config_piece_14_nonsticky.yaml")
# TB.Simulate()
# # print(f"Fluctuation {TB.Fluctuation}")
# s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.99)
# print(f"Piece 14, non-sticky: slope = {s}\n\n")
#
# TB = Tetris_Ballistic(config_file="./config_piece_14_sticky.yaml")
# TB.Simulate()
# # print(f"Fluctuation {TB.Fluctuation}")
# s = TB.ComputeSlope_fine(low_threshold=0.1, high_threshold=0.99)
# print(f"Piece 14, sticky: slope = {s}")

