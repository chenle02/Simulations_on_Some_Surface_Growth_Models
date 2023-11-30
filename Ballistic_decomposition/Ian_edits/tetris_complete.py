import numpy as np
import random
#Hi Ian

def Tetris_Choice():  # This gives the tetris case
    choice = np.random.randint(1, [7,4])  # There are 7 tetris pieces that we are rotating counterclockwise
    # 0 is the square, 1 is the line, 2 is the L, 3 is J, 4 is the T, 5 is the S, 6 is the Z
    # 0 is the original orientation, 1 is the 90 degree rotation, 2 is the 180 degree rotation, 3 is the 270 degree rotation
    return choice

width = 100
height = 1000

def ffnz(matrix, height, column):  # ffnz Finds the First NonZero entry in a fixed column
    i = 0
    flag = height
    while (flag == height) and (i < height):
        if matrix[i, column] == 0:
            i = i + 1
        else:
            flag = i
    return flag

substrate = np.zeros((height, width))
topmost = height - 1 

i = 0
steps = 2000
#choice[0] = 6
#choice[1] = 3
substrate[11, 3] = 11
substrate[12, 3] = 11
substrate[13, 3] = 11
substrate[14, 0] = 11
substrate[14, 1] = 0
substrate[14, 3] = 11
substrate[14, 6] = 11
substrate[15, 0] = 11
substrate[15, 1] = 0
substrate[15, 2] = 11
substrate[15, 3] = 11
substrate[15, 4] = 11
substrate[15, 5] = 11
substrate[15, 6] = 11
substrate[12, 2] = 11
substrate[10, 6] = 11
print(substrate)


def Tetris_RD(width, height, steps):
    i = 0
    substrate = np.zeros((height, width))
    topmost = height - 1 
    while i < steps:
        choice = Tetris_Choice()
        print(choice)

        # Square Piece
        if choice[0] == 0 and (choice[1] == 0 or choice[1] == 1):   # Square, check right boundary
            position = random.randint(0, width-1)
            #position = 4
            print('position=', position)
            if position != (width - 1):
                #Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position + 1)) - 1

                substrate[landing_row - 1, position] = i + 1
                substrate[landing_row, position] = i + 1
                substrate[landing_row - 1, position + 1] = i + 1
                substrate[landing_row, position + 1] = i + 1

                i += 1

            else:
                continue

        if choice[0] == 0 and (choice[1] == 2 or choice[1] == 3):  # Square, check left boundary
            position = random.randint(0, width-1)
            #position = 4
            print('position=', position)
            if position != 0:
                #Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position - 1)) - 1

                substrate[landing_row - 1, position] = i + 1
                substrate[landing_row, position] = i + 1
                substrate[landing_row - 1, position - 1] = i + 1
                substrate[landing_row, position - 1] = i + 1

                i += 1
            else: 
                continue

        if choice[0] == 1 and (choice[1] == 0 or choice[1] == 2):   # Vertical, check ceiling case 
            position = random.randint(0, width-1)
            #position = 7
            print('position=', position)
            landing_row = ffnz(substrate, height, position) - 1
            if landing_row >= 3:
                substrate[landing_row, position] = i + 1
                substrate[landing_row - 1 , position] = i + 1
                substrate[landing_row - 2, position] = i + 1
                substrate[landing_row - 3, position] = i + 1
                i += 1
            else:
               break 

        if choice[0] == 1 and choice[1] == 1 :  # Line with right pivot, check left boundary
            position = random.randint(0, width-1)
            # position = 6
            print('position=', position)
            if position - 3 >= 0:
                #Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position - 1), ffnz(substrate, height, position - 2), ffnz(substrate, height, position - 3)) - 1

                substrate[landing_row, position] = i + 1
                substrate[landing_row, position - 1] = i + 1
                substrate[landing_row, position - 2] = i + 1
                substrate[landing_row, position - 3] = i + 1

                i += 1
            else: 
                continue

        if choice[0] == 1 and choice[1] == 3 :  # Line with left pivot, check right boundary
            position = random.randint(0, width-1)
            # position = 6
            print('position=', position)
            if position + 3 <= width - 1:
                #Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position + 1), ffnz(substrate, height, position + 2), ffnz(substrate, height, position + 3)) - 1

                substrate[landing_row, position] = i + 1
                substrate[landing_row, position + 1] = i + 1
                substrate[landing_row, position + 2] = i + 1
                substrate[landing_row, position + 3] = i + 1

                i += 1
            else: 
                continue

       #L Case 
        if choice[0] == 2 and choice[1] == 0 :  # L case upright, check right boundary
            position = random.randint(0, width-1)
            # position = 6
            print('position=', position)
            if position + 1 <= width - 1:
                #Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position + 1)) - 1 

                if landing_row >= 2:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row, position + 1] = i + 1
                    substrate[landing_row - 1, position] = i + 1
                    substrate[landing_row - 2, position] = i + 1

                    i += 1
                else: 
                    break 
            else:
                continue

        if choice[0] == 2 and choice[1] == 1 :  # L case laying down, check left boundary
            position = random.randint(0, width-1)
            # position = 6
            print('position=', position)
            if position != 0 and position != 1:
                #Pass function through here
                landing_row = ffnz(substrate, height, position) - 1 

                if landing_row >= 1:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row - 1 , position] = i + 1
                    substrate[landing_row, position - 1] = i + 1
                    substrate[landing_row, position - 2] = i + 1

                    i += 1
                else: 
                    break 
            else:
                continue

        if choice[0] == 2 and choice[1] == 2 :  # L case standing up, check left boundary
            position = random.randint(0, width-1)
            # position = 6
            print('position=', position)
            if position != 0:
                #Pass function through here
                landing_row_right = ffnz(substrate, height, position) - 1 
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_right, landing_row_left)

                if min(landing_row_right, landing_row_left) <= 2:
                    break
                
                elif landing_row_left < landing_row_right - 1:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1
                    substrate[landing_row_left + 2, position] = i + 1

                    i += 1

                else:
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 2, position] = i + 1
                    substrate[landing_row_right - 2, position - 1] = i + 1

                    i += 1
            else:
                continue

        if choice[0] == 2 and choice[1] == 3:  # L case laying down, check right boundary
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position != width - 1 and position != width - 2:
                # Pass function through here
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_right_2 = ffnz(substrate, height, position + 2) - 1
                landing_row = min (landing_row_pivot, landing_row_right, landing_row_right_2)
                print(landing_row_pivot, landing_row_right, landing_row_right_2, landing_row)

                if landing_row_pivot <= landing_row_right and landing_row_pivot <= landing_row_right_2:
                    substrate[landing_row_pivot, position] = i + 1
                    print("help help!")
                    substrate[landing_row_pivot - 1, position] = i + 1
                    substrate[landing_row_pivot - 1, position + 1] = i + 1
                    substrate[landing_row_pivot - 1, position + 2] = i + 1
                    i += 1

                elif landing_row_right < landing_row_pivot and landing_row_right <= landing_row_right_2:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position + 2] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    i += 1

                elif landing_row_right_2 < landing_row_pivot and landing_row_right_2 <= landing_row_right:
                    substrate[landing_row_right_2, position + 1] = i + 1
                    substrate[landing_row_right_2, position + 2] = i + 1
                    substrate[landing_row_right_2, position] = i + 1
                    print("find me")
                    substrate[landing_row_right_2 + 1, position] = i + 1
                    i += 1
                else:
                  continue 

            else:
                continue

        if choice[0] == 3 and choice[1] == 0:  # J case upright, check left boundary
            position = random.randint(0, width - 1)
            # position = 6
            print('position=', position)
            if position != 0:
                # Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position - 1)) - 1

                if landing_row >= 2:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row, position - 1] = i + 1
                    substrate[landing_row - 1, position] = i + 1
                    substrate[landing_row - 2, position] = i + 1

                    i += 1
                else:
                    break
            else:
                continue

        if choice[0] == 3 and choice[1] == 1:  # J case long part on top, check left boundary
            position = random.randint(0, width - 1)
            #position = 7
            print('position=', position)
            if position - 2 >= 0:
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position - 2) - 1
                landing_row_center = ffnz(substrate, height, position - 1) - 1
                landing_row_right = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_left, landing_row_center, landing_row_right)

                if (landing_row_left <= landing_row_center) and (landing_row_left < landing_row_right):
                    substrate[landing_row_left, position - 2] = i + 1
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1

                    i += 1
                elif (landing_row_center <= landing_row_left) and (landing_row_center < landing_row_right):
                    substrate[landing_row_center, position - 1] = i + 1
                    substrate[landing_row_center, position - 2] = i + 1
                    substrate[landing_row_center, position] = i + 1
                    substrate[landing_row_center + 1, position] = i + 1
                    i += 1
                elif (landing_row_right <= landing_row_left) and (landing_row_right <= landing_row_center):
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 1, position - 1] = i + 1
                    substrate[landing_row_right - 1, position - 2] = i + 1
                    i += 1

                else:
                   continue 
            else:
                continue
        if choice[0] == 3 and choice[1] == 2:  # J case long part on the left, check right boundary
            position = random.randint(0, width - 1)
            # position = 7
            print('position=', position)
            if position != width - 1:
                # Pass function through here
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_left = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_right, landing_row_left)
                print('lrr=', landing_row_right)
                print('lrl=', landing_row_left)

                if min(landing_row_right, landing_row_left) <= 2:
                    break

                elif landing_row_right <= landing_row_left - 2:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    substrate[landing_row_right + 2, position] = i + 1

                    i += 1

                else:
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left - 2, position] = i + 1
                    substrate[landing_row_left - 2, position + 1] = i + 1

                    i += 1
            else:
                continue
        if choice[0] == 3 and choice[1] == 3:  # J case long part on the bottom, check right boundary
            position = random.randint(0, width - 1)
            # position = 7
            print('position=', position)
            if position + 2 <= width - 1:
                # Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position + 1), ffnz(substrate, height, position + 2)) - 1

                if landing_row >= 1:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row - 1, position] = i + 1
                    substrate[landing_row, position + 1] = i + 1
                    substrate[landing_row, position + 2] = i + 1

                    i += 1
                else:
                    break
            else:
                continue

    # T case

        if choice[0] == 4 and choice[1] == 0:  # T case long part on top, check left and right boundaries
            position = random.randint(0, width - 1)
            # position = 7
            print('position=', position)
            if (position != width - 1) and (position != 0):
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_center = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_right, landing_row_left, landing_row_center)

                if (landing_row_left < landing_row_center) and (landing_row_left <= landing_row_right):
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left, position + 1] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1

                    i += 1
                elif (landing_row_center <= landing_row_left) and (landing_row_center <= landing_row_right):
                    substrate[landing_row_center, position] = i + 1
                    substrate[landing_row_center - 1, position - 1] = i + 1
                    substrate[landing_row_center - 1, position] = i + 1
                    substrate[landing_row_center - 1, position + 1] = i + 1
                    i += 1
                elif (landing_row_right <= landing_row_left) and (landing_row_right < landing_row_center):
                    substrate[landing_row_right, position - 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    i += 1

                else:
                   continue 
            else:
                continue
        if choice[0] == 4 and choice[1] == 1:  # T case long part on the left, check right boundary
            position = random.randint(0, width - 1)
            # position = 7
            print('position=', position)
            if position != width - 1:
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_right, landing_row_left)
                print('lrr=', landing_row_left)
                print('lrl=', landing_row_right)

                if min(landing_row_right, landing_row_left) < 2:
                    break

                elif landing_row_right < landing_row_left:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1

                    i += 1
                elif landing_row_right >= landing_row_left:
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left - 2, position] = i + 1
                    substrate[landing_row_left - 1, position + 1] = i + 1
                    i += 1
                else:
                    continue
        if choice[0] == 4 and choice[1] == 2:  # T case long part on the bottom, check left and right boundaries
            position = random.randint(0, width - 1)
            # position = 4
            print('position=', position)
            if (position != 0) and (position != width - 1):
                # Pass function through here
                landing_row = min(ffnz(substrate, height, position), ffnz(substrate, height, position + 1), ffnz(substrate, height, position - 1)) - 1

                if landing_row >= 1:
                    substrate[landing_row, position] = i + 1
                    substrate[landing_row, position + 1] = i + 1
                    substrate[landing_row, position - 1] = i + 1
                    substrate[landing_row - 1, position] = i + 1

                    i += 1
                else:
                    break
            else:
                continue
        if choice[0] == 4 and choice[1] == 3:  # T case long part on the right, check left boundary
            position = random.randint(0, width - 1)
            # position = 7
            print('position=', position)
            if position != 0:
                # Pass function through here
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_right = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_right, landing_row_left)
                print('lrl=', landing_row_left)
                print('lrr=', landing_row_right)

                if min(landing_row_right, landing_row_left) < 2:
                    break

                elif landing_row_right > landing_row_left:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1

                    i += 1
                elif landing_row_right <= landing_row_left:
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 2, position] = i + 1
                    substrate[landing_row_right - 1, position - 1] = i + 1
                    i += 1
                else:
                    continue
            else:
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row_right = ffnz(substrate, height, position) - 1
                landing_row = min(landing_row_right, landing_row_left)
                continue


            # S Case
        if choice[0] == 5 and (choice[1] == 0 or choice[1] == 2):  # S case laying down, check left and right boundary
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position + 1 <= width - 1 and position - 1 >= 0: #Check left and right bdy
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_right and landing_row_pivot <= landing_row_left:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot, position - 1] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi")
                    substrate[landing_row_pivot - 1, position + 1] = i + 1
                    i += 1

                elif landing_row_right < landing_row_pivot and landing_row_right < landing_row_left:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    print("Hi2")
                    substrate[landing_row_right + 1, position - 1] = i + 1
                    i += 1

            else:
                continue

    #NEED TO FIX CEILING ISSUES HERE
        if choice[0] == 5 and choice[1] == 1: # S case standing up, pivot on the right, check left boundary SEE Z CASE 
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position - 1 >= 0:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_left - 1: 
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi")
                    substrate[landing_row_pivot - 1, position - 1] = i + 1
                    substrate[landing_row_pivot - 2, position - 1] = i + 1
                    i += 1

                elif landing_row_left + 1 < landing_row_pivot:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position - 1] = i + 1
                    print("Hi2")
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1
                    i += 1
            else:
                continue

        if choice[0] == 5 and choice[1] == 3: # S case standing up, pivot on the left, check right boundary SEE Z CASE 
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position + 1 <= width - 1:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_right: 
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi")
                    substrate[landing_row_pivot, position + 1] = i + 1
                    substrate[landing_row_pivot + 1, position + 1] = i + 1
                    i += 1

                elif landing_row_right <= landing_row_pivot:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position + 1] = i + 1
                    print("Hi2")
                    substrate[landing_row_right - 1, position] = i + 1
                    substrate[landing_row_right - 2, position] = i + 1
                    i += 1
            else:
                continue


            # Z Case

        if choice[0] == 6 and (choice[1] == 0 or choice[1] == 2):  # Z case laying down, check left and right boundary
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position + 1 <= width - 1 and position - 1 >= 0: #Check left and right bdy
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_pivot < landing_row_left and landing_row_pivot <= landing_row_right:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot, position + 1] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi")
                    substrate[landing_row_pivot - 1, position - 1] = i + 1
                    i += 1

                elif landing_row_left < landing_row_pivot and landing_row_left < landing_row_right:
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left, position] = i + 1
                    substrate[landing_row_left + 1, position] = i + 1
                    print("Hi2")
                    substrate[landing_row_left + 1, position + 1] = i + 1
                    i += 1

                elif landing_row_right <= landing_row_pivot and landing_row_right < landing_row_left:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right - 1, position] = i + 1
                    print("Hi2")
                    substrate[landing_row_right - 1, position - 1] = i + 1
                    i += 1

            else:
                continue


        if choice[0] == 6 and choice[1] == 1: # Z case standing up, pivot on the right, check left boundary SEE S CASE  
            position = random.randint(0, width - 1)
            #position = 1
            print('position=', position)
            if position - 1 >= 0:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_left = ffnz(substrate, height, position - 1) - 1
                landing_row = min(landing_row_pivot, landing_row_left)

                if landing_row <= 2:
                    break

                if landing_row_left <= landing_row_pivot: 
                    substrate[landing_row_left, position - 1] = i + 1
                    substrate[landing_row_left - 1, position - 1] = i + 1
                    print("Hi")
                    substrate[landing_row_left - 1, position] = i + 1
                    substrate[landing_row_left - 2, position] = i + 1
                    i += 1

                elif landing_row_pivot < landing_row_left:
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi2")
                    substrate[landing_row_pivot, position - 1] = i + 1
                    substrate[landing_row_pivot + 1, position - 1] = i + 1
                    i += 1
            else:
                continue

        if choice[0] == 6 and choice[1] == 3: # Z case standing up, pivot on the left, check right boundary SEE S CASE
            position = random.randint(0, width - 1)
            #position = 3
            print('position=', position)
            if position + 1 <= width - 1:
                landing_row_pivot = ffnz(substrate, height, position) - 1
                landing_row_right = ffnz(substrate, height, position + 1) - 1
                landing_row = min(landing_row_pivot, landing_row_right)

                if landing_row <= 2:
                    break

                if landing_row_pivot <= landing_row_right: 
                    substrate[landing_row_pivot, position] = i + 1
                    substrate[landing_row_pivot - 1, position] = i + 1
                    print("Hi")
                    substrate[landing_row_pivot - 1, position + 1] = i + 1
                    substrate[landing_row_pivot - 2, position + 1] = i + 1
                    i += 1

                elif landing_row_right < landing_row_pivot:
                    substrate[landing_row_right, position + 1] = i + 1
                    substrate[landing_row_right - 1, position + 1] = i + 1
                    print("Hi2")
                    substrate[landing_row_right, position] = i + 1
                    substrate[landing_row_right + 1, position] = i + 1
                    i += 1
            else:
                continue


        if landing_row < topmost:
            topmost = landing_row

        if (steps + 1) % 200 == 0:
            print(f"Step: {steps + 1}/{steps}, Level at {height - topmost}/{height}")

        if topmost < height * 0.05 or topmost <= 2:
            print(f"Stopped at step {steps + 1}, Level at {height - topmost}/{height}")
            break


    outputfile = f'Tetris_Substrate_{width}x{height}_Particles={steps}.txt'
    np.savetxt(outputfile, substrate, fmt='%d', delimiter=',')
    print(f"{outputfile} saved!")
    return outputfile


print(substrate)

Tetris_RD(width, height, steps)
