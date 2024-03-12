#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Sun Mar 10 08:48:49 PM EDT 2024
#
from PIL import Image, ImageDraw, ImageFont

def text_to_png(text, output_file, font_path="arial.ttf", font_size=24):
    # Create an image with white background
    image = Image.new('RGB', (300, 50), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Define the font
    font = ImageFont.truetype(font_path, font_size)

    # Use the font object directly to get text size
    text_width, text_height = font.getsize(text)

    # Calculate position (centered)
    position = ((image.width - text_width) / 2, (image.height - text_height) / 2)

    # Draw the text on the image
    draw.text(position, text, fill=(0, 0, 0), font=font)

    # Save the image
    image.save(output_file)


# Example usage
text = "Hello, World!"
output_file = "text_image.png"
# Provide the path to a TTF font file on your system
font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
text_to_png(text, output_file, font_path=font_path, font_size=24)

print(f"Generated image: {output_file}")
