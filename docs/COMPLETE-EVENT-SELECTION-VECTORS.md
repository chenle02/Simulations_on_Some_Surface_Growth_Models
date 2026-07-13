# Complete tetromino event-selection conformance vectors

These vectors are normative for the provisional S2.4 selector in
`tetris_ballistic.engine.event`. The selector composes the certified S2.2
counter-addressed RNG and S2.3 exact one-stream records into one complete,
named tetromino event without placing a piece.

## Fixed executable orders

The event law uses these exact built-in-string tuples:

```text
family      = ("i", "lj", "o", "sz", "t")
contact     = ("supported-v1", "edge-first-contact-v1")
streams     = ("family", "orientation", "launch", "contact")
```

The complete conditional orientation table has all five family branches in
family order, even when a family has zero weight:

```text
i   = ("tetromino.i.00", "tetromino.i.01")
lj  = ("tetromino.lj.00", ..., "tetromino.lj.07")
o   = ("tetromino.o.00",)
sz  = ("tetromino.sz.00", ..., "tetromino.sz.03")
t   = ("tetromino.t.00", ..., "tetromino.t.03")
```

These are the exact 2/8/1/4/4 orders from `FAMILY_ORIENTATION_IDS`, not a
sorted or inferred view. Every branch law is validated before any RNG call.
The selector then evaluates exactly one logical draw from each fixed stream in
the order family, selected-family orientation, launch, contact. A one-outcome
selected orientation law, launch bound one, or fixed contact still consumes
the corresponding logical raw candidate. Zero-weight family branches remain
prevalidated but receive no orientation draw unless selected by a different
valid family law.

## Canonical complete-event vector

Use root seed `00000000000000000000000000000000`, coupling group
`paired-main`, event zero, equal family counts, equal counts within every
orientation branch, launch bound 17, and equal contact counts.

| Stream | Rejection-zero raw word | Selected record |
|---|---:|---|
| `family` | `9fc97b3e13cee41b` | index 3, `sz`, accepted rejection 0 |
| `orientation` | `ffc7fb838d848799` | index 3, `tetromino.sz.03`, accepted rejection 0 |
| `launch` | `40af7280b937935a` | value 4, accepted rejection 0 |
| `contact` | `cdcc6e52e762825f` | index 1, `edge-first-contact-v1`, accepted rejection 0 |

Only the selected `sz` orientation branch is evaluated. The other four branch
laws remain validated, immutable in-memory law evidence; they do not receive
extra draws and are not yet assigned a serialized identity.

## Shared-tape, unequal-bound vector

The approved coupling contract shares the raw candidate tape at an equal base
event address. It does not require unequal laws to share one accepted bounded
value or rejection ordinal.

At root zero, group `paired-main`, stream `launch`, event one, the first two
candidate words are

```text
W_0 = 853fe237a36163cc = 9601641659169334220
W_1 = 72b281009e3eb9c5 = 8264810105833175493
```

The two launch laws therefore produce

| Bound | Selected value | Accepted rejection ordinal |
|---:|---:|---:|
| `2` | `1` | 0 |
| `2**63 + 1` | `8264810105833175493` | 1 |

For bound 2, every word is acceptable and `W_0` maps to 1. For bound
`2**63 + 1`, the acceptance threshold is `9223372036854775809`; `W_0` is
rejected and `W_1` is accepted. The family, orientation, and contact results
remain identical because their laws and base addresses are identical. A
launch rejection cannot shift another stream or event: the launch word at
event two, rejection zero remains `d997d7678fd2d614`.

No arm, width, family, selected geometry, contact outcome, law label, or
rejection count is added to the stream key. Equal root seed, coupling group,
event ordinal, and literal stream name identify the whole candidate tape
`W_0, W_1, ...`; each law applies its own exact rejection map to that tape.

## Record and certification boundary

`TetrominoEventSelection` carries the validated root seed, coupling group,
event ordinal, complete frozen law, and all four immutable selections with
their `SemanticDraw` metadata. Direct record construction checks structural
consistency but does not replay Philox. The certified generation guarantee
applies to records returned by `select_event` with the in-package S2.2/S2.3
oracles.

The conformance suite also compares 10,000 complete events against an
independent composition oracle and requires all five families, all 19
orientations, both contacts, and a nonzero rejection ordinal to be observed.
Hash-seed changes may not alter any fixed order or selected result.

S2.4 defines no generic conditional DAG, named one-cell/control law, placement,
state transition, configuration or legacy adapter, trajectory, canonical JSON,
digest, shared artifact identity, checkpoint, optimized kernel, CLI, batch,
Slurm/HPC, or production route. The API is available only by explicit import
of `tetris_ballistic.engine.event`; it is not re-exported from either package
root.
