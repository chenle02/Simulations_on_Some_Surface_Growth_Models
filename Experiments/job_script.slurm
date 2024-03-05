#!/bin/bash
#SBATCH --job-name=ddd
#SBATCH --partition=abebeas_bg2
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --mem=48gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu,ian.ruau@auburn.edu
#SBATCH --time=48:00:00
#SBATCH --output=job_%x_%j.out
#SBATCH --error=job_%x_%j.err

# Your commands here
module load python/anaconda/3.10.9
cd $(git rev-parse --show-toplevel)

# Install the package in editable mode
pip3 install -e .

# Change back to the initial directory
cd - 

# Now this is the script to run
abc

echo "Starting job..."
