#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Thu 01 Feb 2024 11:09:04 AM CST"
  echo ""
  echo ""
  exit 1
fi

# Split the window horizontally into two panes
tmux split-window -h

# Select pane 0 and split it vertically
tmux select-pane -t 0
tmux split-window -v

# Select pane 0 and split it vertically
tmux select-pane -t 1
tmux split-window -v

# Commands for each pane
tmux send-keys -t 0 "htop" C-m
tmux send-keys -t 1 "nohup python SweepParameters2.py &" C-m "tail -f nohup.out" C-m
tmux send-keys -t 2 "tail -f simulation_progress.log" C-m
tmux send-keys -t 4 "monitor_large_files.sh" C-m
