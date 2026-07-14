"""Independent certification tests for one-certificate placement primitives."""

from __future__ import annotations

import builtins
from dataclasses import FrozenInstanceError, fields, replace
from itertools import product
from types import SimpleNamespace

import pytest

import tetris_ballistic.engine.event as event_engine
import tetris_ballistic.engine.observables as observable_engine
import tetris_ballistic.engine.reference as reference_engine
import tetris_ballistic.engine.rng as rng_engine
import tetris_ballistic.engine.selection as selection_engine
from tetris_ballistic.engine.observables import ReferencePlacementPrimitives, measure_placement
from tetris_ballistic.engine.reference import ContactFace, ContactFaceKind, ReferencePlacement, place_one
from tetris_ballistic.engine.state import SparseAggregate
from tetris_ballistic.models import GEOMETRY_BY_ID, ONE_CELL, ContactKind, PieceGeometry

Cell = tuple[int, int]
CountTuple = tuple[tuple[ContactFaceKind, int], ...]
GraphEdge = tuple[Cell, Cell]

_FACE_KINDS = tuple(ContactFaceKind)
_LATERAL_KINDS = frozenset({ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT})


def _counts(contacts: tuple[ContactFace, ...]) -> CountTuple:
    """Count faces in the public enum order without package helpers."""

    return tuple((kind, sum(contact.kind is kind for contact in contacts)) for kind in _FACE_KINDS)


def _column_heights(occupied: frozenset[Cell]) -> dict[int, int]:
    heights: dict[int, int] = {}
    for x, y in occupied:
        candidate = y + 1
        if candidate > heights.get(x, 0):
            heights[x] = candidate
    return heights


def _support_graph(
    sites: tuple[Cell, ...],
    *,
    width: int,
) -> tuple[tuple[GraphEdge, ...], int]:
    """Build the induced periodic-N4 graph by pairwise site comparison."""

    edges: list[GraphEdge] = []
    neighbors = {site: set() for site in sites}
    for index, left in enumerate(sites):
        for right in sites[index + 1 :]:
            vertical = left[0] == right[0] and abs(left[1] - right[1]) == 1
            horizontal = left[1] == right[1] and (left[0] - right[0]) % width in (1, width - 1)
            if vertical or horizontal:
                edge = (left, right) if left < right else (right, left)
                edges.append(edge)
                neighbors[left].add(right)
                neighbors[right].add(left)

    component_count = 0
    unseen = set(sites)
    while unseen:
        component_count += 1
        frontier = [unseen.pop()]
        while frontier:
            site = frontier.pop()
            for neighbor in neighbors[site]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    frontier.append(neighbor)
    return tuple(sorted(set(edges))), component_count


def _support_arc(
    columns: tuple[int, ...],
    *,
    width: int,
) -> tuple[int | None, int, tuple[int, ...]]:
    """Apply the S1a-09 largest-gap rule independently."""

    if not columns:
        return None, 0, ()
    if len(columns) == 1:
        return columns[0], 0, (width,)

    cyclic_gaps = tuple((columns[(index + 1) % len(columns)] - column) % width for index, column in enumerate(columns))
    largest_gap = max(cyclic_gaps)
    excluded_index = min(
        (index for index, gap in enumerate(cyclic_gaps) if gap == largest_gap),
        key=lambda index: columns[(index + 1) % len(columns)],
    )
    origin = columns[(excluded_index + 1) % len(columns)]
    rotated_gaps = cyclic_gaps[excluded_index + 1 :] + cyclic_gaps[: excluded_index + 1]
    return origin, width - largest_gap, rotated_gaps


def _independent_oracle(placement: ReferencePlacement) -> dict[str, object]:
    """Project only raw certificate fields using no observables implementation."""

    contacts = placement.contacts
    support_sites = tuple(
        sorted(
            {
                contact.neighbor_cell
                for contact in contacts
                if contact.kind is ContactFaceKind.AGGREGATE_SUPPORT and contact.neighbor_cell is not None
            }
        )
    )
    support_columns = tuple(sorted({x for x, _ in support_sites}))
    graph_edges, cluster_count = _support_graph(support_sites, width=placement.pre_state.width)
    arc_origin, arc_span, column_gaps = _support_arc(support_columns, width=placement.pre_state.width)

    pre_heights = _column_heights(placement.pre_state.occupied)
    post_heights = _column_heights(placement.post_state.occupied)
    envelope_changes = tuple(
        (x, pre_heights.get(x, 0), post_heights.get(x, 0))
        for x in sorted(pre_heights.keys() | post_heights.keys())
        if pre_heights.get(x, 0) != post_heights.get(x, 0)
    )
    height_sum_delta = sum(post_heights.values()) - sum(pre_heights.values())
    height_square_sum_delta = sum(height * height for height in post_heights.values()) - sum(
        height * height for height in pre_heights.values()
    )
    placed_mass = len(placement.post_state.occupied) - len(placement.pre_state.occupied)
    causal_contact_set = frozenset(placement.causal_contacts)

    return {
        "width": placement.pre_state.width,
        "contact_kind": placement.contact_kind,
        "placed_mass": placed_mass,
        "early_arrest_gap": placement.landing_y - placement.supported_landing_y,
        "lateral_trigger": (
            placement.contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1
            and placement.landing_y > placement.supported_landing_y
        ),
        "contact_face_kinds": tuple(contact.kind for contact in contacts),
        "contact_face_kind_counts": _counts(contacts),
        "causal_face_kind_counts": _counts(placement.causal_contacts),
        "causal_contact_mask": sum(
            1 << index for index, contact in enumerate(contacts) if contact in causal_contact_set
        ),
        "seam_lateral_face_count": sum(contact.crosses_seam and contact.kind in _LATERAL_KINDS for contact in contacts),
        "contacting_piece_cells": tuple(sorted({contact.piece_cell for contact in contacts})),
        "contacted_aggregate_cells": tuple(
            sorted({contact.neighbor_cell for contact in contacts if contact.neighbor_cell is not None})
        ),
        "contacted_support_sites": support_sites,
        "contacted_support_columns": support_columns,
        "support_graph_edges": graph_edges,
        "support_cluster_count": cluster_count,
        "support_arc_origin": arc_origin,
        "support_arc_span": arc_span,
        "support_column_gaps": column_gaps,
        "envelope_changes": envelope_changes,
        "height_sum_delta": height_sum_delta,
        "height_square_sum_delta": height_square_sum_delta,
        "void_count_delta": height_sum_delta - placed_mass,
    }


def _assert_matches_oracle(placement: ReferencePlacement) -> ReferencePlacementPrimitives:
    expected = _independent_oracle(placement)
    actual = measure_placement(placement)
    assert {name: getattr(actual, name) for name in expected} == expected
    assert all(type(value) is int for _, value in actual.contact_face_kind_counts)
    assert all(type(value) is int for _, value in actual.causal_face_kind_counts)
    assert all(type(kind) is ContactFaceKind for kind, _ in actual.contact_face_kind_counts)
    assert all(type(kind) is ContactFaceKind for kind, _ in actual.causal_face_kind_counts)
    return actual


@pytest.mark.parametrize(("width", "height"), ((3, 2), (4, 2)))
def test_exhaustive_small_one_cell_certificates_match_independent_oracle(width: int, height: int) -> None:
    cells = tuple((x, y) for y in range(height) for x in range(width))
    for occupancy_bits in product((False, True), repeat=len(cells)):
        occupied = frozenset(cell for cell, present in zip(cells, occupancy_bits) if present)
        state = SparseAggregate(width, occupied)
        for anchor_x in range(width):
            for contact_kind in (ContactKind.SUPPORTED_V1, ContactKind.EDGE_FIRST_CONTACT_V1):
                _assert_matches_oracle(place_one(state, ONE_CELL, anchor_x, contact_kind))


@pytest.mark.parametrize(
    ("width", "occupied", "geometry", "anchor_x", "contact_kind"),
    (
        (3, frozenset(), ONE_CELL, 0, ContactKind.SUPPORTED_V1),
        (4, frozenset({(0, 0), (1, 1)}), ONE_CELL, 0, ContactKind.EDGE_FIRST_CONTACT_V1),
        (5, frozenset({(4, 7)}), ONE_CELL, 0, ContactKind.EDGE_FIRST_CONTACT_V1),
        (
            5,
            frozenset({(0, 0), (1, 0), (2, 0), (3, 0)}),
            GEOMETRY_BY_ID["tetromino.i.00"],
            0,
            ContactKind.SUPPORTED_V1,
        ),
        (
            5,
            frozenset({(0, 0), (2, 0)}),
            GEOMETRY_BY_ID["tetromino.i.00"],
            0,
            ContactKind.SUPPORTED_V1,
        ),
        (
            5,
            frozenset({(0, 0), (4, 0)}),
            GEOMETRY_BY_ID["tetromino.i.00"],
            4,
            ContactKind.SUPPORTED_V1,
        ),
    ),
)
def test_named_floor_incidental_trigger_seam_cluster_and_arc_cases(
    width: int,
    occupied: frozenset[Cell],
    geometry: PieceGeometry,
    anchor_x: int,
    contact_kind: ContactKind,
) -> None:
    _assert_matches_oracle(place_one(SparseAggregate(width, occupied), geometry, anchor_x, contact_kind))


def test_floor_only_support_has_null_arc_and_no_support_cluster() -> None:
    actual = _assert_matches_oracle(place_one(SparseAggregate.empty(3), ONE_CELL, 1, ContactKind.SUPPORTED_V1))
    assert actual.contacted_support_sites == ()
    assert actual.contacted_support_columns == ()
    assert actual.support_graph_edges == ()
    assert actual.support_cluster_count == 0
    assert actual.support_arc_origin is None
    assert actual.support_arc_span == 0
    assert actual.support_column_gaps == ()


def test_singleton_support_arc_retains_full_width_gap() -> None:
    actual = _assert_matches_oracle(place_one(SparseAggregate(7, {(3, 9)}), ONE_CELL, 3, ContactKind.SUPPORTED_V1))
    assert actual.contacted_support_columns == (3,)
    assert actual.support_arc_origin == 3
    assert actual.support_arc_span == 0
    assert actual.support_column_gaps == (7,)


def test_largest_gap_tie_chooses_smallest_resulting_origin() -> None:
    horizontal_i = GEOMETRY_BY_ID["tetromino.i.00"]
    actual = _assert_matches_oracle(
        place_one(SparseAggregate(6, {(0, 0), (3, 0)}), horizontal_i, 0, ContactKind.SUPPORTED_V1)
    )
    assert actual.contacted_support_columns == (0, 3)
    assert actual.support_arc_origin == 0
    assert actual.support_arc_span == 3
    assert actual.support_column_gaps == (3, 3)


def test_causal_mask_indexes_canonical_final_contact_order() -> None:
    placement = place_one(
        SparseAggregate(4, {(0, 0), (1, 1)}),
        ONE_CELL,
        0,
        ContactKind.EDGE_FIRST_CONTACT_V1,
    )
    actual = _assert_matches_oracle(placement)
    expected_indices = tuple(
        index for index, contact in enumerate(placement.contacts) if contact in placement.causal_contacts
    )
    assert (
        tuple(index for index in range(len(placement.contacts)) if actual.causal_contact_mask & (1 << index))
        == expected_indices
    )


def test_huge_width_and_height_require_no_dense_allocation(monkeypatch: pytest.MonkeyPatch) -> None:
    huge_width = 10**1000
    huge_y = 10**1000
    placement = place_one(
        SparseAggregate(huge_width, {(0, huge_y), (huge_width - 1, 0)}),
        ONE_CELL,
        0,
        ContactKind.SUPPORTED_V1,
    )

    def guarded_range(*args: int) -> range:
        if any(abs(value) > 8 for value in args):
            raise AssertionError("measurement attempted a width- or height-sized range")
        return builtins.range(*args)

    monkeypatch.setattr(observable_engine, "range", guarded_range, raising=False)
    actual = _assert_matches_oracle(placement)
    assert actual.width == huge_width
    assert actual.envelope_changes == ((0, huge_y + 1, huge_y + 2),)
    assert actual.height_sum_delta == 1
    assert actual.height_square_sum_delta == 2 * huge_y + 3


@pytest.mark.parametrize("invalid", (object(), SimpleNamespace(pre_state=SparseAggregate.empty(3))))
def test_measure_placement_requires_exact_reference_placement(invalid: object) -> None:
    with pytest.raises(TypeError, match="placement must be a ReferencePlacement"):
        measure_placement(invalid)  # type: ignore[arg-type]


def test_measure_placement_rejects_reference_placement_subclasses() -> None:
    class ReferencePlacementSubclass(ReferencePlacement):
        pass

    placement = place_one(SparseAggregate.empty(3), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    subclass = ReferencePlacementSubclass(*(getattr(placement, field.name) for field in fields(ReferencePlacement)))
    with pytest.raises(TypeError, match="placement must be a ReferencePlacement"):
        measure_placement(subclass)


def test_measure_placement_rejects_partially_initialized_certificate() -> None:
    forged = object.__new__(ReferencePlacement)
    object.__setattr__(forged, "geometry_id", "baseline.one-cell")
    with pytest.raises(TypeError, match="placement must be fully initialized"):
        measure_placement(forged)


def test_measure_placement_defensively_revalidates_certificate() -> None:
    forged = place_one(SparseAggregate.empty(3), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    object.__setattr__(forged, "causal_contacts", ())
    with pytest.raises(ValueError, match="causal_contacts"):
        measure_placement(forged)


def test_measure_placement_rejects_hostile_nested_container_before_iteration() -> None:
    class HostileTuple(tuple[ContactFace, ...]):
        def __iter__(self):  # type: ignore[no-untyped-def]
            raise AssertionError("hostile contact tuple was iterated")

    forged = place_one(SparseAggregate.empty(3), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    object.__setattr__(forged, "contacts", HostileTuple(forged.contacts))
    with pytest.raises(TypeError, match="contacts must be a built-in tuple"):
        measure_placement(forged)


def test_measure_placement_detaches_from_revalidated_certificate() -> None:
    placement = place_one(SparseAggregate(3, {(1, 4)}), ONE_CELL, 1, ContactKind.SUPPORTED_V1)
    actual = measure_placement(placement)
    object.__setattr__(placement, "pre_state", SparseAggregate.empty(3))
    assert actual.contacted_support_sites == ((1, 4),)
    assert actual.envelope_changes == ((1, 5, 6),)


def test_placement_record_field_order_frozen_slots_and_valid_construction_are_pinned() -> None:
    expected_fields = (
        "width",
        "contact_kind",
        "placed_mass",
        "early_arrest_gap",
        "lateral_trigger",
        "contact_face_kinds",
        "contact_face_kind_counts",
        "causal_face_kind_counts",
        "causal_contact_mask",
        "seam_lateral_face_count",
        "contacting_piece_cells",
        "contacted_aggregate_cells",
        "contacted_support_sites",
        "contacted_support_columns",
        "support_graph_edges",
        "support_cluster_count",
        "support_arc_origin",
        "support_arc_span",
        "support_column_gaps",
        "envelope_changes",
        "height_sum_delta",
        "height_square_sum_delta",
        "void_count_delta",
    )
    assert tuple(field.name for field in fields(ReferencePlacementPrimitives)) == expected_fields
    actual = measure_placement(
        place_one(
            SparseAggregate(5, {(0, 0), (2, 0)}),
            GEOMETRY_BY_ID["tetromino.i.00"],
            0,
            ContactKind.SUPPORTED_V1,
        )
    )
    reconstructed = ReferencePlacementPrimitives(*(getattr(actual, name) for name in expected_fields))
    assert reconstructed == actual
    with pytest.raises(FrozenInstanceError):
        actual.placed_mass = 99  # type: ignore[misc]
    assert not hasattr(actual, "__dict__")


def test_direct_placement_record_construction_fails_closed() -> None:
    valid = measure_placement(
        place_one(
            SparseAggregate(5, {(0, 0), (2, 0)}),
            GEOMETRY_BY_ID["tetromino.i.00"],
            0,
            ContactKind.SUPPORTED_V1,
        )
    )
    wrong_contact_counts = tuple(reversed(valid.contact_face_kind_counts))
    negative_contact_counts = (
        (valid.contact_face_kind_counts[0][0], -1),
        *valid.contact_face_kind_counts[1:],
    )
    invalid_changes: tuple[dict[str, object], ...] = (
        {"width": True},
        {"width": 2},
        {"contact_kind": ContactKind.SUPPORTED},
        {"contact_kind": ContactKind.SUPPORTED_V1.value},
        {"placed_mass": True},
        {"placed_mass": 0},
        {"early_arrest_gap": -1},
        {"lateral_trigger": 1},
        {"lateral_trigger": True},
        {"contact_face_kinds": list(valid.contact_face_kinds)},
        {"contact_face_kinds": (ContactFaceKind.AGGREGATE_ABOVE,) * len(valid.contact_face_kinds)},
        {"contact_face_kind_counts": list(valid.contact_face_kind_counts)},
        {"contact_face_kind_counts": wrong_contact_counts},
        {"contact_face_kind_counts": negative_contact_counts},
        {"causal_face_kind_counts": list(valid.causal_face_kind_counts)},
        {"causal_face_kind_counts": wrong_contact_counts},
        {"causal_contact_mask": True},
        {"causal_contact_mask": valid.causal_contact_mask ^ 1},
        {"seam_lateral_face_count": -1},
        {
            "seam_lateral_face_count": 1
            + sum(value for kind, value in valid.contact_face_kind_counts if kind in _LATERAL_KINDS)
        },
        {"contacting_piece_cells": list(valid.contacting_piece_cells)},
        {"contacting_piece_cells": tuple(reversed(valid.contacting_piece_cells))},
        {"contacted_aggregate_cells": list(valid.contacted_aggregate_cells)},
        {"contacted_aggregate_cells": valid.contacted_aggregate_cells + valid.contacted_aggregate_cells[:1]},
        {"contacted_support_sites": list(valid.contacted_support_sites)},
        {"contacted_support_sites": ((valid.width, 0),)},
        {"contacted_support_columns": list(valid.contacted_support_columns)},
        {"contacted_support_columns": tuple(reversed(valid.contacted_support_columns))},
        {"support_graph_edges": list(valid.support_graph_edges)},
        {"support_graph_edges": (((2, 0), (0, 0)),)},
        {"support_cluster_count": True},
        {"support_cluster_count": valid.support_cluster_count + 1},
        {"support_arc_origin": valid.width},
        {"support_arc_span": valid.support_arc_span + 1},
        {"support_column_gaps": valid.support_column_gaps + (1,)},
        {"envelope_changes": list(valid.envelope_changes)},
        {"envelope_changes": ((0, 1, 1),)},
        {"envelope_changes": tuple(reversed(valid.envelope_changes))},
        {"height_sum_delta": valid.height_sum_delta + 1},
        {"height_square_sum_delta": valid.height_square_sum_delta + 1},
        {"void_count_delta": valid.void_count_delta + 1},
    )
    for changes in invalid_changes:
        with pytest.raises((TypeError, ValueError), match="."):
            replace(valid, **changes)


def test_direct_placement_record_rejects_mask_on_incidental_contact_kind() -> None:
    valid = measure_placement(
        place_one(
            SparseAggregate(4, {(0, 0), (1, 1)}),
            ONE_CELL,
            0,
            ContactKind.EDGE_FIRST_CONTACT_V1,
        )
    )
    assert valid.contact_face_kinds == (
        ContactFaceKind.AGGREGATE_SUPPORT,
        ContactFaceKind.LATERAL_RIGHT,
    )
    assert valid.causal_contact_mask == 0b01
    with pytest.raises(ValueError, match="select exactly the causal contact kinds"):
        replace(valid, causal_contact_mask=0b10)


def test_measure_placement_calls_no_measure_state_rng_selection_event_or_placement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    placement = place_one(
        SparseAggregate(5, {(4, 7)}),
        ONE_CELL,
        0,
        ContactKind.EDGE_FIRST_CONTACT_V1,
    )

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("pure certificate measurement crossed a forbidden layer")

    monkeypatch.setattr(observable_engine, "measure_state", forbidden)
    monkeypatch.setattr(rng_engine, "raw_u64", forbidden)
    monkeypatch.setattr(selection_engine, "select_weighted", forbidden)
    monkeypatch.setattr(event_engine, "select_event", forbidden)
    monkeypatch.setattr(reference_engine, "place_one", forbidden)
    actual = measure_placement(placement)
    assert actual.lateral_trigger is True
    assert actual.seam_lateral_face_count == 1
