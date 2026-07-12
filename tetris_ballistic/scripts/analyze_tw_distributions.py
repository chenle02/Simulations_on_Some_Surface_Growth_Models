#!/usr/bin/env python3
"""Analyze compact exp14 interfaces against GOE Tracy--Widom moments."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import tempfile

import numpy as np

from tetris_ballistic.tw_analysis import (
    DEFAULT_Q_VALUES,
    DENSITY_CONVENTION,
    EXP14_SEEDS,
    PERCENTAGE_SEMANTICS,
    bootstrap_seed_block_moments,
    classify_cross_l_goe,
    compare_to_goe,
    fixed_column_moments,
)

_CELL_RE = re.compile(r"pct_(\d+)/L_(\d+)\.npz$")


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


def atomic_write_json(path, payload):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".tw-analysis-", suffix=".json", dir=os.path.dirname(path)
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


def analyze_compact_cell(path, n_boot=2000, rng_seed=20260712):
    with np.load(path) as data:
        required = {
            "interfaces", "seeds", "q_values", "target_trace_indices",
            "deposition_counts", "target_mean_hbar", "sticky_fraction_pct",
            "L", "percentage_semantics", "density_convention",
            "physical_height_sign",
        }
        missing = required - set(data.files)
        if missing:
            raise ValueError(f"compact interface NPZ lacks fields: {sorted(missing)}")
        interfaces = np.asarray(data["interfaces"])
        seeds = np.asarray(data["seeds"])
        q_values = np.asarray(data["q_values"], dtype=np.float64)
        target_indices = np.asarray(data["target_trace_indices"])
        deposition_counts = np.asarray(data["deposition_counts"])
        target_mean_hbar = np.asarray(data["target_mean_hbar"])
        pct = int(np.asarray(data["sticky_fraction_pct"]).item())
        L = int(np.asarray(data["L"]).item())
        semantics = str(np.asarray(data["percentage_semantics"]).item())
        convention = str(np.asarray(data["density_convention"]).item())
        physical_height_sign = str(
            np.asarray(data["physical_height_sign"]).item()
        )

    if semantics != PERCENTAGE_SEMANTICS or convention != DENSITY_CONVENTION:
        raise ValueError("compact input has incompatible percentage semantics")
    if physical_height_sign != "positive-growth-direction":
        raise ValueError("compact input has incompatible physical-height sign")
    expected_q = np.asarray(DEFAULT_Q_VALUES, dtype=np.float64)
    if q_values.shape != expected_q.shape or not np.array_equal(q_values, expected_q):
        raise ValueError("compact input must use exact q values (0.15,0.25,0.40)")
    if not np.issubdtype(seeds.dtype, np.integer):
        raise ValueError("compact seed metadata must be integer-valued")
    expected_seeds = np.asarray(EXP14_SEEDS, dtype=seeds.dtype)
    if seeds.shape != expected_seeds.shape or not np.array_equal(seeds, expected_seeds):
        raise ValueError("compact input must use exact ordered seeds [0,10,...,990]")
    if interfaces.shape != (expected_q.size, expected_seeds.size, L):
        raise ValueError("interfaces shape is inconsistent with q/seeds/L metadata")
    if not (
        target_indices.shape == deposition_counts.shape
        == target_mean_hbar.shape == expected_q.shape
    ):
        raise ValueError("target-time metadata arrays have inconsistent shapes")
    if not (
        np.issubdtype(target_indices.dtype, np.integer)
        and np.issubdtype(deposition_counts.dtype, np.integer)
    ):
        raise ValueError("target indices and deposition counts must be integers")
    if not np.array_equal(deposition_counts, target_indices + 1):
        raise ValueError("deposition_counts must equal target_trace_indices + 1")
    if np.any(target_indices < 0) or np.any(deposition_counts < 1):
        raise ValueError("target indices and deposition counts must be positive")
    if not np.all(np.isfinite(interfaces)) or not np.all(np.isfinite(target_mean_hbar)):
        raise ValueError("compact interface and target arrays must be finite")
    if n_boot < 2000:
        raise ValueError("n_boot must be at least 2000")

    records = []
    for q_index, q in enumerate(q_values):
        q_seed = int(rng_seed + pct * 100_000 + L * 100 + q_index * 2)
        pooled = compare_to_goe(
            bootstrap_seed_block_moments(
                interfaces[q_index], n_boot=n_boot, rng_seed=q_seed
            )
        )
        fixed = compare_to_goe(
            fixed_column_moments(
                interfaces[q_index], column=L // 2, n_boot=n_boot,
                rng_seed=q_seed + 1,
            )
        )
        records.append({
            "sticky_fraction_pct": pct,
            "L": L,
            "q": float(q),
            "target_trace_index": int(target_indices[q_index]),
            "deposition_count": int(deposition_counts[q_index]),
            "target_mean_hbar": float(target_mean_hbar[q_index]),
            "pooled": pooled,
            "fixed_center_column": fixed,
        })

    return {
        "experiment": "exp14",
        "sticky_fraction_pct": pct,
        "L": L,
        "percentage_semantics": PERCENTAGE_SEMANTICS,
        "density_convention": DENSITY_CONVENTION,
        "physical_height_sign": "positive-growth-direction",
        "n_seeds": int(seeds.size),
        "n_boot": int(n_boot),
        "interpretation_limit": (
            "two-moment GOE compatibility is a KPZ fingerprint, not proof of full universality"
        ),
        "records": records,
    }


def analyze_directory(input_root, output_root, n_boot=2000, rng_seed=20260712):
    cell_results = []
    aggregate_records = []
    paths = sorted(glob.glob(os.path.join(input_root, "pct_*", "L_*.npz")))
    if not paths:
        raise FileNotFoundError(f"no compact interface NPZ files under {input_root}")
    for path in paths:
        match = _CELL_RE.search(path)
        if match is None:
            continue
        result = analyze_compact_cell(path, n_boot=n_boot, rng_seed=rng_seed)
        pct, L = result["sticky_fraction_pct"], result["L"]
        output = os.path.join(output_root, f"pct_{pct:02d}", f"L_{L:04d}.json")
        atomic_write_json(output, result)
        cell_results.append({"sticky_fraction_pct": pct, "L": L, "path": output})
        aggregate_records.extend(result["records"])

    pcts = sorted({record["sticky_fraction_pct"] for record in aggregate_records})
    verdicts = {
        str(pct): classify_cross_l_goe(aggregate_records, pct) for pct in pcts
    }
    aggregate = {
        "experiment": "exp14",
        "percentage_semantics": PERCENTAGE_SEMANTICS,
        "density_convention": DENSITY_CONVENTION,
        "physical_height_sign": "positive-growth-direction",
        "goe_reference": {"skewness": 0.2935, "excess_kurtosis": 0.1652},
        "bootstrap_unit": "seed_block",
        "n_boot": int(n_boot),
        "cell_results": cell_results,
        "records": aggregate_records,
        "cross_L_verdicts": verdicts,
        "interpretation_limit": (
            "KPZ-GOE consistent means two moments pass a conservative finite-size gate; "
            "it does not establish full KPZ universality"
        ),
    }
    aggregate_path = os.path.join(output_root, "results.json")
    atomic_write_json(aggregate_path, aggregate)
    return aggregate_path, aggregate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--n-boot", type=int, default=2000)
    parser.add_argument("--rng-seed", type=int, default=20260712)
    args = parser.parse_args()
    path, aggregate = analyze_directory(
        os.path.abspath(args.input_root), os.path.abspath(args.output_root),
        n_boot=args.n_boot, rng_seed=args.rng_seed,
    )
    print(f"analyzed {len(aggregate['cell_results'])} cells -> {path}")


if __name__ == "__main__":
    main()
