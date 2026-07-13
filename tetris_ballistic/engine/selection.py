"""Exact stateless law records and one-stream semantic selection.

This provisional S2.3 layer binds ordered semantic outcome IDs to canonical
integer counts.  Each one-stream selection is checked against an explicit
declared stream-set record and evaluated through the S2.2 counter-addressed
RNG oracle.

This module deliberately does not resolve conditional laws, consume a complete
event schedule, name a model law, compose a placement, run a trajectory, adapt
legacy configuration, define serialization identity, schedule work, or expose
a production execution route.

The generator is a scientific reproducibility primitive, not a cryptographic
random-number generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd

from . import rng as semantic_rng
from .rng import SemanticDraw

_U64_MODULUS = 1 << 64
_U64_MAX = _U64_MODULUS - 1
_U128_MAX = (1 << 128) - 1
_U32_MAX = (1 << 32) - 1


def _require_plain_uint(value: object, *, maximum: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return value


def _snapshot_utf8_text(value: object, *, label: str, length_framed: bool) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    if not value:
        raise ValueError(f"{label} must be nonempty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must be valid UTF-8 text") from error
    if length_framed and len(encoded) > _U32_MAX:
        raise ValueError(f"{label} UTF-8 encoding is too long")
    return value


def _snapshot_counts(counts: object) -> tuple[int, ...]:
    if type(counts) not in (list, tuple):
        raise TypeError("weighted-law counts must be a plain list or tuple")
    if not counts:
        raise ValueError("weighted-law counts must not be empty")

    snapshot: list[int] = []
    total = 0
    common_divisor = 0
    for index, count in enumerate(counts):
        if type(count) is not int:
            raise TypeError(f"weighted-law count {index} must be a built-in integer")
        if count < 0:
            raise ValueError(f"weighted-law count {index} must be nonnegative")
        total += count
        if total > _U64_MODULUS:
            raise ValueError("weighted-law count sum must not exceed 2**64")
        if count:
            common_divisor = gcd(common_divisor, count)
        snapshot.append(count)

    if total == 0:
        raise ValueError("weighted-law counts must contain a positive count")
    if common_divisor != 1:
        raise ValueError("positive weighted-law counts must have greatest common divisor one")
    return tuple(snapshot)


@dataclass(frozen=True, slots=True)
class ExactWeightedLaw:
    """An ordered semantic-outcome vector and canonical exact counts.

    Order and zero-count positions are part of the record.  No sorting,
    normalization, floating-point conversion, or removal of zero slots occurs.
    """

    outcome_ids: tuple[str, ...]
    counts: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.outcome_ids) not in (list, tuple):
            raise TypeError("weighted-law outcome IDs must be a plain list or tuple")
        outcomes = tuple(
            _snapshot_utf8_text(value, label=f"weighted-law outcome ID {index}", length_framed=False)
            for index, value in enumerate(self.outcome_ids)
        )
        if not outcomes:
            raise ValueError("weighted-law outcome IDs must not be empty")
        if len(set(outcomes)) != len(outcomes):
            raise ValueError("weighted-law outcome IDs must be unique")
        counts = _snapshot_counts(self.counts)
        if len(outcomes) != len(counts):
            raise ValueError("weighted-law outcome IDs and counts must have equal length")
        object.__setattr__(self, "outcome_ids", outcomes)
        object.__setattr__(self, "counts", counts)

    @property
    def total_count(self) -> int:
        """Return the exact positive count total."""

        return sum(self.counts)

    @property
    def positive_outcome_ids(self) -> tuple[str, ...]:
        """Return positive-support outcome IDs in their normative order."""

        return tuple(outcome_id for outcome_id, count in zip(self.outcome_ids, self.counts) if count)


@dataclass(frozen=True, slots=True)
class UniformIntegerLaw:
    """An exact uniform law on ``range(upper_bound)``."""

    upper_bound: int

    def __post_init__(self) -> None:
        if type(self.upper_bound) is not int:
            raise TypeError("uniform-integer upper bound must be a built-in integer")
        if not 1 <= self.upper_bound <= _U64_MODULUS:
            raise ValueError("uniform-integer upper bound must lie in [1, 2**64]")


@dataclass(frozen=True, slots=True)
class DeclaredStreamSet:
    """A complete ordered per-law stream-name record.

    This record declares membership and order.  The one-stream selectors below
    do not claim that a complete event schedule has been consumed.
    """

    stream_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.stream_names) not in (list, tuple):
            raise TypeError("declared stream names must be a plain list or tuple")
        names = tuple(
            _snapshot_utf8_text(value, label=f"declared stream name {index}", length_framed=True)
            for index, value in enumerate(self.stream_names)
        )
        if not names:
            raise ValueError("declared stream set must not be empty")
        if len(set(names)) != len(names):
            raise ValueError("declared stream names must be unique")
        object.__setattr__(self, "stream_names", names)


@dataclass(frozen=True, slots=True)
class WeightedSelection:
    """One selected semantic outcome and its complete categorical draw.

    This is an immutable value record, not a standalone authenticated artifact:
    it does not bind the request address or law. The semantic guarantee applies
    to records returned by :func:`select_weighted` with the certified in-package
    S2.2 oracle.
    """

    stream_name: str
    outcome_id: str
    draw: SemanticDraw

    def __post_init__(self) -> None:
        stream_name = _snapshot_utf8_text(self.stream_name, label="stream name", length_framed=True)
        outcome = _snapshot_utf8_text(self.outcome_id, label="selected outcome ID", length_framed=False)
        if type(self.draw) is not SemanticDraw:
            raise TypeError("weighted selection draw must be a SemanticDraw")
        try:
            draw = SemanticDraw(self.draw.value, self.draw.accepted_rejection_ordinal)
        except AttributeError as error:
            raise TypeError("weighted selection draw must be fully initialized") from error
        object.__setattr__(self, "stream_name", stream_name)
        object.__setattr__(self, "outcome_id", outcome)
        object.__setattr__(self, "draw", draw)

    @property
    def selected_index(self) -> int:
        """Return the normative outcome index selected by the draw."""

        return self.draw.value


@dataclass(frozen=True, slots=True)
class UniformSelection:
    """One selected uniform integer and its complete bounded draw.

    This is an immutable value record, not a standalone authenticated artifact:
    it does not bind the request address or law. The semantic guarantee applies
    to records returned by :func:`select_uniform` with the certified in-package
    S2.2 oracle.
    """

    stream_name: str
    draw: SemanticDraw

    def __post_init__(self) -> None:
        stream_name = _snapshot_utf8_text(self.stream_name, label="stream name", length_framed=True)
        if type(self.draw) is not SemanticDraw:
            raise TypeError("uniform selection draw must be a SemanticDraw")
        try:
            draw = SemanticDraw(self.draw.value, self.draw.accepted_rejection_ordinal)
        except AttributeError as error:
            raise TypeError("uniform selection draw must be fully initialized") from error
        object.__setattr__(self, "stream_name", stream_name)
        object.__setattr__(self, "draw", draw)

    @property
    def value(self) -> int:
        """Return the selected integer."""

        return self.draw.value


def _snapshot_stream_set(value: object) -> DeclaredStreamSet:
    if type(value) is not DeclaredStreamSet:
        raise TypeError("stream_set must be a DeclaredStreamSet")
    try:
        return DeclaredStreamSet(value.stream_names)
    except AttributeError as error:
        raise TypeError("stream_set must be fully initialized") from error


def _snapshot_weighted_law(value: object) -> ExactWeightedLaw:
    if type(value) is not ExactWeightedLaw:
        raise TypeError("law must be an ExactWeightedLaw")
    try:
        return ExactWeightedLaw(value.outcome_ids, value.counts)
    except AttributeError as error:
        raise TypeError("law must be fully initialized") from error


def _snapshot_uniform_law(value: object) -> UniformIntegerLaw:
    if type(value) is not UniformIntegerLaw:
        raise TypeError("law must be a UniformIntegerLaw")
    try:
        return UniformIntegerLaw(value.upper_bound)
    except AttributeError as error:
        raise TypeError("law must be fully initialized") from error


def _snapshot_address(
    *,
    root_seed: object,
    coupling_group_id: object,
    event_ordinal: object,
) -> tuple[int, str, int]:
    root = _require_plain_uint(root_seed, maximum=_U128_MAX, label="root seed")
    group = _snapshot_utf8_text(coupling_group_id, label="coupling group ID", length_framed=True)
    event = _require_plain_uint(event_ordinal, maximum=_U64_MAX, label="event ordinal")
    return root, group, event


def _require_declared(stream_set: DeclaredStreamSet, *, stream_name: str) -> None:
    if stream_name not in stream_set.stream_names:
        raise ValueError(f"stream {stream_name!r} is not present in the declared stream set")


def _snapshot_delegated_draw(value: object, *, label: str) -> SemanticDraw:
    if type(value) is not SemanticDraw:
        raise AssertionError(f"{label} RNG returned a non-SemanticDraw result")
    try:
        return SemanticDraw(value.value, value.accepted_rejection_ordinal)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError(f"{label} RNG returned a malformed SemanticDraw") from error


def select_weighted(
    *,
    root_seed: int,
    coupling_group_id: str,
    event_ordinal: int,
    declared_streams: DeclaredStreamSet,
    stream_name: str,
    law: ExactWeightedLaw,
) -> WeightedSelection:
    """Select one exact semantic outcome from one declared named stream.

    The full address, stream record, and law record are validated before the
    RNG call.  Order and zero slots remain exactly as supplied by ``law``.
    """

    root, group, event = _snapshot_address(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        event_ordinal=event_ordinal,
    )
    declared = _snapshot_stream_set(declared_streams)
    stream = _snapshot_utf8_text(stream_name, label="stream name", length_framed=True)
    weighted_law = _snapshot_weighted_law(law)
    _require_declared(declared, stream_name=stream)
    draw = _snapshot_delegated_draw(
        semantic_rng.categorical_index(
            root_seed=root,
            coupling_group_id=group,
            stream_name=stream,
            event_ordinal=event,
            counts=weighted_law.counts,
        ),
        label="categorical",
    )
    if draw.value >= len(weighted_law.outcome_ids) or weighted_law.counts[draw.value] == 0:
        raise AssertionError("categorical RNG returned an invalid draw for the weighted law")
    return WeightedSelection(
        stream_name=stream,
        outcome_id=weighted_law.outcome_ids[draw.value],
        draw=draw,
    )


def select_uniform(
    *,
    root_seed: int,
    coupling_group_id: str,
    event_ordinal: int,
    declared_streams: DeclaredStreamSet,
    stream_name: str,
    law: UniformIntegerLaw,
) -> UniformSelection:
    """Select one exact bounded integer from one declared named stream."""

    root, group, event = _snapshot_address(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        event_ordinal=event_ordinal,
    )
    declared = _snapshot_stream_set(declared_streams)
    stream = _snapshot_utf8_text(stream_name, label="stream name", length_framed=True)
    uniform_law = _snapshot_uniform_law(law)
    _require_declared(declared, stream_name=stream)
    draw = _snapshot_delegated_draw(
        semantic_rng.uniform_below(
            root_seed=root,
            coupling_group_id=group,
            stream_name=stream,
            event_ordinal=event,
            n=uniform_law.upper_bound,
        ),
        label="bounded",
    )
    if draw.value >= uniform_law.upper_bound:
        raise AssertionError("bounded RNG returned an invalid draw for the uniform law")
    return UniformSelection(stream_name=stream, draw=draw)


__all__ = [
    "DeclaredStreamSet",
    "ExactWeightedLaw",
    "UniformIntegerLaw",
    "UniformSelection",
    "WeightedSelection",
    "select_uniform",
    "select_weighted",
]
