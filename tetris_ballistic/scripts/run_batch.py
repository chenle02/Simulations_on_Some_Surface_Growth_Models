#!/usr/bin/env python3
"""Run a contiguous range of grid cells in ONE process.

Numba JIT compilation costs ~30-50 s per fresh Python process, so a
one-cell-per-Slurm-task array pays that tax N times.  This batch runner
compiles once and then streams many cells in a hot loop, cutting the
per-cell overhead to zero after warm-up.

Task mapping for a Slurm array of ``A`` tasks over a grid of ``T`` cells:
each array index ``i`` owns the block ``[i*chunk, (i+1)*chunk)`` where
``chunk = ceil(T / A)``. Cells are reusable only through the managed manifest
gate, so re-submitting after preemption resumes complete identity/checksum-
validated work and rejects stale or partial output.

Usage
-----
    # one array task covering a block of `chunk` cells
    python -m tetris_ballistic.scripts.run_batch \\
        --grid-spec experiments/exp14/grid.yaml \\
        --out-dir /scratch/$USER/tetris14/results \\
        --array-index $SLURM_ARRAY_TASK_ID --n-arrays 120

    # explicit half-open cell range
    python -m tetris_ballistic.scripts.run_batch \\
        --grid-spec grid.yaml --out-dir out --start 0 --stop 30
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.run_artifacts import CellDisposition
from tetris_ballistic.scripts.run_one_cell import (
    decode_task_id,
    grid_size,
    load_grid_spec,
    run_cell_result,
)


def _warm_up_kernel() -> None:
    """Trigger numba compilation once on a tiny throwaway simulation."""
    from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

    density = {f"Piece-{i}": [0, 0] for i in range(20)}
    density["Piece-19"] = [50, 50]
    tb = Tetris_Ballistic(width=8, height=40, steps=64, seed=0, density=density)
    tb.Simulate()


def _resolve_range(args, total: int) -> tuple[int, int]:
    if args.start is not None or args.stop is not None:
        start = args.start or 0
        stop = args.stop if args.stop is not None else total
        return start, min(stop, total)
    if args.array_index is None or args.n_arrays is None:
        raise SystemExit("give either --start/--stop or --array-index + --n-arrays")
    chunk = math.ceil(total / args.n_arrays)
    start = args.array_index * chunk
    stop = min(start + chunk, total)
    return start, stop


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--grid-spec", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--array-index", type=int)
    p.add_argument("--n-arrays", type=int)
    p.add_argument("--start", type=int)
    p.add_argument("--stop", type=int)
    p.add_argument("--flat-output", action="store_true")
    args = p.parse_args()

    spec = load_grid_spec(args.grid_spec)
    total = grid_size(spec)
    start, stop = _resolve_range(args, total)

    print(f"[batch] grid total={total} cells; this task owns [{start}, {stop}) "
          f"= {stop - start} cells", flush=True)
    if start >= stop:
        print("[batch] empty range, nothing to do", flush=True)
        return

    t0 = time.time()
    _warm_up_kernel()
    print(f"[batch] kernel warm-up done in {time.time() - t0:.1f}s", flush=True)

    n_done = n_skip = n_fail = 0
    for tid in range(start, stop):
        pct, L, seed = decode_task_id(tid, spec)
        try:
            result = run_cell_result(
                spec, pct, L, seed, args.out_dir, flat=args.flat_output
            )
            if result.disposition is CellDisposition.CREATED:
                n_done += 1
            else:
                n_skip += 1
        except Exception as exc:  # noqa: BLE001 - one bad cell must not kill the block
            n_fail += 1
            print(f"[batch] FAIL tid={tid} pct={pct} L={L} seed={seed}: {exc}",
                  flush=True)

    dt = time.time() - t0
    print(f"[batch] block done in {dt:.1f}s: {n_done} run, {n_skip} skipped, "
          f"{n_fail} failed", flush=True)
    if n_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
