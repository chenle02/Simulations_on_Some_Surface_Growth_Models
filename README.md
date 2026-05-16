
[![CI](https://github.com/chenle02/Simulations_on_Some_Surface_Growth_Models/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/chenle02/Simulations_on_Some_Surface_Growth_Models/actions/workflows/ci.yml)
[![Publish Python Package to PyPI](https://github.com/chenle02/Simulations_on_Some_Surface_Growth_Models/actions/workflows/workflow.yml/badge.svg?branch=main)](https://github.com/chenle02/Simulations_on_Some_Surface_Growth_Models/actions/workflows/workflow.yml)

# Simulations on Some Surface Growth Models

<!-- Visual example removed; see examples.md for usage examples -->

This repository contains simulations for various surface growth models,
developed initially as a final exam project for Math-7820 (Applied Stochastic
Processes I), Fall 2023 at Auburn University. It was further expanded as a
course project for Math-7830 (Applied Stochastic Processes II), Spring 2024.
More information about the courses can be found here: [Math-7820 Fall
2023](http://webhome.auburn.edu/~lzc0090/teaching/2023_Fall_Math7820/).

These simulations provide insights into the dynamics and characteristics of
surface growth processes, inspired by theoretical models and real-world
applications.

## Features

- Comprehensive simulations of different surface growth models.
- Easy-to-use interface for conducting and analyzing simulations.
- Detailed documentation for understanding and extending the simulations.

## Install

```bash
# Standard install (pure Python + numpy fast path)
pip install tetris-ballistic

# Recommended: HPC-optimized install with numba (~380x faster on the
# piece_19 / 1x1 workload, see Performance below)
pip install 'tetris-ballistic[hpc]'

# Development install (pytest, ruff, benchmarks)
pip install -e '.[dev,hpc]'
```

Pypi link: [here](https://pypi.org/project/tetris-ballistic/).

## Sample Usage

Usage examples are provided in [examples.md](examples.md), which contains Python snippets demonstrating how to run simulations.

Here are some simulations [examples](examples.md)

## Performance

As of v2.0.0, `Tetris_Ballistic.Simulate()` runs the entire 1x1-piece
configuration (the typical `Piece-19` workload used in experimental
papers) inside a numba `@njit` kernel. Cumulative speedup vs the v1
pure-Python path:

| Strip width `L` | Steps | v1 wall-clock | v2 wall-clock | Speedup |
|----------------:|------:|--------------:|--------------:|--------:|
| 50              | 2,498 | 2.0 s         | 0.02 s        | **85×** |
| 100             |10,878 | 16.7 s        | 0.09 s        | **182×**|
| 200             |43,064 | 140.2 s       | 0.37 s        | **380×**|

(Measured on the same machine with `tests/benchmark_baseline.py`.)
Steps/sec is now ~115K and *flat across* `L`, vs the v1 trend that
dropped from 1239 down to 307 steps/s as L grew — confirming the
O(W×H) per-step bookkeeping has been eliminated.

For mixed-piece configurations the kernel is bypassed transparently
and the v1 dispatch path is used. Set `TETRIS_USE_KERNEL=0` to force
the v1 path explicitly (debug/audit).

## HPC usage (Slurm-array)

For 10K+ run experiments on a Slurm cluster (e.g. Auburn Easley):

```bash
# Copy the templates into your experiment dir
cp experiments/templates/grid.yaml experiments/exp14/grid.yaml
cp experiments/templates/job_array.slurm experiments/exp14/

# Edit grid.yaml to set pcts/widths/seeds/ratio.
# Compute total task count: len(pcts) * len(widths) * len(seeds)
# Edit job_array.slurm: set --array=0-(N-1) and --partition.

# Submit:
sbatch experiments/exp14/job_array.slurm
```

Each array task runs ONE cell via `python -m
tetris_ballistic.scripts.run_one_cell --task-id $SLURM_ARRAY_TASK_ID`.
Outputs land in `experiments/exp14/results/pct_NN/L_LLLL/seed_SSS.joblib`.
The job is idempotent — re-submitting after preemption skips completed
cells. After the array finishes, run the streaming KPZ analysis:

```bash
python -m tetris_ballistic.scripts.run_kpz_analysis \
    --exp-dir experiments/exp14/results \
    --resume   # picks up where it left off if needed
```

## Documentation

For detailed information about the package and its functionalities, visit our [Read the Docs](https://simulations-on-some-surface-growth-models.readthedocs.io/main/) page.

## How to Contribute

Contributions to this project are welcome! To contribute, please:

1. Fork the repository.
2. Create a new branch for your feature.
3. Add your changes and commit them.
4. Push to the branch.
5. Create a new pull request.

## References

1. Le Chen's Graduate Student Seminar talk on surface growth models: [here](https://github.com/chenle02/Graduate_Student_Seminars_by_Le_Chen/blob/main/2023-11-01/readme.md).
2. Barabási and Stanley, ''Fractal Concepts in Surface Growth'', Cambridge University Press, 1995.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

For any queries or further discussion, feel free to contact us at 

- Le Chen: [chenle02@gmail.com] or [le.chen@auburn.edu].
- Ian Ruau: [ian.ruau@auburn.edu].
- Mauricio Montes: [mauricio.montes@auburn.edu].
