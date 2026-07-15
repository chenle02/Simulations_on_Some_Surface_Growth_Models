"""Pure exact one-event transition for the three PRE one-cell boundaries.

This provisional explicit-submodule surface certifies the periodic, archived
legacy-asymmetric hard-wall, and corrected reflection-symmetric hard-wall
scalar laws. It performs no RNG, arm coupling, accumulation, trajectory,
compiled execution, persistence, configuration, legacy dispatch, or HPC
routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .one_cell import OneCellCausalSide, OneCellPeriodicTransition, transition_one_cell_periodic

_VERTICAL_EQUALITY_BIT = 1
_LEFT_EQUALITY_BIT = 2
_RIGHT_EQUALITY_BIT = 4


class OneCellBoundaryLaw(str, Enum):
    """Frozen scalar boundary identities for the PRE one-cell study."""

    PERIODIC = "periodic-v1"
    HARD_WALL_LEGACY_ASYMMETRIC = "hard-wall-legacy-asymmetric-v1"
    HARD_WALL_REFLECTION_SYMMETRIC = "hard-wall-reflection-symmetric-v1"


_BOUNDARY_LAW_TYPE = OneCellBoundaryLaw
_CAUSAL_SIDE_TYPE = OneCellCausalSide
_PERIODIC_TRANSITION_TYPE = OneCellPeriodicTransition


def _validate_height_tuple(value: object, *, label: str) -> tuple[int, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    if len(value) < 3:
        raise ValueError(f"{label} must contain at least three columns")
    for height in value:
        if type(height) is not int:
            raise TypeError(f"{label} must contain built-in integers")
        if height < 0:
            raise ValueError(f"{label} must contain nonnegative heights")
    return value


def _snapshot_heights(value: object) -> tuple[int, ...]:
    if type(value) not in (list, tuple):
        raise TypeError("heights must be a built-in list or tuple")
    return _validate_height_tuple(tuple(value), label="heights")


def _validate_launch_x(value: object, *, width: int) -> int:
    if type(value) is not int:
        raise TypeError("launch_x must be a built-in integer")
    if not 0 <= value < width:
        raise ValueError("launch_x must lie in [0, width)")
    return value


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return value


def _require_optional_height(value: object, *, label: str) -> int | None:
    if value is None:
        return None
    return _require_nonnegative_int(value, label=label)


def _neighbor_state(
    boundary_law: OneCellBoundaryLaw,
    pre_heights: tuple[int, ...],
    *,
    launch_x: int,
) -> tuple[int | None, int | None, bool, bool]:
    width = len(pre_heights)
    if boundary_law is _BOUNDARY_LAW_TYPE.PERIODIC:
        return (
            pre_heights[(launch_x - 1) % width],
            pre_heights[(launch_x + 1) % width],
            True,
            True,
        )

    left_pre_height = pre_heights[launch_x - 1] if launch_x > 0 else None
    right_pre_height = pre_heights[launch_x + 1] if launch_x < width - 1 else None
    if boundary_law is _BOUNDARY_LAW_TYPE.HARD_WALL_LEGACY_ASYMMETRIC:
        left_neighbor_eligible = launch_x > 1
    elif boundary_law is _BOUNDARY_LAW_TYPE.HARD_WALL_REFLECTION_SYMMETRIC:
        left_neighbor_eligible = launch_x > 0
    else:  # pragma: no cover - exact enum validation excludes this branch
        raise AssertionError("unrecognized one-cell boundary law")
    return (
        left_pre_height,
        right_pre_height,
        left_neighbor_eligible,
        launch_x < width - 1,
    )


def _derive_event(
    boundary_law: OneCellBoundaryLaw,
    pre_heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> tuple[
    int | None,
    int,
    int | None,
    bool,
    bool,
    int,
    int,
    int,
    int,
    bool,
    OneCellCausalSide,
    int,
    bool | None,
]:
    (
        left_pre_height,
        right_pre_height,
        left_neighbor_eligible,
        right_neighbor_eligible,
    ) = _neighbor_state(boundary_law, pre_heights, launch_x=launch_x)
    launch_pre_height = pre_heights[launch_x]
    vertical_height = launch_pre_height + 1
    launch_post_height = vertical_height
    if sticky_endpoint_selected:
        if left_neighbor_eligible:
            if left_pre_height is None:  # pragma: no cover - internal law invariant
                raise AssertionError("an eligible left neighbor must physically exist")
            launch_post_height = max(launch_post_height, left_pre_height)
        if right_neighbor_eligible:
            if right_pre_height is None:  # pragma: no cover - internal law invariant
                raise AssertionError("an eligible right neighbor must physically exist")
            launch_post_height = max(launch_post_height, right_pre_height)

    delta_s = launch_post_height - launch_pre_height
    delta_v = launch_post_height - vertical_height
    delta_q = launch_post_height * launch_post_height - launch_pre_height * launch_pre_height
    positive_gap_trigger = sticky_endpoint_selected and delta_v > 0

    if positive_gap_trigger:
        left_causal = left_neighbor_eligible and left_pre_height == launch_post_height
        right_causal = right_neighbor_eligible and right_pre_height == launch_post_height
        if left_causal and right_causal:
            causal_side = _CAUSAL_SIDE_TYPE.BOTH
        elif left_causal:
            causal_side = _CAUSAL_SIDE_TYPE.LEFT
        elif right_causal:
            causal_side = _CAUSAL_SIDE_TYPE.RIGHT
        else:  # pragma: no cover - excluded by the eligible-neighbor maximum
            raise RuntimeError("a positive-gap arrest must have an eligible causal neighbor")
    else:
        causal_side = _CAUSAL_SIDE_TYPE.NONE

    equality_mask = (
        _VERTICAL_EQUALITY_BIT * (launch_post_height == vertical_height)
        + _LEFT_EQUALITY_BIT * (left_pre_height is not None and left_pre_height == launch_post_height)
        + _RIGHT_EQUALITY_BIT * (right_pre_height is not None and right_pre_height == launch_post_height)
    )
    seam_equality = (
        bool(
            (launch_x == 0 and equality_mask & _LEFT_EQUALITY_BIT)
            or (launch_x == len(pre_heights) - 1 and equality_mask & _RIGHT_EQUALITY_BIT)
        )
        if boundary_law is _BOUNDARY_LAW_TYPE.PERIODIC
        else None
    )
    return (
        left_pre_height,
        launch_pre_height,
        right_pre_height,
        left_neighbor_eligible,
        right_neighbor_eligible,
        launch_post_height,
        delta_s,
        delta_v,
        delta_q,
        positive_gap_trigger,
        causal_side,
        equality_mask,
        seam_equality,
    )


@dataclass(frozen=True, slots=True)
class OneCellBoundaryTransition:
    """Immutable self-validating certificate for one boundary-aware event."""

    boundary_law: OneCellBoundaryLaw
    pre_heights: tuple[int, ...]
    post_heights: tuple[int, ...]
    launch_x: int
    sticky_endpoint_selected: bool
    left_pre_height: int | None
    launch_pre_height: int
    right_pre_height: int | None
    left_neighbor_eligible: bool
    right_neighbor_eligible: bool
    launch_post_height: int
    delta_s: int
    delta_v: int
    delta_q: int
    positive_gap_trigger: bool
    causal_side: OneCellCausalSide
    equality_mask: int
    seam_equality: bool | None

    def __post_init__(self) -> None:
        if type(self.boundary_law) is not _BOUNDARY_LAW_TYPE:
            raise TypeError("boundary_law must be a OneCellBoundaryLaw")
        pre_heights = _validate_height_tuple(self.pre_heights, label="pre_heights")
        post_heights = _validate_height_tuple(self.post_heights, label="post_heights")
        if len(post_heights) != len(pre_heights):
            raise ValueError("pre_heights and post_heights must have the same width")
        launch_x = _validate_launch_x(self.launch_x, width=len(pre_heights))
        if type(self.sticky_endpoint_selected) is not bool:
            raise TypeError("sticky_endpoint_selected must be a built-in bool")

        _require_optional_height(self.left_pre_height, label="left_pre_height")
        _require_optional_height(self.right_pre_height, label="right_pre_height")
        for label, value in (
            ("launch_pre_height", self.launch_pre_height),
            ("launch_post_height", self.launch_post_height),
            ("delta_s", self.delta_s),
            ("delta_v", self.delta_v),
            ("delta_q", self.delta_q),
            ("equality_mask", self.equality_mask),
        ):
            _require_nonnegative_int(value, label=label)
        if type(self.left_neighbor_eligible) is not bool:
            raise TypeError("left_neighbor_eligible must be a built-in bool")
        if type(self.right_neighbor_eligible) is not bool:
            raise TypeError("right_neighbor_eligible must be a built-in bool")
        if type(self.positive_gap_trigger) is not bool:
            raise TypeError("positive_gap_trigger must be a built-in bool")
        if type(self.causal_side) is not _CAUSAL_SIDE_TYPE:
            raise TypeError("causal_side must be a OneCellCausalSide")
        if self.seam_equality is not None and type(self.seam_equality) is not bool:
            raise TypeError("seam_equality must be a built-in bool or None")

        expected = _derive_event(
            self.boundary_law,
            pre_heights,
            launch_x=launch_x,
            sticky_endpoint_selected=self.sticky_endpoint_selected,
        )
        actual = (
            self.left_pre_height,
            self.launch_pre_height,
            self.right_pre_height,
            self.left_neighbor_eligible,
            self.right_neighbor_eligible,
            self.launch_post_height,
            self.delta_s,
            self.delta_v,
            self.delta_q,
            self.positive_gap_trigger,
            self.causal_side,
            self.equality_mask,
            self.seam_equality,
        )
        if actual != expected:
            raise ValueError("transition primitives must match the selected one-cell boundary law")

        expected_post = list(pre_heights)
        expected_post[launch_x] = self.launch_post_height
        if post_heights != tuple(expected_post):
            raise ValueError("post_heights must change only launch_x according to the boundary law")

    @property
    def width(self) -> int:
        """Return the substrate width."""

        return len(self.pre_heights)

    @property
    def gap(self) -> int:
        """Return the exact realized gap, identical to ``delta_v``."""

        return self.delta_v


_BOUNDARY_TRANSITION_TYPE = OneCellBoundaryTransition


def _snapshot_periodic_transition(value: object) -> OneCellPeriodicTransition:
    if type(value) is not _PERIODIC_TRANSITION_TYPE:
        raise AssertionError("periodic delegate returned an invalid record type")
    try:
        return _PERIODIC_TRANSITION_TYPE(
            pre_heights=value.pre_heights,
            post_heights=value.post_heights,
            launch_x=value.launch_x,
            sticky_endpoint_selected=value.sticky_endpoint_selected,
            left_pre_height=value.left_pre_height,
            launch_pre_height=value.launch_pre_height,
            right_pre_height=value.right_pre_height,
            launch_post_height=value.launch_post_height,
            delta_s=value.delta_s,
            delta_v=value.delta_v,
            delta_q=value.delta_q,
            positive_gap_trigger=value.positive_gap_trigger,
            causal_side=value.causal_side,
            equality_mask=value.equality_mask,
            seam_equality=value.seam_equality,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("periodic delegate returned a malformed record") from error


def _from_periodic_delegate(
    pre_heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> OneCellBoundaryTransition:
    delegated = _snapshot_periodic_transition(
        transition_one_cell_periodic(
            heights=pre_heights,
            launch_x=launch_x,
            sticky_endpoint_selected=sticky_endpoint_selected,
        )
    )
    if (
        delegated.pre_heights != pre_heights
        or delegated.launch_x != launch_x
        or delegated.sticky_endpoint_selected is not sticky_endpoint_selected
    ):
        raise AssertionError("periodic delegate returned a record for a different request")
    try:
        return _BOUNDARY_TRANSITION_TYPE(
            boundary_law=_BOUNDARY_LAW_TYPE.PERIODIC,
            pre_heights=delegated.pre_heights,
            post_heights=delegated.post_heights,
            launch_x=delegated.launch_x,
            sticky_endpoint_selected=delegated.sticky_endpoint_selected,
            left_pre_height=delegated.left_pre_height,
            launch_pre_height=delegated.launch_pre_height,
            right_pre_height=delegated.right_pre_height,
            left_neighbor_eligible=True,
            right_neighbor_eligible=True,
            launch_post_height=delegated.launch_post_height,
            delta_s=delegated.delta_s,
            delta_v=delegated.delta_v,
            delta_q=delegated.delta_q,
            positive_gap_trigger=delegated.positive_gap_trigger,
            causal_side=delegated.causal_side,
            equality_mask=delegated.equality_mask,
            seam_equality=delegated.seam_equality,
        )
    except (TypeError, ValueError) as error:
        raise AssertionError("periodic delegate returned a result inconsistent with its request") from error


def transition_one_cell_boundary(
    *,
    boundary_law: OneCellBoundaryLaw,
    heights: list[int] | tuple[int, ...],
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> OneCellBoundaryTransition:
    """Apply one exact boundary-aware event without mutating ``heights``."""

    if type(boundary_law) is not _BOUNDARY_LAW_TYPE:
        raise TypeError("boundary_law must be a OneCellBoundaryLaw")
    pre_heights = _snapshot_heights(heights)
    launch_x = _validate_launch_x(launch_x, width=len(pre_heights))
    if type(sticky_endpoint_selected) is not bool:
        raise TypeError("sticky_endpoint_selected must be a built-in bool")

    if boundary_law is _BOUNDARY_LAW_TYPE.PERIODIC:
        return _from_periodic_delegate(
            pre_heights,
            launch_x=launch_x,
            sticky_endpoint_selected=sticky_endpoint_selected,
        )

    (
        left_pre_height,
        launch_pre_height,
        right_pre_height,
        left_neighbor_eligible,
        right_neighbor_eligible,
        launch_post_height,
        delta_s,
        delta_v,
        delta_q,
        positive_gap_trigger,
        causal_side,
        equality_mask,
        seam_equality,
    ) = _derive_event(
        boundary_law,
        pre_heights,
        launch_x=launch_x,
        sticky_endpoint_selected=sticky_endpoint_selected,
    )
    post_heights = list(pre_heights)
    post_heights[launch_x] = launch_post_height
    return _BOUNDARY_TRANSITION_TYPE(
        boundary_law=boundary_law,
        pre_heights=pre_heights,
        post_heights=tuple(post_heights),
        launch_x=launch_x,
        sticky_endpoint_selected=sticky_endpoint_selected,
        left_pre_height=left_pre_height,
        launch_pre_height=launch_pre_height,
        right_pre_height=right_pre_height,
        left_neighbor_eligible=left_neighbor_eligible,
        right_neighbor_eligible=right_neighbor_eligible,
        launch_post_height=launch_post_height,
        delta_s=delta_s,
        delta_v=delta_v,
        delta_q=delta_q,
        positive_gap_trigger=positive_gap_trigger,
        causal_side=causal_side,
        equality_mask=equality_mask,
        seam_equality=seam_equality,
    )


__all__ = [
    "OneCellBoundaryLaw",
    "OneCellBoundaryTransition",
    "transition_one_cell_boundary",
]
