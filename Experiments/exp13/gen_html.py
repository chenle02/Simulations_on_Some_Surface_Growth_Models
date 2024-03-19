#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Tue 19 Mar 2024 08:39:10 AM CDT
#

html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Image Display</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
        }
        .image-pair {
            margin: 20px;
            text-align: center;
        }
        img {
            width: 300px; /* You can adjust this to better fit your images */
            height: auto;
            margin: 10px;
        }
    </style>
</head>
<body>
"""

# Generate the body part by iterating through the percentages
percentages = list(range(5, 100, 5)) + [98, 99]
for percentage in percentages:
    formatted_percentage = str(percentage).zfill(2)
    loglog_img = f"combined_loglog_plot_combined_percentage_{formatted_percentage}.png"
    original_img = f"combined_original_combined_percentage_{formatted_percentage}.png"
    html_template += f"""
    <div class="image-pair">
        <img src="{original_img}" alt="Original {formatted_percentage}%"/>
        <img src="{loglog_img}" alt="Log-Log Plot {formatted_percentage}%"/>
        <p>Percentage: {formatted_percentage}%</p>
    </div><br>
    """

# Closing tags for HTML
html_template += """
</body>
</html>
"""

# Save the HTML content to a file
file_path = "images_display.html"
with open(file_path, "w") as file:
    file.write(html_template)

file_path
