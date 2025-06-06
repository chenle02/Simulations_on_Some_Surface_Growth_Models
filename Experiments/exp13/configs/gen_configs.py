#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Mon Mar 18 01:17:02 PM EDT 2024
#


def generate_config_file(filename, num):
    with open(filename, 'w') as f:
        f.write("steps: 12000\n")
        f.write("width: 100\n")
        f.write("height: 300\n")
        f.write("seed: 12\n")
        for i in range(20):
            if i == 19:
                f.write(f"Piece-{i}: [{num}, {100-num}]\n")
            else:
                f.write(f"Piece-{i}: [0, 0]\n")


def generate_config_files(start_num, end_num, step):
    for num in range(start_num, end_num, step):
        filename = f"config_piece_19_combined_percentage_{num:02d}.yaml"
        generate_config_file(filename, num)


if __name__ == "__main__":
    start_num = 5
    end_num = 100
    step = 5
    generate_config_files(start_num, end_num, step)
    start_num = 98
    end_num = 100
    step = 1
    generate_config_files(start_num, end_num, step)
