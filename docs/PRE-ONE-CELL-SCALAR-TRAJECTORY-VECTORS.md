# PRE one-cell scalar trajectory vectors

These vectors are normative complete-prefix snapshots for the provisional
scalar trajectory in `tetris_ballistic.engine.one_cell_trajectory`. They pin
the common-draw eight-arm fold across all three certified boundary laws. They
do not replace the separately certified selection or boundary authorities and
do not create a compiled, persistent, configured, or production execution
route.

Every row below is also asserted against a separately written primitive-tuple
oracle by the package certification suite.

## Frozen authorities

The Slice 5 implementation contract is frozen by
`tetris-kpz-data/docs/PRE-ONE-CELL-ROADMAP.md` at commit
`fc727ccaaa3d925090e1f2fd014ecf715a339868`, from software parent
`56e228a3596c10713fcd9cf838315f1dd785fef1`. The governing private protocol is
`PRE-DISCOVERY-PROTOCOL.md` at commit
`85404aee4dab7ade81c6893fac9f34aeaddf50dd`, full-file SHA-256
`ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358`.

The inputs to this trajectory certificate are pinned exactly:

| Authority | SHA-256 |
|---|---|
| `tetris_ballistic/engine/one_cell_coupling.py` | `ebf8a2ada59cb176319eab167bef6502811c6d696f93ba60d429921ed26ba6a7` |
| `tetris_ballistic/engine/one_cell_boundary.py` | `2bc7e184476e46bae25b7878847000664f50e1140a009c7917a802e6022089fb` |
| `docs/PRE-ONE-CELL-COUPLING-VECTORS.md` | `74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3` |
| `docs/PRE-ONE-CELL-BOUNDARY-VECTORS.md` | `d70374dc2239fc0c5f44781ef49ee9e0d9cce2ca6e16050678a0057282eee23f` |
| `docs/SEMANTIC-RNG-VECTORS.md` | `913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34` |
| `tetris_ballistic/engine/rng.py` | `19dca94ea97fae16278b198505200a5be27d80821dd54c8e454f135390888489` |

## Snapshot notation

All vectors use numerical root seed zero, width three, zero-based event
ordinals, and threshold order

```text
(0, 1, 2, 5, 10, 25, 50, 100).
```

Each arm row has this exact shape:

```text
A(
  threshold,
  heights,
  (S, Q, R, V),
  (endpoint_selected_count, positive_gap_trigger_count, gap_sum, maximum_gap),
  causal_counts,
  causal_gap_sums,
  equality_counts_endpoint_false,
  equality_counts_endpoint_true,
  gap_histogram,
  seam_equality_count,
)
```

Here `R = width*Q - S*S` is the derived exact roughness numerator. Causal
tuples are ordered `(none, left, right, both)`. Each equality tuple is indexed
by masks zero through seven. The boundary law and common event count `N` are
given by the enclosing snapshot header; all other retained accumulator fields
appear literally in each row. `None` means that seam equality is inapplicable
under a hard wall, not physical false or numeric zero.

At `N=0`, all eight arms have distinct all-zero height tuples, empty
histograms, zero scalar and tuple counts, and `(S,Q,R,V)=(0,0,0,0)`.
The periodic seam count is zero; either hard-wall seam count is `None`.

## Common root-zero event tape

The independent oracle implements the SHA-256 domain and length-prefix
encoding, arbitrary-precision Philox4x64-10, and exact quotient/rejection
mapping directly. It obtains the already-pinned stream keys

```text
launch:  81ba8e755ea8a360 f829a74d482f4ebb
contact: 6c00b0c4102c9848 4373aa5df7ef12bd
```

and this width-three `(launch, contact)` prefix. Every shown draw accepts at
rejection ordinal zero.

```text
 0.. 9: (1,79) (1, 9) (1,63) (0, 2) (0,92) (1,17) (2,24) (0,97) (2, 3) (1,48)
10..19: (2,81) (1,97) (0,75) (1, 3) (2,81) (2, 2) (0,58) (1,80) (1,95) (0,45)
20..29: (2,65) (2,26) (0,27) (2, 0) (2, 5) (1,81) (0,75) (0,41) (1,16) (1,21)
30..39: (0,58) (0,74) (2,26) (1,81) (0,23) (0,67) (2,13) (2,33) (2,54) (2,87)
40..49: (1,75) (0,25) (1,10) (2,99) (0,71) (0,49) (1,91) (2,85) (0,58) (1, 3)
```

The contact value is interpreted by the literal rule `contact < threshold`.
The trajectory neither stores this tape nor exposes it through its records.

## Complete prefix `[0,7)`

### `periodic-v1`, `N=7`

```text
A(  0, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             0)
A(  1, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             0)
A(  2, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             0)
A(  5, (4,4,1), ( 9,33,18,2), (1,1,2,2), (6,0,1,0), (0,0,2,0), (0,5,0,1,0,0,0,0), (0,0,0,0,1,0,0,0), ((0,6),(2,1)),       0)
A( 10, (4,4,1), ( 9,33,18,2), (2,1,2,2), (6,0,1,0), (0,0,2,0), (0,4,0,1,0,0,0,0), (0,1,0,0,1,0,0,0), ((0,6),(2,1)),       0)
A( 25, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,0,1,1), (0,0,2,3), (0,3,0,0,0,0,0,0), (0,1,0,1,1,0,1,0), ((0,5),(2,1),(3,1)), 1)
A( 50, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,0,1,1), (0,0,2,3), (0,3,0,0,0,0,0,0), (0,1,0,1,1,0,1,0), ((0,5),(2,1),(3,1)), 1)
A(100, (4,4,4), (12,48, 0,5), (7,2,5,3), (5,0,1,1), (0,0,2,3), (0,0,0,0,0,0,0,0), (0,4,0,1,1,0,1,0), ((0,5),(2,1),(3,1)), 1)
```

### `hard-wall-legacy-asymmetric-v1`, `N=7`

```text
A(  0, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  1, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  2, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  5, (4,4,1), ( 9,33,18,2), (1,1,2,2), (6,0,1,0), (0,0,2,0), (0,5,0,1,0,0,0,0), (0,0,0,0,1,0,0,0), ((0,6),(2,1)),       None)
A( 10, (4,4,1), ( 9,33,18,2), (2,1,2,2), (6,0,1,0), (0,0,2,0), (0,4,0,1,0,0,0,0), (0,1,0,0,1,0,0,0), ((0,6),(2,1)),       None)
A( 25, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,1,1,0), (0,3,2,0), (0,3,0,0,0,0,0,0), (0,1,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
A( 50, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,1,1,0), (0,3,2,0), (0,3,0,0,0,0,0,0), (0,1,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
A(100, (4,4,4), (12,48, 0,5), (7,2,5,3), (5,1,1,0), (0,3,2,0), (0,0,0,0,0,0,0,0), (0,4,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
```

### `hard-wall-reflection-symmetric-v1`, `N=7`

For this particular prefix the corrected and legacy hard-wall snapshots are
identical, including every equality and causal stratum. They are nevertheless
listed literally for both identities; this is not a claim that the laws agree
in general. The `N=50` vectors below expose their reachable difference.

```text
A(  0, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  1, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  2, (2,4,1), ( 7,21,14,0), (0,0,0,0), (7,0,0,0), (0,0,0,0), (0,7,0,0,0,0,0,0), (0,0,0,0,0,0,0,0), ((0,7),),             None)
A(  5, (4,4,1), ( 9,33,18,2), (1,1,2,2), (6,0,1,0), (0,0,2,0), (0,5,0,1,0,0,0,0), (0,0,0,0,1,0,0,0), ((0,6),(2,1)),       None)
A( 10, (4,4,1), ( 9,33,18,2), (2,1,2,2), (6,0,1,0), (0,0,2,0), (0,4,0,1,0,0,0,0), (0,1,0,0,1,0,0,0), ((0,6),(2,1)),       None)
A( 25, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,1,1,0), (0,3,2,0), (0,3,0,0,0,0,0,0), (0,1,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
A( 50, (4,4,4), (12,48, 0,5), (4,2,5,3), (5,1,1,0), (0,3,2,0), (0,3,0,0,0,0,0,0), (0,1,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
A(100, (4,4,4), (12,48, 0,5), (7,2,5,3), (5,1,1,0), (0,3,2,0), (0,0,0,0,0,0,0,0), (0,4,1,1,1,0,0,0), ((0,5),(2,1),(3,1)), None)
```

## Complete prefix `[0,50)`

### `periodic-v1`, `N=50`

```text
A(  0, (17,17,16), (50, 834,2, 0), ( 0,0, 0,0), (50,0,0,0), (0,0,0,0),  (0,34,0,7,0,5,0,4), (0,0,0,0,0,0,0,0),   ((0,50),),                         10)
A(  1, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0),  (0,32,0,5,0,9,0,3), (0,0,1,0,0,0,0,0),   ((0,49),(1,1)),                   10)
A(  2, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0),  (0,32,0,5,0,9,0,3), (0,0,1,0,0,0,0,0),   ((0,49),(1,1)),                   10)
A(  5, (19,19,19), (57,1083,0, 7), ( 6,3, 7,3), (47,0,2,1), (0,0,5,2),  (0,25,0,7,0,8,0,4), (0,3,0,0,2,0,1,0),   ((0,47),(2,2),(3,1)),              8)
A( 10, (19,19,19), (57,1083,0, 7), ( 8,3, 7,3), (47,0,2,1), (0,0,5,2),  (0,23,0,7,0,8,0,4), (0,5,0,0,2,0,1,0),   ((0,47),(2,2),(3,1)),              8)
A( 25, (19,20,20), (59,1161,2, 9), (15,5, 9,3), (45,0,4,1), (0,0,6,3),  (0,18,0,5,0,9,0,3), (0,6,0,1,4,3,1,0),   ((0,45),(1,2),(2,2),(3,1)),        7)
A( 50, (22,22,21), (65,1409,2,15), (24,9,15,3), (41,2,4,3), (0,3,5,7),  (0,14,0,3,0,6,0,3), (0,10,2,3,4,1,3,1),  ((0,41),(1,5),(2,2),(3,2)),       11)
A(100, (23,23,22), (68,1542,2,18), (50,9,18,4), (41,1,5,3), (0,1,11,6), (0,0,0,0,0,0,0,0),  (0,23,1,7,5,4,3,7),  ((0,41),(1,3),(2,4),(3,1),(4,1)), 12)
```

### `hard-wall-legacy-asymmetric-v1`, `N=50`

```text
A(  0, (17,17,16), (50, 834,2, 0), ( 0,0, 0,0), (50,0,0,0), (0,0,0,0), (0,40,0,6,0,4,0,0), (0,0,0,0,0,0,0,0),  ((0,50),),                         None)
A(  1, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0), (0,41,0,1,0,5,0,2), (0,0,1,0,0,0,0,0),  ((0,49),(1,1)),                   None)
A(  2, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0), (0,41,0,1,0,5,0,2), (0,0,1,0,0,0,0,0),  ((0,49),(1,1)),                   None)
A(  5, (19,18,18), (55,1009,2, 5), ( 6,3, 5,2), (47,1,2,0), (0,2,3,0), (0,31,0,7,0,5,0,1), (0,2,1,1,2,0,0,0),  ((0,47),(1,1),(2,2)),             None)
A( 10, (19,18,18), (55,1009,2, 5), ( 8,3, 5,2), (47,1,2,0), (0,2,3,0), (0,29,0,7,0,5,0,1), (0,4,1,1,2,0,0,0),  ((0,47),(1,1),(2,2)),             None)
A( 25, (19,19,19), (57,1083,0, 7), (15,4, 7,3), (46,1,3,0), (0,3,4,0), (0,21,0,4,0,8,0,2), (0,7,1,2,3,1,0,1),  ((0,46),(1,2),(2,1),(3,1)),       None)
A( 50, (20,19,19), (58,1122,2, 8), (24,5, 8,3), (45,1,4,0), (0,3,5,0), (0,16,0,4,0,6,0,0), (0,14,1,3,2,1,2,1), ((0,45),(1,3),(2,1),(3,1)),       None)
A(100, (21,21,20), (62,1282,2,12), (50,7,12,3), (43,2,5,0), (0,4,8,0), (0,0,0,0,0,0,0,0),  (0,25,2,10,5,7,0,1), ((0,43),(1,3),(2,3),(3,1)),       None)
```

### `hard-wall-reflection-symmetric-v1`, `N=50`

```text
A(  0, (17,17,16), (50, 834,2, 0), ( 0,0, 0,0), (50,0,0,0), (0,0,0,0), (0,40,0,6,0,4,0,0), (0,0,0,0,0,0,0,0),  ((0,50),),                         None)
A(  1, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0), (0,41,0,1,0,5,0,2), (0,0,1,0,0,0,0,0),  ((0,49),(1,1)),                   None)
A(  2, (17,17,17), (51, 867,0, 1), ( 1,1, 1,1), (49,1,0,0), (0,1,0,0), (0,41,0,1,0,5,0,2), (0,0,1,0,0,0,0,0),  ((0,49),(1,1)),                   None)
A(  5, (19,19,18), (56,1046,2, 6), ( 6,3, 6,2), (47,2,1,0), (0,4,2,0), (0,31,0,7,0,5,0,1), (0,2,2,1,1,0,0,0),  ((0,47),(2,3)),                   None)
A( 10, (19,19,18), (56,1046,2, 6), ( 8,3, 6,2), (47,2,1,0), (0,4,2,0), (0,29,0,7,0,5,0,1), (0,4,2,1,1,0,0,0),  ((0,47),(2,3)),                   None)
A( 25, (19,19,19), (57,1083,0, 7), (15,4, 7,3), (46,1,3,0), (0,3,4,0), (0,21,0,4,0,8,0,2), (0,7,1,2,3,1,0,1),  ((0,46),(1,2),(2,1),(3,1)),       None)
A( 50, (20,20,19), (59,1161,2, 9), (24,6, 9,3), (44,2,2,2), (0,4,3,2), (0,16,0,4,0,6,0,0), (0,14,2,3,2,0,2,1), ((0,44),(1,4),(2,1),(3,1)),       None)
A(100, (21,21,20), (62,1282,2,12), (50,7,12,3), (43,2,5,0), (0,4,8,0), (0,0,0,0,0,0,0,0),  (0,25,2,10,5,7,0,1), ((0,43),(1,3),(2,3),(3,1)),       None)
```

The threshold-five rows are the compact decisive boundary witness:

| Law | Heights | `S` | `Q` | `V` | Causal counts | Histogram |
|---|---|---:|---:|---:|---|---|
| periodic | `(19,19,19)` | 57 | 1083 | 7 | `(47,0,2,1)` | `((0,47),(2,2),(3,1))` |
| legacy hard wall | `(19,18,18)` | 55 | 1009 | 5 | `(47,1,2,0)` | `((0,47),(1,1),(2,2))` |
| corrected hard wall | `(19,19,18)` | 56 | 1046 | 6 | `(47,2,1,0)` | `((0,47),(2,3))` |

## Independent certification envelope

The test-side oracle owns its SHA-256 key derivation, arbitrary-precision
Philox and rejection mapper, strict threshold ladder, three boundary
recurrences, and every accumulator fold. It imports and calls no production
RNG, selector, transition, trajectory, accumulator, or observable helper.
The persisted rows are a small normative subset, not the exhaustive domain.

The fast suite separately covers all 3,600 one-event width-three-to-five
cases; all 1,323 two-event width-three tapes; a real-RNG sweep over roots
0--15, widths 3, 4, 5, and 32, all laws, all arms, and 64 events; forced launch
and contact rejection through the real Slice 2 route; and exhaustive chunk
partitions of these prefixes. A declared-slow gate covers all 27,783
three-event tapes. Named adversarial cases exercise every causal side,
equality versus eligibility, bilateral ties, periodic seam equality on
nontrigger events, the reachable archived `x=1` defect, nesting, histogram
projections, unsigned bounds, high/low-word `Q` round trips, forged records,
delegate call order, rebinding, exports, dependencies, and hash-seed stability.

## Scope boundary

This certificate advances only the scalar trajectory prerequisite for
common-correctness item 4. It closes no numbered common-correctness item.
Packed unsigned-128 `Q`, compiled or Numba trajectories, scalar/compiled
equality, performance claims, checkpointing, persistence, resume, campaign
identity and schedules, configuration/YAML, legacy dispatch, runner/CLI,
scheduler, Easley/Slurm/HPC, pilots, canaries, simulation output, analysis,
and every form of scientific acquisition remain closed. Common-correctness
items 4--6 therefore remain open for Slice 6 and later work.
