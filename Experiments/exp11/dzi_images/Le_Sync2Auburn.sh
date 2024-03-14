#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Tue 12 Mar 2024 10:11:34 AM CDT"
  echo ""
  echo ""
  exit 1
fi

pass sudo | sudo -S rsync -av --progress . /mnt/Auburn-Server/public_html/Tetris_Ballistic/exp11/dzi_images
