"""Explicit compatibility bridge for the legacy 40-state sampler.

The legacy simulator samples a flattened 20 x 2 table: Piece-0..Piece-19,
with nonsticky then sticky state for each piece.  This module gives every
state a stable typed identity without changing the legacy engine or RNG.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .models import GEOMETRY_BY_ID, ContactKind

LEGACY_ADAPTER_VERSION = "1.0.0"

# Verified by depositing each legacy Piece-N once on an empty hard-wall
# substrate, normalizing its occupied coordinates, and matching those
# coordinates against the canonical registry.
LEGACY_PIECE_GEOMETRY_IDS: tuple[str, ...] = (
    "tetromino.o.00",
    "tetromino.i.00",
    "tetromino.i.01",
    "tetromino.lj.05",
    "tetromino.lj.07",
    "tetromino.lj.03",
    "tetromino.lj.00",
    "tetromino.lj.06",
    "tetromino.lj.01",
    "tetromino.lj.02",
    "tetromino.lj.04",
    "tetromino.t.00",
    "tetromino.t.01",
    "tetromino.t.02",
    "tetromino.t.03",
    "tetromino.sz.02",
    "tetromino.sz.01",
    "tetromino.sz.00",
    "tetromino.sz.03",
    "baseline.one-cell",
)

if len(LEGACY_PIECE_GEOMETRY_IDS) != 20 or len(set(LEGACY_PIECE_GEOMETRY_IDS)) != 20:
    raise RuntimeError("legacy piece map must be a bijection onto 20 geometry IDs")
if set(LEGACY_PIECE_GEOMETRY_IDS) != set(GEOMETRY_BY_ID):
    raise RuntimeError("legacy piece map and canonical geometry registry disagree")

GEOMETRY_ID_TO_LEGACY_PIECE: Mapping[str, int] = MappingProxyType(
    {geometry_id: piece_id for piece_id, geometry_id in enumerate(LEGACY_PIECE_GEOMETRY_IDS)}
)


@dataclass(frozen=True, slots=True)
class LegacyState:
    """One exact entry in the flattened legacy sampling table."""

    flat_index: int
    piece_id: int
    sticky: bool
    geometry_id: str
    contact_kind: ContactKind

    def __post_init__(self) -> None:
        if not 0 <= self.flat_index < 40:
            raise ValueError("flat_index must be in [0, 39]")
        expected_piece, expected_column = divmod(self.flat_index, 2)
        if self.piece_id != expected_piece or self.sticky != bool(expected_column):
            raise ValueError("flat index, piece ID, and sticky flag disagree")
        if self.geometry_id != LEGACY_PIECE_GEOMETRY_IDS[self.piece_id]:
            raise ValueError("piece ID and geometry ID disagree")
        expected_contact = ContactKind.FIRST_CONTACT if self.sticky else ContactKind.SUPPORTED
        if self.contact_kind is not expected_contact:
            raise ValueError("sticky flag and contact kind disagree")

    @property
    def legacy_key(self) -> str:
        return f"Piece-{self.piece_id}"

    @property
    def legacy_column(self) -> int:
        return int(self.sticky)

    def canonical_record(self) -> dict[str, object]:
        return {
            "adapter_version": LEGACY_ADAPTER_VERSION,
            "contact_kind": self.contact_kind.value,
            "flat_index": self.flat_index,
            "geometry_id": self.geometry_id,
            "legacy_column": self.legacy_column,
            "legacy_key": self.legacy_key,
            "piece_id": self.piece_id,
            "sticky": self.sticky,
        }


LEGACY_STATES: tuple[LegacyState, ...] = tuple(
    LegacyState(
        flat_index=flat_index,
        piece_id=flat_index // 2,
        sticky=bool(flat_index % 2),
        geometry_id=LEGACY_PIECE_GEOMETRY_IDS[flat_index // 2],
        contact_kind=ContactKind.FIRST_CONTACT if flat_index % 2 else ContactKind.SUPPORTED,
    )
    for flat_index in range(40)
)


@dataclass(frozen=True, slots=True)
class LegacyWeightedState:
    state: LegacyState
    probability: float


@dataclass(frozen=True, slots=True)
class LegacyDistribution:
    """Normalized joint distribution on geometry and legacy contact state."""

    states: tuple[LegacyWeightedState, ...]

    def __post_init__(self) -> None:
        if not self.states:
            raise ValueError("legacy distribution must not be empty")
        indices = [item.state.flat_index for item in self.states]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("legacy states must be unique and sorted by flat index")
        probabilities = [item.probability for item in self.states]
        if any(not math.isfinite(value) or value <= 0 for value in probabilities):
            raise ValueError("legacy probabilities must be finite and positive")
        if not math.isclose(sum(probabilities), 1.0, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("legacy probabilities must sum to one")

    def canonical_record(self) -> dict[str, object]:
        return {
            "adapter_version": LEGACY_ADAPTER_VERSION,
            "states": [{**item.state.canonical_record(), "probability": item.probability} for item in self.states],
        }


def legacy_state(flat_index: int) -> LegacyState:
    if not isinstance(flat_index, int) or not 0 <= flat_index < 40:
        raise ValueError("flat_index must be an integer in [0, 39]")
    return LEGACY_STATES[flat_index]


def state_for(geometry_id: str, contact_kind: ContactKind | str) -> LegacyState:
    try:
        piece_id = GEOMETRY_ID_TO_LEGACY_PIECE[geometry_id]
    except KeyError as error:
        raise ValueError(f"unknown canonical geometry ID: {geometry_id}") from error
    contact = ContactKind(contact_kind)
    sticky = contact is ContactKind.FIRST_CONTACT
    return legacy_state(2 * piece_id + int(sticky))


def distribution_from_density(density: Mapping[str, object]) -> LegacyDistribution:
    """Validate and normalize a legacy ``Piece-N: [nonsticky, sticky]`` map."""

    expected = {f"Piece-{piece_id}" for piece_id in range(20)}
    supplied = {key for key in density if key.startswith("Piece-")}
    missing = expected - supplied
    unknown = supplied - expected
    if missing or unknown:
        raise ValueError(f"legacy density keys mismatch: missing={sorted(missing)}, unknown={sorted(unknown)}")

    weighted: list[tuple[LegacyState, float]] = []
    for piece_id in range(20):
        raw_pair = density[f"Piece-{piece_id}"]
        if not isinstance(raw_pair, (list, tuple)) or len(raw_pair) != 2:
            raise ValueError(f"Piece-{piece_id} must contain [nonsticky, sticky]")
        for column, raw_value in enumerate(raw_pair):
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Piece-{piece_id} weights must be numeric") from error
            if not math.isfinite(value) or value < 0:
                raise ValueError("legacy density weights must be finite and nonnegative")
            if value > 0:
                weighted.append((legacy_state(2 * piece_id + column), value))

    total = sum(value for _, value in weighted)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("legacy density must have positive finite total")
    return LegacyDistribution(tuple(LegacyWeightedState(state, value / total) for state, value in weighted))


def density_from_distribution(distribution: LegacyDistribution) -> dict[str, list[float]]:
    """Return a 20 x 2 legacy density table with normalized floating weights."""

    density = {f"Piece-{piece_id}": [0.0, 0.0] for piece_id in range(20)}
    for weighted in distribution.states:
        density[weighted.state.legacy_key][weighted.state.legacy_column] = weighted.probability
    return density
