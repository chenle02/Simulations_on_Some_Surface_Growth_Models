#!/usr/bin/env python3
"""Compare full-point and log-subsampled KPZ growth-window OLS estimates.

This is a sensitivity diagnostic, not the production bootstrap runner.  It
measures how changing point weights affects the central slope while keeping the
physical clock (mean deposited height) and growth window fixed.

For exp14, ``pct`` means sticky fraction: ``run_one_cell.build_density`` writes
Piece-19 as ``[100 - pct, pct]``, and the canonical state ordering is
``[nonsticky, sticky]``.
"""

import argparse
import glob
import json
import os
import tempfile

import numpy as np
from scipy.stats import linregress

from tetris_ballistic.kpz_analysis import (
    load_ensemble,
    log_subsample_paired_traces,
)


def _paired_common_length(W_list, hbar_list):
    if not W_list or not hbar_list:
        raise ValueError("W_list and hbar_list must be non-empty")
    if len(W_list) != len(hbar_list):
        raise ValueError("W_list and hbar_list must contain the same seeds")
    common_len = min(
        min(len(trace) for trace in W_list),
        min(len(trace) for trace in hbar_list),
    )
    if common_len < 2:
        raise ValueError("traces must contain at least two paired samples")
    return common_len


def streaming_trace_means(W_list, hbar_list):
    """Return paired full-resolution means without creating a seed-by-time copy."""
    common_len = _paired_common_length(W_list, hbar_list)
    mean_W = np.zeros(common_len, dtype=np.float64)
    mean_hbar = np.zeros(common_len, dtype=np.float64)
    for W_trace, hbar_trace in zip(W_list, hbar_list):
        np.add(mean_W, W_trace[:common_len], out=mean_W)
        np.add(mean_hbar, hbar_trace[:common_len], out=mean_hbar)
    scale = 1.0 / len(W_list)
    mean_W *= scale
    mean_hbar *= scale
    return mean_W, mean_hbar, common_len


def central_growth_window_slope(mean_W, mean_hbar, L, hbar_lo=10.0):
    """Central OLS slope of log W versus log hbar, plus fitted point count."""
    hbar_hi = 0.5 * L ** 1.5
    mask = (
        (mean_hbar >= hbar_lo)
        & (mean_hbar <= hbar_hi)
        & (mean_W > 0)
    )
    if mask.sum() < 10:
        mask = (mean_hbar >= hbar_lo) & (mean_W > 0)
    point_count = int(mask.sum())
    if point_count < 5:
        return float("nan"), point_count
    fit = linregress(
        np.log10(mean_hbar[mask]),
        np.log10(mean_W[mask]),
    )
    return float(fit.slope), point_count


def analyze_cell(exp_dir, sticky_fraction_pct, L, max_points=5000):
    W_list, hbar_list = load_ensemble(exp_dir, sticky_fraction_pct, L)
    mean_W, mean_hbar, common_len = streaming_trace_means(W_list, hbar_list)
    full_beta, full_point_count = central_growth_window_slope(
        mean_W, mean_hbar, L
    )
    hbar_max = float(mean_hbar[-1])

    sampled_W, sampled_hbar, sampled_common_len, indices = (
        log_subsample_paired_traces(
            W_list, hbar_list, max_points=max_points
        )
    )
    if sampled_common_len != common_len:
        raise RuntimeError("full and sampled common lengths disagree")
    sampled_mean_W = np.mean(sampled_W, axis=0, dtype=np.float64)
    sampled_mean_hbar = np.mean(sampled_hbar, axis=0, dtype=np.float64)
    log_beta, log_growth_window_points = central_growth_window_slope(
        sampled_mean_W, sampled_mean_hbar, L
    )

    delta = log_beta - full_beta
    relative_delta = delta / full_beta if full_beta != 0 else float("nan")
    return {
        "sticky_fraction_pct": int(sticky_fraction_pct),
        "L": int(L),
        "n_seeds": len(W_list),
        "original_common_length": int(common_len),
        "full_growth_window_point_count": full_point_count,
        "full_point_beta": full_beta,
        "log_sample_total_point_count": int(indices.size),
        "log_sample_growth_window_point_count": log_growth_window_points,
        "log_sample_beta": log_beta,
        "beta_delta_log_minus_full": delta,
        "beta_relative_delta_log_minus_full": relative_delta,
        "hbar_max": hbar_max,
        "saturated": bool(hbar_max >= L ** 1.5),
    }


def _cell_data_available(exp_dir, sticky_fraction_pct, L):
    """Return whether the reduced NPZ or raw joblib layout contains a cell."""
    npz_path = os.path.join(
        exp_dir,
        f"pct_{sticky_fraction_pct:02d}",
        f"L_{L:04d}.npz",
    )
    if os.path.exists(npz_path):
        return True
    pattern = os.path.join(
        exp_dir,
        f"config_piece_19_combined_percentage_{sticky_fraction_pct:02d}_w={L}_seed=*.joblib",
    )
    return bool(glob.glob(pattern))


def analyze_grid(exp_dir, pcts, widths, max_points=5000):
    if max_points < 2:
        raise ValueError("max_points must be at least 2")

    cells = []
    missing_cells = []
    for pct in pcts:
        for L in widths:
            if not _cell_data_available(exp_dir, pct, L):
                missing_cells.append({
                    "sticky_fraction_pct": int(pct),
                    "L": int(L),
                    "reason": "no reduced NPZ or raw joblib cell data",
                })
                continue
            cells.append(analyze_cell(exp_dir, pct, L, max_points))
    return {
        "experiment": "exp14",
        "percentage_semantics": "sticky_fraction_pct",
        "density_convention": "Piece-19=[100-pct,pct]=[nonsticky,sticky]",
        "full_estimator": "OLS(log10(mean W), log10(mean hbar)) on all growth-window points",
        "sampled_estimator": "same OLS after paired log-spaced index sampling",
        "growth_window": "10 <= mean_hbar <= 0.5 * L**1.5 (production fallback retained)",
        "max_sample_points": int(max_points),
        "nonfinite_numeric_convention": "JSON null",
        "cells": cells,
        "missing_cells": missing_cells,
    }


def _json_safe(value):
    """Recursively encode nonfinite numeric estimates as JSON null."""
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
    output = os.path.abspath(path)
    parent = os.path.dirname(output)
    os.makedirs(parent, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".sampling-sensitivity-", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(
                _json_safe(payload),
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temp_path, output)
    except BaseException:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def _csv_ints(value):
    return [int(item) for item in value.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp-dir", required=True)
    parser.add_argument("--pcts", default="5,50,90,95,98,99")
    parser.add_argument("--widths", default="50,80,100,150,200,250,300,400,500")
    parser.add_argument("--max-points", type=int, default=5000)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    result = analyze_grid(
        os.path.abspath(args.exp_dir),
        _csv_ints(args.pcts),
        _csv_ints(args.widths),
        max_points=args.max_points,
    )
    atomic_write_json(args.output, result)
    print(
        f"Wrote {len(result['cells'])} cells and "
        f"{len(result['missing_cells'])} missing cells to {args.output}"
    )


if __name__ == "__main__":
    main()
