# HANDOFF

**Last updated**: 2026-07-14 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: M1.2/S2 reference-only binding of one already-selected
tetromino event to one slow-reference placement, without accumulation or a
trajectory

## Current state

The approved one-event binding slice is implemented over predecessor software
authority `fc02f7ff35935c8540f3cf43e320166b38f4aa2c`. The current
handoff-bearing commit will be the new software authority; after commit, obtain
its exact hash with `git rev-parse HEAD` rather than embedding a self-hash here.

The new explicit-only `tetris_ballistic.engine.binding` submodule defines
keyword-only `place_selected_event(*, state, selection)` and the frozen,
slotted two-field `ReferenceEventPlacement`. The function consumes one
already-created S2.4 `TetrominoEventSelection`, validates the complete positive
geometry support against the supplied S2.1 sparse state, delegates exactly one
placement, and retains both recertified certificates.

This slice completes the exact in-memory selection-to-placement relation for
one reference event. It completes neither Article S1a-09, M1.2, nor overall S2
and opens no accumulation, persistence, configuration, trajectory, HPC, or
production gate.

## Executable contract

- `place_selected_event` accepts only exact, fully initialized
  `SparseAggregate` and `TetrominoEventSelection` values and defensively
  reconstructs them in state-first order. It never calls `select_event`, any
  one-stream selector, RNG, or either observable extractor.
- The selection launch-law upper bound must equal the sparse-state width. An
  incidentally in-range selected anchor does not repair a mismatched law.
- Complete positive support is the fixed family-order/per-family-orientation-
  order tuple for which both the family count and orientation count are
  positive. Zero-family branches and zero-orientation slots remain in the law
  record but do not execute. Every reachable geometry is resolved through and
  checked against the ratified 19-orientation registry.
- `validate_periodic_law` checks that complete positive support before the
  placement call, so a narrow selected geometry cannot conceal a different
  reachable orientation that is invalid at the same width.
- The selected contact ID maps only to `ContactKind.SUPPORTED_V1` or
  `ContactKind.EDGE_FIRST_CONTACT_V1`. After validation, `place_one` is called
  exactly once with the frozen state, selected ratified geometry, launch, and
  contact endpoint.
- The delegated result must be one exact, fully recertified
  `ReferencePlacement` and must agree with the selection and input state in
  geometry ID and family, anchor, contact kind, pre-state, disjoint placed
  cells, and exact geometry-area mass increment. Malformed or inconsistent
  internal delegate results fail closed.
- `ReferenceEventPlacement` stores only the frozen selection and placement
  certificates. Direct construction reruns full nested, law-wide, and
  cross-field validation. The function avoids a redundant second preflight
  only after completing the identical checks itself.
- No Philox replay is performed. A direct structurally valid selection remains
  non-authenticating; a selection returned by `select_event` retains its
  certified address, complete law, and four semantic draws unchanged.
- Work is sparse plus a fixed scan of the 19-geometry registry and positive
  law support. It does not iterate or allocate in proportion to numerical
  width or height; exact-integer work still scales with bit length.

## Current validation evidence

- Focused binding suite: 32 passed.
- The independent differential oracle covers exactly 16,320 bindings: 6,080
  cases from all 19 geometries, five anchors, two contact endpoints, and every
  one-row occupancy at width five, plus 10,240 O-geometry cases over every
  two-row occupancy. Positive early-arrest gaps and seam contacts both occur.
- Combined reference placement, selection, binding, and observable suites:
  178 passed with one declared-slow test deselected.
- Exact field order, frozen/slots construction, direct recertification,
  forged/subclass/partial/mutable input rejection, caller detachment,
  law-width mismatch, hidden positive support, zero-support exclusion,
  runtime and pre-import ratified-registry drift, mutating/no-op/malformed
  preflight and placement delegates, exact one-call placement, maximum
  `2**64` sparse width, forbidden-layer imports/calls, and package-root export
  guards are covered.
- Independent post-repair audit passed 10,000 randomized differential cases,
  5,000 complete-support projections, 40 hidden/zero-support cases, all 38
  geometry/contact pairs at width `2**64` with 201-digit heights, identical
  interpreter-line counts at width five and `2**64`, and 21 registry/preflight/
  placement-delegate failure attacks. Two discovered authority-alias/import-
  order defects were repaired and their fresh-process regressions pass.
- Full default suite: 863 passed, 6 declared slow skips, 6 deselections.
- Declared slow suite: 6 passed, 869 deselections.
- CI-scope Ruff, changed-file Ruff format, compileall, and diff checks passed.
- Clean isolated PEP 517 sdist-to-wheel build and Twine passed. The 205-member
  sdist SHA-256 is
  `6b575472420c2cd9aab4327151c4cb3f66b222337b04bbd5d686834ba19136b0`;
  the 158-member wheel SHA-256 is
  `78596902dbba3c00b6e193c018d8aa7e27b6d2b9fecd1746cd197d1158fcaf25`.
  Every packaged source byte matches the staged tree, the binding/test files
  are byte-identical where intended, the focused 32-test suite passes from the
  unpacked sdist, and source-only tests remain absent from the wheel.
- Fresh full-dependency wheel installs, `pip check`, outside-repository exact
  event-binding smokes, and root-export guards passed on Python 3.10.18,
  3.11.13, 3.12.11, 3.13.7, and 3.14.6 with inherited Python paths explicitly
  removed. Certification artifacts are retained under
  `/home/lechen/.cache/tetris-binding-cert.qm2kjH`.

Repository-wide `ruff format --check .` is not the configured CI gate and has
pre-existing unrelated formatting debt. Check and format only the changed
Python files; do not mix a bulk repository reformat into this unit.

## Scope boundary

This unit binds one already-created S2.4 selection certificate to exactly one
S2.1 placement certificate in memory. It does not perform event selection or
RNG replay, accumulate event/contact counters, create checkpoints or
persistence, define canonical serialization or digest identity, expose a
`SimulationConfig` or legacy adapter, run a multi-event trajectory, or open an
optimized kernel, CLI, batch, Easley/Slurm/HPC, release, or production route.
The selection, placement, RNG, state, and observable certificate surfaces are
otherwise unchanged.

`engine/reference.py`, `engine/event.py`, `engine/rng.py`,
`engine/selection.py`, `engine/state.py`, `models.py`, every configuration
model/route, and both package-root `__init__.py` files remain unchanged.

## Provenance anchors and parallel-work guard

- Software authority immediately preceding this slice:
  `fc02f7ff35935c8540f3cf43e320166b38f4aa2c`.
- Preceding Article placement-primitives receipt:
  `51ff0365f01847948b1e3514619bf11c2d9f413b`.
- Preceding authored wiki implementation page:
  `2d63fa46b376befc848d98c6c0ccbe1289f995cc`.
- Preceding generated wiki dashboard:
  `c6a7488f64442c589ecc3766983a8991ce5a95ca`.
- Preceding final Article closure:
  `4a682382701a4ca9fbaf32eb6ea4925695062d9f`.

Another worker may own the multi-repository pipeline. Do not edit, regenerate,
stage, or advance that pipeline's files. Any downstream Article/wiki update
must use the shared-repository bi-directional sync workflow first and stage
only explicitly audited Tetris provenance paths.

## Next bounded step

1. Complete the software closure gates, commit only the audited one-event
   binding unit, and immediately push the new software authority.
2. Record that exact authority through the Article receipt -> authored wiki
   page -> generated dashboard -> final Article closure provenance loop, with
   a fresh preflight before each repository write.
3. Do not infer a following implementation unit. Event/contact accumulation,
   checkpoints/persistence, configuration, trajectories, S3, Easley/HPC,
   release, and production remain closed pending a separate contract and
   explicit approval.

## Pre-flight for a future software session

1. Stand at
   `/home/lechen/Dropbox/Public/Simulations_on_Some_Surface_Growth_Models`.
2. Confirm `git status --short` has no tracked changes and only the foreign
   untracked `.omx/` and `.pi-subagents/` directories.
3. Confirm Dell `main`, `origin/main`, and Greenwood are synchronized at this
   handoff-bearing authority or a documented later bounded unit.
4. Run the full default and slow suites before another semantic change.
5. Preserve the one-event binding boundary and keep accumulation, checkpoints,
   persistence, configuration execution, and multi-event routes closed until a
   separate approved gate authorizes them.
