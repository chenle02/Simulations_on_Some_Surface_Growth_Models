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
  
## Post-processing and Visualization

### 1. Extracting Fluctuation Data
- **analysis.py**  
  Queries `simulation_results.db` to extract raw fluctuation BLOBs for each simulation run and organizes them into nested dictionaries `{type_value: {width_value: [np.ndarray, ...]}}`.  
  Saves three joblib files:
  - `fluctuations_combined_dict.joblib`
  - `fluctuations_nonsticky_dict.joblib`
  - `fluctuations_sticky_dict.joblib`

### 2. Plotting Raw Fluctuations
- **plotfluctuations.py**  
  Reads the fluctuations joblib files and plots fluctuation vs. time for each stickiness category (combined, nonsticky, sticky) and type.  
  Usage:
  ```bash
  python3 plotfluctuations.py [--with_ci]
  ```
  - Pass `--with_ci` to include 95% confidence intervals around the mean curves.  
  Output images:
  - `combined_original_<stickiness>_<type>.png`
  - `combined_original_CI_<stickiness>_<type>.png` (when CI enabled)

### 3. Log–Log Scaling Collapse
- **loglogplot.py**  
  Loads the fluctuations dicts to produce log–log plots rescaled by width:
    - X offset = log10(time) – (3/2)·log10(width)
    - Y offset = log10(fluctuation) – (1/2)·log10(width)
  Usage:
  ```bash
  python3 loglogplot.py
  ```
  Output images:
  - `loglog_plot_<stickiness>_<type>.png`

### 4. Utility Scripts
- **db.py**  
  Python helper for ad-hoc queries on `simulation_results.db`.
- **checkstatus.sh**  
  Shell script to monitor simulation progress by checking for generated `.joblib` files and simulation logs.
- **db_status.sh**  
  Shell script to report record counts in the database tables.

## Requirements
- Python 3.13  
- numpy  
- scipy (for confidence intervals in `plotfluctuations.py`)  
- matplotlib  
- joblib  
- sqlite3 (built-in)  
- `tetris_ballistic` package installed (e.g. `pip install -e ./tetris_ballistic`)
