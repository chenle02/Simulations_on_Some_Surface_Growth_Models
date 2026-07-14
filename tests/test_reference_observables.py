"""Independent certification tests for pure reference-state primitives."""

from __future__ import annotations

import ast
import builtins
from dataclasses import FrozenInstanceError, fields, replace
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

import tetris_ballistic
import tetris_ballistic.engine as engine
import tetris_ballistic.engine.event as event_engine
import tetris_ballistic.engine.observables as observable_engine
import tetris_ballistic.engine.reference as reference_engine
import tetris_ballistic.engine.rng as rng_engine
import tetris_ballistic.engine.selection as selection_engine
from tetris_ballistic.engine.observables import ReferenceStatePrimitives, measure_state
from tetris_ballistic.engine.state import SparseAggregate

Cell = tuple[int, int]


def _independent_oracle(
    width: int,
    occupied: frozenset[Cell],
) -> tuple[tuple[tuple[int, int], ...], int, int, int, int]:
    """Derive exact primitives by a dense top-down scan, not the package code."""

    top = max((y for _, y in occupied), default=-1)
    envelope: list[int] = []
    for x in range(width):
        height = 0
        for y in range(top, -1, -1):
            if (x, y) in occupied:
                height = y + 1
                break
        envelope.append(height)
    frozen_envelope = tuple((x, height) for x, height in enumerate(envelope) if height > 0)
    height_sum = sum(height for _, height in frozen_envelope)
    height_square_sum = sum(height * height for _, height in frozen_envelope)
    void_count = height_sum - len(occupied)
    return frozen_envelope, len(occupied), height_sum, height_square_sum, void_count


def _assert_matches_oracle(state: SparseAggregate) -> None:
    actual = measure_state(state)
    envelope, mass, height_sum, height_square_sum, void_count = _independent_oracle(
        state.width,
        state.occupied,
    )
    assert actual == ReferenceStatePrimitives(
        width=state.width,
        nonzero_column_heights=envelope,
        occupied_mass=mass,
        height_sum=height_sum,
        height_square_sum=height_square_sum,
        below_envelope_volume=height_sum,
        void_count=void_count,
    )
    assert all(type(x) is int and type(height) is int for x, height in actual.nonzero_column_heights)
    assert all(
        type(value) is int
        for value in (
            actual.width,
            actual.occupied_mass,
            actual.height_sum,
            actual.height_square_sum,
            actual.below_envelope_volume,
            actual.void_count,
        )
    )


@pytest.mark.parametrize(("width", "height"), ((3, 3), (4, 3)))
def test_exhaustive_small_occupancy_states_match_independent_oracle(width: int, height: int) -> None:
    cells = tuple((x, y) for x in range(width) for y in range(height))
    for occupancy_bits in product((False, True), repeat=len(cells)):
        occupied = frozenset(cell for cell, present in zip(cells, occupancy_bits) if present)
        _assert_matches_oracle(SparseAggregate(width=width, occupied=occupied))


@pytest.mark.parametrize(
    "state",
    (
        SparseAggregate.empty(3),
        SparseAggregate(5, {(0, 0), (4, 0)}),
        SparseAggregate(5, {(0, 0), (0, 4), (2, 1), (4, 3)}),
        SparseAggregate(6, {(0, 7), (1, 0), (3, 2), (5, 7)}),
    ),
)
def test_empty_holey_seam_and_tied_top_states_match_oracle(state: SparseAggregate) -> None:
    _assert_matches_oracle(state)


def test_empty_state_has_zero_exact_primitives() -> None:
    assert measure_state(SparseAggregate.empty(4)) == ReferenceStatePrimitives(
        width=4,
        nonzero_column_heights=(),
        occupied_mass=0,
        height_sum=0,
        height_square_sum=0,
        below_envelope_volume=0,
        void_count=0,
    )


def test_huge_vertical_coordinate_requires_no_dense_vertical_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    huge_y = 10**1000
    state = SparseAggregate(3, {(0, huge_y), (2, 0)})

    def guarded_range(*args: int) -> range:
        if any(abs(value) > state.width for value in args):
            raise AssertionError("measurement attempted a height-sized range")
        return builtins.range(*args)

    monkeypatch.setattr(observable_engine, "range", guarded_range, raising=False)
    actual = measure_state(state)
    assert actual.nonzero_column_heights == ((0, huge_y + 1), (2, 1))
    assert actual.occupied_mass == 2
    assert actual.height_sum == huge_y + 2
    assert actual.height_square_sum == (huge_y + 1) ** 2 + 1
    assert actual.below_envelope_volume == huge_y + 2
    assert actual.void_count == huge_y


def test_huge_width_uses_exact_sparse_envelope_without_width_sized_allocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge_width = 10**1000
    state = SparseAggregate(huge_width, {(0, 0), (huge_width - 1, 2)})

    def guarded_range(*args: int) -> range:
        if any(abs(value) > 3 for value in args):
            raise AssertionError("measurement attempted a width-sized range")
        return builtins.range(*args)

    monkeypatch.setattr(observable_engine, "range", guarded_range, raising=False)
    actual = measure_state(state)
    assert actual.width == huge_width
    assert actual.nonzero_column_heights == ((0, 1), (huge_width - 1, 3))
    assert actual.occupied_mass == 2
    assert actual.height_sum == actual.below_envelope_volume == 4
    assert actual.height_square_sum == 10
    assert actual.void_count == 2


def test_sparse_state_snapshots_caller_cells_before_measurement() -> None:
    caller_cells = [[0, 0], [1, 3]]
    state = SparseAggregate(width=3, occupied=caller_cells)
    caller_cells[0][1] = 99
    caller_cells.append([2, 100])
    assert measure_state(state).nonzero_column_heights == ((0, 1), (1, 4))


def test_measure_state_revalidates_and_detaches_from_its_input() -> None:
    state = SparseAggregate(3, {(0, 0), (1, 2)})
    actual = measure_state(state)
    object.__setattr__(state, "occupied", frozenset({(2, 99)}))
    assert actual.nonzero_column_heights == ((0, 1), (1, 3))
    assert actual.occupied_mass == 2


@pytest.mark.parametrize("invalid", (object(), SimpleNamespace(width=3, occupied=frozenset())))
def test_measure_state_requires_exact_sparse_aggregate(invalid: object) -> None:
    with pytest.raises(TypeError, match="state must be a SparseAggregate"):
        measure_state(invalid)  # type: ignore[arg-type]


def test_measure_state_rejects_sparse_aggregate_subclasses() -> None:
    class SparseAggregateSubclass(SparseAggregate):
        pass

    with pytest.raises(TypeError, match="state must be a SparseAggregate"):
        measure_state(SparseAggregateSubclass.empty(3))


def test_measure_state_rejects_partially_initialized_sparse_aggregate() -> None:
    forged = object.__new__(SparseAggregate)
    object.__setattr__(forged, "width", 3)
    with pytest.raises(TypeError, match="state must be fully initialized"):
        measure_state(forged)


def test_measure_state_revalidates_forged_nested_values() -> None:
    forged = SparseAggregate.empty(3)
    object.__setattr__(forged, "occupied", frozenset({(3, 0)}))
    with pytest.raises(ValueError, match="occupied x coordinates"):
        measure_state(forged)


def test_measure_state_rejects_hostile_container_subclass_before_iteration() -> None:
    class HostileFrozenSet(frozenset[Cell]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            raise AssertionError("hostile container was iterated")

    forged = SparseAggregate.empty(3)
    object.__setattr__(forged, "occupied", HostileFrozenSet({(0, 0)}))
    with pytest.raises(TypeError, match="plain list, tuple, set, or frozenset"):
        measure_state(forged)


def test_record_field_order_and_valid_direct_construction_are_pinned() -> None:
    assert tuple(field.name for field in fields(ReferenceStatePrimitives)) == (
        "width",
        "nonzero_column_heights",
        "occupied_mass",
        "height_sum",
        "height_square_sum",
        "below_envelope_volume",
        "void_count",
    )
    record = ReferenceStatePrimitives(3, ((0, 1), (1, 3)), 2, 4, 10, 4, 2)
    assert record.nonzero_column_heights == ((0, 1), (1, 3))
    with pytest.raises(FrozenInstanceError):
        record.void_count = 3  # type: ignore[misc]
    assert not hasattr(record, "__dict__")


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"width": True}, "width"),
        ({"width": 2}, "width"),
        ({"nonzero_column_heights": [(0, 1), (1, 3)]}, "nonzero_column_heights"),
        ({"nonzero_column_heights": ((0, 1), [1, 3])}, "built-in \\(x, height\\) tuples"),
        ({"nonzero_column_heights": ((0, 1), (3, 3))}, "columns"),
        ({"nonzero_column_heights": ((0, 1), (True, 3))}, "columns"),
        ({"nonzero_column_heights": ((0, 1), (1, 0))}, "positive built-in integers"),
        ({"nonzero_column_heights": ((1, 3), (0, 1))}, "sorted"),
        ({"nonzero_column_heights": ((0, 1), (0, 3))}, "unique"),
        ({"occupied_mass": True}, "occupied_mass"),
        ({"occupied_mass": -1}, "occupied_mass"),
        ({"occupied_mass": 1, "void_count": 3}, "number of nonzero columns"),
        ({"height_sum": 5}, "height_sum"),
        ({"height_square_sum": 11}, "height_square_sum"),
        ({"below_envelope_volume": 5}, "below_envelope_volume"),
        ({"void_count": 1}, "void_count"),
        ({"occupied_mass": 5, "void_count": 0}, "occupied_mass"),
        ({"occupied_mass": 5, "void_count": -1}, "void_count"),
    ),
)
def test_direct_record_construction_fails_closed(changes: dict[str, object], message: str) -> None:
    valid = ReferenceStatePrimitives(3, ((0, 1), (1, 3)), 2, 4, 10, 4, 2)
    with pytest.raises((TypeError, ValueError), match=message):
        replace(valid, **changes)


def test_measure_state_calls_no_rng_selection_event_or_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("pure state measurement crossed a forbidden layer")

    monkeypatch.setattr(rng_engine, "raw_u64", forbidden)
    monkeypatch.setattr(selection_engine, "select_weighted", forbidden)
    monkeypatch.setattr(event_engine, "select_event", forbidden)
    monkeypatch.setattr(reference_engine, "place_one", forbidden)
    assert measure_state(SparseAggregate(3, {(1, 2)})).nonzero_column_heights == ((1, 3),)


def test_observables_module_has_only_the_approved_import_dependencies() -> None:
    source = Path(observable_engine.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.append((0, None, tuple(alias.name for alias in node.names)))
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.level, node.module, tuple(alias.name for alias in node.names)))
    assert imports == [
        (0, "__future__", ("annotations",)),
        (0, "dataclasses", ("dataclass",)),
        (1, "state", ("SparseAggregate",)),
    ]


def test_observable_symbols_remain_explicit_submodule_only() -> None:
    assert observable_engine.__all__ == ["ReferenceStatePrimitives", "measure_state"]
    assert not hasattr(tetris_ballistic, "ReferenceStatePrimitives")
    assert not hasattr(tetris_ballistic, "measure_state")
    assert not hasattr(engine, "ReferenceStatePrimitives")
    assert not hasattr(engine, "measure_state")
