# Exact law-selection conformance vectors

These vectors are normative for the provisional S2.3 one-stream selection
layer in `tetris_ballistic.engine.selection`. They bind explicit outcome order,
zero-slot retention, declared-stream membership, selected semantic IDs, and
accepted rejection ordinals without floating-point probabilities or mapping
iteration order.

Every outcome tuple below is complete for that test record. The examples do
not declare a global canonical family/contact order, a named model law, or a
shared serialization/digest profile. Conditional and complete-event selection
remain outside this boundary.

## Exact record rules

`ExactWeightedLaw(outcome_ids, counts)` preserves both supplied tuples exactly
after defensive snapshotting. A valid record has

- a nonempty ordered tuple of unique, nonempty built-in string outcome IDs;
- exact UTF-8 code points with no Unicode normalization;
- an equally long tuple of built-in nonnegative integer counts;
- a positive total no greater than `2**64`; and
- greatest common divisor one across positive counts.

Zero-count positions are retained. Sorting, mapping conversion, float
normalization, count reduction, and removal of zero positions are forbidden.
A different outcome order is a different executable record.

`DeclaredStreamSet(stream_names)` likewise preserves a nonempty ordered tuple
of unique exact UTF-8 names. The one-stream selectors require the requested
name to be present before any RNG call. The record does not yet certify that a
complete event consumed every declared stream.

## Weighted semantic-ID vectors

All rows use root seed `00000000000000000000000000000000`, coupling group
`paired-main`, and event zero.

| Stream | Explicit outcome IDs | Counts | Result |
|---|---|---|---|
| `family` | `("slot-0","slot-1","slot-2","slot-3","slot-4")` | `(1,1,1,1,1)` | index 3, `slot-3`, accepted rejection 0 |
| `contact` | `("zero-a","bulk","tail","zero-b")` | `(0,3,1,0)` | index 2, `tail`, accepted rejection 0 |
| `orientation` | `("orientation-0","orientation-1","orientation-2","orientation-3","orientation-4","orientation-5","orientation-6","orientation-7")` | `(1,1,1,1,1,1,1,1)` | index 7, `orientation-7`, accepted rejection 0 |

At the same `family` address, total-five records with counts `(4,1)` and
`(1,4)` use the same bounded value 3 and accepted rejection ordinal 0. With
outcomes `("left","right")`, they select `left` at index 0 and `right` at
index 1 respectively. Reversing an all-one outcome tuple retains selected
index 3 but changes the semantic ID at that position; order is not inferred
from labels.

The degenerate record `ExactWeightedLaw(("fixed",), (1,))` at root 1, group
`degenerate`, stream `contact`, event 9 returns index 0 / `fixed` / rejection
0 and still reads the raw candidate at rejection ordinal zero.

## Uniform vectors

| Root seed (hex, 16 bytes) | Group | Stream | Event | Bound | Result |
|---|---|---|---:|---:|---|
| `0123456789abcdeffedcba9876543210` | `c0e-pure-i` | `launch` | 42 | 17 | value 11, accepted rejection 0 |
| `0123456789abcdeffedcba9876543210` | `rejection-test` | `launch` | 0 | 2 | value 1, accepted rejection 0 |
| `0123456789abcdeffedcba9876543210` | `rejection-test` | `launch` | 0 | `2**63+1` | value `7255411166493364322`, accepted rejection 1 |
| `0123456789abcdeffedcba9876543210` | `rejection-test` | `launch` | 0 | `2**64` | value `16291224046481783505`, accepted rejection 0 |

A bound of one returns zero but still reads the rejection-zero candidate.

## Coupling guarantee at different bounds

The exact shared object for equal `(root seed, coupling group, stream name,
event ordinal)` is the counter-addressed raw candidate tape. At the
`rejection-test` address its first two words are

```text
W_0 = e2160df4a6d93ad1
W_1 = 64b06603de3d5062
```

Bound 2 and bound `2**64` accept `W_0`; bound `2**63+1` rejects `W_0` and
accepts `W_1`. Thus equal bounds share the accepted bounded variate and
rejection ordinal, but different bounds need not share one literal accepted
uniform. No arm, width, selected outcome, or law label is added to the stream
key; rejection remains local to that named stream and event.

This package-level statement records the behavior of the frozen S2.2 mapper.
The scientific coupling terminology and any complete conditional selector must
be closed before named tetromino laws or paired event composition are added.

## Explicitly absent

S2.3 supplies no conditional law, branch resolver, full-event selector, named
family/contact/control constructor, model-registry validation, canonical JSON,
record digest, shared identity, configuration adapter, placement call,
trajectory, legacy migration, optimized kernel, CLI, batch, Slurm/HPC, or
production route.
