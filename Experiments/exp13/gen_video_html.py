#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Tue 19 Mar 2024 09:03:50 AM CDT
#

video_html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Video and Image Display</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            background-color: #f0f0f0; /* Light grey background */
        }
        .block {
            margin: 20px;
            display: flex;
            align-items: flex-start;
            background-color: #ffffff; /* White background */
            box-shadow: 0px 0px 10px rgba(0,0,0,0.1); /* Subtle shadow */
            padding: 15px;
            border-radius: 5px; /* Optional: Adds rounded corners */
        }
        video {
            width: 300px; /* Adjust as needed */
            height: auto;
            margin-right: 2px;
        }
        img {
            width: 300px; /* Adjust as needed */
            height: auto;
            margin-top: 2px;
        }
        .image-pair {
            display: flex;
            flex-direction: column;
            text-align: center;
        }
        p {
            font-size: 10px;
        }
    </style>
</head>
<body>
"""

# Data for the videos and their corresponding images
video_data = [
    {"percentage": "05", "seed": 10},
    {"percentage": "50", "seed": 10},
    {"percentage": "90", "seed": 10},
    {"percentage": "95", "seed": 10},
    {"percentage": "98", "seed": 10},
    {"percentage": "99", "seed": 10},
]
for data in video_data:
    percentage = data["percentage"]
    seed = data["seed"]
    video_file = f"config_piece_19_combined_percentage_{percentage}_w=50_seed={seed}.mp4"
    loglog_img = f"combined_loglog_plot_combined_percentage_{percentage}.png"
    original_img = f"combined_original_combined_percentage_{percentage}.png"
    video_html_template += f"""
    <div class="block">
        <video controls>
            <source src="{video_file}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        <div class="image-pair">
            <p>{int(percentage)}% nonsticky + {100-int(percentage)}% sticky</p>
            <img src="{loglog_img}" alt="Log-Log Plot {percentage}%"/>
            <img src="{original_img}" alt="Original {percentage}%"/>
        </div>
    </div>
    """
# Closing tags for HTML
video_html_template += """
</body>
<script>
document.addEventListener("DOMContentLoaded", function() {
    const videos = document.querySelectorAll('video');
    videos.forEach(video => {
        // Wait for the metadata to load to know the video duration
        video.addEventListener('loadedmetadata', function() {
            // Seek to just before the last second to ensure the last frame shows
            this.currentTime = Math.max(0, this.duration - 1);
        });

        // Optional: If you want the video to end up paused on the last frame
        // when it naturally finishes playing, you can still include the 'ended' event listener
        video.addEventListener('ended', function() {
            this.currentTime = Math.max(0, this.duration - 1);
            this.pause(); // Ensure the video is paused on the last frame
        });
    });
});
</script>
</html>
"""

# Save the HTML content to a new file
video_file_path = "videos_and_images_display.html"
with open(video_file_path, "w") as file:
    file.write(video_html_template)
