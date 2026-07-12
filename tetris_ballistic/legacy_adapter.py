"""Explicit compatibility bridge for the legacy 40-state sampler.

The legacy simulator samples a flattened 20 x 2 table: Piece-0..Piece-19,
with nonsticky then sticky state for each piece.  This module gives every
state a stable typed identity without changing the legacy engine or RNG.  Its
sticky column is the pinned ``legacy-sticky-v1`` mechanic, not an assertion of
equivalence to a generic first-contact neighborhood.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .models import (
    GEOMETRY_BY_ID,
    ONE_CELL,
    BoundaryKind,
    ContactKind,
    ContactRule,
    OrientationDistribution,
    PieceEnsemble,
    SimulationConfig,
)

LEGACY_ADAPTER_VERSION = "2.0.0"
MAX_FACTORIZATION_TOLERANCE = 1e-12
_LEGACY_CONTACT_COLUMNS: Mapping[ContactKind, int] = MappingProxyType(
    {
        ContactKind.SUPPORTED: 0,
        ContactKind.LEGACY_STICKY_V1: 1,
    }
)
_LEGACY_CONTACT_KINDS = tuple(_LEGACY_CONTACT_COLUMNS)

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
        if type(self.flat_index) is not int or type(self.piece_id) is not int:
            raise ValueError("legacy indices must be built-in integers")
        if type(self.sticky) is not bool:
            raise ValueError("legacy sticky flag must be a built-in bool")
        if type(self.geometry_id) is not str:
            raise ValueError("legacy geometry ID must be a built-in string")
        if type(self.contact_kind) is not ContactKind:
            raise ValueError("legacy contact kind must be a ContactKind value")
        if not 0 <= self.flat_index < 40:
            raise ValueError("flat_index must be in [0, 39]")
        expected_piece, expected_column = divmod(self.flat_index, 2)
        if self.piece_id != expected_piece or self.sticky != bool(expected_column):
            raise ValueError("flat index, piece ID, and sticky flag disagree")
        if self.geometry_id != LEGACY_PIECE_GEOMETRY_IDS[self.piece_id]:
            raise ValueError("piece ID and geometry ID disagree")
        expected_contact = ContactKind.LEGACY_STICKY_V1 if self.sticky else ContactKind.SUPPORTED
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
        contact_kind=ContactKind.LEGACY_STICKY_V1 if flat_index % 2 else ContactKind.SUPPORTED,
    )
    for flat_index in range(40)
)


def _snapshot_legacy_state(state: object) -> LegacyState:
    if type(state) is not LegacyState:
        raise ValueError("legacy weighted state must contain a LegacyState")
    try:
        return LegacyState(
            flat_index=state.flat_index,
            piece_id=state.piece_id,
            sticky=state.sticky,
            geometry_id=state.geometry_id,
            contact_kind=state.contact_kind,
        )
    except AttributeError as error:
        raise ValueError("legacy state must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class LegacyWeightedState:
    state: LegacyState
    probability: float

    def __post_init__(self) -> None:
        state = _snapshot_legacy_state(self.state)
        if type(self.probability) not in (int, float):
            raise ValueError("legacy probability must be a built-in int or float")
        try:
            probability = float(self.probability)
        except OverflowError as error:
            raise ValueError("legacy probability must be finite and positive") from error
        if not math.isfinite(probability) or probability <= 0:
            raise ValueError("legacy probability must be finite and positive")
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "probability", probability)


@dataclass(frozen=True, slots=True)
class LegacyDistribution:
    """Normalized joint distribution on geometry and legacy contact state."""

    states: tuple[LegacyWeightedState, ...]

    def __post_init__(self) -> None:
        if type(self.states) not in (list, tuple):
            raise ValueError("legacy distribution states must be a plain list or tuple")
        snapshot: list[LegacyWeightedState] = []
        for item in self.states:
            if type(item) is not LegacyWeightedState:
                raise ValueError("legacy distribution entries must be LegacyWeightedState values")
            try:
                state = item.state
                probability = item.probability
            except AttributeError as error:
                raise ValueError("legacy weighted states must be fully initialized") from error
            if type(probability) is not float:
                raise ValueError("legacy distribution probabilities must be canonical built-in floats")
            snapshot.append(LegacyWeightedState(state, probability))
        states = tuple(snapshot)
        object.__setattr__(self, "states", states)
        if not states:
            raise ValueError("legacy distribution must not be empty")
        indices = [item.state.flat_index for item in states]
        if indices != sorted(indices) or len(indices) != len(set(indices)):
            raise ValueError("legacy states must be unique and sorted by flat index")
        probabilities = [item.probability for item in states]
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
    if type(flat_index) is not int or not 0 <= flat_index < 40:
        raise ValueError("flat_index must be an integer in [0, 39]")
    return LEGACY_STATES[flat_index]


def state_for(geometry_id: str, contact_kind: ContactKind | str) -> LegacyState:
    try:
        piece_id = GEOMETRY_ID_TO_LEGACY_PIECE[geometry_id]
    except KeyError as error:
        raise ValueError(f"unknown canonical geometry ID: {geometry_id}") from error
    try:
        contact = ContactKind(contact_kind)
    except (TypeError, ValueError) as error:
        raise ValueError(f"unknown contact kind: {contact_kind!r}") from error
    try:
        legacy_column = _LEGACY_CONTACT_COLUMNS[contact]
    except KeyError as error:
        raise ValueError(f"contact kind {contact.value!r} has no certified legacy mapping") from error
    return legacy_state(2 * piece_id + legacy_column)


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


def distribution_from_simulation_config(config: SimulationConfig) -> LegacyDistribution:
    """Expand independent typed laws into the exactly equivalent legacy joint law.

    The legacy engine implements hard-wall boundaries only. This function is
    deliberately an adapter, not an execution route.
    """

    if config.boundary is not BoundaryKind.HARD_WALL:
        raise ValueError("legacy adapter represents hard-wall configurations only")
    family_weights = dict(config.ensemble.weights)
    orientation_by_family = (
        {family_id: dict(weights) for family_id, weights in config.orientations.by_family}
        if config.orientations is not None
        else {}
    )
    contact_weights = dict(config.contact_rule.weights)
    joint: list[tuple[LegacyState, float]] = []
    for family_id, family_probability in family_weights.items():
        if family_id == ONE_CELL.family_id:
            geometry_weights = {ONE_CELL.id: 1.0}
        else:
            geometry_weights = orientation_by_family[family_id]
        for geometry_id, orientation_probability in geometry_weights.items():
            for contact_kind, contact_probability in contact_weights.items():
                probability = family_probability * orientation_probability * contact_probability
                if probability > 0:
                    joint.append((state_for(geometry_id, contact_kind), probability))
    joint.sort(key=lambda item: item[0].flat_index)
    return LegacyDistribution(tuple(LegacyWeightedState(state, probability) for state, probability in joint))


def density_from_simulation_config(config: SimulationConfig) -> dict[str, list[float]]:
    return density_from_distribution(distribution_from_simulation_config(config))


def simulation_config_from_density(
    density: Mapping[str, object],
    *,
    width: int,
    height: int,
    steps: int,
    root_seed: int,
    factorization_tolerance: float = MAX_FACTORIZATION_TOLERANCE,
) -> SimulationConfig:
    """Factor a legacy joint law into independent typed laws or fail closed.

    A general legacy 20 x 2 table can correlate geometry with contact behavior.
    ``SimulationConfig`` intentionally models contact as independent. Such a
    correlated table is rejected rather than silently approximated.
    """

    if type(factorization_tolerance) not in (int, float):
        raise ValueError("factorization_tolerance must be a built-in int or float")
    normalized_tolerance = float(factorization_tolerance)
    if not math.isfinite(normalized_tolerance) or not 0 <= normalized_tolerance <= MAX_FACTORIZATION_TOLERANCE:
        raise ValueError(f"factorization_tolerance must be finite and between 0 and {MAX_FACTORIZATION_TOLERANCE}")
    distribution = distribution_from_density(density)
    joint = {
        (weighted.state.geometry_id, weighted.state.contact_kind): weighted.probability
        for weighted in distribution.states
    }
    geometry_probabilities = {
        geometry_id: sum(joint.get((geometry_id, contact_kind), 0.0) for contact_kind in _LEGACY_CONTACT_KINDS)
        for geometry_id in GEOMETRY_BY_ID
    }
    contact_probabilities = {
        contact_kind: sum(joint.get((geometry_id, contact_kind), 0.0) for geometry_id in GEOMETRY_BY_ID)
        for contact_kind in _LEGACY_CONTACT_KINDS
    }
    for geometry_id, geometry_probability in geometry_probabilities.items():
        for contact_kind, contact_probability in contact_probabilities.items():
            observed = joint.get((geometry_id, contact_kind), 0.0)
            expected = geometry_probability * contact_probability
            if not math.isclose(
                observed,
                expected,
                rel_tol=normalized_tolerance,
                abs_tol=normalized_tolerance,
            ):
                raise ValueError(
                    "legacy geometry/contact weights are correlated and cannot be represented by independent typed laws"
                )

    family_probabilities: dict[str, float] = {}
    orientation_weights: dict[str, dict[str, float]] = {}
    for geometry_id, probability in geometry_probabilities.items():
        if probability <= 0:
            continue
        family_id = GEOMETRY_BY_ID[geometry_id].family_id
        family_probabilities[family_id] = family_probabilities.get(family_id, 0.0) + probability
        if family_id != ONE_CELL.family_id:
            orientation_weights.setdefault(family_id, {})[geometry_id] = probability
    for family_id, weights in orientation_weights.items():
        family_probability = family_probabilities[family_id]
        orientation_weights[family_id] = {
            geometry_id: probability / family_probability for geometry_id, probability in weights.items()
        }

    ensemble = PieceEnsemble.from_weights(family_probabilities)
    orientations = OrientationDistribution.from_weights(orientation_weights) if orientation_weights else None
    contact_rule = ContactRule.from_weights(
        {contact_kind: probability for contact_kind, probability in contact_probabilities.items() if probability > 0}
    )
    return SimulationConfig(
        width=width,
        height=height,
        steps=steps,
        root_seed=root_seed,
        ensemble=ensemble,
        orientations=orientations,
        contact_rule=contact_rule,
        boundary=BoundaryKind.HARD_WALL,
    )
