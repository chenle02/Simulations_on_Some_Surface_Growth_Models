"""I/O contracts for the identity-bound KPZ-analysis runner.

Verifies:
- ``_atomic_write_json`` writes atomically (no leftover .tmp on success).
- ``aggregate_results`` reads an exact grid of managed cell artifacts.

These tests are pure unit tests of the runner's I/O contract — they
do NOT load any joblib simulation data, so they run in milliseconds.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tetris_ballistic.analysis_artifacts import (
    AnalysisArtifactValidationError,
    build_analysis_identity,
    build_identity,
    write_json_artifact,
)
from tetris_ballistic.scripts.run_kpz_analysis import (
    CELL_INPUT_PROFILE,
    _atomic_write_json,
    _cell_path,
    _cells_dir,
    _per_pct_path,
    aggregate_results,
)


def _cell(pct: int, L: int) -> dict:
    return {
        "L": L,
        "analysis_point_count": 2,
        "beta_err_for_extrap": 0.01,
        "beta_for_extrap": 0.33,
        "eval_log_t": [1.0, 2.0],
        "growth_window_beta": 0.33,
        "growth_window_ci": [0.32, 0.34],
        "hbar_max": 1000.0,
        "meakin_window1": {"se": 0.01, "slope": 0.32},
        "meakin_window2": {"se": 0.01, "slope": 0.34},
        "min_trace_len": 2,
        "model_profile": "piece-19-one-cell-v1",
        "n_seeds": 2,
        "percentage": pct,
        "percentage_convention": "sticky-fraction",
        "plateau_detected": False,
        "plateau_mask": [False, False],
        "sampling_policy": {
            "includes_endpoints": True,
            "max_points": 5000,
            "method": "paired_log_spaced_indices",
        },
        "saturated": True,
        "slope_hi": [0.34, 0.34],
        "slope_lo": [0.32, 0.32],
        "slope_med": [0.33, 0.33],
    }


def _identity(pct: int, L: int) -> dict:
    content = build_identity("test-content-v1", {"cell": [pct, L]})
    return build_analysis_identity(
        artifact_kind="test-kpz-cell",
        context={
            "L": L,
            "percentage": pct,
            "percentage_convention": "sticky-fraction",
            "model_profile": "piece-19-one-cell-v1",
        },
        inputs=build_identity(
            CELL_INPUT_PROFILE,
            {
                "content": content,
                "layout": "reduced",
                "seed_inventory": [0, 10],
            },
        ),
        rng={},
        settings={"min_seeds": 2, "n_eval": 2},
        software=build_identity("test-software-v1", {}),
    )


def _write_cell(root: Path, pct: int, L: int) -> dict:
    identity = _identity(pct, L)
    write_json_artifact(_cell_path(str(root), pct, L), _cell(pct, L), identity)
    return identity


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
    identity = _identity(50, 100)

    with pytest.raises(AnalysisArtifactValidationError):
        aggregate_results(str(tmp_path), [50], [100], {(50, 100): identity})


def test_aggregate_rejects_identity_without_managed_seed_inventory(
    tmp_path: Path,
) -> None:
    identity = build_analysis_identity(
        artifact_kind="test-kpz-cell",
        context={
            "L": 100,
            "percentage": 50,
            "percentage_convention": "sticky-fraction",
            "model_profile": "piece-19-one-cell-v1",
        },
        inputs=build_identity("malformed-input-v1", {"cell": [50, 100]}),
        rng={},
        settings={"min_seeds": 2, "n_eval": 2},
        software=build_identity("test-software-v1", {}),
    )
    write_json_artifact(_cell_path(str(tmp_path), 50, 100), _cell(50, 100), identity)

    with pytest.raises(AnalysisArtifactValidationError, match="seed inventory"):
        aggregate_results(str(tmp_path), [50], [100], {(50, 100): identity})


def test_aggregate_results_two_pcts(tmp_path: Path):
    identities = {
        (pct, 100): _write_cell(tmp_path, pct, 100) for pct in (50, 90)
    }
    out = aggregate_results(str(tmp_path), [50, 90], [100], identities)
    assert set(out.keys()) == {"50", "90"}
    assert out["50"]["cells"]["100"]["growth_window_beta"] == 0.33
    assert out["90"]["cells"]["100"]["growth_window_beta"] == 0.33


def test_aggregate_ignores_stale_per_percentage_files(tmp_path: Path):
    """Only requested managed cells, never stale summaries, feed aggregation."""
    identity = _write_cell(tmp_path, 50, 100)
    _atomic_write_json(
        _per_pct_path(str(tmp_path), 50),
        {"pct": 999, "cells": {"999": {"growth_window_beta": -10}}},
    )
    out = aggregate_results(str(tmp_path), [50], [100], {(50, 100): identity})
    assert list(out.keys()) == ["50"]
    assert out["50"]["pct"] == 50
    assert out["50"]["cells"]["100"]["growth_window_beta"] == 0.33


def test_atomic_write_overwrites_existing(tmp_path: Path):
    target = tmp_path / "out.json"
    _atomic_write_json(str(target), {"v": 1})
    _atomic_write_json(str(target), {"v": 2})
    assert json.loads(target.read_text()) == {"v": 2}
