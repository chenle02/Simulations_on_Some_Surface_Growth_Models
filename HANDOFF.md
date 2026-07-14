# HANDOFF

**Last updated**: 2026-07-14 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: S2 periodic-law preflight complexity hardening

## Current state

The bounded preflight-hardening implementation and its industrial validation
gates are complete over software baseline
`e44e8e335f06d982da8a0fa5b31b6efed9717c6e`. The current handoff-bearing
commit is the software authority; obtain its exact hash with `git rev-parse
HEAD` rather than embedding a self-hash here.

The public signature and return value of
`tetris_ballistic.engine.validate_periodic_law` are unchanged. The preflight
now makes one canonical anchor-zero wrapping check per positive-weight geometry
instead of scanning every substrate column. It remains provisional, is not
exported from the package root, and is not routed through event selection,
configuration execution, a trajectory, legacy code, HPC, or production.

## Executable contract

- Validation and error precedence are unchanged: width, exact support-container
  type, nonempty support, geometry revalidation/snapshot, unique IDs, and the
  strict maximum-geometry-width guard all precede wrapping checks.
- For fixed width, cyclic horizontal translation is a bijection of lattice
  sites and an automorphism of the periodic N4 graph. Wrapping at anchor `a` is
  anchor-zero wrapping followed by translation by `a`; cell cardinality and the
  internal indexed N4 edge graph therefore have the same verdict at every
  anchor.
- The preflight performs exactly one `_validate_wrapping` call at anchor zero
  for each defensively reconstructed positive-weight geometry. Its anchor-check
  count is independent of substrate width.
- `place_one` still validates the actual supplied event anchor. No placement
  semantics, event selector, RNG schedule, public export, or serialized identity
  changed.

## Validation evidence

- Focused reference-engine suite: 35 passed.
- Width-`10**1000` regression: one anchor-zero check for each of the 20
  ratified geometries, with no width-linear scan.
- Independent all-anchor oracle: all 20 ratified geometries plus all 91
  deterministically generated fixed polyominoes through area five pass at
  three legal-width cases per geometry; a horizontal-I width-four negative
  control fails as required.
- Full default suite: 768 passed, 6 skipped, 6 deselected.
- Full slow suite: 6 passed, 774 deselected.
- CI-scope `ruff check tetris_ballistic/ tests/`, changed-file Ruff formatting,
  `compileall`, conflict scan, and `git diff --check`: passed.
- Clean PEP 517 sdist-to-wheel build, Twine, gzip/ZIP integrity, required-member
  audit, and foreign-directory exclusion: passed. The wheel SHA-256 is
  `99e7f524e36adeca4b358773b3af0ec284156780be2771c750d68fba9d6d3125`;
  the sdist SHA-256 is
  `1831ccd2b2baaee2c3c97387e4b5b92767b2dcbea724e136f9eb51d16ddeadd8`.
- Isolated final-wheel dependency checks, all 35 reference-engine tests,
  package-root export guards, and huge-width smokes passed on Python 3.10.18,
  3.11.13, 3.12.11, 3.13.7, and 3.14.6.
- Independent read-only code/contract and test/artifact reviews passed with no
  blocking findings.

Repository-wide `ruff format --check .` is not the configured CI gate and has
pre-existing unrelated formatting debt. The two changed Python files are
Ruff-formatted; do not mix a bulk repository reformat into this unit.

## Scope boundary

This unit changes only the manual complete-positive-support preflight's anchor
complexity and its proof/tests/documentation. It adds no selection-to-placement
composition, state transition, `SimulationConfig` adapter, legacy migration,
trajectory, canonical JSON, digest/shared artifact identity, checkpoint,
optimized kernel, CLI, batch runner, Slurm/HPC integration, release, or
production route. `engine/event.py`, `engine/rng.py`, `engine/selection.py`,
both package-root `__init__.py` files, and all historical exp13/exp14 behavior
remain unchanged.

## Provenance anchors and parallel-work guard

- S2.4 software baseline:
  `e44e8e335f06d982da8a0fa5b31b6efed9717c6e`.
- Final S2.4 Article closure:
  `3ebaa6c10798d6fb97cbaa6618d8266d7a6e0f48`.
- S2.4 authored wiki implementation page:
  `9a17e5f6a8b80b4b0a0ec9aaed98b3b2c3636a58`.
- S2.4 generated wiki dashboard:
  `5681476d03714c5341441c07ec699eecd2d810db`.

Another worker may own the six-repository pipeline. Do not edit, regenerate,
stage, or advance that pipeline's files. Any downstream Article/wiki update
must use the shared-repository bi-directional sync workflow first and stage
only explicitly audited Tetris provenance paths.

## Next bounded step

1. Commit and immediately push this software unit, then record its exact hash
   through the Article receipt -> authored wiki page -> generated dashboard ->
   final Article closure provenance loop.
2. Re-run the exact downstream preflights before each repository write and
   preserve concurrent foreign work.
3. Do not compose event selection with placement or configuration. Any further
   S2 unit requires a separately fixed contract, tests, scope, and approval;
   S3, Easley/HPC, release, and production gates remain closed.

## Pre-flight for a future software session

1. Stand at
   `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`.
2. Confirm `git status --short` has no tracked changes and only the foreign
   untracked `.omx/` and `.pi-subagents/` directories.
3. Confirm local `main` and `origin/main` are synchronized at this hardening
   authority or a documented later bounded unit.
4. Run `.venv/bin/python -m pytest -q` and
   `.venv/bin/python -m pytest -q -m slow` before another semantic change.
5. Keep the event and placement layers uncomposed until a separate approved
   gate authorizes that route.
