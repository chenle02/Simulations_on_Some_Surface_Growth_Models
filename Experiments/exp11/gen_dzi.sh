#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Sat Mar  9 11:35:51 PM EST 2024"
  echo ""
  echo ""
  exit 1
fi


image1_1="./combined_loglog_plot_sticky_piece_19.png"
image2_1="./combined_loglog_plot_sticky_type_2.png"
image3_1="./combined_loglog_plot_sticky_piece_all.png"
image1_2="./combined_loglog_plot_sticky_type_1.png"
image2_2="./combined_loglog_plot_sticky_type_3.png"
image3_2="./combined_loglog_plot_sticky_type_5.png"
image1_3="./combined_loglog_plot_sticky_piece_0.png"
image2_3="./combined_loglog_plot_sticky_type_4.png"
image3_3="./combined_loglog_plot_sticky_type_6.png"

# create a 3x3 dzi image

OUTPUT_DIR="dzi_images"

# Convert images to DZI format
convert_to_dzi() {
    local image_path="$1"
    local output_base="$2"
    
    if [ ! -f "$image_path" ]; then
        echo "File $image_path does not exist."
        return
    fi
    
    vips dzsave "$image_path" "$OUTPUT_DIR/$output_base" --suffix .jpg[Q=80] --layout=dz
    echo "Converted $image_path to DZI format."
}

# First remove all subdirectories in the output directory
find $OUTPUT_DIR -type d -mindepth 1 -exec rm -r {} +

# Process each image
convert_to_dzi $image1_1 "image1_1"
convert_to_dzi $image1_2 "image1_2"
convert_to_dzi $image1_3 "image1_3"
convert_to_dzi $image2_1 "image2_1"
convert_to_dzi $image2_2 "image2_2"
convert_to_dzi $image2_3 "image2_3"
convert_to_dzi $image3_1 "image3_1"
convert_to_dzi $image3_2 "image3_2"
convert_to_dzi $image3_3 "image3_3"

echo "All specified images have been converted to DZI format."

