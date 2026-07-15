"""Exact two-stream coupling for one boundary-agnostic PRE one-cell event.

This provisional explicit-submodule surface composes the certified semantic
RNG and uniform-selection layers into one shared launch draw, one shared
contact draw, and the eight nested PRE stickiness decisions.  It performs no
state transition, trajectory, accumulation, persistence, compiled execution,
legacy adaptation, or HPC routing.
"""

from __future__ import annotations

from dataclasses import dataclass

from .selection import DeclaredStreamSet, UniformIntegerLaw, UniformSelection, select_uniform

ONE_CELL_COUPLING_GROUP_ID = "pre-one-cell-discovery-v1"
ONE_CELL_STREAM_SET = DeclaredStreamSet(("launch", "contact"))
ONE_CELL_CONTACT_DENOMINATOR = 100
ONE_CELL_STICKINESS_THRESHOLDS = (0, 1, 2, 5, 10, 25, 50, 100)

_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1


def _require_plain_uint(value: object, *, maximum: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return value


def _require_width(value: object) -> int:
    if type(value) is not int:
        raise TypeError("width must be a built-in integer")
    if not 3 <= value <= _U64_SPACE:
        raise ValueError("width must lie in [3, 2**64]")
    return value


def _snapshot_stream_set() -> DeclaredStreamSet:
    if type(ONE_CELL_STREAM_SET) is not DeclaredStreamSet:
        raise AssertionError("ONE_CELL_STREAM_SET has an invalid record type")
    try:
        stream_set = DeclaredStreamSet(ONE_CELL_STREAM_SET.stream_names)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("ONE_CELL_STREAM_SET is malformed") from error
    if stream_set.stream_names != ("launch", "contact"):
        raise AssertionError("ONE_CELL_STREAM_SET does not match the fixed two-stream schedule")
    return stream_set


def _assert_contract_integrity() -> DeclaredStreamSet:
    if type(ONE_CELL_COUPLING_GROUP_ID) is not str or ONE_CELL_COUPLING_GROUP_ID != "pre-one-cell-discovery-v1":
        raise AssertionError("ONE_CELL_COUPLING_GROUP_ID does not match the frozen protocol")
    if type(ONE_CELL_CONTACT_DENOMINATOR) is not int or ONE_CELL_CONTACT_DENOMINATOR != 100:
        raise AssertionError("ONE_CELL_CONTACT_DENOMINATOR does not match the frozen protocol")
    if (
        type(ONE_CELL_STICKINESS_THRESHOLDS) is not tuple
        or ONE_CELL_STICKINESS_THRESHOLDS != (0, 1, 2, 5, 10, 25, 50, 100)
        or any(type(value) is not int for value in ONE_CELL_STICKINESS_THRESHOLDS)
    ):
        raise AssertionError("ONE_CELL_STICKINESS_THRESHOLDS do not match the frozen protocol")
    return _snapshot_stream_set()


def _snapshot_uniform_selection(value: object, *, label: str) -> UniformSelection:
    if type(value) is not UniformSelection:
        raise TypeError(f"{label} must be a UniformSelection")
    try:
        return UniformSelection(value.stream_name, value.draw)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


def _validate_uniform_selection(
    selection: UniformSelection,
    *,
    stream_name: str,
    upper_bound: int,
    label: str,
) -> None:
    if selection.stream_name != stream_name:
        raise ValueError(f"{label} stream name must be {stream_name!r}")
    if selection.value >= upper_bound:
        raise ValueError(f"{label} lies outside its uniform law")


def _snapshot_delegated_uniform(value: object, *, label: str) -> UniformSelection:
    try:
        return _snapshot_uniform_selection(value, label=label)
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{label} selector returned a malformed result") from error


def _assert_delegated_uniform_matches(
    selection: UniformSelection,
    *,
    stream_name: str,
    upper_bound: int,
    label: str,
) -> None:
    try:
        _validate_uniform_selection(
            selection,
            stream_name=stream_name,
            upper_bound=upper_bound,
            label=label,
        )
    except ValueError as error:
        raise AssertionError(f"{label} selector returned a result inconsistent with its law") from error


@dataclass(frozen=True, slots=True)
class OneCellCoupledEventSelection:
    """Structurally consistent evidence for one shared two-stream selection.

    Direct construction validates the address, laws, stream identities, and
    draw ranges but does not replay Philox.  The certified semantic guarantee
    applies to records returned by :func:`select_one_cell_coupled_event`.
    """

    root_seed: int
    event_ordinal: int
    width: int
    launch: UniformSelection
    contact: UniformSelection

    def __post_init__(self) -> None:
        _assert_contract_integrity()
        root = _require_plain_uint(self.root_seed, maximum=_U128_MAX, label="root seed")
        event = _require_plain_uint(self.event_ordinal, maximum=_U64_MAX, label="event ordinal")
        width = _require_width(self.width)
        launch = _snapshot_uniform_selection(self.launch, label="launch selection")
        contact = _snapshot_uniform_selection(self.contact, label="contact selection")
        _validate_uniform_selection(
            launch,
            stream_name="launch",
            upper_bound=width,
            label="launch selection",
        )
        _validate_uniform_selection(
            contact,
            stream_name="contact",
            upper_bound=100,
            label="contact selection",
        )
        object.__setattr__(self, "root_seed", root)
        object.__setattr__(self, "event_ordinal", event)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "launch", launch)
        object.__setattr__(self, "contact", contact)

    @property
    def coupling_group_id(self) -> str:
        """Return the frozen PRE coupling-group identity."""

        return "pre-one-cell-discovery-v1"

    @property
    def stream_names(self) -> tuple[str, str]:
        """Return the fixed logical stream schedule."""

        return ("launch", "contact")

    @property
    def launch_x(self) -> int:
        """Return the launch column shared by all eight arms."""

        return self.launch.value

    @property
    def contact_value(self) -> int:
        """Return the common integer contact draw in ``range(100)``."""

        return self.contact.value

    @property
    def sticky_by_threshold(self) -> tuple[bool, ...]:
        """Return the eight nested sticky-endpoint decisions in fixed order."""

        return tuple(self.contact_value < threshold for threshold in (0, 1, 2, 5, 10, 25, 50, 100))

    @property
    def arm_decisions(self) -> tuple[tuple[int, bool], ...]:
        """Return each frozen threshold paired with its common-draw decision."""

        return tuple(zip((0, 1, 2, 5, 10, 25, 50, 100), self.sticky_by_threshold))


def select_one_cell_coupled_event(
    *,
    root_seed: int,
    event_ordinal: int,
    width: int,
) -> OneCellCoupledEventSelection:
    """Select one shared launch and the eight common-contact arm decisions."""

    stream_set = _assert_contract_integrity()
    root = _require_plain_uint(root_seed, maximum=_U128_MAX, label="root seed")
    event = _require_plain_uint(event_ordinal, maximum=_U64_MAX, label="event ordinal")
    selected_width = _require_width(width)
    launch_law = UniformIntegerLaw(selected_width)
    contact_law = UniformIntegerLaw(100)

    launch = _snapshot_delegated_uniform(
        select_uniform(
            root_seed=root,
            coupling_group_id="pre-one-cell-discovery-v1",
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="launch",
            law=launch_law,
        ),
        label="launch",
    )
    _assert_delegated_uniform_matches(
        launch,
        stream_name="launch",
        upper_bound=selected_width,
        label="launch",
    )

    contact = _snapshot_delegated_uniform(
        select_uniform(
            root_seed=root,
            coupling_group_id="pre-one-cell-discovery-v1",
            event_ordinal=event,
            declared_streams=stream_set,
            stream_name="contact",
            law=contact_law,
        ),
        label="contact",
    )
    _assert_delegated_uniform_matches(
        contact,
        stream_name="contact",
        upper_bound=100,
        label="contact",
    )

    return OneCellCoupledEventSelection(
        root_seed=root,
        event_ordinal=event,
        width=selected_width,
        launch=launch,
        contact=contact,
    )


__all__ = [
    "ONE_CELL_CONTACT_DENOMINATOR",
    "ONE_CELL_COUPLING_GROUP_ID",
    "ONE_CELL_STICKINESS_THRESHOLDS",
    "ONE_CELL_STREAM_SET",
    "OneCellCoupledEventSelection",
    "select_one_cell_coupled_event",
]
