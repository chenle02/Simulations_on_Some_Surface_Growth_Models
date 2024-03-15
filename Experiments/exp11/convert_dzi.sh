#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Sun Mar 10 11:57:47 AM EDT 2024"
  echo ""
  echo ""
  exit 1
fi

# Define your output directory
OUTPUT_DIR="./dzi_images"

# Ensure the output directory exists
mkdir -p $OUTPUT_DIR

# List of your images
declare -a images=($(ls combined_*.png))

# First remove all subdirectories in the output directory
find $OUTPUT_DIR -type d -mindepth 1 -exec rm -r {} +
cd $OUTPUT_DIR
rm *.dzi
cd -

# Generate DZI files for each image
echo "Generating title image ..."
./str2png.sh 96 1 Title "Simulation results for Tetris decomposition"

# Generate DZI files for each image
for img in "${images[@]}"; do
    base=$(basename "$img" .png)
    echo "Processing $img..."
    vips dzsave "$img" "$OUTPUT_DIR/${base}" --suffix .jpg[Q=80]
done

echo "DZI generation complete."
