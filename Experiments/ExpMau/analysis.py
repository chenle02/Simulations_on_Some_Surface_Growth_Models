#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

import numpy as np
import joblib
import os
import glob
import re
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
import statistics
import matplotlib.pyplot as plt


# Regex pattern to match filename and extract components
pattern_parse = r'config_(?P<type>piece_\d+)_combined_w=(?P<width>\d+)_seed=(?P<seed>\d+).joblib'
width =75
pattern = f"*_w={width}*.joblib"

files = glob.glob(pattern)
dic_me = {}
height = 50
TB = Tetris_Ballistic.load_simulation(files[3])
print("The width is:", TB.width)
frame_id = TB.substrate[height, :]
frame_id = int( (np.min(frame_id[np.nonzero(frame_id)])) )

print(f"At height {height}, the frame id is {frame_id}")

print("With",TB.count_holes_stack(height), "holes in the substrate at that height")

step_list = [min(int((TB.FinalSteps)*(i+1)//10), TB.FinalSteps -1) for i in range(10)]

def model_holes(substrate):
    step_list
    growth_rate
    for i in range(len(step_list)):
        filtered = substrate[step_list[i] <= substrate]
        growth_rate[f'step_list[i]'] = Tetris_Ballistic(filtered.count_holes_stack)


#TODO Plot time vs hole growth



def hole_statistics(steps, substrate, interval = 10):
    hole_hist = {}

    for i in range(interval):
        hole_hist[min(int(i*steps), substrate.height-1)] = substrate.count_holes_stack(min(int(i*steps), substrate.height-1))

    return hole_hist


#maufile = hole_statistics(TB)
#joblib.dump(maufile, "holes_counted.joblib")
#mau_load = joblib.load("holes_counted.joblib")
#print(mau_load)

def count_holes_stats(self, frame_id=None, verbose=False):
        """
        Counts the number of holes in the substrate
        --------------------------------------------

        A hole is defined as a collection of zero entries in the substrate that
        has a boundary of nonzero entries surrounding it.

        Args:
           frame_id (int): The frame id to count the holes in. If None, the last farm will be used.
           verbose (bool): Whether to print out the result.

        Returns:
            int: The number of holes in the substrate.
        """
        if self.substrate.size == 0:
            return 0

        vis_substrate = np.copy(self.substrate)
        copy_substrate = np.copy(self.substrate)
        if frame_id is None:
            frame_id = self.FinalSteps  # Use self.FinalSteps if frame_id is not provided
        else:
            # filter out the values greater than the current frame_id
            vis_substrate[self.substrate > frame_id] = 0

        visited = np.zeros_like(vis_substrate, dtype=bool)

        def dfs_stack(r, c, hole_number):
            stack = [(r, c)]
            while stack:
                r, c = stack.pop()
                if r < 0 or c < 0 or r >= self.height or c >= self.width or visited[r][c] or vis_substrate[r][c] != 0:
                    continue
                visited[r][c] = True
                copy_substrate[r,c] = hole_number
                stack.append((r + 1, c))
                stack.append((r - 1, c))
                stack.append((r, c + 1))
                stack.append((r, c - 1))

        hole_count = -1
        hole_sizes ={}

        for r in range(self.height):
            for c in range(self.width):
                if vis_substrate[r][c] == 0 and not visited[r][c]:
                    dfs_stack(r, c, hole_count)
                    hole_sizes[hole_count] = np.count_nonzero(copy_substrate == hole_count)
                    hole_count -= 1

        if verbose:
            print(f"Hole count: {hole_count} at the end of step {frame_id}.")

        return hole_sizes




#hole_dic = count_holes_stats(TB)
#
#print(hole_dic)
#print(hole_dic.get(-4))
#
#print(TB.count_holes_stack())
#
#filtered_dic = {key: value for key, value in hole_dic.items() if value > 1}
#
#filtered_dic.popitem()
#
#alt_dic = {key: value for key, value in hole_dic.items() if value > 1 and value < 400}
#
#
#raw_values = list(hole_dic.values())
#
#print("a",statistics.mean(raw_values))
#
#print("b",statistics.median(raw_values))
#
#print("c",statistics.mode(raw_values))
#
#values = list(filtered_dic.values())
#
#mean = statistics.mean(values)
#
#median = statistics.median(values)
#
#mode = statistics.mode(values)
#
#print("mean", mean)
#
#print("median", median)
#
#print("mode", mode)
#
#values2 = list(alt_dic.values())
#
#mean2 = statistics.mean(values2)
#
#median2 = statistics.median(values2)
#
#mode2 = statistics.mode(values2)
#
#print("mean", mean2)
#
#print("median", median2)
#
#print("mode", mode2)


#for file in files:
#
#    job = Tetris_Ballistic.load_simulation(file)
#    hole_stat = count_holes_stats(job)
#    raw_values = list(hole_stat.values())
#    dic_me[file] = [statistics.mean(raw_values), statistics.median(raw_values), statistics.mode(raw_values)]


#load_data = joblib.load('hole_stats.joblib')

#print(load_data)

#for file in files:


#    fl =[]
    # Load simulation from file
#    TB = Tetris_Ballistic.load_simulation(file)

#    dic_me[file] = [TB.count_holes_stack(TB.FinalSteps // 3), TB.count_holes_stack(int(TB.FinalSteps * (2/3))), TB.count_holes_stack()]



# Saving the complete fluctuations dictionary to disk
#print("Saving hole counting to disk...")
#joblib.dump(dic_me, "holes_counted.joblib")
