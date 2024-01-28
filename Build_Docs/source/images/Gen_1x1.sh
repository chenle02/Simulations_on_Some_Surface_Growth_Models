#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Sun Jan 28 08:47:52 AM EST 2024"
  echo ""
  echo ""
  exit 1
fi
convert Tetromino_O_Single.png -resize 50% input.png
convert input.png -fill black -colorize 100 Tetromino_1x1_Single.png 
rm input.png
