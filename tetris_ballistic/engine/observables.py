"""Pure exact primitives for sparse reference-engine states.

This explicit-only M1.2/S2 slice measures one immutable
:class:`~tetris_ballistic.engine.state.SparseAggregate`.  It performs no RNG,
event selection, placement, state transition, configuration execution,
checkpoint I/O, canonical serialization or persistence API, trajectory, or
production routing.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import SparseAggregate

__all__ = ["ReferenceStatePrimitives", "measure_state"]


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative built-in integer")
    return value


def _snapshot_state(value: object) -> SparseAggregate:
    if type(value) is not SparseAggregate:
        raise TypeError("state must be a SparseAggregate")
    try:
        return SparseAggregate(width=value.width, occupied=value.occupied)
    except AttributeError as error:
        raise TypeError("state must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class ReferenceStatePrimitives:
    """Frozen exact state primitives for one sparse aggregate.

    ``nonzero_column_heights`` is the canonically sorted sparse representation
    of the complete interface envelope: omitted columns have height zero, and
    each stored height is one plus that column's maximum occupied ``y``.
    ``below_envelope_volume`` is therefore exactly ``height_sum`` and
    ``void_count`` is the difference between that volume and
    ``occupied_mass``.  No floating porosity or roughness summary is stored
    here.
    """

    width: int
    nonzero_column_heights: tuple[tuple[int, int], ...]
    occupied_mass: int
    height_sum: int
    height_square_sum: int
    below_envelope_volume: int
    void_count: int

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 3:
            raise ValueError("width must be a built-in integer at least 3")
        if type(self.nonzero_column_heights) is not tuple:
            raise TypeError("nonzero_column_heights must be a built-in tuple")
        normalized_heights: list[tuple[int, int]] = []
        for entry in self.nonzero_column_heights:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("nonzero_column_heights must contain built-in (x, height) tuples")
            x, height = entry
            if type(x) is not int or not 0 <= x < self.width:
                raise ValueError("nonzero envelope columns must be built-in integers in [0, width)")
            if type(height) is not int or height <= 0:
                raise ValueError("nonzero envelope heights must be positive built-in integers")
            normalized_heights.append((x, height))
        if tuple(normalized_heights) != tuple(sorted(normalized_heights)):
            raise ValueError("nonzero_column_heights must be sorted by column")
        columns = tuple(x for x, _ in normalized_heights)
        if len(set(columns)) != len(columns):
            raise ValueError("nonzero_column_heights must contain unique columns")

        occupied_mass = _require_nonnegative_int(self.occupied_mass, label="occupied_mass")
        height_sum = _require_nonnegative_int(self.height_sum, label="height_sum")
        height_square_sum = _require_nonnegative_int(self.height_square_sum, label="height_square_sum")
        below_envelope_volume = _require_nonnegative_int(
            self.below_envelope_volume,
            label="below_envelope_volume",
        )
        void_count = _require_nonnegative_int(self.void_count, label="void_count")

        expected_height_sum = sum(height for _, height in normalized_heights)
        if height_sum != expected_height_sum:
            raise ValueError("height_sum must equal the sum of nonzero envelope heights")
        expected_height_square_sum = sum(height * height for _, height in normalized_heights)
        if height_square_sum != expected_height_square_sum:
            raise ValueError("height_square_sum must equal the sum of squared interface heights")
        if below_envelope_volume != height_sum:
            raise ValueError("below_envelope_volume must equal height_sum")
        if len(normalized_heights) > occupied_mass:
            raise ValueError("the number of nonzero columns must not exceed occupied_mass")
        if occupied_mass > below_envelope_volume:
            raise ValueError("occupied_mass must not exceed below_envelope_volume")
        if void_count != below_envelope_volume - occupied_mass:
            raise ValueError("void_count must equal below_envelope_volume minus occupied_mass")


def measure_state(state: SparseAggregate) -> ReferenceStatePrimitives:
    """Return exact primitives for one defensively reconstructed sparse state.

    For occupied mass ``m`` and ``k`` occupied columns, expected container work
    is ``O(m + k log k)`` and peak snapshot/auxiliary memory is ``O(m + k)``.
    The implementation does not iterate or allocate in proportion to the
    numerical magnitude of substrate width or maximum occupied height.  It
    defines no canonical serialization, digest identity, or persistence API.
    """

    snapshot = _snapshot_state(state)
    nonzero_heights: dict[int, int] = {}
    for x, y in snapshot.occupied:
        height = y + 1
        if height > nonzero_heights.get(x, 0):
            nonzero_heights[x] = height
    nonzero_column_heights = tuple(sorted(nonzero_heights.items()))
    occupied_mass = snapshot.mass
    height_sum = sum(nonzero_heights.values())
    height_square_sum = sum(height * height for height in nonzero_heights.values())
    below_envelope_volume = height_sum
    void_count = below_envelope_volume - occupied_mass
    return ReferenceStatePrimitives(
        width=snapshot.width,
        nonzero_column_heights=nonzero_column_heights,
        occupied_mass=occupied_mass,
        height_sum=height_sum,
        height_square_sum=height_square_sum,
        below_envelope_volume=below_envelope_volume,
        void_count=void_count,
    )
