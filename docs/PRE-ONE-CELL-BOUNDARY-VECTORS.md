# PRE one-cell scalar boundary vectors

These vectors are normative for the provisional scalar transition in
`tetris_ballistic.engine.one_cell_boundary`. They pin the three boundary laws,
the archived exp14 defect, the corrected reflection-symmetric rule, and the
certificate semantics without creating a trajectory or production route.

Every scalar vector and exhaustive count below is asserted by the package
certification suite.

## Frozen boundary contract

The exact boundary identities are

```text
periodic-v1
hard-wall-legacy-asymmetric-v1
hard-wall-reflection-symmetric-v1
```

For pre-event physical heights `h`, launch column `x`, and
`vertical = h[x] + 1`, a nonsticky event has `post = vertical` under every
law. A selected sticky event has

```text
periodic:          post = max(vertical, h[(x-1) mod L], h[(x+1) mod L])
legacy hard wall:  post = max(vertical,
                              h[x-1] if x > 1,
                              h[x+1] if x < L-1)
corrected wall:    post = max(vertical,
                              h[x-1] if x > 0,
                              h[x+1] if x < L-1)
```

Only the launch column changes. The hard-wall laws therefore agree everywhere
except the existing left neighbor at launch `x=1`. Eligibility is determined
by law and position, independently of whether the sticky endpoint was
selected. A nonsticky event ignores otherwise eligible neighbors.

The exact integer increments are

```text
delta_s = post - h[x]
delta_v = post - (h[x] + 1)
delta_q = post**2 - h[x]**2
```

The positive-gap trigger requires both a selected sticky endpoint and
`delta_v > 0`. Causal sides are only eligible neighbors attaining `post` on
such an event. By contrast, equality bits are height-defined for every
physically existing neighbor, including the legacy-ineligible left neighbor
at `x=1`:

```text
mask = 1 * (post == vertical)
     + 2 * (existing left height == post)
     + 4 * (existing right height == post).
```

An absent hard-wall neighbor is recorded as `None` and cannot set an equality
bit. Periodic seam equality is Boolean; hard-wall seam equality is not
applicable and is recorded as `None`, never as physical false or zero.

## Archived exp14 authority

The legacy law is pinned to all five exp14 simulation commits:

```text
767577aaa00988a3eeb8a4a5a6c795234cb89aa2
06d3e38c2fbdb19f8bc47ed24d09181e21e39bbf
58b17f814c0b0e6c3e4f72ab62f072a2792e86e9
a47ec6c6606bc78a86427cca7a2f331c68dce653
218819fb67742f9f4652176cd61c180713edd448
```

In every commit, `tetris_ballistic/tetris_ballistic.py` is Git blob
`8c4f64f71a1e2b1769dbd1b37fee3c40df608323`, with full-file SHA-256
`3ce8ade36fa1e471fa54cce6e3b3fd8950f0ef21d734343423f46275e83dc206`.
The archived anchors are `_surface_row` at lines 662--677, `_Place_1x1` at
1668--1680, and `Update_1x1` at 1682--1722; the asymmetric eligibility guards
are at 1699--1701.

The compiled `tetris_ballistic/_kernel_1x1.py` is likewise identical across
all five commits: blob `3d6bf4c3f6bc622b357be1a328fd5fe4541a3d99`,
full-file SHA-256
`eaeb255240fa05610c6d77abdc93df15020c6699b47cafac6a7444e98acd74c7`.
Its landing arithmetic carries the same guards.

The certification file embeds the exact archived `_surface_row`,
`_update_heights_for_columns`, `_Place_1x1`, and `Update_1x1` method bodies and
executes that engine fixture on every small state. It also translates the
top-origin row calculation into a structurally independent oracle. For any
test state, choose `H = max(h) + 4`, set `surface(c) = H - h[c]`, and compute

```text
left row  = surface(x-1) + 1  if sticky and x > 1   else H
pivot row = surface(x)
right row = surface(x+1) + 1  if sticky and x < L-1 else H
landing   = min(left row, pivot row, right row)
post      = H - (landing - 1).
```

The executable fixture and independent inverted-row oracle are both
self-contained in shallow CI checkouts. A separate slow local-history test
rehashes both archived files at all five commits and proves that every embedded
method body equals the archived source when the objects are present; CI
correctness never depends on those historical objects being available.

## Normative boundary vectors

All rows select the sticky endpoint.

| Pre-heights | Launch | Law | Post-heights | Gap | Causal side | Equality mask | Neighbor eligibility |
|---|---:|---|---|---:|---|---:|---|
| `(0, 5, 0)` | 0 | either hard wall | `(5, 5, 0)` | 4 | right | 4 | left false, right true |
| `(5, 0, 0)` | 1 | legacy | `(5, 1, 0)` | 0 | none | 1 | left false, right true |
| `(5, 0, 0)` | 1 | corrected | `(5, 5, 0)` | 4 | left | 2 | left true, right true |
| `(1, 0, 0)` | 1 | legacy | `(1, 1, 0)` | 0 | none | 3 | left false, right true |
| `(5, 0, 5)` | 1 | legacy | `(5, 5, 5)` | 4 | right | 6 | left false, right true |
| `(5, 0, 5)` | 1 | corrected | `(5, 5, 5)` | 4 | both | 6 | left true, right true |
| `(0, 5, 0)` | 2 | either hard wall | `(0, 5, 5)` | 4 | left | 2 | left true, right false |

The decisive defect witness is therefore `(5, 0, 0)`, launch 1: legacy post
height 1 versus corrected post height 5. The `(1, 0, 0)` row separately shows
that an existing but ineligible neighbor can remain height-equal without
becoming causal.

These seam-separation vectors prevent accidental wraparound:

| Pre-heights | Launch | Hard-wall post | Periodic post |
|---|---:|---|---|
| `(0, 0, 5)` | 0 | `(1, 0, 5)` | `(5, 0, 5)` |
| `(5, 0, 0)` | 2 | `(5, 0, 1)` | `(5, 0, 5)` |

The periodic route delegates exactly once to the Slice 1
`transition_one_cell_periodic` authority and returns its complete certificate
as a boundary-record projection. Both hard-wall routes are independent of that
delegate.

## Exhaustive evidence

For each law, the fast suite enumerates widths 3, 4, and 5; every height vector
in `product(range(4), repeat=L)`; every launch; and both endpoint selections.
That is exactly 12,672 events per law.

The legacy route agrees event by event with both the exact executable archived
engine fixture and the independent inverted-row archive oracle. The corrected
route agrees with a separately written direct physical-height oracle. The
corrected law is reflection symmetric on all 12,672 cases. The legacy and
corrected routes differ in exactly 168 cases:
8 at width 3, 32 at width 4, and 128 at width 5. Every difference, and only a
difference, satisfies

```text
sticky and x == 1 and h[0] > max(h[1] + 1, h[2]).
```

The suite also covers exact periodic delegation and cross-binding, forged and
cross-request delegate records, every record field, hostile concrete types,
arbitrary-precision integers, immutable caller snapshots, frozen/slotted
records, public-alias rebinding, explicit-submodule exports, and dependency
guards.

## Scope boundary

`OneCellBoundaryTransition` is an immutable in-memory scalar certificate. This
unit adds no RNG, coupled-arm evolution, accumulation, multi-event trajectory,
compiled/Numba path, checkpoint or persistence identity, configuration or
legacy dispatch, CLI, scheduler, Easley/Slurm/HPC route, release, or production
path. It closes only common-correctness item 2 when its complete source,
package, review, CI, and parity gates pass. Compiled RNG, compiled/scalar
trajectories, interruption/resume, campaign identity, pilots, canaries, and all
scientific acquisition remain closed.
