"""Independent semantic tests for the slow periodic reference engine."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from tetris_ballistic.engine import (
    ContactFace,
    ContactFaceKind,
    ReferencePlacement,
    SparseAggregate,
    place_one,
    validate_periodic_law,
)
from tetris_ballistic.models import GEOMETRY_BY_ID, ONE_CELL, TETROMINO_REGISTRY, ContactKind, PieceGeometry

Cell = tuple[int, int]
OracleFace = tuple[Cell, str, Cell | None, bool]

_AGGREGATE_ABOVE = "aggregate-above"
_AGGREGATE_SUPPORT = "aggregate-support"
_FLOOR_SUPPORT = "floor-support"
_LATERAL_LEFT = "lateral-left"
_LATERAL_RIGHT = "lateral-right"
_FACE_ORDER = {
    _FLOOR_SUPPORT: 0,
    _AGGREGATE_SUPPORT: 1,
    _LATERAL_LEFT: 2,
    _LATERAL_RIGHT: 3,
    _AGGREGATE_ABOVE: 4,
}
_SUPPORT_KINDS = frozenset({_AGGREGATE_SUPPORT, _FLOOR_SUPPORT})
_EDGE_KINDS = frozenset({_AGGREGATE_SUPPORT, _FLOOR_SUPPORT, _LATERAL_LEFT, _LATERAL_RIGHT})
_EXECUTABLE_KINDS = (ContactKind.SUPPORTED_V1, ContactKind.EDGE_FIRST_CONTACT_V1)

# These are frozen public-world law coordinates, written as (delta_x, delta_y).
# The oracle deliberately does not ask PieceGeometry.world_coordinates for them.
_LOCAL_CELLS: dict[str, tuple[Cell, ...]] = {
    "baseline.one-cell": ((0, 0),),
    "tetromino.lj.02": ((0, 0), (0, 1), (0, 2), (1, 2)),
    "tetromino.i.00": ((0, 0), (1, 0), (2, 0), (3, 0)),
}


@dataclass(frozen=True)
class _OraclePlacement:
    landing_y: int
    supported_landing_y: int
    early_arrest_gap: int
    piece_cells: tuple[Cell, ...]
    contacts: tuple[OracleFace, ...]
    stopping_contacts: tuple[OracleFace, ...]
    causal_contacts: tuple[OracleFace, ...]
    post_occupied: frozenset[Cell]


def _wrapped_cells(local_cells: tuple[Cell, ...], width: int, anchor_x: int, landing_y: int) -> tuple[Cell, ...]:
    return tuple(sorted(((anchor_x + delta_x) % width, landing_y + delta_y) for delta_x, delta_y in local_cells))


def _has_support(piece_cells: tuple[Cell, ...], occupied: frozenset[Cell]) -> bool:
    return any(y == 0 or (x, y - 1) in occupied for x, y in piece_cells)


def _has_lateral_contact(piece_cells: tuple[Cell, ...], width: int, occupied: frozenset[Cell]) -> bool:
    return any(
        ((x - 1) % width, y) in occupied or ((x + 1) % width, y) in occupied
        for x, y in piece_cells
    )


def _brute_landing_height(
    local_cells: tuple[Cell, ...],
    *,
    width: int,
    anchor_x: int,
    occupied: frozenset[Cell],
    include_lateral: bool,
) -> int:
    # Any support candidate is at most one row above the finite aggregate;
    # lateral candidates are no higher.  Enumerating every intervening height
    # is intentionally independent of the engine's contact-derived candidates.
    search_top = max((y for _, y in occupied), default=-1) + 1
    valid_stopping_heights: list[int] = []
    for landing_y in range(search_top + 1):
        piece_cells = _wrapped_cells(local_cells, width, anchor_x, landing_y)
        valid = len(set(piece_cells)) == len(local_cells) and occupied.isdisjoint(piece_cells)
        if not valid:
            continue
        stops = _has_support(piece_cells, occupied)
        if include_lateral:
            stops = stops or _has_lateral_contact(piece_cells, width, occupied)
        if stops:
            valid_stopping_heights.append(landing_y)

    assert valid_stopping_heights, "floor support must give every valid geometry a stopping height"
    return max(valid_stopping_heights)


def _crosses_seam(piece_cell: Cell, neighbor_cell: Cell | None, width: int) -> bool:
    if neighbor_cell is None:
        return False
    piece_x, piece_y = piece_cell
    neighbor_x, neighbor_y = neighbor_cell
    return piece_y == neighbor_y and {piece_x, neighbor_x} == {0, width - 1}


def _oracle_contacts(piece_cells: tuple[Cell, ...], width: int, occupied: frozenset[Cell]) -> tuple[OracleFace, ...]:
    contacts: list[OracleFace] = []
    for piece_cell in piece_cells:
        x, y = piece_cell

        if y == 0:
            contacts.append((piece_cell, _FLOOR_SUPPORT, None, False))
        elif (x, y - 1) in occupied:
            neighbor = (x, y - 1)
            contacts.append((piece_cell, _AGGREGATE_SUPPORT, neighbor, False))

        above = (x, y + 1)
        if above in occupied:
            contacts.append((piece_cell, _AGGREGATE_ABOVE, above, False))

        left = ((x - 1) % width, y)
        if left in occupied:
            contacts.append((piece_cell, _LATERAL_LEFT, left, _crosses_seam(piece_cell, left, width)))

        right = ((x + 1) % width, y)
        if right in occupied:
            contacts.append((piece_cell, _LATERAL_RIGHT, right, _crosses_seam(piece_cell, right, width)))

    return tuple(sorted(contacts, key=lambda face: (face[0], _FACE_ORDER[face[1]], face[2] or (-1, -1))))


def _oracle_place(
    local_cells: tuple[Cell, ...],
    *,
    width: int,
    anchor_x: int,
    occupied: frozenset[Cell],
    contact_kind: ContactKind,
) -> _OraclePlacement:
    supported_y = _brute_landing_height(
        local_cells,
        width=width,
        anchor_x=anchor_x,
        occupied=occupied,
        include_lateral=False,
    )
    landing_y = (
        supported_y
        if contact_kind is ContactKind.SUPPORTED_V1
        else _brute_landing_height(
            local_cells,
            width=width,
            anchor_x=anchor_x,
            occupied=occupied,
            include_lateral=True,
        )
    )
    piece_cells = _wrapped_cells(local_cells, width, anchor_x, landing_y)
    contacts = _oracle_contacts(piece_cells, width, occupied)
    stopping_kinds = _SUPPORT_KINDS if contact_kind is ContactKind.SUPPORTED_V1 else _EDGE_KINDS
    stopping_contacts = tuple(face for face in contacts if face[1] in stopping_kinds)
    causal_kinds = (
        frozenset({_LATERAL_LEFT, _LATERAL_RIGHT})
        if contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1 and landing_y > supported_y
        else _SUPPORT_KINDS
    )
    causal_contacts = tuple(face for face in contacts if face[1] in causal_kinds)
    return _OraclePlacement(
        landing_y=landing_y,
        supported_landing_y=supported_y,
        early_arrest_gap=landing_y - supported_y,
        piece_cells=piece_cells,
        contacts=contacts,
        stopping_contacts=stopping_contacts,
        causal_contacts=causal_contacts,
        post_occupied=occupied.union(piece_cells),
    )


def _normalize_faces(faces: tuple[ContactFace, ...]) -> tuple[OracleFace, ...]:
    return tuple(
        (face.piece_cell, face.kind.value, face.neighbor_cell, face.crosses_seam)
        for face in faces
    )


def _occupied_from_mask(width: int, height: int, mask: int) -> frozenset[Cell]:
    cells = tuple((x, y) for y in range(height) for x in range(width))
    return frozenset(cell for index, cell in enumerate(cells) if mask & (1 << index))


def _assert_matches_oracle(actual: ReferencePlacement, expected: _OraclePlacement, *, context: str) -> None:
    assert actual.landing_y == expected.landing_y, context
    assert actual.supported_landing_y == expected.supported_landing_y, context
    assert actual.early_arrest_gap == expected.early_arrest_gap, context
    assert actual.piece_cells == expected.piece_cells, context
    assert _normalize_faces(actual.contacts) == expected.contacts, context
    assert _normalize_faces(actual.stopping_contacts) == expected.stopping_contacts, context
    assert _normalize_faces(actual.causal_contacts) == expected.causal_contacts, context
    assert actual.post_state.occupied == expected.post_occupied, context


def test_exhaustive_small_states_match_independent_brute_height_oracle() -> None:
    configurations = (
        (3, 3, ONE_CELL),
        (3, 3, GEOMETRY_BY_ID["tetromino.lj.02"]),
        (5, 2, GEOMETRY_BY_ID["tetromino.i.00"]),
    )
    case_count = 0

    for width, state_height, geometry in configurations:
        local_cells = _LOCAL_CELLS[geometry.id]
        for mask in range(1 << (width * state_height)):
            occupied = _occupied_from_mask(width, state_height, mask)
            state = SparseAggregate(width, occupied)
            for anchor_x in range(width):
                for contact_kind in _EXECUTABLE_KINDS:
                    context = (
                        f"width={width}, geometry={geometry.id}, mask={mask}, "
                        f"anchor_x={anchor_x}, contact_kind={contact_kind.value}, occupied={sorted(occupied)}"
                    )
                    expected = _oracle_place(
                        local_cells,
                        width=width,
                        anchor_x=anchor_x,
                        occupied=occupied,
                        contact_kind=contact_kind,
                    )
                    actual = place_one(state, geometry, anchor_x, contact_kind)
                    _assert_matches_oracle(actual, expected, context=context)
                    assert actual.geometry_id == geometry.id, context
                    assert actual.geometry == geometry, context
                    assert actual.contact_kind is contact_kind, context
                    assert actual.anchor_x == anchor_x, context
                    assert actual.pre_state == state, context
                    assert actual.post_state.width == width, context
                    assert all(
                        face.kind is not ContactFaceKind.AGGREGATE_ABOVE for face in actual.stopping_contacts
                    ), context
                    assert all(face.kind is not ContactFaceKind.AGGREGATE_ABOVE for face in actual.causal_contacts), context
                    case_count += 1

    assert case_count == 16_384


def test_every_ratified_geometry_places_at_every_empty_state_anchor() -> None:
    state = SparseAggregate.empty(5)
    geometries = (*TETROMINO_REGISTRY, ONE_CELL)
    assert validate_periodic_law(state.width, geometries) == geometries
    for geometry in geometries:
        local_cells = tuple((delta_x, delta_y) for delta_y, delta_x in geometry.world_coordinates)
        for anchor_x in range(state.width):
            expected_cells = _wrapped_cells(local_cells, state.width, anchor_x, 0)
            for contact_kind in _EXECUTABLE_KINDS:
                placement = place_one(state, geometry, anchor_x, contact_kind)
                assert placement.landing_y == placement.supported_landing_y == 0
                assert placement.piece_cells == expected_cells
                assert placement.pre_state == state
                assert placement.post_state.mass == geometry.area
                assert placement.early_arrest_gap == 0


def test_seam_wrapping_and_seam_contact_are_explicit() -> None:
    horizontal_i = GEOMETRY_BY_ID["tetromino.i.00"]
    wrapped = place_one(SparseAggregate.empty(5), horizontal_i, 4, ContactKind.SUPPORTED_V1)
    assert wrapped.piece_cells == ((0, 0), (1, 0), (2, 0), (4, 0))
    assert all(not face.crosses_seam for face in wrapped.contacts)

    seam_height = 10**9
    state = SparseAggregate(3, {(2, seam_height)})
    placement = place_one(state, ONE_CELL, 0, ContactKind.EDGE_FIRST_CONTACT_V1)
    assert placement.landing_y == seam_height
    assert placement.supported_landing_y == 0
    assert placement.early_arrest_gap == seam_height
    assert len(placement.contacts) == 1
    assert placement.contacts[0].kind is ContactFaceKind.LATERAL_LEFT
    assert placement.contacts[0].neighbor_cell == (2, seam_height)
    assert placement.contacts[0].crosses_seam is True
    assert placement.stopping_contacts == placement.causal_contacts == placement.contacts
    assert placement.lateral_trigger is True
    assert placement.contacted_support_columns == ()


def test_simultaneous_contacts_keep_incidental_faces_out_of_supported_causality() -> None:
    state = SparseAggregate(3, {(1, 1), (0, 2), (2, 2)})
    supported = place_one(state, ONE_CELL, 1, ContactKind.SUPPORTED_V1)
    edge = place_one(state, ONE_CELL, 1, ContactKind.EDGE_FIRST_CONTACT_V1)

    expected_kinds = (
        ContactFaceKind.AGGREGATE_SUPPORT,
        ContactFaceKind.LATERAL_LEFT,
        ContactFaceKind.LATERAL_RIGHT,
    )
    assert supported.landing_y == edge.landing_y == 2
    assert tuple(face.kind for face in supported.contacts) == expected_kinds
    assert tuple(face.kind for face in supported.stopping_contacts) == (ContactFaceKind.AGGREGATE_SUPPORT,)
    assert tuple(face.kind for face in supported.causal_contacts) == (ContactFaceKind.AGGREGATE_SUPPORT,)
    assert tuple(face.kind for face in edge.stopping_contacts) == expected_kinds
    assert tuple(face.kind for face in edge.causal_contacts) == (ContactFaceKind.AGGREGATE_SUPPORT,)
    assert supported.contacted_support_columns == edge.contacted_support_columns == (1,)
    assert supported.lateral_trigger is edge.lateral_trigger is False
    assert all(face.kind is not ContactFaceKind.AGGREGATE_ABOVE for face in supported.causal_contacts)
    assert all(face.kind is not ContactFaceKind.AGGREGATE_ABOVE for face in edge.causal_contacts)


def test_direct_face_and_result_construction_fails_closed() -> None:
    with pytest.raises(TypeError):
        ContactFace("floor-support", (0, 0), None, False)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        ContactFace(ContactFaceKind.FLOOR_SUPPORT, (0, 1), None, False)
    with pytest.raises(ValueError):
        ContactFace(ContactFaceKind.AGGREGATE_SUPPORT, (0, 1), None, False)
    with pytest.raises(ValueError):
        ContactFace(ContactFaceKind.AGGREGATE_SUPPORT, (0, 1), (0, 0), True)

    valid = place_one(SparseAggregate.empty(3), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    with pytest.raises(ValueError, match="early_arrest_gap"):
        replace(valid, early_arrest_gap=1)
    with pytest.raises(ValueError, match="every final directed face"):
        replace(valid, contacts=())
    with pytest.raises(ValueError, match="stopping_contacts"):
        replace(valid, stopping_contacts=())
    with pytest.raises(ValueError, match="causal_contacts"):
        replace(valid, causal_contacts=())
    with pytest.raises(TypeError, match="piece_cells"):
        replace(valid, piece_cells=list(valid.piece_cells))
    with pytest.raises(ValueError, match="post_state"):
        replace(valid, post_state=SparseAggregate.empty(3))

    false_pre_state = SparseAggregate(3, {(0, 5)})
    false_post_state = SparseAggregate(3, {(0, 0), (0, 5)})
    with pytest.raises(ValueError, match="maximum valid heights"):
        replace(valid, pre_state=false_pre_state, post_state=false_post_state)

    horizontal_i = GEOMETRY_BY_ID["tetromino.i.00"]
    valid_wide = place_one(SparseAggregate.empty(5), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    with pytest.raises(ValueError, match="piece_cells do not match geometry"):
        replace(valid_wide, geometry_id=horizontal_i.id, geometry=horizontal_i)

    forged_geometry = PieceGeometry("audit.valid", "audit", ((0, 0),))
    object.__setattr__(forged_geometry, "coordinates", ((0, 0), (2, 0)))
    with pytest.raises(ValueError, match="connected"):
        replace(valid, geometry_id=forged_geometry.id, geometry=forged_geometry)

    mutable_pre: set[Cell] = set()
    mutable_post: set[Cell] = {(0, 0)}
    forged_pre = SparseAggregate.empty(3)
    forged_post = SparseAggregate.empty(3)
    object.__setattr__(forged_pre, "occupied", mutable_pre)
    object.__setattr__(forged_post, "occupied", mutable_post)
    resnapshotted = replace(valid, pre_state=forged_pre, post_state=forged_post)
    mutable_pre.add((2, 4))
    mutable_post.add((1, 7))
    assert resnapshotted.pre_state.occupied == frozenset()
    assert resnapshotted.post_state.occupied == frozenset({(0, 0)})


def test_input_and_result_snapshots_are_immutable() -> None:
    caller_cells = [[0, 0]]
    state = SparseAggregate(3, caller_cells)
    caller_cells[0][0] = 2
    caller_cells.append([1, 7])

    before = state.occupied
    placement = place_one(state, ONE_CELL, 1, ContactKind.SUPPORTED_V1)

    assert before == frozenset({(0, 0)})
    assert state.occupied == before
    assert placement.post_state.occupied == before.union(placement.piece_cells)
    assert placement.post_state.mass == state.mass + ONE_CELL.area
    assert state.occupied.isdisjoint(placement.piece_cells)
    assert isinstance(state.occupied, frozenset)
    assert isinstance(placement.piece_cells, tuple)
    assert isinstance(placement.contacts, tuple)
    assert isinstance(placement.stopping_contacts, tuple)
    assert isinstance(placement.causal_contacts, tuple)


@pytest.mark.parametrize(
    ("width", "occupied"),
    (
        (True, ()),
        (2, ()),
        (3.0, ()),
        (3, ((3, 0),)),
        (3, ((0, -1),)),
        (3, ((True, 0),)),
        (3, ((0, False),)),
        (3, ((0.0, 0),)),
        (3, ((0, 0.0),)),
        (3, ((0, 0), (0, 0))),
        (3, ((0, 0, 0),)),
    ),
)
def test_sparse_state_rejects_malformed_builtin_inputs(width: object, occupied: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SparseAggregate(width, occupied)  # type: ignore[arg-type]


def test_sparse_state_rejects_hostile_collection_subclasses_without_iterating_them() -> None:
    class HostileList(list[object]):
        def __iter__(self):
            raise AssertionError("hostile collection was iterated")

    class HostileTuple(tuple[object, ...]):
        def __iter__(self):
            raise AssertionError("hostile point was iterated")

    with pytest.raises(TypeError):
        SparseAggregate(3, HostileList([(0, 0)]))
    with pytest.raises(TypeError):
        SparseAggregate(3, [HostileTuple((0, 0))])


@pytest.mark.parametrize("anchor_x", (True, -1, 3, 1.0, None))
def test_place_one_rejects_noncanonical_anchors(anchor_x: object) -> None:
    with pytest.raises(ValueError):
        place_one(SparseAggregate.empty(3), ONE_CELL, anchor_x, ContactKind.SUPPORTED_V1)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "contact_kind",
    (
        ContactKind.SUPPORTED,
        ContactKind.FIRST_CONTACT,
        ContactKind.LEGACY_STICKY_V1,
        "supported-v1",
        "edge-first-contact-v1",
        None,
    ),
)
def test_place_one_fails_closed_for_old_or_untyped_contact_kinds(contact_kind: object) -> None:
    with pytest.raises(ValueError):
        place_one(SparseAggregate.empty(3), ONE_CELL, 0, contact_kind)  # type: ignore[arg-type]


def test_place_one_rejects_hostile_boundary_types_before_using_them() -> None:
    class SparseAggregateSubclass(SparseAggregate):
        pass

    class PieceGeometrySubclass(PieceGeometry):
        pass

    class HostileInt(int):
        def __index__(self):
            raise AssertionError("hostile integer was used")

    state = SparseAggregate.empty(3)
    with pytest.raises(TypeError):
        place_one(SparseAggregateSubclass(3, ()), ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    with pytest.raises(TypeError):
        place_one(
            state,
            PieceGeometrySubclass("test.one", "test", ((0, 0),)),
            0,
            ContactKind.SUPPORTED_V1,
        )
    with pytest.raises(ValueError):
        place_one(state, ONE_CELL, HostileInt(0), ContactKind.SUPPORTED_V1)
    with pytest.raises(TypeError):
        place_one(object(), ONE_CELL, 0, ContactKind.SUPPORTED_V1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        place_one(state, object(), 0, ContactKind.SUPPORTED_V1)  # type: ignore[arg-type]


def test_public_boundaries_revalidate_forged_exact_geometry_and_snapshot_state() -> None:
    forged_geometry = PieceGeometry("audit.valid", "audit", ((0, 0),))
    object.__setattr__(forged_geometry, "coordinates", ((0, 0), (2, 0)))
    with pytest.raises(ValueError, match="connected"):
        place_one(SparseAggregate.empty(3), forged_geometry, 0, ContactKind.SUPPORTED_V1)
    with pytest.raises(ValueError, match="connected"):
        validate_periodic_law(3, [forged_geometry])

    caller_cells: set[Cell] = set()
    forged_state = SparseAggregate.empty(3)
    object.__setattr__(forged_state, "occupied", caller_cells)
    placement = place_one(forged_state, ONE_CELL, 0, ContactKind.SUPPORTED_V1)
    caller_cells.add((2, 4))
    assert placement.pre_state.occupied == frozenset()
    assert placement.post_state.occupied == frozenset({(0, 0)})

    invalid_state = SparseAggregate.empty(3)
    object.__setattr__(invalid_state, "occupied", {(3, 0)})
    with pytest.raises(ValueError, match="occupied x"):
        place_one(invalid_state, ONE_CELL, 0, ContactKind.SUPPORTED_V1)


def test_generic_width_guards_are_geometry_aware() -> None:
    horizontal_i = GEOMETRY_BY_ID["tetromino.i.00"]
    lj = GEOMETRY_BY_ID["tetromino.lj.02"]

    with pytest.raises(ValueError):
        SparseAggregate.empty(2)
    with pytest.raises(ValueError):
        place_one(SparseAggregate.empty(3), horizontal_i, 0, ContactKind.SUPPORTED_V1)
    with pytest.raises(ValueError):
        place_one(SparseAggregate.empty(4), horizontal_i, 0, ContactKind.EDGE_FIRST_CONTACT_V1)

    assert place_one(SparseAggregate.empty(3), lj, 2, ContactKind.SUPPORTED_V1).post_state.mass == lj.area
    assert place_one(SparseAggregate.empty(5), horizontal_i, 4, ContactKind.SUPPORTED_V1).post_state.mass == horizontal_i.area


def test_periodic_law_preflight_checks_the_complete_positive_weight_support() -> None:
    horizontal_i = GEOMETRY_BY_ID["tetromino.i.00"]

    # A one-cell event is individually legal at L=3, but the enclosing mixed
    # law is not: its positive-weight horizontal-I orientation has width four.
    assert place_one(SparseAggregate.empty(3), ONE_CELL, 0, ContactKind.SUPPORTED_V1).post_state.mass == 1
    with pytest.raises(ValueError, match="every positive-weight geometry"):
        validate_periodic_law(3, [ONE_CELL, horizontal_i])

    supplied = [ONE_CELL, horizontal_i]
    snapshot = validate_periodic_law(5, supplied)
    supplied.clear()
    assert snapshot == (ONE_CELL, horizontal_i)

    with pytest.raises(ValueError, match="must not be empty"):
        validate_periodic_law(5, [])
    with pytest.raises(TypeError, match="plain nonempty list or tuple"):
        validate_periodic_law(5, {ONE_CELL})
    with pytest.raises(ValueError, match="unique geometry IDs"):
        validate_periodic_law(5, [ONE_CELL, ONE_CELL])
