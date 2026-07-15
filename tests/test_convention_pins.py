"""Absolute convention-pin invariant tests for physical height observables.

These tests guard against the historical bug where ``AvergeHeight`` reported
mean row-index-from-top (descending) instead of physical mean height
(ascending). Shared-bug-blind equivalence and golden tests cannot catch that
kind of inversion; these assertions pin the semantic convention directly.
"""

from __future__ import annotations

import numpy as np
import pytest

from tetris_ballistic import Tetris_Ballistic


def _piece_19_density() -> dict[str, list[int]]:
    density = {f"Piece-{i}": [0, 0] for i in range(20)}
    density["Piece-19"] = [50, 50]
    return density


def _run_piece_19(
    monkeypatch: pytest.MonkeyPatch,
    *,
    use_kernel: str,
    width: int,
    height: int,
    steps: int,
    seed: int,
) -> tuple[Tetris_Ballistic, int]:
    monkeypatch.setenv("TETRIS_USE_KERNEL", use_kernel)
    simulation = Tetris_Ballistic(
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        density=_piece_19_density(),
    )
    simulation.Simulate()
    final_steps = simulation.FinalSteps
    assert final_steps == steps, (
        f"expected full deterministic run of {steps} steps, got {final_steps}"
    )
    return simulation, final_steps


@pytest.mark.parametrize("use_kernel", ["0", "1"])
def test_physical_mean_height_starts_near_zero_and_increases(
    monkeypatch: pytest.MonkeyPatch, use_kernel: str
) -> None:
    simulation, final_steps = _run_piece_19(
        monkeypatch,
        use_kernel=use_kernel,
        width=32,
        height=160,
        steps=256,
        seed=7,
    )

    mean_height = np.asarray(simulation.AvergeHeight[:final_steps], dtype=np.float64)
    assert mean_height[0] < 2.0, (
        f"path={use_kernel}: physical mean height should start near 0 / O(1) on an empty "
        f"substrate, got {mean_height[0]:.6f}"
    )
    assert mean_height[-1] > mean_height[0], (
        f"path={use_kernel}: physical mean height must increase with deposition "
        f"({mean_height[0]:.6f} -> {mean_height[-1]:.6f})"
    )
    diffs = np.diff(mean_height)
    assert np.all(diffs >= -1e-12), (
        f"path={use_kernel}: physical mean height must be weakly increasing"
    )


@pytest.mark.parametrize("use_kernel", ["0", "1"])
def test_public_averageheight_matches_grid_height_minus_mean_row_index(
    monkeypatch: pytest.MonkeyPatch, use_kernel: str
) -> None:
    simulation, final_steps = _run_piece_19(
        monkeypatch,
        use_kernel=use_kernel,
        width=24,
        height=120,
        steps=180,
        seed=11,
    )

    final_public_height = float(simulation.AvergeHeight[final_steps - 1])
    row_index_mean = float(np.mean(simulation.heights, dtype=np.float64))
    converted_physical_height = float(simulation.height - row_index_mean)

    assert final_public_height == pytest.approx(converted_physical_height, abs=1e-12)


def test_interface_width_is_flip_invariant_for_same_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    simulation, final_steps = _run_piece_19(
        monkeypatch,
        use_kernel="1",
        width=20,
        height=100,
        steps=180,
        seed=5,
    )

    row_index_heights = np.asarray(simulation.heights, dtype=np.float64)
    flipped_heights = (simulation.height - 1) - row_index_heights

    raw_width = float(np.std(row_index_heights))
    flipped_width = float(np.std(flipped_heights))
    public_width = float(simulation.Fluctuation[final_steps - 1])

    assert raw_width == pytest.approx(flipped_width, abs=1e-12)
    assert public_width == pytest.approx(raw_width, abs=1e-12)


def test_saturation_gate_quantity_grows_toward_l_pow_3_over_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    width = 8
    threshold = width**1.5
    simulation, final_steps = _run_piece_19(
        monkeypatch,
        use_kernel="1",
        width=width,
        height=120,
        steps=260,
        seed=13,
    )

    mean_height = np.asarray(simulation.AvergeHeight[:final_steps], dtype=np.float64)
    crossings = np.flatnonzero(mean_height >= threshold)

    assert mean_height[0] < threshold, (
        f"saturation quantity should start below L^1.5={threshold:.6f}, "
        f"got {mean_height[0]:.6f}"
    )
    assert crossings.size > 0, (
        f"test setup should reach the saturation threshold L^1.5={threshold:.6f}; "
        f"final mean height was {mean_height[-1]:.6f}"
    )
    assert mean_height[-1] > mean_height[0], (
        f"quantity compared against L^1.5 must grow with time, not shrink "
        f"({mean_height[0]:.6f} -> {mean_height[-1]:.6f})"
    )
