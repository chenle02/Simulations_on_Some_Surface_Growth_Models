# HANDOFF

**Last updated**: 2026-07-13 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: S2.4 complete tetromino event selection without placement

## Current state

The S2.4 implementation and its industrial validation gates are complete. The
pre-S2.4 software baseline was `296ad7d381a72fcfab664a02c2a0f97d46b7d636`.
The current handoff-bearing commit is the S2.4 software authority; obtain its
exact hash with `git rev-parse HEAD` rather than embedding a self-hash here.

The explicit-submodule API is `tetris_ballistic.engine.event`. It is not
re-exported from `tetris_ballistic` or `tetris_ballistic.engine`, and it is not
routed through configuration execution, placement, a trajectory, legacy code,
HPC, or any production path.

## Ratified executable contract

- Family order: `("i", "lj", "o", "sz", "t")`.
- Contact order: `("supported-v1", "edge-first-contact-v1")`.
- Stream order: `("family", "orientation", "launch", "contact")`.
- Orientation branches: all five families in family order, with exact
  2/8/1/4/4 `FAMILY_ORIENTATION_IDS` outcome tuples.
- Validation: the complete address, full five-branch law, public/private order
  integrity, and fixed stream schedule fail closed before the first RNG call.
- Evaluation: family, the selected family's orientation, launch, and contact
  are drawn exactly once in that order. Unselected branches are validated but
  receive no draw. Degenerate selected laws still consume their logical raw
  candidate.
- Coupling: equal root seed, coupling group, event ordinal, and literal stream
  name share the whole raw candidate tape. Each law performs its own rejection
  and acceptance; unequal bounds need not share an accepted value or rejection
  ordinal.
- Evidence: the immutable result carries the address, complete frozen law, and
  all four selections with their accepted-rejection metadata. Direct record
  construction is structurally checked but does not replay Philox.

The normative vector at root zero / `paired-main` / event zero selects
`sz`, `tetromino.sz.03`, launch 4, and `edge-first-contact-v1`. The unequal
launch-bound vector at event one accepts rejection ordinal 0 for bound 2 and
ordinal 1 for bound `2**63 + 1`. See
`docs/COMPLETE-EVENT-SELECTION-VECTORS.md`.

## Validation evidence

- Focused S2.4 suite: 48 passed, 1 slow test deselected.
- Independent 10,000-event composition oracle: 1 passed.
- Full default suite: 766 passed, 6 skipped, 6 deselected.
- Full slow suite: 6 passed, 772 deselected.
- CI-scope `ruff check tetris_ballistic/ tests/`: passed.
- Ruff formatting for all changed Python files: passed.
- `compileall` for package and tests, plus `git diff --check`: passed.
- Clean isolated PEP 517 build from the sdist: wheel and sdist passed.
- `twine check`, compressed-archive integrity, required-member audit, and
  foreign-directory exclusion: passed.
- The source manifest excludes the ignored, untracked
  `tests/test_compute_endpoint_slope.py`; the final sdist contains no stale
  worktree-only test material.
- Isolated built-wheel vector/root-export smoke and dependency checks: passed
  on Python 3.10.18, 3.11.13, 3.12.11, 3.13.7, and 3.14.6.
- Three independent read-only reviews passed. The adversarial review first
  found a rebindable canonical-order authority; private ratified snapshots,
  pre-draw integrity checks, and hostile-rebinding tests closed that defect.

Repository-wide `ruff format --check .` is not the configured CI gate and
still reports pre-existing formatting debt in 42 unrelated files. A separate
mechanical cleanup unit may address that debt; do not mix a bulk reformat into
this semantic commit.

## Scope boundary

S2.4 adds no generic conditional selector/DAG, named one-cell or control law,
placement call, state transition, `SimulationConfig` adapter, legacy migration,
trajectory, canonical JSON, digest/shared artifact identity, checkpoint,
optimized kernel, CLI, batch runner, Slurm/HPC integration, release, or
production route. `engine/rng.py`, `engine/selection.py`,
`engine/reference.py`, and both package-root `__init__.py` files remain
unchanged. `MANIFEST.in` changes only to exclude an ignored worktree-only test
from the sdist.

The historical exp13/exp14 workflows remain one-cell `piece_19` experiments;
this provisional tetromino selector does not reinterpret or reroute them.

## Provenance anchors and parallel-work guard

- Article S2.4 decision closure:
  `930751b24575d660ecdfddbd94ae985e504f124a`.
- Wiki authored decision page:
  `43f0fb926076abb2f22b58a2b58d567ac632dcd4`.
- Wiki generated dashboard:
  `ab6ba394db4896cffb4150207931eee8c925bf22`.

Another LLM owns the six-repository pipeline. Do not edit, regenerate, stage,
or advance that pipeline's files. Any downstream Article/wiki implementation
update must preserve its section byte-for-byte, use the shared-repository
bi-directional sync workflow first, and stage only the explicitly audited
project-page/report paths.

## Next bounded step

1. Commit and immediately push the S2.4 software unit, then record its exact
   software hash downstream through the Article -> authored wiki page ->
   generated dashboard -> final Article closure provenance loop.
2. Re-run the exact downstream preflights before each repository write and
   preserve the parallel six-repository work.
3. Do not compose S2.4 with placement or configuration automatically. Propose
   the next bounded unit separately, with its API, identity boundary, tests,
   and rollback conditions fixed before implementation.

## Pre-flight for a future software session

1. Stand at
   `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`.
2. Confirm `git status --short` has no tracked changes and only the foreign
   untracked `.omx/` and `.pi-subagents/` directories.
3. Confirm local `main` and `origin/main` are synchronized at this S2.4 commit
   or a documented later bounded unit.
4. Run `.venv/bin/python -m pytest -q` and
   `.venv/bin/python -m pytest -q -m slow` before another semantic change.
5. Keep the event selector explicit-submodule-only until a separately approved
   migration gate authorizes a public or production route.
