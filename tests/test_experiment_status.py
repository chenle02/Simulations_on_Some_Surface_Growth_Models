"""Declared-grid completion gates for Easley reduction handoff."""

from __future__ import annotations

import hashlib
import os
import sys

import joblib
import numpy as np
import pytest
import yaml

from tetris_ballistic.scripts import reduce_traces
from tetris_ballistic.scripts import run_one_cell as run_one_cell_module
from tetris_ballistic.scripts.experiment_status import (
    EXPERIMENT_STATUS_SCHEMA,
    audit_experiment,
    declare_experiment,
)
from tetris_ballistic.scripts.run_one_cell import run_cell


def _grid(tmp_path):
    spec = {
        "piece_config": "piece_19_combined_percentage",
        "pcts": [50],
        "widths": [5],
        "seeds": [0, 1],
        "ratio": 0.4,
    }
    path = tmp_path / "grid.yaml"
    path.write_text(yaml.safe_dump(spec), encoding="utf-8")
    return spec, path


def _write_trace(results, traces, *, seeds):
    width_traces = []
    height_traces = []
    finals = []
    for seed in seeds:
        simulation = joblib.load(results / "pct_50" / "L_0005" / f"seed_{seed:03d}.joblib")
        finals.append(simulation.FinalSteps)
        width_traces.append(np.asarray(simulation.Fluctuation, dtype=np.float32))
        height_traces.append(np.asarray(simulation.AvergeHeight, dtype=np.float32))
    length = min(map(len, width_traces))
    output = traces / "pct_50" / "L_0005.npz"
    output.parent.mkdir(parents=True)
    np.savez_compressed(
        output,
        seeds=np.asarray(seeds, dtype=np.int64),
        final_steps=np.asarray(finals, dtype=np.int64),
        W=np.stack([trace[:length] for trace in width_traces]),
        hbar=np.stack([trace[:length] for trace in height_traces]),
        pct=np.int32(50),
        L=np.int32(5),
        hbar_max=np.float32(1.0),
        saturated=np.bool_(False),
    )


def test_declared_grid_audit_requires_every_raw_cell_and_trace_seed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    run_cell(spec, 50, 5, 0, str(results))
    _write_trace(results, traces, seeds=[0])

    audit = audit_experiment(
        experiment="tiny",
        grid_specs=[grid],
        results_dir=results,
        traces_dir=traces,
        reduce_rc=0,
    )

    assert not audit.complete
    assert audit.heartbeat["expected_cells"] == 2
    assert audit.heartbeat["joblib_cells"] == 1
    assert audit.heartbeat["validated_joblib_cells"] == 1
    assert audit.heartbeat["error_count"] >= 2
    assert not (results / "pct_50" / "L_0005" / "seed_001.lock").exists()


def test_declared_grid_audit_accepts_exact_closed_inventory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    for seed in spec["seeds"]:
        run_cell(spec, 50, 5, seed, str(results))
    _write_trace(results, traces, seeds=[0, 1])

    audit = audit_experiment(
        experiment="tiny",
        grid_specs=[grid],
        results_dir=results,
        traces_dir=traces,
        reduce_rc=0,
    )

    assert audit.complete
    assert audit.heartbeat["error_count"] == 0
    assert audit.heartbeat["expected_cells"] == 2
    assert audit.heartbeat["expected_ensembles"] == 1
    assert audit.heartbeat["joblib_cells"] == 2
    assert audit.heartbeat["npz_cells"] == 1
    assert audit.heartbeat["reduce_complete"] is True
    assert audit.heartbeat["schema_version"] == EXPERIMENT_STATUS_SCHEMA
    assert audit.heartbeat["validated_joblib_cells"] == 2
    assert audit.heartbeat["validated_npz_cells"] == 1


def test_declared_grid_audit_rejects_extra_observed_outputs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    for seed in spec["seeds"]:
        run_cell(spec, 50, 5, seed, str(results))
    _write_trace(results, traces, seeds=[0, 1])
    extra = results / "pct_50" / "L_0005" / "seed_999.joblib"
    extra.write_bytes(b"extra")

    audit = audit_experiment(
        experiment="tiny",
        grid_specs=[grid],
        results_dir=results,
        traces_dir=traces,
        reduce_rc=0,
    )

    assert not audit.complete
    assert any("unexpected raw joblibs" in error for error in audit.heartbeat["errors"])


def test_declared_grid_audit_rejects_reduction_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    for seed in spec["seeds"]:
        run_cell(spec, 50, 5, seed, str(results))
    _write_trace(results, traces, seeds=[0, 1])

    audit = audit_experiment(
        experiment="tiny",
        grid_specs=[grid],
        results_dir=results,
        traces_dir=traces,
        reduce_rc=9,
    )

    assert not audit.complete
    assert audit.heartbeat["reduce_rc"] == 9


def test_managed_reducer_preflights_and_writes_declared_ensemble(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    for seed in spec["seeds"]:
        run_cell(spec, 50, 5, seed, str(results))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reduce_traces",
            "--in",
            str(results),
            "--out",
            str(traces),
            "--grid-spec",
            str(grid),
        ],
    )

    reduce_traces.main()

    with np.load(traces / "pct_50" / "L_0005.npz", allow_pickle=False) as trace:
        assert trace["seeds"].tolist() == [0, 1]


def test_managed_reducer_refuses_incomplete_declared_raw_grid(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    run_cell(spec, 50, 5, 0, str(results))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reduce_traces",
            "--in",
            str(results),
            "--out",
            str(traces),
            "--grid-spec",
            str(grid),
        ],
    )

    with pytest.raises(SystemExit, match="managed raw preflight failed"):
        reduce_traces.main()

    assert not list(traces.glob("**/*.npz"))


def test_managed_reducer_revalidates_the_object_used_for_reduction(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    spec, grid = _grid(tmp_path)
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    for seed in spec["seeds"]:
        run_cell(spec, 50, 5, seed, str(results))
    original_preflight = reduce_traces.validate_declared_raw_cells

    def tamper_after_preflight(declaration, results_dir):
        result = original_preflight(declaration, results_dir)
        target = results / "pct_50" / "L_0005" / "seed_000.joblib"
        target.write_bytes(target.read_bytes() + b"tampered-after-preflight")
        return result

    monkeypatch.setattr(
        reduce_traces, "validate_declared_raw_cells", tamper_after_preflight
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reduce_traces",
            "--in",
            str(results),
            "--out",
            str(traces),
            "--grid-spec",
            str(grid),
        ],
    )

    with pytest.raises(RuntimeError, match="size|checksum"):
        reduce_traces.main()

    assert not list(traces.glob("**/*.npz"))


def test_declared_grid_hash_and_cells_share_one_open_snapshot(tmp_path, monkeypatch) -> None:
    _spec_data, grid = _grid(tmp_path)
    original_payload = grid.read_bytes()
    replacement = tmp_path / "replacement.yaml"
    replacement.write_text(
        yaml.safe_dump(
            {
                "piece_config": "piece_19_combined_percentage",
                "pcts": [50],
                "widths": [5],
                "seeds": [99],
                "ratio": 0.4,
            }
        ),
        encoding="utf-8",
    )
    original_open = os.open
    replaced = False

    def replace_after_open(path, flags, *args):
        nonlocal replaced
        descriptor = original_open(path, flags, *args)
        if not replaced and os.fspath(path) == os.fspath(grid):
            replaced = True
            os.replace(replacement, grid)
        return descriptor

    monkeypatch.setattr(run_one_cell_module.os, "open", replace_after_open)
    declaration = declare_experiment([grid], tmp_path / "results")

    assert replaced
    assert set(declaration.cells) == {(50, 5, 0), (50, 5, 1)}
    assert declaration.grid_records[0]["sha256"] == hashlib.sha256(original_payload).hexdigest()
    assert yaml.safe_load(grid.read_text(encoding="utf-8"))["seeds"] == [99]


def test_managed_reducer_preserves_maximum_supported_seed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    seed = 2**32 - 1
    spec = {
        "piece_config": "piece_19_combined_percentage",
        "pcts": [50],
        "widths": [5],
        "seeds": [seed],
        "ratio": 0.4,
    }
    grid = tmp_path / "max-seed-grid.yaml"
    grid.write_text(yaml.safe_dump(spec), encoding="utf-8")
    results = tmp_path / "results"
    traces = tmp_path / "traces"
    run_cell(spec, 50, 5, seed, str(results))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reduce_traces",
            "--in",
            str(results),
            "--out",
            str(traces),
            "--grid-spec",
            str(grid),
        ],
    )

    reduce_traces.main()

    with np.load(traces / "pct_50" / "L_0005.npz", allow_pickle=False) as trace:
        assert np.issubdtype(trace["seeds"].dtype, np.integer)
        assert trace["seeds"].tolist() == [seed]
