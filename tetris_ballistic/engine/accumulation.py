"""Exact in-memory folding of already-bound reference event certificates.

This explicit-only reference surface accumulates reconstructible integer
observables for one structurally claimed contiguous prefix.  It performs no
RNG, event selection, placement, trajectory driving, persistence, I/O,
configuration execution, optimization, or scheduler routing.  A value that
passes structural recertification authenticates neither its claimed history
nor the Philox provenance of its nested event selections.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import ContactKind, PieceGeometry
from . import binding as binding_engine
from .binding import ReferenceEventPlacement
from .event import (
    TETROMINO_CONTACT_ORDER,
    TETROMINO_FAMILY_ORDER,
    TetrominoEventLaw,
)
from .observables import (
    ReferencePlacementPrimitives,
    ReferenceStatePrimitives,
    measure_placement,
    measure_state,
)
from .reference import ContactFace, ContactFaceKind, ReferencePlacement, validate_periodic_law
from .state import SparseAggregate

__all__ = [
    "ReferenceEventAccumulator",
    "start_event_accumulator",
    "accumulate_event",
]

_U32_MAX = (1 << 32) - 1
_U64_MAX = (1 << 64) - 1
_U64_MODULUS = 1 << 64
_U128_MAX = (1 << 128) - 1
_RATIFIED_FAMILY_ORDER = ("i", "lj", "o", "sz", "t")
_RATIFIED_CONTACT_ORDER = ("supported-v1", "edge-first-contact-v1")
_CONTACT_KIND_BY_ID = {
    _RATIFIED_CONTACT_ORDER[0]: ContactKind.SUPPORTED_V1,
    _RATIFIED_CONTACT_ORDER[1]: ContactKind.EDGE_FIRST_CONTACT_V1,
}


def _assert_ratified_order_integrity() -> None:
    if (
        type(TETROMINO_FAMILY_ORDER) is not tuple
        or TETROMINO_FAMILY_ORDER != _RATIFIED_FAMILY_ORDER
        or any(type(value) is not str for value in TETROMINO_FAMILY_ORDER)
    ):
        raise AssertionError("TETROMINO_FAMILY_ORDER does not match the ratified order")
    if (
        type(TETROMINO_CONTACT_ORDER) is not tuple
        or TETROMINO_CONTACT_ORDER != _RATIFIED_CONTACT_ORDER
        or any(type(value) is not str for value in TETROMINO_CONTACT_ORDER)
    ):
        raise AssertionError("TETROMINO_CONTACT_ORDER does not match the ratified order")
    if (
        tuple(_CONTACT_KIND_BY_ID) != _RATIFIED_CONTACT_ORDER
        or tuple(kind.value for kind in _CONTACT_KIND_BY_ID.values()) != _RATIFIED_CONTACT_ORDER
    ):
        raise AssertionError("the executable contact map does not match the ratified order")


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _require_nonnegative_int(value: object, *, label: str) -> int:
    result = _require_int(value, label=label)
    if result < 0:
        raise ValueError(f"{label} must be nonnegative")
    return result


def _require_positive_int(value: object, *, label: str) -> int:
    result = _require_int(value, label=label)
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _require_uint(value: object, *, maximum: int, label: str) -> int:
    result = _require_int(value, label=label)
    if not 0 <= result <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return result


def _snapshot_text(value: object, *, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    if not value:
        raise ValueError(f"{label} must be nonempty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must be valid UTF-8 text") from error
    if len(encoded) > _U32_MAX:
        raise ValueError(f"{label} UTF-8 encoding is too long")
    return value


def _snapshot_state(value: object, *, label: str = "state") -> SparseAggregate:
    if type(value) is not SparseAggregate:
        raise TypeError(f"{label} must be a SparseAggregate")
    try:
        return SparseAggregate(width=value.width, occupied=value.occupied)
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


def _snapshot_law(value: object) -> TetrominoEventLaw:
    _assert_ratified_order_integrity()
    if type(value) is not TetrominoEventLaw:
        raise TypeError("law must be a TetrominoEventLaw")
    try:
        return TetrominoEventLaw(
            family_law=value.family_law,
            orientation_laws=value.orientation_laws,
            launch_law=value.launch_law,
            contact_law=value.contact_law,
        )
    except AttributeError as error:
        raise TypeError("law must be fully initialized") from error


def _snapshot_event(value: object) -> ReferenceEventPlacement:
    if type(value) is not ReferenceEventPlacement:
        raise TypeError("event must be a ReferenceEventPlacement")
    try:
        return ReferenceEventPlacement(selection=value.selection, placement=value.placement)
    except AttributeError as error:
        raise TypeError("event must be fully initialized") from error


def _copy_geometry(value: PieceGeometry) -> PieceGeometry:
    return PieceGeometry(id=value.id, family_id=value.family_id, coordinates=value.coordinates)


def _copy_contact(value: ContactFace) -> ContactFace:
    return ContactFace(
        kind=value.kind,
        piece_cell=value.piece_cell,
        neighbor_cell=value.neighbor_cell,
        crosses_seam=value.crosses_seam,
    )


def _copy_placement(value: ReferencePlacement) -> ReferencePlacement:
    return ReferencePlacement(
        geometry_id=value.geometry_id,
        geometry=_copy_geometry(value.geometry),
        contact_kind=value.contact_kind,
        anchor_x=value.anchor_x,
        landing_y=value.landing_y,
        supported_landing_y=value.supported_landing_y,
        early_arrest_gap=value.early_arrest_gap,
        piece_cells=value.piece_cells,
        contacts=tuple(_copy_contact(contact) for contact in value.contacts),
        stopping_contacts=tuple(_copy_contact(contact) for contact in value.stopping_contacts),
        causal_contacts=tuple(_copy_contact(contact) for contact in value.causal_contacts),
        pre_state=SparseAggregate(value.pre_state.width, value.pre_state.occupied),
        post_state=SparseAggregate(value.post_state.width, value.post_state.occupied),
    )


def _orientation_order(law: TetrominoEventLaw) -> tuple[str, ...]:
    return tuple(
        orientation_id
        for orientation_law in law.orientation_laws.branch_laws
        for orientation_id in orientation_law.outcome_ids
    )


def _orientation_family(law: TetrominoEventLaw) -> dict[str, str]:
    return {
        orientation_id: family_id
        for family_id, orientation_law in zip(law.orientation_laws.branch_ids, law.orientation_laws.branch_laws)
        for orientation_id in orientation_law.outcome_ids
    }


def _geometry_face_capacities(geometry: PieceGeometry) -> tuple[int, int, int, int, int]:
    cells = {(delta_x, delta_y) for delta_y, delta_x in geometry.world_coordinates}
    down = sum((x, y - 1) not in cells for x, y in cells)
    left = sum((x - 1, y) not in cells for x, y in cells)
    right = sum((x + 1, y) not in cells for x, y in cells)
    above = sum((x, y + 1) not in cells for x, y in cells)
    return down, left, right, above, down + left + right + above


def _preflight_event_law(
    *,
    width: int,
    law: TetrominoEventLaw,
) -> tuple[dict[str, int], dict[str, tuple[int, int, int, int, int]]]:
    if law.launch_law.upper_bound != width:
        raise ValueError("law launch-law upper bound must equal accumulator width")

    registry = binding_engine._ratified_geometry_by_id()
    support: list[PieceGeometry] = []
    for family_id, family_count, orientation_law in zip(
        law.family_law.outcome_ids,
        law.family_law.counts,
        law.orientation_laws.branch_laws,
    ):
        if family_count == 0:
            continue
        for orientation_id, orientation_count in zip(orientation_law.outcome_ids, orientation_law.counts):
            if orientation_count == 0:
                continue
            geometry = registry.get(orientation_id)
            if geometry is None or geometry.family_id != family_id:
                raise AssertionError("the event law is inconsistent with the ratified geometry registry")
            support.append(geometry)
    if not support:
        raise AssertionError("the event law has no positive family-by-orientation support")
    if width <= max(geometry.width for geometry in support):
        raise ValueError(
            "generic periodic laws require width greater than every positive-weight geometry bounding-box width"
        )

    pristine = tuple(_copy_geometry(geometry) for geometry in support)
    delegated = tuple(_copy_geometry(geometry) for geometry in support)
    try:
        result = validate_periodic_law(width, delegated)
    except TypeError as error:
        raise AssertionError("validate_periodic_law rejected validated accumulator inputs") from error
    if type(result) is not tuple:
        raise AssertionError("validate_periodic_law returned a non-tuple result")
    try:
        actual = tuple(_copy_geometry(geometry) for geometry in result)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("validate_periodic_law returned malformed geometry support") from error
    if actual != pristine:
        raise AssertionError("validate_periodic_law returned support inconsistent with its input")
    return (
        {orientation_id: geometry.width for orientation_id, geometry in registry.items()},
        {orientation_id: _geometry_face_capacities(geometry) for orientation_id, geometry in registry.items()},
    )


def _snapshot_state_primitives(value: object) -> ReferenceStatePrimitives:
    if type(value) is not ReferenceStatePrimitives:
        raise TypeError("measure_state must return a ReferenceStatePrimitives")
    try:
        return ReferenceStatePrimitives(
            width=value.width,
            nonzero_column_heights=value.nonzero_column_heights,
            occupied_mass=value.occupied_mass,
            height_sum=value.height_sum,
            height_square_sum=value.height_square_sum,
            below_envelope_volume=value.below_envelope_volume,
            void_count=value.void_count,
        )
    except AttributeError as error:
        raise TypeError("measure_state returned a partially initialized record") from error


def _independent_state_primitives(state: SparseAggregate) -> ReferenceStatePrimitives:
    heights: dict[int, int] = {}
    for x, y in state.occupied:
        height = y + 1
        if height > heights.get(x, 0):
            heights[x] = height
    nonzero = tuple(sorted(heights.items()))
    height_sum = sum(heights.values())
    height_square_sum = sum(height * height for height in heights.values())
    return ReferenceStatePrimitives(
        width=state.width,
        nonzero_column_heights=nonzero,
        occupied_mass=state.mass,
        height_sum=height_sum,
        height_square_sum=height_square_sum,
        below_envelope_volume=height_sum,
        void_count=height_sum - state.mass,
    )


def _measure_state_bound(state: SparseAggregate, *, label: str) -> ReferenceStatePrimitives:
    pristine = SparseAggregate(state.width, state.occupied)
    delegated = SparseAggregate(state.width, state.occupied)
    try:
        measured = _snapshot_state_primitives(measure_state(delegated))
    except (TypeError, ValueError) as error:
        raise AssertionError(f"measure_state returned malformed {label} primitives") from error
    expected = _independent_state_primitives(pristine)
    if measured != expected:
        raise AssertionError(f"measure_state returned {label} primitives inconsistent with the certified state")
    return measured


def _snapshot_placement_primitives(value: object) -> ReferencePlacementPrimitives:
    if type(value) is not ReferencePlacementPrimitives:
        raise TypeError("measure_placement must return a ReferencePlacementPrimitives")
    try:
        return ReferencePlacementPrimitives(
            width=value.width,
            contact_kind=value.contact_kind,
            placed_mass=value.placed_mass,
            early_arrest_gap=value.early_arrest_gap,
            lateral_trigger=value.lateral_trigger,
            contact_face_kinds=value.contact_face_kinds,
            contact_face_kind_counts=value.contact_face_kind_counts,
            causal_face_kind_counts=value.causal_face_kind_counts,
            causal_contact_mask=value.causal_contact_mask,
            seam_lateral_face_count=value.seam_lateral_face_count,
            contacting_piece_cells=value.contacting_piece_cells,
            contacted_aggregate_cells=value.contacted_aggregate_cells,
            contacted_support_sites=value.contacted_support_sites,
            contacted_support_columns=value.contacted_support_columns,
            support_graph_edges=value.support_graph_edges,
            support_cluster_count=value.support_cluster_count,
            support_arc_origin=value.support_arc_origin,
            support_arc_span=value.support_arc_span,
            support_column_gaps=value.support_column_gaps,
            envelope_changes=value.envelope_changes,
            height_sum_delta=value.height_sum_delta,
            height_square_sum_delta=value.height_square_sum_delta,
            void_count_delta=value.void_count_delta,
        )
    except AttributeError as error:
        raise TypeError("measure_placement returned a partially initialized record") from error


def _face_counts(contacts: tuple[ContactFace, ...]) -> tuple[tuple[ContactFaceKind, int], ...]:
    return tuple((kind, sum(contact.kind is kind for contact in contacts)) for kind in ContactFaceKind)


def _support_graph_edges(
    width: int,
    support_sites: tuple[tuple[int, int], ...],
) -> tuple[tuple[tuple[int, int], tuple[int, int]], ...]:
    site_set = set(support_sites)
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for site in support_sites:
        x, y = site
        for neighbor in (((x + 1) % width, y), (x, y + 1)):
            if neighbor in site_set:
                edges.add((site, neighbor) if site < neighbor else (neighbor, site))
    return tuple(sorted(edges))


def _support_cluster_count(
    support_sites: tuple[tuple[int, int], ...],
    support_edges: tuple[tuple[tuple[int, int], tuple[int, int]], ...],
) -> int:
    adjacency = {site: set() for site in support_sites}
    for left, right in support_edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    unseen = set(support_sites)
    components = 0
    while unseen:
        components += 1
        stack = [unseen.pop()]
        while stack:
            site = stack.pop()
            new_sites = adjacency[site].intersection(unseen)
            unseen.difference_update(new_sites)
            stack.extend(new_sites)
    return components


def _support_arc(
    width: int,
    columns: tuple[int, ...],
) -> tuple[int | None, int, tuple[int, ...]]:
    if not columns:
        return None, 0, ()
    if len(columns) == 1:
        return columns[0], 0, (width,)
    cyclic_gaps = tuple((columns[(index + 1) % len(columns)] - column) % width for index, column in enumerate(columns))
    excluded_gap = max(cyclic_gaps)
    excluded_index = min(
        (index for index, gap in enumerate(cyclic_gaps) if gap == excluded_gap),
        key=lambda index: columns[(index + 1) % len(columns)],
    )
    origin_index = (excluded_index + 1) % len(columns)
    ordered_gaps = cyclic_gaps[origin_index:] + cyclic_gaps[:origin_index]
    return columns[origin_index], width - excluded_gap, ordered_gaps


def _cross_bind_placement_primitives(
    primitives: ReferencePlacementPrimitives,
    placement: ReferencePlacement,
    pre: ReferenceStatePrimitives,
    post: ReferenceStatePrimitives,
) -> None:
    contact_face_kinds = tuple(contact.kind for contact in placement.contacts)
    causal_set = set(placement.causal_contacts)
    causal_mask = sum(1 << index for index, contact in enumerate(placement.contacts) if contact in causal_set)
    contacting_piece_cells = tuple(sorted({contact.piece_cell for contact in placement.contacts}))
    contacted_aggregate_cells = tuple(
        sorted({contact.neighbor_cell for contact in placement.contacts if contact.neighbor_cell is not None})
    )
    contacted_support_sites = tuple(
        sorted(
            {
                contact.neighbor_cell
                for contact in placement.contacts
                if contact.kind is ContactFaceKind.AGGREGATE_SUPPORT and contact.neighbor_cell is not None
            }
        )
    )
    contacted_support_columns = tuple(sorted({x for x, _ in contacted_support_sites}))
    support_graph_edges = _support_graph_edges(placement.pre_state.width, contacted_support_sites)
    support_cluster_count = _support_cluster_count(contacted_support_sites, support_graph_edges)
    support_arc_origin, support_arc_span, support_column_gaps = _support_arc(
        placement.pre_state.width, contacted_support_columns
    )
    pre_heights = dict(pre.nonzero_column_heights)
    post_heights = dict(post.nonzero_column_heights)
    envelope_changes = tuple(
        (x, pre_heights.get(x, 0), post_height)
        for x, post_height in sorted(post_heights.items())
        if post_height != pre_heights.get(x, 0)
    )
    expected_pairs = (
        (primitives.width, placement.pre_state.width),
        (primitives.contact_kind, placement.contact_kind),
        (primitives.placed_mass, post.occupied_mass - pre.occupied_mass),
        (primitives.early_arrest_gap, placement.early_arrest_gap),
        (primitives.lateral_trigger, placement.lateral_trigger),
        (primitives.contact_face_kinds, contact_face_kinds),
        (primitives.contact_face_kind_counts, _face_counts(placement.contacts)),
        (primitives.causal_face_kind_counts, _face_counts(placement.causal_contacts)),
        (primitives.causal_contact_mask, causal_mask),
        (
            primitives.seam_lateral_face_count,
            sum(
                contact.crosses_seam
                for contact in placement.contacts
                if contact.kind in (ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT)
            ),
        ),
        (primitives.contacting_piece_cells, contacting_piece_cells),
        (primitives.contacted_aggregate_cells, contacted_aggregate_cells),
        (primitives.contacted_support_sites, contacted_support_sites),
        (primitives.contacted_support_columns, contacted_support_columns),
        (primitives.support_graph_edges, support_graph_edges),
        (primitives.support_cluster_count, support_cluster_count),
        (primitives.support_arc_origin, support_arc_origin),
        (primitives.support_arc_span, support_arc_span),
        (primitives.support_column_gaps, support_column_gaps),
        (primitives.envelope_changes, envelope_changes),
        (primitives.height_sum_delta, post.height_sum - pre.height_sum),
        (primitives.height_square_sum_delta, post.height_square_sum - pre.height_square_sum),
        (primitives.void_count_delta, post.void_count - pre.void_count),
    )
    if any(actual != expected for actual, expected in expected_pairs):
        raise AssertionError("measure_placement returned primitives inconsistent with the certified placement")


def _snapshot_fixed_string_counts(
    value: object,
    *,
    expected_keys: tuple[str, ...],
    label: str,
) -> tuple[tuple[str, int], ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    result: list[tuple[str, int]] = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError(f"{label} must contain exact built-in two-tuples")
        key, count = entry
        if type(key) is not str:
            raise TypeError(f"{label} keys must be built-in strings")
        result.append((key, _require_nonnegative_int(count, label=f"{label} count")))
    if tuple(key for key, _ in result) != expected_keys:
        raise ValueError(f"{label} must contain every declared key exactly once in declared order")
    return tuple(result)


def _snapshot_face_counts(value: object, *, label: str) -> tuple[tuple[ContactFaceKind, int], ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    result: list[tuple[ContactFaceKind, int]] = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError(f"{label} must contain exact built-in two-tuples")
        key, count = entry
        if type(key) is not ContactFaceKind:
            raise TypeError(f"{label} keys must be exact ContactFaceKind values")
        result.append((key, _require_nonnegative_int(count, label=f"{label} count")))
    if tuple(key for key, _ in result) != tuple(ContactFaceKind):
        raise ValueError(f"{label} must contain every ContactFaceKind exactly once in enum order")
    return tuple(result)


def _least_cyclic_rotation(signature: tuple[int, ...]) -> tuple[int, ...]:
    if not signature:
        return ()
    return min(signature[index:] + signature[:index] for index in range(len(signature)))


def _snapshot_gap_signature(value: object, *, width: int, label: str) -> tuple[int, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    if len(value) > 4:
        raise ValueError(f"{label} must contain at most four gaps")
    signature = tuple(_require_positive_int(gap, label=f"{label} gap") for gap in value)
    if signature and sum(signature) != width:
        raise ValueError(f"{label} must sum to width when nonempty")
    if signature != _least_cyclic_rotation(signature):
        raise ValueError(f"{label} must equal its lexicographically least cyclic rotation")
    return signature


def _snapshot_nonnegative_key(value: object, *, label: str) -> int:
    return _require_nonnegative_int(value, label=label)


def _snapshot_envelope_change_key(value: object, *, width: int) -> tuple[int, int, int]:
    if type(value) is not tuple or len(value) != 3:
        raise TypeError("envelope-change keys must be exact built-in three-tuples")
    x = _require_nonnegative_int(value[0], label="envelope-change column")
    pre = _require_nonnegative_int(value[1], label="envelope-change pre-height")
    post = _require_nonnegative_int(value[2], label="envelope-change post-height")
    if x >= width:
        raise ValueError("envelope-change columns must lie in [0, width)")
    if post <= pre:
        raise ValueError("envelope changes must be strict height increases")
    return x, pre, post


def _snapshot_contact_gap_key(value: object) -> tuple[str, int, int, int]:
    if type(value) is not tuple or len(value) != 4:
        raise TypeError("contact-gap keys must be exact built-in four-tuples")
    contact_id, raw_gap, raw_void, raw_roughness = value
    if type(contact_id) is not str:
        raise TypeError("contact-gap contact IDs must be built-in strings")
    if contact_id not in _RATIFIED_CONTACT_ORDER:
        raise ValueError("contact-gap contact IDs must name a declared endpoint")
    gap = _require_nonnegative_int(raw_gap, label="contact-gap landing gap")
    void_delta = _require_int(raw_void, label="contact-gap void delta")
    roughness_delta = _require_int(raw_roughness, label="contact-gap roughness delta")
    if void_delta < -4:
        raise ValueError("a tetromino event void delta must be at least minus four")
    if contact_id == ContactKind.SUPPORTED_V1.value and gap != 0:
        raise ValueError("supported-v1 contact-gap keys must have zero landing gap")
    return contact_id, gap, void_delta, roughness_delta


def _snapshot_topology_key(
    value: object,
    *,
    width: int,
    orientations: tuple[str, ...],
    orientation_widths: dict[str, int],
) -> tuple[str, str, int, int, tuple[int, ...], int]:
    if type(value) is not tuple or len(value) != 6:
        raise TypeError("topology keys must be exact built-in six-tuples")
    orientation_id, contact_id, raw_clusters, raw_span, raw_signature, raw_columns = value
    if type(orientation_id) is not str:
        raise TypeError("topology orientation IDs must be built-in strings")
    if orientation_id not in orientations:
        raise ValueError("topology orientation IDs must be ratified")
    if type(contact_id) is not str:
        raise TypeError("topology contact IDs must be built-in strings")
    if contact_id not in _RATIFIED_CONTACT_ORDER:
        raise ValueError("topology contact IDs must name a declared endpoint")
    clusters = _require_nonnegative_int(raw_clusters, label="topology support-cluster count")
    span = _require_nonnegative_int(raw_span, label="topology support-arc span")
    columns = _require_nonnegative_int(raw_columns, label="topology support-column count")
    signature = _snapshot_gap_signature(raw_signature, width=width, label="topology gap signature")
    if columns > 4:
        raise ValueError("topology support-column count must not exceed tetromino area")
    geometry_width = orientation_widths[orientation_id]
    if columns > geometry_width:
        raise ValueError("topology support-column count must not exceed the selected geometry width")
    if span > geometry_width - 1:
        raise ValueError("topology support-arc span must not exceed the selected geometry width minus one")
    if len(signature) != columns:
        raise ValueError("topology gap-signature length must equal support-column count")
    if columns == 0:
        if clusters != 0 or span != 0 or signature:
            raise ValueError("empty support must have zero clusters, zero span, and an empty signature")
    else:
        if not 1 <= clusters <= columns:
            raise ValueError("nonempty support clusters must not exceed support columns")
        if span != width - max(signature):
            raise ValueError("support-arc span must exclude a largest cyclic gap")
    return orientation_id, contact_id, clusters, span, signature, columns


def _snapshot_count_map(
    value: object,
    *,
    label: str,
    key_snapshot,
) -> tuple[tuple[object, int], ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    result: list[tuple[object, int]] = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError(f"{label} must contain exact built-in two-tuples")
        key = key_snapshot(entry[0])
        count = _require_positive_int(entry[1], label=f"{label} count")
        result.append((key, count))
    if tuple(result) != tuple(sorted(result, key=lambda entry: entry[0])):
        raise ValueError(f"{label} must be strictly lexicographically sorted")
    keys = tuple(key for key, _ in result)
    if len(set(keys)) != len(keys):
        raise ValueError(f"{label} keys must be duplicate-free")
    return tuple(result)


def _snapshot_topology_table(
    value: object,
    *,
    width: int,
    orientations: tuple[str, ...],
    orientation_widths: dict[str, int],
) -> tuple[tuple[tuple[str, str, int, int, tuple[int, ...], int], int, int, int], ...]:
    if type(value) is not tuple:
        raise TypeError("topology_joint_counts must be a built-in tuple")
    result = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 4:
            raise TypeError("topology_joint_counts must contain exact built-in four-tuples")
        key = _snapshot_topology_key(
            entry[0],
            width=width,
            orientations=orientations,
            orientation_widths=orientation_widths,
        )
        count = _require_positive_int(entry[1], label="topology joint count")
        void_sum = _require_int(entry[2], label="topology void-delta sum")
        roughness_sum = _require_int(entry[3], label="topology roughness-delta sum")
        if void_sum < -4 * count:
            raise ValueError("a topology stratum void-delta sum must be at least minus four per event")
        result.append((key, count, void_sum, roughness_sum))
    if tuple(result) != tuple(sorted(result, key=lambda entry: entry[0])):
        raise ValueError("topology_joint_counts must be strictly lexicographically sorted")
    keys = tuple(entry[0] for entry in result)
    if len(set(keys)) != len(keys):
        raise ValueError("topology_joint_counts keys must be duplicate-free")
    return tuple(result)


def _height_histogram(primitives: ReferenceStatePrimitives) -> tuple[tuple[int, int], ...]:
    counts: dict[int, int] = {}
    zero_count = primitives.width - len(primitives.nonzero_column_heights)
    if zero_count:
        counts[0] = zero_count
    for _, height in primitives.nonzero_column_heights:
        counts[height] = counts.get(height, 0) + 1
    return tuple(sorted(counts.items()))


def _count_map_dict(value: tuple[tuple[object, int], ...]) -> dict[object, int]:
    return dict(value)


def _increment_count_map(value: tuple[tuple[object, int], ...], key: object) -> tuple[tuple[object, int], ...]:
    counts = _count_map_dict(value)
    counts[key] = counts.get(key, 0) + 1
    return tuple(sorted(counts.items()))


def _add_histogram(
    value: tuple[tuple[int, int], ...],
    histogram: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    counts = dict(value)
    for key, count in histogram:
        counts[key] = counts.get(key, 0) + count
    return tuple(sorted(counts.items()))


def _increment_fixed_string_counts(
    value: tuple[tuple[str, int], ...],
    key: str,
) -> tuple[tuple[str, int], ...]:
    return tuple((candidate, count + (candidate == key)) for candidate, count in value)


def _add_face_counts(
    value: tuple[tuple[ContactFaceKind, int], ...],
    increments: tuple[tuple[ContactFaceKind, int], ...],
) -> tuple[tuple[ContactFaceKind, int], ...]:
    return tuple(
        (kind, count + increment) for (kind, count), (other, increment) in zip(value, increments) if kind is other
    )


def _increment_topology_table(
    value: tuple[tuple[tuple[str, str, int, int, tuple[int, ...], int], int, int, int], ...],
    key: tuple[str, str, int, int, tuple[int, ...], int],
    *,
    void_delta: int,
    roughness_delta: int,
) -> tuple[tuple[tuple[str, str, int, int, tuple[int, ...], int], int, int, int], ...]:
    table = {row_key: (count, void_sum, roughness_sum) for row_key, count, void_sum, roughness_sum in value}
    count, void_sum, roughness_sum = table.get(key, (0, 0, 0))
    table[key] = (count + 1, void_sum + void_delta, roughness_sum + roughness_delta)
    return tuple(
        (row_key, count, void_sum, roughness_sum) for row_key, (count, void_sum, roughness_sum) in sorted(table.items())
    )


def _checked_next_event_count(value: object) -> int:
    event_count = _require_int(value, label="event count")
    if not 0 <= event_count <= _U64_MAX:
        raise ValueError("event count cannot advance beyond the terminal value 2**64")
    return event_count + 1


@dataclass(frozen=True, slots=True)
class ReferenceEventAccumulator:
    """Frozen structural summary of a claimed contiguous reference prefix."""

    root_seed: int
    coupling_group_id: str
    law: TetrominoEventLaw
    width: int
    event_count: int
    current_state: SparseAggregate
    occupied_mass: int
    height_sum: int
    height_square_sum: int
    below_envelope_volume: int
    void_count: int
    family_counts: tuple[tuple[str, int], ...]
    orientation_counts: tuple[tuple[str, int], ...]
    contact_counts: tuple[tuple[str, int], ...]
    contact_face_kind_counts: tuple[tuple[ContactFaceKind, int], ...]
    causal_face_kind_counts: tuple[tuple[ContactFaceKind, int], ...]
    seam_lateral_face_count: int
    contacting_piece_cell_count: int
    contacted_aggregate_cell_count: int
    contacted_support_site_count: int
    contacted_support_column_count: int
    events_with_floor_support_face: int
    events_with_aggregate_support_face: int
    landing_gap_counts: tuple[tuple[int, int], ...]
    support_cluster_counts: tuple[tuple[int, int], ...]
    support_arc_span_counts: tuple[tuple[int, int], ...]
    support_gap_signature_counts: tuple[tuple[tuple[int, ...], int], ...]
    pre_envelope_height_counts: tuple[tuple[int, int], ...]
    post_envelope_height_counts: tuple[tuple[int, int], ...]
    envelope_change_counts: tuple[tuple[tuple[int, int, int], int], ...]
    contact_gap_delta_counts: tuple[tuple[tuple[str, int, int, int], int], ...]
    topology_joint_counts: tuple[tuple[tuple[str, str, int, int, tuple[int, ...], int], int, int, int], ...]
    height_sum_delta: int
    height_square_sum_delta: int
    void_count_delta: int

    def __post_init__(self) -> None:
        root_seed = _require_uint(self.root_seed, maximum=_U128_MAX, label="root seed")
        coupling_group_id = _snapshot_text(self.coupling_group_id, label="coupling group ID")
        law = _snapshot_law(self.law)
        width = _require_nonnegative_int(self.width, label="width")
        event_count = _require_uint(self.event_count, maximum=_U64_MODULUS, label="event count")
        current_state = _snapshot_state(self.current_state, label="current_state")
        if current_state.width != width:
            raise ValueError("current_state width must equal accumulator width")
        orientation_widths, orientation_face_capacities = _preflight_event_law(width=width, law=law)
        measured = _measure_state_bound(current_state, label="current")

        occupied_mass = _require_nonnegative_int(self.occupied_mass, label="occupied_mass")
        height_sum = _require_nonnegative_int(self.height_sum, label="height_sum")
        height_square_sum = _require_nonnegative_int(self.height_square_sum, label="height_square_sum")
        below_envelope_volume = _require_nonnegative_int(self.below_envelope_volume, label="below_envelope_volume")
        void_count = _require_nonnegative_int(self.void_count, label="void_count")
        height_sum_delta = _require_nonnegative_int(self.height_sum_delta, label="height_sum_delta")
        height_square_sum_delta = _require_nonnegative_int(
            self.height_square_sum_delta, label="height_square_sum_delta"
        )
        void_count_delta = _require_int(self.void_count_delta, label="void_count_delta")

        orientations = _orientation_order(law)
        family_counts = _snapshot_fixed_string_counts(
            self.family_counts, expected_keys=_RATIFIED_FAMILY_ORDER, label="family_counts"
        )
        orientation_counts = _snapshot_fixed_string_counts(
            self.orientation_counts, expected_keys=orientations, label="orientation_counts"
        )
        contact_counts = _snapshot_fixed_string_counts(
            self.contact_counts, expected_keys=_RATIFIED_CONTACT_ORDER, label="contact_counts"
        )
        contact_face_kind_counts = _snapshot_face_counts(
            self.contact_face_kind_counts, label="contact_face_kind_counts"
        )
        causal_face_kind_counts = _snapshot_face_counts(self.causal_face_kind_counts, label="causal_face_kind_counts")

        scalar_counts = {
            "seam_lateral_face_count": _require_nonnegative_int(
                self.seam_lateral_face_count, label="seam_lateral_face_count"
            ),
            "contacting_piece_cell_count": _require_nonnegative_int(
                self.contacting_piece_cell_count, label="contacting_piece_cell_count"
            ),
            "contacted_aggregate_cell_count": _require_nonnegative_int(
                self.contacted_aggregate_cell_count, label="contacted_aggregate_cell_count"
            ),
            "contacted_support_site_count": _require_nonnegative_int(
                self.contacted_support_site_count, label="contacted_support_site_count"
            ),
            "contacted_support_column_count": _require_nonnegative_int(
                self.contacted_support_column_count, label="contacted_support_column_count"
            ),
            "events_with_floor_support_face": _require_nonnegative_int(
                self.events_with_floor_support_face, label="events_with_floor_support_face"
            ),
            "events_with_aggregate_support_face": _require_nonnegative_int(
                self.events_with_aggregate_support_face, label="events_with_aggregate_support_face"
            ),
        }

        def int_key(key: object) -> int:
            return _snapshot_nonnegative_key(key, label="sparse integer key")

        landing_gap_counts = _snapshot_count_map(
            self.landing_gap_counts, label="landing_gap_counts", key_snapshot=int_key
        )
        support_cluster_counts = _snapshot_count_map(
            self.support_cluster_counts, label="support_cluster_counts", key_snapshot=int_key
        )
        support_arc_span_counts = _snapshot_count_map(
            self.support_arc_span_counts, label="support_arc_span_counts", key_snapshot=int_key
        )
        support_gap_signature_counts = _snapshot_count_map(
            self.support_gap_signature_counts,
            label="support_gap_signature_counts",
            key_snapshot=lambda key: _snapshot_gap_signature(key, width=width, label="support gap signature"),
        )
        pre_envelope_height_counts = _snapshot_count_map(
            self.pre_envelope_height_counts, label="pre_envelope_height_counts", key_snapshot=int_key
        )
        post_envelope_height_counts = _snapshot_count_map(
            self.post_envelope_height_counts, label="post_envelope_height_counts", key_snapshot=int_key
        )
        envelope_change_counts = _snapshot_count_map(
            self.envelope_change_counts,
            label="envelope_change_counts",
            key_snapshot=lambda key: _snapshot_envelope_change_key(key, width=width),
        )
        contact_gap_delta_counts = _snapshot_count_map(
            self.contact_gap_delta_counts,
            label="contact_gap_delta_counts",
            key_snapshot=_snapshot_contact_gap_key,
        )
        topology_joint_counts = _snapshot_topology_table(
            self.topology_joint_counts,
            width=width,
            orientations=orientations,
            orientation_widths=orientation_widths,
        )

        if (
            occupied_mass,
            height_sum,
            height_square_sum,
            below_envelope_volume,
            void_count,
        ) != (
            measured.occupied_mass,
            measured.height_sum,
            measured.height_square_sum,
            measured.below_envelope_volume,
            measured.void_count,
        ):
            raise ValueError("stored state totals must equal the independently measured current state")
        if occupied_mass != 4 * event_count:
            raise ValueError("occupied_mass must equal four times event_count")
        if height_sum != occupied_mass + void_count or below_envelope_volume != height_sum:
            raise ValueError("height_sum must equal occupied_mass plus void_count and envelope volume")
        if (height_sum_delta, height_square_sum_delta, void_count_delta) != (
            height_sum,
            height_square_sum,
            void_count,
        ):
            raise ValueError("cumulative height and void deltas must telescope from the empty state")
        roughness = width * height_square_sum - height_sum * height_sum
        if roughness < 0:
            raise ValueError("the exact roughness numerator must be nonnegative")
        if (
            measured.nonzero_column_heights
            and max(height for _, height in measured.nonzero_column_heights) > 4 * event_count
        ):
            raise ValueError("current envelope height must not grow by more than four per event")

        if any(
            sum(count for _, count in counts) != event_count
            for counts in (family_counts, orientation_counts, contact_counts)
        ):
            raise ValueError("family, orientation, and contact counts must each total event_count")
        orientation_family = _orientation_family(law)
        orientation_by_family = {
            family_id: sum(
                count for orientation_id, count in orientation_counts if orientation_family[orientation_id] == family_id
            )
            for family_id in _RATIFIED_FAMILY_ORDER
        }
        if tuple((family, orientation_by_family[family]) for family in _RATIFIED_FAMILY_ORDER) != family_counts:
            raise ValueError("family counts must equal their orientation projections")
        family_law_counts = dict(zip(law.family_law.outcome_ids, law.family_law.counts))
        if any(count and family_law_counts[family] == 0 for family, count in family_counts):
            raise ValueError("zero-law family slots must remain zero")
        orientation_law_counts = {
            orientation_id: family_law_counts[family_id] * orientation_count
            for family_id, orientation_law in zip(law.orientation_laws.branch_ids, law.orientation_laws.branch_laws)
            for orientation_id, orientation_count in zip(orientation_law.outcome_ids, orientation_law.counts)
        }
        if any(count and orientation_law_counts[orientation] == 0 for orientation, count in orientation_counts):
            raise ValueError("zero-law orientation slots must remain zero")
        contact_law_counts = dict(zip(law.contact_law.outcome_ids, law.contact_law.counts))
        if any(count and contact_law_counts[contact] == 0 for contact, count in contact_counts):
            raise ValueError("zero-law contact slots must remain zero")

        final_faces = dict(contact_face_kind_counts)
        causal_faces = dict(causal_face_kind_counts)
        if any(causal_faces[kind] > final_faces[kind] for kind in ContactFaceKind):
            raise ValueError("causal face counts must not exceed final face counts")
        positive_gap_events = sum(
            count
            for (contact, gap, _, _), count in contact_gap_delta_counts
            if contact == _RATIFIED_CONTACT_ORDER[1] and gap > 0
        )
        nontrigger_events = event_count - positive_gap_events
        causal_support_total = (
            causal_faces[ContactFaceKind.FLOOR_SUPPORT] + causal_faces[ContactFaceKind.AGGREGATE_SUPPORT]
        )
        causal_lateral_total = causal_faces[ContactFaceKind.LATERAL_LEFT] + causal_faces[ContactFaceKind.LATERAL_RIGHT]
        if causal_faces[ContactFaceKind.AGGREGATE_ABOVE] != 0:
            raise ValueError("aggregate-above faces are never causal")
        if causal_faces[ContactFaceKind.FLOOR_SUPPORT] != final_faces[ContactFaceKind.FLOOR_SUPPORT]:
            raise ValueError("every final floor-support face must be causal")
        if causal_faces[ContactFaceKind.AGGREGATE_SUPPORT] != final_faces[ContactFaceKind.AGGREGATE_SUPPORT]:
            raise ValueError("every final aggregate-support face must be causal")
        if not nontrigger_events <= causal_support_total <= 4 * nontrigger_events:
            raise ValueError("causal support faces must match supported and zero-gap event multiplicity")
        if not positive_gap_events <= causal_lateral_total <= 8 * positive_gap_events:
            raise ValueError("causal lateral faces must match positive-gap edge-first event multiplicity")
        if any(
            causal_faces[kind] > 4 * positive_gap_events
            for kind in (ContactFaceKind.LATERAL_LEFT, ContactFaceKind.LATERAL_RIGHT)
        ):
            raise ValueError("each causal lateral direction must not exceed four per positive-gap event")
        final_face_total = sum(final_faces.values())
        causal_face_total = sum(causal_faces.values())
        if final_face_total < event_count or causal_face_total < event_count:
            raise ValueError("every accumulated event must contribute final and causal faces")
        down_capacity = 0
        left_capacity = 0
        right_capacity = 0
        above_capacity = 0
        perimeter_capacity = 0
        for orientation_id, count in orientation_counts:
            down, left, right, above, perimeter = orientation_face_capacities[orientation_id]
            down_capacity += down * count
            left_capacity += left * count
            right_capacity += right * count
            above_capacity += above * count
            perimeter_capacity += perimeter * count
        support_face_total = final_faces[ContactFaceKind.FLOOR_SUPPORT] + final_faces[ContactFaceKind.AGGREGATE_SUPPORT]
        if support_face_total > down_capacity:
            raise ValueError("floor and aggregate-support event faces exceed the selected geometries' down boundaries")
        if final_faces[ContactFaceKind.LATERAL_LEFT] > left_capacity:
            raise ValueError("left-lateral event faces exceed the selected geometries' left boundaries")
        if final_faces[ContactFaceKind.LATERAL_RIGHT] > right_capacity:
            raise ValueError("right-lateral event faces exceed the selected geometries' right boundaries")
        if final_faces[ContactFaceKind.AGGREGATE_ABOVE] > above_capacity:
            raise ValueError("aggregate-above event faces exceed the selected geometries' upper boundaries")
        if final_face_total > perimeter_capacity:
            raise ValueError("final event faces exceed the selected geometries' total perimeter")
        lateral_total = final_faces[ContactFaceKind.LATERAL_LEFT] + final_faces[ContactFaceKind.LATERAL_RIGHT]
        if scalar_counts["seam_lateral_face_count"] > lateral_total:
            raise ValueError("seam-lateral count must not exceed final lateral faces")
        if scalar_counts["seam_lateral_face_count"] > 4 * event_count:
            raise ValueError("seam-lateral count must not exceed four per event")
        minimum_contacting_piece_cells = max(
            event_count,
            (final_face_total + 3) // 4,
            max(final_faces.values(), default=0),
        )
        maximum_contacting_piece_cells = min(4 * event_count, final_face_total)
        if (
            not minimum_contacting_piece_cells
            <= scalar_counts["contacting_piece_cell_count"]
            <= maximum_contacting_piece_cells
        ):
            raise ValueError("contacting piece-cell multiplicity is inconsistent with final faces")
        nonfloor_faces = final_face_total - final_faces[ContactFaceKind.FLOOR_SUPPORT]
        minimum_contacted_aggregate_cells = max(
            (nonfloor_faces + 3) // 4,
            max(final_faces[kind] for kind in ContactFaceKind if kind is not ContactFaceKind.FLOOR_SUPPORT),
            scalar_counts["contacted_support_site_count"],
        )
        if not minimum_contacted_aggregate_cells <= scalar_counts["contacted_aggregate_cell_count"] <= nonfloor_faces:
            raise ValueError("contacted aggregate-cell multiplicity is inconsistent with nonfloor faces")
        if scalar_counts["contacted_support_site_count"] != final_faces[ContactFaceKind.AGGREGATE_SUPPORT]:
            raise ValueError("contacted support sites must equal aggregate-support face multiplicity")
        if scalar_counts["contacted_support_column_count"] != scalar_counts["contacted_support_site_count"]:
            raise ValueError("ratified tetromino support sites and support columns must have equal multiplicity")
        for flag_name, kind in (
            ("events_with_floor_support_face", ContactFaceKind.FLOOR_SUPPORT),
            ("events_with_aggregate_support_face", ContactFaceKind.AGGREGATE_SUPPORT),
        ):
            face_count = final_faces[kind]
            minimum_events = (face_count + 3) // 4
            maximum_events = min(event_count, face_count)
            if not minimum_events <= scalar_counts[flag_name] <= maximum_events:
                raise ValueError(f"{flag_name} is inconsistent with its face multiplicity")
            if scalar_counts[flag_name] > nontrigger_events:
                raise ValueError(f"{flag_name} cannot include positive-gap edge-first events")
        if (
            scalar_counts["events_with_floor_support_face"] + scalar_counts["events_with_aggregate_support_face"]
            < nontrigger_events
        ):
            raise ValueError("floor and aggregate-support event flags must cover every nontrigger event")

        ordinary_maps = (
            landing_gap_counts,
            support_cluster_counts,
            support_arc_span_counts,
            support_gap_signature_counts,
            contact_gap_delta_counts,
        )
        if any(sum(count for _, count in counts) != event_count for counts in ordinary_maps):
            raise ValueError("event-level sparse maps must each total event_count")
        if sum(count for _, count, _, _ in topology_joint_counts) != event_count:
            raise ValueError("topology_joint_counts must total event_count")

        contact_gap_contact = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        contact_gap_landing: dict[int, int] = {}
        contact_gap_void = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        contact_gap_roughness = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        for (contact, gap, void_delta, roughness_delta), count in contact_gap_delta_counts:
            contact_gap_contact[contact] += count
            contact_gap_landing[gap] = contact_gap_landing.get(gap, 0) + count
            contact_gap_void[contact] += void_delta * count
            contact_gap_roughness[contact] += roughness_delta * count
        if tuple(sorted(contact_gap_landing.items())) != landing_gap_counts:
            raise ValueError("contact-gap landing projection must equal landing_gap_counts")
        if tuple((contact, contact_gap_contact[contact]) for contact in _RATIFIED_CONTACT_ORDER) != contact_counts:
            raise ValueError("contact-gap endpoint projection must equal contact_counts")

        topology_contact = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        topology_orientation = {orientation: 0 for orientation in orientations}
        topology_clusters: dict[int, int] = {}
        topology_spans: dict[int, int] = {}
        topology_signatures: dict[tuple[int, ...], int] = {}
        topology_void = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        topology_roughness = {contact: 0 for contact in _RATIFIED_CONTACT_ORDER}
        topology_columns = 0
        topology_events_with_aggregate_support = 0
        for key, count, void_sum, roughness_sum in topology_joint_counts:
            orientation, contact, clusters, span, signature, columns = key
            topology_contact[contact] += count
            topology_orientation[orientation] += count
            topology_clusters[clusters] = topology_clusters.get(clusters, 0) + count
            topology_spans[span] = topology_spans.get(span, 0) + count
            topology_signatures[signature] = topology_signatures.get(signature, 0) + count
            topology_void[contact] += void_sum
            topology_roughness[contact] += roughness_sum
            topology_columns += columns * count
            if columns > 0:
                topology_events_with_aggregate_support += count
        if tuple((contact, topology_contact[contact]) for contact in _RATIFIED_CONTACT_ORDER) != contact_counts:
            raise ValueError("topology endpoint projection must equal contact_counts")
        if (
            tuple((orientation, topology_orientation[orientation]) for orientation in orientations)
            != orientation_counts
        ):
            raise ValueError("topology orientation projection must equal orientation_counts")
        if tuple(sorted(topology_clusters.items())) != support_cluster_counts:
            raise ValueError("topology cluster projection must equal support_cluster_counts")
        if tuple(sorted(topology_spans.items())) != support_arc_span_counts:
            raise ValueError("topology span projection must equal support_arc_span_counts")
        if tuple(sorted(topology_signatures.items())) != support_gap_signature_counts:
            raise ValueError("topology signature projection must equal support_gap_signature_counts")
        if topology_columns != scalar_counts["contacted_support_column_count"]:
            raise ValueError("topology support-column projection must equal its cumulative multiplicity")
        if topology_events_with_aggregate_support != scalar_counts["events_with_aggregate_support_face"]:
            raise ValueError("positive-support topology strata must equal the aggregate-support event count")
        if topology_void != contact_gap_void or topology_roughness != contact_gap_roughness:
            raise ValueError("joint tables must agree per endpoint on signed delta sums")
        if sum(contact_gap_void.values()) != void_count_delta:
            raise ValueError("joint void deltas must sum to cumulative void_count_delta")
        if sum(contact_gap_roughness.values()) != roughness:
            raise ValueError("joint roughness deltas must sum to the current roughness numerator")

        if sum(count for _, count in pre_envelope_height_counts) != width * event_count:
            raise ValueError("pre-event whole-envelope histograms must total width times event_count")
        if sum(count for _, count in post_envelope_height_counts) != width * event_count:
            raise ValueError("post-event whole-envelope histograms must total width times event_count")
        if event_count:
            maximum_pre_height = 4 * (event_count - 1)
            maximum_post_height = 4 * event_count
            if pre_envelope_height_counts[-1][0] > maximum_pre_height:
                raise ValueError("pre-event envelope heights must not exceed four times the prior event count")
            if post_envelope_height_counts[-1][0] > maximum_post_height:
                raise ValueError("post-event envelope heights must not exceed four times event_count")
            if len(pre_envelope_height_counts) > maximum_pre_height + 1:
                raise ValueError("pre-event envelope histogram has too many distinct integer heights")
            if len(post_envelope_height_counts) > maximum_post_height + 1:
                raise ValueError("post-event envelope histogram has too many distinct integer heights")
            if landing_gap_counts[-1][0] > pre_envelope_height_counts[-1][0]:
                raise ValueError("landing gaps must not exceed the maximum observed pre-event envelope height")
        pre_hist = dict(pre_envelope_height_counts)
        post_hist = dict(post_envelope_height_counts)
        current_hist = dict(_height_histogram(measured))
        initial_hist = {0: width}
        for height in set(pre_hist) | set(post_hist) | set(current_hist) | {0}:
            if post_hist.get(height, 0) - pre_hist.get(height, 0) != current_hist.get(height, 0) - initial_hist.get(
                height, 0
            ):
                raise ValueError("whole-envelope histograms must telescope from the all-zero initial envelope")

        total_changes = sum(count for _, count in envelope_change_counts)
        if total_changes > 4 * event_count:
            raise ValueError("the envelope-change table may contain at most four changes per event")
        if event_count and any(
            pre > 4 * (event_count - 1) or post > 4 * event_count for (_, pre, post), _ in envelope_change_counts
        ):
            raise ValueError("envelope-change heights must respect four-cell per-event growth")
        if sum((post - pre) * count for (_, pre, post), count in envelope_change_counts) != height_sum_delta:
            raise ValueError("envelope changes must project to cumulative height_sum_delta")
        if (
            sum((post * post - pre * pre) * count for (_, pre, post), count in envelope_change_counts)
            != height_square_sum_delta
        ):
            raise ValueError("envelope changes must project to cumulative height_square_sum_delta")
        flow: dict[tuple[int, int], int] = {}
        for (x, pre, post), count in envelope_change_counts:
            flow[(x, pre)] = flow.get((x, pre), 0) - count
            flow[(x, post)] = flow.get((x, post), 0) + count
        flow = {key: count for key, count in flow.items() if count}
        expected_flow: dict[tuple[int, int], int] = {}
        for x, height in measured.nonzero_column_heights:
            expected_flow[(x, 0)] = -1
            expected_flow[(x, height)] = expected_flow.get((x, height), 0) + 1
        expected_flow = {key: count for key, count in expected_flow.items() if count}
        if flow != expected_flow:
            raise ValueError("envelope changes must have exact per-column zero-to-current flow")

        object.__setattr__(self, "root_seed", root_seed)
        object.__setattr__(self, "coupling_group_id", coupling_group_id)
        object.__setattr__(self, "law", law)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "event_count", event_count)
        object.__setattr__(self, "current_state", current_state)
        object.__setattr__(self, "family_counts", family_counts)
        object.__setattr__(self, "orientation_counts", orientation_counts)
        object.__setattr__(self, "contact_counts", contact_counts)
        object.__setattr__(self, "contact_face_kind_counts", contact_face_kind_counts)
        object.__setattr__(self, "causal_face_kind_counts", causal_face_kind_counts)
        for name, value in scalar_counts.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "landing_gap_counts", landing_gap_counts)
        object.__setattr__(self, "support_cluster_counts", support_cluster_counts)
        object.__setattr__(self, "support_arc_span_counts", support_arc_span_counts)
        object.__setattr__(self, "support_gap_signature_counts", support_gap_signature_counts)
        object.__setattr__(self, "pre_envelope_height_counts", pre_envelope_height_counts)
        object.__setattr__(self, "post_envelope_height_counts", post_envelope_height_counts)
        object.__setattr__(self, "envelope_change_counts", envelope_change_counts)
        object.__setattr__(self, "contact_gap_delta_counts", contact_gap_delta_counts)
        object.__setattr__(self, "topology_joint_counts", topology_joint_counts)


def _snapshot_accumulator(value: object) -> ReferenceEventAccumulator:
    if type(value) is not ReferenceEventAccumulator:
        raise TypeError("accumulator must be a ReferenceEventAccumulator")
    try:
        return ReferenceEventAccumulator(
            root_seed=value.root_seed,
            coupling_group_id=value.coupling_group_id,
            law=value.law,
            width=value.width,
            event_count=value.event_count,
            current_state=value.current_state,
            occupied_mass=value.occupied_mass,
            height_sum=value.height_sum,
            height_square_sum=value.height_square_sum,
            below_envelope_volume=value.below_envelope_volume,
            void_count=value.void_count,
            family_counts=value.family_counts,
            orientation_counts=value.orientation_counts,
            contact_counts=value.contact_counts,
            contact_face_kind_counts=value.contact_face_kind_counts,
            causal_face_kind_counts=value.causal_face_kind_counts,
            seam_lateral_face_count=value.seam_lateral_face_count,
            contacting_piece_cell_count=value.contacting_piece_cell_count,
            contacted_aggregate_cell_count=value.contacted_aggregate_cell_count,
            contacted_support_site_count=value.contacted_support_site_count,
            contacted_support_column_count=value.contacted_support_column_count,
            events_with_floor_support_face=value.events_with_floor_support_face,
            events_with_aggregate_support_face=value.events_with_aggregate_support_face,
            landing_gap_counts=value.landing_gap_counts,
            support_cluster_counts=value.support_cluster_counts,
            support_arc_span_counts=value.support_arc_span_counts,
            support_gap_signature_counts=value.support_gap_signature_counts,
            pre_envelope_height_counts=value.pre_envelope_height_counts,
            post_envelope_height_counts=value.post_envelope_height_counts,
            envelope_change_counts=value.envelope_change_counts,
            contact_gap_delta_counts=value.contact_gap_delta_counts,
            topology_joint_counts=value.topology_joint_counts,
            height_sum_delta=value.height_sum_delta,
            height_square_sum_delta=value.height_square_sum_delta,
            void_count_delta=value.void_count_delta,
        )
    except AttributeError as error:
        raise TypeError("accumulator must be fully initialized") from error


def start_event_accumulator(
    *,
    empty_state: SparseAggregate,
    root_seed: int,
    coupling_group_id: str,
    law: TetrominoEventLaw,
) -> ReferenceEventAccumulator:
    """Start an exact structural accumulator at the canonical empty state."""

    state = _snapshot_state(empty_state, label="empty_state")
    root = _require_uint(root_seed, maximum=_U128_MAX, label="root seed")
    group = _snapshot_text(coupling_group_id, label="coupling group ID")
    event_law = _snapshot_law(law)
    if state.occupied:
        raise ValueError("empty_state must be the canonical empty aggregate")
    _preflight_event_law(width=state.width, law=event_law)
    empty_measurement = _measure_state_bound(state, label="empty")
    if any(
        (
            empty_measurement.occupied_mass,
            empty_measurement.height_sum,
            empty_measurement.height_square_sum,
            empty_measurement.below_envelope_volume,
            empty_measurement.void_count,
        )
    ):
        raise AssertionError("the canonical empty state must have zero exact primitives")
    zeros_by_family = tuple((family, 0) for family in _RATIFIED_FAMILY_ORDER)
    zeros_by_orientation = tuple((orientation, 0) for orientation in _orientation_order(event_law))
    zeros_by_contact = tuple((contact, 0) for contact in _RATIFIED_CONTACT_ORDER)
    zeros_by_face = tuple((kind, 0) for kind in ContactFaceKind)
    return ReferenceEventAccumulator(
        root_seed=root,
        coupling_group_id=group,
        law=event_law,
        width=state.width,
        event_count=0,
        current_state=state,
        occupied_mass=0,
        height_sum=0,
        height_square_sum=0,
        below_envelope_volume=0,
        void_count=0,
        family_counts=zeros_by_family,
        orientation_counts=zeros_by_orientation,
        contact_counts=zeros_by_contact,
        contact_face_kind_counts=zeros_by_face,
        causal_face_kind_counts=zeros_by_face,
        seam_lateral_face_count=0,
        contacting_piece_cell_count=0,
        contacted_aggregate_cell_count=0,
        contacted_support_site_count=0,
        contacted_support_column_count=0,
        events_with_floor_support_face=0,
        events_with_aggregate_support_face=0,
        landing_gap_counts=(),
        support_cluster_counts=(),
        support_arc_span_counts=(),
        support_gap_signature_counts=(),
        pre_envelope_height_counts=(),
        post_envelope_height_counts=(),
        envelope_change_counts=(),
        contact_gap_delta_counts=(),
        topology_joint_counts=(),
        height_sum_delta=0,
        height_square_sum_delta=0,
        void_count_delta=0,
    )


def accumulate_event(
    *,
    accumulator: ReferenceEventAccumulator,
    event: ReferenceEventPlacement,
) -> ReferenceEventAccumulator:
    """Fold one already-bound event into a structurally recertified summary."""

    current = _snapshot_accumulator(accumulator)
    event_authority = _snapshot_event(event)
    next_event_count = _checked_next_event_count(current.event_count)
    selection = event_authority.selection
    placement = event_authority.placement
    if selection.root_seed != current.root_seed:
        raise ValueError("event root seed must equal accumulator root seed")
    if selection.coupling_group_id != current.coupling_group_id:
        raise ValueError("event coupling group must equal accumulator coupling group")
    if selection.law != current.law:
        raise ValueError("event law must equal accumulator law")
    if placement.pre_state.width != current.width or placement.post_state.width != current.width:
        raise ValueError("event width must equal accumulator width")
    if selection.event_ordinal != current.event_count:
        raise ValueError("event ordinal must equal accumulator event_count")
    if placement.pre_state != current.current_state:
        raise ValueError("event pre_state must equal accumulator current_state")

    pre = _measure_state_bound(placement.pre_state, label="event pre-state")
    post = _measure_state_bound(placement.post_state, label="event post-state")
    delegated_placement = _copy_placement(placement)
    try:
        primitives = _snapshot_placement_primitives(measure_placement(delegated_placement))
    except (TypeError, ValueError) as error:
        raise AssertionError("measure_placement returned malformed primitives") from error
    _cross_bind_placement_primitives(primitives, placement, pre, post)
    if (
        pre.occupied_mass != current.occupied_mass
        or pre.height_sum != current.height_sum
        or pre.height_square_sum != current.height_square_sum
        or pre.void_count != current.void_count
    ):
        raise ValueError("event pre-state measurements must equal accumulator totals")
    if primitives.placed_mass != 4:
        raise ValueError("a tetromino event must place exactly four occupied cells")
    if (
        current.occupied_mass + primitives.placed_mass,
        current.height_sum + primitives.height_sum_delta,
        current.height_square_sum + primitives.height_square_sum_delta,
        current.void_count + primitives.void_count_delta,
    ) != (post.occupied_mass, post.height_sum, post.height_square_sum, post.void_count):
        raise ValueError("event state primitives must telescope exactly")

    roughness_delta = current.width * primitives.height_square_sum_delta - (
        (current.height_sum + primitives.height_sum_delta) ** 2 - current.height_sum**2
    )
    contact_id = selection.contact_id
    if primitives.contact_kind is not _CONTACT_KIND_BY_ID[contact_id]:
        raise AssertionError("measured contact endpoint is inconsistent with the bound selection")
    signature = _least_cyclic_rotation(primitives.support_column_gaps)
    contact_gap_key = (
        contact_id,
        primitives.early_arrest_gap,
        primitives.void_count_delta,
        roughness_delta,
    )
    topology_key = (
        selection.geometry_id,
        contact_id,
        primitives.support_cluster_count,
        primitives.support_arc_span,
        signature,
        primitives.contacted_support_column_count,
    )
    pre_histogram = _height_histogram(pre)
    post_histogram = _height_histogram(post)
    envelope_change_counts = current.envelope_change_counts
    for change in primitives.envelope_changes:
        envelope_change_counts = _increment_count_map(envelope_change_counts, change)

    final_face_counts = dict(primitives.contact_face_kind_counts)
    return ReferenceEventAccumulator(
        root_seed=current.root_seed,
        coupling_group_id=current.coupling_group_id,
        law=current.law,
        width=current.width,
        event_count=next_event_count,
        current_state=placement.post_state,
        occupied_mass=post.occupied_mass,
        height_sum=post.height_sum,
        height_square_sum=post.height_square_sum,
        below_envelope_volume=post.below_envelope_volume,
        void_count=post.void_count,
        family_counts=_increment_fixed_string_counts(current.family_counts, selection.family_id),
        orientation_counts=_increment_fixed_string_counts(current.orientation_counts, selection.geometry_id),
        contact_counts=_increment_fixed_string_counts(current.contact_counts, contact_id),
        contact_face_kind_counts=_add_face_counts(
            current.contact_face_kind_counts, primitives.contact_face_kind_counts
        ),
        causal_face_kind_counts=_add_face_counts(current.causal_face_kind_counts, primitives.causal_face_kind_counts),
        seam_lateral_face_count=current.seam_lateral_face_count + primitives.seam_lateral_face_count,
        contacting_piece_cell_count=current.contacting_piece_cell_count + primitives.contacting_piece_cell_count,
        contacted_aggregate_cell_count=current.contacted_aggregate_cell_count
        + primitives.contacted_aggregate_cell_count,
        contacted_support_site_count=current.contacted_support_site_count + primitives.contacted_support_site_count,
        contacted_support_column_count=current.contacted_support_column_count
        + primitives.contacted_support_column_count,
        events_with_floor_support_face=current.events_with_floor_support_face
        + (final_face_counts[ContactFaceKind.FLOOR_SUPPORT] > 0),
        events_with_aggregate_support_face=current.events_with_aggregate_support_face
        + (final_face_counts[ContactFaceKind.AGGREGATE_SUPPORT] > 0),
        landing_gap_counts=_increment_count_map(current.landing_gap_counts, primitives.early_arrest_gap),
        support_cluster_counts=_increment_count_map(current.support_cluster_counts, primitives.support_cluster_count),
        support_arc_span_counts=_increment_count_map(current.support_arc_span_counts, primitives.support_arc_span),
        support_gap_signature_counts=_increment_count_map(current.support_gap_signature_counts, signature),
        pre_envelope_height_counts=_add_histogram(current.pre_envelope_height_counts, pre_histogram),
        post_envelope_height_counts=_add_histogram(current.post_envelope_height_counts, post_histogram),
        envelope_change_counts=envelope_change_counts,
        contact_gap_delta_counts=_increment_count_map(current.contact_gap_delta_counts, contact_gap_key),
        topology_joint_counts=_increment_topology_table(
            current.topology_joint_counts,
            topology_key,
            void_delta=primitives.void_count_delta,
            roughness_delta=roughness_delta,
        ),
        height_sum_delta=current.height_sum_delta + primitives.height_sum_delta,
        height_square_sum_delta=current.height_square_sum_delta + primitives.height_square_sum_delta,
        void_count_delta=current.void_count_delta + primitives.void_count_delta,
    )
