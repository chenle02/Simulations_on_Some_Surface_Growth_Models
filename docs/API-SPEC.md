# `tetris-ballistic` Community API and Architecture Specification

**Specification version:** 0.5.7

**Status:** M1.1 contracts plus provisional S2.1 exact placement, S2.2
counter-addressed semantic-RNG oracles, and S2.3 explicit-order exact-law/
one-stream selection records, plus S2.4 fixed-order tetromino event selection,
an explicit reference-only one-event selection-to-placement binder, and
pure exact reference-state and already-certified-placement primitive
extractors, plus an explicit-only exact in-memory event/contact accumulator
and separate explicit-only clean periodic one-cell transition and PRE
two-stream common-random-number event selector, plus an explicit-only
three-boundary scalar one-cell transition with archived and corrected
hard-wall laws, plus an explicit-only pre-derived-key compiled Philox and
exact bounded-integer implementation contract, plus an explicit-only exact
scalar common-draw four-schedule trajectory and accumulator fold, an
explicit-only Numba compiled multi-arm chunk backend with full-record scalar
equality, an explicit-only manifest-last checkpoint/final codec, an
explicit-only held-byte PRE campaign/task-map identity codec, and an
explicit-only fail-closed PRE launch/Slurm runner with single-use scheduler
claims and bounded interruption/requeue state; no production campaign,
admission, launch authority, Easley deployment certificate, scheduler action,
or scientific acquisition is created by the software slice

**Compatibility target:** backward-compatible 2.1.x transition, then 3.0.0 only after migration gates

## 1. Purpose and authority

`tetris-ballistic` is the public authority for simulation semantics, configuration validation, deterministic execution, observables, analysis algorithms, command-line interfaces, and scientific result-bundle schemas.

It must not contain manuscript drafts, private raw joblibs, project email, or mutable paper claims. Public datasets pin released package versions; the private Article repository owns scientific interpretation.

## 2. Users

1. Researchers running one-cell or tetromino surface-growth simulations locally.
2. HPC users launching reproducible parameter sweeps on Slurm.
3. Data analysts reanalyzing reduced trajectories without simulating.
4. Method developers adding a shape, orientation law, contact rule, observable, or estimator.
5. Referees reproducing a published figure from a released dataset.
6. Instructors using small deterministic examples.

## 3. Current baseline and debt

The current package already has PEP 621 metadata in `pyproject.toml`, public PyPI distribution, GitHub CI for Python 3.10--3.12, pytest/ruff, Slurm runners, streaming analysis, and a deterministic numba fast path for one-cell `piece_19` workloads.

The migration must explicitly address:

- the approximately 2,509-line legacy core `tetris_ballistic/tetris_ballistic.py`;
- wildcard exports in `tetris_ballistic/__init__.py`;
- duplicated packaging metadata in `setup.py` and `pyproject.toml`;
- the one-cell-only optimized kernel in `tetris_ballistic/_kernel_1x1.py`;
- mixed-piece workloads falling back to the legacy dispatch path;
- absent stable console entry points;
- legacy modules/tests excluded from current lint or default test collection;
- tag publishing through an old token-based GitHub Actions workflow;
- analysis scripts whose contracts are implicit rather than schema-versioned.

No legacy path is removed before migration and golden-equivalence tests pass.

## 4. Design principles

- Geometry, orientation probability, piece-mixture probability, and contact/adhesion behavior are independent objects.
- All public configurations are immutable after validation and canonically serializable.
- Every stochastic output records the RNG algorithm, root seed, and seed-derivation rule.
- Every numerical artifact is schema-versioned and bound to configuration and geometry hashes.
- Public APIs use explicit imports and typed return values.
- Reference implementations remain available to validate optimized kernels.
- Scientific clocks are named, stored, and never inferred silently.
- Breaking changes require a major version and a documented migration path.

## 5. Proposed package layout

After the compatibility transition, the source tree should become

```text
src/tetris_ballistic/
  __init__.py
  model/
    geometry.py
    orientations.py
    ensembles.py
    contact.py
    clocks.py
    config.py
  engine/
    simulator.py
    state.py
    rng.py
    reference.py
    kernels/
      one_cell.py
      tetromino.py
  observables/
    interface.py
    porosity.py
    contacts.py
  analysis/
    growth.py
    scaling.py
    distributions.py
  io/
    schema.py
    bundles.py
    legacy.py
  cli/
    main.py
```

The migration may happen module-by-module while the installed import name remains `tetris_ballistic`.

## 6. Typed public model

### 6.1 Geometry

`PieceGeometry` is an immutable value object with

- stable string ID;
- canonical occupied integer coordinates;
- area;
- width and height;
- symmetry metadata;
- canonical orientation IDs;
- deterministic software-local JSON record and a profile-qualified SHA-256 digest.

Stored coordinates are `(row, column)` pairs whose row increases downward.
They are translated so the minimum row and column are zero, sorted
lexicographically, duplicate-free, and nonempty. The provisional
`world_coordinates` property exposes the reflected public placement view as
`(delta_y, delta_x)` pairs:

```text
delta_y = geometry.height - 1 - row
delta_x = column
```

This property is a derived view. It is deliberately absent from the
`tetris-ballistic/software-geometry-record@1` payload, so existing canonical
geometry records and digests do not change. Engine cells use `(x, y)` order;
callers must not treat the property's `(delta_y, delta_x)` pairs as engine
cells without swapping the two components.

### 6.2 Canonical tetromino registry

Terminology is fixed as follows: a **free tetromino** identifies shapes modulo translations, rotations, and reflections; a **fixed tetromino orientation** identifies occupied coordinates modulo translation only. The registry represents the five free families and the 19 fixed orientation geometries obtained by applying the dihedral transforms and deduplicating normalized coordinates. Reflection-related families such as L/J and S/Z therefore share a free-family identity but retain distinct fixed orientation IDs when their occupied coordinates differ. IDs must not depend on Python hash order or registry insertion order.

Acceptance tests must verify

- area four for each tetromino orientation;
- exactly five free families;
- exactly 19 distinct fixed orientations under the project convention;
- expected symmetry-related orientation counts;
- round-trip canonical serialization;
- no duplicate normalized coordinates.

The one-cell baseline is a separate geometry, not a tetromino.

### 6.3 Ensembles and orientation laws

`PieceEnsemble` maps free-family IDs (or the separate one-cell baseline family)
to normalized nonnegative probabilities. `OrientationDistribution` maps each
selected free family to probabilities on its canonical orientation IDs.
Zero-total, negative, nonfinite, unknown, or duplicate entries are rejected.

Constructors should include

- pure geometry;
- equal free-shape mixture;
- equal fixed-orientation mixture;
- user-supplied weighted mixture;
- isotropic orientation law;
- explicit orientation bias.

### 6.4 Contact rules

`ContactRule` defines placement mechanics independently of geometry:

- mechanically supported/nonadhesive placement;
- the versioned `legacy-sticky-v1` compatibility mechanic, meaning the pinned
  geometry-specific `sticky=True` hard-wall branches;
- the provisional periodic `supported-v1` and N4
  `edge-first-contact-v1` reference mechanics;
- a validated probabilistic mixture of named rules.

The public result records the realized rule for each event or sufficient
deterministic RNG provenance to reconstruct it. During 2.1.x, legacy input
named `sticky` maps only to `legacy-sticky-v1`; it is never an alias for a
generic first-contact law. The unversioned `first-contact` prototype and both
versioned generic laws, `supported-v1` and `edge-first-contact-v1`, have no
legacy-adapter mapping.

The older enum values `supported` and `first-contact` remain unchanged as
unversioned compatibility/prototype identities. They are not aliases for the
new versioned values and are rejected by the S2.1 reference oracle. The
`ContactRule.supported_v1()` and `ContactRule.edge_first_contact_v1()`
factories can represent the new identities in typed configuration records,
but no `SimulationConfig` execution route consumes them yet.

### 6.5 Provisional S2.1 single-event reference oracle

The slow deterministic oracle is available only through an explicit
provisional import:

```python
from tetris_ballistic.engine import (
    ContactFace,
    ContactFaceKind,
    ReferencePlacement,
    SparseAggregate,
    place_one,
    validate_periodic_law,
)
```

These names are intentionally not re-exported from `tetris_ballistic`. The
existing package-root import surface and legacy trajectory dispatch remain
unchanged.

#### State and validation boundary

`SparseAggregate(width, occupied)` is a finite immutable snapshot on the
periodic lattice `{0, ..., width - 1} x {0, 1, ...}`. It accepts only a plain
`list`, `tuple`, `set`, or `frozenset` of plain integer `(x, y)` pairs, rejects
duplicate sequence entries, requires canonical horizontal coordinates and
nonnegative vertical coordinates, and freezes the result as a `frozenset`.
`width` must be a built-in integer of at least three. A snapshot need not be
reachable by deposition; arbitrary legal finite states are accepted so the
type can support exhaustive transition tests. `SparseAggregate.empty(width)`
constructs an empty state, and `mass` is the exact occupied-cell count.

`place_one(state, geometry, anchor_x, contact_kind)` accepts exact
`SparseAggregate`, `PieceGeometry`, and `ContactKind` instances. The anchor
must be a built-in integer already in `[0, width)`; the function does not
silently normalize it. Only `ContactKind.SUPPORTED_V1` and
`ContactKind.EDGE_FIRST_CONTACT_V1` execute. Generic periodic placement also
requires `state.width > geometry.width` and rejects any wrap that merges two
piece cells or changes the geometry's internal N4 adjacency graph. Inputs are
not mutated. The state and geometry are reconstructed through their public
validators at the boundary, so exact-type instances with forged mutable or
invalid internals fail closed or are defensively frozen before use.

An enclosing multi-geometry law must separately call
`validate_periodic_law(width, positive_geometries)` with its complete
positive-weight geometry support. This manual configuration-wide preflight
requires a nonempty plain list or tuple with unique geometry IDs, defensively
revalidates and snapshots every geometry, requires width at least three and
strictly greater than every positive geometry's bounding-box width, and checks
the periodic cardinality/N4-adjacency invariant at canonical anchor zero. This
single check is complete: for fixed width, cyclic horizontal translation is a
bijection of lattice sites and an automorphism of the periodic N4 graph, while
wrapping at anchor `a` is anchor-zero wrapping followed by translation by `a`.
Consequently neither cell collisions nor internal N4 edges depend on the
anchor. The number of wrapping checks is independent of substrate width after
the width guard. The preflight returns the validated immutable geometry tuple.
The one-event function cannot infer a mixture's other positive-weight
geometries, and this preflight is not a `SimulationConfig` execution route.
`place_one` still checks the actual supplied anchor for each event.

For each reflected local `(delta_y, delta_x)` cell, an anchor height `y`
produces the world cell

```text
((anchor_x + delta_x) % width, y + delta_y).
```

A placement is valid when every resulting height is nonnegative, wrapping
preserves the geometry's area, and no resulting cell overlaps the pre-event
aggregate. Support means that moving the piece down by one row would meet the
aggregate or cross the floor immediately below `y = 0`. Lateral contact means
that a periodic left or right N4 neighbor of a piece cell belongs to the
pre-event aggregate.

- `supported-v1` chooses the maximum valid anchor height having support.
- `edge-first-contact-v1` chooses the maximum valid anchor height having
  support or lateral contact.

The maximum is spawn-height independent. The implementation has no fixed
vertical capacity. Diagonal, radius-two, upward, and remote contacts do not
stop descent, and the piece never moves horizontally, rotates, rolls, slides,
or relaxes after contact.

#### Placement result

`place_one` returns a `ReferencePlacement` with these exact provisional
fields:

| Field | Meaning |
|---|---|
| `geometry_id` | Stable ID of the fixed input geometry. |
| `geometry` | Defensively revalidated immutable fixed geometry. |
| `contact_kind` | Executed versioned endpoint. |
| `anchor_x` | Canonical launch/placement anchor. |
| `landing_y` | Actual final anchor height. |
| `supported_landing_y` | Supported-only counterfactual on the same input. |
| `early_arrest_gap` | `landing_y - supported_landing_y`, always nonnegative for an oracle result. |
| `piece_cells` | Canonically sorted final `(x, y)` cells. |
| `contacts` | Canonically sorted complete set of directed N4 aggregate faces plus floor support. |
| `stopping_contacts` | Final faces enabled by the selected stopping predicate. |
| `causal_contacts` | Counterfactually causal support or lateral subset. |
| `pre_state` | Defensively revalidated immutable pre-event snapshot. |
| `post_state` | New sparse snapshot equal to the pre-state union `piece_cells`. |

Each `ContactFace` stores `kind`, `piece_cell`, `neighbor_cell`, and the
explicit Boolean `crosses_seam`. Its kind is one of `floor-support`,
`aggregate-support`, `lateral-left`, `lateral-right`, or `aggregate-above`.
These records cover every external directed N4 face from a final piece cell to
the floor or pre-event aggregate; internal piece-to-piece faces are not
contacts. Floor support uses `neighbor_cell=None`. Every aggregate contact
names the exact pre-event neighbor. `crosses_seam` is true exactly for a
left/right face wrapping between columns zero and `width - 1`; support and
above faces never cross the seam.

For `supported-v1`, `stopping_contacts` contains final floor and aggregate
support faces. For `edge-first-contact-v1`, it contains every final support
and lateral face enabled by that predicate. `causal_contacts` is narrower: it
contains support faces when the early-arrest gap is zero and lateral faces
when an edge-first event has positive gap. A zero-gap lateral face is therefore
recorded in `contacts` and, for edge-first, in `stopping_contacts`, but remains
incidental rather than causal. `aggregate-above` is recorded for completeness
but never belongs to either subset because upward contact is not a stopping
condition.

Direct constructors also fail closed. `ContactFace` requires exact immutable
cell tuples and enum/Boolean types, enforces the floor representation, requires
a neighbor for aggregate faces, and permits a seam flag only on lateral
faces. `ReferencePlacement` defensively revalidates and snapshots its geometry
and pre/post states, binds `geometry_id` to that geometry, requires exact
immutable canonical cell/contact tuples, and validates the executable rule,
anchor, nonnegative heights, and gap identity. It reconstructs the placed
cells from geometry/anchor/height, checks non-overlap and the exact
`post_state = pre_state union piece_cells` transition, recomputes
both the supported counterfactual and selected-law maximum landing heights,
and reconstructs the complete contacts, stopping subset, and nonempty causal
subset in canonical order. Direct construction is therefore subject to the
same one-event law and cross-field consistency checks as `place_one`.

`ReferencePlacement.lateral_trigger` is the exact derived indicator for an
`edge-first-contact-v1` event with positive gap.
`contacted_support_columns` is the sorted set of aggregate-support columns,
excluding floor support.

#### Stability and explicit exclusions

This S2.1 surface is an event-level correctness oracle, not a production
simulator or a persisted scientific protocol. Until its exhaustive acceptance
suite and a separately versioned shared schema are approved, the
`tetris_ballistic.engine` names, result fields, contact representation, and
ordering are provisional.

The S2.1 slice deliberately provides none of the following:

- package-root exports for engine symbols;
- routing from `SimulationConfig`, `simulate`, or `Tetris_Ballistic`;
- event selection, law-specific stream scheduling, or trajectory draw
  accounting (the separate S2.2 module supplies only stateless RNG primitives);
- multi-event trajectories, event journals, checkpoints, observables, or
  stopping plans;
- optimized kernels, benchmark claims, Slurm/HPC dispatch, or batch tooling;
- a mapping from either versioned generic law to the legacy 20-by-2 density
  table or `legacy-sticky-v1` branches;
- a shared serialization profile, canonical event digest, result-bundle
  schema, or cross-repository identity; or
- the future lossless production event schema beyond this placement record,
  including envelope deltas, support-cluster summaries, and contact-site
  graphs.

### 6.6 Provisional S2.2 semantic RNG oracle

`tetris_ballistic.engine.rng` is an explicit-submodule, stateless reference
implementation of `semantic-philox4x64-10-v1`. It is not re-exported from
`tetris_ballistic` or `tetris_ballistic.engine` and is not connected to
`SimulationConfig`, the legacy simulator, or a trajectory loop.

The provisional surface contains

- `derive_stream_key(root_seed, coupling_group_id, stream_name)`, using an
  exact unsigned 128-bit root serialized as 16 big-endian bytes and the first
  128 SHA-256 bits of the frozen domain/root/four-byte-length-prefixed UTF-8
  nonempty group and stream preimage, encoded exactly without Unicode
  normalization;
- `philox4x64_10(counter, key)`, the pure Random123 ten-round four-by-64-bit
  bijection;
- `raw_u64(...)`, returning lane zero for the exact counter
  `(event_ordinal, rejection_ordinal, 0, 0)`;
- `uniform_below(...)`, using the frozen unbiased rejection map for every
  integer bound from 1 through `2**64`; and
- `categorical_index(...)`, which accepts only an ordered, nonempty canonical
  vector of exact nonnegative integer counts, with positive total at most
  `2**64` and greatest common divisor one across positive entries.

S1a fixed UTF-8 length framing but did not spell out empty-name or Unicode
normalization behavior. S2.2 ratifies two fail-closed encoding refinements:
coupling-group and stream identifiers are nonempty, and their exact code-point
sequences are UTF-8 encoded without normalization. Visually equivalent but
byte-distinct names therefore denote different streams.

`uniform_below` and `categorical_index` return an immutable `SemanticDraw`
containing the selected value and the zero-based rejection ordinal whose word
was accepted. Inputs fail closed on bools, integer/string subclasses, negative
or overflowing words, malformed tuple/container shapes, non-UTF-8 surrogate
text, noncanonical count vectors, and counter wrap. No floating-point or
high-level NumPy distribution participates in these semantics.

The conformance boundary includes upstream Random123 known-answer vectors plus
independently derived project key, raw, bounded-integer, and categorical
vectors, recorded in `docs/SEMANTIC-RNG-VECTORS.md`. The S2.2 oracle itself
does not define model-law records, stream declarations, conditional selection,
placement composition, checkpoints, serialization, a stateful generator, or
scheduling. It also supplies no root export, legacy migration, optimized
kernel, CLI, batch, Slurm/HPC, or production route.

### 6.7 Provisional S2.3 exact law-selection records

`tetris_ballistic.engine.selection` is an explicit-submodule, stateless layer
over the S2.2 primitives. It is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`, and it does not modify the existing float-normalized
`PieceEnsemble`, `OrientationDistribution`, `ContactRule`, or
`SimulationConfig` records.

The provisional surface contains

- `ExactWeightedLaw(outcome_ids, counts)`, an immutable record whose ordered,
  unique, nonempty exact UTF-8 outcome IDs and equally long canonical integer
  counts retain both caller order and zero-count positions;
- `UniformIntegerLaw(upper_bound)`, an immutable exact bound in
  `[1, 2**64]`;
- `DeclaredStreamSet(stream_names)`, an immutable, ordered, nonempty, unique
  exact UTF-8 declaration record;
- `select_weighted(...)`, which requires an explicitly named stream to be in
  the declared record before delegating the exact count vector to
  `categorical_index`; and
- `select_uniform(...)`, which applies the same declared-membership check
  before delegating the exact bound to `uniform_below`.

Both selectors are keyword-only, validate and defensively reconstruct every
address and record before the RNG call, and return an immutable selection that
retains the complete `SemanticDraw`. A one-outcome law or a bound of one still
reads one logical RNG variate. There is no fallback, coercion, implicit stream,
floating normalization, mapping-order inference, zero-slot removal, or modulo
repair. A delegated draw that selects an out-of-range or zero-count position
fails closed.

`WeightedSelection` and `UniformSelection` are immutable value records, not
standalone authenticated artifacts: they do not bind the request address or
law, and direct construction does not verify those absent fields. The semantic
guarantee applies to values returned by the selectors with the certified
in-package S2.2 oracle. S2.4 separately adds a complete tetromino record that
structurally carries its address and law; replay-authenticated serialization
and identity remain deferred.

The ordered outcome tuple is the complete executable order for that one
record. S2.3 does **not** declare a global canonical family or contact order,
provide named tetromino/control factories, resolve conditional orientation
laws, or evaluate a full event. `DeclaredStreamSet` establishes exact
membership and record order; the one-stream selectors do not claim that every
declared stream has been consumed. S2.4 separately fixes the tetromino
dependency order, full branch-table validation, and complete in-memory event
record; generic conditional selection, named law factories, and portable
artifact materialization remain deferred.

The conformance vectors in `docs/EXACT-SELECTION-VECTORS.md` use explicit
outcome tuples; they are test records, not aliases for a future named model
law. No canonical JSON, digest/profile, shared `model_law_id`, configuration
adapter, placement call, trajectory, legacy route, optimized kernel, CLI,
batch, Slurm/HPC, or production path is supplied.

### 6.8 Provisional S2.4 complete tetromino event selection

`tetris_ballistic.engine.event` is an explicit-submodule-only composition of
the S2.2/S2.3 primitives. It fixes the executable family order
`("i","lj","o","sz","t")`, contact order
`("supported-v1","edge-first-contact-v1")`, and stream schedule
`("family","orientation","launch","contact")`. It is not re-exported from
`tetris_ballistic` or `tetris_ballistic.engine`.

The provisional surface contains

- `ConditionalWeightedLaw(branch_ids, branch_laws)`, an immutable complete
  ordered branch table;
- `TetrominoEventLaw(family_law, orientation_laws, launch_law, contact_law)`,
  which requires the exact family/contact orders and all five orientation
  branches in family order, including branches unreachable under zero family
  counts;
- `TetrominoEventSelection`, a structurally consistent in-memory record that
  carries the root seed, coupling group, event ordinal, frozen complete law,
  and all four selections with accepted-rejection metadata; and
- keyword-only `select_event(...)`, which validates the full address, nested
  law, and fixed schedule before any RNG call, then draws family, the selected
  family's orientation, launch, and contact exactly once in that order.

Every orientation outcome tuple must equal the corresponding exact
2/8/1/4/4 `FAMILY_ORIENTATION_IDS` registry tuple. No mapping-order inference,
sorting, selected-family salt, geometry salt, arm salt, width salt, or law salt
is permitted. Degenerate laws still consume one logical raw candidate from
their stream. Only the selected orientation branch is evaluated; every branch
is nevertheless prevalidated and retained as in-memory law evidence.

The coupling contract is the shared raw candidate tape at an equal base event
address. Equal root seed, coupling group, event ordinal, and literal stream
name identify `W_0,W_1,...`. Each law performs its own rejection/acceptance map,
so unequal bounds can accept different candidates and values without shifting
another stream or event. `docs/COMPLETE-EVENT-SELECTION-VECTORS.md` pins the
full event and unequal-bound rejection examples.

Direct `TetrominoEventSelection` construction checks structural consistency
but does not replay Philox; canonical serialization, digest identity, and
portable artifact verification remain deferred. S2.4 supplies no generic
conditional DAG, named control law, placement, configuration/legacy adapter,
trajectory, optimized kernel, CLI, batch, Slurm/HPC, or production path.

### 6.9 Provisional pure reference-state primitives

`tetris_ballistic.engine.observables` is an explicit-submodule-only, pure state
measurement surface. It is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`, and neither package `__init__.py` changes.

`measure_state(state)` requires and defensively reconstructs an exact
`SparseAggregate`, then returns a frozen, slotted `ReferenceStatePrimitives`
record with

- `width`;
- `nonzero_column_heights`, the canonically sorted `(x, h_x)` pairs for
  positive-height columns, with omitted columns exactly representing height
  zero and each stored height equal to one plus the maximum occupied `y` in
  that column;
- `occupied_mass`;
- `height_sum` and `height_square_sum`;
- `below_envelope_volume`, exactly equal to `height_sum`; and
- `void_count`, exactly `below_envelope_volume - occupied_mass`.

The width plus sparse pairs reconstructs the complete integer interface
envelope without allocating a width-sized or height-sized array. For occupied
mass `m` and `k` occupied columns, expected container work is
`O(m + k log k)` and peak snapshot/auxiliary memory is `O(m + k)`. The
implementation does not iterate or allocate in proportion to the numerical
magnitude of substrate width or maximum occupied height; ordinary big-integer
arithmetic still scales with their bit length. This is required because valid
exact sparse states may carry arbitrarily large integer widths and heights.

Direct record construction rejects non-built-in integer values, malformed or
noncanonical sparse pairs, zero/negative stored heights, out-of-range or
duplicate columns, and inconsistent exact identities. In particular it
requires

```text
k <= occupied_mass <= height_sum,
height_sum = sum(h_x),
height_square_sum = sum(h_x**2),
below_envelope_volume = height_sum,
void_count = height_sum - occupied_mass.
```

This state slice deliberately computes no floating-valued mean height, surface
width/roughness, or porosity ratio. It adds no event/contact counters, RNG,
event selection, placement call or composition, state transition,
configuration adapter, checkpoint I/O, canonical serialization or digest
identity, persistence API, trajectory, legacy route, optimized kernel, CLI,
scheduler, Slurm/HPC, release, or production path.

### 6.10 Provisional pure reference-placement primitives

The same explicit-only `tetris_ballistic.engine.observables` submodule also
defines `measure_placement(placement)`. Its input is one **already-created**,
exact `ReferencePlacement`; the function does not select or place an event.
It accepts only the exact record type and defensively reconstructs that record,
thereby rerunning the S2.1 placement certificate's geometry, landing, contact,
and pre/post-state checks before deriving any primitive. It never calls
`place_one`, `measure_state`, an RNG surface, or an event-selection surface.

The result is a frozen, slotted `ReferencePlacementPrimitives` companion with
the following stored fields:

- `width`, the common periodic width of the certified pre/post states;
- `contact_kind`, restricted to `supported-v1` or
  `edge-first-contact-v1`;
- `placed_mass`, the exact positive post-state minus pre-state mass;
- `early_arrest_gap` and `lateral_trigger`, where `lateral_trigger` is true
  exactly for an `edge-first-contact-v1` certificate with positive gap, and a
  supported certificate has zero gap;
- `contact_face_kinds`, the exact `ContactFaceKind` sequence in canonical
  `placement.contacts` order;
- `contact_face_kind_counts` and `causal_face_kind_counts`, each a complete
  tuple of `(ContactFaceKind, count)` pairs in enum order, including zero
  counts for `floor-support`, `aggregate-support`, `lateral-left`,
  `lateral-right`, and `aggregate-above`;
- `causal_contact_mask`, a nonnegative exact integer whose bit `i` indexes the
  canonical `placement.contacts` tuple and is set exactly when that final face
  is in `placement.causal_contacts`;
- `seam_lateral_face_count`, the number of final left/right lateral faces
  whose directed neighbor relation crosses the periodic seam;
- `contacting_piece_cells`, the sorted unique piece-cell endpoints of all
  final face contacts;
- `contacted_aggregate_cells`, the sorted unique non-floor neighbor endpoints
  of all final face contacts;
- `contacted_support_sites`, the sorted unique aggregate-neighbor endpoints of
  the `aggregate-support` faces, and `contacted_support_columns`, their sorted
  unique horizontal projection;
- `support_graph_edges`, the canonical undirected edge tuple of the graph
  induced by `contacted_support_sites` under periodic-horizontal and ordinary-
  vertical N4 adjacency, with each edge's endpoints lexicographically ordered
  and the edge tuple sorted;
- `support_cluster_count`, the exact number of connected components of that
  induced graph, including zero for an empty support-site set;
- `support_arc_origin`, `support_arc_span`, and `support_column_gaps`, the
  canonical cyclic summary of the distinct support columns;
- `envelope_changes`, the sorted sparse tuple of only strict
  `(x, pre_height, post_height)` increases caused by the certified piece; and
- `height_sum_delta`, `height_square_sum_delta`, and `void_count_delta`, the
  exact signed/integer changes implied by the sparse envelope and placed mass.

The record also exposes derived read-only properties `contact_face_count`,
`causal_contact_face_count`, `contacting_piece_cell_count`,
`contacted_aggregate_cell_count`, `contacted_support_site_count`, and
`contacted_support_column_count`. These are tuple cardinalities or sums of the
stored count vectors; they add no independent state.

The final count vector exactly counts `contact_face_kinds`. The causal count
vector is the final support-face vector for a supported
landing or an edge-first landing with zero gap, and it is the final lateral-
face vector for an edge-first landing with positive gap; all other causal-kind
counts are zero. The causal mask sets exactly the positions in
`contact_face_kinds` belonging to that causal-kind set, no bit at or above
`contact_face_count`, and its population equals `causal_contact_face_count`.
Support sites are a subset of contacted aggregate cells, their multiplicity
equals the aggregate-support face count, and support columns are exactly their
horizontal projection.

For sorted distinct support columns `x_0, ..., x_(r-1)` at width `L`, define
each forward cyclic gap by `(x_(i+1) - x_i) mod L`. The canonical support-arc
rules are:

- no columns: `(support_arc_origin, support_arc_span,
  support_column_gaps) = (None, 0, ())`;
- one column `x`: `(x, 0, (L,))`; and
- two or more columns: exclude a largest cyclic gap, breaking a tie by the
  numerically smallest successor column; that successor is the origin, the
  span is `L - largest_gap`, and the gap tuple starts at the origin and retains
  the excluded closing gap as its final entry.

Thus every nonempty gap tuple sums to `L`, and for two or more columns its
entries except the final excluded gap sum to `support_arc_span`. The graph and
arc are summaries of aggregate support sites only; floor support, lateral
neighbors, and aggregate-above neighbors do not become support sites.

If `envelope_changes = ((x_j, a_j, b_j), ...)`, each entry has
`0 <= a_j < b_j`, columns are unique and sorted, and the exact identities are

```text
height_sum_delta = sum(b_j - a_j),
height_square_sum_delta = sum(b_j**2 - a_j**2),
void_count_delta = height_sum_delta - placed_mass.
```

`void_count_delta` is intentionally signed. The source `ReferencePlacement`
remains authoritative for geometry identity, launch anchor, actual and
counterfactual landing heights, complete directed face records, and pre/post
states; this companion neither duplicates those fields nor declares a
persisted event schema or identity.

Let `m` be pre-state mass, `k` its occupied-column count, `p` the placed-cell
count, `c` the final-face count, and `s` the aggregate-support-site count.
After defensive certificate reconstruction, expected extractor container work
is bounded by `O(m + c log c + (k + p) log(k + p) + s log s)` with sparse
auxiliary storage. Total call cost also includes the existing
`ReferencePlacement` landing/contact replay used for recertification. Neither
phase iterates or allocates in proportion to the numerical magnitude of width
or maximum height; exact-integer work still scales with bit length.

This is a pure one-certificate projection. It adds no selection-to-placement
binding, event ordinal, counter accumulation, checkpoint or persistence
contract, canonical serialization or digest identity, configuration or legacy
route, multi-event trajectory, optimized kernel, CLI, scheduler, Easley/Slurm/
HPC route, release, or production path. Article S1a-09, M1.2, and overall S2
therefore remain open.

### 6.11 Provisional reference event-placement binding

`tetris_ballistic.engine.binding` is an explicit-submodule-only bridge from one
already-created S2.4 selection certificate to one S2.1 slow-reference
placement. It is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`. The provisional surface contains

- frozen, slotted `ReferenceEventPlacement(selection, placement)`, whose two
  stored fields retain defensively reconstructed `TetrominoEventSelection` and
  `ReferencePlacement` certificates; and
- keyword-only `place_selected_event(*, state, selection)`, which accepts an
  exact `SparseAggregate` and exact `TetrominoEventSelection`.

Validation proceeds state first and then selection. The launch-law upper bound
must equal the state width; an incidentally in-range selected anchor does not
repair a mismatched launch law. Before placement, the binder derives the full
positive joint geometry support in fixed family and per-family orientation
order: a geometry is reachable exactly when both its family count and its
orientation count are positive. Zero-family branches and zero-orientation
slots are retained in the selection law but excluded from the executable
support. Every reachable ID is resolved through the ratified 19-orientation
registry, its family is checked, and `validate_periodic_law` preflights that
complete support. Thus a narrow selected geometry cannot hide a different
reachable orientation that is invalid at the same periodic width.

The selected contact ID maps only to `ContactKind.SUPPORTED_V1` or
`ContactKind.EDGE_FIRST_CONTACT_V1`. After all caller-controlled validation and
law-wide preflight pass, the function calls `place_one` exactly once. It
defensively recertifies the delegated result and requires exact agreement in
selected geometry and family, launch anchor, contact endpoint, pre-state,
placed mass, and disjoint state transition before returning the composite
certificate. Direct `ReferenceEventPlacement` construction enforces the same
selection/placement cross-field and positive-support periodic-law identities.

The binder does not call `select_event`, any one-stream selector, RNG, or either
observable extractor. In particular, it does not replay Philox: a directly
constructed, structurally valid `TetrominoEventSelection` remains
non-authenticating, while a record originally returned by `select_event`
retains its certified address/law/draw evidence unchanged. The result is an
in-memory one-event certificate, not a serialization or persistence identity.

This unit adds no event/contact accumulator, checkpoint or persistence schema,
canonical digest, `SimulationConfig` or legacy adapter, multi-event trajectory,
optimized kernel, CLI, scheduler, Easley/Slurm/HPC route, release, or production
path. Article S1a-09 executable completion, M1.2, and overall S2 remain open;
S3 and all later gates remain closed.

### 6.12 Provisional reference event/contact accumulation

`tetris_ballistic.engine.accumulation` is an explicit-submodule-only fold over
already-created `ReferenceEventPlacement` certificates. It is not re-exported
from `tetris_ballistic` or `tetris_ballistic.engine`. Its public surface is
limited to the frozen, slotted `ReferenceEventAccumulator` record and two
keyword-only functions:

```python
start_event_accumulator(
    *,
    empty_state: SparseAggregate,
    root_seed: int,
    coupling_group_id: str,
    law: TetrominoEventLaw,
) -> ReferenceEventAccumulator

accumulate_event(
    *,
    accumulator: ReferenceEventAccumulator,
    event: ReferenceEventPlacement,
) -> ReferenceEventAccumulator
```

Start accepts only a recertified canonical empty state. The frozen event law's
launch bound must equal that state's width, and its complete positive
family--orientation support must satisfy the existing periodic-law preflight.
The initial event count and every additive total are zero, while the five
family, 19-orientation, two-contact, and five face-kind tuples retain all
declared zero slots. The address contract is inherited from event selection:
the root seed is a built-in integer in `[0, 2**128 - 1]`, the coupling group is
nonempty built-in UTF-8 text whose length-framed encoding is at most
`2**32 - 1` bytes, and event ordinals lie in `[0, 2**64 - 1]`.

Each fold first recertifies the supplied accumulator and bound event, then
requires identical root, coupling group, law, and width; an event ordinal equal
to the current event count; and an event pre-state equal to the current state.
The terminal ordinal `2**64 - 1` may be consumed to produce event count
`2**64`; every later fold fails before measurement. One placement primitive is
measured exactly once across an adversarial delegate boundary. Every consumed
primitive is cross-bound to pristine detached selection, placement, and
independently measured pre/post-state authorities before the post-state becomes
the next current state.

The accumulator retains exact integers and canonical immutable tuples for:

- current mass, height sum, height-square sum, below-envelope volume, and void
  count;
- fixed family, orientation, contact endpoint, final face-kind, and causal
  face-kind counts;
- seam-lateral faces, per-event distinct contacting-cell/support-site/support-
  column multiplicities, and floor-/aggregate-support event flags;
- sparse landing-gap, support-cluster, support-span, and normalized cyclic
  support-gap-signature counts;
- whole-envelope pre/post height histograms, including arithmetically counted
  zero-height columns, plus strict per-column envelope-change flow;
- contact--gap--signed-delta strata and orientation--contact--topology strata,
  the latter retaining count, signed void-delta sum, and signed roughness-
  numerator-delta sum; and
- cumulative height, squared-height, and signed void deltas.

The cyclic signature is the lexicographically least rotation of the placement
primitive's certified gap tuple. This supplies translation-invariant
accumulator keys without redefining the coordinate-tie-broken tuple at the
placement API boundary. Contact keys contain the selected built-in rule ID
string; only face-kind tuples contain exact `ContactFaceKind` values. Sparse
count entries have positive counts and are strictly sorted and duplicate-free;
topology records have the same canonical ordering. Nested lists, dictionaries,
booleans in integer positions, subclasses, aliases, and mutable values are
rejected.

Direct construction performs structural recertification. Among its normative
projections are

```text
occupied_mass = 4 * event_count,
height_sum = occupied_mass + void_count = below_envelope_volume,
R = width * height_square_sum - height_sum**2 >= 0.
```

Family/orientation/contact marginals, topology/contact joint tables, signed
delta sums, whole-envelope histogram flow, and per-column envelope changes
must all reproduce their common totals and the independently measured current
state. Every pre/post histogram contributes exactly `width` columns per event;
strict envelope changes contribute at most four columns per event and telescope
from the all-zero initial envelope. All arithmetic uses exact Python integers.

This value is a structurally consistent claimed-prefix summary, not an
authenticated history. An uninterrupted caller-observed chain beginning at
`start_event_accumulator` procedurally enforces empty origin and one-step
ordinal/state continuity, but a directly constructed equal record proves
neither its historical events nor Philox provenance. No lineage token, digest,
journal, merge operation, serialization, or persistence identity is implied.

The unit performs no RNG or event selection, no placement, no trajectory
driving, no configuration or legacy adaptation, no floating summary, no I/O,
and no optimized, CLI, scheduler, Easley/Slurm/HPC, release, or production
routing. It advances the in-memory reference instrumentation but completes
neither Article S1a-09, M1.2, nor overall S2; all later gates remain closed.

### 6.13 Provisional PRE clean periodic one-cell transition

`tetris_ballistic.engine.one_cell` is an explicit-submodule-only,
deterministic one-event oracle for `one-cell-rd-bd-periodic-v1`. It is not
re-exported from `tetris_ballistic` or `tetris_ballistic.engine`; neither
package `__init__.py` changes. Its complete provisional surface is

```python
from tetris_ballistic.engine.one_cell import (
    ONE_CELL_PERIODIC_MODEL_ID,
    OneCellCausalSide,
    OneCellPeriodicTransition,
    transition_one_cell_periodic,
)
```

`transition_one_cell_periodic` is keyword-only. It accepts a plain `list` or
`tuple` of at least three nonnegative built-in integer heights, a built-in
launch integer already in `[0, width)`, and a built-in Boolean
`sticky_endpoint_selected`. It snapshots the complete interface as an
immutable tuple and never mutates the caller's sequence. Wrong concrete types
raise `TypeError`; legal concrete types outside the model domain raise
`ValueError`. Heights use arbitrary-precision Python integers in this oracle;
production storage bounds remain a later gate.

For launch height `a` and modulo-periodic pre-event neighbor heights `b` and
`c`, the exact recurrence is

```text
vertical = a + 1
post     = vertical                 if sticky_endpoint_selected is false
post     = max(vertical, b, c)      if sticky_endpoint_selected is true
```

Only the launch column changes. The returned frozen, slotted
`OneCellPeriodicTransition` retains immutable pre/post height tuples, the
launch and endpoint selection, the three local pre-heights and launch
post-height, and the exact integer primitives

```text
delta_s = post - a
delta_v = post - (a + 1)
delta_q = post**2 - a**2
```

Its `gap` property is exactly `delta_v`; `width` and `model_id` are also
derived read-only properties. The record additionally retains the positive-gap
trigger, causal side, equality mask, and periodic-seam equality. Direct record
construction reruns the complete recurrence and rejects inconsistent local
heights, deltas, classifications, or off-launch changes.

The positive-gap trigger is true exactly when the sticky endpoint was selected
and `delta_v > 0`. `OneCellCausalSide` is `none` without such a trigger;
otherwise it is `left`, `right`, or `both` according to which pre-event
neighbor heights attain `post`. This causal classification is deliberately
separate from the fixed height-equality mask

```text
mask = 1 * (post == a + 1) + 2 * (b == post) + 4 * (c == post).
```

Lateral equality bits remain height-defined on nonsticky and selected-sticky
zero-gap events and therefore do not imply causal arrest. `seam_equality` is
true only for a mask-qualified left equality from launch column zero or a
mask-qualified right equality from launch column `width - 1`; an incidental
contact against a taller neighbor is not equality.

This slice is independent of the legacy one-cell fast path and the tetromino
event stack. It adds no RNG or launch selection, common-draw eight-arm
coupling, accumulation, trajectory, checkpoint, persistence or serialization,
configuration/legacy dispatch, hard-wall or finite-ceiling law, float archive,
optimized kernel, CLI, scheduler, Easley/Slurm/HPC route, release, or
production path. Existing legacy and tetromino semantics remain unchanged.

### 6.14 Provisional PRE one-cell coupled event selection

`tetris_ballistic.engine.one_cell_coupling` is an explicit-submodule-only,
stateless composition of the certified S2.2 semantic RNG and S2.3 uniform
selection layers. It is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`; neither package `__init__.py` changes. Its complete
provisional surface is

```python
from tetris_ballistic.engine.one_cell_coupling import (
    ONE_CELL_CONTACT_DENOMINATOR,
    ONE_CELL_COUPLING_GROUP_ID,
    ONE_CELL_STICKINESS_THRESHOLDS,
    ONE_CELL_STREAM_SET,
    OneCellCoupledEventSelection,
    select_one_cell_coupled_event,
)
```

The model-level coupling identity and logical schedule are fixed internally:

```text
coupling group = pre-one-cell-discovery-v1
streams        = (launch, contact)
thresholds     = (0, 1, 2, 5, 10, 25, 50, 100)

launch  ~ uniform_below(width)
contact ~ uniform_below(100)
```

The keyword-only selector accepts a built-in unsigned 128-bit root seed, a
built-in unsigned 64-bit event ordinal, and a built-in integer width in
`[3, 2**64]`. Scientific root index `r` is supplied unchanged as the numerical
root seed, and event ordinals are zero based. It validates the complete fixed
contract and request before any draw, then calls the S2.3 uniform selector
exactly twice in the displayed order. No arm, width, or endpoint is an implicit
stream-key salt, and no categorical, floating probability, per-arm Bernoulli,
or endpoint shortcut is permitted.

All eight arms share the selected launch column and contact integer. In the
fixed threshold order, the sticky-endpoint predicate is literally

```text
contact_value < threshold.
```

Therefore equality at a threshold is nonsticky for that arm. The 0% arm is
always nonsticky and the 100% arm always sticky, but both retain the common
event-level contact draw. The eight decisions are nested and have seven
possible Boolean patterns over contact values 0 through 99.

The frozen, slotted `OneCellCoupledEventSelection` retains the root, event,
width, launch `UniformSelection`, and contact `UniformSelection`, including
both accepted-rejection ordinals. Its type fixes the coupling group and stream
schedule; read-only properties expose those identities, the shared launch and
contact values, the eight sticky flags, and threshold--decision pairs. Nested
selection records are defensively reconstructed. A malformed launch delegate
fails before contact; a malformed contact delegate fails after the second
logical call.

At equal root seed and event ordinal, widths in one coupling group share the
launch raw candidate tape, not necessarily the accepted launch value: unequal
bounds can reject at different ordinals. Their contact selection is identical
because its address and bound 100 are identical. Launch rejection cannot shift
contact or later events. The root remains the resampling block; coupled widths
and arms are not independent replicates. Persistent exact keys, raw words,
planned-width mappings, threshold boundaries, and unequal-width rejection
evidence are recorded in `docs/PRE-ONE-CELL-COUPLING-VECTORS.md`.

Direct record construction enforces structural consistency but does not replay
Philox. Certified semantic provenance applies to selector-produced records.
This slice performs no call to the deterministic one-cell transition, no
arm-state evolution, trajectory, accumulator, checkpoint or persistence
identity, canonical serialization, configuration or legacy route, compiled
RNG or optimized kernel, CLI, scheduler, Easley/Slurm/HPC route, release, or
production dispatch. It therefore does not close the protocol's compiled-RNG
admission gate, complete common correctness, or authorize scientific
acquisition. Boundary-law certification is addressed separately in Section
6.15 and scalar/compiled trajectory equality in Sections 6.17--6.18;
interruption/resume and campaign-identity gates remain open.

### 6.15 Provisional PRE one-cell scalar boundary transition

`tetris_ballistic.engine.one_cell_boundary` is an
explicit-submodule-only, deterministic one-event oracle for the three PRE
boundary laws. It is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`; neither package `__init__.py` changes. Its complete
provisional surface is

```python
from tetris_ballistic.engine.one_cell_boundary import (
    OneCellBoundaryLaw,
    OneCellBoundaryTransition,
    transition_one_cell_boundary,
)
```

The exact `OneCellBoundaryLaw` values are

```text
periodic-v1
hard-wall-legacy-asymmetric-v1
hard-wall-reflection-symmetric-v1
```

`transition_one_cell_boundary` is keyword-only. It accepts one exact enum
member, a plain `list` or `tuple` of at least three nonnegative built-in
integer heights, a built-in launch integer in `[0, width)`, and a built-in
Boolean `sticky_endpoint_selected`. It snapshots the full interface as an
immutable tuple and never mutates the caller's sequence. Wrong concrete types
raise `TypeError`; legal concrete types outside the scalar domain raise
`ValueError`. Heights use arbitrary-precision Python integers; production
storage bounds remain a later gate.

For physical launch height `a`, set `vertical = a + 1`. Every nonsticky event
has `post = vertical`. For a selected sticky event, the exact recurrences are

```text
periodic:          post = max(vertical, h[(x-1) mod L], h[(x+1) mod L])
legacy hard wall:  post = max(vertical,
                              h[x-1] if x > 1,
                              h[x+1] if x < L-1)
corrected wall:    post = max(vertical,
                              h[x-1] if x > 0,
                              h[x+1] if x < L-1).
```

Only the launch column changes. Neighbor eligibility is determined solely by
boundary law and position, independent of endpoint selection. Both periodic
neighbors are eligible. For either hard wall, the right neighbor is eligible
exactly at `x < L-1`; the legacy left guard is `x > 1`, while the corrected
guard is `x > 0`. A nonsticky event simply ignores otherwise eligible
neighbors.

The frozen, slotted `OneCellBoundaryTransition` retains the boundary enum,
immutable pre/post height tuples, launch and endpoint selection, optional
physical left and right pre-heights, launch pre-height, separate left/right
eligibility flags, launch post-height, exact `delta_s`, `delta_v`, and
`delta_q`, positive-gap trigger, the Slice 1 `OneCellCausalSide`, equality
mask, and `seam_equality: bool | None`. Its only derived properties are
`width` and `gap`, with `gap == delta_v`; the boundary enum is the identity,
so no duplicate `model_id` property is added. Direct construction reruns the
selected recurrence without calling the Slice 1 delegate and rejects
inconsistent local heights, eligibility, deltas, classifications, or
off-launch changes.

A missing hard-wall neighbor is `None`. An existing neighbor retains its
physical height even if the legacy law makes it ineligible. The equality mask
therefore remains height-defined on every physical neighbor:

```text
mask = 1 * (post == a + 1)
     + 2 * (existing left height == post)
     + 4 * (existing right height == post).
```

The positive-gap trigger is true exactly when the sticky endpoint was selected
and `delta_v > 0`. Causal sides consider only law-eligible neighbors attaining
`post` on such an event. Thus at `(1, 0, 0)`, launch 1, sticky selected, the
legacy result has equality mask 3 but no causal side: the left neighbor exists
and is height-equal, yet is ineligible. Periodic seam equality is Boolean;
hard-wall seam equality is not applicable and is exactly `None`, never a
physical false or zero.

The periodic route calls the already certified
`transition_one_cell_periodic` exactly once with the immutable request. It
requires an exact-type, fully self-validating result, cross-binds that result
to the complete request, and projects every Slice 1 certificate field into the
unified boundary record. Wrong-type, subclass, malformed, or cross-request
delegate results fail closed. Hard-wall routes never call the periodic
delegate.

The archived legacy authority comprises exp14 commits
`767577aaa00988a3eeb8a4a5a6c795234cb89aa2`,
`06d3e38c2fbdb19f8bc47ed24d09181e21e39bbf`,
`58b17f814c0b0e6c3e4f72ab62f072a2792e86e9`,
`a47ec6c6606bc78a86427cca7a2f331c68dce653`, and
`218819fb67742f9f4652176cd61c180713edd448`. Their Python one-cell code is
identical at blob `8c4f64f71a1e2b1769dbd1b37fee3c40df608323`, SHA-256
`3ce8ade36fa1e471fa54cce6e3b3fd8950f0ef21d734343423f46275e83dc206`;
their compiled one-cell kernel is also identical at blob
`3d6bf4c3f6bc622b357be1a328fd5fe4541a3d99`, SHA-256
`eaeb255240fa05610c6d77abdc93df15020c6699b47cafac6a7444e98acd74c7`.
The certification suite embeds and executes the exact four archived method
bodies and separately evaluates an independent archived-row translation; a
local-history gate proves the embedded source equals the pinned blob. The
normative vectors are recorded in `docs/PRE-ONE-CELL-BOUNDARY-VECTORS.md`, so
shallow CI does not depend on historical Git objects.

The fast certification suite exhausts widths 3--5, heights 0--3, every launch,
and both endpoint selections: 12,672 cases per law. Periodic records match
Slice 1 field for field; legacy records match both the exact executable
archived engine fixture and an independent inverted-row oracle; corrected
records match a separately written physical-height oracle and pass exhaustive
reflection symmetry. The hard-wall laws differ in exactly 168 small-state
cases, all and only at the archived `x=1` defect. The decisive `(5, 0, 0)`
sticky witness yields legacy launch post-height 1 versus corrected post-height
5.

This slice adds no RNG or launch selection, coupled-arm evolution,
accumulation, multi-event trajectory, compiled/Numba path, checkpoint or
persistence identity, configuration or legacy dispatch, CLI, scheduler,
Easley/Slurm/HPC route, release, or production path. It closes only
common-correctness item 2 after source, package, review, CI, and parity gates;
compiled RNG, compiled/scalar trajectories, interruption/resume, campaign
identity, pilots, canaries, and scientific acquisition remain closed.

### 6.16 Provisional PRE compiled semantic-RNG primitives

`tetris_ballistic.engine.rng_compiled` is an explicit-submodule-only,
pre-derived-key implementation of the Philox and exact bounded-integer portion
of `semantic-philox4x64-10-v1`. It is not re-exported from
`tetris_ballistic` or `tetris_ballistic.engine`, and importing either root does
not require the optional compiled dependency.

Its complete public surface is

```python
philox4x64_10(*, counter, key) -> tuple[int, int, int, int]
raw_u64_from_key(*, key, event_ordinal, rejection_ordinal=0) -> int
uniform_below_from_key(*, key, event_ordinal, n) -> SemanticDraw
```

All calls are keyword-only. Counter and key containers are exact built-in
tuples of, respectively, four and two exact unsigned-64 built-in integers;
event, rejection, and bound values use the same fail-closed exact-type policy.
The bounded call accepts every `n` in `[1, 2**64]` and returns the already
certified frozen `tetris_ballistic.engine.rng.SemanticDraw`. The module neither
duplicates that record nor introduces another RNG identity.

This surface deliberately begins after key derivation. The certified scalar
SHA-256 root/group/stream derivation remains a host operation; Slice 4 does not
recompile SHA-256 or describe a partially scalar root-address wrapper as fully
compiled. `raw_u64_from_key` selects output lane zero at counter
`(event_ordinal, rejection_ordinal, 0, 0)`. `philox4x64_10` retains all four
lanes so the complete Random123 known answers remain observable.

For `M = 2**64`, `q = floor(M / n)`, and `T = q*n`, the exact bounded law
rejects `word >= T` and otherwise returns `floor(word / q)`. The private
compiled boundary encodes the public bound as unsigned word `n - 1`, making
both endpoint bounds representable without an API sentinel. Bound one still
evaluates its ordinal-zero candidate and returns zero; bound `2**64` accepts
that candidate unchanged. Rejections increment only the second counter lane,
retain the accepted zero-based ordinal, and fail before unsigned wrap.

Numerical kernels use unsigned integer arithmetic, including limb-based exact
high/low multiplication, and must acquire Numba nopython signatures. Object
mode, floating point, fast math, high-level NumPy random operations, and calls
to the scalar Philox or bounded implementation are outside the contract. The
scalar module supplies only the shared result type and comparison evidence.

The implementation and certification boundary is indexed by
`docs/PRE-ONE-CELL-COMPILED-RNG-VECTORS.md`. That receipt pins the upstream
Random123 suite; project `SEMANTIC-RNG-VECTORS.md`
(`913258f0...18c34`), `EXACT-SELECTION-VECTORS.md`
(`324f43f4...f21a9`), `COMPLETE-EVENT-SELECTION-VECTORS.md`
(`331a445c...f2839`), and `PRE-ONE-CELL-COUPLING-VECTORS.md`
(`74c1ab6e...eba3`); the scalar comparison digest; and the frozen PRE
authority. The required suite begins with a 56-row base manifest plus three
supplementary fixed key/raw probes, then replays every applicable
exact-selection and complete-event underlying uniform/raw projection. It also
covers endpoint and threshold neighbors, natural rejection chains accepted at
ordinals one, two, and five, event/stream isolation, hostile boundaries, and
demonstrated nopython signatures. Categorical examples are checked only at
their bounded-uniform layer; categorical interval search is not part of this
API.

This slice adds no compiled key derivation, PRE two-draw scheduling, nested-arm
evolution, transition, trajectory, chunk, accumulation, checkpoint, resume,
persistence, configuration or legacy dispatch, CLI, benchmark claim,
GPU/CUDA or scheduler route, Easley/Slurm/HPC submission, release, or
production path. The legacy `_kernel_1x1.py` is neither imported nor an
authority. Common-correctness item 3 closes only after all source, package,
review, CI, and repository-parity gates pass. Items 4--6 remain open; all
scientific acquisition remains closed.

### 6.17 Provisional PRE scalar one-cell trajectory

`tetris_ballistic.engine.one_cell_trajectory` is an
explicit-submodule-only, exact in-memory scalar trajectory over the certified
PRE coupling and three boundary laws. It is not re-exported from
`tetris_ballistic` or `tetris_ballistic.engine`; neither package initializer
changes. Its complete public surface is

```python
from tetris_ballistic.engine.one_cell_trajectory import (
    OneCellScalarArmAccumulator,
    OneCellScalarTrajectory,
    advance_one_cell_scalar_chunk,
    start_one_cell_scalar_trajectory,
)
```

The module's `__all__` contains exactly those four names.
Both calls are keyword-only and both records are frozen and slotted.
`start_one_cell_scalar_trajectory` accepts an exact built-in unsigned-128
`root_seed`, an exact certified `OneCellBoundaryLaw`, and an exact built-in
width in `[3, 1024]`. Its complete call is

```python
start_one_cell_scalar_trajectory(
    *,
    root_seed: int,
    boundary_law: OneCellBoundaryLaw,
    width: int,
    threshold_schedule: tuple[int, ...] = (0, 1, 2, 5, 10, 25, 50, 100),
) -> OneCellScalarTrajectory
```

`threshold_schedule` must be an exact built-in tuple of exact built-in
integers and must equal exactly one of

```text
primary = (0, 1, 2, 5, 10, 25, 50, 100)
B1      = (0, 5, 50, 100)
B2-full = (5, 50, 90, 95, 98, 99)
B2-high = (90, 95, 98, 99).
```

Every other tuple, list, or tuple subclass fails before allocation or delegate
calls. The default retains the original eight-arm primary result exactly.
This PRE-specific width ceiling covers every declared campaign width while
rejecting infeasible arithmetic-only Slice 2 widths before allocating a height
tuple.

`advance_one_cell_scalar_chunk` accepts an already certified trajectory and
an exact built-in `stop_event_ordinal`. It evolves exactly the contiguous
half-open interval

```text
[trajectory.event_count, stop_event_ordinal).
```

The inferred start forbids skipping or replaying an ordinal. Equality is a
delegate-free identity operation: an equal stop returns an equal defensively
reconstructed trajectory without selecting or transitioning an event. Neither
operation mutates the caller's record or any nested tuple.

`OneCellScalarArmAccumulator` retains exactly

```text
boundary_law
threshold
heights
event_count
height_sum
height_square_sum
void_volume
endpoint_selected_count
positive_gap_trigger_count
gap_sum
maximum_gap
causal_counts
causal_gap_sums
endpoint_equality_mask_counts
gap_histogram
seam_equality_count
```

The causal tuples use fixed order `(none, left, right, both)`. Equality counts
are a two-row tuple indexed first by endpoint false/true and then by masks zero
through seven. The histogram is a sorted sparse tuple of `(gap, count)` pairs.
Periodic seam equality is an integer count; either hard-wall value is exactly
`None`, not physical false or numeric zero. The record's only derived
properties are `width` and the exact roughness numerator
`width*height_square_sum - height_sum**2`.

`OneCellScalarTrajectory` retains only `root_seed`, `boundary_law`, `width`,
the common `event_count`, and one complete ordered four-, six-, or eight-arm
schedule. Its only additional derived property is `threshold_schedule`; no
retained field changes. Individual arms admit only thresholds in the union of
the four frozen schedules. The record retains no per-event selection, contact,
RNG, transition, or height-history tape. Direct construction of either record
proves all structural projections but does not authenticate a claimed Philox
history.

For every event, advance calls the certified Slice 2
`select_one_cell_coupled_event` exactly once and cross-binds its exact result
to the requested root, ordinal, and width. It then calls the certified Slice 3
`transition_one_cell_boundary` exactly once per selected arm in threshold
order, using the one shared launch and literal endpoint decision
`contact < threshold`, and cross-binds every transition before folding its
certified primitives. The generalized fold consumes only the selector's
certified launch and contact values, not its primary-only derived decision
properties. No arm, boundary law, schedule, or threshold enters an RNG
address.

All scalar state uses exact integers. Heights, `N`, `S`, `V`, counters, gaps,
histogram entries, and periodic seam counts are unsigned-64 values; `Q` is an
unsigned-128 Python integer. Before any delegate call, advance checks with
arbitrary precision that

```text
0 <= current N <= stop < 2**64
width * stop < 2**64
width * stop**2 < 2**128.
```

Every arm certifies `S=sum(heights)`, `Q=sum(h*h)`, `V=S-N=gap_sum`, and a
nonnegative roughness numerator. Its histogram, causal/equality projections,
endpoint/trigger totals, and seam count reproduce the common event count and
void volume. In particular, equality counts total `N`, their selected row
totals the endpoint count, and both mask-zero cells are zero. Causal counts
total `N`; the `none` count is `N-trigger`, and causal gap sums total `V` with
zero in the `none` stratum. At `N=0` the histogram is empty. Every nonempty
prefix has a positive zero-gap bin, positive counts on strictly increasing
keys, count total `N`, weighted total `V`, positive-bin count equal to the
trigger count, and final key equal to the maximum gap. Every height is at most
`N`. When present, the 0% arm always has `S=N` and zero endpoint, trigger, and
void counts, and the 100% endpoint count is `N`. Endpoint counts and every
height column are nondecreasing across the selected threshold order. All
Slice 5 projection and cross-arm nesting laws apply to every schedule.

Normative complete `[0,7)` and `[0,50)` snapshots for root zero, width three,
all primary and B2-full arms, and all three laws are recorded in
`docs/PRE-ONE-CELL-SCALAR-TRAJECTORY-VECTORS.md`. The certificate is produced
by a separately written SHA-256/Philox/rejection/recurrence/accumulator oracle,
exhaustive small injected-event tapes, real-RNG sweeps, forced rejection, and
chunk-partition equivalence. The 48 primary rows remain value-for-value; 36
B2-full rows are additive, while B1 and B2-high are certified exact
projections. Exact high/low-word round-trip compatibility for `Q` is proved in
tests but exposes no packed representation.

These are evolution schedules, not campaign identities. P0/P1 use primary,
B1 uses B1, B2 widths through 300 and the width-50 F0 canaries use B2-full,
and B2 widths 400/500 and the width-500 F0 canaries use B2-high. This scalar
surface adds no width dispatch, campaign artifact, packed public `Q`,
checkpoint, persistence, resume, serialization, configuration, runner, CLI,
scheduler, Easley/Slurm/HPC route, simulation output, analysis, release, or
scientific-acquisition path.

### 6.18 Provisional PRE compiled one-cell trajectory chunks

`tetris_ballistic.engine.one_cell_trajectory_compiled` is an
explicit-submodule-only Numba backend for the exact scalar record contract. It
is not re-exported from `tetris_ballistic` or `tetris_ballistic.engine`; neither
package initializer imports Numba. Its complete public surface is

```python
from tetris_ballistic.engine.one_cell_trajectory_compiled import (
    advance_one_cell_compiled_chunk,
)

advance_one_cell_compiled_chunk(
    *,
    trajectory: OneCellScalarTrajectory,
    stop_event_ordinal: int,
) -> OneCellScalarTrajectory
```

The module's `__all__` contains exactly that one name. There is no compiled
start function and no duplicate compiled trajectory or accumulator record.
Callers initialize through `start_one_cell_scalar_trajectory` with any of the
four exact schedules in Section 6.17. The operation returns the frozen scalar
record type, making complete backend agreement ordinary record equality.

The operation advances exactly the half-open interval
`[trajectory.event_count, stop_event_ordinal)`. Before allocating compiled
state or deriving keys, the host defensively reconstructs the complete scalar
record and validates the requested stop with arbitrary-precision arithmetic.
An empty interval returns an equal reconstructed record without key derivation,
compiled-state allocation, RNG, or kernel dispatch. For a nonempty interval,
the host derives the launch and contact keys exactly once each, in that order,
under coupling group `pre-one-cell-discovery-v1`.

SHA-256 key derivation and immutable result construction remain host steps.
Every RNG mapping, boundary recurrence, and accumulator arithmetic operation
is in Numba nopython code. At event ordinal `e`, launch uses bound `width` and
contact uses bound 100 at counter `(e, rejection, 0, 0)`. Rejection advances
only that draw's rejection lane. One accepted launch/contact pair is shared by
all arms and the decision is exactly `contact < threshold`; schedule, law, and
threshold never enter an RNG address.

The private compiled state uses fresh native-endian C-contiguous unsigned-64
arrays for heights, scalar fields, causal counts and gap sums, and both rows of
equality-mask counts, plus one typed sparse histogram keyed by
`(arm_index, gap)`. The scalar fields carry `S`, `V`, endpoint/trigger counts,
maximum gap, hard-wall seam scratch, and packed `Q_high,Q_low`. A literal
private schedule code selects the exact four-, six-, or eight-arm threshold
ladder. No caller-configurable threshold array, event tape, dense
horizon-sized histogram, public mutable state, or persistent packed state is
created.

The kernel implements all three Section 6.15 recurrences and folds every
Section 6.17 field. Physical equality and causal eligibility remain separate;
equality mask order is `vertical + 2*left + 4*right`; and periodic seam
equality includes nonsticky and zero-gap events. The hard-wall seam scratch
must remain zero and reconstructs to public `None`.

Public `Q` remains an exact Python integer. Its private projection is
`(Q_high << 64) | Q_low`, high word first, with `(0,0)` representing zero.
The kernel uses the captured certified unsigned 64-by-64 multiplier, explicit
square-subtraction borrow, addition carry, and overflow detection. All retained
scientific state is unsigned; floats, fast math, object mode, signed
scientific arithmetic, silent wrap, high-level random distributions, and calls
to scalar numerical helpers are outside the contract. Signed machine `intp`
is permitted only for indexing and control flow.

Before dispatch, the host proves

```text
0 <= current N <= stop < 2**64
width * stop < 2**64
width * stop**2 < 2**128.
```

Compiled-word arithmetic or rejection-ordinal exhaustion raises
`OverflowError`; nonexact public types raise `TypeError`; invalid ranges,
records, schedules, or protocol products raise `ValueError`; corrupted
captured authorities or malformed compiled results raise `AssertionError`.
Work occurs on fresh private buffers, so no failed call can mutate the caller
or publish a partial result.

The required conformance relation is a three-way full-record comparison among
a separately written primitive-tuple SHA-256/Philox/recurrence oracle, the
scalar backend, and the compiled result. It includes all four schedules, all
three laws, packed-Q projections, strict threshold neighbors, exhaustive small
tapes, real-RNG matrices, all short partitions, longer irregular partitions,
forced launch/contact rejection, arithmetic carry/borrow/overflow witnesses,
hostile records and state shapes, authority rebinding, and package/import
gates. The complete receipt and exact matrix counts are indexed by
`docs/PRE-ONE-CELL-COMPILED-TRAJECTORY-VECTORS.md`.

The existing optional `hpc` extra supplies `numba>=0.58`. Without a compatible
Numba installation, explicit import raises a clear `ImportError` naming
`tetris_ballistic.engine.one_cell_trajectory_compiled` and
`tetris_ballistic[hpc]`; package-root imports remain available. Kernels use
`cache=False` and `fastmath=False`.

This backend adds no checkpoint, persistence/resume or digest identity,
campaign identity, width-to-schedule dispatch, configuration/YAML, runner,
CLI, legacy route, scheduler, Slurm/Easley/HPC submission, performance claim,
GPU/CUDA, pilot, canary, simulation output, analysis, release, or scientific
acquisition. Slice 6 may close common-correctness item 4 only after all source,
test, package, review, CI, and repository-parity gates pass; items 5--6 remain
open.

### 6.19 Provisional PRE one-cell checkpoint and resume identity

`tetris_ballistic.engine.one_cell_checkpoint` is the explicit-submodule-only
Slice 7 checkpoint, interruption, and finalization surface for the certified
Slice 5/6 one-cell trajectories. It is not re-exported from
`tetris_ballistic` or `tetris_ballistic.engine`. Its `__all__` contains exactly

```python
[
    "OneCellCheckpointValidationError",
    "OneCellCheckpointBinding",
    "OneCellCheckpointSchedule",
    "OneCellCheckpointProgress",
    "OneCellInterruptionFlag",
    "build_one_cell_checkpoint_schedule",
    "advance_one_cell_checkpoint_generation",
    "publish_one_cell_final",
]
```

Package and engine roots remain importable without Numba. Explicit import of
this module without a compatible `hpc` extra raises a clear `ImportError`
naming `tetris_ballistic.engine.one_cell_checkpoint` and
`tetris_ballistic[hpc]`.

All record constructors and the three top-level functions are keyword-only.
Every record is frozen and slotted except `OneCellInterruptionFlag`, the sole
mutable operational latch. The calls are

```python
build_one_cell_checkpoint_schedule(
    *,
    terminal_event_count: int,
) -> OneCellCheckpointSchedule

advance_one_cell_checkpoint_generation(
    *,
    task_directory: str,
    binding: OneCellCheckpointBinding,
    interruption_flag: OneCellInterruptionFlag | None = None,
) -> OneCellCheckpointProgress

publish_one_cell_final(
    *,
    task_directory: str,
    binding: OneCellCheckpointBinding,
) -> OneCellCheckpointProgress
```

The record field order is frozen:

```text
OneCellCheckpointSchedule:
  terminal_event_count
  checkpoint_event_counts
  snapshot_checkpoint_indices
  snapshot_event_counts
  checkpoint_vector_sha256
  snapshot_vector_sha256

OneCellCheckpointBinding:
  root_seed
  boundary_law
  width
  threshold_schedule
  terminal_event_count
  configuration_bytes
  scientific_identity_bytes
  software_commit

OneCellCheckpointProgress:
  disposition
  trajectory
  generation
  checkpoint_count
  snapshot_count
  used_fallback
  manifest_path
```

Schedule vectors and trajectory arms are exact built-in tuples. Counts and
generation are exact built-in integers. Digests, disposition, commit, and the
absolute normalized manifest path are exact built-in strings.
`used_fallback` is an exact Boolean, and `trajectory` is the exact Slice 5
record. Progress dispositions are exactly `ready`, `requeue-required`,
`terminal`, `complete`, or `reused`. Direct progress construction proves only
structural consistency; progress is never accepted as recovery authority.
For final `complete` or `reused` progress, generation is exactly zero,
checkpoint/snapshot counts are 512/16, and the trajectory is reconstructed
from the final bundle. `used_fallback` is false for `reused`; newly `complete`
reports only whether that publication invocation selected an older valid
terminal recovery generation.

`OneCellInterruptionFlag` exposes exactly a read-only `requested` property,
idempotent zero-argument `request()`, and signal-compatible
`__call__(signum, frame)` with the two positional arguments supplied by
Python's signal machinery. Each mutator performs one Boolean store and no I/O,
allocation, formatting, logging, locking, exception raising, kernel work,
exit, or requeue operation. The module does not install a signal handler.

#### Binding and schedule

A binding accepts only an unsigned-128 built-in root seed, an exact
`OneCellBoundaryLaw`, width in `[3,1024]`, one exact primary, B1, B2-full, or
B2-high threshold tuple, terminal processed-event count, two nonempty exact
built-in byte strings no larger than 1 MiB each, and a full lowercase 40-hex
software commit. The terminal is at least 769 and below `2**64`, with exact
preflight laws

```text
width * N < 2**64
width * N**2 < 2**128.
```

Configuration and scientific-identity bytes are persisted and compared
exactly but remain opaque. This module does not parse YAML or JSON and does not
derive a campaign, horizon branch, task, attempt, or directory identity.

The request identity binds the root, boundary enum value, width, threshold
order, terminal, schedule hashes, raw-byte sizes and hashes, software commit,
and literal RNG contract:

```text
algorithm       = semantic-philox4x64-10-v1
coupling group  = pre-one-cell-discovery-v1
stream order    = (launch, contact)
counter         = (zero-based event ordinal, rejection ordinal, 0, 0).
```

It is compact sorted-key canonical JSON with exact envelope keys `profile`,
`record`, and `sha256`. Profile is
`tetris-pre-one-cell-checkpoint-request@1`; the digest hashes the compact
canonical bytes of `record` alone without a trailing LF. The record keys are

```text
boundary_law
checkpoint_vector_sha256
configuration_sha256
configuration_size_bytes
counter_fields
coupling_group
rng_algorithm
root_seed_decimal
scientific_identity_sha256
scientific_identity_size_bytes
snapshot_vector_sha256
software_commit
stream_order
terminal_event_count
threshold_schedule
width
```

`root_seed_decimal` is an unsigned base-ten string with no leading zero except
literal `"0"`; raw opaque bytes are never base64-encoded into JSON. The stored
raw bytes, member sizes and hashes, request record, and envelope digest must
all agree.

The schedule contains exactly 384 early and 128 late processed-event counts.
For `A=ceil(N/2)` and `M=A-1`, the early mathematical value is
`M**(j/383)`, rounded half up and forced forward by

```text
n_0 = 1
n_j = min(M-(383-j), max(n_(j-1)+1, round_half_up(M**(j/383))))
n_383 = M.
```

Rounding is decided exactly by

```text
(2*r-1)**383 <= 2**383 * M**j < (2*r+1)**383.
```

The late values are `A+floor(k*(N-A)/127)`, `k=0,...,127`. Snapshot indices
are exactly

```text
(0,34,68,102,136,170,204,238,273,307,341,375,409,443,477,511).
```

Checkpoint and snapshot digests use their separate compact sorted-key profiles
without a trailing LF. The full KATs at `N=769` and `N=100663296`, plus both
hashes for every declared horizon, are normative in
`docs/PRE-ONE-CELL-CHECKPOINT-VECTORS.md`. They certify the schedule only;
Slice 8 must still bind selected literal vectors and hashes into exact campaign
bytes.

#### Recovery and interruption

A fresh task starts only through the captured Slice 5 scalar start at `N=0`.
Callers cannot inject a prefix or numerical delegate. Resume state comes only
from the validated task directory, and numerical evolution calls only the
captured public Slice 6 `advance_one_cell_compiled_chunk`.

One invocation holds the persistent task lock across discovery, validation,
compiled advance, generation publication, readback, and retention. It stops at
the next strict global multiple of `2**20` processed events or the terminal,
and compiled calls stop additionally at every unrecorded scientific
checkpoint. No call crosses an observation point or spans more than `2**20`
events. Due rows and snapshots are captured at their exact stops. Without an
interruption, one durable generation is returned as `ready` or `terminal`.

The flag is sampled after lock-time validation, before a compiled call, after
each bounded return, and after readback and retention immediately before the
returned disposition. The last sample is the interruption linearization
point. A fresh pre-requested task may commit one canonical `N=0` generation;
an already durable state is never duplicated. A requested flag returns
`requeue-required` after durable publication. Because a terminal recovery
generation is still incomplete, `requeue-required` takes precedence over
`terminal` until a separate final manifest exists. No interrupted invocation
publishes a final manifest, installs a signal handler, or requests requeue.

#### Closed codec

Recovery profile is `tetris-ballistic/pre-one-cell-checkpoint@1`; final
profile is `tetris-ballistic/pre-one-cell-final@1`. Pickle, joblib, YAML,
NPZ/ZIP, object arrays, native structs, and caller-selected member names are
forbidden. For zero-padded 20-digit generation text `G`, recovery names are

```text
checkpoint.G.configuration.bin
checkpoint.G.scientific-identity.bin
checkpoint.G.state.json
checkpoint.G.arrays.u64le
checkpoint.G.manifest.json
```

Final names are the corresponding fixed `final.*` names. A temporary is
`.TARGET.NONCE.tmp` with a 32-lowercase-hex nonce. Every created member is a
single-link regular owner-only 0600 file. Configuration, identity, state, and
manifest members are bounded by 1 MiB; arrays are bounded by 64 MiB. The latter
is a fail-closed parser/allocation ceiling, not an Article output-cap result.

The five final names are literally

```text
final.configuration.bin
final.scientific-identity.bin
final.state.json
final.arrays.u64le
final.manifest.json
```

Stored JSON is strict compact sorted-key UTF-8 with exact keys, duplicate-key
and nonfinite-value rejection, and one trailing LF. Member SHA-256 values hash
the exact stored bytes. Array bytes are a headerless, uncompressed C-order
concatenation of little-endian unsigned-64 words. Each section record has
exactly `dtype`, `name`, `offset_words`, `shape`, and `word_count`; dtype is
literal `<u8`, offsets are contiguous from zero, and file length is eight times
the final word count.

A current or checkpoint arm row has 33 words in this order:

```text
S, Q_high, Q_low, V, endpoint_count, trigger_count, gap_sum, maximum_gap,
causal_counts[none,left,right,both],
causal_gap_sums[none,left,right,both],
equality_counts[endpoint_false,masks 0..7],
equality_counts[endpoint_true,masks 0..7],
seam_count_scratch.
```

Hard-wall state marks seam applicability false and reconstructs the scratch
word as public `None`, never physical zero. Histogram rows are sorted exact
`(arm_index,gap,count)` triples.

For arm count `A`, width `L`, completed checkpoints `K`, snapshots `J`, and
histogram rows `H`, recovery sections are exactly

```text
current_heights              (A,L)
current_rows                 (A,33)
current_histogram            (H,3)
checkpoint_event_counts      (K)
checkpoint_rows              (K,A,33)
snapshot_checkpoint_indices  (J)
snapshot_event_counts        (J)
snapshot_heights             (J,A,L)
```

Final sections are exactly

```text
checkpoint_event_counts      (512)
checkpoint_rows              (512,A,33)
snapshot_checkpoint_indices  (16)
snapshot_event_counts        (16)
snapshot_heights             (16,A,L)
final_histogram              (H,3)
```

Rank-one shapes remain one-element JSON arrays. The terminal snapshot is the
final interface. No per-event launch, contact, rejection, transition, RNG, or
height-history tape beyond the 16 snapshots is persisted.

Checkpoint manifests have exact keys `current_event_count`, `generation`,
`members`, `next_event_ordinal`, `profile`, `request_identity`, and `status`,
with status `checkpoint`. Final manifests have only `members`, `profile`,
`request_identity`, and status `complete`. `members` has exact keys `arrays`,
`configuration`, `scientific_identity`, and `state`; each member record has
exactly `filename`, `sha256`, and `size_bytes`.

Checkpoint state JSON has exact keys

```text
arm_count, checkpoint_count, current_event_count, generation,
next_event_ordinal, profile, seam_equality_applicable, sections,
snapshot_count, terminal_event_count, width.
```

Its profile is `tetris-pre-one-cell-checkpoint-state@1`. Final state omits
`current_event_count`, `generation`, and `next_event_ordinal` and uses
`tetris-pre-one-cell-final-state@1`.

#### Filesystem, validation, and finalization

`task_directory` is an absolute normalized exact built-in string naming one
pre-existing dedicated directory. Every path component and inner member is
opened relative to held no-follow descriptors. Symlinks, hard links,
nonregular members, substituted ancestors, malformed reserved names, and
unexpected entries fail closed.

`task.lock` is a persistent, never-replaced inode held with exclusive
`flock`. Payload members are exclusively created, flushed, fsynced, installed
without replacement, and followed by a directory fsync. The strict manifest
is installed last, followed by another directory fsync and full descriptor-
based readback. Retention begins only after that validation and keeps at most
the newest two fully valid matching generations.

Recovery ordinals lie in `[1,2**64-1]`. They are numeric, strictly increasing,
and never derived from mtime or directory enumeration order. The next ordinal
is one greater than the maximum ordinal observed in any well-formed committed,
payload-only, or managed-temporary checkpoint basename; exhaustion fails
before filesystem mutation or numerical execution.

Malformed, noncanonical, identity-unreadable, or request-mismatched manifests
are fatal and never fall back. Once a canonical manifest proves matching
identity, a corrupt referenced payload, checksum, layout, or scientific
invariant rejects that candidate and may select only the immediately older
retained fully valid generation. `used_fallback` reports this choice. If no
valid matching state remains while committed material exists, execution fails
instead of restarting from zero. New generations use one plus every observed
ordinal and never reuse a corrupt or orphan ordinal.

Before every compiled call, publication, resume, fallback, finalization, and
reuse, the host reconstructs the exact Slice 5 records and recomputes in Python
arbitrary precision all height sums, squared-height sums and high-first `Q`
words, roughness nonnegativity, void/gap identities, histograms,
causal/equality projections, endpoint laws, seams, arm nesting, schedule
prefixes, snapshot projections, identity fields, layouts, sizes, and hashes.

Reaching the terminal creates and validates only a private terminal recovery
generation. `publish_one_cell_final` separately requires that state plus all
512 rows and 16 snapshots, derives deterministic final members, installs
`final.manifest.json` last without overwrite, and validates it again. Only a
valid final manifest marks completion. A malformed or corrupt present final is
fatal and never falls back; the same exact binding may validate and return a
valid final as `reused`. Every recovery generation remains private. Only the
manifest-closed final bundle is eligible for a later deliberate promotion;
this module performs no promotion.

Exact regular fixed final payloads left without a manifest are uncommitted
debris. After revalidating the terminal recovery state, the publisher may
adopt them only when they equal the newly derived deterministic bytes exactly;
otherwise it removes regular managed debris, fsyncs, and rebuilds. It never
adopts a nonregular, linked, unexpected, or mismatching member.

#### Failure and scope boundary

Nonexact caller types raise `TypeError`; invalid values, ranges, laws, or task
paths raise `ValueError`; compiled or generation-ordinal exhaustion raises
`OverflowError`; and private captured-authority corruption raises
`AssertionError`. Untrusted filesystem state, publication/readback/retention
failure, or a persisted scientific-invariant failure raises
`OneCellCheckpointValidationError`, a `RuntimeError` subclass, before further
numerical execution or destructive cleanup. Caller-owned values are never
mutated. SHA-256 detects accidental corruption but is not authentication, and
the advisory lock does not defend against a malicious same-UID writer.

This slice defines no campaign YAML/schema, plan/cell/task/attempt identity,
horizon selection, bootstrap matrix, task loop, runner, CLI, legacy dispatch,
signal installation, Slurm environment or requeue/submission action, Easley
deployment, pilot/canary/campaign execution, simulation acquisition, analysis,
promotion, release, or scientific inference. It may close only common-
correctness item 5 after its complete evidence gate. Item 6 and common
correctness remain open until Slice 8 binds one exact campaign and isolated
clone.

### 6.20 Provisional PRE campaign identity codec

Slice 8A adds a pure held-byte identity layer only through the explicit
submodule:

```python
from tetris_ballistic.engine.one_cell_campaign import (
    OneCellBootstrapMatrixIdentity,
    OneCellCampaignAuthority,
    OneCellCampaignTask,
    OneCellCampaignValidationError,
    OneCellHorizonBranch,
    OneCellTaskMapIdentity,
    decode_one_cell_campaign_task,
    encode_one_cell_campaign_task_index,
    explain_one_cell_campaign_task,
    load_one_cell_campaign,
)
```

These names are absent from both package roots. The module imports neither
Numba nor the Slice 7 checkpoint implementation and performs no filesystem,
runner, scheduler, Easley, numerical-evolution, promotion, or analysis action.

`load_one_cell_campaign` accepts exact built-in configuration bytes plus all
nine ordered `(relative_path, member_bytes)` task-map members. The campaign
member uses profile `tetris-pre-one-cell-campaign@1` and is general-YAML-
incompatible by design: it is the strict canonical JSON byte string produced
by compact sorted-key UTF-8 encoding plus one terminal LF. Duplicate or
unknown keys, floats and nonfinite values, noncanonical integer or string
encodings, alternate whitespace/newlines, aliases, anchors, tags, merges,
unsafe paths, hostile runtime subclasses, and over-limit documents fail
closed. Every task-map member is canonical LF-terminated JSONL, is bound by
exact size and SHA-256, and contains every row in the frozen root-fast order.

The held configuration binds the frozen Article protocol commit/blob/digest,
the clean one-cell model and all three boundary-law IDs, exact Philox stream
and counter conventions, four threshold schedules, F0/P0/P1/B1/B2 inventories,
all four P1 horizon branches, four bootstrap descriptors, execution and output
bounds, and all 20 complete literal 512-checkpoint/16-snapshot vectors with
their Slice 7 hashes. Synthetic Slice 8A fixtures may use future-authority
placeholder digests, but no final campaign, matrix, transported wheel, or
deployment lock is stored in this software repository.

The five returned record types are frozen, slotted, keyword-only dataclasses.
They preserve exact raw configuration/member bytes and validated immutable
projections for bootstrap matrices, task maps, horizon branches, campaign
authority, and decoded tasks. Public construction and every later operation
revalidate exact built-in types, complete cross-relations, literal vectors,
and private captured authorities; equality with a Boolean or string/integer
subclass is not accepted as an identity substitute.

The zero-based task maps are algebraically invertible:

```text
F0               8 cells   boundary -> width -> root
P0 initial      48 cells   width -> root
P0 confirmation  1 cell    its own map at index zero
each P1 map     480 cells   width -> root
B1              384 cells   boundary -> width -> root
B2             1800 cells   boundary -> width -> root
```

Threshold arms remain coupled inside a cell and are never a task dimension.
`decode_one_cell_campaign_task` maps one declared map/index to its exact
boundary, width, root, schedule, horizon, literal checkpoint/snapshot plan,
inference role, and applicable bootstrap population index.
`encode_one_cell_campaign_task_index` performs the reverse mapping and accepts
only a declared exact `OneCellBoundaryLaw`, width, and root.

`explain_one_cell_campaign_task` derives compact canonical scientific-identity
bytes. They bind the raw campaign digest, task-map digest, decoded primitive
task, complete checkpoint/snapshot vectors, applicable bootstrap descriptor
and population index, pushed 40-hex source commit, exact wheel digest, and
deployment-lock digest. P1 and the conditional P0 confirmation additionally
require a branch-decision digest; fixed-horizon maps reject one. Host, queue,
partition, concurrency, attempt, job ID, log path, and other scheduler metadata
are deliberately absent.

`OneCellCampaignValidationError`, a `RuntimeError` subclass, marks untrusted
held-byte/schema/cross-binding failures. Nonexact public argument types raise
`TypeError`, invalid exact map/value/range requests raise `ValueError`, and
captured module, builtin, imported-function, class, map-specification, or
private-cache corruption raises `AssertionError`. Cached decoded records are
sealed by deeply immutable primitive values, exact-type checked on access, and
deep-cloned before use. SHA-256 is an accidental-corruption and authority-join
mechanism, not authentication.

This pure-Python seal assumes that the genuine outermost public function or
runtime-sealed record-constructor entry executes. Replacement of that entry's
own code, closure cells, or metaclass call before its first instruction, or
direct invocation of closure-internal objects obtained through introspection,
is not an enforceable in-process boundary. Once genuine entry begins, all
captured module, builtin, imported, callable, class, cache, and literal
dependencies are checked before use.

This codec is only the Slice 8A prerequisite. It creates no `SOURCE`, `WHEEL`,
`CAMPAIGN`, `DEPLOYMENT`, admission, launch, or single-use submission claim.
Common-correctness item 6 remains open until later slices freeze the runner and
exact campaign, transport the one exact wheel, and certify a fresh isolated
Easley deployment with zero scheduler submissions or scientific tasks.

### 6.21 Provisional PRE launch and Slurm runner

Slice 8B adds a fail-closed orchestration layer through the explicit submodule
only:

```python
from tetris_ballistic.engine.one_cell_runner import (
    OneCellAuthorizedTask,
    OneCellLaunchAuthority,
    OneCellLaunchTask,
    OneCellRunnerAuthorizationError,
    OneCellRunnerOutcome,
    OneCellRunnerPaths,
    OneCellRunnerValidationError,
    OneCellSchedulerError,
    OneCellSlurmResourceEnvelope,
    OneCellSubmissionOutcome,
    authorize_one_cell_slurm_task,
    explain_one_cell_launch_task,
    list_one_cell_launch_tasks,
    load_one_cell_launch_authority,
    run_one_cell_authorized_task,
    submit_one_cell_launch,
)
```

These names are absent from both package roots. The three errors are direct
sibling `RuntimeError` subclasses. All seven records are sealed, frozen,
slotted, keyword-only dataclasses with exact resolved annotations; nested
campaign/task/authority values and ordered environment tuples are deep-
snapshotted and revalidated at every public entry.

```text
load_one_cell_launch_authority(*, authorization_path: str)
list_one_cell_launch_tasks(*, launch: OneCellLaunchAuthority)
explain_one_cell_launch_task(*, launch: OneCellLaunchAuthority,
                             array_position: int)
authorize_one_cell_slurm_task(*, launch: OneCellLaunchAuthority,
                              submission_claim_bytes: bytes,
                              submission_receipt_bytes: bytes)
run_one_cell_authorized_task(*, authorization: OneCellAuthorizedTask)
submit_one_cell_launch(*, launch: OneCellLaunchAuthority)
```

The loader accepts one absolute private authorization directory containing
exact `launch.json`, `ordered-tasks.jsonl`, `readback.json`, and
`runtime-python.path`. It parses strict duplicate-aware canonical JSON/JSONL,
enforces every profile/key/type/size/path bound, reconstructs the Slice 8A
campaign and scientific identities, and joins the pushed protocol, source,
wheel, campaign, deployment, branch when applicable, admission, task map,
batch wrapper, resources, interpreter, and coordinator readback. The clean
detached coordinator checkout is inspected only with a content-bound Git
binary, a scrubbed environment/config inventory, the exact main-only fetch
refspec `+refs/heads/main:refs/remotes/origin/main`, and exact no-write argv.
The launch commit must descend coordinator authority
`087cdaf8d8444de7d9548bc1c97ca42f221cef27`; the detached `SOURCE` must descend
software parent `b33cc0191298d80f0bdc944a3a5e444952873e37`.
Bootstrap Git must be owned by a trusted administrator other than the current
user; scheduler tools may instead use an explicitly allowed owner.

Production records bind immutable scheduler and scientific process
environments, a single partition, bounded array mapping, exact `sbatch` and
`scontrol` content identities, private task/log/cache/temp/ledger roots, a
content-bound Python interpreter, and one generic wrapper. Scheduler IDs are
bounded positive uint32 decimal strings. Generated names and absolute paths
are checked against fixed and descriptor-reported component/path limits before
any write or call. Before the first Git process, the closest existing held
parents preflight all ledger target/temporary shapes, task/attempt and
checkpoint/final shapes, log templates, and scheduler argv members. The only
persisted fixture profiles are the paired
`tetris-pre-one-cell-launch-fixture@1` and
`tetris-pre-one-cell-admission-fixture@1`; both carry the same frozen
`scientific_execution_permitted: false` object. Supporting records keep their
single production schema spelling, and every other `-fixture@1` spelling is
invalid. Inspection may parse the fixture pair, but every submission, Slurm
authorization, and lifecycle mutation route refuses the fixture launch before
a scheduler call, checkpoint import, or persistent write.
Every public record argument is recursively cloned through campaign
identities, ordered tasks, resources, paths, and environment tuples before it
is used; nested caller-owned dataclass objects are never retained by alias.

A branch decision must join the selected Slice 8A horizon record and P1 task
map: `rule.profile` is `tetris-pre-one-cell-horizon-branch@1`,
`rule.input_sha256` equals the initial-P0 `final-manifests.jsonl` file-ref
digest, and the map digest, `l_star`, and confirmation fields reproduce the
campaign authority.

Submission is initial-call-exactly-once. Under a descriptor-relative private
ledger lock, the gate durably installs and reads back one no-replace claim
before the sole exact argv-based `sbatch` call. It drains stdout/stderr with
8-KiB bounded prefixes and explicit overflow flags, then durably installs one
immutable accepted/rejected/unknown receipt. Any prior claim, rejection,
timeout, malformed response, ambiguous spawn, overflow, crash, or publication
failure consumes that launch and permits no automatic replay. Only an accepted
receipt with one bounded decimal array job ID can authorize an in-job task.
Before the claim is written, held claims/receipts descriptors validate the
complete target names plus the receipt's fixed 32-hex temporary-link shape
against component and rendered-path limits. The same preflight covers the
permit/result names and result temporary-link shape before a permit write or
`scontrol`; impossible durable publication therefore causes zero scheduler
calls.
Receipt/result publication first fsyncs the temporary file and directory to
establish the guard, then fsyncs the target directory while target and guard
links both exist, unlinks the guard, and fsyncs again. A crash before the
proving fsync or guard unlink leaves link count two and is refused; afterward
the target is already durable and single-link. Proving-fsync failure removes
the target before the guard and fsyncs cleanup. Stable file reads recheck
identity, timestamps, ownership, mode, and link count after the final byte;
retained private-directory descriptors are rechecked throughout creation.
The private submission-reconciliation parser validates committed evidence
only: both replay permissions remain false and another initial call requires a
separately approved superseding launch.

The top-level CLI dispatcher only materializes argv and selects the execute or
inspection entry. The dedicated execute entry blocks `SIGUSR1` in its first
statement, before argument or authority parsing. After all authority, receipt,
Slurm, path, restart-permit, and lazy checkpoint-import gates, it installs the
request-only `OneCellInterruptionFlag` handler and unblocks atomically, so a
signal pending during the receipt handshake is neither fatal nor lost. The
prior mask and handler are restored on every exit.
One decoded campaign cell maps to one exact Slice 7 binding and task directory.
The runner advances durable generations until terminal, publishes/reuses the
sole final manifest only after the final signal linearization point, and may
issue one exact-element `scontrol requeue` only after a durable no-replace
permit. Accepted, rejected, and unknown requeue results are immutable; no
result permits a second call.

The runner module imports neither the checkpoint module nor Numba eagerly.
The first production checkpoint import occurs only after full authorization;
an installed no-`hpc` environment therefore preserves ordinary package and
campaign imports and gives the frozen explicit missing-extra failure only on
the private probe/authorized runner boundary. The new CLIs are
`python -m tetris_ballistic.scripts.run_pre_one_cell` and
`python -m tetris_ballistic.scripts.submit_pre_one_cell`; neither is a console
entry point or legacy-dispatch alias. Their exact modes, outputs, controlled
exit codes, wrapper, authority profiles, and operational file layout are
specified in `docs/PRE-ONE-CELL-RUNNER.md`.

The source distribution also carries a separate inert administrative compute
wrapper for the submission CLI. It requires the live fields of an exact
non-array `nova_short` compute allocation and kernel/Slurm hostname equality
before reading the runtime sidecar or starting project Python. A separately
sealed operational manifest and coordinator record bind outer options that are
not observable from inside the allocation, including no-requeue/export mode,
walltime, working directory, and logs. The wrapper is not imported, installed
in the wheel, or used as the launch-bound scientific batch script, and
therefore does not change the runner API, campaign identity, or child-array
scheduler argv. Both sealed PRE wrappers invoke the installed sibling module
`tetris_ballistic_pre_one_cell_bootstrap` with exactly one literal `run` or
`submit` target. That sibling validates isolated/cache-disabled/UTF-8 startup,
the scrubbed environment, collision-free module state, and canonical unlinked
installed paths before seeding synthetic package, engine, and scripts paths.
It never executes the legacy package-root or engine initializer, rejects any
unexpected descendant or plotting/XML import, and keeps the run CLI's lazy
runner behind its existing SIGUSR1 mask boundary. This is not a public package
mode or API, and no environment sentinel or root/CLI edit is involved. Because
the sibling changes wheel identity and both wrapper bytes, deployments using
it must pin fresh source, wheel, and wrapper authorities.

This slice implements and tests the generic gate with permanently ineligible
fixtures and private mocked state-machine drivers. It creates no real campaign,
deployment certificate, admission, launch, ledger claim, scheduler job,
Easley task, checkpoint/final under a declared campaign root, scientific
output, promotion, analysis, or inference. Common-correctness item 6 remains
open until the exact transported wheel and campaign are frozen and an isolated
Easley tree passes the separate zero-launch certification.

### 6.22 Clocks

The engine records, without substitution,

- event count;
- attempts per substrate site;
- deposited occupied mass per substrate width;
- mean interface height.

`ClockKind` is an enum in analysis APIs. Every fitted quantity records its clock. A function must not silently change from one clock to another.

### 6.23 Configuration

`SimulationConfig` contains

- schema version;
- substrate geometry and boundary condition;
- piece ensemble;
- orientation law;
- contact rule;
- stopping rule;
- requested observables/checkpoints;
- RNG specification;
- numeric dtype/precision policy;
- output policy.

Validation occurs before allocation or simulation. During M1.1, the typed objects expose only the repository-local digest profiles `tetris-ballistic/software-geometry-record@1` and `tetris-ballistic/software-config-record@1`. These digests are not shared scientific identities and must not be compared with data-repository record hashes. A shared result-bundle projection remains an M1.3 gate.

### 6.24 Results

`SimulationResult` exposes read-only-by-contract arrays or defensive copies for

- clocks;
- interface width;
- interface envelope/checkpoints;
- deposited mass;
- porosity;
- lateral-contact and bridge statistics;
- stopping metadata;
- provenance.

The persistence layer snapshots caller arrays before writing. A reversible NumPy `writeable=False` flag is not advertised as strong immutability.

## 7. RNG and reproducibility

- New generic transition laws use the exact
  `semantic-philox4x64-10-v1` counter-addressed contract, not a library-default
  NumPy bit generator or high-level distribution call.
- Root seeds are unsigned 128-bit values. Stream keys bind the frozen domain,
  exact root bytes, coupling group, and stable semantic stream name.
- Event and rejection ordinals are direct counter words, so parallel
  scheduling, a rejection in one event, or a draw in another named stream may
  not shift a trajectory.
- Common-random-number factor arms and widths share the counter-addressed raw
  candidate tape for each explicitly declared `family`, `orientation`,
  `launch`, and `contact` stream within a coupling group; an arm or width is
  not an implicit key salt. Equal bounds accept the same bounded variate and
  rejection ordinal. Different bounds can reject at different ordinals, so the
  frozen mapper does not guarantee one literal accepted uniform across such
  laws. S2.4 implements the PI-ratified shared raw tape—not a shared accepted
  variate—as the package coupling contract.
- The S2.4 selector consumes one logical variate from each fixed stream at every
  event, including degenerate choices. Its orientation draw is interpreted
  through the selected family's prevalidated branch; unselected branch laws
  receive no additional draws.
- The existing one-cell compatibility path remains separately pinned to
  `legacy-dual-stream-v1`; it is not silently migrated to the semantic
  contract.
- Golden fixtures bind raw Philox output, stream-key bytes, bounded and
  categorical mappings, configuration identity, software version, and expected
  transition arrays.

## 8. Public Python API

The 3.0 target surface is deliberately small:

```python
from tetris_ballistic import (
    SimulationConfig,
    PieceGeometry,
    PieceEnsemble,
    OrientationDistribution,
    ContactRule,
    ClockKind,
    simulate,
    run_ensemble,
    load_result,
)
```

Analysis APIs live under explicit modules:

```python
from tetris_ballistic.analysis import analyze_growth, analyze_scaling, analyze_distribution
```

No wildcard exports are permitted in the 3.0 public surface. The project publishes an API stability table distinguishing stable, provisional, and internal symbols.

## 9. CLI contract

Install one entry point, `tetris-bd`:

```text
tetris-bd simulate CONFIG --output DIR [--dry-run]
tetris-bd sweep GRID --output DIR [--resume] [--dry-run]
tetris-bd reduce RUN_DIR --output BUNDLE
tetris-bd analyze growth BUNDLE --output DIR
tetris-bd analyze distribution BUNDLE --output DIR
tetris-bd validate PATH
tetris-bd benchmark [--json OUTPUT]
```

Rules:

- every command supports `--help` and machine-readable errors;
- after the shared M1.3 schema exists, simulation/sweep commands validate and print its profile-qualified config hash before work;
- `--dry-run` performs validation, geometry expansion, resource estimates, and output planning without mutation;
- resume verifies configuration identity before skipping existing cells;
- exit codes distinguish invalid input, incomplete data, integrity failure, and runtime failure;
- CLI smoke examples run in CI.

Legacy `python -m tetris_ballistic.scripts.*` entry points remain during 2.1.x and delegate to the new implementation where possible.

## 10. Scientific result-bundle protocol

A result bundle is a closed, content-addressed protocol:

```text
config.json
geometry.json
provenance.json
summary.json
arrays.npz            # or arrays.zarr in a release asset
manifest.json
checksums.sha256
```

### Required identities (M1.3 target)

The current M1.1 software-local record digests do not satisfy this cross-repository contract.

- schema version;
- shared, profile-qualified configuration hash;
- shared, profile-qualified geometry hash;
- manifest generation ID;
- software version and git SHA when available;
- platform and dependency versions;
- RNG identity and seeds.

### Canonical data rules

- UTF-8 canonical JSON; finite numbers only; duplicate keys rejected;
- canonical dtype strings such as `<f4`, not aliases such as `f4`/`float`;
- no pickle, object, or structured dtypes in public arrays;
- rank, shape, array count, member count, JSON size, header size, and aggregate uncompressed size are bounded;
- directory, checksum, manifest, and archive inventories match exactly;
- unexpected files, symlinks, devices, traversal, and absolute paths are rejected;
- a reader hashes and decodes the same opened bytes, not a path reopened after validation;
- publication validates the complete staged bundle before atomic no-replace publication.

Schema-major changes require a bundle major-version change and migration utility.

## 11. Compatibility and releases

### 2.1.x transition

- preserve `Tetris_Ballistic` and current imports;
- introduce typed objects and adapters;
- route existing scripts through shared validated configuration code;
- add deprecation warnings with documented replacements;
- retain reference behavior and golden fixtures;
- publish a migration guide.

### 3.0.0 gate

Version 3.0 may ship only when

- one-cell and representative tetromino configurations pass migration tests;
- reference/optimized trajectories satisfy declared equivalence;
- public CLI and bundle schemas are stable;
- data-repository smoke fixtures reproduce with the release candidate;
- one full deprecation minor cycle has elapsed.

No silent behavior change is permitted under an existing schema or API version.

## 12. Quality requirements

### Platforms and packaging

- Python 3.10--3.13;
- Linux, macOS, and Windows CI for pure Python/reference paths;
- Linux numba/HPC CI;
- PEP 517 wheel and sdist build from `pyproject.toml` only;
- clean-venv install/import/CLI smoke;
- no duplicate authoritative metadata in `setup.py`.

### Static quality

- ruff format and lint on the migrated source/test tree;
- mypy or pyright strict mode on new public modules;
- no type suppressions as substitutes for correct models;
- explicit public exports;
- API documentation generated from typed docstrings.

### Tests

- at least 90% statement coverage on new modules;
- 100% branch coverage for schema/config validation;
- property tests for coordinate normalization, orientation generation, ensemble probabilities, and bundle inventories;
- deterministic RNG and parallel-scheduling tests;
- legacy migration and golden-trajectory tests;
- adversarial bundle tests: nonfinite values, pickle/object dtype, duplicate JSON keys, checksum omission, traversal, symlink swap, archive bomb, config/geometry mismatch, stale overwrite, and concurrent writers;
- documentation examples executed in CI.

### Performance

- preserve a versioned benchmark corpus and JSON output;
- no more than 10% regression on the existing one-cell benchmark without documented approval;
- add reference versus optimized mixed-tetromino benchmarks before claiming speedups;
- performance claims cite hardware, software versions, warm-up policy, and sample statistics.

Invented target speedups are prohibited.

## 13. Documentation requirements

The public site must contain

- five-minute quickstart;
- model and contact-rule taxonomy;
- geometry/orientation/mixture tutorial;
- clocks and observable semantics;
- local sweep and Slurm/HPC guide;
- result-bundle/data-schema reference;
- reproducibility and RNG guide;
- analysis assumptions and finite-size warnings;
- extension guide for a new piece/contact rule/observable;
- migration guide from legacy APIs;
- troubleshooting and scientific anti-patterns.

At least two end-to-end examples must be independently runnable: one one-cell baseline and one mixed tetromino experiment.

## 14. Governance and supply chain

Add and maintain

- `CONTRIBUTING.md`;
- `SECURITY.md`;
- issue and pull-request templates;
- `CODEOWNERS`;
- code of conduct;
- API/deprecation policy;
- semantic changelog;
- signed/checksummed GitHub releases;
- PyPI trusted publishing through OIDC rather than a long-lived token;
- dependency review and automated update policy;
- release checklist including clean build, tests, type checks, docs, data smoke, and provenance.

## 15. Phased implementation

### M1.1 — contracts and compatibility shell

- introduce model/config/schema modules without replacing legacy simulation;
- add canonical registry and property tests;
- define CLI parser and dry-run behavior;
- establish API exports and migration adapters.

### S2.1 — provisional deterministic event oracle

- expose the reflected geometry view without changing software-local records;
- implement exact sparse one-event placement for `supported-v1` and
  `edge-first-contact-v1`;
- provide an explicit complete-positive-support periodic-law preflight;
- keep the oracle behind an explicit provisional submodule import; and
- require exhaustive and independent reference evidence before any production
  trajectory route or optimization.

### S2.2 — provisional counter-addressed RNG oracle

- implement the frozen raw Philox4x64-10, stream-key, exact bounded-integer,
  and canonical categorical primitives with no NumPy distribution semantics;
- certify the byte, word, lane, counter, and mapping order against upstream
  known-answer vectors and a separately implemented end-to-end oracle;
- keep the stateless primitives behind an explicit submodule import; and
- defer exact weighted-law records, law-specific stream schedules, event
  selection, trajectories, configuration execution, and all production routes
  to separately verified units.

### S2.3 — provisional exact-law and one-stream selection records

- preserve explicit ordered outcome IDs, canonical integer counts, and zero
  positions without using the established float-normalized model records;
- validate ordered declared-stream membership before every one-stream draw;
- retain complete accepted-rejection metadata and pin shared-candidate/
  different-bound rejection behavior; and
- defer named family/contact order, conditional orientation resolution,
  complete-event consumption, configuration execution, placement composition,
  trajectories, serialization identity, and every production route.

### S2.4 — provisional complete tetromino event selection

- implement the PI-ratified exact five-family, two-contact, and four-stream
  orders plus the full five-branch orientation table from the fixed
  19-geometry registry;
- validate and snapshot the complete address, law, and stream schedule before
  drawing family, selected-family orientation, launch, and contact exactly once;
- bind the returned in-memory evidence to its address, complete law, and all
  four accepted-rejection records while defining coupling as the shared raw
  candidate tape under law-local acceptance; and
- defer a generic conditional selector/DAG, named control laws, canonical
  serialization and digest identity, placement/configuration composition,
  trajectories, legacy migration, optimized kernels, HPC, and every production
  route.

### M1.2 — reference engine extraction

- complete the pure exact state- and already-certified-placement-primitives
  slices under the explicit `engine.observables` submodule and the exact
  one-event selection-to-placement certificate under explicit
  `engine.binding`, plus the exact in-memory fold of an already-bound event
  under explicit `engine.accumulation`, while leaving checkpoint/persisted-byte
  identity, I/O, configuration execution, and trajectories open;
- separate state, placement, RNG, observables, and I/O from the legacy class;
- preserve legacy adapters and golden behavior;
- add contact-rule and multi-clock instrumentation.

### M1.3 — bundle and analysis integration

- implement safe writer/reader and schemas;
- migrate analysis entry points to typed bundles;
- verify data-repository smoke fixtures.

### M1.4 — optimized tetromino path

- profile the reference implementation;
- optimize only measured bottlenecks;
- require reference equivalence and benchmark evidence.

### M1.5 — release hardening

- cross-platform CI, typing, docs, trusted publishing, governance;
- release 2.1.x compatibility version;
- complete deprecation cycle and assess 3.0 gate.

## 16. Non-goals

- No universality classification is encoded in the simulation API.
- No raw research dataset is bundled in wheels.
- No automatic publishing from an HPC cluster.
- No optimization before reference correctness and profiling.
- No mandatory heavy dependency for basic simulation; optional I/O/HPC extras may provide numba/Zarr/xarray support.
- No removal of legacy APIs before the declared migration gate.

## 17. M1 acceptance checklist

M1 is complete only when

- geometry, orientation, ensemble, contact, clocks, config, RNG, and result semantics are independently typed and serialized;
- five-free/19-fixed registry tests pass;
- one-cell and tetromino reference simulations run through the public API and CLI;
- result bundles pass ordinary and adversarial validation;
- legacy examples pass through the compatibility layer;
- cross-platform CI, typing, coverage, build, docs, and data smoke gates pass;
- a versioned 2.1.x release is published through trusted workflows;
- the public documentation states limitations and avoids asymptotic scientific claims.
