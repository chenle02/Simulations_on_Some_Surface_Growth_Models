"""Phase-4b tests for the numba @njit fast path.

Verifies:
- ``is_1x1_only`` correctly identifies piece_19-only configurations.
- Kernel path produces results bit-identical (atol=1e-12) to the legacy
  path on a tiny shared input (regression guard).
- ``TETRIS_USE_KERNEL=0`` env-var forces the legacy path.
- The kernel updates ``SampleDist`` like the legacy path does.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from tests.build_golden_reference import build_density_for_piece_19_combined
from tetris_ballistic._kernel_1x1 import is_1x1_only


def test_is_1x1_only_true():
    cfg = {f"Piece-{i}": [0, 0] for i in range(20)}
    cfg["Piece-19"] = [50, 50]
    assert is_1x1_only(cfg) is True


def test_is_1x1_only_false_other_piece():
    cfg = {f"Piece-{i}": [0, 0] for i in range(20)}
    cfg["Piece-0"] = [1, 0]
    cfg["Piece-19"] = [50, 50]
    assert is_1x1_only(cfg) is False


def test_is_1x1_only_false_empty():
    cfg = {f"Piece-{i}": [0, 0] for i in range(20)}
    assert is_1x1_only(cfg) is False


@pytest.mark.slow
def test_kernel_matches_legacy_path(monkeypatch):
    """Run the SAME (pct, L, seed) once with TETRIS_USE_KERNEL=1 and once
    with =0; both must agree at the FP-roundoff tolerance.
    """
    from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

    density = build_density_for_piece_19_combined(50)
    width, height, steps = 30, 60, 500
    seed = 7

    monkeypatch.setenv("TETRIS_USE_KERNEL", "1")
    tb_k = Tetris_Ballistic(width=width, height=height, steps=steps, seed=seed, density=density)
    tb_k.Simulate()

    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    tb_l = Tetris_Ballistic(width=width, height=height, steps=steps, seed=seed, density=density)
    tb_l.Simulate()

    n_k = tb_k.FinalSteps
    n_l = tb_l.FinalSteps
    assert n_k == n_l, f"FinalSteps disagree: kernel={n_k}, legacy={n_l}"

    np.testing.assert_allclose(
        tb_k.Fluctuation[:n_k], tb_l.Fluctuation[:n_l],
        atol=1e-12, rtol=1e-12,
        err_msg="Fluctuation diverged between kernel and legacy paths",
    )
    np.testing.assert_allclose(
        tb_k.AvergeHeight[:n_k], tb_l.AvergeHeight[:n_l],
        atol=0.0, rtol=0.0,
        err_msg="AvergeHeight diverged between kernel and legacy paths",
    )


@pytest.mark.slow
def test_kernel_path_updates_sample_dist():
    """The kernel orchestrator must populate SampleDist (used by
    PrintStatus / Jensen-Shannon-divergence diagnostic). Regression
    guard against forgetting to update it inside the JIT path."""
    from tetris_ballistic.tetris_ballistic import Tetris_Ballistic
    os.environ["TETRIS_USE_KERNEL"] = "1"
    density = build_density_for_piece_19_combined(50)
    tb = Tetris_Ballistic(width=30, height=60, steps=500, seed=0, density=density)
    tb.Simulate()
    # Piece-19 has two slots [50, 50]; both should have nonzero counts.
    assert tb.SampleDist[19, 0] > 0
    assert tb.SampleDist[19, 1] > 0
