"""Fail-closed Slice 8B authority, scheduler, and one-cell lifecycle runner.

This module is deliberately explicit-only.  Importing it performs no file-system
write, checkpoint/Numba import, signal installation, Git command, or scheduler
operation.  Production effects are reachable only through the six public
entrypoints after exact authority validation.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import locale
import os
import re
import selectors
import signal
import stat
import subprocess
import time
from dataclasses import dataclass, fields
from typing import Literal

from .one_cell_campaign import (
    OneCellBootstrapMatrixIdentity,
    OneCellCampaignAuthority,
    OneCellCampaignValidationError,
    OneCellHorizonBranch,
    OneCellTaskMapIdentity,
    decode_one_cell_campaign_task,
    explain_one_cell_campaign_task,
    load_one_cell_campaign,
)

__all__ = [
    "OneCellRunnerValidationError",
    "OneCellRunnerAuthorizationError",
    "OneCellSchedulerError",
    "OneCellLaunchTask",
    "OneCellSlurmResourceEnvelope",
    "OneCellRunnerPaths",
    "OneCellLaunchAuthority",
    "OneCellAuthorizedTask",
    "OneCellRunnerOutcome",
    "OneCellSubmissionOutcome",
    "load_one_cell_launch_authority",
    "list_one_cell_launch_tasks",
    "explain_one_cell_launch_task",
    "authorize_one_cell_slurm_task",
    "run_one_cell_authorized_task",
    "submit_one_cell_launch",
]

_CONTROLLED_EXIT_CODES = frozenset({64, 65, 66, 69, 70, 74, 75, 76, 77, 78})
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_POSITIVE_DECIMAL = re.compile(r"[1-9][0-9]{0,9}\Z")
_SAFE_PATH = re.compile(r"[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*\Z")
_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9._-]+\Z")
_ASCII_TOKEN = re.compile(r"[A-Za-z0-9._-]{1,128}\Z")
_MAIN_FETCH_REFSPEC = "+refs/heads/main:refs/remotes/origin/main"
_MODE_TEXT = re.compile(r"0[0-7]{3}\Z")
_MAX_JSON = 1 << 20
_MAX_JSONL = 64 << 20
_MAX_JSONL_LINE = 1 << 20
_MAX_TASKS = 1_800
_MAX_IDENTITY = 1 << 20
_MAX_TOOL_BYTES = 128 << 20
_MAX_CAPTURE = 8 << 10
_MAX_DIAGNOSTIC = 4 << 10
_U32_MAX = (1 << 32) - 1
_U64_MAX = (1 << 64) - 1
_SLICE_8B_SOFTWARE_PARENT = "b33cc0191298d80f0bdc944a3a5e444952873e37"
_SLICE_8B_COORDINATOR_AUTHORITY = "087cdaf8d8444de7d9548bc1c97ca42f221cef27"

_DEPLOYMENT_LOCK_PROFILE = "tetris-pre-one-cell-deployment-lock@1"
_DEPLOYMENT_PROFILE = "tetris-pre-one-cell-deployment-certificate@1"
_BRANCH_PROFILE = "tetris-pre-one-cell-branch-decision@1"
_HORIZON_BRANCH_PROFILE = "tetris-pre-one-cell-horizon-branch@1"
_ADMISSION_PROFILE = "tetris-pre-one-cell-admission@1"
_COMPLETION_PROFILE = "tetris-pre-one-cell-lane-completion@1"
_FINAL_MANIFEST_ROW_PROFILE = "tetris-pre-one-cell-final-manifest-row@1"
_PRECISION_AUDIT_PROFILE = "tetris-pre-one-cell-b2-precision-audit@1"
_PRECISION_RESULT_PROFILE = "tetris-pre-one-cell-b2-precision-result@1"
_RESOURCE_ADMISSION_PROFILE = "tetris-pre-one-cell-resource-admission@1"
_RESOURCE_ANALYSIS_PROFILE = "tetris-pre-one-cell-resource-analysis@1"
_LAUNCH_TASK_PROFILE = "tetris-pre-one-cell-launch-task@1"
_ORDERED_TASKS_PROFILE = "tetris-pre-one-cell-ordered-tasks@1"
_LAUNCH_PROFILE = "tetris-pre-one-cell-launch@1"
_READBACK_PROFILE = "tetris-pre-one-cell-authority-readback@1"
_RUNNER_PROFILE = "tetris-pre-one-cell-runner@1"
_ARRAY_PROFILE = "tetris-pre-one-cell-slurm-array-position@1"
_RESOURCE_PROFILE = "tetris-pre-one-cell-slurm-resource-envelope@1"
_SCIENTIFIC_ENV_PROFILE = "tetris-pre-one-cell-scientific-process-environment@1"
_SBATCH_ARGV_PROFILE = "tetris-pre-one-cell-sbatch-argv@1"
_CLAIM_PROFILE = "tetris-pre-one-cell-submission-claim@1"
_RECEIPT_PROFILE = "tetris-pre-one-cell-submission-receipt@1"
_RECONCILIATION_PROFILE = "tetris-pre-one-cell-submission-reconciliation@1"
_SCONTROL_ARGV_PROFILE = "tetris-pre-one-cell-scontrol-argv@1"
_PERMIT_PROFILE = "tetris-pre-one-cell-requeue-permit@1"
_RESULT_PROFILE = "tetris-pre-one-cell-requeue-result@1"
_LAUNCH_FIXTURE_PROFILE = "tetris-pre-one-cell-launch-fixture@1"
_ADMISSION_FIXTURE_PROFILE = "tetris-pre-one-cell-admission-fixture@1"

_LANES = frozenset(
    {
        "f0",
        "p0-initial",
        "p0-confirmation",
        "p1-no-l-star",
        "p1-l-star-64",
        "p1-l-star-256",
        "p1-l-star-1024",
        "b1",
        "b2",
    }
)
_LANE_SPECS = {
    "f0": ("f0", "f0", "excluded-forensic-canary", 8),
    "p0-initial": ("p0-initial", "p0", "excluded-horizon-pilot", 48),
    "p0-confirmation": ("p0-confirmation", "p0", "excluded-conditional-confirmation", 1),
    "p1-no-l-star": ("p1-no-l-star", "p1", "clean-primary", 480),
    "p1-l-star-64": ("p1-l-star-64", "p1", "clean-primary", 480),
    "p1-l-star-256": ("p1-l-star-256", "p1", "clean-primary", 480),
    "p1-l-star-1024": ("p1-l-star-1024", "p1", "clean-primary", 480),
    "b1": ("b1", "b1", "boundary-forensic", 384),
    "b2": ("b2", "b2", "historical-grid-correction", 1_800),
}
_SCIENTIFIC_ENV_KEYS = (
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "NUMBA_CACHE_DIR",
    "NUMBA_NUM_THREADS",
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "OMP_DYNAMIC",
    "MKL_DYNAMIC",
)
_GIT_ENVIRONMENT = (
    ("LANG", "C"),
    ("LC_ALL", "C"),
    ("GIT_CONFIG_NOSYSTEM", "1"),
    ("GIT_CONFIG_GLOBAL", "/dev/null"),
    ("GIT_CONFIG_COUNT", "0"),
    ("GIT_ATTR_NOSYSTEM", "1"),
    ("GIT_NO_REPLACE_OBJECTS", "1"),
    ("GIT_OPTIONAL_LOCKS", "0"),
    ("GIT_TERMINAL_PROMPT", "0"),
)
_SCHEDULER_ENVIRONMENT = (("LANG", "C"), ("LC_ALL", "C"))


def _validate_exit_code(value: object, *, default: int) -> int:
    if value is None:
        return default
    if type(value) is not int or value not in _CONTROLLED_EXIT_CODES:
        raise TypeError("exit_code must be an exact controlled built-in integer")
    return value


class OneCellRunnerValidationError(RuntimeError):
    """Canonical or schema input failed closed."""

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        if type(message) is not str:
            raise TypeError("message must be a built-in string")
        super().__init__(message)
        self.exit_code = _validate_exit_code(exit_code, default=65)


class OneCellRunnerAuthorizationError(RuntimeError):
    """Authority, ownership, or runtime joins failed closed."""

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        if type(message) is not str:
            raise TypeError("message must be a built-in string")
        super().__init__(message)
        self.exit_code = _validate_exit_code(exit_code, default=77)


class OneCellSchedulerError(RuntimeError):
    """A durable scheduler operation rejected or became ambiguous."""

    def __init__(self, message: str, *, exit_code: int | None = None) -> None:
        if type(message) is not str:
            raise TypeError("message must be a built-in string")
        super().__init__(message)
        self.exit_code = _validate_exit_code(exit_code, default=69)


class _SealedRecordMeta(type):
    def __setattr__(cls, name: str, value: object) -> None:
        if cls.__dict__.get("_runtime_sealed", False):
            raise TypeError("runner record classes are runtime sealed")
        type.__setattr__(cls, name, value)

    def __delattr__(cls, name: str) -> None:
        if cls.__dict__.get("_runtime_sealed", False):
            raise TypeError("runner record classes are runtime sealed")
        type.__delattr__(cls, name)


class _SealedRecord(metaclass=_SealedRecordMeta):
    __slots__ = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellLaunchTask(_SealedRecord):
    array_position: int
    wave: str
    role: str
    task_map_id: str
    task_index: int
    scientific_identity_bytes: bytes
    scientific_identity_sha256: str
    relative_task_directory: str

    def __post_init__(self) -> None:
        _validate_launch_task(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellSlurmResourceEnvelope(_SealedRecord):
    profile: str
    partition: str
    wall_minutes: int
    cpus_per_task: int
    memory_mib: int
    array_concurrency: int
    signal_name: str
    signal_warning_seconds: int
    receipt_handshake_seconds: int
    scheduler_timeout_seconds: int
    max_requeues_per_task: int
    sbatch_executable: str
    sbatch_executable_realpath: str
    sbatch_owner_uid: int
    sbatch_mode: int
    sbatch_size_bytes: int
    sbatch_sha256: str
    sbatch_version: str
    scontrol_executable: str
    scontrol_executable_realpath: str
    scontrol_owner_uid: int
    scontrol_mode: int
    scontrol_size_bytes: int
    scontrol_sha256: str
    scontrol_version: str
    scheduler_environment: tuple[tuple[str, str], ...]
    scientific_environment: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        _validate_resources(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellRunnerPaths(_SealedRecord):
    campaign_root: str
    authorization_checkout: str
    authorization_directory: str
    runtime_python_file: str
    runtime_python_bytes: bytes
    runtime_python_sha256: str
    python_executable: str
    python_executable_realpath: str
    python_executable_sha256: str
    python_executable_size_bytes: int
    task_root: str
    attempt_root: str
    log_root: str
    cache_root: str
    temporary_root: str
    submission_ledger_root: str
    submission_ledger_lock: str
    authorized_run_directory: str
    batch_script: str
    stdout_template: str
    stderr_template: str
    git_executable: str
    git_executable_realpath: str
    git_owner_uid: int
    git_mode: int
    git_size_bytes: int
    git_sha256: str
    git_version: str
    coordinator_remote_url: str
    coordinator_fetch_refspec: str

    def __post_init__(self) -> None:
        _validate_paths(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellLaunchAuthority(_SealedRecord):
    authorization_path: str
    launch_bytes: bytes
    launch_sha256: str
    launch_commit: str
    launch_path: str
    launch_size_bytes: int
    profile: str
    launch_id: str
    lane: str
    campaign: OneCellCampaignAuthority
    deployment_lock_bytes: bytes
    deployment_lock_sha256: str
    deployment_certificate_bytes: bytes
    deployment_certificate_sha256: str
    admission_bytes: bytes
    admission_sha256: str
    protocol_commit: str
    protocol_blob: str
    protocol_sha256: str
    software_commit: str
    wheel_sha256: str
    campaign_commit: str
    campaign_manifest_sha256: str
    deployment_commit: str
    admission_commit: str
    branch_decision_bytes: bytes | None
    branch_decision_sha256: str | None
    branch_commit: str | None
    branch_path: str | None
    branch_size_bytes: int | None
    mapping_profile: str
    ordered_tasks_profile: str
    ordered_tasks_sha256: str
    ordered_tasks: tuple[OneCellLaunchTask, ...]
    readback_bytes: bytes
    readback_sha256: str
    git_environment: tuple[tuple[str, str], ...]
    resources: OneCellSlurmResourceEnvelope
    paths: OneCellRunnerPaths

    def __post_init__(self) -> None:
        _validate_launch_authority(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellAuthorizedTask(_SealedRecord):
    launch: OneCellLaunchAuthority
    array_position: int
    task: OneCellLaunchTask
    scientific_identity_bytes: bytes
    scientific_identity_sha256: str
    slurm_array_job_id: str
    slurm_array_task_id: str
    slurm_job_id: str
    restart_count: int
    attempt_id: str
    task_directory: str
    attempt_directory: str
    submission_claim_sha256: str
    submission_receipt_sha256: str
    requeue_target: str

    def __post_init__(self) -> None:
        _validate_authorized_task(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellRunnerOutcome(_SealedRecord):
    disposition: Literal["complete", "reused", "requeue-submitted"]
    array_position: int
    task_map_id: str
    task_index: int
    attempt_id: str
    task_directory: str
    manifest_path: str | None
    generation: int
    checkpoint_count: int
    snapshot_count: int
    used_fallback: bool

    def __post_init__(self) -> None:
        _validate_runner_outcome(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellSubmissionOutcome(_SealedRecord):
    disposition: Literal["accepted"]
    launch_sha256: str
    claim_path: str
    claim_sha256: str
    receipt_path: str
    receipt_sha256: str
    sbatch_argv_sha256: str
    array_job_id: str

    def __post_init__(self) -> None:
        _validate_submission_outcome(self)


_RECORD_TYPES = (
    OneCellLaunchTask,
    OneCellSlurmResourceEnvelope,
    OneCellRunnerPaths,
    OneCellLaunchAuthority,
    OneCellAuthorizedTask,
    OneCellRunnerOutcome,
    OneCellSubmissionOutcome,
)


def _require_exact_int(value: object, *, label: str, minimum: int = 0, maximum: int = _U64_MAX) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} is outside its frozen range")
    return value


def _require_exact_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a built-in Boolean")
    return value


def _require_exact_str(value: object, *, label: str, maximum: int = 4096) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    try:
        encoded = value.encode("utf-8", "strict")
    except UnicodeError as error:
        raise ValueError(f"{label} is not strict UTF-8") from error
    if (
        not encoded
        or len(encoded) > maximum
        or "\x00" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ValueError(f"{label} has invalid length or control characters")
    return value


def _require_utc_timestamp(value: object, *, label: str) -> str:
    selected = _require_exact_str(value, label=label, maximum=20)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", selected) is None:
        raise OneCellRunnerValidationError(f"{label} is not canonical UTC RFC 3339 seconds")
    try:
        time.strptime(selected, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise OneCellRunnerValidationError(f"{label} is not a valid UTC timestamp") from error
    return selected


def _require_ascii_token(value: object, *, label: str) -> str:
    selected = _require_exact_str(value, label=label, maximum=128)
    if _ASCII_TOKEN.fullmatch(selected) is None:
        raise OneCellRunnerValidationError(f"{label} is not a frozen ASCII token")
    return selected


def _require_exact_bytes(value: object, *, label: str, maximum: int) -> bytes:
    if type(value) is not bytes:
        raise TypeError(f"{label} must be built-in bytes")
    if not value or len(value) > maximum:
        raise ValueError(f"{label} has invalid length")
    return value


def _require_hex(value: object, *, label: str, width: int = 64) -> str:
    result = _require_exact_str(value, label=label, maximum=width)
    pattern = _HEX40 if width == 40 else _HEX64
    if pattern.fullmatch(result) is None:
        raise ValueError(f"{label} must be {width} lowercase hexadecimal characters")
    return result


def _require_abs_path(value: object, *, label: str) -> str:
    result = _require_exact_str(value, label=label)
    if not os.path.isabs(result) or os.path.normpath(result) != result or result == "/":
        raise ValueError(f"{label} must be a normalized non-root absolute path")
    if len(os.fsencode(result)) > 4096:
        raise ValueError(f"{label} exceeds the path bound")
    return result


def _require_safe_path(value: object, *, label: str) -> str:
    result = _require_exact_str(value, label=label)
    if _SAFE_PATH.fullmatch(result) is None or any(len(part.encode()) > 255 for part in result.split("/")):
        raise ValueError(f"{label} is not a frozen safe relative path")
    return result


def _require_positive_decimal(value: object, *, label: str) -> str:
    result = _require_exact_str(value, label=label, maximum=10)
    if _POSITIVE_DECIMAL.fullmatch(result) is None or int(result) > _U32_MAX:
        raise ValueError(f"{label} must be a canonical positive scheduler ID")
    return result


def _require_tuple_pairs(value: object, *, label: str) -> tuple[tuple[str, str], ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    result: list[tuple[str, str]] = []
    for index, pair in enumerate(value):
        if type(pair) is not tuple or len(pair) != 2 or any(type(item) is not str for item in pair):
            raise TypeError(f"{label}[{index}] must be an exact string pair")
        _require_exact_str(pair[0], label=f"{label}[{index}].key", maximum=128)
        _require_exact_str(pair[1], label=f"{label}[{index}].value")
        result.append(pair)
    if len({key for key, _ in result}) != len(result):
        raise ValueError(f"{label} has duplicate keys")
    return tuple(result)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class _DuplicateKeyError(ValueError):
    pass


def _object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str:
            raise _DuplicateKeyError("JSON object key is not a built-in string")
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _canonical_json(value: object, *, newline: bool = True) -> bytes:
    try:
        payload = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8", "strict")
    except (TypeError, ValueError, UnicodeError) as error:
        raise OneCellRunnerValidationError("value is not canonical JSON data") from error
    return payload + (b"\n" if newline else b"")


def _validate_json_tree(value: object, *, label: str, integer_maximum: int = _U64_MAX) -> None:
    if type(integer_maximum) is not int or not _U64_MAX <= integer_maximum <= 1 << 128:
        raise TypeError("JSON integer maximum is outside the private parser contract")
    pending: list[tuple[object, int]] = [(value, 1)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        if nodes > 100_000 or depth > 32:
            raise OneCellRunnerValidationError(f"{label} exceeds the JSON tree bound")
        if current is None or type(current) in {bool, int, str}:
            if type(current) is int and not -(1 << 63) <= current <= integer_maximum:
                raise OneCellRunnerValidationError(f"{label} integer exceeds the wire bound")
            if type(current) is str:
                try:
                    encoded = current.encode("utf-8", "strict")
                except UnicodeError as error:
                    raise OneCellRunnerValidationError(f"{label} contains invalid UTF-8 text") from error
                if (
                    len(encoded) > _MAX_JSON
                    or "\x00" in current
                    or any(ord(char) < 32 or ord(char) == 127 for char in current)
                ):
                    raise OneCellRunnerValidationError(f"{label} contains invalid string data")
            continue
        if type(current) is list:
            pending.extend((item, depth + 1) for item in current)
            continue
        if type(current) is dict:
            pending.extend((item, depth + 1) for item in current.values())
            continue
        raise OneCellRunnerValidationError(f"{label} contains a forbidden JSON type")


def _parse_canonical_json(
    payload: object,
    *,
    label: str,
    maximum: int = _MAX_JSON,
    newline: bool = True,
    integer_maximum: int = _U64_MAX,
) -> object:
    if type(payload) is not bytes:
        raise TypeError(f"{label} must be built-in bytes")
    if not payload or len(payload) > maximum:
        raise OneCellRunnerValidationError(f"{label} is empty or oversized")
    if newline:
        if not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
            raise OneCellRunnerValidationError(f"{label} must end in exactly one LF")
        encoded = payload[:-1]
    else:
        if payload.endswith(b"\n"):
            raise OneCellRunnerValidationError(f"{label} must not end in LF")
        encoded = payload
    try:
        text = encoded.decode("utf-8", "strict")
        value = json.loads(
            text,
            object_pairs_hook=_object_from_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise OneCellRunnerValidationError(f"{label} is not strict duplicate-free JSON") from error
    _validate_json_tree(value, label=label, integer_maximum=integer_maximum)
    if _canonical_json(value, newline=newline) != payload:
        raise OneCellRunnerValidationError(f"{label} is not byte-canonical JSON")
    return value


def _parse_canonical_jsonl(
    payload: object,
    *,
    label: str,
    profile: str,
    maximum: int = _MAX_JSONL,
    line_maximum: int = _MAX_JSONL_LINE,
    row_maximum: int = _MAX_TASKS,
) -> tuple[dict[str, object], ...]:
    if type(payload) is not bytes:
        raise TypeError(f"{label} must be built-in bytes")
    if not payload or len(payload) > maximum or not payload.endswith(b"\n"):
        raise OneCellRunnerValidationError(f"{label} is empty, oversized, or lacks final LF")
    raw_lines = payload.splitlines(keepends=True)
    if not 1 <= len(raw_lines) <= row_maximum:
        raise OneCellRunnerValidationError(f"{label} row count is outside its bound")
    records: list[dict[str, object]] = []
    for index, line in enumerate(raw_lines):
        if len(line) > line_maximum:
            raise OneCellRunnerValidationError(f"{label} line {index} is oversized")
        value = _parse_canonical_json(line, label=f"{label}[{index}]", maximum=line_maximum)
        if type(value) is not dict or value.get("profile") != profile:
            raise OneCellRunnerValidationError(f"{label} line {index} has the wrong profile")
        records.append(value)
    return tuple(records)


def _exact_dict(value: object, *, keys: tuple[str, ...], label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise OneCellRunnerValidationError(f"{label} must be a JSON object")
    if set(value) != set(keys) or len(value) != len(keys):
        raise OneCellRunnerValidationError(f"{label} has an unknown or missing key")
    return value


def _exact_list(value: object, *, label: str, maximum: int = _MAX_TASKS) -> list[object]:
    if type(value) is not list or len(value) > maximum:
        raise OneCellRunnerValidationError(f"{label} must be a bounded JSON array")
    return value


def _parse_file_ref(value: object, *, label: str) -> dict[str, object]:
    record = _exact_dict(value, keys=("commit", "path", "sha256", "size_bytes"), label=label)
    _require_hex(record["commit"], label=f"{label}.commit", width=40)
    _require_safe_path(record["path"], label=f"{label}.path")
    _require_hex(record["sha256"], label=f"{label}.sha256")
    _require_exact_int(record["size_bytes"], label=f"{label}.size_bytes", maximum=_MAX_JSONL)
    return record


@dataclass(frozen=True, slots=True)
class _ProcessResult:
    returncode: int | None
    stdout: bytes
    stdout_overflow: bool
    stderr: bytes
    stderr_overflow: bool
    timed_out: bool
    spawn_ambiguous: bool


def _run_bounded_process(
    argv: tuple[str, ...],
    *,
    environment: tuple[tuple[str, str], ...],
    timeout_seconds: int,
    capture_limit: int = _MAX_CAPTURE,
) -> _ProcessResult:
    if type(argv) is not tuple or not argv or any(type(item) is not str or not item for item in argv):
        raise TypeError("argv must be a nonempty exact string tuple")
    if any("\x00" in item or len(os.fsencode(item)) > 4096 for item in argv):
        raise OneCellRunnerAuthorizationError("process argv member exceeds the hard path bound", exit_code=76)
    selected_environment = dict(_require_tuple_pairs(environment, label="process environment"))
    _require_exact_int(timeout_seconds, label="timeout_seconds", minimum=1, maximum=300)
    _require_exact_int(capture_limit, label="capture_limit", minimum=1, maximum=_MAX_JSONL)
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=selected_environment,
            shell=False,
            close_fds=True,
        )
    except OSError:
        return _ProcessResult(None, b"", False, b"", False, False, True)
    assert process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    streams = {process.stdout: [bytearray(), False], process.stderr: [bytearray(), False]}
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    deadline = time.monotonic_ns() + timeout_seconds * 1_000_000_000
    timed_out = False
    overflowed = False
    try:
        while selector.get_map():
            remaining_ns = deadline - time.monotonic_ns()
            if remaining_ns <= 0:
                timed_out = True
                process.kill()
                break
            events = selector.select(min(0.25, remaining_ns / 1_000_000_000))
            for key, _ in events:
                stream = key.fileobj
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(stream)
                    continue
                buffer, overflow = streams[stream]
                room = max(0, capture_limit - len(buffer))
                buffer.extend(chunk[:room])
                if len(chunk) > room:
                    streams[stream][1] = True
                    overflowed = True
                    process.kill()
            if overflowed:
                break
        if timed_out or overflowed:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        else:
            try:
                process.wait(timeout=max(0.0, (deadline - time.monotonic_ns()) / 1_000_000_000))
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                process.wait()
        # Drain only enough to establish and retain the exact bounded prefixes.
        for stream, state in streams.items():
            while True:
                try:
                    chunk = os.read(stream.fileno(), 65536)
                except BlockingIOError:
                    break
                if not chunk:
                    break
                buffer, _ = state
                room = max(0, capture_limit - len(buffer))
                buffer.extend(chunk[:room])
                if len(chunk) > room:
                    state[1] = True
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()
    stdout_state = streams[process.stdout]
    stderr_state = streams[process.stderr]
    return _ProcessResult(
        process.returncode,
        bytes(stdout_state[0]),
        bool(stdout_state[1]),
        bytes(stderr_state[0]),
        bool(stderr_state[1]),
        timed_out,
        False,
    )


def _classify_scheduler_result(
    *,
    result: _ProcessResult,
    submission: bool,
) -> tuple[str, str | None]:
    if type(result) is not _ProcessResult or type(submission) is not bool:
        raise TypeError("scheduler classification requires exact private records")
    if (
        result.spawn_ambiguous
        or result.timed_out
        or result.stdout_overflow
        or result.stderr_overflow
        or result.returncode is None
        or result.returncode < 0
    ):
        return "unknown", None
    if result.returncode > 0:
        return "rejected", None
    if submission:
        try:
            stdout = result.stdout.decode("ascii", "strict")
        except UnicodeError:
            return "unknown", None
        candidate = stdout[:-1] if stdout.endswith("\n") else ""
        if result.stderr or stdout != candidate + "\n":
            return "unknown", None
        try:
            return "accepted", _require_positive_decimal(candidate, label="array_job_id")
        except (TypeError, ValueError):
            return "unknown", None
    if result.stdout or result.stderr:
        return "unknown", None
    return "accepted", None


def _parse_canonical_json_for_test(*, payload: bytes, profile: str) -> dict[str, object]:
    """Private parser oracle used by nonexecuting fixture tests."""

    selected_profile = _require_exact_str(profile, label="profile", maximum=128)
    value = _parse_canonical_json(payload, label="fixture")
    if type(value) is not dict or value.get("profile") != selected_profile:
        raise OneCellRunnerValidationError("fixture profile does not match")
    return value


def _parse_canonical_jsonl_for_test(
    *, payload: bytes, profile: str, row_maximum: int = _MAX_TASKS
) -> tuple[dict[str, object], ...]:
    """Private JSONL parser oracle used by nonexecuting fixture tests."""

    return _parse_canonical_jsonl(
        payload,
        label="fixture-jsonl",
        profile=_require_exact_str(profile, label="profile", maximum=128),
        row_maximum=_require_exact_int(row_maximum, label="row_maximum", minimum=1, maximum=_MAX_TASKS),
    )


def _classify_scheduler_result_for_test(
    *,
    returncode: int | None,
    stdout: bytes,
    stderr: bytes,
    submission: bool,
    timed_out: bool = False,
    spawn_ambiguous: bool = False,
    stdout_overflow: bool = False,
    stderr_overflow: bool = False,
) -> tuple[str, str | None]:
    """Classify inert synthetic scheduler output without spawning a process."""

    if returncode is not None and (type(returncode) is not int or not -(1 << 31) <= returncode < (1 << 31)):
        raise TypeError("returncode must be a signed 32-bit built-in integer or None")
    if type(stdout) is not bytes or type(stderr) is not bytes:
        raise TypeError("captured streams must be built-in bytes")
    for label, value in (
        ("submission", submission),
        ("timed_out", timed_out),
        ("spawn_ambiguous", spawn_ambiguous),
        ("stdout_overflow", stdout_overflow),
        ("stderr_overflow", stderr_overflow),
    ):
        _require_exact_bool(value, label=label)
    result = _ProcessResult(
        returncode,
        stdout[:_MAX_CAPTURE],
        stdout_overflow,
        stderr[:_MAX_CAPTURE],
        stderr_overflow,
        timed_out,
        spawn_ambiguous,
    )
    return _classify_scheduler_result(result=result, submission=submission)


def _fixture_launch_authority_for_test(*, directory: str) -> OneCellLaunchAuthority:
    """Build an inert, permanently ineligible authority without touching disk."""

    base = _require_abs_path(directory, label="fixture directory")
    digest_a = "a" * 64
    digest_b = "b" * 64
    commit_a = "a" * 40
    identity = b'{"fixture":true}'
    identity_digest = _sha256(identity)
    task = OneCellLaunchTask(
        array_position=0,
        wave="f0",
        role="fixture-nonexecuting",
        task_map_id="f0",
        task_index=0,
        scientific_identity_bytes=identity,
        scientific_identity_sha256=identity_digest,
        relative_task_directory=f"f0/{0:020d}-{identity_digest}",
    )
    campaign_root = os.path.join(base, "campaign")
    authorization_directory = os.path.join(base, "authorization")
    cache_root = os.path.join(campaign_root, "private", "cache")
    temporary_root = os.path.join(campaign_root, "private", "tmp")
    scientific_environment = (
        ("LANG", "C"),
        ("LC_ALL", "C"),
        ("TMPDIR", temporary_root),
        ("NUMBA_CACHE_DIR", os.path.join(cache_root, "numba")),
        ("NUMBA_NUM_THREADS", "1"),
        ("OMP_NUM_THREADS", "1"),
        ("OPENBLAS_NUM_THREADS", "1"),
        ("MKL_NUM_THREADS", "1"),
        ("NUMEXPR_NUM_THREADS", "1"),
        ("BLIS_NUM_THREADS", "1"),
        ("VECLIB_MAXIMUM_THREADS", "1"),
        ("OMP_DYNAMIC", "FALSE"),
        ("MKL_DYNAMIC", "FALSE"),
    )
    sbatch = os.path.join(base, "bin", "sbatch")
    scontrol = os.path.join(base, "bin", "scontrol")
    git = os.path.join(base, "bin", "git")
    python = os.path.join(base, "environment", "bin", "python")
    resources = OneCellSlurmResourceEnvelope(
        profile=_RESOURCE_PROFILE,
        partition="fixture",
        wall_minutes=17,
        cpus_per_task=1,
        memory_mib=1,
        array_concurrency=1,
        signal_name="SIGUSR1",
        signal_warning_seconds=900,
        receipt_handshake_seconds=60,
        scheduler_timeout_seconds=30,
        max_requeues_per_task=0,
        sbatch_executable=sbatch,
        sbatch_executable_realpath=sbatch,
        sbatch_owner_uid=os.geteuid(),
        sbatch_mode=0o755,
        sbatch_size_bytes=1,
        sbatch_sha256=digest_a,
        sbatch_version=f"content-sha256:{digest_a}",
        scontrol_executable=scontrol,
        scontrol_executable_realpath=scontrol,
        scontrol_owner_uid=os.geteuid(),
        scontrol_mode=0o755,
        scontrol_size_bytes=1,
        scontrol_sha256=digest_b,
        scontrol_version=f"content-sha256:{digest_b}",
        scheduler_environment=_SCHEDULER_ENVIRONMENT,
        scientific_environment=scientific_environment,
    )
    runtime_bytes = os.fsencode(python) + b"\n"
    paths = OneCellRunnerPaths(
        campaign_root=campaign_root,
        authorization_checkout=os.path.join(base, "checkout"),
        authorization_directory=authorization_directory,
        runtime_python_file=os.path.join(authorization_directory, "runtime-python.path"),
        runtime_python_bytes=runtime_bytes,
        runtime_python_sha256=_sha256(runtime_bytes),
        python_executable=python,
        python_executable_realpath=python,
        python_executable_sha256=digest_a,
        python_executable_size_bytes=1,
        task_root=os.path.join(campaign_root, "private", "tasks"),
        attempt_root=os.path.join(campaign_root, "private", "attempts"),
        log_root=os.path.join(campaign_root, "private", "logs"),
        cache_root=cache_root,
        temporary_root=temporary_root,
        submission_ledger_root=os.path.join(campaign_root, "private", "submission-ledger"),
        submission_ledger_lock=os.path.join(campaign_root, "private", "submission-ledger", "ledger.lock"),
        authorized_run_directory=os.path.join(campaign_root, "private", "run"),
        batch_script=os.path.join(base, "run_pre_one_cell.sbatch"),
        stdout_template=os.path.join(campaign_root, "private", "logs", "slurm-%A_%a.out"),
        stderr_template=os.path.join(campaign_root, "private", "logs", "slurm-%A_%a.err"),
        git_executable=git,
        git_executable_realpath=git,
        git_owner_uid=os.geteuid(),
        git_mode=0o755,
        git_size_bytes=1,
        git_sha256=digest_a,
        git_version="git version fixture",
        coordinator_remote_url="fixture.invalid:coordinator.git",
        coordinator_fetch_refspec=_MAIN_FETCH_REFSPEC,
    )
    campaign = object.__new__(OneCellCampaignAuthority)
    launch_bytes = _canonical_json(
        {
            "fixture": {
                "fixture_id": "slice-8b-authority-parser-nonexecuting",
                "scientific_execution_permitted": False,
            },
            "profile": _LAUNCH_FIXTURE_PROFILE,
        }
    )
    deployment_lock = b'{"fixture":false}\n'
    deployment = b'{"fixture":false}\n'
    admission = b'{"fixture":false}\n'
    readback = b'{"fixture":false}\n'
    row = _canonical_json(
        {
            "array_position": 0,
            "profile": _LAUNCH_TASK_PROFILE,
            "relative_task_directory": task.relative_task_directory,
            "role": task.role,
            "scientific_identity_hex": identity.hex(),
            "scientific_identity_sha256": identity_digest,
            "scientific_identity_size_bytes": len(identity),
            "scientific_index": 0,
            "task_map_id": "f0",
            "wave": "f0",
        }
    )
    return OneCellLaunchAuthority(
        authorization_path=authorization_directory,
        launch_bytes=launch_bytes,
        launch_sha256=_sha256(launch_bytes),
        launch_commit=commit_a,
        launch_path="authorizations/pre-one-cell-discovery-v1/launches/f0-0000/launch.json",
        launch_size_bytes=len(launch_bytes),
        profile=_LAUNCH_FIXTURE_PROFILE,
        launch_id="fixture-launch",
        lane="f0",
        campaign=campaign,
        deployment_lock_bytes=deployment_lock,
        deployment_lock_sha256=_sha256(deployment_lock),
        deployment_certificate_bytes=deployment,
        deployment_certificate_sha256=_sha256(deployment),
        admission_bytes=admission,
        admission_sha256=_sha256(admission),
        protocol_commit=commit_a,
        protocol_blob=commit_a,
        protocol_sha256=digest_a,
        software_commit=commit_a,
        wheel_sha256=digest_a,
        campaign_commit=commit_a,
        campaign_manifest_sha256=digest_a,
        deployment_commit=commit_a,
        admission_commit=commit_a,
        branch_decision_bytes=None,
        branch_decision_sha256=None,
        branch_commit=None,
        branch_path=None,
        branch_size_bytes=None,
        mapping_profile=_ARRAY_PROFILE,
        ordered_tasks_profile=_ORDERED_TASKS_PROFILE,
        ordered_tasks_sha256=_sha256(row),
        ordered_tasks=(task,),
        readback_bytes=readback,
        readback_sha256=_sha256(readback),
        git_environment=_GIT_ENVIRONMENT,
        resources=resources,
        paths=paths,
    )


def _production_shaped_launch_for_test(*, directory: str) -> OneCellLaunchAuthority:
    """Return inert production-shaped records solely for private state-machine tests."""

    fixture = _fixture_launch_authority_for_test(directory=directory)
    values = {field.name: getattr(fixture, field.name) for field in fields(OneCellLaunchAuthority)}
    values["profile"] = _LAUNCH_PROFILE
    return OneCellLaunchAuthority(**values)


def _run_submission_state_machine_for_test(
    *,
    returncode: int | None,
    stdout: bytes,
    stderr: bytes,
    receipt_durable: bool,
    timed_out: bool = False,
    spawn_ambiguous: bool = False,
    stdout_overflow: bool = False,
    stderr_overflow: bool = False,
) -> tuple[str, str | None, bool]:
    """Exercise post-claim scheduler/receipt decisions without any subprocess or I/O."""

    _require_exact_bool(receipt_durable, label="receipt_durable")
    outcome, array_job_id = _classify_scheduler_result_for_test(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        submission=True,
        timed_out=timed_out,
        spawn_ambiguous=spawn_ambiguous,
        stdout_overflow=stdout_overflow,
        stderr_overflow=stderr_overflow,
    )
    claim_consumed = True
    if not receipt_durable:
        if outcome == "accepted":
            error = OneCellSchedulerError(
                "scheduler accepted but its receipt was not durable",
                exit_code=75,
            )
            error.claim_consumed = True
            error.additional_initial_call_permitted = False
            raise error
        raise OneCellRunnerAuthorizationError("nonaccepted receipt was not durable", exit_code=74)
    return outcome, array_job_id, claim_consumed


def _run_requeue_state_machine_for_test(
    *,
    scontrol_executable: str,
    array_job_id: str,
    array_position: int,
    current_restart_count: int,
    retry_cap: int,
    permit_already_exists: bool,
    result_already_exists: bool,
    returncode: int | None,
    stdout: bytes,
    stderr: bytes,
    result_durable: bool,
    timed_out: bool = False,
    spawn_ambiguous: bool = False,
    stdout_overflow: bool = False,
    stderr_overflow: bool = False,
) -> tuple[tuple[str, ...], int, bool]:
    """Exercise the permit-bound requeue decision without I/O or subprocesses."""

    executable = _require_abs_path(scontrol_executable, label="scontrol_executable")
    job_id = _require_positive_decimal(array_job_id, label="array_job_id")
    position = _require_exact_int(array_position, label="array_position", maximum=_MAX_TASKS - 1)
    current = _require_exact_int(current_restart_count, label="current_restart_count", maximum=16)
    cap = _require_exact_int(retry_cap, label="retry_cap", maximum=16)
    for label, value in (
        ("permit_already_exists", permit_already_exists),
        ("result_already_exists", result_already_exists),
        ("result_durable", result_durable),
    ):
        _require_exact_bool(value, label=label)
    if current >= cap:
        raise OneCellRunnerAuthorizationError("requeue retry cap is exhausted", exit_code=77)
    if permit_already_exists or result_already_exists:
        raise OneCellRunnerAuthorizationError("requeue attempt is already consumed", exit_code=77)
    target = current + 1
    argv = (executable, "requeue", f"{job_id}_{position}")
    outcome, _ = _classify_scheduler_result_for_test(
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        submission=False,
        timed_out=timed_out,
        spawn_ambiguous=spawn_ambiguous,
        stdout_overflow=stdout_overflow,
        stderr_overflow=stderr_overflow,
    )
    permit_consumed = True
    if not result_durable:
        error = OneCellRunnerAuthorizationError("requeue result was not durable", exit_code=74)
        error.permit_consumed = True
        error.additional_scontrol_permitted = False
        raise error
    if outcome != "accepted":
        error = OneCellSchedulerError(
            f"scheduler requeue {outcome}",
            exit_code=69 if outcome == "rejected" else 75,
        )
        error.permit_consumed = True
        error.additional_scontrol_permitted = False
        raise error
    return argv, target, permit_consumed


def _validate_launch_task(value: object) -> None:
    if type(value) is not OneCellLaunchTask:
        raise TypeError("task must be an exact OneCellLaunchTask")
    position = _require_exact_int(value.array_position, label="array_position", maximum=_MAX_TASKS - 1)
    _require_ascii_token(value.wave, label="wave")
    _require_ascii_token(value.role, label="role")
    _require_ascii_token(value.task_map_id, label="task_map_id")
    index = _require_exact_int(value.task_index, label="task_index", maximum=_MAX_TASKS - 1)
    identity = _require_exact_bytes(
        value.scientific_identity_bytes, label="scientific_identity_bytes", maximum=_MAX_IDENTITY
    )
    digest = _require_hex(value.scientific_identity_sha256, label="scientific_identity_sha256")
    if digest != _sha256(identity):
        raise ValueError("scientific identity digest does not match held bytes")
    relative = _require_safe_path(value.relative_task_directory, label="relative_task_directory")
    expected = f"{value.wave}/{index:020d}-{digest}"
    if relative != expected or position < 0:
        raise ValueError("relative task directory is not the frozen task path")


def _validate_tool_fields(
    *,
    label: str,
    path: object,
    realpath: object,
    owner_uid: object,
    mode: object,
    size_bytes: object,
    sha256: object,
    version: object,
) -> None:
    selected_path = _require_abs_path(path, label=f"{label}_executable")
    selected_realpath = _require_abs_path(realpath, label=f"{label}_executable_realpath")
    if selected_path != selected_realpath:
        raise ValueError(f"{label} executable and realpath differ")
    _require_exact_int(owner_uid, label=f"{label}_owner_uid", maximum=_U32_MAX)
    selected_mode = _require_exact_int(mode, label=f"{label}_mode", maximum=0o7777)
    if selected_mode & 0o022 or not selected_mode & 0o111:
        raise ValueError(f"{label} mode is writable by group/world or not executable")
    _require_exact_int(size_bytes, label=f"{label}_size_bytes", minimum=1, maximum=_MAX_TOOL_BYTES)
    digest = _require_hex(sha256, label=f"{label}_sha256")
    selected_version = _require_exact_str(version, label=f"{label}_version", maximum=256)
    if not selected_version.isascii():
        raise ValueError(f"{label} version is not printable ASCII")
    if label in {"sbatch", "scontrol"} and selected_version != f"content-sha256:{digest}":
        raise ValueError(f"{label} version is not its content digest label")


def _validate_resources(value: object) -> None:
    if type(value) is not OneCellSlurmResourceEnvelope:
        raise TypeError("resources must be exact OneCellSlurmResourceEnvelope")
    if value.profile != _RESOURCE_PROFILE:
        raise ValueError("resource profile is not frozen")
    partition = _require_exact_str(value.partition, label="partition", maximum=128)
    if _SAFE_COMPONENT.fullmatch(partition) is None or any(char in partition for char in ",/:"):
        raise ValueError("partition is not one literal component")
    _require_exact_int(value.wall_minutes, label="wall_minutes", minimum=17, maximum=28_800)
    cpus = _require_exact_int(value.cpus_per_task, label="cpus_per_task", minimum=1, maximum=128)
    _require_exact_int(value.memory_mib, label="memory_mib", minimum=1, maximum=786_432)
    _require_exact_int(value.array_concurrency, label="array_concurrency", minimum=1, maximum=_MAX_TASKS)
    if value.signal_name != "SIGUSR1" or value.signal_warning_seconds != 900:
        raise ValueError("signal resources are not frozen")
    if value.receipt_handshake_seconds != 60 or value.scheduler_timeout_seconds != 30:
        raise ValueError("scheduler timing resources are not frozen")
    _require_exact_int(value.max_requeues_per_task, label="max_requeues_per_task", maximum=16)
    _validate_tool_fields(
        label="sbatch",
        path=value.sbatch_executable,
        realpath=value.sbatch_executable_realpath,
        owner_uid=value.sbatch_owner_uid,
        mode=value.sbatch_mode,
        size_bytes=value.sbatch_size_bytes,
        sha256=value.sbatch_sha256,
        version=value.sbatch_version,
    )
    _validate_tool_fields(
        label="scontrol",
        path=value.scontrol_executable,
        realpath=value.scontrol_executable_realpath,
        owner_uid=value.scontrol_owner_uid,
        mode=value.scontrol_mode,
        size_bytes=value.scontrol_size_bytes,
        sha256=value.scontrol_sha256,
        version=value.scontrol_version,
    )
    scheduler = _require_tuple_pairs(value.scheduler_environment, label="scheduler_environment")
    scientific = _require_tuple_pairs(value.scientific_environment, label="scientific_environment")
    if scheduler != _SCHEDULER_ENVIRONMENT:
        raise ValueError("scheduler environment is not frozen")
    if tuple(key for key, _ in scientific) != _SCIENTIFIC_ENV_KEYS:
        raise ValueError("scientific environment key order is not frozen")
    scientific_map = dict(scientific)
    if scientific_map["LANG"] != "C" or scientific_map["LC_ALL"] != "C":
        raise ValueError("scientific locale is not frozen")
    if scientific_map["OMP_DYNAMIC"] != "FALSE" or scientific_map["MKL_DYNAMIC"] != "FALSE":
        raise ValueError("scientific dynamic threading is not disabled")
    if any(scientific_map[key] != str(cpus) for key in _SCIENTIFIC_ENV_KEYS[4:11]):
        raise ValueError("scientific thread counts do not match cpus_per_task")


def _validate_paths(value: object) -> None:
    if type(value) is not OneCellRunnerPaths:
        raise TypeError("paths must be exact OneCellRunnerPaths")
    absolute_fields = (
        "campaign_root",
        "authorization_checkout",
        "authorization_directory",
        "runtime_python_file",
        "python_executable",
        "python_executable_realpath",
        "task_root",
        "attempt_root",
        "log_root",
        "cache_root",
        "temporary_root",
        "submission_ledger_root",
        "submission_ledger_lock",
        "authorized_run_directory",
        "batch_script",
        "stdout_template",
        "stderr_template",
        "git_executable",
        "git_executable_realpath",
    )
    for name in absolute_fields:
        _require_abs_path(getattr(value, name), label=name)
    runtime_bytes = _require_exact_bytes(value.runtime_python_bytes, label="runtime_python_bytes", maximum=4096)
    _require_hex(value.runtime_python_sha256, label="runtime_python_sha256")
    _require_hex(value.python_executable_sha256, label="python_executable_sha256")
    _require_exact_int(
        value.python_executable_size_bytes, label="python_executable_size_bytes", minimum=1, maximum=_MAX_TOOL_BYTES
    )
    if (
        value.runtime_python_sha256 != _sha256(runtime_bytes)
        or runtime_bytes != os.fsencode(value.python_executable) + b"\n"
    ):
        raise ValueError("runtime Python sidecar does not bind the executable")
    if value.python_executable != value.python_executable_realpath:
        raise ValueError("Python executable and realpath differ")
    if value.runtime_python_file != os.path.join(value.authorization_directory, "runtime-python.path"):
        raise ValueError("runtime Python sidecar location is not frozen")
    private_root = os.path.join(value.campaign_root, "private")
    expected_private_paths = {
        "task_root": os.path.join(private_root, "tasks"),
        "attempt_root": os.path.join(private_root, "attempts"),
        "log_root": os.path.join(private_root, "logs"),
        "cache_root": os.path.join(private_root, "cache"),
        "temporary_root": os.path.join(private_root, "tmp"),
        "submission_ledger_root": os.path.join(private_root, "submission-ledger"),
        "authorized_run_directory": os.path.join(private_root, "run"),
    }
    if any(getattr(value, name) != expected for name, expected in expected_private_paths.items()):
        raise ValueError("runner private paths do not match the frozen campaign layout")
    if value.submission_ledger_lock != os.path.join(value.submission_ledger_root, "ledger.lock"):
        raise ValueError("submission ledger lock location is not frozen")
    if value.stdout_template != os.path.join(value.log_root, "slurm-%A_%a.out"):
        raise ValueError("Slurm stdout template is not frozen")
    if value.stderr_template != os.path.join(value.log_root, "slurm-%A_%a.err"):
        raise ValueError("Slurm stderr template is not frozen")
    _validate_tool_fields(
        label="git",
        path=value.git_executable,
        realpath=value.git_executable_realpath,
        owner_uid=value.git_owner_uid,
        mode=value.git_mode,
        size_bytes=value.git_size_bytes,
        sha256=value.git_sha256,
        version=value.git_version,
    )
    _require_exact_str(value.coordinator_remote_url, label="coordinator_remote_url")
    if value.coordinator_fetch_refspec != _MAIN_FETCH_REFSPEC:
        raise ValueError("coordinator fetch refspec is not frozen to origin/main")


def _validate_scientific_environment_paths(
    resources: OneCellSlurmResourceEnvelope,
    paths: OneCellRunnerPaths,
) -> None:
    scientific = dict(resources.scientific_environment)
    if scientific["TMPDIR"] != paths.temporary_root:
        raise ValueError("scientific TMPDIR does not equal the certified temporary root")
    if scientific["NUMBA_CACHE_DIR"] != os.path.join(paths.cache_root, "numba"):
        raise ValueError("scientific NUMBA_CACHE_DIR does not equal the certified cache child")


def _validate_launch_authority(value: object) -> None:
    if type(value) is not OneCellLaunchAuthority:
        raise TypeError("launch must be exact OneCellLaunchAuthority")
    _require_abs_path(value.authorization_path, label="authorization_path")
    launch_bytes = _require_exact_bytes(value.launch_bytes, label="launch_bytes", maximum=_MAX_JSON)
    if _require_hex(value.launch_sha256, label="launch_sha256") != _sha256(launch_bytes):
        raise ValueError("launch digest does not match held bytes")
    _require_hex(value.launch_commit, label="launch_commit", width=40)
    _require_safe_path(value.launch_path, label="launch_path")
    if value.launch_size_bytes != len(launch_bytes):
        raise ValueError("launch size does not match held bytes")
    if value.profile not in {_LAUNCH_PROFILE, _LAUNCH_FIXTURE_PROFILE} or value.lane not in _LANES:
        raise ValueError("launch profile or lane is not frozen")
    _require_ascii_token(value.launch_id, label="launch_id")
    if type(value.campaign) is not OneCellCampaignAuthority:
        raise TypeError("campaign must be exact OneCellCampaignAuthority")
    for label, payload, digest in (
        ("deployment_lock", value.deployment_lock_bytes, value.deployment_lock_sha256),
        ("deployment_certificate", value.deployment_certificate_bytes, value.deployment_certificate_sha256),
        ("admission", value.admission_bytes, value.admission_sha256),
        ("readback", value.readback_bytes, value.readback_sha256),
    ):
        selected = _require_exact_bytes(payload, label=f"{label}_bytes", maximum=_MAX_JSON)
        if _require_hex(digest, label=f"{label}_sha256") != _sha256(selected):
            raise ValueError(f"{label} digest does not match held bytes")
    for label in (
        "protocol_commit",
        "software_commit",
        "campaign_commit",
        "deployment_commit",
        "admission_commit",
    ):
        _require_hex(getattr(value, label), label=label, width=40)
    _require_hex(value.protocol_blob, label="protocol_blob", width=40)
    for label in ("protocol_sha256", "wheel_sha256", "campaign_manifest_sha256"):
        _require_hex(getattr(value, label), label=label)
    branch_values = (
        value.branch_decision_bytes,
        value.branch_decision_sha256,
        value.branch_commit,
        value.branch_path,
        value.branch_size_bytes,
    )
    if any(item is None for item in branch_values) and not all(item is None for item in branch_values):
        raise ValueError("branch authority fields must be present or absent together")
    if value.branch_decision_bytes is not None:
        branch_bytes = _require_exact_bytes(
            value.branch_decision_bytes, label="branch_decision_bytes", maximum=_MAX_JSON
        )
        if _require_hex(value.branch_decision_sha256, label="branch_decision_sha256") != _sha256(branch_bytes):
            raise ValueError("branch digest does not match held bytes")
        _require_hex(value.branch_commit, label="branch_commit", width=40)
        _require_safe_path(value.branch_path, label="branch_path")
        if value.branch_size_bytes != len(branch_bytes):
            raise ValueError("branch size does not match held bytes")
    if value.mapping_profile != _ARRAY_PROFILE or value.ordered_tasks_profile != _ORDERED_TASKS_PROFILE:
        raise ValueError("mapping or ordered-task profile is not frozen")
    _require_hex(value.ordered_tasks_sha256, label="ordered_tasks_sha256")
    if type(value.ordered_tasks) is not tuple or not 1 <= len(value.ordered_tasks) <= _MAX_TASKS:
        raise TypeError("ordered_tasks must be a nonempty bounded built-in tuple")
    for position, task in enumerate(value.ordered_tasks):
        if type(task) is not OneCellLaunchTask:
            raise TypeError("ordered_tasks must contain exact OneCellLaunchTask records")
        _validate_launch_task(task)
        if task.array_position != position:
            raise ValueError("ordered tasks are not contiguous in array order")
    if _require_tuple_pairs(value.git_environment, label="git_environment") != _GIT_ENVIRONMENT:
        raise ValueError("Git environment is not frozen")
    if type(value.resources) is not OneCellSlurmResourceEnvelope or type(value.paths) is not OneCellRunnerPaths:
        raise TypeError("resources and paths must be exact runner records")
    _validate_resources(value.resources)
    _validate_paths(value.paths)
    _validate_scientific_environment_paths(value.resources, value.paths)
    if value.resources.array_concurrency > len(value.ordered_tasks):
        raise ValueError("array concurrency exceeds task count")
    if value.authorization_path != value.paths.authorization_directory:
        raise ValueError("authorization path and runner path differ")


def _validate_authorized_task(value: object) -> None:
    if type(value) is not OneCellAuthorizedTask:
        raise TypeError("authorization must be exact OneCellAuthorizedTask")
    if type(value.launch) is not OneCellLaunchAuthority:
        raise TypeError("launch must be exact OneCellLaunchAuthority")
    _validate_launch_authority(value.launch)
    position = _require_exact_int(
        value.array_position, label="array_position", maximum=len(value.launch.ordered_tasks) - 1
    )
    if type(value.task) is not OneCellLaunchTask or value.task != value.launch.ordered_tasks[position]:
        raise ValueError("authorized task does not equal its ordered launch row")
    if value.scientific_identity_bytes != value.task.scientific_identity_bytes:
        raise ValueError("authorized scientific identity bytes differ from task")
    if value.scientific_identity_sha256 != value.task.scientific_identity_sha256:
        raise ValueError("authorized scientific identity digest differs from task")
    array_job = _require_positive_decimal(value.slurm_array_job_id, label="slurm_array_job_id")
    if value.slurm_array_task_id != str(position):
        raise ValueError("Slurm array task ID does not match position")
    job_id = _require_positive_decimal(value.slurm_job_id, label="slurm_job_id")
    restart = _require_exact_int(
        value.restart_count, label="restart_count", maximum=value.launch.resources.max_requeues_per_task
    )
    expected_attempt = f"{array_job}_{position:020d}-r{restart:020d}-j{job_id}"
    if value.attempt_id != expected_attempt:
        raise ValueError("attempt ID is not frozen")
    task_directory = _require_abs_path(value.task_directory, label="task_directory")
    expected_task_directory = os.path.join(value.launch.paths.task_root, value.task.relative_task_directory)
    if task_directory != expected_task_directory:
        raise ValueError("task directory does not match launch task root")
    attempt_directory = _require_abs_path(value.attempt_directory, label="attempt_directory")
    expected_attempt_directory = os.path.join(
        value.launch.paths.attempt_root,
        value.task.relative_task_directory,
        expected_attempt,
    )
    if attempt_directory != expected_attempt_directory:
        raise ValueError("attempt directory does not match the exact authorized attempt path")
    _require_hex(value.submission_claim_sha256, label="submission_claim_sha256")
    _require_hex(value.submission_receipt_sha256, label="submission_receipt_sha256")
    if value.requeue_target != f"{array_job}_{position}":
        raise ValueError("requeue target is not the exact array element")


def _validate_runner_outcome(value: object) -> None:
    if type(value) is not OneCellRunnerOutcome:
        raise TypeError("outcome must be exact OneCellRunnerOutcome")
    if value.disposition not in {"complete", "reused", "requeue-submitted"}:
        raise ValueError("runner disposition is not frozen")
    _require_exact_int(value.array_position, label="array_position", maximum=_MAX_TASKS - 1)
    _require_ascii_token(value.task_map_id, label="task_map_id")
    _require_exact_int(value.task_index, label="task_index", maximum=_MAX_TASKS - 1)
    _require_ascii_token(value.attempt_id, label="attempt_id")
    _require_abs_path(value.task_directory, label="task_directory")
    _require_exact_int(value.generation, label="generation")
    _require_exact_int(value.checkpoint_count, label="checkpoint_count", maximum=512)
    _require_exact_int(value.snapshot_count, label="snapshot_count", maximum=16)
    _require_exact_bool(value.used_fallback, label="used_fallback")
    if value.disposition in {"complete", "reused"}:
        if value.manifest_path is None:
            raise ValueError("completed runner outcome requires manifest_path")
        _require_abs_path(value.manifest_path, label="manifest_path")
        if value.generation != 0 or value.checkpoint_count != 512 or value.snapshot_count != 16:
            raise ValueError("completed runner outcome requires generation zero and complete observation counts")
        if value.disposition == "reused" and value.used_fallback:
            raise ValueError("reused runner outcome cannot report recovery fallback")
    else:
        if value.manifest_path is not None:
            raise ValueError("requeue outcome must not expose a final manifest")
        if value.generation < 1:
            raise ValueError("requeue outcome requires a positive durable generation")


def _validate_submission_outcome(value: object) -> None:
    if type(value) is not OneCellSubmissionOutcome:
        raise TypeError("outcome must be exact OneCellSubmissionOutcome")
    if value.disposition != "accepted":
        raise ValueError("submission outcome must be accepted")
    _require_hex(value.launch_sha256, label="launch_sha256")
    _require_abs_path(value.claim_path, label="claim_path")
    _require_hex(value.claim_sha256, label="claim_sha256")
    _require_abs_path(value.receipt_path, label="receipt_path")
    _require_hex(value.receipt_sha256, label="receipt_sha256")
    _require_hex(value.sbatch_argv_sha256, label="sbatch_argv_sha256")
    _require_positive_decimal(value.array_job_id, label="array_job_id")


def _snapshot_record(value: object, expected: type[object]) -> object:
    if type(value) is not expected:
        raise TypeError(f"value must be exact {expected.__name__}")
    try:
        if expected is OneCellAuthorizedTask:
            _validate_authorized_task(value)
            assert type(value) is OneCellAuthorizedTask
            launch = _deep_clone_snapshot_value(value.launch)
            assert type(launch) is OneCellLaunchAuthority
            values = {
                field.name: _deep_clone_snapshot_value(getattr(value, field.name))
                for field in fields(OneCellAuthorizedTask)
                if field.name not in {"launch", "task"}
            }
            values["launch"] = launch
            values["task"] = launch.ordered_tasks[value.array_position]
            return OneCellAuthorizedTask(**values)
        return _deep_clone_snapshot_value(value)
    except AttributeError as error:
        raise TypeError(f"{expected.__name__} must be fully initialized") from error


def _deep_clone_snapshot_value(value: object) -> object:
    value_type = type(value)
    if value is None or value_type in {bool, int, str, bytes}:
        return value
    if value_type is tuple:
        return tuple(_deep_clone_snapshot_value(item) for item in value)
    campaign_record_types = (
        OneCellBootstrapMatrixIdentity,
        OneCellTaskMapIdentity,
        OneCellHorizonBranch,
        OneCellCampaignAuthority,
    )
    if value_type in campaign_record_types:
        record_fields = fields(value_type)
        present = tuple(hasattr(value, field.name) for field in record_fields)
        if not all(present):
            if value_type is OneCellCampaignAuthority and not any(present):
                # Private parser fixtures carry a deliberately opaque blank
                # campaign marker and are permanently nonexecuting.
                return object.__new__(OneCellCampaignAuthority)
            raise AttributeError("campaign snapshot record is partially initialized")
        cloned = object.__new__(value_type)
        for field in record_fields:
            object.__setattr__(cloned, field.name, _deep_clone_snapshot_value(getattr(value, field.name)))
        return cloned
    record_types = (
        OneCellLaunchTask,
        OneCellSlurmResourceEnvelope,
        OneCellRunnerPaths,
        OneCellLaunchAuthority,
        OneCellRunnerOutcome,
        OneCellSubmissionOutcome,
    )
    if value_type not in record_types:
        raise TypeError(f"snapshot contains unsupported exact type {value_type.__name__}")
    return value_type(
        **{field.name: _deep_clone_snapshot_value(getattr(value, field.name)) for field in fields(value_type)}
    )


def _fpathconf_bound(descriptor: int, name: str, *, hard_limit: int, label: str) -> int:
    """Return the finite effective filesystem bound for a held descriptor."""

    if type(descriptor) is not int or descriptor < 0:
        raise TypeError("pathconf descriptor must be an open built-in integer")
    try:
        observed = os.fpathconf(descriptor, name)
    except (OSError, ValueError) as error:
        raise OneCellRunnerAuthorizationError(
            f"{label} filesystem limit is unavailable",
            exit_code=76,
        ) from error
    if type(observed) is not int or observed == 0 or observed < -1:
        raise OneCellRunnerAuthorizationError(
            f"{label} filesystem limit is invalid",
            exit_code=76,
        )
    return hard_limit if observed == -1 else min(hard_limit, observed)


def _validate_descriptor_component_limit(descriptor: int, component: str, *, label: str) -> None:
    if type(component) is not str or not component or "/" in component or "\x00" in component:
        raise OneCellRunnerAuthorizationError(f"{label} is not one path component", exit_code=76)
    try:
        encoded = os.fsencode(component)
    except UnicodeError as error:
        raise OneCellRunnerAuthorizationError(f"{label} cannot be encoded", exit_code=76) from error
    limit = _fpathconf_bound(descriptor, "PC_NAME_MAX", hard_limit=255, label=label)
    if len(encoded) > limit:
        raise OneCellRunnerAuthorizationError(f"{label} exceeds the held parent name limit", exit_code=76)


def _validate_descriptor_path_limit(descriptor: int, rendered: str, *, label: str) -> None:
    if type(rendered) is not str or not rendered or "\x00" in rendered:
        raise OneCellRunnerAuthorizationError(f"{label} is not a valid rendered path", exit_code=76)
    try:
        encoded = os.fsencode(rendered)
    except UnicodeError as error:
        raise OneCellRunnerAuthorizationError(f"{label} cannot be encoded", exit_code=76) from error
    limit = _fpathconf_bound(descriptor, "PC_PATH_MAX", hard_limit=4096, label=label)
    if len(encoded) > limit:
        raise OneCellRunnerAuthorizationError(f"{label} exceeds the filesystem path limit", exit_code=76)


def _validate_named_child_limits(
    descriptor: int,
    parent_path: str,
    component: str,
    *,
    label: str,
) -> None:
    _validate_descriptor_component_limit(descriptor, component, label=f"{label} component")
    _validate_descriptor_path_limit(
        descriptor,
        os.path.join(parent_path, component),
        label=label,
    )


def _validate_existing_named_path_limits(path: str, *, label: str) -> None:
    selected = _require_abs_path(path, label=label)
    parent = os.path.dirname(selected)
    component = os.path.basename(selected)
    chain, parts = _open_absolute_directory_chain(parent)
    try:
        _verify_directory_chain(chain, parts)
        _validate_named_child_limits(chain[-1], parent, component, label=label)
        _verify_directory_chain(chain, parts)
    finally:
        _close_directory_chain(chain)


def _validate_argv_path_limits(
    argv: tuple[str, ...],
    *,
    reference_directories: tuple[str, ...],
    label: str,
) -> None:
    if type(argv) is not tuple or not argv or any(type(item) is not str or not item for item in argv):
        raise TypeError(f"{label} must be a nonempty exact string tuple")
    bound = 4096
    if not reference_directories:
        raise TypeError(f"{label} requires at least one filesystem reference")
    for reference in reference_directories:
        selected = _require_abs_path(reference, label=f"{label} reference")
        chain, parts = _open_absolute_directory_chain(selected)
        try:
            _verify_directory_chain(chain, parts)
            bound = min(
                bound,
                _fpathconf_bound(chain[-1], "PC_PATH_MAX", hard_limit=4096, label=label),
            )
        finally:
            _close_directory_chain(chain)
    if any(len(os.fsencode(item)) > bound for item in argv):
        raise OneCellRunnerAuthorizationError(f"{label} member exceeds the filesystem path limit", exit_code=76)


def _validate_relative_path_limits(root: str, parts: tuple[str, ...], *, label: str) -> None:
    selected_root = _require_abs_path(root, label=f"{label} root")
    chain, named_parts = _open_absolute_directory_chain(selected_root)
    try:
        _verify_directory_chain(chain, named_parts)
        current = selected_root
        for part in parts:
            if type(part) is not str or _SAFE_COMPONENT.fullmatch(part) is None:
                raise OneCellRunnerAuthorizationError(f"{label} component is invalid", exit_code=76)
            _validate_named_child_limits(chain[-1], current, part, label=label)
            current = os.path.join(current, part)
        _verify_directory_chain(chain, named_parts)
    finally:
        _close_directory_chain(chain)


def _validate_relative_leaf_path_limits(
    root: str,
    parts: tuple[str, ...],
    leaves: tuple[str, ...],
    *,
    label: str,
) -> None:
    selected_root = _require_abs_path(root, label=f"{label} root")
    if type(leaves) is not tuple or not leaves:
        raise TypeError(f"{label} leaves must be a nonempty exact tuple")
    root_chain, root_parts = _open_absolute_directory_chain(selected_root)
    chain = list(root_chain)
    named_parts = list(root_parts)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        _verify_directory_chain(tuple(chain), tuple(named_parts))
        current = selected_root
        missing_parent = False
        for part in parts:
            if type(part) is not str or _SAFE_COMPONENT.fullmatch(part) is None:
                raise OneCellRunnerAuthorizationError(f"{label} component is invalid", exit_code=76)
            _validate_named_child_limits(chain[-1], current, part, label=label)
            if not missing_parent:
                try:
                    child = os.open(part, flags, dir_fd=chain[-1])
                except FileNotFoundError:
                    missing_parent = True
                except OSError as error:
                    exit_code = 77 if error.errno in {errno.EACCES, errno.EPERM} else 76
                    raise OneCellRunnerAuthorizationError(
                        f"{label} existing parent cannot be inspected",
                        exit_code=exit_code,
                    ) from error
                else:
                    info = os.fstat(child)
                    try:
                        named = os.stat(part, dir_fd=chain[-1], follow_symlinks=False)
                    except OSError as error:
                        os.close(child)
                        raise OneCellRunnerAuthorizationError(
                            f"{label} existing parent identity vanished",
                            exit_code=76,
                        ) from error
                    if not stat.S_ISDIR(info.st_mode) or (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                        os.close(child)
                        raise OneCellRunnerAuthorizationError(
                            f"{label} existing parent identity changed",
                            exit_code=76,
                        )
                    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                        os.close(child)
                        raise OneCellRunnerAuthorizationError(
                            f"{label} existing parent is not private",
                            exit_code=77,
                        )
                    chain.append(child)
                    named_parts.append(part)
            current = os.path.join(current, part)
        for leaf in leaves:
            if type(leaf) is not str or _SAFE_COMPONENT.fullmatch(leaf) is None:
                raise OneCellRunnerAuthorizationError(f"{label} leaf is invalid", exit_code=76)
            _validate_named_child_limits(chain[-1], current, leaf, label=label)
        _verify_directory_chain(tuple(chain), tuple(named_parts))
    finally:
        _close_directory_chain(tuple(chain))


def _read_regular_file(
    path: str,
    *,
    label: str,
    maximum: int,
    expected_mode: int | None = None,
    expected_uid: int | None = None,
    require_single_link: bool = True,
    forbid_group_world_write: bool = False,
) -> bytes:
    _require_exact_bool(forbid_group_world_write, label=f"{label} forbid_group_world_write")
    selected_path = _require_abs_path(path, label=label)
    parent_path = os.path.dirname(selected_path)
    component = os.path.basename(selected_path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    chain, parts = _open_absolute_directory_chain(parent_path)
    descriptor: int | None = None
    try:
        _verify_directory_chain(chain, parts)
        _validate_named_child_limits(chain[-1], parent_path, component, label=label)
        try:
            descriptor = os.open(component, flags, dir_fd=chain[-1])
        except FileNotFoundError as error:
            raise OneCellRunnerAuthorizationError(f"{label} cannot be opened safely", exit_code=66) from error
        except OSError as error:
            if error.errno in {errno.ELOOP, errno.ENOTDIR, errno.EISDIR}:
                exit_code = 76
            elif error.errno in {errno.EACCES, errno.EPERM}:
                exit_code = 77
            else:
                exit_code = 74
            raise OneCellRunnerAuthorizationError(f"{label} cannot be opened safely", exit_code=exit_code) from error
        info = os.fstat(descriptor)
        try:
            named = os.stat(component, dir_fd=chain[-1], follow_symlinks=False)
        except OSError as error:
            raise OneCellRunnerAuthorizationError(f"{label} named identity vanished", exit_code=76) from error
        if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
            raise OneCellRunnerAuthorizationError(f"{label} named identity changed", exit_code=76)
        _verify_directory_chain(chain, parts)
        if not stat.S_ISREG(info.st_mode):
            raise OneCellRunnerAuthorizationError(f"{label} is not a regular file", exit_code=76)
        if require_single_link and info.st_nlink != 1:
            raise OneCellRunnerAuthorizationError(f"{label} is linked", exit_code=76)
        if expected_uid is not None and info.st_uid != expected_uid:
            raise OneCellRunnerAuthorizationError(f"{label} has the wrong owner", exit_code=77)
        if expected_mode is not None and stat.S_IMODE(info.st_mode) != expected_mode:
            raise OneCellRunnerAuthorizationError(f"{label} has the wrong mode", exit_code=77)
        if forbid_group_world_write and stat.S_IMODE(info.st_mode) & 0o022:
            raise OneCellRunnerAuthorizationError(f"{label} is writable by group or world", exit_code=77)
        if not 0 < info.st_size <= maximum:
            raise OneCellRunnerAuthorizationError(f"{label} is empty or oversized", exit_code=76)
        chunks: list[bytes] = []
        remaining = info.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1 << 20))
            if not chunk:
                raise OneCellRunnerAuthorizationError(f"{label} changed during read", exit_code=76)
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise OneCellRunnerAuthorizationError(f"{label} grew during read", exit_code=76)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ):
            raise OneCellRunnerAuthorizationError(f"{label} changed during read", exit_code=76)
        if not stat.S_ISREG(after.st_mode):
            raise OneCellRunnerAuthorizationError(f"{label} stopped being a regular file", exit_code=76)
        if require_single_link and after.st_nlink != 1:
            raise OneCellRunnerAuthorizationError(f"{label} link count changed", exit_code=76)
        if expected_uid is not None and after.st_uid != expected_uid:
            raise OneCellRunnerAuthorizationError(f"{label} owner changed", exit_code=76)
        if expected_mode is not None and stat.S_IMODE(after.st_mode) != expected_mode:
            raise OneCellRunnerAuthorizationError(f"{label} mode changed", exit_code=76)
        if forbid_group_world_write and stat.S_IMODE(after.st_mode) & 0o022:
            raise OneCellRunnerAuthorizationError(f"{label} became writable by group or world", exit_code=76)
        try:
            named_after = os.stat(component, dir_fd=chain[-1], follow_symlinks=False)
        except OSError as error:
            raise OneCellRunnerAuthorizationError(f"{label} named identity vanished", exit_code=76) from error
        if (named_after.st_dev, named_after.st_ino) != (after.st_dev, after.st_ino):
            raise OneCellRunnerAuthorizationError(f"{label} named identity changed", exit_code=76)
        _verify_directory_chain(chain, parts)
        return b"".join(chunks)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        _close_directory_chain(chain)


def _validate_private_directory(path: str, *, label: str, mode: int = 0o700) -> os.stat_result:
    selected = _require_abs_path(path, label=label)
    try:
        initial = os.lstat(selected)
    except OSError as error:
        raise OneCellRunnerAuthorizationError(f"{label} does not exist", exit_code=66) from error
    if not stat.S_ISDIR(initial.st_mode) or stat.S_ISLNK(initial.st_mode):
        raise OneCellRunnerAuthorizationError(f"{label} is not a real directory", exit_code=76)
    chain, parts = _open_absolute_directory_chain(selected)
    try:
        _verify_directory_chain(chain, parts)
        info = os.fstat(chain[-1])
        if (initial.st_dev, initial.st_ino) != (info.st_dev, info.st_ino):
            raise OneCellRunnerAuthorizationError(f"{label} identity changed", exit_code=76)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != mode:
            raise OneCellRunnerAuthorizationError(f"{label} ownership or mode is invalid", exit_code=77)
        return info
    finally:
        _close_directory_chain(chain)


def _read_bound_runtime_file(
    path: str,
    *,
    label: str,
    maximum: int,
    expected_uid: int | None = None,
    expected_mode: int | None = None,
    require_single_link: bool = True,
    forbid_group_world_write: bool = False,
) -> bytes:
    try:
        return _read_regular_file(
            path,
            label=label,
            maximum=maximum,
            expected_uid=expected_uid,
            expected_mode=expected_mode,
            require_single_link=require_single_link,
            forbid_group_world_write=forbid_group_world_write,
        )
    except OneCellRunnerAuthorizationError as error:
        if error.exit_code == 66:
            raise OneCellRunnerAuthorizationError(
                f"{label} bound runtime identity is unavailable", exit_code=78
            ) from error
        raise


def _validate_tool_file(
    *,
    label: str,
    path: str,
    owner_uid: int,
    mode: int,
    size_bytes: int,
    digest: str,
) -> None:
    if os.path.realpath(path) != path:
        raise OneCellRunnerAuthorizationError(f"{label} live realpath differs", exit_code=78)
    selected = _read_regular_file(
        path,
        label=label,
        maximum=_MAX_TOOL_BYTES,
        expected_uid=owner_uid,
        require_single_link=False,
    )
    try:
        info = os.lstat(path)
    except OSError as error:
        raise OneCellRunnerAuthorizationError(f"{label} identity vanished", exit_code=78) from error
    if stat.S_ISLNK(info.st_mode) or stat.S_IMODE(info.st_mode) != mode:
        raise OneCellRunnerAuthorizationError(f"{label} mode or symlink identity changed", exit_code=78)
    if len(selected) != size_bytes or _sha256(selected) != digest:
        raise OneCellRunnerAuthorizationError(f"{label} byte identity changed", exit_code=78)


def _validate_bound_tool_file(
    *,
    label: str,
    path: str,
    owner_uid: int,
    mode: int,
    size_bytes: int,
    digest: str,
) -> None:
    try:
        _validate_tool_file(
            label=label,
            path=path,
            owner_uid=owner_uid,
            mode=mode,
            size_bytes=size_bytes,
            digest=digest,
        )
    except OneCellRunnerAuthorizationError as error:
        if error.exit_code == 66:
            raise OneCellRunnerAuthorizationError(
                f"{label} bound deployment identity is unavailable", exit_code=78
            ) from error
        raise


def _validate_scheduler_tool_file(
    *,
    label: str,
    path: str,
    owner_uid: int,
    mode: int,
    size_bytes: int,
    digest: str,
) -> None:
    try:
        _validate_tool_file(
            label=label,
            path=path,
            owner_uid=owner_uid,
            mode=mode,
            size_bytes=size_bytes,
            digest=digest,
        )
    except OneCellRunnerAuthorizationError as error:
        if error.exit_code == 66:
            raise OneCellSchedulerError(f"{label} is unavailable", exit_code=69) from error
        raise


def _git_prefix(paths: OneCellRunnerPaths, *, checkout: str | None = None) -> tuple[str, ...]:
    selected_checkout = (
        paths.authorization_checkout
        if checkout is None
        else _require_abs_path(
            checkout,
            label="Git checkout",
        )
    )
    return (
        paths.git_executable,
        "--no-pager",
        "--no-replace-objects",
        "--literal-pathspecs",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "diff.external=",
        "-c",
        "credential.helper=",
        "-C",
        selected_checkout,
    )


def _git_command(
    paths: OneCellRunnerPaths,
    suffix: tuple[str, ...],
    *,
    maximum: int = _MAX_JSONL,
    accepted_returncodes: tuple[int, ...] = (0,),
    checkout: str | None = None,
) -> _ProcessResult:
    selected_checkout = (
        paths.authorization_checkout if checkout is None else _require_abs_path(checkout, label="Git checkout")
    )
    version_argv = (paths.git_executable, "--version")
    command_argv = _git_prefix(paths, checkout=selected_checkout) + suffix
    references = (selected_checkout, os.path.dirname(paths.git_executable))
    _validate_argv_path_limits(version_argv, reference_directories=references, label="Git version argv")
    _validate_argv_path_limits(command_argv, reference_directories=references, label="Git authority argv")
    _validate_bound_tool_file(
        label="Git executable",
        path=paths.git_executable,
        owner_uid=paths.git_owner_uid,
        mode=paths.git_mode,
        size_bytes=paths.git_size_bytes,
        digest=paths.git_sha256,
    )
    environment = _GIT_ENVIRONMENT
    version = _run_bounded_process(
        version_argv,
        environment=environment,
        timeout_seconds=30,
        capture_limit=257,
    )
    expected_version = paths.git_version.encode("ascii") + b"\n"
    if (
        version.returncode != 0
        or version.stdout != expected_version
        or version.stderr
        or version.stdout_overflow
        or version.stderr_overflow
        or version.timed_out
        or version.spawn_ambiguous
    ):
        raise OneCellRunnerAuthorizationError("Git version identity changed", exit_code=78)
    result = _run_bounded_process(
        command_argv,
        environment=environment,
        timeout_seconds=30,
        capture_limit=maximum,
    )
    if (
        result.returncode not in accepted_returncodes
        or result.stderr
        or result.stdout_overflow
        or result.stderr_overflow
        or result.timed_out
        or result.spawn_ambiguous
    ):
        raise OneCellRunnerAuthorizationError("Git authority command failed", exit_code=76)
    return result


def _require_git_ancestor(
    paths: OneCellRunnerPaths,
    *,
    prerequisite: str,
    trusted_commit: str,
    checkout: str | None = None,
) -> None:
    _require_hex(prerequisite, label="prerequisite commit", width=40)
    _require_hex(trusted_commit, label="trusted commit", width=40)
    keyword_arguments: dict[str, object] = {
        "maximum": 1,
        "accepted_returncodes": (0, 1),
    }
    if checkout is not None:
        keyword_arguments["checkout"] = checkout
    result = _git_command(
        paths,
        ("merge-base", "--is-ancestor", prerequisite, trusted_commit),
        **keyword_arguments,
    )
    if result.stdout or result.returncode != 0:
        raise OneCellRunnerAuthorizationError(
            "prerequisite commit is not reachable from the pushed launch commit",
            exit_code=76,
        )


def _git_blob(
    paths: OneCellRunnerPaths,
    reference: dict[str, object],
    *,
    maximum: int,
    trusted_commit: str | None = None,
) -> bytes:
    selected = _parse_file_ref(reference, label="file reference")
    commit = str(selected["commit"])
    member_path = str(selected["path"])
    if trusted_commit is not None:
        _require_git_ancestor(paths, prerequisite=commit, trusted_commit=trusted_commit)
    tree = _git_command(paths, ("ls-tree", "-z", commit, "--", member_path), maximum=1024)
    expected_suffix = b"\t" + member_path.encode("utf-8") + b"\x00"
    if not tree.stdout.endswith(expected_suffix):
        raise OneCellRunnerAuthorizationError("Git member path is absent or ambiguous", exit_code=76)
    prefix = tree.stdout[: -len(expected_suffix)]
    pieces = prefix.split(b" ")
    if len(pieces) != 3 or pieces[0] not in {b"100644", b"100755"} or pieces[1] != b"blob":
        raise OneCellRunnerAuthorizationError("Git member is not an exact regular blob", exit_code=76)
    blob = _git_command(paths, ("cat-file", "blob", f"{commit}:{member_path}"), maximum=maximum).stdout
    if len(blob) != selected["size_bytes"] or _sha256(blob) != selected["sha256"]:
        raise OneCellRunnerAuthorizationError("Git blob bytes do not match their file reference", exit_code=76)
    return blob


def _parse_tool_identity(value: object, *, label: str) -> dict[str, object]:
    record = _exact_dict(
        value,
        keys=("path", "realpath", "owner_uid", "mode", "size_bytes", "sha256", "version"),
        label=label,
    )
    path = _require_abs_path(record["path"], label=f"{label}.path")
    realpath = _require_abs_path(record["realpath"], label=f"{label}.realpath")
    owner = _require_exact_int(record["owner_uid"], label=f"{label}.owner_uid", maximum=_U32_MAX)
    mode_text = _require_exact_str(record["mode"], label=f"{label}.mode", maximum=4)
    if _MODE_TEXT.fullmatch(mode_text) is None:
        raise OneCellRunnerValidationError(f"{label}.mode is not four-digit octal")
    mode = int(mode_text, 8)
    size = _require_exact_int(record["size_bytes"], label=f"{label}.size_bytes", minimum=1, maximum=_MAX_TOOL_BYTES)
    digest = _require_hex(record["sha256"], label=f"{label}.sha256")
    version = _require_exact_str(record["version"], label=f"{label}.version", maximum=256)
    _validate_tool_fields(
        label=label,
        path=path,
        realpath=realpath,
        owner_uid=owner,
        mode=mode,
        size_bytes=size,
        sha256=digest,
        version=version,
    )
    return {
        "path": path,
        "realpath": realpath,
        "owner_uid": owner,
        "mode": mode,
        "size_bytes": size,
        "sha256": digest,
        "version": version,
    }


def _parse_string_map(value: object, *, keys: tuple[str, ...], label: str) -> tuple[tuple[str, str], ...]:
    record = _exact_dict(value, keys=keys, label=label)
    result = tuple((key, _require_exact_str(record[key], label=f"{label}.{key}")) for key in keys)
    return result


def _parse_launch_wire(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="launch.json")
    fixture_metadata: dict[str, object] | None = None
    if type(value) is dict and value.get("profile") == _LAUNCH_FIXTURE_PROFILE:
        fixture_record = _exact_dict(
            value,
            keys=(
                "profile",
                "launch_id",
                "lane",
                "self_path",
                "authorities",
                "ordered_tasks",
                "mapping",
                "batch_script",
                "resources",
                "runtime_python",
                "git_environment",
                "git_local_config",
                "tool_identities",
                "paths",
                "user_approval",
                "fixture",
            ),
            label="fixture launch",
        )
        fixture = _exact_dict(
            fixture_record["fixture"],
            keys=("fixture_id", "scientific_execution_permitted"),
            label="fixture launch metadata",
        )
        if (
            fixture["fixture_id"] != "slice-8b-authority-parser-nonexecuting"
            or fixture["scientific_execution_permitted"] is not False
        ):
            raise OneCellRunnerValidationError("fixture launch metadata is not frozen")
        fixture_metadata = fixture
        value = dict(value)
        del value["fixture"]
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "launch_id",
            "lane",
            "self_path",
            "authorities",
            "ordered_tasks",
            "mapping",
            "batch_script",
            "resources",
            "runtime_python",
            "git_environment",
            "git_local_config",
            "tool_identities",
            "paths",
            "user_approval",
        ),
        label="launch.json",
    )
    if record["profile"] not in {_LAUNCH_PROFILE, _LAUNCH_FIXTURE_PROFILE}:
        raise OneCellRunnerValidationError("launch profile is not frozen")
    _require_ascii_token(record["launch_id"], label="launch_id")
    if record["lane"] not in _LANES:
        raise OneCellRunnerValidationError("launch lane is not frozen")
    _require_safe_path(record["self_path"], label="launch.self_path")
    authorities = _exact_dict(
        record["authorities"],
        keys=(
            "protocol_commit",
            "protocol_sha256",
            "source_commit",
            "wheel_sha256",
            "campaign_commit",
            "campaign_manifest_sha256",
            "configuration_sha256",
            "deployment_lock",
            "deployment",
            "admission",
            "branch",
        ),
        label="launch.authorities",
    )
    for key in ("protocol_commit", "source_commit", "campaign_commit"):
        _require_hex(authorities[key], label=f"launch.authorities.{key}", width=40)
    for key in ("protocol_sha256", "wheel_sha256", "campaign_manifest_sha256", "configuration_sha256"):
        _require_hex(authorities[key], label=f"launch.authorities.{key}")
    for key in ("deployment_lock", "deployment", "admission"):
        _parse_file_ref(authorities[key], label=f"launch.authorities.{key}")
    if authorities["branch"] is not None:
        _parse_file_ref(authorities["branch"], label="launch.authorities.branch")
    ordered = _exact_dict(
        record["ordered_tasks"],
        keys=("profile", "path", "sha256", "size_bytes", "task_count"),
        label="launch.ordered_tasks",
    )
    if ordered["profile"] != _ORDERED_TASKS_PROFILE:
        raise OneCellRunnerValidationError("ordered task profile is not frozen")
    _require_safe_path(ordered["path"], label="launch.ordered_tasks.path")
    _require_hex(ordered["sha256"], label="launch.ordered_tasks.sha256")
    task_count = _require_exact_int(
        ordered["task_count"], label="launch.ordered_tasks.task_count", minimum=1, maximum=_MAX_TASKS
    )
    _require_exact_int(ordered["size_bytes"], label="launch.ordered_tasks.size_bytes", minimum=1, maximum=_MAX_JSONL)
    mapping = _exact_dict(
        record["mapping"], keys=("profile", "array_first", "array_last", "array_step"), label="launch.mapping"
    )
    if (
        mapping["profile"] != _ARRAY_PROFILE
        or type(mapping["array_first"]) is not int
        or mapping["array_first"] != 0
        or type(mapping["array_last"]) is not int
        or mapping["array_last"] != task_count - 1
        or type(mapping["array_step"]) is not int
        or mapping["array_step"] != 1
    ):
        raise OneCellRunnerValidationError("launch array mapping is not zero-based contiguous step one")
    batch = _exact_dict(
        record["batch_script"],
        keys=("source_commit", "path", "git_blob", "sha256", "size_bytes"),
        label="launch.batch_script",
    )
    _require_hex(batch["source_commit"], label="launch.batch_script.source_commit", width=40)
    _require_safe_path(batch["path"], label="launch.batch_script.path")
    _require_hex(batch["git_blob"], label="launch.batch_script.git_blob", width=40)
    _require_hex(batch["sha256"], label="launch.batch_script.sha256")
    _require_exact_int(batch["size_bytes"], label="launch.batch_script.size_bytes", minimum=1, maximum=_MAX_JSON)
    _exact_dict(
        record["resources"],
        keys=(
            "profile",
            "partition",
            "wall_minutes",
            "cpus_per_task",
            "memory_mib",
            "array_concurrency",
            "signal_name",
            "signal_warning_seconds",
            "receipt_handshake_seconds",
            "scheduler_timeout_seconds",
            "max_requeues_per_task",
            "sbatch_executable",
            "scontrol_executable",
            "scheduler_environment",
            "scientific_environment",
        ),
        label="launch.resources",
    )
    _exact_dict(
        record["runtime_python"],
        keys=(
            "sidecar_path",
            "sidecar_bytes_hex",
            "sidecar_sha256",
            "sidecar_size_bytes",
            "executable_path",
            "executable_realpath",
            "executable_sha256",
            "executable_size_bytes",
        ),
        label="launch.runtime_python",
    )
    tools = _exact_dict(record["tool_identities"], keys=("sbatch", "scontrol", "git"), label="launch.tool_identities")
    parsed_tools = {name: _parse_tool_identity(tools[name], label=name) for name in ("sbatch", "scontrol", "git")}
    paths = _exact_dict(
        record["paths"],
        keys=(
            "campaign_root",
            "authorization_checkout",
            "authorization_directory",
            "runtime_python_file",
            "python_executable",
            "task_root",
            "attempt_root",
            "log_root",
            "cache_root",
            "temporary_root",
            "submission_ledger_root",
            "submission_ledger_lock",
            "authorized_run_directory",
            "batch_script",
            "stdout_template",
            "stderr_template",
            "git_executable",
            "coordinator_remote_url",
            "coordinator_fetch_refspec",
        ),
        label="launch.paths",
    )
    for key in (
        "campaign_root",
        "authorization_checkout",
        "authorization_directory",
        "runtime_python_file",
        "python_executable",
        "task_root",
        "attempt_root",
        "log_root",
        "cache_root",
        "temporary_root",
        "submission_ledger_root",
        "submission_ledger_lock",
        "authorized_run_directory",
        "batch_script",
        "stdout_template",
        "stderr_template",
        "git_executable",
    ):
        _require_abs_path(paths[key], label=f"launch.paths.{key}")
    _require_exact_str(paths["coordinator_remote_url"], label="launch.paths.coordinator_remote_url")
    _require_exact_str(paths["coordinator_fetch_refspec"], label="launch.paths.coordinator_fetch_refspec")
    _parse_string_map(
        record["git_environment"], keys=tuple(key for key, _ in _GIT_ENVIRONMENT), label="launch.git_environment"
    )
    git_local_config = _parse_git_local_config(record["git_local_config"])
    if (
        paths["coordinator_fetch_refspec"] != _MAIN_FETCH_REFSPEC
        or git_local_config["remote_origin_url"] != paths["coordinator_remote_url"]
        or git_local_config["remote_origin_fetch"] != _MAIN_FETCH_REFSPEC
    ):
        raise OneCellRunnerValidationError("launch coordinator configuration is not frozen to origin/main")
    approval = _exact_dict(
        record["user_approval"], keys=("actor", "approved_at_utc", "scope"), label="launch.user_approval"
    )
    for key in approval:
        _require_exact_str(approval[key], label=f"launch.user_approval.{key}", maximum=128)
    _require_utc_timestamp(approval["approved_at_utc"], label="launch.user_approval.approved_at_utc")
    if record["profile"] == _LAUNCH_PROFILE and (
        approval["scope"] != record["lane"] or approval["scope"] in {"test-suite", "fixture"}
    ):
        raise OneCellRunnerAuthorizationError("production launch approval scope is invalid", exit_code=77)
    record["_parsed_tools"] = parsed_tools
    record["_fixture"] = fixture_metadata
    return record


def _parse_deployment_lock(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="deployment.lock.json")
    record = _exact_dict(
        value,
        keys=("profile", "protocol", "source", "wheel", "campaign", "environment", "profiles", "batch_script"),
        label="deployment.lock.json",
    )
    if record["profile"] != _DEPLOYMENT_LOCK_PROFILE:
        raise OneCellRunnerValidationError("deployment-lock profile is not frozen")
    protocol = _exact_dict(
        record["protocol"], keys=("blob", "commit", "path", "sha256", "size_bytes"), label="deployment-lock.protocol"
    )
    _require_hex(protocol["blob"], label="deployment-lock.protocol.blob", width=40)
    _require_hex(protocol["commit"], label="deployment-lock.protocol.commit", width=40)
    if protocol["path"] != "PRE-DISCOVERY-PROTOCOL.md":
        raise OneCellRunnerValidationError("deployment-lock protocol path is not frozen")
    _require_hex(protocol["sha256"], label="deployment-lock.protocol.sha256")
    _require_exact_int(
        protocol["size_bytes"], label="deployment-lock.protocol.size_bytes", minimum=1, maximum=_MAX_JSON
    )
    source = _exact_dict(record["source"], keys=("commit",), label="deployment-lock.source")
    _require_hex(source["commit"], label="deployment-lock.source.commit", width=40)
    wheel = _exact_dict(record["wheel"], keys=("member_path", "sha256", "size_bytes"), label="deployment-lock.wheel")
    _require_safe_path(wheel["member_path"], label="deployment-lock.wheel.member_path")
    _require_hex(wheel["sha256"], label="deployment-lock.wheel.sha256")
    _require_exact_int(wheel["size_bytes"], label="deployment-lock.wheel.size_bytes", minimum=1, maximum=1 << 30)
    campaign = _exact_dict(
        record["campaign"], keys=("configuration_sha256", "authority_manifest_sha256"), label="deployment-lock.campaign"
    )
    _require_hex(campaign["configuration_sha256"], label="deployment-lock.campaign.configuration_sha256")
    _require_hex(campaign["authority_manifest_sha256"], label="deployment-lock.campaign.authority_manifest_sha256")
    environment = _exact_dict(
        record["environment"],
        keys=(
            "python_implementation",
            "python_version",
            "numpy_version",
            "numba_version",
            "llvmlite_version",
            "package_version",
            "constraints_sha256",
        ),
        label="deployment-lock.environment",
    )
    for key, item in environment.items():
        if key == "constraints_sha256":
            _require_hex(item, label=f"deployment-lock.environment.{key}")
        else:
            _require_exact_str(item, label=f"deployment-lock.environment.{key}", maximum=128)
    profiles = _exact_dict(
        record["profiles"],
        keys=("campaign", "scientific_identity", "array_mapping", "runner"),
        label="deployment-lock.profiles",
    )
    expected_profiles = {
        "campaign": "tetris-pre-one-cell-campaign@1",
        "scientific_identity": "tetris-pre-one-cell-scientific-identity@1",
        "array_mapping": _ARRAY_PROFILE,
        "runner": _RUNNER_PROFILE,
    }
    if profiles != expected_profiles:
        raise OneCellRunnerValidationError("deployment-lock profiles are not frozen")
    batch = _exact_dict(
        record["batch_script"],
        keys=("source_commit", "path", "git_blob", "sha256", "size_bytes"),
        label="deployment-lock.batch_script",
    )
    _require_hex(batch["source_commit"], label="deployment-lock.batch_script.source_commit", width=40)
    _require_safe_path(batch["path"], label="deployment-lock.batch_script.path")
    _require_hex(batch["git_blob"], label="deployment-lock.batch_script.git_blob", width=40)
    _require_hex(batch["sha256"], label="deployment-lock.batch_script.sha256")
    _require_exact_int(
        batch["size_bytes"], label="deployment-lock.batch_script.size_bytes", minimum=1, maximum=_MAX_JSON
    )
    return record


def _parse_deployment(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="deployment certificate")
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "protocol",
            "source_commit",
            "wheel",
            "campaign",
            "batch_script",
            "environment",
            "runtime_python",
            "scientific_environment",
            "scheduler_environment",
            "git_environment",
            "git_local_config",
            "tool_identities",
            "coordinator_repository",
            "paths",
            "mapping_profile",
            "ownership",
            "capacity",
            "certification",
        ),
        label="deployment certificate",
    )
    if record["profile"] != _DEPLOYMENT_PROFILE:
        raise OneCellRunnerValidationError("deployment profile is not frozen")
    protocol = _exact_dict(
        record["protocol"], keys=("blob", "commit", "path", "sha256", "size_bytes"), label="deployment.protocol"
    )
    _require_hex(protocol["blob"], label="deployment.protocol.blob", width=40)
    _require_hex(protocol["commit"], label="deployment.protocol.commit", width=40)
    if protocol["path"] != "PRE-DISCOVERY-PROTOCOL.md":
        raise OneCellRunnerValidationError("deployment protocol path is not frozen")
    _require_hex(protocol["sha256"], label="deployment.protocol.sha256")
    _require_exact_int(protocol["size_bytes"], label="deployment.protocol.size_bytes", minimum=1, maximum=_MAX_JSON)
    _require_hex(record["source_commit"], label="deployment.source_commit", width=40)
    _parse_file_ref(record["wheel"], label="deployment.wheel")
    campaign = _exact_dict(
        record["campaign"], keys=("commit", "configuration", "manifest", "deployment_lock"), label="deployment.campaign"
    )
    _require_hex(campaign["commit"], label="deployment.campaign.commit", width=40)
    for key in ("configuration", "manifest", "deployment_lock"):
        _parse_file_ref(campaign[key], label=f"deployment.campaign.{key}")
        if campaign[key]["commit"] != campaign["commit"]:
            raise OneCellRunnerValidationError("deployment campaign member commit differs from campaign.commit")
    batch = _exact_dict(
        record["batch_script"],
        keys=("source_commit", "path", "git_blob", "sha256", "size_bytes"),
        label="deployment.batch_script",
    )
    _require_hex(batch["source_commit"], label="deployment.batch_script.source_commit", width=40)
    _require_safe_path(batch["path"], label="deployment.batch_script.path")
    _require_hex(batch["git_blob"], label="deployment.batch_script.git_blob", width=40)
    _require_hex(batch["sha256"], label="deployment.batch_script.sha256")
    _require_exact_int(batch["size_bytes"], label="deployment.batch_script.size_bytes", minimum=1, maximum=_MAX_JSON)
    environment = _exact_dict(
        record["environment"],
        keys=(
            "python_implementation",
            "python_version",
            "numpy_version",
            "numba_version",
            "llvmlite_version",
            "package_version",
            "constraints_sha256",
        ),
        label="deployment.environment",
    )
    for key, item in environment.items():
        if key == "constraints_sha256":
            _require_hex(item, label=f"deployment.environment.{key}")
        else:
            _require_exact_str(item, label=f"deployment.environment.{key}", maximum=128)
    runtime = _exact_dict(
        record["runtime_python"],
        keys=(
            "sidecar_name",
            "sidecar_bytes_hex",
            "sidecar_sha256",
            "sidecar_size_bytes",
            "executable_path",
            "executable_realpath",
            "executable_sha256",
            "executable_size_bytes",
        ),
        label="deployment.runtime_python",
    )
    if runtime["sidecar_name"] != "runtime-python.path":
        raise OneCellRunnerValidationError("runtime sidecar name is not frozen")
    _parse_scientific_environment_template(record["scientific_environment"])
    scheduler_environment = _parse_string_map(
        record["scheduler_environment"], keys=("LANG", "LC_ALL"), label="deployment.scheduler_environment"
    )
    if scheduler_environment != _SCHEDULER_ENVIRONMENT:
        raise OneCellRunnerValidationError("deployment scheduler environment is not frozen")
    git_environment = _parse_string_map(
        record["git_environment"], keys=tuple(key for key, _ in _GIT_ENVIRONMENT), label="deployment.git_environment"
    )
    if git_environment != _GIT_ENVIRONMENT:
        raise OneCellRunnerValidationError("deployment Git environment is not frozen")
    git_local_config = _parse_git_local_config(record["git_local_config"])
    tools = _exact_dict(
        record["tool_identities"], keys=("sbatch", "scontrol", "git"), label="deployment.tool_identities"
    )
    record["_parsed_tools"] = {
        name: _parse_tool_identity(tools[name], label=name) for name in ("sbatch", "scontrol", "git")
    }
    repository = _exact_dict(
        record["coordinator_repository"],
        keys=("repository_id", "remote_url", "fetch_refspec", "branch", "authorization_readback_root"),
        label="deployment.coordinator_repository",
    )
    for key, item in repository.items():
        if key == "authorization_readback_root":
            _require_abs_path(item, label=f"deployment.coordinator_repository.{key}")
        elif key == "repository_id":
            _require_ascii_token(item, label="deployment.coordinator_repository.repository_id")
        else:
            _require_exact_str(item, label=f"deployment.coordinator_repository.{key}")
    if (
        repository["branch"] != "main"
        or repository["fetch_refspec"] != _MAIN_FETCH_REFSPEC
        or git_local_config["remote_origin_url"] != repository["remote_url"]
        or git_local_config["remote_origin_fetch"] != _MAIN_FETCH_REFSPEC
    ):
        raise OneCellRunnerValidationError("coordinator repository/configuration is not frozen to origin/main")
    paths = _exact_dict(
        record["paths"],
        keys=(
            "article_checkout",
            "software_checkout",
            "coordinator_checkout",
            "campaign_root",
            "environment_root",
            "python_executable",
            "private_task_root",
            "attempt_root",
            "log_root",
            "cache_root",
            "temporary_root",
            "submission_ledger_root",
            "submission_ledger_lock",
            "authorized_run_directory",
            "batch_script",
            "sbatch_executable",
            "scontrol_executable",
            "git_executable",
        ),
        label="deployment.paths",
    )
    for key, item in paths.items():
        _require_abs_path(item, label=f"deployment.paths.{key}")
    if record["mapping_profile"] != _ARRAY_PROFILE:
        raise OneCellRunnerValidationError("deployment mapping profile is not frozen")
    ownership = _exact_dict(
        record["ownership"],
        keys=(
            "campaign_user",
            "campaign_uid",
            "trusted_base",
            "trusted_administrator_uids",
            "campaign_root_mode",
            "authorization_readback_root_mode",
            "environment_root_mode",
            "private_task_root_mode",
            "attempt_root_mode",
            "log_root_mode",
            "cache_root_mode",
            "temporary_root_mode",
            "no_symlink_ancestors",
            "user_owned_mutable_roots",
        ),
        label="deployment.ownership",
    )
    _require_exact_str(ownership["campaign_user"], label="deployment.ownership.campaign_user", maximum=128)
    campaign_uid = _require_exact_int(
        ownership["campaign_uid"], label="deployment.ownership.campaign_uid", maximum=_U32_MAX
    )
    _require_abs_path(ownership["trusted_base"], label="deployment.ownership.trusted_base")
    administrators = _exact_list(
        ownership["trusted_administrator_uids"], label="deployment.ownership.trusted_administrator_uids", maximum=128
    )
    if not administrators or any(type(item) is not int or not 0 <= item <= _U32_MAX for item in administrators):
        raise OneCellRunnerValidationError("trusted administrator UIDs are malformed")
    if administrators != sorted(set(administrators)) or campaign_uid in administrators:
        raise OneCellRunnerValidationError("trusted administrator UIDs are not sorted unique and disjoint")
    for key in (
        "campaign_root_mode",
        "authorization_readback_root_mode",
        "environment_root_mode",
        "private_task_root_mode",
        "attempt_root_mode",
        "log_root_mode",
        "cache_root_mode",
        "temporary_root_mode",
    ):
        if ownership[key] != "0700":
            raise OneCellRunnerValidationError("deployment ownership modes are not private")
    if ownership["no_symlink_ancestors"] is not True or ownership["user_owned_mutable_roots"] is not True:
        raise OneCellRunnerValidationError("deployment ownership Boolean evidence is not true")
    capacity = _exact_dict(
        record["capacity"],
        keys=(
            "quota_bytes",
            "free_bytes",
            "free_inodes",
            "private_state_envelope_bytes",
            "final_output_envelope_bytes",
        ),
        label="deployment.capacity",
    )
    if capacity["quota_bytes"] is not None:
        _require_exact_int(capacity["quota_bytes"], label="deployment.capacity.quota_bytes")
    for key in ("free_bytes", "free_inodes", "private_state_envelope_bytes", "final_output_envelope_bytes"):
        _require_exact_int(capacity[key], label=f"deployment.capacity.{key}")
    certification = _exact_dict(
        record["certification"],
        keys=(
            "checks",
            "exhaustive_map_sha256",
            "no_launch_authority",
            "zero_scientific_tasks",
            "zero_campaign_finals",
            "zero_submissions",
            "zero_requeues",
        ),
        label="deployment.certification",
    )
    checks = _exact_dict(
        certification["checks"],
        keys=(
            "git_authority",
            "protocol",
            "campaign_members",
            "wheel_install",
            "runtime_identity",
            "path_safety",
            "capacity",
            "exhaustive_mapping",
            "no_launch",
        ),
        label="deployment.certification.checks",
    )
    if any(value is not True for value in checks.values()):
        raise OneCellRunnerValidationError("deployment certification checks are not all true")
    _require_hex(certification["exhaustive_map_sha256"], label="deployment.certification.exhaustive_map_sha256")
    if certification["no_launch_authority"] is not True or any(
        certification[key] != 0 or type(certification[key]) is not int
        for key in ("zero_scientific_tasks", "zero_campaign_finals", "zero_submissions", "zero_requeues")
    ):
        raise OneCellRunnerValidationError("deployment closure evidence is not zero/no-launch")
    return record


def _parse_scientific_environment_template(value: object) -> dict[str, object]:
    record = _exact_dict(
        value,
        keys=("profile", "ordered_keys", "literal_bindings", "path_bindings", "cpu_bindings"),
        label="scientific_environment",
    )
    if record["profile"] != _SCIENTIFIC_ENV_PROFILE:
        raise OneCellRunnerValidationError("scientific environment profile is not frozen")
    ordered = _exact_list(
        record["ordered_keys"], label="scientific_environment.ordered_keys", maximum=len(_SCIENTIFIC_ENV_KEYS)
    )
    if tuple(ordered) != _SCIENTIFIC_ENV_KEYS:
        raise OneCellRunnerValidationError("scientific environment order is not frozen")
    literal = _exact_dict(
        record["literal_bindings"],
        keys=("LANG", "LC_ALL", "OMP_DYNAMIC", "MKL_DYNAMIC"),
        label="scientific_environment.literal_bindings",
    )
    if literal != {"LANG": "C", "LC_ALL": "C", "OMP_DYNAMIC": "FALSE", "MKL_DYNAMIC": "FALSE"}:
        raise OneCellRunnerValidationError("scientific literal environment is not frozen")
    paths = _exact_dict(
        record["path_bindings"], keys=("TMPDIR", "NUMBA_CACHE_DIR"), label="scientific_environment.path_bindings"
    )
    if paths != {"TMPDIR": "temporary_root", "NUMBA_CACHE_DIR": "cache_root/numba"}:
        raise OneCellRunnerValidationError("scientific path bindings are not frozen")
    cpus = _exact_list(record["cpu_bindings"], label="scientific_environment.cpu_bindings", maximum=7)
    if tuple(cpus) != _SCIENTIFIC_ENV_KEYS[4:11]:
        raise OneCellRunnerValidationError("scientific CPU bindings are not frozen")
    return record


def _parse_git_local_config(value: object) -> dict[str, object]:
    keys = (
        "core_repositoryformatversion",
        "core_filemode",
        "core_bare",
        "core_logallrefupdates",
        "remote_origin_url",
        "remote_origin_fetch",
        "branch_main_remote",
        "branch_main_merge",
    )
    record = _exact_dict(value, keys=keys, label="git_local_config")
    expected_literals = {
        "core_repositoryformatversion": "0",
        "core_filemode": "true",
        "core_bare": "false",
        "core_logallrefupdates": "true",
        "branch_main_remote": "origin",
        "branch_main_merge": "refs/heads/main",
    }
    for key, expected in expected_literals.items():
        if record[key] != expected:
            raise OneCellRunnerValidationError("Git local configuration literals are not frozen")
    _require_exact_str(record["remote_origin_url"], label="git_local_config.remote_origin_url")
    _require_exact_str(record["remote_origin_fetch"], label="git_local_config.remote_origin_fetch")
    return record


def _parse_common_authorities(value: object, *, label: str) -> dict[str, object]:
    record = _exact_dict(
        value,
        keys=("protocol_commit", "protocol_sha256", "source_commit", "wheel_sha256", "campaign_commit", "deployment"),
        label=label,
    )
    for key in ("protocol_commit", "source_commit", "campaign_commit"):
        _require_hex(record[key], label=f"{label}.{key}", width=40)
    for key in ("protocol_sha256", "wheel_sha256"):
        _require_hex(record[key], label=f"{label}.{key}")
    _parse_file_ref(record["deployment"], label=f"{label}.deployment")
    return record


def _parse_branch(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="branch decision")
    record = _exact_dict(
        value, keys=("profile", "authorities", "initial_p0", "rule", "selection"), label="branch decision"
    )
    if record["profile"] != _BRANCH_PROFILE:
        raise OneCellRunnerValidationError("branch profile is not frozen")
    _parse_common_authorities(record["authorities"], label="branch.authorities")
    initial = _exact_dict(
        record["initial_p0"],
        keys=("completion", "launch", "task_count", "ordered_tasks_sha256", "final_manifests"),
        label="branch.initial_p0",
    )
    _parse_file_ref(initial["completion"], label="branch.initial_p0.completion")
    _parse_file_ref(initial["launch"], label="branch.initial_p0.launch")
    _parse_file_ref(initial["final_manifests"], label="branch.initial_p0.final_manifests")
    _require_exact_int(initial["task_count"], label="branch.initial_p0.task_count", minimum=1, maximum=_MAX_TASKS)
    _require_hex(initial["ordered_tasks_sha256"], label="branch.initial_p0.ordered_tasks_sha256")
    rule = _exact_dict(
        record["rule"], keys=("profile", "input_sha256", "l_star", "confirmation_required"), label="branch.rule"
    )
    if rule["profile"] != _HORIZON_BRANCH_PROFILE:
        raise OneCellRunnerValidationError("branch rule profile does not join the Slice 8A horizon branch")
    _require_hex(rule["input_sha256"], label="branch.rule.input_sha256")
    final_manifests = initial["final_manifests"]
    assert type(final_manifests) is dict
    if rule["input_sha256"] != final_manifests["sha256"]:
        raise OneCellRunnerAuthorizationError(
            "branch rule input does not bind the exact initial-P0 final-manifest set",
            exit_code=76,
        )
    if rule["l_star"] is not None and (type(rule["l_star"]) is not int or rule["l_star"] not in {64, 256, 1024}):
        raise OneCellRunnerValidationError("branch l_star is not frozen")
    _require_exact_bool(rule["confirmation_required"], label="branch.rule.confirmation_required")
    selection = _exact_dict(
        record["selection"],
        keys=("branch_id", "p1_task_map_id", "p1_task_map_sha256", "confirmation_task_map_id"),
        label="branch.selection",
    )
    for key in ("branch_id", "p1_task_map_id"):
        _require_exact_str(selection[key], label=f"branch.selection.{key}", maximum=128)
    _require_hex(selection["p1_task_map_sha256"], label="branch.selection.p1_task_map_sha256")
    if rule["l_star"] is None:
        if selection["confirmation_task_map_id"] is not None or rule["confirmation_required"] is not False:
            raise OneCellRunnerValidationError("no-L-star branch has confirmation fields")
    elif selection["confirmation_task_map_id"] != "p0-confirmation" or rule["confirmation_required"] is not True:
        raise OneCellRunnerValidationError("L-star branch lacks exact confirmation fields")
    expected_branch = "p1-no-l-star" if rule["l_star"] is None else f"p1-l-star-{rule['l_star']}"
    if selection["branch_id"] != expected_branch or selection["p1_task_map_id"] != expected_branch:
        raise OneCellRunnerValidationError("branch selection does not match the frozen rule")
    return record


def _parse_admission(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="admission")
    fixture_metadata: dict[str, object] | None = None
    if type(value) is dict and value.get("profile") == _ADMISSION_FIXTURE_PROFILE:
        fixture_record = _exact_dict(
            value,
            keys=("profile", "authorities", "lane", "decision", "evidence", "user_approval", "fixture"),
            label="fixture admission",
        )
        fixture = _exact_dict(
            fixture_record["fixture"],
            keys=("fixture_id", "scientific_execution_permitted"),
            label="fixture admission metadata",
        )
        if (
            fixture["fixture_id"] != "slice-8b-authority-parser-nonexecuting"
            or fixture["scientific_execution_permitted"] is not False
        ):
            raise OneCellRunnerValidationError("fixture admission metadata is not frozen")
        fixture_metadata = fixture
        value = dict(value)
        del value["fixture"]
    record = _exact_dict(
        value, keys=("profile", "authorities", "lane", "decision", "evidence", "user_approval"), label="admission"
    )
    if record["profile"] not in {_ADMISSION_PROFILE, _ADMISSION_FIXTURE_PROFILE}:
        raise OneCellRunnerValidationError("admission profile is not frozen")
    authorities = _exact_dict(
        record["authorities"],
        keys=(
            "protocol_commit",
            "protocol_sha256",
            "source_commit",
            "wheel_sha256",
            "campaign_commit",
            "configuration_sha256",
            "deployment_lock",
            "deployment",
            "branch",
        ),
        label="admission.authorities",
    )
    for key in ("protocol_commit", "source_commit", "campaign_commit"):
        _require_hex(authorities[key], label=f"admission.authorities.{key}", width=40)
    for key in ("protocol_sha256", "wheel_sha256", "configuration_sha256"):
        _require_hex(authorities[key], label=f"admission.authorities.{key}")
    for key in ("deployment_lock", "deployment"):
        _parse_file_ref(authorities[key], label=f"admission.authorities.{key}")
    if authorities["branch"] is not None:
        _parse_file_ref(authorities["branch"], label="admission.authorities.branch")
    lane = _exact_dict(
        record["lane"], keys=("lane_id", "wave", "role", "task_map_id", "task_count"), label="admission.lane"
    )
    if lane["lane_id"] not in _LANES:
        raise OneCellRunnerValidationError("admission lane is not frozen")
    for key in ("wave", "role", "task_map_id"):
        _require_exact_str(lane[key], label=f"admission.lane.{key}", maximum=128)
    _require_exact_int(lane["task_count"], label="admission.lane.task_count", minimum=1, maximum=_MAX_TASKS)
    expected_map, expected_wave, expected_role, expected_count = _LANE_SPECS[str(lane["lane_id"])]
    if (
        lane["task_map_id"] != expected_map
        or lane["wave"] != expected_wave
        or lane["role"] != expected_role
        or lane["task_count"] != expected_count
    ):
        raise OneCellRunnerValidationError("admission lane does not match its frozen Slice 8A task map")
    if record["decision"] != "admitted":
        raise OneCellRunnerAuthorizationError("lane is not admitted", exit_code=77)
    evidence_keys = (
        "f0_completion",
        "initial_p0_completion",
        "branch_decision",
        "confirmation_completion",
        "b2_precision_audit",
        "b2_resource_admission",
        "clean_resource_admission",
    )
    evidence = _exact_dict(record["evidence"], keys=evidence_keys, label="admission.evidence")
    for key, item in evidence.items():
        if item is not None:
            _parse_file_ref(item, label=f"admission.evidence.{key}")
    branch_required = lane["lane_id"] in {
        "p0-confirmation",
        "p1-no-l-star",
        "p1-l-star-64",
        "p1-l-star-256",
        "p1-l-star-1024",
    }
    if (authorities["branch"] is not None) is not branch_required:
        raise OneCellRunnerValidationError("admission branch presence does not match lane")
    if lane["lane_id"] in {"f0", "p0-initial"}:
        required: set[str] = set()
    elif lane["lane_id"] == "p0-confirmation":
        required = {"initial_p0_completion", "branch_decision"}
    elif lane["lane_id"] == "b2":
        required = {"f0_completion", "b2_precision_audit", "b2_resource_admission"}
    elif lane["lane_id"] == "b1" or str(lane["lane_id"]).startswith("p1-"):
        required = {
            "f0_completion",
            "initial_p0_completion",
            "branch_decision",
            "b2_precision_audit",
            "b2_resource_admission",
            "clean_resource_admission",
        }
        # confirmation_completion is checked against the branch rule later.
    else:
        required = set()
    for key in evidence_keys:
        if key in required and evidence[key] is None:
            raise OneCellRunnerValidationError(f"admission evidence {key} is required")
        if key not in required and key != "confirmation_completion" and evidence[key] is not None:
            raise OneCellRunnerValidationError(f"admission evidence {key} is inapplicable")
    approval = _exact_dict(
        record["user_approval"], keys=("actor", "approved_at_utc", "scope"), label="admission.user_approval"
    )
    for key in approval:
        _require_exact_str(approval[key], label=f"admission.user_approval.{key}", maximum=128)
    _require_utc_timestamp(approval["approved_at_utc"], label="admission.user_approval.approved_at_utc")
    if not approval["actor"] or approval["scope"] != lane["lane_id"] or approval["scope"] in {"test-suite", "fixture"}:
        raise OneCellRunnerAuthorizationError("production user approval scope is invalid", exit_code=77)
    record["_fixture"] = fixture_metadata
    return record


def _parse_readback(payload: bytes) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="readback.json")
    record = _exact_dict(value, keys=("profile", "repository", "launch", "observation"), label="readback.json")
    if record["profile"] != _READBACK_PROFILE:
        raise OneCellRunnerValidationError("readback profile is not frozen")
    repository = _exact_dict(
        record["repository"],
        keys=("repository_id", "remote_url", "fetch_refspec", "branch"),
        label="readback.repository",
    )
    _require_ascii_token(repository["repository_id"], label="readback.repository.repository_id")
    for key in ("remote_url", "fetch_refspec", "branch"):
        _require_exact_str(repository[key], label=f"readback.repository.{key}")
    if repository["branch"] != "main" or repository["fetch_refspec"] != _MAIN_FETCH_REFSPEC:
        raise OneCellRunnerValidationError("readback repository is not frozen to origin/main")
    _parse_file_ref(record["launch"], label="readback.launch")
    observation = _exact_dict(
        record["observation"],
        keys=("checkout_root", "head_commit", "origin_main_commit", "detached", "clean", "observed_at_utc"),
        label="readback.observation",
    )
    _require_abs_path(observation["checkout_root"], label="readback.observation.checkout_root")
    _require_hex(observation["head_commit"], label="readback.observation.head_commit", width=40)
    _require_hex(observation["origin_main_commit"], label="readback.observation.origin_main_commit", width=40)
    if observation["detached"] is not True or observation["clean"] is not True:
        raise OneCellRunnerAuthorizationError("readback checkout observation is not detached and clean", exit_code=76)
    _require_utc_timestamp(observation["observed_at_utc"], label="readback.observation.observed_at_utc")
    if (
        observation["head_commit"] != observation["origin_main_commit"]
        or observation["head_commit"] != record["launch"]["commit"]
    ):
        raise OneCellRunnerAuthorizationError("readback commit observations disagree", exit_code=76)
    return record


def _parse_ordered_tasks(
    payload: bytes,
    *,
    campaign: OneCellCampaignAuthority,
    deployment_lock_sha256: str,
    software_commit: str,
    wheel_sha256: str,
    branch_decision_sha256: str | None,
) -> tuple[OneCellLaunchTask, ...]:
    rows = _parse_canonical_jsonl(payload, label="ordered-tasks.jsonl", profile=_LAUNCH_TASK_PROFILE)
    tasks: list[OneCellLaunchTask] = []
    identities: set[str] = set()
    directories: set[str] = set()
    indices: set[tuple[str, int]] = set()
    keys = (
        "profile",
        "array_position",
        "wave",
        "role",
        "task_map_id",
        "scientific_index",
        "scientific_identity_hex",
        "scientific_identity_sha256",
        "scientific_identity_size_bytes",
        "relative_task_directory",
    )
    for position, raw in enumerate(rows):
        row = _exact_dict(raw, keys=keys, label=f"ordered task {position}")
        if type(row["array_position"]) is not int or row["array_position"] != position:
            raise OneCellRunnerValidationError("ordered task array positions are not contiguous")
        task_index = _require_exact_int(row["scientific_index"], label="scientific_index", maximum=_MAX_TASKS - 1)
        for key in ("wave", "role", "task_map_id"):
            _require_exact_str(row[key], label=f"ordered task {key}", maximum=128)
        identity_hex = _require_exact_str(
            row["scientific_identity_hex"], label="scientific_identity_hex", maximum=2 * _MAX_IDENTITY
        )
        if len(identity_hex) % 2 or re.fullmatch(r"[0-9a-f]+", identity_hex) is None:
            raise OneCellRunnerValidationError("scientific identity hex is malformed")
        identity = bytes.fromhex(identity_hex)
        if (
            not identity
            or len(identity) > _MAX_IDENTITY
            or row["scientific_identity_size_bytes"] != len(identity)
            or type(row["scientific_identity_size_bytes"]) is not int
        ):
            raise OneCellRunnerValidationError("scientific identity size is invalid")
        digest = _require_hex(row["scientific_identity_sha256"], label="scientific_identity_sha256")
        if _sha256(identity) != digest:
            raise OneCellRunnerValidationError("scientific identity digest differs from its bytes")
        try:
            campaign_task = decode_one_cell_campaign_task(
                campaign=campaign,
                task_map_id=str(row["task_map_id"]),
                task_index=task_index,
            )
            expected_identity = explain_one_cell_campaign_task(
                campaign=campaign,
                task_map_id=str(row["task_map_id"]),
                task_index=task_index,
                deployment_lock_sha256=deployment_lock_sha256,
                software_commit=software_commit,
                wheel_sha256=wheel_sha256,
                branch_decision_sha256=branch_decision_sha256,
            )
        except (OneCellCampaignValidationError, TypeError, ValueError) as error:
            raise OneCellRunnerValidationError("ordered task cannot be reproduced by Slice 8A") from error
        if expected_identity != identity or campaign_task.wave != row["wave"] or campaign_task.role != row["role"]:
            raise OneCellRunnerValidationError("ordered task differs from its Slice 8A authority")
        relative = _require_safe_path(row["relative_task_directory"], label="relative_task_directory")
        expected_relative = f"{row['wave']}/{task_index:020d}-{digest}"
        if relative != expected_relative:
            raise OneCellRunnerValidationError("ordered task relative directory is not frozen")
        if digest in identities or relative in directories or (str(row["task_map_id"]), task_index) in indices:
            raise OneCellRunnerValidationError("ordered tasks contain a duplicate identity or mapping")
        identities.add(digest)
        directories.add(relative)
        indices.add((str(row["task_map_id"]), task_index))
        tasks.append(
            OneCellLaunchTask(
                array_position=position,
                wave=str(row["wave"]),
                role=str(row["role"]),
                task_map_id=str(row["task_map_id"]),
                task_index=task_index,
                scientific_identity_bytes=identity,
                scientific_identity_sha256=digest,
                relative_task_directory=relative,
            )
        )
    return tuple(tasks)


def _validate_common_evidence_authorities(
    value: object,
    *,
    launch_authorities: dict[str, object],
    label: str,
) -> dict[str, object]:
    record = _parse_common_authorities(value, label=label)
    for key in ("protocol_commit", "protocol_sha256", "source_commit", "wheel_sha256", "campaign_commit"):
        if record[key] != launch_authorities[key]:
            raise OneCellRunnerAuthorizationError(f"{label} does not join the launch authority", exit_code=76)
    if record["deployment"] != launch_authorities["deployment"]:
        raise OneCellRunnerAuthorizationError(f"{label} deployment reference differs from launch", exit_code=76)
    return record


def _unique_file_refs(value: object, *, label: str, maximum: int = 128) -> tuple[dict[str, object], ...]:
    raw = _exact_list(value, label=label, maximum=maximum)
    if not raw:
        raise OneCellRunnerValidationError(f"{label} must be nonempty")
    parsed = tuple(_parse_file_ref(item, label=f"{label}[{index}]") for index, item in enumerate(raw))
    fingerprints = tuple(_canonical_json(item, newline=False) for item in parsed)
    if len(set(fingerprints)) != len(fingerprints):
        raise OneCellRunnerValidationError(f"{label} contains duplicate references")
    return parsed


def _parse_submission_reconciliation(
    payload: bytes,
    *,
    reconciliation_reference: object,
) -> dict[str, object]:
    """Validate committed reconciliation evidence without touching the ledger."""

    value = _parse_canonical_json(
        payload,
        label="submission reconciliation",
        maximum=64 << 10,
    )
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "launch",
            "claim",
            "receipt",
            "resolved_outcome",
            "resolved_array_job_id",
            "evidence",
            "automatic_replay_permitted",
            "additional_initial_sbatch_permitted",
            "superseding_launch_required",
            "approved_by",
            "approved_at_utc",
        ),
        label="submission reconciliation",
    )
    if record["profile"] != _RECONCILIATION_PROFILE:
        raise OneCellRunnerValidationError("submission reconciliation profile is not frozen")

    reconciliation_ref = _parse_file_ref(
        reconciliation_reference,
        label="submission reconciliation reference",
    )
    if reconciliation_ref["size_bytes"] != len(payload) or reconciliation_ref["sha256"] != _sha256(payload):
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation reference differs from its bytes",
            exit_code=76,
        )

    launch_ref = _parse_file_ref(record["launch"], label="submission reconciliation launch")
    launch_sha256 = str(launch_ref["sha256"])
    lane_alternation = "|".join(re.escape(lane) for lane in sorted(_LANES, key=lambda item: (-len(item), item)))
    launch_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/launches/(?:{lane_alternation})-[0-9]{{4}}/launch\.json\Z"
    )
    if launch_pattern.fullmatch(str(launch_ref["path"])) is None:
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation launch path is not exact",
            exit_code=76,
        )

    reconciliation_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/reconciliations/{re.escape(launch_sha256)}-[0-9]{{4}}/"
        r"reconciliation\.json\Z"
    )
    if reconciliation_pattern.fullmatch(str(reconciliation_ref["path"])) is None:
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation path does not bind its launch digest",
            exit_code=76,
        )

    claim_ref = _parse_file_ref(record["claim"], label="submission reconciliation claim")
    submission_prefix = f"authorizations/pre-one-cell-discovery-v1/submissions/{launch_sha256}"
    if claim_ref["path"] != f"{submission_prefix}/claim.json":
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation claim path does not bind its launch digest",
            exit_code=76,
        )
    receipt_ref: dict[str, object] | None = None
    if record["receipt"] is not None:
        receipt_ref = _parse_file_ref(record["receipt"], label="submission reconciliation receipt")
        if receipt_ref["path"] != f"{submission_prefix}/receipt.json":
            raise OneCellRunnerAuthorizationError(
                "submission reconciliation receipt path does not bind its launch digest",
                exit_code=76,
            )

    _unique_file_refs(record["evidence"], label="submission reconciliation evidence")
    outcome = _require_exact_str(
        record["resolved_outcome"],
        label="submission reconciliation resolved_outcome",
        maximum=8,
    )
    if outcome not in {"accepted", "rejected", "unknown"}:
        raise OneCellRunnerValidationError("submission reconciliation resolved outcome is invalid")
    if outcome == "accepted":
        _require_positive_decimal(
            record["resolved_array_job_id"],
            label="submission reconciliation resolved_array_job_id",
        )
    elif record["resolved_array_job_id"] is not None:
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation resolved job ID contradicts its outcome",
            exit_code=76,
        )
    if (
        record["automatic_replay_permitted"] is not False
        or record["additional_initial_sbatch_permitted"] is not False
        or record["superseding_launch_required"] is not True
    ):
        raise OneCellRunnerAuthorizationError(
            "submission reconciliation replay policy is not frozen",
            exit_code=76,
        )
    _require_exact_str(record["approved_by"], label="submission reconciliation approved_by", maximum=128)
    _require_utc_timestamp(
        record["approved_at_utc"],
        label="submission reconciliation approved_at_utc",
    )
    return record


def _validate_completed_launch_authorities(
    completed_launch: dict[str, object],
    *,
    completed_launch_ref: dict[str, object],
    completion_authorities: dict[str, object],
    launch_authorities: dict[str, object],
    expected_lane: str,
) -> dict[str, object]:
    authorities = completed_launch["authorities"]
    assert type(authorities) is dict
    for key in ("protocol_commit", "protocol_sha256", "source_commit", "wheel_sha256", "campaign_commit"):
        if authorities[key] != completion_authorities[key] or authorities[key] != launch_authorities[key]:
            raise OneCellRunnerAuthorizationError(
                "completed launch common authorities differ from completion/current launch",
                exit_code=76,
            )
    if (
        authorities["deployment"] != completion_authorities["deployment"]
        or authorities["deployment"] != launch_authorities["deployment"]
        or authorities["deployment_lock"] != launch_authorities["deployment_lock"]
        or authorities["campaign_manifest_sha256"] != launch_authorities["campaign_manifest_sha256"]
        or authorities["configuration_sha256"] != launch_authorities["configuration_sha256"]
    ):
        raise OneCellRunnerAuthorizationError("completed launch authority closure differs", exit_code=76)
    launch_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/launches/{re.escape(expected_lane)}-[0-9]{{4}}/launch\.json\Z"
    )
    if (
        launch_pattern.fullmatch(str(completed_launch_ref["path"])) is None
        or completed_launch["self_path"] != completed_launch_ref["path"]
    ):
        raise OneCellRunnerAuthorizationError("completed launch self path differs from its reference", exit_code=76)
    admission = authorities["admission"]
    assert type(admission) is dict
    admission_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/admissions/{re.escape(expected_lane)}-[0-9]{{4}}/admission\.json\Z"
    )
    if admission_pattern.fullmatch(str(admission["path"])) is None:
        raise OneCellRunnerAuthorizationError("completed launch admission path differs from its lane", exit_code=76)
    if expected_lane in {"f0", "p0-initial"}:
        if authorities["branch"] is not None:
            raise OneCellRunnerAuthorizationError("unbranched completion launch carries a branch", exit_code=76)
    elif expected_lane == "p0-confirmation" and authorities["branch"] is None:
        raise OneCellRunnerAuthorizationError("confirmation completion launch lacks its branch", exit_code=76)
    return authorities


def _validate_completion_evidence(
    paths: OneCellRunnerPaths,
    reference: dict[str, object],
    *,
    expected_lane: str,
    launch_authorities: dict[str, object],
    trusted_commit: str,
    campaign: OneCellCampaignAuthority,
) -> dict[str, object]:
    selected_ref = _parse_file_ref(reference, label=f"{expected_lane} completion reference")
    pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/completions/{re.escape(expected_lane)}-[0-9]{{4}}/completion\.json\Z"
    )
    if pattern.fullmatch(str(selected_ref["path"])) is None:
        raise OneCellRunnerAuthorizationError("completion reference path is not exact for its lane", exit_code=76)
    payload = _git_blob(paths, selected_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
    value = _parse_canonical_json(payload, label=f"{expected_lane} completion")
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "authorities",
            "lane_id",
            "launch",
            "ordered_tasks_sha256",
            "task_count",
            "final_manifests",
            "outcome",
            "completed_at_utc",
        ),
        label=f"{expected_lane} completion",
    )
    if (
        record["profile"] != _COMPLETION_PROFILE
        or record["lane_id"] != expected_lane
        or record["outcome"] != "complete"
    ):
        raise OneCellRunnerAuthorizationError("completion profile, lane, or outcome is invalid", exit_code=76)
    completion_authorities = _validate_common_evidence_authorities(
        record["authorities"],
        launch_authorities=launch_authorities,
        label=f"{expected_lane} completion authorities",
    )
    expected_count = _LANE_SPECS[expected_lane][3]
    if type(record["task_count"]) is not int or record["task_count"] != expected_count:
        raise OneCellRunnerAuthorizationError("completion task count differs from the frozen lane", exit_code=76)
    _require_hex(record["ordered_tasks_sha256"], label="completion ordered_tasks_sha256")
    _require_utc_timestamp(record["completed_at_utc"], label="completion completed_at_utc")
    completed_launch_ref = _parse_file_ref(record["launch"], label="completion launch")
    completed_launch_bytes = _git_blob(
        paths,
        completed_launch_ref,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    completed_launch = _parse_launch_wire(completed_launch_bytes)
    if completed_launch["profile"] != _LAUNCH_PROFILE or completed_launch["lane"] != expected_lane:
        raise OneCellRunnerAuthorizationError("completion launch profile or lane is invalid", exit_code=76)
    completed_launch_authorities = _validate_completed_launch_authorities(
        completed_launch,
        completed_launch_ref=completed_launch_ref,
        completion_authorities=completion_authorities,
        launch_authorities=launch_authorities,
        expected_lane=expected_lane,
    )
    completed_ordered = completed_launch["ordered_tasks"]
    assert type(completed_ordered) is dict
    completed_launch_directory = os.path.dirname(str(completed_launch_ref["path"]))
    if (
        completed_ordered["task_count"] != expected_count
        or completed_ordered["sha256"] != record["ordered_tasks_sha256"]
        or completed_ordered["path"] != f"{completed_launch_directory}/ordered-tasks.jsonl"
    ):
        raise OneCellRunnerAuthorizationError("completion does not reproduce its launch task set", exit_code=76)
    ordered_ref = _parse_file_ref(
        {
            "commit": completed_launch_ref["commit"],
            "path": completed_ordered["path"],
            "sha256": completed_ordered["sha256"],
            "size_bytes": completed_ordered["size_bytes"],
        },
        label="completion ordered tasks",
    )
    ordered_bytes = _git_blob(paths, ordered_ref, maximum=_MAX_JSONL, trusted_commit=trusted_commit)
    completed_branch = completed_launch_authorities["branch"]
    assert completed_branch is None or type(completed_branch) is dict
    ordered_tasks = _parse_ordered_tasks(
        ordered_bytes,
        campaign=campaign,
        deployment_lock_sha256=str(launch_authorities["deployment_lock"]["sha256"]),
        software_commit=str(launch_authorities["source_commit"]),
        wheel_sha256=str(launch_authorities["wheel_sha256"]),
        branch_decision_sha256=None if completed_branch is None else str(completed_branch["sha256"]),
    )
    expected_map, expected_wave, expected_role, _ = _LANE_SPECS[expected_lane]
    if (
        len(ordered_tasks) != expected_count
        or any(task.task_map_id != expected_map for task in ordered_tasks)
        or any(task.wave != expected_wave or task.role != expected_role for task in ordered_tasks)
    ):
        raise OneCellRunnerAuthorizationError("completion ordered task map differs from its frozen lane", exit_code=76)
    final_ref = _parse_file_ref(record["final_manifests"], label="completion final manifests")
    completion_directory = os.path.dirname(str(selected_ref["path"]))
    if final_ref["path"] != f"{completion_directory}/final-manifests.jsonl":
        raise OneCellRunnerAuthorizationError("completion final-manifest path is not exact", exit_code=76)
    final_bytes = _git_blob(paths, final_ref, maximum=8 << 20, trusted_commit=trusted_commit)
    final_rows = _parse_canonical_jsonl(
        final_bytes,
        label="completion final manifests",
        profile=_FINAL_MANIFEST_ROW_PROFILE,
        maximum=8 << 20,
        line_maximum=4 << 10,
        row_maximum=expected_count,
    )
    if len(final_rows) != expected_count:
        raise OneCellRunnerAuthorizationError("completion final-manifest row count differs", exit_code=76)
    identities: set[str] = set()
    finals: set[str] = set()
    for position, (ordered_task, final_row) in enumerate(zip(ordered_tasks, final_rows)):
        final_record = _exact_dict(
            final_row,
            keys=("profile", "array_position", "scientific_identity_sha256", "final_manifest_sha256"),
            label=f"completion final row {position}",
        )
        if (
            type(final_record["array_position"]) is not int
            or final_record["array_position"] != position
            or final_record["scientific_identity_sha256"] != ordered_task.scientific_identity_sha256
        ):
            raise OneCellRunnerAuthorizationError("completion final row does not join ordered task", exit_code=76)
        identity = _require_hex(final_record["scientific_identity_sha256"], label="completion identity digest")
        final_digest = _require_hex(final_record["final_manifest_sha256"], label="completion final digest")
        if identity in identities or final_digest in finals:
            raise OneCellRunnerAuthorizationError("completion final set contains duplicate digests", exit_code=76)
        identities.add(identity)
        finals.add(final_digest)
    record["_reference"] = selected_ref
    record["_final_reference"] = final_ref
    record["_launch_branch"] = completed_launch_authorities["branch"]
    return record


def _validate_precision_evidence(
    paths: OneCellRunnerPaths,
    reference: dict[str, object],
    *,
    launch_authorities: dict[str, object],
    trusted_commit: str,
) -> dict[str, object]:
    selected_ref = _parse_file_ref(reference, label="B2 precision audit reference")
    pattern = re.compile(r"authorizations/pre-one-cell-discovery-v1/audits/b2-precision-[0-9]{4}/audit\.json\Z")
    if pattern.fullmatch(str(selected_ref["path"])) is None:
        raise OneCellRunnerAuthorizationError("precision audit path is not exact", exit_code=76)
    payload = _git_blob(paths, selected_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
    value = _parse_canonical_json(payload, label="B2 precision audit")
    audit = _exact_dict(
        value,
        keys=("profile", "authorities", "audit_source", "audit_result", "decision", "reviewed_by", "reviewed_at_utc"),
        label="B2 precision audit",
    )
    if audit["profile"] != _PRECISION_AUDIT_PROFILE or audit["decision"] != "pass":
        raise OneCellRunnerAuthorizationError("precision audit profile or decision is invalid", exit_code=76)
    _validate_common_evidence_authorities(
        audit["authorities"], launch_authorities=launch_authorities, label="precision audit authorities"
    )
    _require_exact_str(audit["reviewed_by"], label="precision reviewed_by", maximum=128)
    _require_utc_timestamp(audit["reviewed_at_utc"], label="precision reviewed_at_utc")
    source_ref = _parse_file_ref(audit["audit_source"], label="precision audit source")
    _git_blob(paths, source_ref, maximum=_MAX_JSONL, trusted_commit=trusted_commit)
    result_ref = _parse_file_ref(audit["audit_result"], label="precision audit result")
    if result_ref["path"] != f"{os.path.dirname(str(selected_ref['path']))}/result.json":
        raise OneCellRunnerAuthorizationError("precision result path is not exact", exit_code=76)
    result_payload = _git_blob(paths, result_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
    result_value = _parse_canonical_json(result_payload, label="B2 precision result")
    result = _exact_dict(
        result_value,
        keys=("profile", "authorities", "inputs", "checks", "decision"),
        label="B2 precision result",
    )
    if result["profile"] != _PRECISION_RESULT_PROFILE or result["decision"] != "pass":
        raise OneCellRunnerAuthorizationError("precision result profile or decision is invalid", exit_code=76)
    _validate_common_evidence_authorities(
        result["authorities"], launch_authorities=launch_authorities, label="precision result authorities"
    )
    inputs = _unique_file_refs(result["inputs"], label="precision result inputs")
    if source_ref not in inputs:
        raise OneCellRunnerAuthorizationError("precision audit source is absent from result inputs", exit_code=76)
    for input_ref in inputs:
        _git_blob(paths, input_ref, maximum=_MAX_JSONL, trusted_commit=trusted_commit)
    checks = _exact_dict(
        result["checks"],
        keys=("archived_exp14_source", "preregistered_method", "precision_sufficient", "no_outcome_tuning"),
        label="precision result checks",
    )
    if any(item is not True for item in checks.values()):
        raise OneCellRunnerAuthorizationError("precision result checks are not all true", exit_code=76)
    audit["_result"] = result
    return audit


def _validate_resource_evidence(
    paths: OneCellRunnerPaths,
    reference: dict[str, object],
    *,
    expected_scope: str,
    launch_authorities: dict[str, object],
    trusted_commit: str,
) -> dict[str, object]:
    selected_ref = _parse_file_ref(reference, label=f"{expected_scope} resource admission reference")
    pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/resource-admissions/{re.escape(expected_scope)}-[0-9]{{4}}/admission\.json\Z"
    )
    if pattern.fullmatch(str(selected_ref["path"])) is None:
        raise OneCellRunnerAuthorizationError("resource admission path is not exact", exit_code=76)
    payload = _git_blob(paths, selected_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
    value = _parse_canonical_json(payload, label=f"{expected_scope} resource admission")
    admission = _exact_dict(
        value,
        keys=("profile", "authorities", "scope", "inputs", "analysis", "decision", "approved_by", "approved_at_utc"),
        label=f"{expected_scope} resource admission",
    )
    if (
        admission["profile"] != _RESOURCE_ADMISSION_PROFILE
        or admission["scope"] != expected_scope
        or admission["decision"] != "admitted"
    ):
        raise OneCellRunnerAuthorizationError("resource admission profile, scope, or decision is invalid", exit_code=76)
    _validate_common_evidence_authorities(
        admission["authorities"], launch_authorities=launch_authorities, label="resource admission authorities"
    )
    _require_exact_str(admission["approved_by"], label="resource approved_by", maximum=128)
    _require_utc_timestamp(admission["approved_at_utc"], label="resource approved_at_utc")
    inputs = _unique_file_refs(admission["inputs"], label="resource admission inputs")
    for input_ref in inputs:
        _git_blob(paths, input_ref, maximum=_MAX_JSONL, trusted_commit=trusted_commit)
    analysis_ref = _parse_file_ref(admission["analysis"], label="resource analysis")
    if analysis_ref["path"] != f"{os.path.dirname(str(selected_ref['path']))}/analysis.json":
        raise OneCellRunnerAuthorizationError("resource analysis path is not exact", exit_code=76)
    analysis_payload = _git_blob(paths, analysis_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
    analysis_value = _parse_canonical_json(analysis_payload, label=f"{expected_scope} resource analysis")
    analysis = _exact_dict(
        analysis_value,
        keys=(
            "profile",
            "authorities",
            "scope",
            "inputs",
            "estimates",
            "caps",
            "reserve_basis_points",
            "checks",
            "decision",
        ),
        label=f"{expected_scope} resource analysis",
    )
    if (
        analysis["profile"] != _RESOURCE_ANALYSIS_PROFILE
        or analysis["scope"] != expected_scope
        or analysis["decision"] != "admitted"
        or analysis["reserve_basis_points"] != 2000
        or type(analysis["reserve_basis_points"]) is not int
    ):
        raise OneCellRunnerAuthorizationError(
            "resource analysis profile, scope, reserve, or decision is invalid", exit_code=76
        )
    _validate_common_evidence_authorities(
        analysis["authorities"], launch_authorities=launch_authorities, label="resource analysis authorities"
    )
    analysis_inputs = _unique_file_refs(analysis["inputs"], label="resource analysis inputs")
    if analysis_inputs != inputs:
        raise OneCellRunnerAuthorizationError("resource admission and analysis inputs differ", exit_code=76)
    if expected_scope == "b2":
        names = (
            "projected_core_seconds_with_reserve",
            "projected_final_bytes",
            "projected_private_bytes",
            "f0_max_runtime_seconds",
            "f0_max_rss_bytes",
            "f0_min_signal_grace_seconds",
        )
        expected_caps = (1_080_000, 4_294_967_296, 12_884_901_888, 3_600, 2_147_483_648, 900)
        check_names = (
            "f0_integrity",
            "f0_runtime",
            "f0_memory",
            "f0_signal_grace",
            "precision",
            "projected_core_hours",
            "projected_final_bytes",
            "projected_private_bytes",
        )
    else:
        names = (
            "projected_core_seconds_with_reserve",
            "p1_final_bytes",
            "campaign_final_bytes",
            "campaign_private_bytes",
        )
        expected_caps = (2_880_000, 1_073_741_824, 6_442_450_944, 17_179_869_184)
        check_names = (
            "b2_forensic_admitted",
            "selected_horizon_complete",
            "p0_integrity",
            "p0_runtime",
            "p0_memory",
            "p0_signal_grace",
            "clean_scalability",
            "aggregate_core_hours",
            "p1_final_bytes",
            "campaign_final_bytes",
            "campaign_private_bytes",
        )
    estimates = _exact_dict(analysis["estimates"], keys=names, label="resource estimates")
    caps = _exact_dict(analysis["caps"], keys=names, label="resource caps")
    for name, expected_cap in zip(names, expected_caps):
        _require_exact_int(estimates[name], label=f"resource estimate {name}")
        if type(caps[name]) is not int or caps[name] != expected_cap:
            raise OneCellRunnerAuthorizationError("resource cap differs from protocol", exit_code=76)
    if expected_scope == "b2":
        if any(estimates[name] >= caps[name] for name in names[:3]):
            raise OneCellRunnerAuthorizationError("projected B2 resources do not stay below caps", exit_code=76)
        if estimates[names[3]] > caps[names[3]] or estimates[names[4]] > caps[names[4]]:
            raise OneCellRunnerAuthorizationError("F0 runtime or memory exceeds its cap", exit_code=76)
        if estimates[names[5]] < caps[names[5]]:
            raise OneCellRunnerAuthorizationError("F0 signal grace is below its floor", exit_code=76)
    elif any(estimates[name] >= caps[name] for name in names):
        raise OneCellRunnerAuthorizationError("clean resource estimates do not stay below caps", exit_code=76)
    checks = _exact_dict(analysis["checks"], keys=check_names, label="resource analysis checks")
    if any(item is not True for item in checks.values()):
        raise OneCellRunnerAuthorizationError("resource analysis checks are not all true", exit_code=76)
    admission["_analysis"] = analysis
    return admission


def _validate_admission_evidence(
    paths: OneCellRunnerPaths,
    *,
    admission: dict[str, object],
    configured_branch: dict[str, object] | None,
    launch_authorities: dict[str, object],
    trusted_commit: str,
    campaign: OneCellCampaignAuthority | None = None,
) -> None:
    evidence = admission["evidence"]
    lane = admission["lane"]
    assert type(evidence) is dict and type(lane) is dict
    completions: dict[str, dict[str, object]] = {}
    for key, expected_lane in (
        ("f0_completion", "f0"),
        ("initial_p0_completion", "p0-initial"),
        ("confirmation_completion", "p0-confirmation"),
    ):
        if evidence[key] is not None:
            completion_kwargs: dict[str, object] = {
                "expected_lane": expected_lane,
                "launch_authorities": launch_authorities,
                "trusted_commit": trusted_commit,
            }
            if campaign is not None:
                completion_kwargs["campaign"] = campaign
            completions[key] = _validate_completion_evidence(paths, evidence[key], **completion_kwargs)  # type: ignore[arg-type]
    evidence_branch: dict[str, object] | None = None
    if evidence["branch_decision"] is not None:
        branch_ref = _parse_file_ref(evidence["branch_decision"], label="admission evidence branch")
        admission_authorities = admission["authorities"]
        assert type(admission_authorities) is dict
        if configured_branch is not None and branch_ref != admission_authorities["branch"]:
            raise OneCellRunnerAuthorizationError(
                "configured branch and admission evidence references differ",
                exit_code=76,
            )
        branch_bytes = _git_blob(paths, branch_ref, maximum=_MAX_JSON, trusted_commit=trusted_commit)
        evidence_branch = _parse_branch(branch_bytes)
        _validate_common_evidence_authorities(
            evidence_branch["authorities"],
            launch_authorities=launch_authorities,
            label="evidence branch authorities",
        )
        branch_id = str(evidence_branch["selection"]["branch_id"])
        expected_path = f"authorizations/pre-one-cell-discovery-v1/branches/{branch_id}/decision.json"
        if branch_ref["path"] != expected_path:
            raise OneCellRunnerAuthorizationError("evidence branch path is not exact", exit_code=76)
        if configured_branch is not None and evidence_branch != configured_branch:
            raise OneCellRunnerAuthorizationError("configured and evidence branch decisions differ", exit_code=76)
        initial = evidence_branch["initial_p0"]
        assert type(initial) is dict
        branch_completion_kwargs: dict[str, object] = {
            "expected_lane": "p0-initial",
            "launch_authorities": launch_authorities,
            "trusted_commit": trusted_commit,
        }
        if campaign is not None:
            branch_completion_kwargs["campaign"] = campaign
        branch_completion = _validate_completion_evidence(  # type: ignore[arg-type]
            paths,
            initial["completion"],
            **branch_completion_kwargs,
        )
        if (
            initial["launch"] != branch_completion["launch"]
            or initial["task_count"] != branch_completion["task_count"]
            or initial["ordered_tasks_sha256"] != branch_completion["ordered_tasks_sha256"]
            or initial["final_manifests"] != branch_completion["final_manifests"]
        ):
            raise OneCellRunnerAuthorizationError("branch initial-P0 evidence does not join completion", exit_code=76)
        if "initial_p0_completion" in completions and evidence["initial_p0_completion"] != initial["completion"]:
            raise OneCellRunnerAuthorizationError("admission and branch initial-P0 completion differ", exit_code=76)
    if evidence["b2_precision_audit"] is not None:
        _validate_precision_evidence(
            paths,
            evidence["b2_precision_audit"],
            launch_authorities=launch_authorities,
            trusted_commit=trusted_commit,
        )
    if evidence["b2_resource_admission"] is not None:
        _validate_resource_evidence(
            paths,
            evidence["b2_resource_admission"],
            expected_scope="b2",
            launch_authorities=launch_authorities,
            trusted_commit=trusted_commit,
        )
    if evidence["clean_resource_admission"] is not None:
        _validate_resource_evidence(
            paths,
            evidence["clean_resource_admission"],
            expected_scope="clean",
            launch_authorities=launch_authorities,
            trusted_commit=trusted_commit,
        )
    controlling_branch = configured_branch if configured_branch is not None else evidence_branch
    if evidence_branch is not None and campaign is not None:
        _validate_branch_campaign_join(evidence_branch, campaign=campaign)
    confirmation_completion = completions.get("confirmation_completion")
    if confirmation_completion is not None and confirmation_completion["_launch_branch"] != evidence["branch_decision"]:
        raise OneCellRunnerAuthorizationError(
            "confirmation completion launch does not bind the controlling branch",
            exit_code=76,
        )
    if str(lane["lane_id"]) in {"b1", "p1-no-l-star", "p1-l-star-64", "p1-l-star-256", "p1-l-star-1024"}:
        if controlling_branch is None:
            raise OneCellRunnerAuthorizationError("P1/B1 admission lacks its evidence branch", exit_code=76)
        confirmation_required = controlling_branch["rule"]["confirmation_required"] is True
        if (evidence["confirmation_completion"] is not None) is not confirmation_required:
            raise OneCellRunnerAuthorizationError("confirmation evidence differs from branch rule", exit_code=76)


def _validate_branch_campaign_join(
    branch: dict[str, object] | None,
    *,
    campaign: OneCellCampaignAuthority,
) -> None:
    if branch is None:
        return
    selection = branch["selection"]
    rule = branch["rule"]
    assert type(selection) is dict and type(rule) is dict
    branch_id = str(selection["branch_id"])
    task_map_id = str(selection["p1_task_map_id"])
    task_map = next((item for item in campaign.task_maps if item.task_map_id == task_map_id), None)
    horizon = next((item for item in campaign.horizon_branches if item.branch_id == branch_id), None)
    if (
        task_map is None
        or horizon is None
        or task_map.sha256 != selection["p1_task_map_sha256"]
        or horizon.p1_task_map_id != task_map_id
        or horizon.profile != rule["profile"]
        or horizon.l_star != rule["l_star"]
        or horizon.confirmation_required is not rule["confirmation_required"]
    ):
        raise OneCellRunnerAuthorizationError(
            "branch decision differs from its frozen campaign branch/map", exit_code=76
        )


def _ordered_tasks_bytes_for_cli(*, launch: OneCellLaunchAuthority) -> bytes:
    """Reproduce byte-identical canonical ordered-task JSONL without writes."""

    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    lines = []
    for task in selected.ordered_tasks:
        lines.append(
            _canonical_json(
                {
                    "profile": _LAUNCH_TASK_PROFILE,
                    "array_position": task.array_position,
                    "wave": task.wave,
                    "role": task.role,
                    "task_map_id": task.task_map_id,
                    "scientific_index": task.task_index,
                    "scientific_identity_hex": task.scientific_identity_bytes.hex(),
                    "scientific_identity_sha256": task.scientific_identity_sha256,
                    "scientific_identity_size_bytes": len(task.scientific_identity_bytes),
                    "relative_task_directory": task.relative_task_directory,
                }
            )
        )
    payload = b"".join(lines)
    if _sha256(payload) != selected.ordered_tasks_sha256:
        raise OneCellRunnerAuthorizationError("ordered-task reconstruction digest changed", exit_code=76)
    return payload


def _decode_hex_bytes(value: object, *, label: str, maximum: int) -> bytes:
    text = _require_exact_str(value, label=label, maximum=2 * maximum)
    if len(text) % 2 or re.fullmatch(r"[0-9a-f]+", text) is None:
        raise OneCellRunnerValidationError(f"{label} is not lowercase even-length hex")
    payload = bytes.fromhex(text)
    if not payload or len(payload) > maximum:
        raise OneCellRunnerValidationError(f"{label} decoded size is invalid")
    return payload


def _decode_captured_hex(value: object, *, overflow: bool, label: str) -> bytes:
    text = value
    if type(text) is not str or len(text) % 2 or re.fullmatch(r"[0-9a-f]*", text) is None:
        raise OneCellRunnerValidationError(f"{label} is not lowercase even-length hexadecimal")
    payload = bytes.fromhex(text)
    if len(payload) > _MAX_CAPTURE or overflow and len(payload) != _MAX_CAPTURE:
        raise OneCellRunnerValidationError(f"{label} does not match its capture/overflow bound")
    return payload


def _resources_from_wires(launch: dict[str, object], deployment: dict[str, object]) -> OneCellSlurmResourceEnvelope:
    resources = launch["resources"]
    assert type(resources) is dict
    parsed_tools = launch["_parsed_tools"]
    deployment_tools = deployment.get("_parsed_tools")
    assert type(parsed_tools) is dict and type(deployment_tools) is dict
    if parsed_tools != deployment_tools:
        raise OneCellRunnerAuthorizationError("deployment and launch tool identities differ", exit_code=76)
    scheduler = _parse_string_map(
        resources["scheduler_environment"], keys=("LANG", "LC_ALL"), label="launch.resources.scheduler_environment"
    )
    if scheduler != _SCHEDULER_ENVIRONMENT:
        raise OneCellRunnerValidationError("launch scheduler environment is not frozen")
    scientific = _parse_string_map(
        resources["scientific_environment"], keys=_SCIENTIFIC_ENV_KEYS, label="launch.resources.scientific_environment"
    )
    sbatch = parsed_tools["sbatch"]
    scontrol = parsed_tools["scontrol"]
    assert type(sbatch) is dict and type(scontrol) is dict
    if resources["sbatch_executable"] != sbatch["path"] or resources["scontrol_executable"] != scontrol["path"]:
        raise OneCellRunnerAuthorizationError("resource executables differ from tool identities", exit_code=76)
    return OneCellSlurmResourceEnvelope(
        profile=_require_exact_str(resources["profile"], label="resources.profile", maximum=128),
        partition=_require_exact_str(resources["partition"], label="resources.partition", maximum=128),
        wall_minutes=_require_exact_int(
            resources["wall_minutes"], label="resources.wall_minutes", minimum=17, maximum=28_800
        ),
        cpus_per_task=_require_exact_int(
            resources["cpus_per_task"], label="resources.cpus_per_task", minimum=1, maximum=128
        ),
        memory_mib=_require_exact_int(
            resources["memory_mib"], label="resources.memory_mib", minimum=1, maximum=786_432
        ),
        array_concurrency=_require_exact_int(
            resources["array_concurrency"], label="resources.array_concurrency", minimum=1, maximum=_MAX_TASKS
        ),
        signal_name=_require_exact_str(resources["signal_name"], label="resources.signal_name", maximum=128),
        signal_warning_seconds=_require_exact_int(
            resources["signal_warning_seconds"], label="resources.signal_warning_seconds", maximum=86_400
        ),
        receipt_handshake_seconds=_require_exact_int(
            resources["receipt_handshake_seconds"], label="resources.receipt_handshake_seconds", maximum=300
        ),
        scheduler_timeout_seconds=_require_exact_int(
            resources["scheduler_timeout_seconds"], label="resources.scheduler_timeout_seconds", maximum=300
        ),
        max_requeues_per_task=_require_exact_int(
            resources["max_requeues_per_task"], label="resources.max_requeues_per_task", maximum=16
        ),
        sbatch_executable=str(sbatch["path"]),
        sbatch_executable_realpath=str(sbatch["realpath"]),
        sbatch_owner_uid=int(sbatch["owner_uid"]),
        sbatch_mode=int(sbatch["mode"]),
        sbatch_size_bytes=int(sbatch["size_bytes"]),
        sbatch_sha256=str(sbatch["sha256"]),
        sbatch_version=str(sbatch["version"]),
        scontrol_executable=str(scontrol["path"]),
        scontrol_executable_realpath=str(scontrol["realpath"]),
        scontrol_owner_uid=int(scontrol["owner_uid"]),
        scontrol_mode=int(scontrol["mode"]),
        scontrol_size_bytes=int(scontrol["size_bytes"]),
        scontrol_sha256=str(scontrol["sha256"]),
        scontrol_version=str(scontrol["version"]),
        scheduler_environment=scheduler,
        scientific_environment=scientific,
    )


def _require_pairwise_isolated_roots(roots: tuple[tuple[str, str], ...]) -> None:
    normalized: list[tuple[str, str]] = []
    for label, path in roots:
        normalized.append((label, _require_abs_path(path, label=label)))
    for left_index, (left_label, left) in enumerate(normalized):
        for right_label, right in normalized[left_index + 1 :]:
            try:
                shared = os.path.commonpath((left, right))
            except ValueError as error:
                raise OneCellRunnerAuthorizationError(
                    f"{left_label} and {right_label} do not share a valid path domain",
                    exit_code=76,
                ) from error
            if shared in {left, right}:
                raise OneCellRunnerAuthorizationError(
                    f"{left_label} and {right_label} are not isolated",
                    exit_code=76,
                )


def _paths_from_wires(
    launch: dict[str, object],
    deployment: dict[str, object],
    *,
    authorization_path: str,
    runtime_python_bytes: bytes,
) -> OneCellRunnerPaths:
    paths = launch["paths"]
    runtime = launch["runtime_python"]
    parsed_tools = launch["_parsed_tools"]
    deployment_paths = deployment["paths"]
    deployment_runtime = deployment["runtime_python"]
    deployment_tools = deployment["_parsed_tools"]
    repository = deployment["coordinator_repository"]
    if not all(
        type(value) is dict
        for value in (paths, runtime, parsed_tools, deployment_paths, deployment_runtime, deployment_tools, repository)
    ):
        raise OneCellRunnerValidationError("launch/deployment path inputs are not parsed authority objects")
    git = parsed_tools["git"]
    assert type(git) is dict
    runtime_hex = _decode_hex_bytes(
        runtime["sidecar_bytes_hex"], label="launch.runtime_python.sidecar_bytes_hex", maximum=4096
    )
    deployment_runtime_hex = _decode_hex_bytes(
        deployment_runtime["sidecar_bytes_hex"], label="deployment.runtime_python.sidecar_bytes_hex", maximum=4096
    )
    if runtime_hex != deployment_runtime_hex or runtime_hex != runtime_python_bytes:
        raise OneCellRunnerAuthorizationError("runtime sidecar bytes differ across authority and disk", exit_code=76)
    for key in (
        "sidecar_sha256",
        "sidecar_size_bytes",
        "executable_path",
        "executable_realpath",
        "executable_sha256",
        "executable_size_bytes",
    ):
        if runtime[key] != deployment_runtime[key]:
            raise OneCellRunnerAuthorizationError(
                "runtime Python identities differ across deployment and launch", exit_code=76
            )
    if (
        runtime["sidecar_path"] != paths["runtime_python_file"]
        or runtime["executable_path"] != paths["python_executable"]
        or deployment_runtime["executable_path"] != deployment_paths["python_executable"]
    ):
        raise OneCellRunnerAuthorizationError("runtime Python paths differ from path authorities", exit_code=76)
    environment_root = str(deployment_paths["environment_root"])
    python_path = str(deployment_paths["python_executable"])
    if os.path.commonpath((environment_root, python_path)) != environment_root or python_path == environment_root:
        raise OneCellRunnerAuthorizationError("runtime Python is outside the certified environment root", exit_code=76)
    if parsed_tools != deployment_tools:
        raise OneCellRunnerAuthorizationError("deployment and launch tool identities differ", exit_code=76)
    for name, path_key in (
        ("sbatch", "sbatch_executable"),
        ("scontrol", "scontrol_executable"),
        ("git", "git_executable"),
    ):
        tool = deployment_tools[name]
        assert type(tool) is dict
        if deployment_paths[path_key] != tool["path"]:
            raise OneCellRunnerAuthorizationError(f"deployment {name} path differs from tool identity", exit_code=76)
    _require_pairwise_isolated_roots(
        (
            ("Article checkout", str(deployment_paths["article_checkout"])),
            ("software checkout", str(deployment_paths["software_checkout"])),
            ("coordinator checkout", str(deployment_paths["coordinator_checkout"])),
            ("campaign mutable root", str(deployment_paths["campaign_root"])),
            ("authorization readback root", str(repository["authorization_readback_root"])),
            ("runtime environment root", environment_root),
            ("deployed batch root", os.path.dirname(str(deployment_paths["batch_script"]))),
        )
    )
    if paths["git_executable"] != git["path"]:
        raise OneCellRunnerAuthorizationError("launch Git path differs from tool identity", exit_code=76)
    if (
        runtime["sidecar_sha256"] != _sha256(runtime_hex)
        or runtime["sidecar_size_bytes"] != len(runtime_hex)
        or type(runtime["sidecar_size_bytes"]) is not int
    ):
        raise OneCellRunnerValidationError("runtime sidecar size or digest is invalid")
    if paths["authorization_directory"] != authorization_path:
        raise OneCellRunnerAuthorizationError("authorization directory differs from caller path", exit_code=76)
    if paths["authorization_checkout"] != deployment_paths["coordinator_checkout"]:
        raise OneCellRunnerAuthorizationError(
            "authorization checkout differs from the deployment coordinator checkout",
            exit_code=76,
        )
    checkout = str(paths["authorization_checkout"])
    authorization_directory = str(paths["authorization_directory"])
    try:
        shared = os.path.commonpath((checkout, authorization_directory))
    except ValueError as error:
        raise OneCellRunnerAuthorizationError(
            "authorization paths do not share a valid filesystem root", exit_code=76
        ) from error
    if shared in {checkout, authorization_directory}:
        raise OneCellRunnerAuthorizationError(
            "authorization runtime directory must be separate from the Git checkout",
            exit_code=76,
        )
    readback_root = str(repository["authorization_readback_root"])
    if os.path.commonpath((readback_root, authorization_directory)) != readback_root:
        raise OneCellRunnerAuthorizationError(
            "authorization directory is outside the certified readback root",
            exit_code=76,
        )
    duplicate_paths = {
        "campaign_root": "campaign_root",
        "python_executable": "python_executable",
        "task_root": "private_task_root",
        "attempt_root": "attempt_root",
        "log_root": "log_root",
        "cache_root": "cache_root",
        "temporary_root": "temporary_root",
        "submission_ledger_root": "submission_ledger_root",
        "submission_ledger_lock": "submission_ledger_lock",
        "authorized_run_directory": "authorized_run_directory",
        "batch_script": "batch_script",
        "git_executable": "git_executable",
    }
    for launch_key, deployment_key in duplicate_paths.items():
        if paths[launch_key] != deployment_paths[deployment_key]:
            raise OneCellRunnerAuthorizationError(
                f"path {launch_key} differs across deployment and launch", exit_code=76
            )
    if (
        repository["remote_url"] != paths["coordinator_remote_url"]
        or repository["fetch_refspec"] != paths["coordinator_fetch_refspec"]
    ):
        raise OneCellRunnerAuthorizationError("coordinator repository identity differs across records", exit_code=76)
    return OneCellRunnerPaths(
        campaign_root=str(paths["campaign_root"]),
        authorization_checkout=str(paths["authorization_checkout"]),
        authorization_directory=str(paths["authorization_directory"]),
        runtime_python_file=str(paths["runtime_python_file"]),
        runtime_python_bytes=runtime_hex,
        runtime_python_sha256=str(runtime["sidecar_sha256"]),
        python_executable=str(runtime["executable_path"]),
        python_executable_realpath=str(runtime["executable_realpath"]),
        python_executable_sha256=str(runtime["executable_sha256"]),
        python_executable_size_bytes=_require_exact_int(
            runtime["executable_size_bytes"], label="runtime executable size", minimum=1, maximum=_MAX_TOOL_BYTES
        ),
        task_root=str(paths["task_root"]),
        attempt_root=str(paths["attempt_root"]),
        log_root=str(paths["log_root"]),
        cache_root=str(paths["cache_root"]),
        temporary_root=str(paths["temporary_root"]),
        submission_ledger_root=str(paths["submission_ledger_root"]),
        submission_ledger_lock=str(paths["submission_ledger_lock"]),
        authorized_run_directory=str(paths["authorized_run_directory"]),
        batch_script=str(paths["batch_script"]),
        stdout_template=str(paths["stdout_template"]),
        stderr_template=str(paths["stderr_template"]),
        git_executable=str(git["path"]),
        git_executable_realpath=str(git["realpath"]),
        git_owner_uid=int(git["owner_uid"]),
        git_mode=int(git["mode"]),
        git_size_bytes=int(git["size_bytes"]),
        git_sha256=str(git["sha256"]),
        git_version=str(git["version"]),
        coordinator_remote_url=str(paths["coordinator_remote_url"]),
        coordinator_fetch_refspec=str(paths["coordinator_fetch_refspec"]),
    )


def _validate_bootstrap_git_trust(paths: OneCellRunnerPaths, deployment: dict[str, object]) -> None:
    ownership = deployment["ownership"]
    tools = deployment["_parsed_tools"]
    assert type(ownership) is dict and type(tools) is dict and type(tools["git"]) is dict
    campaign_uid = int(ownership["campaign_uid"])
    administrators = tuple(int(value) for value in ownership["trusted_administrator_uids"])
    git_identity = tools["git"]
    git_owner = int(git_identity["owner_uid"])
    if campaign_uid != os.geteuid():
        raise OneCellRunnerAuthorizationError("deployment campaign UID is not the current user", exit_code=77)
    if git_owner == os.geteuid() or git_owner not in administrators:
        raise OneCellRunnerAuthorizationError(
            "bootstrap Git must be owned by a non-current trusted administrator",
            exit_code=77,
        )
    if git_identity["path"] != paths.git_executable or git_identity["realpath"] != paths.git_executable_realpath:
        raise OneCellRunnerAuthorizationError("bootstrap Git path differs from deployment identity", exit_code=76)
    mode = int(git_identity["mode"])
    if mode & 0o022 or not mode & 0o111:
        raise OneCellRunnerAuthorizationError("bootstrap Git is writable or nonexecutable", exit_code=77)
    _validate_bound_tool_file(
        label="bootstrap Git executable",
        path=paths.git_executable,
        owner_uid=git_owner,
        mode=mode,
        size_bytes=int(git_identity["size_bytes"]),
        digest=str(git_identity["sha256"]),
    )


def _validate_pushed_detached_checkout(
    paths: OneCellRunnerPaths,
    *,
    checkout: str,
    commit: str,
    label: str,
    allow_origin_descendant: bool = False,
) -> None:
    _require_exact_bool(allow_origin_descendant, label="allow_origin_descendant")
    selected_checkout = _require_abs_path(checkout, label=label)
    _require_hex(commit, label=f"{label} commit", width=40)
    top = _git_command(
        paths,
        ("rev-parse", "--path-format=absolute", "--show-toplevel"),
        maximum=4096,
        checkout=selected_checkout,
    ).stdout
    if top != os.fsencode(selected_checkout) + b"\n":
        raise OneCellRunnerAuthorizationError(f"{label} top level differs from deployment", exit_code=76)
    expected = commit.encode("ascii") + b"\n"
    head = _git_command(
        paths,
        ("rev-parse", "--verify", "HEAD"),
        maximum=64,
        checkout=selected_checkout,
    ).stdout
    origin = _git_command(
        paths,
        ("rev-parse", "--verify", "refs/remotes/origin/main"),
        maximum=64,
        checkout=selected_checkout,
    ).stdout
    if head != expected:
        raise OneCellRunnerAuthorizationError(f"{label} HEAD differs from its frozen commit", exit_code=76)
    if allow_origin_descendant:
        if re.fullmatch(rb"[0-9a-f]{40}\n", origin) is None:
            raise OneCellRunnerAuthorizationError(f"{label} origin/main is malformed", exit_code=76)
        ancestry = _git_command(
            paths,
            ("merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"),
            maximum=1,
            accepted_returncodes=(0, 1),
            checkout=selected_checkout,
        )
        if ancestry.returncode != 0 or ancestry.stdout:
            raise OneCellRunnerAuthorizationError(f"{label} frozen commit is not pushed", exit_code=76)
    elif origin != expected:
        raise OneCellRunnerAuthorizationError(f"{label} origin/main differs from frozen SOURCE", exit_code=76)
    symbolic = _git_command(
        paths,
        ("symbolic-ref", "-q", "HEAD"),
        maximum=256,
        accepted_returncodes=(1,),
        checkout=selected_checkout,
    ).stdout
    if symbolic:
        raise OneCellRunnerAuthorizationError(f"{label} is not detached", exit_code=76)
    status_result = _git_command(
        paths,
        ("status", "--porcelain=v1", "--untracked-files=all"),
        maximum=1 << 20,
        checkout=selected_checkout,
    )
    if status_result.stdout:
        raise OneCellRunnerAuthorizationError(f"{label} is not clean", exit_code=76)


def _validate_software_checkout_and_batch(
    paths: OneCellRunnerPaths,
    *,
    deployment: dict[str, object],
    deployment_lock: dict[str, object],
    launch: dict[str, object],
) -> bytes:
    deployment_paths = deployment["paths"]
    deployment_batch = deployment["batch_script"]
    lock_batch = deployment_lock["batch_script"]
    launch_batch = launch["batch_script"]
    lock_source = deployment_lock["source"]
    assert all(
        type(value) is dict for value in (deployment_paths, deployment_batch, lock_batch, launch_batch, lock_source)
    )
    source_commit = str(deployment["source_commit"])
    if (
        deployment_batch != lock_batch
        or deployment_batch != launch_batch
        or deployment_batch["source_commit"] != source_commit
        or lock_source["commit"] != source_commit
        or deployment_batch["path"] != "scripts/easley/run_pre_one_cell.sbatch"
    ):
        raise OneCellRunnerAuthorizationError("batch source authority does not join SOURCE exactly", exit_code=76)
    software_checkout = _require_abs_path(deployment_paths["software_checkout"], label="software checkout")
    _validate_pushed_detached_checkout(
        paths,
        checkout=software_checkout,
        commit=source_commit,
        label="software checkout",
    )
    _require_git_ancestor(
        paths,
        prerequisite=_SLICE_8B_SOFTWARE_PARENT,
        trusted_commit=source_commit,
        checkout=software_checkout,
    )
    member_path = str(deployment_batch["path"])
    tree = _git_command(
        paths,
        ("ls-tree", "-z", source_commit, "--", member_path),
        maximum=1024,
        checkout=software_checkout,
    ).stdout
    expected_suffix = b"\t" + member_path.encode("utf-8") + b"\x00"
    if not tree.endswith(expected_suffix):
        raise OneCellRunnerAuthorizationError("batch source path is absent or ambiguous", exit_code=76)
    fields = tree[: -len(expected_suffix)].split(b" ")
    if (
        len(fields) != 3
        or fields[0] not in {b"100644", b"100755"}
        or fields[1] != b"blob"
        or fields[2].decode("ascii", "strict") != deployment_batch["git_blob"]
    ):
        raise OneCellRunnerAuthorizationError("batch source Git blob identity differs", exit_code=76)
    blob = _git_command(
        paths,
        ("cat-file", "blob", f"{source_commit}:{member_path}"),
        maximum=_MAX_JSON,
        checkout=software_checkout,
    ).stdout
    if len(blob) != deployment_batch["size_bytes"] or _sha256(blob) != deployment_batch["sha256"]:
        raise OneCellRunnerAuthorizationError("batch source bytes differ from deployment", exit_code=76)
    live = _read_bound_runtime_file(
        paths.batch_script,
        label="deployed batch script",
        maximum=_MAX_JSON,
        expected_uid=os.geteuid(),
        require_single_link=True,
        forbid_group_world_write=True,
    )
    if live != blob:
        raise OneCellRunnerAuthorizationError("deployed batch script differs from SOURCE blob", exit_code=78)
    return blob


def _validate_protocol_checkout_and_campaign(
    paths: OneCellRunnerPaths,
    *,
    deployment: dict[str, object],
    deployment_lock: dict[str, object],
    campaign: OneCellCampaignAuthority,
) -> None:
    protocol = deployment["protocol"]
    lock_protocol = deployment_lock["protocol"]
    deployment_paths = deployment["paths"]
    assert type(protocol) is dict and type(lock_protocol) is dict and type(deployment_paths) is dict
    if protocol != lock_protocol:
        raise OneCellRunnerAuthorizationError("deployment protocol records differ", exit_code=76)
    campaign_protocol = {
        "blob": campaign.protocol_blob,
        "commit": campaign.protocol_commit,
        "path": campaign.protocol_path,
        "sha256": campaign.protocol_sha256,
        "size_bytes": campaign.protocol_size_bytes,
    }
    if protocol != campaign_protocol:
        raise OneCellRunnerAuthorizationError("campaign protocol identity differs from deployment", exit_code=76)
    article_checkout = _require_abs_path(deployment_paths["article_checkout"], label="Article checkout")
    commit = str(protocol["commit"])
    member_path = str(protocol["path"])
    blob = str(protocol["blob"])
    _validate_pushed_detached_checkout(
        paths,
        checkout=article_checkout,
        commit=commit,
        label="Article checkout",
        allow_origin_descendant=True,
    )
    tree = _git_command(
        paths,
        ("ls-tree", "-z", commit, "--", member_path),
        maximum=1024,
        checkout=article_checkout,
    ).stdout
    expected_tree = f"100644 blob {blob}\t{member_path}".encode("utf-8") + b"\x00"
    if tree != expected_tree:
        raise OneCellRunnerAuthorizationError("Article protocol tree/blob identity differs", exit_code=76)
    protocol_bytes = _git_command(
        paths,
        ("cat-file", "blob", f"{commit}:{member_path}"),
        maximum=_MAX_JSON,
        checkout=article_checkout,
    ).stdout
    if len(protocol_bytes) != protocol["size_bytes"] or _sha256(protocol_bytes) != protocol["sha256"]:
        raise OneCellRunnerAuthorizationError("Article protocol bytes differ from deployment", exit_code=76)


def _validate_git_checkout(paths: OneCellRunnerPaths, readback: dict[str, object], launch: dict[str, object]) -> None:
    observation = readback["observation"]
    repository = readback["repository"]
    assert type(observation) is dict and type(repository) is dict
    if observation["checkout_root"] != paths.authorization_checkout:
        raise OneCellRunnerAuthorizationError("readback checkout root differs from launch", exit_code=76)
    if (
        repository["remote_url"] != paths.coordinator_remote_url
        or repository["fetch_refspec"] != paths.coordinator_fetch_refspec
    ):
        raise OneCellRunnerAuthorizationError("readback repository differs from launch", exit_code=76)
    local_result = _git_command(
        paths,
        ("config", "--local", "--null", "--list", "--show-origin", "--no-includes"),
        maximum=16 << 10,
    )
    segments = local_result.stdout.split(b"\x00")
    if not segments or segments[-1] != b"" or (len(segments) - 1) % 2:
        raise OneCellRunnerAuthorizationError("Git local configuration output is malformed", exit_code=76)
    configured = launch["git_local_config"]
    assert type(configured) is dict
    expected_configuration = {
        "core.repositoryformatversion": configured["core_repositoryformatversion"],
        "core.filemode": configured["core_filemode"],
        "core.bare": configured["core_bare"],
        "core.logallrefupdates": configured["core_logallrefupdates"],
        "remote.origin.url": configured["remote_origin_url"],
        "remote.origin.fetch": configured["remote_origin_fetch"],
        "branch.main.remote": configured["branch_main_remote"],
        "branch.main.merge": configured["branch_main_merge"],
    }
    observed_configuration: dict[str, str] = {}
    for index in range(0, len(segments) - 1, 2):
        if segments[index] != b"file:.git/config":
            raise OneCellRunnerAuthorizationError(
                "Git local configuration has an untrusted origin",
                exit_code=76,
            )
        try:
            key_bytes, value_bytes = segments[index + 1].split(b"\n", 1)
            key = key_bytes.decode("ascii", "strict")
            value = value_bytes.decode("utf-8", "strict")
        except (ValueError, UnicodeError) as error:
            raise OneCellRunnerAuthorizationError(
                "Git local configuration entry is malformed",
                exit_code=76,
            ) from error
        if key in observed_configuration:
            raise OneCellRunnerAuthorizationError(
                "Git local configuration has a duplicate entry",
                exit_code=76,
            )
        observed_configuration[key] = value
    if observed_configuration != expected_configuration:
        raise OneCellRunnerAuthorizationError(
            "Git local configuration inventory is not frozen",
            exit_code=76,
        )
    head = _git_command(paths, ("rev-parse", "--verify", "HEAD"), maximum=64).stdout
    origin = _git_command(paths, ("rev-parse", "--verify", "refs/remotes/origin/main"), maximum=64).stdout
    expected = (str(observation["head_commit"]) + "\n").encode("ascii")
    if head != expected or origin != expected:
        raise OneCellRunnerAuthorizationError("live HEAD/origin do not equal readback authority", exit_code=76)
    top = _git_command(paths, ("rev-parse", "--path-format=absolute", "--show-toplevel"), maximum=4096).stdout
    if top != os.fsencode(paths.authorization_checkout) + b"\n":
        raise OneCellRunnerAuthorizationError("Git top-level path differs from authority", exit_code=76)
    symbolic = _git_command(paths, ("symbolic-ref", "-q", "HEAD"), maximum=256, accepted_returncodes=(1,)).stdout
    if symbolic:
        raise OneCellRunnerAuthorizationError("authorization checkout is not detached", exit_code=76)
    status_result = _git_command(paths, ("status", "--porcelain=v1", "--untracked-files=all"), maximum=1 << 20)
    if status_result.stdout:
        raise OneCellRunnerAuthorizationError("authorization checkout is not clean", exit_code=76)
    remote = _git_command(paths, ("remote", "get-url", "--all", "origin"), maximum=4096).stdout
    if remote != paths.coordinator_remote_url.encode("utf-8") + b"\n":
        raise OneCellRunnerAuthorizationError("live origin URL differs from authority", exit_code=76)
    fetch = _git_command(paths, ("config", "--get-all", "remote.origin.fetch"), maximum=4096).stdout
    if fetch != paths.coordinator_fetch_refspec.encode("utf-8") + b"\n":
        raise OneCellRunnerAuthorizationError("live fetch refspec differs from authority", exit_code=76)


def _validate_authority_joins(
    *,
    launch: dict[str, object],
    deployment_lock: dict[str, object],
    deployment: dict[str, object],
    admission: dict[str, object],
    branch: dict[str, object] | None,
) -> None:
    launch_profile = launch.get("profile")
    admission_profile = admission.get("profile")
    if (
        launch_profile == _LAUNCH_PROFILE
        and admission_profile != _ADMISSION_PROFILE
        or launch_profile == _LAUNCH_FIXTURE_PROFILE
        and admission_profile != _ADMISSION_FIXTURE_PROFILE
        or launch_profile not in {_LAUNCH_PROFILE, _LAUNCH_FIXTURE_PROFILE}
    ):
        raise OneCellRunnerAuthorizationError(
            "launch and admission production/fixture profiles cannot be composed",
            exit_code=76,
        )
    launch_fixture = launch.get("_fixture")
    admission_fixture = admission.get("_fixture")
    if launch_profile == _LAUNCH_PROFILE:
        if launch_fixture is not None or admission_fixture is not None:
            raise OneCellRunnerAuthorizationError("production authority contains fixture metadata", exit_code=76)
    elif (
        type(launch_fixture) is not dict
        or type(admission_fixture) is not dict
        or launch_fixture != admission_fixture
        or launch_fixture
        != {
            "fixture_id": "slice-8b-authority-parser-nonexecuting",
            "scientific_execution_permitted": False,
        }
    ):
        raise OneCellRunnerAuthorizationError("fixture launch/admission metadata do not pair exactly", exit_code=76)
    authorities = launch["authorities"]
    admission_authorities = admission["authorities"]
    assert type(authorities) is dict and type(admission_authorities) is dict
    protocol = deployment_lock["protocol"]
    source = deployment_lock["source"]
    wheel = deployment_lock["wheel"]
    campaign = deployment_lock["campaign"]
    deployment_protocol = deployment["protocol"]
    deployment_campaign = deployment["campaign"]
    deployment_wheel = deployment["wheel"]
    assert all(
        type(item) is dict
        for item in (protocol, source, wheel, campaign, deployment_protocol, deployment_campaign, deployment_wheel)
    )
    joins = (
        (authorities["protocol_commit"], protocol["commit"]),
        (authorities["protocol_commit"], deployment_protocol["commit"]),
        (authorities["protocol_commit"], admission_authorities["protocol_commit"]),
        (authorities["protocol_sha256"], protocol["sha256"]),
        (authorities["protocol_sha256"], deployment_protocol["sha256"]),
        (authorities["protocol_sha256"], admission_authorities["protocol_sha256"]),
        (authorities["source_commit"], source["commit"]),
        (authorities["source_commit"], deployment["source_commit"]),
        (authorities["source_commit"], admission_authorities["source_commit"]),
        (authorities["wheel_sha256"], wheel["sha256"]),
        (authorities["wheel_sha256"], admission_authorities["wheel_sha256"]),
        (authorities["campaign_commit"], deployment_campaign["commit"]),
        (authorities["campaign_commit"], admission_authorities["campaign_commit"]),
        (authorities["campaign_manifest_sha256"], campaign["authority_manifest_sha256"]),
        (authorities["configuration_sha256"], campaign["configuration_sha256"]),
        (authorities["configuration_sha256"], admission_authorities["configuration_sha256"]),
    )
    if any(left != right for left, right in joins):
        raise OneCellRunnerAuthorizationError("authority identities do not join byte for byte", exit_code=76)
    configuration_ref = deployment_campaign["configuration"]
    manifest_ref = deployment_campaign["manifest"]
    deployment_lock_ref = deployment_campaign["deployment_lock"]
    assert type(configuration_ref) is dict and type(manifest_ref) is dict and type(deployment_lock_ref) is dict
    if (
        protocol != deployment_protocol
        or source["commit"] != deployment["source_commit"]
        or wheel["member_path"] != deployment_wheel["path"]
        or wheel["sha256"] != deployment_wheel["sha256"]
        or wheel["size_bytes"] != deployment_wheel["size_bytes"]
        or configuration_ref["commit"] != deployment_campaign["commit"]
        or manifest_ref["commit"] != deployment_campaign["commit"]
        or deployment_lock_ref["commit"] != deployment_campaign["commit"]
        or configuration_ref["sha256"] != campaign["configuration_sha256"]
        or manifest_ref["sha256"] != campaign["authority_manifest_sha256"]
        or deployment_campaign["deployment_lock"] != authorities["deployment_lock"]
        or admission_authorities["deployment_lock"] != authorities["deployment_lock"]
        or admission_authorities["deployment"] != authorities["deployment"]
        or configuration_ref["sha256"] != authorities["configuration_sha256"]
        or manifest_ref["sha256"] != authorities["campaign_manifest_sha256"]
        or deployment_wheel["sha256"] != authorities["wheel_sha256"]
        or deployment_lock["environment"] != deployment["environment"]
    ):
        raise OneCellRunnerAuthorizationError("referenced authority records do not join byte for byte", exit_code=76)
    if (
        launch["batch_script"] != deployment_lock["batch_script"]
        or launch["batch_script"] != deployment["batch_script"]
    ):
        raise OneCellRunnerAuthorizationError("batch-script identities differ across authorities", exit_code=76)
    if (
        launch["git_environment"] != deployment["git_environment"]
        or launch["git_local_config"] != deployment["git_local_config"]
    ):
        raise OneCellRunnerAuthorizationError("Git authority differs across deployment and launch", exit_code=76)
    if launch["lane"] != admission["lane"]["lane_id"]:
        raise OneCellRunnerAuthorizationError("launch lane differs from admission lane", exit_code=76)
    branch_ref = authorities["branch"]
    admission_branch_ref = admission_authorities["branch"]
    if branch_ref != admission_branch_ref or (branch is None) is not (branch_ref is None):
        raise OneCellRunnerAuthorizationError("branch references differ across authorities", exit_code=76)
    if branch is not None:
        common = branch["authorities"]
        assert type(common) is dict
        if any(
            common[key] != authorities[launch_key]
            for key, launch_key in (
                ("protocol_commit", "protocol_commit"),
                ("protocol_sha256", "protocol_sha256"),
                ("source_commit", "source_commit"),
                ("wheel_sha256", "wheel_sha256"),
                ("campaign_commit", "campaign_commit"),
            )
        ):
            raise OneCellRunnerAuthorizationError("branch authorities do not join launch", exit_code=76)
        if common["deployment"] != authorities["deployment"]:
            raise OneCellRunnerAuthorizationError("branch deployment reference differs from launch", exit_code=76)
        branch_id = branch["selection"]["branch_id"]
        if launch["lane"] not in {"p0-confirmation", branch_id}:
            raise OneCellRunnerAuthorizationError("branch selection does not authorize launch lane", exit_code=76)
        confirmation = admission["evidence"]["confirmation_completion"]
        required = branch["rule"]["confirmation_required"] is True and launch["lane"] != "p0-confirmation"
        if (confirmation is not None) is not required:
            raise OneCellRunnerAuthorizationError(
                "confirmation completion presence differs from branch rule", exit_code=76
            )


def _validate_authority_locations(
    launch: dict[str, object],
    *,
    launch_reference: dict[str, object],
    branch: dict[str, object] | None,
) -> None:
    authorities = launch["authorities"]
    ordered = launch["ordered_tasks"]
    assert type(authorities) is dict and type(ordered) is dict
    lane = str(launch["lane"])
    launch_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/launches/{re.escape(lane)}-[0-9]{{4}}/launch\.json\Z"
    )
    launch_path = str(launch_reference["path"])
    if launch_pattern.fullmatch(launch_path) is None or launch["self_path"] != launch_path:
        raise OneCellRunnerAuthorizationError("launch does not occupy its exact authority location", exit_code=76)
    launch_directory = os.path.dirname(launch_path)
    if ordered["path"] != f"{launch_directory}/ordered-tasks.jsonl":
        raise OneCellRunnerAuthorizationError(
            "ordered tasks do not occupy the launch authority directory", exit_code=76
        )
    if authorities["deployment_lock"]["path"] != "campaigns/pre-one-cell-discovery-v1/deployment.lock.json":
        raise OneCellRunnerAuthorizationError("deployment lock path is not exact", exit_code=76)
    if authorities["deployment"]["path"] != "authorizations/pre-one-cell-discovery-v1/deployment/certificate.json":
        raise OneCellRunnerAuthorizationError("deployment certificate path is not exact", exit_code=76)
    admission_pattern = re.compile(
        rf"authorizations/pre-one-cell-discovery-v1/admissions/{re.escape(lane)}-[0-9]{{4}}/admission\.json\Z"
    )
    if admission_pattern.fullmatch(str(authorities["admission"]["path"])) is None:
        raise OneCellRunnerAuthorizationError("admission path is not exact for its lane", exit_code=76)
    branch_reference = authorities["branch"]
    if branch is None:
        if branch_reference is not None:
            raise OneCellRunnerAuthorizationError("branch path exists without branch bytes", exit_code=76)
    else:
        branch_id = str(branch["selection"]["branch_id"])
        expected = f"authorizations/pre-one-cell-discovery-v1/branches/{branch_id}/decision.json"
        if type(branch_reference) is not dict or branch_reference["path"] != expected:
            raise OneCellRunnerAuthorizationError("branch decision path is not exact", exit_code=76)


def _campaign_from_deployment(
    paths: OneCellRunnerPaths,
    deployment: dict[str, object],
    *,
    trusted_commit: str,
) -> OneCellCampaignAuthority:
    campaign = deployment["campaign"]
    assert type(campaign) is dict
    configuration_ref = _parse_file_ref(campaign["configuration"], label="deployment.campaign.configuration")
    configuration = _git_blob(
        paths,
        configuration_ref,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    _git_blob(
        paths,
        _parse_file_ref(campaign["manifest"], label="deployment.campaign.manifest"),
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    parsed_configuration = _parse_canonical_json(
        configuration,
        label="campaign configuration",
        integer_maximum=1 << 128,
    )
    if type(parsed_configuration) is not dict or type(parsed_configuration.get("task_maps")) is not list:
        raise OneCellRunnerValidationError("campaign configuration lacks task-map inventory")
    base = os.path.dirname(str(configuration_ref["path"]))
    members: list[tuple[str, bytes]] = []
    for index, raw in enumerate(parsed_configuration["task_maps"]):
        if type(raw) is not dict or type(raw.get("member_path")) is not str:
            raise OneCellRunnerValidationError("campaign task-map inventory is malformed")
        member_path = _require_safe_path(raw["member_path"], label=f"campaign task map {index}")
        repository_path = _require_safe_path(
            os.path.join(base, member_path) if base else member_path, label="campaign member repository path"
        )
        reference = {
            "commit": campaign["commit"],
            "path": repository_path,
            "sha256": raw.get("sha256"),
            "size_bytes": raw.get("size_bytes"),
        }
        member_bytes = _git_blob(
            paths,
            _parse_file_ref(reference, label=f"campaign task map {index}"),
            maximum=_MAX_JSONL,
            trusted_commit=trusted_commit,
        )
        members.append((member_path, member_bytes))
    try:
        return load_one_cell_campaign(configuration_bytes=configuration, task_map_members=tuple(members))
    except (OneCellCampaignValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerValidationError("campaign authority failed Slice 8A validation") from error


def _bootstrap_paths_from_launch(
    launch: dict[str, object],
    *,
    authorization_path: str,
    runtime_python_bytes: bytes,
) -> OneCellRunnerPaths:
    paths = launch["paths"]
    runtime = launch["runtime_python"]
    tools = launch["_parsed_tools"]
    assert type(paths) is dict and type(runtime) is dict and type(tools) is dict
    git = tools["git"]
    assert type(git) is dict
    sidecar = _decode_hex_bytes(
        runtime["sidecar_bytes_hex"], label="launch.runtime_python.sidecar_bytes_hex", maximum=4096
    )
    if sidecar != runtime_python_bytes:
        raise OneCellRunnerAuthorizationError("runtime sidecar differs from launch", exit_code=76)
    if (
        runtime["sidecar_sha256"] != _sha256(sidecar)
        or runtime["sidecar_size_bytes"] != len(sidecar)
        or type(runtime["sidecar_size_bytes"]) is not int
    ):
        raise OneCellRunnerValidationError("launch runtime sidecar identity is malformed")
    if paths["authorization_directory"] != authorization_path:
        raise OneCellRunnerAuthorizationError("caller authorization path differs from launch", exit_code=76)
    return OneCellRunnerPaths(
        campaign_root=str(paths["campaign_root"]),
        authorization_checkout=str(paths["authorization_checkout"]),
        authorization_directory=str(paths["authorization_directory"]),
        runtime_python_file=str(paths["runtime_python_file"]),
        runtime_python_bytes=sidecar,
        runtime_python_sha256=str(runtime["sidecar_sha256"]),
        python_executable=str(runtime["executable_path"]),
        python_executable_realpath=str(runtime["executable_realpath"]),
        python_executable_sha256=_require_hex(runtime["executable_sha256"], label="runtime executable digest"),
        python_executable_size_bytes=_require_exact_int(
            runtime["executable_size_bytes"], label="runtime executable size", minimum=1, maximum=_MAX_TOOL_BYTES
        ),
        task_root=str(paths["task_root"]),
        attempt_root=str(paths["attempt_root"]),
        log_root=str(paths["log_root"]),
        cache_root=str(paths["cache_root"]),
        temporary_root=str(paths["temporary_root"]),
        submission_ledger_root=str(paths["submission_ledger_root"]),
        submission_ledger_lock=str(paths["submission_ledger_lock"]),
        authorized_run_directory=str(paths["authorized_run_directory"]),
        batch_script=str(paths["batch_script"]),
        stdout_template=str(paths["stdout_template"]),
        stderr_template=str(paths["stderr_template"]),
        git_executable=str(git["path"]),
        git_executable_realpath=str(git["realpath"]),
        git_owner_uid=int(git["owner_uid"]),
        git_mode=int(git["mode"]),
        git_size_bytes=int(git["size_bytes"]),
        git_sha256=str(git["sha256"]),
        git_version=str(git["version"]),
        coordinator_remote_url=str(paths["coordinator_remote_url"]),
        coordinator_fetch_refspec=str(paths["coordinator_fetch_refspec"]),
    )


def _validate_runtime_files(
    launch: OneCellLaunchAuthority,
    deployment: dict[str, object],
    *,
    runtime_revalidation: bool = False,
) -> None:
    _require_exact_bool(runtime_revalidation, label="runtime_revalidation")
    paths = launch.paths
    ownership = deployment["ownership"]
    assert type(ownership) is dict
    campaign_uid = int(ownership["campaign_uid"])
    administrators = {int(value) for value in ownership["trusted_administrator_uids"]}
    if campaign_uid != os.geteuid():
        raise OneCellRunnerAuthorizationError("campaign UID is not the current user", exit_code=77)
    _validate_deployment_path_policy(launch.paths, deployment)
    try:
        _validate_exact_directory_members(
            launch.authorization_path,
            expected=frozenset({"launch.json", "ordered-tasks.jsonl", "readback.json", "runtime-python.path"}),
            label="authorization runtime directory",
        )
    except OneCellRunnerAuthorizationError as error:
        if runtime_revalidation and error.exit_code == 66:
            raise OneCellRunnerAuthorizationError(
                "bound authorization runtime member vanished",
                exit_code=78,
            ) from error
        raise
    current_authority_members = (
        ("runtime launch copy", os.path.join(launch.authorization_path, "launch.json"), launch.launch_bytes, _MAX_JSON),
        (
            "runtime ordered-task copy",
            os.path.join(launch.authorization_path, "ordered-tasks.jsonl"),
            _ordered_tasks_bytes_for_cli(launch=launch),
            _MAX_JSONL,
        ),
        (
            "runtime readback copy",
            os.path.join(launch.authorization_path, "readback.json"),
            launch.readback_bytes,
            _MAX_JSON,
        ),
    )
    for label, path, expected_bytes, maximum in current_authority_members:
        current_bytes = _read_bound_runtime_file(
            path,
            label=label,
            maximum=maximum,
            expected_uid=campaign_uid,
            require_single_link=True,
        )
        if current_bytes != expected_bytes:
            raise OneCellRunnerAuthorizationError(f"{label} changed after load", exit_code=78)
    allowed_tool_owners = administrators | {campaign_uid}
    if (
        launch.resources.sbatch_owner_uid not in allowed_tool_owners
        or launch.resources.scontrol_owner_uid not in allowed_tool_owners
        or launch.paths.git_owner_uid not in administrators
        or launch.paths.git_owner_uid == campaign_uid
    ):
        raise OneCellRunnerAuthorizationError("runtime tool owner is outside deployment ownership policy", exit_code=77)
    python_bytes = _read_bound_runtime_file(
        paths.python_executable,
        label="runtime Python",
        maximum=_MAX_TOOL_BYTES,
        expected_uid=campaign_uid,
        require_single_link=True,
    )
    if os.path.realpath(paths.python_executable) != paths.python_executable:
        raise OneCellRunnerAuthorizationError("runtime Python live realpath changed", exit_code=78)
    try:
        python_info = os.lstat(paths.python_executable)
    except OSError as error:
        raise OneCellRunnerAuthorizationError("runtime Python vanished", exit_code=78) from error
    if (
        stat.S_ISLNK(python_info.st_mode)
        or not stat.S_IMODE(python_info.st_mode) & 0o111
        or stat.S_IMODE(python_info.st_mode) & 0o022
    ):
        raise OneCellRunnerAuthorizationError("runtime Python mode is not trusted executable", exit_code=78)
    if (
        len(python_bytes) != paths.python_executable_size_bytes
        or _sha256(python_bytes) != paths.python_executable_sha256
    ):
        raise OneCellRunnerAuthorizationError("runtime Python byte identity changed", exit_code=78)
    sidecar = _read_bound_runtime_file(
        paths.runtime_python_file,
        label="runtime Python sidecar",
        maximum=4096,
        expected_uid=campaign_uid,
        expected_mode=0o600,
        require_single_link=True,
    )
    if sidecar != paths.runtime_python_bytes:
        raise OneCellRunnerAuthorizationError("runtime Python sidecar changed", exit_code=78)
    _validate_scheduler_tool_file(
        label="sbatch executable",
        path=launch.resources.sbatch_executable,
        owner_uid=launch.resources.sbatch_owner_uid,
        mode=launch.resources.sbatch_mode,
        size_bytes=launch.resources.sbatch_size_bytes,
        digest=launch.resources.sbatch_sha256,
    )
    _validate_scheduler_tool_file(
        label="scontrol executable",
        path=launch.resources.scontrol_executable,
        owner_uid=launch.resources.scontrol_owner_uid,
        mode=launch.resources.scontrol_mode,
        size_bytes=launch.resources.scontrol_size_bytes,
        digest=launch.resources.scontrol_sha256,
    )
    for label, path in (
        ("campaign root", paths.campaign_root),
        ("task root", paths.task_root),
        ("attempt root", paths.attempt_root),
        ("log root", paths.log_root),
        ("cache root", paths.cache_root),
        ("temporary root", paths.temporary_root),
        ("submission ledger root", paths.submission_ledger_root),
        ("authorized run directory", paths.authorized_run_directory),
    ):
        _validate_private_directory(path, label=label)


def _validate_held_launch_projection(launch: OneCellLaunchAuthority) -> None:
    """Reconstruct every inspection-visible projection from held authority bytes."""

    _validate_launch_authority(launch)
    ordered_bytes = _ordered_tasks_bytes_for_cli(launch=launch)
    if _sha256(ordered_bytes) != launch.ordered_tasks_sha256:
        raise OneCellRunnerAuthorizationError(
            "held ordered tasks differ from their public digest",
            exit_code=76,
        )
    private_fixture_bytes = _canonical_json(
        {
            "fixture": {
                "fixture_id": "slice-8b-authority-parser-nonexecuting",
                "scientific_execution_permitted": False,
            },
            "profile": _LAUNCH_FIXTURE_PROFILE,
        }
    )
    if launch.launch_bytes == private_fixture_bytes:
        if (
            launch.profile != _LAUNCH_FIXTURE_PROFILE
            or launch.launch_id != "fixture-launch"
            or launch.lane != "f0"
            or len(launch.ordered_tasks) != 1
        ):
            raise OneCellRunnerAuthorizationError("private fixture projection changed", exit_code=76)
        return

    launch_wire = _parse_launch_wire(launch.launch_bytes)
    deployment_lock = _parse_deployment_lock(launch.deployment_lock_bytes)
    deployment = _parse_deployment(launch.deployment_certificate_bytes)
    admission = _parse_admission(launch.admission_bytes)
    readback = _parse_readback(launch.readback_bytes)
    branch = None if launch.branch_decision_bytes is None else _parse_branch(launch.branch_decision_bytes)
    launch_reference = _parse_file_ref(readback["launch"], label="held readback.launch")
    authorities = launch_wire["authorities"]
    ordered_wire = launch_wire["ordered_tasks"]
    mapping = launch_wire["mapping"]
    assert type(authorities) is dict and type(ordered_wire) is dict and type(mapping) is dict
    _validate_authority_locations(launch_wire, launch_reference=launch_reference, branch=branch)
    _validate_authority_joins(
        launch=launch_wire,
        deployment_lock=deployment_lock,
        deployment=deployment,
        admission=admission,
        branch=branch,
    )
    reconstructed_resources = _resources_from_wires(launch_wire, deployment)
    reconstructed_paths = _paths_from_wires(
        launch_wire,
        deployment,
        authorization_path=launch.authorization_path,
        runtime_python_bytes=launch.paths.runtime_python_bytes,
    )
    try:
        reconstructed_campaign = load_one_cell_campaign(
            configuration_bytes=launch.campaign.configuration_bytes,
            task_map_members=launch.campaign.task_map_members,
        )
    except (OneCellCampaignValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError("held campaign projection is invalid", exit_code=76) from error
    campaign_record = deployment["campaign"]
    assert type(campaign_record) is dict
    configuration_reference = _parse_file_ref(
        campaign_record["configuration"],
        label="held deployment campaign configuration",
    )
    manifest_reference = _parse_file_ref(
        campaign_record["manifest"],
        label="held deployment campaign manifest",
    )
    deployment_lock_reference = _parse_file_ref(
        authorities["deployment_lock"],
        label="held launch deployment lock",
    )
    deployment_reference = _parse_file_ref(authorities["deployment"], label="held launch deployment")
    admission_reference = _parse_file_ref(authorities["admission"], label="held launch admission")
    held_reference_payloads = (
        (
            deployment_lock_reference,
            launch.deployment_lock_bytes,
            launch.deployment_lock_sha256,
            "campaigns/pre-one-cell-discovery-v1/deployment.lock.json",
        ),
        (
            deployment_reference,
            launch.deployment_certificate_bytes,
            launch.deployment_certificate_sha256,
            "authorizations/pre-one-cell-discovery-v1/deployment/certificate.json",
        ),
        (admission_reference, launch.admission_bytes, launch.admission_sha256, None),
    )
    for reference, payload, public_digest, exact_path in held_reference_payloads:
        if (
            reference["sha256"] != public_digest
            or reference["sha256"] != _sha256(payload)
            or reference["size_bytes"] != len(payload)
            or (exact_path is not None and reference["path"] != exact_path)
        ):
            raise OneCellRunnerAuthorizationError(
                "held authority bytes differ from their launch file reference",
                exit_code=76,
            )
    if (
        reconstructed_campaign != launch.campaign
        or configuration_reference["commit"] != launch.campaign_commit
        or configuration_reference["sha256"] != launch.campaign.configuration_sha256
        or configuration_reference["size_bytes"] != len(launch.campaign.configuration_bytes)
        or manifest_reference["commit"] != launch.campaign_commit
        or manifest_reference["sha256"] != launch.campaign_manifest_sha256
    ):
        raise OneCellRunnerAuthorizationError("held campaign differs from deployment bytes", exit_code=76)
    parsed_tasks = _parse_ordered_tasks(
        ordered_bytes,
        campaign=reconstructed_campaign,
        deployment_lock_sha256=launch.deployment_lock_sha256,
        software_commit=launch.software_commit,
        wheel_sha256=launch.wheel_sha256,
        branch_decision_sha256=launch.branch_decision_sha256,
    )
    protocol = deployment_lock["protocol"]
    assert type(protocol) is dict
    expected_branch_reference = authorities["branch"]
    branch_matches = (
        expected_branch_reference is None
        and launch.branch_decision_bytes is None
        and launch.branch_decision_sha256 is None
        and launch.branch_commit is None
        and launch.branch_path is None
        and launch.branch_size_bytes is None
    )
    if type(expected_branch_reference) is dict and launch.branch_decision_bytes is not None:
        branch_reference = _parse_file_ref(expected_branch_reference, label="held launch branch")
        branch_matches = (
            branch_reference["commit"] == launch.branch_commit
            and branch_reference["path"] == launch.branch_path
            and branch_reference["sha256"] == launch.branch_decision_sha256
            and branch_reference["size_bytes"] == launch.branch_size_bytes
        )
    git_environment = _parse_string_map(
        launch_wire["git_environment"],
        keys=tuple(key for key, _ in _GIT_ENVIRONMENT),
        label="held launch Git environment",
    )
    if (
        launch_reference["commit"] != launch.launch_commit
        or launch_reference["path"] != launch.launch_path
        or launch_reference["sha256"] != launch.launch_sha256
        or launch_reference["size_bytes"] != launch.launch_size_bytes
        or launch_wire["profile"] != launch.profile
        or launch_wire["launch_id"] != launch.launch_id
        or launch_wire["lane"] != launch.lane
        or authorities["protocol_commit"] != launch.protocol_commit
        or protocol["blob"] != launch.protocol_blob
        or authorities["protocol_sha256"] != launch.protocol_sha256
        or authorities["source_commit"] != launch.software_commit
        or authorities["wheel_sha256"] != launch.wheel_sha256
        or authorities["campaign_commit"] != launch.campaign_commit
        or authorities["campaign_manifest_sha256"] != launch.campaign_manifest_sha256
        or deployment_reference["commit"] != launch.deployment_commit
        or admission_reference["commit"] != launch.admission_commit
        or ordered_wire["profile"] != launch.ordered_tasks_profile
        or ordered_wire["sha256"] != launch.ordered_tasks_sha256
        or ordered_wire["size_bytes"] != len(ordered_bytes)
        or ordered_wire["task_count"] != len(launch.ordered_tasks)
        or mapping["profile"] != launch.mapping_profile
        or parsed_tasks != launch.ordered_tasks
        or reconstructed_resources != launch.resources
        or reconstructed_paths != launch.paths
        or git_environment != launch.git_environment
        or not branch_matches
    ):
        raise OneCellRunnerAuthorizationError("held launch projection differs from authority bytes", exit_code=76)
    _validate_branch_campaign_join(branch, campaign=reconstructed_campaign)


def _revalidate_loaded_launch_runtime(launch: OneCellLaunchAuthority) -> None:
    """Rebind a held public launch to all canonical bytes and live files."""

    _validate_held_launch_projection(launch)
    reloaded = _load_one_cell_launch_authority_impl(
        authorization_path=launch.authorization_path,
    )
    if reloaded != launch:
        raise OneCellRunnerAuthorizationError(
            "held launch projection differs from the current authenticated authority",
            exit_code=76,
        )
    launch_wire = _parse_launch_wire(launch.launch_bytes)
    deployment = _parse_deployment(launch.deployment_certificate_bytes)
    reconstructed_resources = _resources_from_wires(launch_wire, deployment)
    if reconstructed_resources != launch.resources:
        raise OneCellRunnerAuthorizationError(
            "held scheduler resources differ from their authority bytes",
            exit_code=76,
        )
    reconstructed = _paths_from_wires(
        launch_wire,
        deployment,
        authorization_path=launch.authorization_path,
        runtime_python_bytes=launch.paths.runtime_python_bytes,
    )
    if reconstructed != launch.paths:
        raise OneCellRunnerAuthorizationError("held runner paths differ from their authority bytes", exit_code=76)
    _validate_runtime_files(launch, deployment, runtime_revalidation=True)
    _validate_live_batch_script(launch)


@dataclass(frozen=True, slots=True)
class _LedgerHandles:
    root: int
    claims: int
    receipts: int
    permits: int
    results: int
    lock: int
    path_chain: tuple[int, ...]
    path_parts: tuple[str, ...]
    path_identities: tuple[tuple[int, int, int, int], ...]
    trusted_start_index: int
    allowed_uids: frozenset[int]
    lock_name: str


def _open_absolute_directory_chain(path: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    selected = _require_abs_path(path, label="descriptor-walk path")
    parts = tuple(part for part in selected.split(os.sep) if part)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    try:
        current = os.open(os.sep, flags)
        descriptors.append(current)
        current_path = os.sep
        for part in parts:
            _validate_named_child_limits(
                current,
                current_path,
                part,
                label="descriptor-walk component",
            )
            child = os.open(part, flags, dir_fd=current)
            info = os.fstat(child)
            if not stat.S_ISDIR(info.st_mode):
                os.close(child)
                raise OneCellRunnerAuthorizationError("descriptor-walk component is not a directory", exit_code=76)
            descriptors.append(child)
            current = child
            current_path = os.path.join(current_path, part)
        return tuple(descriptors), parts
    except BaseException as error:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
        if isinstance(error, FileNotFoundError):
            raise OneCellRunnerAuthorizationError(
                "descriptor-walk encountered a missing component",
                exit_code=66,
            ) from error
        if isinstance(error, OSError):
            raise OneCellRunnerAuthorizationError(
                "descriptor-walk encountered a missing, replaced, or symlink component",
                exit_code=76,
            ) from error
        raise


def _verify_directory_chain(chain: tuple[int, ...], parts: tuple[str, ...]) -> None:
    if len(chain) != len(parts) + 1:
        raise AssertionError("descriptor chain shape is invalid")
    for index, part in enumerate(parts):
        try:
            named = os.stat(part, dir_fd=chain[index], follow_symlinks=False)
            held = os.fstat(chain[index + 1])
        except OSError as error:
            raise OneCellRunnerAuthorizationError("descriptor-walk parent was replaced", exit_code=76) from error
        if not stat.S_ISDIR(named.st_mode) or (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
            raise OneCellRunnerAuthorizationError("descriptor-walk parent/name identity changed", exit_code=76)


def _close_directory_chain(chain: tuple[int, ...]) -> None:
    for descriptor in reversed(chain):
        try:
            os.close(descriptor)
        except OSError:
            pass


def _validate_exact_directory_members(path: str, *, expected: frozenset[str], label: str) -> None:
    """Reject extra/missing authorization members through a held directory."""

    chain, parts = _open_absolute_directory_chain(path)
    try:
        _verify_directory_chain(chain, parts)
        try:
            observed = os.listdir(chain[-1])
        except OSError as error:
            raise OneCellRunnerAuthorizationError(f"{label} cannot be enumerated", exit_code=66) from error
        observed_set = set(observed)
        if observed_set - expected:
            raise OneCellRunnerAuthorizationError(f"{label} contains an unexpected member", exit_code=76)
        if expected - observed_set:
            raise OneCellRunnerAuthorizationError(f"{label} lacks a required member", exit_code=66)
        _verify_directory_chain(chain, parts)
    finally:
        _close_directory_chain(chain)


def _validate_trusted_directory_chain(
    path: str,
    *,
    trusted_base: str,
    allowed_uids: frozenset[int],
    label: str,
    final_uid: int | None = None,
    final_mode: int | None = None,
) -> None:
    """Validate no-follow ancestry and ownership from the certified base."""

    selected = _require_abs_path(path, label=label)
    base = _require_abs_path(trusted_base, label="deployment trusted base")
    selected_parts = tuple(part for part in selected.split(os.sep) if part)
    base_parts = tuple(part for part in base.split(os.sep) if part)
    if selected_parts[: len(base_parts)] != base_parts:
        raise OneCellRunnerAuthorizationError(f"{label} is outside the certified trusted base", exit_code=77)
    chain, parts = _open_absolute_directory_chain(selected)
    try:
        _verify_directory_chain(chain, parts)
        # Descriptor zero is '/'; descriptor len(base_parts) names the base.
        for descriptor in chain[len(base_parts) :]:
            info = os.fstat(descriptor)
            if info.st_uid not in allowed_uids or stat.S_IMODE(info.st_mode) & 0o022:
                raise OneCellRunnerAuthorizationError(
                    f"{label} has an untrusted owner or writable ancestor",
                    exit_code=77,
                )
        final = os.fstat(chain[-1])
        if final_uid is not None and final.st_uid != final_uid:
            raise OneCellRunnerAuthorizationError(f"{label} has the wrong owner", exit_code=77)
        if final_mode is not None and stat.S_IMODE(final.st_mode) != final_mode:
            raise OneCellRunnerAuthorizationError(f"{label} has the wrong mode", exit_code=77)
        _verify_directory_chain(chain, parts)
    finally:
        _close_directory_chain(chain)


def _validate_deployment_path_policy(paths: OneCellRunnerPaths, deployment: dict[str, object]) -> None:
    deployment_paths = deployment["paths"]
    ownership = deployment["ownership"]
    repository = deployment["coordinator_repository"]
    assert type(deployment_paths) is dict and type(ownership) is dict and type(repository) is dict
    campaign_uid = int(ownership["campaign_uid"])
    allowed = frozenset({campaign_uid, *(int(value) for value in ownership["trusted_administrator_uids"])})
    trusted_base = str(ownership["trusted_base"])
    private_mode = int(str(ownership["campaign_root_mode"]), 8)
    readback_root = str(repository["authorization_readback_root"])

    # The deployment's isolated tree and both source checkouts must be rooted
    # in the certified base.  Checkout modes may be read-only or searchable;
    # all mutable/runtime leaves are exact current-user 0700 directories.
    for label, path in (
        ("article checkout", str(deployment_paths["article_checkout"])),
        ("software checkout", str(deployment_paths["software_checkout"])),
        ("coordinator checkout", str(deployment_paths["coordinator_checkout"])),
        ("deployed batch root", os.path.dirname(str(deployment_paths["batch_script"]))),
    ):
        _validate_trusted_directory_chain(
            path,
            trusted_base=trusted_base,
            allowed_uids=allowed,
            label=label,
        )
    for label, path, mode_key in (
        ("campaign root", paths.campaign_root, "campaign_root_mode"),
        ("environment root", str(deployment_paths["environment_root"]), "environment_root_mode"),
        ("authorization readback root", readback_root, "authorization_readback_root_mode"),
        ("authorization runtime directory", paths.authorization_directory, "authorization_readback_root_mode"),
        ("task root", paths.task_root, "private_task_root_mode"),
        ("attempt root", paths.attempt_root, "attempt_root_mode"),
        ("log root", paths.log_root, "log_root_mode"),
        ("cache root", paths.cache_root, "cache_root_mode"),
        ("temporary root", paths.temporary_root, "temporary_root_mode"),
        ("Numba cache root", os.path.join(paths.cache_root, "numba"), "cache_root_mode"),
        ("submission ledger root", paths.submission_ledger_root, "campaign_root_mode"),
        ("authorized run directory", paths.authorized_run_directory, "campaign_root_mode"),
    ):
        expected_mode = int(str(ownership[mode_key]), 8) if mode_key in ownership else private_mode
        _validate_trusted_directory_chain(
            path,
            trusted_base=trusted_base,
            allowed_uids=allowed,
            label=label,
            final_uid=campaign_uid,
            final_mode=expected_mode,
        )
    log_chain, log_parts = _open_absolute_directory_chain(paths.log_root)
    try:
        _verify_directory_chain(log_chain, log_parts)
        for label, template in (
            ("Slurm stdout template", paths.stdout_template),
            ("Slurm stderr template", paths.stderr_template),
        ):
            _validate_named_child_limits(
                log_chain[-1],
                paths.log_root,
                os.path.basename(template),
                label=label,
            )
        _verify_directory_chain(log_chain, log_parts)
    finally:
        _close_directory_chain(log_chain)


def _verify_ledger_handles(handles: _LedgerHandles) -> None:
    _verify_directory_chain(handles.path_chain, handles.path_parts)
    if len(handles.path_identities) != len(handles.path_chain):
        raise AssertionError("ledger path identity snapshot has the wrong shape")
    for index, (descriptor, expected) in enumerate(zip(handles.path_chain, handles.path_identities, strict=True)):
        current = os.fstat(descriptor)
        identity = (current.st_dev, current.st_ino, current.st_uid, stat.S_IMODE(current.st_mode))
        if identity != expected:
            raise OneCellRunnerAuthorizationError("submission ledger ancestor identity changed", exit_code=76)
        if index >= handles.trusted_start_index and (
            current.st_uid not in handles.allowed_uids or stat.S_IMODE(current.st_mode) & 0o022
        ):
            raise OneCellRunnerAuthorizationError(
                "submission ledger ancestor ownership or mode changed",
                exit_code=77,
            )
    for name, descriptor, directory_required in (
        ("claims", handles.claims, True),
        ("receipts", handles.receipts, True),
        ("requeue-permits", handles.permits, True),
        ("requeue-results", handles.results, True),
        (handles.lock_name, handles.lock, False),
    ):
        try:
            named = os.stat(name, dir_fd=handles.root, follow_symlinks=False)
            held = os.fstat(descriptor)
        except OSError as error:
            raise OneCellRunnerAuthorizationError(
                "submission ledger named child was replaced",
                exit_code=76,
            ) from error
        if (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino):
            raise OneCellRunnerAuthorizationError(
                "submission ledger named child and held descriptor differ",
                exit_code=76,
            )
        if directory_required:
            if not stat.S_ISDIR(named.st_mode) or named.st_uid != os.geteuid() or stat.S_IMODE(named.st_mode) != 0o700:
                raise OneCellRunnerAuthorizationError("submission ledger child is not private", exit_code=77)
        elif (
            not stat.S_ISREG(named.st_mode)
            or named.st_uid != os.geteuid()
            or stat.S_IMODE(named.st_mode) != 0o600
            or named.st_nlink != 1
        ):
            raise OneCellRunnerAuthorizationError("submission ledger lock is not private", exit_code=77)


def _ledger_trust_policy(launch: OneCellLaunchAuthority) -> tuple[str, frozenset[int]]:
    """Return the deployment policy; recognize only the private inert test record."""

    if launch.deployment_certificate_bytes == b'{"fixture":false}\n' and launch.launch_bytes == _canonical_json(
        {
            "fixture": {
                "fixture_id": "slice-8b-authority-parser-nonexecuting",
                "scientific_execution_permitted": False,
            },
            "profile": _LAUNCH_FIXTURE_PROFILE,
        }
    ):
        return os.path.dirname(launch.paths.campaign_root), frozenset({os.geteuid()})
    deployment = _parse_deployment(launch.deployment_certificate_bytes)
    ownership = deployment["ownership"]
    assert type(ownership) is dict
    return (
        _require_abs_path(ownership["trusted_base"], label="ledger trusted base"),
        frozenset(
            {
                int(ownership["campaign_uid"]),
                *(int(value) for value in ownership["trusted_administrator_uids"]),
            }
        ),
    )


def _open_required_ledger_child(parent: int, name: str, flags: int, *, label: str) -> int:
    try:
        return os.open(name, flags, dir_fd=parent)
    except FileNotFoundError as error:
        raise OneCellRunnerAuthorizationError(f"{label} is absent", exit_code=66) from error
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR, errno.EISDIR}:
            exit_code = 76
        elif error.errno in {errno.EACCES, errno.EPERM}:
            exit_code = 77
        else:
            exit_code = 74
        raise OneCellRunnerAuthorizationError(f"{label} cannot be opened", exit_code=exit_code) from error


def _open_ledger(launch: OneCellLaunchAuthority, *, exclusive: bool, nonblocking: bool = False) -> _LedgerHandles:
    root_path = launch.paths.submission_ledger_root
    lock_path = launch.paths.submission_ledger_lock
    if os.path.dirname(lock_path) != root_path:
        raise OneCellRunnerAuthorizationError("submission ledger lock is outside ledger root", exit_code=76)
    directory_flags = (
        os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptors: list[int] = []
    path_chain: tuple[int, ...] = ()
    path_parts: tuple[str, ...] = ()
    try:
        path_chain, path_parts = _open_absolute_directory_chain(root_path)
        root = path_chain[-1]
        descriptors.extend(path_chain)
        trusted_base, allowed_uids = _ledger_trust_policy(launch)
        trusted_parts = tuple(part for part in trusted_base.split(os.sep) if part)
        if path_parts[: len(trusted_parts)] != trusted_parts:
            raise OneCellRunnerAuthorizationError("submission ledger is outside its trusted base", exit_code=77)
        trusted_start_index = len(trusted_parts)
        path_identities = tuple(
            (
                info.st_dev,
                info.st_ino,
                info.st_uid,
                stat.S_IMODE(info.st_mode),
            )
            for info in (os.fstat(descriptor) for descriptor in path_chain)
        )
        for index, identity in enumerate(path_identities):
            _device, _inode, owner_uid, mode = identity
            if index >= trusted_start_index and (owner_uid not in allowed_uids or mode & 0o022):
                raise OneCellRunnerAuthorizationError(
                    "submission ledger ancestor ownership or mode is invalid",
                    exit_code=77,
                )
        root_info = os.fstat(root)
        if (
            not stat.S_ISDIR(root_info.st_mode)
            or root_info.st_uid != os.geteuid()
            or stat.S_IMODE(root_info.st_mode) != 0o700
        ):
            raise OneCellRunnerAuthorizationError("submission ledger root is not private", exit_code=77)
        children: list[int] = []
        for name in ("claims", "receipts", "requeue-permits", "requeue-results"):
            _validate_named_child_limits(root, root_path, name, label="submission ledger child")
            descriptor = _open_required_ledger_child(
                root,
                name,
                directory_flags,
                label="submission ledger child",
            )
            descriptors.append(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise OneCellRunnerAuthorizationError("submission ledger child is not private", exit_code=77)
            children.append(descriptor)
        lock_name = os.path.basename(lock_path)
        _validate_named_child_limits(root, root_path, lock_name, label="submission ledger lock")
        lock = _open_required_ledger_child(root, lock_name, file_flags, label="submission ledger lock")
        descriptors.append(lock)
        lock_info = os.fstat(lock)
        if (
            not stat.S_ISREG(lock_info.st_mode)
            or lock_info.st_uid != os.geteuid()
            or stat.S_IMODE(lock_info.st_mode) != 0o600
            or lock_info.st_nlink != 1
        ):
            raise OneCellRunnerAuthorizationError("submission ledger lock inode is invalid", exit_code=77)
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if nonblocking:
            operation |= fcntl.LOCK_NB
        fcntl.flock(lock, operation)
        handles = _LedgerHandles(
            root,
            children[0],
            children[1],
            children[2],
            children[3],
            lock,
            path_chain,
            path_parts,
            path_identities,
            trusted_start_index,
            allowed_uids,
            lock_name,
        )
        _verify_ledger_handles(handles)
        return handles
    except BaseException:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass
        raise


def _close_ledger(handles: _LedgerHandles) -> None:
    verification_error: BaseException | None = None
    try:
        try:
            _verify_ledger_handles(handles)
        except BaseException as error:
            verification_error = error
        fcntl.flock(handles.lock, fcntl.LOCK_UN)
    finally:
        for descriptor in (
            handles.lock,
            handles.results,
            handles.permits,
            handles.receipts,
            handles.claims,
            *reversed(handles.path_chain),
        ):
            os.close(descriptor)
    if verification_error is not None:
        raise verification_error


def _read_ledger_member(
    directory: int,
    name: str,
    *,
    parent_path: str,
    label: str,
    maximum: int = 64 << 10,
) -> bytes | None:
    if type(name) is not str or "/" in name or not name:
        raise TypeError("ledger member name must be one component")
    selected_parent = _require_abs_path(parent_path, label=f"{label} parent")
    _validate_named_child_limits(directory, selected_parent, name, label=label)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory)
    except FileNotFoundError:
        return None
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR, errno.EISDIR}:
            exit_code = 76
        elif error.errno in {errno.EACCES, errno.EPERM}:
            exit_code = 77
        else:
            exit_code = 74
        raise OneCellRunnerAuthorizationError(f"{label} cannot be opened", exit_code=exit_code) from error
    try:
        info = os.fstat(descriptor)
        try:
            named = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except OSError as error:
            raise OneCellRunnerAuthorizationError(f"{label} named identity vanished", exit_code=76) from error
        if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
            raise OneCellRunnerAuthorizationError(f"{label} named identity differs", exit_code=76)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or not 0 < info.st_size <= maximum
        ):
            raise OneCellRunnerAuthorizationError(f"{label} is not an exact private ledger record", exit_code=76)
        payload = b""
        while len(payload) < info.st_size:
            chunk = os.read(descriptor, info.st_size - len(payload))
            if not chunk:
                raise OneCellRunnerAuthorizationError(f"{label} changed while reading", exit_code=76)
            payload += chunk
        if os.read(descriptor, 1):
            raise OneCellRunnerAuthorizationError(f"{label} grew while reading", exit_code=76)
        after = os.fstat(descriptor)
        if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
            info.st_dev,
            info.st_ino,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        ):
            raise OneCellRunnerAuthorizationError(f"{label} changed while reading", exit_code=76)
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_uid != os.geteuid()
            or stat.S_IMODE(after.st_mode) != 0o600
            or after.st_nlink != 1
        ):
            raise OneCellRunnerAuthorizationError(f"{label} private metadata changed", exit_code=76)
        try:
            named_after = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except OSError as error:
            raise OneCellRunnerAuthorizationError(f"{label} named identity vanished", exit_code=76) from error
        if (named_after.st_dev, named_after.st_ino) != (after.st_dev, after.st_ino):
            raise OneCellRunnerAuthorizationError(f"{label} named identity changed", exit_code=76)
        return payload
    finally:
        os.close(descriptor)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError(errno.EIO, "short ledger write")
        view = view[written:]


def _install_claim(directory: int, name: str, payload: bytes, *, parent_path: str) -> None:
    selected_parent = _require_abs_path(parent_path, label="claim parent")
    _validate_named_child_limits(directory, selected_parent, name, label="claim record")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=directory)
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.fsync(directory)
    except FileExistsError as error:
        raise OneCellRunnerAuthorizationError("submission launch is already claimed", exit_code=77) from error
    except OSError as error:
        raise OneCellRunnerAuthorizationError("submission claim durability failed", exit_code=74) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _preflight_link_record_limits(
    directory: int,
    name: str,
    *,
    parent_path: str,
    label: str,
) -> str:
    selected_parent = _require_abs_path(parent_path, label=f"{label} parent")
    _validate_named_child_limits(directory, selected_parent, name, label=label)
    temporary_template = f".{name}.{'0' * 32}.tmp"
    _validate_named_child_limits(
        directory,
        selected_parent,
        temporary_template,
        label=f"temporary {label}",
    )
    return selected_parent


def _preflight_link_record_path_limits(parent_path: str, name: str, *, label: str) -> None:
    selected_parent = _require_abs_path(parent_path, label=f"{label} parent")
    chain, parts = _open_absolute_directory_chain(selected_parent)
    try:
        _verify_directory_chain(chain, parts)
        _preflight_link_record_limits(
            chain[-1],
            name,
            parent_path=selected_parent,
            label=label,
        )
        _verify_directory_chain(chain, parts)
    finally:
        _close_directory_chain(chain)


def _install_link_record(
    directory: int,
    name: str,
    payload: bytes,
    *,
    parent_path: str,
    label: str,
) -> None:
    selected_parent = _preflight_link_record_limits(
        directory,
        name,
        parent_path=parent_path,
        label=label,
    )
    temporary = f".{name}.{os.urandom(16).hex()}.tmp"
    _validate_named_child_limits(directory, selected_parent, temporary, label=f"temporary {label}")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(temporary, flags, 0o600, dir_fd=directory)
            _write_all(descriptor, payload)
            os.fsync(descriptor)
            # Persist the guard entry before the target can exist.  File fsync
            # alone does not make its containing directory entry durable.
            os.fsync(directory)
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        except FileExistsError as error:
            if descriptor is not None:
                try:
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
                except OSError:
                    pass
            raise OneCellRunnerAuthorizationError(f"{label} already exists", exit_code=76) from error
        except OSError as error:
            if descriptor is not None:
                try:
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
                except OSError:
                    pass
            raise OneCellRunnerAuthorizationError(f"{label} durability failed", exit_code=74) from error

        # Make the target link durable while the temporary link still keeps
        # nlink == 2.  A crash anywhere before this fsync can therefore expose
        # only a target that the shared-lock reader refuses as linked.
        try:
            os.fsync(directory)
        except OSError as error:
            target_removed = False
            try:
                os.unlink(name, dir_fd=directory)
                target_removed = True
            except FileNotFoundError:
                target_removed = True
            except OSError:
                # Keep the temporary link: any surviving target remains nlink
                # two and cannot authorize a worker.
                pass
            guarded_state_synced = False
            try:
                # Whether target removal succeeded or not, try to persist a
                # state that is either target-absent or guarded at nlink two.
                os.fsync(directory)
                guarded_state_synced = True
            except OSError:
                pass
            if target_removed and guarded_state_synced:
                try:
                    os.unlink(temporary, dir_fd=directory)
                    os.fsync(directory)
                except OSError:
                    pass
            raise OneCellRunnerAuthorizationError(f"{label} durability failed", exit_code=74) from error

        # The target is now durable.  Remove the guard link; while the lock is
        # held, nlink two remains fail-closed.  If cleanup fsync fails after a
        # successful unlink, the current target is already durable and safe;
        # a reboot may only conservatively restore nlink two.
        try:
            os.unlink(temporary, dir_fd=directory)
        except OSError:
            try:
                os.unlink(temporary, dir_fd=directory)
            except OSError as retry_error:
                raise OneCellRunnerAuthorizationError(
                    f"{label} durable target remains guarded by its temporary link",
                    exit_code=74,
                ) from retry_error
        try:
            os.fsync(directory)
        except OSError:
            # The preceding directory fsync already made the target durable,
            # and the live target is single-link.  Cleanup non-durability can
            # only restore the guard link after a crash, which fails closed.
            pass
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


def _argv_digest(argv: tuple[str, ...], *, profile: str) -> str:
    return _sha256(_canonical_json({"argv": list(argv), "profile": profile}, newline=False))


def _sbatch_argv_from_runtime(
    *,
    resources: OneCellSlurmResourceEnvelope,
    task_count: int,
    paths: OneCellRunnerPaths,
    authorization_path: str,
) -> tuple[str, ...]:
    if type(resources) is not OneCellSlurmResourceEnvelope or type(paths) is not OneCellRunnerPaths:
        raise TypeError("sbatch argv requires exact resource and path records")
    selected_count = _require_exact_int(task_count, label="sbatch task count", minimum=1, maximum=_MAX_TASKS)
    selected_authorization = _require_abs_path(authorization_path, label="sbatch authorization path")
    if resources.array_concurrency > selected_count:
        raise OneCellRunnerAuthorizationError("sbatch concurrency exceeds task count", exit_code=76)
    argv = (
        resources.sbatch_executable,
        "--parsable",
        "--requeue",
        "--export=NIL",
        "--open-mode=append",
        "--nodes=1",
        "--ntasks=1",
        f"--cpus-per-task={resources.cpus_per_task}",
        f"--mem={resources.memory_mib}M",
        f"--time={resources.wall_minutes}",
        f"--partition={resources.partition}",
        f"--array=0-{selected_count - 1}%{resources.array_concurrency}",
        "--signal=B:USR1@900",
        f"--chdir={paths.authorized_run_directory}",
        f"--output={paths.stdout_template}",
        f"--error={paths.stderr_template}",
        paths.batch_script,
        selected_authorization,
    )
    if any(len(os.fsencode(item)) > 4096 for item in argv):
        raise OneCellRunnerAuthorizationError("sbatch argv member exceeds path bound", exit_code=76)
    return argv


def _sbatch_argv(launch: OneCellLaunchAuthority) -> tuple[str, ...]:
    return _sbatch_argv_from_runtime(
        resources=launch.resources,
        task_count=len(launch.ordered_tasks),
        paths=launch.paths,
        authorization_path=launch.authorization_path,
    )


def _preflight_generated_runtime_paths(
    *,
    paths: OneCellRunnerPaths,
    resources: OneCellSlurmResourceEnvelope,
    launch_sha256: str,
    ordered_rows: tuple[dict[str, object], ...],
    authorization_path: str,
) -> None:
    launch_digest = _require_hex(launch_sha256, label="preflight launch digest")
    task_count = len(ordered_rows)
    _require_exact_int(task_count, label="preflight task count", minimum=1, maximum=_MAX_TASKS)
    launch_record_name = f"{launch_digest}.json"
    claims_path = os.path.join(paths.submission_ledger_root, "claims")
    receipts_path = os.path.join(paths.submission_ledger_root, "receipts")
    permits_path = os.path.join(paths.submission_ledger_root, "requeue-permits")
    results_path = os.path.join(paths.submission_ledger_root, "requeue-results")
    _validate_relative_path_limits(claims_path, (launch_record_name,), label="submission claim path")
    _preflight_link_record_path_limits(receipts_path, launch_record_name, label="submission receipt")
    requeue_record_name = f"{launch_digest}-p{_MAX_TASKS - 1:020d}-r{16:020d}-to-{16:020d}.json"
    _validate_relative_path_limits(permits_path, (requeue_record_name,), label="requeue permit path")
    _preflight_link_record_path_limits(results_path, requeue_record_name, label="requeue result")

    generation = f"{_U64_MAX:020d}"
    checkpoint_targets = tuple(
        f"checkpoint.{generation}.{suffix}"
        for suffix in (
            "arrays.u64le",
            "configuration.bin",
            "scientific-identity.bin",
            "state.json",
            "manifest.json",
        )
    )
    final_targets = (
        "final.arrays.u64le",
        "final.configuration.bin",
        "final.scientific-identity.bin",
        "final.state.json",
        "final.manifest.json",
    )
    publication_targets = checkpoint_targets + final_targets
    task_leaves = (
        "task.lock",
        *publication_targets,
        *(f".{target}.{'0' * 32}.tmp" for target in publication_targets),
    )
    maximum_attempt_id = f"{_U32_MAX}_{_MAX_TASKS - 1:020d}-r{16:020d}-j{_U32_MAX}"
    row_keys = (
        "profile",
        "array_position",
        "wave",
        "role",
        "task_map_id",
        "scientific_index",
        "scientific_identity_hex",
        "scientific_identity_sha256",
        "scientific_identity_size_bytes",
        "relative_task_directory",
    )
    for position, raw in enumerate(ordered_rows):
        row = _exact_dict(raw, keys=row_keys, label=f"preflight ordered task {position}")
        if type(row["array_position"]) is not int or row["array_position"] != position:
            raise OneCellRunnerAuthorizationError("preflight array positions are not contiguous", exit_code=76)
        wave = _require_ascii_token(row["wave"], label="preflight task wave")
        task_index = _require_exact_int(
            row["scientific_index"],
            label="preflight scientific index",
            maximum=_MAX_TASKS - 1,
        )
        digest = _require_hex(row["scientific_identity_sha256"], label="preflight scientific identity digest")
        relative = _require_safe_path(row["relative_task_directory"], label="preflight relative task directory")
        if relative != f"{wave}/{task_index:020d}-{digest}":
            raise OneCellRunnerAuthorizationError("preflight task directory is not frozen", exit_code=76)
        relative_parts = tuple(relative.split("/"))
        _validate_relative_leaf_path_limits(
            paths.task_root,
            relative_parts,
            task_leaves,
            label="preflight task/checkpoint path",
        )
        _validate_relative_leaf_path_limits(
            paths.attempt_root,
            relative_parts,
            (maximum_attempt_id,),
            label="preflight attempt path",
        )

    sbatch_argv = _sbatch_argv_from_runtime(
        resources=resources,
        task_count=task_count,
        paths=paths,
        authorization_path=authorization_path,
    )
    _validate_argv_path_limits(
        sbatch_argv,
        reference_directories=(
            paths.campaign_root,
            authorization_path,
            paths.authorized_run_directory,
            paths.log_root,
            os.path.dirname(resources.sbatch_executable),
            os.path.dirname(paths.batch_script),
        ),
        label="preflight sbatch argv",
    )
    _validate_argv_path_limits(
        (resources.scontrol_executable, "requeue", f"{_U32_MAX}_{_MAX_TASKS - 1}"),
        reference_directories=(
            paths.campaign_root,
            os.path.dirname(resources.scontrol_executable),
        ),
        label="preflight scontrol argv",
    )


def _launch_batch_authority(launch: OneCellLaunchAuthority) -> dict[str, object]:
    wire = _parse_launch_wire(launch.launch_bytes)
    if wire["profile"] != _LAUNCH_PROFILE or wire["authorities"]["source_commit"] != launch.software_commit:
        raise OneCellRunnerAuthorizationError("held launch bytes do not bind the public SOURCE", exit_code=76)
    batch = wire["batch_script"]
    paths = wire["paths"]
    assert type(batch) is dict and type(paths) is dict
    if (
        batch["source_commit"] != launch.software_commit
        or batch["path"] != "scripts/easley/run_pre_one_cell.sbatch"
        or paths["batch_script"] != launch.paths.batch_script
    ):
        raise OneCellRunnerAuthorizationError("held launch batch authority does not join public paths", exit_code=76)
    return batch


def _validate_live_batch_script(launch: OneCellLaunchAuthority) -> bytes:
    batch = _launch_batch_authority(launch)
    live = _read_bound_runtime_file(
        launch.paths.batch_script,
        label="live batch script",
        maximum=_MAX_JSON,
        expected_uid=os.geteuid(),
        require_single_link=True,
        forbid_group_world_write=True,
    )
    if len(live) != batch["size_bytes"] or _sha256(live) != batch["sha256"]:
        raise OneCellRunnerAuthorizationError("live batch script differs from LAUNCH authority", exit_code=78)
    return live


def _submission_claim_bytes(launch: OneCellLaunchAuthority, argv: tuple[str, ...]) -> bytes:
    batch = _launch_batch_authority(launch)
    _validate_live_batch_script(launch)
    return _canonical_json(
        {
            "array_mapping": {
                "array_first": 0,
                "array_last": len(launch.ordered_tasks) - 1,
                "array_step": 1,
                "profile": _ARRAY_PROFILE,
            },
            "authorization_path": launch.authorization_path,
            "batch_script_sha256": batch["sha256"],
            "launch_commit": launch.launch_commit,
            "launch_path": launch.launch_path,
            "launch_sha256": launch.launch_sha256,
            "launch_size_bytes": launch.launch_size_bytes,
            "ordered_tasks_sha256": launch.ordered_tasks_sha256,
            "profile": _CLAIM_PROFILE,
            "readback_sha256": launch.readback_sha256,
            "sbatch_argv": list(argv),
            "sbatch_argv_sha256": _argv_digest(argv, profile=_SBATCH_ARGV_PROFILE),
        }
    )


def _parse_submission_claim(payload: bytes, *, launch: OneCellLaunchAuthority) -> dict[str, object]:
    batch = _launch_batch_authority(launch)
    _validate_live_batch_script(launch)
    value = _parse_canonical_json(payload, label="submission claim", maximum=64 << 10)
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "authorization_path",
            "launch_commit",
            "launch_path",
            "launch_sha256",
            "launch_size_bytes",
            "readback_sha256",
            "ordered_tasks_sha256",
            "array_mapping",
            "batch_script_sha256",
            "sbatch_argv",
            "sbatch_argv_sha256",
        ),
        label="submission claim",
    )
    if record["profile"] != _CLAIM_PROFILE:
        raise OneCellRunnerValidationError("submission claim profile is not frozen")
    mapping = _exact_dict(
        record["array_mapping"],
        keys=("profile", "array_first", "array_last", "array_step"),
        label="submission claim array mapping",
    )
    expected_mapping = {
        "profile": _ARRAY_PROFILE,
        "array_first": 0,
        "array_last": len(launch.ordered_tasks) - 1,
        "array_step": 1,
    }
    argv_list = _exact_list(record["sbatch_argv"], label="submission claim argv", maximum=64)
    if any(type(item) is not str for item in argv_list):
        raise OneCellRunnerValidationError("submission claim argv entries are not strings")
    argv = tuple(argv_list)
    expected = {
        "authorization_path": launch.authorization_path,
        "launch_commit": launch.launch_commit,
        "launch_path": launch.launch_path,
        "launch_sha256": launch.launch_sha256,
        "launch_size_bytes": launch.launch_size_bytes,
        "readback_sha256": launch.readback_sha256,
        "ordered_tasks_sha256": launch.ordered_tasks_sha256,
        "batch_script_sha256": batch["sha256"],
        "sbatch_argv_sha256": _argv_digest(argv, profile=_SBATCH_ARGV_PROFILE),
    }
    if (
        mapping != expected_mapping
        or argv != _sbatch_argv(launch)
        or any(record[key] != item for key, item in expected.items())
    ):
        raise OneCellRunnerAuthorizationError("submission claim does not bind this launch", exit_code=76)
    return record


def _submission_receipt_bytes(
    *,
    launch: OneCellLaunchAuthority,
    claim_sha256: str,
    sbatch_argv_sha256: str,
    result: _ProcessResult,
    outcome: str,
    array_job_id: str | None,
) -> bytes:
    return _canonical_json(
        {
            "array_job_id": array_job_id,
            "array_mapping": {
                "array_first": 0,
                "array_last": len(launch.ordered_tasks) - 1,
                "array_step": 1,
                "profile": _ARRAY_PROFILE,
            },
            "claim_sha256": claim_sha256,
            "launch_sha256": launch.launch_sha256,
            "outcome": outcome,
            "profile": _RECEIPT_PROFILE,
            # The frozen wire schema has no separate timeout/spawn field.  A
            # scheduler observation that cannot be attributed to a completed
            # child is therefore represented by the schema's exact `null`
            # return code, even if a timeout/kill race happened to reap zero.
            "returncode": None if result.timed_out or result.spawn_ambiguous else result.returncode,
            "sbatch_argv_sha256": sbatch_argv_sha256,
            "stderr_hex": result.stderr.hex(),
            "stderr_overflow": result.stderr_overflow,
            "stdout_hex": result.stdout.hex(),
            "stdout_overflow": result.stdout_overflow,
        }
    )


def _parse_submission_receipt(
    payload: bytes,
    *,
    launch: OneCellLaunchAuthority,
    claim_bytes: bytes,
    claim: dict[str, object],
) -> dict[str, object]:
    value = _parse_canonical_json(payload, label="submission receipt", maximum=64 << 10)
    record = _exact_dict(
        value,
        keys=(
            "profile",
            "claim_sha256",
            "launch_sha256",
            "sbatch_argv_sha256",
            "outcome",
            "returncode",
            "stdout_hex",
            "stdout_overflow",
            "stderr_hex",
            "stderr_overflow",
            "array_job_id",
            "array_mapping",
        ),
        label="submission receipt",
    )
    if record["profile"] != _RECEIPT_PROFILE:
        raise OneCellRunnerValidationError("submission receipt profile is not frozen")
    if (
        record["claim_sha256"] != _sha256(claim_bytes)
        or record["launch_sha256"] != launch.launch_sha256
        or record["sbatch_argv_sha256"] != claim["sbatch_argv_sha256"]
    ):
        raise OneCellRunnerAuthorizationError("submission receipt does not bind claim/launch/argv", exit_code=76)
    mapping = _exact_dict(
        record["array_mapping"],
        keys=("profile", "array_first", "array_last", "array_step"),
        label="submission receipt array mapping",
    )
    if mapping != claim["array_mapping"]:
        raise OneCellRunnerAuthorizationError("submission receipt array mapping differs from claim", exit_code=76)
    returncode = record["returncode"]
    if returncode is not None and (type(returncode) is not int or not -(1 << 31) <= returncode < (1 << 31)):
        raise OneCellRunnerValidationError("submission receipt returncode is invalid")
    stdout_overflow = _require_exact_bool(record["stdout_overflow"], label="submission receipt stdout_overflow")
    stderr_overflow = _require_exact_bool(record["stderr_overflow"], label="submission receipt stderr_overflow")
    stdout = _decode_captured_hex(
        record["stdout_hex"],
        overflow=stdout_overflow,
        label="submission receipt stdout_hex",
    )
    stderr = _decode_captured_hex(
        record["stderr_hex"],
        overflow=stderr_overflow,
        label="submission receipt stderr_hex",
    )
    result = _ProcessResult(returncode, stdout, stdout_overflow, stderr, stderr_overflow, returncode is None, False)
    expected_outcome, expected_job = _classify_scheduler_result(result=result, submission=True)
    if record["outcome"] != expected_outcome or record["array_job_id"] != expected_job:
        raise OneCellRunnerAuthorizationError("submission receipt outcome contradicts captured result", exit_code=76)
    return record


def _parse_stable_submission_handshake(
    claim_bytes: bytes,
    receipt_bytes: bytes,
    *,
    launch: OneCellLaunchAuthority,
) -> tuple[dict[str, object], dict[str, object]]:
    """Map malformed durable handshake state to the frozen integrity exit."""

    try:
        claim = _parse_submission_claim(claim_bytes, launch=launch)
        receipt = _parse_submission_receipt(
            receipt_bytes,
            launch=launch,
            claim_bytes=claim_bytes,
            claim=claim,
        )
    except OneCellRunnerAuthorizationError:
        raise
    except (OneCellRunnerValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError(
            "durable submission handshake is malformed",
            exit_code=76,
        ) from error
    return claim, receipt


def _load_submission_handshake_for_cli(*, launch: OneCellLaunchAuthority) -> tuple[bytes, bytes]:
    """Wait for the one append-only claim/receipt pair under a shared lock."""

    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    if selected.profile != _LAUNCH_PROFILE:
        raise OneCellRunnerAuthorizationError("fixture launch is permanently nonexecuting", exit_code=77)
    name = f"{selected.launch_sha256}.json"
    claims_path = os.path.join(selected.paths.submission_ledger_root, "claims")
    receipts_path = os.path.join(selected.paths.submission_ledger_root, "receipts")
    deadline = time.monotonic_ns() + selected.resources.receipt_handshake_seconds * 1_000_000_000
    final_read = False
    while True:
        handles: _LedgerHandles | None = None
        try:
            try:
                handles = _open_ledger(selected, exclusive=False, nonblocking=True)
            except BlockingIOError:
                handles = None
            if handles is not None:
                claim_bytes = _read_ledger_member(
                    handles.claims,
                    name,
                    parent_path=claims_path,
                    label="submission claim",
                )
                receipt_bytes = _read_ledger_member(
                    handles.receipts,
                    name,
                    parent_path=receipts_path,
                    label="submission receipt",
                )
                if claim_bytes is None and receipt_bytes is not None:
                    raise OneCellRunnerAuthorizationError(
                        "submission receipt exists without its claim",
                        exit_code=76,
                    )
                if claim_bytes is not None and receipt_bytes is not None:
                    _claim, receipt = _parse_stable_submission_handshake(
                        claim_bytes,
                        receipt_bytes,
                        launch=selected,
                    )
                    if receipt["outcome"] != "accepted":
                        raise OneCellRunnerAuthorizationError("submission receipt is not accepted", exit_code=76)
                    return claim_bytes, receipt_bytes
        finally:
            if handles is not None:
                _close_ledger(handles)
        remaining = deadline - time.monotonic_ns()
        if remaining <= 0:
            if final_read:
                raise OneCellRunnerAuthorizationError("submission receipt handshake timed out", exit_code=66)
            final_read = True
            continue
        time.sleep(min(0.250, remaining / 1_000_000_000))


def _canonical_zero_decimal(value: object, *, label: str, maximum: int) -> int:
    text = _require_exact_str(value, label=label, maximum=20)
    if re.fullmatch(r"0|[1-9][0-9]*", text) is None:
        raise OneCellRunnerAuthorizationError(f"{label} is not canonical decimal", exit_code=76)
    number = int(text)
    if number > maximum:
        raise OneCellRunnerAuthorizationError(f"{label} exceeds its bound", exit_code=76)
    return number


def _parse_requeue_result_record(payload: bytes, *, permit_bytes: bytes) -> dict[str, object]:
    result_value = _parse_canonical_json(payload, label="requeue result", maximum=64 << 10)
    result = _exact_dict(
        result_value,
        keys=(
            "profile",
            "permit_sha256",
            "outcome",
            "returncode",
            "stdout_hex",
            "stdout_overflow",
            "stderr_hex",
            "stderr_overflow",
        ),
        label="requeue result",
    )
    if result["profile"] != _RESULT_PROFILE or result["permit_sha256"] != _sha256(permit_bytes):
        raise OneCellRunnerAuthorizationError("requeue result does not bind permit", exit_code=76)
    returncode = result["returncode"]
    if returncode is not None and (type(returncode) is not int or not -(1 << 31) <= returncode < (1 << 31)):
        raise OneCellRunnerValidationError("requeue result returncode is invalid")
    stdout_overflow = _require_exact_bool(result["stdout_overflow"], label="requeue result stdout_overflow")
    stderr_overflow = _require_exact_bool(result["stderr_overflow"], label="requeue result stderr_overflow")
    stdout = _decode_captured_hex(
        result["stdout_hex"],
        overflow=stdout_overflow,
        label="requeue result stdout_hex",
    )
    stderr = _decode_captured_hex(
        result["stderr_hex"],
        overflow=stderr_overflow,
        label="requeue result stderr_hex",
    )
    observed = _ProcessResult(
        returncode,
        stdout,
        stdout_overflow,
        stderr,
        stderr_overflow,
        returncode is None,
        False,
    )
    expected_outcome, expected_job_id = _classify_scheduler_result(result=observed, submission=False)
    if expected_job_id is not None or result["outcome"] != expected_outcome:
        raise OneCellRunnerAuthorizationError("requeue result outcome contradicts its captured fields", exit_code=76)
    return result


def _slurm_positive_decimal(value: object, *, label: str) -> str:
    try:
        return _require_positive_decimal(value, label=label)
    except (OneCellRunnerValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError(f"{label} contradicts the launch mapping", exit_code=76) from error


def _slurm_zero_decimal(value: object, *, label: str, maximum: int) -> int:
    try:
        return _canonical_zero_decimal(value, label=label, maximum=maximum)
    except (OneCellRunnerValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError(f"{label} contradicts the launch mapping", exit_code=76) from error


def _validate_slurm_execution_environment(
    launch: OneCellLaunchAuthority,
    *,
    receipt: dict[str, object],
) -> tuple[str, int, str, int]:
    required = {
        "SLURM_ARRAY_JOB_ID": os.environ.get("SLURM_ARRAY_JOB_ID"),
        "SLURM_ARRAY_TASK_ID": os.environ.get("SLURM_ARRAY_TASK_ID"),
        "SLURM_ARRAY_TASK_MIN": os.environ.get("SLURM_ARRAY_TASK_MIN"),
        "SLURM_ARRAY_TASK_MAX": os.environ.get("SLURM_ARRAY_TASK_MAX"),
        "SLURM_ARRAY_TASK_COUNT": os.environ.get("SLURM_ARRAY_TASK_COUNT"),
        "SLURM_ARRAY_TASK_STEP": os.environ.get("SLURM_ARRAY_TASK_STEP"),
        "SLURM_JOB_ID": os.environ.get("SLURM_JOB_ID"),
        "SLURM_JOB_PARTITION": os.environ.get("SLURM_JOB_PARTITION"),
        "SLURM_CPUS_PER_TASK": os.environ.get("SLURM_CPUS_PER_TASK"),
        "SLURM_MEM_PER_NODE": os.environ.get("SLURM_MEM_PER_NODE"),
    }
    if any(value is None or type(value) is not str for value in required.values()):
        raise OneCellRunnerAuthorizationError("required Slurm environment is absent", exit_code=78)
    array_job_id = _slurm_positive_decimal(required["SLURM_ARRAY_JOB_ID"], label="SLURM_ARRAY_JOB_ID")
    if receipt["outcome"] != "accepted" or array_job_id != receipt["array_job_id"]:
        raise OneCellRunnerAuthorizationError("Slurm array job differs from accepted receipt", exit_code=76)
    position = _slurm_zero_decimal(
        required["SLURM_ARRAY_TASK_ID"],
        label="SLURM_ARRAY_TASK_ID",
        maximum=len(launch.ordered_tasks) - 1,
    )
    if (
        required["SLURM_ARRAY_TASK_MIN"] != "0"
        or required["SLURM_ARRAY_TASK_MAX"] != str(len(launch.ordered_tasks) - 1)
        or required["SLURM_ARRAY_TASK_COUNT"] != str(len(launch.ordered_tasks))
        or required["SLURM_ARRAY_TASK_STEP"] != "1"
    ):
        raise OneCellRunnerAuthorizationError("Slurm array mapping differs from launch", exit_code=76)
    slurm_job_id = _slurm_positive_decimal(required["SLURM_JOB_ID"], label="SLURM_JOB_ID")
    if (
        required["SLURM_JOB_PARTITION"] != launch.resources.partition
        or required["SLURM_CPUS_PER_TASK"] != str(launch.resources.cpus_per_task)
        or required["SLURM_MEM_PER_NODE"] != str(launch.resources.memory_mib)
    ):
        raise OneCellRunnerAuthorizationError("Slurm resource environment differs from launch", exit_code=78)
    restart_text = os.environ.get("SLURM_RESTART_COUNT")
    if restart_text is None or restart_text == "0":
        restart_count = 0
    else:
        restart_count = _slurm_zero_decimal(
            restart_text,
            label="SLURM_RESTART_COUNT",
            maximum=launch.resources.max_requeues_per_task,
        )
        if restart_count == 0:
            raise OneCellRunnerAuthorizationError("restart count is not canonical", exit_code=76)
    return array_job_id, position, slurm_job_id, restart_count


def _validate_restart_permit(
    launch: OneCellLaunchAuthority,
    *,
    receipt_sha256: str,
    task: OneCellLaunchTask,
    array_job_id: str,
    array_position: int,
    restart_count: int,
    handles: _LedgerHandles | None = None,
    require_live_manifest: bool = True,
) -> None:
    _require_exact_bool(require_live_manifest, label="require_live_manifest")
    if restart_count == 0:
        return
    previous = restart_count - 1
    name = f"{launch.launch_sha256}-p{array_position:020d}-r{previous:020d}-to-{restart_count:020d}.json"
    permits_path = os.path.join(launch.paths.submission_ledger_root, "requeue-permits")
    results_path = os.path.join(launch.paths.submission_ledger_root, "requeue-results")
    owned_handles = handles is None
    selected_handles = _open_ledger(launch, exclusive=False) if handles is None else handles
    try:
        permit_bytes = _read_ledger_member(
            selected_handles.permits,
            name,
            parent_path=permits_path,
            label="requeue permit",
        )
        result_bytes = _read_ledger_member(
            selected_handles.results,
            name,
            parent_path=results_path,
            label="requeue result",
        )
    finally:
        if owned_handles:
            _close_ledger(selected_handles)
    if permit_bytes is None:
        raise OneCellRunnerAuthorizationError("automatic restart lacks its exact permit", exit_code=77)
    value = _parse_canonical_json(permit_bytes, label="requeue permit", maximum=64 << 10)
    permit = _exact_dict(
        value,
        keys=(
            "profile",
            "launch_sha256",
            "submission_receipt_sha256",
            "scientific_identity_sha256",
            "array_job_id",
            "array_position",
            "slurm_job_id",
            "current_restart_count",
            "target_restart_count",
            "retry_cap",
            "generation",
            "checkpoint_manifest_path",
            "checkpoint_manifest_sha256",
            "scontrol_argv",
            "scontrol_argv_sha256",
        ),
        label="requeue permit",
    )
    argv = _exact_list(permit["scontrol_argv"], label="requeue permit argv", maximum=3)
    expected_argv = [launch.resources.scontrol_executable, "requeue", f"{array_job_id}_{array_position}"]
    if (
        permit["profile"] != _PERMIT_PROFILE
        or permit["launch_sha256"] != launch.launch_sha256
        or permit["submission_receipt_sha256"] != receipt_sha256
        or permit["scientific_identity_sha256"] != task.scientific_identity_sha256
        or permit["array_job_id"] != array_job_id
        or permit["array_position"] != array_position
        or type(permit["array_position"]) is not int
        or permit["current_restart_count"] != previous
        or type(permit["current_restart_count"]) is not int
        or permit["target_restart_count"] != restart_count
        or type(permit["target_restart_count"]) is not int
        or permit["retry_cap"] != launch.resources.max_requeues_per_task
        or type(permit["retry_cap"]) is not int
        or type(permit["generation"]) is not int
        or not 1 <= permit["generation"] <= _U64_MAX
        or argv != expected_argv
        or permit["scontrol_argv_sha256"] != _argv_digest(tuple(expected_argv), profile=_SCONTROL_ARGV_PROFILE)
    ):
        raise OneCellRunnerAuthorizationError("requeue permit does not bind this restart", exit_code=76)
    _require_positive_decimal(permit["slurm_job_id"], label="permit.slurm_job_id")
    if result_bytes is not None:
        result = _parse_requeue_result_record(result_bytes, permit_bytes=permit_bytes)
        if result["outcome"] == "rejected":
            raise OneCellRunnerAuthorizationError("requeue permit has a clear rejection result", exit_code=77)
    generation = int(permit["generation"])
    expected_task_directory = os.path.join(launch.paths.task_root, task.relative_task_directory)
    expected_manifest_path = os.path.join(
        expected_task_directory,
        f"checkpoint.{generation:020d}.manifest.json",
    )
    manifest_path = _require_abs_path(permit["checkpoint_manifest_path"], label="permit.checkpoint_manifest_path")
    manifest_sha256 = _require_hex(
        permit["checkpoint_manifest_sha256"],
        label="permit.checkpoint_manifest_sha256",
    )
    if manifest_path != expected_manifest_path:
        raise OneCellRunnerAuthorizationError("requeue permit checkpoint path is not exact", exit_code=76)
    if not require_live_manifest:
        return
    manifest_bytes = _read_regular_file(
        manifest_path,
        label="permitted checkpoint manifest",
        maximum=_MAX_JSON,
        expected_uid=os.geteuid(),
        expected_mode=0o600,
    )
    if _sha256(manifest_bytes) != manifest_sha256:
        raise OneCellRunnerAuthorizationError("requeue permit checkpoint digest changed", exit_code=76)


def _validate_restart_permit_integrity(
    launch: OneCellLaunchAuthority,
    *,
    receipt_sha256: str,
    task: OneCellLaunchTask,
    array_job_id: str,
    array_position: int,
    restart_count: int,
    handles: _LedgerHandles | None = None,
    require_live_manifest: bool = True,
) -> None:
    try:
        _validate_restart_permit(
            launch,
            receipt_sha256=receipt_sha256,
            task=task,
            array_job_id=array_job_id,
            array_position=array_position,
            restart_count=restart_count,
            handles=handles,
            require_live_manifest=require_live_manifest,
        )
    except OneCellRunnerAuthorizationError:
        raise
    except (OneCellRunnerValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError("durable restart permit or result is malformed", exit_code=76) from error


def _revalidate_authorized_execution_context(
    authorization: OneCellAuthorizedTask,
    *,
    claim_bytes: bytes,
    receipt_bytes: bytes,
) -> None:
    """Rebind held authorization to current ledger bytes and Slurm state."""

    _claim, receipt = _parse_stable_submission_handshake(
        claim_bytes,
        receipt_bytes,
        launch=authorization.launch,
    )
    if receipt["outcome"] != "accepted":
        raise OneCellRunnerAuthorizationError("current submission receipt is not accepted", exit_code=76)
    if (
        _sha256(claim_bytes) != authorization.submission_claim_sha256
        or _sha256(receipt_bytes) != authorization.submission_receipt_sha256
    ):
        raise OneCellRunnerAuthorizationError("authorized claim or receipt identity changed", exit_code=76)
    array_job_id, position, slurm_job_id, restart_count = _validate_slurm_execution_environment(
        authorization.launch,
        receipt=receipt,
    )
    if (
        array_job_id != authorization.slurm_array_job_id
        or position != authorization.array_position
        or slurm_job_id != authorization.slurm_job_id
        or restart_count != authorization.restart_count
    ):
        raise OneCellRunnerAuthorizationError("current Slurm mapping differs from authorization", exit_code=76)
    _validate_restart_permit_integrity(
        authorization.launch,
        receipt_sha256=authorization.submission_receipt_sha256,
        task=authorization.task,
        array_job_id=array_job_id,
        array_position=position,
        restart_count=restart_count,
    )


def _authorize_one_cell_slurm_task_impl(
    *,
    launch: OneCellLaunchAuthority,
    submission_claim_bytes: bytes,
    submission_receipt_bytes: bytes,
) -> OneCellAuthorizedTask:
    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    if selected.profile != _LAUNCH_PROFILE:
        raise OneCellRunnerAuthorizationError("fixture launch is permanently nonexecuting", exit_code=77)
    if type(submission_claim_bytes) is not bytes or type(submission_receipt_bytes) is not bytes:
        raise TypeError("submission claim and receipt must be built-in bytes")
    _revalidate_loaded_launch_runtime(selected)
    _claim, receipt = _parse_stable_submission_handshake(
        submission_claim_bytes,
        submission_receipt_bytes,
        launch=selected,
    )
    if receipt["outcome"] != "accepted" or receipt["array_job_id"] is None:
        raise OneCellRunnerAuthorizationError("only an accepted receipt is executable", exit_code=76)
    array_job_id, position, slurm_job_id, restart_count = _validate_slurm_execution_environment(
        selected,
        receipt=receipt,
    )
    task = selected.ordered_tasks[position]
    receipt_sha256 = _sha256(submission_receipt_bytes)
    _validate_restart_permit_integrity(
        selected,
        receipt_sha256=receipt_sha256,
        task=task,
        array_job_id=array_job_id,
        array_position=position,
        restart_count=restart_count,
    )
    attempt_id = f"{array_job_id}_{position:020d}-r{restart_count:020d}-j{slurm_job_id}"
    task_parts = tuple(task.relative_task_directory.split("/"))
    _validate_relative_path_limits(selected.paths.task_root, task_parts, label="authorized task path")
    _validate_relative_path_limits(
        selected.paths.attempt_root,
        task_parts + (attempt_id,),
        label="authorized attempt path",
    )
    task_directory = os.path.join(selected.paths.task_root, task.relative_task_directory)
    attempt_directory = os.path.join(
        selected.paths.attempt_root,
        task.wave,
        f"{task.task_index:020d}-{task.scientific_identity_sha256}",
        attempt_id,
    )
    return OneCellAuthorizedTask(
        launch=selected,
        array_position=position,
        task=task,
        scientific_identity_bytes=task.scientific_identity_bytes,
        scientific_identity_sha256=task.scientific_identity_sha256,
        slurm_array_job_id=array_job_id,
        slurm_array_task_id=str(position),
        slurm_job_id=slurm_job_id,
        restart_count=restart_count,
        attempt_id=attempt_id,
        task_directory=task_directory,
        attempt_directory=attempt_directory,
        submission_claim_sha256=_sha256(submission_claim_bytes),
        submission_receipt_sha256=receipt_sha256,
        requeue_target=f"{array_job_id}_{position}",
    )


def _submit_one_cell_launch_impl(*, launch: OneCellLaunchAuthority) -> OneCellSubmissionOutcome:
    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    if selected.profile != _LAUNCH_PROFILE:
        raise OneCellRunnerAuthorizationError("fixture launch is permanently nonexecuting", exit_code=77)
    _revalidate_loaded_launch_runtime(selected)
    argv = _sbatch_argv(selected)
    _validate_argv_path_limits(
        argv,
        reference_directories=(
            selected.paths.campaign_root,
            selected.authorization_path,
            selected.paths.authorized_run_directory,
            selected.paths.log_root,
            os.path.dirname(selected.resources.sbatch_executable),
            os.path.dirname(selected.paths.batch_script),
        ),
        label="sbatch argv",
    )
    claim_bytes = _submission_claim_bytes(selected, argv)
    claim_sha256 = _sha256(claim_bytes)
    argv_sha256 = _argv_digest(argv, profile=_SBATCH_ARGV_PROFILE)
    name = f"{selected.launch_sha256}.json"
    claims_path = os.path.join(selected.paths.submission_ledger_root, "claims")
    receipts_path = os.path.join(selected.paths.submission_ledger_root, "receipts")
    handles = _open_ledger(selected, exclusive=True)
    try:
        _validate_named_child_limits(
            handles.claims,
            claims_path,
            name,
            label="submission claim",
        )
        _preflight_link_record_limits(
            handles.receipts,
            name,
            parent_path=receipts_path,
            label="submission receipt",
        )
        existing_claim = _read_ledger_member(
            handles.claims,
            name,
            parent_path=claims_path,
            label="submission claim",
        )
        existing_receipt = _read_ledger_member(
            handles.receipts,
            name,
            parent_path=receipts_path,
            label="submission receipt",
        )
        if existing_claim is not None or existing_receipt is not None:
            raise OneCellRunnerAuthorizationError("launch has already been claimed or received", exit_code=77)
        _install_claim(handles.claims, name, claim_bytes, parent_path=claims_path)
        if (
            _read_ledger_member(
                handles.claims,
                name,
                parent_path=claims_path,
                label="submission claim",
            )
            != claim_bytes
        ):
            raise OneCellRunnerAuthorizationError("durable submission claim readback differs", exit_code=74)
        _revalidate_loaded_launch_runtime(selected)
        _validate_scheduler_tool_file(
            label="sbatch executable",
            path=selected.resources.sbatch_executable,
            owner_uid=selected.resources.sbatch_owner_uid,
            mode=selected.resources.sbatch_mode,
            size_bytes=selected.resources.sbatch_size_bytes,
            digest=selected.resources.sbatch_sha256,
        )
        _verify_ledger_handles(handles)
        result = _run_bounded_process(
            argv,
            environment=selected.resources.scheduler_environment,
            timeout_seconds=selected.resources.scheduler_timeout_seconds,
        )
        outcome, array_job_id = _classify_scheduler_result(result=result, submission=True)
        receipt_bytes = _submission_receipt_bytes(
            launch=selected,
            claim_sha256=claim_sha256,
            sbatch_argv_sha256=argv_sha256,
            result=result,
            outcome=outcome,
            array_job_id=array_job_id,
        )
        try:
            _install_link_record(
                handles.receipts,
                name,
                receipt_bytes,
                parent_path=receipts_path,
                label="submission receipt",
            )
            if (
                _read_ledger_member(
                    handles.receipts,
                    name,
                    parent_path=receipts_path,
                    label="submission receipt",
                )
                != receipt_bytes
            ):
                raise OneCellRunnerAuthorizationError("durable submission receipt readback differs", exit_code=74)
        except (OneCellRunnerAuthorizationError, OSError) as error:
            if outcome == "accepted":
                raise OneCellSchedulerError(
                    "scheduler accepted but its receipt was not durable",
                    exit_code=75,
                ) from error
            raise
    finally:
        _close_ledger(handles)
    receipt_sha256 = _sha256(receipt_bytes)
    if outcome != "accepted" or array_job_id is None:
        exit_code = 69 if outcome == "rejected" else 75
        raise OneCellSchedulerError(f"scheduler submission {outcome}", exit_code=exit_code)
    return OneCellSubmissionOutcome(
        disposition="accepted",
        launch_sha256=selected.launch_sha256,
        claim_path=os.path.join(selected.paths.submission_ledger_root, "claims", name),
        claim_sha256=claim_sha256,
        receipt_path=os.path.join(selected.paths.submission_ledger_root, "receipts", name),
        receipt_sha256=receipt_sha256,
        sbatch_argv_sha256=argv_sha256,
        array_job_id=array_job_id,
    )


def _run_lifecycle_state_machine_for_test(
    *,
    advance: object,
    publish: object,
    interruption_flag: object,
    final_present: bool = False,
) -> tuple[str, object]:
    """Drive inert injected checkpoint callables without importing Slice 7."""

    if not callable(advance) or not callable(publish):
        raise TypeError("advance and publish must be callable")
    if type(final_present) is not bool:
        raise TypeError("final_present must be a built-in Boolean")
    if not hasattr(interruption_flag, "requested"):
        raise TypeError("interruption_flag must expose requested")
    if final_present:
        final = publish()
        if getattr(final, "disposition", None) not in {"complete", "reused"}:
            raise OneCellRunnerValidationError("existing final did not validate as complete/reused")
        return str(final.disposition), final
    for _ in range(1_024):
        progress = advance()
        disposition = getattr(progress, "disposition", None)
        if disposition == "ready":
            continue
        if disposition == "requeue-required":
            return "requeue-required", progress
        if disposition != "terminal":
            raise OneCellRunnerValidationError("checkpoint advance returned an unknown disposition")
        # This is the sole final linearization check.  A request already seen
        # prevents publication; once publication begins, a valid final wins.
        if interruption_flag.requested is not False:
            return "requeue-required", progress
        final = publish()
        if getattr(final, "disposition", None) not in {"complete", "reused"}:
            raise OneCellRunnerValidationError("final publisher returned an unknown disposition")
        return str(final.disposition), final
    raise OneCellRunnerAuthorizationError("checkpoint lifecycle exceeded its bounded steps", exit_code=70)


def _probe_one_cell_checkpoint_import_without_hpc_for_test() -> None:
    """Privately attempt only the lazy Slice 7 import; perform no other action."""

    from .one_cell_checkpoint import OneCellCheckpointBinding as checkpoint_binding

    # Keep no module/class/callable alias in runner globals even when the probe
    # executes in an HPC-capable test environment.
    del checkpoint_binding


def _ensure_private_relative_directory(root: str, parts: tuple[str, ...]) -> str:
    selected_root = _require_abs_path(root, label="private path root")
    expected_root = _validate_private_directory(selected_root, label="private path root")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    root_chain, root_parts = _open_absolute_directory_chain(selected_root)
    chain = list(root_chain)
    named_parts = list(root_parts)
    private_start = len(root_chain) - 1
    current = selected_root

    def verify_private_chain() -> None:
        _verify_directory_chain(tuple(chain), tuple(named_parts))
        for descriptor in chain[private_start:]:
            info = os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode):
                raise OneCellRunnerAuthorizationError(
                    "private path retained descriptor is not a directory", exit_code=76
                )
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise OneCellRunnerAuthorizationError(
                    "private path retained metadata changed",
                    exit_code=77,
                )

    try:
        verify_private_chain()
        held_root = os.fstat(chain[-1])
        if (held_root.st_dev, held_root.st_ino) != (expected_root.st_dev, expected_root.st_ino):
            raise OneCellRunnerAuthorizationError("private path root identity changed", exit_code=76)
        for part in parts:
            if type(part) is not str or _SAFE_COMPONENT.fullmatch(part) is None or len(os.fsencode(part)) > 255:
                raise OneCellRunnerAuthorizationError("private path component is invalid", exit_code=76)
            parent = chain[-1]
            _validate_named_child_limits(parent, current, part, label="private path child")
            verify_private_chain()
            try:
                os.mkdir(part, 0o700, dir_fd=parent)
                os.fsync(parent)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=parent)
            info = os.fstat(child)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                os.close(child)
                raise OneCellRunnerAuthorizationError("private path child is not trusted", exit_code=77)
            named = os.stat(part, dir_fd=parent, follow_symlinks=False)
            if (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino):
                os.close(child)
                raise OneCellRunnerAuthorizationError("private path child identity changed", exit_code=76)
            chain.append(child)
            named_parts.append(part)
            current = os.path.join(current, part)
            verify_private_chain()
        verify_private_chain()
        return current
    except OSError as error:
        if error.errno in {errno.ENOENT, errno.ELOOP, errno.ENOTDIR, errno.EISDIR}:
            exit_code = 76
        elif error.errno in {errno.EACCES, errno.EPERM}:
            exit_code = 77
        else:
            exit_code = 74
        raise OneCellRunnerAuthorizationError("private directory creation failed", exit_code=exit_code) from error
    finally:
        _close_directory_chain(tuple(chain))


def _requeue_permit_bytes(
    authorization: OneCellAuthorizedTask,
    *,
    generation: int,
    checkpoint_manifest_path: str,
    checkpoint_manifest_sha256: str,
    argv: tuple[str, ...],
) -> bytes:
    target = authorization.restart_count + 1
    return _canonical_json(
        {
            "array_job_id": authorization.slurm_array_job_id,
            "array_position": authorization.array_position,
            "checkpoint_manifest_path": checkpoint_manifest_path,
            "checkpoint_manifest_sha256": checkpoint_manifest_sha256,
            "current_restart_count": authorization.restart_count,
            "generation": generation,
            "launch_sha256": authorization.launch.launch_sha256,
            "profile": _PERMIT_PROFILE,
            "retry_cap": authorization.launch.resources.max_requeues_per_task,
            "scientific_identity_sha256": authorization.scientific_identity_sha256,
            "scontrol_argv": list(argv),
            "scontrol_argv_sha256": _argv_digest(argv, profile=_SCONTROL_ARGV_PROFILE),
            "slurm_job_id": authorization.slurm_job_id,
            "submission_receipt_sha256": authorization.submission_receipt_sha256,
            "target_restart_count": target,
        }
    )


def _requeue_result_bytes(*, permit_sha256: str, result: _ProcessResult, outcome: str) -> bytes:
    return _canonical_json(
        {
            "outcome": outcome,
            "permit_sha256": permit_sha256,
            "profile": _RESULT_PROFILE,
            # Preserve timeout/spawn ambiguity through the schema's only
            # canonical representation for an unobserved completion.
            "returncode": None if result.timed_out or result.spawn_ambiguous else result.returncode,
            "stderr_hex": result.stderr.hex(),
            "stderr_overflow": result.stderr_overflow,
            "stdout_hex": result.stdout.hex(),
            "stdout_overflow": result.stdout_overflow,
        }
    )


def _revalidate_requeue_context_with_handles(
    authorization: OneCellAuthorizedTask,
    handles: _LedgerHandles,
) -> None:
    name = f"{authorization.launch.launch_sha256}.json"
    claims_path = os.path.join(authorization.launch.paths.submission_ledger_root, "claims")
    receipts_path = os.path.join(authorization.launch.paths.submission_ledger_root, "receipts")
    claim_bytes = _read_ledger_member(
        handles.claims,
        name,
        parent_path=claims_path,
        label="submission claim",
    )
    receipt_bytes = _read_ledger_member(
        handles.receipts,
        name,
        parent_path=receipts_path,
        label="submission receipt",
    )
    if claim_bytes is None or receipt_bytes is None:
        raise OneCellRunnerAuthorizationError("requeue context lacks its durable claim or receipt", exit_code=76)
    _claim, receipt = _parse_stable_submission_handshake(
        claim_bytes,
        receipt_bytes,
        launch=authorization.launch,
    )
    if (
        _sha256(claim_bytes) != authorization.submission_claim_sha256
        or _sha256(receipt_bytes) != authorization.submission_receipt_sha256
    ):
        raise OneCellRunnerAuthorizationError("requeue claim or receipt identity changed", exit_code=76)
    array_job_id, position, slurm_job_id, restart_count = _validate_slurm_execution_environment(
        authorization.launch,
        receipt=receipt,
    )
    if (
        array_job_id != authorization.slurm_array_job_id
        or position != authorization.array_position
        or slurm_job_id != authorization.slurm_job_id
        or restart_count != authorization.restart_count
    ):
        raise OneCellRunnerAuthorizationError("requeue Slurm mapping changed after authorization", exit_code=76)
    _validate_restart_permit_integrity(
        authorization.launch,
        receipt_sha256=authorization.submission_receipt_sha256,
        task=authorization.task,
        array_job_id=array_job_id,
        array_position=position,
        restart_count=restart_count,
        handles=handles,
        require_live_manifest=False,
    )


def _revalidate_requeue_context(authorization: OneCellAuthorizedTask) -> None:
    selected = _snapshot_record(authorization, OneCellAuthorizedTask)
    assert type(selected) is OneCellAuthorizedTask
    handles = _open_ledger(selected.launch, exclusive=False)
    try:
        _revalidate_requeue_context_with_handles(selected, handles)
    finally:
        _close_ledger(handles)


def _submit_requeue(
    authorization: OneCellAuthorizedTask,
    *,
    generation: int,
    checkpoint_manifest_path: str,
) -> None:
    launch = authorization.launch
    if authorization.restart_count >= launch.resources.max_requeues_per_task:
        raise OneCellRunnerAuthorizationError("requeue retry cap is exhausted", exit_code=77)
    _revalidate_loaded_launch_runtime(launch)
    _revalidate_requeue_context(authorization)
    selected_generation = _require_exact_int(generation, label="requeue generation", minimum=1, maximum=_U64_MAX)
    manifest_path = _require_abs_path(checkpoint_manifest_path, label="checkpoint manifest path")
    expected_manifest_path = os.path.join(
        authorization.task_directory,
        f"checkpoint.{selected_generation:020d}.manifest.json",
    )
    if manifest_path != expected_manifest_path:
        raise OneCellRunnerAuthorizationError("checkpoint manifest path does not match its generation", exit_code=76)
    manifest_bytes = _read_regular_file(
        manifest_path,
        label="checkpoint manifest",
        maximum=_MAX_JSON,
        expected_uid=os.geteuid(),
        expected_mode=0o600,
    )
    manifest_sha256 = _sha256(manifest_bytes)
    argv = (launch.resources.scontrol_executable, "requeue", authorization.requeue_target)
    _validate_argv_path_limits(
        argv,
        reference_directories=(
            launch.paths.campaign_root,
            os.path.dirname(launch.resources.scontrol_executable),
        ),
        label="scontrol argv",
    )
    _validate_scheduler_tool_file(
        label="scontrol executable",
        path=launch.resources.scontrol_executable,
        owner_uid=launch.resources.scontrol_owner_uid,
        mode=launch.resources.scontrol_mode,
        size_bytes=launch.resources.scontrol_size_bytes,
        digest=launch.resources.scontrol_sha256,
    )
    permit_bytes = _requeue_permit_bytes(
        authorization,
        generation=selected_generation,
        checkpoint_manifest_path=manifest_path,
        checkpoint_manifest_sha256=manifest_sha256,
        argv=argv,
    )
    permit_sha256 = _sha256(permit_bytes)
    target = authorization.restart_count + 1
    name = (
        f"{launch.launch_sha256}-p{authorization.array_position:020d}"
        f"-r{authorization.restart_count:020d}-to-{target:020d}.json"
    )
    permits_path = os.path.join(launch.paths.submission_ledger_root, "requeue-permits")
    results_path = os.path.join(launch.paths.submission_ledger_root, "requeue-results")
    handles = _open_ledger(launch, exclusive=True)
    try:
        _validate_named_child_limits(
            handles.permits,
            permits_path,
            name,
            label="requeue permit",
        )
        _preflight_link_record_limits(
            handles.results,
            name,
            parent_path=results_path,
            label="requeue result",
        )
        if (
            _read_ledger_member(
                handles.permits,
                name,
                parent_path=permits_path,
                label="requeue permit",
            )
            is not None
            or _read_ledger_member(
                handles.results,
                name,
                parent_path=results_path,
                label="requeue result",
            )
            is not None
        ):
            raise OneCellRunnerAuthorizationError("requeue attempt is already consumed", exit_code=77)
        _install_claim(handles.permits, name, permit_bytes, parent_path=permits_path)
        if (
            _read_ledger_member(
                handles.permits,
                name,
                parent_path=permits_path,
                label="requeue permit",
            )
            != permit_bytes
        ):
            raise OneCellRunnerAuthorizationError("durable requeue permit readback differs", exit_code=74)
        _revalidate_requeue_context_with_handles(authorization, handles)
        _revalidate_loaded_launch_runtime(launch)
        _validate_scheduler_tool_file(
            label="scontrol executable",
            path=launch.resources.scontrol_executable,
            owner_uid=launch.resources.scontrol_owner_uid,
            mode=launch.resources.scontrol_mode,
            size_bytes=launch.resources.scontrol_size_bytes,
            digest=launch.resources.scontrol_sha256,
        )
        _verify_ledger_handles(handles)
        result = _run_bounded_process(
            argv,
            environment=launch.resources.scheduler_environment,
            timeout_seconds=launch.resources.scheduler_timeout_seconds,
        )
        outcome, _ = _classify_scheduler_result(result=result, submission=False)
        result_bytes = _requeue_result_bytes(permit_sha256=permit_sha256, result=result, outcome=outcome)
        _install_link_record(
            handles.results,
            name,
            result_bytes,
            parent_path=results_path,
            label="requeue result",
        )
        if (
            _read_ledger_member(
                handles.results,
                name,
                parent_path=results_path,
                label="requeue result",
            )
            != result_bytes
        ):
            raise OneCellRunnerAuthorizationError("durable requeue result readback differs", exit_code=74)
    finally:
        _close_ledger(handles)
    if outcome != "accepted":
        raise OneCellSchedulerError(
            f"scheduler requeue {outcome}",
            exit_code=69 if outcome == "rejected" else 75,
        )


def load_one_cell_launch_authority(*, authorization_path: str) -> OneCellLaunchAuthority:
    """Load, authenticate, and deep-snapshot one committed launch authority."""

    return _load_one_cell_launch_authority_impl(authorization_path=authorization_path)


def list_one_cell_launch_tasks(*, launch: OneCellLaunchAuthority) -> tuple[OneCellLaunchTask, ...]:
    """Return deep snapshots of the exact launch rows in array order."""

    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    _validate_held_launch_projection(selected)
    return tuple(_snapshot_record(task, OneCellLaunchTask) for task in selected.ordered_tasks)  # type: ignore[return-value]


def explain_one_cell_launch_task(*, launch: OneCellLaunchAuthority, array_position: int) -> bytes:
    """Return the held compact scientific identity for one array position."""

    selected = _snapshot_record(launch, OneCellLaunchAuthority)
    assert type(selected) is OneCellLaunchAuthority
    _validate_held_launch_projection(selected)
    position = _require_exact_int(array_position, label="array_position", maximum=len(selected.ordered_tasks) - 1)
    return bytes(selected.ordered_tasks[position].scientific_identity_bytes)


def authorize_one_cell_slurm_task(
    *,
    launch: OneCellLaunchAuthority,
    submission_claim_bytes: bytes,
    submission_receipt_bytes: bytes,
) -> OneCellAuthorizedTask:
    """Bind one accepted durable submission receipt to the current Slurm task."""

    return _authorize_one_cell_slurm_task_impl(
        launch=launch,
        submission_claim_bytes=submission_claim_bytes,
        submission_receipt_bytes=submission_receipt_bytes,
    )


def run_one_cell_authorized_task(*, authorization: OneCellAuthorizedTask) -> OneCellRunnerOutcome:
    """Run one authorized task through deterministic checkpoint/final lifecycle."""

    return _run_one_cell_authorized_task_impl(authorization=authorization)


def submit_one_cell_launch(*, launch: OneCellLaunchAuthority) -> OneCellSubmissionOutcome:
    """Claim and submit one launch exactly once through the private ledger."""

    return _submit_one_cell_launch_impl(launch=launch)


# The implementation helpers are intentionally private so tests can exercise
# state machines without broadening the explicit-only package API.
def _load_one_cell_launch_authority_impl(*, authorization_path: str) -> OneCellLaunchAuthority:
    selected_path = _require_abs_path(authorization_path, label="authorization_path")
    _validate_private_directory(selected_path, label="authorization runtime directory")
    _validate_exact_directory_members(
        selected_path,
        expected=frozenset({"launch.json", "ordered-tasks.jsonl", "readback.json", "runtime-python.path"}),
        label="authorization runtime directory",
    )
    launch_path = os.path.join(selected_path, "launch.json")
    ordered_local_path = os.path.join(selected_path, "ordered-tasks.jsonl")
    readback_path = os.path.join(selected_path, "readback.json")
    sidecar_path = os.path.join(selected_path, "runtime-python.path")
    launch_bytes = _read_regular_file(launch_path, label="launch.json", maximum=_MAX_JSON, require_single_link=True)
    local_ordered_bytes = _read_regular_file(
        ordered_local_path,
        label="local ordered-tasks.jsonl",
        maximum=_MAX_JSONL,
        require_single_link=True,
    )
    launch_wire = _parse_launch_wire(launch_bytes)
    readback_bytes = _read_regular_file(
        readback_path, label="readback.json", maximum=_MAX_JSON, require_single_link=True
    )
    readback_wire = _parse_readback(readback_bytes)
    runtime_python_bytes = _read_regular_file(
        sidecar_path, label="runtime-python.path", maximum=4096, require_single_link=True
    )
    authorities = launch_wire["authorities"]
    launch_paths = launch_wire["paths"]
    assert type(authorities) is dict and type(launch_paths) is dict
    deployment_lock_reference = _parse_file_ref(
        authorities["deployment_lock"], label="launch.authorities.deployment_lock"
    )
    deployment_reference = _parse_file_ref(authorities["deployment"], label="launch.authorities.deployment")
    admission_reference = _parse_file_ref(authorities["admission"], label="launch.authorities.admission")
    if deployment_lock_reference["path"] != "campaigns/pre-one-cell-discovery-v1/deployment.lock.json":
        raise OneCellRunnerAuthorizationError("deployment lock bootstrap path is not exact", exit_code=76)
    if deployment_reference["path"] != "authorizations/pre-one-cell-discovery-v1/deployment/certificate.json":
        raise OneCellRunnerAuthorizationError("deployment certificate bootstrap path is not exact", exit_code=76)
    candidate_checkout = _require_abs_path(
        launch_paths["authorization_checkout"], label="candidate coordinator checkout"
    )
    inert_deployment_lock = _read_regular_file(
        os.path.join(candidate_checkout, str(deployment_lock_reference["path"])),
        label="inert deployment lock",
        maximum=_MAX_JSON,
        require_single_link=True,
    )
    inert_deployment = _read_regular_file(
        os.path.join(candidate_checkout, str(deployment_reference["path"])),
        label="inert deployment certificate",
        maximum=_MAX_JSON,
        require_single_link=True,
    )
    if (
        len(inert_deployment_lock) != deployment_lock_reference["size_bytes"]
        or _sha256(inert_deployment_lock) != deployment_lock_reference["sha256"]
        or len(inert_deployment) != deployment_reference["size_bytes"]
        or _sha256(inert_deployment) != deployment_reference["sha256"]
    ):
        raise OneCellRunnerAuthorizationError("inert deployment bytes differ from launch references", exit_code=76)
    deployment_lock_wire = _parse_deployment_lock(inert_deployment_lock)
    deployment_wire = _parse_deployment(inert_deployment)
    readback_repository = readback_wire["repository"]
    deployment_repository = deployment_wire["coordinator_repository"]
    assert type(readback_repository) is dict and type(deployment_repository) is dict
    if any(
        readback_repository[key] != deployment_repository[key]
        for key in ("repository_id", "remote_url", "fetch_refspec", "branch")
    ):
        raise OneCellRunnerAuthorizationError(
            "readback repository identity differs from deployment",
            exit_code=76,
        )
    paths = _paths_from_wires(
        launch_wire,
        deployment_wire,
        authorization_path=selected_path,
        runtime_python_bytes=runtime_python_bytes,
    )
    _validate_deployment_path_policy(paths, deployment_wire)
    resources = _resources_from_wires(launch_wire, deployment_wire)
    ordered_wire = launch_wire["ordered_tasks"]
    assert type(ordered_wire) is dict
    try:
        preflight_rows = _parse_canonical_jsonl(
            local_ordered_bytes,
            label="local ordered task path preflight",
            profile=_LAUNCH_TASK_PROFILE,
        )
        if ordered_wire["task_count"] != len(preflight_rows):
            raise OneCellRunnerAuthorizationError("local ordered task count differs from launch", exit_code=76)
        _preflight_generated_runtime_paths(
            paths=paths,
            resources=resources,
            launch_sha256=_sha256(launch_bytes),
            ordered_rows=preflight_rows,
            authorization_path=selected_path,
        )
    except OneCellRunnerAuthorizationError:
        raise
    except (OneCellRunnerValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError("local ordered task copy is malformed", exit_code=76) from error
    _validate_bootstrap_git_trust(paths, deployment_wire)
    launch_reference = _parse_file_ref(readback_wire["launch"], label="readback.launch")
    if launch_reference["path"] != launch_wire["self_path"]:
        raise OneCellRunnerAuthorizationError("launch self path differs from readback reference", exit_code=76)
    if os.path.basename(str(launch_wire["self_path"])) != "launch.json":
        raise OneCellRunnerAuthorizationError("launch authority filename is not exact", exit_code=76)
    bootstrap_authority = dict(launch_wire)
    bootstrap_authority["git_local_config"] = deployment_wire["git_local_config"]
    _validate_git_checkout(paths, readback_wire, bootstrap_authority)
    trusted_commit = str(launch_reference["commit"])
    _require_git_ancestor(
        paths,
        prerequisite=_SLICE_8B_COORDINATOR_AUTHORITY,
        trusted_commit=trusted_commit,
    )
    committed_launch = _git_blob(
        paths,
        launch_reference,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    if committed_launch != launch_bytes:
        raise OneCellRunnerAuthorizationError("local launch differs from committed readback bytes", exit_code=76)
    deployment_lock_bytes = _git_blob(
        paths,
        deployment_lock_reference,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    deployment_bytes = _git_blob(
        paths,
        deployment_reference,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    if deployment_lock_bytes != inert_deployment_lock or deployment_bytes != inert_deployment:
        raise OneCellRunnerAuthorizationError("committed deployment differs from inert bootstrap bytes", exit_code=76)
    admission_bytes = _git_blob(
        paths,
        admission_reference,
        maximum=_MAX_JSON,
        trusted_commit=trusted_commit,
    )
    admission_wire = _parse_admission(admission_bytes)
    branch_bytes: bytes | None = None
    branch_wire: dict[str, object] | None = None
    branch_reference: dict[str, object] | None = None
    if authorities["branch"] is not None:
        branch_reference = _parse_file_ref(authorities["branch"], label="launch.authorities.branch")
        branch_bytes = _git_blob(
            paths,
            branch_reference,
            maximum=_MAX_JSON,
            trusted_commit=trusted_commit,
        )
        branch_wire = _parse_branch(branch_bytes)
    _validate_authority_locations(
        launch_wire,
        launch_reference=launch_reference,
        branch=branch_wire,
    )
    _validate_authority_joins(
        launch=launch_wire,
        deployment_lock=deployment_lock_wire,
        deployment=deployment_wire,
        admission=admission_wire,
        branch=branch_wire,
    )
    _validate_software_checkout_and_batch(
        paths,
        deployment=deployment_wire,
        deployment_lock=deployment_lock_wire,
        launch=launch_wire,
    )
    _git_blob(
        paths,
        _parse_file_ref(deployment_wire["wheel"], label="deployment wheel"),
        maximum=_MAX_JSONL,
        trusted_commit=trusted_commit,
    )
    campaign = _campaign_from_deployment(paths, deployment_wire, trusted_commit=trusted_commit)
    _validate_protocol_checkout_and_campaign(
        paths,
        deployment=deployment_wire,
        deployment_lock=deployment_lock_wire,
        campaign=campaign,
    )
    _validate_branch_campaign_join(branch_wire, campaign=campaign)
    _validate_admission_evidence(
        paths,
        admission=admission_wire,
        configured_branch=branch_wire,
        launch_authorities=authorities,
        trusted_commit=trusted_commit,
        campaign=campaign,
    )
    ordered_reference = {
        "commit": launch_reference["commit"],
        "path": ordered_wire["path"],
        "sha256": ordered_wire["sha256"],
        "size_bytes": ordered_wire["size_bytes"],
    }
    ordered_bytes = _git_blob(
        paths,
        _parse_file_ref(ordered_reference, label="launch ordered tasks"),
        maximum=_MAX_JSONL,
        trusted_commit=trusted_commit,
    )
    if local_ordered_bytes != ordered_bytes:
        raise OneCellRunnerAuthorizationError("local ordered task copy differs from pushed Git blob", exit_code=76)
    tasks = _parse_ordered_tasks(
        ordered_bytes,
        campaign=campaign,
        deployment_lock_sha256=_sha256(deployment_lock_bytes),
        software_commit=str(authorities["source_commit"]),
        wheel_sha256=str(authorities["wheel_sha256"]),
        branch_decision_sha256=None if branch_bytes is None else _sha256(branch_bytes),
    )
    for task in tasks:
        task_parts = tuple(task.relative_task_directory.split("/"))
        _validate_relative_path_limits(paths.task_root, task_parts, label="task path")
        _validate_relative_path_limits(paths.attempt_root, task_parts, label="attempt task path")
    admission_lane = admission_wire["lane"]
    assert type(admission_lane) is dict
    map_identity = next(
        (item for item in campaign.task_maps if item.task_map_id == admission_lane["task_map_id"]), None
    )
    if (
        map_identity is None
        or map_identity.wave != admission_lane["wave"]
        or map_identity.role != admission_lane["role"]
        or map_identity.task_count != admission_lane["task_count"]
        or len(tasks) != ordered_wire["task_count"]
        or len(tasks) != admission_lane["task_count"]
        or any(task.task_map_id != admission_lane["task_map_id"] for task in tasks)
        or any(task.wave != admission_lane["wave"] or task.role != admission_lane["role"] for task in tasks)
    ):
        raise OneCellRunnerAuthorizationError("ordered tasks differ from launch/admission lane", exit_code=76)
    git_environment = _parse_string_map(
        launch_wire["git_environment"],
        keys=tuple(key for key, _ in _GIT_ENVIRONMENT),
        label="launch.git_environment",
    )
    launch = OneCellLaunchAuthority(
        authorization_path=selected_path,
        launch_bytes=launch_bytes,
        launch_sha256=_sha256(launch_bytes),
        launch_commit=str(launch_reference["commit"]),
        launch_path=str(launch_reference["path"]),
        launch_size_bytes=len(launch_bytes),
        profile=str(launch_wire["profile"]),
        launch_id=str(launch_wire["launch_id"]),
        lane=str(launch_wire["lane"]),
        campaign=campaign,
        deployment_lock_bytes=deployment_lock_bytes,
        deployment_lock_sha256=_sha256(deployment_lock_bytes),
        deployment_certificate_bytes=deployment_bytes,
        deployment_certificate_sha256=_sha256(deployment_bytes),
        admission_bytes=admission_bytes,
        admission_sha256=_sha256(admission_bytes),
        protocol_commit=str(authorities["protocol_commit"]),
        protocol_blob=str(deployment_lock_wire["protocol"]["blob"]),
        protocol_sha256=str(authorities["protocol_sha256"]),
        software_commit=str(authorities["source_commit"]),
        wheel_sha256=str(authorities["wheel_sha256"]),
        campaign_commit=str(authorities["campaign_commit"]),
        campaign_manifest_sha256=str(authorities["campaign_manifest_sha256"]),
        deployment_commit=str(deployment_reference["commit"]),
        admission_commit=str(admission_reference["commit"]),
        branch_decision_bytes=branch_bytes,
        branch_decision_sha256=None if branch_bytes is None else _sha256(branch_bytes),
        branch_commit=None if branch_reference is None else str(branch_reference["commit"]),
        branch_path=None if branch_reference is None else str(branch_reference["path"]),
        branch_size_bytes=None if branch_reference is None else int(branch_reference["size_bytes"]),
        mapping_profile=str(launch_wire["mapping"]["profile"]),
        ordered_tasks_profile=str(ordered_wire["profile"]),
        ordered_tasks_sha256=str(ordered_wire["sha256"]),
        ordered_tasks=tasks,
        readback_bytes=readback_bytes,
        readback_sha256=_sha256(readback_bytes),
        git_environment=git_environment,
        resources=resources,
        paths=paths,
    )
    if _ordered_tasks_bytes_for_cli(launch=launch) != ordered_bytes:
        raise OneCellRunnerAuthorizationError("ordered-task bytes do not round-trip", exit_code=76)
    _validate_runtime_files(launch, deployment_wire)
    return launch


def _require_sigusr1_blocked_at_lifecycle_entry() -> set[signal.Signals]:
    if not hasattr(signal, "pthread_sigmask"):
        raise OneCellRunnerAuthorizationError("pthread signal masking is unavailable", exit_code=78)
    prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    if signal.SIGUSR1 not in prior_mask:
        raise OneCellRunnerAuthorizationError("SIGUSR1 was not blocked at execute-route entry", exit_code=78)
    return prior_mask


def _run_one_cell_authorized_task_impl(*, authorization: OneCellAuthorizedTask) -> OneCellRunnerOutcome:
    if type(authorization) is not OneCellAuthorizedTask:
        raise TypeError("authorization must be an exact OneCellAuthorizedTask")
    if type(authorization.launch) is not OneCellLaunchAuthority:
        raise TypeError("authorization launch must be exact OneCellLaunchAuthority")
    # Exact fixture refusal precedes receipt I/O, signal changes, directory
    # creation, scientific-environment mutation, and checkpoint import.
    if authorization.launch.profile != _LAUNCH_PROFILE:
        raise OneCellRunnerAuthorizationError("fixture launch is permanently nonexecuting", exit_code=77)
    entry_signal_mask = _require_sigusr1_blocked_at_lifecycle_entry()
    selected = _snapshot_record(authorization, OneCellAuthorizedTask)
    assert type(selected) is OneCellAuthorizedTask
    claim_bytes, receipt_bytes = _load_submission_handshake_for_cli(launch=selected.launch)
    if (
        _sha256(claim_bytes) != selected.submission_claim_sha256
        or _sha256(receipt_bytes) != selected.submission_receipt_sha256
    ):
        raise OneCellRunnerAuthorizationError("authorized task receipt identity changed", exit_code=76)
    # Public authorization is a held snapshot, not a capability that survives
    # later ledger or scheduler-environment substitution.  Rebind it before
    # the first task/attempt directory may be created.
    _revalidate_authorized_execution_context(
        selected,
        claim_bytes=claim_bytes,
        receipt_bytes=receipt_bytes,
    )
    _revalidate_loaded_launch_runtime(selected.launch)
    # Every mutable root must already exist and be certified before either
    # private task path can be created.  Numba/checkpoint imports remain later
    # still; the descriptor-relative creators repeat root checks at use.
    _validate_private_directory(selected.launch.paths.task_root, label="task root")
    _validate_private_directory(selected.launch.paths.attempt_root, label="attempt root")
    _validate_private_directory(selected.launch.paths.temporary_root, label="temporary root")
    _validate_private_directory(selected.launch.paths.cache_root, label="cache root")
    _validate_private_directory(os.path.join(selected.launch.paths.cache_root, "numba"), label="Numba cache root")
    task = selected.task
    try:
        campaign_task = decode_one_cell_campaign_task(
            campaign=selected.launch.campaign,
            task_map_id=task.task_map_id,
            task_index=task.task_index,
        )
        expected_identity = explain_one_cell_campaign_task(
            campaign=selected.launch.campaign,
            task_map_id=task.task_map_id,
            task_index=task.task_index,
            deployment_lock_sha256=selected.launch.deployment_lock_sha256,
            software_commit=selected.launch.software_commit,
            wheel_sha256=selected.launch.wheel_sha256,
            branch_decision_sha256=selected.launch.branch_decision_sha256,
        )
    except (OneCellCampaignValidationError, TypeError, ValueError) as error:
        raise OneCellRunnerAuthorizationError("authorized campaign task no longer validates", exit_code=76) from error
    if expected_identity != selected.scientific_identity_bytes:
        raise OneCellRunnerAuthorizationError("authorized scientific identity no longer reproduces", exit_code=76)
    task_component = f"{task.task_index:020d}-{task.scientific_identity_sha256}"
    actual_task_directory = _ensure_private_relative_directory(
        selected.launch.paths.task_root,
        (task.wave, task_component),
    )
    if actual_task_directory != selected.task_directory:
        raise OneCellRunnerAuthorizationError("created task path differs from authorization", exit_code=76)
    actual_attempt_directory = _ensure_private_relative_directory(
        selected.launch.paths.attempt_root,
        (task.wave, task_component, selected.attempt_id),
    )
    if actual_attempt_directory != selected.attempt_directory:
        raise OneCellRunnerAuthorizationError("created attempt path differs from authorization", exit_code=76)
    scientific_environment = dict(selected.launch.resources.scientific_environment)
    old_environment = dict(os.environ)
    old_locale = locale.setlocale(locale.LC_ALL)
    mask_acquired = False
    prior_mask: set[signal.Signals] | None = None
    handler_installed = False
    prior_handler: object = None
    try:
        prior_mask = entry_signal_mask
        mask_acquired = True
        os.environ.clear()
        os.environ.update(scientific_environment)
        if locale.setlocale(locale.LC_ALL, "C") != "C":
            raise OneCellRunnerAuthorizationError("scientific locale did not resolve to C", exit_code=78)
        # The first checkpoint/Numba import is intentionally here, after all
        # public authority, receipt, Slurm, path, restart, and fixture gates.
        try:
            from .one_cell_checkpoint import (
                OneCellCheckpointBinding,
                OneCellInterruptionFlag,
                advance_one_cell_checkpoint_generation,
                publish_one_cell_final,
            )
        except ImportError as error:
            raise OneCellRunnerAuthorizationError(
                "authorized lifecycle requires the installed HPC checkpoint extra",
                exit_code=78,
            ) from error
        binding = OneCellCheckpointBinding(
            root_seed=campaign_task.root_seed,
            boundary_law=campaign_task.boundary_law,
            width=campaign_task.width,
            threshold_schedule=campaign_task.threshold_schedule,
            terminal_event_count=campaign_task.terminal_event_count,
            configuration_bytes=selected.launch.campaign.configuration_bytes,
            scientific_identity_bytes=selected.scientific_identity_bytes,
            software_commit=selected.launch.software_commit,
        )
        interruption_flag = OneCellInterruptionFlag()

        def request_interruption(_signum: int, _frame: object) -> None:
            interruption_flag.request()

        prior_handler = signal.getsignal(signal.SIGUSR1)
        signal.signal(signal.SIGUSR1, request_interruption)
        handler_installed = True
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGUSR1})

        def advance() -> object:
            return advance_one_cell_checkpoint_generation(
                task_directory=selected.task_directory,
                binding=binding,
                interruption_flag=interruption_flag,
            )

        def publish() -> object:
            return publish_one_cell_final(
                task_directory=selected.task_directory,
                binding=binding,
            )

        disposition, progress = _run_lifecycle_state_machine_for_test(
            advance=advance,
            publish=publish,
            interruption_flag=interruption_flag,
            final_present=os.path.lexists(os.path.join(selected.task_directory, "final.manifest.json")),
        )
        if disposition == "requeue-required":
            # Numerical execution ran under the exact scientific map.  The
            # fresh Slurm binding check and sole scontrol call require the
            # validated pre-scientific scheduler environment to be current
            # again; the outer finally restores it on every exit as well.
            os.environ.clear()
            os.environ.update(old_environment)
            _submit_requeue(
                selected,
                generation=int(progress.generation),
                checkpoint_manifest_path=str(progress.manifest_path),
            )
            return OneCellRunnerOutcome(
                disposition="requeue-submitted",
                array_position=selected.array_position,
                task_map_id=task.task_map_id,
                task_index=task.task_index,
                attempt_id=selected.attempt_id,
                task_directory=selected.task_directory,
                manifest_path=None,
                generation=int(progress.generation),
                checkpoint_count=int(progress.checkpoint_count),
                snapshot_count=int(progress.snapshot_count),
                used_fallback=bool(progress.used_fallback),
            )
        return OneCellRunnerOutcome(
            disposition="reused" if disposition == "reused" else "complete",
            array_position=selected.array_position,
            task_map_id=task.task_map_id,
            task_index=task.task_index,
            attempt_id=selected.attempt_id,
            task_directory=selected.task_directory,
            manifest_path=str(progress.manifest_path),
            generation=int(progress.generation),
            checkpoint_count=int(progress.checkpoint_count),
            snapshot_count=int(progress.snapshot_count),
            used_fallback=bool(progress.used_fallback),
        )
    except OneCellRunnerValidationError as error:
        raise OneCellRunnerAuthorizationError(
            "authorized checkpoint runtime violated its frozen lifecycle",
            exit_code=70,
        ) from error
    except OneCellRunnerAuthorizationError:
        raise
    except OneCellSchedulerError:
        raise
    except (TypeError, ValueError, OSError, RuntimeError) as error:
        raise OneCellRunnerAuthorizationError("authorized checkpoint lifecycle failed closed", exit_code=70) from error
    finally:
        if mask_acquired:
            try:
                signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
                if handler_installed:
                    signal.signal(signal.SIGUSR1, prior_handler)
                assert prior_mask is not None
                signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
            finally:
                os.environ.clear()
                os.environ.update(old_environment)
                locale.setlocale(locale.LC_ALL, old_locale)


def _fixture_authorized_task_for_test(*, directory: str) -> OneCellAuthorizedTask:
    """Build an inert fixture authorization for early-refusal tests."""

    launch = _fixture_launch_authority_for_test(directory=directory)
    task = launch.ordered_tasks[0]
    attempt_id = "17_00000000000000000000-r00000000000000000000-j29"
    task_directory = os.path.join(launch.paths.task_root, task.relative_task_directory)
    attempt_directory = os.path.join(
        launch.paths.attempt_root,
        task.wave,
        f"{task.task_index:020d}-{task.scientific_identity_sha256}",
        attempt_id,
    )
    return OneCellAuthorizedTask(
        launch=launch,
        array_position=0,
        task=task,
        scientific_identity_bytes=task.scientific_identity_bytes,
        scientific_identity_sha256=task.scientific_identity_sha256,
        slurm_array_job_id="17",
        slurm_array_task_id="0",
        slurm_job_id="29",
        restart_count=0,
        attempt_id=attempt_id,
        task_directory=task_directory,
        attempt_directory=attempt_directory,
        submission_claim_sha256="a" * 64,
        submission_receipt_sha256="b" * 64,
        requeue_target="17_0",
    )


for _record_type in _RECORD_TYPES:
    type.__setattr__(_record_type, "_runtime_sealed", True)

del _record_type
