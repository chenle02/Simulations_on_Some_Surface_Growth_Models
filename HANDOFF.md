# HANDOFF — tetris-KPZ crossover: finish exp14 + Tracy-Widom test

Last updated: 2026-07-12 08:36 EDT
HEAD: `3328f5c` (sim repo, ahead=0, clean except gitignored exp14 symlinks)
Wiki project page: `~/Dropbox/workspace/svn/SPDEs-wiki/content/projects/tetris-kpz-slope-extraction.md`

## ⏭ Next session

Resume the tetromino-BD KPZ crossover. Two things are ready to do, gated on ONE
PI decision:

**(A) [BLOCKED on PI decision] Finish the corrected exp14 crossover.** The height
inversion bug (`e7ba915`) is fixed and all 50 exp14 npz are corrected & verified,
but only 4/50 crossover cells are computed. Completing it needs a choice about the
estimator/compute, because the corrected deep traces are 100 seeds × ~8M steps
(hours of bootstrap + OOM risk on L≥400 locally):
   1. **Log-subsample the estimator (recommended)** — in `kpz_analysis.py`,
      log-subsample each trace to ~5000 log-spaced points before the bootstrap.
      Minutes to run; negligible effect on a log-log slope. Numerics change to a
      load-bearing estimator → needs Le's explicit OK.
   2. **Easley bigmem** — push corrected npz to Easley, run on bigmem (64 GB).
   3. **Fewer bootstraps** (`--n-boot 40`) on deep cells only.

**(B) [NEW, recommended — decisive science] Tracy-Widom height-distribution test.**
The 2026-07-12 search session concluded the apparent "super-KPZ β≈0.44-0.49" at
high stickiness is almost certainly a FINITE-SIZE OVERSHOOT, not a new universality
class (β_eff falls monotonically with L toward 1/3; no known local 1+1D BD class has
β>1/3). The decisive test is NOT more β extrapolation — it is the rescaled
one-point height-distribution skewness/kurtosis vs Tracy-Widom (GOE for flat
geometry: skew≈0.2935, ex-kurt≈0.1652). If the distribution is KPZ-TW at high pct
while β_eff still drifts down, the super-KPZ interpretation is dead and the paper's
headline becomes "sticky-fraction knob tunes an RD/EW→KPZ crossover, verified by
Tracy-Widom" (strong) rather than "we measured β" (weak).

Do (A) first (confirms the downward β trend), then (B) (the sharp fingerprint).

## Pre-flight checks

1. `cd /home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models && git rev-parse --short HEAD` → expect `3328f5c` or later.
2. `.venv/bin/python -m pytest tests/test_kernel_fast_path.py -q` → 4 passed (confirms the AvergeHeight physical-height fix is intact).
3. `ls /home/lechen/Dropbox/workspace/tetris-kpz-raw-joblib/traces/exp14/pct_*/*.npz | wc -l` → 50 (corrected npz present).
4. `.venv/bin/python -c "import numpy as np; d=np.load('/home/lechen/Dropbox/workspace/tetris-kpz-raw-joblib/traces/exp14/pct_05/L_0050.npz'); print('ascending' if d['hbar'].mean(0)[0] < d['hbar'].mean(0)[-1] else 'INVERTED-STOP', 'height_grid' in d.files)"` → `ascending True`.
5. `ls experiments/exp14/kpz_cells/cell_*.json | wc -l` → 4 (resumable done cells; symlinks in `experiments/exp14/` point to the corrected npz).
6. `free -g` → need >25 GB free for a full-res L=500 cell, else pick estimator option 1/2/3.

## Concrete deliverables

1. **(A)** `experiments/exp14/results.json` + per-pct + β∞-extrapolation plots, from
   the corrected npz. Verbatim resume (after the PI estimator choice):
   ```
   cd /home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models
   .venv/bin/python -m tetris_ballistic.scripts.run_kpz_analysis \
     --exp-dir experiments/exp14 \
     --pcts 5,50,90,95,98,99 \
     --widths 50,80,100,150,200,250,300,400,500 \
     --n-boot 200 --n-eval 150 --resume
   ```
2. **(B)** A new height-distribution / Tracy-Widom analysis: rescaled skewness &
   excess-kurtosis per (pct,L) at the largest saturated L, compared to GOE-TW
   (0.2935 / 0.1652). New module + script mirroring the reduce/analysis layout.
3. Update wiki β-table + `Article-TetrisKPZ-Crossover/notes/notes_tetris_kpz.tex`
   with the corrected crossover AND the honest finite-size-vs-KPZ framing.
4. Ingest the 4 crossover-canon refs (verified real, absent from refdb):
   Braunstein-Buceta-Muraca 2004 (DOI 10.1103/PhysRevE.69.065103),
   Chame-Aarão Reis 2002 (cond-mat/0210562), Horowitz-Monetti-Albano 2001,
   Farnudi-Vvedensky 2011 — plus check Oliveira Filho et al. 2013, Das et al. 2021.
5. Commit/push sim (if new code), wiki, Article.

## Success criteria

- exp14 `results.json` produced from CORRECTED npz; high-pct β∞ reported with CIs
  and the L-dependence shown (expected: high-pct β_eff decreasing toward ~1/3).
- Tracy-Widom skew/kurtosis computed and compared to GOE-TW with an explicit
  verdict: KPZ-consistent vs genuinely-anomalous.
- Wiki + Article state the crossover as REAL and the super-KPZ as finite-size
  UNLESS the Tracy-Widom test contradicts that — no overclaiming either way.
- All cited refs verified in refdb (grep) before writing; no hallucinated citekeys.

## Anti-success criteria

- Do NOT report "super-KPZ / β>1/3 discovery" from β_eff alone — it is very likely
  a finite-size artifact (β_eff still falling at L=200). Only a Tracy-Widom/α+z
  test can support a non-KPZ claim.
- Do NOT extrapolate β∞ from UNSATURATED cells (truncated growth window droops β).
  Use only saturated large-L cells.
- Do NOT re-run the reduce or the exp14 inversion — both are done, verified,
  idempotent. Do NOT re-introduce the AvergeHeight inversion.
- Do NOT change the estimator numerics (option 1) without Le's explicit OK.

## What previous sessions produced

- **Root-caused + fixed a load-bearing bug**: commit `e7ba915` (a 2026-05 speedup
  refactor) silently inverted `AvergeHeight` from physical height → mean row-index;
  its "two paths agree" self-check couldn't catch it (both paths flipped together).
  Fixed in `ba2580b` (kernel+legacy + convention-pinning regression test + golden
  regenerated); analysis-side npz loader + `invert_exp14_height.py` in `a57de24`.
- **exp14 corrected**: 50/50 npz inverted (`grid_height − hbar`, verified vs raw
  joblib `.height`), all now correctly saturated, `height_grid` recorded.
- **exp13 confirmed UNAFFECTED** (pre-`e7ba915`, ascending physical height) — its
  committed results, the wiki β-table, and the Article stand.
- **Search-session finding (2026-07-12)**: the crossover is real & monotone (β 0.16
  →0.49 across pct); but the high-pct "super-KPZ" is a finite-size overshoot
  (β_eff(L) monotone-decreasing toward 1/3; exp13 headline biased by averaging only
  the 2 smallest saturated widths). Literature: competitive RD↔BD crossover is
  known (Braunstein-Buceta-Muraca 2004) but not with tetromino pieces; no local
  1+1D BD class has asymptotic β>1/3. Decisive next test = Tracy-Widom.
- Skills learned this arc: `reduce-heavy-sim-output-before-sync` (F1/F2 footguns),
  `equivalence-test-blind-to-shared-bug-pin-the-convention`.
- Full bug diagnosis: `FINDING-kernel-height-inversion.md`.

## Repo & git state

- sim repo `Simulations_on_Some_Surface_Growth_Models` @ `3328f5c` (pushed, ahead=0).
  Clean except gitignored `experiments/exp14/` symlinks + foreign `.omx/`.
- data repo `tetris-kpz-data`: exp13 traces committed; **exp14 npz are in the
  PRIVATE backup** `~/Dropbox/workspace/tetris-kpz-raw-joblib/traces/exp14/`
  (36.5 GB, too big for git per approved option A) — NOT in git.
- `Article-TetrisKPZ-Crossover` @ `2712c11` (Greenwood remote) — β-table update pending.
- SPDEs-wiki project page exists — β-table + framing update pending.
- Le-AI-Lab skills pushed @ `7d52d8f`.

## Operating notes

- Interpreter: `.venv/bin/python` (has joblib/numpy/matplotlib; system python lacks joblib).
- `experiments/exp14/` is gitignored (symlinks to the private-backup npz); never commit it.
- Corrected npz have a `height_grid` field; `load_ensemble` is npz-aware (keeps float32
  to avoid float64 OOM on deep cells) and falls back to raw joblib.
- Process-kill in this env can hang the shell — use a detached `setsid`/`nohup` subshell.
- Easley = `ssh Easley` (user lzc0090, needs VPN+Duo); repo synced by git pull, not Dropbox.
- Cite discipline: grep every citekey in `~/Dropbox/workspace/svn/refdb/All.bib` before writing.

## Risks to monitor

- **Overclaiming super-KPZ** — the biggest scientific risk; gate any β>1/3 claim on
  Tracy-Widom + α/z, never on β_eff alone.
- **Full-res local analysis OOMs on L≥400** (~25 GB/cell float64 with only ~13-18 GB
  free) — this IS the blocked estimator decision.
- **Unsaturated-cell extrapolation** gives nonsense β∞ (droop artifact) — filter to
  saturated L only.
- exp14 raw joblib on Easley `/scratch` has a 30-day purge window — the reduced npz
  (private backup) are the durable copy; don't rely on scratch persisting.
