"""Phase-3 tests for the Slurm-array entry point.

Covers:
- grid spec parsing + validation
- decode_task_id iteration order (pct outermost, seed innermost)
- build_density correctness
- cell output path layout (hierarchical + flat)
- end-to-end single-cell run (tiny config so it finishes in <1 s)
- resume semantics (re-running an existing cell is a no-op)
"""

from __future__ import annotations

import joblib
import numpy as np
import pytest
import yaml

from tetris_ballistic.scripts.run_one_cell import (
    build_density,
    cell_output_paths,
    decode_task_id,
    grid_size,
    load_grid_spec,
    run_cell,
)


@pytest.fixture
def tiny_spec_path(tmp_path):
    """A tiny 2x2x2 = 8-cell grid that runs in seconds."""
    spec = {
        "piece_config": "piece_19_combined_percentage",
        "pcts": [50, 90],
        "widths": [20, 30],
        "seeds": [0, 1],
        "ratio": 2,
    }
    p = tmp_path / "grid.yaml"
    p.write_text(yaml.safe_dump(spec))
    return p


def test_load_grid_spec_missing_key_raises(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump({"pcts": [5], "widths": [50]}))  # missing seeds + piece_config
    with pytest.raises(ValueError, match="missing=.*piece_config.*seeds"):
        load_grid_spec(str(p))


def test_load_grid_spec_defaults_ratio_to_10(tmp_path):
    p = tmp_path / "good.yaml"
    p.write_text(yaml.safe_dump({
        "piece_config": "piece_19_combined_percentage",
        "pcts": [5], "widths": [50], "seeds": [0],
    }))
    spec = load_grid_spec(str(p))
    assert spec["ratio"] == 10


def test_grid_size(tiny_spec_path):
    spec = load_grid_spec(str(tiny_spec_path))
    assert grid_size(spec) == 8


def test_decode_task_id_iteration_order(tiny_spec_path):
    """Iteration order: pct outermost, L middle, seed innermost.

    For pcts=[50,90], widths=[20,30], seeds=[0,1], the order is:
      0: (50, 20, 0)   4: (90, 20, 0)
      1: (50, 20, 1)   5: (90, 20, 1)
      2: (50, 30, 0)   6: (90, 30, 0)
      3: (50, 30, 1)   7: (90, 30, 1)
    """
    spec = load_grid_spec(str(tiny_spec_path))
    assert decode_task_id(0, spec) == (50, 20, 0)
    assert decode_task_id(1, spec) == (50, 20, 1)
    assert decode_task_id(2, spec) == (50, 30, 0)
    assert decode_task_id(3, spec) == (50, 30, 1)
    assert decode_task_id(4, spec) == (90, 20, 0)
    assert decode_task_id(7, spec) == (90, 30, 1)


def test_decode_task_id_out_of_range(tiny_spec_path):
    spec = load_grid_spec(str(tiny_spec_path))
    with pytest.raises(IndexError):
        decode_task_id(8, spec)
    with pytest.raises(IndexError):
        decode_task_id(-1, spec)


def test_build_density_pct_50(tiny_spec_path):
    spec = load_grid_spec(str(tiny_spec_path))
    d = build_density(spec, 50)
    assert d["Piece-19"] == [50, 50]
    for i in range(19):
        assert d[f"Piece-{i}"] == [0, 0]


def test_build_density_pct_90(tiny_spec_path):
    spec = load_grid_spec(str(tiny_spec_path))
    d = build_density(spec, 90)
    assert d["Piece-19"] == [10, 90]


def test_build_density_unknown_config_raises(tmp_path):
    spec = {"piece_config": "tetromino_T_only"}
    with pytest.raises(NotImplementedError, match="not yet supported"):
        build_density(spec, 50)


def test_cell_output_paths_hierarchical(tmp_path):
    jp, yp = cell_output_paths(str(tmp_path), pct=5, L=100, seed=42)
    assert str(jp).endswith("pct_05/L_0100/seed_042.joblib")
    assert str(yp).endswith("pct_05/L_0100/seed_042.yaml")


def test_cell_output_paths_flat(tmp_path):
    jp, yp = cell_output_paths(str(tmp_path), pct=5, L=100, seed=42,
                                flat=True, basename="config_pct05")
    assert str(jp).endswith("config_pct05_w=100_seed=42.joblib")


@pytest.mark.slow
def test_run_cell_e2e(tiny_spec_path, tmp_path):
    """Run an actual tiny cell end-to-end. Marked slow because it
    instantiates Tetris_Ballistic and runs a real simulation (~0.5s)."""
    spec = load_grid_spec(str(tiny_spec_path))
    out_dir = tmp_path / "results"
    jp = run_cell(spec, pct=50, L=20, seed=0, out_dir=str(out_dir))
    assert jp.exists()
    assert jp.with_suffix(".manifest.json").exists()

    # Re-run is idempotent (resume contract)
    mtime_first = jp.stat().st_mtime_ns
    jp2 = run_cell(spec, pct=50, L=20, seed=0, out_dir=str(out_dir))
    assert jp == jp2
    assert jp.stat().st_mtime_ns == mtime_first

    # Load and sanity-check the joblib
    tb = joblib.load(str(jp))
    assert tb.width == 20
    assert tb.FinalSteps > 0
    # Simulate() may trim Fluctuation to FinalSteps on early game-over (top reached).
    # Otherwise the full requested-steps length is preserved.
    n = tb.FinalSteps
    requested = spec["ratio"] * 20 * 20
    assert tb.Fluctuation.shape in [(n,), (requested,)]
    assert np.all(np.isfinite(tb.Fluctuation[:n]))


@pytest.mark.slow
def test_run_cell_consistent_with_direct_construction(tiny_spec_path, tmp_path):
    """Verify run_one_cell produces identical output to constructing
    Tetris_Ballistic directly with the same parameters."""
    from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

    spec = load_grid_spec(str(tiny_spec_path))
    out_dir = tmp_path / "results"

    jp = run_cell(spec, pct=50, L=20, seed=0, out_dir=str(out_dir))
    tb_via_runner = joblib.load(str(jp))

    density = build_density(spec, 50)
    tb_direct = Tetris_Ballistic(
        width=20, height=40, steps=2 * 20 * 20, seed=0, density=density
    )
    tb_direct.Simulate()

    n = tb_via_runner.FinalSteps
    assert tb_direct.FinalSteps == n
    np.testing.assert_array_equal(
        tb_via_runner.Fluctuation[:n], tb_direct.Fluctuation[:n]
    )
    np.testing.assert_array_equal(
        tb_via_runner.AvergeHeight[:n], tb_direct.AvergeHeight[:n]
    )
