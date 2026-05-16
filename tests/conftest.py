"""Shared pytest fixtures for tetris_ballistic test suite."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


GOLDEN_DIR = Path(__file__).parent / "golden_reference"

GOLDEN_GRID = [
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


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return GOLDEN_DIR


@pytest.fixture(params=GOLDEN_GRID, ids=lambda p: f"pct{p[0]:02d}_L{p[1]}_seed{p[2]}")
def golden_cell(request, golden_dir):
    pct, L, seed = request.param
    path = golden_dir / f"pct{pct:02d}_L{L}_seed{seed}.npz"
    if not path.exists():
        pytest.skip(f"Golden reference {path.name} not yet built")
    data = np.load(path)
    return {
        "pct": pct,
        "L": L,
        "seed": seed,
        "fluctuation": data["fluctuation"],
        "avg_height": data["avg_height"],
        "final_steps": int(data["final_steps"]),
    }
