# HANDOFF

**Last updated**: 2026-07-14 EDT

**Project**: `Simulations_on_Some_Surface_Growth_Models`

**Current bounded unit**: M1.2/S2 pure primitives for one already-certified
reference placement, without selection-to-placement composition or accumulation

## Current state

The approved placement-primitives slice is implemented over predecessor
software authority `8335dff8693fed8dbf3601c55406869a503d36fb`. The current
handoff-bearing commit will be the new software authority; after commit, obtain
its exact hash with `git rev-parse HEAD` rather than embedding a self-hash here.

The explicit-only `tetris_ballistic.engine.observables` submodule retains the
pure `measure_state` surface and adds `measure_placement(ReferencePlacement)`
plus a frozen, slotted `ReferencePlacementPrimitives` companion. The input is
one already-created S2.1 placement certificate. The extractor defensively
reconstructs and recertifies it, then derives exact final/causal contact,
aggregate-support topology, canonical cyclic-support-arc, and sparse envelope-
change primitives.

This slice completes neither Article S1a-09, M1.2, nor overall S2 and opens no
composition, accumulation, persistence, execution, or production gate.

## Executable contract

- `measure_placement` accepts only an exact, fully initialized
  `ReferencePlacement`. Reconstruction reruns the existing geometry, landing,
  contact, and pre/post-state certificate checks before measurement. The
  extractor never calls `place_one`, `measure_state`, RNG, or selection.
- The 23 stored fields are `width`, `contact_kind`, `placed_mass`,
  `early_arrest_gap`, `lateral_trigger`, `contact_face_kinds`,
  `contact_face_kind_counts`, `causal_face_kind_counts`, `causal_contact_mask`,
  `seam_lateral_face_count`, `contacting_piece_cells`,
  `contacted_aggregate_cells`, `contacted_support_sites`,
  `contacted_support_columns`, `support_graph_edges`,
  `support_cluster_count`, `support_arc_origin`, `support_arc_span`,
  `support_column_gaps`, `envelope_changes`, `height_sum_delta`,
  `height_square_sum_delta`, and `void_count_delta`.
- `contact_face_kinds` retains the exact kind at every canonical
  `placement.contacts` position. Both face-count tuples contain every
  `ContactFaceKind` exactly once in enum order, including zeros. Causal-mask
  bit `i` indexes that sequence and is set exactly at causal-kind positions;
  no higher bit is set, and the mask population equals the causal-face count.
  Causal kinds are support faces unless a positive-gap edge-first landing
  triggered lateral arrest, in which case they are lateral faces.
- Contact endpoints are canonical sorted unique world cells. Aggregate-support
  sites exclude floor and all non-support aggregate contacts; support columns
  are exactly their sorted horizontal projection.
- `support_graph_edges` is the sorted canonical undirected graph induced on
  aggregate-support sites by periodic-horizontal and ordinary-vertical N4
  adjacency. `support_cluster_count` is its exact component count.
- The support arc excludes one largest forward cyclic column gap, breaking a
  tie by the smallest successor/origin column. Empty support has
  `(None, 0, ())`; singleton support at `x` has `(x, 0, (width,))`; otherwise
  the gap tuple starts at the origin and retains the excluded closing gap last,
  while `support_arc_span = width - largest_gap`.
- `envelope_changes` is the sorted unique tuple of strict sparse
  `(x, pre_height, post_height)` increases. Exact identities are
  `height_sum_delta = sum(post - pre)`,
  `height_square_sum_delta = sum(post**2 - pre**2)`, and
  `void_count_delta = height_sum_delta - placed_mass`; the void delta is
  intentionally signed.
- Six derived properties expose the total final and causal face counts and the
  cardinalities of contacting piece cells, contacted aggregate cells, support
  sites, and support columns. They store no additional state.
- Geometry identity, launch anchor, actual/counterfactual landing heights,
  complete directed faces, and pre/post states remain authoritative on the
  source `ReferencePlacement`; the primitive companion is not a persisted
  event schema or identity.
- After certificate reconstruction, extractor work stays sparse in pre-state
  mass/occupied columns, placed cells, contacts, and support sites. Total cost
  also includes the existing S2.1 landing/contact replay used to recertify the
  input. There is no iteration or allocation proportional to numerical width
  or maximum height; ordinary exact-integer work still scales with bit length.

## Current validation evidence

- Focused state-plus-placement observables suites: 63 passed.
- The independent placement oracle covers all 2,432 one-cell certificates from
  every occupancy of `3 x 2` and `4 x 2` windows, every anchor, and both exact
  contact kinds, plus named floor, incidental-contact, lateral-trigger, seam,
  support-cluster, cyclic-gap tie, sparse-envelope, and signed-void cases.
- Combined reference-engine plus both observables suites: 98 passed.
- Exact-field-order/frozen/slots construction, every direct-record invariant,
  forged/subclass/partial/hostile input rejection, caller-mutation detachment,
  canonical causal-mask indexing, huge-width/height sparse behavior, forbidden
  `place_one`/`measure_state`/RNG/selection calls, forbidden import coupling,
  and package-root export guards are covered.
- Independent adversarial review exhaustively checked 4,088 support-column
  subsets at widths 3--11, 37,376 periodic support-site subsets, and 60,000
  all-geometry placement/envelope comparisons. Its one causal-mask constructor
  finding was fixed with `contact_face_kinds` plus an exact same-popcount
  regression; the follow-up audit passed.
- Full default suite: 831 passed, 6 declared slow skips, 6 deselections.
- Declared slow suite: 6 passed, 837 deselections.
- CI-scope Ruff, changed-file Ruff format, compileall, and diff checks passed.
- Clean isolated PEP 517 sdist-to-wheel build and Twine passed. The sdist has
  203 members and SHA-256
  `82a809ec92a0d3c4987d70cb635ea62232ec25bb883ab4b405dd0a91cc132bdd`;
  the wheel has 157 members and SHA-256
  `741e61672e7fd9baeaeda9a43619d4a78a1886bfdb2a7c31f14326e9413e7531`.
  Live, staged, sdist, and wheel copies of `engine/observables.py` are
  byte-identical; source-only tests/docs occur only in the sdist as intended.
- Fresh full-dependency wheel installs, `pip check`, outside-repository exact
  placement/topology/envelope smokes, and root-export guards passed on Python
  3.10.18, 3.11.13, 3.12.11, 3.13.7, and 3.14.6 with inherited Python paths
  explicitly removed.

Repository-wide `ruff format --check .` is not the configured CI gate and has
pre-existing unrelated formatting debt. Check and format only the changed
Python files; do not mix a bulk repository reformat into this unit.

## Scope boundary

This unit is a pure projection of one supplied placement certificate. It does
not bind an S2.4 selection to S2.1 placement, assign an event ordinal, accumulate
event/contact counters, create checkpoints or persistence, define canonical
serialization or digest identity, expose a configuration or legacy adapter,
run a multi-event trajectory, or open an optimized kernel, CLI, batch,
Easley/Slurm/HPC, release, or production route. The placement certificate
itself is unchanged.

`engine/reference.py`, `engine/event.py`, `engine/rng.py`,
`engine/selection.py`, `engine/state.py`, `models.py`, every configuration
model/route, and both package-root `__init__.py` files remain unchanged.

## Provenance anchors and parallel-work guard

- Software authority immediately preceding this slice:
  `8335dff8693fed8dbf3601c55406869a503d36fb`.
- Preceding Article receipt:
  `07a866e312e915579a0890d3effacc163b900106`.
- Preceding authored wiki implementation page:
  `712ae48a11d7134a435af4b1d0c0394e2fb28fc8`.
- Preceding generated wiki dashboard:
  `7fba2f266add5b7e66391d2fad38883dbf13b65c`.
- Preceding final Article closure:
  `26b3e1b701c7a273ced03df327f1ea5ec7addc6e`.

Another worker may own the multi-repository pipeline. Do not edit, regenerate,
stage, or advance that pipeline's files. Any downstream Article/wiki update
must use the shared-repository bi-directional sync workflow first and stage
only explicitly audited Tetris provenance paths.

## Next bounded step

1. Complete the software closure gates, commit only the audited placement-
   primitives unit, and immediately push the new software authority.
2. Record that exact authority through the Article receipt -> authored wiki
   page -> generated dashboard -> final Article closure provenance loop, with
   a fresh preflight before each repository write.
3. Do not infer a following implementation unit. Selection/placement binding,
   accumulation/checkpoints, configuration, trajectories, S3, Easley/HPC,
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
5. Keep selection and placement uncomposed, and keep cumulative/event execution
   routes closed until a separate approved gate authorizes them.
