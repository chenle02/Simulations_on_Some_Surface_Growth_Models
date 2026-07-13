# `semantic-philox4x64-10-v1` conformance vectors

These vectors are normative for the provisional S2.2 transition-RNG oracle.
They pin byte order, word order, lane selection, rejection accounting, and
categorical interval semantics independently of any Python or NumPy release.

The upstream core vectors were checked against D. E. Shaw Research's pinned
[Random123 known-answer suite](https://github.com/DEShawResearch/random123/blob/9545ff6413f258be2f04c1d319d99aaef7521150/tests/kat_vectors)
at commit `9545ff6413f258be2f04c1d319d99aaef7521150`; its executable suite passed all
60 cases. A separate unsigned-128-bit C/C++ checker and the independent Python
test oracle agree on the project-specific vectors below. Every table row in
this document is also a persistent package test.

## Exact key preimage

The SHA-256 preimage is the byte concatenation

```text
"tetris-kpz/semantic-philox4x64-10-v1\0"
|| root_seed_u128_be16
|| coupling_group_utf8_length_u32_be
|| coupling_group_utf8
|| stream_name_utf8_length_u32_be
|| stream_name_utf8
```

Group and stream identifiers are nonempty exact Unicode strings. Their UTF-8
bytes are used without normalization. The first 16 digest bytes are split into
two consecutive big-endian unsigned 64-bit key words.

S1a fixed the UTF-8 length framing but left empty identifiers and Unicode
normalization implicit. S2.2 ratifies the fail-closed refinement above:
identifiers are nonempty, and distinct Unicode code-point sequences remain
distinct stream identities even when they render alike.

## Upstream Philox4x64-10 known answers

Each row contains four counter words, two key words, then four output words.

| Counter | Key | Output |
|---|---|---|
| `0000000000000000 0000000000000000 0000000000000000 0000000000000000` | `0000000000000000 0000000000000000` | `16554d9eca36314c db20fe9d672d0fdc d7e772cee186176b 7e68b68aec7ba23b` |
| `ffffffffffffffff ffffffffffffffff ffffffffffffffff ffffffffffffffff` | `ffffffffffffffff ffffffffffffffff` | `87b092c3013fe90b 438c3c67be8d0224 9cc7d7c69cd777b6 a09caebf594f0ba0` |
| `243f6a8885a308d3 13198a2e03707344 a4093822299f31d0 082efa98ec4e6c89` | `452821e638d01377 be5466cf34e90c6c` | `a528f45403e61d95 38c72dbd566e9788 a5a1610e72fd18b5 57bd43b5e52b7fe6` |

## Project key and raw-word vectors

The raw candidate is output lane zero at counter
`(event_ordinal, rejection_ordinal, 0, 0)`.

| Root seed (hex, 16 bytes) | Group | Stream | Event | Rejection | Key | Philox output |
|---|---|---|---:|---:|---|---|
| `00000000000000000000000000000000` | `paired-main` | `family` | 0 | 0 | `1682c41740e367dc d803dc8cb13639ca` | `9fc97b3e13cee41b ead120cbcc65480e eedd7c7d8401e708 d2e3c98cfa1e44fb` |
| `0123456789abcdeffedcba9876543210` | `c0e-pure-i` | `launch` | 42 | 0 | `9e291b64fe60da0c 857f38fc86cf72e4` | `acd7b7cd13c14731 0ac0ced1323a53d8 607f1ccee599ef39 ca64c369062051da` |
| `ffffffffffffffffffffffffffffffff` | `independent-arm` | `contact` | `18446744073709551615` | `18446744073709551615` | `ec843c817f1fddbd 4c47480a694a88d9` | `8691ce71f2cf45b4 bd6694be8520464b aec41c4237190877 bbebcb4623a49998` |
| `80000000000000000000000000000001` | `paired-α` | `tie` | `9223372036854775808` | 7 | `2c2eb2cd1913125e a8b16cdefd2e3a6e` | `be68c64b42393906 4dc66acca051a17b b8913d53897e4cfa 8a0e11c9757843e4` |

## Exact bounded and categorical vectors

For bound `n`, let `M = 2**64`, `q = floor(M/n)`, and `T = q*n`. Reject a
candidate when `w >= T`; otherwise return `floor(w/q)`. The accepted rejection
ordinal is the zero-based candidate address, so the number of raw words read is
that ordinal plus one.

| Address | Mapping | Result |
|---|---|---|
| zero root / `paired-main` / `family` / event 0 | `n=5` | value 3, accepted rejection 0 |
| `0123456789abcdeffedcba9876543210` / `c0e-pure-i` / `launch` / event 42 | `n=17` | value 11, accepted rejection 0 |
| zero root / `paired-main` / `contact` / event 0 | `n=4` | value 3, accepted rejection 0 |
| all-`ff` root / `independent-arm` / `contact` / maximum event | `n=2**64` | value `10231637573218554332`, accepted rejection 0 |
| `0123456789abcdeffedcba9876543210` / `rejection-test` / `launch` / event 0 | `n=9223372036854775809` | reject `e2160df4a6d93ad1` at ordinal 0; accept `64b06603de3d5062` = `7255411166493364322` at ordinal 1 |

Categorical vectors retain zero-count positions and use half-open cumulative
intervals:

| Address | Counts | Uniform value | Selected index |
|---|---|---:|---:|
| zero root / `paired-main` / `family` / event 0 | `(1,1,1,1,1)` | 3 | 3 |
| zero root / `paired-main` / `contact` / event 0 | `(1,3)` | 3 | 1 |
| zero root / `paired-main` / `contact` / event 0 | `(0,3,1,0)` | 3 | 2 |
| zero root / `paired-main` / `orientation` / event 0 | `(1,1,1,1,1,1,1,1)` | 7 | 7 |
| root 1 / `degenerate` / `contact` / event 9 | `(1)` | 0 | 0 |

Only nonempty ordered vectors of exact nonnegative integer counts are valid.
Their sum must lie in `[1, 2**64]`, and the greatest common divisor of positive
counts must be one.
