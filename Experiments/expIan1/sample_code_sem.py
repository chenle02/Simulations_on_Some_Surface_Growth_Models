import numpy as np

# Simulate a dataset of n=100 numbers, for example, random numbers from a normal distribution
np.random.seed(0)  # Seed for reproducibility
data = np.random.normal(loc=0, scale=1, size=100)  # mean=0, std=1

# Calculate the mean
mean = np.mean(data)

# Calculate the standard deviation
std_dev = np.std(data)

# Calculate the standard error of the mean
sem = std_dev / np.sqrt(len(data))

print(f"Mean of the dataset: {mean:.2f}")
print(f"Standard Deviation of the dataset: {std_dev:.2f}")
print(f"Standard Error of the Mean: {sem:.2f}")
