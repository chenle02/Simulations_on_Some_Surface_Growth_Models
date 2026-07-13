"""Certification tests for provisional S2.4 tetromino event selection."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.event as complete_event
import tetris_ballistic.engine.reference as placement_engine
import tetris_ballistic.engine.selection as exact_selection
from tetris_ballistic.engine.event import (
    TETROMINO_CONTACT_ORDER,
    TETROMINO_FAMILY_ORDER,
    TETROMINO_STREAM_SET,
    ConditionalWeightedLaw,
    TetrominoEventLaw,
    TetrominoEventSelection,
    select_event,
)
from tetris_ballistic.engine.rng import SemanticDraw, raw_u64
from tetris_ballistic.engine.selection import (
    DeclaredStreamSet,
    ExactWeightedLaw,
    UniformIntegerLaw,
    UniformSelection,
    WeightedSelection,
)
from tetris_ballistic.models import FAMILY_ORIENTATION_IDS

_U64_SPACE = 1 << 64
_U128_MAX = (1 << 128) - 1

_EXPECTED_ORIENTATION_IDS = {
    "i": ("tetromino.i.00", "tetromino.i.01"),
    "lj": tuple(f"tetromino.lj.{index:02d}" for index in range(8)),
    "o": ("tetromino.o.00",),
    "sz": tuple(f"tetromino.sz.{index:02d}" for index in range(4)),
    "t": tuple(f"tetromino.t.{index:02d}" for index in range(4)),
}


class _TupleSubclass(tuple):
    pass


class _StringSubclass(str):
    pass


def _orientation_laws(
    counts_by_family: dict[str, tuple[int, ...]] | None = None,
) -> ConditionalWeightedLaw:
    counts_by_family = counts_by_family or {
        family_id: (1,) * len(_EXPECTED_ORIENTATION_IDS[family_id]) for family_id in TETROMINO_FAMILY_ORDER
    }
    return ConditionalWeightedLaw(
        TETROMINO_FAMILY_ORDER,
        tuple(
            ExactWeightedLaw(_EXPECTED_ORIENTATION_IDS[family_id], counts_by_family[family_id])
            for family_id in TETROMINO_FAMILY_ORDER
        ),
    )


def _event_law(
    *,
    family_counts: tuple[int, ...] = (1, 1, 1, 1, 1),
    orientation_counts: dict[str, tuple[int, ...]] | None = None,
    launch_bound: int = 17,
    contact_counts: tuple[int, ...] = (1, 1),
) -> TetrominoEventLaw:
    return TetrominoEventLaw(
        family_law=ExactWeightedLaw(TETROMINO_FAMILY_ORDER, family_counts),
        orientation_laws=_orientation_laws(orientation_counts),
        launch_law=UniformIntegerLaw(launch_bound),
        contact_law=ExactWeightedLaw(TETROMINO_CONTACT_ORDER, contact_counts),
    )


def _select(law: TetrominoEventLaw, *, event_ordinal: int = 0) -> TetrominoEventSelection:
    return select_event(
        root_seed=0,
        coupling_group_id="paired-main",
        event_ordinal=event_ordinal,
        law=law,
    )


def _manual_bounded(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    upper_bound: int,
) -> SemanticDraw:
    quotient = _U64_SPACE // upper_bound
    threshold = quotient * upper_bound
    rejection = 0
    while True:
        word = raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection,
        )
        if word < threshold:
            return SemanticDraw(word // quotient, rejection)
        rejection += 1


def _manual_weighted(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    law: ExactWeightedLaw,
) -> tuple[str, SemanticDraw]:
    bounded = _manual_bounded(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        stream_name=stream_name,
        event_ordinal=event_ordinal,
        upper_bound=law.total_count,
    )
    cumulative = 0
    for index, count in enumerate(law.counts):
        cumulative += count
        if bounded.value < cumulative:
            return law.outcome_ids[index], SemanticDraw(index, bounded.accepted_rejection_ordinal)
    raise AssertionError("manual categorical interval search did not terminate")


def test_ratified_family_contact_stream_and_orientation_orders_are_exact() -> None:
    assert TETROMINO_FAMILY_ORDER == ("i", "lj", "o", "sz", "t")
    assert TETROMINO_CONTACT_ORDER == ("supported-v1", "edge-first-contact-v1")
    assert TETROMINO_STREAM_SET == DeclaredStreamSet(("family", "orientation", "launch", "contact"))
    assert dict(FAMILY_ORIENTATION_IDS) == _EXPECTED_ORIENTATION_IDS
    assert tuple(map(len, _EXPECTED_ORIENTATION_IDS.values())) == (2, 8, 1, 4, 4)
    assert sum(map(len, _EXPECTED_ORIENTATION_IDS.values())) == 19


def test_conditional_law_defensively_snapshots_and_returns_a_copy() -> None:
    branch_ids = list(TETROMINO_FAMILY_ORDER)
    branch_laws = [
        ExactWeightedLaw(_EXPECTED_ORIENTATION_IDS[family_id], (1,) * len(_EXPECTED_ORIENTATION_IDS[family_id]))
        for family_id in branch_ids
    ]
    law = ConditionalWeightedLaw(branch_ids, branch_laws)
    branch_ids.reverse()
    branch_laws.clear()

    assert law.branch_ids == TETROMINO_FAMILY_ORDER
    assert len(law.branch_laws) == 5
    copied = law.law_for("lj")
    assert copied == law.branch_laws[1]
    assert copied is not law.branch_laws[1]
    object.__setattr__(copied, "counts", (1,))
    assert law.branch_laws[1].counts == (1,) * 8
    with pytest.raises(FrozenInstanceError):
        law.branch_ids = ()  # type: ignore[misc]


def test_event_law_and_result_defensively_snapshot_nested_records() -> None:
    supplied_family = ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1))
    supplied_orientations = _orientation_laws()
    supplied_launch = UniformIntegerLaw(17)
    supplied_contact = ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1))
    law = TetrominoEventLaw(
        supplied_family,
        supplied_orientations,
        supplied_launch,
        supplied_contact,
    )
    object.__setattr__(supplied_family, "counts", (1, 0, 0, 0, 0))
    object.__setattr__(supplied_orientations.branch_laws[3], "counts", (1, 0, 0, 0))
    object.__setattr__(supplied_launch, "upper_bound", 1)
    object.__setattr__(supplied_contact, "counts", (1, 0))

    assert law.family_law.counts == (1, 1, 1, 1, 1)
    assert law.orientation_laws.branch_laws[3].counts == (1, 1, 1, 1)
    assert law.launch_law.upper_bound == 17
    assert law.contact_law.counts == (1, 1)
    result = _select(law)
    object.__setattr__(law.family_law, "counts", (1, 0, 0, 0, 0))
    assert result.law.family_law.counts == (1, 1, 1, 1, 1)
    assert hash(result)
    with pytest.raises(FrozenInstanceError):
        result.event_ordinal = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("branch_ids", "branch_laws", "exception"),
    [
        ([], [], ValueError),
        (("i", "i"), (ExactWeightedLaw(("a",), (1,)),) * 2, ValueError),
        (("i",), (), ValueError),
        ({"i"}, (ExactWeightedLaw(("a",), (1,)),), TypeError),
        (_TupleSubclass(("i",)), (ExactWeightedLaw(("a",), (1,)),), TypeError),
        (("i",), {ExactWeightedLaw(("a",), (1,))}, TypeError),
        ((_StringSubclass("i"),), (ExactWeightedLaw(("a",), (1,)),), TypeError),
        (("i",), (object(),), TypeError),
    ],
)
def test_conditional_law_rejects_malformed_records(
    branch_ids: object,
    branch_laws: object,
    exception: type[Exception],
) -> None:
    with pytest.raises(exception):
        ConditionalWeightedLaw(branch_ids, branch_laws)  # type: ignore[arg-type]


def test_conditional_law_rejects_unknown_lookup() -> None:
    law = _orientation_laws()
    with pytest.raises(ValueError, match="unknown conditional-law branch"):
        law.law_for("one-cell")
    with pytest.raises(TypeError):
        law.law_for(_StringSubclass("i"))


def test_event_law_rejects_reordered_family_and_contact_outcomes() -> None:
    orientations = _orientation_laws()
    with pytest.raises(ValueError, match="family_law outcome IDs"):
        TetrominoEventLaw(
            ExactWeightedLaw(tuple(reversed(TETROMINO_FAMILY_ORDER)), (1, 1, 1, 1, 1)),
            orientations,
            UniformIntegerLaw(17),
            ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
        )
    with pytest.raises(ValueError, match="contact_law outcome IDs"):
        TetrominoEventLaw(
            ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
            orientations,
            UniformIntegerLaw(17),
            ExactWeightedLaw(tuple(reversed(TETROMINO_CONTACT_ORDER)), (1, 1)),
        )


def test_event_law_requires_the_complete_five_branch_table_even_if_unreachable() -> None:
    family = ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 0, 0, 0, 0))
    full_law = TetrominoEventLaw(
        family,
        _orientation_laws(),
        UniformIntegerLaw(1),
        ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 0)),
    )
    assert full_law.orientation_laws.branch_ids == TETROMINO_FAMILY_ORDER

    incomplete = ConditionalWeightedLaw(
        TETROMINO_FAMILY_ORDER[:-1],
        _orientation_laws().branch_laws[:-1],
    )
    with pytest.raises(ValueError, match="branch IDs"):
        TetrominoEventLaw(
            family,
            incomplete,
            UniformIntegerLaw(1),
            ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 0)),
        )


def test_event_law_rejects_reordered_and_cross_family_orientation_ids() -> None:
    valid = _orientation_laws()
    reordered_laws = list(valid.branch_laws)
    reordered_laws[1] = ExactWeightedLaw(tuple(reversed(_EXPECTED_ORIENTATION_IDS["lj"])), (1,) * 8)
    with pytest.raises(ValueError, match="ratified orientation order"):
        TetrominoEventLaw(
            ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
            ConditionalWeightedLaw(TETROMINO_FAMILY_ORDER, reordered_laws),
            UniformIntegerLaw(17),
            ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
        )

    cross_family_laws = list(valid.branch_laws)
    cross_family_laws[2] = ExactWeightedLaw((_EXPECTED_ORIENTATION_IDS["i"][0],), (1,))
    with pytest.raises(ValueError, match="ratified orientation order"):
        TetrominoEventLaw(
            ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
            ConditionalWeightedLaw(TETROMINO_FAMILY_ORDER, cross_family_laws),
            UniformIntegerLaw(17),
            ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
        )


def test_event_law_rejects_reordered_orientation_branches() -> None:
    valid = _orientation_laws()
    with pytest.raises(ValueError, match="branch IDs"):
        TetrominoEventLaw(
            ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
            ConditionalWeightedLaw(
                tuple(reversed(valid.branch_ids)),
                tuple(reversed(valid.branch_laws)),
            ),
            UniformIntegerLaw(17),
            ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
        )


@pytest.mark.parametrize(
    ("field", "replacement", "exception"),
    [
        ("family_law", object(), TypeError),
        ("orientation_laws", object(), TypeError),
        ("launch_law", object(), TypeError),
        ("contact_law", object(), TypeError),
    ],
)
def test_event_law_requires_exact_record_types(
    field: str,
    replacement: object,
    exception: type[Exception],
) -> None:
    values = {
        "family_law": ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
        "orientation_laws": _orientation_laws(),
        "launch_law": UniformIntegerLaw(17),
        "contact_law": ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
    }
    values[field] = replacement
    with pytest.raises(exception):
        TetrominoEventLaw(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("address_update", "exception"),
    [
        ({"root_seed": True}, TypeError),
        ({"root_seed": -1}, ValueError),
        ({"root_seed": _U128_MAX + 1}, ValueError),
        ({"coupling_group_id": ""}, ValueError),
        ({"coupling_group_id": _StringSubclass("group")}, TypeError),
        ({"coupling_group_id": "\ud800"}, ValueError),
        ({"event_ordinal": True}, TypeError),
        ({"event_ordinal": -1}, ValueError),
        ({"event_ordinal": 1 << 64}, ValueError),
    ],
)
def test_invalid_address_fails_before_any_draw(
    monkeypatch: pytest.MonkeyPatch,
    address_update: dict[str, object],
    exception: type[Exception],
) -> None:
    def forbidden(**_: object) -> object:
        raise AssertionError("selector must not run")

    monkeypatch.setattr(complete_event, "select_weighted", forbidden)
    monkeypatch.setattr(complete_event, "select_uniform", forbidden)
    address: dict[str, object] = {
        "root_seed": 0,
        "coupling_group_id": "group",
        "event_ordinal": 0,
    }
    address.update(address_update)
    with pytest.raises(exception):
        select_event(**address, law=_event_law())  # type: ignore[arg-type]


def test_complete_law_is_revalidated_before_any_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    law = _event_law(family_counts=(1, 0, 0, 0, 0))
    object.__setattr__(
        law.orientation_laws.branch_laws[-1],
        "outcome_ids",
        tuple(f"corrupt-unreachable-{index}" for index in range(4)),
    )

    def forbidden(**_: object) -> object:
        raise AssertionError("selector must not run")

    monkeypatch.setattr(complete_event, "select_weighted", forbidden)
    monkeypatch.setattr(complete_event, "select_uniform", forbidden)
    with pytest.raises(ValueError, match="ratified orientation order"):
        _select(law)


def test_fixed_stream_schedule_is_revalidated_before_any_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        complete_event,
        "TETROMINO_STREAM_SET",
        DeclaredStreamSet(("family",)),
    )

    def forbidden(**_: object) -> object:
        raise AssertionError("selector must not run")

    monkeypatch.setattr(complete_event, "select_weighted", forbidden)
    monkeypatch.setattr(complete_event, "select_uniform", forbidden)
    with pytest.raises(AssertionError, match="fixed event schedule"):
        _select(_event_law())


@pytest.mark.parametrize(
    ("public_name", "replacement", "message"),
    [
        ("TETROMINO_FAMILY_ORDER", tuple(reversed(TETROMINO_FAMILY_ORDER)), "FAMILY_ORDER"),
        ("TETROMINO_CONTACT_ORDER", tuple(reversed(TETROMINO_CONTACT_ORDER)), "CONTACT_ORDER"),
        ("FAMILY_ORIENTATION_IDS", {"i": ("forged.i.00",)}, "FAMILY_ORIENTATION_IDS"),
    ],
)
def test_rebound_public_orders_fail_before_any_draw(
    monkeypatch: pytest.MonkeyPatch,
    public_name: str,
    replacement: object,
    message: str,
) -> None:
    law = _event_law()

    def forbidden(**_: object) -> object:
        raise AssertionError("selector must not run")

    monkeypatch.setattr(complete_event, public_name, replacement)
    monkeypatch.setattr(complete_event, "select_weighted", forbidden)
    monkeypatch.setattr(complete_event, "select_uniform", forbidden)
    with pytest.raises(AssertionError, match=message):
        _select(law)


def test_selector_uses_exact_four_call_schedule_and_only_selected_orientation_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law()
    real_weighted = complete_event.select_weighted
    real_uniform = complete_event.select_uniform
    calls: list[tuple[str, dict[str, object]]] = []

    def weighted_spy(**kwargs: object) -> WeightedSelection:
        calls.append(("weighted", kwargs))
        return real_weighted(**kwargs)  # type: ignore[arg-type]

    def uniform_spy(**kwargs: object) -> UniformSelection:
        calls.append(("uniform", kwargs))
        return real_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(complete_event, "select_weighted", weighted_spy)
    monkeypatch.setattr(complete_event, "select_uniform", uniform_spy)
    result = _select(law)

    assert [call[1]["stream_name"] for call in calls] == ["family", "orientation", "launch", "contact"]
    assert [call[0] for call in calls] == ["weighted", "weighted", "uniform", "weighted"]
    assert all(call[1]["root_seed"] == 0 for call in calls)
    assert all(call[1]["coupling_group_id"] == "paired-main" for call in calls)
    assert all(call[1]["event_ordinal"] == 0 for call in calls)
    assert all(
        call[1]["declared_streams"] == DeclaredStreamSet(("family", "orientation", "launch", "contact"))
        for call in calls
    )
    assert calls[1][1]["law"] == law.orientation_laws.law_for(result.family_id)
    assert result.family_id == "sz"


def test_degenerate_event_still_performs_one_logical_draw_per_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    law = _event_law(
        family_counts=(0, 0, 1, 0, 0),
        launch_bound=1,
        contact_counts=(1, 0),
    )
    calls: list[str] = []
    real_weighted = complete_event.select_weighted
    real_uniform = complete_event.select_uniform

    def weighted_spy(**kwargs: object) -> WeightedSelection:
        calls.append(str(kwargs["stream_name"]))
        return real_weighted(**kwargs)  # type: ignore[arg-type]

    def uniform_spy(**kwargs: object) -> UniformSelection:
        calls.append(str(kwargs["stream_name"]))
        return real_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(complete_event, "select_weighted", weighted_spy)
    monkeypatch.setattr(complete_event, "select_uniform", uniform_spy)
    result = _select(law, event_ordinal=9)

    assert calls == ["family", "orientation", "launch", "contact"]
    assert result.family_id == "o"
    assert result.geometry_id == "tetromino.o.00"
    assert result.launch_x == 0
    assert result.contact_id == "supported-v1"
    assert tuple(
        selection.draw.accepted_rejection_ordinal
        for selection in (result.family, result.orientation, result.launch, result.contact)
    ) == (0, 0, 0, 0)


def test_documented_complete_event_vector_is_fixed() -> None:
    result = _select(_event_law())
    assert result.root_seed == 0
    assert result.coupling_group_id == "paired-main"
    assert result.event_ordinal == 0
    assert result.family == WeightedSelection("family", "sz", SemanticDraw(3, 0))
    assert result.orientation == WeightedSelection(
        "orientation",
        "tetromino.sz.03",
        SemanticDraw(3, 0),
    )
    assert result.launch == UniformSelection("launch", SemanticDraw(4, 0))
    assert result.contact == WeightedSelection(
        "contact",
        "edge-first-contact-v1",
        SemanticDraw(1, 0),
    )
    assert (
        result.family_id,
        result.geometry_id,
        result.launch_x,
        result.contact_id,
    ) == ("sz", "tetromino.sz.03", 4, "edge-first-contact-v1")
    assert tuple(
        raw_u64(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name=stream,
            event_ordinal=0,
            rejection_ordinal=0,
        )
        for stream in TETROMINO_STREAM_SET.stream_names
    ) == (
        0x9FC97B3E13CEE41B,
        0xFFC7FB838D848799,
        0x40AF7280B937935A,
        0xCDCC6E52E762825F,
    )


def test_unequal_launch_bounds_share_candidate_tape_not_accepted_variate() -> None:
    future_word_before = raw_u64(
        root_seed=0,
        coupling_group_id="paired-main",
        stream_name="launch",
        event_ordinal=2,
        rejection_ordinal=0,
    )
    narrow = _select(_event_law(launch_bound=2), event_ordinal=1)
    wide = _select(_event_law(launch_bound=(1 << 63) + 1), event_ordinal=1)
    future_word_after = raw_u64(
        root_seed=0,
        coupling_group_id="paired-main",
        stream_name="launch",
        event_ordinal=2,
        rejection_ordinal=0,
    )

    assert narrow.family == wide.family
    assert narrow.orientation == wide.orientation
    assert narrow.contact == wide.contact
    assert narrow.launch == UniformSelection("launch", SemanticDraw(1, 0))
    assert wide.launch == UniformSelection("launch", SemanticDraw(8264810105833175493, 1))
    assert (
        raw_u64(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="launch",
            event_ordinal=1,
            rejection_ordinal=0,
        )
        == 0x853FE237A36163CC
    )
    assert (
        raw_u64(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="launch",
            event_ordinal=1,
            rejection_ordinal=1,
        )
        == 0x72B281009E3EB9C5
    )
    assert future_word_before == future_word_after == 0xD997D7678FD2D614


def test_result_constructor_rejects_cross_field_inconsistency() -> None:
    result = _select(_event_law())
    base = {
        "root_seed": result.root_seed,
        "coupling_group_id": result.coupling_group_id,
        "event_ordinal": result.event_ordinal,
        "law": result.law,
        "family": result.family,
        "orientation": result.orientation,
        "launch": result.launch,
        "contact": result.contact,
    }
    invalid_updates = (
        {"family": WeightedSelection("family", "i", SemanticDraw(3, 0))},
        {"orientation": WeightedSelection("orientation", "tetromino.o.00", SemanticDraw(0, 0))},
        {"launch": UniformSelection("launch", SemanticDraw(17, 0))},
        {"contact": WeightedSelection("family", "edge-first-contact-v1", SemanticDraw(1, 0))},
    )
    for update in invalid_updates:
        with pytest.raises(ValueError):
            TetrominoEventSelection(**(base | update))


def test_selector_rejects_malformed_delegated_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(complete_event, "select_weighted", lambda **_: object())
    with pytest.raises(AssertionError, match="malformed result"):
        _select(_event_law())


@pytest.mark.parametrize(
    ("bad_stage", "expected_calls"),
    [
        ("family", ["family"]),
        ("orientation", ["family", "orientation"]),
        ("launch", ["family", "orientation", "launch"]),
        ("contact", ["family", "orientation", "launch", "contact"]),
    ],
)
def test_well_typed_delegated_inconsistency_fails_at_its_stage(
    monkeypatch: pytest.MonkeyPatch,
    bad_stage: str,
    expected_calls: list[str],
) -> None:
    real_weighted = complete_event.select_weighted
    real_uniform = complete_event.select_uniform
    calls: list[str] = []

    def weighted_delegate(**kwargs: object) -> WeightedSelection:
        stream_name = str(kwargs["stream_name"])
        calls.append(stream_name)
        if stream_name == bad_stage == "family":
            return WeightedSelection("contact", "sz", SemanticDraw(3, 0))
        if stream_name == bad_stage == "orientation":
            return WeightedSelection("orientation", "tetromino.sz.00", SemanticDraw(3, 0))
        if stream_name == bad_stage == "contact":
            return WeightedSelection("contact", "supported-v1", SemanticDraw(1, 0))
        return real_weighted(**kwargs)  # type: ignore[arg-type]

    def uniform_delegate(**kwargs: object) -> UniformSelection:
        calls.append(str(kwargs["stream_name"]))
        if bad_stage == "launch":
            return UniformSelection("launch", SemanticDraw(17, 0))
        return real_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(complete_event, "select_weighted", weighted_delegate)
    monkeypatch.setattr(complete_event, "select_uniform", uniform_delegate)
    with pytest.raises(AssertionError, match="inconsistent with its law"):
        _select(_event_law())
    assert calls == expected_calls


def test_forged_nested_delegated_draw_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    forged_draw = object.__new__(SemanticDraw)
    object.__setattr__(forged_draw, "value", -1)
    object.__setattr__(forged_draw, "accepted_rejection_ordinal", 0)
    forged_selection = object.__new__(WeightedSelection)
    object.__setattr__(forged_selection, "stream_name", "family")
    object.__setattr__(forged_selection, "outcome_id", "i")
    object.__setattr__(forged_selection, "draw", forged_draw)
    monkeypatch.setattr(complete_event, "select_weighted", lambda **_: forged_selection)

    with pytest.raises(AssertionError, match="malformed result"):
        _select(_event_law())


def test_event_selector_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        select_event(0, "paired-main", 0, _event_law())  # type: ignore[misc]


def test_event_api_stays_behind_explicit_submodule_and_away_from_placement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = (
        "ConditionalWeightedLaw",
        "TETROMINO_CONTACT_ORDER",
        "TETROMINO_FAMILY_ORDER",
        "TETROMINO_STREAM_SET",
        "TetrominoEventLaw",
        "TetrominoEventSelection",
        "select_event",
    )
    for module in (tetris_ballistic, reference_engine, exact_selection):
        for name in names:
            assert not hasattr(module, name)

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("event selection must not place a piece")

    monkeypatch.setattr(placement_engine, "place_one", forbidden)
    assert _select(_event_law()).geometry_id == "tetromino.sz.03"


def test_hash_seed_does_not_change_event_order_or_selection() -> None:
    script = """
import json
from tetris_ballistic.engine.event import (
    ConditionalWeightedLaw, TETROMINO_CONTACT_ORDER, TETROMINO_FAMILY_ORDER,
    TETROMINO_STREAM_SET, TetrominoEventLaw, select_event,
)
from tetris_ballistic.engine.selection import ExactWeightedLaw, UniformIntegerLaw
from tetris_ballistic.models import FAMILY_ORIENTATION_IDS
orientation_laws = ConditionalWeightedLaw(
    TETROMINO_FAMILY_ORDER,
    tuple(ExactWeightedLaw(FAMILY_ORIENTATION_IDS[f], (1,) * len(FAMILY_ORIENTATION_IDS[f]))
          for f in TETROMINO_FAMILY_ORDER),
)
law = TetrominoEventLaw(
    ExactWeightedLaw(TETROMINO_FAMILY_ORDER, (1, 1, 1, 1, 1)),
    orientation_laws,
    UniformIntegerLaw(17),
    ExactWeightedLaw(TETROMINO_CONTACT_ORDER, (1, 1)),
)
result = select_event(root_seed=0, coupling_group_id="paired-main", event_ordinal=0, law=law)
print(json.dumps([
    TETROMINO_FAMILY_ORDER, TETROMINO_CONTACT_ORDER, TETROMINO_STREAM_SET.stream_names,
    result.family_id, result.geometry_id, result.launch_x, result.contact_id,
]))
"""
    project_root = Path(__file__).resolve().parents[1]
    outputs = []
    for hash_seed in ("0", "1", "123456"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            cwd=project_root,
            text=True,
            env=env,
        )
        outputs.append(json.loads(completed.stdout))
    assert (
        outputs
        == [
            [
                ["i", "lj", "o", "sz", "t"],
                ["supported-v1", "edge-first-contact-v1"],
                ["family", "orientation", "launch", "contact"],
                "sz",
                "tetromino.sz.03",
                4,
                "edge-first-contact-v1",
            ]
        ]
        * 3
    )


@pytest.mark.slow
def test_ten_thousand_events_match_an_independent_composition_oracle() -> None:
    orientation_counts = {
        family_id: tuple(range(1, len(_EXPECTED_ORIENTATION_IDS[family_id]) + 1))
        for family_id in TETROMINO_FAMILY_ORDER
    }
    law = _event_law(
        family_counts=(1, 2, 3, 4, 5),
        orientation_counts=orientation_counts,
        launch_bound=(1 << 63) + 1,
        contact_counts=(2, 1),
    )
    seen_families: set[str] = set()
    seen_orientations: set[str] = set()
    seen_contacts: set[str] = set()
    saw_rejection = False

    for event_ordinal in range(10_000):
        result = _select(law, event_ordinal=event_ordinal)
        expected_family, family_draw = _manual_weighted(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="family",
            event_ordinal=event_ordinal,
            law=law.family_law,
        )
        orientation_law = law.orientation_laws.law_for(expected_family)
        expected_orientation, orientation_draw = _manual_weighted(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="orientation",
            event_ordinal=event_ordinal,
            law=orientation_law,
        )
        launch_draw = _manual_bounded(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="launch",
            event_ordinal=event_ordinal,
            upper_bound=law.launch_law.upper_bound,
        )
        expected_contact, contact_draw = _manual_weighted(
            root_seed=0,
            coupling_group_id="paired-main",
            stream_name="contact",
            event_ordinal=event_ordinal,
            law=law.contact_law,
        )

        assert result.family == WeightedSelection("family", expected_family, family_draw)
        assert result.orientation == WeightedSelection(
            "orientation",
            expected_orientation,
            orientation_draw,
        )
        assert result.launch == UniformSelection("launch", launch_draw)
        assert result.contact == WeightedSelection("contact", expected_contact, contact_draw)
        seen_families.add(result.family_id)
        seen_orientations.add(result.geometry_id)
        seen_contacts.add(result.contact_id)
        saw_rejection |= result.launch.draw.accepted_rejection_ordinal > 0

    assert seen_families == set(TETROMINO_FAMILY_ORDER)
    assert seen_orientations == {orientation_id for ids in _EXPECTED_ORIENTATION_IDS.values() for orientation_id in ids}
    assert seen_contacts == set(TETROMINO_CONTACT_ORDER)
    assert saw_rejection
