"""Adversarial certification for one selected reference event placement.

The expected transition is deliberately composed from the independently
certified public geometry registry and :func:`place_one`.  These tests do not
reuse any geometry/contact resolver from the binding implementation.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as engine_package
from tetris_ballistic import models
from tetris_ballistic.engine import binding as binding_engine
from tetris_ballistic.engine import event as event_engine
from tetris_ballistic.engine import observables as observables_engine
from tetris_ballistic.engine import rng as semantic_rng
from tetris_ballistic.engine import selection as selection_engine
from tetris_ballistic.engine.binding import ReferenceEventPlacement, place_selected_event
from tetris_ballistic.engine.event import (
    TETROMINO_CONTACT_ORDER,
    TETROMINO_FAMILY_ORDER,
    ConditionalWeightedLaw,
    TetrominoEventLaw,
    TetrominoEventSelection,
    select_event,
)
from tetris_ballistic.engine.reference import ReferencePlacement, place_one
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.selection import (
    ExactWeightedLaw,
    UniformIntegerLaw,
    UniformSelection,
    WeightedSelection,
)
from tetris_ballistic.engine.state import SparseAggregate
from tetris_ballistic.models import GEOMETRY_BY_ID, TETROMINO_REGISTRY, ContactKind, PieceGeometry

_EXPECTED_GEOMETRIES = (
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
_EXPECTED_BY_ID = {
    geometry_id: PieceGeometry(geometry_id, family_id, coordinates)
    for geometry_id, family_id, coordinates in _EXPECTED_GEOMETRIES
}
_FAMILY_INDEX = {family_id: index for index, family_id in enumerate(TETROMINO_FAMILY_ORDER)}
_CONTACT_KIND_BY_ID = {
    "supported-v1": ContactKind.SUPPORTED_V1,
    "edge-first-contact-v1": ContactKind.EDGE_FIRST_CONTACT_V1,
}


def _orientation_counts_with(
    updates: dict[str, tuple[int, ...]] | None = None,
) -> dict[str, tuple[int, ...]]:
    counts = {family_id: (1,) * len(models.FAMILY_ORIENTATION_IDS[family_id]) for family_id in TETROMINO_FAMILY_ORDER}
    if updates:
        counts.update(updates)
    return counts


def _event_law(
    width: int,
    *,
    family_counts: tuple[int, ...] = (1, 1, 1, 1, 1),
    orientation_counts: dict[str, tuple[int, ...]] | None = None,
    contact_counts: tuple[int, int] = (1, 1),
) -> TetrominoEventLaw:
    per_family = _orientation_counts_with(orientation_counts)
    return TetrominoEventLaw(
        family_law=ExactWeightedLaw(TETROMINO_FAMILY_ORDER, family_counts),
        orientation_laws=ConditionalWeightedLaw(
            TETROMINO_FAMILY_ORDER,
            tuple(
                ExactWeightedLaw(models.FAMILY_ORIENTATION_IDS[family_id], per_family[family_id])
                for family_id in TETROMINO_FAMILY_ORDER
            ),
        ),
        launch_law=UniformIntegerLaw(width),
        contact_law=ExactWeightedLaw(TETROMINO_CONTACT_ORDER, contact_counts),
    )


def _selection_for(
    geometry_id: str,
    *,
    width: int,
    anchor_x: int,
    contact_id: str,
    law: TetrominoEventLaw | None = None,
    rejection_ordinals: tuple[int, int, int, int] = (11, 12, 13, 14),
) -> TetrominoEventSelection:
    family_id = _EXPECTED_BY_ID[geometry_id].family_id
    family_index = _FAMILY_INDEX[family_id]
    orientation_ids = models.FAMILY_ORIENTATION_IDS[family_id]
    orientation_index = orientation_ids.index(geometry_id)
    contact_index = TETROMINO_CONTACT_ORDER.index(contact_id)
    selected_law = law if law is not None else _event_law(width)
    return TetrominoEventSelection(
        root_seed=0x1234,
        coupling_group_id="binding-oracle",
        event_ordinal=0x5678,
        law=selected_law,
        family=WeightedSelection(
            "family",
            family_id,
            SemanticDraw(family_index, rejection_ordinals[0]),
        ),
        orientation=WeightedSelection(
            "orientation",
            geometry_id,
            SemanticDraw(orientation_index, rejection_ordinals[1]),
        ),
        launch=UniformSelection("launch", SemanticDraw(anchor_x, rejection_ordinals[2])),
        contact=WeightedSelection(
            "contact",
            contact_id,
            SemanticDraw(contact_index, rejection_ordinals[3]),
        ),
    )


def _single_geometry_selection(
    geometry_id: str,
    *,
    width: int,
    anchor_x: int,
    contact_id: str,
) -> TetrominoEventSelection:
    family_id = _EXPECTED_BY_ID[geometry_id].family_id
    family_counts = tuple(int(candidate == family_id) for candidate in TETROMINO_FAMILY_ORDER)
    selected_index = models.FAMILY_ORIENTATION_IDS[family_id].index(geometry_id)
    selected_counts = tuple(
        int(index == selected_index) for index in range(len(models.FAMILY_ORIENTATION_IDS[family_id]))
    )
    return _selection_for(
        geometry_id,
        width=width,
        anchor_x=anchor_x,
        contact_id=contact_id,
        law=_event_law(
            width,
            family_counts=family_counts,
            orientation_counts={family_id: selected_counts},
        ),
    )


def _expected_placement(
    state: SparseAggregate,
    selection: TetrominoEventSelection,
) -> ReferencePlacement:
    # This lookup and contact map are intentionally independent of binding.py.
    geometry = GEOMETRY_BY_ID[selection.geometry_id]
    return place_one(
        state,
        geometry,
        selection.launch_x,
        _CONTACT_KIND_BY_ID[selection.contact_id],
    )


def _occupied_from_mask(width: int, height: int, mask: int) -> frozenset[tuple[int, int]]:
    return frozenset((x, y) for y in range(height) for x in range(width) if mask & (1 << (y * width + x)))


def test_independent_ratified_geometry_fixture_matches_public_registry() -> None:
    actual = tuple((geometry.id, geometry.family_id, geometry.coordinates) for geometry in TETROMINO_REGISTRY)
    assert actual == _EXPECTED_GEOMETRIES
    assert tuple(GEOMETRY_BY_ID[geometry_id] for geometry_id in _EXPECTED_BY_ID) == TETROMINO_REGISTRY
    assert len(TETROMINO_REGISTRY) == len(_EXPECTED_BY_ID) == 19


def test_all_geometries_anchors_contacts_and_one_row_states_match_place_one() -> None:
    width = 5
    selections = tuple(
        _single_geometry_selection(
            geometry_id,
            width=width,
            anchor_x=anchor_x,
            contact_id=contact_id,
        )
        for geometry_id in _EXPECTED_BY_ID
        for anchor_x in range(width)
        for contact_id in TETROMINO_CONTACT_ORDER
    )
    case_count = 0
    for mask in range(1 << width):
        state = SparseAggregate(width, _occupied_from_mask(width, 1, mask))
        for selection in selections:
            actual = place_selected_event(state=state, selection=selection)
            assert type(actual) is ReferenceEventPlacement
            assert actual.selection == selection
            assert actual.selection is not selection
            assert actual.placement == _expected_placement(state, selection)
            assert actual.placement.geometry == _EXPECTED_BY_ID[selection.geometry_id]
            assert actual.placement.geometry.family_id == selection.family_id
            assert actual.placement.anchor_x == selection.launch_x
            assert actual.placement.contact_kind is _CONTACT_KIND_BY_ID[selection.contact_id]
            case_count += 1
    assert case_count == 6_080


def test_exhaustive_two_row_states_cover_positive_gaps_and_seams() -> None:
    width = 5
    geometry_id = "tetromino.o.00"
    selections = tuple(
        _single_geometry_selection(
            geometry_id,
            width=width,
            anchor_x=anchor_x,
            contact_id=contact_id,
        )
        for anchor_x in range(width)
        for contact_id in TETROMINO_CONTACT_ORDER
    )
    case_count = 0
    positive_gap_count = 0
    seam_contact_count = 0
    for mask in range(1 << (2 * width)):
        state = SparseAggregate(width, _occupied_from_mask(width, 2, mask))
        for selection in selections:
            actual = place_selected_event(state=state, selection=selection)
            assert actual.placement == _expected_placement(state, selection)
            positive_gap_count += int(actual.placement.early_arrest_gap > 0)
            seam_contact_count += int(any(face.crosses_seam for face in actual.placement.contacts))
            case_count += 1
    assert case_count == 10_240
    assert positive_gap_count > 0
    assert seam_contact_count > 0


@pytest.mark.parametrize("law_width", [3, 5])
def test_launch_law_bound_must_equal_state_width_even_when_anchor_fits(
    monkeypatch: pytest.MonkeyPatch,
    law_width: int,
) -> None:
    state = SparseAggregate.empty(4)
    selection = _single_geometry_selection(
        "tetromino.i.01",
        width=law_width,
        anchor_x=0,
        contact_id="supported-v1",
    )
    monkeypatch.setattr(
        "tetris_ballistic.engine.binding.place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran before the width mismatch failed"),
    )
    with pytest.raises(ValueError, match="launch-law upper bound must equal state width"):
        place_selected_event(state=state, selection=selection)


def test_positive_unselected_orientation_cannot_hide_periodic_width_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Vertical I is individually legal at width four; positive horizontal I is not.
    law = _event_law(
        4,
        family_counts=(1, 0, 0, 0, 0),
        orientation_counts={"i": (1, 1)},
    )
    selection = _selection_for(
        "tetromino.i.01",
        width=4,
        anchor_x=0,
        contact_id="supported-v1",
        law=law,
    )
    monkeypatch.setattr(
        "tetris_ballistic.engine.binding.place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran before complete-support preflight"),
    )
    with pytest.raises(ValueError, match="width greater than every positive-weight geometry"):
        place_selected_event(state=SparseAggregate.empty(4), selection=selection)


def test_well_typed_noop_preflight_cannot_bypass_positive_support_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law(
        4,
        family_counts=(1, 0, 0, 0, 0),
        orientation_counts={"i": (1, 1)},
    )
    selection = _selection_for(
        "tetromino.i.01",
        width=4,
        anchor_x=0,
        contact_id="supported-v1",
        law=law,
    )
    monkeypatch.setattr(binding_engine, "validate_periodic_law", lambda _width, support: tuple(support))
    monkeypatch.setattr(
        binding_engine,
        "place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran after a no-op positive-support preflight"),
    )
    with pytest.raises(ValueError, match="width greater than every positive-weight geometry"):
        place_selected_event(state=SparseAggregate.empty(4), selection=selection)


def test_positive_unselected_family_cannot_hide_periodic_width_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Selected O is legal at width three, but reachable horizontal I is not.
    law = _event_law(
        3,
        family_counts=(1, 0, 1, 0, 0),
        orientation_counts={"i": (1, 0)},
    )
    selection = _selection_for(
        "tetromino.o.00",
        width=3,
        anchor_x=0,
        contact_id="supported-v1",
        law=law,
    )
    monkeypatch.setattr(
        "tetris_ballistic.engine.binding.place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran before complete-support preflight"),
    )
    with pytest.raises(ValueError, match="width greater than every positive-weight geometry"):
        place_selected_event(state=SparseAggregate.empty(3), selection=selection)


def test_zero_orientation_and_zero_family_support_are_not_executed() -> None:
    vertical_i_only = _selection_for(
        "tetromino.i.01",
        width=4,
        anchor_x=3,
        contact_id="edge-first-contact-v1",
        law=_event_law(
            4,
            family_counts=(1, 0, 0, 0, 0),
            orientation_counts={"i": (0, 1)},
        ),
    )
    vertical_result = place_selected_event(state=SparseAggregate.empty(4), selection=vertical_i_only)
    assert vertical_result.placement == _expected_placement(SparseAggregate.empty(4), vertical_i_only)

    o_only = _selection_for(
        "tetromino.o.00",
        width=3,
        anchor_x=2,
        contact_id="supported-v1",
        law=_event_law(
            3,
            family_counts=(0, 0, 1, 0, 0),
            orientation_counts={"i": (1, 0)},
        ),
    )
    o_result = place_selected_event(state=SparseAggregate.empty(3), selection=o_only)
    assert o_result.placement == _expected_placement(SparseAggregate.empty(3), o_only)


def test_positive_support_is_preflighted_in_family_then_orientation_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law(
        5,
        family_counts=(1, 0, 1, 0, 0),
        orientation_counts={"i": (0, 1)},
    )
    selection = _selection_for(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
        law=law,
    )
    real_preflight = binding_engine.validate_periodic_law
    calls: list[tuple[str, ...]] = []

    def preflight_spy(width: int, geometries: tuple[PieceGeometry, ...]) -> tuple[PieceGeometry, ...]:
        calls.append(tuple(geometry.id for geometry in geometries))
        return real_preflight(width, geometries)

    monkeypatch.setattr(binding_engine, "validate_periodic_law", preflight_spy)
    place_selected_event(state=SparseAggregate.empty(5), selection=selection)
    assert calls == [("tetromino.i.01", "tetromino.o.00")]


@pytest.mark.parametrize(
    ("authority_name", "replacement", "message"),
    [
        ("TETROMINO_REGISTRY", tuple(reversed(TETROMINO_REGISTRY)), "TETROMINO_REGISTRY"),
        ("FAMILY_ORIENTATION_IDS", dict(models.FAMILY_ORIENTATION_IDS), "FAMILY_ORIENTATION_IDS"),
        ("GEOMETRY_BY_ID", dict(GEOMETRY_BY_ID), "GEOMETRY_BY_ID"),
    ],
)
def test_rebound_geometry_authorities_fail_before_placement(
    monkeypatch: pytest.MonkeyPatch,
    authority_name: str,
    replacement: object,
    message: str,
) -> None:
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )
    monkeypatch.setattr(binding_engine, authority_name, replacement)
    monkeypatch.setattr(
        binding_engine,
        "place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran with a rebound registry authority"),
    )
    with pytest.raises(AssertionError, match=message):
        place_selected_event(state=SparseAggregate.empty(5), selection=selection)


def test_cross_family_registry_drift_fails_before_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    drifted = list(TETROMINO_REGISTRY)
    original = drifted[10]
    drifted[10] = PieceGeometry(original.id, "i", original.coordinates)
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )
    monkeypatch.setattr(binding_engine, "TETROMINO_REGISTRY", tuple(drifted))
    monkeypatch.setattr(
        binding_engine,
        "place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran with cross-family registry drift"),
    )
    with pytest.raises(AssertionError, match="ratified geometry registry"):
        place_selected_event(state=SparseAggregate.empty(5), selection=selection)


def test_registry_poisoned_before_first_binding_import_fails_closed() -> None:
    script = r"""
from types import MappingProxyType

import tetris_ballistic.models as models

poisoned_registry = tuple(
    models.PieceGeometry(
        geometry.id,
        geometry.family_id,
        models.GEOMETRY_BY_ID["tetromino.i.01"].coordinates
        if geometry.id == "tetromino.o.00"
        else geometry.coordinates,
    )
    for geometry in models.TETROMINO_REGISTRY
)
one_cell = models.GEOMETRY_BY_ID["baseline.one-cell"]
models.TETROMINO_REGISTRY = poisoned_registry
models.GEOMETRY_BY_ID = MappingProxyType(
    {geometry.id: geometry for geometry in (*poisoned_registry, one_cell)}
)

from tetris_ballistic.engine.binding import place_selected_event
from tetris_ballistic.engine.event import (
    ConditionalWeightedLaw,
    TETROMINO_CONTACT_ORDER,
    TETROMINO_FAMILY_ORDER,
    TetrominoEventLaw,
    TetrominoEventSelection,
)
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.selection import (
    ExactWeightedLaw,
    UniformIntegerLaw,
    UniformSelection,
    WeightedSelection,
)
from tetris_ballistic.engine.state import SparseAggregate

orientation_laws = ConditionalWeightedLaw(
    TETROMINO_FAMILY_ORDER,
    tuple(
        ExactWeightedLaw(models.FAMILY_ORIENTATION_IDS[family], (1,) * len(models.FAMILY_ORIENTATION_IDS[family]))
        for family in TETROMINO_FAMILY_ORDER
    ),
)
law = TetrominoEventLaw(
    ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
    orientation_laws,
    UniformIntegerLaw(5),
    ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
)
selection = TetrominoEventSelection(
    0,
    "import-order-poison",
    0,
    law,
    WeightedSelection("family", "o", SemanticDraw(2, 0)),
    WeightedSelection("orientation", "tetromino.o.00", SemanticDraw(0, 0)),
    UniformSelection("launch", SemanticDraw(0, 0)),
    WeightedSelection("contact", "supported-v1", SemanticDraw(0, 0)),
)
try:
    place_selected_event(state=SparseAggregate.empty(5), selection=selection)
except AssertionError:
    print("rejected")
else:
    raise AssertionError("binding accepted a geometry registry poisoned before first import")
"""
    project_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        cwd=project_root,
        text=True,
    )
    assert completed.stdout == "rejected\n"


def test_malformed_preflight_result_fails_before_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )
    monkeypatch.setattr(binding_engine, "validate_periodic_law", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        binding_engine,
        "place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran after malformed preflight output"),
    )
    with pytest.raises(AssertionError, match="geometry support inconsistent"):
        place_selected_event(state=SparseAggregate.empty(5), selection=selection)


def test_mutating_preflight_cannot_rewrite_the_expected_geometry_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )

    def mutating_preflight(
        _width: int,
        geometries: tuple[PieceGeometry, ...],
    ) -> tuple[PieceGeometry, ...]:
        object.__setattr__(geometries[0], "coordinates", _EXPECTED_BY_ID["tetromino.t.00"].coordinates)
        return geometries

    monkeypatch.setattr(binding_engine, "validate_periodic_law", mutating_preflight)
    monkeypatch.setattr(
        binding_engine,
        "place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran after preflight input mutation"),
    )
    with pytest.raises(AssertionError, match="geometry support inconsistent"):
        place_selected_event(state=SparseAggregate.empty(5), selection=selection)


def test_maximum_semantic_width_is_sparse_and_width_independent() -> None:
    width = 1 << 64
    anchor_x = width - 1
    height = 10**100
    state = SparseAggregate(width, {(0, height)})
    selection = _single_geometry_selection(
        "tetromino.i.01",
        width=width,
        anchor_x=anchor_x,
        contact_id="edge-first-contact-v1",
    )
    actual = place_selected_event(state=state, selection=selection)
    assert actual.placement == _expected_placement(state, selection)
    assert actual.placement.anchor_x == anchor_x
    assert actual.placement.landing_y == height
    assert any(face.crosses_seam for face in actual.placement.contacts)


def test_state_wider_than_semantic_u64_domain_fails_before_placement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maximum_law_width = 1 << 64
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=maximum_law_width,
        anchor_x=0,
        contact_id="supported-v1",
    )
    monkeypatch.setattr(
        "tetris_ballistic.engine.binding.place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran for an unequal-width law"),
    )
    with pytest.raises(ValueError, match="launch-law upper bound must equal state width"):
        place_selected_event(state=SparseAggregate.empty(maximum_law_width + 1), selection=selection)


def test_binding_consumes_no_rng_selection_or_observable_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SparseAggregate(5, {(4, 7)})
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="edge-first-contact-v1",
    )
    expected = _expected_placement(state, selection)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("binding crossed a forbidden layer")

    monkeypatch.setattr(event_engine, "select_event", forbidden)
    monkeypatch.setattr(selection_engine, "select_weighted", forbidden)
    monkeypatch.setattr(selection_engine, "select_uniform", forbidden)
    monkeypatch.setattr(semantic_rng, "raw_u64", forbidden)
    monkeypatch.setattr(semantic_rng, "uniform_below", forbidden)
    monkeypatch.setattr(semantic_rng, "categorical_index", forbidden)
    monkeypatch.setattr(observables_engine, "measure_state", forbidden)
    monkeypatch.setattr(observables_engine, "measure_placement", forbidden)

    calls: list[tuple[SparseAggregate, PieceGeometry, int, ContactKind]] = []

    def placement_spy(
        supplied_state: SparseAggregate,
        geometry: PieceGeometry,
        anchor_x: int,
        contact_kind: ContactKind,
    ) -> ReferencePlacement:
        calls.append((supplied_state, geometry, anchor_x, contact_kind))
        return place_one(supplied_state, geometry, anchor_x, contact_kind)

    monkeypatch.setattr("tetris_ballistic.engine.binding.place_one", placement_spy)
    actual = place_selected_event(state=state, selection=selection)

    assert actual.placement == expected
    assert calls == [
        (state, GEOMETRY_BY_ID[selection.geometry_id], selection.launch_x, ContactKind.EDGE_FIRST_CONTACT_V1)
    ]
    assert calls[0][0] is not state


def test_genuine_select_event_evidence_is_preserved_without_replay() -> None:
    law = _event_law(5)
    selection = select_event(
        root_seed=0,
        coupling_group_id="paired-main",
        event_ordinal=0,
        law=law,
    )
    state = SparseAggregate(5, {(0, 2), (4, 4)})
    actual = place_selected_event(state=state, selection=selection)
    assert actual.selection == selection
    assert actual.selection is not selection
    assert tuple(
        selected.draw
        for selected in (
            actual.selection.family,
            actual.selection.orientation,
            actual.selection.launch,
            actual.selection.contact,
        )
    ) == tuple(
        selected.draw for selected in (selection.family, selection.orientation, selection.launch, selection.contact)
    )
    assert actual.placement == _expected_placement(state, selection)


def test_structurally_valid_nonreplayed_draw_metadata_is_preserved() -> None:
    selection = _single_geometry_selection(
        "tetromino.t.03",
        width=5,
        anchor_x=4,
        contact_id="edge-first-contact-v1",
    )
    assert tuple(
        selected.draw.accepted_rejection_ordinal
        for selected in (selection.family, selection.orientation, selection.launch, selection.contact)
    ) == (11, 12, 13, 14)
    actual = place_selected_event(state=SparseAggregate.empty(5), selection=selection)
    assert tuple(
        selected.draw.accepted_rejection_ordinal
        for selected in (
            actual.selection.family,
            actual.selection.orientation,
            actual.selection.launch,
            actual.selection.contact,
        )
    ) == (11, 12, 13, 14)


def test_inputs_and_nested_output_are_defensive_immutable_snapshots() -> None:
    mutable_cells: set[tuple[int, int]] = {(1, 0)}
    state = SparseAggregate.empty(5)
    object.__setattr__(state, "occupied", mutable_cells)
    selection = _single_geometry_selection(
        "tetromino.t.00",
        width=5,
        anchor_x=3,
        contact_id="supported-v1",
    )
    expected_family_counts = selection.law.family_law.counts
    actual = place_selected_event(state=state, selection=selection)

    mutable_cells.add((2, 100))
    object.__setattr__(selection.law.family_law, "counts", (0, 0, 1, 0, 0))
    assert actual.placement.pre_state.occupied == frozenset({(1, 0)})
    assert actual.selection.law.family_law.counts == expected_family_counts
    assert actual.placement.pre_state is not state
    assert actual.selection is not selection
    assert isinstance(actual.placement.pre_state.occupied, frozenset)
    with pytest.raises(FrozenInstanceError):
        actual.placement = actual.placement  # type: ignore[misc]


def test_exact_boundary_types_and_validation_order() -> None:
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )

    class SparseAggregateSubclass(SparseAggregate):
        pass

    class SelectionSubclass(TetrominoEventSelection):
        pass

    with pytest.raises(TypeError, match="state must be a SparseAggregate"):
        place_selected_event(state=object(), selection=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="state must be a SparseAggregate"):
        place_selected_event(state=SparseAggregateSubclass(5, ()), selection=selection)
    with pytest.raises(TypeError, match="selection must be a TetrominoEventSelection"):
        place_selected_event(state=SparseAggregate.empty(5), selection=object())  # type: ignore[arg-type]

    subclass = SelectionSubclass(*(getattr(selection, field.name) for field in fields(TetrominoEventSelection)))
    with pytest.raises(TypeError, match="selection must be a TetrominoEventSelection"):
        place_selected_event(state=SparseAggregate.empty(5), selection=subclass)


def test_forged_partial_and_malformed_nested_inputs_fail_before_placement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "tetris_ballistic.engine.binding.place_one",
        lambda *_args, **_kwargs: pytest.fail("placement ran for a malformed input certificate"),
    )
    partial = object.__new__(TetrominoEventSelection)
    with pytest.raises(TypeError, match="selection must be fully initialized"):
        place_selected_event(state=SparseAggregate.empty(5), selection=partial)

    malformed = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )
    object.__setattr__(malformed.orientation.draw, "value", 99)
    with pytest.raises((TypeError, ValueError)):
        place_selected_event(state=SparseAggregate.empty(5), selection=malformed)


def test_result_record_is_exact_frozen_slotted_and_directly_recertified() -> None:
    state = SparseAggregate.empty(5)
    selection = _single_geometry_selection(
        "tetromino.sz.03",
        width=5,
        anchor_x=4,
        contact_id="edge-first-contact-v1",
    )
    actual = place_selected_event(state=state, selection=selection)
    assert tuple(field.name for field in fields(ReferenceEventPlacement)) == ("selection", "placement")
    assert ReferenceEventPlacement(actual.selection, actual.placement) == actual
    assert hash(actual)
    assert not hasattr(actual, "__dict__")

    wrong_anchor_placement = place_one(
        state,
        GEOMETRY_BY_ID[selection.geometry_id],
        0,
        ContactKind.EDGE_FIRST_CONTACT_V1,
    )
    with pytest.raises(ValueError):
        replace(actual, placement=wrong_anchor_placement)
    with pytest.raises(TypeError, match="selection must be a TetrominoEventSelection"):
        ReferenceEventPlacement(object(), actual.placement)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="placement must be a ReferencePlacement"):
        ReferenceEventPlacement(actual.selection, object())  # type: ignore[arg-type]


def test_direct_result_construction_rechecks_complete_positive_support() -> None:
    law = _event_law(
        4,
        family_counts=(1, 0, 0, 0, 0),
        orientation_counts={"i": (1, 1)},
    )
    selection = _selection_for(
        "tetromino.i.01",
        width=4,
        anchor_x=0,
        contact_id="supported-v1",
        law=law,
    )
    placement = place_one(
        SparseAggregate.empty(4),
        GEOMETRY_BY_ID[selection.geometry_id],
        selection.launch_x,
        ContactKind.SUPPORTED_V1,
    )
    with pytest.raises(ValueError, match="width greater than every positive-weight geometry"):
        ReferenceEventPlacement(selection, placement)


def test_malformed_or_inconsistent_delegated_placement_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = SparseAggregate.empty(5)
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=1,
        contact_id="supported-v1",
    )
    monkeypatch.setattr("tetris_ballistic.engine.binding.place_one", lambda *_args, **_kwargs: object())
    with pytest.raises(AssertionError, match="place_one|placement"):
        place_selected_event(state=state, selection=selection)

    inconsistent = place_one(
        state,
        GEOMETRY_BY_ID[selection.geometry_id],
        2,
        ContactKind.SUPPORTED_V1,
    )
    monkeypatch.setattr("tetris_ballistic.engine.binding.place_one", lambda *_args, **_kwargs: inconsistent)
    with pytest.raises(AssertionError, match="placement"):
        place_selected_event(state=state, selection=selection)


@pytest.mark.parametrize("mutated_authority", ["state", "geometry"])
def test_mutating_delegate_cannot_rewrite_pristine_binding_authorities(
    monkeypatch: pytest.MonkeyPatch,
    mutated_authority: str,
) -> None:
    state = SparseAggregate.empty(5)
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=1,
        contact_id="supported-v1",
    )

    def mutating_delegate(
        supplied_state: SparseAggregate,
        supplied_geometry: PieceGeometry,
        anchor_x: int,
        contact_kind: ContactKind,
    ) -> ReferencePlacement:
        if mutated_authority == "state":
            object.__setattr__(supplied_state, "occupied", frozenset({(4, 10)}))
        else:
            object.__setattr__(
                supplied_geometry,
                "coordinates",
                _EXPECTED_BY_ID["tetromino.t.00"].coordinates,
            )
        return place_one(supplied_state, supplied_geometry, anchor_x, contact_kind)

    monkeypatch.setattr(binding_engine, "place_one", mutating_delegate)
    message = "placement pre_state" if mutated_authority == "state" else "placement geometry"
    with pytest.raises(AssertionError, match=message):
        place_selected_event(state=state, selection=selection)


def test_binding_function_is_keyword_only() -> None:
    state = SparseAggregate.empty(5)
    selection = _single_geometry_selection(
        "tetromino.o.00",
        width=5,
        anchor_x=0,
        contact_id="supported-v1",
    )
    with pytest.raises(TypeError):
        place_selected_event(state, selection)  # type: ignore[misc]


def test_binding_api_stays_explicit_only_and_imports_no_later_layers() -> None:
    names = ("ReferenceEventPlacement", "place_selected_event")
    for module in (
        tetris_ballistic,
        engine_package,
        event_engine,
        selection_engine,
        semantic_rng,
        observables_engine,
    ):
        for name in names:
            assert not hasattr(module, name)

    source_path = Path(__file__).resolve().parents[1] / "tetris_ballistic" / "engine" / "binding.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    forbidden_fragments = (
        "config",
        "observables",
        "rng",
        "selection",
        "simulation",
        "tetris_ballistic.tetris_ballistic",
    )
    assert not any(fragment in imported for imported in imported_modules for fragment in forbidden_fragments)
