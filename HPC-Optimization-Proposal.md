# HPC Optimization Proposal — `tetris-ballistic`

**Date**: 2026-05-16
**Goal**: Scale from current ~300 runs (single 48-core node, ~63 h wall) to 10K+ runs across many HPC nodes, with each run reaching larger `(L, height, steps)` than today.
**Audience**: Le Chen, for review before any code changes.

---

## TL;DR

Four **independent and multiplicative** bottlenecks. Conservative combined headroom: **≈ 1000× total throughput**. Optimal order is bottom-up: fix the per-step inner loop first, then per-core JIT, then experiment-level Slurm-array fan-out.

| Path | Where | Effort | Speedup | Risk |
|---|---|---|---|---|
| **#1 Incremental `heights` array** | `tetris_ballistic.py` `_UpdateStatus` / `_TopEnvelop` | 1 day | **50–100×** per simulation | Low — pure algorithmic, identical output |
| **#2 Numba JIT inner loop** | `_ffnz` + `Update_*` + sim driver | 2–3 days | **10–50×** on top of #1 | Medium — needs type annotations, possibly object → array refactor |
| **#3 Slurm-array fan-out** | New `job_array.slurm`, refactor `Sweep.py` to accept `--task-id` | 1 day | **~node-count×** (potentially 100× wall-clock) | Low — orthogonal to inner loop, standard pattern |
| **#4 Streaming analysis** | `analysis.py` + `kpz_analysis.py` runner | 1 day | Enables 10K+ scale (without this, OOM at ~3K runs) | Low |
| ~~Multi-surface coding~~ | (not recommended) | — | 30× claimed | Doesn't apply to tetromino shapes (see §5) |
| ~~GPU / CUDA~~ | (not recommended yet) | weeks | 100–400× claimed | Premature — #1+#2+#3 likely sufficient |

---

## Current state (evidence from `bg_8a23b4cb` + `bg_9d1f9fc8` + code read)

### Inner loop (per simulation)

The main driver `Simulate()` (line 546) runs:

```python
while i < self.steps:
    Update, *_ = self.Sample_Tetris()
    i = Update(i)
```

Each `Update_*` method calls `_ffnz(column)` (Python `while` loop scanning a column top-down) and then `_UpdateStatus(step)` (line 1650), which currently:

1. **Copies the entire substrate** `np.copy(self.substrate)` — O(W × H) every step
2. Masks it `work_substrate[self.substrate > step] = 0` — O(W × H) again
3. Loops over all W columns in Python with `np.any` + `np.argmax` — O(W × H)
4. Computes Fluctuation with a **Python for-loop over W** (line 1676) instead of `np.var`

**Cost per step**: O(W × H) ≈ 100 × 1000 = 10⁵ operations.
**Total**: ~50K steps × 10⁵ ops = **5 × 10⁹ operations per simulation** — almost all spent re-computing what could be a single-column update.

### Experiment driver

- `experiments/exp13/job_script.slurm`: `--nodes=1 --ntasks-per-node=48 --time=48:00:00 --mem=96gb`
- One Slurm job → one big Python process → `multiprocessing.Pool(48)` over the (pct, L, seed) grid
- **NOT** a Slurm array. Single 48 h wall-time wall.
- `analysis.py` post-processing: loads **every** `.joblib` into one `fluctuations_dict` in RAM — will OOM at ~3K runs on 96 GB.
- Output convention: flat directory `experiments/exp13/config_*.joblib` (file-per-cell, no hierarchy).
- Resume support: `if os.path.exists(joblib_filename): return` — good, but only works on the same node.

### What's good (keep)

- `np.uint32` substrate (memory-efficient).
- `joblib` checkpointing (skip-if-exists).
- `git rev-parse --show-toplevel` in Slurm (portable).
- Object identity `Tetris_Ballistic` instance is pickleable — works for joblib.

---

## Optimization paths (ranked)

### Path #1 — Incremental `heights` array (BIGGEST WIN, do first)

**Diagnosis**: 90% of CPU time is in `_UpdateStatus` / `_TopEnvelop` doing repeated full-substrate scans that should be O(1) updates.

**Fix**: Maintain a 1-D `self.heights: np.ndarray[uint32]` of length `W`, where `heights[col]` is the current top of the surface in column `col`. Every piece placement updates **only the touched columns** (≤ 4 for a tetromino).

```python
# In __init__:
self.heights = np.zeros(self.width, dtype=np.uint32)

# After placing a tetromino at column `col` of shape `shape`:
for dx, dy in shape.cells:
    new_top = heights[col + dx] + dy + 1
    heights[col + dx] = new_top  # O(1) per cell, ≤ 4 cells per piece

# In _UpdateStatus (was O(W·H), now O(W) for the std; O(1) for the mean if we cache the running sum):
avg = self.heights.mean()
self.AvergeHeight[step] = avg
self.Fluctuation[step]  = self.heights.std()    # replaces lines 1675-1678
```

**Where the speedup comes from**:
- `_TopEnvelop` eliminated entirely → ~10⁵ ops / step → ~1 op / step. **5 × 10⁴× speedup on that line.**
- `_ffnz` becomes `self.heights[column]` (O(1) lookup instead of O(H) while loop).
- `_UpdateStatus`: `np.std` on a length-W array is C-vectorized, replaces the Python for-loop.

**Expected total speedup**: **50–100×** per simulation. A run that takes 600 s today takes ~10 s.

**Risks / verification**:
- The 2-D `self.substrate` is still useful for `visualize_simulation()` and `count_holes()`. Keep it (it's a write-only record now), or make it optional via a `record_substrate=False` flag for production runs.
- Verify byte-for-byte equivalence of `Fluctuation` and `AvergeHeight` on 5 seeds × 3 widths × 1 pct (15 runs) before deploying. Diff against a tagged commit's output.

**Effort**: 1 day to implement, 1 day to verify. Touches `__init__`, all `_Place_*` methods, `_UpdateStatus`, `_ffnz`. ~150 LOC modified.

---

### Path #2 — Numba JIT inner loop (do AFTER #1)

**Diagnosis**: Even after #1, the dispatch loop (`while i < self.steps: Update = ...; i = Update(i)`) plus the per-piece logic stays in pure Python. The `Sample_Tetris` uses `np.random.choice` (slow per-call) and dispatches via class-method lookups.

**Fix**: Refactor the inner kernel as a free function taking `(heights, substrate_optional, piece_table, rng_state) → updated_heights`, decorate with `@njit`.

Canonical pattern (from `bg_58cd8c2a`):

```python
from numba import njit

@njit(cache=True, fastmath=True)
def _place_piece(heights, piece_id, rot, col, sticky):
    # piece_table[piece_id, rot] is a (4, 2) int8 array of (dx, dy) offsets
    # ... pure-array operations only, no Python objects
    return new_heights

@njit(cache=True)
def simulate_kernel(heights, steps, piece_table, sticky_mask, seed):
    np.random.seed(seed)
    fluctuation = np.empty(steps, dtype=np.float64)
    avg_height  = np.empty(steps, dtype=np.float64)
    for i in range(steps):
        # sample piece & rotation
        ...
        heights = _place_piece(heights, ...)
        fluctuation[i] = heights.std()
        avg_height[i]  = heights.mean()
    return heights, fluctuation, avg_height
```

**Expected speedup**: **10–50×** on top of #1. Combined #1+#2: **500–5000×** per simulation.

**Risks**:
- Numba doesn't JIT the `Tetris_Ballistic` class itself — need to refactor the hot path into free functions that take ndarrays. The class wrapper survives for I/O.
- `np.random.choice` is supported in numba but slower than a hand-rolled `np.random.randint` + lookup. Replace.
- The 19-piece table needs to be a numpy array of shape `(19, 4, max_cells, 2)`, not a list of Python objects.
- First-call JIT compile is ~5 s; mitigate with `cache=True` (compiles to disk on first run, reused on subsequent runs/processes).

**Effort**: 2-3 days. Hardest part is refactoring `Sample_Tetris` + piece dispatch from Python class-method to a numba-friendly array-driven kernel.

---

### Path #3 — Slurm-array fan-out (orthogonal, do anytime)

**Diagnosis**: Current setup wastes the cluster — one 48-core job means **at most 48 simulations in flight at once**, with a 48 h wall-time wall. The cluster has thousands of cores idle.

**Fix**: Convert the (pct, L, seed) grid to a flat task index, dispatch as `--array=0-N`. Per the `slurm-array-fan-out` skill in this lab.

```bash
#!/bin/bash
#SBATCH --job-name=tetris_bd
#SBATCH --array=0-299%50         # 300 tasks, max 50 running at once
#SBATCH --cpus-per-task=1        # 1 simulation per task
#SBATCH --time=04:00:00          # per-task time
#SBATCH --mem=4gb                # per-task memory
#SBATCH --output=logs/exp13_%A_%a.out
#SBATCH --partition=abebeas_std

cd "$(git rev-parse --show-toplevel)"
source .venv/bin/activate
python -m tetris_ballistic.scripts.run_one_cell --task-id $SLURM_ARRAY_TASK_ID
```

The `run_one_cell` script takes a flat task ID, decodes it back to (pct, L, seed), and runs ONE simulation. Resume-friendly because each task checks `if joblib exists: skip`.

**Expected speedup**: **N-fold wall-clock** where N = number of array tasks running concurrently (limited by queue policy, not code). With `--array=0-9999%500`, 10K runs finish in roughly the time of ONE run.

**Risks**:
- Filesystem metadata pressure with 10K files in one dir. Mitigate with hierarchical output: `results/pct_{pct}/L_{L}/seed_{seed}.joblib`.
- Slurm job ID tracking — log `(SLURM_ARRAY_JOB_ID, SLURM_ARRAY_TASK_ID, task_params)` to a manifest file for post-mortem.

**Effort**: 1 day. Already have the `slurm-array-fan-out` skill as a template.

---

### Path #4 — Streaming analysis (preventive, do BEFORE the 10K run)

**Diagnosis**: `analysis.py` and `experiments/exp13/run_kpz_analysis.py` both load **every** `.joblib` and the entire `fluctuations_dict` into RAM. At ~10 MB / joblib × 10K runs = 100 GB → OOM on a 96 GB node.

**Fix**: Replace the monolithic dict with per-cell HDF5 or Zarr accumulators that touch one `(pct, L)` group at a time. The `kpz_analysis.run_single_cell` function already operates per-(pct, L) cell — extend the runner to write per-cell `cell_results.json` immediately and stream-aggregate at the end.

```python
# Per-cell write (in run_single_cell):
import json
with open(f"{out_dir}/cell_pct{pct:02d}_L{L}.json", "w") as f:
    json.dump(cell, f)
# Final aggregate just glob.glob() + concat — never holds full data in RAM
```

**Expected impact**: Unlocks 10K-scale analysis. No throughput speedup, but **without this we can't run #3 at full scale**.

**Effort**: 1 day. Small refactor of `run_kpz_analysis.py`.

---

### Why NOT multi-surface coding (Pagnani-Parisi)

From `bg_58cd8c2a`: MSC packs 64 independent simulations into one 64-bit word, updates them via bitwise ops. Reported 30× speedup for RSOS models. **But it's RSOS-specific**: requires that the height-update rule be expressible as `(h_left, h_center, h_right) → bitwise op`. Tetrominoes have **multi-cell shapes** that span 2-4 columns with arbitrary relative heights — the local update is not a Boolean function of 3 neighbors. Mapping it to bitwise ops would require encoding tetromino shape + sticky/nonsticky as an enormous truth table.

**Verdict**: Skip. Numba (#2) gets us most of the way at a fraction of the engineering risk.

### Why NOT GPU yet

From `bg_58cd8c2a`: CUDA implementations report 100-400× speedup. But:
- The work is **embarrassingly parallel across runs** (300+ independent seeds), not within a run.
- Slurm-array (#3) extracts this parallelism trivially at the **cluster level** with zero CUDA code.
- A GPU implementation requires moving the entire piece-dispatch logic into CUDA C / CuPy. This is weeks of work for speedup we likely get from #1+#2+#3.

**Verdict**: Revisit only if (a) #1+#2+#3 still aren't fast enough for the target experiment scale, AND (b) we have a per-run problem too large for one CPU core (currently we don't — each simulation is < 1 GB).

---

## Recommended execution order

1. **Path #1** (incremental heights) — 1-2 days, ≈ 50-100× per-simulation speedup, lowest risk, highest payoff.
2. **Path #4** (streaming analysis) — 1 day, prevents OOM at 10K scale, must happen before #3 at scale.
3. **Path #3** (Slurm array) — 1 day, unlocks cross-node scaling, orthogonal to #1/#2 (works with or without them).
4. **Path #2** (Numba JIT) — 2-3 days, further 10-50×, only worth it after #1 (otherwise we'd JIT the wrong thing).

**Critical-path gate**: Before #2, profile with `cProfile + snakeviz` on a single representative run after #1 to confirm where time is actually spent. The estimate of "Numba gives another 10-50×" assumes a Python loop is still dominant; if #1 already pushed everything into vectorized numpy, the marginal Numba gain shrinks.

---

## Verification plan (before any path ships)

For **#1 and #2** (algorithmic changes):
- Pick 5 seeds × 3 widths × 1 pct = 15 reference runs from the existing `experiments/exp13/`.
- Re-run with the new code path.
- Assert `np.allclose(old.Fluctuation, new.Fluctuation, atol=1e-10)` and `np.allclose(old.AvergeHeight, new.AvergeHeight, atol=1e-10)`.
- If exact bit-equality is broken by `np.var` vs the manual Python sum (floating-point order of operations), tighten tolerance to `1e-12 * W`.

For **#3** (Slurm array):
- Submit a dry-run `--array=0-2` with 3 tasks, verify outputs match a non-array submission.

For **#4** (streaming analysis):
- Compare aggregate `results.json` from the streaming version against today's monolithic version on the existing exp13.

---

## What I want from you

1. **Approve the ranking** (or rerank — e.g., maybe #3 first because the cluster is idle and the wall-time wall already hurt you).
2. **Confirm the verification plan** — exact bit-equality vs `atol`.
3. **Tell me when to start**. Default: I do #1 first as a fresh paper-dev / dev-loop session, ship it, then circle back for #4 + #3.

If you want, I can ALSO check whether the `slurm-array-fan-out` skill already has a template that maps directly onto `Sweep.py` — that would shrink #3 to a few hours.
