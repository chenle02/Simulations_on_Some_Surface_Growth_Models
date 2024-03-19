#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 dummy"
  echo "Two way of  synchronization between local and remote"
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Thu 07 Mar 2024 02:20:39 AM EST"
  echo ""
  echo ""
  exit 1
fi

local="."
remote="lechen@Office:/home/lzc0090/Dropbox/Simulations_on_Some_Surface_Growth_Models/branches/Tetris_Domino_Le/Experiments/exp13"
rsync -avzu --progress "$remote/" "$local/"
# rsync -avzu --progress "$local/" "$remote/"
