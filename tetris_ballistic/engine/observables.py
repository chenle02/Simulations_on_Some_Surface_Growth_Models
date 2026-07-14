"""Pure exact primitives for sparse states and certified placements.

This explicit-only M1.2/S2 surface measures either one immutable
:class:`~tetris_ballistic.engine.state.SparseAggregate` or one already-created
:class:`~tetris_ballistic.engine.reference.ReferencePlacement` certificate.
It performs no RNG, event selection, placement call, selection-to-placement
composition, configuration execution, checkpoint I/O, canonical serialization
or persistence API, trajectory, or production routing.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import ContactKind
from .reference import ContactFace, ContactFaceKind, ReferencePlacement
from .state import SparseAggregate, WorldCell

__all__ = [
    "ReferenceStatePrimitives",
    "measure_state",
    "ReferencePlacementPrimitives",
    "measure_placement",
]

FaceKindCounts = tuple[tuple[ContactFaceKind, int], ...]
SupportGraphEdge = tuple[WorldCell, WorldCell]
EnvelopeChange = tuple[int, int, int]

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
_LATERAL_FACE_KINDS = frozenset(
    {
        ContactFaceKind.LATERAL_LEFT,
        ContactFaceKind.LATERAL_RIGHT,
    }
)


def _require_nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a nonnegative built-in integer")
    return value


def _require_positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{label} must be a positive built-in integer")
    return value


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _snapshot_state(value: object) -> SparseAggregate:
    if type(value) is not SparseAggregate:
        raise TypeError("state must be a SparseAggregate")
    try:
        return SparseAggregate(width=value.width, occupied=value.occupied)
    except AttributeError as error:
        raise TypeError("state must be fully initialized") from error


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


def _face_kind_counts(contacts: tuple[ContactFace, ...]) -> FaceKindCounts:
    return tuple((kind, sum(contact.kind is kind for contact in contacts)) for kind in ContactFaceKind)


def _validate_face_kind_counts(value: object, *, label: str) -> FaceKindCounts:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    normalized: list[tuple[ContactFaceKind, int]] = []
    for entry in value:
        if type(entry) is not tuple or len(entry) != 2:
            raise TypeError(f"{label} must contain built-in (ContactFaceKind, count) tuples")
        kind, count = entry
        if type(kind) is not ContactFaceKind:
            raise TypeError(f"{label} kinds must be ContactFaceKind values")
        normalized.append((kind, _require_nonnegative_int(count, label=f"{label} count")))
    if tuple(kind for kind, _ in normalized) != tuple(ContactFaceKind):
        raise ValueError(f"{label} must contain every ContactFaceKind exactly once in enum order")
    return tuple(normalized)


def _validate_world_cells(value: object, *, width: int, label: str) -> tuple[WorldCell, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    normalized: list[WorldCell] = []
    for cell in value:
        if type(cell) is not tuple or len(cell) != 2:
            raise TypeError(f"{label} must contain built-in integer (x, y) tuples")
        x, y = cell
        if type(x) is not int or type(y) is not int:
            raise TypeError(f"{label} must contain built-in integer (x, y) tuples")
        if not 0 <= x < width or y < 0:
            raise ValueError(f"{label} cells must lie in the nonnegative periodic lattice")
        normalized.append((x, y))
    if tuple(normalized) != tuple(sorted(set(normalized))):
        raise ValueError(f"{label} must be unique and canonically sorted")
    return tuple(normalized)


def _support_graph_edges(
    width: int,
    support_sites: tuple[WorldCell, ...],
) -> tuple[SupportGraphEdge, ...]:
    site_set = set(support_sites)
    edges: set[SupportGraphEdge] = set()
    for site in support_sites:
        x, y = site
        for neighbor in (((x + 1) % width, y), (x, y + 1)):
            if neighbor in site_set:
                edges.add((site, neighbor) if site < neighbor else (neighbor, site))
    return tuple(sorted(edges))


def _support_cluster_count(
    support_sites: tuple[WorldCell, ...],
    support_edges: tuple[SupportGraphEdge, ...],
) -> int:
    adjacency = {site: set() for site in support_sites}
    for left, right in support_edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    unseen = set(support_sites)
    component_count = 0
    while unseen:
        component_count += 1
        stack = [unseen.pop()]
        while stack:
            site = stack.pop()
            new_sites = adjacency[site].intersection(unseen)
            unseen.difference_update(new_sites)
            stack.extend(new_sites)
    return component_count


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


def _column_heights(state: SparseAggregate) -> dict[int, int]:
    heights: dict[int, int] = {}
    for x, y in state.occupied:
        height = y + 1
        if height > heights.get(x, 0):
            heights[x] = height
    return heights


@dataclass(frozen=True, slots=True)
class ReferenceStatePrimitives:
    """Frozen exact state primitives for one sparse aggregate.

    ``nonzero_column_heights`` is the canonically sorted sparse representation
    of the complete interface envelope: omitted columns have height zero, and
    each stored height is one plus that column's maximum occupied ``y``.
    ``below_envelope_volume`` is therefore exactly ``height_sum`` and
    ``void_count`` is the difference between that volume and
    ``occupied_mass``.  No floating porosity or roughness summary is stored
    here.
    """

    width: int
    nonzero_column_heights: tuple[tuple[int, int], ...]
    occupied_mass: int
    height_sum: int
    height_square_sum: int
    below_envelope_volume: int
    void_count: int

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 3:
            raise ValueError("width must be a built-in integer at least 3")
        if type(self.nonzero_column_heights) is not tuple:
            raise TypeError("nonzero_column_heights must be a built-in tuple")
        normalized_heights: list[tuple[int, int]] = []
        for entry in self.nonzero_column_heights:
            if type(entry) is not tuple or len(entry) != 2:
                raise TypeError("nonzero_column_heights must contain built-in (x, height) tuples")
            x, height = entry
            if type(x) is not int or not 0 <= x < self.width:
                raise ValueError("nonzero envelope columns must be built-in integers in [0, width)")
            if type(height) is not int or height <= 0:
                raise ValueError("nonzero envelope heights must be positive built-in integers")
            normalized_heights.append((x, height))
        if tuple(normalized_heights) != tuple(sorted(normalized_heights)):
            raise ValueError("nonzero_column_heights must be sorted by column")
        columns = tuple(x for x, _ in normalized_heights)
        if len(set(columns)) != len(columns):
            raise ValueError("nonzero_column_heights must contain unique columns")

        occupied_mass = _require_nonnegative_int(self.occupied_mass, label="occupied_mass")
        height_sum = _require_nonnegative_int(self.height_sum, label="height_sum")
        height_square_sum = _require_nonnegative_int(self.height_square_sum, label="height_square_sum")
        below_envelope_volume = _require_nonnegative_int(
            self.below_envelope_volume,
            label="below_envelope_volume",
        )
        void_count = _require_nonnegative_int(self.void_count, label="void_count")

        expected_height_sum = sum(height for _, height in normalized_heights)
        if height_sum != expected_height_sum:
            raise ValueError("height_sum must equal the sum of nonzero envelope heights")
        expected_height_square_sum = sum(height * height for _, height in normalized_heights)
        if height_square_sum != expected_height_square_sum:
            raise ValueError("height_square_sum must equal the sum of squared interface heights")
        if below_envelope_volume != height_sum:
            raise ValueError("below_envelope_volume must equal height_sum")
        if len(normalized_heights) > occupied_mass:
            raise ValueError("the number of nonzero columns must not exceed occupied_mass")
        if occupied_mass > below_envelope_volume:
            raise ValueError("occupied_mass must not exceed below_envelope_volume")
        if void_count != below_envelope_volume - occupied_mass:
            raise ValueError("void_count must equal below_envelope_volume minus occupied_mass")


def measure_state(state: SparseAggregate) -> ReferenceStatePrimitives:
    """Return exact primitives for one defensively reconstructed sparse state.

    For occupied mass ``m`` and ``k`` occupied columns, expected container work
    is ``O(m + k log k)`` and peak snapshot/auxiliary memory is ``O(m + k)``.
    The implementation does not iterate or allocate in proportion to the
    numerical magnitude of substrate width or maximum occupied height.  It
    defines no canonical serialization, digest identity, or persistence API.
    """

    snapshot = _snapshot_state(state)
    nonzero_heights: dict[int, int] = {}
    for x, y in snapshot.occupied:
        height = y + 1
        if height > nonzero_heights.get(x, 0):
            nonzero_heights[x] = height
    nonzero_column_heights = tuple(sorted(nonzero_heights.items()))
    occupied_mass = snapshot.mass
    height_sum = sum(nonzero_heights.values())
    height_square_sum = sum(height * height for height in nonzero_heights.values())
    below_envelope_volume = height_sum
    void_count = below_envelope_volume - occupied_mass
    return ReferenceStatePrimitives(
        width=snapshot.width,
        nonzero_column_heights=nonzero_column_heights,
        occupied_mass=occupied_mass,
        height_sum=height_sum,
        height_square_sum=height_square_sum,
        below_envelope_volume=below_envelope_volume,
        void_count=void_count,
    )


@dataclass(frozen=True, slots=True)
class ReferencePlacementPrimitives:
    """Exact derived primitives companion to one placement certificate.

    The contact masks use the canonical ``ReferencePlacement.contacts`` order:
    bit ``i`` is set precisely when that final face is counterfactually causal.
    ``contact_face_kinds`` retains the kind at every canonical position so the
    mask remains exactly self-validating without duplicating full face records.
    ``support_graph_edges`` is the canonical undirected edge set of the graph
    induced by ``contacted_support_sites`` under periodic-horizontal and
    ordinary-vertical N4 adjacency.

    ``envelope_changes`` stores only strict sparse changes as
    ``(x, pre_height, post_height)``.  The source placement remains the
    authority for geometry, anchor, landing heights, complete face records,
    and pre/post states; this companion is not a persisted event schema.
    """

    width: int
    contact_kind: ContactKind
    placed_mass: int
    early_arrest_gap: int
    lateral_trigger: bool
    contact_face_kinds: tuple[ContactFaceKind, ...]
    contact_face_kind_counts: FaceKindCounts
    causal_face_kind_counts: FaceKindCounts
    causal_contact_mask: int
    seam_lateral_face_count: int
    contacting_piece_cells: tuple[WorldCell, ...]
    contacted_aggregate_cells: tuple[WorldCell, ...]
    contacted_support_sites: tuple[WorldCell, ...]
    contacted_support_columns: tuple[int, ...]
    support_graph_edges: tuple[SupportGraphEdge, ...]
    support_cluster_count: int
    support_arc_origin: int | None
    support_arc_span: int
    support_column_gaps: tuple[int, ...]
    envelope_changes: tuple[EnvelopeChange, ...]
    height_sum_delta: int
    height_square_sum_delta: int
    void_count_delta: int

    def __post_init__(self) -> None:
        if type(self.width) is not int or self.width < 3:
            raise ValueError("width must be a built-in integer at least 3")
        if type(self.contact_kind) is not ContactKind or self.contact_kind not in _EXECUTABLE_CONTACT_KINDS:
            raise ValueError("contact_kind must be supported-v1 or edge-first-contact-v1")
        placed_mass = _require_positive_int(self.placed_mass, label="placed_mass")
        gap = _require_nonnegative_int(self.early_arrest_gap, label="early_arrest_gap")
        if type(self.lateral_trigger) is not bool:
            raise TypeError("lateral_trigger must be a built-in bool")
        expected_lateral_trigger = self.contact_kind is ContactKind.EDGE_FIRST_CONTACT_V1 and gap > 0
        if self.lateral_trigger is not expected_lateral_trigger:
            raise ValueError("lateral_trigger must mean an edge-first placement with positive gap")
        if self.contact_kind is ContactKind.SUPPORTED_V1 and gap != 0:
            raise ValueError("supported-v1 must have zero early_arrest_gap")

        if type(self.contact_face_kinds) is not tuple:
            raise TypeError("contact_face_kinds must be a built-in tuple")
        if not self.contact_face_kinds or any(type(kind) is not ContactFaceKind for kind in self.contact_face_kinds):
            raise TypeError("contact_face_kinds must contain ContactFaceKind values")

        contact_counts = _validate_face_kind_counts(
            self.contact_face_kind_counts,
            label="contact_face_kind_counts",
        )
        causal_counts = _validate_face_kind_counts(
            self.causal_face_kind_counts,
            label="causal_face_kind_counts",
        )
        contact_count_by_kind = dict(contact_counts)
        causal_count_by_kind = dict(causal_counts)
        contact_face_count = sum(contact_count_by_kind.values())
        causal_face_count = sum(causal_count_by_kind.values())
        expected_contact_counts = tuple(
            (kind, sum(face_kind is kind for face_kind in self.contact_face_kinds)) for kind in ContactFaceKind
        )
        if contact_counts != expected_contact_counts:
            raise ValueError("contact_face_kind_counts must count the canonical contact_face_kinds sequence")
        if contact_face_count == 0:
            raise ValueError("contact_face_kind_counts must describe at least one final face")
        if causal_face_count == 0:
            raise ValueError("causal_face_kind_counts must describe at least one causal face")
        if any(causal_count_by_kind[kind] > contact_count_by_kind[kind] for kind in ContactFaceKind):
            raise ValueError("causal face counts must not exceed final face counts")

        causal_kinds = _LATERAL_FACE_KINDS if self.lateral_trigger else _SUPPORT_FACE_KINDS
        for kind in ContactFaceKind:
            expected_count = contact_count_by_kind[kind] if kind in causal_kinds else 0
            if causal_count_by_kind[kind] != expected_count:
                raise ValueError("causal face counts must match the contact rule and early-arrest gap")

        causal_mask = _require_nonnegative_int(self.causal_contact_mask, label="causal_contact_mask")
        if causal_mask >> contact_face_count:
            raise ValueError("causal_contact_mask must not set bits above the final contact tuple")
        if causal_mask.bit_count() != causal_face_count:
            raise ValueError("causal_contact_mask population must equal the causal face count")
        expected_causal_mask = sum(
            1 << index for index, kind in enumerate(self.contact_face_kinds) if kind in causal_kinds
        )
        if causal_mask != expected_causal_mask:
            raise ValueError("causal_contact_mask must select exactly the causal contact kinds")
        seam_count = _require_nonnegative_int(
            self.seam_lateral_face_count,
            label="seam_lateral_face_count",
        )
        lateral_face_count = sum(contact_count_by_kind[kind] for kind in _LATERAL_FACE_KINDS)
        if seam_count > lateral_face_count:
            raise ValueError("seam_lateral_face_count must not exceed the final lateral face count")

        contacting_piece_cells = _validate_world_cells(
            self.contacting_piece_cells,
            width=self.width,
            label="contacting_piece_cells",
        )
        contacted_aggregate_cells = _validate_world_cells(
            self.contacted_aggregate_cells,
            width=self.width,
            label="contacted_aggregate_cells",
        )
        contacted_support_sites = _validate_world_cells(
            self.contacted_support_sites,
            width=self.width,
            label="contacted_support_sites",
        )
        if not contacting_piece_cells or len(contacting_piece_cells) > contact_face_count:
            raise ValueError("contacting_piece_cells must match at least one and at most all final faces")
        nonfloor_face_count = contact_face_count - contact_count_by_kind[ContactFaceKind.FLOOR_SUPPORT]
        if len(contacted_aggregate_cells) > nonfloor_face_count:
            raise ValueError("contacted_aggregate_cells must not outnumber aggregate final faces")
        if not set(contacted_support_sites).issubset(contacted_aggregate_cells):
            raise ValueError("contacted_support_sites must be a subset of contacted_aggregate_cells")
        if len(contacted_support_sites) != contact_count_by_kind[ContactFaceKind.AGGREGATE_SUPPORT]:
            raise ValueError("contacted_support_sites must match aggregate-support face multiplicity")

        if type(self.contacted_support_columns) is not tuple:
            raise TypeError("contacted_support_columns must be a built-in tuple")
        support_columns: list[int] = []
        for column in self.contacted_support_columns:
            if type(column) is not int or not 0 <= column < self.width:
                raise ValueError("contacted_support_columns must contain built-in integers in [0, width)")
            support_columns.append(column)
        expected_support_columns = tuple(sorted({x for x, _ in contacted_support_sites}))
        if tuple(support_columns) != expected_support_columns:
            raise ValueError("contacted_support_columns must be the sorted support-site projection")

        expected_edges = _support_graph_edges(self.width, contacted_support_sites)
        if type(self.support_graph_edges) is not tuple:
            raise TypeError("support_graph_edges must be a built-in tuple")
        normalized_edges: list[SupportGraphEdge] = []
        for edge in self.support_graph_edges:
            if type(edge) is not tuple or len(edge) != 2:
                raise TypeError("support_graph_edges must contain built-in two-cell tuples")
            left = _validate_world_cells((edge[0],), width=self.width, label="support_graph_edges")[0]
            right = _validate_world_cells((edge[1],), width=self.width, label="support_graph_edges")[0]
            if left >= right:
                raise ValueError("support_graph_edges endpoints must be in canonical order")
            normalized_edges.append((left, right))
        if tuple(normalized_edges) != expected_edges:
            raise ValueError("support_graph_edges must be the canonical induced periodic N4 graph")

        cluster_count = _require_nonnegative_int(
            self.support_cluster_count,
            label="support_cluster_count",
        )
        expected_cluster_count = _support_cluster_count(contacted_support_sites, expected_edges)
        if cluster_count != expected_cluster_count:
            raise ValueError("support_cluster_count must equal the induced graph component count")

        expected_origin, expected_span, expected_gaps = _support_arc(self.width, expected_support_columns)
        if self.support_arc_origin is not None and (
            type(self.support_arc_origin) is not int or not 0 <= self.support_arc_origin < self.width
        ):
            raise ValueError("support_arc_origin must be None or a built-in integer in [0, width)")
        span = _require_nonnegative_int(self.support_arc_span, label="support_arc_span")
        if type(self.support_column_gaps) is not tuple:
            raise TypeError("support_column_gaps must be a built-in tuple")
        gaps = tuple(
            _require_positive_int(value, label="support_column_gaps value") for value in self.support_column_gaps
        )
        if (self.support_arc_origin, span, gaps) != (expected_origin, expected_span, expected_gaps):
            raise ValueError("support arc origin, span, and gaps must use the canonical cyclic rule")

        if type(self.envelope_changes) is not tuple:
            raise TypeError("envelope_changes must be a built-in tuple")
        changes: list[EnvelopeChange] = []
        for change in self.envelope_changes:
            if type(change) is not tuple or len(change) != 3:
                raise TypeError("envelope_changes must contain built-in (x, pre_height, post_height) tuples")
            x, pre_height, post_height = change
            if type(x) is not int or not 0 <= x < self.width:
                raise ValueError("envelope change columns must be built-in integers in [0, width)")
            if type(pre_height) is not int or type(post_height) is not int:
                raise TypeError("envelope change heights must be built-in integers")
            if pre_height < 0 or post_height <= pre_height:
                raise ValueError("envelope changes must record strict nonnegative height increases")
            changes.append((x, pre_height, post_height))
        if tuple(changes) != tuple(sorted(changes)) or len({x for x, _, _ in changes}) != len(changes):
            raise ValueError("envelope_changes must have unique columns in canonical order")

        height_sum_delta = _require_nonnegative_int(self.height_sum_delta, label="height_sum_delta")
        height_square_sum_delta = _require_nonnegative_int(
            self.height_square_sum_delta,
            label="height_square_sum_delta",
        )
        void_count_delta = _require_int(self.void_count_delta, label="void_count_delta")
        expected_height_sum_delta = sum(post - pre for _, pre, post in changes)
        expected_height_square_sum_delta = sum(post * post - pre * pre for _, pre, post in changes)
        if height_sum_delta != expected_height_sum_delta:
            raise ValueError("height_sum_delta must equal the sparse envelope-change sum")
        if height_square_sum_delta != expected_height_square_sum_delta:
            raise ValueError("height_square_sum_delta must equal the sparse squared-height-change sum")
        if void_count_delta != height_sum_delta - placed_mass:
            raise ValueError("void_count_delta must equal height_sum_delta minus placed_mass")

    @property
    def contact_face_count(self) -> int:
        return sum(count for _, count in self.contact_face_kind_counts)

    @property
    def causal_contact_face_count(self) -> int:
        return sum(count for _, count in self.causal_face_kind_counts)

    @property
    def contacting_piece_cell_count(self) -> int:
        return len(self.contacting_piece_cells)

    @property
    def contacted_aggregate_cell_count(self) -> int:
        return len(self.contacted_aggregate_cells)

    @property
    def contacted_support_site_count(self) -> int:
        return len(self.contacted_support_sites)

    @property
    def contacted_support_column_count(self) -> int:
        return len(self.contacted_support_columns)


def measure_placement(placement: ReferencePlacement) -> ReferencePlacementPrimitives:
    """Derive exact primitives from one defensively recertified placement.

    This function does not call :func:`place_one`; it reconstructs the supplied
    certificate through ``ReferencePlacement`` so all one-event identities are
    checked before measurement.  Work after that validation is sparse in the
    pre-state mass, contact count, support sites, and changed columns, with no
    iteration or allocation proportional to numerical width or height.  Total
    call cost includes the reference certificate's own landing/contact replay.
    """

    snapshot = _snapshot_placement(placement)
    contact_face_kinds = tuple(contact.kind for contact in snapshot.contacts)
    contact_face_kind_counts = _face_kind_counts(snapshot.contacts)
    causal_face_kind_counts = _face_kind_counts(snapshot.causal_contacts)
    causal_set = set(snapshot.causal_contacts)
    causal_contact_mask = sum(1 << index for index, contact in enumerate(snapshot.contacts) if contact in causal_set)
    seam_lateral_face_count = sum(
        contact.crosses_seam for contact in snapshot.contacts if contact.kind in _LATERAL_FACE_KINDS
    )
    contacting_piece_cells = tuple(sorted({contact.piece_cell for contact in snapshot.contacts}))
    contacted_aggregate_cells = tuple(
        sorted({contact.neighbor_cell for contact in snapshot.contacts if contact.neighbor_cell is not None})
    )
    contacted_support_sites = tuple(
        sorted(
            {
                contact.neighbor_cell
                for contact in snapshot.contacts
                if contact.kind is ContactFaceKind.AGGREGATE_SUPPORT and contact.neighbor_cell is not None
            }
        )
    )
    contacted_support_columns = tuple(sorted({x for x, _ in contacted_support_sites}))
    support_graph_edges = _support_graph_edges(snapshot.pre_state.width, contacted_support_sites)
    support_cluster_count = _support_cluster_count(contacted_support_sites, support_graph_edges)
    support_arc_origin, support_arc_span, support_column_gaps = _support_arc(
        snapshot.pre_state.width,
        contacted_support_columns,
    )

    pre_heights = _column_heights(snapshot.pre_state)
    post_heights = dict(pre_heights)
    for x, y in snapshot.piece_cells:
        height = y + 1
        if height > post_heights.get(x, 0):
            post_heights[x] = height
    envelope_changes = tuple(
        (x, pre_heights.get(x, 0), post_height)
        for x, post_height in sorted(post_heights.items())
        if post_height != pre_heights.get(x, 0)
    )
    placed_mass = snapshot.post_state.mass - snapshot.pre_state.mass
    height_sum_delta = sum(post - pre for _, pre, post in envelope_changes)
    height_square_sum_delta = sum(post * post - pre * pre for _, pre, post in envelope_changes)
    void_count_delta = height_sum_delta - placed_mass

    return ReferencePlacementPrimitives(
        width=snapshot.pre_state.width,
        contact_kind=snapshot.contact_kind,
        placed_mass=placed_mass,
        early_arrest_gap=snapshot.early_arrest_gap,
        lateral_trigger=snapshot.lateral_trigger,
        contact_face_kinds=contact_face_kinds,
        contact_face_kind_counts=contact_face_kind_counts,
        causal_face_kind_counts=causal_face_kind_counts,
        causal_contact_mask=causal_contact_mask,
        seam_lateral_face_count=seam_lateral_face_count,
        contacting_piece_cells=contacting_piece_cells,
        contacted_aggregate_cells=contacted_aggregate_cells,
        contacted_support_sites=contacted_support_sites,
        contacted_support_columns=contacted_support_columns,
        support_graph_edges=support_graph_edges,
        support_cluster_count=support_cluster_count,
        support_arc_origin=support_arc_origin,
        support_arc_span=support_arc_span,
        support_column_gaps=support_column_gaps,
        envelope_changes=envelope_changes,
        height_sum_delta=height_sum_delta,
        height_square_sum_delta=height_square_sum_delta,
        void_count_delta=void_count_delta,
    )
