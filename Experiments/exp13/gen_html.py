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
            margin: 1px;
            padding: 1px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
            background-color: #f0f0f0; /* Light grey background for the whole page */
        }
        .image-pair {
            margin: 1px;
            padding: 1px;
            background-color: #ffffff; /* White background for each pair */
            box-shadow: 0px 0px 10px rgba(0,0,0,0.1); /* Subtle shadow around each pair */
            border: 1px solid #e0e0e0; /* Light grey border */
            border-radius: 5px; /* Optional: Adds rounded corners */
            text-align: center;
        }
        img {
            width: 300px; /* You can adjust this to better fit your images */
            height: auto;
            margin: 0px;
        }
        p {
            font-size: 10px;
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
        <p>{percentage}% nonsticky + {100-percentage}% sticky</p>
        <img src="{original_img}" alt="Original {formatted_percentage}%"/>
        <img src="{loglog_img}" alt="Log-Log Plot {formatted_percentage}%"/>
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
