# HANDOFF

**Last updated**: 2026-05-15 22:30 (closing previous session)
**Project**: Robust KPZ slope extraction for Tetromino ballistic deposition
**Wiki page (authoritative strategy)**: `~/Dropbox/workspace/svn/SPDEs-wiki/content/projects/tetris-kpz-slope-extraction.md`

---

## ⏭ Next session: where to stand and what to do

```bash
cd ~/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models
```

**Implement `tetris_ballistic/kpz_analysis.py`** per Steps 1–8 of the *Proposed protocol* section of the wiki project page. Run it on `experiments/exp13/` (300 joblib files already there, no new simulation needed). Report $\hat\beta_\infty \pm \mathrm{CI}$ per percentage.

---

## Why (deeper context)

Read the full project page first:
```bash
cat ~/Dropbox/workspace/svn/SPDEs-wiki/content/projects/tetris-kpz-slope-extraction.md
```

It contains:
- 35-year literature survey (Family-Vicsek 85 → Halpin-Healy-Takeuchi 15) with explicit attribution of each algorithmic component to its earliest published origin
- 8-step protocol (preprocessing, ensemble, local-slope bootstrap, plateau detection, Meakin range-of-fit cross-validation, multi-$L$ extrapolation, simultaneous moment cross-check, Tetris-specific tests)
- Exp13 data layout (300 files: `piece_19` × 6 percentages × 5 widths × 10 seeds)
- Diagnostic baseline: existing `loglogplot_stat.py` reports $\hat\beta = 0.239$ vs KPZ target $1/3 = 0.333$ — this is the failure mode we're fixing

---

## What the previous session(s) produced

- **Wiki project page** at HEAD `b6a77de3` on `SPDEs-wiki/v4` — fully documents the strategy
- **11 refs added to refdb** (HEAD `302fa0a5`): clauset.shalizi.ea:07, pagnani.parisi:12 and :15, halpin-healy:12 and :13, halpin-healy.takeuchi:15:kpz, lopez.castro.ea:97 and :05, lopez:99, ramasco.lopez.ea:00, family.vicsek:91:dynamics
- **Family-Vicsek 1991 book** acquired (All_PDFs HEAD `dae9e3f`): `f/family_vicsek-91-dynamics.pdf` (24.8 MB, 493 pp from DjVu→PDF); original DjVu at `_djvu_originals/`
- **Three forged + wiki-ed papers** with full theorem-statement digests for Family-Vicsek 85, Meakin et al. 86, Baiod et al. 88 (the foundational range-of-fit + cross-validation methodology trio)
- **Two new skills** in Le-AI-Lab: `paper-digester-wikilink-vocabulary-precheck`, `zsh-glob-no-matches-vs-missing-directory`, `withdrawn-arxiv-paper-wiki-treatment`
- **Verified data shape**: see *Data layout (exp13/)* in the wiki project page; reproduced here in §Pre-flight below

---

## Pre-flight checks for the next session

### 1. Verify you're in the right tmux pane and venv

```bash
pwd                                        # should be .../Simulations_on_Some_Surface_Growth_Models
ls .venv/bin/python                        # should exist
.venv/bin/python -c "import joblib, numpy, scipy, matplotlib, yaml, imageio; print('ok')"
```

If any module is missing: `.venv/bin/python -m pip install <pkg>`.

### 2. Verify the data is present

```bash
ls experiments/exp13/*.joblib | wc -l      # expect: 300
ls experiments/exp13/config_piece_19_combined_percentage_05_w=100_seed=0.joblib
```

### 3. Verify the wiki project page is reachable

```bash
ls ~/Dropbox/workspace/svn/SPDEs-wiki/content/projects/tetris-kpz-slope-extraction.md
```

### 4. Quick joblib sanity-check (reproducing the previous-session inspection)

```bash
.venv/bin/python - <<'PY'
import joblib, glob
f = sorted(glob.glob("experiments/exp13/config_piece_19_*.joblib"))[0]
obj = joblib.load(f)
print(f"width={obj.width}, FinalSteps={obj.FinalSteps}, "
      f"Fluctuation.shape={obj.Fluctuation.shape}, "
      f"estimated_slope={obj.estimated_slope:.4f}")
PY
```

Expected output (on a 5%-sticky $L=100$ run):
```
width=100, FinalSteps=47816, Fluctuation.shape=(47816,), estimated_slope=0.2391
```

---

## Concrete deliverables

| # | Deliverable | File | Definition of done |
|---|---|---|---|
| 1 | The methodology module | `tetris_ballistic/kpz_analysis.py` | ~250 lines, 6 functions per the protocol, docstrings cite Meakin 86 + Amar-Family 90 + Krug-Meakin 90 + Baiod 88 |
| 2 | A runner script | `experiments/exp13/run_kpz_analysis.py` | Loads all 300 joblib files, dispatches the module, produces per-(pct, $L$) outputs |
| 3 | Local-slope plot per $L$ | `experiments/exp13/local_slope_L{50,80,100,150,200}.png` | Shows $\hat\beta(t)$ with bootstrap CI band; horizontal line at $1/3$; plateau region highlighted |
| 4 | Multi-$L$ extrapolation plot | `experiments/exp13/multi_L_extrapolation.png` | $\hat\beta(L)$ vs $1/L^\omega$ with fitted $\beta_\infty + c\, L^{-\omega}$ curve, separate per percentage |
| 5 | Numeric report | terminal output + `experiments/exp13/results.json` | $\beta_\infty \pm \mathrm{CI}$ per percentage |

---

## Success criteria

1. **Lint & test**: module imports without error in `.venv`; runs on the existing 300 files without crashes.
2. **Plateau detected**: `detect_plateau` returns non-`None` for at least 4 of the 5 $L$ values (the smallest $L$ may be too short).
3. **Beats baseline**: $\beta_\infty$ extrapolated value lands in $[0.30, 0.36]$ for at least one percentage (preferably 95% or 98% which should be closest to pure ballistic deposition).
4. **Cross-validates**: Meakin two-window cross-validation agrees within CI for the larger $L$ values.
5. **Documents reality honestly**: if $\beta_\infty$ is systematically below $0.30$, the module reports "simulation needs longer runs" rather than silently underestimating.

---

## Anti-success criteria (things that mean the protocol is wrong)

- $\beta_\infty$ converges to a value far from $1/3$ across **all** percentages and **all** plateau-detected $L$ values
- Plateau detector returns `None` for all 5 $L$ values
- Bootstrap CI bands are wider than $\pm 0.05$ — indicates ensemble too small (need >10 seeds, or longer per-run traces)

If any of these triggers, the next-session output is *not* a wrong $\beta$ — it's an honest diagnostic + a recommendation for what additional simulation is needed.

---

## After the methodology module works

The downstream tasks (in order, only after $\beta_\infty \approx 1/3$ is confirmed):

1. **Sticky-fraction sweep diagnostic**: confirm $\beta_\infty$ independent of percentage (Baiod-88 $p$-independence test)
2. **Tetromino-shape extension**: extend to all 19 `piece_*` shapes (currently only `piece_19` data exists)
3. **$\omega_{\rm tetris}$ measurement**: extract the correction-to-scaling exponent $\omega$ and compare to single-particle ballistic deposition's $\omega \approx 0.5$
4. **Methods paper**: if (3) reveals an unusual $\omega_{\rm tetris}$, that's a publishable observation

Each of these is a separate session; update HANDOFF.md at session end to point at the next.

---

## Operating notes

- **Commit + push at session end** to: this repo (sim-repo), and optionally `SPDEs-wiki` if the project page Status section gains new entries.
- **Update this HANDOFF.md** at session end with the new "Next session" instructions.
- **Honest reporting > pretty numbers**: if the protocol fails to find a clean $\beta = 1/3$, the report should diagnose *why* (simulations too short, sticky fraction in a non-universal regime, missing correction term) rather than tune hyperparameters until $0.333$ appears.

---

## Repo & git state at handoff

```
sim-repo               HEAD: 5b7856a8 fix(gitignore)
SPDEs-wiki             HEAD: b6a77de3 project(tetris-kpz-slope): document exp13 joblib data layout
refdb                  HEAD: 302fa0a5 Add 11 references for Tetris-KPZ-slope-extraction project
All_PDFs               HEAD: dae9e3f Add Family-Vicsek 1991 Dynamics of Fractal Surfaces
Le-AI-Lab              HEAD: 02950a3 docs(skills): add IMAP filing checkpoints
```

All five repos clean (0 dirty files) at handoff.
