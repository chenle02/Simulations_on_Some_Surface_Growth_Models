# Tests Directory Overview

This directory contains pytest-based tests for the `tetris_ballistic` package.
All tests are executed in complete isolation, and any file-based outputs (e.g., `*.txt`, `*.png`, `*.mp4`, `*.joblib`, etc.) are created in a fresh temporary working directory.  This ensures the project root remains clean and free of test artifacts.

## Key Components

- **conftest.py**
  - Defines an autouse fixture `change_cwd` that switches the current working directory to a new `tmp_path` for each test.
  - Any file operations using relative paths will write into this temporary directory.

- **configs_dir**
  - Tests that need to load YAML configuration files should import `configs_dir` from `tetris_ballistic.retrieve_default_configs`.
  - This constant points to the package’s `configs/` folder containing default simulation settings.

## Writing New Tests

1. Simply create or append to files in this directory as usual; tests can open files by relative name (e.g., `open("output.txt", "w")`) without polluting the repo.
2. When you need to reference default config files, use:
   ```python
   from tetris_ballistic.retrieve_default_configs import configs_dir
   path = os.path.join(configs_dir, "config_piece_0_sticky.yaml")
   ```
3. If you need finer control over temporary paths (e.g., nested directories), you can still request pytest’s `tmp_path` fixture explicitly in your test signature.

## Running the Test Suite

    pytest -q

No manual cleanup is required; temporary directories are removed automatically when pytest finishes.
## Test Organization

Below is an overview of the main test modules and what they cover:

- **counter_holes/**
  - `test_CountHoles.py`: verifies hole-counting algorithms (`count_holes`, `count_holes_stack`).
- **indivisual-pieces/**
  - Per-piece tests (`test_O.py`, `test_I.py`, etc.) to validate individual tetromino placement and output.
- **load_save_config/**
  - `test_save_config.py`: tests saving to and loading from YAML configuration files.
- **Load_Save_Simulations/**
  - `test_Load_Save_Simulations.py`: tests saving simulation state to Joblib and reloading it, plus substrate PNG export.
- **sample/**
  - `test_sample.py`: validates sampling distributions of tetromino pieces.
- **ShowData/**
  - `test_showdata.py`, `test_showdata_images.py`: tests the `ShowData()` plot and image export functionality.
- **simulation/**
  - `test_simulation.py`: end-to-end simulation runs with joblib caching and GIF/MP4 visualization.
  - `test_Substrate2PNG.py`: exports substrate frames to PNG.
- **sweepparameters/**
  - `test_sweepParameters.py`: tests parameter sweep utilities (`sweep_parameters.py`).
- **test_data_analysis/**
  - `test_retreiv_config.py`: tests `retrieve_default_configs` and `retrieve_fluctuations` for joblib data aggregation.
- **test_imageloader/**
  - `test_imageloader.py`: validates `TetrominoImageLoader.get_image_path()`.
- **test_piece-9_nonsticky/**
  - `test_piece_9-5_nonsticky.py`: tests non-sticky behavior for specific piece combinations.
- **test_plotstat/**
  - `test_plotstat.py`: tests statistical plotting (`PlotStat()`).
- **test_resize/**
  - `test_Load_resize.py`: tests substrate resizing mid-simulation and re-visualization.
- **test_retreive_config/**
  - `test_retreiv_config.py`: tests default config retrieval patterns.
- **test_SampleDist/**
  - `test_simulation.py`: tests sample distribution metrics in the simulation output.
- **test_slope/**
  - `test_slope.py`: verifies slope computation methods (`ComputeSlope` variants).
- **tests_piece-14/**
  - `test_piece_14.py`: tests slope behavior for piece 14 under various conditions.
- **test_Sweep/**
  - `test_Sweep.py`: tests high-level parameter sweep scripts and job submission logic.
- **visualization/**
  - `test_visualize_simulation.py`, `test_visualize_simulation_parallel.py`: tests `visualize_simulation()` animation generation.