#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Sun Mar 10 12:03:52 PM EDT 2024
#

import yaml
import os

# Define the path to your YAML configuration and output directory
yaml_path = './dzi_config.yaml'
output_dir = 'dzi_images'
index_html_path = os.path.join(output_dir, 'index.html')

# Ensure the output directory exists
os.makedirs(output_dir, exist_ok=True)

# Read the YAML configuration
with open(yaml_path, 'r') as file:
    config = yaml.safe_load(file)

# Begin constructing the HTML content
html_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>OpenSeadragon 3x3 Grid Example</title>
    <script src="/home/lechen/Dropbox/Develop/openseadragon-bin-4.1.0/openseadragon.js"></script>
    <style>
        body, html {
            height: 100%;
            margin: 0;
            padding: 0;
        }
        #openseadragon-viewer {
            width: 100%;
            height: 100%;
        }
    </style>
</head>
<body>
    <div id="openseadragon-viewer"></div>
    <script>
        var viewer = OpenSeadragon({
            id: "openseadragon-viewer",
            prefixUrl: "/home/lechen/Dropbox/Develop/openseadragon-bin-4.1.0/images/",
            tileSources: [
'''

# Add the tileSources based on the YAML configuration
for result in config.get('results', []):
    print(f"Processing result: {result['name']}")
    shift_x, shift_y = eval(result['Shift'])  # Caution: Using eval() can be unsafe
    print(f"Shift: {shift_x}, {shift_y}")

    for row in result['rows']:
        print(f"Processing row: {row['number']}")
        for idx, image_path in enumerate(row['images'], start=1):
            x_position = shift_x + row['number']
            y_position = 0.5  * (shift_y + (idx - 1))
            html_content += f'''
                {{
                    tileSource: "./{image_path.replace('png','dzi')}",
                    x: {x_position},
                    y: {y_position},
                    width: 1
                }},
'''

# Finish the HTML content
html_content += '''
            ],
            maxZoomPixelRatio: 2,
            zoomPerClick: 1.5,
            zoomPerScroll: 1.1,
            maxZoomLevel: 10
        });
    </script>
</body>
</html>
'''

# Write the HTML content to the index.html file
with open(index_html_path, 'w') as file:
    file.write(html_content)

print(f"Generated {index_html_path}")
