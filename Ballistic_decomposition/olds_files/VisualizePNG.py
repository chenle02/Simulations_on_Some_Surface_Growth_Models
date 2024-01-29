#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Tue 28 Nov 2023 01:21:35 PM CST
#


import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Replace this with your file path
file_path = "./Substrate_domino_500x500_Particles=15000.txt"

# Assuming the file is a space-separated txt file, reading the 500x500 array
data = pd.read_csv(file_path, header=None, sep=",\s*", engine="python")

# Check if the data is loaded correctly
print(data.shape)

# Plotting the heatmap
plt.figure(figsize=(10, 10))
sns.heatmap(data, cmap="viridis")
plt.title("Heatmap of 500x500 Integer Array")
# plt.show()
# Please save the image for future use

plt.savefig(file_path.replace(".txt", ".png"))
plt.close()
