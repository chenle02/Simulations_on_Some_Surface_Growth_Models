# CRITICAL FINDING: `AvergeHeight` convention silently inverted by commit e7ba915

**Date:** 2026-07-11
**Severity:** load-bearing scientific correctness (affects exp14; NOT exp13)
**Status:** PI approved Option 3 (fix code + one-time invert exp14 artifacts)

## The bug (corrected root cause)

`AvergeHeight` was **physical mean height** (0 at t=0, growing up) until commit
**`e7ba915` "perf(sim): incremental heights array (Phase 1, 30x speedup)"**
(2026-05-16). That refactor redefined `self.heights` as **row-index measured
from the TOP** (`np.full(width, height-1)`), so `AvergeHeight = heights.mean()`
became the **mean row-index** — which **decreases** as the pile grows. The commit
message claimed "AvergeHeight: bit-equal (atol=0) — same np.mean path", but that
self-check only compared `mean(heights)` to `mean(heights)`; it did NOT verify the
physical-height *convention* was preserved, so the inversion went unnoticed.

Both the current legacy path (`tetris_ballistic.py:1807`
`self.AvergeHeight[step] = self.heights.mean()`) AND the numba kernel
(`_kernel_1x1.py:122` `avg_height[i] = mean`) now store the **inverted row-index**.
They agree with each other (verified: identical to 1.78e-15), but both disagree
with the correct pre-`e7ba915` physical-height convention.

## Evidence

| run | date | code era | `AvergeHeight` L=50 pct=5 | orientation |
|---|---|---|---|---|
| exp13 | 2025-06-05 | pre-`e7ba915` (`_ffnz`) | `[0.02 … 493]` | ascending ✅ physical height |
| exp14 | 2026-07 | post-`e7ba915` + kernel | `[1098.98 … 69]` | descending ❌ mean row-index |

exp13 was run ~11 months BEFORE `e7ba915`, so it used the correct convention.
For exp14 L=50, grid height = L·ratio = 50·22 = 1100, so physical mean height is
`h_phys = 1100 − AvergeHeight`, which IS monotone increasing (0 → 1030) and aligns
exactly with W (both ~0 at t=0). Confirmed numerically.

The fix: restore physical height, `AvergeHeight = height − mean(heights)`, in BOTH
paths, with a regression test that pins the physical-height convention (not just
"the two paths agree").

## Blast radius

- **exp14**: the whole crossover analysis is invalid as-run — the height clock
  (`log W` vs `log h̄`) used the **inverted, wrong** quantity, and the saturation
  gate `hbar_max >= L^1.5` compared row-index (~68) to L^1.5 (~353) and so
  wrongly flagged EVERY exp14 cell "unsat" (this explains the reduce logs).
- **exp13**: legacy path, `AvergeHeight` ascending, `hbar_max=475 ≈ ratio·L`,
  `saturated=True` — **CORRECT**. The committed exp13 crossover, the wiki
  β-table, and the Article are **NOT affected**.
- **The reduced exp14 npz** (backup tier) inherit the inverted `hbar` verbatim
  (reduce_traces.py copies the field faithfully — the reduce is NOT the bug).

## Recovery (no re-simulation needed)

The raw exp14 joblib (255 GB on Easley scratch, 5000 cells) and the reduced npz
both contain the full W and the row-index AvergeHeight. Physical height is
recoverable as `h_phys = grid_height − AvergeHeight` per cell, where
`grid_height = L · ratio(L)`. So exp14 can be re-derived **without re-running**.

## Options (PI decision)

1. **Fix the kernel** (`_kernel_1x1.py`: `avg_height[i] = height − mean(heights)`)
   so the numba path matches the legacy path, add a regression test that the two
   paths agree, re-reduce exp14 from raw joblib (bigmem job), re-run the crossover,
   update wiki + Article β-table with the corrected exp14 curve.
2. **Fix at the analysis layer only** (invert exp14 npz `hbar` on load, keyed by a
   per-experiment `height_convention` flag) — faster, but leaves the kernel bug
   for future runs.
3. **Both**: fix the kernel (correct going forward) AND add a one-time inversion
   for the already-produced exp14 artifacts.

Recommended: **Option 3** — the kernel bug is the root cause and will bite every
future `[hpc]` run; the exp14 artifacts just need a documented one-time inversion.

## What I did NOT do

Per the coauthor/PI-decision protocol, I did NOT unilaterally flip data or patch
the kernel across the 4 repos, because this changes a load-bearing scientific
convention and touches committed results. Escalating for your decision.
