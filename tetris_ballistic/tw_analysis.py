"""Tracy--Widom moment diagnostics for timestamped growth interfaces.

The routines here test only the GOE Tracy--Widom one-point moment fingerprint;
matching two moments is not, by itself, proof of KPZ universality.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import kurtosis, skew

GOE_SKEWNESS = 0.2935
GOE_EXCESS_KURTOSIS = 0.1652
DEFAULT_Q_VALUES = (0.15, 0.25, 0.40)
EXP14_SEEDS = tuple(range(0, 1000, 10))
PERCENTAGE_SEMANTICS = "sticky_fraction_pct"
DENSITY_CONVENTION = "Piece-19=[100-pct,pct]=[nonsticky,sticky]"


def select_target_times(hbar, L, q_values=DEFAULT_Q_VALUES, hbar_floor=10.0):
    """Select common deposition counts from corrected ensemble height traces.

    For each ``q``, selects the largest trace index ``i`` for which the
    ensemble mean height is at most ``q * L**(3/2)``.  Deposition timestamps in
    substrates are one-based, hence the returned count is ``i + 1``.
    """
    hbar = np.asarray(hbar)
    if hbar.ndim != 2 or hbar.shape[0] == 0 or hbar.shape[1] == 0:
        raise ValueError("hbar must be a non-empty (n_seeds, n_steps) array")
    if L <= 0:
        raise ValueError("L must be positive")
    if not np.all(np.isfinite(hbar)):
        raise ValueError("hbar contains nonfinite values")

    mean_hbar = np.mean(hbar, axis=0, dtype=np.float64)
    if np.any(np.diff(mean_hbar) < -1e-6):
        raise ValueError("ensemble mean hbar must be monotone nondecreasing")
    indices, counts, targets = [], [], []
    for q in np.asarray(q_values, dtype=np.float64):
        if not (0.0 < q < 1.0):
            raise ValueError("q values must lie strictly between zero and one")
        threshold = float(q * L ** 1.5)
        eligible = np.flatnonzero(mean_hbar <= threshold)
        if eligible.size == 0:
            raise ValueError(f"no trace point at or below q={q:g} target")
        index = int(eligible[-1])
        target = float(mean_hbar[index])
        if target < hbar_floor:
            raise ValueError(
                f"q={q:g} target mean height {target:.6g} is below {hbar_floor:g}"
            )
        indices.append(index)
        counts.append(index + 1)
        targets.append(target)
    return (
        np.asarray(indices, dtype=np.int64),
        np.asarray(counts, dtype=np.int64),
        np.asarray(targets, dtype=np.float64),
    )


def reconstruct_interface(substrate, deposition_count):
    """Reconstruct physical column heights at a common deposition count.

    This exactly follows ``Tetris_Ballistic._TopEnvelop``: the envelope row is
    one above the top occupied row and is ``H-1`` for an empty column.  The
    physical-height orientation is ``H - envelope_row`` and therefore has the
    positive-skew sign used for the GOE reference values.
    """
    substrate = np.asarray(substrate)
    if substrate.ndim != 2:
        raise ValueError("substrate must be a two-dimensional array")
    if deposition_count < 1:
        raise ValueError("deposition_count must be positive")
    height, width = substrate.shape
    if height == 0 or width == 0:
        raise ValueError("substrate must have nonzero dimensions")

    occupied = (substrate > 0) & (substrate <= deposition_count)
    nonempty = np.any(occupied, axis=0)
    top_rows = np.argmax(occupied, axis=0).astype(np.int64)
    envelope_rows = np.where(nonempty, top_rows - 1, height - 1)
    physical_heights = height - envelope_rows
    return physical_heights.astype(np.int32, copy=False)


def validate_interface(
    interface,
    expected_hbar,
    expected_fluctuation,
    *,
    atol=1e-3,
    rtol=2e-6,
):
    """Validate reconstructed mean and population width against trace values."""
    interface = np.asarray(interface, dtype=np.float64)
    if interface.ndim != 1 or interface.size == 0:
        raise ValueError("interface must be a non-empty one-dimensional array")
    actual_hbar = float(np.mean(interface))
    actual_fluctuation = float(np.std(interface, ddof=0))
    mean_ok = np.isclose(actual_hbar, expected_hbar, atol=atol, rtol=rtol)
    width_ok = np.isclose(
        actual_fluctuation, expected_fluctuation, atol=atol, rtol=rtol
    )
    if not mean_ok or not width_ok:
        raise ValueError(
            "interface validation failed: "
            f"mean={actual_hbar:.9g} expected={expected_hbar:.9g}; "
            f"std={actual_fluctuation:.9g} expected={expected_fluctuation:.9g}; "
            f"atol={atol:g}, rtol={rtol:g}"
        )
    return {
        "mean": actual_hbar,
        "population_std": actual_fluctuation,
        "mean_abs_error": abs(actual_hbar - float(expected_hbar)),
        "std_abs_error": abs(actual_fluctuation - float(expected_fluctuation)),
    }


def sample_moments(values):
    """Return bias-corrected skewness and Fisher excess kurtosis."""
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if values.size < 4:
        raise ValueError("at least four observations are required")
    return float(skew(values, bias=False)), float(
        kurtosis(values, fisher=True, bias=False)
    )


def seed_block_indices(n_seeds, n_boot, rng_seed):
    """Draw bootstrap indices that resample complete seed rows."""
    if n_seeds < 2:
        raise ValueError("at least two seed blocks are required")
    if n_boot < 1:
        raise ValueError("n_boot must be positive")
    rng = np.random.default_rng(rng_seed)
    return rng.integers(0, n_seeds, size=(n_boot, n_seeds))


def bootstrap_seed_block_moments(interfaces, n_boot=2000, rng_seed=42):
    """Estimate moment uncertainty by resampling whole seed interfaces only."""
    interfaces = np.asarray(interfaces)
    if interfaces.ndim != 2 or interfaces.shape[1] == 0:
        raise ValueError("interfaces must have shape (n_seeds, L)")
    if n_boot < 2000:
        raise ValueError("Tracy--Widom analysis requires at least 2000 bootstraps")

    point_skew, point_kurt = sample_moments(interfaces.reshape(-1))
    draws = seed_block_indices(interfaces.shape[0], n_boot, rng_seed)
    boot = np.empty((n_boot, 2), dtype=np.float64)
    for b, indices in enumerate(draws):
        boot[b] = sample_moments(interfaces[indices].reshape(-1))

    ci95 = np.percentile(boot, [2.5, 97.5], axis=0)
    ci99 = np.percentile(boot, [0.5, 99.5], axis=0)
    covariance = np.cov(boot, rowvar=False, ddof=1)
    return {
        "skewness": point_skew,
        "excess_kurtosis": point_kurt,
        "ci95": {
            "skewness": ci95[:, 0].tolist(),
            "excess_kurtosis": ci95[:, 1].tolist(),
        },
        "ci99": {
            "skewness": ci99[:, 0].tolist(),
            "excess_kurtosis": ci99[:, 1].tolist(),
        },
        "bootstrap_covariance": covariance.tolist(),
        "n_boot": int(n_boot),
        "bootstrap_unit": "seed_block",
        "rng_seed": int(rng_seed),
    }


def fixed_column_moments(interfaces, column=None, n_boot=2000, rng_seed=42):
    """Secondary fixed-column diagnostic across independent seeds."""
    interfaces = np.asarray(interfaces)
    if interfaces.ndim != 2:
        raise ValueError("interfaces must have shape (n_seeds, L)")
    if column is None:
        column = interfaces.shape[1] // 2
    if not (0 <= column < interfaces.shape[1]):
        raise ValueError("column is outside the interface")
    result = bootstrap_seed_block_moments(
        interfaces[:, column : column + 1], n_boot=n_boot, rng_seed=rng_seed
    )
    result["column"] = int(column)
    return result


def compare_to_goe(moment_result):
    """Annotate moment estimates and interval-wise GOE compatibility."""
    result = dict(moment_result)
    targets = {
        "skewness": GOE_SKEWNESS,
        "excess_kurtosis": GOE_EXCESS_KURTOSIS,
    }
    result["goe_targets"] = targets
    result["goe_delta"] = {
        name: float(result[name] - target) for name, target in targets.items()
    }
    compatibility = {}
    for name, target in targets.items():
        lo95, hi95 = result["ci95"][name]
        lo99, hi99 = result["ci99"][name]
        if lo95 <= target <= hi95:
            verdict = "compatible_95"
        elif target < lo99 or target > hi99:
            verdict = "incompatible_99"
        else:
            verdict = "inconclusive_between_95_and_99"
        compatibility[name] = verdict
    result["goe_compatibility"] = compatibility
    return result


def _records_for(records, pct, q):
    return sorted(
        [
            r
            for r in records
            if int(r["sticky_fraction_pct"]) == int(pct)
            and np.isclose(float(r["q"]), float(q))
        ],
        key=lambda r: int(r["L"]),
    )


def classify_cross_l_goe(records, sticky_fraction_pct, late_q=(0.25, 0.40)):
    """Apply a conservative two-largest-L GOE moment verdict.

    ``KPZ-GOE consistent`` requires both GOE targets inside every pooled 95%
    interval at the two largest common widths and no outward absolute-delta
    drift from the second-largest to largest width.  ``inconsistent`` requires
    both targets outside every 99% interval.  Everything else is explicitly
    inconclusive/crossover-dominated.
    """
    selected = {}
    common_widths = None
    for q in late_q:
        q_records = _records_for(records, sticky_fraction_pct, q)
        widths = {int(record["L"]) for record in q_records}
        common_widths = widths if common_widths is None else common_widths & widths
        selected[float(q)] = {int(record["L"]): record for record in q_records}
    if not common_widths or len(common_widths) < 2:
        return {
            "verdict": "inconclusive/crossover-dominated",
            "reason": "fewer than two common late-q widths",
            "widths_used": sorted(common_widths or []),
        }

    widths_used = sorted(common_widths)[-2:]
    names = ("skewness", "excess_kurtosis")
    all_compatible = True
    all_incompatible = True
    no_outward_drift = True
    for q in late_q:
        smaller = selected[float(q)][widths_used[0]]["pooled"]
        larger = selected[float(q)][widths_used[1]]["pooled"]
        for name in names:
            all_compatible &= (
                smaller["goe_compatibility"][name] == "compatible_95"
                and larger["goe_compatibility"][name] == "compatible_95"
            )
            all_incompatible &= (
                smaller["goe_compatibility"][name] == "incompatible_99"
                and larger["goe_compatibility"][name] == "incompatible_99"
            )
            no_outward_drift &= abs(larger["goe_delta"][name]) <= abs(
                smaller["goe_delta"][name]
            )

    if all_compatible and no_outward_drift:
        verdict = "KPZ-GOE consistent"
        reason = "two largest widths compatible at both late q with no outward drift"
    elif all_incompatible:
        verdict = "inconsistent-on-accessible-scales"
        reason = "both GOE moments excluded at 99% across both widths and late q"
    else:
        verdict = "inconclusive/crossover-dominated"
        reason = "strict two-width late-q consistency/inconsistency gate not met"
    return {"verdict": verdict, "reason": reason, "widths_used": widths_used}
