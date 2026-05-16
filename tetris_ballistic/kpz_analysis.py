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
    pattern = (
        f"{exp_dir}/config_piece_19_combined_percentage_"
        f"{percentage:02d}_w={L}_seed=*.joblib"
    )
    files = sorted(glob.glob(pattern))
    if not files:
        raise ValueError(f"No files for pct={percentage}, L={L}: {pattern}")
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


def growth_window_slope(W_ensemble, hbar_ensemble, L,
                        hbar_lo=10.0, n_boot=200, ci_level=0.95,
                        rng_seed=42):
    """OLS slope in the growth window h̄ ∈ [hbar_lo, L^{3/2}/2].

    Avoids both the early transient (h̄ < 10 lattice units) and the
    saturation tail (h̄ > L^{3/2}/2).  Case-resampling bootstrap CI
    over independent runs.

    Returns
    -------
    beta : float — central slope estimate
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

    log_t_all = np.log10(np.arange(1, len(mean_W) + 1, dtype=float))

    def _fit(w_arr):
        w_pos = np.maximum(w_arr, 1e-30)
        return linregress(log_t_all[mask], np.log10(w_pos[mask])).slope

    beta_center = _fit(mean_W)

    n_runs = W_ensemble.shape[0]
    rng = np.random.default_rng(rng_seed)
    boot_betas = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        boot_betas[b] = _fit(np.mean(W_ensemble[idx], axis=0))

    alpha = 1.0 - ci_level
    ci_lo = float(np.percentile(boot_betas, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_betas, 100 * (1 - alpha / 2)))
    return float(beta_center), ci_lo, ci_hi


# ---------------------------------------------------------------------------
#  Step 3 — Local-slope curve with bootstrap CI
# ---------------------------------------------------------------------------

def local_slope_bootstrap(W_ensemble, n_eval=200, log_half_width=0.5,
                          n_boot=500, ci_level=0.95, rng_seed=42):
    """Running local slope with case-resampling bootstrap CI bands.

    Per-time local slope on a sliding log-window following the
    Wolf–Kertész (1987) effective-exponent concept.  Bootstrap CI is
    obtained by case-resampling independent runs (the analogue of the
    Wendt–Abry–Jaffard 2007 block-bootstrap philosophy; since runs are
    independent, case-resampling suffices).

    Parameters
    ----------
    W_ensemble : ndarray, shape (n_runs, T)
        Interface width W(t) per run.
    n_eval : int
        Number of log-spaced evaluation points (default 200).
    log_half_width : float
        Half-width of the sliding log10 window in decades (default 0.5).
    n_boot : int
        Bootstrap replicates (default 500).
    ci_level : float
        Confidence level (default 0.95).
    rng_seed : int
        Reproducibility seed.

    Returns
    -------
    eval_log_t : ndarray, shape (n_eval_actual,)
    slope_med  : ndarray — median bootstrap slope
    slope_lo   : ndarray — lower CI bound
    slope_hi   : ndarray — upper CI bound
    """
    n_runs, T = W_ensemble.shape
    log_t = np.log10(np.arange(1, T + 1, dtype=float))

    # Skip trivial early regime (h̄ < ~10 lattice units → first ~1 % of data)
    start_idx = max(2, int(T * 0.002))
    eval_indices = np.unique(
        np.geomspace(start_idx, T - 1, n_eval).astype(int)
    )
    eval_log_t = log_t[eval_indices]
    n_pts = len(eval_indices)

    # Precompute window boundaries via searchsorted (O(n_pts log T) total)
    win_lo_idx = np.searchsorted(log_t, eval_log_t - log_half_width, side="left")
    win_hi_idx = np.searchsorted(log_t, eval_log_t + log_half_width, side="right")

    rng = np.random.default_rng(rng_seed)

    def _slopes_from_log_W(log_W_mean):
        """OLS slope inside each precomputed log-window."""
        slopes = np.full(n_pts, np.nan)
        for k in range(n_pts):
            a, b = win_lo_idx[k], win_hi_idx[k]
            if b - a < 5:
                continue
            x = log_t[a:b]
            y = log_W_mean[a:b]
            if np.ptp(y) < 1e-12:
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

    # Central estimate (on the ensemble average)
    mean_W = np.mean(W_ensemble, axis=0)
    mean_W = np.maximum(mean_W, 1e-30)
    slope_center = _slopes_from_log_W(np.log10(mean_W))

    # Bootstrap replicates
    boot_slopes = np.empty((n_boot, n_pts))
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        bW = np.mean(W_ensemble[idx], axis=0)
        bW = np.maximum(bW, 1e-30)
        boot_slopes[b] = _slopes_from_log_W(np.log10(bW))

    alpha = 1.0 - ci_level
    slope_lo = np.nanpercentile(boot_slopes, 100 * alpha / 2, axis=0)
    slope_hi = np.nanpercentile(boot_slopes, 100 * (1 - alpha / 2), axis=0)
    slope_med = np.nanmedian(boot_slopes, axis=0)

    return eval_log_t, slope_med, slope_lo, slope_hi


# ---------------------------------------------------------------------------
#  Step 4 — Automatic plateau detection (the one genuinely new piece)
# ---------------------------------------------------------------------------

def detect_plateau(eval_log_t, slope_med, slope_lo, slope_hi,
                   deriv_thresh=0.05, ci_width_thresh=0.15,
                   min_log_extent=0.4):
    """Algorithmic plateau detector for the local-slope curve.

    Finds the longest contiguous time range where:
      (a) |dβ̂ / d(log t)| < *deriv_thresh*,
      (b) CI width (hi − lo) < *ci_width_thresh*,
      (c) log-extent ≥ *min_log_extent* decades.

    Parameters
    ----------
    eval_log_t, slope_med, slope_lo, slope_hi : ndarray
        Output of :func:`local_slope_bootstrap`.
    deriv_thresh : float
        Maximum absolute slope-derivative to qualify as "flat".
    ci_width_thresh : float
        Maximum CI width (slope_hi − slope_lo).
    min_log_extent : float
        Minimum plateau extent in decades of log₁₀(t).

    Returns
    -------
    tuple (plateau_mask, plateau_beta, (ci_lo, ci_hi))
        or *None* if no plateau is found.
    """
    valid = ~np.isnan(slope_med)
    if valid.sum() < 5:
        return None

    # Numerical derivative of slope w.r.t. log_t
    d_slope = np.gradient(slope_med, eval_log_t)
    ci_width = slope_hi - slope_lo

    candidate = (
        valid
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
