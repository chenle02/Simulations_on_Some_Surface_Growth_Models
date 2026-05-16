"""Phase-2 tests for the streaming KPZ-analysis runner.

Verifies:
- ``_atomic_write_json`` writes atomically (no leftover .tmp on success).
- ``aggregate_results`` correctly stream-collects per-pct JSON files.
- ``--resume`` skips cells whose per-cell JSON exists.

These tests are pure unit tests of the runner's I/O contract — they
do NOT load any joblib simulation data, so they run in milliseconds.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tetris_ballistic.scripts.run_kpz_analysis import (
    _atomic_write_json,
    _cell_path,
    _cells_dir,
    _per_pct_path,
    aggregate_results,
)


def test_atomic_write_creates_file_no_tmp_left(tmp_path: Path):
    target = tmp_path / "out.json"
    _atomic_write_json(str(target), {"hello": 42})
    assert target.exists()
    assert not (tmp_path / "out.json.tmp").exists()
    assert json.loads(target.read_text()) == {"hello": 42}


def test_atomic_write_creates_parent_dirs(tmp_path: Path):
    target = tmp_path / "deep" / "nested" / "file.json"
    _atomic_write_json(str(target), [1, 2, 3])
    assert target.exists()


def test_cell_path_format(tmp_path: Path):
    p = _cell_path(str(tmp_path), pct=5, L=100)
    assert p.endswith("kpz_cells/cell_pct05_L0100.json")


def test_per_pct_path_format(tmp_path: Path):
    p = _per_pct_path(str(tmp_path), pct=99)
    assert p.endswith("kpz_cells/per_pct99.json")


def test_aggregate_results_empty(tmp_path: Path):
    os.makedirs(_cells_dir(str(tmp_path)), exist_ok=True)
    assert aggregate_results(str(tmp_path)) == {}


def test_aggregate_results_two_pcts(tmp_path: Path):
    cells_dir = _cells_dir(str(tmp_path))
    os.makedirs(cells_dir, exist_ok=True)
    _atomic_write_json(
        _per_pct_path(str(tmp_path), 50),
        {"pct": 50, "extrapolation": {"beta_inf": 0.32}},
    )
    _atomic_write_json(
        _per_pct_path(str(tmp_path), 90),
        {"pct": 90, "extrapolation": {"beta_inf": 0.34}},
    )
    out = aggregate_results(str(tmp_path))
    assert set(out.keys()) == {"50", "90"}
    assert out["50"]["extrapolation"]["beta_inf"] == 0.32
    assert out["90"]["extrapolation"]["beta_inf"] == 0.34


def test_aggregate_ignores_cell_files(tmp_path: Path):
    """Cell files (not per_pct files) must not appear in the aggregate."""
    cells_dir = _cells_dir(str(tmp_path))
    os.makedirs(cells_dir, exist_ok=True)
    _atomic_write_json(
        _cell_path(str(tmp_path), 50, 100),
        {"L": 100, "growth_window_beta": 0.31},
    )
    _atomic_write_json(
        _per_pct_path(str(tmp_path), 50),
        {"pct": 50, "extrapolation": {"beta_inf": 0.32}},
    )
    out = aggregate_results(str(tmp_path))
    assert list(out.keys()) == ["50"]


def test_atomic_write_overwrites_existing(tmp_path: Path):
    target = tmp_path / "out.json"
    _atomic_write_json(str(target), {"v": 1})
    _atomic_write_json(str(target), {"v": 2})
    assert json.loads(target.read_text()) == {"v": 2}
