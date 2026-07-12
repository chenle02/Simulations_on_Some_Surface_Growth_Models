"""Focused tests for common-time Tracy--Widom interface diagnostics."""

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

from tetris_ballistic.scripts import analyze_tw_distributions, reduce_tw_interfaces
from tetris_ballistic.tw_analysis import (
    GOE_EXCESS_KURTOSIS,
    GOE_SKEWNESS,
    bootstrap_seed_block_moments,
    classify_cross_l_goe,
    compare_to_goe,
    reconstruct_interface,
    sample_moments,
    seed_block_indices,
    select_target_times,
    validate_interface,
)


def test_reconstruct_interface_obeys_timestamps_off_by_one_and_empty_columns():
    substrate = np.zeros((8, 4), dtype=np.int32)
    substrate[6, 0] = 1
    substrate[4, 1] = 2
    substrate[2, 1] = 3  # Future occupation must be excluded at t=2.
    substrate[7, 3] = 1

    at_two = reconstruct_interface(substrate, deposition_count=2)
    at_three = reconstruct_interface(substrate, deposition_count=3)

    # _TopEnvelop uses top occupied row minus one; an empty column uses H-1.
    np.testing.assert_array_equal(at_two, [3, 5, 1, 2])
    np.testing.assert_array_equal(at_three, [3, 7, 1, 2])


def test_target_time_is_last_index_not_exceeding_height_scale():
    values = np.arange(1.0, 31.0)
    hbar = np.vstack([values, values])

    indices, counts, targets = select_target_times(
        hbar, L=25, q_values=(0.15, 0.20)
    )

    # L^(3/2)=125: targets are 18.75 and 25.0.
    np.testing.assert_array_equal(indices, [17, 24])
    np.testing.assert_array_equal(counts, [18, 25])
    np.testing.assert_allclose(targets, [18.0, 25.0])


def test_target_time_rejects_pre_growth_target():
    hbar = np.vstack([np.arange(1.0, 8.0)] * 2)
    with pytest.raises(ValueError, match="below 10"):
        select_target_times(hbar, L=10, q_values=(0.15,))


def test_target_time_rejects_inverted_or_nonmonotone_height_clock():
    hbar = np.vstack([np.arange(30.0, 0.0, -1.0)] * 2)
    with pytest.raises(ValueError, match="monotone nondecreasing"):
        select_target_times(hbar, L=25, q_values=(0.15,))


def test_reducer_requires_exact_ordered_exp14_seeds(tmp_path):
    trace_root = tmp_path / "traces"
    cell_dir = trace_root / "pct_99"
    cell_dir.mkdir(parents=True)
    wrong_seeds = np.arange(1, 101, dtype=np.int32)
    np.savez_compressed(
        cell_dir / "L_0500.npz",
        seeds=wrong_seeds,
        final_steps=np.full(100, 20, dtype=np.int32),
        W=np.ones((100, 20), dtype=np.float32),
        hbar=np.tile(np.arange(1, 21, dtype=np.float32), (100, 1)),
        height_grid=np.int32(100),
    )
    with pytest.raises(ValueError, match="exact ordered seeds"):
        reduce_tw_interfaces.reduce_cell(
            str(tmp_path / "raw"), str(trace_root), 99, 500
        )


def test_missing_height_grid_rejects_ambiguous_ascending_hbar(tmp_path):
    path = tmp_path / "ambiguous.npz"
    np.savez_compressed(
        path,
        hbar=np.tile(np.arange(1, 21, dtype=np.float32), (2, 1)),
    )
    with np.load(path) as trace:
        with pytest.raises(ValueError, match="provenance is ambiguous"):
            reduce_tw_interfaces._physical_hbar_from_trace(trace, L=25)


def _fixture_interface(substrate, deposition_count):
    """Independent, loop-based timestamp reconstruction for reducer tests."""
    height, width = substrate.shape
    result = np.ones(width, dtype=np.int32)
    for column in range(width):
        occupied_rows = [
            row for row in range(height)
            if 0 < substrate[row, column] <= deposition_count
        ]
        if occupied_rows:
            result[column] = height - min(occupied_rows) + 1
    return result


@pytest.mark.parametrize(
    ("include_height_grid", "expected_correction"),
    [
        (True, "already_physical_height_grid_field"),
        (False, "in_memory_grid_height_minus_raw_hbar"),
    ],
)
def test_reduce_cell_end_to_end_pairs_seeds_and_validates_interfaces(
    tmp_path, include_height_grid, expected_correction
):
    pct, L, n_steps = 99, 25, 50
    height = reduce_tw_interfaces.grid_height_for_L(L)
    seeds = np.arange(0, 1000, 10, dtype=np.int32)
    raw_root = tmp_path / "raw"
    trace_root = tmp_path / "traces"
    raw_cell = raw_root / f"pct_{pct:02d}" / f"L_{L:04d}"
    trace_cell = trace_root / f"pct_{pct:02d}"
    raw_cell.mkdir(parents=True)
    trace_cell.mkdir(parents=True)

    substrates = []
    W = np.empty((seeds.size, n_steps), dtype=np.float32)
    hbar = np.empty_like(W)
    for seed_index, seed in enumerate(seeds):
        substrate = np.zeros((height, L), dtype=np.int32)
        for column in range(L):
            offset = (column + seed_index) % 3
            for physical_height in range(2, 52):
                timestamp = physical_height - 1 + offset
                if timestamp <= n_steps:
                    row = height - physical_height + 1
                    substrate[row, column] = timestamp
        substrates.append(substrate)

        expected_interfaces = np.stack([
            _fixture_interface(substrate, count)
            for count in range(1, n_steps + 1)
        ])
        hbar[seed_index] = expected_interfaces.mean(axis=1)
        W[seed_index] = expected_interfaces.std(axis=1, ddof=0)
        joblib.dump(
            SimpleNamespace(
                seed=int(seed), width=L, height=height, FinalSteps=n_steps,
                substrate=substrate, Fluctuation=W[seed_index].copy(),
            ),
            raw_cell / f"seed_{int(seed):03d}.joblib",
        )

    trace_path = trace_cell / f"L_{L:04d}.npz"
    trace_payload = {
        "seeds": seeds,
        "final_steps": np.full(seeds.size, n_steps, dtype=np.int64),
        "W": W,
        "hbar": hbar if include_height_grid else (height - hbar).astype(np.float32),
    }
    if include_height_grid:
        trace_payload["height_grid"] = np.int32(height)
    np.savez_compressed(trace_path, **trace_payload)
    trace_bytes_before = trace_path.read_bytes()

    arrays, metadata = reduce_tw_interfaces.reduce_cell(
        str(raw_root), str(trace_root), pct, L
    )

    assert trace_path.read_bytes() == trace_bytes_before

    ensemble_hbar = hbar.mean(axis=0, dtype=np.float64)
    expected_indices = []
    for q in (0.15, 0.25, 0.40):
        expected_indices.append(
            int(np.flatnonzero(ensemble_hbar <= q * L ** 1.5)[-1])
        )
    expected_indices = np.asarray(expected_indices, dtype=np.int64)
    np.testing.assert_array_equal(arrays["target_trace_indices"], expected_indices)
    np.testing.assert_array_equal(arrays["deposition_counts"], expected_indices + 1)

    expected_interfaces = np.stack([
        np.stack([
            _fixture_interface(substrate, int(count))
            for substrate in substrates
        ])
        for count in expected_indices + 1
    ])
    np.testing.assert_array_equal(arrays["interfaces"], expected_interfaces)
    np.testing.assert_array_equal(arrays["seeds"], seeds)
    assert metadata["seeds"] == seeds.tolist()
    assert metadata["raw_file_count"] == 100
    assert metadata["height_grid"] == height
    assert metadata["trace_hbar_correction"] == expected_correction
    assert metadata["validation"]["checks_passed"] == 300
    assert metadata["validation"]["max_mean_abs_error"] < 1e-3
    assert metadata["validation"]["max_std_abs_error"] < 1e-3


def test_interface_mean_and_population_std_validation():
    interface = np.array([3, 5, 1, 2], dtype=np.int32)
    result = validate_interface(
        interface,
        expected_hbar=float(interface.mean()),
        expected_fluctuation=float(interface.std(ddof=0)),
    )
    assert result["mean_abs_error"] == 0.0
    assert result["std_abs_error"] == 0.0

    with pytest.raises(ValueError, match="validation failed"):
        validate_interface(interface, expected_hbar=99.0,
                           expected_fluctuation=interface.std())


def test_physical_height_sign_has_positive_right_tail_skew():
    physical_height = np.array([1] * 20 + [2] * 5 + [8, 10], dtype=float)
    envelope_row = 20.0 - physical_height

    physical_skew, _ = sample_moments(physical_height)
    envelope_skew, _ = sample_moments(envelope_row)

    assert physical_skew > 0
    assert envelope_skew == pytest.approx(-physical_skew)


def test_known_symmetric_distribution_has_zero_skewness():
    symmetric = np.tile(np.array([-2.0, -1.0, 0.0, 1.0, 2.0]), 8)
    measured_skew, measured_kurtosis = sample_moments(symmetric)
    assert measured_skew == pytest.approx(0.0, abs=1e-15)
    assert measured_kurtosis < 0.0


def test_seed_block_draws_resample_complete_rows():
    interfaces = np.arange(4 * 5).reshape(4, 5)
    draws = seed_block_indices(n_seeds=4, n_boot=3, rng_seed=7)

    assert draws.shape == (3, 4)
    for draw in draws:
        resampled = interfaces[draw]
        for output_row, source_seed in zip(resampled, draw):
            np.testing.assert_array_equal(output_row, interfaces[source_seed])


def test_seed_block_bootstrap_is_deterministic_and_reports_covariance():
    rng = np.random.default_rng(123)
    interfaces = rng.gamma(shape=4.0, scale=1.0, size=(20, 8))

    first = bootstrap_seed_block_moments(interfaces, n_boot=2000, rng_seed=19)
    second = bootstrap_seed_block_moments(interfaces, n_boot=2000, rng_seed=19)

    assert first == second
    assert first["bootstrap_unit"] == "seed_block"
    assert np.asarray(first["bootstrap_covariance"]).shape == (2, 2)
    assert first["ci99"]["skewness"][0] <= first["ci95"]["skewness"][0]
    assert first["ci99"]["skewness"][1] >= first["ci95"]["skewness"][1]


def _moment(goe_state, skew_delta=0.0, kurt_delta=0.0):
    if goe_state == "compatible_95":
        skew_ci95 = [GOE_SKEWNESS - 0.02, GOE_SKEWNESS + 0.02]
        skew_ci99 = [GOE_SKEWNESS - 0.04, GOE_SKEWNESS + 0.04]
        kurt_ci95 = [GOE_EXCESS_KURTOSIS - 0.02, GOE_EXCESS_KURTOSIS + 0.02]
        kurt_ci99 = [GOE_EXCESS_KURTOSIS - 0.04, GOE_EXCESS_KURTOSIS + 0.04]
    else:
        skew_ci95 = [0.50, 0.60]
        skew_ci99 = [0.45, 0.65]
        kurt_ci95 = [0.40, 0.50]
        kurt_ci99 = [0.35, 0.55]
    base = {
        "skewness": GOE_SKEWNESS + skew_delta,
        "excess_kurtosis": GOE_EXCESS_KURTOSIS + kurt_delta,
        "ci95": {"skewness": skew_ci95, "excess_kurtosis": kurt_ci95},
        "ci99": {"skewness": skew_ci99, "excess_kurtosis": kurt_ci99},
    }
    return compare_to_goe(base)


def _records(state, outward=False):
    records = []
    for q in (0.25, 0.40):
        records.extend([
            {"sticky_fraction_pct": 99, "L": 400, "q": q,
             "pooled": _moment(state, 0.01, 0.01)},
            {"sticky_fraction_pct": 99, "L": 500, "q": q,
             "pooled": _moment(state, 0.02 if outward else 0.005,
                               0.02 if outward else 0.005)},
        ])
    return records


def test_cross_l_verdict_requires_compatibility_and_no_outward_drift():
    consistent = classify_cross_l_goe(_records("compatible_95"), 99)
    assert consistent["verdict"] == "KPZ-GOE consistent"
    assert consistent["widths_used"] == [400, 500]

    drifting = classify_cross_l_goe(_records("compatible_95", outward=True), 99)
    assert drifting["verdict"] == "inconclusive/crossover-dominated"


def test_cross_l_verdict_requires_99pct_exclusion_at_both_late_q():
    incompatible = classify_cross_l_goe(_records("incompatible_99"), 99)
    assert incompatible["verdict"] == "inconsistent-on-accessible-scales"

    records = _records("incompatible_99")
    records = [record for record in records if not (record["q"] == 0.40 and record["L"] == 500)]
    inconclusive = classify_cross_l_goe(records, 99)
    assert inconclusive["verdict"] == "inconclusive/crossover-dominated"


def _write_compact_fixture(path, **overrides):
    payload = {
        "interfaces": np.ones((3, 100, 4), dtype=np.int32),
        "seeds": np.arange(0, 1000, 10, dtype=np.int32),
        "q_values": np.asarray([0.15, 0.25, 0.40], dtype=np.float64),
        "target_trace_indices": np.asarray([10, 20, 30], dtype=np.int64),
        "deposition_counts": np.asarray([11, 21, 31], dtype=np.int64),
        "target_mean_hbar": np.asarray([12.0, 20.0, 30.0]),
        "sticky_fraction_pct": np.int32(99),
        "L": np.int32(4),
        "percentage_semantics": np.asarray("sticky_fraction_pct"),
        "density_convention": np.asarray(
            "Piece-19=[100-pct,pct]=[nonsticky,sticky]"
        ),
        "physical_height_sign": np.asarray("positive-growth-direction"),
    }
    payload.update(overrides)
    np.savez_compressed(path, **payload)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"q_values": np.asarray([0.15, 0.30, 0.40])}, "exact q values"),
        ({"seeds": np.arange(100, dtype=np.int32)}, "exact ordered seeds"),
        ({"deposition_counts": np.asarray([11, 22, 31])}, "must equal"),
        ({"target_mean_hbar": np.asarray([12.0, np.nan, 30.0])}, "must be finite"),
        ({"interfaces": np.full((3, 100, 4), np.nan)}, "must be finite"),
        ({"physical_height_sign": np.asarray("row-index")}, "height sign"),
        ({"target_trace_indices": np.asarray([10, 20])}, "inconsistent shapes"),
    ],
)
def test_analyzer_rejects_invalid_compact_protocol(tmp_path, overrides, message):
    path = tmp_path / "bad.npz"
    _write_compact_fixture(path, **overrides)
    with pytest.raises(ValueError, match=message):
        analyze_tw_distributions.analyze_compact_cell(path)


def test_analyzer_requires_physical_height_sign_field(tmp_path):
    path = tmp_path / "missing-sign.npz"
    payload_path = tmp_path / "complete.npz"
    _write_compact_fixture(payload_path)
    with np.load(payload_path) as data:
        payload = {name: np.asarray(data[name]) for name in data.files
                   if name != "physical_height_sign"}
    np.savez_compressed(path, **payload)
    with pytest.raises(ValueError, match="lacks fields.*physical_height_sign"):
        analyze_tw_distributions.analyze_compact_cell(path)


@pytest.mark.parametrize(
    ("task_id", "expected"),
    list(enumerate([
        "90 300", "90 400", "90 500",
        "95 300", "95 400", "95 500",
        "98 300", "98 400", "98 500",
        "99 300", "99 400", "99 500",
        "5 300", "50 300",
    ])),
)
def test_slurm_priority_array_mapping_is_explicit_and_probeable(task_id, expected):
    repo = Path(__file__).resolve().parents[1]
    script = repo / "scripts" / "easley" / "reduce_tw_interfaces.sbatch"
    env = dict(os.environ, SLURM_ARRAY_TASK_ID=str(task_id), TW_MAPPING_ONLY="1")
    completed = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, check=True, env=env
    )
    assert completed.stdout.strip() == expected


@pytest.mark.parametrize("task_id", [-1, 14])
def test_slurm_priority_array_mapping_rejects_invalid_bounds(task_id):
    repo = Path(__file__).resolve().parents[1]
    script = repo / "scripts" / "easley" / "reduce_tw_interfaces.sbatch"
    env = dict(os.environ, SLURM_ARRAY_TASK_ID=str(task_id), TW_MAPPING_ONLY="1")
    completed = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, env=env
    )
    assert completed.returncode == 2
    assert f"invalid array index: {task_id}" in completed.stderr
