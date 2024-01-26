#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Mon Oct 23 09:08:47 PM EDT 2023"
  echo ""
  echo ""
  exit 1
fi


./RD_CLI.py --width 200 --height 200 --steps 9900
./RD_CLI.py --width 200 --height 200 --steps 9900 --relax
./RD_CLI.py --width 200 --height 200 --steps 9900 --BD

./RD_CLI.py --width 300 --height 300 --steps 20000
./RD_CLI.py --width 300 --height 300 --steps 20000 --relax
./RD_CLI.py --width 300 --height 300 --steps 20000 --BD

./RD_CLI.py --width 500 --height 500 --steps 30000
./RD_CLI.py --width 500 --height 500 --steps 30000 --relax
./RD_CLI.py --width 500 --height 500 --steps 30000 --BD

