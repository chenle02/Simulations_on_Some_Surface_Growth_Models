# exp14 analysis result bundle

This directory contains compact, tracked products from the corrected exp14 one-by-one `piece_19` sticky/nonsticky ballistic-deposition analysis. It does **not** contain the 255 GB raw joblib ensemble.

## Percentage convention

For exp14, `pct` is the **sticky fraction**. The generator writes
`Piece-19 = [100-pct, pct]`, with state order `[nonsticky, sticky]`.
This differs from exp13, whose named percentage used `[pct, 100-pct]` and
therefore denoted the nonsticky fraction. Equal exp13/exp14 percentage labels
are opposite physical mixtures and must not be compared without conversion.

## Contents

### Sampling sensitivity

`sampling_sensitivity_2026-07-12.json` compares the central growth-window OLS
slope using every time point with the slope after paired log-spaced sampling to
at most 5,000 points. The physical clock and fit window are unchanged.

- 50 corrected exp14 cells are included; four absent `(pct,L)` cells are listed.
- Log weighting raises the fitted beta in all 50 cells and is not a numerically
  negligible replacement for full-point weighting.
- SHA-256:
  `114733ce9e962d4566cad63d8c38268a209db91b11a6645a047e558ead5f459f`.
- Reproducibility code: `06d3e38` (comparison tool) and `58b17f8` (tracked
  result snapshot); the paired production sampler was introduced in `767577a`.

Representative values:

| exp14 sticky fraction | Summary | Full-point beta | Log-sampled beta |
|---:|---|---:|---:|
| 5% | mean over available widths | 0.3320 | 0.3966 |
| 5% | L=300 | 0.2869 | 0.3537 |
| 99% | mean over available widths | 0.1911 | 0.2305 |
| 99% | L=500 | 0.2228 | 0.2572 |

These differences show that the accessible traces contain substantial
curvature/crossover. The asymptotic exponent is estimator-sensitive on these
scales.

### Common-time interfaces

`tw_interfaces/` contains 14 compact cells, each as one NPZ plus one JSON
metadata file. They were reduced from timestamped raw substrates at **common
deposition times**, not from each seed's potentially different final time.
Each NPZ contains the interface snapshots needed to repeat the moment analysis;
the raw joblibs are not needed for re-bootstrap/reanalysis.

Reduction grid:

- sticky fractions 90, 95, 98, 99 at L=300, 400, 500;
- controls 5 and 50 at L=300;
- 100 seeds per cell;
- scaled growth times q = 0.15, 0.25, 0.40, where target mean height is
  `q * L^(3/2)`.

The reducer reconstructs physical column heights from deposition timestamps and
validates each interface against the corrected per-seed mean height and the raw
per-seed interface width. The production run made 4,200 checks (14 cells x 100
seeds x 3 times), all passing. Provenance:

- implementation `a47ec6c`;
- in-memory compatibility fix for Easley's original inverted trace copies
  `218819f`;
- Easley canary job `5373333` (`pct=90`, L=300);
- Easley full reduction array `5373334` (14/14 completed).

The 255 GB raw joblibs remain on Easley scratch. Corrected reduced W/hbar traces
remain in the private backup. The compact tracked snapshots are sufficient to
reproduce the committed Tracy--Widom moment analysis.

### Tracy--Widom moment analysis

`tw_analysis/` contains one JSON result per compact cell and aggregate
`tw_analysis/results.json`. Moments use the positive physical-height sign,
2,000 bootstrap replicates, and whole-seed block resampling so spatial columns
from a seed are never treated as independent bootstrap units.

Flat-geometry GOE reference moments:

- skewness: 0.2935;
- excess kurtosis: 0.1652.

**Result:** every cross-L classification is
`inconclusive/crossover-dominated`. At high sticky fractions, pooled L=400
excess kurtosis is often significantly negative, while L=500 shifts back toward
or above zero. The two largest widths therefore do not show a stable
two-width/two-time GOE fingerprint. Fixed-center-column checks have broad
intervals and do not resolve that instability.

## Interpretation limit (load-bearing)

**NONPROOF / finite-scale diagnostic:** matching GOE skewness and kurtosis would
be a useful KPZ fingerprint, not proof of full KPZ universality. The present
bundle does not even establish stable two-moment GOE agreement. It supports an
observed crossover in effective behavior, but it supports neither a super-KPZ
claim nor a settled asymptotic KPZ/EW classification. Larger widths and/or more
independent seeds, alpha and z estimates, and—if moments stabilize—a full
standardized CDF comparison are still required.
