#!/usr/bin/env bash
# #!/bin/bash
if [[ $# -eq 0 ]] || [[ "" == "--help" ]]
then
  echo ""
  echo ""
  echo "Usage: $0 "
  echo "Work under working directory."
  echo "by Le CHEN, (chenle02@gmail.com)"
  echo "Thu Mar  7 10:41:25 PM EST 2024"
  echo ""
  echo ""
  exit 1
fi

# 1. First remove the joblib files and regenerate them
rm *piece_14_*.joblib *type_4*.joblib *piece_all*.joblib
./Sweep.py

# 2. Delete the related entries in the database and then add the newly generated
# entries back 
#
DATABASE_PATH="simulation_results.db"
#
# # Define an array of table names
# declare -a tables=("sticky" "nonsticky" "combined" "Simulations")
#
# # Define an array of type values to delete
# declare -a types=("piece_14" "type_4" "piece_all")
#
# # Loop through each table
# for table in "${tables[@]}"; do
#     # Loop through each type
#     for type in "${types[@]}"; do
#         # Execute the delete command
#         sqlite3 $DATABASE_PATH "DELETE FROM $table WHERE type = '$type';"
#     done
# done
#
# echo "Deletion completed."

rm $DATABASE_PATH
./db.py
./db_status.sh

# 3. Run ./analysis.py to generate the fluctuaions dictionary joblib files.
./analysis.py

# 4. Generate the images again
./loglogplot_stat.py

# 5. Generate the video files again
rm *piece_14*.mp4 *type_4*.mp4 *piece_all*.mp4
./gen_anemation.py
