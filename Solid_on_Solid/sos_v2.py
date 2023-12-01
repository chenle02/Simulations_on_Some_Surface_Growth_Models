
import pandas as pd
import matplotlib.pyplot as plt
import random
import time

start_time = time.time()

h, w = 10, 10
p_desorp, p_grow = 0.1, 0.1

# Initialization
base_df = pd.DataFrame(0, index=range(h), columns=range(w))
base_df.iloc[-1] = 1
base_df.iloc[-2, ::2] = 1

# Store the position to be updated for each column
update_positions = [h - 1] * w

while not base_df.iloc[2].eq(1).any():
    p_plus, p_minus = random.random(), random.random()
    col = random.randint(1, w - 2)
    aa = update_positions[col]

    if aa > 0 and base_df.iloc[aa, col] == 0:
        if base_df.iloc[aa, col + 1] == 0 and base_df.iloc[aa, col - 1] == 0 and p_plus <= p_desorp:
            base_df.iloc[aa:min(aa + 2, h), col] = 0
            update_positions[col] += 2
            continue

        if base_df.iloc[aa, col + 1] == 1 and base_df.iloc[aa, col - 1] == 1 and p_minus >= p_grow:
            base_df.iloc[aa - 1:aa + 1, col] = 1
            update_positions[col] -= 1

    update_positions[col] = max(0, update_positions[col] - 1)

# Display the DataFrame
plt.imshow(base_df, cmap='gray')
plt.show()

# Calculating the running time of code
elapsed_time = (time.time() - start_time) / 60
print(f"Elapsed time: {elapsed_time} minutes")
