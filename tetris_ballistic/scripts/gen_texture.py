#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Tue 13 Feb 2024 11:46:57 AM CST
#

from PIL import Image, ImageOps
import glob
import os


def add_high_contrast_border(original_image_path, border_size=5, border_color='red'):
    # Open the original image
    original = Image.open(original_image_path)

    # Add a high-contrast border
    bordered_image = ImageOps.expand(original, border=border_size, fill=border_color)

    # Generate new filename with '_bordered'
    base, ext = os.path.splitext(original_image_path)
    new_filename = f"{base}_bordered{ext}"

    # Save the modified image
    bordered_image.save(new_filename)
    print(f"Processed {original_image_path} -> {new_filename}")


original_image_path = "../data/"

# Process all PNG files in the specified directory
for original_image_path in glob.glob(f'{original_image_path}*.png'):
    print(f"Processing {original_image_path}")
    add_high_contrast_border(original_image_path)


# def add_sticky_texture_to_file(original_image_path):
#     # Open the original and texture images
#     original = Image.open(original_image_path).convert("RGBA")
#     texture = Image.open(original_image_path).convert("RGBA")
#
#     # Resize texture to match original image size
#     texture = texture.resize(original.size)
#
#     # Blend the original and the texture
#     sticky = Image.blend(original, texture, alpha=0.5)  # Adjust alpha for desired effect
#
#     # Generate new filename with '_texture'
#     base, ext = os.path.splitext(original_image_path)
#     new_filename = f"{base}_texture{ext}"
#
#     # Save the modified image
#     sticky.save(new_filename)
#     print(f"Processed {original_image_path} -> {new_filename}")
#
#
# original_image_path = "../data/"
#
# # Process all PNG files in the current directory
# for original_image_path in glob.glob(f'{original_image_path}*.png'):
#     print(f"Processing {original_image_path}")
#     add_sticky_texture_to_file(original_image_path)
