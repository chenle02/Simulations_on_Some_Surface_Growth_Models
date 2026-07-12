#!/usr/bin/env python3
"""Regenerate small JSON-only legacy trajectory fixtures.

Run from the repository root with the project virtual environment.  The script
forces the general legacy dispatch path and never writes pickle/joblib data.
"""

from __future__ import annotations

import json
import os
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np

from tetris_ballistic.legacy_adapter import LEGACY_ADAPTER_VERSION
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "fixtures" / "legacy-trajectories-v1.json"

CASES = (
    {
        "name": "one-cell-combined",
        "piece_id": 19,
        "weights": [1, 1],
        "width": 12,
        "height": 120,
        "steps": 40,
        "seed": 7,
    },
    {"name": "o-supported", "piece_id": 0, "weights": [1, 0], "width": 12, "height": 120, "steps": 20, "seed": 11},
    {"name": "l-first-contact", "piece_id": 3, "weights": [0, 1], "width": 12, "height": 120, "steps": 20, "seed": 13},
    {"name": "t-mixed-contact", "piece_id": 11, "weights": [1, 1], "width": 12, "height": 120, "steps": 20, "seed": 17},
)


def _density(piece_id: int, weights: list[int]) -> dict[str, list[int]]:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density[f"Piece-{piece_id}"] = list(weights)
    return density


def _run(case: dict[str, Any]) -> dict[str, Any]:
    simulation = Tetris_Ballistic(
        width=case["width"],
        height=case["height"],
        steps=case["steps"],
        seed=case["seed"],
        density=_density(case["piece_id"], case["weights"]),
    )
    with redirect_stdout(StringIO()):
        simulation.Simulate()
    final_steps = int(simulation.FinalSteps)
    substrate = np.ascontiguousarray(simulation.substrate)
    return {
        **case,
        "average_height": simulation.AvergeHeight[:final_steps].tolist(),
        "final_steps": final_steps,
        "fluctuation": simulation.Fluctuation[:final_steps].tolist(),
        "occupied_cells": int(np.count_nonzero(substrate)),
        "sample_dist": simulation.SampleDist.astype(int).tolist(),
        "substrate_dtype": substrate.dtype.str,
        "substrate_sha256": sha256(substrate.tobytes()).hexdigest(),
        "substrate_shape": list(substrate.shape),
    }


def main() -> None:
    previous = os.environ.get("TETRIS_USE_KERNEL")
    os.environ["TETRIS_USE_KERNEL"] = "0"
    try:
        payload = {
            "fixture_version": "1.0.0",
            "generated_by": "tests/build_legacy_golden.py",
            "generated_from_git_sha": "09b0a53",
            "legacy_adapter_version": LEGACY_ADAPTER_VERSION,
            "legacy_dispatch_forced": True,
            "cases": [_run(case) for case in CASES],
        }
    finally:
        if previous is None:
            os.environ.pop("TETRIS_USE_KERNEL", None)
        else:
            os.environ["TETRIS_USE_KERNEL"] = previous
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
