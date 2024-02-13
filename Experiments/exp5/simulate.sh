#!/usr/bin/env bash
#PBS -N your_job_name
#PBS -l select=2:ncpus=48:mem=48gb
#PBS -l walltime=48:00:00
#PBS -j oe
#PBS -o your_job_name.log
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

# Select pane 2 and split it vertically
tmux select-pane -t 2
tmux split-window -v

# Select pane 3 and split it vertically
tmux select-pane -t 3
tmux split-window -v

# Move to the last working pane and send all keys from there to other 4 panes:
tmux select-pane -t 4

# Commands for each pane
tmux send-keys -t 1 "nohup python SweepParameters.py &" C-m "tail -f nohup.out" C-m
sleep 2
tmux send-keys -t 0 "htop -p $(pgrep -d ',' -f SweepParameters.py)" C-m
tmux send-keys -t 2 "tail -f simulation_progress.log" C-m
tmux send-keys -t 3 "./monitor_large_files.sh ." C-m
