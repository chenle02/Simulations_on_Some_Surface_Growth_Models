# Overnight Industrial-Grade Optimization — Detailed Plan

**Authorized**: 2026-05-16 by Le Chen
**Operator**: Sisyphus (OpenCode, fully autonomous, commit+push, best-judgment defaults)
**Repo**: `chenle02/Simulations_on_Some_Surface_Growth_Models` @ `main`
**Reference proposal**: `HPC-Optimization-Proposal.md` (4 paths ranked)
**Final deliverable**: Industrial-grade `tetris_ballistic` package with full test coverage, ≥100× single-simulation speedup, Slurm-array HPC entry point, streaming analysis, CI on GitHub.

---

## Operating principles (binding)

1. **Correctness is non-negotiable.** Every optimization PHASE must pass a bit-equality (or documented `atol`) test against the **Phase-0 golden reference** before commit.
2. **Atomic commits.** One commit = one logically reviewable change with passing tests. Push after each green phase.
3. **Best-judgment defaults.** Where the plan doesn't specify, choose what an industrial codebase would do (typed, tested, documented, CI-gated). Don't ask.
4. **Rollback rule.** If verification fails twice in a row inside one phase: `git reset --hard` to the last green commit, log the failure in `OVERNIGHT-LOG.md`, skip that phase, continue with the next independent phase.
5. **Stall rule.** If a phase exceeds 3 hours of wall time, abort that phase, log it, continue.
6. **No premature push.** Push only after `pytest` is green AND benchmarks ran cleanly. Otherwise the commit is local until fixed.
7. **No interactive prompts.** No `input()`, no `git commit` editor sessions, no prompted pip installs. Everything scripted.
8. **Document everything.** `OVERNIGHT-LOG.md` is the durable record. Every phase appends timing, decisions, deviations.

---

## Snapshot of starting state (2026-05-16 11:30 EDT)

- Branch: `main` @ `c5a453c`
- Remote: `origin` clean (no diverged commits)
- Tests: `tests/` exists but is NOT a pytest layout — it's a directory of standalone `test_*.py` scripts. **No `pytest` installed.** No `pyproject.toml`.
- Package: `setup.py`, version `1.2.7`, no `extras_require[hpc]`.
- Hot path: `tetris_ballistic/tetris_ballistic.py` (2365 LOC), bottleneck in `_UpdateStatus`/`_TopEnvelop` (line 1629-1678).
- Downstream consumers: only `obj.Fluctuation` and `obj.AvergeHeight` matter for KPZ analysis. `obj.substrate` is needed only for `visualize_simulation()` + `count_holes()`, NOT the hot path.
- Slurm: 1 monolithic job, `multiprocessing.Pool(48)`, no `--array`, will OOM in `analysis.py` at >3K runs.

---

## Phase 0 — Baseline & test scaffolding (foundational, 90 min budget)

**Goal**: Lock down "what is correct" and "what is fast NOW" so every later phase has a deterministic gate.

### 0.1 Install dev tooling
```bash
.venv/bin/pip install pytest pytest-benchmark numba
```
- pytest for the test gate
- pytest-benchmark for speedup numbers
- numba for Phase 4 (install now to avoid breaking the env later)

### 0.2 Create pytest infrastructure
- `pyproject.toml` (new): packaging metadata, pytest config, ruff/black config
- `tests/conftest.py`: pytest fixtures for golden references
- `tests/test_simulation_correctness.py`: bit-equality tests vs golden references
- `tests/test_simulation_performance.py`: benchmark suite (skipped unless `--benchmark`)
- Migrate the **existing** standalone `tests/` scripts into the pytest layout as separate `test_legacy_*.py` (preserve them, don't delete)

### 0.3 Capture the golden reference
**Reference grid**: 1 piece (piece_19) × 1 pct (50%) × 3 widths (50, 100, 200) × 3 seeds (0, 10, 20) = **9 runs**, deterministic, ~1 minute total.

```python
# tests/golden_reference/build_reference.py
# Runs 9 simulations with the CURRENT (pre-optimization) code,
# saves obj.Fluctuation and obj.AvergeHeight as .npz per cell.
```

Output: `tests/golden_reference/pct50_L{50,100,200}_seed{0,10,20}.npz` (9 files, ~few KB each, tracked in git).

### 0.4 Capture the baseline timing
```python
# tests/benchmark_baseline.py
# Runs 3 representative configs:
#   - (L=50,  steps=12_000)  → tiny
#   - (L=100, steps=50_000)  → medium
#   - (L=200, steps=200_000) → large
# Records wall time + steps/sec to baseline_timings.json
```

Output: `tests/golden_reference/baseline_timings.json`. This becomes the speedup denominator.

### 0.5 Gate
- All 9 golden runs complete without error
- All baseline timings recorded
- `pytest tests/test_simulation_correctness.py` is GREEN (verifies the reference loader round-trips)
- **Commit + push**: `test: phase 0 — golden reference + baseline timings`

---

## Phase 1 — Incremental heights array (the BIG win, 150 min budget)

**Goal**: Eliminate the per-step O(W×H) `_TopEnvelop` + `_UpdateStatus` overhead. Expected speedup: **50-100×** per simulation.

### 1.1 Add `self.heights` to `__init__` and `reset`
- New attribute: `self.heights: np.ndarray[uint32]` shape `(width,)`, initialized to 0
- Semantics: `heights[col]` = number of occupied cells in column `col`, equivalently the row-index of the next empty cell from the bottom IF the substrate were stored bottom-up. **But** the substrate uses TOP-DOWN indexing (row 0 = top, `height-1` = bottom). So `heights[col]` represents "stack height" and the corresponding substrate row is `height - 1 - (heights[col] - 1) = height - heights[col]`.

### 1.2 Add a fast `_ffnz` replacement
```python
def _surface_row(self, col):
    """Row index of topmost occupied cell, or self.height if empty.
    Equivalent to _ffnz(col) but O(1)."""
    if self.heights[col] == 0:
        return self.height
    return self.height - self.heights[col]
```

### 1.3 Wrap all `_Place_*` methods to update `heights` AFTER substrate writes
For each of the 8 `_Place_*` methods (`_Place_O`, `_Place_I`, `_Place_L`, `_Place_J`, `_Place_T`, `_Place_S`, `_Place_Z`, `_Place_1x1`):
- After the existing substrate writes, recompute `self.heights[touched_col] = self.height - min(touched_row_indices)`
- The touched columns and minimum row indices are local — no full scan needed
- Cost: O(piece_cells) ≈ O(4) per placement

### 1.4 Replace `_UpdateStatus` and `_TopEnvelop` on the hot path
```python
def _UpdateStatus(self, step):
    self.AvergeHeight[step] = self.heights.mean()
    self.Fluctuation[step]  = self.heights.std()
```
- Keep the old methods around (don't delete) but add a flag `self._fast_stats = True` in `__init__`; the old `_TopEnvelop` becomes a `_legacy_TopEnvelop` for visualization-only use
- This is O(W) for std, O(W) for mean — vs O(W·H) before. For W=200, H=3000: **3000× per-step**

### 1.5 Wire `Update_*` to use the fast `_ffnz` replacement
- Replace every `self._ffnz(col)` call inside `Update_*` methods with `self._surface_row(col)`
- This eliminates the inner Python while-loop

### 1.6 Test
```bash
pytest tests/test_simulation_correctness.py -v
```
- All 9 golden reference comparisons must pass with `atol=0.0` (bit-equality)
  - **Note**: `self.heights.std()` uses N-divisor (population std). The legacy code uses `sqrt(sum((x-mean)^2) / W)` = population std. Same formula → bit-equal.
- If `atol=0.0` fails: tighten to `atol=1e-12 * W` and document why

### 1.7 Benchmark
```bash
.venv/bin/python tests/benchmark_phase1.py
```
- Run the same 3 representative configs
- Compute `speedup = baseline_time / phase1_time`
- Append to `OVERNIGHT-LOG.md`

### 1.8 Gate
- All golden tests GREEN
- Speedup ≥ 30× on the largest config (sanity floor)
- **Commit + push**: `perf(sim): incremental heights array (Phase 1, NN× speedup)`

### 1.9 Rollback if needed
If gate fails: `git checkout HEAD -- tetris_ballistic/tetris_ballistic.py`, log failure, skip to Phase 2.

---

## Phase 2 — Streaming analysis (memory-bound prevention, 60 min budget)

**Goal**: Replace `analysis.py` and the existing `run_kpz_analysis.py` monolithic load with per-cell streaming so 10K-run experiments don't OOM.

### 2.1 Modify `kpz_analysis.load_ensemble`
- Add an optional `lazy=True` mode that loads one joblib at a time and yields, instead of building a list
- Existing eager mode preserved for back-compat

### 2.2 Modify `run_kpz_analysis.py`
- After each `run_single_cell`, immediately write `cell_pct{pct:02d}_L{L}.json` to disk
- Final aggregation just `glob.glob()` + concat — never holds full dataset in RAM

### 2.3 Test
```bash
pytest tests/test_streaming_analysis.py
```
- Run streaming version on exp13 (9-cell subset)
- Compare to existing `results_2026-05-16.json` snapshot — must be bit-equal modulo dict key order

### 2.4 Gate
- Streaming matches monolithic
- Peak RSS during streaming is < 500 MB even with 30 cells (measure with `resource.getrusage`)
- **Commit + push**: `perf(analysis): streaming per-cell aggregation (Phase 2)`

---

## Phase 3 — Slurm array fan-out (HPC orchestration, 90 min budget)

**Goal**: Turn one monolithic Slurm job into 10K+ array tasks.

### 3.1 Create `tetris_ballistic/scripts/run_one_cell.py`
- Takes `--task-id N --grid-spec grid.yaml` (or `--pct P --L L --seed S` directly)
- Resumable: if output joblib exists, exit 0 silently
- Atomic: write to `.tmp`, then rename

### 3.2 Create `tetris_ballistic/scripts/expand_grid.py`
- Helper to enumerate `(piece, pct, L, seed)` combos → flat list of task IDs
- `grid.yaml` is the source of truth for the experiment

### 3.3 Create `experiments/templates/job_array.slurm`
```bash
#SBATCH --job-name=tetris_bd
#SBATCH --array=0-299%50
#SBATCH --cpus-per-task=1
#SBATCH --time=04:00:00
#SBATCH --mem=4gb
#SBATCH --output=logs/exp_%A_%a.out
#SBATCH --partition=abebeas_std
...
python -m tetris_ballistic.scripts.run_one_cell \
    --task-id $SLURM_ARRAY_TASK_ID \
    --grid-spec $GRID_SPEC
```

### 3.4 Hierarchical output
- Default output path: `experiments/<exp_name>/results/pct_{pct}/L_{L}/seed_{seed}.joblib`
- Backward-compatible flag `--flat-output` for legacy exp13 layout

### 3.5 Test
```bash
# Dry-run: 3 tasks
for tid in 0 1 2; do
    .venv/bin/python -m tetris_ballistic.scripts.run_one_cell \
        --task-id $tid --grid-spec tests/test_grid_tiny.yaml \
        --out-dir /tmp/test_array
done
# Compare outputs to a non-array run on the same 3 cells
pytest tests/test_slurm_array_compat.py
```

### 3.6 Gate
- 3-task local dry-run produces bit-equal outputs to non-array reference
- `job_array.slurm` passes `sbatch --test-only` (parse check, doesn't actually submit)
- **Commit + push**: `feat(hpc): Slurm-array entry point (Phase 3)`

---

## Phase 4 — Numba JIT (further 10-50×, 180 min budget)

**Goal**: Refactor the inner kernel into a numba-jittable free function. This is the highest-risk phase because the dispatch logic is heavy on Python class methods.

### 4.1 Decision point at phase start
Profile the Phase-1 code with `cProfile`. If `_Place_*` + `Update_*` + `Sample_Tetris` collectively account for <30% of remaining runtime → **SKIP Phase 4** (Numba would optimize a non-dominant component). Otherwise proceed.

### 4.2 Extract piece table as a fixed numpy array
```python
# tetris_ballistic/_piece_table.py
# Shape (n_pieces, n_rotations, max_cells, 2) of int8 offsets (dr, dc)
PIECE_OFFSETS = np.array([...], dtype=np.int8)
PIECE_N_CELLS = np.array([4, 4, 4, 4, 4, 4, 4, 1, ...], dtype=np.int8)
```

### 4.3 Free-function inner kernel
```python
# tetris_ballistic/_kernel.py
import numba as nb

@nb.njit(cache=True, fastmath=False)  # fastmath=False to preserve bit-equality
def simulate_kernel(width, height, steps, seed,
                    piece_dist_cdf, piece_offsets, piece_n_cells, sticky_flag):
    rng = np.random.default_rng(seed)
    heights     = np.zeros(width, dtype=np.uint32)
    fluctuation = np.empty(steps, dtype=np.float64)
    avg_height  = np.empty(steps, dtype=np.float64)
    final_steps = steps
    for i in range(steps):
        # sample piece, place, update heights, write fluctuation[i] + avg_height[i]
        ...
        if heights.max() >= height - 1:
            final_steps = i
            break
    return heights, fluctuation, avg_height, final_steps
```

### 4.4 Wire into `Tetris_Ballistic.Simulate`
- Add `self._use_kernel = True` flag (env var override `TETRIS_NO_NUMBA=1`)
- If kernel mode: delegate to `_kernel.simulate_kernel`, deserialize outputs into `self.Fluctuation`, `self.AvergeHeight`, `self.FinalSteps`
- If kernel mode: substrate is NOT updated cell-by-cell (since we no longer need it for stats). Add `--record-substrate` flag for legacy/visualization mode.

### 4.5 Test
The critical bit-equality concern is **random number generation**. `random.randint` (stdlib) vs `np.random.default_rng` produce different sequences. Decision: keep `np.random.default_rng(seed)` in the kernel and document that **Phase-4 outputs are NOT bit-equal to legacy outputs** — they're independent statistical samples with the same distribution.

**Test strategy**:
- (a) **Determinism within Phase 4**: same seed → same output (run twice, assert equal)
- (b) **Statistical equivalence**: run 50 seeds with legacy + 50 seeds with kernel, assert ensemble Fluctuation means agree within `2 σ / sqrt(50)`
- (c) **Conservation laws**: sum(heights) == total cells placed (deposition mass conservation)

### 4.6 Benchmark
- Compare Phase-1 vs Phase-4 on the same 3 representative configs
- Report combined Phase-0 → Phase-4 speedup

### 4.7 Gate
- Determinism + statistical equivalence + mass conservation all pass
- Speedup ≥ 5× on top of Phase 1 (sanity floor; Numba should give 10-50×)
- **Commit + push**: `perf(kernel): @njit simulation kernel (Phase 4, NNN× total speedup)`

### 4.8 If Phase 4 introduces bit-equality break for downstream
If existing `experiments/exp13/results.json` becomes irreproducible, write `MIGRATION.md` explaining the RNG change and how to reproduce historical runs (`TETRIS_NO_NUMBA=1`).

---

## Phase 5 — Industrial polish (90 min budget)

**Goal**: Make the package look and feel professional.

### 5.1 `pyproject.toml`
- Migrate from `setup.py` to `pyproject.toml` (PEP 621)
- Add `[project.optional-dependencies]`: `hpc` = `[numba]`, `dev` = `[pytest, pytest-benchmark, ruff, black]`
- Add `[project.scripts]`: `tetris-bd-run-cell = tetris_ballistic.scripts.run_one_cell:main`
- Add `[tool.pytest.ini_options]`
- Add `[tool.ruff]` config

### 5.2 CI on GitHub Actions
- `.github/workflows/ci.yml`: matrix Python 3.10/3.11/3.12, runs pytest on every push/PR
- `.github/workflows/benchmark.yml`: runs benchmark on tag, posts speedup to README

### 5.3 README updates
- New section "Performance" with the speedup table from each phase
- New section "HPC usage" with the Slurm-array recipe
- Keep existing content intact

### 5.4 Module-level docstrings + type hints
- Add type hints to `Tetris_Ballistic.__init__`, `Simulate`, `Sample_Tetris`, `_Place_*`, `_surface_row`, `_UpdateStatus`
- Add `from __future__ import annotations` at top of files where useful

### 5.5 Version bump
- `1.2.7` → `2.0.0` (major: API change with `heights` array + optional numba dep)
- `CHANGELOG.md`: list all phase achievements

### 5.6 Gate
- `pytest` GREEN
- `ruff check tetris_ballistic/` clean (or documented suppressions)
- `python -c "import tetris_ballistic; print(tetris_ballistic.__version__)"` shows 2.0.0
- **Commit + push**: `chore: industrial polish — pyproject.toml + CI + v2.0.0`

---

## Phase 6 — Final report + HANDOFF.md (30 min budget)

### 6.1 `BENCHMARKS.md`
Full table:
| Phase | Wall time (L=200, 200K steps) | steps/sec | Speedup vs Phase 0 |
|---|---|---|---|
| 0 (baseline) | T0 | r0 | 1× |
| 1 (incremental heights) | T1 | r1 | s1× |
| 4 (numba) | T4 | r4 | s4× |

Combined improvement, memory footprint comparison, Slurm-array throughput estimate.

### 6.2 Update `HANDOFF.md`
- Next session = "run a real 10K-cell experiment on Easley using the new array script, then re-run KPZ analysis with streaming"
- Reference all the new artifacts

### 6.3 Update `SPDEs-wiki` project page (`tetris-kpz-slope-extraction.md`)
- New 2026-05-16 (overnight) Status entry
- Reference the new performance numbers

### 6.4 Final commit + push of all three repos
- `sim-repo` final commit: docs + handoff
- `SPDEs-wiki` final commit: status update
- (No Le-AI-Lab changes unless a new skill emerges — `/retro` at very end)

### 6.5 Retro
Run `/retro` and extract any durable lessons (e.g., "incremental-state-array-for-monte-carlo", "numba-kernel-for-monte-carlo-bit-equality-RNG-tradeoff").

---

## Commit message convention (used throughout)

Conventional Commits style, matching the recent history:

- `test: phase 0 — golden reference + baseline timings`
- `perf(sim): incremental heights array (Phase 1, NN× speedup)`
- `perf(analysis): streaming per-cell aggregation (Phase 2)`
- `feat(hpc): Slurm-array entry point (Phase 3)`
- `perf(kernel): @njit simulation kernel (Phase 4, NNN× total speedup)`
- `chore: industrial polish — pyproject.toml + CI + v2.0.0`
- `docs: final benchmark report + handoff update`

All commits include a body with: what changed, why, test/benchmark evidence, refs to issue/HANDOFF if any.

---

## Push policy

After each phase passes its gate:
```bash
git push origin main
```
- No force-push. If a divergence is detected (somebody else pushed to `main` while I worked), pull-rebase first, then push. If rebase has conflicts in a phase's files, abort that phase and roll back.

---

## Decision-tree for known forks

### Q: What if `pytest-benchmark` won't install?
**A**: Fall back to `time.perf_counter()` in raw scripts. Don't block the rest.

### Q: What if numba install fails (e.g., no LLVM)?
**A**: Skip Phase 4. Phases 1-3 are independent and still deliver substantial speedup.

### Q: What if Phase-1 bit-equality fails because legacy `_TopEnvelop` had a `landing_row - 1` off-by-one?
**A**: Document the legacy bug in `MIGRATION.md`, treat the NEW result as authoritative, regenerate the golden reference. (This is the right industrial-grade move: tests document the correct behavior, not the bug.)

### Q: What if I exceed the budget on Phase 4?
**A**: Per stall rule: commit any in-progress kernel work to a branch `wip/numba-kernel` (don't merge to main), continue with Phase 5.

### Q: What if `git push` fails (network, auth)?
**A**: Retry 3 times with backoff. If still failing, continue local commits, log the failure, push everything at end.

### Q: What if a `_Place_*` method has unusual cell layout I missed?
**A**: Run the bit-equality test PER PIECE-TYPE (filter the legacy `tests/indivisual-pieces/` outputs as additional golden references). If a specific piece fails, fix that one, don't roll back all of Phase 1.

---

## Logging

`OVERNIGHT-LOG.md` is appended to at every phase boundary with:
- Timestamp (start/end)
- Phase number + status (GREEN/AMBER/RED)
- Speedup measured (if applicable)
- Decisions made + reasoning
- Any unexpected behavior
- Files touched

Final log entry is a single-line summary table.

---

## End-state success criteria

- [ ] `git log` shows ≥6 atomic commits with passing tests at each step
- [ ] `pytest` is GREEN
- [ ] `python -c "import tetris_ballistic; print(tetris_ballistic.__version__)"` → `2.0.0`
- [ ] `BENCHMARKS.md` shows ≥100× speedup on the largest config
- [ ] `experiments/templates/job_array.slurm` exists and parses cleanly
- [ ] CI badge on README (passing)
- [ ] `HANDOFF.md` points at next session ("run 10K-cell experiment on Easley")
- [ ] All commits pushed to `origin/main`
