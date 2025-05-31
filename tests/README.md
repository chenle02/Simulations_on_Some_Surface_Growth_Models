<!--
This README provides an overview of the project's test suite, how to run tests,
and a description of each test module and its responsibilities.
-->
# Test Suite Overview

This directory (and the test directories across the project) contains the automated
tests that verify the functionality of each component of the application.

## Running Tests

We use [pytest](https://docs.pytest.org/) as the test runner. From the project root:
```
pytest
```

To run a subset of tests (e.g., for a specific module or directory):
```
pytest counter_holes
pytest simulation/test_simulation.py
```

For verbose output and detailed logs:
```
pytest -v
```

## Test Organization

Tests are organized into two categories:

1. **Package-Level Tests**: Located alongside the code they verify.
2. **Standalone Test Directories**: Top-level directories prefixed with `test_` or `tests_`.

Below is a breakdown of each location and its purpose.

### Package-Level Tests

- **counter_holes**
  - `test_CountHoles.py`: Verifies that `CountHoles` correctly counts holes in a single substrate frame.
  - `test_CountHoles_stack.py`: Ensures hole counting works across stacked frames (time series).

- **indivisual-pieces**
  - `test_<Shape>.py` (e.g., `test_I.py`, `test_T.py`): Confirms that each Tetris piece generator produces the correct block coordinates.

- **load_save_config**
  - `test_save_config.py`: Tests saving configurations to YAML, including handling of `None` values.

- **Load_Save_Simulations**
  - `test_Load_Save_Simulations.py`: Checks serialization and deserialization of simulation results (Joblib, metadata, frames).

- **sample**
  - `test_sample.py`: Verifies random sampling logic and output consistency.

- **ShowData**
  - `test_showdata.py`: Tests tabular data export (e.g., CSV/HTML) for summary reports.
  - `test_showdata_images.py`: Validates generation of PNG images for data visualizations.

- **simulation**
  - `test_simulation.py`: Covers core simulation engine for different configurations (1x1, Tetris, sticky/non-sticky).
  - `test_Substrate2PNG.py`: Verifies conversion of substrate state arrays into PNG images.

- **sweepparameters**
  - `test_sweepParameters.py`: Ensures parameter grid generation for sweep experiments is correct.

### Standalone Test Directories

- **test_data_analysis**
  - `test_retreiv_config.py`: Tests data retrieval and insertion utilities for experiment analysis (SQLite, Joblib).

- **test_imageloader**
  - `test_imageloader.py`: Validates image-loading utilities against known reference outputs.

- **test_piece-9_nonsticky**
  - `test_piece_9-5_nonsticky.py`: Tests non-sticky behavior for piece 9 under specific parameters.

- **test_plotstat**
  - `test_plotstat.py`: Verifies statistical plotting routines against reference YAML and text outputs.

- **test_resize**
  - `test_Load_resize.py`: Tests loading and resizing of simulation videos and Joblib artifacts.

- **test_retreive_config**
  - `test_retreiv_config.py`: Ensures default configuration lookup functions behave as expected.

- **test_SampleDist**
  - `test_simulation.py`: Checks sample distribution results for various configurations (1x1, Tetris, sticky/non-sticky).

- **test_slope**
  - `test_slope.py`: Tests slope calculation (deposit rate) for piece configurations (e.g., piece 14 sticky/non-sticky).

- **tests_piece-14**
  - `test_piece_14.py`: End-to-end verification for piece 14 simulation outputs.

- **test_Sweep**
  - `test_Sweep.py`: Tests full parameter sweep execution scripts and SQL query generation.

- **visualization**
  - `test_visualize_simulation.py`: Validates single-threaded simulation visualization outputs (MP4, PNG).
  - `test_visualize_simulation_parallel.py`: Tests parallel visualization workflows for multi-simulation jobs.

## Adding New Tests

- Name files using the `test_*.py` pattern.
- Use pytest fixtures for common setup/teardown routines.
- Include reference files (`.txt`, `.yaml`, images) when testing visual or numeric outputs.

---

*This README will help contributors understand how the test suite is structured and maintained.*

