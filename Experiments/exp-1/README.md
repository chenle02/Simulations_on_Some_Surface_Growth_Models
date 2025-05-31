# Experiment 1: Parameter Sweep and Slope Estimation

This experiment performs a parameter sweep over Tetris Ballistic simulations,
computes scaling exponents (growth‐exponent slopes) for each run, and stores
the results in a SQLite database.

## Files
- **Sweep.py**: Launches simulations for various widths, seeds, and configs.
- **simulation_results.db**: SQLite database created by `insert_joblibs`, table `Simulations`.
- **simulation_progress.log**: Progress log for completed simulations.

## Usage

1. Run the parameter sweep (will generate `.joblib` files):
   ```bash
   cd experiments/Exp-1
   python3 Sweep.py
   ```

2. Insert simulation outputs into the database, including the estimated
   median local slope (exponent) in the `slope` column:
   ```bash
   python3 -c "from tetris_ballistic.data_analysis_utilities import insert_joblibs;\
   insert_joblibs('config_*_w=*_*seed=*.joblib')"
   ```

   By default, `insert_joblibs` uses the **median of local log–log slopes**
   as the stored exponent. If local‐slope computation fails, it falls back
   to the endpoint slope (between 10% and 90% thresholds).

3. Inspect the database:
   ```bash
   sqlite3 simulation_results.db
   sqlite> SELECT type, sticky, width, random_seed, slope FROM Simulations;
   ```

## What is stored

-- **slope**: Robust estimate of the growth exponent v.
  1) First, compute the **local** slopes d log Fluc / d log time via centered finite
     differences, discarding the first and last 10% of points.
     • The **median** of these local slopes is the primary estimate and the
       half‐interquartile range (half‐IQR) is shown as its uncertainty.
  2) If the local‐slope estimate is too noisy (half‐IQR > 50% of the median),
     fallback to the **endpoint** slope (between 10% and 90% of max fluctuation).
  The final chosen slope is stored in the `slope` column.

Feel free to customize `Sweep.py` (e.g. adding/removing config patterns or seeds).
