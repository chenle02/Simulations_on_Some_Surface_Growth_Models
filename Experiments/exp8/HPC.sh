#!/bin/bash
#SBATCH --job-name=Le
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=48
#SBATCH --mem=96gb
#SBATCH --time=48:00:00
#SBATCH --output=100Seeds.log
#SBATCH --error=100Seeds.log

./SweepParameters.py
