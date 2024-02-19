#!/usr/bin/env python3
import os
import pytest
import contextlib
from tetris_ballistic.image_loader import TetrominoImageLoader


@pytest.fixture
def image_loader():
    return TetrominoImageLoader()


# Define test parameters for piece IDs and their expected non-sticky and sticky
# image file names.


output_file = "test_iamgeloader_output.txt"

# Remove the file if it exists before starting the test
if os.path.exists(output_file):
    os.remove(output_file)


@pytest.mark.parametrize(
    "piece_id, expected_sticky, expected_non_sticky", [
        (0, 'Tetromino_O_Single.png', 'Tetromino_O_Single_bordered.png'),
        (1, 'Tetromino_I_Horizontal.png', 'Tetromino_I_Horizontal_bordered.png'),
        (2, 'Tetromino_I_Vertical.png', 'Tetromino_I_Vertical_bordered.png'),
        (3, 'Tetromino_L_Up.png', 'Tetromino_L_Up_bordered.png'),
        (4, 'Tetromino_L_Left.png', 'Tetromino_L_Left_bordered.png'),
        (5, 'Tetromino_L_Down.png', 'Tetromino_L_Down_bordered.png'),
        (6, 'Tetromino_L_Right.png', 'Tetromino_L_Right_bordered.png'),
        (7, 'Tetromino_J_Up.png', 'Tetromino_J_Up_bordered.png'),
        (8, 'Tetromino_J_Left.png', 'Tetromino_J_Left_bordered.png'),
        (9, 'Tetromino_J_Down.png', 'Tetromino_J_Down_bordered.png'),
        (10, 'Tetromino_J_Right.png', 'Tetromino_J_Right_bordered.png'),
        (11, 'Tetromino_T_Up.png', 'Tetromino_T_Up_bordered.png'),
        (12, 'Tetromino_T_Left.png', 'Tetromino_T_Left_bordered.png'),
        (13, 'Tetromino_T_Down.png', 'Tetromino_T_Down_bordered.png'),
        (14, 'Tetromino_T_Right.png', 'Tetromino_T_Right_bordered.png'),
        (15, 'Tetromino_S_Horizontal.png', 'Tetromino_S_Horizontal_bordered.png'),
        (16, 'Tetromino_S_Vertical.png', 'Tetromino_S_Vertical_bordered.png'),
        (17, 'Tetromino_Z_Horizontal.png', 'Tetromino_Z_Horizontal_bordered.png'),
        (18, 'Tetromino_Z_Vertical.png', 'Tetromino_Z_Vertical_bordered.png'),
        (19, 'Tetromino_1x1_Single.png', 'Tetromino_1x1_Single_bordered.png'),
    ])
def test_get_image_path_for_piece_ids(image_loader,
                                      piece_id,
                                      expected_sticky,
                                      expected_non_sticky):


    with open(output_file, "a") as file, contextlib.redirect_stdout(file):
        # Test non-sticky variation
        # Even IDs for non-sticky
        print("\n")
        image_path_non_sticky = image_loader.get_image_path(piece_id, sticky=False)
        print(image_path_non_sticky, "and", expected_non_sticky, "\n")
        assert expected_non_sticky in image_path_non_sticky, f"Non-sticky test failed for piece_id: {piece_id}"

        # Test sticky variation
        # Odd IDs for sticky
        image_path_sticky = image_loader.get_image_path(piece_id, sticky=True)
        print(image_path_sticky, "and", expected_sticky, "\n")
        assert expected_sticky in image_path_sticky, f"Sticky test failed for piece_id: {piece_id}"
