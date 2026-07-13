#!/usr/bin/env python3
"""
Runner for the KPZ slope-extraction pipeline.

Loads one explicit reduced or legacy-flat trace layout, applies the 8-step
protocol from ``tetris_ballistic.kpz_analysis``, and publishes identity-bound
cell, percentage, and aggregate JSON artifacts. Cached cells are reusable only
when their exact input bytes, estimator settings, software, and RNG identity
match the current request.

Usage:
    .venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \\
        --trace-root experiments/exp13/traces --input-layout reduced \\
        --percentage-convention nonsticky-fraction \\
        --model-profile piece-19-one-cell-v1 \\
        --out-dir experiments/exp13/analysis
    .venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \\
        --trace-root experiments/exp14/traces --input-layout reduced \\
        --percentage-convention sticky-fraction \\
        --model-profile piece-19-one-cell-v1 \\
        --out-dir experiments/exp14/analysis \\
        --pcts 5,50,90,95,98,99 --widths 50,80,100,150,200
"""

import argparse
import math
import os
import stat
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.analysis_artifacts import (
    AnalysisArtifactValidationError,
    analysis_artifact_lock,
    analysis_artifact_paths,
    analysis_software_identity,
    build_analysis_identity,
    build_identity,
    canonical_json_bytes,
    fingerprint_regular_file,
    fingerprint_regular_files,
    invalidate_json_artifact,
    load_json_artifact,
    write_json_artifact,
)
from tetris_ballistic.kpz_analysis import (
    REDUCED_INPUT_LAYOUT,
    SUPPORTED_INPUT_LAYOUTS,
    detect_plateau,
    extrapolate_to_infinity,
    growth_window_slope,
    load_ensemble,
    local_slope_bootstrap,
    log_subsample_paired_traces,
    meakin_range_of_fit,
    resolve_ensemble_input,
)
from tetris_ballistic.run_artifacts import atomic_write_bytes

KPZ_BETA = 1.0 / 3.0
SAMPLING_POLICY = {
    "method": "paired_log_spaced_indices",
    "max_points": 5000,
    "includes_endpoints": True,
}
ANALYSIS_RNG_POLICY = {
    "bit_generator": "numpy.random.PCG64",
    "stream_policy": "estimator-local-restart-same-seed-v1",
}
CELL_INPUT_PROFILE = "tetris-kpz-cell-input-sha256-v1"
DERIVED_INPUT_PROFILE = "tetris-kpz-derived-input-set-sha256-v1"
ESTIMATOR_PROFILE = "tetris-kpz-slope-estimator-v2"
DERIVATION_PROFILE = "tetris-kpz-extrapolation-v1"
PERCENTAGE_CONVENTIONS = ("nonsticky-fraction", "sticky-fraction")
MODEL_PROFILES = ("piece-19-one-cell-v1",)
MIN_PRODUCTION_BOOTSTRAPS = 200
MIN_PRODUCTION_SEEDS = 10


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


def run_single_cell(
    trace_root,
    pct,
    L,
    n_eval=150,
    n_boot=200,
    *,
    percentage_convention,
    model_profile,
    min_seeds=10,
    rng_seed=42,
    input_layout=REDUCED_INPUT_LAYOUT,
    resolved_input=None,
):
    """Run Steps 1-5 for one (percentage, L) cell."""
    percentage_convention = _require_percentage_convention(percentage_convention)
    model_profile = _require_model_profile(model_profile)
    W_list, hbar_list = load_ensemble(
        trace_root,
        pct,
        L,
        input_layout=input_layout,
        percentage_convention=percentage_convention,
        resolved_input=resolved_input,
    )
    if type(min_seeds) is not int or min_seeds < 2:
        raise ValueError("min_seeds must be a built-in integer of at least two")
    if len(W_list) < min_seeds:
        raise ValueError(
            f"pct={pct}, L={L} has {len(W_list)} seeds; at least {min_seeds} are required"
        )
    n_seeds = len(W_list)
    W_ens, hbar_ens, original_common_len, sample_indices = (
        log_subsample_paired_traces(W_list, hbar_list)
    )
    del W_list, hbar_list

    # Primary estimate: growth-window OLS (avoids transient + saturation)
    gw_beta, gw_lo, gw_hi = growth_window_slope(
        W_ens, hbar_ens, L, n_boot=n_boot, rng_seed=rng_seed
    )

    eval_log_t, slope_med, slope_lo, slope_hi = local_slope_bootstrap(
        W_ens, hbar_ens, n_eval=n_eval, n_boot=n_boot, rng_seed=rng_seed
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
        "percentage_convention": percentage_convention,
        "model_profile": model_profile,
        "L": L,
        "n_seeds": n_seeds,
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
        plateau_mask, plateau_beta, (ci_lo, ci_hi) = plateau_result
        cell["plateau_beta"] = plateau_beta
        cell["plateau_ci"] = [ci_lo, ci_hi]
        cell["plateau_detected"] = True
        cell["plateau_mask"] = plateau_mask.tolist()
    else:
        cell["plateau_detected"] = False
        cell["plateau_mask"] = [False] * len(eval_log_t)

    # Use growth-window slope as primary β estimate for extrapolation
    cell["beta_for_extrap"] = gw_beta
    cell["beta_err_for_extrap"] = (
        (gw_hi - gw_lo) / 2.0 if not np.isnan(gw_beta) else np.nan
    )

    return cell, eval_log_t, slope_med, slope_lo, slope_hi, plateau_result


def _atomic_save_figure(fig, path, *, dpi=150):
    """Publish one diagnostic figure through a unique fsynced temporary."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        fig.savefig(temporary, dpi=dpi, format=target.suffix.lstrip("."))
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        directory = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def plot_local_slopes(
    pct,
    per_L_data,
    widths,
    out_dir,
    *,
    percentage_convention,
    model_profile,
):
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
    fraction_label = _require_percentage_convention(percentage_convention).replace("-", " ")
    model_label = _model_profile_label(model_profile)
    ax.set_title(f"Effective exponent — {model_label}, {pct}% {fraction_label}")
    ax.set_ylim(0, 0.7)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = os.path.join(out_dir, f"local_slope_pct{pct:02d}.png")
    _atomic_save_figure(fig, fname)
    plt.close(fig)
    print(f"  Saved {fname}")


def plot_extrapolation(
    pct,
    L_arr,
    beta_arr,
    err_arr,
    extrap,
    out_dir,
    *,
    percentage_convention,
    model_profile,
):
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
    fraction_label = _require_percentage_convention(percentage_convention).replace("-", " ")
    model_label = _model_profile_label(model_profile)
    ax.set_title(
        f"Multi-L extrapolation — {model_label}, {pct}% {fraction_label}"
    )
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fname = os.path.join(out_dir, f"multi_L_extrapolation_pct{pct:02d}.png")
    _atomic_save_figure(fig, fname)
    plt.close(fig)
    print(f"  Saved {fname}")


def _json_ready(value):
    """Normalize scientific values to finite built-in JSON, using null for missing fits."""

    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if type(value) is float:
        return value if math.isfinite(value) else None
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) in {list, tuple}:
        return [_json_ready(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be built-in strings")
        return {key: _json_ready(item) for key, item in value.items()}
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def _cells_dir(out_dir):
    return os.path.join(out_dir, "kpz_cells")


def _cell_path(out_dir, pct, L):
    return os.path.join(_cells_dir(out_dir), f"cell_pct{pct:02d}_L{L:04d}.json")


def _per_pct_path(out_dir, pct):
    return os.path.join(_cells_dir(out_dir), f"per_pct{pct:02d}.json")


def _atomic_write_json(path, data):
    """Write finite canonical JSON atomically (non-authoritative helper)."""

    payload = canonical_json_bytes(_json_ready(data)) + b"\n"
    atomic_write_bytes(path, payload)


def _finite_number(value, *, label, optional=False):
    if value is None and optional:
        return None
    if type(value) not in {int, float} or type(value) is bool or not math.isfinite(value):
        qualifier = "finite number or null" if optional else "finite number"
        raise AnalysisArtifactValidationError(f"{label} must be a {qualifier}")
    return float(value)


def _numeric_list(value, *, label, length, optional):
    if type(value) is not list or len(value) != length:
        raise AnalysisArtifactValidationError(f"{label} must contain exactly {length} values")
    return [
        _finite_number(item, label=f"{label}[{index}]", optional=optional)
        for index, item in enumerate(value)
    ]


def _validate_cell_payload(
    cell,
    *,
    percentage,
    L,
    n_eval,
    expected_n_seeds,
    min_seeds=2,
    percentage_convention="sticky-fraction",
    model_profile="piece-19-one-cell-v1",
):
    """Validate the strict finite schema of one trusted cache payload."""

    if type(cell) is not dict:
        raise AnalysisArtifactValidationError("analysis cell payload must be a JSON object")
    required = {
        "L",
        "analysis_point_count",
        "beta_err_for_extrap",
        "beta_for_extrap",
        "eval_log_t",
        "growth_window_beta",
        "growth_window_ci",
        "hbar_max",
        "meakin_window1",
        "meakin_window2",
        "min_trace_len",
        "model_profile",
        "n_seeds",
        "percentage",
        "percentage_convention",
        "plateau_detected",
        "plateau_mask",
        "sampling_policy",
        "saturated",
        "slope_hi",
        "slope_lo",
        "slope_med",
    }
    plateau_detected = cell.get("plateau_detected")
    if plateau_detected is True:
        required.update({"plateau_beta", "plateau_ci"})
    if set(cell) != required:
        raise AnalysisArtifactValidationError(
            "analysis cell keys differ: "
            f"missing={sorted(required - set(cell))}, unexpected={sorted(set(cell) - required)}"
        )
    if type(cell["percentage"]) is not int or cell["percentage"] != percentage:
        raise AnalysisArtifactValidationError("analysis cell percentage does not match request")
    if type(cell["L"]) is not int or cell["L"] != L:
        raise AnalysisArtifactValidationError("analysis cell width does not match request")
    expected_convention = _require_percentage_convention(percentage_convention)
    if cell["percentage_convention"] != expected_convention:
        raise AnalysisArtifactValidationError(
            "analysis cell percentage convention does not match request"
        )
    if cell["model_profile"] != _require_model_profile(model_profile):
        raise AnalysisArtifactValidationError(
            "analysis cell model profile does not match request"
        )
    if (
        type(expected_n_seeds) is not int
        or expected_n_seeds <= 0
        or type(cell["n_seeds"]) is not int
        or cell["n_seeds"] != expected_n_seeds
    ):
        raise AnalysisArtifactValidationError(
            "analysis cell n_seeds does not match the identity-bound seed inventory"
        )
    if type(min_seeds) is not int or min_seeds < 2 or cell["n_seeds"] < min_seeds:
        raise AnalysisArtifactValidationError(
            "analysis cell does not meet the requested minimum seed count"
        )
    if type(cell["min_trace_len"]) is not int or cell["min_trace_len"] < 2:
        raise AnalysisArtifactValidationError("analysis cell min_trace_len must be at least two")
    point_count = cell["analysis_point_count"]
    if (
        type(point_count) is not int
        or point_count
        != min(cell["min_trace_len"], SAMPLING_POLICY["max_points"])
    ):
        raise AnalysisArtifactValidationError(
            "analysis cell analysis_point_count disagrees with the sampling policy"
        )
    if canonical_json_bytes(cell["sampling_policy"]) != canonical_json_bytes(SAMPLING_POLICY):
        raise AnalysisArtifactValidationError("analysis cell sampling policy is not current")
    hbar_max = _finite_number(cell["hbar_max"], label="analysis cell hbar_max")
    if hbar_max < 0:
        raise AnalysisArtifactValidationError("analysis cell hbar_max cannot be negative")
    if type(cell["saturated"]) is not bool:
        raise AnalysisArtifactValidationError("analysis cell saturated must be boolean")
    if cell["saturated"] != (hbar_max >= L**1.5):
        raise AnalysisArtifactValidationError("analysis cell saturation flag is inconsistent")
    if type(plateau_detected) is not bool:
        raise AnalysisArtifactValidationError("analysis cell plateau_detected must be boolean")

    growth_beta = _finite_number(
        cell["growth_window_beta"], label="analysis cell growth_window_beta", optional=True
    )
    extrap_beta = _finite_number(
        cell["beta_for_extrap"], label="analysis cell beta_for_extrap", optional=True
    )
    beta_error = _finite_number(
        cell["beta_err_for_extrap"],
        label="analysis cell beta_err_for_extrap",
        optional=True,
    )
    if beta_error is not None and beta_error < 0:
        raise AnalysisArtifactValidationError("analysis cell extrapolation error cannot be negative")
    growth_interval = _numeric_list(
        cell["growth_window_ci"],
        label="analysis cell growth_window_ci",
        length=2,
        optional=True,
    )
    if extrap_beta != growth_beta:
        raise AnalysisArtifactValidationError(
            "analysis cell extrapolation estimate must equal growth-window estimate"
        )
    missing_interval = [item is None for item in growth_interval]
    if any(missing_interval) and not all(missing_interval):
        raise AnalysisArtifactValidationError(
            "analysis cell growth-window interval is partially missing"
        )
    finite_interval = not any(missing_interval)
    if growth_beta is None:
        if finite_interval or beta_error is not None:
            raise AnalysisArtifactValidationError(
                "missing growth-window estimate must have null interval and error"
            )
    else:
        if not finite_interval or growth_interval[0] > growth_interval[1]:
            raise AnalysisArtifactValidationError(
                "analysis cell growth-window interval is invalid"
            )
        expected_error = (growth_interval[1] - growth_interval[0]) / 2.0
        if beta_error is None or not math.isclose(
            beta_error, expected_error, rel_tol=1e-12, abs_tol=1e-15
        ):
            raise AnalysisArtifactValidationError(
                "analysis cell extrapolation error disagrees with growth-window interval"
            )
    for name in ("meakin_window1", "meakin_window2"):
        window = cell[name]
        if type(window) is not dict or set(window) != {"se", "slope"}:
            raise AnalysisArtifactValidationError(f"analysis cell {name} has invalid keys")
        _finite_number(
            window["slope"], label=f"analysis cell {name}.slope", optional=True
        )
        standard_error = _finite_number(
            window["se"], label=f"analysis cell {name}.se", optional=True
        )
        if standard_error is not None and standard_error < 0:
            raise AnalysisArtifactValidationError(f"analysis cell {name}.se cannot be negative")

    eval_log_t = _numeric_list(
        cell["eval_log_t"], label="analysis cell eval_log_t", length=n_eval, optional=False
    )
    if any(right <= left for left, right in zip(eval_log_t, eval_log_t[1:])):
        raise AnalysisArtifactValidationError("analysis cell eval_log_t must be strictly increasing")
    slope_values = {
        name: _numeric_list(
            cell[name], label=f"analysis cell {name}", length=n_eval, optional=True
        )
        for name in ("slope_med", "slope_lo", "slope_hi")
    }
    for index, (median, lower, upper) in enumerate(
        zip(slope_values["slope_med"], slope_values["slope_lo"], slope_values["slope_hi"])
    ):
        missing = (median is None, lower is None, upper is None)
        if any(missing) and not all(missing):
            raise AnalysisArtifactValidationError(
                f"analysis cell local-slope interval is partially missing at index {index}"
            )
        if not any(missing) and not lower <= median <= upper:
            raise AnalysisArtifactValidationError(
                f"analysis cell local-slope interval is unordered at index {index}"
            )
    plateau_mask = cell["plateau_mask"]
    if (
        type(plateau_mask) is not list
        or len(plateau_mask) != n_eval
        or any(type(item) is not bool for item in plateau_mask)
    ):
        raise AnalysisArtifactValidationError("analysis cell plateau_mask is invalid")
    if plateau_detected:
        if not any(plateau_mask):
            raise AnalysisArtifactValidationError("detected plateau must have a nonempty mask")
        plateau_beta = _finite_number(
            cell["plateau_beta"], label="analysis cell plateau_beta"
        )
        plateau_interval = _numeric_list(
            cell["plateau_ci"],
            label="analysis cell plateau_ci",
            length=2,
            optional=False,
        )
        if not plateau_interval[0] <= plateau_beta <= plateau_interval[1]:
            raise AnalysisArtifactValidationError(
                "analysis cell plateau estimate is outside its interval"
            )
    elif any(plateau_mask):
        raise AnalysisArtifactValidationError("undetected plateau must have an empty mask")
    return cell


def _estimator_settings(n_boot, n_eval, min_seeds=10):
    if type(n_boot) is not int or n_boot <= 0:
        raise ValueError("n_boot must be a positive built-in integer")
    if type(n_eval) is not int or n_eval < 2:
        raise ValueError("n_eval must be a built-in integer of at least two")
    if type(min_seeds) is not int or min_seeds < 2:
        raise ValueError("min_seeds must be a built-in integer of at least two")
    return {
        "growth_window": {
            "ci_level": 0.95,
            "hbar_hi": "0.5*L**1.5",
            "hbar_lo": 10.0,
            "minimum_points": 5,
        },
        "local_slope": {"ci_level": 0.95, "log_half_width": 0.5},
        "meakin_windows": [[0.01, 0.1], [0.1, 1.0]],
        "min_seeds": min_seeds,
        "n_boot": n_boot,
        "n_eval": n_eval,
        "plateau": {
            "ci_width_thresh": 0.25,
            "deriv_thresh": 0.08,
            "log_hbar_hi": "log10(0.5*L**1.5)",
            "log_hbar_lo": "log10(10)",
            "min_log_extent": 0.3,
        },
        "profile": ESTIMATOR_PROFILE,
        "sampling": dict(SAMPLING_POLICY),
        "saturation_threshold": "hbar_max>=L**1.5",
    }


def _production_estimator_settings(n_boot, n_eval, min_seeds=10):
    """Validate settings allowed to publish through the managed CLI."""

    settings = _estimator_settings(n_boot, n_eval, min_seeds)
    if n_boot < MIN_PRODUCTION_BOOTSTRAPS:
        raise ValueError(
            f"production analysis requires at least {MIN_PRODUCTION_BOOTSTRAPS} "
            "bootstrap replicates"
        )
    if min_seeds < MIN_PRODUCTION_SEEDS:
        raise ValueError(
            f"production analysis requires at least {MIN_PRODUCTION_SEEDS} "
            "independent runs per ensemble"
        )
    return settings


def _require_percentage_convention(value):
    if type(value) is not str or value not in PERCENTAGE_CONVENTIONS:
        choices = ", ".join(PERCENTAGE_CONVENTIONS)
        raise ValueError(f"percentage_convention must be one of: {choices}")
    return value


def _require_model_profile(value):
    if type(value) is not str or value not in MODEL_PROFILES:
        choices = ", ".join(MODEL_PROFILES)
        raise ValueError(f"model_profile must be one of: {choices}")
    return value


def _model_profile_label(value):
    profile = _require_model_profile(value)
    if profile == "piece-19-one-cell-v1":
        return "Piece-19 one-cell"
    raise AssertionError(f"missing display label for model profile {profile}")


def _rng_settings(rng_seed):
    if type(rng_seed) is not int or not 0 <= rng_seed <= 2**32 - 1:
        raise ValueError("rng_seed must be a built-in integer in [0, 2**32 - 1]")
    return {
        **ANALYSIS_RNG_POLICY,
        "growth_window_seed": rng_seed,
        "local_slope_seed": rng_seed,
        "root_seed": rng_seed,
    }


def _selected_input_identity(selected):
    content = fingerprint_regular_files(selected.paths, root=selected.root)
    return build_identity(
        CELL_INPUT_PROFILE,
        {
            "content": content,
            "layout": selected.layout,
            "seed_inventory": list(selected.seeds),
        },
    )


def _cell_identity(
    trace_root,
    pct,
    L,
    *,
    input_layout,
    n_boot,
    n_eval,
    rng_seed,
    min_seeds=10,
    percentage_convention="sticky-fraction",
    model_profile="piece-19-one-cell-v1",
    software=None,
    resolved_input=None,
    input_identity=None,
):
    selected = resolved_input or resolve_ensemble_input(
        trace_root, pct, L, input_layout=input_layout
    )
    current_inputs = input_identity or _selected_input_identity(selected)
    return build_analysis_identity(
        artifact_kind="kpz-slope-cell",
        context={
            "L": L,
            "input_layout": input_layout,
            "percentage": pct,
            "percentage_convention": _require_percentage_convention(
                percentage_convention
            ),
            "model_profile": _require_model_profile(model_profile),
        },
        inputs=current_inputs,
        rng=_rng_settings(rng_seed),
        settings=_estimator_settings(n_boot, n_eval, min_seeds),
        software=software,
    )


_analysis_identity = _cell_identity


def _load_cached_cell(path, expected_identity):
    cell = load_json_artifact(path, expected_identity)
    try:
        record = expected_identity["record"]
        context = record["context"]
        settings = record["settings"]["record"]
        seed_inventory = record["inputs"]["record"]["seed_inventory"]
    except (KeyError, TypeError) as error:
        raise AnalysisArtifactValidationError(
            "analysis cell identity lacks the managed seed inventory"
        ) from error
    if (
        type(seed_inventory) is not list
        or not seed_inventory
        or any(type(seed) is not int for seed in seed_inventory)
        or seed_inventory != sorted(seed_inventory)
        or len(seed_inventory) != len(set(seed_inventory))
    ):
        raise AnalysisArtifactValidationError(
            "analysis cell identity has an invalid managed seed inventory"
        )
    return _validate_cell_payload(
        cell,
        percentage=context["percentage"],
        L=context["L"],
        n_eval=settings["n_eval"],
        expected_n_seeds=len(seed_inventory),
        min_seeds=settings["min_seeds"],
        percentage_convention=context["percentage_convention"],
        model_profile=context["model_profile"],
    )


def _artifact_payload_or_manifest_exists(path):
    paths = analysis_artifact_paths(path)
    return os.path.lexists(paths.payload) or os.path.lexists(paths.manifest)


def _compute_or_load_cell(
    *,
    trace_root,
    out_dir,
    pct,
    L,
    input_layout,
    n_boot,
    n_eval,
    rng_seed,
    min_seeds,
    percentage_convention,
    model_profile,
    software,
    selected,
    resume,
    replace,
    aggregate_only,
):
    path = _cell_path(out_dir, pct, L)
    with analysis_artifact_lock(path):
        current_selected = resolve_ensemble_input(
            trace_root, pct, L, input_layout=input_layout
        )
        if current_selected != selected:
            raise AnalysisArtifactValidationError(
                f"analysis input inventory changed after preflight for pct={pct}, L={L}"
            )
        input_before = _selected_input_identity(selected)
        identity = _cell_identity(
            trace_root,
            pct,
            L,
            input_layout=input_layout,
            n_boot=n_boot,
            n_eval=n_eval,
            rng_seed=rng_seed,
            min_seeds=min_seeds,
            percentage_convention=percentage_convention,
            model_profile=model_profile,
            software=software,
            resolved_input=selected,
            input_identity=input_before,
        )
        exists = _artifact_payload_or_manifest_exists(path)
        if aggregate_only or (resume and exists):
            try:
                cell = _load_cached_cell(path, identity)
            except AnalysisArtifactValidationError as error:
                raise AnalysisArtifactValidationError(
                    f"cached cell pct={pct}, L={L} is not reusable; "
                    "review it and rerun with --replace to regenerate"
                ) from error
            input_after = _selected_input_identity(selected)
            if (
                resolve_ensemble_input(
                    trace_root, pct, L, input_layout=input_layout
                )
                != selected
                or canonical_json_bytes(input_after) != canonical_json_bytes(input_before)
            ):
                raise AnalysisArtifactValidationError(
                    f"analysis input changed during cache validation for pct={pct}, L={L}"
                )
            return cell, identity, True
        if aggregate_only:
            raise AnalysisArtifactValidationError(
                f"aggregate-only requires a complete cached cell for pct={pct}, L={L}"
            )
        if exists and not replace:
            raise AnalysisArtifactValidationError(
                f"analysis output already exists for pct={pct}, L={L}; "
                "use --resume to validate/reuse it or --replace to regenerate it"
            )

        cell, eval_log_t, slope_med, slope_lo, slope_hi, _plateau = run_single_cell(
            trace_root,
            pct,
            L,
            n_eval=n_eval,
            n_boot=n_boot,
            min_seeds=min_seeds,
            rng_seed=rng_seed,
            input_layout=input_layout,
            percentage_convention=percentage_convention,
            model_profile=model_profile,
            resolved_input=selected,
        )
        cell["eval_log_t"] = eval_log_t.tolist()
        cell["slope_med"] = slope_med.tolist()
        cell["slope_lo"] = slope_lo.tolist()
        cell["slope_hi"] = slope_hi.tolist()
        cell = _json_ready(cell)
        _validate_cell_payload(
            cell,
            percentage=pct,
            L=L,
            n_eval=n_eval,
            expected_n_seeds=len(selected.seeds),
            min_seeds=min_seeds,
            percentage_convention=percentage_convention,
            model_profile=model_profile,
        )
        input_after = _selected_input_identity(selected)
        final_selected = resolve_ensemble_input(
            trace_root, pct, L, input_layout=input_layout
        )
        if (
            final_selected != selected
            or canonical_json_bytes(input_after) != canonical_json_bytes(input_before)
        ):
            raise AnalysisArtifactValidationError(
                f"analysis input changed during computation for pct={pct}, L={L}"
            )
        write_json_artifact(path, cell, identity, lock_held=True)
        return _load_cached_cell(path, identity), identity, False


def _valid_estimate(value):
    return type(value) in {int, float} and type(value) is not bool and math.isfinite(value)


def _summarize_percentage(
    pct, widths, cells, percentage_convention, model_profile
):
    convention = _require_percentage_convention(percentage_convention)
    model = _require_model_profile(model_profile)
    cells_for_pct = {str(L): cells[(pct, L)] for L in widths}
    saturated_widths = [L for L in widths if _is_saturated(cells[(pct, L)], L)]
    usable = [
        (
            L,
            float(cells[(pct, L)]["beta_for_extrap"]),
            float(cells[(pct, L)]["beta_err_for_extrap"]),
        )
        for L in saturated_widths
        if _valid_estimate(cells[(pct, L)]["beta_for_extrap"])
        and _valid_estimate(cells[(pct, L)]["beta_err_for_extrap"])
        and cells[(pct, L)]["beta_err_for_extrap"] >= 0
    ]
    saturated_betas = [
        float(cells[(pct, L)]["growth_window_beta"])
        for L in saturated_widths
        if _valid_estimate(cells[(pct, L)]["growth_window_beta"])
    ]
    mean_beta = float(np.mean(saturated_betas)) if saturated_betas else None
    std_beta = (
        float(np.std(saturated_betas, ddof=1)) if len(saturated_betas) > 1 else None
    )
    per_pct = {
        "cells": cells_for_pct,
        "n_saturated_L": len(saturated_widths),
        "model_profile": model,
        "pct": pct,
        "percentage_convention": convention,
        "saturated_mean_beta": mean_beta,
        "saturated_std_beta": std_beta,
    }
    extrap = None
    if len(usable) >= 2:
        L_arr = np.asarray([item[0] for item in usable], dtype=float)
        beta_arr = np.asarray([item[1] for item in usable], dtype=float)
        error_arr = np.asarray([item[2] for item in usable], dtype=float)
        extrap = extrapolate_to_infinity(L_arr, beta_arr, error_arr)
        beta_inf, beta_inf_err, popt, _pcov = extrap
        extrapolation = {
            "beta_inf": beta_inf,
            "beta_inf_err": beta_inf_err,
            "fit_converged": popt is not None,
            "n_L_used": len(usable),
        }
        if popt is not None:
            extrapolation.update({"c": float(popt[1]), "omega": float(popt[2])})
        per_pct["extrapolation"] = extrapolation
    else:
        per_pct["extrapolation"] = {
            "beta_inf": None,
            "beta_inf_err": None,
            "fit_converged": False,
            "n_L_used": len(usable),
            "note": "insufficient finite saturated widths for extrapolation; "
            "report saturated_mean_beta instead",
        }
    return _json_ready(per_pct), usable, extrap


def aggregate_results(out_dir, percentages, widths, expected_cell_identities):
    """Aggregate exactly the requested identity-validated cell grid."""

    if type(percentages) not in {list, tuple} or not percentages:
        raise ValueError("percentages must be a nonempty built-in list or tuple")
    if type(widths) not in {list, tuple} or not widths:
        raise ValueError("widths must be a nonempty built-in list or tuple")
    if (
        any(type(pct) is not int or not 0 <= pct <= 100 for pct in percentages)
        or len(set(percentages)) != len(percentages)
    ):
        raise ValueError("percentages must be unique built-in integers in [0, 100]")
    if (
        any(type(L) is not int or L <= 0 for L in widths)
        or len(set(widths)) != len(widths)
    ):
        raise ValueError("widths must be unique positive built-in integers")
    if type(expected_cell_identities) is not dict:
        raise ValueError("expected_cell_identities must be a built-in mapping")
    expected_keys = {(pct, L) for pct in percentages for L in widths}
    if set(expected_cell_identities) != expected_keys:
        raise ValueError("expected cell identities do not match the requested closed grid")
    cells = {}
    conventions = set()
    model_profiles = set()
    for key in sorted(expected_keys):
        pct, L = key
        identity = expected_cell_identities[key]
        try:
            context = identity["record"]["context"]
        except (KeyError, TypeError) as error:
            raise ValueError(f"cell identity for grid coordinate {key} is malformed") from error
        if (
            type(context) is not dict
            or context.get("percentage") != pct
            or context.get("L") != L
            or type(context.get("percentage")) is not int
            or type(context.get("L")) is not int
        ):
            raise ValueError(f"cell identity context disagrees with grid coordinate {key}")
        convention = context.get("percentage_convention")
        try:
            conventions.add(_require_percentage_convention(convention))
        except ValueError as error:
            raise ValueError(
                f"cell identity percentage convention is invalid for grid coordinate {key}"
            ) from error
        try:
            model_profiles.add(_require_model_profile(context.get("model_profile")))
        except ValueError as error:
            raise ValueError(
                f"cell identity model profile is invalid for grid coordinate {key}"
            ) from error
        path = _cell_path(out_dir, pct, L)
        with analysis_artifact_lock(path):
            cells[key] = _load_cached_cell(path, identity)
    if len(conventions) != 1:
        raise ValueError("cell identities mix percentage conventions")
    if len(model_profiles) != 1:
        raise ValueError("cell identities mix model profiles")
    percentage_convention = next(iter(conventions))
    model_profile = next(iter(model_profiles))
    return {
        str(pct): _summarize_percentage(
            pct, widths, cells, percentage_convention, model_profile
        )[0]
        for pct in percentages
    }


def _lock_artifacts(stack, paths):
    unique_paths = sorted(set(paths), key=lambda path: os.fspath(path))
    if len(unique_paths) != len(paths):
        raise ValueError("derived artifact dependency paths must be unique")
    for path in unique_paths:
        stack.enter_context(analysis_artifact_lock(path))


def _dependency_record(out_dir, *, context, path, identity, cell):
    """Validate and fingerprint one dependency while its lock is held."""

    payload = (
        _load_cached_cell(path, identity)
        if cell
        else load_json_artifact(path, identity)
    )
    paths = analysis_artifact_paths(path)
    record = {
        "artifact": fingerprint_regular_file(paths.payload, root=out_dir),
        "context": context,
        "identity_sha256": identity["sha256"],
        "manifest": fingerprint_regular_file(paths.manifest, root=out_dir),
    }
    return payload, record


def _derived_input_identity(records):
    return build_identity(DERIVED_INPUT_PROFILE, {"children": records})


def _derived_identity(*, kind, context, inputs, software):
    return build_analysis_identity(
        artifact_kind=kind,
        context=context,
        inputs=inputs,
        rng={"policy": "no-random-draws"},
        settings={"profile": DERIVATION_PROFILE},
        software=software,
    )


def _publish_derived_results(
    *,
    out_dir,
    percentages,
    widths,
    percentage_convention,
    model_profile,
    results,
    cell_identities,
    software,
):
    convention = _require_percentage_convention(percentage_convention)
    model = _require_model_profile(model_profile)
    per_pct_identities = {}
    cell_paths = [
        _cell_path(out_dir, pct, L) for pct in percentages for L in widths
    ]
    with ExitStack() as stack:
        _lock_artifacts(stack, cell_paths)
        for pct in percentages:
            records = []
            for L in widths:
                path = _cell_path(out_dir, pct, L)
                payload, record = _dependency_record(
                    out_dir,
                    context={"L": L, "percentage": pct},
                    path=path,
                    identity=cell_identities[(pct, L)],
                    cell=True,
                )
                if canonical_json_bytes(payload) != canonical_json_bytes(
                    results[str(pct)]["cells"][str(L)]
                ):
                    raise AnalysisArtifactValidationError(
                        f"percentage summary input changed for pct={pct}, L={L}"
                    )
                records.append(record)
            identity = _derived_identity(
                kind="kpz-percentage-summary",
                context={
                    "percentage": pct,
                    "percentage_convention": convention,
                    "model_profile": model,
                    "widths": widths,
                },
                inputs=_derived_input_identity(records),
                software=software,
            )
            write_json_artifact(
                _per_pct_path(out_dir, pct), results[str(pct)], identity
            )
            per_pct_identities[pct] = identity

    per_pct_paths = [_per_pct_path(out_dir, pct) for pct in percentages]
    results_path = os.path.join(out_dir, "results.json")
    with ExitStack() as stack:
        _lock_artifacts(stack, per_pct_paths)
        records = []
        for pct in percentages:
            payload, record = _dependency_record(
                out_dir,
                context={"percentage": pct},
                path=_per_pct_path(out_dir, pct),
                identity=per_pct_identities[pct],
                cell=False,
            )
            if canonical_json_bytes(payload) != canonical_json_bytes(results[str(pct)]):
                raise AnalysisArtifactValidationError(
                    f"grid summary input changed for pct={pct}"
                )
            records.append(record)
        results_identity = _derived_identity(
            kind="kpz-grid-summary",
            context={
                "percentage_convention": convention,
                "model_profile": model,
                "percentages": percentages,
                "widths": widths,
            },
            inputs=_derived_input_identity(records),
            software=software,
        )
        write_json_artifact(results_path, results, results_identity)
    return results_path, per_pct_identities, results_identity


def load_current_results(
    *,
    out_dir,
    percentages,
    widths,
    percentage_convention,
    model_profile,
    cell_identities,
    software,
):
    """Load results only after recomputing the complete dependency snapshot."""

    convention = _require_percentage_convention(percentage_convention)
    model = _require_model_profile(model_profile)
    expected_keys = {(pct, L) for pct in percentages for L in widths}
    if set(cell_identities) != expected_keys:
        raise ValueError("cell identities do not match the requested results grid")
    cell_paths = [_cell_path(out_dir, *key) for key in sorted(expected_keys)]
    per_pct_paths = [_per_pct_path(out_dir, pct) for pct in percentages]
    results_path = os.path.join(out_dir, "results.json")
    with ExitStack() as stack:
        _lock_artifacts(stack, cell_paths + per_pct_paths + [results_path])
        cells = {}
        cell_records = {}
        for pct, L in sorted(expected_keys):
            payload, record = _dependency_record(
                out_dir,
                context={"L": L, "percentage": pct},
                path=_cell_path(out_dir, pct, L),
                identity=cell_identities[(pct, L)],
                cell=True,
            )
            cells[(pct, L)] = payload
            cell_records[(pct, L)] = record

        expected_results = {
            str(pct): _summarize_percentage(
                pct, widths, cells, convention, model
            )[0]
            for pct in percentages
        }
        per_pct_identities = {}
        per_pct_records = []
        for pct in percentages:
            identity = _derived_identity(
                kind="kpz-percentage-summary",
                context={
                    "percentage": pct,
                    "percentage_convention": convention,
                    "model_profile": model,
                    "widths": widths,
                },
                inputs=_derived_input_identity(
                    [cell_records[(pct, L)] for L in widths]
                ),
                software=software,
            )
            payload, record = _dependency_record(
                out_dir,
                context={"percentage": pct},
                path=_per_pct_path(out_dir, pct),
                identity=identity,
                cell=False,
            )
            if canonical_json_bytes(payload) != canonical_json_bytes(
                expected_results[str(pct)]
            ):
                raise AnalysisArtifactValidationError(
                    f"percentage summary is not current for pct={pct}"
                )
            per_pct_identities[pct] = identity
            per_pct_records.append(record)

        results_identity = _derived_identity(
            kind="kpz-grid-summary",
            context={
                "percentage_convention": convention,
                "model_profile": model,
                "percentages": percentages,
                "widths": widths,
            },
            inputs=_derived_input_identity(per_pct_records),
            software=software,
        )
        payload = load_json_artifact(results_path, results_identity)
        if canonical_json_bytes(payload) != canonical_json_bytes(expected_results):
            raise AnalysisArtifactValidationError("grid summary payload is not current")
        return payload


def _plot_data_from_cell(cell):
    eval_log_t = np.asarray(cell["eval_log_t"], dtype=float)
    slope_med = np.asarray(cell["slope_med"], dtype=float)
    slope_lo = np.asarray(cell["slope_lo"], dtype=float)
    slope_hi = np.asarray(cell["slope_hi"], dtype=float)
    plateau = None
    if cell["plateau_detected"]:
        plateau = (
            np.asarray(cell["plateau_mask"], dtype=bool),
            cell["plateau_beta"],
            tuple(cell["plateau_ci"]),
        )
    return eval_log_t, slope_med, slope_lo, slope_hi, plateau


def _parse_axis(raw, *, label, minimum, maximum=None):
    if type(raw) is not str:
        raise ValueError(f"{label} must be a comma-separated integer list")
    parts = raw.split(",")
    if any(not item.strip() for item in parts):
        raise ValueError(f"{label} cannot contain empty entries")
    try:
        values = [int(item.strip()) for item in parts]
    except ValueError as error:
        raise ValueError(f"{label} must be a comma-separated integer list") from error
    if not values:
        raise ValueError(f"{label} cannot be empty")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} cannot contain duplicates")
    if any(value < minimum or (maximum is not None and value > maximum) for value in values):
        bounds = f"[{minimum}, {maximum}]" if maximum is not None else f">={minimum}"
        raise ValueError(f"{label} values must be in {bounds}")
    return values


def _withdraw_derived_outputs(out_dir, percentages):
    """Withdraw commit markers and diagnostics before a fallible generation."""

    invalidate_json_artifact(os.path.join(out_dir, "results.json"))
    for pct in percentages:
        invalidate_json_artifact(_per_pct_path(out_dir, pct))
        for name in (
            f"local_slope_pct{pct:02d}.png",
            f"multi_L_extrapolation_pct{pct:02d}.png",
        ):
            path = Path(out_dir) / name
            if not os.path.lexists(path):
                continue
            if stat.S_ISDIR(path.lstat().st_mode):
                raise AnalysisArtifactValidationError(
                    f"derived diagnostic path is a directory: {path}"
                )
            path.unlink()
    directory = os.open(out_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--trace-root", help="Root of the declared input layout")
    source.add_argument("--exp-dir", help="Deprecated alias for --trace-root")
    parser.add_argument(
        "--input-layout",
        required=True,
        choices=sorted(SUPPORTED_INPUT_LAYOUTS),
        help="Input contract; managed raw outputs must first be reduced",
    )
    parser.add_argument(
        "--percentage-convention",
        required=True,
        choices=PERCENTAGE_CONVENTIONS,
        help="Scientific meaning of each percentage label",
    )
    parser.add_argument(
        "--model-profile",
        required=True,
        choices=MODEL_PROFILES,
        help="Executable model identity represented by the traces",
    )
    parser.add_argument("--out-dir", required=True, help="Analysis artifact directory")
    parser.add_argument(
        "--pcts", default="5,50,90,95,98,99",
        help="Comma-separated percentages (default: 5,50,90,95,98,99)",
    )
    parser.add_argument(
        "--widths", default="50,80,100,150,200",
        help="Comma-separated strip widths (default: 50,80,100,150,200)",
    )
    parser.add_argument(
        "--n-boot",
        type=int,
        default=MIN_PRODUCTION_BOOTSTRAPS,
        help=(
            "Bootstrap replicates; managed production output requires at least "
            f"{MIN_PRODUCTION_BOOTSTRAPS}"
        ),
    )
    parser.add_argument(
        "--n-eval", type=int, default=150, help="Log-spaced evaluation points"
    )
    parser.add_argument(
        "--rng-seed", type=int, default=42, help="Bootstrap root seed (default: 42)"
    )
    parser.add_argument(
        "--min-seeds",
        type=int,
        default=MIN_PRODUCTION_SEEDS,
        help=(
            "Minimum independent runs per ensemble; managed production output "
            f"requires at least {MIN_PRODUCTION_SEEDS}"
        ),
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only exact identity-validated cells; stale/corrupt cells are fatal",
    )
    action.add_argument(
        "--replace",
        action="store_true",
        help="Explicitly replace existing cells with the current request",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Require and aggregate the exact requested set of valid cached cells",
    )
    args = parser.parse_args()

    if args.aggregate_only and (args.resume or args.replace):
        parser.error("--aggregate-only cannot be combined with --resume or --replace")
    trace_root = os.path.abspath(args.trace_root or args.exp_dir)
    out_dir = os.path.abspath(args.out_dir)
    if args.exp_dir:
        print("warning: --exp-dir is deprecated; use --trace-root", file=sys.stderr)
    if not os.path.isdir(trace_root):
        parser.error(f"trace root not found: {trace_root}")
    try:
        percentages = _parse_axis(args.pcts, label="pcts", minimum=0, maximum=100)
        widths = _parse_axis(args.widths, label="widths", minimum=1)
        _production_estimator_settings(args.n_boot, args.n_eval, args.min_seeds)
        _rng_settings(args.rng_seed)
        _require_percentage_convention(args.percentage_convention)
        _require_model_profile(args.model_profile)
        selected = {
            (pct, L): resolve_ensemble_input(
                trace_root, pct, L, input_layout=args.input_layout
            )
            for pct in percentages
            for L in widths
        }
    except ValueError as error:
        parser.error(str(error))
    os.makedirs(_cells_dir(out_dir), exist_ok=True)
    software = analysis_software_identity()

    print("=" * 60)
    print(f"KPZ Slope Extraction — {trace_root}")
    print(
        f"Input layout: {args.input_layout}; percentage: "
        f"{args.percentage_convention}; model: {args.model_profile}; output: {out_dir}"
    )
    if args.resume:
        print("(--resume: exact input/settings/software/RNG identity required)")
    if args.replace:
        print("(--replace: explicitly replacing managed cells)")
    if args.aggregate_only:
        print("(--aggregate-only: validating the exact requested cache grid)")
    print("=" * 60)

    cells = {}
    cell_identities = {}
    run_stack = ExitStack()
    try:
        run_stack.enter_context(
            analysis_artifact_lock(os.path.join(out_dir, "analysis_generation.json"))
        )
        _withdraw_derived_outputs(out_dir, percentages)
        for pct in percentages:
            print(f"\n--- Percentage = {pct}% ---")
            for L in widths:
                print(f"  L={L}: validating input/cache...", end=" ", flush=True)
                cell, identity, reused = _compute_or_load_cell(
                    trace_root=trace_root,
                    out_dir=out_dir,
                    pct=pct,
                    L=L,
                    input_layout=args.input_layout,
                    n_boot=args.n_boot,
                    n_eval=args.n_eval,
                    rng_seed=args.rng_seed,
                    min_seeds=args.min_seeds,
                    percentage_convention=args.percentage_convention,
                    model_profile=args.model_profile,
                    software=software,
                    selected=selected[(pct, L)],
                    resume=args.resume,
                    replace=args.replace,
                    aggregate_only=args.aggregate_only,
                )
                cells[(pct, L)] = cell
                cell_identities[(pct, L)] = identity
                if reused:
                    print("reused exact managed artifact")
                else:
                    beta = cell["growth_window_beta"]
                    interval = cell["growth_window_ci"]
                    plateau = " + plateau" if cell["plateau_detected"] else ""
                    if beta is None:
                        print("computed; growth-window estimate unavailable")
                    else:
                        print(
                            f"computed β̂={beta:.4f} "
                            f"[{interval[0]:.4f}, {interval[1]:.4f}]{plateau}"
                        )

        all_results = aggregate_results(
            out_dir, percentages, widths, cell_identities
        )
        for pct in percentages:
            per_L_data = {
                L: _plot_data_from_cell(cells[(pct, L)]) for L in widths
            }
            plot_local_slopes(
                pct,
                per_L_data,
                widths,
                out_dir,
                percentage_convention=args.percentage_convention,
                model_profile=args.model_profile,
            )
            _per_pct, usable, extrap = _summarize_percentage(
                pct,
                widths,
                cells,
                args.percentage_convention,
                args.model_profile,
            )
            if len(usable) >= 2 and extrap is not None:
                plot_extrapolation(
                    pct,
                    np.asarray([item[0] for item in usable], dtype=float),
                    np.asarray([item[1] for item in usable], dtype=float),
                    np.asarray([item[2] for item in usable], dtype=float),
                    extrap,
                    out_dir,
                    percentage_convention=args.percentage_convention,
                    model_profile=args.model_profile,
                )
        results_path, _per_pct_identities, _results_identity = _publish_derived_results(
            out_dir=out_dir,
            percentages=percentages,
            widths=widths,
            percentage_convention=args.percentage_convention,
            model_profile=args.model_profile,
            results=all_results,
            cell_identities=cell_identities,
            software=software,
        )
        all_results = load_current_results(
            out_dir=out_dir,
            percentages=percentages,
            widths=widths,
            percentage_convention=args.percentage_convention,
            model_profile=args.model_profile,
            cell_identities=cell_identities,
            software=software,
        )
    except (AnalysisArtifactValidationError, ValueError, OSError) as error:
        try:
            _withdraw_derived_outputs(out_dir, percentages)
        except (AnalysisArtifactValidationError, OSError) as cleanup_error:
            sys.exit(
                "analysis failed closed and derived-output withdrawal also failed: "
                f"{error}; cleanup error: {cleanup_error}"
            )
        sys.exit(f"analysis failed closed: {error}")
    finally:
        run_stack.close()

    print(f"\nResults written to {results_path} with a validating manifest")
    print("\n" + "=" * 60)
    print(
        "SUMMARY — β vs "
        f"{args.percentage_convention.replace('-', ' ')} (KPZ↔EW crossover)"
    )
    print("  KPZ β=1/3≈0.333   EW β=1/4=0.250   (measured on log h̄ axis)")
    print("=" * 60)
    for pct in percentages:
        pdata = all_results[str(pct)]
        mean_beta = pdata["saturated_mean_beta"]
        count = pdata["n_saturated_L"]
        beta_inf = pdata["extrapolation"]["beta_inf"]
        if mean_beta is None:
            classification = "—"
            mean_text = "n/a"
        else:
            classification = (
                "KPZ" if 0.30 <= mean_beta <= 0.36
                else "EW" if 0.22 <= mean_beta < 0.30
                else "—"
            )
            mean_text = f"{mean_beta:.3f}"
        infinity_text = f"β∞={beta_inf:.3f}" if beta_inf is not None else "β∞=n/a"
        print(
            f"  pct={pct:2d}%: saturated-mean β = {mean_text} "
            f"({count} sat. L)  [{classification}]   {infinity_text}"
        )


if __name__ == "__main__":
    main()
