import sqlite3
import numpy as np
import joblib
import pandas as pd
# from tetris_ballistic.image_loader import TetrominoImageLoader as til

# Connect to your SQLite database
conn = sqlite3.connect('./simulation_results.db')

# Create a cursor object
cursor = conn.cursor()

stickiness = ["sticky", "nonsticky", "combined"]
for stick in stickiness:
    # SQL: select types for this stickiness from unified Simulations table
    query_types = (
        "SELECT DISTINCT type FROM Simulations"
        " WHERE sticky = ? ORDER BY type ASC"
    )
    cursor.execute(query_types, (stick,))
    distinct_types = [row[0] for row in cursor.fetchall()]

    # Build dictionary: { type: { width: {data} } }
    results = {}
    for type_value in distinct_types:
        print(f"Processing type: {type_value} (sticky={stick})")
        # widths for this type and stickiness
        query_widths = (
            "SELECT DISTINCT width FROM Simulations"
            " WHERE type = ? AND sticky = ? ORDER BY width ASC"
        )
        cursor.execute(query_widths, (type_value, stick))
        widths = [row[0] for row in cursor.fetchall()]
        results[type_value] = {}
        for width_value in widths:
            print(f"  Width: {width_value}")
            # fetch fluctuations and slope estimates
            query_data = (
                "SELECT fluctuation, endpoint_slope, endpoint_error,"
                " local_median, local_half_iqr"
                " FROM Simulations"
                " WHERE type = ? AND width = ? AND sticky = ?"
            )
            cursor.execute(query_data, (type_value, width_value, stick))
            rows = cursor.fetchall()
            # parse into lists
            fl_list = []
            ep_slopes = []
            ep_errors = []
            local_meds = []
            local_iqrs = []
            for fl_blob, ep_s, ep_e, lm, li in rows:
                fl_list.append(np.frombuffer(fl_blob, dtype=np.float64))
                ep_slopes.append(ep_s)
                ep_errors.append(ep_e)
                local_meds.append(lm)
                local_iqrs.append(li)
            # store
            results[type_value][width_value] = {
                'fluctuations': fl_list,
                'endpoint_slopes': ep_slopes,
                'endpoint_errors': ep_errors,
                'local_medians': local_meds,
                'local_half_iqrs': local_iqrs,
            }
    # save per-stickiness result
    out_file = f"fluctuations_{stick}_dict.joblib"
    print(f"Saving results to {out_file}")
    joblib.dump(results, out_file)

# Clean up: close the cursor and connection
cursor.close()
conn.close()

