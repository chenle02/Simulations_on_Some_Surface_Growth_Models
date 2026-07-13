"""Certification tests for provisional exact law and stream selection records."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.rng as semantic_rng
import tetris_ballistic.engine.selection as exact_selection
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.selection import (
    DeclaredStreamSet,
    ExactWeightedLaw,
    UniformIntegerLaw,
    UniformSelection,
    WeightedSelection,
    select_uniform,
    select_weighted,
)

_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1

_FOUR_STREAMS = DeclaredStreamSet(("family", "orientation", "launch", "contact"))
_BASE_ADDRESS = {
    "root_seed": 0,
    "coupling_group_id": "paired-main",
    "event_ordinal": 0,
}


class _IntSubclass(int):
    pass


class _StringSubclass(str):
    pass


class _TupleSubclass(tuple):
    pass


class _CoercibleInteger:
    def __int__(self) -> int:
        return 1


def _forged_semantic_draw(value: int, rejection: int) -> SemanticDraw:
    draw = object.__new__(SemanticDraw)
    object.__setattr__(draw, "value", value)
    object.__setattr__(draw, "accepted_rejection_ordinal", rejection)
    return draw


def _independent_weighted_selection(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    outcome_ids: tuple[str, ...],
    counts: tuple[int, ...],
) -> tuple[int, str, int]:
    total = sum(counts)
    quotient = _U64_SPACE // total
    threshold = quotient * total
    rejection = 0
    while True:
        word = semantic_rng.raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection,
        )
        if word < threshold:
            uniform_value = word // quotient
            cumulative = 0
            for index, count in enumerate(counts):
                cumulative += count
                if uniform_value < cumulative:
                    return index, outcome_ids[index], rejection
            raise AssertionError("independent interval search did not terminate")
        rejection += 1


def test_weighted_law_defensively_freezes_order_and_zero_slots() -> None:
    outcomes = ["i", "lj", "o", "sz", "t"]
    counts = [1, 0, 0, 0, 1]
    law = ExactWeightedLaw(outcomes, counts)
    outcomes.reverse()
    counts[:] = [1]
    assert law.outcome_ids == ("i", "lj", "o", "sz", "t")
    assert law.counts == (1, 0, 0, 0, 1)
    assert law.positive_outcome_ids == ("i", "t")
    assert law.total_count == 2


def test_weighted_law_keeps_exact_unicode_code_points_without_normalization() -> None:
    law = ExactWeightedLaw(("é", "e\u0301"), (1, 1))
    assert law.outcome_ids == ("é", "e\u0301")
    assert law.outcome_ids[0].encode("utf-8") != law.outcome_ids[1].encode("utf-8")


def test_weighted_law_allows_the_exact_maximum_total() -> None:
    law = ExactWeightedLaw(("bulk", "last"), (_U64_MAX, 1))
    assert law.total_count == _U64_SPACE


def test_weighted_law_is_hashable_slotted_and_immutable() -> None:
    law = ExactWeightedLaw(("left", "right"), (1, 1))
    assert hash(law) == hash(ExactWeightedLaw(("left", "right"), (1, 1)))
    assert not hasattr(law, "__dict__")
    with pytest.raises(FrozenInstanceError):
        law.counts = (1, 0)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("outcome_ids", "counts", "error"),
    (
        ((), (), ValueError),
        ([], [1], ValueError),
        ({"a": 1}, [1], TypeError),
        (_TupleSubclass(("a",)), [1], TypeError),
        (("a",), {"a": 1}, TypeError),
        (("a",), (1, 1), ValueError),
        (("a", "a"), (1, 1), ValueError),
        (("",), (1,), ValueError),
        (("\ud800",), (1,), ValueError),
        ((1,), (1,), TypeError),
        ((_StringSubclass("a"),), (1,), TypeError),
    ),
)
def test_weighted_law_rejects_malformed_outcome_records(
    outcome_ids: object,
    counts: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        ExactWeightedLaw(outcome_ids, counts)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("counts", "error"),
    (
        ((), ValueError),
        ({"a": 1}, TypeError),
        (_TupleSubclass((1,)), TypeError),
        ((True,), TypeError),
        ((1.0,), TypeError),
        ((_IntSubclass(1),), TypeError),
        ((Fraction(1, 1),), TypeError),
        ((_CoercibleInteger(),), TypeError),
        ((-1,), ValueError),
        ((0,), ValueError),
        ((2,), ValueError),
        ((2, 4), ValueError),
        ((_U64_SPACE + 1,), ValueError),
        ((_U64_SPACE, 1), ValueError),
    ),
)
def test_weighted_law_rejects_noncanonical_counts(
    counts: object,
    error: type[Exception],
) -> None:
    outcomes = tuple(f"outcome-{index}" for index in range(len(counts)))
    with pytest.raises(error):
        ExactWeightedLaw(outcomes, counts)  # type: ignore[arg-type]


def test_declared_stream_set_defensively_freezes_exact_order() -> None:
    names = ["family", "orientation", "launch", "contact"]
    declared = DeclaredStreamSet(names)
    names.reverse()
    assert declared.stream_names == ("family", "orientation", "launch", "contact")
    assert declared != DeclaredStreamSet(tuple(reversed(declared.stream_names)))


def test_declared_stream_set_is_hashable_slotted_and_immutable() -> None:
    declared = DeclaredStreamSet(("launch", "tie"))
    assert hash(declared) == hash(DeclaredStreamSet(("launch", "tie")))
    assert not hasattr(declared, "__dict__")
    with pytest.raises(FrozenInstanceError):
        declared.stream_names = ("launch",)  # type: ignore[misc]


@pytest.mark.parametrize(
    ("names", "error"),
    (
        ((), ValueError),
        ([], ValueError),
        ({"family", "launch"}, TypeError),
        (_TupleSubclass(("family",)), TypeError),
        (("family", "family"), ValueError),
        (("",), ValueError),
        (("\ud800",), ValueError),
        ((1,), TypeError),
        ((_StringSubclass("family"),), TypeError),
    ),
)
def test_declared_stream_set_rejects_malformed_records(
    names: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        DeclaredStreamSet(names)  # type: ignore[arg-type]


@pytest.mark.parametrize("upper_bound", (1, 2, (1 << 63) + 1, _U64_SPACE))
def test_uniform_integer_law_accepts_its_exact_domain(upper_bound: int) -> None:
    law = UniformIntegerLaw(upper_bound)
    assert law.upper_bound == upper_bound
    assert hash(law) == hash(UniformIntegerLaw(upper_bound))


@pytest.mark.parametrize(
    "upper_bound",
    (True, 1.0, _IntSubclass(1), Fraction(1, 1), _CoercibleInteger(), 0, -1, _U64_SPACE + 1),
)
def test_uniform_integer_law_rejects_invalid_bounds(upper_bound: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        UniformIntegerLaw(upper_bound)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("stream_name", "outcome_ids", "counts", "expected_index", "expected_outcome"),
    (
        ("family", ("slot-0", "slot-1", "slot-2", "slot-3", "slot-4"), (1, 1, 1, 1, 1), 3, "slot-3"),
        ("contact", ("zero-a", "bulk", "tail", "zero-b"), (0, 3, 1, 0), 2, "tail"),
        (
            "orientation",
            tuple(f"orientation-{index}" for index in range(8)),
            (1, 1, 1, 1, 1, 1, 1, 1),
            7,
            "orientation-7",
        ),
    ),
)
def test_documented_id_level_selection_vectors_are_fixed(
    stream_name: str,
    outcome_ids: tuple[str, ...],
    counts: tuple[int, ...],
    expected_index: int,
    expected_outcome: str,
) -> None:
    result = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=_FOUR_STREAMS,
        stream_name=stream_name,
        law=ExactWeightedLaw(outcome_ids, counts),
    )
    assert type(result) is WeightedSelection
    assert result.stream_name == stream_name
    assert result.selected_index == expected_index
    assert result.outcome_id == expected_outcome
    assert result.draw == SemanticDraw(expected_index, 0)


def test_documented_uniform_selection_vector_is_fixed() -> None:
    result = select_uniform(
        root_seed=0x0123456789ABCDEFFEDCBA9876543210,
        coupling_group_id="c0e-pure-i",
        event_ordinal=42,
        declared_streams=DeclaredStreamSet(("launch",)),
        stream_name="launch",
        law=UniformIntegerLaw(17),
    )
    assert type(result) is UniformSelection
    assert result.stream_name == "launch"
    assert result.value == 11
    assert result.draw == SemanticDraw(11, 0)


def test_documented_rejection_selection_vector_retains_draw_metadata() -> None:
    result = select_uniform(
        root_seed=0x0123456789ABCDEFFEDCBA9876543210,
        coupling_group_id="rejection-test",
        event_ordinal=0,
        declared_streams=DeclaredStreamSet(("launch",)),
        stream_name="launch",
        law=UniformIntegerLaw((1 << 63) + 1),
    )
    assert result.value == 7255411166493364322
    assert result.draw.accepted_rejection_ordinal == 1


def test_same_total_shares_rejection_address_but_maps_by_explicit_law() -> None:
    declared = DeclaredStreamSet(("family",))
    left_heavy = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=declared,
        stream_name="family",
        law=ExactWeightedLaw(("left", "right"), (4, 1)),
    )
    right_heavy = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=declared,
        stream_name="family",
        law=ExactWeightedLaw(("left", "right"), (1, 4)),
    )
    assert left_heavy.draw == SemanticDraw(0, 0)
    assert right_heavy.draw == SemanticDraw(1, 0)
    assert left_heavy.draw.accepted_rejection_ordinal == right_heavy.draw.accepted_rejection_ordinal == 0
    assert left_heavy.outcome_id == "left"
    assert right_heavy.outcome_id == "right"


def test_same_total_and_counts_but_different_order_is_a_different_executable_law() -> None:
    first = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=DeclaredStreamSet(("family",)),
        stream_name="family",
        law=ExactWeightedLaw(("a", "b", "c", "d", "e"), (1, 1, 1, 1, 1)),
    )
    second = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=DeclaredStreamSet(("family",)),
        stream_name="family",
        law=ExactWeightedLaw(("e", "d", "c", "b", "a"), (1, 1, 1, 1, 1)),
    )
    assert first.draw == second.draw == SemanticDraw(3, 0)
    assert first.outcome_id == "d"
    assert second.outcome_id == "b"


def test_different_bounds_share_candidate_tape_but_may_accept_different_ordinals() -> None:
    address = {
        "root_seed": 0x0123456789ABCDEFFEDCBA9876543210,
        "coupling_group_id": "rejection-test",
        "event_ordinal": 0,
        "declared_streams": DeclaredStreamSet(("launch",)),
        "stream_name": "launch",
    }
    bound_two = select_uniform(**address, law=UniformIntegerLaw(2))
    wide_bound = select_uniform(**address, law=UniformIntegerLaw((1 << 63) + 1))
    full_bound = select_uniform(**address, law=UniformIntegerLaw(_U64_SPACE))
    assert bound_two.value == 1
    assert wide_bound.value == 7255411166493364322
    assert full_bound.value == 16291224046481783505
    assert bound_two.draw.accepted_rejection_ordinal == 0
    assert wide_bound.draw.accepted_rejection_ordinal == 1
    assert full_bound.draw.accepted_rejection_ordinal == 0
    assert (
        semantic_rng.raw_u64(
            root_seed=address["root_seed"],
            coupling_group_id=address["coupling_group_id"],
            stream_name=address["stream_name"],
            event_ordinal=address["event_ordinal"],
            rejection_ordinal=0,
        )
        == 0xE2160DF4A6D93AD1
    )


def test_declared_stream_order_does_not_change_a_named_one_stream_draw() -> None:
    law = ExactWeightedLaw(("a", "b", "c", "d", "e"), (1, 1, 1, 1, 1))
    forward = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=DeclaredStreamSet(("family", "contact")),
        stream_name="family",
        law=law,
    )
    reverse = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=DeclaredStreamSet(("contact", "family")),
        stream_name="family",
        law=law,
    )
    assert forward == reverse


def test_degenerate_weighted_law_still_reads_one_raw_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    original = semantic_rng.raw_u64

    def spy(**kwargs: object) -> int:
        calls.append(dict(kwargs))
        return original(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(semantic_rng, "raw_u64", spy)
    result = select_weighted(
        root_seed=1,
        coupling_group_id="degenerate",
        event_ordinal=9,
        declared_streams=DeclaredStreamSet(("contact",)),
        stream_name="contact",
        law=ExactWeightedLaw(("fixed",), (1,)),
    )
    assert result == WeightedSelection("contact", "fixed", SemanticDraw(0, 0))
    assert len(calls) == 1
    assert calls[0]["stream_name"] == "contact"
    assert calls[0]["rejection_ordinal"] == 0


def test_degenerate_uniform_law_still_reads_one_raw_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    original = semantic_rng.raw_u64

    def spy(**kwargs: object) -> int:
        calls.append(dict(kwargs))
        return original(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(semantic_rng, "raw_u64", spy)
    result = select_uniform(
        root_seed=1,
        coupling_group_id="degenerate",
        event_ordinal=9,
        declared_streams=DeclaredStreamSet(("launch",)),
        stream_name="launch",
        law=UniformIntegerLaw(1),
    )
    assert result == UniformSelection("launch", SemanticDraw(0, 0))
    assert len(calls) == 1


def test_maximum_total_weighted_law_uses_the_raw_word_without_rejection() -> None:
    result = select_weighted(
        **_BASE_ADDRESS,
        declared_streams=DeclaredStreamSet(("family",)),
        stream_name="family",
        law=ExactWeightedLaw(("bulk", "last"), (_U64_MAX, 1)),
    )
    assert result.draw.accepted_rejection_ordinal == 0
    assert result.selected_index == 0
    assert result.outcome_id == "bulk"


def test_randomized_id_interval_differential_against_independent_wrapper() -> None:
    outcome_ids = ("zero", "one", "two", "three", "four", "five")
    counts = (0, 1, 2, 0, 3, 5)
    law = ExactWeightedLaw(outcome_ids, counts)
    declared = DeclaredStreamSet(("family",))
    for root_seed in range(257):
        event_ordinal = root_seed * 7919
        expected = _independent_weighted_selection(
            root_seed=root_seed,
            coupling_group_id="differential",
            stream_name="family",
            event_ordinal=event_ordinal,
            outcome_ids=outcome_ids,
            counts=counts,
        )
        actual = select_weighted(
            root_seed=root_seed,
            coupling_group_id="differential",
            event_ordinal=event_ordinal,
            declared_streams=declared,
            stream_name="family",
            law=law,
        )
        assert (actual.selected_index, actual.outcome_id, actual.draw.accepted_rejection_ordinal) == expected


@pytest.mark.parametrize(
    ("root_seed", "coupling_group_id", "event_ordinal", "stream_name", "error"),
    (
        (True, "group", 0, "family", TypeError),
        (-1, "group", 0, "family", ValueError),
        (_U128_MAX + 1, "group", 0, "family", ValueError),
        (0, _StringSubclass("group"), 0, "family", TypeError),
        (0, "", 0, "family", ValueError),
        (0, "\ud800", 0, "family", ValueError),
        (0, "group", True, "family", TypeError),
        (0, "group", -1, "family", ValueError),
        (0, "group", _U64_SPACE, "family", ValueError),
        (0, "group", 0, _StringSubclass("family"), TypeError),
        (0, "group", 0, "", ValueError),
        (0, "group", 0, "\ud800", ValueError),
    ),
)
def test_selector_rejects_malformed_addresses_before_rng(
    monkeypatch: pytest.MonkeyPatch,
    root_seed: object,
    coupling_group_id: object,
    event_ordinal: object,
    stream_name: object,
    error: type[Exception],
) -> None:
    calls = 0

    def forbidden(**_: object) -> SemanticDraw:
        nonlocal calls
        calls += 1
        return SemanticDraw(0, 0)

    monkeypatch.setattr(exact_selection.semantic_rng, "categorical_index", forbidden)
    with pytest.raises(error):
        select_weighted(
            root_seed=root_seed,  # type: ignore[arg-type]
            coupling_group_id=coupling_group_id,  # type: ignore[arg-type]
            event_ordinal=event_ordinal,  # type: ignore[arg-type]
            declared_streams=DeclaredStreamSet(("family",)),
            stream_name=stream_name,  # type: ignore[arg-type]
            law=ExactWeightedLaw(("only",), (1,)),
        )
    assert calls == 0


@pytest.mark.parametrize("selector", (select_weighted, select_uniform))
def test_undeclared_stream_fails_before_rng(
    monkeypatch: pytest.MonkeyPatch,
    selector: object,
) -> None:
    calls = 0

    def forbidden(**_: object) -> SemanticDraw:
        nonlocal calls
        calls += 1
        return SemanticDraw(0, 0)

    law: object
    if selector is select_weighted:
        monkeypatch.setattr(exact_selection.semantic_rng, "categorical_index", forbidden)
        law = ExactWeightedLaw(("only",), (1,))
    else:
        monkeypatch.setattr(exact_selection.semantic_rng, "uniform_below", forbidden)
        law = UniformIntegerLaw(1)
    with pytest.raises(ValueError, match="not present"):
        selector(  # type: ignore[operator]
            **_BASE_ADDRESS,
            declared_streams=DeclaredStreamSet(("launch",)),
            stream_name="contact",
            law=law,
        )
    assert calls == 0


def test_forged_weighted_law_fails_before_rng(monkeypatch: pytest.MonkeyPatch) -> None:
    forged = object.__new__(ExactWeightedLaw)
    object.__setattr__(forged, "outcome_ids", ("a", "b"))
    object.__setattr__(forged, "counts", (2, 2))
    calls = 0

    def forbidden(**_: object) -> SemanticDraw:
        nonlocal calls
        calls += 1
        return SemanticDraw(0, 0)

    monkeypatch.setattr(exact_selection.semantic_rng, "categorical_index", forbidden)
    with pytest.raises(ValueError, match="greatest common divisor"):
        select_weighted(
            **_BASE_ADDRESS,
            declared_streams=DeclaredStreamSet(("family",)),
            stream_name="family",
            law=forged,
        )
    assert calls == 0


def test_forged_declared_stream_set_fails_before_rng(monkeypatch: pytest.MonkeyPatch) -> None:
    forged = object.__new__(DeclaredStreamSet)
    object.__setattr__(forged, "stream_names", ("family", "family"))
    calls = 0

    def forbidden(**_: object) -> SemanticDraw:
        nonlocal calls
        calls += 1
        return SemanticDraw(0, 0)

    monkeypatch.setattr(exact_selection.semantic_rng, "categorical_index", forbidden)
    with pytest.raises(ValueError, match="unique"):
        select_weighted(
            **_BASE_ADDRESS,
            declared_streams=forged,
            stream_name="family",
            law=ExactWeightedLaw(("only",), (1,)),
        )
    assert calls == 0


@pytest.mark.parametrize(
    "delegated",
    (
        object(),
        SemanticDraw(2, 0),
        SemanticDraw(1, 0),
        _forged_semantic_draw(-1, 0),
        _forged_semantic_draw(0, -1),
    ),
)
def test_weighted_selector_rejects_structurally_invalid_delegated_results(
    monkeypatch: pytest.MonkeyPatch,
    delegated: object,
) -> None:
    monkeypatch.setattr(exact_selection.semantic_rng, "categorical_index", lambda **_: delegated)
    law = ExactWeightedLaw(("positive", "zero"), (1, 0))
    with pytest.raises(AssertionError, match="RNG returned"):
        select_weighted(
            **_BASE_ADDRESS,
            declared_streams=DeclaredStreamSet(("family",)),
            stream_name="family",
            law=law,
        )


@pytest.mark.parametrize(
    "delegated",
    (object(), SemanticDraw(3, 0), _forged_semantic_draw(-1, 0), _forged_semantic_draw(0, -1)),
)
def test_uniform_selector_rejects_structurally_invalid_delegated_results(
    monkeypatch: pytest.MonkeyPatch,
    delegated: object,
) -> None:
    monkeypatch.setattr(exact_selection.semantic_rng, "uniform_below", lambda **_: delegated)
    with pytest.raises(AssertionError, match="RNG returned"):
        select_uniform(
            **_BASE_ADDRESS,
            declared_streams=DeclaredStreamSet(("launch",)),
            stream_name="launch",
            law=UniformIntegerLaw(3),
        )


@pytest.mark.parametrize(
    ("declared_streams", "law", "error"),
    (
        (("family",), ExactWeightedLaw(("a",), (1,)), TypeError),
        (DeclaredStreamSet(("family",)), ("a",), TypeError),
    ),
)
def test_weighted_selector_requires_exact_record_types(
    declared_streams: object,
    law: object,
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        select_weighted(
            **_BASE_ADDRESS,
            declared_streams=declared_streams,  # type: ignore[arg-type]
            stream_name="family",
            law=law,  # type: ignore[arg-type]
        )


def test_selection_records_defensively_copy_draws_and_are_immutable() -> None:
    draw = SemanticDraw(1, 2)
    weighted = WeightedSelection("family", "t", draw)
    uniform = UniformSelection("launch", draw)
    object.__setattr__(draw, "value", 9)
    assert weighted.draw == SemanticDraw(1, 2)
    assert uniform.draw == SemanticDraw(1, 2)
    assert hash(weighted)
    assert hash(uniform)
    assert not hasattr(weighted, "__dict__")
    assert not hasattr(uniform, "__dict__")
    with pytest.raises(FrozenInstanceError):
        weighted.outcome_id = "i"  # type: ignore[misc]


def test_selectors_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        select_weighted(  # type: ignore[misc]
            0,
            "group",
            0,
            DeclaredStreamSet(("family",)),
            "family",
            ExactWeightedLaw(("only",), (1,)),
        )
    with pytest.raises(TypeError):
        select_uniform(  # type: ignore[misc]
            0,
            "group",
            0,
            DeclaredStreamSet(("launch",)),
            "launch",
            UniformIntegerLaw(1),
        )


def test_selection_api_stays_behind_its_explicit_submodule() -> None:
    names = (
        "DeclaredStreamSet",
        "ExactWeightedLaw",
        "UniformIntegerLaw",
        "UniformSelection",
        "WeightedSelection",
        "select_uniform",
        "select_weighted",
    )
    for root in (tetris_ballistic, reference_engine):
        for name in names:
            assert not hasattr(root, name)


def test_composite_and_named_law_apis_stay_out_of_one_stream_module() -> None:
    for name in (
        "ConditionalWeightedLaw",
        "TetrominoEventLaw",
        "TetrominoEventSelection",
        "select_declared_streams",
        "select_event",
        "TETROMINO_CONTACT_ORDER",
        "TETROMINO_FAMILY_ORDER",
        "TETROMINO_STREAM_SET",
        "ONE_CELL_BD_STREAM_SET",
        "FAMILY_RDSR_STREAM_SET",
    ):
        assert not hasattr(exact_selection, name)


def test_hash_seed_does_not_change_explicit_order_or_selection() -> None:
    script = """
import json
from tetris_ballistic.engine.selection import DeclaredStreamSet, ExactWeightedLaw, select_weighted
law = ExactWeightedLaw(("z", "a", "m", "q", "b"), (1, 1, 1, 1, 1))
result = select_weighted(
    root_seed=0,
    coupling_group_id="paired-main",
    event_ordinal=0,
    declared_streams=DeclaredStreamSet(("contact", "family")),
    stream_name="family",
    law=law,
)
print(json.dumps([law.outcome_ids, law.counts, result.selected_index, result.outcome_id]))
"""
    outputs = []
    project_root = Path(__file__).resolve().parents[1]
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
    assert outputs == [[["z", "a", "m", "q", "b"], [1, 1, 1, 1, 1], 3, "q"]] * 3
