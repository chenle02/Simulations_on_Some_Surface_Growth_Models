#!/usr/bin/env python3
"""Audit a declared managed grid and write fail-closed reduction status."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from tetris_ballistic.run_artifacts import (
    ArtifactValidationError,
    artifact_paths,
    atomic_write_bytes,
    build_run_expectation,
    managed_cell_lock,
    validate_completed_run,
)
from tetris_ballistic.scripts.run_one_cell import (
    CellRequest,
    grid_size,
    load_grid_spec_snapshot,
    prepare_cell_request,
)

EXPERIMENT_STATUS_SCHEMA = "tetris-experiment-completion-v1"
_TRACE_KEYS = {
    "L",
    "W",
    "final_steps",
    "hbar",
    "hbar_max",
    "pct",
    "saturated",
    "seeds",
}


@dataclass(frozen=True)
class ExperimentAudit:
    heartbeat: dict[str, object]
    status_markdown: str

    @property
    def complete(self) -> bool:
        return self.heartbeat["reduce_complete"] is True


@dataclass(frozen=True)
class DeclaredExperiment:
    cells: dict[tuple[int, int, int], CellRequest]
    ensembles: dict[tuple[int, int], tuple[int, ...]]
    grid_records: tuple[dict[str, str], ...]


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except FileNotFoundError:
        return False


def _validate_trace(path: Path, *, pct: int, width: int, seeds: tuple[int, ...]) -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactValidationError(f"reduced trace is missing or nonregular: {path}") from error
    try:
        with os.fdopen(descriptor, "rb") as handle:
            file_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise ArtifactValidationError(f"reduced trace is nonregular: {path}")
            with np.load(handle, allow_pickle=False) as trace:
                if set(trace.files) != _TRACE_KEYS:
                    raise ArtifactValidationError(f"reduced trace keys differ: {path}")
                observed_seeds = np.asarray(trace["seeds"])
                if (
                    observed_seeds.ndim != 1
                    or not np.issubdtype(observed_seeds.dtype, np.integer)
                    or observed_seeds.tolist() != list(seeds)
                ):
                    raise ArtifactValidationError(f"reduced trace seeds do not match grid: {path}")
                final_steps = np.asarray(trace["final_steps"])
                width_trace = np.asarray(trace["W"])
                height_trace = np.asarray(trace["hbar"])
                if final_steps.shape != (len(seeds),) or not np.issubdtype(
                    final_steps.dtype, np.integer
                ):
                    raise ArtifactValidationError(f"reduced trace final_steps shape is invalid: {path}")
                if (
                    width_trace.ndim != 2
                    or height_trace.shape != width_trace.shape
                    or width_trace.shape[0] != len(seeds)
                    or width_trace.shape[1] == 0
                ):
                    raise ArtifactValidationError(f"reduced trace matrices are invalid: {path}")
                if (
                    not np.all(np.isfinite(width_trace))
                    or not np.all(np.isfinite(height_trace))
                    or not np.all(np.isfinite(final_steps))
                ):
                    raise ArtifactValidationError(f"reduced trace contains nonfinite values: {path}")
                observed_pct = np.asarray(trace["pct"])
                observed_width = np.asarray(trace["L"])
                if (
                    observed_pct.shape != ()
                    or observed_width.shape != ()
                    or not np.issubdtype(observed_pct.dtype, np.integer)
                    or not np.issubdtype(observed_width.dtype, np.integer)
                    or int(observed_pct.item()) != pct
                    or int(observed_width.item()) != width
                ):
                    raise ArtifactValidationError(f"reduced trace identity does not match path: {path}")
    except ArtifactValidationError:
        raise
    except Exception as error:
        raise ArtifactValidationError(f"reduced trace cannot be loaded: {path}") from error
    return file_stat.st_size


def declare_experiment(
    grid_specs: list[str | os.PathLike[str]],
    results_dir: str | os.PathLike[str],
) -> DeclaredExperiment:
    """Enumerate the closed raw-cell inventory from one or more grid specs."""

    if not grid_specs:
        raise ValueError("at least one grid spec is required")
    results_root = Path(results_dir)
    declared_cells: dict[tuple[int, int, int], CellRequest] = {}
    declared_ensembles: dict[tuple[int, int], tuple[int, ...]] = {}
    grid_records: list[dict[str, str]] = []
    for grid_path in grid_specs:
        grid_file = Path(grid_path)
        spec, grid_payload = load_grid_spec_snapshot(grid_file)
        grid_records.append(
            {"path": str(grid_file), "sha256": hashlib.sha256(grid_payload).hexdigest()}
        )
        if grid_size(spec) <= 0:
            raise ValueError(f"grid is empty: {grid_path}")
        for pct in spec["pcts"]:
            for width in spec["widths"]:
                ensemble = (pct, width)
                seeds = tuple(sorted(spec["seeds"]))
                existing_seeds = declared_ensembles.get(ensemble)
                if existing_seeds is not None and existing_seeds != seeds:
                    raise ValueError(f"grid specs disagree on seeds for ensemble {ensemble}")
                declared_ensembles[ensemble] = seeds
                for seed in spec["seeds"]:
                    key = (pct, width, seed)
                    if key in declared_cells:
                        raise ValueError(f"grid specs declare duplicate cell {key}")
                    declared_cells[key] = prepare_cell_request(
                        spec, pct, width, seed, str(results_root)
                    )
    return DeclaredExperiment(
        cells=declared_cells,
        ensembles=declared_ensembles,
        grid_records=tuple(grid_records),
    )


def validate_declared_raw_cells(
    declaration: DeclaredExperiment,
    results_dir: str | os.PathLike[str],
) -> tuple[int, list[str], set[Path]]:
    """Validate every managed raw bundle and reject undeclared joblibs."""

    results_root = Path(results_dir)
    errors: list[str] = []
    valid_cells = 0
    expected_joblibs: set[Path] = set()
    for key, request in sorted(declaration.cells.items()):
        paths = artifact_paths(request.joblib_path, request.config_path)
        expected_joblibs.add(paths.joblib)
        try:
            load_validated_declared_cell(request)
        except Exception as error:
            errors.append(f"cell {key}: {error}")
        else:
            valid_cells += 1
    observed_joblibs = set(results_root.glob("**/*.joblib"))
    unexpected_joblibs = sorted(observed_joblibs - expected_joblibs)
    if unexpected_joblibs:
        errors.append(f"unexpected raw joblibs: {[str(path) for path in unexpected_joblibs[:20]]}")
    return valid_cells, errors, observed_joblibs


def load_validated_declared_cell(request: CellRequest) -> object:
    """Load one declared simulation only through its locked managed validator."""

    paths = artifact_paths(request.joblib_path, request.config_path)
    expectation = build_run_expectation(
        width=request.width,
        height=request.height,
        steps=request.steps,
        seed=request.seed,
        density=request.density,
        engine_route=request.engine_route,
        semantic_context=request.semantic_context,
    )
    if not _regular_file(paths.lock):
        raise ArtifactValidationError(f"managed cell lock is missing or nonregular: {paths.lock}")
    with managed_cell_lock(paths):
        return validate_completed_run(paths, expectation)


def audit_experiment(
    *,
    experiment: str,
    grid_specs: list[str | os.PathLike[str]],
    results_dir: str | os.PathLike[str],
    traces_dir: str | os.PathLike[str],
    reduce_rc: int,
) -> ExperimentAudit:
    """Validate every declared raw cell and reduced ensemble, not observed subsets."""

    if type(experiment) is not str or not experiment:
        raise ValueError("experiment must be a nonempty built-in string")
    results_root = Path(results_dir)
    traces_root = Path(traces_dir)
    declaration = declare_experiment(grid_specs, results_root)
    valid_cells, errors, observed_joblibs = validate_declared_raw_cells(
        declaration, results_root
    )

    valid_traces = 0
    trace_bytes = 0
    expected_traces: set[Path] = set()
    for (pct, width), seeds in sorted(declaration.ensembles.items()):
        trace_path = traces_root / f"pct_{pct:02d}" / f"L_{width:04d}.npz"
        expected_traces.add(trace_path)
        try:
            trace_bytes += _validate_trace(trace_path, pct=pct, width=width, seeds=seeds)
        except Exception as error:
            errors.append(f"ensemble {(pct, width)}: {error}")
        else:
            valid_traces += 1
    observed_traces = set(traces_root.glob("**/*.npz"))
    unexpected_traces = sorted(observed_traces - expected_traces)
    if unexpected_traces:
        errors.append(f"unexpected reduced traces: {[str(path) for path in unexpected_traces[:20]]}")

    expected_cells = len(declaration.cells)
    expected_ensembles = len(declaration.ensembles)
    complete = (
        type(reduce_rc) is int
        and reduce_rc == 0
        and not errors
        and valid_cells == expected_cells
        and valid_traces == expected_ensembles
        and len(observed_joblibs) == expected_cells
        and len(observed_traces) == expected_ensembles
    )
    heartbeat: dict[str, object] = {
        "error_count": len(errors),
        "errors": errors[:50],
        "expected_cells": expected_cells,
        "expected_ensembles": expected_ensembles,
        "experiment": experiment,
        "grid_specs": list(declaration.grid_records),
        "joblib_cells": len(observed_joblibs),
        "npz_bytes": trace_bytes,
        "npz_cells": len(observed_traces),
        "reduce_complete": complete,
        "reduce_rc": reduce_rc,
        "schema_version": EXPERIMENT_STATUS_SCHEMA,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validated_joblib_cells": valid_cells,
        "validated_npz_cells": valid_traces,
    }
    rows = [
        f"# Easley {experiment} compute status",
        "",
        f"Timestamp: `{heartbeat['timestamp_utc']}`",
        "",
        "| joblib | valid joblib | npz | valid npz | expected cells | expected ensembles | complete |",
        "|---:|---:|---:|---:|---:|---:|:--:|",
        (
            f"| {heartbeat['joblib_cells']} | {valid_cells} | {heartbeat['npz_cells']} | "
            f"{valid_traces} | {expected_cells} | {expected_ensembles} | "
            f"{'yes' if complete else 'NO'} |"
        ),
        "",
    ]
    if errors:
        rows.extend(["## Validation errors", "", *[f"- {error}" for error in errors[:50]], ""])
    rows.append("Pull reduced traces only when `reduce_complete` is true.")
    return ExperimentAudit(heartbeat=heartbeat, status_markdown="\n".join(rows) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--grid-spec", action="append", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--traces", required=True)
    parser.add_argument("--heartbeat", required=True)
    parser.add_argument("--status", required=True)
    parser.add_argument("--reduce-rc", type=int, required=True)
    args = parser.parse_args()
    audit = audit_experiment(
        experiment=args.experiment,
        grid_specs=args.grid_spec,
        results_dir=args.results,
        traces_dir=args.traces,
        reduce_rc=args.reduce_rc,
    )
    atomic_write_bytes(args.status, audit.status_markdown.encode("utf-8"))
    atomic_write_bytes(
        args.heartbeat,
        (json.dumps(audit.heartbeat, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    raise SystemExit(0 if audit.complete else 1)


if __name__ == "__main__":
    main()
