# PRE one-cell compiled trajectory conformance receipt and index

This document freezes the Slice 6 compiled-conformance boundary for
`tetris_ballistic.engine.one_cell_trajectory_compiled`. It is an evidence
index, not a replacement for the scalar trajectory, compiled RNG, coupling,
boundary, or semantic-RNG vector authorities. A conflict is resolved in favor
of those pinned authorities and, for scientific semantics, the frozen PRE
protocol.

Slice 6 may close only common-correctness item 4. This receipt does not by
itself assert that source, package, review, CI, or repository-parity gates have
passed, and it does not authorize scientific acquisition.

## Pinned authorities

| Authority | Frozen identity |
|---|---|
| PRE scientific protocol | Article commit `85404aee4dab7ade81c6893fac9f34aeaddf50dd`; `PRE-DISCOVERY-PROTOCOL.md` SHA-256 `ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358` |
| Slice 6 implementation freeze | Coordinator roadmap commit `7039bbc`; software parent `434419680958d07266847f44b70dee33f16b55ec` |
| Compiled RNG implementation | `tetris_ballistic/engine/rng_compiled.py` SHA-256 `22dc059d37b04a2dd6099eaef5ba82e0ac218f726c0f4d19b7e2ea1398ebb560` |
| Scalar RNG and key derivation | `tetris_ballistic/engine/rng.py` SHA-256 `19dca94ea97fae16278b198505200a5be27d80821dd54c8e454f135390888489` |
| Scalar trajectory regression preimage | `tetris_ballistic/engine/one_cell_trajectory.py` SHA-256 `7d4f71c9d4728f193b116eb1a216bb3e3987725e1b006471947f8822751c16b2` |
| Scalar trajectory test regression preimage | `tests/test_one_cell_trajectory.py` SHA-256 `9d64dbe550539e90b36592ff66cef186959187e01325448778a85435450a868c` |
| Scalar trajectory vector regression preimage | `docs/PRE-ONE-CELL-SCALAR-TRAJECTORY-VECTORS.md` SHA-256 `f143990e98efdbc71d5fd8764de2626876c47b61000fdbefba55e5841a2b4072` |
| Three-boundary transition | `tetris_ballistic/engine/one_cell_boundary.py` SHA-256 `2bc7e184476e46bae25b7878847000664f50e1140a009c7917a802e6022089fb` |
| Common-draw selector | `tetris_ballistic/engine/one_cell_coupling.py` SHA-256 `ebf8a2ada59cb176319eab167bef6502811c6d696f93ba60d429921ed26ba6a7` |
| Compiled RNG receipt | `docs/PRE-ONE-CELL-COMPILED-RNG-VECTORS.md` SHA-256 `51900866902cba527b981ec9335bf5112482e91ef6d2dec68ff2fb22ccdffd38` |
| Coupling vectors | `docs/PRE-ONE-CELL-COUPLING-VECTORS.md` SHA-256 `74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3` |
| Boundary vectors | `docs/PRE-ONE-CELL-BOUNDARY-VECTORS.md` SHA-256 `d70374dc2239fc0c5f44781ef49ee9e0d9cce2ca6e16050678a0057282eee23f` |
| Semantic RNG vectors | `docs/SEMANTIC-RNG-VECTORS.md` SHA-256 `913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34` |

The three preimage digests protect the already-certified Slice 5 primary
behavior. The recertified scalar implementation and scalar vector document are
expected to change additively for the additional schedules; the preimage
digests are not claims that those files remain byte-identical.

## Explicit API and schedule boundary

The compiled module has exactly this public surface:

```python
advance_one_cell_compiled_chunk(
    *,
    trajectory: OneCellScalarTrajectory,
    stop_event_ordinal: int,
) -> OneCellScalarTrajectory
```

Its `__all__` contains exactly `advance_one_cell_compiled_chunk`. The operation
is keyword-only and is not re-exported from `tetris_ballistic` or
`tetris_ballistic.engine`. There is no compiled start operation and no
compiled public record. Initialization uses the scalar start operation; input
and output are the frozen scalar trajectory and arm records, so complete
backend agreement is ordinary record equality.

Both backends admit exactly four evolution schedules:

```text
primary = (0, 1, 2, 5, 10, 25, 50, 100)
B1      = (0, 5, 50, 100)
B2-full = (5, 50, 90, 95, 98, 99)
B2-high = (90, 95, 98, 99)
```

These tuples are evolution schedules, not campaign identities. P0/P1 use
primary; B1 uses B1; B2 widths through 300 and the width-50 F0 canaries use
B2-full; and B2 widths 400/500 and the width-500 F0 canaries use B2-high.
Width-to-schedule dispatch, campaign applicability, and artifact identity are
deferred to Slice 8.

The compiled operation advances the contiguous half-open interval
`[trajectory.event_count, stop_event_ordinal)`. An empty interval defensively
reconstructs an equal record without deriving keys, allocating compiled state,
calling RNG, or dispatching a kernel. Directly constructed records retain the
scalar API's structural-only provenance caveat; the compiled backend does not
authenticate a forged past Philox history.

## Host and compiled boundary

Before allocation, key derivation, or compiled mutation, the host
reconstructs the complete scalar record and checks the stop in Python
arbitrary precision. A nonempty chunk derives exactly two keys, once each and
in this order:

```text
(root, "pre-one-cell-discovery-v1", "launch")
(root, "pre-one-cell-discovery-v1", "contact")
```

SHA-256 derivation and immutable result construction are host operations. All
RNG mapping, recurrence, and accumulator arithmetic are Numba nopython work.
The numerical path uses the captured Slice 4 bounded mapper and unsigned
64-by-64 multiplier; it calls no scalar Philox, raw-word, bounded-mapping,
selector, boundary-transition, trajectory, or accumulator helper.

At zero-based event ordinal `e`, launch uses bound `width` and contact uses
bound 100 at counter `(e, rejection, 0, 0)`. Only the rejected draw's
rejection lane advances. The accepted launch and contact are shared by every
arm, and the decision remains exactly `contact < threshold`. Boundary law,
schedule, and threshold never enter an RNG address.

The host copies records into fresh, native-endian, C-contiguous unsigned-64
state with these private layouts:

```text
heights[arm_count, width]
scalars[arm_count, 8] = (S, V, endpoint, trigger, maximum_gap,
                         seam_scratch, Q_high, Q_low)
causal_counts[arm_count, 4]
causal_gap_sums[arm_count, 4]
equality_counts[arm_count, 2, 8]
histogram[(arm_index, gap)] = count
```

The sparse histogram is one nopython typed dictionary. No dense horizon-sized
histogram, fixed-capacity map, Python object map, threshold array, per-event
tape, or caller-mutable compiled record is public. A private literal schedule
code determines the exact four-, six-, or eight-arm threshold ladder. The
host and kernel both reject schedule/code/shape mismatches. The hard-wall seam
scratch word must stay zero and reconstructs to public `None`.

The kernel implements all three certified recurrences and folds every scalar
record field: heights, `S`, `Q`, `V`, endpoint and positive-gap counts,
maximum gap, causal counts and gap sums, both equality-mask rows, sparse gap
histogram, and periodic seam equality. Endpoint selection, positive-gap
triggering, causal eligibility, and physical height equality remain distinct.
Equality uses mask `vertical + 2*left + 4*right`; periodic seam equality also
includes nonsticky and zero-gap events.

## Packed-Q and unsigned arithmetic evidence

Packed words are private comparison projections, not new public fields. High
word comes first:

```text
Q = (Q_high << 64) | Q_low
```

`(0,0)` is exact zero, not a sentinel. Before dispatch, arbitrary precision
proves

```text
0 <= current N <= stop < 2**64
width * stop < 2**64
width * stop**2 < 2**128.
```

The kernel obtains exact high/low words of the old and new height squares,
subtracts with explicit borrow, and adds the nonnegative delta with explicit
carry and overflow checks. Other retained state is unsigned-64 and every
increment is checked. No scientific operation uses signed arithmetic,
floating point, fast math, object mode, or silent wrap; signed `intp` is
limited to indexing and control flow.

The fixed packed-add rows are

```text
(0,0)       + (0,1) = (0,1)
(0,MAX)     + (0,1) = (1,0)
(5,MAX-2)   + (7,3) = (13,0)
(MAX-1,MAX) + (0,1) = (MAX,0)
(MAX,MAX)   + (0,1) = overflow
```

A constructed selected-event witness crosses a column from `2**32-1` to
`2**32`, moving Q words from `(0,18446744065119617025)` to `(1,0)` and then
to `(1,8589934593)`. The nonzero-high/nonzero-low witness is
`(3458764513820540929,9223372036854775811)`. Multiplication, subtraction
borrow, addition carry, high-word overflow, counter and histogram overflow,
and rejection exhaustion are all separately exercised. A failing kernel may
partially change only its fresh private buffers; no caller state is mutated and
no result is published.

## Normative vectors and three-way oracle

Every normative comparison is

```text
independent primitive-tuple oracle
             ==
certified scalar trajectory
             ==
compiled full-record result.
```

The independent oracle owns literal copies of all four schedules and directly
implements SHA-256 derivation, arbitrary-precision Philox and rejection
mapping, both streams, all three recurrences, and every accumulator fold. It
imports no production RNG, selector, transition, scalar/compiled trajectory,
accumulator, or observable helper. Comparisons include all public fields, both
private Q words, histogram order, seam applicability, and roughness numerator.
Partitioned runs compare at every returned stop.

The scalar vector authority retains all 48 primary root-zero, width-three rows
value-for-value and adds 36 B2-full rows over three laws, six thresholds, and
`N=7,50`, for 84 schedule-indexed complete rows. B1 is an exact projection of
primary, B2-high is an exact projection of B2-full, and thresholds 5/50 agree
between primary and B2-full. Every row replays through the compiled backend;
its packed Q projection is `(0,Q)`.

The threshold-five `N=50` boundary witnesses remain

| Law | Heights | `S/Q/V` |
|---|---|---|
| periodic | `(19,19,19)` | `57/1083/7` |
| legacy hard wall | `(19,18,18)` | `55/1009/5` |
| corrected hard wall | `(19,19,18)` | `56/1046/6` |

For B2 at `N=50`, periodic thresholds 90/95/98/99 have heights
`(23,23,22)`, `S/Q/V=68/1542/18`, and endpoint totals 44/46/49/49. Either
hard wall has heights `(21,21,20)`, `62/1282/12`, and the same endpoint
totals. Strict contact neighbors are `4,5,49,50,89,90,94,95,97,98,99`; in
particular contact 98 selects threshold 99, while contact 99 selects no B2
arm. The root-zero accepted-at-ordinal-zero contact witnesses are

```text
(4,55,0bfb25192b17f92e)    (5,24,0f3558266a1ecb4c)
(49,45,7daaf3e15f89f819)  (50,216,81e81f92c924dd8f)
(89,67,e3f955d77cf51347)  (90,70,e85457065d119d2a)
(94,221,f1f54e9cab7b23d6) (95,18,f5c22f4c931abfb3)
(97,7,fa673b3a532b5051)   (98,135,fb2f98475c7d4d5e)
(99,43,fed165ae9ecf81ff)
```

## Finite certification envelope

The exhaustive and differential certificate contains:

- 14,400 one-event trajectories and 79,200 arm transitions over all four
  schedules, all laws, widths 3--5, every launch, and all 100 contacts;
- 3,564 two-event trajectories and 44,388 arm transitions, plus 67,878
  declared-slow three-event trajectories and 1,314,630 arm transitions, using
  decision representatives primary `(0,1,2,5,10,25,50)`, B1 `(0,5,50)`,
  B2-full `(0,5,50,90,95,98,99)`, and B2-high
  `(0,90,95,98,99)`;
- 768 real-RNG trajectories and 270,336 arm transitions for roots 0--15,
  widths 3, 4, 5, and 32, every law and schedule, through 64 events;
- 1,440 trajectories and 253,440 arm transitions across eight boundary roots,
  `(0,95,1000015,2000031,3000099,2**64-1,2**64,2**128-1)`, all 15 declared
  widths `(32,50,64,80,100,128,150,200,250,256,300,400,500,512,1024)`,
  every law and schedule, through 32 events;
- the exact Article B2 matrix, 1,800 trajectories and 320,000 arm transitions,
  for roots `3000000..3000099`, both hard-wall laws, B2-full at widths
  `(50,80,100,150,200,250,300)`, and B2-high at `(400,500)`; plus the exact
  F0 matrix, 8 trajectories and 1,280 arm transitions, for roots
  `3100000,3100001`, both hard-wall laws, width 50 with B2-full, and width
  500 with B2-high, for a combined 1,808 trajectories and 321,280 arm
  transitions; and
- 768 partitioned executions and 1,085,568 arm transitions through 257 events
  for roots zero and `2**128-1`, widths 3, 32, 256, and 1024, every law and
  schedule, and uninterrupted, unit, Fibonacci, boundary-clustered, and four
  deterministic irregular partition families with repeated empty chunks.

All 64 partitions of `[0,7)` and every split, unit partition, and repeated
empty chunk of `[0,50)` are also checked for every law and schedule. Hostile
coverage includes nonexact scalar/container types, malformed and cross-law
records, every undeclared or mixed schedule, invalid private array/map state,
authority rebinding, hash-seed stability, dependency and export guards,
stop/product bounds, malformed compiled results, and caller immutability.

## Forced-rejection composition

Natural launch rejection is too rare at feasible widths to search for as a
trajectory fixture. Tests instead specialize the same private nopython chunk
body with a test-only uniform-compatible dispatcher. That dispatcher alone
feeds candidate words `(2**64-1, 0)` through the certified Slice 4 prepare/map
helpers, accepting zero at rejection ordinal one for bounds three and 100.
There is no public injection flag, scalar monkeypatch, or Python `.py_func`
claim.

With launch rejection at event one and contact rejection at event two, the
accepted tape is exactly

```text
((1,79),(0,9),(1,0),(0,2),(0,92)).
```

Endpoint totals are primary `(0,1,1,2,3,3,3,5)`, B1 `(0,2,3,5)`, B2-full
`(2,3,4,5,5,5)`, and B2-high `(4,5,5,5)`. The physical event count remains
five, the other stream and later event addresses remain fixed, and uninterrupted
execution equals partitions `(1,2,2,3,5)`. The dispatcher audits exact
`(stream,event,rejection)` calls. The suite separately replays the Slice 4
natural rejection chains accepted at ordinals one, two, and five, stream and
future-event isolation, and fail-before-wrap exhaustion.

## Optional dependency and scope boundary

The existing `hpc` extra supplies `numba>=0.58`. Package-root and engine-root
imports do not import Numba. Importing the explicit compiled-trajectory
submodule without a compatible Numba installation raises a clear `ImportError`
that names `tetris_ballistic.engine.one_cell_trajectory_compiled` and the
`tetris_ballistic[hpc]` extra. Every numerical dispatcher demonstrates only
the intended native unsigned nopython signatures with `cache=False` and
`fastmath=False`.

Slice 6 adds no packed public record, persistence or digest identity,
checkpoint, resume, generation, manifest, lock, configuration/YAML or campaign
identity, 512/16 schedule, `2**20` cadence, runner, CLI, legacy dispatch,
benchmark or performance claim, GPU/CUDA, scheduler integration,
Slurm/Easley/HPC submission, pilot, canary, simulation output, analysis,
release, or scientific acquisition. Common-correctness items 5--6 remain open
even after item 4 closes.
