#!/bin/bash

# Define an array of file patterns
declare -a patterns=("*w=50_*.joblib" "*w=100_*.joblib" "*w=200_*.joblib" "*w=500_*.joblib" "*w=1000_*.joblib"  "*w=1500_*.joblib"  "*w=2000_*.joblib")

# Header of the table
printf "%-40s %-20s\n" "Pattern" "Numbers of files"
printf "%-40s %-20s\n" "------------------" "-------"

# Loop through each pattern
for pattern in "${patterns[@]}"; do
    # Count the number of files matching the pattern
    num_files=$(ls $pattern 2> /dev/null | wc -l)
    
    # Print the pattern and the number of files
    printf "%-40s %-20d\n" "$pattern" "$num_files"
done
