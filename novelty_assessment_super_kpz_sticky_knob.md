# Evidence memo: sticky-fraction crossover in tetromino ballistic deposition

## Current verdict

The original hypothesis—**increasing stickiness produces a super-KPZ regime**—is
**SUPERSEDED and not supported by the corrected exp14 evidence**. The simulations
show a strong change in finite-scale effective behavior across the mixture knob,
but neither the asymptotic exponent nor the universality class is resolved.
There is no justified super-KPZ claim and no justified full KPZ-universality
claim.

## Load-bearing percentage convention

The exp13 and exp14 labels encode opposite physical fractions:

- **exp13:** `Piece-19 = [pct, 100-pct]`; `pct` is the **nonsticky fraction**.
- **exp14:** `Piece-19 = [100-pct, pct]`; `pct` is the **sticky fraction**.
- State order is `[nonsticky, sticky]` in both cases.

Consequently, equal percentage labels in exp13 and exp14 describe opposite
mixtures. Earlier cross-experiment prose that treated both labels as the sticky
fraction is invalid.

## Corrected exp14 exponent evidence

The tracked sensitivity result is
`tetris_ballistic/data/exp14_results/sampling_sensitivity_2026-07-12.json`
(SHA-256
`114733ce9e962d4566cad63d8c38268a209db91b11a6645a047e558ead5f459f`).
It compares the same deposited-height clock and physical growth window under two
point-weighting rules.

| exp14 sticky fraction | Summary | Full-point beta | Log-sampled beta |
|---:|---|---:|---:|
| 5% | mean over available widths | 0.3320 | 0.3966 |
| 5% | L=300 | 0.2869 | 0.3537 |
| 99% | mean over available widths | 0.1911 | 0.2305 |
| 99% | L=500 | 0.2228 | 0.2572 |

Log-spaced weighting raises beta in **all 50 cells**. The change is
non-negligible, so the approved 5,000-point sampler is not numerically equivalent
to full-point OLS. This estimator dependence is itself evidence of substantial
curvature/crossover on accessible scales. It forbids treating a single beta fit
as an asymptotic universality-class measurement.

The corrected data do show a real finite-scale progression as sticky fraction
changes: low-stickiness cells are more RD-like/high-beta, while high-stickiness
cells have substantially lower effective beta. That observation is compatible
with a crossover narrative, but it does not determine whether the large-scale
limit is KPZ, EW-like, or still preasymptotic.

## Tracy--Widom diagnostic

The common-time interface pipeline reconstructs height snapshots from raw
substrate deposition timestamps, avoiding the invalid comparison of different
per-seed final times. The priority analysis used:

- 14 cells: sticky fractions 90, 95, 98, 99 at L=300, 400, 500, plus 5 and 50
  at L=300;
- 100 independent seeds per cell;
- q = 0.15, 0.25, 0.40 of the `L^(3/2)` height scale;
- 2,000 whole-seed block bootstrap replicates;
- flat-geometry GOE targets skewness 0.2935 and excess kurtosis 0.1652.

All cross-L verdicts in
`tetris_ballistic/data/exp14_results/tw_analysis/results.json` are
`inconclusive/crossover-dominated`. For high sticky fractions, pooled L=400
excess kurtosis is often significantly negative, whereas L=500 moves back toward
or above zero. There is no stable two-width/two-time GOE moment fingerprint.
Fixed-center-column intervals are broad and do not rescue the pooled
instability.

Matching two moments would be a useful KPZ fingerprint, not proof of the full
height law or universality class. Here the two moments do not yet stabilize.

## Literature reconnaissance (qualified)

The literature survey remains useful as context, but its earlier novelty verdict
was stronger than the evidence:

- Competitive random-deposition/ballistic-deposition studies by Braunstein,
  Buceta, Muraca, and Lam describe crossover between RD-like and standard
  KPZ-like behavior rather than an established super-KPZ fixed point.
- Oliveira Filho, Oliveira, and Redinz studied crossover behavior in a modified
  ballistic-deposition setting without establishing an alpha>1/2 super-rough
  phase.
- Work on patchy, anisotropic, rectangular, or binary particles (including work
  associated with Das, Banerjee, and Roy) indicates that particle geometry can
  produce long structural crossovers; it does not by itself validate the
  proposed sticky-fraction super-KPZ mechanism.

These names are reconnaissance pointers, not verified citekeys for manuscript
use. Bibliographic records must be checked independently before citation.

The potentially defensible novelty is therefore narrower: a controlled
finite-scale crossover study for extended/tetromino deposition with explicit
estimator-sensitivity and common-time distribution diagnostics. A new
universality class is not established.

## Evidence ledger

### Observed

- exp13 and exp14 percentage labels use opposite mixture conventions.
- Corrected exp14 exhibits a strong sticky-fraction dependence in finite-scale
  effective beta.
- Log weighting raises beta in 50/50 analyzed cells; asymptotic inference is
  estimator-sensitive.
- Fourteen common-time interface cells passed 4,200 reconstruction checks.
- Tracy--Widom skewness/kurtosis do not form a stable two-width/two-time GOE
  fingerprint on the tested scales.

### Superseded

- “Higher sticky percentage produces super-KPZ beta.”
- “The exp13 and exp14 percentage labels have the same physical meaning.”
- “Log-subsampling to 5,000 points has negligible effect on the fitted slope.”
- “The current data establish an EW-to-KPZ-to-super-KPZ trajectory.”

### Pending

- Larger L and/or more independent seeds to test whether the moment drift settles.
- Independent roughness alpha and dynamic z estimates, including alpha+z and
  beta=alpha/z consistency checks.
- A full standardized height CDF/quantile comparison if the low-order moments
  first become stable across width and time.
- Final literature/citekey verification before manuscript claims.

## Recommendation

Frame the paper around an **observed tetromino-deposition crossover with strong
finite-size and estimator sensitivity**. Keep the asymptotic class explicitly
unresolved. Do not use “super-KPZ” in the headline or abstract unless future
larger-scale beta, alpha/z, and distributional evidence jointly supports it.
