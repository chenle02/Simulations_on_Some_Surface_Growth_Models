"""Independent certification for the clean periodic one-cell transition."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, dataclass, replace
from itertools import product
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.one_cell as one_cell_engine
from tetris_ballistic.engine import SparseAggregate, place_one
from tetris_ballistic.engine.one_cell import (
    ONE_CELL_PERIODIC_MODEL_ID,
    OneCellCausalSide,
    OneCellPeriodicTransition,
    transition_one_cell_periodic,
)
from tetris_ballistic.models import ONE_CELL, ContactKind


@dataclass(frozen=True)
class _OracleTransition:
    post_heights: tuple[int, ...]
    left_pre_height: int
    launch_pre_height: int
    right_pre_height: int
    launch_post_height: int
    delta_s: int
    delta_v: int
    delta_q: int
    positive_gap_trigger: bool
    causal_side: str
    equality_mask: int
    seam_equality: bool


def _independent_scalar_oracle(
    heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> _OracleTransition:
    width = len(heights)
    a = heights[launch_x]
    b = heights[(launch_x - 1) % width]
    c = heights[(launch_x + 1) % width]
    vertical = a + 1
    post_height = max(vertical, b, c) if sticky_endpoint_selected else vertical
    delta_v = post_height - vertical
    trigger = sticky_endpoint_selected and delta_v > 0

    if not trigger:
        causal_side = "none"
    elif b == post_height and c == post_height:
        causal_side = "both"
    elif b == post_height:
        causal_side = "left"
    else:
        causal_side = "right"

    equality_mask = int(post_height == vertical) + 2 * int(b == post_height) + 4 * int(c == post_height)
    seam_equality = (launch_x == 0 and b == post_height) or (launch_x == width - 1 and c == post_height)
    post_heights = list(heights)
    post_heights[launch_x] = post_height
    return _OracleTransition(
        post_heights=tuple(post_heights),
        left_pre_height=b,
        launch_pre_height=a,
        right_pre_height=c,
        launch_post_height=post_height,
        delta_s=post_height - a,
        delta_v=delta_v,
        delta_q=post_height * post_height - a * a,
        positive_gap_trigger=trigger,
        causal_side=causal_side,
        equality_mask=equality_mask,
        seam_equality=seam_equality,
    )


def _solid_state(heights: tuple[int, ...]) -> SparseAggregate:
    occupied = {(x, y) for x, height in enumerate(heights) for y in range(height)}
    return SparseAggregate(len(heights), occupied)


def _envelope(state: SparseAggregate) -> tuple[int, ...]:
    heights = [0] * state.width
    for x, y in state.occupied:
        heights[x] = max(heights[x], y + 1)
    return tuple(heights)


def _contact_kind(sticky_endpoint_selected: bool) -> ContactKind:
    return ContactKind.EDGE_FIRST_CONTACT_V1 if sticky_endpoint_selected else ContactKind.SUPPORTED_V1


def _assert_transition_matches_oracle(
    actual: OneCellPeriodicTransition,
    expected: _OracleTransition,
    *,
    pre_heights: tuple[int, ...],
    launch_x: int,
    sticky_endpoint_selected: bool,
    context: str,
) -> None:
    assert actual.pre_heights == pre_heights, context
    assert actual.post_heights == expected.post_heights, context
    assert actual.launch_x == launch_x, context
    assert actual.sticky_endpoint_selected is sticky_endpoint_selected, context
    assert actual.left_pre_height == expected.left_pre_height, context
    assert actual.launch_pre_height == expected.launch_pre_height, context
    assert actual.right_pre_height == expected.right_pre_height, context
    assert actual.launch_post_height == expected.launch_post_height, context
    assert actual.delta_s == expected.delta_s, context
    assert actual.delta_v == expected.delta_v, context
    assert actual.delta_q == expected.delta_q, context
    assert actual.positive_gap_trigger is expected.positive_gap_trigger, context
    assert actual.causal_side.value == expected.causal_side, context
    assert actual.equality_mask == expected.equality_mask, context
    assert actual.seam_equality is expected.seam_equality, context
    assert actual.model_id == ONE_CELL_PERIODIC_MODEL_ID, context
    assert actual.width == len(pre_heights), context
    assert actual.gap == actual.delta_v, context
    assert actual.delta_s == 1 + actual.delta_v, context
    assert sum(actual.post_heights) - sum(actual.pre_heights) == actual.delta_s, context
    assert (
        sum(height * height for height in actual.post_heights) - sum(height * height for height in actual.pre_heights)
        == actual.delta_q
    ), context


def test_exhaustive_bounded_heights_match_independent_scalar_and_sparse_references() -> None:
    case_count = 0
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            state = _solid_state(heights)
            for launch_x in range(width):
                for sticky_endpoint_selected in (False, True):
                    context = (
                        f"width={width}, heights={heights}, launch_x={launch_x}, "
                        f"sticky_endpoint_selected={sticky_endpoint_selected}"
                    )
                    expected = _independent_scalar_oracle(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    actual = transition_one_cell_periodic(
                        heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    _assert_transition_matches_oracle(
                        actual,
                        expected,
                        pre_heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                        context=context,
                    )

                    placement = place_one(
                        state,
                        ONE_CELL,
                        launch_x,
                        _contact_kind(sticky_endpoint_selected),
                    )
                    assert placement.supported_landing_y == heights[launch_x], context
                    assert placement.landing_y + 1 == actual.launch_post_height, context
                    assert placement.early_arrest_gap == actual.delta_v, context
                    assert placement.lateral_trigger is actual.positive_gap_trigger, context
                    assert _envelope(placement.post_state) == actual.post_heights, context
                    assert placement.post_state.mass == placement.pre_state.mass + 1, context
                    case_count += 1

    assert case_count == 12_672


def test_all_short_schedules_match_the_holey_sparse_reference_trajectory() -> None:
    width = 3
    frontier = [((0, 0, 0), SparseAggregate.empty(width))]
    transition_count = 0
    saw_hole_bearing_state = False

    for _ in range(4):
        next_frontier: list[tuple[tuple[int, ...], SparseAggregate]] = []
        for heights, state in frontier:
            assert _envelope(state) == heights
            saw_hole_bearing_state = saw_hole_bearing_state or sum(heights) > state.mass
            for launch_x in range(width):
                for sticky_endpoint_selected in (False, True):
                    scalar = transition_one_cell_periodic(
                        heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    placement = place_one(
                        state,
                        ONE_CELL,
                        launch_x,
                        _contact_kind(sticky_endpoint_selected),
                    )
                    assert _envelope(placement.post_state) == scalar.post_heights
                    assert placement.landing_y + 1 == scalar.launch_post_height
                    assert placement.early_arrest_gap == scalar.delta_v
                    assert placement.post_state.mass == state.mass + 1
                    next_frontier.append((scalar.post_heights, placement.post_state))
                    transition_count += 1
        frontier = next_frontier

    assert transition_count == 1_554
    assert len(frontier) == 6**4
    assert saw_hole_bearing_state


@pytest.mark.parametrize(
    ("heights", "sticky", "post_height", "gap", "mask", "side"),
    (
        ((0, 0, 0), False, 1, 0, 1, OneCellCausalSide.NONE),
        ((1, 0, 0), False, 1, 0, 3, OneCellCausalSide.NONE),
        ((0, 0, 1), False, 1, 0, 5, OneCellCausalSide.NONE),
        ((1, 0, 1), False, 1, 0, 7, OneCellCausalSide.NONE),
        ((0, 0, 0), True, 1, 0, 1, OneCellCausalSide.NONE),
        ((1, 0, 0), True, 1, 0, 3, OneCellCausalSide.NONE),
        ((0, 0, 1), True, 1, 0, 5, OneCellCausalSide.NONE),
        ((1, 0, 1), True, 1, 0, 7, OneCellCausalSide.NONE),
        ((2, 0, 0), True, 2, 1, 2, OneCellCausalSide.LEFT),
        ((0, 0, 2), True, 2, 1, 4, OneCellCausalSide.RIGHT),
        ((2, 0, 2), True, 2, 1, 6, OneCellCausalSide.BOTH),
    ),
)
def test_endpoint_selection_equality_and_causality_remain_distinct(
    heights: tuple[int, ...],
    sticky: bool,
    post_height: int,
    gap: int,
    mask: int,
    side: OneCellCausalSide,
) -> None:
    result = transition_one_cell_periodic(
        heights=heights,
        launch_x=1,
        sticky_endpoint_selected=sticky,
    )

    assert result.launch_post_height == post_height
    assert result.gap == gap
    assert result.equality_mask == mask
    assert result.causal_side is side
    assert result.positive_gap_trigger is (sticky and gap > 0)


@pytest.mark.parametrize(
    ("heights", "launch_x", "sticky", "expected_mask", "expected_seam"),
    (
        ((0, 0, 1), 0, False, 3, True),
        ((1, 0, 0), 2, False, 5, True),
        ((1, 0, 0), 1, False, 3, False),
        ((0, 1, 0), 0, False, 5, False),
        ((0, 1, 0), 2, False, 3, False),
        ((0, 0, 2), 0, True, 2, True),
        ((2, 0, 0), 2, True, 4, True),
    ),
)
def test_seam_equality_requires_a_mask_qualified_lateral_equality(
    heights: tuple[int, ...],
    launch_x: int,
    sticky: bool,
    expected_mask: int,
    expected_seam: bool,
) -> None:
    result = transition_one_cell_periodic(
        heights=heights,
        launch_x=launch_x,
        sticky_endpoint_selected=sticky,
    )

    assert result.equality_mask == expected_mask
    assert result.seam_equality is expected_seam


def test_taller_incidental_reference_contact_is_not_height_equality() -> None:
    heights = (1, 0, 4)
    result = transition_one_cell_periodic(
        heights=heights,
        launch_x=0,
        sticky_endpoint_selected=False,
    )
    placement = place_one(
        _solid_state(heights),
        ONE_CELL,
        0,
        ContactKind.SUPPORTED_V1,
    )

    assert result.equality_mask == 1
    assert result.seam_equality is False
    assert any(face.crosses_seam for face in placement.contacts)


def test_arbitrary_precision_transition_has_no_vertical_ceiling() -> None:
    huge = 10**100
    heights = (huge, 0, huge + 7)
    result = transition_one_cell_periodic(
        heights=heights,
        launch_x=1,
        sticky_endpoint_selected=True,
    )

    assert result.launch_post_height == huge + 7
    assert result.delta_s == huge + 7
    assert result.delta_v == huge + 6
    assert result.delta_q == (huge + 7) ** 2
    assert result.causal_side is OneCellCausalSide.RIGHT
    assert result.equality_mask == 4

    top_only_state = SparseAggregate(3, {(0, huge - 1), (2, huge + 6)})
    placement = place_one(top_only_state, ONE_CELL, 1, ContactKind.EDGE_FIRST_CONTACT_V1)
    assert placement.landing_y + 1 == result.launch_post_height
    assert placement.early_arrest_gap == result.delta_v
    assert _envelope(placement.post_state) == result.post_heights


def test_input_is_snapshotted_without_mutating_the_caller() -> None:
    supplied = [2, 0, 4]
    original = supplied.copy()
    result = transition_one_cell_periodic(
        heights=supplied,
        launch_x=1,
        sticky_endpoint_selected=True,
    )

    assert supplied == original
    supplied[:] = [9, 9, 9]
    assert result.pre_heights == (2, 0, 4)
    assert result.post_heights == (2, 4, 4)
    assert hash(result)
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.delta_s = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "error", "match"),
    (
        ({"heights": (0, 0)}, ValueError, "at least three"),
        ({"heights": (0, -1, 0)}, ValueError, "nonnegative"),
        ({"heights": (0, True, 0)}, TypeError, "built-in integers"),
        ({"heights": (0, 1.0, 0)}, TypeError, "built-in integers"),
        ({"heights": {0, 1, 2}}, TypeError, "list or tuple"),
        ({"heights": (value for value in (0, 0, 0))}, TypeError, "list or tuple"),
        ({"launch_x": True}, TypeError, "built-in integer"),
        ({"launch_x": -1}, ValueError, r"\[0, width\)"),
        ({"launch_x": 3}, ValueError, r"\[0, width\)"),
        ({"sticky_endpoint_selected": 1}, TypeError, "built-in bool"),
    ),
)
def test_transition_rejects_hostile_inputs(
    changes: dict[str, object],
    error: type[Exception],
    match: str,
) -> None:
    kwargs: dict[str, object] = {
        "heights": (0, 0, 0),
        "launch_x": 1,
        "sticky_endpoint_selected": False,
    }
    kwargs.update(changes)
    with pytest.raises(error, match=match):
        transition_one_cell_periodic(**kwargs)  # type: ignore[arg-type]


def test_transition_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        transition_one_cell_periodic((0, 0, 0), 1, False)  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    (
        {"pre_heights": (5, 2, 4)},
        {"post_heights": (5, 4, 5)},
        {"launch_x": 0},
        {"sticky_endpoint_selected": False},
        {"left_pre_height": 6},
        {"launch_pre_height": 3},
        {"right_pre_height": 6},
        {"launch_post_height": 6},
        {"delta_s": 4},
        {"delta_v": 3},
        {"delta_q": 22},
        {"positive_gap_trigger": False},
        {"causal_side": OneCellCausalSide.LEFT},
        {"equality_mask": 7},
        {"seam_equality": True},
    ),
)
def test_direct_record_construction_rejects_inconsistent_primitives(changes: dict[str, object]) -> None:
    valid = transition_one_cell_periodic(
        heights=(5, 2, 5),
        launch_x=1,
        sticky_endpoint_selected=True,
    )
    with pytest.raises(ValueError, match="transition primitives|post_heights"):
        replace(valid, **changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"pre_heights": [5, 2, 5]},
        {"post_heights": [5, 5, 5]},
        {"launch_x": True},
        {"sticky_endpoint_selected": 1},
        {"left_pre_height": True},
        {"positive_gap_trigger": 1},
        {"causal_side": "both"},
        {"seam_equality": 0},
    ),
)
def test_direct_record_construction_rejects_noncanonical_types(changes: dict[str, object]) -> None:
    valid = transition_one_cell_periodic(
        heights=(5, 2, 5),
        launch_x=1,
        sticky_endpoint_selected=True,
    )
    with pytest.raises(TypeError):
        replace(valid, **changes)


def test_one_cell_surface_is_explicit_submodule_only_and_dependency_minimal() -> None:
    expected_exports = [
        "ONE_CELL_PERIODIC_MODEL_ID",
        "OneCellCausalSide",
        "OneCellPeriodicTransition",
        "transition_one_cell_periodic",
    ]
    assert one_cell_engine.__all__ == expected_exports
    for root in (tetris_ballistic, reference_engine):
        for name in expected_exports:
            assert not hasattr(root, name)

    tree = ast.parse(Path(one_cell_engine.__file__).read_text(encoding="utf-8"))
    imports = {
        (node.module, tuple(alias.name for alias in node.names))
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        ("__future__", ("annotations",)),
        ("dataclasses", ("dataclass",)),
        ("enum", ("Enum",)),
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
