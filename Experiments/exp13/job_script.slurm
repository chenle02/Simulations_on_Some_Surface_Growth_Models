#!/bin/bash
#SBATCH --job-name=Tetris
#SBATCH --partition=abebeas_std
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --mem=96gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu
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

cd ./configs
./gen_configs.py

cd ..
./Sweep.py

./analysis.py

./loglogplot_stat.py

echo "Starting job..."
