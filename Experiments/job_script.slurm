#!/bin/bash
#SBATCH --job-name=aba
#SBATCH --partition=mathdep_bg2
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --mem=48gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu,mauricio.montes@auburn.edu,ian.ruau@auburn.edu
#SBATCH --time=48:00:00
#SBATCH --output=job_%x_%j.out
#SBATCH --error=job_%x_%j.err

# Your commands here
module load python/anaconda/3.10.9
cd /home/lechen/Dropbox/Teaching/svn_teaching/2023_Fall_Math7820/GitHub/Simulations_on_Some_Surface_Growth_Models/branches/Tetris_Domino_Le

# Install the our package in editable mode
pip3 install -e .

# Change back to the current directory
cd -

# Now this is the script to run
abc

echo "Starting job..."
