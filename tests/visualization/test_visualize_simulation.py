#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 02:17:33 PM EST 2024
#

import pytest
import contextlib
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def test_visualize_simulation():
    """
    This is a test function for the square piece.
    """
    output_file = "test_visualize_simulation_output.txt"

    with open(output_file, "w") as file, contextlib.redirect_stdout(file):

        TB = Tetris_Ballistic(seed=42, width=10, height=20, steps=200)
        TB.save_config("test_visualize_simulation_config.yaml")

        ListUpdate = [TB.Update_1x1,
                      TB.Update_O,
                      TB.Update_I,
                      TB.Update_T,
                      TB.Update_L,
                      TB.Update_J,
                      TB.Update_S,
                      TB.Update_Z]

        print("Sticky case first:\n")
        for Update in ListUpdate:
            print(f"First, the sticky case of {Update.__name__} piece:")
            TB.reset()
            i = 0
            while i < TB.steps:
                i = Update(i, rot=0, sticky=True)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.visualize_simulation(video_filename=f"{Update.__name__}_sticky.mp4",
                                    plot_title=f"{Update.__name__} sticky")

        print("Non-sticky case now:\n")
        for Update in ListUpdate:
            print(f"First, the sticky case of {Update.__name__} piece:")
            TB.reset()
            i = 0
            while i < TB.steps:
                i = Update(i, rot=0, sticky=False)
                if i == -1:
                    print("Game Over, reach the top")
                    break
            TB.visualize_simulation(video_filename=f"{Update.__name__}_Non-sticky.mp4",
                                    plot_title=f"{Update.__name__} Non-sticky")

        # print("First, the sticky case of 1x1 piece:")
        # TB.reset()
        # i = 0
        # while i < TB.steps:
        #     i = TB.Update_1x1(i, sticky=True)
        #     if i == -1:
        #         print("Game Over, reach the top")
        #         break
        # TB.visualize_simulation(video_filename="1x1_sticky.mp4", title="1x1 sticky")

        # print("Second, the non-sticky case of 1x1 piece:")
        # TB.reset()
        # i = 0
        # while i < TB.steps:
        #     i = TB.Update_1x1(i, sticky=False)
        #     if i == -1:
        #         print("Game Over, reach the top")
        #         break
        # TB.visualize_simulation(video_filename="1x1_Non-sticky.mp4", title="1x1 Non-sticky)
