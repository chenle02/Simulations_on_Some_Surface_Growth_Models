"""Slow, exact one-event oracle for the approved periodic placement laws.

The implementation follows the spawn-independent set definitions of
``supported-v1`` and ``edge-first-contact-v1``.  It contains no RNG,
trajectory loop, capacity ceiling, legacy dispatch, or optimized execution
route.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..models import ContactKind, PieceGeometry
from .state import SparseAggregate, WorldCell


class ContactFaceKind(str, Enum):
    """Directed final face contacts relative to a placed piece cell."""

    FLOOR_SUPPORT = "floor-support"
    AGGREGATE_SUPPORT = "aggregate-support"
    LATERAL_LEFT = "lateral-left"
    LATERAL_RIGHT = "lateral-right"
    AGGREGATE_ABOVE = "aggregate-above"


_CONTACT_FACE_ORDER = {kind: index for index, kind in enumerate(ContactFaceKind)}


@dataclass(frozen=True, slots=True)
class ContactFace:
    """One unique piece-to-floor or piece-to-pre-event-aggregate face."""

    kind: ContactFaceKind
    piece_cell: WorldCell
    neighbor_cell: WorldCell | None
    crosses_seam: bool

    def __post_init__(self) -> None:
        if type(self.kind) is not ContactFaceKind:
            raise TypeError("contact kind must be a ContactFaceKind")
        if type(self.piece_cell) is not tuple or len(self.piece_cell) != 2:
            raise TypeError("piece_cell must be a built-in integer (x, y) tuple")
        if any(type(coordinate) is not int for coordinate in self.piece_cell):
            raise TypeError("piece_cell must be a built-in integer (x, y) tuple")
        if any(coordinate < 0 for coordinate in self.piece_cell):
            raise ValueError("piece_cell coordinates must be nonnegative")
        if self.neighbor_cell is not None:
            if type(self.neighbor_cell) is not tuple or len(self.neighbor_cell) != 2:
                raise TypeError("neighbor_cell must be None or a built-in integer (x, y) tuple")
            if any(type(coordinate) is not int for coordinate in self.neighbor_cell):
                raise TypeError("neighbor_cell must be None or a built-in integer (x, y) tuple")
            if any(coordinate < 0 for coordinate in self.neighbor_cell):
                raise ValueError("neighbor_cell coordinates must be nonnegative")
        if type(self.crosses_seam) is not bool:
            raise TypeError("crosses_seam must be a built-in bool")
        if self.kind is ContactFaceKind.FLOOR_SUPPORT:
            if self.neighbor_cell is not None or self.piece_cell[1] != 0 or self.crosses_seam:
                raise ValueError("floor contacts require a y=0 piece cell, no neighbor cell, and no seam")
        elif self.neighbor_cell is None:
            raise ValueError("aggregate contacts require a neighbor cell")
        elif self.kind not in (ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT) and self.crosses_seam:
            raise ValueError("only lateral contacts can cross the periodic seam")


def _contact_sort_key(contact: ContactFace) -> tuple[WorldCell, int, WorldCell]:
    neighbor_cell = contact.neighbor_cell if contact.neighbor_cell is not None else (-1, -1)
    return (contact.piece_cell, _CONTACT_FACE_ORDER[contact.kind], neighbor_cell)


def _snapshot_geometry(value: object) -> PieceGeometry:
    if type(value) is not PieceGeometry:
        raise TypeError("geometry must be a PieceGeometry")
    try:
        return PieceGeometry(
            id=value.id,
            family_id=value.family_id,
            coordinates=value.coordinates,
        )
    except AttributeError as error:
        raise TypeError("geometry must be fully initialized") from error


def _snapshot_state(value: object, *, label: str) -> SparseAggregate:
    if type(value) is not SparseAggregate:
        raise TypeError(f"{label} must be a SparseAggregate")
    try:
        return SparseAggregate(width=value.width, occupied=value.occupied)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class ReferencePlacement:
    """Immutable output of one reference placement transition.

    ``contacts`` records every directed N4 aggregate face plus floor support at
    the final height. ``stopping_contacts`` records the faces enabled by the
    selected stopping predicate. ``causal_contacts`` is the counterfactually
    causal subset, so zero-gap lateral faces remain incidental.
    """

    geometry_id: str
    geometry: PieceGeometry
    contact_kind: ContactKind
    anchor_x: int
    landing_y: int
    supported_landing_y: int
    early_arrest_gap: int
    piece_cells: tuple[WorldCell, ...]
    contacts: tuple[ContactFace, ...]
    stopping_contacts: tuple[ContactFace, ...]
    causal_contacts: tuple[ContactFace, ...]
    pre_state: SparseAggregate
    post_state: SparseAggregate

    def __post_init__(self) -> None:
        if type(self.geometry_id) is not str or not self.geometry_id:
            raise ValueError("geometry_id must be a nonempty built-in string")
        geometry = _snapshot_geometry(self.geometry)
        pre_state = _snapshot_state(self.pre_state, label="pre_state")
        post_state = _snapshot_state(self.post_state, label="post_state")
        object.__setattr__(self, "geometry", geometry)
        object.__setattr__(self, "pre_state", pre_state)
        object.__setattr__(self, "post_state", post_state)
        if self.geometry_id != geometry.id:
            raise ValueError("geometry_id must match geometry.id")
        if type(self.contact_kind) is not ContactKind or self.contact_kind not in _EXECUTABLE_CONTACT_KINDS:
            raise ValueError("contact_kind must be supported-v1 or edge-first-contact-v1")
        if pre_state.width != post_state.width:
            raise ValueError("pre_state and post_state widths must match")
        if type(self.anchor_x) is not int or not 0 <= self.anchor_x < pre_state.width:
            raise ValueError("anchor_x must be a built-in integer in [0, width)")
        if pre_state.width <= geometry.width:
            raise ValueError("generic periodic laws require width greater than the geometry bounding-box width")
        integer_fields = (
            self.landing_y,
            self.supported_landing_y,
            self.early_arrest_gap,
        )
        if any(type(value) is not int or value < 0 for value in integer_fields):
            raise ValueError("landing heights and early_arrest_gap must be nonnegative built-in integers")
        if self.early_arrest_gap != self.landing_y - self.supported_landing_y:
            raise ValueError("early_arrest_gap must equal landing_y minus supported_landing_y")
        if self.contact_kind is ContactKind.SUPPORTED_V1 and self.early_arrest_gap != 0:
            raise ValueError("supported-v1 must land at its supported counterfactual height")

        local_cells = tuple((delta_x, delta_y) for delta_y, delta_x in geometry.world_coordinates)
        _validate_wrapping(local_cells, state=pre_state, anchor_x=self.anchor_x)
        if type(self.piece_cells) is not tuple or not self.piece_cells:
            raise TypeError("piece_cells must be a nonempty built-in tuple")
        for cell in self.piece_cells:
            if type(cell) is not tuple or len(cell) != 2 or any(type(coordinate) is not int for coordinate in cell):
                raise TypeError("piece_cells must contain built-in integer (x, y) tuples")
            if not 0 <= cell[0] < post_state.width or cell[1] < 0:
                raise ValueError("piece_cells must lie in the post-state lattice")
        if self.piece_cells != tuple(sorted(set(self.piece_cells))):
            raise ValueError("piece_cells must be unique and canonically sorted")
        expected_piece_cells = _wrapped_piece_cells(
            local_cells,
            width=pre_state.width,
            anchor_x=self.anchor_x,
            landing_y=self.landing_y,
        )
        if self.piece_cells != expected_piece_cells:
            raise ValueError("piece_cells do not match geometry, anchor_x, and landing_y")
        if not pre_state.occupied.isdisjoint(self.piece_cells):
            raise ValueError("piece_cells must not overlap pre_state")
        expected_post_occupied = pre_state.occupied.union(self.piece_cells)
        if post_state.occupied != expected_post_occupied:
            raise ValueError("post_state must equal pre_state union piece_cells")

        expected_supported_landing_y = _landing_height(
            local_cells,
            geometry_area=geometry.area,
            state=pre_state,
            anchor_x=self.anchor_x,
            include_lateral=False,
        )
        expected_landing_y = (
            expected_supported_landing_y
            if self.contact_kind is ContactKind.SUPPORTED_V1
            else _landing_height(
                local_cells,
                geometry_area=geometry.area,
                state=pre_state,
                anchor_x=self.anchor_x,
                include_lateral=True,
            )
        )
        if self.supported_landing_y != expected_supported_landing_y or self.landing_y != expected_landing_y:
            raise ValueError("landing heights must be the maximum valid heights under the selected law")

        if type(self.contacts) is not tuple or any(type(contact) is not ContactFace for contact in self.contacts):
            raise TypeError("contacts must be a built-in tuple of ContactFace values")
        if type(self.stopping_contacts) is not tuple or any(
            type(contact) is not ContactFace for contact in self.stopping_contacts
        ):
            raise TypeError("stopping_contacts must be a built-in tuple of ContactFace values")
        if type(self.causal_contacts) is not tuple or any(
            type(contact) is not ContactFace for contact in self.causal_contacts
        ):
            raise TypeError("causal_contacts must be a built-in tuple of ContactFace values")

        expected_contacts = _contact_faces(self.piece_cells, state=pre_state)
        if self.contacts != expected_contacts:
            raise ValueError("contacts must contain every final directed face in canonical order")
        stopping_face_kinds = (
            _SUPPORT_FACE_KINDS if self.contact_kind is ContactKind.SUPPORTED_V1 else _EDGE_FIRST_FACE_KINDS
        )
        expected_stopping_contacts = tuple(contact for contact in self.contacts if contact.kind in stopping_face_kinds)
        if self.stopping_contacts != expected_stopping_contacts:
            raise ValueError("stopping_contacts do not match the selected stopping predicate")
        causal_face_kinds = (
            _LATERAL_FACE_KINDS
            if self.contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1 and self.early_arrest_gap > 0
            else _SUPPORT_FACE_KINDS
        )
        expected_causal_contacts = tuple(contact for contact in self.contacts if contact.kind in causal_face_kinds)
        if self.causal_contacts != expected_causal_contacts:
            raise ValueError("causal_contacts do not match the selected stopping law")
        if not self.causal_contacts:
            raise ValueError("a placement must have at least one causal contact")

    @property
    def lateral_trigger(self) -> bool:
        """Whether edge-first contact stopped strictly above supported descent."""

        return self.contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1 and self.early_arrest_gap > 0

    @property
    def contacted_support_columns(self) -> tuple[int, ...]:
        """Sorted aggregate-support columns, excluding floor support."""

        return tuple(
            sorted(
                {
                    contact.neighbor_cell[0]
                    for contact in self.contacts
                    if contact.kind is ContactFaceKind.AGGREGATE_SUPPORT and contact.neighbor_cell is not None
                }
            )
        )


_EXECUTABLE_CONTACT_KINDS = frozenset(
    {
        ContactKind.SUPPORTED_V1,
        ContactKind.EDGE_FIRST_CONTACT_V1,
    }
)
_SUPPORT_FACE_KINDS = frozenset(
    {
        ContactFaceKind.FLOOR_SUPPORT,
        ContactFaceKind.AGGREGATE_SUPPORT,
    }
)
_LATERAL_FACE_KINDS = frozenset({ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT})
_EDGE_FIRST_FACE_KINDS = _SUPPORT_FACE_KINDS.union(_LATERAL_FACE_KINDS)


def _wrapped_piece_cells(
    local_cells: tuple[WorldCell, ...],
    *,
    width: int,
    anchor_x: int,
    landing_y: int,
) -> tuple[WorldCell, ...]:
    return tuple(sorted((((anchor_x + delta_x) % width, landing_y + delta_y) for delta_x, delta_y in local_cells)))


def _is_valid(piece_cells: tuple[WorldCell, ...], *, area: int, occupied: frozenset[WorldCell]) -> bool:
    return (
        len(piece_cells) == area
        and len(set(piece_cells)) == area
        and all(y >= 0 for _, y in piece_cells)
        and occupied.isdisjoint(piece_cells)
    )


def _has_support(piece_cells: tuple[WorldCell, ...], occupied: frozenset[WorldCell]) -> bool:
    return any(y == 0 or (x, y - 1) in occupied for x, y in piece_cells)


def _has_lateral_contact(
    piece_cells: tuple[WorldCell, ...],
    *,
    width: int,
    occupied: frozenset[WorldCell],
) -> bool:
    return any(((x - 1) % width, y) in occupied or ((x + 1) % width, y) in occupied for x, y in piece_cells)


def _candidate_heights(
    local_cells: tuple[WorldCell, ...],
    *,
    state: SparseAggregate,
    anchor_x: int,
    include_lateral: bool,
) -> set[int]:
    candidates = {0}
    for delta_x, delta_y in local_cells:
        piece_x = (anchor_x + delta_x) % state.width
        for aggregate_x, aggregate_y in state.occupied:
            if aggregate_x == piece_x:
                candidates.add(aggregate_y + 1 - delta_y)
            if include_lateral and aggregate_y >= delta_y:
                if aggregate_x in ((piece_x - 1) % state.width, (piece_x + 1) % state.width):
                    candidates.add(aggregate_y - delta_y)
    return {height for height in candidates if height >= 0}


def _landing_height(
    local_cells: tuple[WorldCell, ...],
    *,
    geometry_area: int,
    state: SparseAggregate,
    anchor_x: int,
    include_lateral: bool,
) -> int:
    valid_landings: list[int] = []
    for height in _candidate_heights(
        local_cells,
        state=state,
        anchor_x=anchor_x,
        include_lateral=include_lateral,
    ):
        piece_cells = _wrapped_piece_cells(
            local_cells,
            width=state.width,
            anchor_x=anchor_x,
            landing_y=height,
        )
        if not _is_valid(piece_cells, area=geometry_area, occupied=state.occupied):
            continue
        if _has_support(piece_cells, state.occupied) or (
            include_lateral and _has_lateral_contact(piece_cells, width=state.width, occupied=state.occupied)
        ):
            valid_landings.append(height)
    if not valid_landings:  # pragma: no cover - floor support guarantees a candidate for valid inputs
        raise RuntimeError("no valid landing height exists")
    return max(valid_landings)


def _internal_edges(local_cells: tuple[WorldCell, ...], *, width: int | None = None) -> frozenset[tuple[int, int]]:
    edges: set[tuple[int, int]] = set()
    for left_index, (left_x, left_y) in enumerate(local_cells):
        for right_index in range(left_index + 1, len(local_cells)):
            right_x, right_y = local_cells[right_index]
            vertical_neighbors = left_x == right_x and abs(left_y - right_y) == 1
            if width is None:
                horizontal_neighbors = left_y == right_y and abs(left_x - right_x) == 1
            else:
                horizontal_neighbors = left_y == right_y and (left_x - right_x) % width in (1, width - 1)
            if vertical_neighbors or horizontal_neighbors:
                edges.add((left_index, right_index))
    return frozenset(edges)


def _validate_wrapping(local_cells: tuple[WorldCell, ...], *, state: SparseAggregate, anchor_x: int) -> None:
    wrapped = tuple(((anchor_x + delta_x) % state.width, delta_y) for delta_x, delta_y in local_cells)
    if len(set(wrapped)) != len(local_cells):
        raise ValueError("periodic wrapping maps multiple geometry cells to one site")
    if _internal_edges(local_cells) != _internal_edges(wrapped, width=state.width):
        raise ValueError("periodic wrapping changes the geometry's internal N4 adjacency graph")


def validate_periodic_law(
    width: int,
    positive_geometries: list[PieceGeometry] | tuple[PieceGeometry, ...],
) -> tuple[PieceGeometry, ...]:
    """Validate every positive-weight geometry before a periodic law executes.

    The one-event oracle cannot infer an enclosing mixture.  Callers defining a
    multi-geometry law must pass its complete positive-weight support here; a
    later trajectory/configuration route will make this preflight mandatory.
    The returned tuple is a defensive immutable snapshot of the validated
    geometry sequence.

    One canonical anchor suffices for each geometry.  For fixed width, cyclic
    horizontal translation is a bijection of lattice sites and an automorphism
    of the periodic N4 graph.  Wrapping at any anchor is therefore the
    anchor-zero wrapping followed by such a translation, so both cell
    cardinality and the internal adjacency graph have the same verdict at
    every anchor.
    """

    state = SparseAggregate.empty(width)
    if type(positive_geometries) not in (list, tuple):
        raise TypeError("positive_geometries must be a plain nonempty list or tuple")
    if not positive_geometries:
        raise ValueError("positive_geometries must not be empty")

    geometries: list[PieceGeometry] = []
    for geometry in positive_geometries:
        try:
            geometries.append(_snapshot_geometry(geometry))
        except TypeError as error:
            raise TypeError("positive_geometries must contain PieceGeometry values") from error
    snapshot = tuple(geometries)
    geometry_ids = tuple(geometry.id for geometry in snapshot)
    if len(set(geometry_ids)) != len(geometry_ids):
        raise ValueError("positive_geometries must have unique geometry IDs")
    maximum_width = max(geometry.width for geometry in snapshot)
    if state.width <= maximum_width:
        raise ValueError(
            "generic periodic laws require width greater than every positive-weight geometry bounding-box width"
        )

    for geometry in snapshot:
        local_cells = tuple((delta_x, delta_y) for delta_y, delta_x in geometry.world_coordinates)
        _validate_wrapping(local_cells, state=state, anchor_x=0)
    return snapshot


def _contact_faces(
    piece_cells: tuple[WorldCell, ...],
    *,
    state: SparseAggregate,
) -> tuple[ContactFace, ...]:
    contacts: list[ContactFace] = []
    for piece_cell in piece_cells:
        x, y = piece_cell
        if y == 0:
            contacts.append(ContactFace(ContactFaceKind.FLOOR_SUPPORT, piece_cell, None, False))
        elif (x, y - 1) in state.occupied:
            contacts.append(ContactFace(ContactFaceKind.AGGREGATE_SUPPORT, piece_cell, (x, y - 1), False))

        left_neighbor = ((x - 1) % state.width, y)
        if left_neighbor in state.occupied:
            contacts.append(ContactFace(ContactFaceKind.LATERAL_LEFT, piece_cell, left_neighbor, x == 0))

        right_neighbor = ((x + 1) % state.width, y)
        if right_neighbor in state.occupied:
            contacts.append(
                ContactFace(ContactFaceKind.LATERAL_RIGHT, piece_cell, right_neighbor, x == state.width - 1)
            )

        above_neighbor = (x, y + 1)
        if above_neighbor in state.occupied:
            contacts.append(ContactFace(ContactFaceKind.AGGREGATE_ABOVE, piece_cell, above_neighbor, False))

    return tuple(
        sorted(
            contacts,
            key=_contact_sort_key,
        )
    )


def place_one(
    state: SparseAggregate,
    geometry: PieceGeometry,
    anchor_x: int,
    contact_kind: ContactKind,
) -> ReferencePlacement:
    """Place one fixed geometry under an approved periodic contact endpoint.

    The input state is not mutated.  The generic-law width restrictions are
    enforced per geometry, and unversioned prototypes plus all legacy mechanics
    fail closed.
    """

    state = _snapshot_state(state, label="state")
    geometry = _snapshot_geometry(geometry)
    if type(anchor_x) is not int or not 0 <= anchor_x < state.width:
        raise ValueError("anchor_x must be a built-in integer in [0, width)")
    if type(contact_kind) is not ContactKind or contact_kind not in _EXECUTABLE_CONTACT_KINDS:
        raise ValueError("contact_kind must be supported-v1 or edge-first-contact-v1")
    if state.width <= geometry.width:
        raise ValueError("generic periodic laws require width greater than the geometry bounding-box width")

    # Geometry records use (row, column); the placement law uses local (x, y).
    local_cells = tuple((delta_x, delta_y) for delta_y, delta_x in geometry.world_coordinates)
    _validate_wrapping(local_cells, state=state, anchor_x=anchor_x)

    supported_landing_y = _landing_height(
        local_cells,
        geometry_area=geometry.area,
        state=state,
        anchor_x=anchor_x,
        include_lateral=False,
    )
    landing_y = (
        supported_landing_y
        if contact_kind is ContactKind.SUPPORTED_V1
        else _landing_height(
            local_cells,
            geometry_area=geometry.area,
            state=state,
            anchor_x=anchor_x,
            include_lateral=True,
        )
    )
    piece_cells = _wrapped_piece_cells(
        local_cells,
        width=state.width,
        anchor_x=anchor_x,
        landing_y=landing_y,
    )
    contacts = _contact_faces(piece_cells, state=state)
    stopping_face_kinds = _SUPPORT_FACE_KINDS if contact_kind is ContactKind.SUPPORTED_V1 else _EDGE_FIRST_FACE_KINDS
    stopping_contacts = tuple(contact for contact in contacts if contact.kind in stopping_face_kinds)
    causal_face_kinds = (
        _LATERAL_FACE_KINDS
        if contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1 and landing_y > supported_landing_y
        else _SUPPORT_FACE_KINDS
    )
    causal_contacts = tuple(contact for contact in contacts if contact.kind in causal_face_kinds)
    post_state = SparseAggregate(state.width, state.occupied.union(piece_cells))

    return ReferencePlacement(
        geometry_id=geometry.id,
        geometry=geometry,
        contact_kind=contact_kind,
        anchor_x=anchor_x,
        landing_y=landing_y,
        supported_landing_y=supported_landing_y,
        early_arrest_gap=landing_y - supported_landing_y,
        piece_cells=piece_cells,
        contacts=contacts,
        stopping_contacts=stopping_contacts,
        causal_contacts=causal_contacts,
        pre_state=state,
        post_state=post_state,
    )
