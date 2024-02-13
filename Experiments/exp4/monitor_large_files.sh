#!/usr/bin/env bash

# Display help information if no arguments or --help is provided
if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]]; then
  echo "Usage: $0 DIRECTORY [MIN_SIZE] [UPDATE_INTERVAL]"
  echo "Monitor large files in a specified directory, refreshing the list at a given interval."
  echo ""
  echo "Arguments:"
  echo "  DIRECTORY        The directory to monitor for large files."
  echo "  MIN_SIZE         Minimum file size to include in the monitoring (e.g., 10M for 10MB, 1G for 1GB)."
  echo "                   Defaults to 10M if not specified."
  echo "  UPDATE_INTERVAL  How often (in seconds) to update the list of large files."
  echo "                   Defaults to 10 seconds if not specified."
  echo ""
  echo "Example:"
  echo "  $0 /path/to/directory 100M 30"
  echo "  This monitors /path/to/directory for files larger than 100MB, updating every 30 seconds."
  echo ""
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Thu 01 Feb 2024 11:36:31 AM CST"
  exit 1
fi

# Assign command line arguments to variables with default values
directory=$1
min_size=${2:-10M}  # Default minimum size to 10M if not specified
sleep_time=${3:-10}  # Default update interval to 60 seconds if not specified


# Function to kill all processes named "SweepParameters.py"
kill_sweep_parameters() {
    echo "Do you really want to kill all 'SweepParameters.py' processes? (yes/no)"
    read answer
    if [[ "$answer" = "yes" ]] || [[ "$answer" = "y" ]]; then
        echo "Killing all 'SweepParameters.py' processes..."
        pkill -f SweepParameters.py
    else
        echo "Abort process killing. Continuing to monitor the processes..."
    fi
}

# Trap SIGINT (Ctrl+C) and execute the kill_sweep_parameters function
trap kill_sweep_parameters SIGINT
    
# Main loop to monitor large files
while true; do
  clear
  echo ""
  echo "Monitoring large files (larger than $min_size) in $directory..."
  # List files larger than the specified size, sorted by size
  echo ""
  find "$directory" -type f -size "+$min_size" -exec du -h {} + | sort -rh | head -n 10 | awk '{print $2 ": " $1}'

  # Count YAML files (.yaml and .yml extensions)
  YAML_COUNT=$(find $MONITOR_DIR -type f \( -name "*.yaml" -o -name "*.yml" \) | wc -l)

  # Count joblib files
  JOBLIB_COUNT=$(find $MONITOR_DIR -type f -name "*.joblib" | wc -l)

  echo ""
  echo "Number of YAML files: $YAML_COUNT"
  echo "Number of joblib files: $JOBLIB_COUNT"

  # Calculate the total size of joblib files
  total_size=$(find . -type f -name "*.joblib" -exec du -cb {} + | grep "total$" | cut -f1)
  
  # Convert total size to human-readable format (e.g., KB, MB)
  readable_size=$(echo $total_size | awk '{ sum=$1; hum[1024^3]="GB";hum[1024^2]="MB";hum[1024]="KB";for (x=1024^3; x>=1024; x/=1024){ if (sum>=x) { printf "%.2f %s\n", sum/x, hum[x]; break } }}')
  
  echo ""
  # Print the total size
  echo "Total size of joblib files: $readable_size"

  echo ""
  echo "Control-c and then type yes or y to kill all 'SweepParameters.py' processes."

  sleep $sleep_time

done
