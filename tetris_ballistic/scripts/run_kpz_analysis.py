#!/usr/bin/env python3
"""
Runner for the KPZ slope-extraction pipeline.

Loads all joblib files in an experiment directory, applies the 8-step
protocol from ``tetris_ballistic.kpz_analysis``, produces per-L
local-slope plots, multi-L extrapolation plots, and writes
``results.json`` into the experiment directory.

Usage:
    .venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \\
        --exp-dir experiments/exp13
    .venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \\
        --exp-dir experiments/exp14 --piece piece_19 \\
        --pcts 5,50,90,95,98,99 --widths 50,80,100,150,200
"""

import argparse
import glob
import json
import os
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.kpz_analysis import (
    detect_plateau,
    extrapolate_to_infinity,
    growth_window_slope,
    load_ensemble,
    local_slope_bootstrap,
    log_subsample_paired_traces,
    meakin_range_of_fit,
)

KPZ_BETA = 1.0 / 3.0
SAMPLING_POLICY = {
    "method": "paired_log_spaced_indices",
    "max_points": 5000,
    "includes_endpoints": True,
}


def _sampling_policy_is_current(cell):
    """Return whether a saved cell has current estimator provenance."""
    saturated = cell.get("saturated")
    hbar_max = cell.get("hbar_max")
    return (
        cell.get("sampling_policy") == SAMPLING_POLICY
        and type(saturated) is bool
        and isinstance(hbar_max, (int, float))
        and not isinstance(hbar_max, bool)
        and np.isfinite(hbar_max)
    )


def _is_saturated(cell, L):
    """True if the mean height reached the saturation scale L^{3/2}.

    Unsaturated cells (h̄_max < L^{3/2}) have not entered the plateau regime,
    so their growth-window β droops below the asymptotic value and must be
    excluded from the multi-L extrapolation.
    """
    if "saturated" in cell:
        return bool(cell["saturated"])
    hbar_max = cell.get("hbar_max")
    if hbar_max is None:
        return True
    return hbar_max >= L ** 1.5


def run_single_cell(exp_dir, pct, L, n_eval=150, n_boot=200):
    """Run Steps 1-5 for one (percentage, L) cell."""
    W_list, hbar_list = load_ensemble(exp_dir, pct, L)
    W_ens, hbar_ens, original_common_len, sample_indices = (
        log_subsample_paired_traces(W_list, hbar_list)
    )

    # Primary estimate: growth-window OLS (avoids transient + saturation)
    gw_beta, gw_lo, gw_hi = growth_window_slope(W_ens, hbar_ens, L, n_boot=n_boot)

    eval_log_t, slope_med, slope_lo, slope_hi = local_slope_bootstrap(
        W_ens, hbar_ens, n_eval=n_eval, n_boot=n_boot
    )

    plateau_result = detect_plateau(
        eval_log_t, slope_med, slope_lo, slope_hi,
        deriv_thresh=0.08, ci_width_thresh=0.25, min_log_extent=0.3,
        log_hbar_lo=np.log10(10.0), log_hbar_hi=np.log10(0.5 * L ** 1.5),
    )

    (m_slope1, m_se1), (m_slope2, m_se2) = meakin_range_of_fit(W_ens, hbar_ens)

    hbar_max = float(np.mean(hbar_ens, axis=0)[-1])
    saturated = hbar_max >= L ** 1.5

    cell = {
        "percentage": pct,
        "L": L,
        "n_seeds": len(W_list),
        "min_trace_len": original_common_len,
        "analysis_point_count": int(sample_indices.size),
        "sampling_policy": dict(SAMPLING_POLICY),
        "hbar_max": hbar_max,
        "saturated": saturated,
        "growth_window_beta": gw_beta,
        "growth_window_ci": [gw_lo, gw_hi],
        "meakin_window1": {"slope": m_slope1, "se": m_se1},
        "meakin_window2": {"slope": m_slope2, "se": m_se2},
    }

    if plateau_result is not None:
        _, plateau_beta, (ci_lo, ci_hi) = plateau_result
        cell["plateau_beta"] = plateau_beta
        cell["plateau_ci"] = [ci_lo, ci_hi]
        cell["plateau_detected"] = True
    else:
        cell["plateau_detected"] = False

    # Use growth-window slope as primary β estimate for extrapolation
    cell["beta_for_extrap"] = gw_beta
    cell["beta_err_for_extrap"] = (
        (gw_hi - gw_lo) / 2.0 if not np.isnan(gw_beta) else np.nan
    )

    return cell, eval_log_t, slope_med, slope_lo, slope_hi, plateau_result


def plot_local_slopes(pct, per_L_data, widths, out_dir):
    """Per-percentage plot: local slope curves for all L values."""
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(widths)))

    for (L, data), color in zip(sorted(per_L_data.items()), colors):
        elt, sm, slo, shi, plateau = data
        ax.plot(elt, sm, color=color, linewidth=1.5, label=f"L={L}")
        ax.fill_between(elt, slo, shi, color=color, alpha=0.15)
        if plateau is not None:
            pmask, _, _ = plateau
            ax.plot(elt[pmask], sm[pmask], color=color, linewidth=3, alpha=0.7)

    ax.axhline(KPZ_BETA, color="red", linestyle="--", linewidth=1, label="β = 1/3")
    ax.axhline(0.25, color="gray", linestyle=":", linewidth=1, label="β = 1/4 (EW)")
    ax.set_xlabel("log₁₀(h̄)  (deposited height)")
    ax.set_ylabel("Effective exponent β_eff(h̄)")
    ax.set_title(f"Effective exponent — piece_19, {pct}% sticky")
    ax.set_ylim(0, 0.7)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = os.path.join(out_dir, f"local_slope_pct{pct:02d}.png")
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_extrapolation(pct, L_arr, beta_arr, err_arr, extrap, out_dir):
    """Per-percentage multi-L extrapolation plot."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.errorbar(L_arr, beta_arr, yerr=err_arr, fmt="o", capsize=4, label="β̂(L)")
    ax.axhline(KPZ_BETA, color="red", linestyle="--", linewidth=1, label="β = 1/3")

    beta_inf, beta_inf_err, popt, _ = extrap
    if popt is not None:
        L_fine = np.linspace(min(L_arr) * 0.8, max(L_arr) * 2, 200)
        ax.plot(
            L_fine, popt[0] + popt[1] * L_fine ** (-popt[2]),
            "k-", linewidth=1, alpha=0.6,
            label=f"β∞={popt[0]:.4f}±{beta_inf_err:.4f}, ω={popt[2]:.2f}",
        )
    else:
        ax.axhline(
            beta_inf, color="green", linestyle=":",
            label=f"β∞={beta_inf:.4f}±{beta_inf_err:.4f} (wtd avg)",
        )

    ax.set_xlabel("Strip width L")
    ax.set_ylabel("Plateau β̂(L)")
    ax.set_title(f"Multi-L extrapolation — {pct}% sticky")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = os.path.join(out_dir, f"multi_L_extrapolation_pct{pct:02d}.png")
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    print(f"  Saved {fname}")


def _serialize(obj):
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not serializable: {type(obj)}")


def _cells_dir(exp_dir):
    return os.path.join(exp_dir, "kpz_cells")


def _cell_path(exp_dir, pct, L):
    return os.path.join(_cells_dir(exp_dir), f"cell_pct{pct:02d}_L{L:04d}.json")


def _per_pct_path(exp_dir, pct):
    return os.path.join(_cells_dir(exp_dir), f"per_pct{pct:02d}.json")


def _atomic_write_json(path, data):
    """Write JSON atomically: write to .tmp then rename.

    Prevents corrupted partial writes when a job is killed mid-write.
    Critical for resumability of long HPC runs.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=_serialize)
    os.replace(tmp, path)


def aggregate_results(exp_dir):
    """Stream-aggregate per-pct JSON files into a single results.json.

    Replaces the old in-memory dict approach. At any scale (300 or 10K
    cells), memory peak stays at one per-pct dict in flight.
    """
    out = {}
    for path in sorted(glob.glob(os.path.join(_cells_dir(exp_dir), "per_pct*.json"))):
        with open(path) as f:
            data = json.load(f)
        out[str(data["pct"])] = data
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exp-dir", required=True,
        help="Directory containing config_piece_*.joblib files",
    )
    parser.add_argument(
        "--pcts", default="5,50,90,95,98,99",
        help="Comma-separated percentages (default: 5,50,90,95,98,99)",
    )
    parser.add_argument(
        "--widths", default="50,80,100,150,200",
        help="Comma-separated strip widths (default: 50,80,100,150,200)",
    )
    parser.add_argument(
        "--n-boot", type=int, default=200, help="Bootstrap replicates",
    )
    parser.add_argument(
        "--n-eval", type=int, default=150,
        help="Number of log-spaced evaluation points",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Skip cells whose per-cell JSON already exists in kpz_cells/",
    )
    parser.add_argument(
        "--aggregate-only", action="store_true",
        help="Skip all computation; just stream-aggregate existing per-pct JSON",
    )
    args = parser.parse_args()

    exp_dir = os.path.abspath(args.exp_dir)
    if not os.path.isdir(exp_dir):
        sys.exit(f"--exp-dir not found: {exp_dir}")
    os.makedirs(_cells_dir(exp_dir), exist_ok=True)

    percentages = [int(x) for x in args.pcts.split(",")]
    widths = [int(x) for x in args.widths.split(",")]

    print("=" * 60)
    print(f"KPZ Slope Extraction — {exp_dir}")
    if args.resume:
        print("(--resume: reusing cells with the current sampling policy)")
    if args.aggregate_only:
        print("(--aggregate-only: skipping all computation)")
    print("=" * 60)

    if not args.aggregate_only:
        for pct in percentages:
            print(f"\n--- Percentage = {pct}% ---")
            per_L_data = {}
            cells_for_pct = {}
            L_vals, beta_vals, err_vals = [], [], []

            for L in widths:
                cell_path = _cell_path(exp_dir, pct, L)
                reuse_cell = False
                if args.resume and os.path.exists(cell_path):
                    with open(cell_path) as f:
                        cell = json.load(f)
                    reuse_cell = _sampling_policy_is_current(cell)
                    if reuse_cell:
                        print(f"  L={L}: resume — loaded {os.path.basename(cell_path)}")
                        plateau = None
                        elt = np.array(cell.get("eval_log_t", []))
                        sm = np.array(cell.get("slope_med", []))
                        slo = np.array(cell.get("slope_lo", []))
                        shi = np.array(cell.get("slope_hi", []))
                    else:
                        print(
                            f"  L={L}: resume — stale sampling policy; recomputing"
                        )

                if not reuse_cell:
                    print(f"  L={L}: loading + bootstrap...", end=" ", flush=True)
                    try:
                        cell, elt, sm, slo, shi, plateau = run_single_cell(
                            exp_dir, pct, L, n_eval=args.n_eval, n_boot=args.n_boot
                        )
                    except ValueError as e:
                        print(f"absent — skipping ({e})")
                        continue
                    cell["eval_log_t"] = elt.tolist()
                    cell["slope_med"] = sm.tolist()
                    cell["slope_lo"] = slo.tolist()
                    cell["slope_hi"] = shi.tolist()
                    _atomic_write_json(cell_path, cell)
                    gw = cell["growth_window_beta"]
                    gwci = cell["growth_window_ci"]
                    pstat = " + plateau" if cell["plateau_detected"] else ""
                    print(f"β̂(growth-win)={gw:.4f} [{gwci[0]:.4f}, {gwci[1]:.4f}]{pstat}")

                per_L_data[L] = (elt, sm, slo, shi, plateau)
                cells_for_pct[str(L)] = cell

                if _is_saturated(cell, L):
                    L_vals.append(L)
                    beta_vals.append(cell["beta_for_extrap"])
                    err_vals.append(cell["beta_err_for_extrap"])

            plot_local_slopes(pct, per_L_data, widths, exp_dir)

            sat_betas = [
                cells_for_pct[str(L)]["growth_window_beta"]
                for L in widths
                if str(L) in cells_for_pct
                and _is_saturated(cells_for_pct[str(L)], L)
                and not np.isnan(cells_for_pct[str(L)]["growth_window_beta"])
            ]
            saturated_mean_beta = float(np.mean(sat_betas)) if sat_betas else np.nan
            saturated_std_beta = (
                float(np.std(sat_betas, ddof=1)) if len(sat_betas) > 1 else np.nan
            )

            per_pct = {
                "pct": pct,
                "cells": cells_for_pct,
                "n_saturated_L": len(L_vals),
                "saturated_mean_beta": saturated_mean_beta,
                "saturated_std_beta": saturated_std_beta,
            }

            if len(L_vals) >= 2:
                L_arr = np.array(L_vals, dtype=float)
                extrap = extrapolate_to_infinity(
                    L_arr, np.array(beta_vals), np.array(err_vals)
                )
                beta_inf, beta_inf_err, popt, _ = extrap
                per_pct["extrapolation"] = {
                    "beta_inf": beta_inf,
                    "beta_inf_err": beta_inf_err,
                    "fit_converged": popt is not None,
                    "n_L_used": len(L_vals),
                }
                if popt is not None:
                    per_pct["extrapolation"]["c"] = float(popt[1])
                    per_pct["extrapolation"]["omega"] = float(popt[2])
                print(f"  → saturated-mean β = {saturated_mean_beta:.4f} "
                      f"(over {len(L_vals)} saturated L); "
                      f"β∞ = {beta_inf:.4f} ± {beta_inf_err:.4f}")
            else:
                extrap = (saturated_mean_beta, saturated_std_beta, None, None)
                per_pct["extrapolation"] = {
                    "beta_inf": np.nan,
                    "beta_inf_err": np.nan,
                    "fit_converged": False,
                    "n_L_used": len(L_vals),
                    "note": "insufficient saturated L for extrapolation; "
                            "report saturated_mean_beta instead",
                }
                print(f"  → saturated-mean β = {saturated_mean_beta:.4f} "
                      f"(only {len(L_vals)} saturated L — β∞ extrapolation skipped)")

            _atomic_write_json(_per_pct_path(exp_dir, pct), per_pct)

            if len(L_vals) >= 2:
                plot_extrapolation(
                    pct, np.array(L_vals, dtype=float), np.array(beta_vals),
                    np.array(err_vals), extrap, exp_dir,
                )

    all_results = aggregate_results(exp_dir)
    results_path = os.path.join(exp_dir, "results.json")
    _atomic_write_json(results_path, all_results)
    print(f"\nResults written to {results_path}")

    print("\n" + "=" * 60)
    print("SUMMARY — β vs sticky-fraction (KPZ↔EW crossover)")
    print("  KPZ β=1/3≈0.333   EW β=1/4=0.250   (measured on log h̄ axis)")
    print("=" * 60)
    for pct in percentages:
        if str(pct) not in all_results:
            continue
        pdata = all_results[str(pct)]
        smb = pdata.get("saturated_mean_beta", float("nan"))
        nsat = pdata.get("n_saturated_L", 0)
        ext = pdata.get("extrapolation", {})
        binf = ext.get("beta_inf", float("nan"))
        cls = "KPZ" if 0.30 <= smb <= 0.36 else ("EW" if 0.22 <= smb < 0.30 else "—")
        binf_str = f"β∞={binf:.3f}" if not np.isnan(binf) else "β∞=n/a"
        print(f"  pct={pct:2d}%: saturated-mean β = {smb:.3f} "
              f"({nsat} sat. L)  [{cls}]   {binf_str}")


if __name__ == "__main__":
    main()
