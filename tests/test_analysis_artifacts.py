"""Adversarial contracts for fail-closed analysis JSON artifacts."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tetris_ballistic import analysis_artifacts
from tetris_ballistic.analysis_artifacts import (
    AnalysisArtifactValidationError,
    analysis_artifact_lock,
    analysis_artifact_paths,
    build_analysis_identity,
    build_identity,
    canonical_json_bytes,
    fingerprint_regular_file,
    fingerprint_regular_files,
    invalidate_json_artifact,
    load_json_artifact,
    write_json_artifact,
)


def _identity(*, seed: object = 42, setting: object = 100) -> dict[str, object]:
    inputs = build_identity(
        analysis_artifacts.INPUT_SET_PROFILE,
        {"files": [{"path": "pct_50/L_0100.npz", "sha256": "a" * 64, "size_bytes": 12}]},
    )
    software = build_identity("test-software-v1", {"source": "abc", "version": "test"})
    return build_analysis_identity(
        artifact_kind="kpz-cell-v1",
        context={"L": 100, "pct": 50},
        inputs=inputs,
        rng={"algorithm": "PCG64", "seed": seed},
        settings={"n_boot": setting},
        software=software,
    )


def _manifest(path: Path) -> dict:
    return json.loads(analysis_artifact_paths(path).manifest.read_text(encoding="utf-8"))


def _write_manifest(path: Path, manifest: dict) -> None:
    analysis_artifact_paths(path).manifest.write_bytes(canonical_json_bytes(manifest) + b"\n")


def test_canonical_json_is_deterministic_finite_and_type_preserving() -> None:
    assert canonical_json_bytes({"z": [True, 1, 1.0], "a": "snowman ☃"}) == (
        b'{"a":"snowman \xe2\x98\x83","z":[true,1,1.0]}'
    )
    assert canonical_json_bytes({"value": True}) != canonical_json_bytes({"value": 1})

    for invalid in (
        {"value": float("nan")},
        {"value": float("inf")},
        {1: "non-string key"},
        {"tuple": (1, 2)},
    ):
        with pytest.raises(ValueError, match="(nonfinite|non-string|non-JSON)"):
            canonical_json_bytes(invalid)


def test_round_trip_requires_complete_exact_identity_and_leaves_persistent_lock(tmp_path) -> None:
    path = tmp_path / "cell_pct50_L0100.json"
    identity = _identity()
    payload = {"beta": 0.333, "plateau": None, "samples": [1, 2, 3]}

    manifest_path = write_json_artifact(path, payload, identity)

    paths = analysis_artifact_paths(path)
    assert manifest_path == paths.manifest
    assert load_json_artifact(path, identity) == payload
    assert paths.lock.is_file()
    assert paths.lock.read_bytes() == b""
    assert not list(tmp_path.glob(".*.tmp"))
    manifest = _manifest(path)
    assert manifest["status"] == "complete"
    assert manifest["artifact"]["filename"] == path.name
    assert manifest["artifact"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "different, match",
    [
        (_identity(seed=43), "identity does not match"),
        (_identity(setting=101), "identity does not match"),
        (_identity(seed=True), "identity does not match"),
    ],
)
def test_rng_settings_and_json_types_are_part_of_reuse_identity(tmp_path, different, match) -> None:
    path = tmp_path / "cell.json"
    write_json_artifact(path, {"beta": 1 / 3}, _identity())

    with pytest.raises(AnalysisArtifactValidationError, match=match):
        load_json_artifact(path, different)


def test_payload_without_commit_marker_is_never_reused(tmp_path) -> None:
    path = tmp_path / "orphan.json"
    path.write_text('{"apparently":"complete"}\n', encoding="utf-8")

    with pytest.raises(AnalysisArtifactValidationError, match="manifest.*missing"):
        load_json_artifact(path, _identity())


def test_payload_size_and_checksum_are_verified_before_json_decode(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"beta": 0.3}, identity)
    path.write_bytes(b"this is deliberately not JSON\n")
    original_decode = analysis_artifacts._decode_json

    def reject_payload_decode(payload, *, label):
        if label == "analysis payload":
            raise AssertionError("untrusted payload must not be decoded before checksum verification")
        return original_decode(payload, label=label)

    monkeypatch.setattr(analysis_artifacts, "_decode_json", reject_payload_decode)
    with pytest.raises(AnalysisArtifactValidationError, match="(size|checksum)"):
        load_json_artifact(path, identity)


def test_duplicate_and_nonfinite_payload_json_are_rejected_even_with_matching_checksum(tmp_path) -> None:
    identity = _identity()
    for name, raw, match in (
        ("duplicate.json", b'{"beta":0.3,"beta":0.4}\n', "duplicate key"),
        ("nonfinite.json", b'{"beta":NaN}\n', "nonfinite"),
        ("overflow.json", b'{"beta":1e9999}\n', "finite"),
    ):
        path = tmp_path / name
        write_json_artifact(path, {"beta": 0.3}, identity)
        path.write_bytes(raw)
        manifest = _manifest(path)
        manifest["artifact"]["sha256"] = hashlib.sha256(raw).hexdigest()
        manifest["artifact"]["size_bytes"] = len(raw)
        _write_manifest(path, manifest)

        with pytest.raises(AnalysisArtifactValidationError, match=match):
            load_json_artifact(path, identity)


def test_duplicate_manifest_keys_and_malformed_identity_are_rejected(tmp_path) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"beta": 0.3}, identity)
    paths = analysis_artifact_paths(path)
    raw = paths.manifest.read_text(encoding="utf-8")
    paths.manifest.write_text(raw.replace("{", '{"status":"complete",', 1), encoding="utf-8")

    with pytest.raises(AnalysisArtifactValidationError, match="duplicate key 'status'"):
        load_json_artifact(path, identity)

    write_json_artifact(path, {"beta": 0.3}, identity)
    manifest = _manifest(path)
    manifest["identity"]["sha256"] = "0" * 64
    _write_manifest(path, manifest)
    with pytest.raises(AnalysisArtifactValidationError, match="identity checksum"):
        load_json_artifact(path, identity)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("status", "incomplete", "supported complete"),
        ("completed_utc", "not-a-time", "completion time"),
        ("completed_utc", "2026-07-13T12:00:00-04:00", "not UTC"),
        ("generation_id", True, "generation id"),
    ],
)
def test_manifest_state_time_and_types_are_strict(tmp_path, field, value, match) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"beta": 0.3}, identity)
    manifest = _manifest(path)
    manifest[field] = value
    _write_manifest(path, manifest)

    with pytest.raises(AnalysisArtifactValidationError, match=match):
        load_json_artifact(path, identity)


@pytest.mark.parametrize("target", ["payload", "manifest"])
def test_symlinks_are_never_followed_for_managed_reads(tmp_path, target) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"beta": 0.3}, identity)
    paths = analysis_artifact_paths(path)
    attacked = getattr(paths, target)
    elsewhere = tmp_path / f"elsewhere-{target}"
    elsewhere.write_bytes(attacked.read_bytes())
    attacked.unlink()
    attacked.symlink_to(elsewhere)

    with pytest.raises(AnalysisArtifactValidationError, match="(symbolic|regular)"):
        load_json_artifact(path, identity)


def test_manifest_and_payload_size_limits_fail_closed(tmp_path) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"values": list(range(20))}, identity)

    with pytest.raises(AnalysisArtifactValidationError, match="safety limit"):
        load_json_artifact(path, identity, max_payload_bytes=10)
    with pytest.raises(ValueError, match="safety limit"):
        write_json_artifact(path, {"values": list(range(20))}, identity, max_payload_bytes=10)


@pytest.mark.parametrize("failed_target", ["payload", "manifest"])
def test_replace_failure_never_leaves_a_reusable_commit_marker(
    tmp_path, monkeypatch, failed_target
) -> None:
    path = tmp_path / "cell.json"
    old_identity = _identity(seed=1)
    write_json_artifact(path, {"generation": "old"}, old_identity)
    paths = analysis_artifact_paths(path)
    original_replace = analysis_artifacts.os.replace

    def fail_selected_replace(source, target):
        if Path(target) == getattr(paths, failed_target):
            raise OSError(f"injected {failed_target} replacement failure")
        return original_replace(source, target)

    monkeypatch.setattr(analysis_artifacts.os, "replace", fail_selected_replace)
    with pytest.raises(OSError, match="injected"):
        write_json_artifact(path, {"generation": "new"}, _identity(seed=2))

    assert not paths.manifest.exists()
    assert not list(tmp_path.glob(".*.tmp"))
    with pytest.raises(AnalysisArtifactValidationError, match="manifest.*missing"):
        load_json_artifact(path, old_identity)


def test_payload_fsync_failure_never_publishes_a_manifest(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cell.json"
    paths = analysis_artifact_paths(path)
    original_fsync = analysis_artifacts.os.fsync
    calls = 0

    def fail_staged_payload_fsync(descriptor):
        nonlocal calls
        calls += 1
        if calls == 2:  # lock metadata is first; staged payload is second
            raise OSError("injected staged payload fsync failure")
        return original_fsync(descriptor)

    monkeypatch.setattr(analysis_artifacts.os, "fsync", fail_staged_payload_fsync)
    with pytest.raises(OSError, match="staged payload fsync"):
        write_json_artifact(path, {"beta": 0.3}, _identity())

    assert not paths.manifest.exists()
    assert not path.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_manifest_directory_fsync_failure_withdraws_commit_marker(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cell.json"
    paths = analysis_artifact_paths(path)
    original_fsync_directory = analysis_artifacts._fsync_directory
    calls = 0

    def fail_manifest_directory_fsync(directory):
        nonlocal calls
        calls += 1
        if calls == 3:  # lock, payload publication, then manifest publication
            raise OSError("injected manifest directory fsync failure")
        return original_fsync_directory(directory)

    monkeypatch.setattr(
        analysis_artifacts, "_fsync_directory", fail_manifest_directory_fsync
    )
    with pytest.raises(OSError, match="manifest directory fsync"):
        write_json_artifact(path, {"beta": 0.3}, _identity())

    assert path.is_file()
    assert not paths.manifest.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_manifest_directory_fails_invalidation_without_touching_payload(tmp_path) -> None:
    path = tmp_path / "cell.json"
    paths = analysis_artifact_paths(path)
    path.write_text('{"old":true}\n', encoding="utf-8")
    paths.manifest.mkdir()

    with pytest.raises(AnalysisArtifactValidationError, match="directory"):
        write_json_artifact(path, {"new": True}, _identity())
    assert path.read_text(encoding="utf-8") == '{"old":true}\n'


def test_lock_can_cover_validation_computation_and_publication(tmp_path) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    with analysis_artifact_lock(path) as paths:
        assert paths.lock.read_bytes()
        write_json_artifact(path, {"beta": 0.3}, identity, lock_held=True)
        assert load_json_artifact(path, identity) == {"beta": 0.3}

    assert analysis_artifact_paths(path).lock.read_bytes() == b""


def test_concurrent_writers_serialize_on_one_persistent_lock(tmp_path, monkeypatch) -> None:
    path = tmp_path / "cell.json"
    identities = [_identity(seed=1), _identity(seed=2)]
    active = 0
    maximum_active = 0
    active_guard = threading.Lock()
    original = analysis_artifacts._write_json_artifact_locked

    def observed_write(*args, **kwargs):
        nonlocal active, maximum_active
        with active_guard:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.05)
        try:
            return original(*args, **kwargs)
        finally:
            with active_guard:
                active -= 1

    monkeypatch.setattr(analysis_artifacts, "_write_json_artifact_locked", observed_write)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(write_json_artifact, path, {"writer": index}, identity)
            for index, identity in enumerate(identities)
        ]
        for future in futures:
            future.result(timeout=5)

    assert maximum_active == 1
    observed_identity = _manifest(path)["identity"]
    assert observed_identity in identities
    assert load_json_artifact(path, observed_identity)["writer"] in {0, 1}
    assert analysis_artifact_paths(path).lock.read_bytes() == b""


def test_invalidate_removes_only_commit_marker(tmp_path) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    write_json_artifact(path, {"beta": 0.3}, identity)

    invalidate_json_artifact(path)

    assert path.is_file()
    assert not analysis_artifact_paths(path).manifest.exists()
    with pytest.raises(AnalysisArtifactValidationError, match="manifest.*missing"):
        load_json_artifact(path, identity)


def test_fingerprint_regular_files_is_streamed_root_relative_sorted_and_closed(tmp_path) -> None:
    root = tmp_path / "inputs"
    root.mkdir()
    second = root / "b.npz"
    first = root / "a.npz"
    second.write_bytes(b"second")
    first.write_bytes(b"first")

    fingerprint = fingerprint_regular_files([second, first], root=root, max_file_bytes=100)

    files = fingerprint["record"]["files"]
    assert [entry["path"] for entry in files] == ["a.npz", "b.npz"]
    assert files[0]["sha256"] == hashlib.sha256(b"first").hexdigest()
    assert files[0]["size_bytes"] == 5
    assert fingerprint == fingerprint_regular_files([first, second], root=root)
    assert fingerprint != fingerprint_regular_files([first], root=root)

    first.write_bytes(b"changed")
    assert fingerprint != fingerprint_regular_files([first, second], root=root)


def test_fingerprint_rejects_symlinks_duplicates_outside_root_and_oversize(tmp_path) -> None:
    root = tmp_path / "inputs"
    root.mkdir()
    source = root / "trace.npz"
    source.write_bytes(b"trace")
    link = root / "link.npz"
    link.symlink_to(source)

    with pytest.raises(AnalysisArtifactValidationError, match="symbolic"):
        fingerprint_regular_file(link, root=root)
    with pytest.raises(ValueError, match="duplicate"):
        fingerprint_regular_files([source, source], root=root)
    with pytest.raises(ValueError, match="outside"):
        fingerprint_regular_file(tmp_path / "elsewhere", root=root)
    with pytest.raises(AnalysisArtifactValidationError, match="safety limit"):
        fingerprint_regular_file(source, root=root, max_bytes=4)


def test_analysis_software_identity_extends_engine_with_analysis_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        "tetris_ballistic.run_artifacts.software_identity",
        lambda package_root=None: build_identity("engine-test-v1", {"tree": "abc"}),
    )
    observed = analysis_artifacts.analysis_software_identity()

    assert observed["profile"] == analysis_artifacts.SOFTWARE_PROFILE
    record = observed["record"]
    assert record["analysis_artifact_schema_version"] == (
        analysis_artifacts.ANALYSIS_ARTIFACT_SCHEMA_VERSION
    )
    assert set(record["dependency_versions"]) == {"matplotlib", "scipy"}
    assert record["engine"]["profile"] == "engine-test-v1"


def test_lock_symlink_is_rejected_without_modifying_its_target(tmp_path) -> None:
    path = tmp_path / "cell.json"
    paths = analysis_artifact_paths(path)
    target = tmp_path / "elsewhere.lock"
    target.write_text("do not truncate", encoding="utf-8")
    paths.lock.symlink_to(target)

    with pytest.raises(AnalysisArtifactValidationError, match="cannot open"):
        with analysis_artifact_lock(path):
            pass
    assert target.read_text(encoding="utf-8") == "do not truncate"


def test_expected_identity_must_have_a_self_consistent_digest(tmp_path) -> None:
    path = tmp_path / "cell.json"
    identity = _identity()
    identity["sha256"] = "0" * 64

    with pytest.raises(ValueError, match="checksum does not match"):
        write_json_artifact(path, {"beta": 0.3}, identity)
    with pytest.raises(ValueError, match="checksum does not match"):
        load_json_artifact(path, identity)
    assert not path.exists()
