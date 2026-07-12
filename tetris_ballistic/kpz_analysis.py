#!/usr/bin/env python3
"""
Robust KPZ growth-exponent extraction for tetromino ballistic deposition.

Implements the 8-step protocol documented in the SPDEs-wiki project page
``tetris-kpz-slope-extraction.md``.  Each function cites its methodological
origin in the docstring.

References
----------
- Family & Vicsek (1985). J. Phys. A 18, L75.
- Meakin, Ramanlal, Sander, Ball (1986). Phys. Rev. A 34, 5091.
- Baiod, Kessler, Ramanlal, Sander, Savit (1988). Phys. Rev. A 38, 3672.
- Krug & Meakin (1990). J. Phys. A 23, L987.
- Amar & Family (1990). Phys. Rev. A 41, 3399.
- Wendt, Abry, Jaffard (2007). IEEE wavelet-leader bootstrap.
- Pagnani & Parisi (2013). Phys. Rev. E 87, 010102.

Author: Le Chen (le.chen@auburn.edu)
"""

import glob
import os

import joblib
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress

# ---------------------------------------------------------------------------
#  Step 1-2 — Data loading & ensemble construction
# ---------------------------------------------------------------------------

def load_ensemble(exp_dir, percentage, L):
    """Load all seeds for one (percentage, L) cell.

    Implements **Step 2** (ensemble construction, Baiod et al. 1988: ≥10
    independent runs).

    Parameters
    ----------
    exp_dir : str
        Path to ``experiments/exp13/``.
    percentage : int
        Sticky-fraction percentage (5, 50, 90, 95, 98, 99).
    L : int
        Strip width (50, 80, 100, 150, 200).

    Returns
    -------
    W_list : list[ndarray]
        ``Fluctuation`` array per seed, trimmed to ``FinalSteps``.
    hbar_list : list[ndarray]
        ``AvergeHeight`` array per seed, trimmed to ``FinalSteps``.
    """
    # Prefer the REDUCED npz layout (pct_NN/L_LLLL.npz) if present — one file
    # per (pct,L) cell holding all seeds as (n_seeds, max_len) float32 matrices
    # plus per-seed final_steps. This lets a revised estimator re-run on the
    # committed reduced traces WITHOUT the raw joblib (reanalysis-complete).
    # Falls back to the raw per-seed joblib layout when no npz is found.
    npz_path = os.path.join(exp_dir, f"pct_{percentage:02d}", f"L_{L:04d}.npz")
    if os.path.exists(npz_path):
        d = np.load(npz_path)
        W_mat, hbar_mat = d["W"], d["hbar"]
        # W/hbar are padded to max_len; final_steps un-pads each seed to its
        # true length (else padding zeros corrupt the analysis).
        fs = d["final_steps"] if "final_steps" in d.files else None
        # Keep float32 (npz dtype): deep cells reach 100 x ~8M steps, so a
        # float64 upcast would need ~25 GB peak per L=500 cell and OOM on a
        # 16 GB box. float32 mean/std are ample for the log-log slope.
        W_list, hbar_list = [], []
        for i in range(W_mat.shape[0]):
            n = int(fs[i]) if fs is not None else W_mat.shape[1]
            W_list.append(np.ascontiguousarray(W_mat[i, :n]))
            hbar_list.append(np.ascontiguousarray(hbar_mat[i, :n]))
        return W_list, hbar_list

    pattern = (
        f"{exp_dir}/config_piece_19_combined_percentage_"
        f"{percentage:02d}_w={L}_seed=*.joblib"
    )
    files = sorted(glob.glob(pattern))
    if not files:
        raise ValueError(
            f"No npz ({npz_path}) and no joblib for pct={percentage}, L={L}: {pattern}"
        )
    W_list, hbar_list = [], []
    for f in files:
        obj = joblib.load(f)
        n = obj.FinalSteps
        W_list.append(obj.Fluctuation[:n].astype(float))
        hbar_list.append(obj.AvergeHeight[:n].astype(float))
    return W_list, hbar_list


def truncate_to_common_length(arrays):
    """Truncate a list of 1-D arrays to the shortest length.

    Variable trace lengths arise because the simulation stops when the
    domain fills (``FinalSteps`` varies across seeds).

    Returns
    -------
    mat : ndarray, shape (n_arrays, min_len)
    min_len : int
    """
    min_len = min(len(a) for a in arrays)
    mat = np.empty((len(arrays), min_len))
    for i, a in enumerate(arrays):
        mat[i] = a[:min_len]
    return mat, min_len


def log_subsample_paired_traces(W_list, hbar_list, max_points=5000):
    """Align and log-subsample paired width/height traces.

    A single index array is applied to every seed and to both observables, so
    the deposited-height clock remains paired with its width measurement.
    Traces with at most ``max_points`` samples are unchanged.  Longer traces
    retain unique, ordered, approximately log-spaced samples including both
    endpoints.  Source dtypes are preserved.

    Returns
    -------
    W_ensemble, hbar_ensemble : ndarray
        Paired matrices with shape ``(n_seeds, n_analysis_points)``.
    original_common_len : int
        Minimum length across both observables and every seed.
    indices : ndarray
        Original trace indices retained for analysis.
    """
    if not W_list or not hbar_list:
        raise ValueError("W_list and hbar_list must be non-empty")
    if len(W_list) != len(hbar_list):
        raise ValueError("W_list and hbar_list must contain the same seeds")
    if max_points < 2:
        raise ValueError("max_points must be at least 2")

    original_common_len = min(
        min(len(trace) for trace in W_list),
        min(len(trace) for trace in hbar_list),
    )
    if original_common_len < 2:
        raise ValueError("traces must contain at least two paired samples")

    if original_common_len <= max_points:
        indices = np.arange(original_common_len, dtype=np.int64)
    else:
        # Reserve one strictly increasing index per requested point, then
        # distribute the remaining index range logarithmically.  This avoids
        # the duplicate-heavy rounding of geomspace on integer indices while
        # retaining dense early-time coverage and both endpoints.
        extra_range = original_common_len - max_points + 1
        log_offsets = np.rint(
            np.geomspace(1, extra_range, num=max_points) - 1
        ).astype(np.int64)
        indices = np.arange(max_points, dtype=np.int64) + log_offsets

    W_ensemble = np.stack([trace[indices] for trace in W_list])
    hbar_ensemble = np.stack([trace[indices] for trace in hbar_list])
    return W_ensemble, hbar_ensemble, original_common_len, indices


def growth_window_slope(W_ensemble, hbar_ensemble, L,
                        hbar_lo=10.0, n_boot=200, ci_level=0.95,
                        rng_seed=42):
    """OLS slope of log W vs log h̄ in the growth window h̄ ∈ [hbar_lo, L^{3/2}/2].

    The Family–Vicsek growth law is ``W ~ t^β`` with ``t`` = the *deposited
    height* h̄ (number of deposited layers), **not** the raw deposition-step
    index.  For multi-cell (tetromino) pieces the two are not proportional in
    the transient, so the growth exponent MUST be measured against log h̄.
    See the SPDEs-wiki project page, "Findings 2026-07-11", Finding 2.

    Avoids both the early transient (h̄ < ``hbar_lo`` lattice units) and the
    saturation tail (h̄ > L^{3/2}/2).  Case-resampling bootstrap CI over
    independent runs.

    Returns
    -------
    beta : float — central slope estimate (dlogW / dlog h̄)
    ci_lo, ci_hi : float — bootstrap CI bounds
    """
    hbar_hi = 0.5 * L ** 1.5
    mean_W = np.mean(W_ensemble, axis=0)
    mean_hbar = np.mean(hbar_ensemble, axis=0)
    mask = (mean_hbar >= hbar_lo) & (mean_hbar <= hbar_hi) & (mean_W > 0)
    if mask.sum() < 10:
        mask = (mean_hbar >= hbar_lo) & (mean_W > 0)
    if mask.sum() < 5:
        return np.nan, np.nan, np.nan

    def _fit(w_arr, h_arr):
        # Regress log W against log h̄ (the physically correct time axis),
        # NOT against the deposition-step index.
        w_pos = np.maximum(w_arr, 1e-30)
        h_pos = np.maximum(h_arr, 1e-30)
        return linregress(
            np.log10(h_pos[mask]), np.log10(w_pos[mask])
        ).slope

    beta_center = _fit(mean_W, mean_hbar)

    n_runs = W_ensemble.shape[0]
    rng = np.random.default_rng(rng_seed)
    boot_betas = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        boot_betas[b] = _fit(
            np.mean(W_ensemble[idx], axis=0),
            np.mean(hbar_ensemble[idx], axis=0),
        )

    alpha = 1.0 - ci_level
    ci_lo = float(np.percentile(boot_betas, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_betas, 100 * (1 - alpha / 2)))
    return float(beta_center), ci_lo, ci_hi


# ---------------------------------------------------------------------------
#  Step 3 — Local-slope curve with bootstrap CI
# ---------------------------------------------------------------------------

def local_slope_bootstrap(W_ensemble, hbar_ensemble, n_eval=200,
                          log_half_width=0.5, n_boot=500, ci_level=0.95,
                          rng_seed=42):
    """Effective growth exponent β_eff(h̄) = dlogW / dlog h̄ with bootstrap CI.

    The independent variable is the deposited height h̄ (Family–Vicsek time
    variable), evaluated on the ensemble-mean h̄ trajectory.  Regressing
    against the deposition-step index instead would contaminate the exponent
    with the transient (see project page, Finding 2).  The effective-exponent
    idea is Wolf–Kertész (1987); the case-resampling bootstrap over independent
    runs follows the Wendt–Abry–Jaffard (2007) philosophy.

    Parameters
    ----------
    W_ensemble : ndarray, shape (n_runs, T)
        Interface width W per run (per deposition step).
    hbar_ensemble : ndarray, shape (n_runs, T)
        Mean height h̄ per run (per deposition step).
    n_eval : int
        Number of log-spaced evaluation points in h̄ (default 200).
    log_half_width : float
        Half-width of the sliding log10(h̄) window in decades (default 0.5).
    n_boot : int
        Bootstrap replicates (default 500).
    ci_level : float
        Confidence level (default 0.95).
    rng_seed : int
        Reproducibility seed.

    Returns
    -------
    eval_log_hbar : ndarray — log10 h̄ evaluation points
    slope_med     : ndarray — median bootstrap β_eff
    slope_lo      : ndarray — lower CI bound
    slope_hi      : ndarray — upper CI bound
    """
    n_runs = W_ensemble.shape[0]
    mean_hbar_full = np.maximum(np.mean(hbar_ensemble, axis=0), 1e-30)
    log_hbar = np.log10(mean_hbar_full)

    lo = np.searchsorted(log_hbar, log_hbar[0] + 0.05, side="left")
    lo = max(lo, 2)
    hi = len(log_hbar) - 1
    eval_log_hbar = np.linspace(log_hbar[lo], log_hbar[hi], n_eval)
    n_pts = len(eval_log_hbar)

    win_lo_idx = np.searchsorted(
        log_hbar, eval_log_hbar - log_half_width, side="left"
    )
    win_hi_idx = np.searchsorted(
        log_hbar, eval_log_hbar + log_half_width, side="right"
    )

    rng = np.random.default_rng(rng_seed)

    def _slopes(log_W, log_h):
        slopes = np.full(n_pts, np.nan)
        for k in range(n_pts):
            a, b = win_lo_idx[k], win_hi_idx[k]
            if b - a < 5:
                continue
            x = log_h[a:b]
            y = log_W[a:b]
            if np.ptp(y) < 1e-12 or np.ptp(x) < 1e-12:
                continue
            n = b - a
            sx = x.sum()
            sy = y.sum()
            sxx = (x * x).sum()
            sxy = (x * y).sum()
            denom = n * sxx - sx * sx
            if abs(denom) < 1e-30:
                continue
            slopes[k] = (n * sxy - sx * sy) / denom
        return slopes

    mean_W = np.maximum(np.mean(W_ensemble, axis=0), 1e-30)
    _ = _slopes(np.log10(mean_W), log_hbar)

    boot_slopes = np.empty((n_boot, n_pts))
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        bW = np.maximum(np.mean(W_ensemble[idx], axis=0), 1e-30)
        bH = np.maximum(np.mean(hbar_ensemble[idx], axis=0), 1e-30)
        boot_slopes[b] = _slopes(np.log10(bW), np.log10(bH))

    alpha = 1.0 - ci_level
    slope_lo = np.nanpercentile(boot_slopes, 100 * alpha / 2, axis=0)
    slope_hi = np.nanpercentile(boot_slopes, 100 * (1 - alpha / 2), axis=0)
    slope_med = np.nanmedian(boot_slopes, axis=0)

    return eval_log_hbar, slope_med, slope_lo, slope_hi


# ---------------------------------------------------------------------------
#  Step 4 — Automatic plateau detection (the one genuinely new piece)
# ---------------------------------------------------------------------------

def detect_plateau(eval_log_hbar, slope_med, slope_lo, slope_hi,
                   deriv_thresh=0.05, ci_width_thresh=0.15,
                   min_log_extent=0.4, log_hbar_lo=None, log_hbar_hi=None):
    """Algorithmic plateau detector for the β_eff(h̄) curve.

    The abscissa is log₁₀ h̄ (deposited height), matching
    :func:`local_slope_bootstrap`.  Finds the longest contiguous h̄ range where:
      (a) |dβ_eff / dlog h̄| < *deriv_thresh*,
      (b) CI width (hi − lo) < *ci_width_thresh*,
      (c) log-extent ≥ *min_log_extent* decades,
      (d) h̄ lies inside the growth window [log_hbar_lo, log_hbar_hi].

    Restricting to the growth window (d) is essential: without an upper bound
    at ≈½L^{3/2} the detector otherwise locks onto the steep early-transient
    flat (β≈0.5) that precedes the true KPZ regime — the classic false-plateau
    failure mode (project page, Finding 2).

    Parameters
    ----------
    eval_log_hbar, slope_med, slope_lo, slope_hi : ndarray
        Output of :func:`local_slope_bootstrap`.
    deriv_thresh : float
        Maximum absolute slope-derivative to qualify as "flat".
    ci_width_thresh : float
        Maximum CI width (slope_hi − slope_lo).
    min_log_extent : float
        Minimum plateau extent in decades of log₁₀ h̄.
    log_hbar_lo, log_hbar_hi : float or None
        Growth-window bounds in log₁₀ h̄.  ``None`` disables that bound.

    Returns
    -------
    tuple (plateau_mask, plateau_beta, (ci_lo, ci_hi))
        or *None* if no plateau is found.
    """
    eval_log_t = eval_log_hbar
    valid = ~np.isnan(slope_med)
    if valid.sum() < 5:
        return None

    d_slope = np.gradient(slope_med, eval_log_t)
    ci_width = slope_hi - slope_lo

    in_window = np.ones_like(eval_log_t, dtype=bool)
    if log_hbar_lo is not None:
        in_window &= eval_log_t >= log_hbar_lo
    if log_hbar_hi is not None:
        in_window &= eval_log_t <= log_hbar_hi

    candidate = (
        valid
        & in_window
        & (np.abs(d_slope) < deriv_thresh)
        & (ci_width < ci_width_thresh)
    )

    # Find longest contiguous qualifying run
    best_start, best_end, best_extent = -1, -1, 0.0
    i = 0
    while i < len(candidate):
        if candidate[i]:
            j = i
            while j < len(candidate) and candidate[j]:
                j += 1
            extent = eval_log_t[j - 1] - eval_log_t[i]
            if extent >= min_log_extent and extent > best_extent:
                best_start, best_end, best_extent = i, j, extent
            i = j
        else:
            i += 1

    if best_start < 0:
        return None

    plateau_mask = np.zeros(len(eval_log_t), dtype=bool)
    plateau_mask[best_start:best_end] = True

    plateau_beta = float(np.nanmedian(slope_med[plateau_mask]))
    plateau_lo = float(np.nanmedian(slope_lo[plateau_mask]))
    plateau_hi = float(np.nanmedian(slope_hi[plateau_mask]))

    return plateau_mask, plateau_beta, (plateau_lo, plateau_hi)


# ---------------------------------------------------------------------------
#  Step 5 — Meakin (1986) range-of-fit cross-validation
# ---------------------------------------------------------------------------

def meakin_range_of_fit(W_ensemble, hbar_ensemble):
    """Two-window cross-validation per Meakin et al. (1986).

    Fit ln W vs ln h̄ on two non-overlapping windows:
      * Window 1: h̄ ∈ [0.01 h_max, 0.1 h_max]
      * Window 2: h̄ ∈ [0.1 h_max, h_max]

    Agreement within SE is a sanity check that the asymptotic regime
    has been reached.

    Returns
    -------
    (slope1, se1), (slope2, se2) : tuple of tuples
    """
    mean_W = np.mean(W_ensemble, axis=0)
    mean_hbar = np.mean(hbar_ensemble, axis=0)

    pos = (mean_W > 0) & (mean_hbar > 0)
    log_W = np.log10(mean_W[pos])
    log_h = np.log10(mean_hbar[pos])
    h = mean_hbar[pos]
    h_max = h[-1]

    results = {}
    windows = {
        "window1": (h >= 0.01 * h_max) & (h <= 0.1 * h_max),
        "window2": (h >= 0.1 * h_max) & (h <= h_max),
    }
    for name, mask in windows.items():
        if mask.sum() < 5:
            results[name] = (np.nan, np.nan)
        else:
            s = linregress(log_h[mask], log_W[mask])
            results[name] = (s.slope, s.stderr)

    return results["window1"], results["window2"]


# ---------------------------------------------------------------------------
#  Step 6 — Multi-L corrections-to-scaling extrapolation
# ---------------------------------------------------------------------------

def extrapolate_to_infinity(L_array, beta_array, beta_err_array):
    """Corrections-to-scaling fit: β_eff(L) = β_∞ + c · L^{-ω}.

    Per Meakin et al. (1986) + Wegner (1972) correction ansatz,
    refined by Pagnani & Parisi (2013).

    Parameters
    ----------
    L_array : ndarray
        Strip widths.
    beta_array : ndarray
        Effective β per L (from plateau detection).
    beta_err_array : ndarray
        Uncertainty on β per L.

    Returns
    -------
    beta_inf : float
    beta_inf_err : float
    popt : tuple (beta_inf, c, omega) or None
    pcov : ndarray or None
    """
    valid = ~np.isnan(beta_array)
    L = L_array[valid].astype(float)
    beta = beta_array[valid]
    sigma = np.maximum(beta_err_array[valid], 1e-6)

    if len(L) < 2:
        w = 1.0 / sigma ** 2
        beta_inf = float(np.average(beta, weights=w))
        beta_inf_err = float(1.0 / np.sqrt(w.sum()))
        return beta_inf, beta_inf_err, None, None

    def model_3p(x, beta_inf, c, omega):
        return beta_inf + c * x ** (-omega)

    def model_2p(x, beta_inf, c):
        return beta_inf + c * x ** (-0.5)

    def _is_sane(popt, pcov):
        beta_inf, err = popt[0], np.sqrt(pcov[0, 0])
        return -1 < beta_inf < 2 and err < 1.0

    # Try 3-parameter fit if ≥4 points
    if len(L) >= 4:
        try:
            popt, pcov = curve_fit(
                model_3p, L, beta, p0=[0.33, -0.5, 0.5],
                sigma=sigma, absolute_sigma=True, maxfev=10000,
            )
            if _is_sane(popt, pcov):
                return float(popt[0]), float(np.sqrt(pcov[0, 0])), popt, pcov
        except Exception:
            pass

    # Fallback: 2-parameter fit with ω fixed at 0.5 (standard BD correction)
    try:
        popt2, pcov2 = curve_fit(
            model_2p, L, beta, p0=[0.33, -0.5],
            sigma=sigma, absolute_sigma=True, maxfev=10000,
        )
        popt_full = np.array([popt2[0], popt2[1], 0.5])
        pcov_full = np.zeros((3, 3))
        pcov_full[:2, :2] = pcov2
        return float(popt2[0]), float(np.sqrt(pcov2[0, 0])), popt_full, pcov_full
    except Exception:
        pass

    w = 1.0 / sigma ** 2
    beta_inf = float(np.average(beta, weights=w))
    beta_inf_err = float(1.0 / np.sqrt(w.sum()))
    return beta_inf, beta_inf_err, None, None
