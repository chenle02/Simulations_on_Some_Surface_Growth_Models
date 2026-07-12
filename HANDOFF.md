# HANDOFF — tetris-KPZ exp14 crossover (blocked on one PI decision)

Last updated: 2026-07-12 (session paused at a science-decision fork)
HEAD: `a57de24`

## Next session — the ONE blocked decision

The exp14 KPZ crossover re-run is blocked on a single PI choice about the
growth-exponent estimator, because the corrected deep traces are huge
(100 seeds × ~8M steps → hours-to-a-day of local bootstrap compute, and the
local box OOM/thrashes on the L≥400 cells).

Pick ONE, then finish Todos below:

1. **Log-subsample the estimator (recommended).** In
   `tetris_ballistic/kpz_analysis.py`, before the bootstrap in
   `growth_window_slope` / `local_slope_bootstrap`, log-subsample each trace to
   ~5000 log-spaced indices. Negligible effect on a log-log slope, run finishes
   in minutes. This is a numerics change to a load-bearing estimator, so it
   needs Le's explicit OK.
2. **Easley bigmem.** Push the corrected npz to Easley and run
   `run_kpz_analysis` on a bigmem partition (64 GB, like the reduce). No numerics
   change; slow; needs the corrected npz copied over.
3. **Fewer bootstraps** (`--n-boot 40`) on the deep cells only — faster, wider CIs.

## Verbatim resume (after the decision)

```
cd /home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models
# corrected npz are symlinked into experiments/exp14/ already; 4/50 cells done
.venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \
  --exp-dir experiments/exp14 \
  --pcts 5,50,90,95,98,99 \
  --widths 50,80,100,150,200,250,300,400,500 \
  --n-boot 200 --n-eval 150 --resume        # --resume reuses the 4 done cells
# -> writes experiments/exp14/results.json + per-pct + extrapolation plots
```

Then remaining Todos:
- Update SPDEs-wiki project page β-table + Article-TetrisKPZ β-table with the
  corrected exp14 curve (`content/projects/tetris-kpz-slope-extraction.md`;
  `Article-TetrisKPZ-Crossover/notes/notes_tetris_kpz.tex`).
- Commit/push wiki + Article. (sim-repo already committed: `ba2580b`, `a57de24`.)

## Pre-flight checks (before resuming)

- Corrected npz present: `ls /home/lechen/Dropbox/workspace/tetris-kpz-raw-joblib/traces/exp14/pct_*/*.npz | wc -l` → 50
- Each cell ascending/saturated (already verified 50/50; `height_grid` recorded).
- `.venv/bin/python -m pytest tests/test_kernel_fast_path.py -q` → 4 passed.
- Machine RAM free before a local run: `free -g` (need >25 GB for L=500 at full res, or use option 1/2/3).

## What previous sessions produced (this session)

- Root-caused + fixed the `AvergeHeight` inversion (commit `e7ba915` regression):
  `ba2580b` (kernel+legacy fix, convention regression test, golden regenerated),
  `a57de24` (npz-aware `load_ensemble`, graceful missing-cell skip,
  `invert_exp14_height.py`).
- exp14 reduce (Easley bigmem) + guarded pull to private backup (36.5 GB, 50 npz).
- exp14 npz one-time inversion: 50/50 corrected + verified (all now saturated).
- exp13 confirmed UNAFFECTED (pre-e7ba915, ascending physical height).
- 4/50 crossover cells verified on corrected data (pct5 β 0.43→0.31 with L,
  trending toward the correct exp13 baseline β≈0.16).
- Le-AI-Lab skills: `reduce-heavy-sim-output-before-sync` (F1/F2 footguns) and
  `equivalence-test-blind-to-shared-bug-pin-the-convention`.
- Full diagnosis in `FINDING-kernel-height-inversion.md`.

## Repo / git state

- sim repo `Simulations_on_Some_Surface_Growth_Models` @ `a57de24` (pushed).
- data repo `tetris-kpz-data`: exp13 traces committed earlier; exp14 npz are in
  the PRIVATE backup `~/Dropbox/workspace/tetris-kpz-raw-joblib/traces/exp14`
  (too big for git, per approved option A) — NOT in git.
- Article-TetrisKPZ-Crossover: manuscript at `2712c11`, β-table update pending.
- SPDEs-wiki project page: β-table update pending.

## Operating notes / risks

- Do NOT re-run the reduce/inversion — both are done and verified (idempotent).
- The corrected npz live under Dropbox; a full-res local analysis OOMs on L≥400
  (needs ~25 GB float64 per cell) — that is exactly the blocked decision above.
- `experiments/exp14/` is gitignored (symlinks to the backup npz); do not commit.
