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
| 3 | 12:45 EDT | 13:10 EDT | **GREEN** | n/a (HPC) | (next) | run_one_cell + grid.yaml + job_array.slurm + 12 tests |
| 4a | 13:10 EDT | 13:20 EDT | **GREEN** | **47×** total | (next) | Cached sampling CDF (no numba needed) |
| 4b | 13:20 EDT | 13:40 EDT | **GREEN** | **380×** total | (next) | @njit kernel for 1x1 piece path (warm) |
| 5 | 13:40 EDT | 14:05 EDT | **GREEN** | n/a | (next) | CI, ruff, README + CHANGELOG, v2.0.0 |
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

### Phase 3 — Slurm-array entry point (2026-05-16 12:45-13:10 EDT)

**Status**: **GREEN** — 12 tests (10 fast + 2 slow e2e), Slurm template parses.

**What shipped**:
- `tetris_ballistic/scripts/run_one_cell.py`: argparse-driven single-cell runner with `--task-id` for Slurm-array, `--list-grid` for inspection, `--flat-output` for legacy compatibility.
- `experiments/templates/grid.yaml`: documented template with iteration-order spec.
- `experiments/templates/job_array.slurm`: complete Auburn-Easley-targeted Slurm submission script.

**Key design choices**:
- Iteration order = **pct outermost, seed innermost**. Consecutive task IDs share the same (pct, L) ensemble, so a small `--array=0-9` gives one complete 10-seed ensemble (useful for quick smoke tests on the cluster).
- Output layout: hierarchical `pct_NN/L_LLLL/seed_SSS.joblib` (avoids the 10K-files-in-one-dir filesystem-metadata pressure that bit exp13).
- `--flat-output` preserves the legacy `config_*_w=*_seed=*.joblib` flat layout for back-compat.
- Idempotent: re-running an existing cell is a no-op. Safe for Slurm preemption / re-queue.
- Atomic writes via `.tmp + rename` pattern (same as Phase 2).

**Verification**:
- Local 3-task dry-run produced 3 joblib + 3 yaml files in the expected layout.
- `bash -n job_array.slurm` clean.
- `test_run_cell_consistent_with_direct_construction` proves the runner wraps `Tetris_Ballistic.Simulate()` without drift (bit-identical Fluctuation + AvergeHeight to direct construction).

**Tests added** (`tests/test_run_one_cell.py`, 12 tests):
- Fast (10 tests, 1.22 s): grid spec parsing, decode_task_id (worked-example regression test), build_density for known + unknown configs, path layout (hierarchical + flat).
- Slow (2 tests, 1.45 s): e2e cell run + idempotent re-run; bit-equality vs direct construction.

**Bug found + fixed during testing**: my initial test assumed `Fluctuation.shape == (steps,)` always; in reality `Simulate()` trims the array to `FinalSteps` on early game-over. Test updated to accept either shape.

### Phase 4 decision-gate profile (2026-05-16 13:10 EDT)

`cProfile` on Phase-1 L=200 run revealed:

| Function | % of runtime |
|---|---|
| Update_1x1 (dispatch + landing-row) | 58% |
| **Sample_Tetris (piece sampling) ★** | **40%** |
| _UpdateStatus (std + mean) | 29% |
| _update_heights_for_columns | 22% |
| np.std internals | 19% |

**Huge surprise**: `Sample_Tetris` was 40% of runtime. The legacy code rebuilt the 40-element probability vector from `self.config_data` on EVERY step + called `np.random.choice(40, p=...)`. Most of this work could be cached. This made Phase 4a (no numba) a low-hanging fruit BEFORE the Phase-4b numba kernel.

### Phase 4a — Cached sampling CDF (2026-05-16 13:10-13:20 EDT)

**Status**: **GREEN** — bit-equality preserved (modulo FP roundoff), additional ~2× speedup.

**Change**: Cache the normalized probability vector + cumulative sum (CDF) in `__init__`. `Sample_Tetris` now does `np.searchsorted(self._sample_cdf, np.random.random())` — a single Python call to vectorized C code, vs the legacy `[self.config_data[f"Piece-{i}"] for i in range(20)] → np.array → flatten → normalize → np.random.choice` chain.

**Bit-equality surprise**: I expected this to break bit-equality because the random-number-consumption pattern changes. It didn't. Reason: `np.random.choice(40, p=p)` internally implements `np.searchsorted(cumsum(p), np.random.uniform())` — same RNG draw, same algorithm, just exposed at a different API level. So the trajectory is byte-identical.

**Benchmark**:

| Config | Phase 0 | Phase 1 | Phase 4a | Cumulative |
|---|---|---|---|---|
| small (L=50) | 1,239 | 8,847 | **17,494** | **14.1×** |
| medium (L=100) | 652 | 9,342 | **16,834** | **25.8×** |
| large (L=200) | 307 | 9,266 | **14,436** | **47.0×** |

Wall-clock for the large config: 140s → 2.98s.

All 30 fast tests + 3 slow tests pass.

### Phase 4b — @njit kernel for 1x1 fast path (2026-05-16 13:20-13:40 EDT)

**Status**: **GREEN** — 380× warm speedup, bit-equality preserved within FP roundoff.

**Scope decision**: kernel handles ONLY the piece_19-only configuration (the exp13 setup). For mixed-piece configurations the orchestrator transparently falls back to the legacy Python dispatch. Extending to all 8 piece types is a multi-day project; scoping to 1x1 captures the entire exp13 workload at a fraction of the engineering risk.

**Architecture**:
- `tetris_ballistic/_kernel_1x1.py`: `@njit(cache=True)` kernel that takes pre-generated `positions` + `sticky_flags` arrays and runs the full 1x1 simulation loop in C-level numba. Includes inline `_surface_row` semantics + heights update + std/mean computation (all kept in C-loop form so the kernel never re-enters Python).
- `is_1x1_only(config_data)`: detection helper.
- `Tetris_Ballistic.Simulate`: dispatches to `_simulate_1x1_kernel` orchestrator when `is_1x1_only` is True, else legacy path.
- `_simulate_1x1_kernel`: orchestrator that pre-generates the (positions, sticky_flags) arrays using the SAME RNG sequence the legacy code would consume, then calls the JIT kernel. This preserves bit-equality.
- Environment variable kill switch: `TETRIS_USE_KERNEL=0` forces the legacy path (for audit / debug).

**RNG contract** (the trickiest design decision):
- Legacy: `Sample_Tetris` calls `np.random.random()` (via `np.searchsorted` after Phase 4a) → derives sticky_flag from `sample_index % 2`. Then `Update_1x1` calls `random.randint(0, width-1)` (stdlib) for position. The kernel must consume the same RNG draws in the same order.
- Implementation: the orchestrator loop generates `np.random.random()` AND `random.randint(0, width-1)` for each step UPFRONT (interleaved exactly as legacy would), packs them into two arrays, then calls the kernel. No RNG draws happen inside the kernel — `@njit` doesn't even see `random` or `np.random`.

**Benchmark — warm (JIT amortized via small pre-run)**:

| Config        | Phase 0 | Phase 4b warm | Cumulative |
|---------------|---------|---------------|------------|
| small  (L=50) |   1,239 |  **105,148**  |    **85×** |
| medium (L=100)|     652 |  **118,940**  |   **182×** |
| large  (L=200)|     307 |  **116,576**  |   **380×** |

Wall-clock for large: 140s → 0.37s. Steps/sec is flat across L at ~115K — same as Phase 1 (flat) but at a 12× higher absolute throughput.

**Benchmark — cold (subprocess, includes JIT compile)**:

| Config        | Cold steps/s | Speedup |
|---------------|--------------|---------|
| small  (L=50) |  6,150       |  5×     |
| medium (L=100)| 110,403      | 169×    |
| large  (L=200)| 113,573      | 370×    |

Cold-call JIT cost is ~0.3s, amortized over any non-trivial workload. For Slurm-array tasks running one big simulation, cold = warm essentially.

**Test outcomes**:
- All 30 fast tests + 3 slow tests pass.
- Fast suite: 4.11s → **1.83s** (2.2× faster gate).
- Slow suite: 10.6s → **2.82s** (3.8× faster).
- Bit-equality preserved at `atol=1e-12` (the same FP-roundoff bound established in Phase 1).

### Phase 5 — Industrial polish (2026-05-16 13:40-14:05 EDT)

**Status**: **GREEN** — pytest + ruff both clean.

**Shipped**:
- `.github/workflows/ci.yml`: pytest + ruff on every push/PR, Python 3.10/3.11/3.12 matrix.
- `pyproject.toml`: ruff config with per-file ignores documenting legacy debt with a clean ratchet-down strategy.
- `CHANGELOG.md`: complete v2.0.0 release notes.
- `README.md`: new "Performance" section with the 85/182/380× table, new "HPC usage" section with Slurm-array recipe, new CI badge.
- Version bump: `1.2.7` → `2.0.0` (major: introduces optional numba dep, changes the inner-loop algorithm, adds new public API surface).

**Lint status**:
- New code (`_kernel_1x1.py`, `scripts/`, `kpz_analysis.py`, new tests): ruff-clean, no per-file ignores.
- Legacy code (`tetris_ballistic.py`, `data_analysis_utilities.py`, etc.): per-file ignores documenting each suppressed rule. Ratchet-down strategy: remove entries from the list as files are refactored.

**Tests**: 33 fast tests pass in 2.07s. 5 slow tests pass in ~3s.

