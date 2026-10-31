# Performance and HPC workflow

This page holds the performance notes and the Slurm-array workflow for the
2.x line on `main` (unreleased; install from source). It was moved here from
the README without changes to its technical content. The PyPI 1.2.x release
does not include the numba kernel or the HPC scripts described below.

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
Each cell also has a canonical YAML snapshot, a SHA-256 manifest, and a
persistent advisory lock. Re-submission reuses a cell only after its exact
configuration and software identities, both payload checksums, and terminal
completion invariants validate. Bare legacy joblibs, stale configurations,
partial writes, and corrupt outputs fail closed instead of being skipped.
After the array finishes, first validate the declared managed grid and reduce
it to the explicit, reanalysis-complete trace layout:

```bash
python -m tetris_ballistic.scripts.reduce_traces \
    --in experiments/exp14/results \
    --out experiments/exp14/traces \
    --grid-spec experiments/exp14/grid.yaml

python -m tetris_ballistic.scripts.run_kpz_analysis \
    --trace-root experiments/exp14/traces \
    --input-layout reduced \
    --percentage-convention sticky-fraction \
    --model-profile piece-19-one-cell-v1 \
    --out-dir experiments/exp14/analysis \
    --pcts 5,50,90,95,98,99 \
    --widths 50,80,100,150,200 \
    --resume
```

`--resume` reuses a cell only when its payload and commit-marker manifest match
the exact trace bytes and ordered seed inventory, requested percentage and
width, percentage convention, executable model profile, estimator settings,
package source/dependency identity, and bootstrap RNG policy. A stale,
corrupt, partial, or identity-mismatched cache fails
closed; after reviewing the discrepancy, use `--replace` to regenerate it
explicitly. `--aggregate-only` requires the same complete requested grid and
rebuilds summaries from those validated cells rather than globbing old
`per_pct` files.

The required percentage convention is part of every cache and summary
identity; exp14 uses `sticky-fraction`, while exp13 uses
`nonsticky-fraction`. Managed hierarchical
`results/pct_NN/L_LLLL/seed_SSS.joblib` files are not
accepted directly by the analysis runner. Historical flat exp13 joblibs can be
read only by selecting `--input-layout legacy-flat --percentage-convention
nonsticky-fraction --model-profile piece-19-one-cell-v1`; this is an explicit
compatibility path for trusted local artifacts, since joblib loading executes
Python pickle data.

Managed CLI output enforces the publication-grade protocol floor of 10
independent runs per ensemble and 200 case-bootstrap replicates. Lower-count
calls are estimator-level exploratory work and cannot be published by this
runner as authoritative 95% intervals.

See the [KPZ analysis currentness contract](KPZ-ANALYSIS-CURRENTNESS.md)
for the complete identity, locking, publication, and recovery rules.

