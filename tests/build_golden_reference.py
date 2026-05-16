#!/usr/bin/env python3
"""Build the golden reference for correctness tests.

Runs 9 deterministic simulations with the CURRENT (Phase-0) code and
saves Fluctuation + AvergeHeight arrays as .npz. Every later phase
must reproduce these arrays bit-for-bit (or document tolerable drift).

Run from repo root: .venv/bin/python tests/build_golden_reference.py
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


GRID = [
    (50, 50, 0),
    (50, 100, 0),
    (50, 200, 0),
    (50, 50, 10),
    (50, 100, 10),
    (50, 200, 10),
    (50, 50, 20),
    (50, 100, 20),
    (50, 200, 20),
]

RATIO = 2

OUT_DIR = Path(__file__).parent / "golden_reference"


def build_density_for_piece_19_combined(pct: int) -> dict:
    """Replicate exp13's 'piece_19_combined_percentage_NN' density.

    Verified by inspecting
    experiments/exp13/config_piece_19_combined_percentage_50_w=100_seed=0.yaml:
    pct=50 → "Piece-19: [50, 50]" (first slot 50, second slot 50).
    All other pieces are [0, 0]. The semantic of "first slot" vs
    "second slot" (sticky vs non-sticky) is intentionally left
    unspecified here — we only require bit-equality with the existing
    code path, not a re-interpretation of the protocol.
    """
    density = {f"Piece-{i}": [0, 0] for i in range(20)}
    density["Piece-19"] = [100 - pct, pct]
    return density


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    timings: dict[str, float] = {}
    print(f"Building golden reference in {OUT_DIR}")
    for pct, L, seed in GRID:
        out_path = OUT_DIR / f"pct{pct:02d}_L{L}_seed{seed}.npz"
        if out_path.exists():
            print(f"  skip {out_path.name} (exists)")
            continue
        density = build_density_for_piece_19_combined(pct)
        height = L * RATIO
        steps = RATIO * L * L
        t0 = time.perf_counter()
        tb = Tetris_Ballistic(
            width=L, height=height, steps=steps, seed=seed, density=density
        )
        tb.Simulate()
        t1 = time.perf_counter()
        elapsed = t1 - t0
        timings[out_path.name] = elapsed
        n = int(tb.FinalSteps)
        np.savez(
            out_path,
            fluctuation=tb.Fluctuation[:n].astype(np.float64),
            avg_height=tb.AvergeHeight[:n].astype(np.float64),
            final_steps=np.array(n, dtype=np.int64),
            width=np.array(L, dtype=np.int64),
            height=np.array(height, dtype=np.int64),
            steps=np.array(steps, dtype=np.int64),
            seed=np.array(seed, dtype=np.int64),
            pct=np.array(pct, dtype=np.int64),
        )
        rate = n / elapsed if elapsed > 0 else 0.0
        print(
            f"  built {out_path.name} | FinalSteps={n} | "
            f"{elapsed:.2f}s | {rate:.0f} steps/s"
        )
    print(f"\nTotal builds: {len(timings)}; total time: {sum(timings.values()):.2f}s")


if __name__ == "__main__":
    main()
