from __future__ import annotations

import json
import operator
from collections import Counter

import pytest

from tetris_ballistic.models import (
    FAMILY_ORIENTATION_IDS,
    GEOMETRY_BY_ID,
    ONE_CELL,
    TETROMINO_REGISTRY,
    BoundaryKind,
    ContactKind,
    ContactRule,
    OrientationDistribution,
    PieceEnsemble,
    PieceGeometry,
    SimulationConfig,
    normalize_coordinates,
)


def test_registry_has_five_free_families_and_19_fixed_orientations() -> None:
    counts = Counter(geometry.family_id for geometry in TETROMINO_REGISTRY)
    assert counts == {"i": 2, "lj": 8, "o": 1, "sz": 4, "t": 4}
    assert len(TETROMINO_REGISTRY) == 19
    assert len({geometry.id for geometry in TETROMINO_REGISTRY}) == 19
    assert len({geometry.coordinates for geometry in TETROMINO_REGISTRY}) == 19


def test_tetrominoes_are_canonical_connected_area_four() -> None:
    for geometry in TETROMINO_REGISTRY:
        assert geometry.area == 4
        assert geometry.coordinates == normalize_coordinates(geometry.coordinates)
        assert len(geometry.sha256) == 64


def test_one_cell_is_a_separate_baseline() -> None:
    assert ONE_CELL.id == "baseline.one-cell"
    assert ONE_CELL.family_id == "one-cell"
    assert ONE_CELL.area == 1
    assert ONE_CELL not in TETROMINO_REGISTRY


def test_registry_mappings_are_read_only() -> None:
    with pytest.raises(TypeError):
        operator.setitem(GEOMETRY_BY_ID, "bad", ONE_CELL)
    with pytest.raises(TypeError):
        operator.setitem(FAMILY_ORIENTATION_IDS, "bad", (ONE_CELL.id,))


def test_piece_geometry_rejects_noncanonical_disconnected_and_duplicates() -> None:
    with pytest.raises(ValueError, match="canonical"):
        PieceGeometry("bad", "bad", ((1, 1),))
    with pytest.raises(ValueError, match="connected"):
        PieceGeometry("bad", "bad", ((0, 0), (2, 0)))
    with pytest.raises(ValueError, match="duplicate"):
        PieceGeometry("bad", "bad", ((0, 0), (0, 0)))


def test_equal_free_family_ensemble_normalizes() -> None:
    ensemble = PieceEnsemble.equal_free_families()
    assert {key for key, _ in ensemble.weights} == set(FAMILY_ORIENTATION_IDS)
    assert sum(value for _, value in ensemble.weights) == pytest.approx(1.0)


def test_direct_ensemble_construction_cannot_bypass_validation() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        PieceEnsemble((("i", 0.2), ("o", 0.2)))
    with pytest.raises(ValueError, match="unique, sorted"):
        PieceEnsemble((("o", 0.5), ("i", 0.5)))


@pytest.mark.parametrize(
    "weights",
    [
        {},
        {"unknown": 1.0},
        {"i": -1.0},
        {"i": float("nan")},
        {"i": 0.0},
    ],
)
def test_piece_ensemble_rejects_invalid_weights(weights: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        PieceEnsemble.from_weights(weights)


def test_isotropic_orientation_distribution_is_conditional_by_family() -> None:
    distribution = OrientationDistribution.isotropic(["i", "lj"])
    by_family = dict(distribution.by_family)
    assert set(by_family) == {"i", "lj"}
    assert {value for _, value in by_family["i"]} == {0.5}
    assert {value for _, value in by_family["lj"]} == {0.125}


def test_orientation_distribution_rejects_cross_family_orientation() -> None:
    with pytest.raises(ValueError, match="unknown orientation"):
        OrientationDistribution.from_weights({"i": {FAMILY_ORIENTATION_IDS["o"][0]: 1.0}})


def test_contact_rule_uses_explicit_mechanics_and_normalizes() -> None:
    rule = ContactRule.from_weights({ContactKind.SUPPORTED: 3.0, ContactKind.FIRST_CONTACT: 1.0})
    assert dict(rule.weights) == {
        ContactKind.FIRST_CONTACT: 0.25,
        ContactKind.SUPPORTED: 0.75,
    }


def test_simulation_config_requires_exact_orientation_family_coverage() -> None:
    ensemble = PieceEnsemble.from_weights({"i": 1.0})
    with pytest.raises(ValueError, match="exactly match"):
        SimulationConfig(
            width=64,
            height=256,
            steps=1000,
            root_seed=42,
            ensemble=ensemble,
            orientations=None,
            contact_rule=ContactRule.supported(),
        )


def test_one_cell_configuration_has_stable_canonical_identity() -> None:
    config = SimulationConfig(
        width=64,
        height=256,
        steps=1000,
        root_seed=42,
        ensemble=PieceEnsemble.pure("one-cell"),
        orientations=None,
        contact_rule=ContactRule.supported(),
    )
    decoded = json.loads(config.to_json())
    assert decoded["width"] == 64
    assert decoded["boundary"] == BoundaryKind.HARD_WALL.value
    assert decoded["contact_rule"]["weights"] == {"supported": 1.0}
    assert config.sha256 == config.sha256
    assert len(config.sha256) == 64


def test_tetromino_configuration_round_trip_payload_is_deterministic() -> None:
    config_a = SimulationConfig(
        width=128,
        height=512,
        steps=5000,
        root_seed=7,
        ensemble=PieceEnsemble.from_weights({"i": 2, "o": 1}),
        orientations=OrientationDistribution.isotropic(["i", "o"]),
        contact_rule=ContactRule.first_contact(),
    )
    config_b = SimulationConfig(
        width=128,
        height=512,
        steps=5000,
        root_seed=7,
        ensemble=PieceEnsemble.from_weights({"o": 1, "i": 2}),
        orientations=OrientationDistribution.isotropic(["o", "i"]),
        contact_rule=ContactRule.first_contact(),
    )
    assert config_a.to_json() == config_b.to_json()
    assert config_a.sha256 == config_b.sha256
