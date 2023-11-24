import numpy as np
import random


def Tetris_Choice():  # This gives the tetris case
    choice = np.random.randint(7, size=4)  # There are 7 tetris pieces that we are rotating counterclockwise
    # 0 is the square, 1 is the line, 2 is the L, 3 is J, 4 is the T, 5 is the S, 6 is the Z
    # 0 is the original orientation, 1 is the 90 degree rotation, 2 is the 180 degree rotation, 3 is the 270 degree rotation
    return choice

# The square pivot starts in the bottom right corner. So the first rotation
# doesn't change how we place the piece.

# The line pivot is at the bottom, it starts vertically. So the first rotation is horizontal, then
# vertical again, then horizontal again.

# The L pivot is at the corner piece. The first rotation (as in, choice[1]=1) leaves the piece
# sticking out to the left.

# The J pivot is at the corner piece. The first rotation leaves the piece sticking out to
# the left.

# The T pivot is in the middle of the top row. The first rotation leaves a piece sticking out to the
# right. The second leaves the piece sticking out to the top. The third leaves the piece sticking out
# to the left.

# The S pivot is at the bottom right corner. The first rotation leaves the piece sticking out to the
# top and bottom. The second rotation leaves the piece sticking out to the left and right. The third
# rotation leaves the piece sticking out to the top and bottom.


# def Random_Deposition_2x1(width, height, steps):
#    substrate = np.zeros((height, width))
#    topmost = height - 1
#    i = 0
#
#   while i < steps:
#        position = random.randint(0, width)
#        Piece_Selection()
#
#        if choice[0] == 0 and choice[1] == 0: # Horizontal piece, left pivot. As in, the nonpivot is on the right.
#            if position != width: # Checks if the piece is in the right boundary
#                landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position + 1] == 0)) )
#                substrate[landing_row, position] = i + 1
#                substrate[landing_row, position + 1] = i + 1
#                i += 1
#            else :
#               continue
#
#        if choice[0] == 0 and choice[1] == 1: # Horizontal piece, right pivot. As in, the nonpivot is on the left.
#            if position != 0: # Need to fix this, can't compare numpy array to int.
#                landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position - 1] == 0)) )
#                substrate[landing_row, position] = i + 1
#                substrate[landing_row, position - 1] = i + 1
#                i += 1
#            else :
#                continue
#
#        if choice[0] == 1: #Vertical piece. We can safely ignore the pivot and we also don't need to check boundary conditions
#            landing_row = np.max(np.where(substrate[:, position] == 0))
#            substrate[landing_row, position] = i + 1
#            substrate[landing_row - 1, position] = i + 1 #This places a block above the first one
#
#        if landing_row < topmost:
#            topmost = landing_row
#
#        if (step + 1) % 200 == 0:
#            print(f"Step: {step + 1}/{steps}, Level at {height - topmost}/{height}")
#
#        if topmost < height * 0.10 or topmost <= 2:
#            print(f"Stopped at step {step + 1}, Level at {height - topmost}/{height}")
#            break
#
#    outputfile = f'Substrate_{width}x{height}_Particles={steps}.txt'
#    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
#    print(f"{outputfile} saved!")
#    return outputfile
#
choice = np.random.randint(7, size=4)
width = 10
height = 15

# def Random_Deposition_tetris(width, height, steps):
position = random.randint(0, width)
substrate = np.zeros((height, width))
topmost = height - 1
landing_row = np.max(np.where(substrate[:, position] == 0))
i = 0
steps = 2
choice[0] = 0
choice[1] = 0

while i < steps:
    position = random.randint(0, width)
    print('position=', position)
    Tetris_Choice()
    print(choice)

    # Square Piece
    if choice[0] == 0 and (choice[1] == 0 or choice[1] == 1):   # Square, check left boundary
        position = random.randint(0, width - 1)
        print('position=', position)
        left_column = position
        right_column = position + 1
        landing_row = np.max()
        substrate[1, 1] = 1
        substrate[5, 5] = 1

    if choice[0] == 0 and (choice[1] == 2 or choice[1] == 3):  # Square, check right boundary
        ...
    # landing_row = np.max(np.where(substrate[:, position] == 0))
    # substrate[landing_row, position] = step + 1
    # The two lines above dictate the most important part
    # of the code. This is what we need to update properly. Thinking out loud, we need to design
    # the piece that drops to simply be in the necessary shape to update the substrate. We can
    # do this by creating a function that creates the piece and then we can call it here. We
    # then can have independent if functions that check if the piece is horizontal or vertical
    # and then check if the piece is rotated or not. We can then have a function that checks
    # if the piece is in the right boundary and if it is not, then we can run the program again
    # and choose a different piece. Overlap should never be an issue if we code this right. So
    # let's do it!
    Tetris_Choice()
    i = i + 1

    if landing_row < topmost:
        topmost = landing_row

    if (steps + 1) % 200 == 0:
        print(f"Step: {steps + 1}/{steps}, Level at {height - topmost}/{height}")

    if topmost < height * 0.10 or topmost <= 2:
        print(f"Stopped at step {steps + 1}, Level at {height - topmost}/{height}")
        break
print(substrate)
#    outputfile = f'Substrate_{width}x{height}_Particles={steps}.txt'
#    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
#    print(f"{outputfile} saved!")
