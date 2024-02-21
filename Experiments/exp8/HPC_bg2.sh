#!/bin/bash
#SBATCH --job-name=Le
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=48
#SBATCH --partition=abebeas_bg2
#SBATCH --mem=96gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=lzc0090@auburn.edu
#SBATCH --time=48:00:00
#SBATCH --output=100Seeds.log
#SBATCH --error=100Seeds.log

module load python/3.11.1
python3 -m venv myvenv
source myvenv/bin/activate
pip install --upgrade pip
pip install joblib
pip install numpy
pip install scipy
pip install matplotlib
pip install imageio
pip install pyyaml 
pip install functools
pip install re
cd ../../
pip install -e .
cd -
./SweepParameters.py
deactivate
