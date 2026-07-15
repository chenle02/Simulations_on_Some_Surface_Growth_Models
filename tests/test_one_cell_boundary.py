"""Independent certification for the three PRE one-cell boundary laws."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from dataclasses import FrozenInstanceError, dataclass, fields, replace
from itertools import product
from pathlib import Path

import numpy as np
import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.one_cell as one_cell_periodic
import tetris_ballistic.engine.one_cell_boundary as one_cell_boundary
import tetris_ballistic.engine.one_cell_coupling as one_cell_coupling
from tetris_ballistic.engine.one_cell import (
    OneCellCausalSide,
    OneCellPeriodicTransition,
    transition_one_cell_periodic,
)
from tetris_ballistic.engine.one_cell_boundary import (
    OneCellBoundaryLaw,
    OneCellBoundaryTransition,
    transition_one_cell_boundary,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARCHIVED_COMMITS = (
    "767577aaa00988a3eeb8a4a5a6c795234cb89aa2",
    "06d3e38c2fbdb19f8bc47ed24d09181e21e39bbf",
    "58b17f814c0b0e6c3e4f72ab62f072a2792e86e9",
    "a47ec6c6606bc78a86427cca7a2f331c68dce653",
    "218819fb67742f9f4652176cd61c180713edd448",
)
_ARCHIVED_SOURCE_PATH = "tetris_ballistic/tetris_ballistic.py"
_ARCHIVED_SOURCE_BLOB = "8c4f64f71a1e2b1769dbd1b37fee3c40df608323"
_ARCHIVED_SOURCE_SHA256 = "3ce8ade36fa1e471fa54cce6e3b3fd8950f0ef21d734343423f46275e83dc206"
_ARCHIVED_KERNEL_PATH = "tetris_ballistic/_kernel_1x1.py"
_ARCHIVED_KERNEL_BLOB = "3d6bf4c3f6bc622b357be1a328fd5fe4541a3d99"
_ARCHIVED_KERNEL_SHA256 = "eaeb255240fa05610c6d77abdc93df15020c6699b47cafac6a7444e98acd74c7"

_ARCHIVED_ENGINE_METHODS_SOURCE = '''\
def _surface_row(self, column):
    """O(1) replacement for ``_ffnz``: row of the topmost occupied cell.

    Equivalent to ``_ffnz(column)`` but uses the maintained
    ``self.heights`` array instead of scanning the substrate. Returns
    ``self.height`` if the column is empty (matching ``_ffnz``).

    Phase-1 optimization: see class docstring + the ``heights``
    attribute comment in ``__init__``.
    """
    if column < 0 or column >= self.width:
        return self.height
    h = self.heights[column]
    if h == self.height - 1:
        return self.height
    return h + 1

def _update_heights_for_columns(self, columns):
    """Re-sync ``self.heights`` for the columns just touched by a piece.

    After a ``_Place_*`` writes into a (small) set of substrate columns,
    we need to recompute their stack heights. We do this with one
    vectorized ``np.argmax`` over the small column slab — O(piece_cols * H)
    per call, vs O(W * H) for the legacy full-substrate ``_TopEnvelop``.

    The result is bit-identical to ``_TopEnvelop`` for those columns
    (semantics: ``heights[c]`` = row index just above topmost occupied,
    or ``height - 1`` if empty).
    """
    cols = sorted({c for c in columns if 0 <= c < self.width})
    if not cols:
        return
    slab = self.substrate[:, cols] > 0
    any_occupied = slab.any(axis=0)
    first_occupied = np.argmax(slab, axis=0)
    for k, c in enumerate(cols):
        if any_occupied[k]:
            self.heights[c] = int(first_occupied[k]) - 1
        else:
            self.heights[c] = self.height - 1

def _Place_1x1(self, position, landing_row, i):
    """
    Place a 1x1 piece.

    Args:
        position (int): The position of the pivot.
        landing_row (int): The landing row of the pivot.
        i (int): The step number.

    Return:
        None
    """
    self.substrate[landing_row - 1, position] = i

def Update_1x1(self, i, rot=0, sticky=True):
    """
    Updates the substrate with a 1x1 piece.

    Args:
        i (int): The step number.
        rot (int): The rotation of the piece. (No use, just be consistent with the others)
        sticky (bool): Whether the piece is sticky or not. (Default: True)

    Returns:
        int: The particle ID or the step number that has been placed in this step.
            + If the value is -1, it means it reaches to the top.
    """
    position = random.randint(0, self.width - 1)

    next = i

    landing_row_outleft = self._surface_row(position - 1) + 1 if position > 1 and sticky else self.height
    landing_row_pivot = self._surface_row(position)
    landing_row_outright = self._surface_row(position + 1) + 1 if position < self.width - 1 and sticky else self.height

    # Find minimum landing row
    landing_row = min(
        landing_row_outleft,
        landing_row_pivot,
        landing_row_outright)

    if landing_row < 2:
        self.FinalSteps = i
        return -1

    # Place square based on the minimum landing row
    next = i + 1
    self._Place_1x1(position, landing_row, next)
    # print(self.substrate)
    # input("")

    self._update_heights_for_columns(
        range(max(0, position - 3), min(self.width, position + 4)))
    self._UpdateStatus(i)
    return next
'''


class _FixedArchivedRandom:
    position = 0

    def randint(self, lower: int, upper: int) -> int:
        assert lower == 0
        assert lower <= self.position <= upper
        return self.position


_FIXED_ARCHIVED_RANDOM = _FixedArchivedRandom()
_ARCHIVED_ENGINE_NAMESPACE: dict[str, object] = {
    "np": np,
    "random": _FIXED_ARCHIVED_RANDOM,
}
exec(_ARCHIVED_ENGINE_METHODS_SOURCE, _ARCHIVED_ENGINE_NAMESPACE)


class _ArchivedOneCellHarness:
    pass


for _method_name in ("_surface_row", "_update_heights_for_columns", "_Place_1x1", "Update_1x1"):
    setattr(_ArchivedOneCellHarness, _method_name, _ARCHIVED_ENGINE_NAMESPACE[_method_name])


@dataclass(frozen=True)
class _OracleTransition:
    post_heights: tuple[int, ...]
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
    causal_side: str
    equality_mask: int
    seam_equality: bool | None


def _archived_inverted_row_oracle(
    heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> _OracleTransition:
    """Translate the archived top-origin Update_1x1 calculation literally."""

    width = len(heights)
    ceiling = max(heights) + 4
    top_origin_surface = tuple(ceiling - height for height in heights)
    landing_row_outleft = top_origin_surface[launch_x - 1] + 1 if sticky_endpoint_selected and launch_x > 1 else ceiling
    landing_row_pivot = top_origin_surface[launch_x]
    landing_row_outright = (
        top_origin_surface[launch_x + 1] + 1 if sticky_endpoint_selected and launch_x < width - 1 else ceiling
    )
    landing_row = min(landing_row_outleft, landing_row_pivot, landing_row_outright)
    launch_post_height = ceiling - (landing_row - 1)

    left_pre_height = heights[launch_x - 1] if launch_x > 0 else None
    right_pre_height = heights[launch_x + 1] if launch_x < width - 1 else None
    left_neighbor_eligible = launch_x > 1
    right_neighbor_eligible = launch_x < width - 1
    launch_pre_height = heights[launch_x]
    vertical_height = launch_pre_height + 1
    delta_v = launch_post_height - vertical_height
    positive_gap_trigger = sticky_endpoint_selected and delta_v > 0

    if not positive_gap_trigger:
        causal_side = "none"
    elif left_neighbor_eligible and left_pre_height == launch_post_height:
        if right_neighbor_eligible and right_pre_height == launch_post_height:
            causal_side = "both"
        else:
            causal_side = "left"
    else:
        causal_side = "right"

    equality_mask = (
        int(launch_post_height == vertical_height)
        + 2 * int(left_pre_height is not None and left_pre_height == launch_post_height)
        + 4 * int(right_pre_height is not None and right_pre_height == launch_post_height)
    )
    post_heights = list(heights)
    post_heights[launch_x] = launch_post_height
    return _OracleTransition(
        post_heights=tuple(post_heights),
        left_pre_height=left_pre_height,
        launch_pre_height=launch_pre_height,
        right_pre_height=right_pre_height,
        left_neighbor_eligible=left_neighbor_eligible,
        right_neighbor_eligible=right_neighbor_eligible,
        launch_post_height=launch_post_height,
        delta_s=launch_post_height - launch_pre_height,
        delta_v=delta_v,
        delta_q=launch_post_height**2 - launch_pre_height**2,
        positive_gap_trigger=positive_gap_trigger,
        causal_side=causal_side,
        equality_mask=equality_mask,
        seam_equality=None,
    )


def _execute_archived_one_cell_engine(
    heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> tuple[int, ...]:
    """Execute the exact embedded exp14 method bodies on one solid state."""

    width = len(heights)
    ceiling = max(heights) + 4
    engine = _ArchivedOneCellHarness()
    engine.width = width
    engine.height = ceiling
    engine.substrate = np.zeros((ceiling, width), dtype=np.uint32)
    for column, physical_height in enumerate(heights):
        if physical_height:
            engine.substrate[ceiling - physical_height :, column] = 1
    engine.heights = np.asarray([ceiling - physical_height - 1 for physical_height in heights], dtype=np.int64)
    engine.FinalSteps = None
    engine._UpdateStatus = lambda _: None
    _FIXED_ARCHIVED_RANDOM.position = launch_x

    assert engine.Update_1x1(0, sticky=sticky_endpoint_selected) == 1
    return tuple(ceiling - engine._surface_row(column) for column in range(width))


def _corrected_physical_height_oracle(
    heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> _OracleTransition:
    """Specify the corrected recurrence independently in physical heights."""

    width = len(heights)
    launch_pre_height = heights[launch_x]
    left_pre_height = heights[launch_x - 1] if launch_x > 0 else None
    right_pre_height = heights[launch_x + 1] if launch_x < width - 1 else None
    left_neighbor_eligible = launch_x > 0
    right_neighbor_eligible = launch_x < width - 1

    vertical_height = launch_pre_height + 1
    candidates = [vertical_height]
    if sticky_endpoint_selected and launch_x > 0:
        candidates.append(heights[launch_x - 1])
    if sticky_endpoint_selected and launch_x < width - 1:
        candidates.append(heights[launch_x + 1])
    launch_post_height = max(candidates)
    delta_v = launch_post_height - vertical_height
    positive_gap_trigger = sticky_endpoint_selected and delta_v > 0

    if not positive_gap_trigger:
        causal_side = "none"
    else:
        left_causal = launch_x > 0 and heights[launch_x - 1] == launch_post_height
        right_causal = launch_x < width - 1 and heights[launch_x + 1] == launch_post_height
        if left_causal and right_causal:
            causal_side = "both"
        elif left_causal:
            causal_side = "left"
        else:
            causal_side = "right"

    equality_mask = int(launch_post_height == vertical_height)
    if launch_x > 0 and heights[launch_x - 1] == launch_post_height:
        equality_mask += 2
    if launch_x < width - 1 and heights[launch_x + 1] == launch_post_height:
        equality_mask += 4
    post_heights = list(heights)
    post_heights[launch_x] = launch_post_height
    return _OracleTransition(
        post_heights=tuple(post_heights),
        left_pre_height=left_pre_height,
        launch_pre_height=launch_pre_height,
        right_pre_height=right_pre_height,
        left_neighbor_eligible=left_neighbor_eligible,
        right_neighbor_eligible=right_neighbor_eligible,
        launch_post_height=launch_post_height,
        delta_s=launch_post_height - launch_pre_height,
        delta_v=delta_v,
        delta_q=launch_post_height**2 - launch_pre_height**2,
        positive_gap_trigger=positive_gap_trigger,
        causal_side=causal_side,
        equality_mask=equality_mask,
        seam_equality=None,
    )


def _assert_matches_oracle(
    actual: OneCellBoundaryTransition,
    expected: _OracleTransition,
    *,
    boundary_law: OneCellBoundaryLaw,
    pre_heights: tuple[int, ...],
    launch_x: int,
    sticky_endpoint_selected: bool,
    context: str,
) -> None:
    assert actual.boundary_law is boundary_law, context
    assert actual.pre_heights == pre_heights, context
    assert actual.post_heights == expected.post_heights, context
    assert actual.launch_x == launch_x, context
    assert actual.sticky_endpoint_selected is sticky_endpoint_selected, context
    assert actual.left_pre_height == expected.left_pre_height, context
    assert actual.launch_pre_height == expected.launch_pre_height, context
    assert actual.right_pre_height == expected.right_pre_height, context
    assert actual.left_neighbor_eligible is expected.left_neighbor_eligible, context
    assert actual.right_neighbor_eligible is expected.right_neighbor_eligible, context
    assert actual.launch_post_height == expected.launch_post_height, context
    assert actual.delta_s == expected.delta_s, context
    assert actual.delta_v == expected.delta_v, context
    assert actual.delta_q == expected.delta_q, context
    assert actual.positive_gap_trigger is expected.positive_gap_trigger, context
    assert actual.causal_side.value == expected.causal_side, context
    assert actual.equality_mask == expected.equality_mask, context
    assert actual.seam_equality is expected.seam_equality, context
    assert actual.width == len(pre_heights), context
    assert actual.gap == actual.delta_v, context
    assert actual.delta_s == 1 + actual.delta_v, context
    assert sum(actual.post_heights) - sum(actual.pre_heights) == actual.delta_s, context
    assert (
        sum(height * height for height in actual.post_heights) - sum(height * height for height in actual.pre_heights)
        == actual.delta_q
    ), context


def _assert_periodic_projection(
    actual: OneCellBoundaryTransition,
    delegated: OneCellPeriodicTransition,
    *,
    context: str,
) -> None:
    assert actual.boundary_law is OneCellBoundaryLaw.PERIODIC, context
    assert actual.pre_heights == delegated.pre_heights, context
    assert actual.post_heights == delegated.post_heights, context
    assert actual.launch_x == delegated.launch_x, context
    assert actual.sticky_endpoint_selected is delegated.sticky_endpoint_selected, context
    assert actual.left_pre_height == delegated.left_pre_height, context
    assert actual.launch_pre_height == delegated.launch_pre_height, context
    assert actual.right_pre_height == delegated.right_pre_height, context
    assert actual.left_neighbor_eligible is True, context
    assert actual.right_neighbor_eligible is True, context
    assert actual.launch_post_height == delegated.launch_post_height, context
    assert actual.delta_s == delegated.delta_s, context
    assert actual.delta_v == delegated.delta_v, context
    assert actual.delta_q == delegated.delta_q, context
    assert actual.positive_gap_trigger is delegated.positive_gap_trigger, context
    assert actual.causal_side is delegated.causal_side, context
    assert actual.equality_mask == delegated.equality_mask, context
    assert actual.seam_equality is delegated.seam_equality, context


def _transition(
    boundary_law: OneCellBoundaryLaw,
    heights: tuple[int, ...] = (5, 0, 0),
    *,
    launch_x: int = 1,
    sticky_endpoint_selected: bool = True,
) -> OneCellBoundaryTransition:
    return transition_one_cell_boundary(
        boundary_law=boundary_law,
        heights=heights,
        launch_x=launch_x,
        sticky_endpoint_selected=sticky_endpoint_selected,
    )


def test_boundary_ids_fields_and_explicit_public_surface_are_exact() -> None:
    assert [(law.name, law.value) for law in OneCellBoundaryLaw] == [
        ("PERIODIC", "periodic-v1"),
        ("HARD_WALL_LEGACY_ASYMMETRIC", "hard-wall-legacy-asymmetric-v1"),
        ("HARD_WALL_REFLECTION_SYMMETRIC", "hard-wall-reflection-symmetric-v1"),
    ]
    assert one_cell_boundary.__all__ == [
        "OneCellBoundaryLaw",
        "OneCellBoundaryTransition",
        "transition_one_cell_boundary",
    ]
    assert tuple(field.name for field in fields(OneCellBoundaryTransition)) == (
        "boundary_law",
        "pre_heights",
        "post_heights",
        "launch_x",
        "sticky_endpoint_selected",
        "left_pre_height",
        "launch_pre_height",
        "right_pre_height",
        "left_neighbor_eligible",
        "right_neighbor_eligible",
        "launch_post_height",
        "delta_s",
        "delta_v",
        "delta_q",
        "positive_gap_trigger",
        "causal_side",
        "equality_mask",
        "seam_equality",
    )
    assert not hasattr(OneCellBoundaryTransition, "model_id")


def test_exhaustive_periodic_route_is_the_exact_slice_one_projection() -> None:
    case_count = 0
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            for launch_x in range(width):
                for sticky_endpoint_selected in (False, True):
                    context = f"width={width}, heights={heights}, x={launch_x}, sticky={sticky_endpoint_selected}"
                    expected = transition_one_cell_periodic(
                        heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    actual = _transition(
                        OneCellBoundaryLaw.PERIODIC,
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    _assert_periodic_projection(actual, expected, context=context)
                    case_count += 1
    assert case_count == 12_672


def test_exhaustive_legacy_route_matches_archived_engine_and_inverted_row_oracle() -> None:
    case_count = 0
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            for launch_x in range(width):
                for sticky_endpoint_selected in (False, True):
                    context = f"width={width}, heights={heights}, x={launch_x}, sticky={sticky_endpoint_selected}"
                    expected = _archived_inverted_row_oracle(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    archived_engine_post = _execute_archived_one_cell_engine(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    assert archived_engine_post == expected.post_heights, context
                    actual = _transition(
                        OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    _assert_matches_oracle(
                        actual,
                        expected,
                        boundary_law=OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
                        pre_heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                        context=context,
                    )
                    case_count += 1
    assert case_count == 12_672


def test_exhaustive_corrected_route_matches_separate_physical_height_oracle() -> None:
    case_count = 0
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            for launch_x in range(width):
                for sticky_endpoint_selected in (False, True):
                    context = f"width={width}, heights={heights}, x={launch_x}, sticky={sticky_endpoint_selected}"
                    expected = _corrected_physical_height_oracle(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    actual = _transition(
                        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                    )
                    _assert_matches_oracle(
                        actual,
                        expected,
                        boundary_law=OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
                        pre_heights=heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky_endpoint_selected,
                        context=context,
                    )
                    case_count += 1
    assert case_count == 12_672


def test_legacy_and_corrected_difference_set_is_exact() -> None:
    difference_counts = {3: 0, 4: 0, 5: 0}
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            for launch_x in range(width):
                for sticky in (False, True):
                    legacy = _archived_inverted_row_oracle(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky,
                    )
                    corrected = _corrected_physical_height_oracle(
                        heights,
                        launch_x=launch_x,
                        sticky_endpoint_selected=sticky,
                    )
                    differs = legacy.post_heights != corrected.post_heights
                    expected_difference = sticky and launch_x == 1 and heights[0] > max(heights[1] + 1, heights[2])
                    assert differs is expected_difference
                    if differs:
                        difference_counts[width] += 1
                    if launch_x in (0, width - 1) or launch_x != 1:
                        assert not differs
    assert difference_counts == {3: 8, 4: 32, 5: 128}
    assert sum(difference_counts.values()) == 168


@pytest.mark.parametrize(
    ("heights", "launch_x", "expected_post", "expected_side"),
    (
        ((0, 5, 0), 0, (5, 5, 0), OneCellCausalSide.RIGHT),
        ((0, 5, 0), 2, (0, 5, 5), OneCellCausalSide.LEFT),
    ),
)
@pytest.mark.parametrize(
    "boundary_law",
    (
        OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
    ),
)
def test_hard_wall_endpoints_admit_only_the_existing_interior_neighbor(
    boundary_law: OneCellBoundaryLaw,
    heights: tuple[int, ...],
    launch_x: int,
    expected_post: tuple[int, ...],
    expected_side: OneCellCausalSide,
) -> None:
    result = _transition(boundary_law, heights, launch_x=launch_x)
    assert result.post_heights == expected_post
    assert result.causal_side is expected_side
    assert result.seam_equality is None
    if launch_x == 0:
        assert result.left_pre_height is None
        assert result.left_neighbor_eligible is False
        assert result.equality_mask & 2 == 0
    else:
        assert result.right_pre_height is None
        assert result.right_neighbor_eligible is False
        assert result.equality_mask & 4 == 0


def test_decisive_archived_defect_witness_is_pinned() -> None:
    legacy = _transition(OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC)
    corrected = _transition(OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC)

    assert legacy.post_heights == (5, 1, 0)
    assert legacy.launch_post_height == 1
    assert legacy.left_pre_height == 5
    assert legacy.left_neighbor_eligible is False
    assert legacy.right_neighbor_eligible is True
    assert legacy.delta_v == 0
    assert legacy.causal_side is OneCellCausalSide.NONE
    assert corrected.post_heights == (5, 5, 0)
    assert corrected.launch_post_height == 5
    assert corrected.left_neighbor_eligible is True
    assert corrected.delta_v == 4
    assert corrected.causal_side is OneCellCausalSide.LEFT


def test_existing_but_legacy_ineligible_neighbor_remains_height_equal_not_causal() -> None:
    result = _transition(
        OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
        (1, 0, 0),
    )
    assert result.launch_post_height == 1
    assert result.left_pre_height == 1
    assert result.left_neighbor_eligible is False
    assert result.equality_mask == 3
    assert result.gap == 0
    assert result.positive_gap_trigger is False
    assert result.causal_side is OneCellCausalSide.NONE


def test_equal_existing_neighbors_separate_eligibility_equality_and_causality() -> None:
    legacy = _transition(OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC, (5, 0, 5))
    corrected = _transition(OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC, (5, 0, 5))

    assert legacy.launch_post_height == corrected.launch_post_height == 5
    assert legacy.equality_mask == corrected.equality_mask == 6
    assert (legacy.left_neighbor_eligible, legacy.right_neighbor_eligible) == (False, True)
    assert legacy.causal_side is OneCellCausalSide.RIGHT
    assert (corrected.left_neighbor_eligible, corrected.right_neighbor_eligible) == (True, True)
    assert corrected.causal_side is OneCellCausalSide.BOTH


@pytest.mark.parametrize(
    ("heights", "launch_x", "hard_wall_post", "periodic_post"),
    (
        ((0, 0, 5), 0, (1, 0, 5), (5, 0, 5)),
        ((5, 0, 0), 2, (5, 0, 1), (5, 0, 5)),
    ),
)
def test_hard_walls_never_wrap_across_the_periodic_seam(
    heights: tuple[int, ...],
    launch_x: int,
    hard_wall_post: tuple[int, ...],
    periodic_post: tuple[int, ...],
) -> None:
    periodic = _transition(OneCellBoundaryLaw.PERIODIC, heights, launch_x=launch_x)
    assert periodic.post_heights == periodic_post
    assert periodic.seam_equality is True
    for law in (
        OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
    ):
        hard_wall = _transition(law, heights, launch_x=launch_x)
        assert hard_wall.post_heights == hard_wall_post
        assert hard_wall.seam_equality is None


def test_nonsticky_event_ignores_law_eligible_neighbors() -> None:
    for law in OneCellBoundaryLaw:
        result = _transition(
            law,
            (10, 0, 11),
            sticky_endpoint_selected=False,
        )
        assert result.post_heights == (10, 1, 11)
        assert result.launch_post_height == 1
        assert result.gap == 0
        assert result.positive_gap_trigger is False
        assert result.causal_side is OneCellCausalSide.NONE


def test_corrected_law_is_exhaustively_reflection_symmetric() -> None:
    case_count = 0
    law = OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC
    for width in (3, 4, 5):
        for heights in product(range(4), repeat=width):
            reflected_heights = tuple(reversed(heights))
            for launch_x in range(width):
                for sticky in (False, True):
                    actual = _transition(law, heights, launch_x=launch_x, sticky_endpoint_selected=sticky)
                    reflected = _transition(
                        law,
                        reflected_heights,
                        launch_x=width - 1 - launch_x,
                        sticky_endpoint_selected=sticky,
                    )
                    assert actual.post_heights == tuple(reversed(reflected.post_heights))
                    assert actual.left_pre_height == reflected.right_pre_height
                    assert actual.right_pre_height == reflected.left_pre_height
                    assert actual.left_neighbor_eligible is reflected.right_neighbor_eligible
                    assert actual.right_neighbor_eligible is reflected.left_neighbor_eligible
                    assert actual.delta_s == reflected.delta_s
                    assert actual.delta_v == reflected.delta_v
                    assert actual.delta_q == reflected.delta_q
                    assert actual.positive_gap_trigger is reflected.positive_gap_trigger
                    assert actual.equality_mask & 1 == reflected.equality_mask & 1
                    assert bool(actual.equality_mask & 2) is bool(reflected.equality_mask & 4)
                    assert bool(actual.equality_mask & 4) is bool(reflected.equality_mask & 2)
                    side_swap = {
                        OneCellCausalSide.NONE: OneCellCausalSide.NONE,
                        OneCellCausalSide.LEFT: OneCellCausalSide.RIGHT,
                        OneCellCausalSide.RIGHT: OneCellCausalSide.LEFT,
                        OneCellCausalSide.BOTH: OneCellCausalSide.BOTH,
                    }
                    assert side_swap[actual.causal_side] is reflected.causal_side
                    case_count += 1
    assert case_count == 12_672


def test_archived_law_has_named_reflection_asymmetry() -> None:
    law = OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC
    forward = _transition(law, (5, 0, 0), launch_x=1)
    reflected = _transition(law, (0, 0, 5), launch_x=1)
    assert forward.post_heights == (5, 1, 0)
    assert tuple(reversed(reflected.post_heights)) == (5, 5, 0)
    assert forward.post_heights != tuple(reversed(reflected.post_heights))


def test_periodic_route_delegates_exactly_once_with_an_immutable_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_delegate = one_cell_boundary.transition_one_cell_periodic
    calls: list[dict[str, object]] = []

    def spy(**kwargs: object) -> OneCellPeriodicTransition:
        calls.append(kwargs)
        return real_delegate(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", spy)
    supplied = [2, 0, 4]
    result = transition_one_cell_boundary(
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        heights=supplied,
        launch_x=1,
        sticky_endpoint_selected=True,
    )

    assert supplied == [2, 0, 4]
    assert calls == [
        {
            "heights": (2, 0, 4),
            "launch_x": 1,
            "sticky_endpoint_selected": True,
        }
    ]
    assert result.pre_heights == (2, 0, 4)
    supplied[:] = [9, 9, 9]
    assert result.pre_heights == (2, 0, 4)


def test_hard_wall_routes_never_call_periodic_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(**_: object) -> OneCellPeriodicTransition:
        raise AssertionError("hard-wall routes must not call the periodic delegate")

    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", forbidden)
    assert _transition(OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC).launch_post_height == 1
    assert _transition(OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC).launch_post_height == 5


def _forge_periodic(**changes: object) -> OneCellPeriodicTransition:
    valid = transition_one_cell_periodic(
        heights=(2, 0, 4),
        launch_x=1,
        sticky_endpoint_selected=True,
    )
    forged = object.__new__(OneCellPeriodicTransition)
    for field in fields(OneCellPeriodicTransition):
        object.__setattr__(forged, field.name, changes.get(field.name, getattr(valid, field.name)))
    return forged


class _PeriodicTransitionSubclass(OneCellPeriodicTransition):
    pass


@pytest.mark.parametrize(
    "delegated",
    (
        object(),
        _PeriodicTransitionSubclass(
            pre_heights=(2, 0, 4),
            post_heights=(2, 4, 4),
            launch_x=1,
            sticky_endpoint_selected=True,
            left_pre_height=2,
            launch_pre_height=0,
            right_pre_height=4,
            launch_post_height=4,
            delta_s=4,
            delta_v=3,
            delta_q=16,
            positive_gap_trigger=True,
            causal_side=OneCellCausalSide.RIGHT,
            equality_mask=4,
            seam_equality=False,
        ),
        object.__new__(OneCellPeriodicTransition),
        _forge_periodic(delta_s=5),
        transition_one_cell_periodic(
            heights=(2, 0, 5),
            launch_x=1,
            sticky_endpoint_selected=True,
        ),
    ),
)
def test_periodic_route_rejects_wrong_subclass_malformed_and_cross_request_results(
    monkeypatch: pytest.MonkeyPatch,
    delegated: object,
) -> None:
    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", lambda **_: delegated)
    with pytest.raises(AssertionError):
        _transition(OneCellBoundaryLaw.PERIODIC, (2, 0, 4))


@pytest.mark.parametrize(
    ("changes", "error", "match"),
    (
        ({"boundary_law": "periodic-v1"}, TypeError, "OneCellBoundaryLaw"),
        ({"boundary_law": object()}, TypeError, "OneCellBoundaryLaw"),
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
def test_invalid_periodic_request_fails_before_delegation(
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, object],
    error: type[Exception],
    match: str,
) -> None:
    def forbidden(**_: object) -> OneCellPeriodicTransition:
        raise AssertionError("invalid requests must fail before delegation")

    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", forbidden)
    kwargs: dict[str, object] = {
        "boundary_law": OneCellBoundaryLaw.PERIODIC,
        "heights": (0, 0, 0),
        "launch_x": 1,
        "sticky_endpoint_selected": False,
    }
    kwargs.update(changes)
    with pytest.raises(error, match=match):
        transition_one_cell_boundary(**kwargs)  # type: ignore[arg-type]


class _IntSubclass(int):
    pass


def test_integer_subclasses_and_keywordless_call_are_rejected() -> None:
    with pytest.raises(TypeError, match="built-in integers"):
        _transition(OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC, (0, _IntSubclass(0), 0))
    with pytest.raises(TypeError, match="built-in integer"):
        _transition(
            OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
            launch_x=_IntSubclass(1),
        )
    with pytest.raises(TypeError):
        transition_one_cell_boundary(  # type: ignore[misc]
            OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
            (0, 0, 0),
            1,
            False,
        )


@pytest.mark.parametrize(
    "changes",
    (
        {"boundary_law": OneCellBoundaryLaw.PERIODIC},
        {"pre_heights": (6, 2, 5)},
        {"post_heights": (5, 5, 6)},
        {"launch_x": 0},
        {"sticky_endpoint_selected": False},
        {"left_pre_height": 6},
        {"launch_pre_height": 3},
        {"right_pre_height": 6},
        {"left_neighbor_eligible": False},
        {"right_neighbor_eligible": False},
        {"launch_post_height": 6},
        {"delta_s": 4},
        {"delta_v": 3},
        {"delta_q": 22},
        {"positive_gap_trigger": False},
        {"causal_side": OneCellCausalSide.RIGHT},
        {"equality_mask": 7},
        {"seam_equality": False},
    ),
)
def test_direct_record_construction_rejects_every_inconsistent_primitive(changes: dict[str, object]) -> None:
    valid = _transition(
        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
        (5, 2, 5),
    )
    with pytest.raises(ValueError, match="transition primitives|post_heights"):
        replace(valid, **changes)


@pytest.mark.parametrize(
    "changes",
    (
        {"boundary_law": "hard-wall-reflection-symmetric-v1"},
        {"pre_heights": [5, 2, 5]},
        {"post_heights": [5, 5, 5]},
        {"launch_x": True},
        {"sticky_endpoint_selected": 1},
        {"left_pre_height": True},
        {"launch_pre_height": True},
        {"right_pre_height": True},
        {"left_neighbor_eligible": 1},
        {"right_neighbor_eligible": 1},
        {"launch_post_height": True},
        {"delta_s": True},
        {"delta_v": True},
        {"delta_q": True},
        {"positive_gap_trigger": 1},
        {"causal_side": "both"},
        {"equality_mask": True},
        {"seam_equality": 0},
    ),
)
def test_direct_record_construction_rejects_every_noncanonical_field_type(changes: dict[str, object]) -> None:
    valid = _transition(
        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
        (5, 2, 5),
    )
    with pytest.raises(TypeError):
        replace(valid, **changes)


def test_direct_periodic_record_recertification_does_not_call_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    valid = _transition(OneCellBoundaryLaw.PERIODIC, (2, 0, 4))

    def forbidden(**_: object) -> OneCellPeriodicTransition:
        raise AssertionError("direct record recertification must not delegate")

    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", forbidden)
    assert replace(valid) == valid


def test_arbitrary_precision_and_frozen_slotted_snapshot() -> None:
    huge = 10**100
    supplied = [huge, 0, huge + 7]
    result = _transition(
        OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
        tuple(supplied),
    )
    assert result.launch_post_height == huge + 7
    assert result.delta_s == huge + 7
    assert result.delta_v == huge + 6
    assert result.delta_q == (huge + 7) ** 2
    assert result.causal_side is OneCellCausalSide.RIGHT
    assert result.equality_mask == 4
    assert hash(result)
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.delta_s = 99  # type: ignore[misc]


def test_public_alias_rebinding_cannot_change_saved_authorities_or_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_law = OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC
    saved_type = OneCellBoundaryTransition
    existing = _transition(saved_law)
    monkeypatch.setattr(one_cell_boundary, "OneCellBoundaryLaw", object())
    monkeypatch.setattr(one_cell_boundary, "OneCellBoundaryTransition", object())
    monkeypatch.setattr(one_cell_boundary, "OneCellCausalSide", object())

    fresh = transition_one_cell_boundary(
        boundary_law=saved_law,
        heights=(5, 0, 0),
        launch_x=1,
        sticky_endpoint_selected=True,
    )
    assert type(fresh) is saved_type
    assert fresh == existing
    assert existing.width == 3
    assert existing.gap == 4


def test_boundary_surface_is_explicit_submodule_only_and_dependency_minimal() -> None:
    expected_exports = [
        "OneCellBoundaryLaw",
        "OneCellBoundaryTransition",
        "transition_one_cell_boundary",
    ]
    for root in (tetris_ballistic, reference_engine, one_cell_periodic, one_cell_coupling):
        for name in expected_exports:
            assert not hasattr(root, name)

    tree = ast.parse(Path(one_cell_boundary.__file__).read_text(encoding="utf-8"))
    imports = {
        (node.module, node.level, tuple(alias.name for alias in node.names))
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert imports == {
        ("__future__", 0, ("annotations",)),
        ("dataclasses", 0, ("dataclass",)),
        ("enum", 0, ("Enum",)),
        (
            "one_cell",
            1,
            ("OneCellCausalSide", "OneCellPeriodicTransition", "transition_one_cell_periodic"),
        ),
    }
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))


def test_independent_oracles_do_not_call_subject_or_each_other() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"_archived_inverted_row_oracle", "_corrected_physical_height_oracle"}
    }
    assert set(functions) == {"_archived_inverted_row_oracle", "_corrected_physical_height_oracle"}
    for name, function in functions.items():
        called_names = {
            node.func.id
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "transition_one_cell_boundary" not in called_names
        assert "_derive_event" not in called_names
        other = (
            "_corrected_physical_height_oracle"
            if name == "_archived_inverted_row_oracle"
            else "_archived_inverted_row_oracle"
        )
        assert other not in called_names

    archived_source = ast.get_source_segment(
        Path(__file__).read_text(encoding="utf-8"), functions["_archived_inverted_row_oracle"]
    )
    corrected_source = ast.get_source_segment(
        Path(__file__).read_text(encoding="utf-8"), functions["_corrected_physical_height_oracle"]
    )
    assert archived_source is not None and "launch_x > 1" in archived_source
    assert corrected_source is not None and "launch_x > 0" in corrected_source


def test_vector_document_pins_archive_provenance_and_self_contained_oracles() -> None:
    text = (_REPO_ROOT / "docs" / "PRE-ONE-CELL-BOUNDARY-VECTORS.md").read_text(encoding="utf-8")
    for commit in _ARCHIVED_COMMITS:
        assert commit in text
    for value in (
        _ARCHIVED_SOURCE_PATH,
        _ARCHIVED_SOURCE_BLOB,
        _ARCHIVED_SOURCE_SHA256,
        _ARCHIVED_KERNEL_PATH,
        _ARCHIVED_KERNEL_BLOB,
        _ARCHIVED_KERNEL_SHA256,
        "12,672",
        "168",
        "(5, 0, 0)",
    ):
        assert value in text


def _normalized_archived_method_sources(source: str) -> dict[str, str]:
    method_names = {"_surface_row", "_update_heights_for_columns", "_Place_1x1", "Update_1x1"}
    tree = ast.parse(source)
    result: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in method_names:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            lines = segment.splitlines()
            if node.col_offset:
                lines = [lines[0], *(line[node.col_offset :] if line else line for line in lines[1:])]
            result[node.name] = "\n".join(lines).strip()
    assert set(result) == method_names
    return result


def _git_output(*args: str) -> bytes:
    completed = subprocess.run(
        ("git", *args),
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        pytest.skip("archived Git objects are absent from this checkout")
    return completed.stdout


@pytest.mark.slow
def test_full_local_history_recertifies_every_archived_blob_and_digest() -> None:
    for commit in _ARCHIVED_COMMITS:
        source_blob = _git_output("rev-parse", f"{commit}:{_ARCHIVED_SOURCE_PATH}").decode().strip()
        kernel_blob = _git_output("rev-parse", f"{commit}:{_ARCHIVED_KERNEL_PATH}").decode().strip()
        assert source_blob == _ARCHIVED_SOURCE_BLOB
        assert kernel_blob == _ARCHIVED_KERNEL_BLOB

    source = _git_output("show", f"{_ARCHIVED_COMMITS[0]}:{_ARCHIVED_SOURCE_PATH}")
    kernel = _git_output("show", f"{_ARCHIVED_COMMITS[0]}:{_ARCHIVED_KERNEL_PATH}")
    assert hashlib.sha256(source).hexdigest() == _ARCHIVED_SOURCE_SHA256
    assert hashlib.sha256(kernel).hexdigest() == _ARCHIVED_KERNEL_SHA256
    assert _normalized_archived_method_sources(source.decode("utf-8")) == _normalized_archived_method_sources(
        _ARCHIVED_ENGINE_METHODS_SOURCE
    )
    assert b"position > 1 and sticky" in source
    assert b"position < self.width - 1 and sticky" in source
    assert b"position > 1 and sticky" in kernel
    assert b"position < width - 1 and sticky" in kernel
