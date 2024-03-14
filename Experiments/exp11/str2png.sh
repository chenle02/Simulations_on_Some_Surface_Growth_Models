#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -ne 4 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 fontsize scale_width filename_no_extension <text>"
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Sun Mar 10 08:59:14 PM EDT 2024"
  echo ""
  echo ""
  exit 1
fi

# Define your text, output file, and desired font size
FONT_SIZE=$1
SCALE=$2
OUTPUT_FILE="$3.png"
BASENAME=$3
TEXT=$4
FONT_PATH="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" # Adjust the font path as needed
DZI_DIR="./dzi_images"

# Use ImageMagick's convert command to create an image from text
convert -background white -fill black -font "$FONT_PATH" -pointsize $FONT_SIZE \
        label:"$TEXT" "$OUTPUT_FILE"

convert "$OUTPUT_FILE" -resize "$SCALE" "$OUTPUT_FILE"

vips dzsave "$OUTPUT_FILE" "$DZI_DIR/$BASENAME" --suffix .jpg[Q=80]
echo "Image created: $OUTPUT_FILE"
