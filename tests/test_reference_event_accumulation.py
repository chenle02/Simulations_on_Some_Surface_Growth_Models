"""Independent adversarial tests for exact reference-event accumulation.

Expected values in this module are reconstructed from raw bound certificates.
The oracle deliberately does not call accumulation helpers, ``measure_state``,
or ``measure_placement``.
"""

from __future__ import annotations

import ast
import builtins
from collections import Counter, defaultdict
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as engine_package
import tetris_ballistic.engine.accumulation as accumulation_engine
import tetris_ballistic.engine.binding as binding_engine
import tetris_ballistic.engine.event as event_engine
import tetris_ballistic.engine.observables as observable_engine
import tetris_ballistic.engine.reference as reference_engine
import tetris_ballistic.engine.rng as rng_engine
import tetris_ballistic.engine.selection as selection_engine
from tetris_ballistic.engine.accumulation import (
    ReferenceEventAccumulator,
    accumulate_event,
    start_event_accumulator,
)
from tetris_ballistic.engine.binding import ReferenceEventPlacement, place_selected_event
from tetris_ballistic.engine.event import ConditionalWeightedLaw, TetrominoEventLaw, TetrominoEventSelection
from tetris_ballistic.engine.reference import ContactFaceKind
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.selection import ExactWeightedLaw, UniformIntegerLaw, UniformSelection, WeightedSelection
from tetris_ballistic.engine.state import SparseAggregate
from tetris_ballistic.models import ContactKind

Cell = tuple[int, int]
EventSpec = tuple[str, int, str]
GapSignature = tuple[int, ...]
ContactGapKey = tuple[str, int, int, int]
TopologyKey = tuple[str, str, int, int, GapSignature, int]

_FAMILY_ORDER = ("i", "lj", "o", "sz", "t")
_ORIENTATION_BY_FAMILY = (
    ("i", ("tetromino.i.00", "tetromino.i.01")),
    ("lj", tuple(f"tetromino.lj.{index:02d}" for index in range(8))),
    ("o", ("tetromino.o.00",)),
    ("sz", tuple(f"tetromino.sz.{index:02d}" for index in range(4))),
    ("t", tuple(f"tetromino.t.{index:02d}" for index in range(4))),
)
_ORIENTATION_ORDER = tuple(orientation for _, orientations in _ORIENTATION_BY_FAMILY for orientation in orientations)
_FAMILY_BY_ORIENTATION = {
    orientation: family for family, orientations in _ORIENTATION_BY_FAMILY for orientation in orientations
}
_CONTACT_ORDER = ("supported-v1", "edge-first-contact-v1")
_FACE_ORDER = tuple(ContactFaceKind)
_LATERAL_FACES = frozenset({ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT})
_EXPECTED_FIELDS = (
    "root_seed",
    "coupling_group_id",
    "law",
    "width",
    "event_count",
    "current_state",
    "occupied_mass",
    "height_sum",
    "height_square_sum",
    "below_envelope_volume",
    "void_count",
    "family_counts",
    "orientation_counts",
    "contact_counts",
    "contact_face_kind_counts",
    "causal_face_kind_counts",
    "seam_lateral_face_count",
    "contacting_piece_cell_count",
    "contacted_aggregate_cell_count",
    "contacted_support_site_count",
    "contacted_support_column_count",
    "events_with_floor_support_face",
    "events_with_aggregate_support_face",
    "landing_gap_counts",
    "support_cluster_counts",
    "support_arc_span_counts",
    "support_gap_signature_counts",
    "pre_envelope_height_counts",
    "post_envelope_height_counts",
    "envelope_change_counts",
    "contact_gap_delta_counts",
    "topology_joint_counts",
    "height_sum_delta",
    "height_square_sum_delta",
    "void_count_delta",
)
_U64_MAX = (1 << 64) - 1
_U64_TERMINAL = 1 << 64
_U128_MAX = (1 << 128) - 1


def _event_law(
    width: int,
    *,
    family_counts: tuple[int, ...] = (1, 1, 1, 1, 1),
    orientation_updates: dict[str, tuple[int, ...]] | None = None,
    contact_counts: tuple[int, int] = (1, 1),
) -> TetrominoEventLaw:
    orientation_counts = {family: (1,) * len(orientations) for family, orientations in _ORIENTATION_BY_FAMILY}
    if orientation_updates:
        orientation_counts.update(orientation_updates)
    return TetrominoEventLaw(
        family_law=ExactWeightedLaw(_FAMILY_ORDER, family_counts),
        orientation_laws=ConditionalWeightedLaw(
            _FAMILY_ORDER,
            tuple(
                ExactWeightedLaw(orientations, orientation_counts[family])
                for family, orientations in _ORIENTATION_BY_FAMILY
            ),
        ),
        launch_law=UniformIntegerLaw(width),
        contact_law=ExactWeightedLaw(_CONTACT_ORDER, contact_counts),
    )


def _selection(
    spec: EventSpec,
    *,
    ordinal: int,
    law: TetrominoEventLaw,
    root_seed: int = 0x1234,
    coupling_group_id: str = "accumulation-oracle",
) -> TetrominoEventSelection:
    orientation_id, anchor_x, contact_id = spec
    family_id = _FAMILY_BY_ORIENTATION[orientation_id]
    family_index = _FAMILY_ORDER.index(family_id)
    orientations = dict(_ORIENTATION_BY_FAMILY)[family_id]
    orientation_index = orientations.index(orientation_id)
    contact_index = _CONTACT_ORDER.index(contact_id)
    return TetrominoEventSelection(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        event_ordinal=ordinal,
        law=law,
        family=WeightedSelection("family", family_id, SemanticDraw(family_index, 0)),
        orientation=WeightedSelection("orientation", orientation_id, SemanticDraw(orientation_index, 0)),
        launch=UniformSelection("launch", SemanticDraw(anchor_x, 0)),
        contact=WeightedSelection("contact", contact_id, SemanticDraw(contact_index, 0)),
    )


def _bind(
    state: SparseAggregate,
    spec: EventSpec,
    *,
    ordinal: int,
    law: TetrominoEventLaw,
    root_seed: int = 0x1234,
    coupling_group_id: str = "accumulation-oracle",
) -> ReferenceEventPlacement:
    return place_selected_event(
        state=state,
        selection=_selection(
            spec,
            ordinal=ordinal,
            law=law,
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
        ),
    )


def _column_heights(state: SparseAggregate) -> dict[int, int]:
    heights: dict[int, int] = {}
    for x, y in state.occupied:
        heights[x] = max(heights.get(x, 0), y + 1)
    return heights


def _whole_height_histogram(state: SparseAggregate) -> Counter[int]:
    heights = _column_heights(state)
    counts = Counter(heights.values())
    zero_count = state.width - len(heights)
    if zero_count:
        counts[0] = zero_count
    return counts


def _state_values(state: SparseAggregate) -> tuple[int, int, int, int]:
    heights = _column_heights(state)
    mass = len(state.occupied)
    height_sum = sum(heights.values())
    height_square_sum = sum(height * height for height in heights.values())
    return mass, height_sum, height_square_sum, height_sum - mass


def _support_topology(
    event: ReferenceEventPlacement,
) -> tuple[tuple[Cell, ...], tuple[int, ...], int, int, GapSignature]:
    placement = event.placement
    sites = tuple(
        sorted(
            {
                face.neighbor_cell
                for face in placement.contacts
                if face.kind is ContactFaceKind.AGGREGATE_SUPPORT and face.neighbor_cell is not None
            }
        )
    )
    columns = tuple(sorted({x for x, _ in sites}))
    adjacency = {site: set() for site in sites}
    for index, left in enumerate(sites):
        for right in sites[index + 1 :]:
            vertical = left[0] == right[0] and abs(left[1] - right[1]) == 1
            horizontal = left[1] == right[1] and (left[0] - right[0]) % placement.pre_state.width in (
                1,
                placement.pre_state.width - 1,
            )
            if vertical or horizontal:
                adjacency[left].add(right)
                adjacency[right].add(left)

    unseen = set(sites)
    clusters = 0
    while unseen:
        clusters += 1
        stack = [unseen.pop()]
        while stack:
            new_sites = adjacency[stack.pop()].intersection(unseen)
            unseen.difference_update(new_sites)
            stack.extend(new_sites)

    if not columns:
        return sites, columns, clusters, 0, ()
    if len(columns) == 1:
        return sites, columns, clusters, 0, (placement.pre_state.width,)
    cyclic_gaps = tuple(
        (columns[(index + 1) % len(columns)] - column) % placement.pre_state.width
        for index, column in enumerate(columns)
    )
    span = placement.pre_state.width - max(cyclic_gaps)
    signature = min(cyclic_gaps[index:] + cyclic_gaps[:index] for index in range(len(cyclic_gaps)))
    return sites, columns, clusters, span, signature


def _certified_gap_tuple(event: ReferenceEventPlacement) -> GapSignature:
    """Reproduce the placement API's coordinate-tie-broken gap order."""

    placement = event.placement
    support_columns = tuple(
        sorted(
            {
                face.neighbor_cell[0]
                for face in placement.contacts
                if face.kind is ContactFaceKind.AGGREGATE_SUPPORT and face.neighbor_cell is not None
            }
        )
    )
    if not support_columns:
        return ()
    if len(support_columns) == 1:
        return (placement.pre_state.width,)
    gaps = tuple(
        (support_columns[(index + 1) % len(support_columns)] - column) % placement.pre_state.width
        for index, column in enumerate(support_columns)
    )
    largest = max(gaps)
    excluded_index = min(
        (index for index, gap in enumerate(gaps) if gap == largest),
        key=lambda index: support_columns[(index + 1) % len(support_columns)],
    )
    origin_index = (excluded_index + 1) % len(support_columns)
    return gaps[origin_index:] + gaps[:origin_index]


def _count_tuple(counter: Counter[object], order: tuple[object, ...]) -> tuple[tuple[object, int], ...]:
    return tuple((key, counter[key]) for key in order)


def _sparse_counts(counter: Counter[object]) -> tuple[tuple[object, int], ...]:
    return tuple(sorted((key, count) for key, count in counter.items() if count))


def _oracle(
    *,
    empty_state: SparseAggregate,
    root_seed: int,
    coupling_group_id: str,
    law: TetrominoEventLaw,
    events: tuple[ReferenceEventPlacement, ...],
) -> dict[str, object]:
    family_counts: Counter[object] = Counter()
    orientation_counts: Counter[object] = Counter()
    contact_counts: Counter[object] = Counter()
    final_face_counts: Counter[object] = Counter()
    causal_face_counts: Counter[object] = Counter()
    landing_gap_counts: Counter[object] = Counter()
    cluster_counts: Counter[object] = Counter()
    span_counts: Counter[object] = Counter()
    signature_counts: Counter[object] = Counter()
    pre_height_counts: Counter[object] = Counter()
    post_height_counts: Counter[object] = Counter()
    envelope_change_counts: Counter[object] = Counter()
    contact_gap_delta_counts: Counter[ContactGapKey] = Counter()
    topology_totals: defaultdict[TopologyKey, list[int]] = defaultdict(lambda: [0, 0, 0])
    seam_lateral_face_count = 0
    contacting_piece_cell_count = 0
    contacted_aggregate_cell_count = 0
    contacted_support_site_count = 0
    contacted_support_column_count = 0
    events_with_floor_support_face = 0
    events_with_aggregate_support_face = 0
    height_sum_delta = 0
    height_square_sum_delta = 0
    void_count_delta = 0
    current_state = empty_state

    for ordinal, event in enumerate(events):
        placement = event.placement
        assert event.selection.event_ordinal == ordinal
        assert placement.pre_state == current_state
        pre_mass, pre_sum, pre_square, pre_void = _state_values(placement.pre_state)
        post_mass, post_sum, post_square, post_void = _state_values(placement.post_state)
        delta_sum = post_sum - pre_sum
        delta_square = post_square - pre_square
        delta_void = post_void - pre_void
        delta_roughness = placement.pre_state.width * delta_square - (post_sum * post_sum - pre_sum * pre_sum)
        gap = placement.landing_y - placement.supported_landing_y
        sites, columns, clusters, span, signature = _support_topology(event)

        family_counts[event.selection.family_id] += 1
        orientation_counts[event.selection.geometry_id] += 1
        contact_counts[event.selection.contact_id] += 1
        final_face_counts.update(face.kind for face in placement.contacts)
        causal_face_counts.update(face.kind for face in placement.causal_contacts)
        seam_lateral_face_count += sum(face.crosses_seam and face.kind in _LATERAL_FACES for face in placement.contacts)
        contacting_piece_cell_count += len({face.piece_cell for face in placement.contacts})
        contacted_aggregate_cell_count += len(
            {face.neighbor_cell for face in placement.contacts if face.neighbor_cell is not None}
        )
        contacted_support_site_count += len(sites)
        contacted_support_column_count += len(columns)
        events_with_floor_support_face += int(
            any(face.kind is ContactFaceKind.FLOOR_SUPPORT for face in placement.contacts)
        )
        events_with_aggregate_support_face += int(
            any(face.kind is ContactFaceKind.AGGREGATE_SUPPORT for face in placement.contacts)
        )
        landing_gap_counts[gap] += 1
        cluster_counts[clusters] += 1
        span_counts[span] += 1
        signature_counts[signature] += 1
        pre_height_counts.update(_whole_height_histogram(placement.pre_state))
        post_height_counts.update(_whole_height_histogram(placement.post_state))

        pre_heights = _column_heights(placement.pre_state)
        post_heights = _column_heights(placement.post_state)
        for x in sorted(pre_heights.keys() | post_heights.keys()):
            pre_height = pre_heights.get(x, 0)
            post_height = post_heights.get(x, 0)
            if pre_height != post_height:
                envelope_change_counts[(x, pre_height, post_height)] += 1

        contact_gap_delta_counts[(event.selection.contact_id, gap, delta_void, delta_roughness)] += 1
        topology_key = (
            event.selection.geometry_id,
            event.selection.contact_id,
            clusters,
            span,
            signature,
            len(columns),
        )
        topology_totals[topology_key][0] += 1
        topology_totals[topology_key][1] += delta_void
        topology_totals[topology_key][2] += delta_roughness
        height_sum_delta += delta_sum
        height_square_sum_delta += delta_square
        void_count_delta += delta_void
        assert post_mass - pre_mass == 4
        current_state = placement.post_state

    occupied_mass, height_sum, height_square_sum, void_count = _state_values(current_state)
    return {
        "root_seed": root_seed,
        "coupling_group_id": coupling_group_id,
        "law": law,
        "width": empty_state.width,
        "event_count": len(events),
        "current_state": current_state,
        "occupied_mass": occupied_mass,
        "height_sum": height_sum,
        "height_square_sum": height_square_sum,
        "below_envelope_volume": height_sum,
        "void_count": void_count,
        "family_counts": _count_tuple(family_counts, _FAMILY_ORDER),
        "orientation_counts": _count_tuple(orientation_counts, _ORIENTATION_ORDER),
        "contact_counts": _count_tuple(contact_counts, _CONTACT_ORDER),
        "contact_face_kind_counts": _count_tuple(final_face_counts, _FACE_ORDER),
        "causal_face_kind_counts": _count_tuple(causal_face_counts, _FACE_ORDER),
        "seam_lateral_face_count": seam_lateral_face_count,
        "contacting_piece_cell_count": contacting_piece_cell_count,
        "contacted_aggregate_cell_count": contacted_aggregate_cell_count,
        "contacted_support_site_count": contacted_support_site_count,
        "contacted_support_column_count": contacted_support_column_count,
        "events_with_floor_support_face": events_with_floor_support_face,
        "events_with_aggregate_support_face": events_with_aggregate_support_face,
        "landing_gap_counts": _sparse_counts(landing_gap_counts),
        "support_cluster_counts": _sparse_counts(cluster_counts),
        "support_arc_span_counts": _sparse_counts(span_counts),
        "support_gap_signature_counts": _sparse_counts(signature_counts),
        "pre_envelope_height_counts": _sparse_counts(pre_height_counts),
        "post_envelope_height_counts": _sparse_counts(post_height_counts),
        "envelope_change_counts": _sparse_counts(envelope_change_counts),
        "contact_gap_delta_counts": _sparse_counts(contact_gap_delta_counts),
        "topology_joint_counts": tuple(
            sorted((key, totals[0], totals[1], totals[2]) for key, totals in topology_totals.items())
        ),
        "height_sum_delta": height_sum_delta,
        "height_square_sum_delta": height_square_sum_delta,
        "void_count_delta": void_count_delta,
    }


def _assert_matches(actual: ReferenceEventAccumulator, expected: dict[str, object]) -> None:
    assert tuple(field.name for field in fields(ReferenceEventAccumulator)) == _EXPECTED_FIELDS
    assert tuple(expected) == _EXPECTED_FIELDS
    for name, value in expected.items():
        assert getattr(actual, name) == value, name


def _run_specs(
    specs: tuple[EventSpec, ...],
    *,
    width: int = 5,
    root_seed: int = 0x1234,
    coupling_group_id: str = "accumulation-oracle",
    law: TetrominoEventLaw | None = None,
) -> tuple[ReferenceEventAccumulator, tuple[ReferenceEventPlacement, ...]]:
    selected_law = law if law is not None else _event_law(width)
    empty = SparseAggregate.empty(width)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        law=selected_law,
    )
    events: list[ReferenceEventPlacement] = []
    state = empty
    for ordinal, spec in enumerate(specs):
        event = _bind(
            state,
            spec,
            ordinal=ordinal,
            law=selected_law,
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
        )
        accumulator = accumulate_event(accumulator=accumulator, event=event)
        events.append(event)
        state = event.placement.post_state
        _assert_matches(
            accumulator,
            _oracle(
                empty_state=empty,
                root_seed=root_seed,
                coupling_group_id=coupling_group_id,
                law=selected_law,
                events=tuple(events),
            ),
        )
    return accumulator, tuple(events)


def _all_specs(width: int) -> tuple[EventSpec, ...]:
    return tuple(
        (orientation_id, anchor_x, contact_id)
        for orientation_id in _ORIENTATION_ORDER
        for anchor_x in range(width)
        for contact_id in _CONTACT_ORDER
    )


def test_start_has_exact_zero_state_and_35_field_contract() -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    actual = start_event_accumulator(
        empty_state=empty,
        root_seed=0x1234,
        coupling_group_id="accumulation-oracle",
        law=law,
    )
    _assert_matches(
        actual,
        _oracle(
            empty_state=empty,
            root_seed=0x1234,
            coupling_group_id="accumulation-oracle",
            law=law,
            events=(),
        ),
    )
    assert not hasattr(actual, "__dict__")
    with pytest.raises(FrozenInstanceError):
        actual.event_count = 1  # type: ignore[misc]


def test_zero_event_record_rejects_every_nonzero_face_scalar_and_flag_cumulant() -> None:
    zero, _ = _run_specs(())
    assert all(count == 0 for _, count in zero.contact_face_kind_counts)
    assert all(count == 0 for _, count in zero.causal_face_kind_counts)

    for face_kind in ContactFaceKind:
        forged_faces = tuple((kind, 1 if kind is face_kind else count) for kind, count in zero.contact_face_kind_counts)
        changes: dict[str, object] = {
            "contact_face_kind_counts": forged_faces,
            "causal_face_kind_counts": forged_faces,
        }
        if face_kind is ContactFaceKind.AGGREGATE_SUPPORT:
            changes["contacted_support_site_count"] = 1
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(zero, **changes)

    scalar_and_flag_fields = (
        "seam_lateral_face_count",
        "contacting_piece_cell_count",
        "contacted_aggregate_cell_count",
        "contacted_support_site_count",
        "contacted_support_column_count",
        "events_with_floor_support_face",
        "events_with_aggregate_support_face",
    )
    for field_name in scalar_and_flag_fields:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(zero, **{field_name: 1})


def test_per_event_tetromino_face_piece_and_floor_flag_bounds() -> None:
    one_event, _ = _run_specs((("tetromino.lj.00", 0, "supported-v1"),))

    excessive_support = tuple(
        (kind, 5 if kind is ContactFaceKind.FLOOR_SUPPORT else count)
        for kind, count in one_event.contact_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="face|support|event"):
        replace(
            one_event,
            contact_face_kind_counts=excessive_support,
            causal_face_kind_counts=excessive_support,
        )

    for face_kind in (
        ContactFaceKind.LATERAL_LEFT,
        ContactFaceKind.LATERAL_RIGHT,
        ContactFaceKind.AGGREGATE_ABOVE,
    ):
        excessive_face = tuple(
            (kind, 5 if kind is face_kind else count) for kind, count in one_event.contact_face_kind_counts
        )
        with pytest.raises((AssertionError, TypeError, ValueError), match="face|lateral|above|event"):
            replace(one_event, contact_face_kind_counts=excessive_face)

    five_contacting_cells = tuple(
        (kind, 4 if kind is ContactFaceKind.LATERAL_LEFT else count)
        for kind, count in one_event.contact_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="piece|cell|event"):
        replace(
            one_event,
            contact_face_kind_counts=five_contacting_cells,
            contacting_piece_cell_count=5,
        )

    two_floor_events, _ = _run_specs(
        (("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.00", 5, "supported-v1")),
        width=10,
    )
    assert dict(two_floor_events.contact_face_kind_counts)[ContactFaceKind.FLOOR_SUPPORT] == 8
    with pytest.raises((AssertionError, TypeError, ValueError), match="floor|flag|event|face"):
        replace(two_floor_events, events_with_floor_support_face=1)


def test_face_capacity_is_bounded_by_selected_orientation_geometry() -> None:
    vertical_i, _ = _run_specs((("tetromino.i.01", 0, "supported-v1"),))
    assert dict(vertical_i.contact_face_kind_counts)[ContactFaceKind.FLOOR_SUPPORT] == 1
    forged_faces = tuple(
        (kind, 4 if kind is ContactFaceKind.FLOOR_SUPPORT else count)
        for kind, count in vertical_i.contact_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="orientation|geometry|capacity|face"):
        replace(
            vertical_i,
            contact_face_kind_counts=forged_faces,
            causal_face_kind_counts=forged_faces,
            contacting_piece_cell_count=4,
        )


def test_aggregate_contact_cell_count_cannot_undercount_support_faces() -> None:
    valid, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"),) * 2)
    final_faces = dict(valid.contact_face_kind_counts)
    assert final_faces[ContactFaceKind.AGGREGATE_SUPPORT] == 4
    assert valid.contacted_support_site_count == 4
    assert valid.contacted_aggregate_cell_count == 4
    with pytest.raises((AssertionError, TypeError, ValueError), match="aggregate|cell|face|support"):
        replace(valid, contacted_aggregate_cell_count=1)


def test_ratified_tetromino_support_sites_equal_support_columns() -> None:
    valid, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"),) * 2)
    key, count, void_sum, roughness_sum = valid.topology_joint_counts[1]
    forged_key = (key[0], key[1], 1, 0, (5,), 1)
    with pytest.raises((AssertionError, TypeError, ValueError), match="site|column|contiguous|support"):
        replace(
            valid,
            contacted_support_column_count=1,
            support_arc_span_counts=((0, 2),),
            support_gap_signature_counts=(((), 1), ((5,), 1)),
            topology_joint_counts=(
                valid.topology_joint_counts[0],
                (forged_key, count, void_sum, roughness_sum),
            ),
        )


def test_causal_face_kinds_are_bound_to_positive_gap_edge_events() -> None:
    supported, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"),))
    shifted_to_above = tuple(
        (
            kind,
            4 if kind is ContactFaceKind.AGGREGATE_ABOVE else 0 if kind is ContactFaceKind.FLOOR_SUPPORT else count,
        )
        for kind, count in supported.contact_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="causal|above|support"):
        replace(
            supported,
            contact_face_kind_counts=shifted_to_above,
            causal_face_kind_counts=shifted_to_above,
            events_with_floor_support_face=0,
        )

    positive_gap, _ = _run_specs(
        (
            ("tetromino.lj.04", 0, "supported-v1"),
            ("tetromino.i.01", 4, "edge-first-contact-v1"),
        )
    )
    assert any(
        contact_id == "edge-first-contact-v1" and gap > 0
        for (contact_id, gap, _, _), _ in positive_gap.contact_gap_delta_counts
    )
    missing_trigger = tuple(
        (kind, 0 if kind is ContactFaceKind.LATERAL_RIGHT else count)
        for kind, count in positive_gap.causal_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="causal|lateral|positive"):
        replace(positive_gap, causal_face_kind_counts=missing_trigger)

    excessive_left = tuple(
        (kind, 5 if kind is ContactFaceKind.LATERAL_LEFT else count)
        for kind, count in positive_gap.contact_face_kind_counts
    )
    excessive_causal_left = tuple(
        (kind, 5 if kind is ContactFaceKind.LATERAL_LEFT else count)
        for kind, count in positive_gap.causal_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="causal|lateral|positive"):
        replace(
            positive_gap,
            contact_face_kind_counts=excessive_left,
            causal_face_kind_counts=excessive_causal_left,
        )


def test_landing_gap_cannot_exceed_the_pre_envelope_height_range() -> None:
    valid, _ = _run_specs((("tetromino.i.00", 0, "edge-first-contact-v1"),))
    ((contact_key, count),) = valid.contact_gap_delta_counts
    contact_id, _, void_delta, roughness_delta = contact_key
    forged_faces = tuple(
        (
            kind,
            1 if kind is ContactFaceKind.LATERAL_LEFT else 0 if kind is ContactFaceKind.FLOOR_SUPPORT else face_count,
        )
        for kind, face_count in valid.contact_face_kind_counts
    )
    assert valid.pre_envelope_height_counts == ((0, valid.width),)
    with pytest.raises((AssertionError, TypeError, ValueError), match="gap|pre|envelope|height"):
        replace(
            valid,
            contact_face_kind_counts=forged_faces,
            causal_face_kind_counts=forged_faces,
            contacting_piece_cell_count=1,
            contacted_aggregate_cell_count=1,
            events_with_floor_support_face=0,
            landing_gap_counts=((1, 1),),
            contact_gap_delta_counts=(((contact_id, 1, void_delta, roughness_delta), count),),
        )


@pytest.mark.parametrize(
    ("specs", "totals"),
    (
        ((("tetromino.i.00", 0, "supported-v1"),), (4, 4, 4, 0, 4)),
        ((("tetromino.lj.00", 0, "supported-v1"),), (4, 6, 12, 2, 24)),
        (
            (
                ("tetromino.i.01", 0, "supported-v1"),
                ("tetromino.i.00", 1, "edge-first-contact-v1"),
            ),
            (8, 20, 80, 12, 0),
        ),
    ),
)
def test_named_mass_void_and_roughness_telescope(
    specs: tuple[EventSpec, ...],
    totals: tuple[int, int, int, int, int],
) -> None:
    actual, _ = _run_specs(specs)
    mass, height_sum, height_square_sum, void_count, roughness = totals
    assert (actual.occupied_mass, actual.height_sum, actual.height_square_sum, actual.void_count) == (
        mass,
        height_sum,
        height_square_sum,
        void_count,
    )
    assert actual.width * actual.height_square_sum - actual.height_sum**2 == roughness


def test_three_horizontal_layers_pin_whole_histograms_and_repeated_topology() -> None:
    actual, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"),) * 3)
    assert actual.pre_envelope_height_counts == ((0, 7), (1, 4), (2, 4))
    assert actual.post_envelope_height_counts == ((0, 3), (1, 4), (2, 4), (3, 4))
    assert sum(count for _, count in actual.pre_envelope_height_counts) == 15
    assert sum(count for _, count in actual.post_envelope_height_counts) == 15
    assert actual.landing_gap_counts == ((0, 3),)
    assert actual.support_cluster_counts == ((0, 1), (1, 2))
    assert actual.support_arc_span_counts == ((0, 1), (3, 2))
    assert actual.support_gap_signature_counts == (((), 1), ((1, 1, 1, 2), 2))
    assert (
        ("tetromino.i.00", "supported-v1", 1, 3, (1, 1, 1, 2), 4),
        2,
        0,
        32,
    ) in actual.topology_joint_counts


def test_named_singleton_seam_and_tied_support_topologies() -> None:
    singleton, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.01", 0, "supported-v1")))
    seam_cluster, _ = _run_specs((("tetromino.i.00", 2, "supported-v1"), ("tetromino.lj.01", 4, "supported-v1")))
    tied, _ = _run_specs(
        (("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.00", 3, "supported-v1")),
        width=6,
    )

    assert singleton.support_gap_signature_counts == (((), 1), ((5,), 1))
    assert (("tetromino.i.01", "supported-v1", 1, 0, (5,), 1), 1, 0, 72) in singleton.topology_joint_counts

    assert seam_cluster.support_gap_signature_counts == (((), 1), ((1, 4), 1))
    assert (("tetromino.lj.01", "supported-v1", 1, 1, (1, 4), 2), 1, 0, 2) in (seam_cluster.topology_joint_counts)
    assert seam_cluster.events_with_floor_support_face == 2
    assert seam_cluster.events_with_aggregate_support_face == 1

    assert tied.support_gap_signature_counts == (((), 1), ((3, 3), 1))
    assert (("tetromino.i.00", "supported-v1", 2, 3, (3, 3), 2), 1, 2, 0) in tied.topology_joint_counts


def test_singleton_topology_cannot_claim_two_clusters_in_one_column() -> None:
    valid, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.01", 0, "supported-v1")))
    key, count, void_sum, roughness_sum = valid.topology_joint_counts[1]
    forged_key = (key[0], key[1], 2, key[3], key[4], key[5])
    with pytest.raises((AssertionError, TypeError, ValueError), match="cluster|column"):
        replace(
            valid,
            support_cluster_counts=((0, 1), (2, 1)),
            topology_joint_counts=(
                valid.topology_joint_counts[0],
                (forged_key, count, void_sum, roughness_sum),
            ),
        )


def test_topology_support_width_is_bounded_by_selected_geometry() -> None:
    valid, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.01", 0, "supported-v1")))
    key, count, void_sum, roughness_sum = valid.topology_joint_counts[1]
    forged_key = (key[0], key[1], 1, 1, (1, 4), 2)
    forged_final_faces = tuple(
        (kind, 2 if kind is ContactFaceKind.AGGREGATE_SUPPORT else face_count)
        for kind, face_count in valid.contact_face_kind_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="geometry|span|column|width"):
        replace(
            valid,
            contact_face_kind_counts=forged_final_faces,
            contacted_support_site_count=2,
            contacted_support_column_count=2,
            support_arc_span_counts=((0, 1), (1, 1)),
            support_gap_signature_counts=(((), 1), ((1, 4), 1)),
            topology_joint_counts=(
                valid.topology_joint_counts[0],
                (forged_key, count, void_sum, roughness_sum),
            ),
        )


def test_zero_gap_edge_contact_keeps_incidental_laterals_out_of_causal_counts() -> None:
    actual, events = _run_specs(
        (
            ("tetromino.i.00", 0, "supported-v1"),
            ("tetromino.i.01", 4, "edge-first-contact-v1"),
        )
    )
    final = events[-1].placement
    assert final.early_arrest_gap == 0
    assert {contact.kind for contact in final.contacts} == {
        ContactFaceKind.FLOOR_SUPPORT,
        ContactFaceKind.LATERAL_LEFT,
        ContactFaceKind.LATERAL_RIGHT,
    }
    assert tuple(contact.kind for contact in final.causal_contacts) == (ContactFaceKind.FLOOR_SUPPORT,)
    assert actual.seam_lateral_face_count == 1
    assert actual.contact_face_kind_counts == (
        (ContactFaceKind.FLOOR_SUPPORT, 5),
        (ContactFaceKind.AGGREGATE_SUPPORT, 0),
        (ContactFaceKind.LATERAL_LEFT, 1),
        (ContactFaceKind.LATERAL_RIGHT, 1),
        (ContactFaceKind.AGGREGATE_ABOVE, 0),
    )
    assert actual.causal_face_kind_counts == (
        (ContactFaceKind.FLOOR_SUPPORT, 5),
        (ContactFaceKind.AGGREGATE_SUPPORT, 0),
        (ContactFaceKind.LATERAL_LEFT, 0),
        (ContactFaceKind.LATERAL_RIGHT, 0),
        (ContactFaceKind.AGGREGATE_ABOVE, 0),
    )


def test_translation_rotates_placement_gaps_but_not_accumulator_signature() -> None:
    left, left_events = _run_specs((("tetromino.i.00", 0, "supported-v1"), ("tetromino.i.00", 2, "supported-v1")))
    translated, translated_events = _run_specs(
        (("tetromino.i.00", 3, "supported-v1"), ("tetromino.i.00", 0, "supported-v1"))
    )
    left_raw = _certified_gap_tuple(left_events[-1])
    translated_raw = _certified_gap_tuple(translated_events[-1])
    assert (left_raw, translated_raw) == ((2, 1, 2), (1, 2, 2))
    assert (
        left.support_gap_signature_counts
        == translated.support_gap_signature_counts
        == (
            ((), 1),
            ((1, 2, 2), 1),
        )
    )
    assert left.support_arc_span_counts == translated.support_arc_span_counts


def test_checked_next_event_count_has_terminal_sentinel_without_wrap() -> None:
    checked = accumulation_engine._checked_next_event_count

    class IntSubclass(int):
        pass

    assert checked(0) == 1
    assert checked(_U64_MAX - 1) == _U64_MAX
    assert checked(_U64_MAX) == _U64_TERMINAL
    for invalid in (True, -1, _U64_TERMINAL, _U64_TERMINAL + 1, 0.0, IntSubclass(0)):
        with pytest.raises((TypeError, ValueError), match="."):
            checked(invalid)


def test_direct_equal_copy_is_structural_not_lineage_authentication() -> None:
    actual, _ = _run_specs((("tetromino.o.00", 4, "edge-first-contact-v1"),))
    copied = ReferenceEventAccumulator(*(getattr(actual, name) for name in _EXPECTED_FIELDS))
    assert copied == actual
    assert copied is not actual
    assert hash(copied) == hash(actual)
    assert not any("lineage" in name or "journal" in name or "digest" in name for name in _EXPECTED_FIELDS)


def test_success_measures_the_bound_placement_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0x1234,
        coupling_group_id="accumulation-oracle",
        law=law,
    )
    event = _bind(empty, ("tetromino.lj.00", 4, "edge-first-contact-v1"), ordinal=0, law=law)
    genuine_measurement = accumulation_engine.measure_placement
    calls: list[object] = []

    def measurement_spy(placement: object) -> object:
        calls.append(placement)
        return genuine_measurement(placement)

    monkeypatch.setattr(accumulation_engine, "measure_placement", measurement_spy)
    actual = accumulate_event(accumulator=accumulator, event=event)
    assert len(calls) == 1
    assert calls[0] == event.placement
    _assert_matches(
        actual,
        _oracle(
            empty_state=empty,
            root_seed=0x1234,
            coupling_group_id="accumulation-oracle",
            law=law,
            events=(event,),
        ),
    )


def test_address_law_ordinal_and_state_failures_precede_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    parent, first_events = _run_specs((("tetromino.i.00", 0, "supported-v1"),), law=law)
    current = parent.current_state
    candidates = (
        _bind(current, ("tetromino.o.00", 1, "supported-v1"), ordinal=1, law=law, root_seed=999),
        _bind(
            current,
            ("tetromino.o.00", 1, "supported-v1"),
            ordinal=1,
            law=law,
            coupling_group_id="other-group",
        ),
        _bind(
            current,
            ("tetromino.o.00", 1, "supported-v1"),
            ordinal=1,
            law=_event_law(5, contact_counts=(1, 2)),
        ),
        _bind(current, ("tetromino.o.00", 1, "supported-v1"), ordinal=0, law=law),
        _bind(SparseAggregate.empty(5), ("tetromino.o.00", 1, "supported-v1"), ordinal=1, law=law),
        _bind(SparseAggregate.empty(6), ("tetromino.o.00", 1, "supported-v1"), ordinal=1, law=_event_law(6)),
        _bind(current, ("tetromino.o.00", 1, "supported-v1"), ordinal=_U64_MAX, law=law),
    )

    def forbidden_measurement(*_args: object, **_kwargs: object) -> object:
        pytest.fail("placement measurement ran before continuity/address rejection")

    monkeypatch.setattr(accumulation_engine, "measure_placement", forbidden_measurement)
    for candidate in candidates:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            accumulate_event(accumulator=parent, event=candidate)
        assert parent.current_state == first_events[-1].placement.post_state
        assert parent.event_count == 1


def test_same_parent_can_branch_without_mutating_its_claimed_prefix() -> None:
    law = _event_law(5)
    parent, first_events = _run_specs((("tetromino.i.00", 0, "supported-v1"),), law=law)
    parent_copy = ReferenceEventAccumulator(*(getattr(parent, name) for name in _EXPECTED_FIELDS))
    left_event = _bind(
        parent.current_state,
        ("tetromino.i.00", 2, "supported-v1"),
        ordinal=1,
        law=law,
    )
    right_event = _bind(
        parent.current_state,
        ("tetromino.i.00", 1, "edge-first-contact-v1"),
        ordinal=1,
        law=law,
    )
    left = accumulate_event(accumulator=parent, event=left_event)
    right = accumulate_event(accumulator=parent, event=right_event)
    assert parent == parent_copy
    assert parent.event_count == 1
    assert left != right
    assert left.current_state != right.current_state
    for actual, event in ((left, left_event), (right, right_event)):
        _assert_matches(
            actual,
            _oracle(
                empty_state=SparseAggregate.empty(5),
                root_seed=0x1234,
                coupling_group_id="accumulation-oracle",
                law=law,
                events=(*first_events, event),
            ),
        )


def test_cross_binding_rejects_valid_but_wrong_delegated_primitives(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    parent, _ = _run_specs((("tetromino.i.01", 0, "supported-v1"),), law=law)
    event = _bind(
        parent.current_state,
        ("tetromino.i.00", 1, "supported-v1"),
        ordinal=1,
        law=law,
    )
    genuine = observable_engine.measure_placement(event.placement)
    assert genuine.seam_lateral_face_count == 1
    forged = replace(genuine, seam_lateral_face_count=0)
    assert forged.seam_lateral_face_count == 0
    calls = 0

    def poisoned_measurement(_placement: object) -> object:
        nonlocal calls
        calls += 1
        return forged

    monkeypatch.setattr(accumulation_engine, "measure_placement", poisoned_measurement)
    with pytest.raises((AssertionError, TypeError, ValueError), match="."):
        accumulate_event(accumulator=parent, event=event)
    assert calls == 1
    assert parent.event_count == 1


def test_cross_binding_rejects_a_primitive_from_another_valid_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0x1234,
        coupling_group_id="accumulation-oracle",
        law=law,
    )
    event = _bind(empty, ("tetromino.lj.00", 0, "supported-v1"), ordinal=0, law=law)
    other = _bind(empty, ("tetromino.i.01", 0, "supported-v1"), ordinal=0, law=law)
    wrong = observable_engine.measure_placement(other.placement)
    monkeypatch.setattr(accumulation_engine, "measure_placement", lambda _placement: wrong)
    with pytest.raises((AssertionError, TypeError, ValueError), match="."):
        accumulate_event(accumulator=accumulator, event=event)
    assert accumulator.event_count == 0


def test_authentic_selected_event_chain_matches_independent_oracle() -> None:
    width = 5
    root_seed = 0xBAD5EED
    coupling_group_id = "authentic-smoke"
    law = _event_law(width)
    empty = SparseAggregate.empty(width)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        law=law,
    )
    state = empty
    events: list[ReferenceEventPlacement] = []
    for ordinal in range(12):
        selection = event_engine.select_event(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            event_ordinal=ordinal,
            law=law,
        )
        event = place_selected_event(state=state, selection=selection)
        accumulator = accumulate_event(accumulator=accumulator, event=event)
        events.append(event)
        state = event.placement.post_state
        _assert_matches(
            accumulator,
            _oracle(
                empty_state=empty,
                root_seed=root_seed,
                coupling_group_id=coupling_group_id,
                law=law,
                events=tuple(events),
            ),
        )


def test_maximum_sparse_width_and_root_require_no_dense_width_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    width = 1 << 64
    root_seed = _U128_MAX
    group = "maximum-Ω-🚀"
    law = _event_law(width)
    empty = SparseAggregate.empty(width)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=root_seed,
        coupling_group_id=group,
        law=law,
    )
    event = _bind(
        empty,
        ("tetromino.i.00", width - 1, "supported-v1"),
        ordinal=0,
        law=law,
        root_seed=root_seed,
        coupling_group_id=group,
    )

    def guarded_range(*args: int) -> range:
        if any(abs(value) > 8 for value in args):
            raise AssertionError("accumulation attempted a width-sized range")
        return builtins.range(*args)

    monkeypatch.setattr(accumulation_engine, "range", guarded_range, raising=False)
    actual = accumulate_event(accumulator=accumulator, event=event)
    _assert_matches(
        actual,
        _oracle(
            empty_state=empty,
            root_seed=root_seed,
            coupling_group_id=group,
            law=law,
            events=(event,),
        ),
    )
    assert actual.current_state.occupied == frozenset({(0, 0), (1, 0), (2, 0), (width - 1, 0)})
    assert actual.pre_envelope_height_counts == ((0, width),)
    assert actual.post_envelope_height_counts == ((0, width - 4), (1, 4))
    assert width * actual.height_square_sum - actual.height_sum**2 == 4 * width - 16


def test_fold_calls_no_rng_selection_binding_or_placement_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0x1234,
        coupling_group_id="accumulation-oracle",
        law=law,
    )
    event = _bind(empty, ("tetromino.o.00", 4, "edge-first-contact-v1"), ordinal=0, law=law)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("accumulation crossed a forbidden execution layer")

    monkeypatch.setattr(rng_engine, "raw_u64", forbidden)
    monkeypatch.setattr(selection_engine, "select_weighted", forbidden)
    monkeypatch.setattr(selection_engine, "select_uniform", forbidden)
    monkeypatch.setattr(event_engine, "select_event", forbidden)
    monkeypatch.setattr(binding_engine, "place_selected_event", forbidden)
    monkeypatch.setattr(reference_engine, "place_one", forbidden)
    actual = accumulate_event(accumulator=accumulator, event=event)
    assert actual.event_count == 1


def test_coverage_directed_short_chains_match_raw_certificate_oracle() -> None:
    width = 5
    law = _event_law(width)
    all_specs = _all_specs(width)
    seen_orientations: set[str] = set()
    seen_contacts: set[str] = set()
    seen_gaps: set[int] = set()
    seen_clusters: set[int] = set()
    seen_spans: set[int] = set()
    seen_signatures: set[GapSignature] = set()
    seen_roughness_signs: set[int] = set()
    saw_seam = False

    for spec in all_specs:
        actual, events = _run_specs((spec,), law=law)
        expected = _oracle(
            empty_state=SparseAggregate.empty(width),
            root_seed=0x1234,
            coupling_group_id="accumulation-oracle",
            law=law,
            events=events,
        )
        _assert_matches(actual, expected)
        seen_orientations.add(spec[0])
        seen_contacts.add(spec[2])

    first_specs = (
        ("tetromino.i.00", 0, "supported-v1"),
        ("tetromino.i.01", 0, "supported-v1"),
        ("tetromino.lj.00", 0, "supported-v1"),
        ("tetromino.o.00", 4, "edge-first-contact-v1"),
    )
    for first_spec in first_specs:
        for second_spec in all_specs:
            actual, events = _run_specs((first_spec, second_spec), law=law)
            expected = _oracle(
                empty_state=SparseAggregate.empty(width),
                root_seed=0x1234,
                coupling_group_id="accumulation-oracle",
                law=law,
                events=events,
            )
            _assert_matches(actual, expected)
            seen_gaps.update(key for key, _ in expected["landing_gap_counts"])
            seen_clusters.update(key for key, _ in expected["support_cluster_counts"])
            seen_spans.update(key for key, _ in expected["support_arc_span_counts"])
            seen_signatures.update(key for key, _ in expected["support_gap_signature_counts"])
            seen_roughness_signs.update((key[3] > 0) - (key[3] < 0) for key, _ in expected["contact_gap_delta_counts"])
            saw_seam = saw_seam or bool(expected["seam_lateral_face_count"])

    assert seen_orientations == set(_ORIENTATION_ORDER)
    assert seen_contacts == set(_CONTACT_ORDER)
    assert {0, 1, 2, 3}.issubset(seen_gaps)
    assert {0, 1, 2}.issubset(seen_clusters)
    assert {0, 1, 2, 3}.issubset(seen_spans)
    assert () in seen_signatures and (5,) in seen_signatures and (1, 2, 2) in seen_signatures
    assert seen_roughness_signs == {-1, 0, 1}
    assert saw_seam


def test_every_accumulator_field_is_recertified_on_direct_construction() -> None:
    valid, _ = _run_specs(
        (
            ("tetromino.i.01", 0, "supported-v1"),
            ("tetromino.i.00", 1, "edge-first-contact-v1"),
        )
    )
    corruptions: tuple[dict[str, object], ...] = (
        {"root_seed": True},
        {"coupling_group_id": ""},
        {"law": object()},
        {"width": valid.width + 1},
        {"event_count": valid.event_count + 1},
        {"current_state": SparseAggregate.empty(valid.width)},
        {"occupied_mass": valid.occupied_mass + 1},
        {"height_sum": valid.height_sum + 1},
        {"height_square_sum": valid.height_square_sum + 1},
        {"below_envelope_volume": valid.below_envelope_volume + 1},
        {"void_count": valid.void_count + 1},
        {"family_counts": tuple(reversed(valid.family_counts))},
        {"orientation_counts": tuple(reversed(valid.orientation_counts))},
        {"contact_counts": tuple(reversed(valid.contact_counts))},
        {"contact_face_kind_counts": tuple(reversed(valid.contact_face_kind_counts))},
        {"causal_face_kind_counts": tuple(reversed(valid.causal_face_kind_counts))},
        {"seam_lateral_face_count": -1},
        {"contacting_piece_cell_count": -1},
        {"contacted_aggregate_cell_count": -1},
        {"contacted_support_site_count": -1},
        {"contacted_support_column_count": -1},
        {"events_with_floor_support_face": valid.event_count + 1},
        {"events_with_aggregate_support_face": valid.event_count + 1},
        {"landing_gap_counts": ((0, valid.event_count + 1),)},
        {"support_cluster_counts": ((0, valid.event_count + 1),)},
        {"support_arc_span_counts": ((0, valid.event_count + 1),)},
        {"support_gap_signature_counts": (((), 1), ((2, 1, 2), 1))},
        {"pre_envelope_height_counts": ((0, valid.width * valid.event_count + 1),)},
        {"post_envelope_height_counts": ((0, valid.width * valid.event_count + 1),)},
        {"envelope_change_counts": (((0, 0, 1), 99),)},
        {"contact_gap_delta_counts": tuple((key, count + 1) for key, count in valid.contact_gap_delta_counts)},
        {
            "topology_joint_counts": tuple(
                (key, count, void_sum, roughness_sum + 1)
                for key, count, void_sum, roughness_sum in valid.topology_joint_counts
            )
        },
        {"height_sum_delta": valid.height_sum_delta + 1},
        {"height_square_sum_delta": valid.height_square_sum_delta + 1},
        {"void_count_delta": valid.void_count_delta + 1},
    )
    assert len(corruptions) == len(_EXPECTED_FIELDS)
    for field_name, changes in zip(_EXPECTED_FIELDS, corruptions, strict=True):
        assert tuple(changes) == (field_name,)
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(valid, **changes)


def test_exact_nested_types_orders_duplicates_and_sparse_zero_counts_fail_closed() -> None:
    valid, _ = _run_specs(
        (
            ("tetromino.i.01", 0, "supported-v1"),
            ("tetromino.i.00", 1, "edge-first-contact-v1"),
        )
    )
    first_joint_key, first_joint_count = valid.contact_gap_delta_counts[0]
    first_topology = valid.topology_joint_counts[0]
    invalid_changes: tuple[dict[str, object], ...] = (
        {"family_counts": list(valid.family_counts)},
        {"family_counts": (("i", True), *valid.family_counts[1:])},
        {"family_counts": (valid.family_counts[0], valid.family_counts[0], *valid.family_counts[2:])},
        {"landing_gap_counts": list(valid.landing_gap_counts)},
        {"landing_gap_counts": ([0, 1],)},
        {"landing_gap_counts": ((True, first_joint_count), *valid.landing_gap_counts[1:])},
        {"landing_gap_counts": ((0, 0),)},
        {"landing_gap_counts": tuple(reversed(valid.landing_gap_counts))},
        {"landing_gap_counts": (valid.landing_gap_counts[0], valid.landing_gap_counts[0])},
        {"support_gap_signature_counts": (([1, 2, 2], 1), ((), 1))},
        {"support_gap_signature_counts": (((2, 1, 2), 1), ((), 1))},
        {"contact_gap_delta_counts": ((list(first_joint_key), first_joint_count),)},
        {"contact_gap_delta_counts": (((valid.current_state.width, *first_joint_key[1:]), first_joint_count),)},
        {"contact_gap_delta_counts": (((ContactKind.SUPPORTED_V1, *first_joint_key[1:]), first_joint_count),)},
        {"contact_gap_delta_counts": ((first_joint_key, True),)},
        {"topology_joint_counts": ((list(first_topology[0]), *first_topology[1:]),)},
        {
            "topology_joint_counts": (
                ((first_topology[0][0], first_topology[0][1], True, *first_topology[0][3:]), *first_topology[1:]),
            )
        },
        {"topology_joint_counts": ((first_topology[0], 0, first_topology[2], first_topology[3]),)},
    )
    for changes in invalid_changes:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(valid, **changes)


def test_zero_law_slots_and_family_orientation_projection_are_normative() -> None:
    law = _event_law(
        5,
        family_counts=(1, 0, 0, 0, 0),
        orientation_updates={"i": (1, 0)},
        contact_counts=(1, 0),
    )
    valid, _ = _run_specs((("tetromino.i.00", 0, "supported-v1"),), law=law)
    assert valid.family_counts == (("i", 1), ("lj", 0), ("o", 0), ("sz", 0), ("t", 0))
    assert valid.orientation_counts[0:2] == (("tetromino.i.00", 1), ("tetromino.i.01", 0))
    assert valid.contact_counts == (("supported-v1", 1), ("edge-first-contact-v1", 0))

    wrong_family = (("i", 0), ("lj", 0), ("o", 1), ("sz", 0), ("t", 0))
    wrong_orientation = (("tetromino.i.00", 0), ("tetromino.i.01", 1), *valid.orientation_counts[2:])
    wrong_contact = (("supported-v1", 0), ("edge-first-contact-v1", 1))
    for changes in (
        {"family_counts": wrong_family},
        {"orientation_counts": wrong_orientation},
        {"contact_counts": wrong_contact},
    ):
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(valid, **changes)


def test_histogram_flow_joint_marginal_and_roughness_projections_are_normative() -> None:
    valid, _ = _run_specs(
        (
            ("tetromino.i.01", 0, "supported-v1"),
            ("tetromino.i.00", 1, "edge-first-contact-v1"),
        )
    )
    contact_key, contact_count = valid.contact_gap_delta_counts[0]
    topology_key, topology_count, topology_void, topology_roughness = valid.topology_joint_counts[0]
    corruptions = (
        {"post_envelope_height_counts": ((0, 2), (4, 8))},
        {"envelope_change_counts": (((0, 0, 4), 2), ((1, 0, 4), 3))},
        {
            "contact_gap_delta_counts": (
                ((contact_key[0], contact_key[1], contact_key[2], contact_key[3] + 1), contact_count),
                *valid.contact_gap_delta_counts[1:],
            )
        },
        {
            "topology_joint_counts": (
                (topology_key, topology_count, topology_void + 1, topology_roughness),
                *valid.topology_joint_counts[1:],
            )
        },
    )
    for changes in corruptions:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            replace(valid, **changes)


def test_signed_negative_stratum_is_structurally_valid_without_authenticating_history() -> None:
    valid, _ = _run_specs(
        (
            ("tetromino.i.01", 0, "supported-v1"),
            ("tetromino.i.00", 1, "edge-first-contact-v1"),
        )
    )
    reassigned_contact: list[tuple[ContactGapKey, int]] = []
    for key, count in valid.contact_gap_delta_counts:
        contact_id, gap, void_delta, roughness_delta = key
        reassigned_void = -1 if contact_id == "supported-v1" else void_delta + 1
        reassigned_contact.append(((contact_id, gap, reassigned_void, roughness_delta), count))
    reassigned_topology = tuple(
        (key, count, -1 if key[1] == "supported-v1" else void_sum + 1, roughness_sum)
        for key, count, void_sum, roughness_sum in valid.topology_joint_counts
    )
    structural_copy = replace(
        valid,
        contact_gap_delta_counts=tuple(sorted(reassigned_contact)),
        topology_joint_counts=tuple(sorted(reassigned_topology)),
    )
    assert structural_copy == structural_copy
    assert any(key[2] < 0 for key, _ in structural_copy.contact_gap_delta_counts)
    assert structural_copy.current_state == valid.current_state


def test_signed_void_strata_cannot_fall_below_one_tetromino_per_event() -> None:
    valid, _ = _run_specs(
        (
            ("tetromino.i.01", 0, "supported-v1"),
            ("tetromino.i.00", 1, "edge-first-contact-v1"),
        )
    )
    rebalanced_contact = tuple(
        (
            (
                contact_id,
                gap,
                -5 if contact_id == "supported-v1" else void_delta + 5,
                roughness_delta,
            ),
            count,
        )
        for (contact_id, gap, void_delta, roughness_delta), count in valid.contact_gap_delta_counts
    )
    rebalanced_topology = tuple(
        (
            key,
            count,
            -5 if key[1] == "supported-v1" else void_sum + 5,
            roughness_sum,
        )
        for key, count, void_sum, roughness_sum in valid.topology_joint_counts
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="void|delta|tetromino|lower"):
        replace(
            valid,
            contact_gap_delta_counts=rebalanced_contact,
            topology_joint_counts=rebalanced_topology,
        )


def test_caller_state_law_and_event_mutations_do_not_reach_snapshots() -> None:
    mutable_cells: set[Cell] = set()
    empty = SparseAggregate.empty(5)
    object.__setattr__(empty, "occupied", mutable_cells)
    law = _event_law(5)
    original_family_counts = law.family_law.counts
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0x1234,
        coupling_group_id="accumulation-oracle",
        law=law,
    )
    mutable_cells.add((0, 99))
    object.__setattr__(law.family_law, "counts", (0, 0, 1, 0, 0))
    assert accumulator.current_state == SparseAggregate.empty(5)
    assert accumulator.law.family_law.counts == original_family_counts

    pristine_law = accumulator.law
    event = _bind(
        accumulator.current_state,
        ("tetromino.o.00", 0, "supported-v1"),
        ordinal=0,
        law=pristine_law,
    )
    actual = accumulate_event(accumulator=accumulator, event=event)
    object.__setattr__(event.selection, "coupling_group_id", "mutated-after-fold")
    object.__setattr__(event.placement.post_state, "occupied", frozenset({(4, 100)}))
    assert actual.coupling_group_id == "accumulation-oracle"
    assert actual.current_state.mass == 4


def test_start_rejects_nonempty_exact_type_address_width_and_support_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law(5)

    class SparseAggregateSubclass(SparseAggregate):
        pass

    class EventLawSubclass(TetrominoEventLaw):
        pass

    law_subclass = EventLawSubclass(
        law.family_law,
        law.orientation_laws,
        law.launch_law,
        law.contact_law,
    )
    invalid_calls = (
        {"empty_state": object(), "root_seed": 0, "coupling_group_id": "g", "law": law},
        {
            "empty_state": SparseAggregateSubclass.empty(5),
            "root_seed": 0,
            "coupling_group_id": "g",
            "law": law,
        },
        {"empty_state": SparseAggregate(5, {(0, 0)}), "root_seed": 0, "coupling_group_id": "g", "law": law},
        {"empty_state": SparseAggregate.empty(5), "root_seed": True, "coupling_group_id": "g", "law": law},
        {"empty_state": SparseAggregate.empty(5), "root_seed": -1, "coupling_group_id": "g", "law": law},
        {
            "empty_state": SparseAggregate.empty(5),
            "root_seed": _U128_MAX + 1,
            "coupling_group_id": "g",
            "law": law,
        },
        {"empty_state": SparseAggregate.empty(5), "root_seed": 0, "coupling_group_id": "", "law": law},
        {
            "empty_state": SparseAggregate.empty(5),
            "root_seed": 0,
            "coupling_group_id": "\ud800",
            "law": law,
        },
        {"empty_state": SparseAggregate.empty(5), "root_seed": 0, "coupling_group_id": "g", "law": object()},
        {
            "empty_state": SparseAggregate.empty(5),
            "root_seed": 0,
            "coupling_group_id": "g",
            "law": law_subclass,
        },
        {"empty_state": SparseAggregate.empty(6), "root_seed": 0, "coupling_group_id": "g", "law": law},
    )
    for kwargs in invalid_calls:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            start_event_accumulator(**kwargs)  # type: ignore[arg-type]

    width_four_law = _event_law(4)
    monkeypatch.setattr(
        accumulation_engine,
        "validate_periodic_law",
        lambda _width, support: tuple(support),
        raising=False,
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="width|geometry|support"):
        start_event_accumulator(
            empty_state=SparseAggregate.empty(4),
            root_seed=0,
            coupling_group_id="g",
            law=width_four_law,
        )


def test_start_fails_closed_on_mutated_public_order_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accumulation_engine, "TETROMINO_FAMILY_ORDER", tuple(reversed(_FAMILY_ORDER)))
    monkeypatch.setattr(accumulation_engine, "TETROMINO_CONTACT_ORDER", tuple(reversed(_CONTACT_ORDER)))
    with pytest.raises(AssertionError, match="order|ratified|authority"):
        start_event_accumulator(
            empty_state=SparseAggregate.empty(5),
            root_seed=0,
            coupling_group_id="g",
            law=_event_law(5),
        )


def test_start_cross_binds_ratified_registry_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    ratified = binding_engine._ratified_geometry_by_id()
    poisoned = dict(ratified)
    poisoned["tetromino.i.00"] = ratified["tetromino.i.01"]
    monkeypatch.setattr(binding_engine, "_ratified_geometry_by_id", lambda: poisoned)
    with pytest.raises((AssertionError, TypeError, ValueError), match="registry|geometry|support"):
        start_event_accumulator(
            empty_state=SparseAggregate.empty(5),
            root_seed=0,
            coupling_group_id="g",
            law=_event_law(5),
        )


def test_start_cross_binds_periodic_preflight_return(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        accumulation_engine,
        "validate_periodic_law",
        lambda _width, support: tuple(reversed(support)),
    )
    with pytest.raises((AssertionError, TypeError, ValueError), match="inconsistent|support"):
        start_event_accumulator(
            empty_state=SparseAggregate.empty(5),
            root_seed=0,
            coupling_group_id="g",
            law=_event_law(5),
        )


def test_coupling_group_length_is_measured_in_utf8_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accumulation_engine, "_U32_MAX", 2)
    actual = start_event_accumulator(
        empty_state=SparseAggregate.empty(5),
        root_seed=0,
        coupling_group_id="é",
        law=_event_law(5),
    )
    assert actual.coupling_group_id == "é"
    with pytest.raises(ValueError, match="UTF-8|too long"):
        start_event_accumulator(
            empty_state=SparseAggregate.empty(5),
            root_seed=0,
            coupling_group_id="abc",
            law=_event_law(5),
        )


def test_start_and_fold_are_keyword_only() -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    with pytest.raises(TypeError):
        start_event_accumulator(empty, 0, "g", law)  # type: ignore[misc]
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0,
        coupling_group_id="g",
        law=law,
    )
    event = _bind(
        empty,
        ("tetromino.i.00", 0, "supported-v1"),
        ordinal=0,
        law=law,
        root_seed=0,
        coupling_group_id="g",
    )
    with pytest.raises(TypeError):
        accumulate_event(accumulator, event)  # type: ignore[misc]


def test_partial_subclass_and_malformed_fold_inputs_fail_before_measurement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    valid_accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0,
        coupling_group_id="g",
        law=law,
    )
    valid_event = _bind(
        empty,
        ("tetromino.i.00", 0, "supported-v1"),
        ordinal=0,
        law=law,
        root_seed=0,
        coupling_group_id="g",
    )

    class AccumulatorSubclass(ReferenceEventAccumulator):
        pass

    class EventSubclass(ReferenceEventPlacement):
        pass

    accumulator_subclass = AccumulatorSubclass(*(getattr(valid_accumulator, name) for name in _EXPECTED_FIELDS))
    event_subclass = EventSubclass(valid_event.selection, valid_event.placement)
    partial_accumulator = object.__new__(ReferenceEventAccumulator)
    partial_event = object.__new__(ReferenceEventPlacement)

    def forbidden_measurement(*_args: object, **_kwargs: object) -> object:
        pytest.fail("measurement ran for a malformed public input")

    monkeypatch.setattr(accumulation_engine, "measure_placement", forbidden_measurement)
    invalid_pairs = (
        (object(), valid_event),
        (valid_accumulator, object()),
        (accumulator_subclass, valid_event),
        (valid_accumulator, event_subclass),
        (partial_accumulator, valid_event),
        (valid_accumulator, partial_event),
    )
    for accumulator, event in invalid_pairs:
        with pytest.raises((AssertionError, TypeError, ValueError), match="."):
            accumulate_event(accumulator=accumulator, event=event)  # type: ignore[arg-type]


def test_delegate_mutation_cannot_rewrite_pristine_event_authorities(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0,
        coupling_group_id="g",
        law=law,
    )
    event = _bind(
        empty,
        ("tetromino.lj.00", 0, "supported-v1"),
        ordinal=0,
        law=law,
        root_seed=0,
        coupling_group_id="g",
    )
    genuine = accumulation_engine.measure_placement
    supplied: list[object] = []

    def mutating_delegate(placement: object) -> object:
        supplied.append(placement)
        result = genuine(placement)
        object.__setattr__(placement, "causal_contacts", ())
        return result

    monkeypatch.setattr(accumulation_engine, "measure_placement", mutating_delegate)
    actual = accumulate_event(accumulator=accumulator, event=event)
    assert len(supplied) == 1
    assert supplied[0] is not event.placement
    assert event.placement.causal_contacts
    assert actual.current_state == event.placement.post_state


def test_partial_measurement_and_wrong_state_measurement_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0,
        coupling_group_id="g",
        law=law,
    )
    event = _bind(
        empty,
        ("tetromino.lj.00", 0, "supported-v1"),
        ordinal=0,
        law=law,
        root_seed=0,
        coupling_group_id="g",
    )
    monkeypatch.setattr(accumulation_engine, "measure_placement", lambda _placement: object())
    with pytest.raises((AssertionError, TypeError, ValueError), match="."):
        accumulate_event(accumulator=accumulator, event=event)

    monkeypatch.undo()
    genuine_state_measurement = accumulation_engine.measure_state
    wrong_post = observable_engine.measure_state(SparseAggregate.empty(5))

    def poisoned_state_measurement(state: SparseAggregate) -> object:
        if state == event.placement.post_state:
            return wrong_post
        return genuine_state_measurement(state)

    monkeypatch.setattr(accumulation_engine, "measure_state", poisoned_state_measurement)
    with pytest.raises((AssertionError, TypeError, ValueError), match="."):
        accumulate_event(accumulator=accumulator, event=event)


def test_forged_terminal_input_fails_before_measurement(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(5)
    empty = SparseAggregate.empty(5)
    accumulator = start_event_accumulator(
        empty_state=empty,
        root_seed=0,
        coupling_group_id="g",
        law=law,
    )
    object.__setattr__(accumulator, "event_count", _U64_TERMINAL)
    event = _bind(
        empty,
        ("tetromino.i.00", 0, "supported-v1"),
        ordinal=_U64_MAX,
        law=law,
        root_seed=0,
        coupling_group_id="g",
    )

    def forbidden_measurement(*_args: object, **_kwargs: object) -> object:
        pytest.fail("terminal accumulator reached placement measurement")

    monkeypatch.setattr(accumulation_engine, "measure_placement", forbidden_measurement)
    with pytest.raises((AssertionError, TypeError, ValueError), match="."):
        accumulate_event(accumulator=accumulator, event=event)


def test_accumulation_symbols_are_explicit_only() -> None:
    assert accumulation_engine.__all__ == [
        "ReferenceEventAccumulator",
        "start_event_accumulator",
        "accumulate_event",
    ]
    assert "_checked_next_event_count" not in accumulation_engine.__all__
    for module in (tetris_ballistic, engine_package, event_engine, observable_engine):
        for name in accumulation_engine.__all__:
            assert not hasattr(module, name)


def test_accumulation_module_imports_no_forbidden_later_layers() -> None:
    tree = ast.parse(Path(accumulation_engine.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden = ("config", "simulation", "trajectory", "checkpoint", "artifact", "scheduler", "legacy_adapter")
    assert not any(fragment in module for fragment in forbidden for module in imported)
    assert not any(
        name in accumulation_engine.__dict__ for name in ("select_event", "place_one", "place_selected_event")
    )
    assert rng_engine.raw_u64 is not None
    assert selection_engine.select_weighted is not None
    assert reference_engine.place_one is not None
