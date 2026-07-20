# Changelog

All notable changes to `tetris_ballistic` are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [2.1.0] — Unreleased

This compatibility release gives the scientific corrections and additive APIs
developed after the 2.0.0 source milestone their own provenance boundary. The
version-boundary change itself does not introduce another simulation-trajectory
change.

### Corrected scientific semantics

- Restored `AvergeHeight` to the physical mean height,
  `height - mean(top-origin row index)`. Some source builds identifying as
  2.0.0 instead stored the descending top-origin row index. This correction
  changes that observable, but not the deposited substrate, `SampleDist`,
  `FinalSteps`, or `Fluctuation`. Existing affected exp14 traces are recoverable
  as `physical_hbar = grid_height - stored_hbar`; that migration must remain
  explicit in artifact provenance.
- Measure KPZ growth exponents against deposited height (`log W` versus
  `log hbar`), restrict plateau detection to the physical growth window, and
  exclude unsaturated widths from infinite-size extrapolation. Estimates from
  the earlier step-index/unbounded-window analysis are not interchangeable with
  the corrected estimates.
- Record the executable one-cell model identity and mixture convention
  explicitly: legacy density entries are `[nonsticky, sticky]`; exp13 percentage
  labels denote the nonsticky fraction, whereas exp14 labels denote the sticky
  fraction. `Piece-19` is a one-cell baseline, not a tetromino.

### Added

- A bounded S2-exit reference trajectory under the explicit
  `tetris_ballistic.engine.reference_trajectory` submodule. Frozen keyword-only
  configuration binds the model/plan IDs, source revision, root and coupling
  group, complete tetromino law, width, terminal horizon, exact
  `semantic-philox4x64-10-v1` identity, and the PRE-compatible vector of 512
  strictly increasing checkpoint ordinals. The slow driver consumes family,
  selected-family orientation, launch, and contact exactly once per event,
  folds the certified placement through the exact accumulator, and emits
  selected full-occupancy checkpoints as compact sorted-key UTF-8 canonical
  JSON with exact built-in integers, one trailing newline, and SHA-256 byte
  identity. Reconstruction reparses strict canonical bytes, independently
  replays the bound configuration through lower certified selection/placement
  primitives rather than the writer's high-level composition path, compares
  every state and accumulator primitive, validates the complete checkpoint
  inventory, and permits resume or the sole terminal manifest only after that
  replay. The fixed test-only exit sweep covers eight approved factor paths,
  two legal widths, four roots, and 256-event prefixes (16,384 total events),
  with no treatment inspection. This closes the ratified bounded oracle-only
  S2 checkpoint/identity/reconstruction/configuration/trajectory contract, but
  adds no root export, filesystem I/O, optimized or legacy route, CLI,
  scheduler, Easley/Slurm/HPC action, acquisition, release, or production
  path; S3 and every later scientific gate remain blocked.
- A source-distributed administrative compute wrapper for PRE submission.  It
  refuses login hosts, outer arrays, restarts, and resource/partition drift,
  rechecks the private runtime sidecar and interpreter, and only then executes
  the unchanged submission CLI.  It is separate from the scientific batch
  authority and from the certified wheel/campaign/deployment; the login node
  performs only the direct outer scheduler-control call.
- A provisional fail-closed PRE launch and Slurm runner under the explicit
  `tetris_ballistic.engine.one_cell_runner` submodule, with distinct in-job
  and submission module CLIs plus one generic inert Easley wrapper. Frozen,
  sealed records join the pushed protocol/source/wheel/campaign/deployment,
  optional branch, lane admission, exact ordered Slice 8A identities,
  content-bound interpreter/Git/Slurm tools, private path/resource/process
  environments, and post-push coordinator readback before any mutable action.
  Public records are recursively snapshotted without retaining nested caller
  aliases.
  Submission installs one durable no-replace claim before the sole exact
  `sbatch` array call and records bounded accepted/rejected/unknown output in
  one immutable receipt; no ambiguity permits replay. In-job authorization
  requires that accepted receipt and exact Slurm mapping, blocks `SIGUSR1`
  before its bounded handshake, lazily imports the Slice 7 checkpoint surface,
  advances one exact cell, and permits only one durable exact-element requeue
  after a no-replace permit. Every public projection is rebound to held and
  live authority bytes; coordinator and software histories must descend their
  frozen Slice 8B prerequisites. Filesystem-reported name/path limits,
  pairwise-isolated roots, retained no-follow descriptor chains, immutable
  ledger-name identities, and nonwritable batch ancestry protect every
  generated path and scheduler boundary. All deterministic runtime path and
  temporary shapes are preflighted before Git; the guard entry is fsynced
  before linking, and two-link target fsync precedes guard unlink so every
  crash boundary is either linked-and-refused or already durable. Final
  file/private-directory metadata is rechecked on retained
  descriptors. A private evidence-only
  reconciliation validator freezes replay to false and requires a superseding
  launch. Fixture profiles refuse submission and scientific
  execution before writes/imports/scheduler calls; successful scheduler and
  width-3/terminal-769 lifecycle coverage uses private mocked drivers only.
  The source distribution carries the wrapper once while the wheel excludes
  it; no root export, console entry point, legacy dispatch, dependency, real
  Easley/Slurm action, final campaign byte, launch authority, declared-horizon
  run, or scientific acquisition is added. Common-correctness item 6 remains
  open through the exact campaign freeze and zero-launch isolated Easley
  certification.
- A provisional held-byte PRE campaign codec under the explicit
  `tetris_ballistic.engine.one_cell_campaign` submodule. Its frozen, slotted,
  keyword-only records and four task operations accept only strict
  `tetris-pre-one-cell-campaign@1` canonical-JSON bytes plus all nine complete
  canonical-JSONL task maps; validate exact protocol/model/execution records,
  four bootstrap descriptors, four precommitted P1 horizon branches, every
  F0/P0/P1/B1/B2 task row, and all 20 literal 512-checkpoint/16-snapshot vector
  pairs; and provide exhaustive root-fast forward/reverse task mapping. The
  task explanation joins raw campaign and map digests to external pushed
  source, exact wheel, deployment lock, and applicable branch-decision
  authorities in compact scientific-identity bytes while excluding host,
  queue, attempt, and scheduler metadata. The module is memory-only, imports
  neither checkpoint/Numba nor legacy dispatch, is not package-root exported,
  and creates no final campaign YAML, bootstrap bytes, wheel, lock, task
  directory, runner/CLI, Slurm/Easley action, simulation acquisition, output,
  analysis, promotion, release, or launch authority. Synthetic exhaustive KATs
  certify Slice 8A only; common-correctness item 6 remains open through the
  later exact campaign freeze and campaign-isolated Easley certification.
- A provisional manifest-last checkpoint and interruption/resume surface under
  the explicit `tetris_ballistic.engine.one_cell_checkpoint` submodule. Its
  exact eight-name, keyword-only API builds the Article's 512-checkpoint and
  16-snapshot schedules, binds one canonical Slice 5 start to the captured
  Slice 6 compiled chunk, commits at strict global `2**20` recovery boundaries,
  and exposes a one-Boolean signal latch without installing handlers or issuing
  requeue actions. Recovery validates exact opaque configuration/scientific
  bytes, request and RNG identity, software commit, next event ordinal,
  checksums, little-endian unsigned array layouts, and every trajectory,
  histogram, causal/equality, seam, snapshot, and nesting invariant before
  reuse. Persistent descriptor-anchored locking, manifest-last fsync/readback,
  monotone generations, newest-two-valid retention, explicit matching-identity
  fallback, and fatal mismatch/corrupt-final rules make partial, stale,
  mismatched, and concurrent same-task state fail closed. A terminal recovery
  generation remains private and incomplete; only the separate deterministic
  `final.manifest.json` marks a final bundle complete. Normative full 512/16
  KATs at terminals 769 and 100,663,296 and exact hashes for all 20 declared
  horizons come from an independent integer-only generator and are schedule
  evidence, not Slice 8 campaign identities. The module is not root-exported,
  imports no legacy artifact authority, and adds no campaign YAML/schema,
  task loop, runner/CLI, signal installation, Slurm/Easley action, pilot or
  campaign execution, simulation acquisition, analysis, promotion, release,
  or scientific inference. Slice 7 may close only common-correctness item 5
  after source, corruption/interruption, package, review, CI, and parity gates;
  item 6 and common correctness remain open.
- A provisional Numba multi-arm chunk backend under the explicit
  `tetris_ballistic.engine.one_cell_trajectory_compiled` submodule. Its one
  keyword-only operation accepts and returns the exact frozen scalar record,
  derives the certified launch/contact keys once each on the host, and evolves
  the inferred contiguous interval entirely through unsigned nopython RNG,
  three-law recurrence, and accumulator arithmetic. It supports the exact
  primary, B1, B2-full, and B2-high schedules without placing schedule, law,
  or threshold in an RNG address. Fresh private arrays and a typed sparse
  histogram carry every scalar field, with exact high-first `Q` words,
  explicit square-subtraction borrow, addition carry, overflow reporting, and
  atomic failure. An empty chunk reconstructs an equal record without key
  derivation, compiled allocation, RNG, or kernel dispatch. The three-way
  certificate compares an independent primitive-tuple oracle, the scalar
  backend, and complete compiled records across 84 persisted rows, exhaustive
  small tapes, real-RNG and exact Article matrices, all short and long
  partitions, forced launch/contact rejection, packed-Q carry/borrow/overflow
  witnesses, hostile records, and Numba 0.58 floor coverage. The existing
  `hpc` extra supplies Numba; package roots remain importable without it, and
  explicit import without it reports the submodule and extra clearly. The
  module is not root-exported and adds no compiled start or public record,
  checkpoint/persistence, campaign dispatch or identity, runner/CLI,
  scheduler, Slurm/Easley/HPC submission, output, analysis, release, or
  scientific acquisition. Slice 6 may close only common-correctness item 4
  after its source, package, review, CI, and parity gates; items 5--6 remain
  open.
- The provisional exact scalar common-draw trajectory under
  `tetris_ballistic.engine.one_cell_trajectory` now accepts one additive
  keyword-only `threshold_schedule`. It admits exactly primary
  `(0, 1, 2, 5, 10, 25, 50, 100)`, B1 `(0, 5, 50, 100)`, B2-full
  `(5, 50, 90, 95, 98, 99)`, or B2-high `(90, 95, 98, 99)`; the original
  primary default, four-name export surface, retained records, and every
  primary vector remain unchanged. A trajectory exposes its schedule only as
  a derived property. Each event shares the certified selector's launch and
  contact values across the selected arms, applies literal
  `contact < threshold`, and folds the certified three-law boundary result.
  B1 and B2-high are exact projections, while 36 B2-full rows extend the 48
  primary root-zero, width-three `[0,7)` and `[0,50)` vectors. The schedules
  are evolution laws only: width-to-schedule dispatch and campaign identity
  remain later gates. This additive scalar recertification creates no packed
  public state, persistence/resume, configuration, runner/CLI, scheduler,
  Easley/Slurm/HPC submission, output, analysis, release, or scientific
  acquisition route.
- A provisional pre-derived-key compiled Philox4x64-10 and exact
  bounded-integer surface under the explicit
  `tetris_ballistic.engine.rng_compiled` submodule. Its three keyword-only
  functions expose the four-lane bijection, lane-zero raw words at counters
  `(event, rejection, 0, 0)`, and exact bounds from one through `2**64`; the
  bounded result reuses the frozen scalar `SemanticDraw`. The implementation
  contract requires unsigned limb multiplication, private `n - 1` bound
  encoding, candidate evaluation even for bound one, identity mapping for
  bound `2**64`, fail-before-wrap rejection accounting, and Numba nopython
  signatures without object mode, floating point, fast math, or high-level
  random distributions. Its conformance-receipt index pins the upstream,
  project, PRE, and scalar-comparison digests and defines a 56-row base
  manifest plus three supplementary probes and every applicable
  exact-selection and complete-event uniform/raw projection, including natural
  acceptance at rejection ordinals one, two, and five.
  This module is not root-exported; it does not compile SHA-256 key derivation
  or categorical interval search and adds no scheduler, transition,
  trajectory, persistence, configuration/legacy, CLI, Easley/Slurm/HPC,
  release, or scientific-acquisition route. The legacy `_kernel_1x1.py` is
  neither imported nor an authority, and common-correctness items 4--6 remain
  open gates.
- A provisional pure three-boundary scalar transition under the explicit
  `tetris_ballistic.engine.one_cell_boundary` submodule. The keyword-only
  operation covers `periodic-v1`, archived
  `hard-wall-legacy-asymmetric-v1`, and corrected
  `hard-wall-reflection-symmetric-v1`; returns a frozen, self-validating
  certificate with physical neighbor existence, separate law eligibility,
  exact height/void/squared-height increments, endpoint and positive-gap
  distinctions, eligible causal side, height-defined equality mask, and
  boundary-appropriate seam status; and delegates the periodic route exactly
  once to the Slice 1 authority. Certification exhausts 12,672 events per law
  at widths 3--5 and heights 0--3, pins five identical exp14 source and kernel
  archives, compares the legacy route with an independent inverted-row oracle
  and an exact executable archived-method fixture, compares the corrected route
  with a separately written physical-height oracle, and proves corrected
  reflection symmetry while retaining the named archived `x=1` defect. The
  module is not root-exported and adds no RNG, coupled-arm evolution,
  accumulation, trajectory, compiled path, persistence,
  configuration/legacy dispatch, CLI, Easley/Slurm/HPC route, release, or
  production path; compiled RNG, trajectory equivalence, resume, campaign
  identity, and scientific acquisition remain gated.
- A provisional PRE one-cell common-random-number selector under the explicit
  `tetris_ballistic.engine.one_cell_coupling` submodule. The keyword-only
  operation fixes coupling group `pre-one-cell-discovery-v1`, the ordered
  `launch`/`contact` stream schedule, and stickiness thresholds
  `(0, 1, 2, 5, 10, 25, 50, 100)`; it consumes one exact uniform launch draw
  and one exact uniform contact draw per event, then derives all eight nested
  arm decisions by the strict predicate `contact < threshold`. Returned frozen
  evidence retains the root, event, width, both selected values, and both
  accepted-rejection ordinals. Certification covers every contact integer and
  every planned campaign width; persistent vectors pin stream keys, strict
  threshold boundaries, forced rejection, and an unequal-width case that
  distinguishes a shared raw candidate tape from a shared accepted variate.
  The module is not root-exported and performs no transition, arm-state
  evolution, trajectory, accumulation, persistence, configuration or legacy
  adaptation, compiled RNG/kernel execution, CLI, Easley/Slurm/HPC routing,
  release, or production dispatch; it does not close the compiled-RNG
  admission gate.
- A provisional pure transition under the explicit
  `tetris_ballistic.engine.one_cell` submodule for the clean
  `one-cell-rd-bd-periodic-v1` law. The keyword-only operation snapshots a
  plain height sequence and applies one exact periodic RD/BD event, returning
  a frozen, self-validating certificate with exact height, void, and squared-
  height increments; endpoint and positive-gap distinctions; causal side;
  fixed vertical/left/right equality mask; and separate seam equality. The
  exhaustive suite compares 12,672 bounded one-event cases with both an
  independent scalar oracle and the existing sparse periodic placement oracle,
  and separately checks reachable hole-bearing prefixes. The module is not
  root-exported and adds no RNG, coupled arms, accumulator, trajectory,
  checkpoint/persistence identity, configuration or legacy route, optimized
  kernel, CLI, Easley/Slurm/HPC route, release, or production path.
- A provisional exact event/contact fold under the explicit
  `tetris_ballistic.engine.accumulation` submodule. A keyword-only start
  operation creates a canonical empty-origin `ReferenceEventAccumulator`, and
  a keyword-only fold consumes one already-bound `ReferenceEventPlacement` at
  the exact next ordinal. The frozen record retains independently recertified
  mass, envelope moments, void count, fixed family/orientation/contact/face
  marginals, contact multiplicities, translation-invariant support topology,
  whole-envelope histograms, strict envelope flow, signed contact-gap and
  topology strata, and exact roughness-numerator projections. Every fold
  cross-binds one exactly-once placement measurement to pristine event and
  state authorities and admits the terminal count `2**64` only after consuming
  ordinal `2**64 - 1`. Direct records remain structurally consistent claimed-
  prefix summaries, not authenticated histories or RNG evidence. The module is
  not root-exported and adds no selection, placement, merge, checkpoint/
  persistence identity, serialization, configuration route, multi-event
  driver, optimized path, CLI, Easley/Slurm/HPC route, release, or production
  path; Article S1a-09, M1.2, and overall S2 remain open.
- A provisional reference-only selection-to-placement binder under the
  explicit `tetris_ballistic.engine.binding` submodule. Given one exact sparse
  state and one already-created `TetrominoEventSelection`,
  `place_selected_event` defensively reconstructs both, requires the launch-law
  bound to equal the substrate width, derives and preflights the complete
  positive family--orientation support, and calls `place_one` exactly once.
  The frozen `ReferenceEventPlacement` result retains both the selection and
  placement certificates and recertifies their geometry/family, launch anchor,
  contact endpoint, and pre-state binding. It never selects or replays RNG and
  adds no accumulation, checkpoint/persistence/identity schema, configuration
  route, multi-event trajectory, legacy/optimized route, root export,
  Easley/Slurm/HPC path, release, or production path; Article S1a-09, M1.2,
  and overall S2 remain open.
- A provisional pure reference-placement primitive extractor under the
  explicit `tetris_ballistic.engine.observables` submodule. Given one
  already-created `ReferencePlacement`, `measure_placement` defensively
  reconstructs and recertifies it, then returns a frozen exact companion with
  canonical ordered final-face kinds, fixed-order final/causal face counts,
  the canonical-contact-indexed causal mask, seam-lateral count, unique contact
  endpoints, aggregate-support sites
  and columns, their induced periodic N4 graph/component count and canonical
  cyclic arc, and sparse strict interface-envelope and integer-moment/void
  deltas. The extractor never calls `place_one`, `measure_state`, RNG, or
  selection. It creates no selection-to-placement binding, accumulation,
  checkpoint/persistence/identity schema, configuration route, trajectory,
  legacy/optimized route, root export, Easley/Slurm/HPC path, release, or
  production path; Article S1a-09, M1.2, and S2 remain open.
- A provisional pure reference-state primitive extractor under the explicit
  `tetris_ballistic.engine.observables` submodule. `measure_state` defensively
  reconstructs an exact sparse aggregate and returns a frozen record containing
  the exact width, canonical sparse positive-column envelope, occupied mass,
  height sum, height-square sum, below-envelope volume, and void count. The
  width plus omitted-zero sparse pairs reconstructs the complete envelope
  without width- or height-sized allocation; no float summary, RNG,
  selection, placement call/composition, transition, configuration adapter,
  checkpoint I/O, canonical serialization or digest identity, trajectory,
  legacy route, root export, HPC, release, or production path is added.
- Hardened the provisional periodic-law preflight to validate one canonical
  anchor per positive-weight geometry instead of scanning every substrate
  column. Cyclic translation makes the check complete, while a width-`10**1000`
  regression and an independent all-anchor oracle over the ratified registry
  plus deterministically generated polyominoes pin a width-independent anchor-
  check count. Public validation order, defensive snapshots, and `place_one`'s
  actual-anchor check are unchanged; no selection/placement composition or
  execution route is added.
- A provisional S2.4 fixed-order tetromino event selector under the explicit
  `tetris_ballistic.engine.event` submodule. Immutable complete laws pin the
  five-family, two-contact, and exact 2/8/1/4/4 orientation orders and validate
  every orientation branch before RNG use; the selector pins the four-stream
  schedule and evaluates family, the selected-family orientation, launch, and
  contact exactly once. Returned in-memory evidence retains the address,
  complete law, and all four semantic draws. Persistent vectors record the
  PI-ratified shared raw candidate tape with law-local rejection/acceptance,
  including an unequal-bound event whose accepted rejection ordinals diverge.
  The selector is not root-exported and has no generic conditional DAG,
  control-law factory, placement, configuration/legacy adapter, trajectory,
  serialization identity, optimized path, CLI, Slurm/HPC, or production route.
- Excluded the ignored, worktree-only `tests/test_compute_endpoint_slope.py`
  from automatic sdist discovery so clean source artifacts cannot capture stale
  local test material that is absent from the release authority.
- A provisional S2.3 stateless exact-law layer under the explicit
  `tetris_ballistic.engine.selection` submodule. Immutable weighted records
  preserve explicit outcome order, canonical integer counts, and zero slots;
  immutable declared-stream records preserve exact membership and order; and
  keyword-only one-stream weighted/uniform selectors reject undeclared names
  before calling the S2.2 oracle while retaining the complete selected value
  and accepted-rejection metadata. The layer has no root export, named family/contact law,
  conditional or complete-event selector, configuration/legacy adapter,
  placement composition, trajectory, serialization identity, optimized path,
  Slurm/HPC, or production route. Its persistent vectors distinguish the
  guaranteed shared raw candidate tape from accepted-variate coupling when
  different bounds reject at different ordinals.
- A provisional S2.2 stateless `semantic-philox4x64-10-v1` oracle under the
  explicit `tetris_ballistic.engine.rng` submodule. It implements exact
  128-bit-root/SHA-256 stream-key derivation, the ten-round Random123
  Philox4x64 bijection, lane-zero event/rejection addressing, unbiased integer
  rejection mapping through `2**64`, and canonical integer-count categorical
  selection with accepted-rejection ordinals. Upstream known-answer and
  independently derived end-to-end vectors, recorded in
  `docs/SEMANTIC-RNG-VECTORS.md`, pin byte/word/lane order. The
  module has no package-root export, model/config integration, stateful stream,
  event selector, trajectory, legacy migration, optimized path, Slurm/HPC, or
  production route.
- Immutable typed geometry, ensemble, orientation, contact-rule, and simulation
  configuration records, together with fail-closed adapters for the legacy
  20-by-2 density table. These contracts are additive and do not route legacy
  simulations through a new placement engine.
- A provisional S2.1 deterministic single-event oracle under the explicit
  `tetris_ballistic.engine` submodule. It provides immutable sparse periodic
  states and exact spawn-independent placement for `supported-v1` and N4
  `edge-first-contact-v1`, including the supported counterfactual height,
  early-arrest gap, all directed final N4 aggregate faces (including
  `aggregate-above`) plus floor support, explicit periodic-seam flags, the
  predicate-enabled stopping faces, the counterfactually causal support or
  lateral subset, and defensively validated pre/post states. The explicit
  `validate_periodic_law` preflight checks width and wrapping against the
  complete positive-weight geometry support before a mixed law executes.
  Direct face/result construction fails closed on forged nested state or
  geometry values, noncanonical cells, incomplete or misordered contacts,
  invalid stopping/causal subsets, inconsistent heights/gaps, nonmaximal
  landings, and pre/post-state disagreement.
- The reflected `PieceGeometry.world_coordinates` view and versioned
  `ContactKind.SUPPORTED_V1` / `ContactKind.EDGE_FIRST_CONTACT_V1` identities
  with matching `ContactRule` factories. The reflected view is excluded from
  the existing software-local geometry record, preserving its canonical JSON
  and digest.
- Paired log-subsampling, estimator-sensitivity checks, and common-time
  Tracy-Widom diagnostics for the exp14 analysis workflow.
- Identity-bound managed run artifacts with canonical configuration snapshots,
  checksums, manifests, persistent locks, strict grid declarations, and
  resumable batch/status tooling.
- Fail-closed KPZ analysis artifacts whose manifests bind the exact reduced or
  explicitly selected legacy input inventory, requested cell, estimator
  settings, package source and numerical dependencies, and bootstrap RNG
  policy. Resume and aggregate-only operations now validate a closed requested
  grid; stale, corrupt, mixed-generation, and nonfinite JSON products are not
  reused.
- Strict reduced-input schemas cover both historical exp13 `int32` and current
  reducer `int64` seed/step metadata, plus the official corrected-exp14
  `height_grid` variant. Unsafe archive members, complex legacy observables,
  and decreasing deposited-height clocks are rejected before estimation.

### Reproducibility and compatibility

- Simulation objects now own instance-local `random.Random` and
  `numpy.random.RandomState` streams under the `legacy-dual-stream-v1` contract.
  Valid seeded legacy runs retain their established draw order and deposition
  trajectories, while construction and execution no longer mutate process-global
  RNG state.
- Legacy configuration loading now rejects duplicate YAML keys, malformed or
  nonfinite weights, invalid seeds, and incomplete mappings before simulation.
  Valid legacy configurations retain their established trajectories.
- Existing `Tetris_Ballistic` imports remain available throughout the 2.1
  compatibility series; breaking engine or schema changes remain deferred to a
  separately versioned migration.
- The S2.1 oracle is provisional and is not exported from the package root or
  routed through `SimulationConfig`, `Tetris_Ballistic`, RNG, trajectory,
  Slurm/HPC, optimized-kernel, or legacy-adapter paths. It defines no shared
  serialization schema or cross-repository identity; the older `supported`,
  `first-contact`, and `legacy-sticky-v1` identities retain their established
  values and compatibility behavior. The unversioned `first-contact`
  prototype and both `supported-v1` and `edge-first-contact-v1` have no
  legacy-adapter mapping.
- The slope-analysis CLI now separates `--trace-root` from `--out-dir` and
  requires an input layout. Managed hierarchical simulation outputs must be
  validated and reduced before analysis; historical flat joblibs remain
  available only through the explicit `legacy-flat` compatibility layout.
- Scientific context is mandatory for direct cell analysis and diagnostic
  plots. The managed CLI enforces at least 10 independent runs and 200
  case-bootstrap replicates before publishing identity-bound 95% intervals.
- Large reduced matrices are validated in bounded one-dimensional chunks and
  released immediately after paired log-subsampling, avoiding multi-gigabyte
  validation temporaries on production exp14 cells.
- Tagged builds now require an exact `v<project-version>` match and produce
  validated PEP 517 artifacts without publishing. The former any-tag,
  long-lived-token PyPI path is disabled until the S5 trusted-publishing gate.

## [2.0.0] — 2026-05-16

**Industrial-grade overnight optimization session.**
Net result: **~380× speedup** on the typical workload (L=200, 80K steps:
140s → 0.37s), full pytest CI, Slurm-array HPC entry point, streaming
analysis, ruff lint config, PEP-621 packaging.

### Added

- **`tetris_ballistic._kernel_1x1`** — numba `@njit` kernel for the
  piece_19 (1x1) fast path. Activated automatically when
  `is_1x1_only(config_data)` returns True (i.e., the exp13
  configuration). Mixed-piece configs use the legacy Python dispatch.
  Kill switch: `TETRIS_USE_KERNEL=0` env var.
- **`Tetris_Ballistic.heights`** — incremental "top-envelope" array
  maintained throughout `Simulate()`. Replaces the O(W·H) per-step
  `_TopEnvelop` scan with O(1) lookups + O(piece_cols × H) updates.
- **`Tetris_Ballistic._surface_row(col)`** — O(1) replacement for
  `_ffnz(col)` (Python while-loop).
- **`Tetris_Ballistic._update_heights_for_columns(cols)`** — refresh
  the heights array for a small column slab after a piece placement.
- **`Tetris_Ballistic._sample_cdf`** — precomputed cumulative
  density function for piece sampling. Eliminates per-step
  `np.random.choice` overhead (40% of legacy runtime).
- **`tetris_ballistic.scripts.run_one_cell`** — Slurm-array entry
  point. Takes `--task-id`, decodes via a grid.yaml, runs one cell.
  Idempotent (resumes on existing output).
- **`tetris_ballistic.scripts.run_kpz_analysis`** — streaming KPZ
  analysis runner with `--resume` and `--aggregate-only` flags.
- **`experiments/templates/grid.yaml`** — documented Slurm-array grid spec.
- **`experiments/templates/job_array.slurm`** — Slurm submission script
  targeting Auburn Easley.
- **`pyproject.toml`** — PEP-621 packaging, pytest config, ruff config.
  Optional extras: `[hpc]` (numba), `[dev]` (pytest, pytest-benchmark, ruff).
- **`tests/`** — pytest layout with:
  - 9-cell golden reference (`tests/golden_reference/*.npz`)
  - bit-equality regression suite (`tests/test_simulation_correctness.py`)
  - kernel-vs-legacy regression (`tests/test_kernel_fast_path.py`)
  - streaming-analysis I/O contract (`tests/test_streaming_analysis.py`)
  - Slurm-array entry-point tests (`tests/test_run_one_cell.py`)
- **`.github/workflows/ci.yml`** — pytest + ruff on every push/PR,
  Python 3.10 / 3.11 / 3.12 matrix.

### Changed

- **`Simulate()`** dispatches to the numba fast path when the
  configuration is piece_19-only; falls back to legacy otherwise.
- **`_UpdateStatus(step)`** is now O(W) instead of O(W·H). Same
  semantics, ~100× faster.
- **`Sample_Tetris()`** uses the cached CDF + `np.searchsorted`
  instead of rebuilding the probability vector on every call.

### Performance

| Config | Phase 0 (legacy) | Phase 4b (numba) | Speedup |
|---|---|---|---|
| L=50, 5K steps | 1,239 steps/s | 105,148 steps/s | **85×** |
| L=100, 20K steps | 652 steps/s | 118,940 steps/s | **182×** |
| L=200, 80K steps | 307 steps/s | 116,576 steps/s | **380×** |

Wall-clock for the L=200 / 80K-step config: 140s → 0.37s.

Steps/sec is now flat across L (~115K) rather than dropping with L —
the O(W·H) per-step term has been eliminated.

### Bit-equality

All optimizations preserve trajectory bit-equality with the legacy code
at `atol=1e-12` (FP roundoff of `np.std` vs hand-rolled population-std
formula). The kernel path explicitly preserves the RNG sequence by
pre-generating `positions` and `sticky_flags` arrays from the same RNG
draws the legacy code would consume.

### Migration

- New code: import from `tetris_ballistic` as before. The numba fast
  path is opaque; existing API unchanged.
- Optional HPC dependency: `pip install tetris_ballistic[hpc]` for
  numba. Without it, the legacy path is used (~50× slower for L=200).
- Slurm-array deployment: copy `experiments/templates/{grid,job_array.slurm}`
  to your experiment dir, edit parameters, `sbatch job_array.slurm`.

## [1.2.7] and earlier

Pre-overnight-session releases. Pure-Python+numpy simulation, sweep
parameters via `multiprocessing.Pool`, no Slurm-array support,
no streaming analysis. See git log for details.
