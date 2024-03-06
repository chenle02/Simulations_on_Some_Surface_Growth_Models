#!/usr/bin/env python3
#
# By Le Chen and Chatgpt
# chenle02@gmail.com / le.chen@auburn.edu
# Created at Wed Mar  6 10:16:49 AM EST 2024
#

import sqlite3
import numpy as np
import joblib
import pandas as pd

# Connect to your SQLite database
conn = sqlite3.connect('./simulation_results.db')

# Create a cursor object
cursor = conn.cursor()

# SQL query to select distinct types from the Simulations table
query_types = "SELECT DISTINCT type FROM Simulations ORDER BY type ASC"

# Execute the query for distinct types
cursor.execute(query_types)

# Fetch all distinct type results
distinct_types = cursor.fetchall()

# Initialize a dictionary to store the fluctuations
fluctuations_dict = {}

for type_value in distinct_types:
    type_value = type_value[0]  # Extract the type value
    print(f"Processing type: {type_value}")

    # SQL query to select distinct widths for the current type
    query_widths = "SELECT DISTINCT width FROM Simulations WHERE type = ? ORDER BY width ASC"
    cursor.execute(query_widths, (type_value,))

    # Fetch all distinct width results for this type
    distinct_widths = cursor.fetchall()

    # Initialize the sub-dictionary for this type if not already initialized
    if type_value not in fluctuations_dict:
        fluctuations_dict[type_value] = {}

    for width_value in distinct_widths:
        width_value = width_value[0]  # Extract the width value
        print(f"Processing width: {width_value}")

        # Prepare the SQL query to select fluctuation values for the current type and width
        query_fluctuations = "SELECT fluctuation FROM Simulations WHERE type = ? AND width = ?"
        cursor.execute(query_fluctuations, (type_value, width_value))

        # Fetch all fluctuation results for this type and width
        fluctuations = cursor.fetchall()

        # # Convert fluctuations to a suitable format (e.g., list of NumPy arrays)
        # # Assuming each fluctuation is a binary blob that can be directly converted into a NumPy array
        # fluctuations_list = [np.frombuffer(fluctuation[0], dtype=np.float64) for fluctuation in fluctuations]
        #
        # # Store the fluctuations list in the sub-dictionary for the current type and width
        # fluctuations_dict[type_value][width_value] = fluctuations_list
        #
        # # Save  the fluctuations_dict to a csv file for further analysis
        # df = pd.DataFrame(fluctuations_list)
        # df.to_csv(f"fluctuations_{type_value}_w={width_value}.csv")

# Clean up: close the cursor and connection
cursor.close()
conn.close()

print("Saving fluctuations_dict to disk...")
joblib.dump(fluctuations_dict, 'fluctuations_dict.joblib')
