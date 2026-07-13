"""Focused tests for memory-safe paired KPZ trace subsampling."""

import numpy as np
import pytest

from tetris_ballistic.kpz_analysis import (
    growth_window_slope,
    log_subsample_paired_traces,
)
from tetris_ballistic.scripts import run_kpz_analysis as runner


def test_short_paired_traces_remain_unchanged():
    W_list = [np.arange(8, dtype=np.float32), np.arange(8, dtype=np.float32) + 10]
    hbar_list = [np.arange(8, dtype=np.float32) + 1, np.arange(8, dtype=np.float32) + 2]

    W, hbar, original_len, indices = log_subsample_paired_traces(
        W_list, hbar_list, max_points=10
    )

    assert original_len == 8
    np.testing.assert_array_equal(indices, np.arange(8))
    np.testing.assert_array_equal(W, np.stack(W_list))
    np.testing.assert_array_equal(hbar, np.stack(hbar_list))


def test_long_traces_are_bounded_paired_and_preserve_float32():
    n = 100_000
    base = np.arange(n, dtype=np.float32)
    W_list = [base, base + 3]
    hbar_list = [2 * base + 1, 2 * base + 7]

    W, hbar, original_len, indices = log_subsample_paired_traces(
        W_list, hbar_list, max_points=5000
    )

    assert original_len == n
    assert indices.size == 5000
    assert indices[0] == 0
    assert indices[-1] == n - 1
    assert np.all(np.diff(indices) > 0)
    assert W.dtype == np.float32
    assert hbar.dtype == np.float32
    np.testing.assert_array_equal(W[1], W_list[1][indices])
    np.testing.assert_array_equal(hbar[1], hbar_list[1][indices])


def test_common_length_spans_both_observables_and_all_seeds():
    W_list = [np.arange(12), np.arange(10)]
    hbar_list = [np.arange(11), np.arange(9)]

    W, hbar, original_len, indices = log_subsample_paired_traces(
        W_list, hbar_list, max_points=20
    )

    assert original_len == 9
    assert W.shape == hbar.shape == (2, 9)
    assert indices[-1] == 8


def test_paired_traces_require_at_least_two_common_samples():
    W_list = [np.arange(3), np.arange(2)]
    hbar_list = [np.arange(4), np.arange(1)]

    with pytest.raises(ValueError, match="at least two paired samples"):
        log_subsample_paired_traces(W_list, hbar_list)


def test_log_subsampling_preserves_synthetic_growth_slope():
    h = np.linspace(1.0, 1000.0, 20_000, dtype=np.float32)
    beta = 0.37
    factors = np.array([0.98, 1.0, 1.02, 1.04], dtype=np.float32)
    W_list = [(factor * h ** beta).astype(np.float32) for factor in factors]
    hbar_list = [h.copy() for _ in factors]
    W_full = np.stack(W_list)
    hbar_full = np.stack(hbar_list)

    full_beta, _, _ = growth_window_slope(
        W_full, hbar_full, L=100, n_boot=10
    )
    W_sampled, hbar_sampled, _, _ = log_subsample_paired_traces(
        W_list, hbar_list, max_points=5000
    )
    sampled_beta, _, _ = growth_window_slope(
        W_sampled, hbar_sampled, L=100, n_boot=10
    )

    assert abs(full_beta - beta) < 1e-5
    assert abs(sampled_beta - full_beta) < 1e-5


def test_resume_rejects_legacy_cell_without_sampling_provenance():
    legacy_cell = {"percentage": 99, "L": 100, "growth_window_beta": 0.4}

    assert not runner._sampling_policy_is_current(legacy_cell)


def test_resume_reuses_only_exact_current_sampling_policy():
    compatible_cell = {
        "sampling_policy": dict(runner.SAMPLING_POLICY),
        "saturated": True,
        "hbar_max": 1234.5,
    }
    incompatible_cell = {
        **compatible_cell,
        "sampling_policy": {
            "method": "paired_log_spaced_indices",
            "max_points": 4000,
            "includes_endpoints": True,
        },
    }

    assert runner._sampling_policy_is_current(compatible_cell)
    assert not runner._sampling_policy_is_current(incompatible_cell)


@pytest.mark.parametrize(
    ("saturated", "hbar_max"),
    [
        (None, 1234.5),
        (1, 1234.5),
        (True, None),
        (True, True),
        (False, float("nan")),
        (False, float("inf")),
    ],
)
def test_resume_rejects_invalid_saturation_provenance(saturated, hbar_max):
    cell = {
        "sampling_policy": dict(runner.SAMPLING_POLICY),
        "saturated": saturated,
        "hbar_max": hbar_max,
    }

    assert not runner._sampling_policy_is_current(cell)


def test_run_single_cell_records_sampling_provenance(monkeypatch):
    n = 6000
    h = np.linspace(1.0, 1000.0, n, dtype=np.float32)
    W_list = [(h ** 0.33).astype(np.float32) for _ in range(3)]
    hbar_list = [h.copy() for _ in range(3)]
    observed_shapes = []

    monkeypatch.setattr(
        runner, "load_ensemble", lambda *_args, **_kwargs: (W_list, hbar_list)
    )

    def fake_growth(W, hbar, *_args, **_kwargs):
        observed_shapes.append((W.shape, hbar.shape))
        return 0.33, 0.32, 0.34

    def fake_local(W, hbar, **_kwargs):
        observed_shapes.append((W.shape, hbar.shape))
        values = np.array([1.0, 2.0])
        return values, values, values, values

    def fake_meakin(W, hbar):
        observed_shapes.append((W.shape, hbar.shape))
        return (0.33, 0.01), (0.34, 0.01)

    monkeypatch.setattr(runner, "growth_window_slope", fake_growth)
    monkeypatch.setattr(runner, "local_slope_bootstrap", fake_local)
    monkeypatch.setattr(runner, "detect_plateau", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(runner, "meakin_range_of_fit", fake_meakin)

    cell, *_ = runner.run_single_cell(
        "unused",
        pct=99,
        L=100,
        n_boot=2,
        min_seeds=2,
        percentage_convention="sticky-fraction",
        model_profile="piece-19-one-cell-v1",
    )

    analysis_points = cell["analysis_point_count"]
    assert analysis_points == 5000
    assert observed_shapes == [
        ((3, analysis_points), (3, analysis_points))
    ] * 3
    assert cell["min_trace_len"] == n
    assert cell["sampling_policy"] == {
        "method": "paired_log_spaced_indices",
        "max_points": 5000,
        "includes_endpoints": True,
    }
    assert cell["percentage_convention"] == "sticky-fraction"
    assert cell["model_profile"] == "piece-19-one-cell-v1"


def test_run_single_cell_enforces_declared_minimum_seed_count(monkeypatch):
    trace = np.arange(20, dtype=np.float32) + 1
    monkeypatch.setattr(
        runner,
        "load_ensemble",
        lambda *_args, **_kwargs: ([trace, trace], [trace, trace]),
    )

    with pytest.raises(ValueError, match="at least 3"):
        runner.run_single_cell(
            "unused",
            pct=50,
            L=10,
            min_seeds=3,
            percentage_convention="sticky-fraction",
            model_profile="piece-19-one-cell-v1",
        )
