"""Fail-closed JSON artifacts for reproducible scientific analysis.

An analysis payload is reusable only when its manifest is a valid commit
marker, its bytes match the recorded size and checksum, and its complete
identity exactly matches the current request.  Writers publish the payload
first and the manifest last while holding a persistent-inode advisory lock.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fcntl import LOCK_EX, flock
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Iterator

ANALYSIS_ARTIFACT_SCHEMA_VERSION = "tetris-analysis-json-v1"
ANALYSIS_IDENTITY_PROFILE = "tetris-analysis-request-sha256-v1"
INPUT_SET_PROFILE = "tetris-analysis-input-set-sha256-v1"
SETTINGS_PROFILE = "tetris-analysis-settings-sha256-v1"
RNG_PROFILE = "tetris-analysis-rng-sha256-v1"
SOFTWARE_PROFILE = "tetris-analysis-software-sha256-v1"

MAX_MANIFEST_BYTES = 1_000_000
MAX_JSON_PAYLOAD_BYTES = 64 * 1024 * 1024
# Raw traces can be large, but a finite ceiling prevents accidental hashing of
# a device or otherwise nonsensical input.  Callers may choose a tighter cap.
MAX_INPUT_FILE_BYTES = 1 << 40
_READ_CHUNK_BYTES = 1024 * 1024

__all__ = [
    "ANALYSIS_ARTIFACT_SCHEMA_VERSION",
    "ANALYSIS_IDENTITY_PROFILE",
    "INPUT_SET_PROFILE",
    "RNG_PROFILE",
    "SETTINGS_PROFILE",
    "SOFTWARE_PROFILE",
    "AnalysisArtifactPaths",
    "AnalysisArtifactValidationError",
    "analysis_artifact_lock",
    "analysis_artifact_paths",
    "analysis_software_identity",
    "build_analysis_identity",
    "build_identity",
    "canonical_json_bytes",
    "cleanup_analysis_temporaries",
    "fingerprint_regular_file",
    "fingerprint_regular_files",
    "invalidate_json_artifact",
    "load_json_artifact",
    "rng_identity",
    "settings_identity",
    "write_json_artifact",
]


class AnalysisArtifactValidationError(RuntimeError):
    """An analysis artifact exists, but it is not safe to reuse."""


@dataclass(frozen=True)
class AnalysisArtifactPaths:
    """The payload, commit marker, and persistent lock for one artifact."""

    payload: Path
    manifest: Path
    lock: Path


def analysis_artifact_paths(path: str | os.PathLike[str]) -> AnalysisArtifactPaths:
    """Derive deterministic sidecars for an analysis JSON payload."""

    payload = Path(path)
    paths = AnalysisArtifactPaths(
        payload=payload,
        manifest=payload.with_suffix(".manifest.json"),
        lock=payload.with_suffix(".lock"),
    )
    if len({paths.payload, paths.manifest, paths.lock}) != 3:
        raise ValueError("analysis payload path collides with a managed sidecar")
    return paths


def _assert_finite_json(value: object, *, location: str = "$") -> None:
    """Accept only built-in, finite JSON values with string object keys."""

    value_type = type(value)
    if value is None or value_type in {bool, int, str}:
        return
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError(f"{location} contains a nonfinite number")
        return
    if value_type is list:
        for index, item in enumerate(value):
            _assert_finite_json(item, location=f"{location}[{index}]")
        return
    if value_type is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError(f"{location} contains a non-string object key")
            _assert_finite_json(item, location=f"{location}.{key}")
        return
    raise ValueError(f"{location} contains non-JSON type {value_type.__name__}")


def canonical_json_bytes(payload: object) -> bytes:
    """Return a deterministic UTF-8 encoding of finite built-in JSON data."""

    _assert_finite_json(payload)
    try:
        serialized = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return serialized.encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValueError("payload must be canonical finite UTF-8 JSON data") from error


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def build_identity(profile: str, record: dict[str, object]) -> dict[str, object]:
    """Bind a named identity record to its canonical SHA-256 digest."""

    if type(profile) is not str or not profile:
        raise ValueError("identity profile must be a nonempty built-in string")
    if type(record) is not dict:
        raise ValueError("identity record must be a built-in JSON object")
    record_bytes = canonical_json_bytes(record)
    return {"profile": profile, "record": record, "sha256": _sha256_bytes(record_bytes)}


def _require_exact_keys(value: object, expected: set[str], *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise AnalysisArtifactValidationError(f"{label} must be a JSON object")
    actual = set(value)
    if actual != expected:
        raise AnalysisArtifactValidationError(
            f"{label} keys differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return value


def _identity_error(identity: object, *, label: str) -> str | None:
    if type(identity) is not dict:
        return f"{label} must be a JSON object"
    if set(identity) != {"profile", "record", "sha256"}:
        return f"{label} must contain exactly profile, record, and sha256"
    profile = identity["profile"]
    record = identity["record"]
    checksum = identity["sha256"]
    if type(profile) is not str or not profile:
        return f"{label} profile is invalid"
    if type(record) is not dict:
        return f"{label} record must be a JSON object"
    if not _valid_sha256(checksum):
        return f"{label} checksum is malformed"
    try:
        expected_checksum = _sha256_bytes(canonical_json_bytes(record))
    except ValueError:
        return f"{label} record is not finite canonical JSON"
    if checksum != expected_checksum:
        return f"{label} checksum does not match its record"
    return None


def _validate_expected_identity(identity: object) -> dict[str, object]:
    error = _identity_error(identity, label="expected identity")
    if error is not None:
        raise ValueError(error)
    return identity  # type: ignore[return-value]


def _validate_manifest_identity(identity: object) -> dict[str, object]:
    error = _identity_error(identity, label="analysis manifest identity")
    if error is not None:
        raise AnalysisArtifactValidationError(error)
    return identity  # type: ignore[return-value]


def _valid_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _open_flags(*, write: bool = False, create: bool = False) -> int:
    flags = os.O_RDWR if write else os.O_RDONLY
    if create:
        flags |= os.O_CREAT
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    return flags


def _stat_signature(file_stat: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


def _open_regular_descriptor(path: Path, *, label: str) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        try:
            if stat.S_ISLNK(path.lstat().st_mode):
                raise AnalysisArtifactValidationError(f"{label} is a symbolic link: {path}")
        except FileNotFoundError as error:
            raise AnalysisArtifactValidationError(f"{label} is missing: {path}") from error
    try:
        descriptor = os.open(path, _open_flags())
    except OSError as error:
        raise AnalysisArtifactValidationError(
            f"{label} is missing, symbolic, or not a regular file: {path}"
        ) from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AnalysisArtifactValidationError(f"{label} is not a regular file: {path}")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _read_regular_bytes(path: Path, *, max_bytes: int, label: str) -> tuple[bytes, os.stat_result]:
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive built-in integer")
    descriptor = _open_regular_descriptor(path, label=label)
    try:
        before = os.fstat(descriptor)
        if before.st_size > max_bytes:
            raise AnalysisArtifactValidationError(
                f"{label} exceeds the {max_bytes}-byte safety limit: {path}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise AnalysisArtifactValidationError(
                    f"{label} exceeds the {max_bytes}-byte safety limit: {path}"
                )
        after = os.fstat(descriptor)
    except BaseException:
        os.close(descriptor)
        raise
    os.close(descriptor)
    if _stat_signature(before) != _stat_signature(after) or total != after.st_size:
        raise AnalysisArtifactValidationError(f"{label} changed while it was being read: {path}")
    return b"".join(chunks), after


def _fingerprint_label(path: Path, root: Path | None) -> str:
    if root is None:
        return path.as_posix()
    absolute_path = Path(os.path.abspath(os.fspath(path)))
    absolute_root = Path(os.path.abspath(os.fspath(root)))
    try:
        return absolute_path.relative_to(absolute_root).as_posix()
    except ValueError as error:
        raise ValueError(f"input path is outside fingerprint root: {path}") from error


def fingerprint_regular_file(
    path: str | os.PathLike[str],
    *,
    root: str | os.PathLike[str] | None = None,
    max_bytes: int = MAX_INPUT_FILE_BYTES,
) -> dict[str, object]:
    """Hash one non-symlink regular file through the descriptor being checked."""

    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive built-in integer")
    input_path = Path(path)
    relative_root = Path(root) if root is not None else None
    input_label = _fingerprint_label(input_path, relative_root)
    descriptor = _open_regular_descriptor(input_path, label="analysis input")
    digest = hashlib.sha256()
    total = 0
    try:
        before = os.fstat(descriptor)
        if before.st_size > max_bytes:
            raise AnalysisArtifactValidationError(
                f"analysis input exceeds the {max_bytes}-byte safety limit: {input_path}"
            )
        while chunk := os.read(descriptor, _READ_CHUNK_BYTES):
            total += len(chunk)
            if total > max_bytes:
                raise AnalysisArtifactValidationError(
                    f"analysis input exceeds the {max_bytes}-byte safety limit: {input_path}"
                )
            digest.update(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if _stat_signature(before) != _stat_signature(after) or total != after.st_size:
        raise AnalysisArtifactValidationError(
            f"analysis input changed while it was being fingerprinted: {input_path}"
        )
    return {
        "path": input_label,
        "sha256": digest.hexdigest(),
        "size_bytes": total,
    }


def fingerprint_regular_files(
    paths: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...],
    *,
    root: str | os.PathLike[str] | None = None,
    max_file_bytes: int = MAX_INPUT_FILE_BYTES,
) -> dict[str, object]:
    """Fingerprint an exact, closed set of inputs in path-sorted order."""

    if type(paths) not in {list, tuple}:
        raise ValueError("paths must be a built-in list or tuple")
    if not paths:
        raise ValueError("input set must contain at least one regular file")
    records = [
        fingerprint_regular_file(path, root=root, max_bytes=max_file_bytes) for path in paths
    ]
    labels = [record["path"] for record in records]
    if len(set(labels)) != len(labels):
        raise ValueError("input set contains duplicate fingerprint paths")
    records.sort(key=lambda record: record["path"])  # type: ignore[arg-type, return-value]
    return build_identity(INPUT_SET_PROFILE, {"files": records})


def analysis_software_identity(
    package_root: str | os.PathLike[str] | None = None,
) -> dict[str, object]:
    """Bind analysis output to package source and numerical dependencies."""

    from tetris_ballistic.run_artifacts import software_identity

    dependency_versions: dict[str, str] = {}
    for distribution in ("matplotlib", "scipy"):
        try:
            dependency_versions[distribution] = version(distribution)
        except PackageNotFoundError:
            dependency_versions[distribution] = "unavailable"
    record: dict[str, object] = {
        "analysis_artifact_schema_version": ANALYSIS_ARTIFACT_SCHEMA_VERSION,
        "dependency_versions": dependency_versions,
        "engine": software_identity(package_root),
    }
    return build_identity(SOFTWARE_PROFILE, record)


def settings_identity(settings: dict[str, object]) -> dict[str, object]:
    """Canonical identity for estimator settings and algorithm policy."""

    return build_identity(SETTINGS_PROFILE, settings)


def rng_identity(rng: dict[str, object]) -> dict[str, object]:
    """Canonical identity for analysis RNG algorithms, seeds, and stream policy."""

    return build_identity(RNG_PROFILE, rng)


def build_analysis_identity(
    *,
    artifact_kind: str,
    inputs: dict[str, object],
    settings: dict[str, object],
    rng: dict[str, object],
    software: dict[str, object] | None = None,
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the complete identity used to decide analysis-cache reuse."""

    if type(artifact_kind) is not str or not artifact_kind:
        raise ValueError("artifact_kind must be a nonempty built-in string")
    input_error = _identity_error(inputs, label="input identity")
    if input_error is not None:
        raise ValueError(input_error)
    current_software = analysis_software_identity() if software is None else software
    software_error = _identity_error(current_software, label="software identity")
    if software_error is not None:
        raise ValueError(software_error)
    if context is None:
        context = {}
    if type(context) is not dict:
        raise ValueError("analysis identity context must be a built-in JSON object")
    record = {
        "artifact_kind": artifact_kind,
        "context": context,
        "inputs": inputs,
        "rng": rng_identity(rng),
        "settings": settings_identity(settings),
        "software": current_software,
    }
    return build_identity(ANALYSIS_IDENTITY_PROFILE, record)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AnalysisArtifactValidationError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> object:
    raise AnalysisArtifactValidationError(f"JSON contains nonfinite constant {value}")


def _decode_json(payload: bytes, *, label: str) -> object:
    try:
        decoded = payload.decode("utf-8")
        value = json.loads(
            decoded,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
        _assert_finite_json(value)
    except AnalysisArtifactValidationError:
        raise
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise AnalysisArtifactValidationError(f"{label} is not finite duplicate-free UTF-8 JSON") from error
    return value


def _load_manifest(paths: AnalysisArtifactPaths) -> dict[str, object]:
    manifest_bytes, _ = _read_regular_bytes(
        paths.manifest,
        max_bytes=MAX_MANIFEST_BYTES,
        label="analysis manifest",
    )
    manifest = _decode_json(manifest_bytes, label="analysis manifest")
    return _require_exact_keys(
        manifest,
        {
            "artifact",
            "completed_utc",
            "generation_id",
            "identity",
            "schema_version",
            "status",
        },
        label="analysis manifest root",
    )


def _validate_utc_timestamp(value: object) -> None:
    if type(value) is not str or not value:
        raise AnalysisArtifactValidationError("analysis manifest completion time is invalid")
    try:
        completed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as error:
        raise AnalysisArtifactValidationError("analysis manifest completion time is invalid") from error
    if completed.utcoffset() != timedelta(0):
        raise AnalysisArtifactValidationError("analysis manifest completion time is not UTC")


def _validate_generation_id(value: object) -> None:
    if (
        type(value) is not str
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AnalysisArtifactValidationError("analysis manifest generation id is invalid")


def load_json_artifact(
    path: str | os.PathLike[str],
    expected_identity: dict[str, object],
    *,
    max_payload_bytes: int = MAX_JSON_PAYLOAD_BYTES,
) -> object:
    """Load a JSON payload only after its commit marker and identity verify."""

    expected = _validate_expected_identity(expected_identity)
    if type(max_payload_bytes) is not int or max_payload_bytes <= 0:
        raise ValueError("max_payload_bytes must be a positive built-in integer")
    paths = analysis_artifact_paths(path)
    manifest = _load_manifest(paths)
    if (
        manifest["schema_version"] != ANALYSIS_ARTIFACT_SCHEMA_VERSION
        or manifest["status"] != "complete"
    ):
        raise AnalysisArtifactValidationError(
            "analysis manifest is not a supported complete artifact"
        )
    _validate_utc_timestamp(manifest["completed_utc"])
    _validate_generation_id(manifest["generation_id"])
    observed_identity = _validate_manifest_identity(manifest["identity"])
    if canonical_json_bytes(observed_identity) != canonical_json_bytes(expected):
        raise AnalysisArtifactValidationError(
            "analysis artifact identity does not match the current request"
        )

    artifact = _require_exact_keys(
        manifest["artifact"], {"filename", "sha256", "size_bytes"}, label="analysis artifact"
    )
    if artifact["filename"] != paths.payload.name:
        raise AnalysisArtifactValidationError(
            "analysis artifact filename does not match the requested path"
        )
    if not _valid_sha256(artifact["sha256"]):
        raise AnalysisArtifactValidationError("analysis artifact checksum is malformed")
    size = artifact["size_bytes"]
    if type(size) is not int or size < 0:
        raise AnalysisArtifactValidationError("analysis artifact size is invalid")
    if size > max_payload_bytes:
        raise AnalysisArtifactValidationError(
            f"analysis artifact exceeds the {max_payload_bytes}-byte safety limit"
        )
    payload_bytes, payload_stat = _read_regular_bytes(
        paths.payload,
        max_bytes=max_payload_bytes,
        label="analysis payload",
    )
    if payload_stat.st_size != size:
        raise AnalysisArtifactValidationError("analysis payload size does not match manifest")
    if _sha256_bytes(payload_bytes) != artifact["sha256"]:
        raise AnalysisArtifactValidationError("analysis payload checksum does not match manifest")
    return _decode_json(payload_bytes, label="analysis payload")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, _open_flags())
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _temporary_path(target: Path) -> Path:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    return Path(temporary)


def _write_fsynced(path: Path, payload: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _remove_commit_marker(paths: AnalysisArtifactPaths) -> None:
    if not _lexists(paths.manifest):
        return
    try:
        mode = paths.manifest.lstat().st_mode
        if stat.S_ISDIR(mode):
            raise AnalysisArtifactValidationError(
                f"analysis manifest is a directory and cannot be invalidated: {paths.manifest}"
            )
        paths.manifest.unlink()
        _fsync_directory(paths.manifest.parent)
    except AnalysisArtifactValidationError:
        raise
    except OSError as error:
        raise AnalysisArtifactValidationError(
            f"analysis manifest cannot be invalidated: {paths.manifest}"
        ) from error


def cleanup_analysis_temporaries(path: str | os.PathLike[str]) -> None:
    """Remove only unique managed temporaries while holding the artifact lock."""

    paths = analysis_artifact_paths(path)
    for target in (paths.payload, paths.manifest):
        for temporary in target.parent.glob(f".{target.name}.*.tmp"):
            try:
                temporary_stat = temporary.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(temporary_stat.st_mode):
                temporary.unlink()


@contextmanager
def analysis_artifact_lock(
    path: str | os.PathLike[str] | AnalysisArtifactPaths,
) -> Iterator[AnalysisArtifactPaths]:
    """Hold a persistent-inode exclusive lock across validation and publish."""

    paths = path if type(path) is AnalysisArtifactPaths else analysis_artifact_paths(path)
    paths.lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(paths.lock, _open_flags(write=True, create=True), 0o600)
    except OSError as error:
        raise AnalysisArtifactValidationError(
            f"cannot open persistent analysis lock: {paths.lock}"
        ) from error
    lock_ready = False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AnalysisArtifactValidationError(
                f"persistent analysis lock is not a regular file: {paths.lock}"
            )
        flock(descriptor, LOCK_EX)
        lock_ready = True
        metadata = {
            "acquired_utc": datetime.now(timezone.utc).isoformat(),
            "hostname": platform.node(),
            "pid": os.getpid(),
        }
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, canonical_json_bytes(metadata) + b"\n")
        os.fsync(descriptor)
        _fsync_directory(paths.lock.parent)
        yield paths
    finally:
        if lock_ready:
            try:
                os.ftruncate(descriptor, 0)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        else:
            os.close(descriptor)


def invalidate_json_artifact(
    path: str | os.PathLike[str], *, lock_held: bool = False
) -> None:
    """Remove only the manifest, making any remaining payload non-reusable."""

    paths = analysis_artifact_paths(path)
    if lock_held:
        _remove_commit_marker(paths)
        return
    with analysis_artifact_lock(paths):
        _remove_commit_marker(paths)


def _write_json_artifact_locked(
    paths: AnalysisArtifactPaths,
    *,
    payload_bytes: bytes,
    identity: dict[str, object],
) -> Path:
    cleanup_analysis_temporaries(paths.payload)
    # Invalidate an older generation before any fallible staging work.  A
    # crash can leave an orphan payload, never a reusable stale commit marker.
    _remove_commit_marker(paths)
    temporaries: list[Path] = []
    try:
        payload_temporary = _temporary_path(paths.payload)
        temporaries.append(payload_temporary)
        manifest_temporary = _temporary_path(paths.manifest)
        temporaries.append(manifest_temporary)
        _write_fsynced(payload_temporary, payload_bytes)
        manifest = {
            "artifact": {
                "filename": paths.payload.name,
                "sha256": _sha256_bytes(payload_bytes),
                "size_bytes": len(payload_bytes),
            },
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "generation_id": uuid.uuid4().hex,
            "identity": identity,
            "schema_version": ANALYSIS_ARTIFACT_SCHEMA_VERSION,
            "status": "complete",
        }
        _write_fsynced(manifest_temporary, canonical_json_bytes(manifest) + b"\n")

        os.replace(payload_temporary, paths.payload)
        _fsync_directory(paths.payload.parent)
        os.replace(manifest_temporary, paths.manifest)
        try:
            _fsync_directory(paths.manifest.parent)
        except BaseException:
            try:
                paths.manifest.unlink()
                _fsync_directory(paths.manifest.parent)
            except OSError:
                pass
            raise
        return paths.manifest
    finally:
        for temporary in temporaries:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def write_json_artifact(
    path: str | os.PathLike[str],
    payload: object,
    identity: dict[str, object],
    *,
    max_payload_bytes: int = MAX_JSON_PAYLOAD_BYTES,
    lock_held: bool = False,
) -> Path:
    """Atomically publish a finite JSON payload and its manifest last.

    By default this function acquires the artifact lock.  A caller that holds
    :func:`analysis_artifact_lock` across validation, computation, and commit
    must pass ``lock_held=True`` to avoid recursively acquiring the lock.
    """

    expected = _validate_expected_identity(identity)
    if type(max_payload_bytes) is not int or max_payload_bytes <= 0:
        raise ValueError("max_payload_bytes must be a positive built-in integer")
    payload_bytes = canonical_json_bytes(payload) + b"\n"
    if len(payload_bytes) > max_payload_bytes:
        raise ValueError(f"analysis payload exceeds the {max_payload_bytes}-byte safety limit")
    paths = analysis_artifact_paths(path)
    paths.payload.parent.mkdir(parents=True, exist_ok=True)
    if lock_held:
        return _write_json_artifact_locked(
            paths, payload_bytes=payload_bytes, identity=expected
        )
    with analysis_artifact_lock(paths):
        return _write_json_artifact_locked(
            paths, payload_bytes=payload_bytes, identity=expected
        )
