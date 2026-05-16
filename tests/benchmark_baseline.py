#!/usr/bin/env python3
"""Capture baseline timings on the current code path.

This is the denominator for every later phase's speedup claim. It is
NOT part of the pytest suite — run manually:

    .venv/bin/python tests/benchmark_baseline.py [--output PATH]

The 3 representative configs span small/medium/large work:
  - L=50,  steps=5_000   (~10 s)
  - L=100, steps=20_000  (~40 s)
  - L=200, steps=80_000  (~150 s)

For Phase 4 we additionally measure steps/sec which removes the effect
of varying ``FinalSteps`` (the simulation stops early when the domain
ceiling is reached).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tests.build_golden_reference import build_density_for_piece_19_combined
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

CONFIGS = [
    ("small",  50,  100,  5_000),
    ("medium", 100, 200, 20_000),
    ("large",  200, 400, 80_000),
]
PCT = 50
SEED = 42


def time_one(width: int, height: int, steps: int, warmup: bool = True) -> dict:
    """Time one simulation. If warmup=True, run a tiny simulation first
    so any JIT compilation cost (Phase 4b kernel) is amortized."""
    density = build_density_for_piece_19_combined(PCT)
    if warmup:
        warm = Tetris_Ballistic(width=10, height=20, steps=50, seed=0, density=density)
        warm.Simulate()
    t0 = time.perf_counter()
    tb = Tetris_Ballistic(
        width=width, height=height, steps=steps, seed=SEED, density=density
    )
    tb.Simulate()
    t1 = time.perf_counter()
    elapsed = t1 - t0
    n_steps = int(tb.FinalSteps)
    return {
        "width": width,
        "height": height,
        "steps_requested": steps,
        "steps_executed": n_steps,
        "elapsed_seconds": elapsed,
        "steps_per_second": n_steps / elapsed if elapsed > 0 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path,
        default=Path(__file__).parent / "golden_reference" / "baseline_timings.json",
        help="Where to write the JSON timings",
    )
    parser.add_argument(
        "--label", default="phase0_baseline",
        help="Tag the timings (e.g. 'phase1_heights', 'phase4_numba')",
    )
    args = parser.parse_args()
    results = {"label": args.label, "configs": {}}
    for name, w, h, s in CONFIGS:
        print(f"  timing {name}: L={w} h={h} steps={s} ...", flush=True)
        results["configs"][name] = time_one(w, h, s)
        last = results["configs"][name]
        print(
            f"    {last['elapsed_seconds']:.2f} s, "
            f"{last['steps_per_second']:.0f} steps/s, "
            f"FinalSteps={last['steps_executed']}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
