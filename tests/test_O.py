#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Fri Jan 26 02:17:33 PM EST 2024
#

import pytest
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def Test_O(self):
    """
    This is a test function for the square piece.
    """
    TB = Tetris_Ballistic()

    print("First, the sticky case:")
    for rot in range(4):
        print("O piece, Test rotation ", rot)
        TB.reset()
        i = 0
        while i < TB.steps:
            i = TB.Update_O(i, sticky=True)
            if i == -1:
                print("Game Over, reach the top")
                break
        print(self.substrate)
        input("")

    print("Second, the non-sticky case:")
    for rot in range(4):
        print("O piece, Test rotation ", rot)
        TB.reset()
        i = 0
        while i < TB.steps:
            i = TB.Update_O(i, sticky=False)
            if i == -1:
                print("Game Over, reach the top")
                break
        print(self.substrate)
        input("")
