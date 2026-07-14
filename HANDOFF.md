# HANDOFF

**Last updated**: 2026-07-14 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: M1.2/S2 pure reference-state primitives without
event or placement composition

## Current state

The approved pure-state slice is complete over software authority
`4e90a1c0daa5f1909277b0abe8f9091fbfca351a`. The current handoff-bearing
commit is the new software authority; obtain its exact hash with
`git rev-parse HEAD` rather than embedding a self-hash here.

The explicit-only `tetris_ballistic.engine.observables` submodule adds a pure
`measure_state(SparseAggregate)` extractor and a frozen, slotted
`ReferenceStatePrimitives` record. The complete interface envelope is retained
exactly as the width plus canonically sorted positive-column `(x, height)`
pairs; omitted columns have height zero. This representation remains exact
without imposing a width-sized or height-sized allocation.

This slice completes neither M1.2 nor overall S2 and opens no composition or
later gate.

## Executable contract

- `measure_state` accepts only an exact, fully initialized `SparseAggregate`
  and defensively reconstructs it before measurement.
- All scalar fields and every envelope coordinate/height are exact built-in
  integers. The record contains width, the sparse positive-column envelope,
  occupied mass, height sum, height-square sum, below-envelope volume, and void
  count.
- The envelope is sorted, unique, in range, and positive. Its exact identities
  are `height_sum = sum(height)`, `height_square_sum = sum(height * height)`,
  `below_envelope_volume = height_sum`, and
  `void_count = below_envelope_volume - occupied_mass`, with the number of
  nonzero columns no greater than occupied mass and occupied mass no greater
  than envelope volume.
- For occupied mass `m` and `k` occupied columns, expected container work is
  `O(m + k log k)` and peak snapshot/auxiliary memory is `O(m + k)`. There is
  no iteration or allocation proportional to the numerical width or maximum
  height; ordinary exact-integer work still scales with bit length.
- The module defines no floating observable, RNG draw, event/contact counter,
  selection or placement call, transition, configuration adapter, checkpoint
  I/O, canonical serialization, digest identity, persistence API, trajectory,
  legacy route, scheduler, release, or production route.

## Validation evidence

- Focused reference-observables suite: 39 passed.
- Independent dense oracle over 4,608 exhaustive small occupancy states (512
  at width/height 3 x 3 plus 4,096 at 4 x 3) agrees on the complete envelope
  and every exact scalar.
- Named empty, holey, seam-adjacent, and tied-maximum cases; exact
  width-`10**1000` and vertical-coordinate `y = 10**1000` regressions;
  caller/state-mutation detachment;
  forged/subclass/partial/hostile-container rejection; direct-record invariant
  checks; forbidden-call/import and package-root export guards: passed.
- Combined observables and reference-engine suites: 74 passed.
- Full default suite: 807 passed, 6 skipped, 6 deselected.
- Full slow suite: 6 passed, 813 deselected.
- CI-scope `ruff check tetris_ballistic/ tests/`, changed-file Ruff formatting,
  `compileall`, conflict scan, and `git diff --check`: passed.
- Clean PEP 517 sdist-to-wheel build, Twine, gzip/ZIP integrity, required-member
  audit, and foreign-directory exclusion: passed. The final wheel SHA-256 is
  `7ec99a311c76a8a3f47e16960532d079d9249995de65c8aa34366f4555c9ac02`;
  the final sdist SHA-256 is
  `70304c967eb0850c94209b2d2228228abf32cab5695149ec56253eeb0b399a49`.
- Isolated final-wheel explicit-import, dependency, root-export, exact-state,
  and huge-width/vertical-coordinate smokes passed on Python 3.10.18,
  3.11.13, 3.12.11, 3.13.7, and 3.14.6.
- Independent read-only code/contract, oracle, and package/provenance reviews
  passed after their documentation findings were incorporated.

Repository-wide `ruff format --check .` is not the configured CI gate and has
pre-existing unrelated formatting debt. The changed Python files are
Ruff-formatted; do not mix a bulk repository reformat into this unit.

## Scope boundary

This unit changes only the pure exact state-primitives surface, its tests, and
its contract/release documentation. It does not compose event selection with
placement, add event/contact instrumentation, expose a configuration or legacy
adapter, create checkpoints or trajectories, define a canonical encoding or
digest, or open an optimized kernel, CLI, batch, Easley/HPC, release, or
production route. `engine/reference.py`, `engine/event.py`, `engine/rng.py`,
`engine/selection.py`, `engine/state.py`, `models.py`, every configuration
model/route, and both package-root `__init__.py` files remain unchanged.

## Provenance anchors and parallel-work guard

- Periodic-law preflight implementation:
  `6e4f2fdf3fb67ac1fcf0674a7ddd7e54f27f286c`.
- Software authority immediately preceding this slice:
  `4e90a1c0daa5f1909277b0abe8f9091fbfca351a`.
- Preceding Article receipt:
  `8380a3b99dfbaca3b517ca1dd40dfc81b579781b`.
- Preceding authored wiki implementation page:
  `4230003c80c994033dda9d9dacb361365be3445c`.
- Preceding generated wiki dashboard:
  `873c2961d83c01c2394eed7c713c8fc42ffe7765`.
- Preceding final Article closure:
  `8b1f495bacf8b1ef709cae272ccea2ae17c0dae3`.

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
3. Do not infer a following implementation unit. Event/placement composition,
   configuration, trajectories, S3, Easley/HPC, release, and production remain
   closed pending a separate contract and explicit approval.

## Pre-flight for a future software session

1. Stand at
   `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`.
2. Confirm `git status --short` has no tracked changes and only the foreign
   untracked `.omx/` and `.pi-subagents/` directories.
3. Confirm Dell `main`, `origin/main`, and Greenwood are synchronized at this
   handoff-bearing authority or a documented later bounded unit.
4. Run `.venv/bin/python -m pytest -q` and
   `.venv/bin/python -m pytest -q -m slow` before another semantic change.
5. Keep event, placement, and configuration uncomposed until a separate
   approved gate authorizes that route.
