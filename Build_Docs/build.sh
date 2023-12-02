#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Fri Dec  1 11:33:36 PM EST 2023"
  echo ""
  echo ""
  exit 1
fi

make html
rsync -avz --delete build/html/ ../docs/html/
make latexpdf
rsync -avz --delete build/latex/*.pdf ../docs/pdf/
make clean

./UploadAuburn.sh
