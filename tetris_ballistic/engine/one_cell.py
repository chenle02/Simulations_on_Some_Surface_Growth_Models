"""Pure exact transition for the clean periodic one-cell RD/BD model.

This provisional explicit-submodule surface implements one deterministic
height-only event for ``one-cell-rd-bd-periodic-v1``.  It performs no RNG,
arm coupling, accumulation, trajectory execution, checkpointing, persistence,
legacy adaptation, optimized dispatch, or HPC routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

ONE_CELL_PERIODIC_MODEL_ID = "one-cell-rd-bd-periodic-v1"

_VERTICAL_EQUALITY_BIT = 1
_LEFT_EQUALITY_BIT = 2
_RIGHT_EQUALITY_BIT = 4


class OneCellCausalSide(str, Enum):
    """Causal lateral side for a selected sticky positive-gap arrest."""

    NONE = "none"
    LEFT = "left"
    RIGHT = "right"
    BOTH = "both"


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


def _derive_event(
    pre_heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> tuple[int, int, int, int, int, int, int, bool, OneCellCausalSide, int, bool]:
    width = len(pre_heights)
    launch_pre_height = pre_heights[launch_x]
    left_pre_height = pre_heights[(launch_x - 1) % width]
    right_pre_height = pre_heights[(launch_x + 1) % width]
    vertical_height = launch_pre_height + 1
    launch_post_height = (
        max(vertical_height, left_pre_height, right_pre_height) if sticky_endpoint_selected else vertical_height
    )

    delta_s = launch_post_height - launch_pre_height
    delta_v = launch_post_height - vertical_height
    delta_q = launch_post_height * launch_post_height - launch_pre_height * launch_pre_height
    positive_gap_trigger = sticky_endpoint_selected and delta_v > 0

    if positive_gap_trigger:
        left_causal = left_pre_height == launch_post_height
        right_causal = right_pre_height == launch_post_height
        if left_causal and right_causal:
            causal_side = OneCellCausalSide.BOTH
        elif left_causal:
            causal_side = OneCellCausalSide.LEFT
        elif right_causal:
            causal_side = OneCellCausalSide.RIGHT
        else:  # pragma: no cover - excluded by the maximum recurrence
            raise RuntimeError("a positive-gap arrest must have a causal lateral neighbor")
    else:
        causal_side = OneCellCausalSide.NONE

    equality_mask = (
        _VERTICAL_EQUALITY_BIT * (launch_post_height == vertical_height)
        + _LEFT_EQUALITY_BIT * (left_pre_height == launch_post_height)
        + _RIGHT_EQUALITY_BIT * (right_pre_height == launch_post_height)
    )
    seam_equality = bool(
        (launch_x == 0 and equality_mask & _LEFT_EQUALITY_BIT)
        or (launch_x == width - 1 and equality_mask & _RIGHT_EQUALITY_BIT)
    )
    return (
        left_pre_height,
        launch_pre_height,
        right_pre_height,
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
class OneCellPeriodicTransition:
    """Immutable, self-validating certificate for one clean periodic event.

    The equality mask uses the fixed height-defined bits ``vertical=1``,
    ``left=2``, and ``right=4``.  Lateral equality can therefore be present on
    a zero-gap or nonsticky event without becoming causal.
    """

    pre_heights: tuple[int, ...]
    post_heights: tuple[int, ...]
    launch_x: int
    sticky_endpoint_selected: bool
    left_pre_height: int
    launch_pre_height: int
    right_pre_height: int
    launch_post_height: int
    delta_s: int
    delta_v: int
    delta_q: int
    positive_gap_trigger: bool
    causal_side: OneCellCausalSide
    equality_mask: int
    seam_equality: bool

    def __post_init__(self) -> None:
        pre_heights = _validate_height_tuple(self.pre_heights, label="pre_heights")
        post_heights = _validate_height_tuple(self.post_heights, label="post_heights")
        if len(post_heights) != len(pre_heights):
            raise ValueError("pre_heights and post_heights must have the same width")
        launch_x = _validate_launch_x(self.launch_x, width=len(pre_heights))
        if type(self.sticky_endpoint_selected) is not bool:
            raise TypeError("sticky_endpoint_selected must be a built-in bool")

        for label, value in (
            ("left_pre_height", self.left_pre_height),
            ("launch_pre_height", self.launch_pre_height),
            ("right_pre_height", self.right_pre_height),
            ("launch_post_height", self.launch_post_height),
            ("delta_s", self.delta_s),
            ("delta_v", self.delta_v),
            ("delta_q", self.delta_q),
            ("equality_mask", self.equality_mask),
        ):
            _require_nonnegative_int(value, label=label)
        if type(self.positive_gap_trigger) is not bool:
            raise TypeError("positive_gap_trigger must be a built-in bool")
        if type(self.causal_side) is not OneCellCausalSide:
            raise TypeError("causal_side must be a OneCellCausalSide")
        if type(self.seam_equality) is not bool:
            raise TypeError("seam_equality must be a built-in bool")

        expected = _derive_event(
            pre_heights,
            launch_x=launch_x,
            sticky_endpoint_selected=self.sticky_endpoint_selected,
        )
        actual = (
            self.left_pre_height,
            self.launch_pre_height,
            self.right_pre_height,
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
            raise ValueError("transition primitives must match the exact periodic one-cell recurrence")

        expected_post = list(pre_heights)
        expected_post[launch_x] = self.launch_post_height
        if post_heights != tuple(expected_post):
            raise ValueError("post_heights must change only launch_x according to the recurrence")

    @property
    def model_id(self) -> str:
        """Return the frozen clean-model identity."""

        return ONE_CELL_PERIODIC_MODEL_ID

    @property
    def width(self) -> int:
        """Return the periodic substrate width."""

        return len(self.pre_heights)

    @property
    def gap(self) -> int:
        """Return the exact realized gap, identical to ``delta_v``."""

        return self.delta_v


def transition_one_cell_periodic(
    *,
    heights: list[int] | tuple[int, ...],
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> OneCellPeriodicTransition:
    """Apply one exact height-only event without mutating ``heights``.

    The nonsticky endpoint updates only the launch column to ``a + 1``.  The
    sticky endpoint updates it to ``max(a + 1, b, c)``, where ``b`` and ``c``
    are the modulo-periodic left and right pre-event neighbor heights.
    """

    pre_heights = _snapshot_heights(heights)
    launch_x = _validate_launch_x(launch_x, width=len(pre_heights))
    if type(sticky_endpoint_selected) is not bool:
        raise TypeError("sticky_endpoint_selected must be a built-in bool")

    (
        left_pre_height,
        launch_pre_height,
        right_pre_height,
        launch_post_height,
        delta_s,
        delta_v,
        delta_q,
        positive_gap_trigger,
        causal_side,
        equality_mask,
        seam_equality,
    ) = _derive_event(
        pre_heights,
        launch_x=launch_x,
        sticky_endpoint_selected=sticky_endpoint_selected,
    )
    post_heights = list(pre_heights)
    post_heights[launch_x] = launch_post_height

    return OneCellPeriodicTransition(
        pre_heights=pre_heights,
        post_heights=tuple(post_heights),
        launch_x=launch_x,
        sticky_endpoint_selected=sticky_endpoint_selected,
        left_pre_height=left_pre_height,
        launch_pre_height=launch_pre_height,
        right_pre_height=right_pre_height,
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
    "ONE_CELL_PERIODIC_MODEL_ID",
    "OneCellCausalSide",
    "OneCellPeriodicTransition",
    "transition_one_cell_periodic",
]
