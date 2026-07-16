# PRE one-cell compiled-RNG conformance receipt and index

This document freezes the Slice 4 compiled-conformance boundary for
`tetris_ballistic.engine.rng_compiled`. It is an evidence index, not a new
random-number-vector authority: the pinned upstream and project documents
below own the expected values. A conflict is resolved in favor of those
authorities and, for scientific semantics, the frozen PRE protocol.

Slice 4 advances only common-correctness item 3. This receipt does not by
itself assert that source, package, review, CI, or repository-parity gates have
passed, and it does not authorize scientific acquisition.

## Pinned authorities

| Authority | Frozen identity |
|---|---|
| PRE scientific protocol | Article commit `85404aee4dab7ade81c6893fac9f34aeaddf50dd`; `PRE-DISCOVERY-PROTOCOL.md` SHA-256 `ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358` |
| Slice 4 implementation freeze | Coordinator roadmap commits `cb8cfe466dc9006ee9a8f4c657ef0ec57f5c6b75`, count clarification `f93cd63611a705f1a0472eebf3e8f6b827a3161c`, and vector-authority expansion `28fe48f03e06cd88372b5bc256b1e6fdf56c1c05`; software parent `1745c3d9aba3a407d87455c5983dd4370daa8b7e` |
| Upstream Philox4x64-10 | Random123 commit `9545ff6413f258be2f04c1d319d99aaef7521150`; `tests/kat_vectors` SHA-256 `aab5ebabf40003f63d6d87b24cbd2c8a02652e00cf8bad64226fd50586929183` |
| Project semantic RNG vectors | `docs/SEMANTIC-RNG-VECTORS.md` SHA-256 `913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34` |
| Project exact-selection vectors | `docs/EXACT-SELECTION-VECTORS.md` SHA-256 `324f43f4a42a0bcf71af01eb1aab32d7c219b986d3bdd67cc888f2f5ed6f21a9` |
| Project complete-event vectors | `docs/COMPLETE-EVENT-SELECTION-VECTORS.md` SHA-256 `331a445c5dc278a79a61bfb6d89eaadf7ed4ec9763036d8a4602d4c1615f2839` |
| PRE coupling vectors | `docs/PRE-ONE-CELL-COUPLING-VECTORS.md` SHA-256 `74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3` |
| Scalar comparison implementation | `tetris_ballistic/engine/rng.py` SHA-256 `19dca94ea97fae16278b198505200a5be27d80821dd54c8e454f135390888489` |

The scalar implementation is comparison evidence, not compiled source. The
compiled module may reuse its frozen `SemanticDraw` record, but it may not call
the scalar Philox or bounded mapper.

## Explicit API boundary

The explicit-only module has exactly this public surface:

```python
philox4x64_10(*, counter, key) -> tuple[int, int, int, int]
raw_u64_from_key(*, key, event_ordinal, rejection_ordinal=0) -> int
uniform_below_from_key(*, key, event_ordinal, n) -> SemanticDraw
```

Counter and key containers are exact built-in tuples containing exact
unsigned-64 built-in integers. Sampling is deliberately key-level: SHA-256
root/group/stream derivation remains the certified scalar host operation and
is not presented as compiled work. No name is re-exported from either package
root.

## Word, counter, and bounded-map laws

Philox uses the Random123 Philox4x64-10 constants, permutation, ten-round key
schedule, and arithmetic modulo `2**64`. The compiled high/low product uses
unsigned integer limbs; it does not enter Python arbitrary-precision arithmetic
inside the numerical kernel.

A semantic raw candidate is output lane zero. The four counter lanes are, in
order,

```text
(event_ordinal, rejection_ordinal, 0, 0).
```

The two key words retain their documented order, and the other three output
lanes remain observable through `philox4x64_10` for full-vector conformance.
Only the rejection lane advances after a rejected candidate, so another event
or stream address cannot move.

For `M = 2**64`, public bound `n` in `[1, M]`,
`q = floor(M / n)`, and `T = q*n`, a candidate `word` is rejected exactly when
`word >= T`; an accepted candidate returns `floor(word / q)`. The private
compiled boundary carries the bound as the unsigned word `n - 1`. Thus zero
encodes public bound one, the maximum unsigned word encodes public bound
`2**64`, and neither endpoint needs an API sentinel.

Bound one still evaluates the ordinal-zero Philox candidate before returning
zero. Bound `2**64` accepts the ordinal-zero candidate unchanged. Powers of two
whose mathematical threshold is `2**64` accept every unsigned word. Rejection
accounting is zero based and must fail before the unsigned rejection ordinal
could wrap.

## Certification-vector manifest

The certification suite begins with three supplementary fixed project key/raw
probes and a 56-row base manifest. The base is exactly 3 upstream
full-output known answers, 4 documented project full-output rows, 5 documented
bounded rows, 5 documented categorical examples at their compiled uniform
layer only, 7 boundary-sized mappings, both root-zero PRE stream rows, all 15
campaign-width launch rows, all 12 strict contact-boundary rows, and all 3
unequal-width launch rows. The supplementary probes are test cross-checks and
do not become another vector authority.

The suite also replays every additional underlying uniform/raw projection that
is applicable to this lower-level API:

- all four exact-selection uniform rows, including the shared
  `rejection-test` tape at bounds `2`, `2**63 + 1`, and `2**64`;
- the canonical complete-event family, selected-family orientation, launch,
  and contact rows, with respective raw words `9fc97b3e13cee41b`,
  `ffc7fb838d848799`, `40af7280b937935a`, and `cdcc6e52e762825f`;
- the complete-event event-one launch tape (`853fe237a36163cc`, then
  `72b281009e3eb9c5`) under both its bound-two and unequal-bound laws, plus the
  unchanged event-two ordinal-zero word `d997d7678fd2d614`; and
- the PRE event-zero contact mapping to value 79 at rejection ordinal zero.

Beyond that row count, the rejection evidence freezes these candidate chains:

- ordinal one: for bound `2**63 + 1`, reject
  `e2160df4a6d93ad1` and accept `64b06603de3d5062`;
- ordinal two: the PRE launch event-six tape for the same bound is
  `c2361db490f49873`, `a4e089425b0398f4`, then accepted
  `29a2134f7be99c8d`; and
- ordinal five: the `rejection-audit` contact event-six tape is
  `d067a4b6d387c47b`, `c8e66d786b591323`, `a4aa97456a5cd3e2`,
  `e0e748fbcbc33456`, `a3fbb0e492eaafcb`, then accepted
  `25443a3d1347f4fe`.

Together these are natural rejection witnesses.
Acceptance occurs at ordinals one, two, and five.
The corresponding checks retain the next event and other stream at their
ordinal-zero addresses. Literal mapper tests also exercise `T - 1` acceptance,
`T` rejection, maximum candidate words, exact endpoint bounds, and
fail-before-wrap behavior.

Two deterministic differential sweeps add 10,000 independently generated
counter/key blocks and 10,000 independently generated raw/bounded addresses.
Their expected values come from the separately written arbitrary-precision
Python oracle; selected rows are also cross-checked against the certified
scalar host implementation, which is never the sole expected authority.

Every numerical kernel must acquire a Numba nopython signature over unsigned
integer arguments. Object mode, floating point, fast math, Python or NumPy
random distributions, and calls into the scalar numerical implementation are
outside the conformance boundary. The optional `hpc` dependency supplies
Numba; package-root and engine-root imports remain usable without it.

## Non-goals

Slice 4 does not compile SHA-256 key derivation or categorical interval search.
It adds no PRE two-draw scheduler, nested-arm evolution, boundary transition,
multi-event trajectory or chunk, accumulator, checkpoint, resume, persistence,
configuration or legacy adapter, CLI, benchmark or performance claim,
GPU/CUDA route, scheduler integration, Slurm/Easley/HPC submission, pilot,
canary, production route, or scientific acquisition. The legacy
`tetris_ballistic/_kernel_1x1.py` is neither imported nor an authority.
Common-correctness items 4--6 remain separate gates.
