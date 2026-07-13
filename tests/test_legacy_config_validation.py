"""Fail-closed contracts for the legacy YAML and 40-state density surface."""

from __future__ import annotations

import random
from copy import deepcopy

import numpy as np
import pytest
import yaml

from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def _valid_density() -> dict[str, list[float]]:
    density = {f"Piece-{index}": [0.0, 0.0] for index in range(20)}
    density["Piece-19"] = [1.0, 0.0]
    return density


def _valid_config() -> dict[str, object]:
    return {
        **_valid_density(),
        "width": 12,
        "height": 40,
        "steps": 20,
        "seed": 7,
    }


def _write_yaml(tmp_path, payload: object):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_no_config_constructor_keeps_documented_default() -> None:
    simulation = Tetris_Ballistic(width=12, height=40, steps=20, seed=7)

    assert simulation.config_data["Piece-0"] == [0, 1]
    assert simulation.config_data["Piece-18"] == [0, 1]
    assert simulation.config_data["Piece-19"] == [0, 0]
    assert simulation._sample_cdf[-1] == 1.0


def test_direct_density_is_validated_and_snapshotted() -> None:
    density = _valid_density()
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=20, seed=7, density=density
    )
    density["Piece-19"][0] = 0.0

    assert simulation.config_data["Piece-19"] == [1.0, 0.0]
    assert simulation._sample_cdf[-1] == 1.0


@pytest.mark.parametrize(
    "mutate, match",
    [
        (lambda density: density.pop("Piece-0"), "exactly Piece-0"),
        (lambda density: density.__setitem__("Piece-20", [1, 0]), "unexpected"),
        (lambda density: density.__setitem__(20, [1, 0]), "keys"),
        (lambda density: density.__setitem__("Piece-19", [1]), "two weights"),
        (lambda density: density.__setitem__("Piece-19", [True, 0]), "not boolean"),
        (lambda density: density.__setitem__("Piece-19", ["1", 0]), "numeric"),
        (lambda density: density.__setitem__("Piece-19", [None, 0]), "numeric"),
        (lambda density: density.__setitem__("Piece-19", [-1, 0]), "nonnegative"),
        (lambda density: density.__setitem__("Piece-19", [np.nan, 0]), "nonnegative"),
        (lambda density: density.__setitem__("Piece-19", [np.inf, 0]), "nonnegative"),
        (lambda density: density.__setitem__("Piece-19", [1e308, 1e308]), "total"),
        (
            lambda density: [density.__setitem__(key, [0, 0]) for key in density],
            "total",
        ),
    ],
)
def test_direct_density_rejects_invalid_contract(mutate, match) -> None:
    density = _valid_density()
    mutate(density)

    with pytest.raises(ValueError, match=match):
        Tetris_Ballistic(
            width=12, height=40, steps=20, seed=7, density=density
        )


def test_explicit_missing_config_does_not_fall_back(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        Tetris_Ballistic(config_file=tmp_path / "missing.yaml")


def test_malformed_yaml_does_not_fall_back(tmp_path) -> None:
    path = tmp_path / "malformed.yaml"
    path.write_text("width: [", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid YAML"):
        Tetris_Ballistic(config_file=path)


def test_duplicate_yaml_key_does_not_select_last_model(tmp_path) -> None:
    payload = yaml.safe_dump(_valid_config(), sort_keys=False)
    path = tmp_path / "duplicate.yaml"
    path.write_text(f"{payload}Piece-19: [0, 1]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid YAML"):
        Tetris_Ballistic(config_file=path)


@pytest.mark.parametrize("payload", [None, [], "width: 12"])
def test_nonmapping_yaml_does_not_fall_back(tmp_path, payload) -> None:
    path = _write_yaml(tmp_path, payload)

    with pytest.raises(ValueError, match="mapping"):
        Tetris_Ballistic(config_file=path)


def test_explicit_config_requires_exact_keys(tmp_path) -> None:
    payload = _valid_config()
    payload.pop("Piece-0")
    payload["extra"] = 1

    with pytest.raises(ValueError, match="missing=.*Piece-0.*unexpected=.*extra"):
        Tetris_Ballistic(config_file=_write_yaml(tmp_path, payload))


@pytest.mark.parametrize(
    "field, value, match",
    [
        ("width", 0, "width"),
        ("height", 1.5, "height"),
        ("steps", np.inf, "steps"),
        ("steps", 10**1000, "steps"),
        ("seed", True, "seed"),
        ("seed", -1, "seed"),
        ("seed", 2**32, "seed"),
    ],
)
def test_explicit_config_validates_metadata(tmp_path, field, value, match) -> None:
    payload = _valid_config()
    payload[field] = value

    with pytest.raises(ValueError, match=match):
        Tetris_Ballistic(config_file=_write_yaml(tmp_path, payload))


def test_saved_none_seed_spelling_remains_loadable(tmp_path) -> None:
    payload = _valid_config()
    payload["seed"] = "None"

    simulation = Tetris_Ballistic(config_file=_write_yaml(tmp_path, payload))

    assert simulation.seed is None
    assert simulation.config_data["seed"] is None


def test_load_config_is_transactional_on_validation_failure(tmp_path) -> None:
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=20, seed=7, density=_valid_density()
    )
    original = deepcopy(simulation.config_data)
    payload = _valid_config()
    payload["Piece-19"] = [0, 0]

    with pytest.raises(ValueError, match="total"):
        simulation.load_config(_write_yaml(tmp_path, payload))

    assert simulation.config_data == original


def test_valid_explicit_config_loads_transactionally(tmp_path) -> None:
    simulation = Tetris_Ballistic(config_file=_write_yaml(tmp_path, _valid_config()))

    assert simulation.width == 12
    assert simulation.height == 40
    assert simulation.steps == 20
    assert simulation.seed == 7
    assert simulation.config_data["Piece-19"] == [1.0, 0.0]
    assert simulation._sample_cdf[-1] == 1.0


def test_valid_yaml_and_direct_density_have_identical_trajectory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    payload = _valid_config()
    payload["Piece-0"] = [0.125, 0.25]
    payload["Piece-19"] = [0.5, 0.125]

    direct = Tetris_Ballistic(
        width=payload["width"],
        height=payload["height"],
        steps=payload["steps"],
        seed=payload["seed"],
        density={key: payload[key] for key in _valid_density()},
    )
    direct.Simulate()
    loaded = Tetris_Ballistic(config_file=_write_yaml(tmp_path, payload))
    loaded.Simulate()

    assert loaded.FinalSteps == direct.FinalSteps
    np.testing.assert_array_equal(loaded.substrate, direct.substrate)
    np.testing.assert_array_equal(loaded.SampleDist, direct.SampleDist)
    np.testing.assert_allclose(loaded.Fluctuation, direct.Fluctuation, atol=0, rtol=0)
    np.testing.assert_allclose(loaded.AvergeHeight, direct.AvergeHeight, atol=0, rtol=0)


def test_nontrivial_float_weight_sampling_sequence_is_pinned() -> None:
    density = {
        f"Piece-{index}": [
            (2 * index + 1) / 17,
            (41 - 2 * index) / 19,
        ]
        for index in range(20)
    }
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=20, seed=2026, density=density
    )

    assert [simulation.Sample_Tetris()[1:] for _ in range(20)] == [
        (2, 1, True),
        (3, 1, True),
        (7, 0, False),
        (1, 0, True),
        (3, 2, True),
        (7, 0, False),
        (2, 1, False),
        (6, 1, False),
        (4, 0, False),
        (5, 0, True),
        (2, 3, False),
        (3, 1, False),
        (2, 3, False),
        (6, 0, True),
        (1, 0, False),
        (3, 2, False),
        (4, 0, False),
        (3, 0, True),
        (4, 3, False),
        (6, 1, False),
    ]


def test_extreme_valid_weights_keep_cached_cdf_monotone() -> None:
    density = {
        f"Piece-{index}": [1.0, 1e-16]
        for index in range(20)
    }
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=20, seed=2026, density=density
    )

    assert np.all(np.diff(simulation._sample_cdf) >= 0)
    assert simulation._sample_cdf[-1] >= 1.0


def test_rejected_config_does_not_mutate_global_rng_streams(tmp_path) -> None:
    path = tmp_path / "malformed.yaml"
    path.write_text("width: [", encoding="utf-8")
    random.seed(12345)
    np.random.seed(12345)
    expected_python = random.random()
    expected_numpy = np.random.random()
    random.seed(12345)
    np.random.seed(12345)

    with pytest.raises(ValueError, match="invalid YAML"):
        Tetris_Ballistic(config_file=path)

    assert random.random() == expected_python
    assert np.random.random() == expected_numpy


def test_corrupt_cached_cdf_raises_in_legacy_sampler(monkeypatch) -> None:
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=1, seed=7, density=_valid_density()
    )
    simulation._sample_cdf = np.zeros(40)
    monkeypatch.setattr(np.random, "random", lambda: 0.5)

    with pytest.raises(RuntimeError, match="invalid cached sampling CDF"):
        simulation.Sample_Tetris()


def test_corrupt_cached_cdf_raises_in_kernel_orchestrator(monkeypatch) -> None:
    simulation = Tetris_Ballistic(
        width=12, height=40, steps=1, seed=7, density=_valid_density()
    )
    simulation._sample_cdf = np.zeros(40)
    monkeypatch.setattr(np.random, "random", lambda: 0.5)

    with pytest.raises(RuntimeError, match="invalid cached sampling CDF"):
        simulation._simulate_1x1_kernel()
