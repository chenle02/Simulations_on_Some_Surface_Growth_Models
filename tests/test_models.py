from __future__ import annotations

import json
import operator
from collections import Counter
from types import MappingProxyType

import pytest

import tetris_ballistic.models as model_module
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


def test_piece_geometry_snapshots_plain_coordinates_into_builtin_tuples() -> None:
    caller_coordinates = [[0, 0], [0, 1]]
    geometry = PieceGeometry("test.domino.00", "domino", caller_coordinates)
    original_digest = geometry.software_geometry_record_sha256

    caller_coordinates[0][0] = 99
    caller_coordinates.clear()

    assert geometry.id == "test.domino.00"
    assert type(geometry.id) is str
    assert geometry.family_id == "domino"
    assert type(geometry.family_id) is str
    assert geometry.coordinates == ((0, 0), (0, 1))
    assert type(geometry.coordinates) is tuple
    assert all(type(point) is tuple for point in geometry.coordinates)
    assert geometry.software_geometry_record_sha256 == original_digest


def test_piece_geometry_rejects_string_and_tuple_subclasses_before_overrides_run() -> None:
    class HostileID(str):
        def __bool__(self) -> bool:
            raise AssertionError("hostile ID truth testing must not run")

        def __str__(self) -> str:
            raise AssertionError("hostile ID conversion must not run")

    class HostileTuple(tuple[object, ...]):
        def __iter__(self) -> object:
            raise AssertionError("hostile tuple iteration must not run")

    with pytest.raises(ValueError, match="built-in strings"):
        PieceGeometry(HostileID("test.one"), "one", ((0, 0),))
    with pytest.raises(ValueError, match="built-in strings"):
        PieceGeometry("test.one", HostileID("one"), ((0, 0),))
    with pytest.raises(TypeError, match="plain list or tuple"):
        PieceGeometry("test.one", "one", HostileTuple(((0, 0),)))
    with pytest.raises(TypeError, match="plain integer pairs"):
        PieceGeometry("test.one", "one", (HostileTuple((0, 0)),))


def test_piece_geometry_hardening_preserves_one_cell_golden_digest() -> None:
    geometry = PieceGeometry("baseline.one-cell", "one-cell", [[0, 0]])

    assert geometry.coordinates == ((0, 0),)
    assert geometry.software_geometry_record_sha256 == (
        "1b453abde9941c43b885836ea4eac89e92f044664f1af15e003bef9a539294e4"
    )


def test_equal_free_family_ensemble_normalizes() -> None:
    ensemble = PieceEnsemble.equal_free_families()
    assert {key for key, _ in ensemble.weights} == set(FAMILY_ORIENTATION_IDS)
    assert sum(value for _, value in ensemble.weights) == pytest.approx(1.0)


def test_direct_ensemble_construction_cannot_bypass_validation() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        PieceEnsemble((("i", 0.2), ("o", 0.2)))
    with pytest.raises(ValueError, match="unique, sorted"):
        PieceEnsemble((("o", 0.5), ("i", 0.5)))


def test_probability_records_snapshot_exact_builtin_key_and_value_types() -> None:
    ensemble = PieceEnsemble([["i", 1]])
    orientations = OrientationDistribution([["i", [["tetromino.i.00", 1]]]])

    assert ensemble.weights == (("i", 1.0),)
    assert type(ensemble.weights[0][0]) is str
    assert type(ensemble.weights[0][1]) is float
    assert orientations.by_family == (("i", (("tetromino.i.00", 1.0),)),)
    assert type(orientations.by_family[0][0]) is str
    assert type(orientations.by_family[0][1][0][0]) is str
    assert type(orientations.by_family[0][1][0][1]) is float


def test_from_weights_preserves_nonnegative_input_and_drops_zero_entries() -> None:
    ensemble = PieceEnsemble.from_weights({"i": 2, "o": 0})
    orientations = OrientationDistribution.from_weights(
        {"i": {"tetromino.i.00": 2, "tetromino.i.01": 0}}
    )

    assert ensemble.weights == (("i", 1.0),)
    assert orientations.by_family == (("i", (("tetromino.i.00", 1.0),)),)


def test_piece_ensemble_rejects_hostile_or_duck_typed_probability_inputs() -> None:
    class HostileID(str):
        __hash__ = str.__hash__

        def __eq__(self, other: object) -> bool:
            raise AssertionError("hostile ID comparison must not run")

    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("hostile float coercion must not run")

    class FloatLike:
        def __float__(self) -> float:
            return 1.0

    class HostileMapping(dict[str, float]):
        def items(self) -> object:
            raise AssertionError("hostile mapping iteration must not run")

    for weights in (
        ((HostileID("i"), 1.0),),
        (("i", True),),
        (("i", HostileFloat(1.0)),),
        (("i", FloatLike()),),
    ):
        with pytest.raises(ValueError, match="built-in"):
            PieceEnsemble(weights)

    with pytest.raises(ValueError, match="built-in"):
        PieceEnsemble.from_weights({HostileID("i"): 1.0})
    with pytest.raises(ValueError, match="built-in"):
        PieceEnsemble.from_weights({"i": HostileFloat(1.0)})
    with pytest.raises(ValueError, match="built-in mapping"):
        PieceEnsemble.from_weights(HostileMapping(i=1.0))


def test_orientation_distribution_rejects_hostile_or_duck_typed_probability_inputs() -> None:
    class HostileID(str):
        __hash__ = str.__hash__

        def __eq__(self, other: object) -> bool:
            raise AssertionError("hostile ID comparison must not run")

    class HostileFloat(float):
        def __float__(self) -> float:
            raise AssertionError("hostile float coercion must not run")

    class FloatLike:
        def __float__(self) -> float:
            return 1.0

    class HostileOuterMapping(dict[str, dict[str, float]]):
        def items(self) -> object:
            raise AssertionError("hostile outer mapping iteration must not run")

    class HostileInnerMapping(dict[str, float]):
        def items(self) -> object:
            raise AssertionError("hostile inner mapping iteration must not run")

    for by_family in (
        ((HostileID("i"), (("tetromino.i.00", 1.0),)),),
        (("i", ((HostileID("tetromino.i.00"), 1.0),)),),
        (("i", (("tetromino.i.00", True),)),),
        (("i", (("tetromino.i.00", HostileFloat(1.0)),)),),
        (("i", (("tetromino.i.00", FloatLike()),)),),
    ):
        with pytest.raises(ValueError, match="built-in"):
            OrientationDistribution(by_family)

    with pytest.raises(ValueError, match="built-in"):
        OrientationDistribution.from_weights({HostileID("i"): {"tetromino.i.00": 1.0}})
    with pytest.raises(ValueError, match="built-in"):
        OrientationDistribution.from_weights({"i": {HostileID("tetromino.i.00"): 1.0}})
    with pytest.raises(ValueError, match="built-in"):
        OrientationDistribution.from_weights({"i": {"tetromino.i.00": HostileFloat(1.0)}})
    with pytest.raises(ValueError, match="built-in mapping"):
        OrientationDistribution.from_weights(HostileOuterMapping())
    with pytest.raises(ValueError, match="built-in mappings"):
        OrientationDistribution.from_weights({"i": HostileInnerMapping()})


def test_probability_contracts_reject_hostile_tuple_containers_before_iteration() -> None:
    class HostileTuple(tuple[object, ...]):
        def __iter__(self) -> object:
            raise AssertionError("hostile tuple iteration must not run")

        def __len__(self) -> int:
            raise AssertionError("hostile tuple length must not run")

    with pytest.raises(ValueError, match="plain list or tuple"):
        PieceEnsemble(HostileTuple((("i", 1.0),)))
    with pytest.raises(ValueError, match="key/value pairs"):
        PieceEnsemble((HostileTuple(("i", 1.0)),))
    with pytest.raises(ValueError, match="plain list or tuple"):
        OrientationDistribution(HostileTuple((("i", (("tetromino.i.00", 1.0),)),)))
    with pytest.raises(ValueError, match="family/weights pairs"):
        OrientationDistribution((HostileTuple(("i", (("tetromino.i.00", 1.0),))),))
    with pytest.raises(ValueError, match="plain list or tuple"):
        OrientationDistribution((("i", HostileTuple((("tetromino.i.00", 1.0),))),))
    with pytest.raises(ValueError, match="plain list or tuple"):
        ContactRule(HostileTuple(((ContactKind.SUPPORTED, 1.0),)))
    with pytest.raises(ValueError, match="key/value pairs"):
        ContactRule((HostileTuple((ContactKind.SUPPORTED, 1.0)),))


def test_probability_factories_reject_nonexact_mappings_before_iteration() -> None:
    class HostileFamilyMapping(dict[str, float]):
        def items(self) -> object:
            raise AssertionError("hostile family mapping iteration must not run")

    class HostileOrientationMapping(dict[str, dict[str, float]]):
        def items(self) -> object:
            raise AssertionError("hostile orientation mapping iteration must not run")

    class HostileInnerOrientationMapping(dict[str, float]):
        def items(self) -> object:
            raise AssertionError("hostile inner orientation mapping iteration must not run")

    class HostileContactMapping(dict[ContactKind, float]):
        def items(self) -> object:
            raise AssertionError("hostile contact mapping iteration must not run")

    with pytest.raises(ValueError, match="built-in mapping"):
        PieceEnsemble.from_weights(HostileFamilyMapping(i=1.0))
    with pytest.raises(ValueError, match="built-in mapping"):
        OrientationDistribution.from_weights(HostileOrientationMapping())
    with pytest.raises(ValueError, match="built-in mapping"):
        ContactRule.from_weights(HostileContactMapping())

    with pytest.raises(ValueError, match="built-in mapping"):
        PieceEnsemble.from_weights(MappingProxyType(HostileFamilyMapping(i=1.0)))
    with pytest.raises(ValueError, match="built-in mapping"):
        OrientationDistribution.from_weights(MappingProxyType(HostileOrientationMapping()))
    with pytest.raises(ValueError, match="built-in mappings"):
        OrientationDistribution.from_weights(
            {"i": MappingProxyType(HostileInnerOrientationMapping({"tetromino.i.00": 1.0}))}
        )
    with pytest.raises(ValueError, match="built-in mapping"):
        ContactRule.from_weights(
            MappingProxyType(HostileContactMapping({ContactKind.SUPPORTED: 1.0}))
        )

    assert PieceEnsemble.from_weights({"i": 1.0}).weights == (("i", 1.0),)
    assert OrientationDistribution.from_weights(
        {"i": {"tetromino.i.00": 1.0}}
    ).by_family == (("i", (("tetromino.i.00", 1.0),)),)
    assert ContactRule.from_weights({ContactKind.SUPPORTED: 1.0}).weights == (
        (ContactKind.SUPPORTED, 1.0),
    )


def test_contact_rule_factory_rejects_hostile_string_keys_before_conversion() -> None:
    class HostileContactKey(str):
        __hash__ = str.__hash__

        def __eq__(self, other: object) -> bool:
            raise AssertionError("hostile contact key comparison must not run")

        def __str__(self) -> str:
            raise AssertionError("hostile contact key conversion must not run")

    with pytest.raises(ValueError, match="built-in strings or ContactKind"):
        ContactRule.from_weights({HostileContactKey("supported"): 1.0})

    assert ContactRule.from_weights({"supported": 1.0}).weights == (
        (ContactKind.SUPPORTED, 1.0),
    )


@pytest.mark.parametrize(
    "weights",
    [
        (("i", 0.0),),
        (("i", -1.0),),
        (("i", float("nan")),),
        (("i", float("inf")),),
        (("i", 10**1000),),
        (("i", 0.4), ("o", 0.4)),
    ],
)
def test_direct_piece_ensemble_requires_positive_finite_normalized_weights(
    weights: tuple[tuple[str, float], ...],
) -> None:
    with pytest.raises(ValueError):
        PieceEnsemble(weights)


@pytest.mark.parametrize(
    "weights",
    [
        (("tetromino.i.00", 0.0),),
        (("tetromino.i.00", -1.0),),
        (("tetromino.i.00", float("nan")),),
        (("tetromino.i.00", float("inf")),),
        (("tetromino.i.00", 10**1000),),
        (("tetromino.i.00", 0.4), ("tetromino.i.01", 0.4)),
    ],
)
def test_direct_orientation_distribution_requires_positive_finite_normalized_weights(
    weights: tuple[tuple[str, float], ...],
) -> None:
    with pytest.raises(ValueError):
        OrientationDistribution((("i", weights),))


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


def test_mutable_pseudo_contact_kind_is_rejected_and_cannot_change_config_identity() -> None:
    class MutablePseudoContactKind:
        def __init__(self, value: str) -> None:
            self.value = value

    pseudo_kind = MutablePseudoContactKind("supported")
    with pytest.raises(ValueError, match="ContactKind"):
        ContactRule(((pseudo_kind, 1.0),))

    caller_weights = [[ContactKind.SUPPORTED, 1.0]]
    contact_rule = ContactRule(caller_weights)
    config = _one_cell_config(contact_rule=contact_rule)
    original_json = config.to_json()
    original_digest = config.software_config_record_sha256

    caller_weights[0][0] = pseudo_kind
    pseudo_kind.value = "first-contact"
    caller_weights.clear()

    assert contact_rule.weights == ((ContactKind.SUPPORTED, 1.0),)
    assert config.to_json() == original_json
    assert config.software_config_record_sha256 == original_digest


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


def test_contact_rule_rejects_overflowing_builtin_integer_weight() -> None:
    with pytest.raises(ValueError, match="finite and positive"):
        ContactRule(((ContactKind.SUPPORTED, 10**1000),))


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


def test_simulation_config_rejects_hostile_schema_version_subclass() -> None:
    class HostileSchemaVersion(str):
        def __eq__(self, other: object) -> bool:
            return True

        def __repr__(self) -> str:
            raise AssertionError("hostile schema version must not control diagnostics")

    with pytest.raises(ValueError, match="unsupported model schema"):
        _one_cell_config(schema_version=HostileSchemaVersion("not-the-schema"))


def test_simulation_config_rejects_none_contact_rule() -> None:
    with pytest.raises(ValueError, match="contact_rule must be a ContactRule"):
        _one_cell_config(contact_rule=None)


def test_simulation_config_rejects_duck_typed_nested_objects() -> None:
    class FakeEnsemble:
        weights = (("one-cell", 1.0),)

    class FakeOrientations:
        by_family: tuple[object, ...] = ()

    class FakeContactRule:
        def canonical_record(self) -> dict[str, object]:
            return {"weights": {"supported": 1.0}}

    with pytest.raises(ValueError, match="ensemble must be a PieceEnsemble"):
        _one_cell_config(ensemble=FakeEnsemble())
    with pytest.raises(ValueError, match="orientations must be an OrientationDistribution"):
        _one_cell_config(orientations=FakeOrientations())
    with pytest.raises(ValueError, match="contact_rule must be a ContactRule"):
        _one_cell_config(contact_rule=FakeContactRule())


def test_simulation_config_snapshots_nested_contracts_against_caller_mutation() -> None:
    ensemble = PieceEnsemble.pure("i")
    orientations = OrientationDistribution.from_weights({"i": {"tetromino.i.00": 1.0}})
    contact_rule = ContactRule.supported()
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
    original_digest = config.software_config_record_sha256

    object.__setattr__(ensemble, "weights", (("o", 1.0),))
    object.__setattr__(orientations, "by_family", (("o", (("tetromino.o.00", 1.0),)),))
    object.__setattr__(contact_rule, "weights", ((ContactKind.FIRST_CONTACT, 1.0),))

    assert config.ensemble is not ensemble
    assert config.orientations is not orientations
    assert config.contact_rule is not contact_rule
    assert config.ensemble.weights == (("i", 1.0),)
    assert config.orientations is not None
    assert config.orientations.by_family == (("i", (("tetromino.i.00", 1.0),)),)
    assert config.contact_rule.weights == ((ContactKind.SUPPORTED, 1.0),)
    assert config.to_json() == original_json
    assert config.software_config_record_sha256 == original_digest


def test_simulation_config_revalidates_forged_exact_nested_instances() -> None:
    forged_ensemble = object.__new__(PieceEnsemble)
    object.__setattr__(forged_ensemble, "weights", (("i", 0.25), ("o", 0.25)))
    with pytest.raises(ValueError, match="sum to one"):
        _one_cell_config(ensemble=forged_ensemble)

    forged_orientations = object.__new__(OrientationDistribution)
    object.__setattr__(
        forged_orientations,
        "by_family",
        (("i", (("tetromino.o.00", 1.0),)),),
    )
    with pytest.raises(ValueError, match="unknown orientation"):
        SimulationConfig(
            width=64,
            height=256,
            steps=1000,
            root_seed=42,
            ensemble=PieceEnsemble.pure("i"),
            orientations=forged_orientations,
            contact_rule=ContactRule.supported(),
        )

    forged_contact_rule = object.__new__(ContactRule)
    object.__setattr__(forged_contact_rule, "weights", ((ContactKind.SUPPORTED, 0.5),))
    with pytest.raises(ValueError, match="sum to one"):
        _one_cell_config(contact_rule=forged_contact_rule)


def test_simulation_config_rejects_incomplete_forged_nested_instances() -> None:
    with pytest.raises(ValueError, match="fully initialized"):
        _one_cell_config(ensemble=object.__new__(PieceEnsemble))


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


@pytest.mark.parametrize(
    "malformed",
    [
        "",
        "0" * 63,
        "0" * 65,
        "A" * 64,
        "g" * 64,
        "0" * 63 + "-",
        "é" * 64,
        "💥" * 64,
    ],
)
def test_malformed_record_digests_are_controlled_mismatches_before_compare_digest(
    malformed: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_compare(left: str, right: str) -> bool:
        raise AssertionError(f"malformed digest reached compare_digest: {left!r}, {right!r}")

    monkeypatch.setattr(model_module, "compare_digest", unexpected_compare)

    assert not ONE_CELL.matches_software_geometry_record_digest(
        profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
        sha256=malformed,
    )


def test_digest_matching_rejects_non_builtin_string_inputs_before_operations() -> None:
    class HostileDigest(str):
        def __len__(self) -> int:
            raise AssertionError("hostile digest length must not run")

        def __iter__(self) -> object:
            raise AssertionError("hostile digest iteration must not run")

    with pytest.raises(ValueError, match="must be a string"):
        ONE_CELL.matches_software_geometry_record_digest(
            profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
            sha256=HostileDigest(ONE_CELL.software_geometry_record_sha256),
        )
    with pytest.raises(ValueError, match="must be a string"):
        ONE_CELL.matches_software_geometry_record_digest(
            profile=SOFTWARE_GEOMETRY_RECORD_PROFILE,
            sha256=b"0" * 64,
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
