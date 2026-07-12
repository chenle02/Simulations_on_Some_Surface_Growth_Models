# HANDOFF

**Last updated**: 2026-07-12 11:18 EDT
**Project**: Simulations_on_Some_Surface_Growth_Models — exp14 sticky-fraction crossover
**Wiki page**: `content/projects/tetris-kpz-slope-extraction.md`

## ⏭ Next session: where to stand and what to do

Stand at `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`. No mandatory compute or edit is queued. The immediate next step is a PI decision: stop and share the completed 8-page Article note, or authorize genuinely new science. New science should begin only with an explicit scope such as `L>=600`, more independent seeds, joint `alpha`/`z` measurements, or a full standardized CDF comparison after the moment diagnostics begin to stabilize.

## Pre-flight checks

1. Run `pwd`; expect `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`.
2. Run `git rev-parse --short HEAD`; expect `0987e09` or a later handoff-only commit.
3. Run `git status --short`; expect no tracked changes and no untracked files except the foreign `.omx/` and `.pi-subagents/` directories. If any other path appears, stop.
4. If code changes are proposed, run `.venv/bin/python -m pytest -q`; the current baseline is `96 passed, 6 skipped, 5 deselected`.
5. Verify the tracked result bundle from its own directory: `cd tetris_ballistic/data/exp14_results && sha256sum -c MANIFEST.sha256`; expect every entry to report `OK`.
6. In `/home/lechen/Dropbox/workspace/svn/Article-TetrisKPZ-Crossover`, run `git rev-parse --short HEAD`; expect `daa5d1b` or later, and confirm `pdfinfo notes/notes_tetris_kpz.pdf` reports 8 pages.
7. In `/home/lechen/Dropbox/workspace/svn/SPDEs-wiki`, confirm branch `v4` is at `f81bac80` or later and synchronized with its upstream.

If any applicable check fails, stop before editing, computing, or sharing.

## Concrete deliverables for the next session

- Record the PI decision to stop/share the verified Article note or authorize a specifically scoped new experiment.
- If sharing, cold-read the canonical PDF at `/home/lechen/Dropbox/workspace/svn/Article-TetrisKPZ-Crossover/notes/notes_tetris_kpz.pdf` and distribute that artifact.
- If new science is authorized, write a fresh plan with explicit widths, seed counts, observables, compute budget, and acceptance criteria before launching work.
- Make no routine simulation, reduction, bootstrap, manuscript, or wiki change merely to continue activity.

## Success criteria for the immediate next step

- A clear stop/share-or-new-science decision is made without launching unapproved compute.
- If shared, the verified 8-page Article PDF is the reviewed and distributed artifact.
- If new science is authorized, it targets asymptotic discrimination rather than another cosmetic estimator variation.
- The recorded interpretation remains limited to a stickiness-dependent finite-scale crossover with unresolved asymptotic classification.

## Anti-success criteria

- Launching new simulations, reductions, bootstraps, or universality analyses without a new PI-approved scope.
- Describing exp13/exp14 as tetromino, multi-cell, polyomino, or extended-object experiments; both use one-by-one `piece_19` deposition.
- Comparing equal exp13/exp14 percentage labels as equal physical mixtures.
- Treating 5,000-point log sampling as estimator-equivalent or numerically negligible.
- Resampling substrate columns or time points as independent observations instead of resampling whole seeds.
- Using raw deposition steps instead of mean height as the Family--Vicsek clock.
- Claiming super-KPZ, stable GOE rejection, or any settled asymptotic universality class.
- Claiming the raw exp13/exp14 joblib ensembles are tracked in git.

## What the previous sessions produced

- Implemented paired log-spaced subsampling with float32 preservation, provenance, stale-cell invalidation, and tests (`767577a`).
- Implemented estimator-sensitivity analysis (`06d3e38`) and recorded the 50-cell comparison bundle (`58b17f8`). Log sampling raises the fitted exponent in all 50 corrected exp14 cells; the relative increase ranges from 5.0% to 32.0%, with median 18.6%.
- Implemented the common-time Tracy--Widom reduction and whole-seed analysis pipeline (`a47ec6c`), including the in-memory fallback for original inverted Easley traces (`218819f`).
- Easley canary job `5373333` and full reduction job `5373334` completed all 14 selected cells with 4,200/4,200 reconstruction validations passing.
- Recorded the compact Tracy--Widom result bundle (`670554d`). The analysis used 100 seeds per cell, common height-clock targets `q=0.15,0.25,0.40`, and 2,000 whole-seed block bootstraps; every cross-width verdict is `inconclusive/crossover-dominated`.
- Replaced the super-KPZ novelty framing with a cautious evidence memo (`e4eaf5c`) and corrected the remaining `piece_19` model-identity descriptions plus bundle manifest (`0987e09`).
- Updated the Article repository with the corrected model identity, percentage semantics, finite-scale slope pattern, estimator sensitivity, and Tracy--Widom result (`6ca0dea`), then recorded the final Article handoff (`daa5d1b`). The canonical build is 8 pages with 0 LaTeX errors, undefined references/citations, or overfull boxes.
- Updated the SPDEs-wiki project page and indices (`dfbe4d4f`), refreshed the project dashboard (`e5e74dbc`), and corrected the sensitivity-distribution wording after independent review (`f81bac80`).

## Repo & git state at handoff

- CWD: `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`
- Branch: `main`
- Substantive HEAD: `0987e09`
- Upstream: `origin/main` at `github.com:chenle02/Simulations_on_Some_Surface_Growth_Models.git`
- `0987e09` is pushed and synchronized with `origin/main`.
- The final handoff commit is expected to be one commit later than `0987e09`.
- `.omx/` and `.pi-subagents/` are foreign untracked directories and remain out of scope.
- Raw exp13/exp14 joblib ensembles remain outside git; only compact reduced evidence products are tracked.

## Operating notes

- Use `.venv/bin/python` for local simulation-repository validation.
- The tracked evidence bundle is `tetris_ballistic/data/exp14_results/`; run its `MANIFEST.sha256` check from inside that directory because manifest paths are relative.
- Preserve `AvergeHeight` as the historical field spelling and preserve mean height `hbar` as the Family--Vicsek clock.
- Exp13 uses `[pct, 100-pct]`, so its label is the nonsticky fraction. Exp14 uses `[100-pct, pct]`, so its label is the sticky fraction.
- Tracy--Widom uncertainty must bootstrap complete seed rows. Matching GOE skewness and excess kurtosis would be a fingerprint, not proof of universality.
- Easley raw data under `/scratch/lzc0090/tetris14/results` are scratch inputs, not tracked artifacts; do not mutate them or describe them as durable git data.

## Risks to monitor

- **Model-identity drift:** the analyzed exp13/exp14 data use the one-by-one `piece_19` configuration, not tetromino or extended pieces.
- **Semantic drift:** exp13 percentages are nonsticky fractions, whereas exp14 percentages are sticky fractions.
- **Clock drift:** use mean height `hbar`, not raw deposition steps, for Family--Vicsek fits and common-time targets.
- **Estimator drift:** log subsampling changes OLS weighting; its all-positive 5.0%--32.0% relative effect must remain explicit.
- **Statistical drift:** uncertainty must resample independent whole seeds, never substrate columns or time points.
- **Claim drift:** effective-`beta` overshoot and finite-scale GOE moments do not establish super-KPZ, KPZ, Edwards--Wilkinson, or another asymptotic class.
