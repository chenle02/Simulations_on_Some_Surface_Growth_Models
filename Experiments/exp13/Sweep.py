#!/usr/bin/env python3
"""Parameter sweep launcher for experiment 13.

This script was copied from an older repository where ``tetris_ballistic`` was
already installed as a package.  When executed directly from this repository the
package might not be on ``PYTHONPATH`` which leads to ``ModuleNotFoundError``.

The small block below adds the project root (two directories up from this file)
to ``sys.path`` so that ``tetris_ballistic`` can be imported without requiring a
prior ``pip install -e .`` step.
"""

from pathlib import Path
import sys

# Add the project root to Python's search path if needed
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tetris_ballistic.sweep_parameters import sweep_parameters as sp
from tetris_ballistic.data_analysis_utilities import insert_joblibs

ListWidth = [50, 80, 100, 150, 200]
ListRandomSeeds = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
config_patterns = ["*.yaml"]
sp(list_width=ListWidth,
   list_random_seeds=ListRandomSeeds,
   config_dir="configs",
   config_patterns=config_patterns)
