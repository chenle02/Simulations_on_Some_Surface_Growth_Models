"""Per-instance RNG isolation and legacy-sequence compatibility contracts."""

from __future__ import annotations

import hashlib
import multiprocessing
import os
import random

import joblib
import numpy as np
import pytest

from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


class _ProcessGlobalNumpyRng:
    """Expose the pre-S0.2 NumPy draw through the new RNG interface."""

    @staticmethod
    def random_sample():
        return np.random.random()


def _one_cell_density() -> dict[str, list[float]]:
    density = {f"Piece-{index}": [0.0, 0.0] for index in range(20)}
    density["Piece-19"] = [1.0, 1.0]
    return density


def _mixed_density() -> dict[str, list[float]]:
    density = _one_cell_density()
    density["Piece-0"] = [0.125, 0.25]
    return density


def _uniform_density() -> dict[str, list[float]]:
    return {f"Piece-{index}": [1.0, 1.0] for index in range(20)}


def _sample_signature(simulation: Tetris_Ballistic, count: int):
    return [simulation.Sample_Tetris()[1:] for _ in range(count)]


def _assert_numpy_rng_state_equal(left, right) -> None:
    assert left[0] == right[0]
    np.testing.assert_array_equal(left[1], right[1])
    assert left[2:] == right[2:]


def _advance_one(simulation: Tetris_Ballistic, step: int) -> int:
    update, *_ = simulation.Sample_Tetris()
    next_step = update(step)
    assert next_step >= 0
    return next_step


def _run_steps(simulation: Tetris_Ballistic, steps: int) -> Tetris_Ballistic:
    step = 0
    while step < steps:
        step = _advance_one(simulation, step)
    return simulation


def _cell_digest(seed: int) -> str:
    previous_kernel_setting = os.environ.get("TETRIS_USE_KERNEL")
    try:
        os.environ["TETRIS_USE_KERNEL"] = "0"
        simulation = Tetris_Ballistic(
            width=12,
            height=100,
            steps=40,
            seed=seed,
            density=_one_cell_density(),
        )
        simulation.Simulate()
        digest = hashlib.sha256()
        for array in (
            simulation.substrate,
            simulation.SampleDist,
            simulation.Fluctuation,
            simulation.AvergeHeight,
        ):
            digest.update(np.ascontiguousarray(array).tobytes())
        return digest.hexdigest()
    finally:
        if previous_kernel_setting is None:
            os.environ.pop("TETRIS_USE_KERNEL", None)
        else:
            os.environ["TETRIS_USE_KERNEL"] = previous_kernel_setting


def _run_legacy_steps(seed: int, steps: int) -> Tetris_Ballistic:
    simulation = Tetris_Ballistic(
        width=12,
        height=100,
        steps=steps,
        seed=seed,
        density=_one_cell_density(),
    )
    step = 0
    while step < steps:
        step = _advance_one(simulation, step)
    return simulation


def test_instance_streams_match_legacy_rng_algorithms() -> None:
    seed = 2026
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=seed, density=_mixed_density()
    )
    legacy_python = random.Random(seed)
    legacy_numpy = np.random.RandomState(seed)

    assert [simulation._python_rng.randint(0, 100) for _ in range(20)] == [
        legacy_python.randint(0, 100) for _ in range(20)
    ]
    np.testing.assert_array_equal(
        simulation._numpy_rng.random_sample(20),
        legacy_numpy.random_sample(20),
    )


@pytest.mark.parametrize(
    "seed, expected_python, expected_numpy",
    [
        (
            0,
            [6, 7, 0, 6, 8, 62],
            [
                0.5488135039273248,
                0.7151893663724195,
                0.6027633760716439,
                0.5448831829968969,
                0.4236547993389047,
                0.6458941130666561,
            ],
        ),
        (
            7,
            [5, 3, 6, 2, 1, 68],
            [
                0.07630828937395717,
                0.7799187922401146,
                0.4384092314408935,
                0.7234651778309412,
                0.9779895119966027,
                0.5384958704104337,
            ],
        ),
        (
            2**32 - 1,
            [10, 10, 3, 5, 9, 66],
            [
                0.0976320289940138,
                0.9123828453026218,
                0.78903530185164,
                0.7800035981134678,
                0.01793967398674523,
                0.9695059322147525,
            ],
        ),
    ],
)
def test_named_stream_draw_tapes_are_pinned(
    seed: int, expected_python: list[int], expected_numpy: list[float]
) -> None:
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=seed, density=_mixed_density()
    )
    bounds = [(0, 11), (1, 11), (0, 8), (2, 11), (0, 9), (0, 100)]

    assert [simulation._python_rng.randint(low, high) for low, high in bounds] == (
        expected_python
    )
    assert simulation._numpy_rng.random_sample(6).tolist() == expected_numpy


def test_instance_rng_path_matches_process_global_legacy_run(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    seed = 2026
    steps = 200
    kwargs = {
        "width": 12,
        "height": 1000,
        "steps": steps,
        "seed": seed,
        "density": _uniform_density(),
    }
    subject = _run_steps(Tetris_Ballistic(**kwargs), steps)
    legacy = Tetris_Ballistic(**kwargs)
    python_state = random.getstate()
    numpy_state = np.random.get_state()
    try:
        random.seed(seed)
        np.random.seed(seed)
        legacy._python_rng = random
        legacy._numpy_rng = _ProcessGlobalNumpyRng()
        _run_steps(legacy, steps)
    finally:
        random.setstate(python_state)
        np.random.set_state(numpy_state)

    np.testing.assert_array_equal(subject.substrate, legacy.substrate)
    np.testing.assert_array_equal(subject.SampleDist, legacy.SampleDist)
    np.testing.assert_allclose(subject.Fluctuation, legacy.Fluctuation, atol=0, rtol=0)
    np.testing.assert_allclose(subject.AvergeHeight, legacy.AvergeHeight, atol=0, rtol=0)


def test_constructing_another_instance_does_not_change_sampling() -> None:
    reference = Tetris_Ballistic(
        width=12, height=100, steps=30, seed=7, density=_mixed_density()
    )
    expected = _sample_signature(reference, 30)

    subject = Tetris_Ballistic(
        width=12, height=100, steps=30, seed=7, density=_mixed_density()
    )
    actual = _sample_signature(subject, 10)
    intruder = Tetris_Ballistic(
        width=12, height=100, steps=30, seed=999, density=_mixed_density()
    )
    _sample_signature(intruder, 30)
    for _ in range(100):
        random.random()
        np.random.random()
    actual.extend(_sample_signature(subject, 20))

    assert actual == expected


def test_interleaved_legacy_execution_matches_isolated_runs(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    steps = 40
    first = Tetris_Ballistic(
        width=12, height=100, steps=steps, seed=7, density=_one_cell_density()
    )
    second = Tetris_Ballistic(
        width=12, height=100, steps=steps, seed=99, density=_one_cell_density()
    )
    first_step = second_step = 0
    while first_step < steps:
        first_step = _advance_one(first, first_step)
        second_step = _advance_one(second, second_step)

    first_reference = _run_legacy_steps(7, steps)
    second_reference = _run_legacy_steps(99, steps)

    for actual, expected in (
        (first, first_reference),
        (second, second_reference),
    ):
        np.testing.assert_array_equal(actual.substrate, expected.substrate)
        np.testing.assert_array_equal(actual.SampleDist, expected.SampleDist)
        np.testing.assert_allclose(actual.Fluctuation, expected.Fluctuation, atol=0, rtol=0)
        np.testing.assert_allclose(actual.AvergeHeight, expected.AvergeHeight, atol=0, rtol=0)


@pytest.mark.parametrize("start_method", ["fork", "spawn"])
def test_process_scheduling_does_not_change_cell_digest(start_method) -> None:
    if start_method not in multiprocessing.get_all_start_methods():
        pytest.skip(f"multiprocessing start method {start_method!r} is unavailable")
    seeds = [0, 7, 99, 2**32 - 1]
    expected = {seed: _cell_digest(seed) for seed in seeds}
    context = multiprocessing.get_context(start_method)

    with context.Pool(processes=2) as pool:
        scheduled = pool.map(_cell_digest, reversed(seeds))

    assert dict(zip(reversed(seeds), scheduled, strict=True)) == expected


def test_kernel_execution_is_independent_of_construction_order(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "1")
    kwargs = {
        "width": 20,
        "height": 100,
        "steps": 100,
        "density": _one_cell_density(),
    }
    first = Tetris_Ballistic(seed=7, **kwargs)
    second = Tetris_Ballistic(seed=99, **kwargs)
    first.Simulate()
    second.Simulate()
    first_reference = Tetris_Ballistic(seed=7, **kwargs)
    first_reference.Simulate()
    second_reference = Tetris_Ballistic(seed=99, **kwargs)
    second_reference.Simulate()

    for actual, expected in (
        (first, first_reference),
        (second, second_reference),
    ):
        np.testing.assert_array_equal(actual.substrate, expected.substrate)
        np.testing.assert_array_equal(actual.SampleDist, expected.SampleDist)
        np.testing.assert_allclose(actual.Fluctuation, expected.Fluctuation, atol=0, rtol=0)
        np.testing.assert_allclose(actual.AvergeHeight, expected.AvergeHeight, atol=0, rtol=0)


def test_kernel_early_stop_matches_legacy_rng_and_attempt_count(monkeypatch) -> None:
    kwargs = {
        "width": 5,
        "height": 10,
        "steps": 100,
        "seed": 7,
        "density": _one_cell_density(),
    }
    monkeypatch.setenv("TETRIS_USE_KERNEL", "1")
    kernel = Tetris_Ballistic(**kwargs)
    kernel.Simulate()
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    legacy = Tetris_Ballistic(**kwargs)
    legacy.Simulate()

    assert kernel.FinalSteps == legacy.FinalSteps
    assert kernel.SampleDist.sum() == legacy.SampleDist.sum()
    assert kernel.SampleDist.sum() == kernel.FinalSteps + 1
    assert kernel._python_rng.getstate() == legacy._python_rng.getstate()
    _assert_numpy_rng_state_equal(
        kernel._numpy_rng.get_state(), legacy._numpy_rng.get_state()
    )
    np.testing.assert_array_equal(kernel.substrate, legacy.substrate)
    np.testing.assert_array_equal(kernel.SampleDist, legacy.SampleDist)
    np.testing.assert_allclose(kernel.Fluctuation, legacy.Fluctuation, atol=0, rtol=0)
    np.testing.assert_allclose(kernel.AvergeHeight, legacy.AvergeHeight, atol=0, rtol=0)


def test_valid_simulation_does_not_mutate_module_global_rngs(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    random.seed(12345)
    np.random.seed(12345)
    expected_python = random.random()
    expected_numpy = np.random.random()
    random.seed(12345)
    np.random.seed(12345)

    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=7, density=_one_cell_density()
    )
    simulation.Simulate()

    assert random.random() == expected_python
    assert np.random.random() == expected_numpy


def test_set_seed_restarts_instance_streams() -> None:
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=7, density=_mixed_density()
    )
    expected_samples = _sample_signature(simulation, 20)
    expected_positions = [simulation._python_rng.randint(0, 11) for _ in range(20)]

    simulation.set_seed(7)

    assert _sample_signature(simulation, 20) == expected_samples
    assert [simulation._python_rng.randint(0, 11) for _ in range(20)] == expected_positions
    assert simulation.seed == 7
    assert simulation.config_data["seed"] == 7


def test_set_seed_updates_recorded_identity() -> None:
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=7, density=_mixed_density()
    )

    simulation.set_seed(99)

    assert simulation.seed == 99
    assert simulation.config_data["seed"] == 99
    assert simulation.rng_contract_metadata["root_seed"] == 99
    assert simulation.rng_contract_metadata["contract_version"] == (
        "legacy-dual-stream-v1"
    )
    assert set(simulation.rng_contract_metadata["streams"]) == {
        "legacy-state-selection-v1",
        "legacy-position-v1",
    }


def test_reset_does_not_reseed_instance_streams() -> None:
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=7, density=_mixed_density()
    )
    _sample_signature(simulation, 5)
    for _ in range(5):
        simulation._python_rng.randint(0, 11)
    python_state = simulation._python_rng.getstate()
    numpy_state = simulation._numpy_rng.get_state()

    simulation.reset()

    assert simulation._python_rng.getstate() == python_state
    _assert_numpy_rng_state_equal(simulation._numpy_rng.get_state(), numpy_state)


def test_simulate_replays_from_recorded_seed(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=40, seed=7, density=_one_cell_density()
    )
    simulation.Simulate()
    expected = (
        simulation.substrate.copy(),
        simulation.SampleDist.copy(),
        simulation.Fluctuation.copy(),
        simulation.AvergeHeight.copy(),
        simulation._python_rng.getstate(),
        simulation._numpy_rng.get_state(),
    )

    simulation.Simulate()

    np.testing.assert_array_equal(simulation.substrate, expected[0])
    np.testing.assert_array_equal(simulation.SampleDist, expected[1])
    np.testing.assert_array_equal(simulation.Fluctuation, expected[2])
    np.testing.assert_array_equal(simulation.AvergeHeight, expected[3])
    assert simulation._python_rng.getstate() == expected[4]
    _assert_numpy_rng_state_equal(simulation._numpy_rng.get_state(), expected[5])


def test_joblib_roundtrip_preserves_both_rng_continuations(tmp_path) -> None:
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=7, density=_mixed_density()
    )
    _sample_signature(simulation, 5)
    for _ in range(5):
        simulation._python_rng.randint(0, 11)
    path = tmp_path / "simulation.joblib"
    joblib.dump(simulation, path)
    restored = joblib.load(path)

    expected = [
        (
            simulation.Sample_Tetris()[1:],
            simulation._python_rng.randint(0, 11),
        )
        for _ in range(20)
    ]
    actual = [
        (
            restored.Sample_Tetris()[1:],
            restored._python_rng.randint(0, 11),
        )
        for _ in range(20)
    ]

    assert actual == expected


def test_loaded_simulate_replays_from_recorded_seed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=40, seed=7, density=_one_cell_density()
    )
    simulation.Simulate()
    path = tmp_path / "completed-simulation.joblib"
    joblib.dump(simulation, path)
    restored = joblib.load(path)
    fresh = Tetris_Ballistic(
        width=12, height=100, steps=40, seed=7, density=_one_cell_density()
    )

    restored.Simulate()
    fresh.Simulate()

    np.testing.assert_array_equal(restored.substrate, fresh.substrate)
    np.testing.assert_array_equal(restored.SampleDist, fresh.SampleDist)
    np.testing.assert_array_equal(restored.Fluctuation, fresh.Fluctuation)
    np.testing.assert_array_equal(restored.AvergeHeight, fresh.AvergeHeight)
    assert restored._python_rng.getstate() == fresh._python_rng.getstate()
    _assert_numpy_rng_state_equal(
        restored._numpy_rng.get_state(), fresh._numpy_rng.get_state()
    )


def test_legacy_joblib_snapshot_restarts_private_streams_from_seed(tmp_path) -> None:
    seed = 7
    simulation = Tetris_Ballistic(
        width=12, height=100, steps=20, seed=seed, density=_mixed_density()
    )
    del simulation._python_rng
    del simulation._numpy_rng
    del simulation._rng_streams
    del simulation._rng_contract_version
    del simulation._rng_runtime_metadata
    del simulation._rng_migration_notice
    del simulation._sample_probs
    del simulation._sample_cdf
    path = tmp_path / "legacy-simulation.joblib"
    joblib.dump(simulation, path)

    with pytest.warns(RuntimeWarning, match="legacy snapshot lacked serialized RNG"):
        restored = joblib.load(path)
    expected_python = random.Random(seed)
    expected_numpy = np.random.RandomState(seed)

    assert restored._rng_migration_notice == (
        "legacy snapshot lacked serialized RNG state; "
        "streams restarted from the stored seed"
    )
    assert [restored._python_rng.randint(0, 100) for _ in range(20)] == [
        expected_python.randint(0, 100) for _ in range(20)
    ]
    np.testing.assert_array_equal(
        restored._numpy_rng.random_sample(20),
        expected_numpy.random_sample(20),
    )
