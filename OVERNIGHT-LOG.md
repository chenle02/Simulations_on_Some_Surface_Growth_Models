# Overnight Execution Log

**Operator**: Sisyphus (OpenCode, fully autonomous)
**Start time**: 2026-05-16 11:35 EDT
**Plan**: `OVERNIGHT-PLAN.md`

---

## Phase boundaries (filled in as we go)

| Phase | Start | End | Status | Speedup | Commit | Notes |
|---|---|---|---|---|---|---|
| 0 | 11:35 EDT | 11:55 EDT | **GREEN** | n/a | 54821e4 + (next) | 9 golden refs, 12 fast tests pass, baseline locked |
| 1 | 11:55 EDT | 12:30 EDT | **GREEN** | **30.2×** on large | (next) | Incremental heights; bit-equality at atol=1e-12 (FP roundoff only) |
| 2 | 12:30 EDT | 12:45 EDT | **GREEN** | n/a (memory) | (next) | Streaming per-cell JSON + resume + atomic writes |
| 3 | TBD | TBD | pending | — | — | Slurm array |
| 4 | TBD | TBD | pending | — | — | Numba kernel |
| 5 | TBD | TBD | pending | — | — | Industrial polish |
| 6 | TBD | TBD | pending | — | — | Final report |

---

## Decisions log

### Phase 0 — Baseline & test scaffolding (2026-05-16 11:35-11:55 EDT)

**Status**: GREEN

**Decisions**:
- Used **ratio=2** (not exp13's ratio=10) for golden references → keeps each cell at most ~140s, total build < 8 min.
- Skipped the legacy `tests/` scripts (kept them on disk via `--ignore` rules in pyproject.toml). They're not pytest-shaped and modernizing them is out of scope.
- Marked L=200 cells as `slow` (skipped by default). The 12 fast tests run in 55 s, which is the right CI gate. Slow tests opt-in via `-m slow`.
- Cached test runs via `lru_cache` so each (pct,L,seed) runs once even though it's used in two tests (fluctuation + avg_height).

**Numbers**:
| Config | steps_executed | wall (s) | steps/s |
|---|---|---|---|
| small (L=50)   |  2,498 |   2.02 | 1239 |
| medium (L=100) | 10,878 |  16.68 |  652 |
| large (L=200)  | 43,064 | 140.18 |  307 |

The steps/sec dropping with L is the smoking-gun confirmation that `_UpdateStatus` is O(W·H) — Phase 1 should flatten this curve.

**Artifacts produced**:
- `pyproject.toml` (replaces setup.py soft — both will coexist until Phase 5)
- `tests/conftest.py`
- `tests/build_golden_reference.py`
- `tests/benchmark_baseline.py`
- `tests/test_simulation_correctness.py`
- `tests/golden_reference/*.npz` (9 files, 2.6 MB)
- `tests/golden_reference/baseline_timings.json`

### Phase 1 — Incremental heights array (2026-05-16 11:55-12:30 EDT)

**Status**: **GREEN** — 30× speedup, bit-equality (modulo FP roundoff)

**Strategy chosen** (Option E in my reasoning):
- Add `self.heights = np.full(width, height - 1, dtype=int64)` array, semantics matching legacy `_TopEnvelop` (row JUST ABOVE topmost occupied, or `height-1` if empty).
- Add `_surface_row(col)` as O(1) replacement for `_ffnz` (Python while-loop).
- Add `_update_heights_for_columns(cols)` helper that re-syncs heights for a small column slab via vectorized `np.argmax` (O(piece_cols × H) per call vs O(W × H) for legacy `_TopEnvelop`).
- Replace `_UpdateStatus` with `self.heights.std()` / `.mean()`.
- **Did NOT** touch any `_Place_*` method — keeps the substrate-write logic intact for legacy/visualization compatibility. The heights sync happens AFTER `_Place_*` in `Update_*`, before `_UpdateStatus`.

**Mechanical edits** (via a Python script — minimized hand-coding risk):
- 90 `self._ffnz(...)` → `self._surface_row(...)` (in Update_* methods)
- 8 `self._UpdateStatus(i)` → `self._update_heights_for_columns(...); self._UpdateStatus(i)`
- Range used: `range(max(0, position - 3), min(self.width, position + 4))` — uniform 7-column window safely covers every piece (verified against the 32 _Place_* substrate-write cases). Slight over-scan vs minimal exact set, but correctness over micro-optimization.

**Bit-equality outcome**:
- `AvergeHeight`: bit-identical (`atol=0.0`) — same `np.mean` algorithm both paths.
- `Fluctuation`: differs by ~1e-15 (FP roundoff) — legacy used a Python for-loop `sum((x-mean)^2 / W)` then `sqrt`; Phase 1 uses `np.std()`. Same population-std formula, different summation order. Relaxed tolerance to `atol=1e-12` with the rationale committed in the test docstring.

**Benchmark**:

| Config         | Baseline (steps/s) | Phase 1 (steps/s) | Wall-clock |   Speedup |
|----------------|---------------------|--------------------|------------|-----------|
| small  (L=50)  |              1,239  |             8,847  |  2.0→0.28s |    **7.1×** |
| medium (L=100) |                652  |             9,342  | 16.7→1.16s |   **14.3×** |
| large  (L=200) |                307  |             9,266  | 140.2→4.65s| **30.2×** |

**Key observation**: steps/sec is now **flat across L** (~9000 regardless of L), confirming we eliminated the O(W·H) per-step term. The remaining bottleneck is the dispatch + landing-row computation (Python class-method calls), which is the Phase-4 (numba) target.

**Test suite timing**:
- Fast tests: 55s → 5.3s (10× — they run the medium configs)
- Slow tests (L=200, 3 seeds): NEW capability, ran in 16.4s — at baseline this would have been ~7 minutes.

### Phase 2 — Streaming analysis (2026-05-16 12:30-12:45 EDT)

**Status**: **GREEN** — all 20 fast tests pass.

**What changed**:
- Added `_atomic_write_json` (write-tmp + rename) for crash-safe per-cell writes.
- Added `_cells_dir`, `_cell_path`, `_per_pct_path` helpers (consistent layout in `<exp>/kpz_cells/`).
- Added `aggregate_results(exp_dir)` that stream-collects per-pct JSON files.
- Modified `main()` to write per-cell + per-pct JSON immediately after computing each, then stream-aggregate at the end.
- Added `--resume` flag (skip cells whose JSON exists) and `--aggregate-only` (rebuild results.json from existing per-pct JSON without re-computation).

**Why this matters for HPC scaling**: At 10K cells, the old in-memory `all_results` dict would have grown to several GB (each cell stores eval_log_t + slope_med + slope_lo + slope_hi arrays of length ~150 each in JSON form). Writing per-cell + aggregating once at the end caps in-flight memory at one per-pct dict.

**Resumability verified**: ran the pipeline twice on exp13/pct=90 — second run loaded both cells from `kpz_cells/` and produced identical β∞ without re-computing anything.

**Tests added** (`tests/test_streaming_analysis.py`, 8 pure-unit tests, 1.35 s total):
- atomic write leaves no .tmp on success
- atomic write creates parent dirs
- cell/per_pct path formats stable
- aggregate handles empty dir
- aggregate handles multi-pct
- aggregate ignores per-cell files (only per_pct)
- atomic write overwrites existing

