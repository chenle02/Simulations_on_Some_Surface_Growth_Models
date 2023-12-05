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
import random


def Piece_Selection(): #This gives the 2x1 case
    choice = np.random.randint(2, size =2)
    # This function chooses the piece that will be dropped. The piece is chosen by a random integer
    # between 0 and 1. 0 corresponds to the horizontal piece, 1 corresponds to the vertical piece,
    # The second digit corresponds to the pivot point. 0 corresponds to the left pivot point, 1
    # corresponds to the right pivot point. The function returns the choice as a list of two
    # integers. We can safely ignore the pivot when working with the vertical piece.
    return choice

def Tetris_Choice(): #This gives the tetris case
    choice = np.random.randint(7, size =4) #There are 7 tetris pieces that we are rotating counterclockwise
    # 0 is the square, 1 is the line, 2 is the L, 3 is the reverse L, 4 is the T, 5 is the S, 6 is the Z
    # 0 is the original orientation, 1 is the 90 degree rotation, 2 is the 180 degree rotation, 3 is the 270 degree rotation
    return choice

# The square pivot starts in the bottom right corner. So the first rotation doesn't change how we place the piece

# The line pivot is at the bottom, it starts vertically. So the first rotation is horizontal, then
# vertical again, then horizontal again.

# The L pivot is at the corner piece. The first rotation (as in, choice[1]=1) leaves the piece
# sticking out to the left

# The reverse L pivot is at the corner piece. The first rotation leaves the piece sticking out to
# the left

# The T pivot is in the middle of the top row. The first rotation leaves a piece sticking out to the
# right. The second leaves the piece sticking out to the top. The third leaves the piece sticking out
# to the left.

# The S pivot is at the bottom right corner. The first rotation leaves the piece sticking out to the
# top and bottom. The second rotation leaves the piece sticking out to the left and right. The third
# rotation leaves the piece sticking out to the top and bottom.


def Random_Deposition_2x1(width, height, steps):# {{{
    substrate = np.zeros((height, width))
    topmost = height - 1
    i = 0

   while i < steps:
        position = random.randint(0, width)
        Piece_Selection()

        if choice[0] == 0 and choice[1] == 0: # Horizontal piece, left pivot. As in, the nonpivot is on the right.
            if position != width: # Checks if the piece is in the right boundary
                landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position + 1] == 0)) )
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position + 1] = i + 1
                i += 1
            else :
               continue

        if choice[0] == 0 and choice[1] == 1: # Horizontal piece, right pivot. As in, the nonpivot is on the left.
            if position != 0: # Need to fix this, can't compare numpy array to int.
                landing_row = np.minimum( np.max(np.where(substrate[:, position] == 0)), np.max(np.where(substrate[:, position - 1] == 0)) )
                substrate[landing_row, position] = i + 1
                substrate[landing_row, position - 1] = i + 1
                i += 1
            else :
                continue

        if choice[0] == 1: #Vertical piece. We can safely ignore the pivot and we also don't need to check boundary conditions
            landing_row = np.max(np.where(substrate[:, position] == 0))
            substrate[landing_row, position] = i + 1
            substrate[landing_row - 1, position] = i + 1 #This places a block above the first one

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
    return outputfile# }}}

def Random_Deposition_tetris(width, height, steps):# {{{
    substrate = np.zeros((height, width))
    topmost = height - 1
    i = 0

   while i < steps:
        position = random.randint(0, width)
        Tetris_Choice()

        # Square Piece {{{
        if choice[0] == 0 and (choice[1] == 0 or choice[1]=1): # Square, check left boundary
            ...

        if choice[0] == 0 and (choice[1] == 2 or choice[1]=3): # Square, check right boundary
            ...# }}}

        # Line Piece {{{
        if choice[0] == 1 and (choice[1] == 0 or choice[1]=2): # Line, vertical position
            ...

        if choice[0] == 1 and choice[1] == 1: # Line, horizontal position, check left boundary
            ...

        if choice[0] == 1 and choice[1] == 3: # Line, horizontal position, check right boundary
            ...# }}}

        # L piece{{{
        if choice[0] == 2 and choice[1] == 0: # L, upright position, check right boundary
            ...

        if choice[0] == 2 and choice[1] == 1: # L, horizontal position, check left boundary
            ...

        if choice[0] == 2 and choice[1] == 2: # L, upside down position, check left boundary
            ...

        if choice[0] == 2 and choice[1] == 3: # L, horizontal position, check right boundary
            ...# }}}

        # Reverse L{{{
        if choice[0] == 3 and choice[1] == 0: # Reverse L, upright position, check left boundary
            ...

        if choice[0] == 3 and choice[1] == 1: # Reverse L, horizontal position, check left boundary
            ...

        if choice[0] == 3 and choice[1] == 2: # Reverse L, upside down position, check right boundary
            ...

        if choice[0] == 3 and choice[1] == 3: # Reverse L, horizontal position, check right boundary
            ...# }}}

        # T piece{{{
        if choice[0] == 4 and choice[1] == 0: # T, upright position, check left and right boundary
            ...

        if choice[0] == 4 and choice[1] == 1: # T, horizontal position, check right boundary
            ...

        if choice[0] == 4 and choice[1] == 2: # T, upside down position, check left and right boundary
            ...

        if choice[0] == 4 and choice[1] == 3: # T, horizontal position, check left boundary
            ...# }}}

        # S Piece{{{
        if choice[5] == 5 and choice[1] == 0: # Z, horizontal position, check left and right boundary
            ...

        if choice[5] == 5 and choice[1] == 1: # Z, vertical position, check left boundary
            ...

        if choice[5] == 5 and choice[1] == 2: # Z, horizontal position, check left and right boundary
            ...

        if choice[5] == 5 and choice[1] == 3: # Z, vertical position, check right boundary
            ...# }}}

        # Z piece{{{
        if choice[5] == 6 and choice[1] == 0: # Z, horizontal position, check left and right boundary
            ...

        if choice[5] == 6 and choice[1] == 1: # Z, vertical position, check left boundary
            ...

        if choice[5] == 6 and choice[1] == 2: # Z, horizontal position, check left and right boundary
            ...

        if choice[5] == 6 and choice[1] == 3: # Z, vertical position, check right boundary
            ...# }}}

        #landing_row = np.max(np.where(substrate[:, position] == 0))
        #substrate[landing_row, position] = step + 1
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
    return outputfile# }}}

def interface_width(filename):# {{{
    # Main function to visualize the simulation
    # Load substrate from file
    substrate = np.loadtxt(filename, delimiter=',')

    # Parameters
    height, width = substrate.shape
    print(f"Height: {height}, Width: {width}")
    steps = int(np.max(substrate))
    interface = np.zeros(steps)

    # Compute the interface width
    for step in range(1, steps + 1):
        # Create a copy of the substrate for visualization
        vis_substrate = np.copy(substrate)

        # Replace values greater than the current step with 0
        vis_substrate[vis_substrate > step] = 0

        top_envelope = Envelop(vis_substrate)
        average = np.mean(top_envelope)

        interface[step - 1] = 0
        for pos in range(width):
            interface[step - 1] += np.power(top_envelope[pos] - average, 2) / width
        interface[step - 1] = np.sqrt(interface[step - 1])

    # Assuming 'time' is your x-axis data and 'interface' is your y-axis data
    time = np.array(range(1, steps + 1))
    quarter_length = len(time) // 4  # Compute the one-fourth point

    slopes = []

    # Loop from one-fourth of t to all t
    for end in range(quarter_length, len(time) + 1):
        current_time = time[:end]
        current_interface = interface[:end]

        log_time = np.log(current_time)
        log_interface = np.log(current_interface)

        # Fit a linear regression to the log-log data of the current window
        slope, _ = np.polyfit(log_time, log_interface, 1)
        slopes.append(slope)

    # Convert slopes to a numpy array for further processing if needed
    slopes = np.array(slopes)

    # Create side-by-side plots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # First plot: log-log plot of the interface width
    ax1.loglog(time, interface, '-o', label='Interface Width')
    ax1.set_xlabel('Log of Time (log(t)')
    ax1.set_ylabel('Interface Width in log')
    ax1.set_title('Log-Log plot of Interface Width vs Time')
    ax1.grid(True)

    # Second plot: slopes
    ax2.plot(time[quarter_length - 1:], slopes, '-o', label='Computed Slopes')
    # ax2.axhline(y=reference_slope, color='r', linestyle='--', label=f'Reference Slope {reference_slope}')
    ax2.axhline(y=1 / 2, color='r', linestyle='--', label='Reference Slope 1/2')
    ax2.axhline(y=1 / 3, color='r', linestyle='--', label='Reference Slope 1/3')
    ax2.axhline(y=1 / 4, color='r', linestyle='--', label='Reference Slope 1/4')
    ax2.set_xlabel('Time (t)')
    ax2.set_ylabel('Slope')
    ax2.set_title('Slope of the log-log plot as a function of log(t)')
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(filename.replace('.txt', '.png'), dpi=300)
    # plt.show()

    return interface# }}}


def Envelop(substrate):# {{{
    # Compute the envelop of the substrate
    height, width = substrate.shape
    top_envelope = np.zeros(width)
    for pos in range(width):
        if np.any(substrate[:, pos] > 0):  # If there's any nonzero value in the column
            top_envelope[pos] = np.argmax(substrate[:, pos] > 0) - 3
        else:
            top_envelope[pos] = height - 2
    return top_envelope# }}}


def main():# {{{
    parser = argparse.ArgumentParser(description="""

    Simulate Random Deposition on a substrate.
    Outputs: 1. Substrate_WIDTHxHEIGHT_Particles=STEPS_[Relaxed/BD].txt
                A text file for the substrate.
             2. Statistical figures, loglog plot for the interface width and the estimated slope.

    Author: Le Chen (le.chen@auburn.edu, chenle02@gmail.com)
    Date: 2023-10-22


                                     """, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-w", "--width", type=int, default=100, help="Width of the substrate (default: 100)")
    parser.add_argument("-e", "--height", type=int, default=60, help="Maximum height of the substrate (default: 60)")
    parser.add_argument("-s", "--steps", type=int, default=5000, help="Number of particles to drop (default: 5000)")
    parser.add_argument("--relax", action="store_true", help="Surface Relaxation: go to the nearest lowest neighbor (default: False)")
    parser.add_argument("--BD", action="store_true", help="Ballistic decomposition (default: False)")
    parser.add_argument("-m", "--movie", action="store_true", help="Generate the mp4 movie (default: False)")
    args = parser.parse_args()

    Outputfile = ""
    if args.relax:
        Title = "Random Decomposition with Surface Relaxation"
        Outputfile = Random_Deposition_Surface_Relaxation(args.width, args.height, args.steps)
        print(Title)
    elif args.BD:
        Title = "Ballistic Decomposition"
        Outputfile = Ballistic_Deposition(args.width, args.height, args.steps)
        print(Title)
    else:
        Title = "Random Decomposition"
        Outputfile = Random_Deposition(args.width, args.height, args.steps)
        print(Title)

    print("Computing the interface width...")
    interface_width(Outputfile)

    if args.movie:
        print("Generating the movie...")
        cmd = [
            'python3', 'mauricio_contributes.py',
            '--file', Outputfile,
            '--title', Title,
            '--envelop',
            '--average',
        ]
        subprocess.run(cmd)
    else:
        print("Do not generate the movie.")# }}}


if __name__ == "__main__":
    main()
