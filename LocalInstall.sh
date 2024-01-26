#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Build the package locally and install it for debugging."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Fri Jan 26 05:22:14 PM EST 2024"
  echo ""
  echo ""
  exit 1
fi


python3 setup.py sdist bdist_wheel
pip3 install -e .
