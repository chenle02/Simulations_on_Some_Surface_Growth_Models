#!/bin/bash
#SBATCH --job-name=Le
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --partition=abebeas_bg2
#SBATCH --mem=96gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu
#SBATCH --time=48:00:00
#SBATCH --output=%x_%j_%N.out
#SBATCH --error=%x_%j_%N.err
#
# In the above output and error, we use SLURM_JOB_NAME and SLURM_JOB_ID for filename uniqueness

module load python/anaconda/3.10.9
cd ../../
pip install -e .
cd -
./SweepParameters.py
