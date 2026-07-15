"""Certification tests for the provisional PRE one-cell coupled selector."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.event as tetromino_event
import tetris_ballistic.engine.one_cell as one_cell_transition
import tetris_ballistic.engine.one_cell_coupling as one_cell_coupling
import tetris_ballistic.engine.rng as semantic_rng
import tetris_ballistic.engine.selection as exact_selection
from tetris_ballistic.engine.one_cell_coupling import (
    ONE_CELL_CONTACT_DENOMINATOR,
    ONE_CELL_COUPLING_GROUP_ID,
    ONE_CELL_STICKINESS_THRESHOLDS,
    ONE_CELL_STREAM_SET,
    OneCellCoupledEventSelection,
    select_one_cell_coupled_event,
)
from tetris_ballistic.engine.rng import SemanticDraw, derive_stream_key, raw_u64
from tetris_ballistic.engine.selection import DeclaredStreamSet, UniformIntegerLaw, UniformSelection

_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1

_EVENT_ZERO_CAMPAIGN_LAUNCHES = (
    (32, 13),
    (50, 21),
    (64, 27),
    (80, 34),
    (100, 43),
    (128, 55),
    (150, 65),
    (200, 87),
    (250, 108),
    (256, 111),
    (300, 130),
    (400, 174),
    (500, 217),
    (512, 222),
    (1024, 445),
)

_CONTACT_BOUNDARY_VECTORS = (
    (23, 0, 0x019AB06E6D647A86),
    (153, 1, 0x043DB201A9973A5D),
    (3, 2, 0x066653BC2AA19546),
    (55, 4, 0x0BFB25192B17F92E),
    (24, 5, 0x0F3558266A1ECB4C),
    (1, 9, 0x1918F1660387FA79),
    (42, 10, 0x19E67647A5038BA7),
    (6, 24, 0x3F52C476D5D5F065),
    (41, 25, 0x41E28830E2FACF93),
    (45, 49, 0x7DAAF3E15F89F819),
    (216, 50, 0x81E81F92C924DD8F),
    (43, 99, 0xFED165AE9ECF81FF),
)


class _IntSubclass(int):
    pass


def _manual_bounded(
    *,
    root_seed: int,
    stream_name: str,
    event_ordinal: int,
    upper_bound: int,
) -> SemanticDraw:
    """Map independently certified raw words without using selection helpers."""

    quotient = _U64_SPACE // upper_bound
    threshold = quotient * upper_bound
    rejection = 0
    while True:
        word = raw_u64(
            root_seed=root_seed,
            coupling_group_id="pre-one-cell-discovery-v1",
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection,
        )
        if word < threshold:
            return SemanticDraw(word // quotient, rejection)
        rejection += 1


def _select(*, event_ordinal: int = 0, width: int = 64) -> OneCellCoupledEventSelection:
    return select_one_cell_coupled_event(
        root_seed=0,
        event_ordinal=event_ordinal,
        width=width,
    )


def _forged_uniform_selection(*, stream_name: str, value: object, rejection: object = 0) -> UniformSelection:
    draw = object.__new__(SemanticDraw)
    object.__setattr__(draw, "value", value)
    object.__setattr__(draw, "accepted_rejection_ordinal", rejection)
    selection = object.__new__(UniformSelection)
    object.__setattr__(selection, "stream_name", stream_name)
    object.__setattr__(selection, "draw", draw)
    return selection


def test_ratified_contract_constants_and_public_surface_are_exact() -> None:
    assert ONE_CELL_COUPLING_GROUP_ID == "pre-one-cell-discovery-v1"
    assert ONE_CELL_STREAM_SET == DeclaredStreamSet(("launch", "contact"))
    assert ONE_CELL_CONTACT_DENOMINATOR == 100
    assert ONE_CELL_STICKINESS_THRESHOLDS == (0, 1, 2, 5, 10, 25, 50, 100)
    assert one_cell_coupling.__all__ == [
        "ONE_CELL_CONTACT_DENOMINATOR",
        "ONE_CELL_COUPLING_GROUP_ID",
        "ONE_CELL_STICKINESS_THRESHOLDS",
        "ONE_CELL_STREAM_SET",
        "OneCellCoupledEventSelection",
        "select_one_cell_coupled_event",
    ]


def test_documented_root_zero_event_zero_vector_is_fixed() -> None:
    assert derive_stream_key(0, ONE_CELL_COUPLING_GROUP_ID, "launch") == (
        0x81BA8E755EA8A360,
        0xF829A74D482F4EBB,
    )
    assert derive_stream_key(0, ONE_CELL_COUPLING_GROUP_ID, "contact") == (
        0x6C00B0C4102C9848,
        0x4373AA5DF7EF12BD,
    )
    assert (
        raw_u64(
            root_seed=0,
            coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
            stream_name="launch",
            event_ordinal=0,
            rejection_ordinal=0,
        )
        == 0x6F7A7D3D95AA5E68
    )
    assert (
        raw_u64(
            root_seed=0,
            coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
            stream_name="contact",
            event_ordinal=0,
            rejection_ordinal=0,
        )
        == 0xCBF5C12A6FEE559E
    )

    result = _select()
    assert result == OneCellCoupledEventSelection(
        root_seed=0,
        event_ordinal=0,
        width=64,
        launch=UniformSelection("launch", SemanticDraw(27, 0)),
        contact=UniformSelection("contact", SemanticDraw(79, 0)),
    )
    assert result.coupling_group_id == ONE_CELL_COUPLING_GROUP_ID
    assert result.stream_names == ("launch", "contact")
    assert result.launch_x == 27
    assert result.contact_value == 79
    assert result.sticky_by_threshold == (False, False, False, False, False, False, False, True)
    assert result.arm_decisions == tuple(zip(ONE_CELL_STICKINESS_THRESHOLDS, result.sticky_by_threshold))


@pytest.mark.parametrize(("width", "expected_launch"), _EVENT_ZERO_CAMPAIGN_LAUNCHES)
def test_event_zero_launch_vector_covers_every_planned_campaign_width(width: int, expected_launch: int) -> None:
    result = _select(width=width)
    assert result.launch == UniformSelection("launch", SemanticDraw(expected_launch, 0))
    assert result.contact == UniformSelection("contact", SemanticDraw(79, 0))


@pytest.mark.parametrize(("event_ordinal", "expected_contact", "expected_raw"), _CONTACT_BOUNDARY_VECTORS)
def test_contact_vectors_pin_strict_threshold_boundaries(
    event_ordinal: int,
    expected_contact: int,
    expected_raw: int,
) -> None:
    assert (
        raw_u64(
            root_seed=0,
            coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
            stream_name="contact",
            event_ordinal=event_ordinal,
            rejection_ordinal=0,
        )
        == expected_raw
    )
    result = _select(event_ordinal=event_ordinal)
    expected_flags = tuple(expected_contact < threshold for threshold in ONE_CELL_STICKINESS_THRESHOLDS)
    assert result.contact == UniformSelection("contact", SemanticDraw(expected_contact, 0))
    assert result.sticky_by_threshold == expected_flags
    assert not result.sticky_by_threshold[0]
    assert result.sticky_by_threshold[-1]
    assert all(left <= right for left, right in zip(expected_flags, expected_flags[1:]))


def test_every_contact_integer_has_exact_nested_arm_decisions_and_one_shared_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contact_value = 0
    calls: list[dict[str, object]] = []

    def deterministic_delegate(**kwargs: object) -> UniformSelection:
        calls.append(kwargs)
        if kwargs["stream_name"] == "launch":
            return UniformSelection("launch", SemanticDraw(2, 0))
        return UniformSelection("contact", SemanticDraw(contact_value, 0))

    monkeypatch.setattr(one_cell_coupling, "select_uniform", deterministic_delegate)
    sticky_counts = [0] * len(ONE_CELL_STICKINESS_THRESHOLDS)
    observed_patterns: set[tuple[bool, ...]] = set()
    for value in range(100):
        contact_value = value
        result = _select(width=3)
        expected = tuple(value < threshold for threshold in ONE_CELL_STICKINESS_THRESHOLDS)
        assert result.contact_value == value
        assert result.sticky_by_threshold == expected
        assert all(left <= right for left, right in zip(expected, expected[1:]))
        sticky_counts = [count + int(flag) for count, flag in zip(sticky_counts, expected)]
        observed_patterns.add(expected)

    assert sticky_counts == list(ONE_CELL_STICKINESS_THRESHOLDS)
    assert observed_patterns == {
        tuple(value < threshold for threshold in ONE_CELL_STICKINESS_THRESHOLDS) for value in range(100)
    }
    assert len(observed_patterns) == 7
    assert len(calls) == 200
    assert [call["stream_name"] for call in calls] == ["launch", "contact"] * 100


def test_selector_uses_exact_two_call_schedule(monkeypatch: pytest.MonkeyPatch) -> None:
    real_select_uniform = one_cell_coupling.select_uniform
    calls: list[dict[str, object]] = []

    def spy(**kwargs: object) -> UniformSelection:
        calls.append(kwargs)
        return real_select_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(one_cell_coupling, "select_uniform", spy)
    result = select_one_cell_coupled_event(
        root_seed=0x0123456789ABCDEFFEDCBA9876543210,
        event_ordinal=42,
        width=257,
    )

    assert type(result) is OneCellCoupledEventSelection
    assert len(calls) == 2
    assert [call["stream_name"] for call in calls] == ["launch", "contact"]
    assert [call["law"] for call in calls] == [UniformIntegerLaw(257), UniformIntegerLaw(100)]
    assert all(call["root_seed"] == 0x0123456789ABCDEFFEDCBA9876543210 for call in calls)
    assert all(call["coupling_group_id"] == ONE_CELL_COUPLING_GROUP_ID for call in calls)
    assert all(call["event_ordinal"] == 42 for call in calls)
    assert all(call["declared_streams"] == DeclaredStreamSet(("launch", "contact")) for call in calls)


@pytest.mark.parametrize(
    ("updates", "exception"),
    (
        ({"root_seed": True}, TypeError),
        ({"root_seed": _IntSubclass(1)}, TypeError),
        ({"root_seed": -1}, ValueError),
        ({"root_seed": _U128_MAX + 1}, ValueError),
        ({"event_ordinal": True}, TypeError),
        ({"event_ordinal": _IntSubclass(1)}, TypeError),
        ({"event_ordinal": -1}, ValueError),
        ({"event_ordinal": _U64_SPACE}, ValueError),
        ({"width": True}, TypeError),
        ({"width": _IntSubclass(3)}, TypeError),
        ({"width": 2}, ValueError),
        ({"width": _U64_SPACE + 1}, ValueError),
    ),
)
def test_invalid_request_fails_before_rng(
    monkeypatch: pytest.MonkeyPatch,
    updates: dict[str, object],
    exception: type[Exception],
) -> None:
    def forbidden(**_: object) -> UniformSelection:
        raise AssertionError("invalid requests must fail before selection")

    monkeypatch.setattr(one_cell_coupling, "select_uniform", forbidden)
    request: dict[str, object] = {"root_seed": 0, "event_ordinal": 0, "width": 3}
    request.update(updates)
    with pytest.raises(exception):
        select_one_cell_coupled_event(**request)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("constant_name", "replacement"),
    (
        ("ONE_CELL_COUPLING_GROUP_ID", "pre-one-cell-discovery-v2"),
        ("ONE_CELL_COUPLING_GROUP_ID", 1),
        ("ONE_CELL_STREAM_SET", DeclaredStreamSet(("contact", "launch"))),
        ("ONE_CELL_STREAM_SET", object()),
        ("ONE_CELL_CONTACT_DENOMINATOR", 99),
        ("ONE_CELL_CONTACT_DENOMINATOR", True),
        ("ONE_CELL_STICKINESS_THRESHOLDS", (0, 1, 2, 5, 10, 25, 50, 99)),
        ("ONE_CELL_STICKINESS_THRESHOLDS", list(ONE_CELL_STICKINESS_THRESHOLDS)),
    ),
)
def test_rebound_contract_constants_fail_before_rng(
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    replacement: object,
) -> None:
    monkeypatch.setattr(one_cell_coupling, constant_name, replacement)

    def forbidden(**_: object) -> UniformSelection:
        raise AssertionError("a corrupted contract must fail before selection")

    monkeypatch.setattr(one_cell_coupling, "select_uniform", forbidden)
    with pytest.raises(AssertionError):
        _select()


def test_existing_record_properties_do_not_depend_on_rebindable_public_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _select(event_ordinal=1)
    monkeypatch.setattr(one_cell_coupling, "ONE_CELL_COUPLING_GROUP_ID", "forged-group")
    monkeypatch.setattr(one_cell_coupling, "ONE_CELL_STREAM_SET", DeclaredStreamSet(("contact", "launch")))
    monkeypatch.setattr(one_cell_coupling, "ONE_CELL_CONTACT_DENOMINATOR", 99)
    monkeypatch.setattr(one_cell_coupling, "ONE_CELL_STICKINESS_THRESHOLDS", (100,))

    assert result.coupling_group_id == "pre-one-cell-discovery-v1"
    assert result.stream_names == ("launch", "contact")
    assert result.sticky_by_threshold == (False, False, False, False, True, True, True, True)
    assert result.arm_decisions == (
        (0, False),
        (1, False),
        (2, False),
        (5, False),
        (10, True),
        (25, True),
        (50, True),
        (100, True),
    )
    with pytest.raises(AssertionError):
        OneCellCoupledEventSelection(
            root_seed=result.root_seed,
            event_ordinal=result.event_ordinal,
            width=result.width,
            launch=result.launch,
            contact=result.contact,
        )


@pytest.mark.parametrize(
    ("bad_stage", "replacement", "expected_calls"),
    (
        ("launch", object(), ["launch"]),
        ("launch", UniformSelection("contact", SemanticDraw(0, 0)), ["launch"]),
        ("launch", UniformSelection("launch", SemanticDraw(64, 0)), ["launch"]),
        ("contact", object(), ["launch", "contact"]),
        ("contact", UniformSelection("launch", SemanticDraw(0, 0)), ["launch", "contact"]),
        ("contact", UniformSelection("contact", SemanticDraw(100, 0)), ["launch", "contact"]),
    ),
)
def test_malformed_delegate_fails_at_its_exact_stage(
    monkeypatch: pytest.MonkeyPatch,
    bad_stage: str,
    replacement: object,
    expected_calls: list[str],
) -> None:
    real_select_uniform = one_cell_coupling.select_uniform
    calls: list[str] = []

    def delegate(**kwargs: object) -> object:
        stream_name = str(kwargs["stream_name"])
        calls.append(stream_name)
        if stream_name == bad_stage:
            return replacement
        return real_select_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(one_cell_coupling, "select_uniform", delegate)
    with pytest.raises(AssertionError):
        _select()
    assert calls == expected_calls


@pytest.mark.parametrize("bad_stage", ("launch", "contact"))
def test_forged_nested_delegate_draw_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    bad_stage: str,
) -> None:
    real_select_uniform = one_cell_coupling.select_uniform
    calls: list[str] = []

    def delegate(**kwargs: object) -> UniformSelection:
        stream_name = str(kwargs["stream_name"])
        calls.append(stream_name)
        if stream_name == bad_stage:
            return _forged_uniform_selection(stream_name=stream_name, value=-1)
        return real_select_uniform(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(one_cell_coupling, "select_uniform", delegate)
    with pytest.raises(AssertionError, match="malformed"):
        _select()
    assert calls == (["launch"] if bad_stage == "launch" else ["launch", "contact"])


def test_direct_record_defensively_snapshots_nested_selections() -> None:
    launch = UniformSelection("launch", SemanticDraw(2, 3))
    contact = UniformSelection("contact", SemanticDraw(9, 4))
    result = OneCellCoupledEventSelection(7, 11, 3, launch, contact)
    object.__setattr__(launch.draw, "value", 0)
    object.__setattr__(contact.draw, "value", 99)

    assert result.launch == UniformSelection("launch", SemanticDraw(2, 3))
    assert result.contact == UniformSelection("contact", SemanticDraw(9, 4))
    assert result.sticky_by_threshold == (False, False, False, False, True, True, True, True)
    assert hash(result)
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.width = 4  # type: ignore[misc]


@pytest.mark.parametrize(
    ("updates", "exception"),
    (
        ({"root_seed": True}, TypeError),
        ({"event_ordinal": _U64_SPACE}, ValueError),
        ({"width": 2}, ValueError),
        ({"launch": object()}, TypeError),
        ({"launch": UniformSelection("contact", SemanticDraw(2, 0))}, ValueError),
        ({"launch": UniformSelection("launch", SemanticDraw(3, 0))}, ValueError),
        ({"contact": object()}, TypeError),
        ({"contact": UniformSelection("launch", SemanticDraw(9, 0))}, ValueError),
        ({"contact": UniformSelection("contact", SemanticDraw(100, 0))}, ValueError),
        ({"launch": _forged_uniform_selection(stream_name="launch", value=-1)}, ValueError),
        ({"launch": _forged_uniform_selection(stream_name="launch", value=True)}, TypeError),
        ({"launch": _forged_uniform_selection(stream_name="launch", value=_U64_SPACE)}, ValueError),
        (
            {"launch": _forged_uniform_selection(stream_name="launch", value=2, rejection=-1)},
            ValueError,
        ),
        (
            {"launch": _forged_uniform_selection(stream_name="launch", value=2, rejection=True)},
            TypeError,
        ),
        (
            {"launch": _forged_uniform_selection(stream_name="launch", value=2, rejection=_U64_SPACE)},
            ValueError,
        ),
    ),
)
def test_direct_record_rejects_structural_inconsistency(
    updates: dict[str, object],
    exception: type[Exception],
) -> None:
    fields: dict[str, object] = {
        "root_seed": 0,
        "event_ordinal": 0,
        "width": 3,
        "launch": UniformSelection("launch", SemanticDraw(2, 0)),
        "contact": UniformSelection("contact", SemanticDraw(9, 0)),
    }
    fields.update(updates)
    with pytest.raises(exception):
        OneCellCoupledEventSelection(**fields)  # type: ignore[arg-type]


def test_direct_record_is_structural_and_does_not_replay_rng(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(**_: object) -> UniformSelection:
        raise AssertionError("direct structural construction must not select RNG")

    monkeypatch.setattr(one_cell_coupling, "select_uniform", forbidden)
    result = OneCellCoupledEventSelection(
        root_seed=0,
        event_ordinal=0,
        width=3,
        launch=UniformSelection("launch", SemanticDraw(2, 7)),
        contact=UniformSelection("contact", SemanticDraw(9, 8)),
    )
    assert result.launch.draw.accepted_rejection_ordinal == 7
    assert result.contact.draw.accepted_rejection_ordinal == 8


def test_unequal_widths_share_launch_tape_not_accepted_variate() -> None:
    future_word_before = raw_u64(
        root_seed=0,
        coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
        stream_name="launch",
        event_ordinal=7,
        rejection_ordinal=0,
    )
    width_64 = _select(event_ordinal=6, width=64)
    width_100 = _select(event_ordinal=6, width=100)
    huge = _select(event_ordinal=6, width=(1 << 63) + 1)
    future_word_after = raw_u64(
        root_seed=0,
        coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
        stream_name="launch",
        event_ordinal=7,
        rejection_ordinal=0,
    )

    assert tuple(
        raw_u64(
            root_seed=0,
            coupling_group_id=ONE_CELL_COUPLING_GROUP_ID,
            stream_name="launch",
            event_ordinal=6,
            rejection_ordinal=rejection,
        )
        for rejection in range(3)
    ) == (
        0xC2361DB490F49873,
        0xA4E089425B0398F4,
        0x29A2134F7BE99C8D,
    )
    assert width_64.launch == UniformSelection("launch", SemanticDraw(48, 0))
    assert width_100.launch == UniformSelection("launch", SemanticDraw(75, 0))
    assert huge.launch == UniformSelection("launch", SemanticDraw(2999981533884423309, 2))
    assert width_64.contact == width_100.contact == huge.contact == UniformSelection("contact", SemanticDraw(24, 0))
    assert width_64.sticky_by_threshold == width_100.sticky_by_threshold == huge.sticky_by_threshold
    assert future_word_before == future_word_after == 0x4C65426535B61D1A


def test_inclusive_address_and_width_maxima_are_legal() -> None:
    result = select_one_cell_coupled_event(
        root_seed=_U128_MAX,
        event_ordinal=_U64_MAX,
        width=_U64_SPACE,
    )
    assert result.root_seed == _U128_MAX
    assert result.event_ordinal == _U64_MAX
    assert result.width == _U64_SPACE
    assert result.launch == UniformSelection(
        "launch",
        _manual_bounded(
            root_seed=_U128_MAX,
            stream_name="launch",
            event_ordinal=_U64_MAX,
            upper_bound=_U64_SPACE,
        ),
    )
    assert result.contact == UniformSelection(
        "contact",
        _manual_bounded(
            root_seed=_U128_MAX,
            stream_name="contact",
            event_ordinal=_U64_MAX,
            upper_bound=100,
        ),
    )


def test_contact_rejection_cannot_shift_launch_or_skip_the_common_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int]] = []

    def forced_raw(**kwargs: object) -> int:
        stream_name = str(kwargs["stream_name"])
        rejection = int(kwargs["rejection_ordinal"])
        calls.append((stream_name, rejection))
        if stream_name == "contact" and rejection == 0:
            return _U64_MAX
        return 0

    monkeypatch.setattr(semantic_rng, "raw_u64", forced_raw)
    result = _select(width=64)
    assert result.launch == UniformSelection("launch", SemanticDraw(0, 0))
    assert result.contact == UniformSelection("contact", SemanticDraw(0, 1))
    assert result.sticky_by_threshold == (False, True, True, True, True, True, True, True)
    assert calls == [("launch", 0), ("contact", 0), ("contact", 1)]


def test_selector_is_keyword_only() -> None:
    with pytest.raises(TypeError):
        select_one_cell_coupled_event(0, 0, 64)  # type: ignore[misc]


def test_api_remains_explicit_submodule_only() -> None:
    names = tuple(one_cell_coupling.__all__)
    for module in (
        tetris_ballistic,
        reference_engine,
        exact_selection,
        tetromino_event,
        one_cell_transition,
    ):
        for name in names:
            assert not hasattr(module, name)


def test_module_dependency_boundary_excludes_transition_and_production_layers() -> None:
    source_path = Path(one_cell_coupling.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    called_names = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    plain_imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}

    assert not plain_imports
    assert imported_modules == {"__future__", "dataclasses", "selection"}
    assert imported_names == {
        "annotations",
        "dataclass",
        "DeclaredStreamSet",
        "UniformIntegerLaw",
        "UniformSelection",
        "select_uniform",
    }
    assert not ({"select_weighted", "categorical_index", "uniform_below", "place_one"} & called_names)


def test_hash_seed_does_not_change_contract_or_selection() -> None:
    script = """
import json
from tetris_ballistic.engine.one_cell_coupling import (
    ONE_CELL_COUPLING_GROUP_ID, ONE_CELL_STICKINESS_THRESHOLDS,
    ONE_CELL_STREAM_SET, select_one_cell_coupled_event,
)
result = select_one_cell_coupled_event(root_seed=0, event_ordinal=6, width=(1 << 63) + 1)
print(json.dumps([
    ONE_CELL_COUPLING_GROUP_ID, ONE_CELL_STREAM_SET.stream_names,
    ONE_CELL_STICKINESS_THRESHOLDS, result.launch_x,
    result.launch.draw.accepted_rejection_ordinal, result.contact_value,
    result.contact.draw.accepted_rejection_ordinal, result.sticky_by_threshold,
]))
"""
    project_root = Path(__file__).resolve().parents[1]
    outputs = []
    for hash_seed in ("0", "1", "123456"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            cwd=project_root,
            text=True,
            env=environment,
        )
        outputs.append(json.loads(completed.stdout))

    assert (
        outputs
        == [
            [
                "pre-one-cell-discovery-v1",
                ["launch", "contact"],
                [0, 1, 2, 5, 10, 25, 50, 100],
                2999981533884423309,
                2,
                24,
                0,
                [False, False, False, False, False, True, True, True],
            ]
        ]
        * 3
    )


def test_independent_oracle_does_not_call_bounded_or_selection_helpers() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_manual_bounded")
    called_names = {
        node.func.id for node in ast.walk(helper) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "raw_u64" in called_names
    assert not ({"uniform_below", "select_uniform", "select_one_cell_coupled_event"} & called_names)


@pytest.mark.slow
def test_ten_thousand_events_match_independent_composition_and_width_coupling() -> None:
    widths = (32, (1 << 63) + 1)
    seen_contacts: set[int] = set()
    seen_patterns: set[tuple[bool, ...]] = set()
    saw_launch_rejection = False

    for event_ordinal in range(10_000):
        expected_contact = _manual_bounded(
            root_seed=0,
            stream_name="contact",
            event_ordinal=event_ordinal,
            upper_bound=100,
        )
        results = tuple(_select(event_ordinal=event_ordinal, width=width) for width in widths)
        for width, result in zip(widths, results):
            expected_launch = _manual_bounded(
                root_seed=0,
                stream_name="launch",
                event_ordinal=event_ordinal,
                upper_bound=width,
            )
            assert result.launch == UniformSelection("launch", expected_launch)
            assert result.contact == UniformSelection("contact", expected_contact)
            assert result.sticky_by_threshold == tuple(
                expected_contact.value < threshold for threshold in ONE_CELL_STICKINESS_THRESHOLDS
            )
            saw_launch_rejection |= result.launch.draw.accepted_rejection_ordinal > 0
        assert results[0].contact == results[1].contact
        assert results[0].sticky_by_threshold == results[1].sticky_by_threshold
        seen_contacts.add(expected_contact.value)
        seen_patterns.add(results[0].sticky_by_threshold)

    assert seen_contacts == set(range(100))
    assert seen_patterns == {
        tuple(value < threshold for threshold in ONE_CELL_STICKINESS_THRESHOLDS) for value in range(100)
    }
    assert len(seen_patterns) == 7
    assert saw_launch_rejection
