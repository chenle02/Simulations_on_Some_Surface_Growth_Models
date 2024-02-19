from pkg_resources import resource_filename


class TetrominoImageLoader:
    """
    A loader class for accessing Tetromino images based on piece IDs and their
    sticky state.

    This class provides a way to dynamically generate the path to image files
    for different Tetromino pieces based on their ID. The piece ID directly
    corresponds to a specific Tetromino shape and rotation, and the sticky
    state is indicated by a separate boolean flag.

    Attributes:
        piece_info (dict): A mapping from piece IDs to their corresponding
                           names and available rotations.
    """

    def __init__(self):
        # Mapping directly from piece_id to piece name and rotation
        self.piece_info = {
            0: ("O", "Single"),
            1: ("I", "Horizontal"),
            2: ("I", "Vertical"),
            3: ("L", "Up"),
            4: ("L", "Left"),
            5: ("L", "Down"),
            6: ("L", "Right"),
            7: ("J", "Up"),
            8: ("J", "Left"),
            9: ("J", "Down"),
            10: ("J", "Right"),
            11: ("T", "Up"),
            12: ("T", "Left"),
            13: ("T", "Down"),
            14: ("T", "Right"),
            15: ("S", "Horizontal"),
            16: ("S", "Vertical"),
            17: ("Z", "Horizontal"),
            18: ("Z", "Vertical"),
            19: ("1x1", "Single")
        }

    def get_image_path(self, piece_id, sticky=True):
        """
        Generates the file path to the image corresponding to a given Tetromino
        piece ID and its sticky state.

        Parameters:
            piece_id (int): The ID of the Tetromino piece (0 -- 19).
            sticky (bool): Indicates if the image should represent a sticky state. Defaults to True.

        Returns:
            str: The file path to the Tetromino piece's image.

        Raises:
            ValueError: If the piece_id does not correspond to any known piece configuration.
        """
        if piece_id not in self.piece_info:
            raise ValueError(f"Invalid piece_id: {piece_id}")

        piece_name, rotation = self.piece_info[piece_id]
        sticky_suffix = "_bordered" if not sticky else ""
        filename = f"Tetromino_{piece_name}_{rotation}{sticky_suffix}.png"
        return resource_filename(__name__, f'data/{filename}')
