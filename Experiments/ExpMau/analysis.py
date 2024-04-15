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

#step_list = [min(int((TB.FinalSteps)*(i+1)//10), TB.FinalSteps -1) for i in range(10)]

def model_holes(substrate, interval = 10):
    step_list = [min(int((substrate.FinalSteps)*(i+1)//interval), substrate.FinalSteps -1) for i in range(interval)]
    growth_rate = {}
    for i in range(len(step_list)):
        growth_rate[step_list[i]] = substrate.count_holes_stack(step_list[i])

    return growth_rate

#for file in files:
#    job = Tetris_Ballistic.load_simulation(file)
#    list_me = range(len(files))
#    hole_stat = model_holes(job)
#    steps = list(hole_stat.keys())
#    holes = list(hole_stat.values())
#    coefficients = np.polyfit(steps, holes, 1)
#    poly_eq = np.poly1d(coefficients)
#    plt.plot(steps, holes, color ='green', marker='o',linestyle ='--')
#    plt.plot(steps, poly_eq(steps), color = 'red', label =f'Linear fit: y = {coefficients[0]:.2f}x + {coefficients[1]:.2f}')
#
#    plt.xlabel('Time')
#    plt.ylabel('Hole Count')
#    plt.title('Hole growth over time')
#    plt.legend()
#    plt.grid(True)
#    #plt.axis('scaled')
#
#    plt.savefig(f'{file.replace("joblib", "png")}')
#    plt.close()
#    #joblib.dump(hole_stat, f'mautest_holes.joblib')
#    print("Done with:TB")


#TODO Compare hole growth to perimeter of substrate

def peri_hole(self, frame_id): 
    perimeter = self._ffnz(0) 
    vis_substrate = np.copy(self.substrate)

    if frame_id is None:
        frame_id = self.FinalSteps  # Use self.FinalSteps if frame_id is not provided
    else:
        # filter out the values greater than the current frame_id
        vis_substrate[self.substrate > frame_id] = 0


    for i in range(vis_substrate.shape[1]-1):
        perimeter += abs(self._ffnz(i) - self._ffnz(i+1))

    return perimeter

print("Final Perimeter",peri_hole(TB, frame_id = None))


#TODO Create Perimeter List, Compare Number of Holes, Time
def peri_v_holes(self, interval = 10):
    peri_list= []
    step_list = [min(int((self.FinalSteps)*(i+1)//interval), self.FinalSteps -1) for i in range(interval)]
    for step in step_list:
        peri_list.append(peri_hole(self, step))
        
    hole_stat = model_holes(self)
    holes = list(hole_stat.values())

    plt.plot(holes,step_list , color ='green', marker='o', linestyle ='--')
#
    plt.xlabel('perimeter')
    plt.ylabel('Hole Count')
    plt.title('Hole growth over perimeter')
    plt.legend()
    plt.grid(True)
#
    plt.savefig('holes_v_perimeter.png')
    plt.close()
#TODO Need to look at why there are more holes vs the perimeter. Might need 3d plot

peri_v_holes(TB)



#TODO Plot time vs hole growth
#joblib.dump(test, "hole_growth.joblib")

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
