# PRE one-cell common-random-number coupling vectors

These vectors are normative for the provisional scalar selector in
`tetris_ballistic.engine.one_cell_coupling`. They pin the pre-discovery
one-cell campaign's shared launch, shared contact, and eight nested stickiness
arms without creating a trajectory or production execution route.

Every value below is also asserted by the package certification suite.

## Frozen event contract

The semantic RNG contract remains `semantic-philox4x64-10-v1`. The model-level
address and logical draw schedule are fixed as

```text
coupling group:  pre-one-cell-discovery-v1
declared streams: (launch, contact)

1. launch  ~ uniform_below(width)
2. contact ~ uniform_below(100)
```

Both logical draws are made exactly once at every event. All eight arms share
the resulting launch column and contact integer. For thresholds

```text
(0, 1, 2, 5, 10, 25, 50, 100)
```

the endpoint is sticky exactly when

```text
contact_value < threshold.
```

The strict inequality is part of the contract. Thus the 0% arm is always
nonsticky, the 100% arm is always sticky, and both still inherit the event's
common contact draw. The nesting can be read as a single rising ladder:

```text
contact u:  0 | 1 | 2..4 | 5..9 | 10..24 | 25..49 | 50..99
sticky at:  1+  2+    5+    10+      25+       50+       100
```

There are eight reported arms but seven possible Boolean decision patterns;
the 0% arm never switches and the 100% arm never switches.

Scientific root index `r` is used unchanged as the numerical unsigned 128-bit
root seed, and event ordinals are zero based.

## Root-zero stream keys and event-zero words

Keys are the two big-endian 64-bit words derived by the frozen S2.2 key
contract. Raw candidates are Philox output lane zero at counter
`(event_ordinal, rejection_ordinal, 0, 0)`.

| Stream | Key | Event-zero raw candidate |
|---|---|---|
| `launch` | `81ba8e755ea8a360 f829a74d482f4ebb` | `6f7a7d3d95aa5e68` |
| `contact` | `6c00b0c4102c9848 4373aa5df7ef12bd` | `cbf5c12a6fee559e` |

At width 64, event zero therefore yields

```text
launch  = value 27, accepted rejection 0
contact = value 79, accepted rejection 0
sticky  = (F, F, F, F, F, F, F, T)
```

## Event-zero campaign-width union

All planned widths share the launch raw candidate above. Their distinct bounds
map it to the following accepted columns; every row accepts rejection ordinal
zero and retains contact value 79.

| Width | 32 | 50 | 64 | 80 | 100 | 128 | 150 | 200 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Launch | 13 | 21 | 27 | 34 | 43 | 55 | 65 | 87 |

| Width | 250 | 256 | 300 | 400 | 500 | 512 | 1024 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| Launch | 108 | 111 | 130 | 174 | 217 | 222 | 445 |

## Strict contact-boundary vectors

These root-zero contact events pin both sides of every nontrivial threshold.
All shown candidates are accepted at rejection ordinal zero.

| Event | Contact value | Raw candidate |
|---:|---:|---|
| 23 | 0 | `019ab06e6d647a86` |
| 153 | 1 | `043db201a9973a5d` |
| 3 | 2 | `066653bc2aa19546` |
| 55 | 4 | `0bfb25192b17f92e` |
| 24 | 5 | `0f3558266a1ecb4c` |
| 1 | 9 | `1918f1660387fa79` |
| 42 | 10 | `19e67647a5038ba7` |
| 6 | 24 | `3f52c476d5d5f065` |
| 41 | 25 | `41e28830e2facf93` |
| 45 | 49 | `7daaf3e15f89f819` |
| 216 | 50 | `81e81f92c924dd8f` |
| 43 | 99 | `fed165ae9ecf81ff` |

For example, event 42 has contact value 10. It is nonsticky in the 10% arm
because equality does not satisfy the strict predicate, and sticky in the
25%, 50%, and 100% arms.

## Unequal-width rejection vector

Root zero, launch event 6 has the shared raw tape

```text
rejection 0: c2361db490f49873
rejection 1: a4e089425b0398f4
rejection 2: 29a2134f7be99c8d
```

It produces

| Width | Launch value | Accepted rejection |
|---:|---:|---:|
| 64 | 48 | 0 |
| 100 | 75 | 0 |
| `2**63 + 1` | 2999981533884423309 | 2 |

All three selections retain contact value 24 at rejection zero and therefore
the same arm decisions

```text
(F, F, F, F, F, T, T, T).
```

The next launch event's first candidate remains `4c65426535b61d1a`.
Consequently, coupling across unequal widths means a shared raw candidate tape,
not a guaranteed shared accepted variate. Rejection in one launch law cannot
shift the contact stream or a later event.

## Evidence and boundary

The fast suite covers the complete contact domain 0 through 99, the exact
two-call schedule, all planned campaign widths, hostile request and delegate
boundaries, forced contact rejection, direct-record recertification,
immutability, hash-seed stability, dependency guards, and absence of root
exports. A slow deterministic sweep compares 10,000 events at widths 32 and
`2**63 + 1` against an independent raw-word quotient/rejection mapper.

`OneCellCoupledEventSelection` is an immutable in-memory record. Direct
construction validates its address, stream names, and draw ranges but does not
replay Philox; certified semantic provenance applies to records returned by
`select_one_cell_coupled_event`.

This unit performs no one-cell transition, arm-state evolution, trajectory,
accumulation, persistence, configuration or legacy adaptation, compiled RNG or
kernel execution, scheduler, Slurm/Easley/HPC routing, release, or production
dispatch. In particular, these scalar vectors do not close the separately
required compiled-RNG admission gate. They also do not complete common
correctness or authorize scientific acquisition: boundary-law certification,
compiled/scalar trajectory equivalence, interruption/resume, and campaign-
identity gates remain open.
