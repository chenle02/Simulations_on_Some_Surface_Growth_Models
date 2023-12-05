# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 11:08:34 2023

"""

import pandas as pd
import matplotlib.pyplot as plt
import random
import time

start_time = time.time()

# Dimensions of the window
h = 100
w = 500

# Probabilities of the change in interface
p_desorp = 0.05  # desorption
p_grow = 0.95  # growth

# Initialization
base_df = pd.DataFrame(0, index=range(h), columns=range(w))

# 1st row
integer_sequence_first_row = list(range(1, w + 1))
random.shuffle(integer_sequence_first_row)
base_df.iloc[-1:, :] = pd.DataFrame([integer_sequence_first_row])

# 2nd row
integer_sequence_second_row = list(range(w + 1, w + 1 + w // 2))
random.shuffle(integer_sequence_second_row)
base_df.iloc[-2, ::2] = integer_sequence_second_row

# Next number that will be added to the dataframe.
particle_no = w + w // 2 + 1

# This wile loop ensures that growth occurs up till top of the window.
while all(base_df.iloc[2] == 0):
    # These are the probabilities assigned to eith grow or desorp respectively.
    p_plus = random.random()
    p_minus = random.random()

    # Randomly picking a column to check if it eligible for growth or desorption.
    col = random.randint(0, w - 1)
    if (col <= w - 2) and (col >= 1):
        left = col - 1
        right = col + 1
    elif col == 0:
        left = col + 1
        right = col + 1
    elif col == w - 1:
        left = col - 1
        right = col - 1

    aa = h - 1

    # Checking the column where does the interface lie and taking the desicion
    # to make it grow or desorp accordingly.
    for i in reversed(base_df.iloc[:, col]):
        if i == 0:
            # This 'if' statement is checking if it is eligible for desorption.
            if (
                (base_df.iloc[aa, right]) == 0
                and (base_df.iloc[aa, left]) == 0
                and (p_plus < p_desorp)
            ):
                one_below = aa
                two_below = aa + 1

                if one_below > (h - 1):
                    one_below = h - 1
                if two_below > (h - 1):
                    two_below = h - 1
                base_df.iloc[one_below, col] = 0
                base_df.iloc[two_below, col] = 0
                break

            # This 'elif' statement is checking if it is eligible for growth.
            elif (
                (base_df.iloc[aa, right]) != 0
                and (base_df.iloc[aa, left]) != 0
                and (p_minus < p_grow)
            ):
                one_below = aa
                two_below = aa - 1
                base_df.iloc[one_below, col] = particle_no
                particle_no += 1
                base_df.iloc[two_below, col] = particle_no
                particle_no += 1
                break

            # This 'elif' statement is checking if there is no change to be
            # taken place for the interface.
            elif ((base_df.iloc[aa, right]) != 0 and (base_df.iloc[aa, left]) == 0) or (
                (base_df.iloc[aa, left]) != 0 and (base_df.iloc[aa, right]) == 0
            ):
                break
        aa -= 1

# Displaying the surface interface.
heatmap = plt.imshow(base_df, cmap="viridis", interpolation="nearest", aspect=3)
plt.xlabel("x-axis of the window", fontweight="bold")
plt.title("Interface of the surface : {} x {}".format(h, w), fontweight="bold")
plt.colorbar(heatmap, orientation="horizontal", label="Colorbar of the values")

# Saving the surface growth as a .txt file.
file_name = "interface_window_size_{}x{}".format(h, w)
# base_df.to_csv(file_name, sep='\t', index=False, header=False)

# Calculating the running time of code.
end_time = time.time()
elapsed_time = round((end_time - start_time) / 60, 4)
print("Window size : {} x {}".format(h, w))
print(f"Elapsed time: {elapsed_time} minutes")
