"""Typed, canonical model contracts for the community API.

This module is additive during the 2.1 compatibility series.  It does not
change the behavior of :class:`Tetris_Ballistic`; adapters will be introduced
only after golden-equivalence tests exist.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Iterable, Mapping

Coordinate = tuple[int, int]
WeightItems = tuple[tuple[str, float], ...]
MODEL_SCHEMA_VERSION = "1.0.0"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _identity(value: object) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def normalize_coordinates(coordinates: Iterable[Coordinate]) -> tuple[Coordinate, ...]:
    points = tuple(coordinates)
    if not points:
        raise ValueError("geometry must contain at least one occupied coordinate")
    if any(not isinstance(row, int) or not isinstance(column, int) for row, column in points):
        raise TypeError("geometry coordinates must be integer pairs")
    min_row = min(row for row, _ in points)
    min_column = min(column for _, column in points)
    normalized = tuple(sorted({(row - min_row, column - min_column) for row, column in points}))
    if len(normalized) != len(points):
        raise ValueError("geometry coordinates must be duplicate-free")
    return normalized


def _is_edge_connected(coordinates: tuple[Coordinate, ...]) -> bool:
    remaining = set(coordinates)
    frontier = {remaining.pop()}
    visited = set(frontier)
    while frontier:
        row, column = frontier.pop()
        for neighbor in ((row - 1, column), (row + 1, column), (row, column - 1), (row, column + 1)):
            if neighbor in remaining:
                remaining.remove(neighbor)
                frontier.add(neighbor)
                visited.add(neighbor)
    return len(visited) == len(coordinates)


@dataclass(frozen=True, slots=True)
class PieceGeometry:
    """An immutable occupied-cell geometry in canonical local coordinates."""

    id: str
    family_id: str
    coordinates: tuple[Coordinate, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.family_id:
            raise ValueError("geometry and family IDs must be nonempty")
        normalized = normalize_coordinates(self.coordinates)
        if normalized != self.coordinates:
            raise ValueError("geometry coordinates must already be canonical")
        if not _is_edge_connected(normalized):
            raise ValueError("geometry must be edge-connected")

    @property
    def area(self) -> int:
        return len(self.coordinates)

    @property
    def height(self) -> int:
        return max(row for row, _ in self.coordinates) + 1

    @property
    def width(self) -> int:
        return max(column for _, column in self.coordinates) + 1

    def canonical_record(self) -> dict[str, object]:
        return {
            "area": self.area,
            "coordinates": [list(point) for point in self.coordinates],
            "family_id": self.family_id,
            "height": self.height,
            "id": self.id,
            "width": self.width,
        }

    @property
    def sha256(self) -> str:
        return _identity(self.canonical_record())


def _dihedral_orientations(coordinates: Iterable[Coordinate]) -> tuple[tuple[Coordinate, ...], ...]:
    current = tuple(coordinates)
    variants: set[tuple[Coordinate, ...]] = set()
    for reflected in (False, True):
        for rotations in range(4):
            transformed = []
            for row, column in current:
                if reflected:
                    column = -column
                for _ in range(rotations):
                    row, column = column, -row
                transformed.append((row, column))
            variants.add(normalize_coordinates(transformed))
    return tuple(sorted(variants))


def _family_orientations(family_id: str, base: tuple[Coordinate, ...]) -> tuple[PieceGeometry, ...]:
    return tuple(
        PieceGeometry(
            id=f"tetromino.{family_id}.{index:02d}",
            family_id=family_id,
            coordinates=coordinates,
        )
        for index, coordinates in enumerate(_dihedral_orientations(base))
    )


_FAMILY_BASES: dict[str, tuple[Coordinate, ...]] = {
    "i": ((0, 0), (0, 1), (0, 2), (0, 3)),
    "lj": ((0, 0), (1, 0), (2, 0), (2, 1)),
    "o": ((0, 0), (0, 1), (1, 0), (1, 1)),
    "sz": ((0, 1), (0, 2), (1, 0), (1, 1)),
    "t": ((0, 0), (0, 1), (0, 2), (1, 1)),
}

TETROMINO_REGISTRY: tuple[PieceGeometry, ...] = tuple(
    geometry
    for family_id in sorted(_FAMILY_BASES)
    for geometry in _family_orientations(family_id, _FAMILY_BASES[family_id])
)
ONE_CELL = PieceGeometry(id="baseline.one-cell", family_id="one-cell", coordinates=((0, 0),))
GEOMETRY_BY_ID: Mapping[str, PieceGeometry] = MappingProxyType(
    {geometry.id: geometry for geometry in (*TETROMINO_REGISTRY, ONE_CELL)}
)
FAMILY_ORIENTATION_IDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        family_id: tuple(geometry.id for geometry in TETROMINO_REGISTRY if geometry.family_id == family_id)
        for family_id in sorted(_FAMILY_BASES)
    }
)


def _normalize_weights(weights: Mapping[str, float], *, allowed: set[str], label: str) -> WeightItems:
    if not weights:
        raise ValueError(f"{label} weights must not be empty")
    unknown = set(weights) - allowed
    if unknown:
        raise ValueError(f"unknown {label} IDs: {sorted(unknown)}")
    converted: list[tuple[str, float]] = []
    for key, raw_value in weights.items():
        value = float(raw_value)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{label} weights must be finite and nonnegative")
        converted.append((key, value))
    total = sum(value for _, value in converted)
    if not math.isfinite(total) or total <= 0:
        raise ValueError(f"{label} weights must have positive finite total")
    return tuple(sorted((key, value / total) for key, value in converted if value > 0))


def _validate_normalized_items(items: WeightItems, *, allowed: set[str], label: str) -> None:
    if not items:
        raise ValueError(f"{label} weights must not be empty")
    keys = [key for key, _ in items]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{label} weights must have unique, sorted IDs")
    unknown = set(keys) - allowed
    if unknown:
        raise ValueError(f"unknown {label} IDs: {sorted(unknown)}")
    values = [value for _, value in items]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError(f"{label} weights must be finite and positive")
    if not math.isclose(sum(values), 1.0, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError(f"{label} weights must sum to one")


@dataclass(frozen=True, slots=True)
class PieceEnsemble:
    """Probability distribution on free-family IDs or the one-cell baseline."""

    weights: WeightItems

    def __post_init__(self) -> None:
        _validate_normalized_items(
            self.weights,
            allowed=set(FAMILY_ORIENTATION_IDS) | {ONE_CELL.family_id},
            label="family",
        )

    @classmethod
    def from_weights(cls, weights: Mapping[str, float]) -> "PieceEnsemble":
        allowed = set(FAMILY_ORIENTATION_IDS) | {ONE_CELL.family_id}
        return cls(_normalize_weights(weights, allowed=allowed, label="family"))

    @classmethod
    def pure(cls, family_id: str) -> "PieceEnsemble":
        return cls.from_weights({family_id: 1.0})

    @classmethod
    def equal_free_families(cls) -> "PieceEnsemble":
        return cls.from_weights({family_id: 1.0 for family_id in FAMILY_ORIENTATION_IDS})

    def canonical_record(self) -> dict[str, object]:
        return {"weights": {key: value for key, value in self.weights}}


@dataclass(frozen=True, slots=True)
class OrientationDistribution:
    """Conditional orientation probabilities for each selected family."""

    by_family: tuple[tuple[str, WeightItems], ...]

    def __post_init__(self) -> None:
        family_ids = [family_id for family_id, _ in self.by_family]
        if not family_ids or family_ids != sorted(family_ids) or len(family_ids) != len(set(family_ids)):
            raise ValueError("orientation families must be nonempty, unique, and sorted")
        for family_id, weights in self.by_family:
            if family_id not in FAMILY_ORIENTATION_IDS:
                raise ValueError(f"unknown orientation family: {family_id}")
            _validate_normalized_items(
                weights,
                allowed=set(FAMILY_ORIENTATION_IDS[family_id]),
                label=f"orientation for {family_id}",
            )

    @classmethod
    def isotropic(cls, families: Iterable[str] | None = None) -> "OrientationDistribution":
        selected = tuple(sorted(families if families is not None else FAMILY_ORIENTATION_IDS))
        return cls.from_weights(
            {
                family_id: {geometry_id: 1.0 for geometry_id in FAMILY_ORIENTATION_IDS[family_id]}
                for family_id in selected
            }
        )

    @classmethod
    def from_weights(cls, weights: Mapping[str, Mapping[str, float]]) -> "OrientationDistribution":
        unknown_families = set(weights) - set(FAMILY_ORIENTATION_IDS)
        if unknown_families:
            raise ValueError(f"unknown orientation families: {sorted(unknown_families)}")
        if not weights:
            raise ValueError("orientation distribution must not be empty")
        normalized = []
        for family_id, family_weights in weights.items():
            items = _normalize_weights(
                family_weights,
                allowed=set(FAMILY_ORIENTATION_IDS[family_id]),
                label=f"orientation for {family_id}",
            )
            normalized.append((family_id, items))
        return cls(tuple(sorted(normalized)))

    def canonical_record(self) -> dict[str, object]:
        return {
            "by_family": {
                family_id: {geometry_id: value for geometry_id, value in weights}
                for family_id, weights in self.by_family
            }
        }


class ContactKind(str, Enum):
    SUPPORTED = "supported"
    FIRST_CONTACT = "first-contact"


@dataclass(frozen=True, slots=True)
class ContactRule:
    """Probability distribution on explicit placement mechanics."""

    weights: tuple[tuple[ContactKind, float], ...]

    def __post_init__(self) -> None:
        string_items = tuple((key.value, value) for key, value in self.weights)
        _validate_normalized_items(
            string_items,
            allowed={kind.value for kind in ContactKind},
            label="contact-rule",
        )

    @classmethod
    def from_weights(cls, weights: Mapping[ContactKind | str, float]) -> "ContactRule":
        converted = {ContactKind(key).value: value for key, value in weights.items()}
        normalized = _normalize_weights(
            converted,
            allowed={kind.value for kind in ContactKind},
            label="contact-rule",
        )
        return cls(tuple((ContactKind(key), value) for key, value in normalized))

    @classmethod
    def supported(cls) -> "ContactRule":
        return cls.from_weights({ContactKind.SUPPORTED: 1.0})

    @classmethod
    def first_contact(cls) -> "ContactRule":
        return cls.from_weights({ContactKind.FIRST_CONTACT: 1.0})

    def canonical_record(self) -> dict[str, object]:
        return {"weights": {key.value: value for key, value in self.weights}}


class ClockKind(str, Enum):
    EVENT_COUNT = "event-count"
    ATTEMPTS_PER_SITE = "attempts-per-site"
    DEPOSITED_MASS_PER_WIDTH = "deposited-mass-per-width"
    MEAN_INTERFACE_HEIGHT = "mean-interface-height"


class BoundaryKind(str, Enum):
    HARD_WALL = "hard-wall"
    PERIODIC = "periodic"


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Minimal canonical M1 configuration identity.

    Engine/checkpoint/output fields will be extended in later M1 milestones under
    a schema-version bump; this object intentionally does not run the legacy
    simulator yet.
    """

    width: int
    height: int
    steps: int
    root_seed: int
    ensemble: PieceEnsemble
    orientations: OrientationDistribution | None
    contact_rule: ContactRule
    boundary: BoundaryKind = BoundaryKind.HARD_WALL
    schema_version: str = MODEL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or self.steps <= 0:
            raise ValueError("width, height, and steps must be positive")
        selected_families = {family_id for family_id, _ in self.ensemble.weights}
        tetromino_families = selected_families - {ONE_CELL.family_id}
        orientation_families = (
            {family_id for family_id, _ in self.orientations.by_family} if self.orientations is not None else set()
        )
        if tetromino_families != orientation_families:
            raise ValueError("orientation families must exactly match selected tetromino families")

    def canonical_record(self) -> dict[str, object]:
        return {
            "contact_rule": self.contact_rule.canonical_record(),
            "ensemble": self.ensemble.canonical_record(),
            "height": self.height,
            "orientations": self.orientations.canonical_record() if self.orientations else None,
            "boundary": self.boundary.value,
            "root_seed": self.root_seed,
            "schema_version": self.schema_version,
            "steps": self.steps,
            "width": self.width,
        }

    @property
    def sha256(self) -> str:
        return _identity(self.canonical_record())

    def to_json(self) -> str:
        return _canonical_json(self.canonical_record()).decode("utf-8")
