"""Adversarial contracts for identity-bound atomic cell persistence."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from fcntl import LOCK_EX, LOCK_NB, flock
from pathlib import Path

import joblib
import pytest
import yaml

from tetris_ballistic import run_artifacts
from tetris_ballistic.run_artifacts import (
    ArtifactValidationError,
    CellDisposition,
    artifact_paths,
)
from tetris_ballistic.scripts.run_one_cell import (
    cell_output_paths,
    load_grid_spec,
    run_cell_result,
    validate_grid_spec,
)
from tetris_ballistic.sweep_parameters import simulate
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


@pytest.fixture(autouse=True)
def _force_dispatch_path(monkeypatch):
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")


def _spec(*, ratio: float = 2.0) -> dict:
    return {
        "piece_config": "piece_19_combined_percentage",
        "pcts": [50],
        "widths": [5],
        "seeds": [7],
        "ratio": ratio,
    }


def _paths(root: Path):
    joblib_path, config_path = cell_output_paths(str(root), 50, 5, 7)
    return artifact_paths(joblib_path, config_path)


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(root: Path, *, spec: dict | None = None):
    return run_cell_result(spec or _spec(), 50, 5, 7, str(root))


def test_managed_bundle_reuses_only_after_full_validation(tmp_path, monkeypatch) -> None:
    result = _run(tmp_path)
    paths = _paths(tmp_path)
    assert result.disposition is CellDisposition.CREATED
    assert all(path.is_file() for path in (paths.joblib, paths.config, paths.manifest, paths.lock))
    assert paths.lock.read_bytes() == b""
    config_snapshot = yaml.safe_load(paths.config.read_text(encoding="utf-8"))
    assert len(config_snapshot) == 24
    assert config_snapshot["Piece-19"] == [50.0, 50.0]
    manifest = _load_manifest(paths.manifest)
    assert manifest["software"]["record"]["source_declared_version"] == "2.1.0"
    assert "distribution_metadata_version" in manifest["software"]["record"]
    assert "package_version" not in manifest["software"]["record"]
    assert manifest["configuration"]["record"]["semantics"] == {
        "percentage": 50,
        "percentage_semantics": "sticky_fraction_pct",
        "piece_config": "piece_19_combined_percentage",
        "producer": "run_one_cell-v1",
    }
    mtimes = {
        path: path.stat().st_mtime_ns
        for path in (paths.joblib, paths.config, paths.manifest)
    }

    def must_not_simulate(_self):
        raise AssertionError("verified reuse must not simulate")

    monkeypatch.setattr(Tetris_Ballistic, "Simulate", must_not_simulate)
    reused = _run(tmp_path)

    assert reused.disposition is CellDisposition.REUSED
    assert {path: path.stat().st_mtime_ns for path in mtimes} == mtimes


def test_ratio_change_conflicts_at_the_same_output_path(tmp_path) -> None:
    _run(tmp_path, spec=_spec(ratio=2.0))

    with pytest.raises(ArtifactValidationError, match="configuration identity"):
        _run(tmp_path, spec=_spec(ratio=3.0))


@pytest.mark.parametrize("kind", ["empty", "directory", "symlink"])
def test_bare_or_nonregular_joblib_is_never_adopted(tmp_path, kind) -> None:
    paths = _paths(tmp_path)
    paths.joblib.parent.mkdir(parents=True)
    if kind == "empty":
        paths.joblib.write_bytes(b"")
    elif kind == "directory":
        paths.joblib.mkdir()
    else:
        target = tmp_path / "elsewhere"
        target.write_bytes(b"not a joblib")
        paths.joblib.symlink_to(target)

    with pytest.raises(ArtifactValidationError, match="manifest is missing"):
        _run(tmp_path)


def test_joblib_checksum_fails_before_unpickling(tmp_path, monkeypatch) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    payload = bytearray(paths.joblib.read_bytes())
    payload[len(payload) // 2] ^= 1
    paths.joblib.write_bytes(payload)

    def forbidden_load(_path):
        raise AssertionError("checksum failure must precede unpickling")

    monkeypatch.setattr(run_artifacts.joblib, "load", forbidden_load)
    with pytest.raises(ArtifactValidationError, match="checksum"):
        _run(tmp_path)


def test_config_tampering_is_rejected(tmp_path) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    paths.config.write_text("seed: 999\n", encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="config (size|checksum)"):
        _run(tmp_path)


@pytest.mark.parametrize("mutation", ["incomplete", "wrong_software", "wrong_completion"])
def test_manifest_identity_and_completion_tampering_is_rejected(tmp_path, mutation) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    manifest = _load_manifest(paths.manifest)
    if mutation == "incomplete":
        manifest["status"] = "incomplete"
        match = "not a supported complete"
    elif mutation == "wrong_software":
        manifest["software"]["sha256"] = "0" * 64
        match = "software identity"
    else:
        manifest["completion"]["attempted_events"] += 1
        match = "completion record"
    _write_manifest(paths.manifest, manifest)

    with pytest.raises(ArtifactValidationError, match=match):
        _run(tmp_path)


@pytest.mark.parametrize(
    "mutation, match",
    [
        ("boolean_seed", "configuration identity"),
        ("boolean_completion", "completion record"),
        ("malformed_time", "completion time"),
        ("non_utc_time", "not UTC"),
    ],
)
def test_manifest_validation_is_type_strict_and_requires_utc_time(
    tmp_path, mutation, match
) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    manifest = _load_manifest(paths.manifest)
    if mutation == "boolean_seed":
        manifest["configuration"]["record"]["constructor"]["seed"] = True
    elif mutation == "boolean_completion":
        manifest["completion"]["attempted_events"] = True
    elif mutation == "malformed_time":
        manifest["completed_utc"] = "not-a-timestamp"
    else:
        manifest["completed_utc"] = "2026-07-12T12:00:00-04:00"
    _write_manifest(paths.manifest, manifest)

    with pytest.raises(ArtifactValidationError, match=match):
        _run(tmp_path)


def test_duplicate_manifest_key_is_rejected(tmp_path) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    text = paths.manifest.read_text(encoding="utf-8")
    paths.manifest.write_text(text.replace('{\n  "artifacts"', '{\n  "status": "complete",\n  "artifacts"'), encoding="utf-8")

    with pytest.raises(ArtifactValidationError, match="duplicate key 'status'"):
        _run(tmp_path)


def test_checksums_do_not_bless_the_wrong_object_type(tmp_path) -> None:
    _run(tmp_path)
    paths = _paths(tmp_path)
    joblib.dump({"not": "a simulation"}, paths.joblib)
    manifest = _load_manifest(paths.manifest)
    manifest["artifacts"]["joblib"]["size_bytes"] = paths.joblib.stat().st_size
    manifest["artifacts"]["joblib"]["sha256"] = _sha256(paths.joblib)
    _write_manifest(paths.manifest, manifest)

    with pytest.raises(ArtifactValidationError, match="does not contain Tetris_Ballistic"):
        _run(tmp_path)


def test_joblib_dump_failure_publishes_nothing_and_cleans_unique_temps(tmp_path, monkeypatch) -> None:
    paths = _paths(tmp_path)

    def fail_dump(_value, filename):
        Path(filename).write_bytes(b"partial")
        raise OSError("injected dump failure")

    monkeypatch.setattr(run_artifacts.joblib, "dump", fail_dump)
    with pytest.raises(OSError, match="injected dump failure"):
        _run(tmp_path)

    assert not any(path.exists() for path in (paths.joblib, paths.config, paths.manifest))
    assert not list(paths.joblib.parent.glob(".*.tmp"))
    assert paths.lock.is_file()


@pytest.mark.parametrize("failed_allocation", [2, 3])
def test_partial_temp_allocation_failure_cleans_earlier_temps(
    tmp_path, monkeypatch, failed_allocation
) -> None:
    paths = _paths(tmp_path)
    original = run_artifacts._temporary_path
    calls = 0

    def fail_selected_allocation(target):
        nonlocal calls
        calls += 1
        if calls == failed_allocation:
            raise OSError(f"injected allocation {failed_allocation} failure")
        return original(target)

    monkeypatch.setattr(run_artifacts, "_temporary_path", fail_selected_allocation)
    with pytest.raises(OSError, match=f"allocation {failed_allocation}"):
        _run(tmp_path)

    assert not any(path.exists() for path in (paths.joblib, paths.config, paths.manifest))
    assert not list(paths.joblib.parent.glob(".*.tmp"))


def test_manifest_publish_failure_leaves_no_reusable_commit_marker(tmp_path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    original_replace = run_artifacts.os.replace

    def fail_manifest_replace(source, target):
        if Path(target) == paths.manifest:
            raise OSError("injected manifest replace failure")
        return original_replace(source, target)

    monkeypatch.setattr(run_artifacts.os, "replace", fail_manifest_replace)
    with pytest.raises(OSError, match="manifest replace"):
        _run(tmp_path)

    assert paths.joblib.is_file()
    assert paths.config.is_file()
    assert not paths.manifest.exists()
    assert not list(paths.joblib.parent.glob(".*.tmp"))
    with pytest.raises(ArtifactValidationError, match="manifest is missing"):
        _run(tmp_path)


@pytest.mark.parametrize("failed_target", ["joblib", "config"])
def test_payload_publish_failure_never_publishes_manifest(tmp_path, monkeypatch, failed_target) -> None:
    paths = _paths(tmp_path)
    original_replace = run_artifacts.os.replace

    def fail_selected_replace(source, target):
        if Path(target) == getattr(paths, failed_target):
            raise OSError(f"injected {failed_target} replace failure")
        return original_replace(source, target)

    monkeypatch.setattr(run_artifacts.os, "replace", fail_selected_replace)
    with pytest.raises(OSError, match=failed_target):
        _run(tmp_path)

    assert not paths.manifest.exists()
    assert not list(paths.joblib.parent.glob(".*.tmp"))


@pytest.mark.parametrize("failed_fsync", [1, 2])
def test_directory_fsync_failure_removes_commit_marker(tmp_path, monkeypatch, failed_fsync) -> None:
    paths = _paths(tmp_path)
    calls = 0

    def fail_selected_fsync(_path):
        nonlocal calls
        calls += 1
        if calls == failed_fsync:
            raise OSError("injected directory fsync failure")

    monkeypatch.setattr(run_artifacts, "_fsync_directory", fail_selected_fsync)
    with pytest.raises(OSError, match="directory fsync"):
        _run(tmp_path)

    assert not paths.manifest.exists()
    assert not list(paths.joblib.parent.glob(".*.tmp"))


def test_config_serialization_failure_precedes_publication(tmp_path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(
        run_artifacts.yaml,
        "safe_dump",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("snapshot serialization failed")),
    )

    with pytest.raises(OSError, match="snapshot serialization"):
        _run(tmp_path)

    assert not any(path.exists() for path in (paths.joblib, paths.config, paths.manifest, paths.lock))


def test_staged_joblib_is_validated_before_publication(tmp_path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    monkeypatch.setattr(run_artifacts.joblib, "load", lambda _path: {"wrong": "type"})

    with pytest.raises(ArtifactValidationError, match="does not contain Tetris_Ballistic"):
        _run(tmp_path)

    assert not any(path.exists() for path in (paths.joblib, paths.config, paths.manifest))
    assert not list(paths.joblib.parent.glob(".*.tmp"))


def test_retry_cleans_only_managed_stale_temporaries(tmp_path) -> None:
    paths = _paths(tmp_path)
    paths.joblib.parent.mkdir(parents=True)
    stale = paths.joblib.parent / f".{paths.joblib.name}.crashed.tmp"
    unrelated = paths.joblib.parent / ".unrelated.tmp"
    stale.write_bytes(b"partial")
    unrelated.write_bytes(b"preserve")

    assert _run(tmp_path).disposition is CellDisposition.CREATED

    assert not stale.exists()
    assert unrelated.read_bytes() == b"preserve"


def test_concurrent_same_identity_runs_once_then_reuses(tmp_path, monkeypatch) -> None:
    original_simulate = Tetris_Ballistic.Simulate
    started = threading.Event()
    release = threading.Event()
    count_lock = threading.Lock()
    calls = 0

    def held_simulate(simulation):
        nonlocal calls
        with count_lock:
            calls += 1
        started.set()
        assert release.wait(timeout=10)
        return original_simulate(simulation)

    monkeypatch.setattr(Tetris_Ballistic, "Simulate", held_simulate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_run, tmp_path)
        assert started.wait(timeout=10)
        second = pool.submit(_run, tmp_path)
        time.sleep(0.1)
        assert not second.done()
        release.set()
        results = [first.result(timeout=10), second.result(timeout=10)]

    assert calls == 1
    assert {result.disposition for result in results} == {
        CellDisposition.CREATED,
        CellDisposition.REUSED,
    }


def test_concurrent_different_identity_cannot_overwrite_winner(tmp_path, monkeypatch) -> None:
    original_simulate = Tetris_Ballistic.Simulate
    started = threading.Event()
    release = threading.Event()

    def held_simulate(simulation):
        started.set()
        assert release.wait(timeout=10)
        return original_simulate(simulation)

    monkeypatch.setattr(Tetris_Ballistic, "Simulate", held_simulate)
    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(_run, tmp_path, spec=_spec(ratio=2.0))
        assert started.wait(timeout=10)
        conflict = pool.submit(_run, tmp_path, spec=_spec(ratio=3.0))
        release.set()
        assert winner.result(timeout=10).disposition is CellDisposition.CREATED
        with pytest.raises(ArtifactValidationError, match="configuration identity"):
            conflict.result(timeout=10)

    assert _run(tmp_path, spec=_spec(ratio=2.0)).disposition is CellDisposition.REUSED


def test_process_crash_releases_persistent_lock_inode(tmp_path) -> None:
    paths = _paths(tmp_path)
    paths.lock.parent.mkdir(parents=True)
    code = """
import os, sys
from tetris_ballistic.run_artifacts import artifact_paths, managed_cell_lock
paths = artifact_paths(sys.argv[1], sys.argv[2])
with managed_cell_lock(paths):
    print('locked', flush=True)
    os._exit(23)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code, str(paths.joblib), str(paths.config)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=Path(run_artifacts.__file__).resolve().parents[1],
    )
    assert process.stdout is not None
    assert process.stdout.readline().strip() == "locked"
    assert process.wait(timeout=10) == 23

    with run_artifacts.managed_cell_lock(paths):
        assert paths.lock.is_file()
    assert paths.lock.read_bytes() == b""


@pytest.mark.parametrize("operation_name", ["ftruncate", "fsync"])
def test_lock_cleanup_failure_always_closes_descriptor(tmp_path, monkeypatch, operation_name) -> None:
    paths = _paths(tmp_path)
    paths.lock.parent.mkdir(parents=True)
    original = getattr(run_artifacts.os, operation_name)
    calls = 0

    def fail_second_call(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError(f"injected cleanup {operation_name} failure")
        return original(*args)

    monkeypatch.setattr(run_artifacts.os, operation_name, fail_second_call)
    with pytest.raises(OSError, match=f"cleanup {operation_name}"):
        with run_artifacts.managed_cell_lock(paths):
            pass

    descriptor = os.open(paths.lock, os.O_RDWR)
    try:
        flock(descriptor, LOCK_EX | LOCK_NB)
    finally:
        os.close(descriptor)


def test_early_top_is_an_honest_complete_terminal_state(tmp_path) -> None:
    result = _run(tmp_path, spec=_spec(ratio=0.4))
    completion = _load_manifest(result.manifest_path)["completion"]

    assert completion["reason"] == "top_reached"
    assert completion["final_steps"] < completion["requested_steps"]
    assert completion["attempted_events"] == completion["final_steps"] + 1


@pytest.mark.parametrize(
    "field, value, match",
    [
        ("pcts", [50, 50], "unique"),
        ("widths", [True], "integers"),
        ("seeds", [2**32], "integers"),
        ("ratio", float("nan"), "finite"),
        ("piece_config", "piece_19_combined_percentage_typo", "unsupported"),
        ("output_basename", "../escape", "safe path"),
    ],
)
def test_grid_validation_rejects_collisions_and_invalid_values(field, value, match) -> None:
    spec = _spec()
    spec[field] = value
    with pytest.raises(ValueError, match=match):
        validate_grid_spec(spec)


def test_grid_yaml_rejects_duplicate_keys(tmp_path) -> None:
    path = tmp_path / "grid.yaml"
    path.write_text(
        "piece_config: piece_19_combined_percentage\n"
        "pcts: [50]\nwidths: [5]\nseeds: [7]\nratio: 2\nratio: 3\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid YAML"):
        load_grid_spec(str(path))


def test_public_legacy_sweep_uses_managed_persistence(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-19"] = [50, 50]
    monkeypatch.setattr(Tetris_Ballistic, "ShowData", lambda *args, **kwargs: None)
    params = (5, 7, "config_piece_19_combined.yaml", density, 0)

    simulate(params, 0.4, 1)
    manifest = tmp_path / "config_piece_19_combined_w=5_seed=7.manifest.json"
    assert manifest.is_file()
    first_mtime = manifest.stat().st_mtime_ns
    simulate(params, 0.4, 1)

    assert manifest.stat().st_mtime_ns == first_mtime


def test_atomic_save_helpers_propagate_failure_and_preserve_existing(tmp_path, monkeypatch) -> None:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-19"] = [1, 1]
    simulation = Tetris_Ballistic(width=5, height=10, steps=10, seed=7, density=density)
    joblib_path = tmp_path / "simulation.joblib"
    config_path = tmp_path / "simulation.yaml"
    joblib_path.write_bytes(b"prior-joblib")
    config_path.write_bytes(b"prior-config")

    def fail_joblib(_value, temporary):
        Path(temporary).write_bytes(b"partial")
        raise OSError("joblib failure")

    monkeypatch.setattr(run_artifacts.joblib, "dump", fail_joblib)
    with pytest.raises(OSError, match="joblib failure"):
        simulation.save_simulation(joblib_path)
    assert joblib_path.read_bytes() == b"prior-joblib"

    def fail_config(_target, _payload):
        raise OSError("config failure")

    monkeypatch.setattr(run_artifacts, "atomic_write_bytes", fail_config)
    with pytest.raises(RuntimeError, match="failed to save configuration"):
        simulation.save_config(config_path)
    assert config_path.read_bytes() == b"prior-config"
