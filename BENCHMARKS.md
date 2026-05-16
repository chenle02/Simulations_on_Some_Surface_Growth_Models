# Benchmarks — `tetris_ballistic` v2.0.0

**Hardware**: Le's Dell laptop (the same machine all Phase-0 → Phase-4b numbers were measured on; no cluster).
**Date**: 2026-05-16 overnight session.
**Method**: `tests/benchmark_baseline.py` — 3 representative configs (small / medium / large) timed end-to-end per phase. The `large` config (L=200, 80K steps requested) is the standard exp13 production scale.

---

## Headline

**~380× cumulative speedup on the large config** (L=200, 80K steps): 140s → 0.37s.
Steps/sec is now **flat across L** (the O(W·H) per-step term has been eliminated).

## Detailed table

All numbers are **steps per second** (higher = better). Speedup column is cumulative vs Phase 0.

| Phase | What changed | small (L=50) | medium (L=100) | large (L=200) | Cumulative (large) |
|---|---|---:|---:|---:|---:|
| 0 (baseline) | Pure Python + numpy, v1.2.7 | 1,239 | 652 | 307 | 1× |
| 1 | Incremental `heights` array | 8,847 | 9,342 | 9,266 | **30×** |
| 4a | Cached sampling CDF | 17,494 | 16,834 | 14,436 | **47×** |
| 4b (cold) | numba `@njit` 1x1 kernel, no warmup | 6,150 | 110,403 | 113,573 | 370× |
| 4b (warm) | numba `@njit` 1x1 kernel, JIT amortized | 105,148 | 118,940 | **116,576** | **380×** |

Per-config wall-clock vs Phase 0:

| Config | Phase 0 | Phase 4b (warm) |
|---|---:|---:|
| L=50, 5K steps | 2.02 s | **0.02 s** |
| L=100, 20K steps | 16.68 s | **0.09 s** |
| L=200, 80K steps | 140.18 s | **0.37 s** |

## Cold vs warm

The "cold" Phase-4b numbers above include the JIT compile cost (~0.3 s
on the first kernel call in a fresh process). The cached `@njit(cache=True)`
decoration writes the compiled artifact to disk on first call, so
subsequent calls in the same process — or even fresh processes that
import the kernel after the first compile — pay zero JIT cost. In real
HPC Slurm-array workloads, each array task imports the kernel once and
runs one or more large simulations afterwards, so warm is the relevant
regime.

The small L=50 case in **cold** shows the regression where compile cost
dominates (the simulation itself only runs ~2K steps); this is a known
quirk that goes away on warm.

## Phase-by-phase analysis

### Phase 1 — Incremental heights array (30×)

The original code recomputed the surface envelope from scratch every
step by copying the full W×H substrate, masking it, and scanning every
column with `np.argmax`. That's O(W·H) per step, dominating the runtime.

The fix: maintain a 1-D `self.heights` array updated incrementally
after each piece placement. Per-step cost drops from O(W·H) to O(W).
Bit-equality at `atol=1e-12`.

**Result**: steps/sec rose from {1239, 652, 307} (a clear O(1/W) trend
indicating O(W) cost per step ∝ H ∝ L) to {8847, 9342, 9266} (flat —
the new per-step cost is O(W), independent of L).

### Phase 4a — Cached sampling CDF (47× cumulative)

Profiling Phase 1 revealed that `Sample_Tetris` was consuming **40% of
runtime** — almost entirely Python overhead rebuilding the 40-element
probability vector on every step. None of this work changes between
steps; cache once in `__init__`.

The fix: precompute `self._sample_probs` + `self._sample_cdf` in
`__init__`. `Sample_Tetris` now uses `np.searchsorted(self._sample_cdf,
np.random.random())` — a single C call per step.

**Surprise**: this preserved bit-equality. `np.random.choice(N, p=p)`
is internally implemented as `searchsorted(cumsum(p), uniform())` — the
RNG draw is identical.

### Phase 4b — Numba @njit kernel (380× cumulative)

Even after Phase 1+4a, the remaining cost was Python dispatch
(while-loop, method calls, attribute access) and the `np.std` /
`np.mean` calls (which themselves involve Python overhead for short
arrays).

The fix: implement a single `@njit(cache=True)` kernel that runs the
**entire** 1x1 simulation loop in compiled C-level numba. The kernel
takes pre-generated `positions` + `sticky_flags` arrays (matching the
legacy RNG sequence) and returns updated `Fluctuation` + `AvergeHeight`
arrays.

**Scope decision**: Only the 1x1-only (piece_19) configuration is
handled by the kernel. Mixed-piece configurations transparently fall
back to the legacy Python dispatch. Extending the kernel to all 8
piece types is a multi-day project; scoping to 1x1 covered the entire
exp13 workload at a fraction of the engineering risk.

**Determinism**: bit-equal to legacy at `atol=1e-12`. The pre-generated
RNG arrays make the kernel itself deterministic; the `random.randint`
/ `np.random.random` draws are still consumed in the same order as
legacy.

## How to reproduce

```bash
# From repo root
python -m pip install -e '.[dev,hpc]'

# Build the golden reference once (slow, ~8 min)
python tests/build_golden_reference.py

# Run the baseline benchmark
python tests/benchmark_baseline.py --label baseline \
    --output tests/golden_reference/my_baseline.json

# Optimization sanity-check (should match the v2.0.0 numbers above
# within a few percent, depending on hardware)
cat tests/golden_reference/my_baseline.json

# Compare to canonical numbers in tests/golden_reference/phase4b_warm_timings.json
```

To force the legacy path for comparison:

```bash
TETRIS_USE_KERNEL=0 python tests/benchmark_baseline.py \
    --label legacy_audit \
    --output tests/golden_reference/legacy_audit.json
```

## Future work (estimated speedups, not yet implemented)

- **Numba kernel for all 8 piece types** (~5× on multi-piece workloads): straightforward extension; bit-equality preserved by same pre-generated-RNG-array approach.
- **Multi-surface coding** (Pagnani-Parisi 2013, ~30× on bit-packable workloads): requires recasting the dynamics as a Boolean function of a few neighbors. Not applicable to tetromino shapes (they span 2-4 columns with arbitrary relative heights).
- **GPU kernel** (~100×): every run is < 1 GB, so 1000s of independent runs fit on one GPU. Useful only if the cluster is GPU-rich AND Slurm-array CPU throughput is the bottleneck.
- **Profile-guided substrate elimination**: in kernel mode, `self.substrate` is only needed for `visualize_simulation` and `count_holes`. Add a `record_substrate=False` flag so production runs skip the substrate writes entirely (substrate write is currently ~10% of remaining runtime).
