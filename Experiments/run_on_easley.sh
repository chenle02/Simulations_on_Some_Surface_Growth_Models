#!/usr/bin/env bash

# Improved Help Option Check
if [[ "$1" == "--help" ]] || [[ $# -eq 0 ]]; then
  echo -e "\nUsage: $0 Script_to_run"
  echo "Generate the job script on Easley HPC at Auburn."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo -e "Tue Mar  5 10:58:56 AM EST 2024\n"
  exit 1
fi

# -------------------------
# Step 0. Ask for job name
# -------------------------
read -p "Enter job name: " job_name

# Validate job name
if [[ -z "$job_name" ]]; then
    echo "Invalid job name. Exiting."
    exit 1
fi

echo "Job name: $job_name" 

# -------------------------
# Step 1. Ask for partition
# -------------------------
declare -A partition_options=(
    ["1"]="mathdep_bg2"
    ["2"]="abebeas_bg2"
    ["3"]="abebeas_std"
)

# Default partition
default_partition_choice="1"

echo "Select a partition:"
for key in "${!partition_options[@]}"; do
    echo "$key. ${partition_options[$key]}"
done

read -p "Enter your choice [default: $default_partition_choice (mathdep_bg2)]: " partition_choice
partition_choice="${partition_choice:-$default_partition_choice}"

selected_partition="${partition_options[$partition_choice]:-${partition_options[$default_partition_choice]}}"

echo "Selected partition: $selected_partition"

# ----------------------
# Step 2. Ask for emails
# ----------------------
email_options=(
    "lzc0090@auburn.edu"
    "mauricio.montes@auburn.edu"
    "ian.ruau@auburn.edu"
)

echo "Select email(s) to notify:"
echo "1. ${email_options[0]}"
echo "2. ${email_options[1]}"
echo "3. ${email_options[2]}"
echo "You can choose multiple options, e.g., 1, 2, or 1 2 3."
read -p "Enter your choice(s) [default: 1]: " email_choices
email_choices="${email_choices:-1}"

IFS=', ' read -r -a selected_indexes <<< "$email_choices"
declare -a selected_emails=("${email_options[0]}") # Default to the first option

for index in "${selected_indexes[@]}"; do
    ((index--)) # Adjust index to 0-based for array access
    if [[ index -ge 0 && index -lt ${#email_options[@]} ]]; then
        selected_emails[index]="${email_options[index]}"
    fi
done

# Generate email list string
email_list=$(IFS=,; echo "${selected_emails[*]}")

echo "Selected email(s) for notification: $email_list"

# -----------------
# Step 3. Finalize
# -----------------
echo "Finalize now:"
echo "Job name: $job_name"
echo "Using partition: $selected_partition"
echo "Emails to notify: $email_list"

# Generate the SLURM script with the specified options
cat <<EOT > job_script.slurm
#!/bin/bash
#SBATCH --job-name=$job_name
#SBATCH --partition=$selected_partition
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=48
#SBATCH --mem=48gb
#SBATCH --mail-type=ALL
#SBATCH --mail-user=$email_list
#SBATCH --time=48:00:00
#SBATCH --output=job_%x_%j.out
#SBATCH --error=job_%x_%j.err

# Your commands here
module load python/anaconda/3.10.9
cd \$(git rev-parse --show-toplevel)

# Install the package in editable mode
pip3 install -e .

# Change back to the initial directory
cd - 

# Now this is the script to run
$1

echo "Starting job..."
EOT

echo "SLURM script 'job_script.slurm' created with the specified options."
echo "Review it and submit with 'sbatch job_script.slurm'."
