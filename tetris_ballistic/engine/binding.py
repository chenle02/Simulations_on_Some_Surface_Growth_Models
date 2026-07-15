"""Explicit one-event binding between certified selection and placement.

This provisional reference-only surface accepts one already-created
:class:`~tetris_ballistic.engine.event.TetrominoEventSelection`, validates its
complete positive geometry support against one sparse periodic state, and
delegates exactly one placement to the S2.1 oracle.  It does not select an
event, replay RNG, measure observables, accumulate counters, run a trajectory,
adapt configuration, serialize an artifact, or expose an HPC/production route.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from ..models import (
    FAMILY_ORIENTATION_IDS,
    GEOMETRY_BY_ID,
    TETROMINO_REGISTRY,
    ContactKind,
    PieceGeometry,
)
from .event import TetrominoEventSelection
from .reference import ReferencePlacement, place_one, validate_periodic_law
from .state import SparseAggregate

__all__ = ["ReferenceEventPlacement", "place_selected_event"]

_MAPPING_PROXY_TYPE = type(MappingProxyType({}))
_RATIFIED_REGISTRY_RECORDS = (
    ("tetromino.i.00", "i", ((0, 0), (0, 1), (0, 2), (0, 3))),
    ("tetromino.i.01", "i", ((0, 0), (1, 0), (2, 0), (3, 0))),
    ("tetromino.lj.00", "lj", ((0, 0), (0, 1), (0, 2), (1, 0))),
    ("tetromino.lj.01", "lj", ((0, 0), (0, 1), (0, 2), (1, 2))),
    ("tetromino.lj.02", "lj", ((0, 0), (0, 1), (1, 0), (2, 0))),
    ("tetromino.lj.03", "lj", ((0, 0), (0, 1), (1, 1), (2, 1))),
    ("tetromino.lj.04", "lj", ((0, 0), (1, 0), (1, 1), (1, 2))),
    ("tetromino.lj.05", "lj", ((0, 0), (1, 0), (2, 0), (2, 1))),
    ("tetromino.lj.06", "lj", ((0, 1), (1, 1), (2, 0), (2, 1))),
    ("tetromino.lj.07", "lj", ((0, 2), (1, 0), (1, 1), (1, 2))),
    ("tetromino.o.00", "o", ((0, 0), (0, 1), (1, 0), (1, 1))),
    ("tetromino.sz.00", "sz", ((0, 0), (0, 1), (1, 1), (1, 2))),
    ("tetromino.sz.01", "sz", ((0, 0), (1, 0), (1, 1), (2, 1))),
    ("tetromino.sz.02", "sz", ((0, 1), (0, 2), (1, 0), (1, 1))),
    ("tetromino.sz.03", "sz", ((0, 1), (1, 0), (1, 1), (2, 0))),
    ("tetromino.t.00", "t", ((0, 0), (0, 1), (0, 2), (1, 1))),
    ("tetromino.t.01", "t", ((0, 0), (1, 0), (1, 1), (2, 0))),
    ("tetromino.t.02", "t", ((0, 1), (1, 0), (1, 1), (1, 2))),
    ("tetromino.t.03", "t", ((0, 1), (1, 0), (1, 1), (2, 1))),
)
_RATIFIED_FAMILY_ORIENTATION_ITEMS = (
    ("i", ("tetromino.i.00", "tetromino.i.01")),
    (
        "lj",
        tuple(f"tetromino.lj.{index:02d}" for index in range(8)),
    ),
    ("o", ("tetromino.o.00",)),
    (
        "sz",
        tuple(f"tetromino.sz.{index:02d}" for index in range(4)),
    ),
    (
        "t",
        tuple(f"tetromino.t.{index:02d}" for index in range(4)),
    ),
)
_RATIFIED_GEOMETRY_MAP_RECORDS = tuple(
    (geometry_id, geometry_id, family_id, coordinates)
    for geometry_id, family_id, coordinates in _RATIFIED_REGISTRY_RECORDS
) + (("baseline.one-cell", "baseline.one-cell", "one-cell", ((0, 0),)),)
_RATIFIED_CONTACTS = (
    ("supported-v1", ContactKind.SUPPORTED_V1),
    ("edge-first-contact-v1", ContactKind.EDGE_FIRST_CONTACT_V1),
)


def _snapshot_state(value: object) -> SparseAggregate:
    if type(value) is not SparseAggregate:
        raise TypeError("state must be a SparseAggregate")
    try:
        return SparseAggregate(width=value.width, occupied=value.occupied)
    except AttributeError as error:
        raise TypeError("state must be fully initialized") from error


def _snapshot_selection(value: object) -> TetrominoEventSelection:
    if type(value) is not TetrominoEventSelection:
        raise TypeError("selection must be a TetrominoEventSelection")
    try:
        return TetrominoEventSelection(
            root_seed=value.root_seed,
            coupling_group_id=value.coupling_group_id,
            event_ordinal=value.event_ordinal,
            law=value.law,
            family=value.family,
            orientation=value.orientation,
            launch=value.launch,
            contact=value.contact,
        )
    except AttributeError as error:
        raise TypeError("selection must be fully initialized") from error


def _snapshot_placement(value: object) -> ReferencePlacement:
    if type(value) is not ReferencePlacement:
        raise TypeError("placement must be a ReferencePlacement")
    try:
        return ReferencePlacement(
            geometry_id=value.geometry_id,
            geometry=value.geometry,
            contact_kind=value.contact_kind,
            anchor_x=value.anchor_x,
            landing_y=value.landing_y,
            supported_landing_y=value.supported_landing_y,
            early_arrest_gap=value.early_arrest_gap,
            piece_cells=value.piece_cells,
            contacts=value.contacts,
            stopping_contacts=value.stopping_contacts,
            causal_contacts=value.causal_contacts,
            pre_state=value.pre_state,
            post_state=value.post_state,
        )
    except AttributeError as error:
        raise TypeError("placement must be fully initialized") from error


def _snapshot_registry_geometry(value: object, *, label: str) -> PieceGeometry:
    if type(value) is not PieceGeometry:
        raise AssertionError(f"{label} must be a PieceGeometry")
    try:
        return PieceGeometry(id=value.id, family_id=value.family_id, coordinates=value.coordinates)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError(f"{label} is malformed") from error


def _copy_geometry(value: PieceGeometry) -> PieceGeometry:
    """Return a detached exact geometry for an untrusted delegate boundary."""

    return PieceGeometry(id=value.id, family_id=value.family_id, coordinates=value.coordinates)


def _ratified_geometry_by_id() -> dict[str, PieceGeometry]:
    """Return fresh registry snapshots after checking every ratified authority."""

    if type(TETROMINO_REGISTRY) is not tuple:
        raise AssertionError("TETROMINO_REGISTRY has an invalid record type")
    registry = tuple(
        _snapshot_registry_geometry(value, label=f"TETROMINO_REGISTRY entry {index}")
        for index, value in enumerate(TETROMINO_REGISTRY)
    )
    registry_records = tuple((value.id, value.family_id, value.coordinates) for value in registry)
    if registry_records != _RATIFIED_REGISTRY_RECORDS:
        raise AssertionError("TETROMINO_REGISTRY does not match the ratified geometry registry")

    if type(FAMILY_ORIENTATION_IDS) is not _MAPPING_PROXY_TYPE:
        raise AssertionError("FAMILY_ORIENTATION_IDS has an invalid mapping type")
    try:
        family_orientation_items = tuple(FAMILY_ORIENTATION_IDS.items())
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("FAMILY_ORIENTATION_IDS is malformed") from error
    if family_orientation_items != _RATIFIED_FAMILY_ORIENTATION_ITEMS or any(
        type(family_id) is not str
        or type(geometry_ids) is not tuple
        or any(type(geometry_id) is not str for geometry_id in geometry_ids)
        for family_id, geometry_ids in family_orientation_items
    ):
        raise AssertionError("FAMILY_ORIENTATION_IDS does not match the ratified geometry registry")

    if type(GEOMETRY_BY_ID) is not _MAPPING_PROXY_TYPE:
        raise AssertionError("GEOMETRY_BY_ID has an invalid mapping type")
    try:
        geometry_map = tuple(
            (
                geometry_id,
                _snapshot_registry_geometry(value, label=f"GEOMETRY_BY_ID entry {geometry_id!r}"),
            )
            for geometry_id, value in GEOMETRY_BY_ID.items()
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("GEOMETRY_BY_ID is malformed") from error
    geometry_map_records = tuple(
        (geometry_id, value.id, value.family_id, value.coordinates) for geometry_id, value in geometry_map
    )
    if geometry_map_records != _RATIFIED_GEOMETRY_MAP_RECORDS:
        raise AssertionError("GEOMETRY_BY_ID does not match the ratified geometry registry")

    snapshots = {value.id: value for value in registry}
    if len(snapshots) != len(registry):
        raise AssertionError("TETROMINO_REGISTRY contains duplicate geometry IDs")
    for family_id, geometry_ids in family_orientation_items:
        for geometry_id in geometry_ids:
            geometry = snapshots.get(geometry_id)
            if geometry is None or geometry.family_id != family_id:
                raise AssertionError("the ratified orientation registry is inconsistent with geometry families")
    return snapshots


def _positive_geometry_support(
    selection: TetrominoEventSelection,
    *,
    registry: dict[str, PieceGeometry],
) -> tuple[PieceGeometry, ...]:
    support: list[PieceGeometry] = []
    family_law = selection.law.family_law
    orientation_laws = selection.law.orientation_laws
    for family_id, family_count, orientation_law in zip(
        family_law.outcome_ids,
        family_law.counts,
        orientation_laws.branch_laws,
    ):
        if family_count == 0:
            continue
        for geometry_id, orientation_count in zip(orientation_law.outcome_ids, orientation_law.counts):
            if orientation_count == 0:
                continue
            geometry = registry.get(geometry_id)
            if geometry is None or geometry.family_id != family_id:
                raise AssertionError("the event law is inconsistent with the ratified geometry registry")
            support.append(geometry)
    if not support or selection.geometry_id not in {geometry.id for geometry in support}:
        raise AssertionError("the selected geometry is absent from the positive joint event-law support")
    return tuple(support)


def _resolve_contact(contact_id: str) -> ContactKind:
    for expected_id, contact_kind in _RATIFIED_CONTACTS:
        if contact_id == expected_id:
            return contact_kind
    raise AssertionError("the selected contact ID is not a ratified executable contact")


def _validate_preflight_result(
    value: object,
    *,
    expected: tuple[PieceGeometry, ...],
) -> None:
    if type(value) is not tuple:
        raise AssertionError("validate_periodic_law returned a non-tuple result")
    actual = tuple(
        _snapshot_registry_geometry(geometry, label=f"validate_periodic_law result {index}")
        for index, geometry in enumerate(value)
    )
    if actual != expected:
        raise AssertionError("validate_periodic_law returned geometry support inconsistent with its input")


def _prepare_binding(
    state: SparseAggregate,
    selection: TetrominoEventSelection,
) -> tuple[PieceGeometry, ContactKind]:
    if selection.law.launch_law.upper_bound != state.width:
        raise ValueError("selection launch-law upper bound must equal state width")

    registry = _ratified_geometry_by_id()
    support = _positive_geometry_support(selection, registry=registry)
    # Recertify the decisive periodic invariant locally before trusting the
    # delegated preflight.  Every ratified geometry is normalized at anchor
    # zero, so width strictly greater than its bounding-box width means no cell
    # wraps there; cardinality and internal N4 adjacency are then unchanged,
    # and cyclic translation proves the same at every anchor.
    if state.width <= max(geometry.width for geometry in support):
        raise ValueError(
            "generic periodic laws require width greater than every positive-weight geometry bounding-box width"
        )
    # Keep the ratified support snapshots pristine.  Exact frozen dataclasses
    # can still be modified by hostile ``object.__setattr__`` calls, so no
    # object handed to a delegate may also serve as a later comparison
    # authority.
    preflight_inputs = tuple(_copy_geometry(geometry) for geometry in support)
    try:
        preflight = validate_periodic_law(state.width, preflight_inputs)
    except TypeError as error:
        raise AssertionError("validate_periodic_law rejected validated binding inputs") from error
    _validate_preflight_result(preflight, expected=support)

    geometry = registry.get(selection.geometry_id)
    if geometry is None or geometry.family_id != selection.family_id:
        raise AssertionError("the selected family and geometry are inconsistent with the ratified registry")
    return geometry, _resolve_contact(selection.contact_id)


def _raise_cross_field(message: str, *, internal: bool) -> None:
    if internal:
        raise AssertionError(message)
    raise ValueError(message)


def _validate_bound_pair(
    selection: TetrominoEventSelection,
    placement: ReferencePlacement,
    *,
    expected_state: SparseAggregate,
    expected_geometry: PieceGeometry,
    expected_contact: ContactKind,
    internal: bool,
) -> None:
    if placement.pre_state != expected_state:
        _raise_cross_field("placement pre_state must equal the bound input state", internal=internal)
    if placement.geometry_id != selection.geometry_id or placement.geometry != expected_geometry:
        _raise_cross_field("placement geometry must equal the selected ratified geometry", internal=internal)
    if placement.geometry.family_id != selection.family_id:
        _raise_cross_field("placement geometry family must equal the selected family", internal=internal)
    if placement.anchor_x != selection.launch_x:
        _raise_cross_field("placement anchor must equal the selected launch", internal=internal)
    if placement.contact_kind is not expected_contact:
        _raise_cross_field("placement contact kind must equal the selected contact", internal=internal)
    if not placement.pre_state.occupied.isdisjoint(placement.piece_cells):
        _raise_cross_field("placement piece cells must not overlap the pre_state", internal=internal)
    if placement.post_state.mass - placement.pre_state.mass != expected_geometry.area:
        _raise_cross_field("placement mass delta must equal the selected geometry area", internal=internal)


@dataclass(frozen=True, slots=True)
class ReferenceEventPlacement:
    """One structural in-memory binding of selection evidence to placement.

    Direct construction defensively recertifies both nested records and their
    complete cross-field relation.  It does not replay Philox, so the semantic
    RNG guarantee applies only when ``selection`` came from ``select_event``.
    This record defines no serialization or persistent event identity.
    """

    selection: TetrominoEventSelection
    placement: ReferencePlacement

    def __post_init__(self) -> None:
        # Placement is reconstructed first so the direct boundary follows the
        # same state-first precedence as ``place_selected_event``.
        placement = _snapshot_placement(self.placement)
        selection = _snapshot_selection(self.selection)
        geometry, contact = _prepare_binding(placement.pre_state, selection)
        _validate_bound_pair(
            selection,
            placement,
            expected_state=placement.pre_state,
            expected_geometry=geometry,
            expected_contact=contact,
            internal=False,
        )
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "placement", placement)


def place_selected_event(
    *,
    state: SparseAggregate,
    selection: TetrominoEventSelection,
) -> ReferenceEventPlacement:
    """Place one already-selected event through the slow reference oracle."""

    state_snapshot = _snapshot_state(state)
    selection_snapshot = _snapshot_selection(selection)
    geometry, contact = _prepare_binding(state_snapshot, selection_snapshot)

    # ``place_one`` is an internal certified dependency, but treat its object
    # boundary adversarially: preserve independent pristine authorities for
    # every post-delegate comparison.
    delegated_state = SparseAggregate(width=state_snapshot.width, occupied=state_snapshot.occupied)
    delegated_geometry = _copy_geometry(geometry)

    try:
        delegated = place_one(
            delegated_state,
            delegated_geometry,
            selection_snapshot.launch_x,
            contact,
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        raise AssertionError("place_one failed for validated binding inputs") from error
    try:
        placement = _snapshot_placement(delegated)
    except (TypeError, ValueError) as error:
        raise AssertionError("place_one returned a malformed placement certificate") from error
    _validate_bound_pair(
        selection_snapshot,
        placement,
        expected_state=state_snapshot,
        expected_geometry=geometry,
        expected_contact=contact,
        internal=True,
    )

    # Both nested records, the full law support, and every cross-field identity
    # have already been recertified above.  Construct the frozen wrapper without
    # repeating the complete-law preflight after the placement call; direct
    # public construction still exercises ``__post_init__`` in full.
    result = object.__new__(ReferenceEventPlacement)
    object.__setattr__(result, "selection", selection_snapshot)
    object.__setattr__(result, "placement", placement)
    return result
