#!/usr/bin/env bash
# Upload the doc to le chen's home page at Auburn University
# URL: http://webhome.auburn.edu/~lzc0090/Simulation_Tetris/
# Author: Le Chen

docs="$(git rev-parse --show-toplevel)/docs/*"
echo $docs

pass sudo | sudo -S rsync -p -a $docs  "/mnt/Auburn-Server/public_html/Simulation_Tetris/"
