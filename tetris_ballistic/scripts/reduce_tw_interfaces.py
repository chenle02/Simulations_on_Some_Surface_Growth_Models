#!/usr/bin/env python3
"""Reduce one exp14 cell to common-time interface snapshots for TW analysis."""

from __future__ import annotations

import argparse
import json
import os
import tempfile

import joblib
import numpy as np

from tetris_ballistic.tw_analysis import (
    DEFAULT_Q_VALUES,
    DENSITY_CONVENTION,
    EXP14_SEEDS,
    PERCENTAGE_SEMANTICS,
    reconstruct_interface,
    select_target_times,
    validate_interface,
)


def _atomic_npz(path, arrays):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".tw-interfaces-", suffix=".npz", dir=os.path.dirname(path)
    )
    os.close(fd)
    try:
        np.savez_compressed(temporary, **arrays)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.integer):
        return int(value)
    return value


def _atomic_json(path, payload):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".tw-metadata-", suffix=".json", dir=os.path.dirname(path)
    )
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(_json_safe(payload), handle, indent=2, sort_keys=True,
                      allow_nan=False)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def reduce_cell(raw_root, trace_root, pct, L, q_values=DEFAULT_Q_VALUES):
    trace_path = os.path.join(trace_root, f"pct_{pct:02d}", f"L_{L:04d}.npz")
    if not os.path.exists(trace_path):
        raise FileNotFoundError(f"corrected trace NPZ is missing: {trace_path}")

    with np.load(trace_path) as trace:
        required = {"seeds", "final_steps", "W", "hbar", "height_grid"}
        missing = required - set(trace.files)
        if missing:
            raise ValueError(f"trace NPZ lacks required fields: {sorted(missing)}")
        seeds = np.asarray(trace["seeds"], dtype=np.int32)
        final_steps = np.asarray(trace["final_steps"], dtype=np.int64)
        W = np.asarray(trace["W"])
        hbar = np.asarray(trace["hbar"])
        height_grid = int(np.asarray(trace["height_grid"]).item())

    if hbar.shape != W.shape or hbar.shape[0] != seeds.size:
        raise ValueError("trace arrays and seed metadata have inconsistent shapes")
    expected_seeds = np.asarray(EXP14_SEEDS, dtype=np.int32)
    if not np.array_equal(seeds, expected_seeds):
        raise ValueError(
            "exp14 TW reduction requires exact ordered seeds [0,10,...,990]"
        )
    if final_steps.shape != seeds.shape:
        raise ValueError("final_steps must have one entry per seed")
    if hbar.shape[1] > int(final_steps.min()):
        raise ValueError("trace NPZ extends beyond at least one seed FinalSteps")

    target_indices, deposition_counts, target_mean_hbar = select_target_times(
        hbar, L, q_values=q_values
    )
    if np.any(deposition_counts > final_steps[:, None]):
        raise ValueError("a common target deposition count exceeds a seed FinalSteps")

    interfaces = np.empty((len(q_values), seeds.size, L), dtype=np.int32)
    max_mean_error = 0.0
    max_std_error = 0.0
    raw_paths = []
    for seed_index, seed in enumerate(seeds):
        raw_path = os.path.join(
            raw_root,
            f"pct_{pct:02d}",
            f"L_{L:04d}",
            f"seed_{int(seed):03d}.joblib",
        )
        if not os.path.exists(raw_path):
            raise FileNotFoundError(f"raw joblib is missing: {raw_path}")
        obj = joblib.load(raw_path)
        if int(obj.seed) != int(seed):
            raise ValueError(
                f"raw seed mismatch in {raw_path}: {obj.seed} != {int(seed)}"
            )
        if int(obj.width) != L or np.asarray(obj.substrate).shape[1] != L:
            raise ValueError(f"raw width mismatch in {raw_path}")
        if int(obj.height) != height_grid:
            raise ValueError(
                f"height_grid mismatch in {raw_path}: {obj.height} != {height_grid}"
            )
        if int(obj.FinalSteps) != int(final_steps[seed_index]):
            raise ValueError(f"FinalSteps mismatch in {raw_path}")

        raw_paths.append(raw_path)
        for q_index, (trace_index, count) in enumerate(
            zip(target_indices, deposition_counts)
        ):
            if count > int(obj.FinalSteps):
                raise ValueError(f"target deposition count exceeds FinalSteps in {raw_path}")
            interface = reconstruct_interface(obj.substrate, int(count))
            validation = validate_interface(
                interface,
                expected_hbar=float(hbar[seed_index, trace_index]),
                expected_fluctuation=float(obj.Fluctuation[trace_index]),
            )
            max_mean_error = max(max_mean_error, validation["mean_abs_error"])
            max_std_error = max(max_std_error, validation["std_abs_error"])
            interfaces[q_index, seed_index] = interface

    arrays = {
        "interfaces": interfaces,
        "seeds": seeds,
        "q_values": np.asarray(q_values, dtype=np.float64),
        "target_trace_indices": target_indices,
        "deposition_counts": deposition_counts,
        "target_mean_hbar": target_mean_hbar,
        "sticky_fraction_pct": np.int32(pct),
        "L": np.int32(L),
        "percentage_semantics": np.asarray(PERCENTAGE_SEMANTICS),
        "density_convention": np.asarray(DENSITY_CONVENTION),
        "physical_height_sign": np.asarray("positive-growth-direction"),
    }
    metadata = {
        "experiment": "exp14",
        "sticky_fraction_pct": int(pct),
        "L": int(L),
        "percentage_semantics": PERCENTAGE_SEMANTICS,
        "density_convention": DENSITY_CONVENTION,
        "n_seeds": int(seeds.size),
        "seeds": seeds.tolist(),
        "q_values": [float(q) for q in q_values],
        "target_trace_indices": target_indices.tolist(),
        "deposition_counts": deposition_counts.tolist(),
        "target_mean_hbar": target_mean_hbar.tolist(),
        "physical_height_sign": "positive-growth-direction",
        "interface_convention": (
            "H - _TopEnvelop row; occupied top row minus 1; empty column H-1"
        ),
        "validation": {
            "mean_reference": "corrected NPZ hbar per seed and trace index",
            "width_reference": "raw joblib Fluctuation per seed and trace index",
            "atol": 1e-3,
            "rtol": 2e-6,
            "max_mean_abs_error": max_mean_error,
            "max_std_abs_error": max_std_error,
            "checks_passed": int(len(q_values) * seeds.size),
        },
        "raw_root": os.path.abspath(raw_root),
        "trace_path": os.path.abspath(trace_path),
        "raw_file_count": len(raw_paths),
    }
    return arrays, metadata


def _csv_floats(value):
    return tuple(float(item) for item in value.split(",") if item.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--trace-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--pct", type=int, required=True)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--q-values", default="0.15,0.25,0.40")
    args = parser.parse_args()

    q_values = _csv_floats(args.q_values)
    arrays, metadata = reduce_cell(
        os.path.abspath(args.raw_root),
        os.path.abspath(args.trace_root),
        args.pct,
        args.width,
        q_values=q_values,
    )
    output_dir = os.path.join(args.output_root, f"pct_{args.pct:02d}")
    npz_path = os.path.join(output_dir, f"L_{args.width:04d}.npz")
    json_path = os.path.join(output_dir, f"L_{args.width:04d}.json")
    _atomic_npz(npz_path, arrays)
    _atomic_json(json_path, metadata)
    print(
        f"reduced pct={args.pct:02d} L={args.width}: "
        f"{arrays['interfaces'].shape} -> {npz_path}"
    )


if __name__ == "__main__":
    main()
