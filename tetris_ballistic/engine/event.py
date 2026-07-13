"""Named conditional complete-event selection for the slow reference engine.

This provisional S2.4 module composes the certified S2.2/S2.3 primitives into
one exact tetromino event-selection record.  It fixes the canonical family,
contact, and stream orders; validates the complete per-family orientation table
before any RNG use; and evaluates exactly one logical draw from ``family``,
``orientation``, ``launch``, and ``contact`` in that order.

The module is deliberately available only by explicit submodule import.  It
does not place a piece, execute ``SimulationConfig``, run a trajectory, adapt a
legacy law, serialize an artifact, schedule work, or expose a production path.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import FAMILY_ORIENTATION_IDS
from .selection import (
    DeclaredStreamSet,
    ExactWeightedLaw,
    UniformIntegerLaw,
    UniformSelection,
    WeightedSelection,
    select_uniform,
    select_weighted,
)

_RATIFIED_FAMILY_ORDER = ("i", "lj", "o", "sz", "t")
_RATIFIED_CONTACT_ORDER = ("supported-v1", "edge-first-contact-v1")
_RATIFIED_ORIENTATION_ORDERS = (
    ("i", ("tetromino.i.00", "tetromino.i.01")),
    (
        "lj",
        (
            "tetromino.lj.00",
            "tetromino.lj.01",
            "tetromino.lj.02",
            "tetromino.lj.03",
            "tetromino.lj.04",
            "tetromino.lj.05",
            "tetromino.lj.06",
            "tetromino.lj.07",
        ),
    ),
    ("o", ("tetromino.o.00",)),
    (
        "sz",
        (
            "tetromino.sz.00",
            "tetromino.sz.01",
            "tetromino.sz.02",
            "tetromino.sz.03",
        ),
    ),
    (
        "t",
        (
            "tetromino.t.00",
            "tetromino.t.01",
            "tetromino.t.02",
            "tetromino.t.03",
        ),
    ),
)

TETROMINO_FAMILY_ORDER = _RATIFIED_FAMILY_ORDER
TETROMINO_CONTACT_ORDER = _RATIFIED_CONTACT_ORDER
_TETROMINO_STREAM_NAMES = ("family", "orientation", "launch", "contact")
TETROMINO_STREAM_SET = DeclaredStreamSet(_TETROMINO_STREAM_NAMES)

_U64_MAX = (1 << 64) - 1
_U128_MAX = (1 << 128) - 1
_U32_MAX = (1 << 32) - 1


def _assert_ratified_order_integrity() -> None:
    family_order = TETROMINO_FAMILY_ORDER
    if (
        type(family_order) is not tuple
        or family_order != _RATIFIED_FAMILY_ORDER
        or any(type(value) is not str for value in family_order)
    ):
        raise AssertionError("TETROMINO_FAMILY_ORDER does not match the ratified order")

    contact_order = TETROMINO_CONTACT_ORDER
    if (
        type(contact_order) is not tuple
        or contact_order != _RATIFIED_CONTACT_ORDER
        or any(type(value) is not str for value in contact_order)
    ):
        raise AssertionError("TETROMINO_CONTACT_ORDER does not match the ratified order")

    try:
        registry_orders = tuple(FAMILY_ORIENTATION_IDS.items())
    except (AttributeError, TypeError) as error:
        raise AssertionError("FAMILY_ORIENTATION_IDS is malformed") from error
    if registry_orders != _RATIFIED_ORIENTATION_ORDERS or any(
        type(family_id) is not str
        or type(orientation_ids) is not tuple
        or any(type(orientation_id) is not str for orientation_id in orientation_ids)
        for family_id, orientation_ids in registry_orders
    ):
        raise AssertionError("FAMILY_ORIENTATION_IDS does not match the ratified orders")


def _ratified_orientation_order(family_id: str) -> tuple[str, ...]:
    for candidate_family, orientation_ids in _RATIFIED_ORIENTATION_ORDERS:
        if candidate_family == family_id:
            return orientation_ids
    raise AssertionError(f"missing ratified orientation order for {family_id!r}")


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


def _snapshot_weighted_law(value: object, *, label: str) -> ExactWeightedLaw:
    if type(value) is not ExactWeightedLaw:
        raise TypeError(f"{label} must be an ExactWeightedLaw")
    try:
        return ExactWeightedLaw(value.outcome_ids, value.counts)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


def _snapshot_uniform_law(value: object, *, label: str) -> UniformIntegerLaw:
    if type(value) is not UniformIntegerLaw:
        raise TypeError(f"{label} must be a UniformIntegerLaw")
    try:
        return UniformIntegerLaw(value.upper_bound)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class ConditionalWeightedLaw:
    """A complete ordered branch table of exact weighted laws.

    This generic record preserves every supplied branch, including branches
    that may be unreachable under a separate selector.  Tetromino-specific
    canonical branch and outcome orders are enforced by
    :class:`TetrominoEventLaw`.
    """

    branch_ids: tuple[str, ...]
    branch_laws: tuple[ExactWeightedLaw, ...]

    def __post_init__(self) -> None:
        if type(self.branch_ids) not in (list, tuple):
            raise TypeError("conditional-law branch IDs must be a plain list or tuple")
        branches = tuple(
            _snapshot_utf8_text(value, label=f"conditional-law branch ID {index}", length_framed=False)
            for index, value in enumerate(self.branch_ids)
        )
        if not branches:
            raise ValueError("conditional-law branch IDs must not be empty")
        if len(set(branches)) != len(branches):
            raise ValueError("conditional-law branch IDs must be unique")
        if type(self.branch_laws) not in (list, tuple):
            raise TypeError("conditional-law branch laws must be a plain list or tuple")
        laws = tuple(
            _snapshot_weighted_law(value, label=f"conditional-law branch law {index}")
            for index, value in enumerate(self.branch_laws)
        )
        if len(branches) != len(laws):
            raise ValueError("conditional-law branch IDs and laws must have equal length")
        object.__setattr__(self, "branch_ids", branches)
        object.__setattr__(self, "branch_laws", laws)

    def law_for(self, branch_id: str) -> ExactWeightedLaw:
        """Return the defensively frozen law for one exact branch ID."""

        branch = _snapshot_utf8_text(branch_id, label="conditional-law branch ID", length_framed=False)
        try:
            index = self.branch_ids.index(branch)
        except ValueError as error:
            raise ValueError(f"unknown conditional-law branch ID: {branch!r}") from error
        law = self.branch_laws[index]
        return ExactWeightedLaw(law.outcome_ids, law.counts)


def _snapshot_conditional_law(value: object) -> ConditionalWeightedLaw:
    if type(value) is not ConditionalWeightedLaw:
        raise TypeError("orientation_laws must be a ConditionalWeightedLaw")
    try:
        return ConditionalWeightedLaw(value.branch_ids, value.branch_laws)
    except AttributeError as error:
        raise TypeError("orientation_laws must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class TetrominoEventLaw:
    """The complete exact named law for one tetromino event selector."""

    family_law: ExactWeightedLaw
    orientation_laws: ConditionalWeightedLaw
    launch_law: UniformIntegerLaw
    contact_law: ExactWeightedLaw

    def __post_init__(self) -> None:
        _assert_ratified_order_integrity()
        family = _snapshot_weighted_law(self.family_law, label="family_law")
        orientations = _snapshot_conditional_law(self.orientation_laws)
        launch = _snapshot_uniform_law(self.launch_law, label="launch_law")
        contact = _snapshot_weighted_law(self.contact_law, label="contact_law")

        if family.outcome_ids != _RATIFIED_FAMILY_ORDER:
            raise ValueError("family_law outcome IDs must equal TETROMINO_FAMILY_ORDER")
        if orientations.branch_ids != _RATIFIED_FAMILY_ORDER:
            raise ValueError("orientation_laws branch IDs must equal TETROMINO_FAMILY_ORDER")
        for family_id, orientation_law in zip(orientations.branch_ids, orientations.branch_laws):
            expected = _ratified_orientation_order(family_id)
            if orientation_law.outcome_ids != expected:
                raise ValueError(f"orientation law for {family_id!r} must use its ratified orientation order")
        if contact.outcome_ids != _RATIFIED_CONTACT_ORDER:
            raise ValueError("contact_law outcome IDs must equal TETROMINO_CONTACT_ORDER")

        object.__setattr__(self, "family_law", family)
        object.__setattr__(self, "orientation_laws", orientations)
        object.__setattr__(self, "launch_law", launch)
        object.__setattr__(self, "contact_law", contact)


def _snapshot_event_law(value: object) -> TetrominoEventLaw:
    if type(value) is not TetrominoEventLaw:
        raise TypeError("law must be a TetrominoEventLaw")
    try:
        return TetrominoEventLaw(
            family_law=value.family_law,
            orientation_laws=value.orientation_laws,
            launch_law=value.launch_law,
            contact_law=value.contact_law,
        )
    except AttributeError as error:
        raise TypeError("law must be fully initialized") from error


def _snapshot_weighted_selection(value: object, *, label: str) -> WeightedSelection:
    if type(value) is not WeightedSelection:
        raise TypeError(f"{label} must be a WeightedSelection")
    try:
        return WeightedSelection(value.stream_name, value.outcome_id, value.draw)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


def _snapshot_uniform_selection(value: object, *, label: str) -> UniformSelection:
    if type(value) is not UniformSelection:
        raise TypeError(f"{label} must be a UniformSelection")
    try:
        return UniformSelection(value.stream_name, value.draw)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


def _validate_weighted_selection(
    selection: WeightedSelection,
    *,
    stream_name: str,
    law: ExactWeightedLaw,
    label: str,
) -> None:
    if selection.stream_name != stream_name:
        raise ValueError(f"{label} stream name must be {stream_name!r}")
    index = selection.selected_index
    if index >= len(law.outcome_ids) or law.counts[index] == 0:
        raise ValueError(f"{label} draw does not select positive support")
    if selection.outcome_id != law.outcome_ids[index]:
        raise ValueError(f"{label} outcome ID does not match its draw index")


@dataclass(frozen=True, slots=True)
class TetrominoEventSelection:
    """A structurally consistent address/law record of four semantic draws.

    Direct construction performs structural consistency checks but does not
    replay Philox.  The certified semantic guarantee applies to records returned
    by :func:`select_event`; canonical serialization and artifact identity remain
    outside S2.4.
    """

    root_seed: int
    coupling_group_id: str
    event_ordinal: int
    law: TetrominoEventLaw
    family: WeightedSelection
    orientation: WeightedSelection
    launch: UniformSelection
    contact: WeightedSelection

    def __post_init__(self) -> None:
        root, group, event = _snapshot_address(
            root_seed=self.root_seed,
            coupling_group_id=self.coupling_group_id,
            event_ordinal=self.event_ordinal,
        )
        law = _snapshot_event_law(self.law)
        family = _snapshot_weighted_selection(self.family, label="family selection")
        orientation = _snapshot_weighted_selection(self.orientation, label="orientation selection")
        launch = _snapshot_uniform_selection(self.launch, label="launch selection")
        contact = _snapshot_weighted_selection(self.contact, label="contact selection")

        _validate_weighted_selection(family, stream_name="family", law=law.family_law, label="family selection")
        orientation_law = law.orientation_laws.law_for(family.outcome_id)
        _validate_weighted_selection(
            orientation,
            stream_name="orientation",
            law=orientation_law,
            label="orientation selection",
        )
        if launch.stream_name != "launch":
            raise ValueError("launch selection stream name must be 'launch'")
        if launch.value >= law.launch_law.upper_bound:
            raise ValueError("launch selection lies outside launch_law")
        _validate_weighted_selection(contact, stream_name="contact", law=law.contact_law, label="contact selection")

        object.__setattr__(self, "root_seed", root)
        object.__setattr__(self, "coupling_group_id", group)
        object.__setattr__(self, "event_ordinal", event)
        object.__setattr__(self, "law", law)
        object.__setattr__(self, "family", family)
        object.__setattr__(self, "orientation", orientation)
        object.__setattr__(self, "launch", launch)
        object.__setattr__(self, "contact", contact)

    @property
    def family_id(self) -> str:
        return self.family.outcome_id

    @property
    def geometry_id(self) -> str:
        return self.orientation.outcome_id

    @property
    def launch_x(self) -> int:
        return self.launch.value

    @property
    def contact_id(self) -> str:
        return self.contact.outcome_id


def _snapshot_delegated_weighted(value: object, *, label: str) -> WeightedSelection:
    try:
        return _snapshot_weighted_selection(value, label=label)
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{label} selector returned a malformed result") from error


def _snapshot_delegated_uniform(value: object, *, label: str) -> UniformSelection:
    try:
        return _snapshot_uniform_selection(value, label=label)
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{label} selector returned a malformed result") from error


def _assert_delegated_weighted_matches(
    selection: WeightedSelection,
    *,
    stream_name: str,
    law: ExactWeightedLaw,
    label: str,
) -> None:
    try:
        _validate_weighted_selection(selection, stream_name=stream_name, law=law, label=label)
    except ValueError as error:
        raise AssertionError(f"{label} selector returned a result inconsistent with its law") from error


def _snapshot_tetromino_stream_set() -> DeclaredStreamSet:
    if type(TETROMINO_STREAM_SET) is not DeclaredStreamSet:
        raise AssertionError("TETROMINO_STREAM_SET has an invalid record type")
    try:
        stream_set = DeclaredStreamSet(TETROMINO_STREAM_SET.stream_names)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("TETROMINO_STREAM_SET is malformed") from error
    if stream_set.stream_names != _TETROMINO_STREAM_NAMES:
        raise AssertionError("TETROMINO_STREAM_SET does not match the fixed event schedule")
    return stream_set


def select_event(
    *,
    root_seed: int,
    coupling_group_id: str,
    event_ordinal: int,
    law: TetrominoEventLaw,
) -> TetrominoEventSelection:
    """Select one complete named tetromino event without placing a piece."""

    root, group, event = _snapshot_address(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        event_ordinal=event_ordinal,
    )
    event_law = _snapshot_event_law(law)
    stream_set = _snapshot_tetromino_stream_set()

    family = _snapshot_delegated_weighted(
        select_weighted(
            root_seed=root,
            coupling_group_id=group,
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="family",
            law=event_law.family_law,
        ),
        label="family",
    )
    _assert_delegated_weighted_matches(
        family,
        stream_name="family",
        law=event_law.family_law,
        label="family",
    )

    orientation_law = event_law.orientation_laws.law_for(family.outcome_id)
    orientation = _snapshot_delegated_weighted(
        select_weighted(
            root_seed=root,
            coupling_group_id=group,
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="orientation",
            law=orientation_law,
        ),
        label="orientation",
    )
    _assert_delegated_weighted_matches(
        orientation,
        stream_name="orientation",
        law=orientation_law,
        label="orientation",
    )

    launch = _snapshot_delegated_uniform(
        select_uniform(
            root_seed=root,
            coupling_group_id=group,
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="launch",
            law=event_law.launch_law,
        ),
        label="launch",
    )
    if launch.stream_name != "launch" or launch.value >= event_law.launch_law.upper_bound:
        raise AssertionError("launch selector returned a result inconsistent with its law")

    contact = _snapshot_delegated_weighted(
        select_weighted(
            root_seed=root,
            coupling_group_id=group,
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="contact",
            law=event_law.contact_law,
        ),
        label="contact",
    )
    _assert_delegated_weighted_matches(
        contact,
        stream_name="contact",
        law=event_law.contact_law,
        label="contact",
    )

    return TetrominoEventSelection(
        root_seed=root,
        coupling_group_id=group,
        event_ordinal=event,
        law=event_law,
        family=family,
        orientation=orientation,
        launch=launch,
        contact=contact,
    )


__all__ = [
    "ConditionalWeightedLaw",
    "TETROMINO_CONTACT_ORDER",
    "TETROMINO_FAMILY_ORDER",
    "TETROMINO_STREAM_SET",
    "TetrominoEventLaw",
    "TetrominoEventSelection",
    "select_event",
]
