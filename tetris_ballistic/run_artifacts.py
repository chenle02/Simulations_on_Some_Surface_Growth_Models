"""Identity-bound, atomic persistence for managed simulation cells.

The manifest is the commit marker: a managed cell is reusable only when its
manifest, configuration snapshot, serialized simulation, checksums, software
identity, and completion invariants all agree with the requested run.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from fcntl import LOCK_EX, flock
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

import joblib
import numpy as np
import yaml

ARTIFACT_SCHEMA_VERSION = "tetris-managed-run-v1"
CONFIGURATION_PROFILE = "legacy-cell-configuration-sha256-v1"
SOFTWARE_PROFILE = "tetris-python-tree-sha256-v1"
RUN_IDENTITY_PROFILE = "tetris-managed-run-sha256-v1"
MAX_MANIFEST_BYTES = 1_000_000
_PROJECT_VERSION_PATTERN = re.compile(
    r'^version\s*=\s*["\']([^"\']+)["\']\s*(?:#.*)?$', re.MULTILINE
)


class ArtifactValidationError(RuntimeError):
    """A managed output exists but cannot be trusted or reused."""


@dataclass(frozen=True)
class ArtifactPaths:
    joblib: Path
    config: Path
    manifest: Path
    lock: Path


@dataclass(frozen=True)
class RunExpectation:
    config_data: dict[str, object]
    config_bytes: bytes
    configuration_identity: dict[str, object]
    software_identity: dict[str, object]
    run_identity: dict[str, str]


class CellDisposition(str, Enum):
    CREATED = "created"
    REUSED = "reused"


@dataclass(frozen=True)
class RunArtifactResult:
    path: Path
    disposition: CellDisposition
    manifest_path: Path

    @property
    def reused(self) -> bool:
        return self.disposition is CellDisposition.REUSED


def artifact_paths(joblib_path: str | os.PathLike[str], config_path: str | os.PathLike[str]) -> ArtifactPaths:
    """Return every managed path derived from a joblib/config pair."""

    joblib_target = Path(joblib_path)
    return ArtifactPaths(
        joblib=joblib_target,
        config=Path(config_path),
        manifest=joblib_target.with_suffix(".manifest.json"),
        lock=joblib_target.with_suffix(".lock"),
    )


def _canonical_json_bytes(payload: object) -> bytes:
    try:
        serialized = json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("run identity payload must be finite JSON data") from error
    return serialized.encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_matches(observed: object, expected: object) -> bool:
    """Compare JSON identities without Python's ``True == 1`` coercion."""

    try:
        return _canonical_json_bytes(observed) == _canonical_json_bytes(expected)
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_positive_int(value: object, *, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive built-in integer")
    return value


def _source_declared_version(package_root: Path) -> str:
    """Read the source checkout's PEP 621 version without importing build code."""

    pyproject_path = package_root.parent / "pyproject.toml"
    try:
        text = pyproject_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "unavailable"
    project_start = text.find("[project]")
    if project_start < 0:
        return "unavailable"
    following_section = text.find("\n[", project_start + len("[project]"))
    project_section = text[project_start : following_section if following_section >= 0 else None]
    match = _PROJECT_VERSION_PATTERN.search(project_section)
    return match.group(1) if match else "unavailable"


def software_identity(package_root: str | os.PathLike[str] | None = None) -> dict[str, object]:
    """Hash the installed Python source tree and record its runtime version."""

    root = Path(package_root) if package_root is not None else Path(__file__).resolve().parent
    source_paths = sorted(root.rglob("*.py"), key=lambda path: path.relative_to(root).as_posix())
    if not source_paths:
        raise RuntimeError(f"no Python sources found under package root {root}")

    digest = hashlib.sha256()
    for source_path in source_paths:
        file_stat = source_path.lstat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise RuntimeError(f"software identity source is not a regular file: {source_path}")
        relative = source_path.relative_to(root).as_posix().encode("utf-8")
        content = source_path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)

    try:
        distribution_metadata_version = version("tetris_ballistic")
    except PackageNotFoundError:
        distribution_metadata_version = "unavailable"
    try:
        numba_version = version("numba")
    except PackageNotFoundError:
        numba_version = "unavailable"
    record = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "distribution_metadata_version": distribution_metadata_version,
        "joblib_version": joblib.__version__,
        "numpy_version": np.__version__,
        "numba_version": numba_version,
        "python_source_tree_sha256": digest.hexdigest(),
        "python_version": platform.python_version(),
        "rng_contract_version": "legacy-dual-stream-v1",
        "source_declared_version": _source_declared_version(root),
    }
    return {
        "profile": SOFTWARE_PROFILE,
        "record": record,
        "sha256": _sha256_bytes(_canonical_json_bytes(record)),
    }


def build_run_expectation(
    *,
    width: object,
    height: object,
    steps: object,
    seed: object,
    density: object,
    engine_route: str,
    semantic_context: object | None = None,
) -> RunExpectation:
    """Canonicalize one legacy cell and bind it to the current software."""

    from tetris_ballistic.tetris_ballistic import _config_seed, _validate_legacy_density

    canonical_width = _require_positive_int(width, name="width")
    canonical_height = _require_positive_int(height, name="height")
    canonical_steps = _require_positive_int(steps, name="steps")
    canonical_seed = _config_seed(seed)
    canonical_density = _validate_legacy_density(density)
    config_data: dict[str, object] = dict(canonical_density)
    config_data.update(
        {
            "height": canonical_height,
            "seed": canonical_seed,
            "steps": canonical_steps,
            "width": canonical_width,
        }
    )
    if type(engine_route) is not str or not engine_route:
        raise ValueError("engine_route must be a nonempty built-in string")
    if semantic_context is None:
        semantic_context = {}
    if type(semantic_context) is not dict:
        raise ValueError("semantic_context must be a built-in mapping")
    canonical_semantic_context = json.loads(_canonical_json_bytes(semantic_context))
    from tetris_ballistic.tetris_ballistic import LEGACY_RNG_CONTRACT_VERSION

    configuration_record = {
        "constructor": config_data,
        "engine_route": engine_route,
        "rng_contract_version": LEGACY_RNG_CONTRACT_VERSION,
        "semantics": canonical_semantic_context,
    }
    config_payload = _canonical_json_bytes(configuration_record)
    config_identity = {
        "profile": CONFIGURATION_PROFILE,
        "record": configuration_record,
        "sha256": _sha256_bytes(config_payload),
    }
    current_software = software_identity()
    run_identity = {
        "profile": RUN_IDENTITY_PROFILE,
        "sha256": _sha256_bytes(
            _canonical_json_bytes(
                {
                    "configuration": config_identity,
                    "software": current_software,
                }
            )
        ),
    }
    config_bytes = yaml.safe_dump(
        config_data,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=True,
    ).encode("utf-8")
    return RunExpectation(
        config_data=config_data,
        config_bytes=config_bytes,
        configuration_identity=config_identity,
        software_identity=current_software,
        run_identity=run_identity,
    )


def resolve_engine_route(density: dict[str, object]) -> str:
    """Resolve the simulation path whose numerical output will be persisted."""

    if os.environ.get("TETRIS_USE_KERNEL", "1") == "0":
        return "python-dispatch-v1"
    try:
        from tetris_ballistic._kernel_1x1 import is_1x1_only
    except ImportError:
        return "python-dispatch-v1"
    return "numba-1x1-v1" if is_1x1_only(density) else "python-dispatch-v1"


def _is_filesystem_entry(path: Path) -> bool:
    return os.path.lexists(path)


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ArtifactValidationError(f"managed manifest contains duplicate key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ArtifactValidationError(f"managed manifest contains nonfinite constant {value}")


def _load_manifest(path: Path) -> dict[str, object]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactValidationError(f"managed manifest is missing or nonregular: {path}") from error
    try:
        with os.fdopen(descriptor, "rb") as handle:
            file_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise ArtifactValidationError(f"managed manifest is not a regular file: {path}")
            if file_stat.st_size > MAX_MANIFEST_BYTES:
                raise ArtifactValidationError(
                    f"managed manifest exceeds {MAX_MANIFEST_BYTES} bytes: {path}"
                )
            manifest_bytes = handle.read(MAX_MANIFEST_BYTES + 1)
        manifest_text = manifest_bytes.decode("utf-8")
        payload = json.loads(
            manifest_text,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_json_constant,
        )
    except ArtifactValidationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactValidationError(f"managed manifest is unreadable: {path}") from error
    if type(payload) is not dict:
        raise ArtifactValidationError("managed manifest must be a JSON object")
    return payload


def _require_exact_keys(payload: object, expected: set[str], *, label: str) -> dict[str, object]:
    if type(payload) is not dict:
        raise ArtifactValidationError(f"managed manifest {label} must be an object")
    actual = set(payload)
    if actual != expected:
        raise ArtifactValidationError(
            f"managed manifest {label} keys differ: missing={sorted(expected - actual)}, "
            f"unexpected={sorted(actual - expected)}"
        )
    return payload


def _completion_record(simulation: object, expectation: RunExpectation) -> dict[str, object]:
    from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

    if type(simulation) is not Tetris_Ballistic:
        raise ArtifactValidationError("managed joblib does not contain Tetris_Ballistic")
    expected = expectation.config_data
    for name in ("width", "height", "steps", "seed"):
        observed = getattr(simulation, name, object())
        if type(observed) is not type(expected[name]) or observed != expected[name]:
            raise ArtifactValidationError(f"managed simulation {name} does not match configuration")
    if not _canonical_json_matches(simulation.config_data, expected):
        raise ArtifactValidationError("managed simulation config_data does not match configuration")

    final_steps = simulation.FinalSteps
    requested_steps = expected["steps"]
    if type(final_steps) is not int or not 0 <= final_steps <= requested_steps:
        raise ArtifactValidationError("managed simulation FinalSteps is outside the requested range")
    expected_trace_length = requested_steps if final_steps == requested_steps else final_steps
    fluctuation = np.asarray(simulation.Fluctuation)
    average_height = np.asarray(simulation.AvergeHeight)
    if fluctuation.shape != (expected_trace_length,) or average_height.shape != (
        expected_trace_length,
    ):
        raise ArtifactValidationError("managed simulation trace lengths do not match completion")
    if not np.all(np.isfinite(fluctuation)) or not np.all(np.isfinite(average_height)):
        raise ArtifactValidationError("managed simulation traces contain nonfinite values")

    substrate = np.asarray(simulation.substrate)
    if substrate.shape != (expected["height"], expected["width"]):
        raise ArtifactValidationError("managed simulation substrate shape does not match configuration")
    if not np.all(np.isfinite(substrate)):
        raise ArtifactValidationError("managed simulation substrate contains nonfinite values")
    sample_dist = np.asarray(simulation.SampleDist)
    if sample_dist.shape != (20, 2) or not np.all(np.isfinite(sample_dist)):
        raise ArtifactValidationError("managed simulation SampleDist is invalid")
    attempted_events = requested_steps if final_steps == requested_steps else final_steps + 1
    if float(sample_dist.sum()) != float(attempted_events):
        raise ArtifactValidationError("managed simulation attempted-event count is inconsistent")

    rng_metadata = getattr(simulation, "rng_contract_metadata", None)
    software_record = expectation.software_identity["record"]
    if (
        not isinstance(rng_metadata, dict)
        or rng_metadata.get("root_seed") != expected["seed"]
        or rng_metadata.get("contract_version") != software_record["rng_contract_version"]
        or rng_metadata.get("python_version") != software_record["python_version"]
        or rng_metadata.get("numpy_version") != software_record["numpy_version"]
    ):
        raise ArtifactValidationError("managed simulation RNG identity is missing or inconsistent")
    return {
        "attempted_events": attempted_events,
        "final_steps": final_steps,
        "reason": "steps_exhausted" if final_steps == requested_steps else "top_reached",
        "requested_steps": requested_steps,
    }


@contextmanager
def _verified_artifact(
    entry: object,
    *,
    path: Path,
    label: str,
) -> Iterator[BinaryIO]:
    artifact = _require_exact_keys(entry, {"filename", "sha256", "size_bytes"}, label=label)
    if artifact["filename"] != path.name:
        raise ArtifactValidationError(f"managed {label} filename does not match requested path")
    checksum = artifact["sha256"]
    if type(checksum) is not str or len(checksum) != 64 or any(
        character not in "0123456789abcdef" for character in checksum
    ):
        raise ArtifactValidationError(f"managed {label} checksum is malformed")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ArtifactValidationError(f"managed {label} is missing or nonregular: {path}") from error
    with os.fdopen(descriptor, "rb") as handle:
        file_stat = os.fstat(handle.fileno())
        if not stat.S_ISREG(file_stat.st_mode):
            raise ArtifactValidationError(f"managed {label} is not a regular file: {path}")
        if type(artifact["size_bytes"]) is not int or artifact["size_bytes"] != file_stat.st_size:
            raise ArtifactValidationError(f"managed {label} size does not match manifest")
        digest = hashlib.sha256()
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
        if digest.hexdigest() != checksum:
            raise ArtifactValidationError(f"managed {label} checksum does not match manifest")
        handle.seek(0)
        yield handle


def validate_completed_run(
    paths: ArtifactPaths,
    expectation: RunExpectation,
) -> object:
    """Validate a complete managed bundle before returning its simulation."""

    manifest = _load_manifest(paths.manifest)
    manifest = _require_exact_keys(
        manifest,
        {
            "artifacts",
            "completed_utc",
            "completion",
            "configuration",
            "generation_id",
            "run_identity",
            "schema_version",
            "software",
            "status",
        },
        label="root",
    )
    if manifest["schema_version"] != ARTIFACT_SCHEMA_VERSION or manifest["status"] != "complete":
        raise ArtifactValidationError("managed manifest is not a supported complete artifact")
    completed_utc = manifest["completed_utc"]
    if type(completed_utc) is not str or not completed_utc:
        raise ArtifactValidationError("managed manifest completion time is invalid")
    try:
        completed_time = datetime.fromisoformat(completed_utc)
    except ValueError as error:
        raise ArtifactValidationError("managed manifest completion time is invalid") from error
    if completed_time.utcoffset() != timedelta(0):
        raise ArtifactValidationError("managed manifest completion time is not UTC")
    generation_id = manifest["generation_id"]
    if type(generation_id) is not str or len(generation_id) != 32 or any(
        character not in "0123456789abcdef" for character in generation_id
    ):
        raise ArtifactValidationError("managed manifest generation id is invalid")
    if not _canonical_json_matches(manifest["configuration"], expectation.configuration_identity):
        raise ArtifactValidationError("managed output configuration identity does not match request")
    if not _canonical_json_matches(manifest["software"], expectation.software_identity):
        raise ArtifactValidationError("managed output software identity does not match current code")
    if not _canonical_json_matches(manifest["run_identity"], expectation.run_identity):
        raise ArtifactValidationError("managed output run identity does not match request")

    artifacts = _require_exact_keys(manifest["artifacts"], {"config", "joblib"}, label="artifacts")
    with _verified_artifact(artifacts["config"], path=paths.config, label="config") as config_handle:
        if config_handle.read() != expectation.config_bytes:
            raise ArtifactValidationError("managed config snapshot does not match requested configuration")

    try:
        with _verified_artifact(
            artifacts["joblib"], path=paths.joblib, label="joblib"
        ) as joblib_handle:
            simulation = joblib.load(joblib_handle)
    except ArtifactValidationError:
        raise
    except Exception as error:
        raise ArtifactValidationError(f"managed joblib cannot be loaded: {paths.joblib}") from error
    completion = _completion_record(simulation, expectation)
    if not _canonical_json_matches(manifest["completion"], completion):
        raise ArtifactValidationError("managed completion record does not match simulation")
    return simulation


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _temporary_path(target: Path) -> Path:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    os.close(descriptor)
    return Path(temporary)


def atomic_write_bytes(target: str | os.PathLike[str], payload: bytes) -> None:
    """Atomically replace one file using a unique same-directory temporary."""

    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target_path)
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target_path)
        _fsync_directory(target_path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def atomic_joblib_dump(value: object, target: str | os.PathLike[str]) -> None:
    """Atomically replace one joblib using a unique same-directory temporary."""

    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(target_path)
    try:
        joblib.dump(value, temporary)
        _fsync_file(temporary)
        os.replace(temporary, target_path)
        _fsync_directory(target_path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _manifest_record(
    *,
    paths: ArtifactPaths,
    expectation: RunExpectation,
    completion: dict[str, object],
    joblib_temporary: Path,
    config_temporary: Path,
) -> dict[str, object]:
    return {
        "artifacts": {
            "config": {
                "filename": paths.config.name,
                "sha256": _sha256_file(config_temporary),
                "size_bytes": config_temporary.stat().st_size,
            },
            "joblib": {
                "filename": paths.joblib.name,
                "sha256": _sha256_file(joblib_temporary),
                "size_bytes": joblib_temporary.stat().st_size,
            },
        },
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "completion": completion,
        "configuration": expectation.configuration_identity,
        "generation_id": uuid.uuid4().hex,
        "run_identity": expectation.run_identity,
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "software": expectation.software_identity,
        "status": "complete",
    }


def publish_completed_run(
    simulation: object,
    paths: ArtifactPaths,
    expectation: RunExpectation,
) -> None:
    """Serialize a complete bundle and publish its manifest last."""

    completion = _completion_record(simulation, expectation)
    if any(_is_filesystem_entry(path) for path in (paths.joblib, paths.config, paths.manifest)):
        raise ArtifactValidationError("managed output appeared before publication")

    temporaries: list[Path] = []
    try:
        for target in (paths.joblib, paths.config, paths.manifest):
            temporaries.append(_temporary_path(target))
        joblib_temporary, config_temporary, manifest_temporary = temporaries
        joblib.dump(simulation, joblib_temporary)
        _fsync_file(joblib_temporary)
        try:
            staged_simulation = joblib.load(joblib_temporary)
        except Exception as error:
            raise ArtifactValidationError("staged managed joblib cannot be loaded") from error
        if not _canonical_json_matches(_completion_record(staged_simulation, expectation), completion):
            raise ArtifactValidationError("staged managed joblib changed during serialization")
        with config_temporary.open("wb") as handle:
            handle.write(expectation.config_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        manifest = _manifest_record(
            paths=paths,
            expectation=expectation,
            completion=completion,
            joblib_temporary=joblib_temporary,
            config_temporary=config_temporary,
        )
        with manifest_temporary.open("wb") as handle:
            handle.write(json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())

        if any(_is_filesystem_entry(path) for path in (paths.joblib, paths.config, paths.manifest)):
            raise ArtifactValidationError("managed output appeared during publication")
        os.replace(joblib_temporary, paths.joblib)
        os.replace(config_temporary, paths.config)
        _fsync_directory(paths.joblib.parent)
        os.replace(manifest_temporary, paths.manifest)
        try:
            _fsync_directory(paths.joblib.parent)
        except BaseException:
            try:
                paths.manifest.unlink()
            except OSError:
                pass
            raise
    finally:
        for temporary in temporaries:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


@contextmanager
def managed_cell_lock(paths: ArtifactPaths) -> Iterator[None]:
    """Hold a persistent-inode advisory lock from validation through commit."""

    paths.lock.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(paths.lock, flags, 0o600)
    except OSError as error:
        raise ArtifactValidationError(f"cannot open managed cell lock: {paths.lock}") from error
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "pid": os.getpid(),
    }
    try:
        flock(descriptor, LOCK_EX)
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, _canonical_json_bytes(metadata) + b"\n")
        os.fsync(descriptor)
        yield
    finally:
        try:
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def managed_outputs_exist(paths: ArtifactPaths) -> bool:
    return any(_is_filesystem_entry(path) for path in (paths.joblib, paths.config, paths.manifest))


def cleanup_stale_temporaries(paths: ArtifactPaths) -> None:
    """Remove only managed unique temps while holding this cell's lock."""

    for target in (paths.joblib, paths.config, paths.manifest):
        pattern = f".{target.name}.*.tmp"
        for temporary in target.parent.glob(pattern):
            try:
                temporary_stat = temporary.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(temporary_stat.st_mode):
                temporary.unlink()


def execute_managed_run(
    *,
    joblib_path: str | os.PathLike[str],
    config_path: str | os.PathLike[str],
    width: object,
    height: object,
    steps: object,
    seed: object,
    density: object,
    engine_route: str,
    semantic_context: object | None = None,
    before_publish: Callable[[object], None] | None = None,
    on_start: Callable[[], None] | None = None,
) -> RunArtifactResult:
    """Reuse one verified cell or exclusively compute and publish it."""

    paths = artifact_paths(joblib_path, config_path)
    if paths.joblib.parent != paths.config.parent:
        raise ValueError("managed joblib and config must share one output directory")
    paths.joblib.parent.mkdir(parents=True, exist_ok=True)
    expectation = build_run_expectation(
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        density=density,
        semantic_context=semantic_context,
        engine_route=engine_route,
    )

    with managed_cell_lock(paths):
        cleanup_stale_temporaries(paths)
        if managed_outputs_exist(paths):
            validate_completed_run(paths, expectation)
            return RunArtifactResult(paths.joblib, CellDisposition.REUSED, paths.manifest)
        if on_start is not None:
            on_start()

        from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

        simulation = Tetris_Ballistic(
            width=expectation.config_data["width"],
            height=expectation.config_data["height"],
            steps=expectation.config_data["steps"],
            seed=expectation.config_data["seed"],
            density={
                f"Piece-{index}": expectation.config_data[f"Piece-{index}"]
                for index in range(20)
            },
        )
        simulation.Simulate()
        if before_publish is not None:
            before_publish(simulation)
        publish_completed_run(simulation, paths, expectation)
    return RunArtifactResult(paths.joblib, CellDisposition.CREATED, paths.manifest)
