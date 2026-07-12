# Legacy model map for the 2.1 compatibility series

This audit records current executable semantics before adapters are introduced. It is descriptive, not a new promise.

## Piece IDs

| Legacy ID | Legacy update path | Orientation count/group |
|---|---|---|
| 0 | O, rotation 0 | O family (1) |
| 1--2 | I, rotations 0--1 | I family (2) |
| 3--6 | L, rotations 0--3 | chiral L subset (4) |
| 7--10 | J, rotations 0--3 | reflected J subset (4) |
| 11--14 | T, rotations 0--3 | T family (4) |
| 15--16 | S, rotations 0--1 | chiral S subset (2) |
| 17--18 | Z, rotations 0--1 | reflected Z subset (2) |
| 19 | `Update_1x1`, rotation 0 | one-cell baseline; not a tetromino |

Thus IDs 0--18 are the 19 fixed tetromino orientations. The new registry groups L/J under free family `lj` and S/Z under free family `sz`, yielding five free families without erasing the fixed-orientation distinctions.

## Density-array semantics

Each `Piece-N: [a, b]` legacy entry contributes two sampling weights:

- index 0 (`a`): update path with `sticky=False`;
- index 1 (`b`): update path with `sticky=True`.

The 40 entries are flattened and normalized together. Therefore equal weights by fixed orientation are not equal weights by free family. A future adapter must preserve this distinction explicitly.

## Placement/contact semantics

- Each update method computes mechanically supported candidate heights.
- With `sticky=True`, methods additionally inspect cells immediately outside the falling piece footprint and permit earlier lateral-contact stopping.
- The exact offsets are piece/orientation-specific in the legacy methods; the legacy boolean is not yet replaced by the generic reference engine.
- Horizontal boundaries are hard walls. Current update methods guard left/right indices rather than wrapping periodically.
- Pieces do not rotate or relax after launch.

The typed `ContactKind.FIRST_CONTACT` name is provisional until golden tests demonstrate equivalence to every legacy sticky path. The typed model contracts do not route legacy simulations yet.

## RNG semantics

`Tetris_Ballistic.set_seed` seeds Python `random` and NumPy's process-global legacy RNG. Piece/state sampling uses the flattened 40-state CDF. The optimized one-cell kernel pregenerates positions and sticky flags to preserve the legacy stream.

The future stream-separated RNG design is scientifically breaking unless an adapter supplies pregenerated arrays that reproduce the legacy trajectory. It therefore needs a model/schema version and golden fixtures.

## Clock semantics

Legacy arrays include step-indexed fluctuation and `AvergeHeight`. Historical substrates store row indices from the top, so some saved mean-height traces descend and require `height_grid - hbar` correction. New typed clocks must never infer that correction silently; provenance records the convention and any migration.

## Typed-law adaptation boundary

`legacy_adapter.py` can expand a typed hard-wall configuration into the exact
legacy 20×2 density table by multiplying the independent free-family,
conditional-orientation, and contact-rule probabilities. It can reconstruct a
typed configuration from a legacy table only when geometry and contact are
independent. A legacy table that correlates particular geometries with sticky
or nonsticky behavior fails closed rather than being approximated. Periodic
typed configurations also fail because the legacy update paths use hard walls.

This conversion establishes distribution equivalence only. It does not route a
typed configuration into the legacy simulator and does not certify a new engine.

## Compatibility gate

Before a typed configuration can execute through a new engine:

1. map all 40 legacy states to registry orientation plus explicit contact rule;
2. freeze representative seed/config golden trajectories;
3. verify hard-wall edge placements for all 19 orientations;
4. verify sticky/nonsticky placement equivalence event by event;
5. verify one-cell optimized/reference equivalence;
6. document RNG and clock migrations.
