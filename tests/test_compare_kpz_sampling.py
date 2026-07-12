"""Tests for the exp14 KPZ estimator-sensitivity diagnostic."""

import json

import numpy as np
import pytest

from tetris_ballistic.scripts import compare_kpz_sampling as sensitivity


def _power_law_traces(beta=0.37, n=20_000, n_seeds=4):
    # Geometric hbar spacing makes the physical clock intentionally
    # non-proportional to the sample index; an index-axis fit would fail.
    hbar = np.geomspace(1.0, 1000.0, n).astype(np.float32)
    W = hbar ** beta
    factors = np.linspace(0.98, 1.02, n_seeds, dtype=np.float32)
    return (
        [(factor * W).astype(np.float32) for factor in factors],
        [hbar.copy() for _ in factors],
    )


def test_exact_power_law_agrees_under_both_weightings(monkeypatch):
    W_list, hbar_list = _power_law_traces()
    monkeypatch.setattr(
        sensitivity, "load_ensemble", lambda *_args: (W_list, hbar_list)
    )

    cell = sensitivity.analyze_cell("unused", 99, 100, max_points=5000)

    assert abs(cell["full_point_beta"] - 0.37) < 1e-6
    assert abs(cell["log_sample_beta"] - 0.37) < 1e-6
    assert abs(cell["beta_delta_log_minus_full"]) < 1e-6


def test_curved_trace_exposes_point_weighting_sensitivity(monkeypatch):
    hbar = np.linspace(1.0, 1000.0, 40_000, dtype=np.float32)
    log_h = np.log(hbar)
    W = np.exp(0.52 * log_h - 0.035 * log_h ** 2).astype(np.float32)
    W_list = [W * factor for factor in (0.99, 1.0, 1.01)]
    hbar_list = [hbar.copy() for _ in W_list]
    monkeypatch.setattr(
        sensitivity, "load_ensemble", lambda *_args: (W_list, hbar_list)
    )

    cell = sensitivity.analyze_cell("unused", 5, 100, max_points=5000)

    assert abs(cell["beta_delta_log_minus_full"]) > 0.005
    assert cell["full_growth_window_point_count"] > cell[
        "log_sample_growth_window_point_count"
    ]


def test_full_mean_is_streaming_and_preserves_float32_inputs(monkeypatch):
    n = 100_000
    W_list = [np.arange(n, dtype=np.float32) + i for i in range(3)]
    hbar_list = [np.arange(n, dtype=np.float32) + i + 1 for i in range(3)]
    original_W_dtypes = [trace.dtype for trace in W_list]
    original_hbar_dtypes = [trace.dtype for trace in hbar_list]

    monkeypatch.setattr(
        sensitivity.np,
        "stack",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("full-resolution path must not stack traces")
        ),
    )
    mean_W, mean_hbar, common_len = sensitivity.streaming_trace_means(
        W_list, hbar_list
    )

    assert mean_W.shape == mean_hbar.shape == (n,)
    assert mean_W.dtype == mean_hbar.dtype == np.float64
    assert common_len == n
    assert [trace.dtype for trace in W_list] == original_W_dtypes
    assert [trace.dtype for trace in hbar_list] == original_hbar_dtypes
    np.testing.assert_allclose(mean_W[:3], [1.0, 2.0, 3.0])


def test_missing_cell_is_recorded_without_aborting_grid(monkeypatch):
    def fake_analyze(_exp_dir, pct, L, _max_points):
        return {"sticky_fraction_pct": pct, "L": L}

    monkeypatch.setattr(
        sensitivity,
        "_cell_data_available",
        lambda _exp_dir, _pct, L: L == 50,
    )
    monkeypatch.setattr(sensitivity, "analyze_cell", fake_analyze)
    result = sensitivity.analyze_grid("unused", [5], [50, 80], 5000)

    assert result["cells"] == [{"sticky_fraction_pct": 5, "L": 50}]
    assert result["missing_cells"] == [
        {
            "sticky_fraction_pct": 5,
            "L": 80,
            "reason": "no reduced NPZ or raw joblib cell data",
        }
    ]


def test_invalid_max_points_fails_before_cell_scan(monkeypatch):
    monkeypatch.setattr(
        sensitivity,
        "_cell_data_available",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("availability scan must not run")
        ),
    )

    with pytest.raises(ValueError, match="max_points must be at least 2"):
        sensitivity.analyze_grid("unused", [5], [50], max_points=1)


def test_malformed_traces_fail_instead_of_becoming_missing(monkeypatch):
    monkeypatch.setattr(sensitivity, "_cell_data_available", lambda *_args: True)
    monkeypatch.setattr(sensitivity, "load_ensemble", lambda *_args: ([], []))

    with pytest.raises(ValueError, match="must be non-empty"):
        sensitivity.analyze_grid("unused", [5], [50], max_points=5000)


def test_output_records_exp14_sticky_semantics_and_writes_atomically(
    monkeypatch, tmp_path
):
    W_list, hbar_list = _power_law_traces(n=100)
    monkeypatch.setattr(
        sensitivity, "load_ensemble", lambda *_args: (W_list, hbar_list)
    )
    monkeypatch.setattr(sensitivity, "_cell_data_available", lambda *_args: True)
    output = tmp_path / "nested" / "sensitivity.json"

    result = sensitivity.analyze_grid("unused", [95], [50], 50)
    sensitivity.atomic_write_json(output, result)
    loaded = json.loads(output.read_text())

    assert loaded["percentage_semantics"] == "sticky_fraction_pct"
    assert loaded["density_convention"] == (
        "Piece-19=[100-pct,pct]=[nonsticky,sticky]"
    )
    assert loaded["cells"][0]["sticky_fraction_pct"] == 95
    assert loaded["nonfinite_numeric_convention"] == "JSON null"
    assert not list(output.parent.glob(".sampling-sensitivity-*.json"))


def test_atomic_output_normalizes_nonfinite_numbers_to_null(tmp_path):
    output = tmp_path / "sensitivity.json"

    sensitivity.atomic_write_json(
        output,
        {
            "nan": float("nan"),
            "positive_infinity": np.float64("inf"),
            "nested": [np.float32("-inf"), 0.25],
        },
    )

    raw = output.read_text()
    assert "NaN" not in raw
    assert "Infinity" not in raw
    assert json.loads(raw) == {
        "nan": None,
        "nested": [None, 0.25],
        "positive_infinity": None,
    }


def test_serialization_failure_preserves_existing_output_and_cleans_temp(tmp_path):
    output = tmp_path / "sensitivity.json"
    original = '{"status": "previous"}\n'
    output.write_text(original)

    with pytest.raises(TypeError):
        sensitivity.atomic_write_json(output, {"bad": object()})

    assert output.read_text() == original
    assert not list(tmp_path.glob(".sampling-sensitivity-*.json"))
