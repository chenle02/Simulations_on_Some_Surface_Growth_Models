# Overnight Execution Log

**Operator**: Sisyphus (OpenCode, fully autonomous)
**Start time**: 2026-05-16 11:35 EDT
**Plan**: `OVERNIGHT-PLAN.md`

---

## Phase boundaries (filled in as we go)

| Phase | Start | End | Status | Speedup | Commit | Notes |
|---|---|---|---|---|---|---|
| 0 | 11:35 EDT | 11:55 EDT | **GREEN** | n/a | 54821e4 + (next) | 9 golden refs, 12 fast tests pass, baseline locked |
| 1 | TBD | TBD | pending | — | — | Incremental heights |
| 2 | TBD | TBD | pending | — | — | Streaming analysis |
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

