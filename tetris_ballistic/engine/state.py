"""Immutable sparse state for the slow periodic reference engine."""

from __future__ import annotations

from dataclasses import dataclass

WorldCell = tuple[int, int]
_PLAIN_CELL_COLLECTIONS = (list, tuple, set, frozenset)


def _snapshot_world_cells(cells: object) -> frozenset[WorldCell]:
    if type(cells) not in _PLAIN_CELL_COLLECTIONS:
        raise TypeError("occupied cells must be a plain list, tuple, set, or frozenset")

    snapshot: list[WorldCell] = []
    for point in cells:
        if type(point) not in (list, tuple) or len(point) != 2:
            raise TypeError("occupied cells must contain plain integer (x, y) pairs")
        x, y = point
        if type(x) is not int or type(y) is not int:
            raise TypeError("occupied cells must contain integer (x, y) pairs")
        snapshot.append((x, y))

    if len(set(snapshot)) != len(snapshot):
        raise ValueError("occupied cells must be duplicate-free")
    return frozenset(snapshot)


@dataclass(frozen=True, slots=True)
class SparseAggregate:
    """A finite occupancy snapshot on a periodic, upward-unbounded lattice.

    Cells use public-world ``(x, y)`` coordinates.  The state deliberately
    accepts finite snapshots that need not be reachable by deposition so it
    can serve as an exhaustive transition oracle.
    """

    width: int
    occupied: frozenset[WorldCell]

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 3:
            raise ValueError("width must be a built-in integer at least 3")
        occupied = _snapshot_world_cells(self.occupied)
        if any(not 0 <= x < self.width for x, _ in occupied):
            raise ValueError("occupied x coordinates must lie in [0, width)")
        if any(y < 0 for _, y in occupied):
            raise ValueError("occupied y coordinates must be nonnegative")
        object.__setattr__(self, "occupied", occupied)

    @classmethod
    def empty(cls, width: int) -> "SparseAggregate":
        """Construct the empty aggregate of a validated periodic width."""

        return cls(width=width, occupied=frozenset())

    @property
    def mass(self) -> int:
        """Return the exact occupied-cell count."""

        return len(self.occupied)
