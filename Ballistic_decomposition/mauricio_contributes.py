#!/usr/bin/env python3
#
# By Mauricio Montes and Chatgpt
# maumont4@gmail.com / mauricio.montes@auburn.edu
# Created at Mon Nov 20 12:38 PM CST 2023
#

import numpy as np
import argparse
import subprocess
import matplotlib.pyplot as plt

class Piece_Selection:

    substrate = np.zeros((height, width))
    topmost = height - 1

    def hor_or_vert_and_pivot(): #Chooses whether the piece is horizontal or vertical and the pivot point
        return np.random.randint(2, size =2)

    def piece_rotation():
        return np.random.randint(4)

    def the_piece():
        if hor_or_vert_and_pivot[0] == 0 and piece_drop=0 and piece_rotation == 0 or 2:
            return #Run the program again and choose a different piece

    def column_drop():
        return np.random.randint(width)

def Piece_Selection():
    choice = np.random.randint(2, size =2) 
    # This function chooses the piece that will be dropped. The piece is chosen by a random integer
    # between 0 and 1. 0 corresponds to the horizontal piece, 1 corresponds to the vertical piece,
    # The second digit corresponds to the pivot point. 0 corresponds to the left pivot point, 1
    # corresponds to the right pivot point. The function returns the choice as a list of two
    # integers. We can safely ignore the pivot when working with the vertical piece.
   if choice[0] == 0: 
       return choice
   if choice[0] == 1:
       return choice # We can safely ignore the pivot when working with the vertical piece.


def Random_Deposition_Modified(width, height, steps):
    substrate = np.zeros((height, width))
    topmost = height - 1

    for step in range(steps):
        position = np.random.randint(0, width)
        # landing_row = np.max(np.where(substrate[:, position] == 0))  <- This will have to be moved
        # to the if functions below. Definitely could be optimized, but right now I want to just get
        # things on the screen.
        Piece_Selection()

        if choice[0] == 0 and choice[1] == 0: # Horizontal piece, left pivot. As in, the nonpivot is on the right.
            landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position + 1] == 0)) )
            substrate[landing_row, position] = step + 1
            substrate[landing_row, position + 1] = step + 1

        if choice[0] == 0 and choice[1] == 1: # Horizontal piece, right pivot. As in, the nonpivot is on the left.
            landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position - 1] == 0)) )
            substrate[landing_row, position] = step + 1
            substrate[landing_row, position - 1] = step + 1

        if choice[0] == 1: #Vertical piece. We can safely ignore the pivot.
            landing_row = np.max(np.where(substrate[:, position] == 0))
            substrate[landing_row, position] = step + 1
            substrate[landing_row - 1, position] = step + 1

        # The two lines above dictate the most important part
        # of the code. This is what we need to update properly. Thinking out loud, we need to design
        # the piece that drops to simply be in the necessary shape to update the substrate. We can
        # do this by creating a function that creates the piece and then we can call it here. We
        # then can have independent if functions that check if the piece is horizontal or vertical
        # and then check if the piece is rotated or not. We can then have a function that checks
        # if the piece is in the right boundary and if it is not, then we can run the program again
        # and choose a different piece. Overlap should never be an issue if we code this right. So
        # let's do it!       
        


        if landing_row < topmost:
            topmost = landing_row

        if (step + 1) % 200 == 0:
            print(f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f'Substrate_{width}x{height}_Particles={steps}.txt'
    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
    print(f"{outputfile} saved!")
    return outputfile

def Random_Deposition(width, height, steps):
    substrate = np.zeros((height, width))
    topmost = height - 1

    for step in range(steps):
        position = np.random.randint(0, width)
        landing_row = np.max(np.where(substrate[:, position] == 0)) 
        substrate[landing_row, position] = step + 1 
        # The two lines above dictate the most important part
        # of the code. This is what we need to update properly. Thinking out loud, we need to design
        # the piece that drops to simply be in the necessary shape to update the substrate. We can
        # do this by creating a function that creates the piece and then we can call it here. We
        # then can have independent if functions that check if the piece is horizontal or vertical
        # and then check if the piece is rotated or not. We can then have a function that checks
        # if the piece is in the right boundary and if it is not, then we can run the program again
        # and choose a different piece. Overlap should never be an issue if we code this right. So
        # let's do it!       
        


        if landing_row < topmost:
            topmost = landing_row

        if (step + 1) % 200 == 0:
            print(f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.10 or topmost <= 2:
            print(f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
            break

    outputfile = f'Substrate_{width}x{height}_Particles={steps}.txt'
    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
    print(f"{outputfile} saved!")
    return outputfile


