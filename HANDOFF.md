# HANDOFF

**Last updated**: 2026-07-15 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: M1.2/S2 explicit-only exact in-memory folding of
already-bound reference tetromino events into a structural event/contact
accumulator, without a trajectory, checkpoint, or production route

## Current state

The bounded accumulator is implemented over local predecessor authority
`91da0299f7e8a196574ce9ed9d3f5177ec8a28fc`, which independently pins the
legacy physical-height convention and descends from published one-event binding
authority `e33d1998f52812d748b183d262d50297b8b776fd`. The repaired private
Article contract is commit `87a83b95b7a41f5b556c5f4735bce7f25844a613`,
with exact contract-file SHA-256
`7b7f4aef5df5cfd36a5642f7a2ac0011d7fefa602fe4bb5ede89dea0563eabe0`.

The current handoff-bearing commit will be the new software authority. After
commit, obtain its exact hash with `git rev-parse HEAD`; do not infer it from
this document or add a self-reference.

The new explicit-only `tetris_ballistic.engine.accumulation` module exports
exactly three names:

- frozen, slotted, 35-field `ReferenceEventAccumulator`;
- keyword-only `start_event_accumulator(*, empty_state, root_seed,
  coupling_group_id, law)`; and
- keyword-only `accumulate_event(*, accumulator, event)`.

Neither package root re-exports the surface. The unit does not call RNG, event
selection, placement, configuration execution, trajectory, persistence, I/O,
optimization, CLI, scheduler, or HPC code.

## Executable contract

- Start accepts only an exact canonical empty `SparseAggregate`, an exact
  unsigned 128-bit root, valid length-framed UTF-8 coupling-group text, and an
  exact `TetrominoEventLaw` whose launch bound equals the state width. Complete
  positive family-by-orientation support is checked against the private
  ratified 19-geometry authority and periodic-law preflight before construction.
- The accumulator stores defensively reconstructed root/group/law/width,
  event count, current state, independently measured mass/envelope/void totals,
  closed family/orientation/contact/face marginals, contact multiplicities and
  flags, sparse gap/topology maps, whole-envelope pre/post histograms, strict
  per-column envelope flow, contact-gap signed strata, topology joint strata,
  and cumulative exact deltas.
- Every scalar, nested key, record, and count uses recursive exact built-in
  types. Fixed tuples retain declared zero slots in canonical order; sparse
  tuples are immutable, positive-count, duplicate-free, and lexicographically
  sorted. Rule IDs are built-in strings; only face-count tuples use exact
  `ContactFaceKind` values.
- Support-gap signatures are translation-invariant least cyclic rotations.
  Empty support is `(clusters, span, signature) = (0, 0, ())`; ratified
  singleton-column support is `(1, 0, (L,))`. Geometry-width, arc-span,
  component, site/column, and orientation-weighted exposed-boundary capacities
  are structural invariants.
- Whole-envelope histograms include every width column at every event without a
  width-sized scan. Their totals are `width * event_count`, their net flow
  telescopes from the all-zero envelope, and their reachable height/key bounds
  follow four-cell growth. Strict envelope changes have exact per-column flow,
  at most four changes per event, and reproduce cumulative first and second
  height moments.
- Exact state identities include occupied mass `4 * event_count`, envelope
  volume equal to height sum, height sum equal to mass plus void count, and
  nonnegative roughness numerator `width * Q - S**2`. Contact-gap and topology
  tables reproduce all shared marginals and agree per endpoint on signed void
  and roughness sums. Each event void delta is at least `-4`.
- Final/causal face counts, per-event unique cell/site/column multiplicities,
  support flags, seam faces, causal trigger semantics, and pristine ratified
  geometry face capacities are cross-checked. Aggregate-above faces are never
  causal; support faces are causal exactly for non-positive-gap events, and
  positive-gap edge events have causal lateral faces.
- Each fold recertifies the accumulator and bound event, then requires exact
  root, group, law, width, ordinal, and pre-state continuity. It independently
  measures pre/post states, measures one detached placement exactly once, and
  cross-binds every consumed primitive to pristine event/state authorities
  before updating immutable tuples and adopting the certified post-state.
- Ordinals `0` through `2**64 - 1` are consumable. The final ordinal produces
  terminal count `2**64`; every later fold fails before placement measurement.
- A direct accepted value is a structurally consistent claimed-prefix summary,
  not an authenticated journal. Only an uninterrupted caller-observed
  start-to-fold chain procedurally establishes empty origin and one-step
  continuity. No RNG provenance, secret lineage, hash, digest, or historical
  realizability proof is claimed.

## Validation evidence

- Focused independent/adversarial accumulator suite: 47 passed in 11.00 s.
  It reconstructs all 35 expected fields from raw bound certificates and never
  uses either accumulator helper or observable extractor for expected values.
- Coverage-directed committed oracle: all 190 first-event combinations of 19
  orientations, five anchors, and two endpoints, plus 760 selected two-event
  chains. Every prefix is compared field-by-field; this is 1,710 certified
  folds and covers seams, positive and zero gaps, signed roughness directions,
  empty/singleton/multicolumn/multicluster support, and all orientations and
  endpoints.
- Deterministic profiled extension: 2,500 independent four-event chains and
  exactly 10,000 field-by-field certified folds pass in 49.555169 s. Checksums
  are mass `40000`, void `28511`, and roughness `467240`. Direct Linux process
  measurement records 141,560 KiB baseline RSS, 143,972 KiB sampled/process
  high-water RSS, and 143,972 KiB final RSS: 2,412 KiB incremental growth. A
  contaminated wrapper-inherited `ru_maxrss` value was rejected and is not the
  certified measurement. The oracle was not extrapolated to 100,000 folds.
- Named fixtures pin first horizontal-I `(M,S,Q,V,R)=(4,4,4,0,4)`, first LJ
  `(4,6,12,2,24)`, the positive-gap two-event telescope
  `(8,20,80,12,0)`, three-layer whole histograms, seam and incidental zero-gap
  contacts, and tied-largest-gap translation normalization.
- Constructor and delegate attacks cover all 35 fields, recursive type/order/
  duplicate/zero-count corruption, zero-law slots, joint/histogram/flow
  projections, order/registry/preflight drift, maximum sparse width `2**64`,
  exact UTF-8 byte limits, caller/delegate mutation, wrong/partial primitives,
  terminal fail-before-measurement, and package/later-layer exposure.
- A hostile line-by-line replay found and closed singleton-cluster,
  mutable-order, zero-event face, causal-above, signed-void, vertical-I
  topology, contact multiplicity, support site/column, orientation face
  capacity, and first-event-gap forgeries. Final verdict: PASS with no remaining
  literal or normative contract blocker.
- Combined reference placement/state observables, complete-event selection,
  event binding, and accumulation suites: 225 passed, one declared-slow test
  deselected.
- Full default suite: 916 passed, 6 declared-slow skips, 6 deselections.
- Declared slow suite: 6 passed, 922 deselections.
- Absolute physical-height convention pins: 6 passed.
- Changed-file Ruff, Ruff format, Python compilation/compileall, and diff checks
  pass. Repository-wide formatting debt remains outside this unit.
- Clean isolated PEP 517 sdist-to-wheel build and Twine checks pass. The
  208-member sdist SHA-256 is
  `4b1c638d97b0ac0bf7e5ad715ee855b4aa46d6558dcb049579cc9b4b8806f8fb`;
  the 159-member wheel SHA-256 is
  `37a31229c90669fdd502826e1f44e92c0d3a1223e7354650909c168494700d80`.
  The accumulator module is byte-identical in source, sdist, and wheel; the
  independent test, API specification, and changelog are byte-identical in the
  sdist; source-only tests remain absent from the wheel. The unpacked-sdist
  focused suite passes 47/47.
- Fresh full-dependency wheel installs, dependency checks, outside-repository
  exact start/bind/fold smokes, and package-root export guards pass on Python
  3.10.18, 3.11.13, 3.12.11, 3.13.7, and 3.14.6 with inherited Python paths and
  user sites removed. Certification artifacts are retained under
  `/home/lechen/.cache/tetris-accumulator-cert.ZrgCrn`.

## Scope boundary

This unit folds one existing `ReferenceEventPlacement` into a new exact
in-memory structural summary. It does not select an event, replay Philox, place
a piece, merge accumulators, define a journal, serialize an artifact, create a
checkpoint or persisted-byte identity, drive a trajectory, execute a typed
configuration, adapt a legacy simulation, or expose an optimized kernel, CLI,
batch, scheduler, Easley/Slurm/HPC, release, or production path.

Article S1a-09, M1.2, and overall S2 remain open. The next S2 closure still
requires selected occupancy checkpoints, canonical persisted-byte identity,
independent reconstruction, typed configuration execution, and a bounded
multi-event slow-reference trajectory with stop/checkpoint routing. S3 and all
experimental gates remain closed.

`engine/reference.py`, `engine/event.py`, `engine/rng.py`,
`engine/selection.py`, `engine/state.py`, `engine/binding.py`,
`engine/observables.py`, `models.py`, configuration/legacy routes, and both
package-root `__init__.py` files remain unchanged in this bounded unit.

## Provenance and next actions

1. Complete the clean package/interpreter gates listed above.
2. Stage only `tetris_ballistic/engine/accumulation.py`,
   `tests/test_reference_event_accumulation.py`, `docs/API-SPEC.md`,
   `CHANGELOG.md`, and `HANDOFF.md`; never stage foreign `.omx/` or
   `.pi-subagents/` directories.
3. Race-check origin, commit the verified unit, and push immediately. The push
   will also publish independent convention-pin ancestor `91da0299`.
4. Record the exact software authority through Article implementation receipt,
   isolated authored-wiki update, generated dashboard update, and final Article
   closure. Do not edit the watched Dropbox wiki tree directly.
5. Do not start checkpoint, trajectory, optimized, data-schema, scientific,
   Easley, or HPC work from this handoff alone. A separate approved bounded
   contract and clean preflight are required.
