#!/bin/bash
#SBATCH --job-name=your_job_name
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=48
#SBATCH --mem=96gb
#SBATCH --time=24:00:00
#SBATCH --output=your_job_name.log
#SBATCH --error=Single_Pieces.log

./SweepParameters.py
