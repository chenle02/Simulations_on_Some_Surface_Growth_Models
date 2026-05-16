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
import json
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.kpz_analysis import (
    load_ensemble,
    truncate_to_common_length,
    growth_window_slope,
    local_slope_bootstrap,
    detect_plateau,
    meakin_range_of_fit,
    extrapolate_to_infinity,
)

KPZ_BETA = 1.0 / 3.0


def run_single_cell(exp_dir, pct, L, n_eval=150, n_boot=200):
    """Run Steps 1-5 for one (percentage, L) cell."""
    W_list, hbar_list = load_ensemble(exp_dir, pct, L)
    W_ens, min_len = truncate_to_common_length(W_list)
    hbar_ens, _ = truncate_to_common_length(hbar_list)

    # Primary estimate: growth-window OLS (avoids transient + saturation)
    gw_beta, gw_lo, gw_hi = growth_window_slope(W_ens, hbar_ens, L, n_boot=n_boot)

    eval_log_t, slope_med, slope_lo, slope_hi = local_slope_bootstrap(
        W_ens, n_eval=n_eval, n_boot=n_boot
    )

    plateau_result = detect_plateau(
        eval_log_t, slope_med, slope_lo, slope_hi,
        deriv_thresh=0.08, ci_width_thresh=0.25, min_log_extent=0.3,
    )

    (m_slope1, m_se1), (m_slope2, m_se2) = meakin_range_of_fit(W_ens, hbar_ens)

    cell = {
        "percentage": pct,
        "L": L,
        "n_seeds": len(W_list),
        "min_trace_len": min_len,
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
    ax.set_xlabel("log₁₀(t)")
    ax.set_ylabel("Local slope β̂(t)")
    ax.set_title(f"Local slope — piece_19, {pct}% sticky")
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
    args = parser.parse_args()

    exp_dir = os.path.abspath(args.exp_dir)
    if not os.path.isdir(exp_dir):
        sys.exit(f"--exp-dir not found: {exp_dir}")

    percentages = [int(x) for x in args.pcts.split(",")]
    widths = [int(x) for x in args.widths.split(",")]

    print("=" * 60)
    print(f"KPZ Slope Extraction — {exp_dir}")
    print("=" * 60)

    all_results = {}

    for pct in percentages:
        print(f"\n--- Percentage = {pct}% ---")
        per_L_data = {}
        L_vals, beta_vals, err_vals = [], [], []

        for L in widths:
            print(f"  L={L}: loading + bootstrap...", end=" ", flush=True)
            cell, elt, sm, slo, shi, plateau = run_single_cell(
                exp_dir, pct, L, n_eval=args.n_eval, n_boot=args.n_boot
            )
            per_L_data[L] = (elt, sm, slo, shi, plateau)

            L_vals.append(L)
            beta_vals.append(cell["beta_for_extrap"])
            err_vals.append(cell["beta_err_for_extrap"])

            gw = cell["growth_window_beta"]
            gwci = cell["growth_window_ci"]
            pstat = " + plateau" if cell["plateau_detected"] else ""
            print(f"β̂(growth-win)={gw:.4f} [{gwci[0]:.4f}, {gwci[1]:.4f}]{pstat}")

            all_results.setdefault(str(pct), {})[str(L)] = cell

        plot_local_slopes(pct, per_L_data, widths, exp_dir)

        L_arr = np.array(L_vals, dtype=float)
        beta_arr = np.array(beta_vals)
        err_arr = np.array(err_vals)
        extrap = extrapolate_to_infinity(L_arr, beta_arr, err_arr)
        beta_inf, beta_inf_err, popt, _ = extrap

        print(f"  → β∞ = {beta_inf:.4f} ± {beta_inf_err:.4f}")
        if popt is not None:
            print(f"    (c={popt[1]:.4f}, ω={popt[2]:.4f})")

        all_results[str(pct)]["extrapolation"] = {
            "beta_inf": beta_inf,
            "beta_inf_err": beta_inf_err,
            "fit_converged": popt is not None,
        }
        if popt is not None:
            all_results[str(pct)]["extrapolation"]["c"] = float(popt[1])
            all_results[str(pct)]["extrapolation"]["omega"] = float(popt[2])

        plot_extrapolation(pct, L_arr, beta_arr, err_arr, extrap, exp_dir)

    results_path = os.path.join(exp_dir, "results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2, default=_serialize)
    print(f"\nResults written to {results_path}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for pct in percentages:
        ext = all_results[str(pct)]["extrapolation"]
        flag = "✓" if 0.25 <= ext["beta_inf"] <= 0.40 else "✗"
        print(f"  pct={pct:2d}%: β∞ = {ext['beta_inf']:.4f} "
              f"± {ext['beta_inf_err']:.4f}  {flag}")


if __name__ == "__main__":
    main()
