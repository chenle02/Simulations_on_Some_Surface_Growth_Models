# PRE one-cell campaign schema

## Status and authority boundary

This document specifies the provisional Slice 8A held-byte campaign decoder in
`tetris_ballistic.engine.one_cell_campaign`. The only accepted campaign profile
is

```text
tetris-pre-one-cell-campaign@1
```

The module is an explicit-submodule-only, pure in-memory identity layer. It
validates exact configuration bytes and all nine task-map byte strings,
constructs immutable campaign/task records, inverts the frozen task maps, and
derives one task's scientific-identity bytes. It performs no filesystem I/O,
Numba or checkpoint import, numerical evolution, signal handling, runner or
scheduler dispatch, Easley contact, simulation acquisition, output promotion,
analysis, or scientific inference. It is not exported from either package
root.

Slice 8A does not create the final campaign. In particular, this repository
contains no final `campaign.yaml`, bootstrap matrix, transported wheel,
deployment lock, branch-decision record, task directory, or launch authority.
The synthetic test fixtures certify the generic codec only. Common-correctness
item 6 therefore remains open.

The frozen protocol authority is exactly:

| Field | Value |
|---|---|
| Article commit | `85404aee4dab7ade81c6893fac9f34aeaddf50dd` |
| path | `PRE-DISCOVERY-PROTOCOL.md` |
| Git blob | `b7b654bb8d2809c409ce6ca24eb21d3afebf7885` |
| SHA-256 | `ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358` |
| size | 44,883 bytes |

The Article protocol, software source, transported wheel, base campaign, and
deployment certificate are separate acyclic authorities:

```text
PROTO + pushed SOURCE + exact WHEEL ---> base CAMPAIGN ---> DEPLOYMENT
```

No member names its own digest or future containing commit. The raw campaign
contains neither a selected P1 outcome branch nor operational launch data.

## Canonical configuration bytes

The `.yaml` campaign member is intentionally a strict canonical-JSON subset,
not general YAML. `configuration_bytes` must be exact built-in `bytes`, contain
1 through 1,048,576 bytes, and equal

```python
json.dumps(
    decoded,
    allow_nan=False,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8") + b"\n"
```

after duplicate-aware strict decoding. The parser admits only JSON objects
with string keys, arrays, strings, exact integers, exact Booleans, and `null`.
It rejects duplicate or unknown keys, floating-point and nonfinite values,
noncanonical integer spelling, a BOM, invalid UTF-8, alternate escaping or
whitespace, missing or extra terminal newlines, CRLF, aliases, anchors, merges,
tags, timestamps, and Boolean-as-integer confusion. Integer tokens are at most
40 characters. Decoded input is bounded to depth 24 and 40,000 total values
before semantic construction.

The exact top-level object has the following sections. Every nested object also
has an exact key set; omission and extension both fail closed.

```text
profile
protocol
model
execution
bootstrap_matrices
task_maps
horizon_branches
checkpoint_vectors
```

The protocol, model, and execution sections are value-for-value frozen records,
not extensible metadata. The model record binds:

- clean model `one-cell-rd-bd-periodic-v1`;
- boundary-law order `periodic-v1`,
  `hard-wall-legacy-asymmetric-v1`, then
  `hard-wall-reflection-symmetric-v1`;
- zero initial height and unsigned-128 numerical root encoding;
- RNG `semantic-philox4x64-10-v1`, coupling group
  `pre-one-cell-discovery-v1`, stream order `launch, contact`, zero-based event
  and rejection counter fields, and contact denominator 100;
- threshold schedules `primary=(0,1,2,5,10,25,50,100)`,
  `b1=(0,5,50,100)`, `b2-full=(5,50,90,95,98,99)`, and
  `b2-high=(90,95,98,99)`.

The execution record binds the exact inventories below, whole-root resampling,
512 checkpoints, 16 snapshots, recovery cadence `2**20`, final-manifest-only
completion, retained primitive names, integer product bounds, output caps, and
exclusive authority of the protocol's locked analysis, admission, Boolean
truth table, release gate, and stop rule.

## Profiles and exact immutable records

The auxiliary profiles are:

| Object | Profile |
|---|---|
| bootstrap descriptor | `tetris-pre-one-cell-bootstrap-matrix@1` |
| task-map descriptor | `tetris-pre-one-cell-task-map@1` |
| task-map row | `tetris-pre-one-cell-task-row@1` |
| horizon branch | `tetris-pre-one-cell-horizon-branch@1` |
| scientific identity | `tetris-pre-one-cell-scientific-identity@1` |
| checkpoint vector digest preimage | `tetris-pre-one-cell-checkpoint-vector@1` |
| snapshot vector digest preimage | `tetris-pre-one-cell-snapshot-vector@1` |

All public records are frozen, slotted, keyword-only dataclasses. Their field
order is:

```text
OneCellBootstrapMatrixIdentity:
  cohort_id
  profile
  member_path
  shape
  seed
  generator
  bit_generator
  numpy_version
  distribution
  dtype
  byte_order
  order
  size_bytes
  sha256

OneCellTaskMapIdentity:
  task_map_id
  profile
  member_path
  wave
  role
  horizon_branch_id
  task_count
  size_bytes
  sha256

OneCellHorizonBranch:
  branch_id
  profile
  l_star
  confirmation_required
  confirmation_terminal_event_count
  p1_terminal_event_counts
  p1_task_map_id

OneCellCampaignAuthority:
  configuration_bytes
  configuration_sha256
  profile
  protocol_commit
  protocol_path
  protocol_blob
  protocol_sha256
  protocol_size_bytes
  bootstrap_matrices
  task_maps
  horizon_branches
  checkpoint_terminals
  task_map_members

OneCellCampaignTask:
  task_map_id
  task_map_sha256
  wave
  role
  included_in_inference
  task_index
  horizon_branch_id
  boundary_law
  width
  root_seed
  root_offset
  threshold_schedule_id
  threshold_schedule
  terminal_event_count
  checkpoint_event_counts
  checkpoint_vector_sha256
  snapshot_checkpoint_indices
  snapshot_event_counts
  snapshot_vector_sha256
  bootstrap_cohort_id
  bootstrap_population_index
```

Public construction defensively validates the complete frozen relation; a
record with individually plausible but cross-inconsistent fields is rejected.
Caller byte strings and tuples are retained only after exact built-in-type and
content validation and are never mutated.

The exact keyword-only operations are:

```python
load_one_cell_campaign(
    *,
    configuration_bytes: bytes,
    task_map_members: tuple[tuple[str, bytes], ...],
) -> OneCellCampaignAuthority

encode_one_cell_campaign_task_index(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    boundary_law: OneCellBoundaryLaw,
    width: int,
    root_seed: int,
) -> int

decode_one_cell_campaign_task(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    task_index: int,
) -> OneCellCampaignTask

explain_one_cell_campaign_task(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    task_index: int,
    deployment_lock_sha256: str,
    software_commit: str,
    wheel_sha256: str,
    branch_decision_sha256: str | None = None,
) -> bytes
```

Loading preserves the exact raw configuration and ordered member bytes. Every
later operation revalidates the exact campaign authority before use. A small
bounded private cache may memoize validation by immutable byte value. Its
decoded record is paired with a deeply immutable primitive seal, exact-type
checked on every access, and deep-cloned before use; private cache or class
mutation therefore fails closed and no mutable decoded JSON is exposed.

## Bootstrap descriptors

`bootstrap_matrices` contains exactly four descriptors in order `p0`, `p1`,
`b1`, `b2`:

| Cohort | Member | Shape | Seed | Size |
|---|---|---:|---:|---:|
| `p0` | `bootstrap/p0.u16le` | `(10000,16)` | `2026071500` | 320,000 |
| `p1` | `bootstrap/p1.u16le` | `(10000,96)` | `2026071501` | 1,920,000 |
| `b1` | `bootstrap/b1.u16le` | `(10000,32)` | `2026071502` | 640,000 |
| `b2` | `bootstrap/b2.u16le` | `(10000,100)` | `2026071503` | 2,000,000 |

Every descriptor uses generator `numpy.random.Generator`, bit generator
`PCG64DXSM`, distribution `integers-half-open-one-call-v1`, dtype `uint16`,
little byte order, and C order. `numpy_version` is one exact release identity;
the final version and exact 64-lowercase-hex matrix digest are frozen only in
Slice 8C. Matrix bytes are generated row-major by one fresh

```python
Generator(PCG64DXSM(seed)).integers(
    0, n, size=(10000, n), dtype=uint16
)
```

call. Generator reuse, chunking, transpose, `default_rng`, and an after-the-fact
cast are different authorities.

The bootstrap population index is the zero-based root offset for P0, B1, and
B2 and the literal root for P1 (identical to its offset because P1 starts at
zero). F0 and the conditional P0 confirmation use exact Python `None` for both
bootstrap fields. The confirmation root is not a seventeenth P0 column.

## Canonical task-map JSONL

`task_map_members` supplies all nine members as exact `(member_path, bytes)`
pairs in descriptor order. A member is nonempty and no larger than 4 MiB. Each
line including LF is no larger than 4,096 bytes. The member has one canonical
JSON object per task, no blank lines or carriage returns, and exactly one LF
after every row including the last. Its size and SHA-256 must equal its
descriptor before rows are trusted.

Each row contains exactly:

```text
boundary_law
profile
root_offset
root_seed
task_index
terminal_event_count
threshold_schedule_id
width
```

The row profile is `tetris-pre-one-cell-task-row@1`. Base rows contain only
primitive task facts. They never cite configuration, manifest, deployment
lock, campaign, branch-decision, admission, launch, or derived scientific-
identity digests. This preserves the generation order

```text
task maps and bootstrap matrices -> raw campaign -> deployment lock
-> per-task scientific identity.
```

Safe member paths are relative POSIX paths matching lowercase letters, digits,
dot, underscore, hyphen, and slash with no empty component. Total length is at
most 255 characters and each component at most 80. Absolute paths, dot
components, backslashes, and traversal are outside the grammar.

## Frozen maps and inversion

Order is root fastest, width next, and boundary slowest:

| Map | Boundaries | Widths | Root start/count | Tasks | Schedule |
|---|---|---|---:|---:|---|
| `f0` | legacy, corrected | 50, 500 | 3,100,000 / 2 | 8 | B2-full below 400; B2-high at 500 |
| `p0-initial` | periodic | 64, 256, 1024 | 1,000,000 / 16 | 48 | primary |
| `p0-confirmation` | periodic | 1024 | 1,000,016 / 1 | 1 | primary |
| each P1 map | periodic | 64, 128, 256, 512, 1024 | 0 / 96 | 480 | primary |
| `b1` | legacy, corrected, periodic | 32, 64, 128, 256 | 2,000,000 / 32 | 384 | B1 |
| `b2` | legacy, corrected | 50, 80, 100, 150, 200, 250, 300, 400, 500 | 3,000,000 / 100 | 1,800 | B2-full through 300; B2-high at 400/500 |

The nine map IDs and members are `f0`, `p0-initial`, `p0-confirmation`,
`p1-no-l-star`, `p1-l-star-64`, `p1-l-star-256`, `p1-l-star-1024`, `b1`,
and `b2` under `task-maps/<ID>.jsonl`.

The zero-based index formulas are:

```text
P0 = width_index*16 + root_offset
F0 = ((boundary_index*2)+width_index)*2 + root_offset
P1 = width_index*96 + root_offset
B1 = ((boundary_index*4)+width_index)*32 + root_offset
B2 = ((boundary_index*9)+width_index)*100 + root_offset
confirmation = 0
```

Encode requires the exact map, exact `OneCellBoundaryLaw`, declared width, and
literal root seed. Decode requires the exact map and an index in
`[0, task_count)`. Both directions are algebraic and must invert one another at
every row, axis seam, first index, and last index.

Roles and inference eligibility are exact: F0 is `excluded-forensic-canary`,
initial P0 is `excluded-horizon-pilot`, confirmation is
`excluded-conditional-confirmation`, and all three are excluded from
inference. P1 is `clean-primary`, B1 is `boundary-forensic`, and B2 is
`historical-grid-correction`; those three are inferential inventories.

## Horizons and one-shot branch

The fixed base horizons are:

```text
L=32:17,378; L=64:98,304; L=128:556,092; L=256:3,145,728;
L=512:17,794,925; L=1024:100,663,296.
```

The doubled P1 horizons are:

```text
L=64:196,608; L=128:1,112,184; L=256:6,291,456;
L=512:35,589,850; L=1024:201,326,592.
```

The historical F0/B2 horizons are:

```text
L=50:55,000; L=80:172,800; L=100:300,000; L=150:832,500;
L=200:1,720,000; L=250:3,000,000; L=300:4,680,000;
L=400:9,600,000; L=500:17,000,000.
```

`horizon_branches` contains exactly, in order:

1. `p1-no-l-star`: no doubling, `l_star=null`, no confirmation;
2. `p1-l-star-64`: every P1 width doubles;
3. `p1-l-star-256`: widths 256, 512, and 1024 double;
4. `p1-l-star-1024`: only width 1024 doubles.

Each triggered branch requires the one periodic primary confirmation at
`L=1024`, root `1,000,016`, terminal `201,326,592`. The confirmation cannot
change the branch and no second doubling exists. The four task-map digests are
frozen before P0; base campaign bytes select none of them.

## Literal checkpoint and snapshot vectors

`checkpoint_vectors` contains exactly 20 records in the frozen terminal order:

```text
17,378; 98,304; 556,092; 3,145,728; 17,794,925; 100,663,296;
196,608; 1,112,184; 6,291,456; 35,589,850; 201,326,592;
55,000; 172,800; 300,000; 832,500; 1,720,000; 3,000,000;
4,680,000; 9,600,000; 17,000,000.
```

Every record contains the terminal, all 512 strictly increasing literal event
counts from 1 through that terminal, the checkpoint digest, the 16 fixed
snapshot indices

```text
(0,34,68,102,136,170,204,238,273,307,341,375,409,443,477,511),
```

the 16 selected literal event counts, and the snapshot digest. Digest
preimages are compact sorted-key canonical JSON without LF under their
respective vector profiles. The loader recomputes both hashes and compares them
with the 20 Slice 7 known-answer pairs; a formula or digest without the literal
vectors is insufficient.

## Scientific identity and external join

The base campaign alone is not executable authority. Per-task identity also
requires externally frozen source, wheel, and deployment-lock facts, and P1 or
conditional confirmation additionally requires the immutable branch-decision
digest. These authorities are inputs to the explain operation and are not
written back into configuration bytes or task-map rows.

Scientific-identity bytes are compact sorted-key canonical JSON under
`tetris-pre-one-cell-scientific-identity@1`, with no trailing LF. They bind the
exact raw configuration digest, task-map digest, decoded task, selected literal
checkpoint/snapshot vectors and hashes, bootstrap descriptor and population
index when applicable, pushed 40-hex source commit, exact wheel digest, and
deployment-lock digest. Host, queue, partition, concurrency, attempt, job ID,
temporary path, log path, and scheduler metadata are operational and absent.

P1 and conditional confirmation fail closed without the applicable branch
join. F0, initial P0, B1, and B2 are branch-independent and reject an
inapplicable branch input. The resulting bytes fit the Slice 7 1 MiB opaque
scientific-identity bound and may later be supplied unchanged to
`OneCellCheckpointBinding`; Slice 8A itself never imports that module or starts
a task.

The exact outer envelope is

```text
profile
record
sha256
```

where `sha256` hashes the compact no-LF canonical bytes of `record` alone. The
inner record has exactly:

```text
bootstrap
checkpoint_plan
configuration_sha256
deployment_lock_sha256
horizon_plan
protocol
software_commit
task
task_map
wheel_sha256
```

`task` contains boundary law, inference eligibility, role, root offset, root
seed, task index, terminal, literal threshold schedule and ID, wave, and width.
`task_map` contains member path, digest, byte size, and map ID.
`checkpoint_plan` contains both complete literal vectors and hashes. A cohort
bootstrap object contains its complete descriptor plus population index;
noncohort tasks use exactly `{"applicable":false}`.

For a P1 or `p0-confirmation` task, `horizon_plan` has kind
`branch-decision`, plan ID, and the required branch-decision digest. For F0,
initial P0, B1, and B2 it has kind `fixed` and plan ID only. The source commit
must be exactly 40 lowercase hexadecimal characters; wheel, lock, and branch
digests must be exactly 64 lowercase hexadecimal characters.

## Parser and failure boundary

The campaign decoder is memory-only. It validates all descriptors, all nine
complete members, every row and cross-reference, every literal vector, and
all counts before returning an authority. A descriptor/member mismatch,
noncanonical stored byte, malformed or unknown profile, wrong fixed value,
wrong ordering, duplicate identity, or failed task/vector cross-binding raises
`OneCellCampaignValidationError`, a `RuntimeError` subclass. Nonexact public
argument types raise `TypeError`; invalid map IDs, indices, or exact record
values raise `ValueError`. Private captured-authority corruption is an
`AssertionError` boundary.

The integrity seal is a fail-closed pure-Python corruption detector, not an
authentication or sandbox boundary. It assumes that the genuine outermost
public callable or runtime-sealed record-constructor entry executes. Replacing
that entry's own code, closure cells, or metaclass call before its first
instruction, or directly invoking closure-internal objects obtained through
introspection, is outside the enforceable in-process boundary; all dependencies
reached after genuine entry are captured and checked before use.

SHA-256 detects accidental byte corruption and joins immutable authorities; it
is not authentication. Deployment ownership, clone parity, environment
identity, wheel installation, scheduler exclusion, and empty production roots
remain Slice 8C/8D gates.

## Synthetic certification boundary

Slice 8A tests may construct complete protocol-shaped campaign and JSONL bytes
in memory, using synthetic lowercase hashes for still-future matrices, source,
wheel, lock, and branch authorities. They may exhaustively encode/decode every
row and independently generate all 20 schedule vectors. Such bytes are test
fixtures only: they are not stored as a final campaign member and authorize no
Easley use or acquisition.

The first future authoritative action is Slice 8C generation after Slice 8B
has frozen and pushed `SOURCE` and built one exact transported `WHEEL`. Slice
8D may then validate those held bytes in a fresh campaign-isolated Easley clone
without scheduler contact or numerical execution. Only a later, separately
approved admission and launch artifact can authorize any F0 or P0 task.
