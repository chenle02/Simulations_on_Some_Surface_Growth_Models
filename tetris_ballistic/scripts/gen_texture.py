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

    # Check if the image has an alpha channel (transparency)
    if original.mode == 'RGBA':
        # Create a white background image
        background = Image.new("RGB", original.size, (255, 255, 255))

        # Paste the original image onto the background using its alpha channel for transparency
        background.paste(original, mask=original.split()[3]) # Use the alpha channel as the mask

        original = background
    elif original.mode == 'LA' or (original.mode == 'P' and 'transparency' in original.info):
        # Convert images with less common transparency types
        original = original.convert("RGBA")
        background = Image.new("RGB", original.size, (255, 255, 255))
        background.paste(original, mask=original.split()[3])
        original = background
    else:
        # For images without transparency, directly convert to RGB to ensure compatibility
        original = original.convert("RGB")

    # Add a high-contrast border
    bordered_image = ImageOps.expand(original, border=border_size, fill=border_color)

    # Generate new filename with '_bordered'
    base, ext = os.path.splitext(original_image_path)
    new_filename = f"{base}_bordered{ext}"

    # Save the modified image
    bordered_image.save(new_filename)
    print(f"Processed {original_image_path} -> {new_filename}")


original_image_path = "../data/"

# Below is in the correct order.
images_filename = []
images_filename.append("Tetromino_O_Single.png")
images_filename.append("Tetromino_I_Horizontal.png")
images_filename.append("Tetromino_I_Vertical.png")
images_filename.append("Tetromino_L_Up.png")
images_filename.append("Tetromino_L_Left.png")
images_filename.append("Tetromino_L_Down.png")
images_filename.append("Tetromino_L_Right.png")
images_filename.append("Tetromino_J_Up.png")
images_filename.append("Tetromino_J_Left.png")
images_filename.append("Tetromino_J_Down.png")
images_filename.append("Tetromino_J_Right.png")
images_filename.append("Tetromino_T_Up.png")
images_filename.append("Tetromino_T_Left.png")
images_filename.append("Tetromino_T_Down.png")
images_filename.append("Tetromino_T_Right.png")
images_filename.append("Tetromino_S_Horizontal.png")
images_filename.append("Tetromino_S_Vertical.png")
images_filename.append("Tetromino_Z_Horizontal.png")
images_filename.append("Tetromino_Z_Vertical.png")
images_filename.append("Tetromino_1x1_Single.png")

print("Here is the list pieces:")
for i in range(20):
    print(f"Piece-{i}: {images_filename[i]}")

for filename in images_filename:
    print(f"Processing {filename}")
    add_high_contrast_border(f"{original_image_path}{filename}")

for i in range(20):
    print(images_filename[i])

