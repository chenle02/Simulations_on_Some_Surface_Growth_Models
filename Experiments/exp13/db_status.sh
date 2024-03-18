#!/bin/bash

# Define the database path
DATABASE_PATH="simulation_results.db"

# Define an array of table names
# declare -a tables=("sticky" "nonsticky" "combined" "Simulations")
declare -a tables=("combined")

# Loop through each table and count the entries
for table in "${tables[@]}"; do
    echo -n "Count in $table: "
    sqlite3 $DATABASE_PATH "SELECT COUNT(*) FROM $table;"
done
