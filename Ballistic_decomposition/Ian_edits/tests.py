import numpy as np
import random


def Tetris_Choice():  # This gives the tetris case
    choice = np.random.randint(
        7, size=4
    )  # There are 7 tetris pieces that we are rotating counterclockwise
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
width = 8
height = 8


def ffnz(
    matrix, height, column
):  # ffnz finds the first nonzero entry in a fixed column
    i = 0
    j = 0
    while j == 0:
        if matrix[i, column] == 0:
            i = i + 1
        else:
            j = i
    return j


# def Random_Deposition_tetris(width, height, steps):
position = random.randint(0, width)
substrate = np.zeros((height, width))
topmost = height - 1
landing_row = np.max(np.where(substrate[:, position] == 0))

i = 0
steps = 1
choice[0] = 0
choice[1] = 0
substrate[3, 3] = 11
substrate[4, 3] = 11
substrate[5, 3] = 11
substrate[6, 0] = 11
substrate[6, 1] = 0
substrate[6, 3] = 11
substrate[6, 6] = 11
substrate[7, 0] = 11
substrate[7, 1] = 0
substrate[7, 2] = 11
substrate[7, 3] = 11
substrate[7, 4] = 11
substrate[7, 5] = 11
substrate[7, 6] = 11
substrate[4, 2] = 11
substrate[2, 6] = 11
print(substrate)
print("ffnz=", ffnz(substrate, height, 2))
print("ffnz=", ffnz(substrate, height, 6))
step = 1  # This is the counter that goes in each piece
while i < steps:
    position = random.randint(0, width)
    # print('position=', position)
    Tetris_Choice()
    print(choice)
    border_hit = False

    # Square Piece
    if choice[0] == 0 and (
        choice[1] == 0 or choice[1] == 1
    ):  # Square, check left boundary
        # position = random.randint(0, width)
        position = 0
        print("position=", position)
        if position != (width - 1):
            if position == 0:
                mleft_column = position
                mright_column = position + 1
                right_column = position + 2
                max_mleft_column = ffnz(substrate, height, mleft_column)
                print("max mlcol=", max_mleft_column)
                max_mright_column = ffnz(substrate, height, mright_column)
                print("max_mrcol=", max_mright_column)
                max_right_column = ffnz(substrate, height, right_column)
                print("max_rc=", max_right_column)
                if (max_right_column < mright_column) and (
                    max_right_column < mleft_column
                ):
                    substrate[max_right_column, position] = step
                    substrate[max_right_column, position + 1] = step
                    substrate[max_right_column + 1, position] = step
                    substrate[max_right_column + 1, position + 1] = step
            elif position == width - 1:
                left_column = position - 1
                mleft_column = position
                mright_column = position + 1
                max_left_column = np.max(np.where(substrate[:, left_column] == 0))
                print("max lc=", max_left_column)
                max_mleft_column = np.max(np.where(substrate[:, mleft_column] == 0))
                print("max mlcol=", max_mleft_column)
                max_mright_column = np.max(np.where(substrate[:, mright_column] == 0))
                print("max_mrcol=", max_mright_column)
            else:
                left_column = position - 1
                mleft_column = position
                mright_column = position + 1
                right_column = position + 2
                max_left_column = np.max(np.where(substrate[:, left_column] == 0))
                print("max lc=", max_left_column)
                max_mleft_column = np.max(np.where(substrate[:, mleft_column] == 0))
                print("max mlcol=", max_mleft_column)
                max_mright_column = np.max(np.where(substrate[:, mright_column] == 0))
                print("max_mrcol=", max_mright_column)
                max_right_column = np.max(np.where(substrate[:, right_column] == 0))
                print("max_rc=", max_right_column)
                # landing_row = np.max()
        else:
            border_hit = True  # A border was hit by the piece, so we must discard it and not augment the counter
            print("borderhit=", border_hit)

    if choice[0] == 0 and (
        choice[1] == 2 or choice[1] == 3
    ):  # Square, check right boundary
        ...
    # landing_row = np.max(np.where(substrate[:, position] == 0))
    # substrate[landing_row, position] = step + 1
    Tetris_Choice()
    if (
        not border_hit
    ):  # If we didn't hit a border with a piece, all the counters increase by 1
        i = i + 1  # This is the counter of steps
        step = step + 1  # This is the counter that goes in each piece

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
