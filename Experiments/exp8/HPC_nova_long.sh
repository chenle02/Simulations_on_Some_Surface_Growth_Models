#!/bin/bash
#SBATCH --job-name=Le
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=28
#SBATCH --partition=nova_long
#SBATCH --mem=28gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu
#SBATCH --time=480:00:00
#SBATCH --output=100Seeds.log
#SBATCH --error=100Seeds.log

module load python/anaconda/3.10.9
cd ../../
pip install -e .
cd -
./SweepParameters.py
