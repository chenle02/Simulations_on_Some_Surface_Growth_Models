# `tetris-ballistic` Community API and Architecture Specification

**Specification version:** 0.2.0

**Status:** M1.1 contracts plus a provisional S2.1 single-event reference
oracle; trajectory routing and shared cross-repository schemas are not
implemented

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

`PieceEnsemble` maps geometry IDs to normalized nonnegative probabilities. `OrientationDistribution` maps each free family to probabilities on its canonical orientation IDs. Zero-total, negative, nonfinite, unknown, or duplicate entries are rejected.

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
the periodic cardinality/N4-adjacency invariant at every anchor. It returns the
validated immutable geometry tuple. The one-event function cannot infer a
mixture's other positive-weight geometries, and this preflight is not a
`SimulationConfig` execution route.

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
- RNG selection, sampling, named streams, or draw accounting;
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

### 6.6 Clocks

The engine records, without substitution,

- event count;
- attempts per substrate site;
- deposited occupied mass per substrate width;
- mean interface height.

`ClockKind` is an enum in analysis APIs. Every fitted quantity records its clock. A function must not silently change from one clock to another.

### 6.7 Configuration

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

### 6.8 Results

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

- Default to a named NumPy bit generator with its exact versioned identity.
- Record root seed and deterministic child-seed derivation.
- Parallel scheduling must not change per-cell trajectories.
- Common-random-number comparisons use a documented shared event stream for shape/orientation and an independent contact-rule stream.
- Optimized and reference kernels must consume equivalent pregenerated random arrays when bit-level comparison is required.
- Golden fixtures include configuration hash, software version, and expected arrays.

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

### M1.2 — reference engine extraction

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
