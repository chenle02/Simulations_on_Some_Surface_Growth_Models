from __future__ import annotations

import json
import operator
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path

import numpy as np
import pytest

from tests.build_legacy_golden import _run
from tetris_ballistic.legacy_adapter import (
    GEOMETRY_ID_TO_LEGACY_PIECE,
    LEGACY_ADAPTER_VERSION,
    LEGACY_PIECE_GEOMETRY_IDS,
    LEGACY_STATES,
    LegacyDistribution,
    LegacyState,
    LegacyWeightedState,
    density_from_distribution,
    density_from_simulation_config,
    distribution_from_density,
    distribution_from_simulation_config,
    legacy_state,
    simulation_config_from_density,
    state_for,
)
from tetris_ballistic.models import (
    GEOMETRY_BY_ID,
    BoundaryKind,
    ContactKind,
    ContactRule,
    OrientationDistribution,
    PieceEnsemble,
    SimulationConfig,
    normalize_coordinates,
)
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

FIXTURE = Path(__file__).parent / "fixtures" / "legacy-trajectories-v1.json"

EXPECTED_GEOMETRY_IDS = (
    "tetromino.o.00",
    "tetromino.i.00",
    "tetromino.i.01",
    "tetromino.lj.05",
    "tetromino.lj.07",
    "tetromino.lj.03",
    "tetromino.lj.00",
    "tetromino.lj.06",
    "tetromino.lj.01",
    "tetromino.lj.02",
    "tetromino.lj.04",
    "tetromino.t.00",
    "tetromino.t.01",
    "tetromino.t.02",
    "tetromino.t.03",
    "tetromino.sz.02",
    "tetromino.sz.01",
    "tetromino.sz.00",
    "tetromino.sz.03",
    "baseline.one-cell",
)


def _single_piece_density(piece_id: int, column: int) -> dict[str, list[int]]:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density[f"Piece-{piece_id}"][column] = 1
    return density


def test_all_40_states_have_exact_flattened_identity() -> None:
    assert LEGACY_PIECE_GEOMETRY_IDS == EXPECTED_GEOMETRY_IDS
    assert len(LEGACY_STATES) == 40
    for flat_index, state in enumerate(LEGACY_STATES):
        assert state.flat_index == flat_index
        assert state.piece_id == flat_index // 2
        assert state.legacy_column == flat_index % 2
        assert state.sticky is bool(flat_index % 2)
        expected_contact = ContactKind.LEGACY_STICKY_V1 if state.sticky else ContactKind.SUPPORTED
        assert state.contact_kind is expected_contact
        assert state_for(state.geometry_id, state.contact_kind) == state


def test_adapter_v2_records_the_versioned_legacy_sticky_mechanic() -> None:
    sticky_state = legacy_state(1)
    assert LEGACY_ADAPTER_VERSION == "2.0.0"
    assert sticky_state.contact_kind is ContactKind.LEGACY_STICKY_V1
    assert sticky_state.canonical_record()["adapter_version"] == LEGACY_ADAPTER_VERSION
    assert sticky_state.canonical_record()["contact_kind"] == "legacy-sticky-v1"


def test_geometry_reverse_map_is_read_only_and_bijective() -> None:
    assert len(GEOMETRY_ID_TO_LEGACY_PIECE) == 20
    with pytest.raises(TypeError):
        operator.setitem(GEOMETRY_ID_TO_LEGACY_PIECE, "bad", 99)


def test_legacy_piece_map_matches_actual_empty_substrate_deposition(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    for piece_id, geometry_id in enumerate(LEGACY_PIECE_GEOMETRY_IDS):
        simulation = Tetris_Ballistic(
            width=30,
            height=30,
            steps=1,
            seed=7,
            density=_single_piece_density(piece_id, 0),
        )
        with redirect_stdout(StringIO()):
            simulation.Simulate()
        coordinates = normalize_coordinates(
            tuple((int(row), int(column)) for row, column in np.argwhere(simulation.substrate > 0))
        )
        assert coordinates == GEOMETRY_BY_ID[geometry_id].coordinates


def test_density_round_trip_preserves_normalized_joint_weights() -> None:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-0"] = [2, 1]
    density["Piece-19"] = [3, 4]
    distribution = distribution_from_density(density)
    round_trip = density_from_distribution(distribution)
    assert round_trip["Piece-0"] == pytest.approx([0.2, 0.1])
    assert round_trip["Piece-19"] == pytest.approx([0.3, 0.4])
    assert sum(sum(pair) for pair in round_trip.values()) == pytest.approx(1.0)


def test_legacy_distribution_defensively_snapshots_caller_state_list() -> None:
    caller_states = [
        LegacyWeightedState(legacy_state(0), 0.4),
        LegacyWeightedState(legacy_state(1), 0.6),
    ]
    distribution = LegacyDistribution(caller_states)
    original_states = distribution.states
    original_record = distribution.canonical_record()

    caller_states[0] = LegacyWeightedState(legacy_state(2), 1.0)
    caller_states.clear()

    assert distribution.states == original_states
    assert isinstance(distribution.states, tuple)
    assert distribution.canonical_record() == original_record


def test_legacy_weighted_state_and_distribution_snapshot_nested_state_records() -> None:
    caller_state = LegacyState(
        flat_index=0,
        piece_id=0,
        sticky=False,
        geometry_id="tetromino.o.00",
        contact_kind=ContactKind.SUPPORTED,
    )
    caller_weighted = LegacyWeightedState(caller_state, 1.0)
    distribution = LegacyDistribution([caller_weighted])
    original_record = distribution.canonical_record()

    object.__setattr__(caller_state, "piece_id", 19)
    object.__setattr__(caller_weighted, "state", caller_state)
    object.__setattr__(caller_weighted, "probability", 0.0)

    assert distribution.states[0] is not caller_weighted
    assert distribution.states[0].state is not caller_state
    assert distribution.canonical_record() == original_record


def test_legacy_distribution_rejects_invalid_nested_state_types() -> None:
    with pytest.raises(ValueError, match="LegacyWeightedState"):
        LegacyDistribution([object()])

    forged_weighted_state = object.__new__(LegacyWeightedState)
    object.__setattr__(forged_weighted_state, "state", object())
    object.__setattr__(forged_weighted_state, "probability", 1.0)
    with pytest.raises(ValueError, match="LegacyState"):
        LegacyDistribution([forged_weighted_state])


def test_legacy_distribution_rejects_forged_inconsistent_nested_records() -> None:
    forged_state = object.__new__(LegacyState)
    object.__setattr__(forged_state, "flat_index", 0)
    object.__setattr__(forged_state, "piece_id", 19)
    object.__setattr__(forged_state, "sticky", False)
    object.__setattr__(forged_state, "geometry_id", "baseline.one-cell")
    object.__setattr__(forged_state, "contact_kind", ContactKind.SUPPORTED)
    forged_weighted = object.__new__(LegacyWeightedState)
    object.__setattr__(forged_weighted, "state", forged_state)
    object.__setattr__(forged_weighted, "probability", 1.0)

    with pytest.raises(ValueError, match="disagree"):
        LegacyDistribution([forged_weighted])

    missing_state = object.__new__(LegacyState)
    missing_weighted = object.__new__(LegacyWeightedState)
    object.__setattr__(missing_weighted, "state", missing_state)
    object.__setattr__(missing_weighted, "probability", 1.0)
    with pytest.raises(ValueError, match="fully initialized"):
        LegacyDistribution([missing_weighted])

    forged_probability = object.__new__(LegacyWeightedState)
    object.__setattr__(forged_probability, "state", legacy_state(0))
    object.__setattr__(forged_probability, "probability", True)
    with pytest.raises(ValueError, match="canonical built-in floats"):
        LegacyDistribution([forged_probability])


def test_legacy_weighted_state_rejects_mutable_custom_probability() -> None:
    class MutableProbability:
        def __init__(self, value: float) -> None:
            self.value = value

        def __float__(self) -> float:
            return self.value

    probability = MutableProbability(1.0)
    with pytest.raises(ValueError, match="built-in int or float"):
        LegacyWeightedState(legacy_state(0), probability)
    probability.value = 0.0


@pytest.mark.parametrize(
    "probability",
    [True, 0, -1, 10**1000, float("nan"), float("inf"), float("-inf")],
)
def test_legacy_weighted_state_requires_positive_finite_probability(probability: object) -> None:
    with pytest.raises(ValueError, match="legacy probability"):
        LegacyWeightedState(legacy_state(0), probability)


def test_legacy_weighted_state_normalizes_probability_to_builtin_float_record() -> None:
    weighted_state = LegacyWeightedState(legacy_state(0), 1)
    distribution = LegacyDistribution([weighted_state])
    record = distribution.canonical_record()

    assert type(weighted_state.probability) is float
    assert weighted_state.probability == 1.0
    assert type(record["states"][0]["probability"]) is float
    assert record["states"][0]["probability"] == 1.0


@pytest.mark.parametrize(
    "density",
    [
        {},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-20": [1, 0]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [1]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [-1, 0]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [float("nan"), 0]},
    ],
)
def test_invalid_legacy_density_fails_closed(density: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        distribution_from_density(density)


def test_direct_inconsistent_state_construction_fails() -> None:
    with pytest.raises(ValueError, match="disagree"):
        LegacyState(0, 1, False, "tetromino.i.00", ContactKind.SUPPORTED)


def test_legacy_state_requires_exact_builtin_field_types_before_operations() -> None:
    class HostileInt(int):
        def __lt__(self, other: object) -> bool:
            raise AssertionError("hostile integer comparison must not run")

        def __divmod__(self, other: object) -> object:
            raise AssertionError("hostile integer divmod must not run")

    class HostileString(str):
        def __eq__(self, other: object) -> bool:
            raise AssertionError("hostile string comparison must not run")

    valid = (0, 0, False, "tetromino.o.00", ContactKind.SUPPORTED)
    invalid_cases = (
        (True, *valid[1:]),
        (HostileInt(0), *valid[1:]),
        (valid[0], True, *valid[2:]),
        (valid[0], valid[1], 0, *valid[3:]),
        (*valid[:3], HostileString(valid[3]), valid[4]),
        (*valid[:4], "supported"),
    )

    for fields in invalid_cases:
        with pytest.raises(ValueError, match="built-in|ContactKind"):
            LegacyState(*fields)

    with pytest.raises(ValueError, match="integer"):
        legacy_state(True)
    with pytest.raises(ValueError, match="integer"):
        legacy_state(HostileInt(0))


def test_json_golden_trajectories_reproduce_current_legacy_engine(monkeypatch) -> None:
    fixture_bytes = FIXTURE.read_bytes()
    assert sha256(fixture_bytes).hexdigest() == "36e0357e7e1d122df337e6aa431bda3d8639ce77c1210a47e8698dd81a4364f3"
    fixture = json.loads(fixture_bytes)
    assert fixture["generated_from_git_sha"] == "09b0a53"
    assert fixture["legacy_adapter_version"] == "1.0.0"
    assert fixture["legacy_dispatch_forced"] is True
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    for expected in fixture["cases"]:
        case = {key: expected[key] for key in ("name", "piece_id", "weights", "width", "height", "steps", "seed")}
        assert _run(case) == expected


def test_typed_independent_laws_round_trip_through_legacy_density() -> None:
    config = SimulationConfig(
        width=64,
        height=512,
        steps=10_000,
        root_seed=23,
        ensemble=PieceEnsemble.from_weights({"i": 0.25, "o": 0.25, "one-cell": 0.5}),
        orientations=OrientationDistribution.from_weights(
            {
                "i": {"tetromino.i.00": 0.5, "tetromino.i.01": 0.5},
                "o": {"tetromino.o.00": 1.0},
            }
        ),
        contact_rule=ContactRule.from_weights(
            {ContactKind.SUPPORTED: 0.5, ContactKind.LEGACY_STICKY_V1: 0.5}
        ),
    )
    density = density_from_simulation_config(config)
    restored = simulation_config_from_density(
        density,
        width=config.width,
        height=config.height,
        steps=config.steps,
        root_seed=config.root_seed,
    )
    assert restored == config
    assert distribution_from_density(density) == distribution_from_simulation_config(config)


@pytest.mark.parametrize("geometry_id", EXPECTED_GEOMETRY_IDS)
@pytest.mark.parametrize(
    "contact_rule",
    [
        ContactRule.supported(),
        ContactRule.legacy_sticky_v1(),
        ContactRule.from_weights({ContactKind.SUPPORTED: 0.25, ContactKind.LEGACY_STICKY_V1: 0.75}),
    ],
)
def test_every_geometry_and_contact_law_round_trips(geometry_id: str, contact_rule: ContactRule) -> None:
    family_id = GEOMETRY_BY_ID[geometry_id].family_id
    orientations = (
        None if family_id == "one-cell" else OrientationDistribution.from_weights({family_id: {geometry_id: 1.0}})
    )
    config = SimulationConfig(
        width=40,
        height=160,
        steps=200,
        root_seed=5,
        ensemble=PieceEnsemble.pure(family_id),
        orientations=orientations,
        contact_rule=contact_rule,
    )
    density = density_from_simulation_config(config)
    restored = simulation_config_from_density(
        density,
        width=config.width,
        height=config.height,
        steps=config.steps,
        root_seed=config.root_seed,
    )
    assert restored == config


def test_correlated_legacy_geometry_contact_law_fails_closed() -> None:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-0"] = [1, 0]
    density["Piece-1"] = [0, 1]
    with pytest.raises(ValueError, match="correlated"):
        simulation_config_from_density(
            density,
            width=32,
            height=128,
            steps=100,
            root_seed=3,
        )


@pytest.mark.parametrize("contact_kind", [ContactKind.FIRST_CONTACT, "first-contact"])
def test_generic_first_contact_has_no_certified_legacy_mapping(contact_kind: ContactKind | str) -> None:
    with pytest.raises(ValueError, match="no certified legacy mapping"):
        state_for("baseline.one-cell", contact_kind)

    config = SimulationConfig(
        width=32,
        height=128,
        steps=100,
        root_seed=3,
        ensemble=PieceEnsemble.pure("one-cell"),
        orientations=None,
        contact_rule=ContactRule.first_contact(),
    )
    with pytest.raises(ValueError, match="no certified legacy mapping"):
        distribution_from_simulation_config(config)


def test_periodic_typed_config_is_not_misrepresented_as_legacy() -> None:
    config = SimulationConfig(
        width=32,
        height=128,
        steps=100,
        root_seed=3,
        ensemble=PieceEnsemble.pure("one-cell"),
        orientations=None,
        contact_rule=ContactRule.supported(),
        boundary=BoundaryKind.PERIODIC,
    )
    with pytest.raises(ValueError, match="hard-wall"):
        density_from_simulation_config(config)


def test_invalid_factorization_tolerance_is_rejected() -> None:
    density = _single_piece_density(19, 0)
    with pytest.raises(ValueError, match="tolerance"):
        simulation_config_from_density(
            density,
            width=32,
            height=128,
            steps=100,
            root_seed=3,
            factorization_tolerance=float("nan"),
        )


def test_large_tolerance_cannot_bypass_correlated_law_gate() -> None:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-0"] = [1, 0]
    density["Piece-1"] = [0, 1]
    with pytest.raises(ValueError, match="factorization_tolerance"):
        simulation_config_from_density(
            density,
            width=32,
            height=128,
            steps=100,
            root_seed=3,
            factorization_tolerance=1.0,
        )


def test_hostile_float_subclass_cannot_control_tolerance_validation() -> None:
    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("hostile tolerance must be rejected before coercion")

        def __le__(self, other: object) -> bool:
            return True

        def __ge__(self, other: object) -> bool:
            return True

    with pytest.raises(ValueError, match="built-in int or float"):
        simulation_config_from_density(
            _single_piece_density(19, 0),
            width=32,
            height=128,
            steps=100,
            root_seed=3,
            factorization_tolerance=HostileFloat(0.0),
        )
