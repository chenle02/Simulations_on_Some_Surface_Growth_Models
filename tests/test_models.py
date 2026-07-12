from __future__ import annotations

import json
import operator
from collections import Counter

import pytest

from tetris_ballistic.models import (
    FAMILY_ORIENTATION_IDS,
    GEOMETRY_BY_ID,
    MODEL_SCHEMA_VERSION,
    ONE_CELL,
    SOFTWARE_CONFIG_RECORD_PROFILE,
    SOFTWARE_GEOMETRY_RECORD_PROFILE,
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
        assert len(geometry.software_geometry_record_sha256) == 64


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


@pytest.mark.parametrize("coordinates", [((False, 0),), ((0, True),)])
def test_piece_geometry_rejects_boolean_coordinates(coordinates: tuple[tuple[object, object], ...]) -> None:
    with pytest.raises(TypeError, match="integer pairs"):
        PieceGeometry("bad", "bad", coordinates)


def test_equal_free_family_ensemble_normalizes() -> None:
    ensemble = PieceEnsemble.equal_free_families()
    assert {key for key, _ in ensemble.weights} == set(FAMILY_ORIENTATION_IDS)
    assert sum(value for _, value in ensemble.weights) == pytest.approx(1.0)


def test_direct_ensemble_construction_cannot_bypass_validation() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        PieceEnsemble((("i", 0.2), ("o", 0.2)))
    with pytest.raises(ValueError, match="unique, sorted"):
        PieceEnsemble((("o", 0.5), ("i", 0.5)))


def test_caller_owned_weight_sequences_are_defensively_frozen() -> None:
    ensemble_weights = [["i", 1.0]]
    orientation_weights = [["i", [["tetromino.i.00", 1.0]]]]
    contact_weights = [[ContactKind.SUPPORTED, 1.0]]
    ensemble = PieceEnsemble(ensemble_weights)
    orientations = OrientationDistribution(orientation_weights)
    contact_rule = ContactRule(contact_weights)
    config = SimulationConfig(
        width=64,
        height=256,
        steps=1000,
        root_seed=42,
        ensemble=ensemble,
        orientations=orientations,
        contact_rule=contact_rule,
    )
    original_json = config.to_json()
    original_hash = config.software_config_record_sha256

    ensemble_weights[0][0] = "unknown"
    ensemble_weights[0][1] = -1.0
    orientation_weights[0][1][0][0] = "tetromino.i.01"
    orientation_weights[0][1][0][1] = -1.0
    contact_weights[0][0] = ContactKind.FIRST_CONTACT
    contact_weights[0][1] = -1.0

    assert ensemble.weights == (("i", 1.0),)
    assert orientations.by_family == (("i", (("tetromino.i.00", 1.0),)),)
    assert contact_rule.weights == ((ContactKind.SUPPORTED, 1.0),)
    assert config.to_json() == original_json
    assert config.software_config_record_sha256 == original_hash


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
    rule = ContactRule.from_weights({ContactKind.SUPPORTED: 3.0, ContactKind.LEGACY_STICKY_V1: 1.0})
    assert dict(rule.weights) == {
        ContactKind.LEGACY_STICKY_V1: 0.25,
        ContactKind.SUPPORTED: 0.75,
    }


def test_generic_first_contact_is_distinct_from_legacy_sticky_v1() -> None:
    assert ContactKind.FIRST_CONTACT.value == "first-contact"
    assert ContactKind.LEGACY_STICKY_V1.value == "legacy-sticky-v1"
    assert ContactRule.first_contact() != ContactRule.legacy_sticky_v1()


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


def _one_cell_config(**overrides: object) -> SimulationConfig:
    values: dict[str, object] = {
        "width": 64,
        "height": 256,
        "steps": 1000,
        "root_seed": 42,
        "ensemble": PieceEnsemble.pure("one-cell"),
        "orientations": None,
        "contact_rule": ContactRule.supported(),
    }
    values.update(overrides)
    return SimulationConfig(**values)


@pytest.mark.parametrize("field", ["width", "height", "steps"])
@pytest.mark.parametrize("invalid", [True, 1.5, 0, -1])
def test_simulation_config_rejects_invalid_positive_integer_fields(field: str, invalid: object) -> None:
    with pytest.raises(ValueError, match=field):
        _one_cell_config(**{field: invalid})


@pytest.mark.parametrize("invalid", [True, 1.5, -1, None])
def test_simulation_config_rejects_invalid_root_seed(invalid: object) -> None:
    with pytest.raises(ValueError, match="root_seed"):
        _one_cell_config(root_seed=invalid)


@pytest.mark.parametrize("invalid", ["hard-wall", True, None])
def test_simulation_config_rejects_non_enum_boundary(invalid: object) -> None:
    with pytest.raises(ValueError, match="BoundaryKind"):
        _one_cell_config(boundary=invalid)


@pytest.mark.parametrize("invalid", ["garbage", "", None, 1])
def test_simulation_config_rejects_unsupported_schema_version(invalid: object) -> None:
    with pytest.raises(ValueError, match="unsupported model schema"):
        _one_cell_config(schema_version=invalid)


def test_simulation_config_accepts_current_schema_and_zero_seed() -> None:
    config = _one_cell_config(root_seed=0, schema_version=MODEL_SCHEMA_VERSION)
    assert config.root_seed == 0
    assert config.schema_version == MODEL_SCHEMA_VERSION


def test_one_cell_configuration_has_stable_software_record_digest() -> None:
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
    assert config.software_config_record_sha256 == config.software_config_record_sha256
    assert len(config.software_config_record_sha256) == 64


def test_software_local_record_profiles_have_golden_one_cell_digests() -> None:
    config = SimulationConfig(
        width=4,
        height=16,
        steps=12,
        root_seed=7,
        ensemble=PieceEnsemble.pure("one-cell"),
        orientations=None,
        contact_rule=ContactRule.supported(),
    )

    assert SOFTWARE_GEOMETRY_RECORD_PROFILE == "tetris-ballistic/software-geometry-record@1"
    assert ONE_CELL.software_geometry_record_sha256 == "1b453abde9941c43b885836ea4eac89e92f044664f1af15e003bef9a539294e4"
    assert ONE_CELL.software_geometry_record_reference() == {
        "profile": SOFTWARE_GEOMETRY_RECORD_PROFILE,
        "sha256": "1b453abde9941c43b885836ea4eac89e92f044664f1af15e003bef9a539294e4",
    }
    assert SOFTWARE_CONFIG_RECORD_PROFILE == "tetris-ballistic/software-config-record@1"
    assert config.software_config_record_sha256 == "853655b21f47f155bc2090a5b0b4a85f2589613e60814020103123a849b552c4"
    assert config.software_config_record_reference() == {
        "profile": SOFTWARE_CONFIG_RECORD_PROFILE,
        "sha256": "853655b21f47f155bc2090a5b0b4a85f2589613e60814020103123a849b552c4",
    }
    assert config.to_json() == (
        '{"boundary":"hard-wall","contact_rule":{"weights":{"supported":1.0}},'
        '"ensemble":{"weights":{"one-cell":1.0}},"height":16,"orientations":null,'
        '"root_seed":7,"schema_version":"1.0.0","steps":12,"width":4}'
    )
    assert ONE_CELL.sha256 == ONE_CELL.software_geometry_record_sha256
    assert config.sha256 == config.software_config_record_sha256


def test_software_record_digest_comparison_rejects_wrong_profiles() -> None:
    config = _one_cell_config()
    with pytest.raises(ValueError, match="profile mismatch"):
        ONE_CELL.matches_software_geometry_record_digest(
            profile=SOFTWARE_CONFIG_RECORD_PROFILE,
            sha256=ONE_CELL.software_geometry_record_sha256,
        )
    assert ONE_CELL.matches_software_geometry_record_digest(
        profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
        sha256=ONE_CELL.software_geometry_record_sha256,
    )
    assert not ONE_CELL.matches_software_geometry_record_digest(
        profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
        sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="profile mismatch"):
        config.matches_software_config_record_digest(
            profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
            sha256=config.software_config_record_sha256,
        )
    assert config.matches_software_config_record_digest(
        profile=SOFTWARE_CONFIG_RECORD_PROFILE,
        sha256=config.software_config_record_sha256,
    )


def test_tetromino_configuration_round_trip_payload_is_deterministic() -> None:
    config_a = SimulationConfig(
        width=128,
        height=512,
        steps=5000,
        root_seed=7,
        ensemble=PieceEnsemble.from_weights({"i": 2, "o": 1}),
        orientations=OrientationDistribution.isotropic(["i", "o"]),
        contact_rule=ContactRule.legacy_sticky_v1(),
    )
    config_b = SimulationConfig(
        width=128,
        height=512,
        steps=5000,
        root_seed=7,
        ensemble=PieceEnsemble.from_weights({"o": 1, "i": 2}),
        orientations=OrientationDistribution.isotropic(["o", "i"]),
        contact_rule=ContactRule.legacy_sticky_v1(),
    )
    assert config_a.to_json() == config_b.to_json()
    assert config_a.software_config_record_sha256 == config_b.software_config_record_sha256
