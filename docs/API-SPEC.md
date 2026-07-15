# `tetris-ballistic` Community API and Architecture Specification

**Specification version:** 0.5.0

**Status:** M1.1 contracts plus provisional S2.1 exact placement, S2.2
counter-addressed semantic-RNG oracles, and S2.3 explicit-order exact-law/
one-stream selection records, plus S2.4 fixed-order tetromino event selection,
an explicit reference-only one-event selection-to-placement binder, and
pure exact reference-state and already-certified-placement primitive
extractors, plus an explicit-only exact in-memory event/contact accumulator;
checkpoint/persistence identity, trajectory routing, and shared
cross-repository schemas are not implemented

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

### 6.13 Clocks

The engine records, without substitution,

- event count;
- attempts per substrate site;
- deposited occupied mass per substrate width;
- mean interface height.

`ClockKind` is an enum in analysis APIs. Every fitted quantity records its clock. A function must not silently change from one clock to another.

### 6.14 Configuration

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

### 6.15 Results

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
