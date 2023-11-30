# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 11:08:34 2023

"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import random
import time
import torch

start_time = time.time()


h = 20
w = 100
p_desorp = 0.1
p_grow = 0.1



# Initialization
base_df = pd.DataFrame(0, index=range(h), columns=range(w))
base_df.iloc[-1:, :] = 1
base_df.iloc[-2, ::2] = 1

while not(base_df.iloc[2].eq(1).any()):
    p_plus = random.random()
    p_minus = random.random()
    col = random.randint(0 + 2, w-2)
    aa = h - 1
    for i in reversed(base_df.iloc[:,col]):
        if i  == 0:
            if (base_df.iloc[aa,col+1])==0 and (base_df.iloc[aa,col-1])==0  and p_plus<= p_desorp:
                one_below = aa
                two_below = aa+1

                if one_below > (h-1) :
                    one_below = h - 1
                if two_below > (h-1):
                    two_below = h - 1

                base_df.iloc[one_below,col] = 0
                base_df.iloc[two_below,col] = 0

                break

            elif (base_df.iloc[aa,col+1])==1 and (base_df.iloc[aa,col-1])==1  and p_minus>= p_grow:

                base_df.iloc[aa,col] = 1
                base_df.iloc[aa-1,col] = 1

                break

            elif ((base_df.iloc[aa,col+1])==1 and (base_df.iloc[aa,col+1])==0) or ((base_df.iloc[aa,col-1])==1 and (base_df.iloc[aa,col-1])==0):

                break

        aa -= 1


# Display the DataFrame
plt.imshow(base_df, cmap='gray')


# Calculating the running time of code
end_time = time.time()
elapsed_time = (end_time - start_time)/60
print(f"Elapsed time: {elapsed_time} minutes")

