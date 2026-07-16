"""Deterministic checkpoints for the certified PRE one-cell trajectory.

This explicit-only module owns the Slice 7 recovery codec, interruption latch,
and final-manifest boundary.  It intentionally performs no campaign routing,
signal installation, scheduler interaction, or configuration parsing.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from fcntl import LOCK_EX, LOCK_UN, flock

from .one_cell_boundary import OneCellBoundaryLaw
from .one_cell_trajectory import (
    OneCellScalarArmAccumulator,
    OneCellScalarTrajectory,
    start_one_cell_scalar_trajectory,
)

try:
    from .one_cell_trajectory_compiled import advance_one_cell_compiled_chunk
except ImportError as error:  # pragma: no cover - exercised by import smoke tests
    raise ImportError(
        "tetris_ballistic.engine.one_cell_checkpoint requires a compatible "
        "Numba installation; install the 'tetris_ballistic[hpc]' extra"
    ) from error

__all__ = [
    "OneCellCheckpointValidationError",
    "OneCellCheckpointBinding",
    "OneCellCheckpointSchedule",
    "OneCellCheckpointProgress",
    "OneCellInterruptionFlag",
    "build_one_cell_checkpoint_schedule",
    "advance_one_cell_checkpoint_generation",
    "publish_one_cell_final",
]

_U64_LIMIT = 1 << 64
_U64_MAX = _U64_LIMIT - 1
_U128_LIMIT = 1 << 128
_OPAQUE_LIMIT = 1 << 20
_JSON_LIMIT = 1 << 20
_ARRAY_LIMIT = 64 << 20
_CADENCE = 1 << 20
_SNAPSHOT_INDICES = (0, 34, 68, 102, 136, 170, 204, 238, 273, 307, 341, 375, 409, 443, 477, 511)
_PRIMARY = (0, 1, 2, 5, 10, 25, 50, 100)
_B1 = (0, 5, 50, 100)
_B2_FULL = (5, 50, 90, 95, 98, 99)
_B2_HIGH = (90, 95, 98, 99)
_SCHEDULES = (_PRIMARY, _B1, _B2_FULL, _B2_HIGH)
_LAWS = (
    OneCellBoundaryLaw.PERIODIC,
    OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
    OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC,
)
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_GENERATION_TEXT = r"[0-9]{20}"
_CHECKPOINT_SUFFIX = r"(?:configuration\.bin|scientific-identity\.bin|state\.json|arrays\.u64le|manifest\.json)"
_CHECKPOINT_NAME = re.compile(rf"checkpoint\.({_GENERATION_TEXT})\.({_CHECKPOINT_SUFFIX})\Z")
_FINAL_NAMES = {
    "final.configuration.bin",
    "final.scientific-identity.bin",
    "final.state.json",
    "final.arrays.u64le",
    "final.manifest.json",
}
_TEMP_NAME = re.compile(
    rf"\.(checkpoint\.({_GENERATION_TEXT})\.{_CHECKPOINT_SUFFIX}|final\.(?:configuration\.bin|scientific-identity\.bin|state\.json|arrays\.u64le|manifest\.json))\.[0-9a-f]{{32}}\.tmp\Z"
)
_MEMBER_KEYS = ("arrays", "configuration", "scientific_identity", "state")
_RECOVERY_SECTION_NAMES = (
    "current_heights",
    "current_rows",
    "current_histogram",
    "checkpoint_event_counts",
    "checkpoint_rows",
    "snapshot_checkpoint_indices",
    "snapshot_event_counts",
    "snapshot_heights",
)
_FINAL_SECTION_NAMES = (
    "checkpoint_event_counts",
    "checkpoint_rows",
    "snapshot_checkpoint_indices",
    "snapshot_event_counts",
    "snapshot_heights",
    "final_histogram",
)

_BOUNDARY_LAW_TYPE = OneCellBoundaryLaw
_ARM_TYPE = OneCellScalarArmAccumulator
_TRAJECTORY_TYPE = OneCellScalarTrajectory
_CERTIFIED_START_TRAJECTORY = start_one_cell_scalar_trajectory
_CERTIFIED_COMPILED_ADVANCE = advance_one_cell_compiled_chunk
_CAPTURED_START_TRAJECTORY = _CERTIFIED_START_TRAJECTORY
_CAPTURED_COMPILED_ADVANCE = _CERTIFIED_COMPILED_ADVANCE


class OneCellCheckpointValidationError(RuntimeError):
    """A task artifact could not be trusted as Slice 7 state."""


class _CandidateError(Exception):
    """A matching committed recovery candidate is corrupt."""


class _FatalArtifact(Exception):
    """A task artifact crosses the fail-closed identity/security boundary."""


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _require_uint(value: object, *, maximum: int, label: str) -> int:
    result = _require_int(value, label=label)
    if not 0 <= result <= maximum:
        raise ValueError(f"{label} is outside its frozen unsigned range")
    return result


def _canonical_json(value: object, *, newline: bool = False) -> bytes:
    result = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return result + (b"\n" if newline else b"")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _rounded_root_power(*, base: int, exponent: int) -> int:
    """Return round-half-up(base**(exponent/383)) with exact authority."""

    scaled = (1 << 383) * pow(base, exponent)
    hint = max(1, min(base, int(math.exp(math.log(base) * exponent / 383.0) + 0.5)))

    def too_high(candidate: int) -> bool:
        return scaled < pow(2 * candidate - 1, 383)

    def too_low(candidate: int) -> bool:
        return scaled >= pow(2 * candidate + 1, 383)

    if not too_high(hint) and not too_low(hint):
        return hint
    if too_high(hint):
        high = hint
        step = 1
        low = max(0, high - step)
        while low > 0 and too_high(low):
            high = low
            step *= 2
            low = max(0, high - step)
    else:
        low = hint
        step = 1
        high = min(base, low + step)
        while high < base and too_low(high):
            low = high
            step *= 2
            high = min(base, low + step)
    while low <= high:
        candidate = (low + high) // 2
        if too_high(candidate):
            high = candidate - 1
        elif too_low(candidate):
            low = candidate + 1
        else:
            return candidate
    raise AssertionError("exact checkpoint rounding candidate was not found")


def _schedule_values(terminal: int) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], str, str]:
    midpoint = (terminal + 1) // 2
    early_terminal = midpoint - 1
    early = [1]
    for index in range(1, 384):
        rounded = _rounded_root_power(base=early_terminal, exponent=index)
        early.append(min(early_terminal - (383 - index), max(early[-1] + 1, rounded)))
    late = tuple(midpoint + index * (terminal - midpoint) // 127 for index in range(128))
    checkpoints = tuple(early) + late
    snapshots = tuple(checkpoints[index] for index in _SNAPSHOT_INDICES)
    checkpoint_digest = _sha256(
        _canonical_json(
            {
                "event_counts": checkpoints,
                "profile": "tetris-pre-one-cell-checkpoint-vector@1",
            }
        )
    )
    snapshot_digest = _sha256(
        _canonical_json(
            {
                "checkpoint_indices": _SNAPSHOT_INDICES,
                "event_counts": snapshots,
                "profile": "tetris-pre-one-cell-snapshot-vector@1",
            }
        )
    )
    return checkpoints, _SNAPSHOT_INDICES, snapshots, checkpoint_digest, snapshot_digest


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellCheckpointSchedule:
    terminal_event_count: int
    checkpoint_event_counts: tuple[int, ...]
    snapshot_checkpoint_indices: tuple[int, ...]
    snapshot_event_counts: tuple[int, ...]
    checkpoint_vector_sha256: str
    snapshot_vector_sha256: str

    def __post_init__(self) -> None:
        terminal = _require_uint(self.terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
        if terminal < 769:
            raise ValueError("terminal_event_count must be at least 769")
        if type(self.checkpoint_event_counts) is not tuple:
            raise TypeError("checkpoint_event_counts must be a built-in tuple")
        if type(self.snapshot_checkpoint_indices) is not tuple:
            raise TypeError("snapshot_checkpoint_indices must be a built-in tuple")
        if type(self.snapshot_event_counts) is not tuple:
            raise TypeError("snapshot_event_counts must be a built-in tuple")
        if any(type(value) is not int for value in self.checkpoint_event_counts):
            raise TypeError("checkpoint_event_counts entries must be built-in integers")
        if any(type(value) is not int for value in self.snapshot_checkpoint_indices):
            raise TypeError("snapshot_checkpoint_indices entries must be built-in integers")
        if any(type(value) is not int for value in self.snapshot_event_counts):
            raise TypeError("snapshot_event_counts entries must be built-in integers")
        if type(self.checkpoint_vector_sha256) is not str or type(self.snapshot_vector_sha256) is not str:
            raise TypeError("schedule digests must be built-in strings")
        expected = _schedule_values(terminal)
        actual = (
            self.checkpoint_event_counts,
            self.snapshot_checkpoint_indices,
            self.snapshot_event_counts,
            self.checkpoint_vector_sha256,
            self.snapshot_vector_sha256,
        )
        if actual != expected:
            raise ValueError("schedule fields do not match the frozen exact construction")


def build_one_cell_checkpoint_schedule(*, terminal_event_count: int) -> OneCellCheckpointSchedule:
    terminal = _require_uint(terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
    if terminal < 769:
        raise ValueError("terminal_event_count must be at least 769")
    values = _schedule_values(terminal)
    return OneCellCheckpointSchedule(
        terminal_event_count=terminal,
        checkpoint_event_counts=values[0],
        snapshot_checkpoint_indices=values[1],
        snapshot_event_counts=values[2],
        checkpoint_vector_sha256=values[3],
        snapshot_vector_sha256=values[4],
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellCheckpointBinding:
    root_seed: int
    boundary_law: OneCellBoundaryLaw
    width: int
    threshold_schedule: tuple[int, ...]
    terminal_event_count: int
    configuration_bytes: bytes
    scientific_identity_bytes: bytes
    software_commit: str

    def __post_init__(self) -> None:
        root = _require_uint(self.root_seed, maximum=_U128_LIMIT - 1, label="root_seed")
        if type(self.boundary_law) is not _BOUNDARY_LAW_TYPE:
            raise TypeError("boundary_law must be an exact OneCellBoundaryLaw")
        if self.boundary_law not in _LAWS:
            raise ValueError("boundary_law is outside the frozen PRE laws")
        width = _require_int(self.width, label="width")
        if not 3 <= width <= 1024:
            raise ValueError("width must lie in [3, 1024]")
        if type(self.threshold_schedule) is not tuple:
            raise TypeError("threshold_schedule must be a built-in tuple")
        if any(type(value) is not int for value in self.threshold_schedule):
            raise TypeError("threshold_schedule entries must be built-in integers")
        if self.threshold_schedule not in _SCHEDULES:
            raise ValueError("threshold_schedule is not one of the four frozen schedules")
        terminal = _require_uint(self.terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
        if terminal < 769:
            raise ValueError("terminal_event_count must be at least 769")
        if width * terminal >= _U64_LIMIT or width * terminal * terminal >= _U128_LIMIT:
            raise ValueError("width and terminal_event_count exceed the exact protocol products")
        for label, value in (
            ("configuration_bytes", self.configuration_bytes),
            ("scientific_identity_bytes", self.scientific_identity_bytes),
        ):
            if type(value) is not bytes:
                raise TypeError(f"{label} must be built-in bytes")
            if not value or len(value) > _OPAQUE_LIMIT:
                raise ValueError(f"{label} must contain 1 through {_OPAQUE_LIMIT} bytes")
        if type(self.software_commit) is not str:
            raise TypeError("software_commit must be a built-in string")
        if _HEX40.fullmatch(self.software_commit) is None:
            raise ValueError("software_commit must be 40 lowercase hexadecimal characters")
        build_one_cell_checkpoint_schedule(terminal_event_count=terminal)
        _CAPTURED_START_TRAJECTORY(
            root_seed=root,
            boundary_law=self.boundary_law,
            width=width,
            threshold_schedule=self.threshold_schedule,
        )


def _snapshot_trajectory(value: object) -> OneCellScalarTrajectory:
    if type(value) is not _TRAJECTORY_TYPE:
        raise TypeError("trajectory must be an exact OneCellScalarTrajectory")
    return _TRAJECTORY_TYPE(
        root_seed=value.root_seed,
        boundary_law=value.boundary_law,
        width=value.width,
        event_count=value.event_count,
        arms=value.arms,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellCheckpointProgress:
    disposition: str
    trajectory: OneCellScalarTrajectory
    generation: int
    checkpoint_count: int
    snapshot_count: int
    used_fallback: bool
    manifest_path: str

    def __post_init__(self) -> None:
        if type(self.disposition) is not str:
            raise TypeError("disposition must be a built-in string")
        if self.disposition not in {"ready", "requeue-required", "terminal", "complete", "reused"}:
            raise ValueError("disposition is outside the frozen progress vocabulary")
        trajectory = _snapshot_trajectory(self.trajectory)
        generation = _require_uint(self.generation, maximum=_U64_MAX, label="generation")
        checkpoint_count = _require_uint(self.checkpoint_count, maximum=512, label="checkpoint_count")
        snapshot_count = _require_uint(self.snapshot_count, maximum=16, label="snapshot_count")
        if type(self.used_fallback) is not bool:
            raise TypeError("used_fallback must be a built-in Boolean")
        if type(self.manifest_path) is not str:
            raise TypeError("manifest_path must be a built-in string")
        if not os.path.isabs(self.manifest_path) or os.path.normpath(self.manifest_path) != self.manifest_path:
            raise ValueError("manifest_path must be an absolute normalized string")
        if self.disposition in {"complete", "reused"}:
            if generation != 0 or checkpoint_count != 512 or snapshot_count != 16:
                raise ValueError("final progress requires generation zero and complete observation counts")
            if self.disposition == "reused" and self.used_fallback:
                raise ValueError("reused progress cannot report recovery fallback")
        elif generation < 1:
            raise ValueError("recovery progress requires a positive generation")
        object.__setattr__(self, "trajectory", trajectory)


class OneCellInterruptionFlag:
    """Minimal signal-compatible, idempotent interruption latch."""

    __slots__ = ("_requested",)

    def __init__(self) -> None:
        self._requested = False

    @property
    def requested(self) -> bool:
        return self._requested

    def request(self) -> None:
        self._requested = True

    def __call__(self, signum: object, frame: object) -> None:
        self._requested = True


@dataclass(frozen=True, slots=True)
class _RecoveryState:
    generation: int
    trajectory: OneCellScalarTrajectory
    checkpoint_event_counts: tuple[int, ...]
    checkpoint_rows: tuple[tuple[tuple[int, ...], ...], ...]
    snapshot_checkpoint_indices: tuple[int, ...]
    snapshot_event_counts: tuple[int, ...]
    snapshot_heights: tuple[tuple[tuple[int, ...], ...], ...]


def _assert_authority() -> None:
    if (
        _CERTIFIED_START_TRAJECTORY is not _CAPTURED_START_TRAJECTORY
        or _CERTIFIED_COMPILED_ADVANCE is not _CAPTURED_COMPILED_ADVANCE
        or _BOUNDARY_LAW_TYPE is not OneCellBoundaryLaw
        or _ARM_TYPE is not OneCellScalarArmAccumulator
        or _TRAJECTORY_TYPE is not OneCellScalarTrajectory
    ):
        raise AssertionError("captured Slice 5/6 checkpoint authority has been rebound")


def _snapshot_binding(value: object) -> OneCellCheckpointBinding:
    if type(value) is not OneCellCheckpointBinding:
        raise TypeError("binding must be an exact OneCellCheckpointBinding")
    try:
        return OneCellCheckpointBinding(
            root_seed=value.root_seed,
            boundary_law=value.boundary_law,
            width=value.width,
            threshold_schedule=value.threshold_schedule,
            terminal_event_count=value.terminal_event_count,
            configuration_bytes=value.configuration_bytes,
            scientific_identity_bytes=value.scientific_identity_bytes,
            software_commit=value.software_commit,
        )
    except AttributeError as error:
        raise TypeError("binding must be fully initialized") from error


def _request_identity(binding: OneCellCheckpointBinding, schedule: OneCellCheckpointSchedule) -> dict[str, object]:
    record = {
        "boundary_law": binding.boundary_law.value,
        "checkpoint_vector_sha256": schedule.checkpoint_vector_sha256,
        "configuration_sha256": _sha256(binding.configuration_bytes),
        "configuration_size_bytes": len(binding.configuration_bytes),
        "counter_fields": ["event-ordinal-zero-based", "rejection-ordinal", "zero", "zero"],
        "coupling_group": "pre-one-cell-discovery-v1",
        "rng_algorithm": "semantic-philox4x64-10-v1",
        "root_seed_decimal": str(binding.root_seed),
        "scientific_identity_sha256": _sha256(binding.scientific_identity_bytes),
        "scientific_identity_size_bytes": len(binding.scientific_identity_bytes),
        "snapshot_vector_sha256": schedule.snapshot_vector_sha256,
        "software_commit": binding.software_commit,
        "stream_order": ["launch", "contact"],
        "terminal_event_count": binding.terminal_event_count,
        "threshold_schedule": list(binding.threshold_schedule),
        "width": binding.width,
    }
    return {
        "profile": "tetris-pre-one-cell-checkpoint-request@1",
        "record": record,
        "sha256": _sha256(_canonical_json(record)),
    }


def _row_from_arm(arm: OneCellScalarArmAccumulator) -> tuple[int, ...]:
    square = arm.height_square_sum
    return (
        arm.height_sum,
        square >> 64,
        square & _U64_MAX,
        arm.void_volume,
        arm.endpoint_selected_count,
        arm.positive_gap_trigger_count,
        arm.gap_sum,
        arm.maximum_gap,
        *arm.causal_counts,
        *arm.causal_gap_sums,
        *arm.endpoint_equality_mask_counts[0],
        *arm.endpoint_equality_mask_counts[1],
        arm.seam_equality_count or 0,
    )


def _rows_from_trajectory(trajectory: OneCellScalarTrajectory) -> tuple[tuple[int, ...], ...]:
    return tuple(_row_from_arm(arm) for arm in trajectory.arms)


def _histogram_words(trajectory: OneCellScalarTrajectory) -> tuple[int, ...]:
    return tuple(
        value
        for arm_index, arm in enumerate(trajectory.arms)
        for gap, count in arm.gap_histogram
        for value in (arm_index, gap, count)
    )


def _arm_from_words(
    *,
    binding: OneCellCheckpointBinding,
    threshold: int,
    event_count: int,
    heights: tuple[int, ...],
    row: tuple[int, ...],
    histogram: tuple[tuple[int, int], ...],
) -> OneCellScalarArmAccumulator:
    if len(row) != 33:
        raise ValueError("an arm row must contain exactly 33 words")
    square = (row[1] << 64) | row[2]
    return _ARM_TYPE(
        boundary_law=binding.boundary_law,
        threshold=threshold,
        heights=heights,
        event_count=event_count,
        height_sum=row[0],
        height_square_sum=square,
        void_volume=row[3],
        endpoint_selected_count=row[4],
        positive_gap_trigger_count=row[5],
        gap_sum=row[6],
        maximum_gap=row[7],
        causal_counts=tuple(row[8:12]),
        causal_gap_sums=tuple(row[12:16]),
        endpoint_equality_mask_counts=(tuple(row[16:24]), tuple(row[24:32])),
        gap_histogram=histogram,
        seam_equality_count=row[32] if binding.boundary_law is OneCellBoundaryLaw.PERIODIC else None,
    )


def _trajectory_from_words(
    *,
    binding: OneCellCheckpointBinding,
    event_count: int,
    heights: tuple[tuple[int, ...], ...],
    rows: tuple[tuple[int, ...], ...],
    histogram_words: tuple[int, ...],
) -> OneCellScalarTrajectory:
    arm_count = len(binding.threshold_schedule)
    if len(heights) != arm_count or len(rows) != arm_count or len(histogram_words) % 3:
        raise ValueError("current trajectory arrays have malformed dimensions")
    histograms: list[list[tuple[int, int]]] = [[] for _ in range(arm_count)]
    previous: tuple[int, int] | None = None
    for offset in range(0, len(histogram_words), 3):
        arm_index, gap, count = histogram_words[offset : offset + 3]
        if arm_index >= arm_count or count < 1:
            raise ValueError("histogram row is outside the current arm domain")
        key = (arm_index, gap)
        if previous is not None and key <= previous:
            raise ValueError("histogram rows must be strictly lexicographically sorted")
        previous = key
        histograms[arm_index].append((gap, count))
    arms = tuple(
        _arm_from_words(
            binding=binding,
            threshold=threshold,
            event_count=event_count,
            heights=heights[index],
            row=rows[index],
            histogram=tuple(histograms[index]),
        )
        for index, threshold in enumerate(binding.threshold_schedule)
    )
    return _TRAJECTORY_TYPE(
        root_seed=binding.root_seed,
        boundary_law=binding.boundary_law,
        width=binding.width,
        event_count=event_count,
        arms=arms,
    )


def _validate_observation_row(
    row: tuple[int, ...],
    *,
    event_count: int,
    threshold: int,
    periodic: bool,
    width: int,
    heights: tuple[int, ...] | None = None,
) -> None:
    if len(row) != 33 or any(type(word) is not int or not 0 <= word <= _U64_MAX for word in row):
        raise ValueError("observation row is not 33 unsigned-64 words")
    height_sum, high, low, void, endpoint, trigger, gap_sum, maximum = row[:8]
    square = (high << 64) | low
    causal = row[8:12]
    causal_gap = row[12:16]
    false_equal = row[16:24]
    true_equal = row[24:32]
    seam = row[32]
    if height_sum - event_count != void or gap_sum != void:
        raise ValueError("observation height/void/gap identity failed")
    if height_sum > width * event_count or square > width * event_count * event_count:
        raise ValueError("observation height moments exceed their exact geometric bounds")
    if width * square - height_sum * height_sum < 0:
        raise ValueError("observation roughness numerator is negative")
    if trigger > endpoint or endpoint > event_count:
        raise ValueError("observation endpoint/trigger order failed")
    if sum(causal) != event_count or causal[0] != event_count - trigger or sum(causal[1:]) != trigger:
        raise ValueError("observation causal projection failed")
    if causal_gap[0] != 0 or sum(causal_gap) != void:
        raise ValueError("observation causal-gap projection failed")
    if false_equal[0] != 0 or true_equal[0] != 0:
        raise ValueError("observation equality mask zero is unreachable")
    if sum(false_equal) + sum(true_equal) != event_count or sum(true_equal) != endpoint:
        raise ValueError("observation equality projection failed")
    if threshold == 0 and (endpoint != 0 or trigger != 0 or void != 0 or height_sum != event_count):
        raise ValueError("zero-percent observation law failed")
    if threshold == 100 and endpoint != event_count:
        raise ValueError("hundred-percent observation law failed")
    if (not periodic and seam != 0) or seam > event_count or maximum > void:
        raise ValueError("observation seam or maximum-gap bound failed")
    if heights is not None:
        if sum(heights) != height_sum or sum(value * value for value in heights) != square:
            raise ValueError("snapshot height projections disagree with its row")
        if len(heights) * square - height_sum * height_sum < 0:
            raise ValueError("snapshot roughness numerator is negative")


def _validate_recovery_state(
    state: _RecoveryState,
    *,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
) -> _RecoveryState:
    trajectory = _snapshot_trajectory(state.trajectory)
    if (
        trajectory.root_seed != binding.root_seed
        or trajectory.boundary_law is not binding.boundary_law
        or trajectory.width != binding.width
        or trajectory.threshold_schedule != binding.threshold_schedule
        or trajectory.event_count > binding.terminal_event_count
    ):
        raise ValueError("recovery trajectory does not match its binding")
    checkpoint_count = len(state.checkpoint_event_counts)
    snapshot_count = len(state.snapshot_checkpoint_indices)
    if state.checkpoint_event_counts != schedule.checkpoint_event_counts[:checkpoint_count]:
        raise ValueError("checkpoint event counts are not the exact schedule prefix")
    if state.snapshot_checkpoint_indices != schedule.snapshot_checkpoint_indices[:snapshot_count]:
        raise ValueError("snapshot indices are not the exact schedule prefix")
    if state.snapshot_event_counts != schedule.snapshot_event_counts[:snapshot_count]:
        raise ValueError("snapshot event counts are not the exact schedule prefix")
    if len(state.checkpoint_rows) != checkpoint_count or len(state.snapshot_heights) != snapshot_count:
        raise ValueError("observation payload counts disagree with their vectors")
    if checkpoint_count and state.checkpoint_event_counts[-1] > trajectory.event_count:
        raise ValueError("checkpoint prefix extends beyond current trajectory")
    due_checkpoints = sum(value <= trajectory.event_count for value in schedule.checkpoint_event_counts)
    if checkpoint_count != due_checkpoints:
        raise ValueError("recovery omitted a due scientific checkpoint")
    due_snapshots = sum(value <= trajectory.event_count for value in schedule.snapshot_event_counts)
    if snapshot_count != due_snapshots:
        raise ValueError("recovery omitted a due scientific snapshot")
    periodic = binding.boundary_law is OneCellBoundaryLaw.PERIODIC
    for checkpoint_index, rows in enumerate(state.checkpoint_rows):
        if len(rows) != len(binding.threshold_schedule):
            raise ValueError("checkpoint row arm count is malformed")
        event_count = state.checkpoint_event_counts[checkpoint_index]
        for row, threshold in zip(rows, binding.threshold_schedule):
            _validate_observation_row(
                row,
                event_count=event_count,
                threshold=threshold,
                periodic=periodic,
                width=binding.width,
            )
        if any(lower[4] > upper[4] for lower, upper in zip(rows, rows[1:])):
            raise ValueError("checkpoint endpoint counts violate threshold nesting")
    for snapshot_index, heights_by_arm in enumerate(state.snapshot_heights):
        if len(heights_by_arm) != len(binding.threshold_schedule):
            raise ValueError("snapshot arm count is malformed")
        checkpoint_index = state.snapshot_checkpoint_indices[snapshot_index]
        rows = state.checkpoint_rows[checkpoint_index]
        event_count = state.snapshot_event_counts[snapshot_index]
        for heights, row, threshold in zip(heights_by_arm, rows, binding.threshold_schedule):
            if len(heights) != binding.width or any(
                type(value) is not int or not 0 <= value <= event_count for value in heights
            ):
                raise ValueError("snapshot height shape is malformed")
            _validate_observation_row(
                row,
                event_count=event_count,
                threshold=threshold,
                periodic=periodic,
                width=binding.width,
                heights=heights,
            )
        for lower, upper in zip(heights_by_arm, heights_by_arm[1:]):
            if any(left > right for left, right in zip(lower, upper)):
                raise ValueError("snapshot arms violate threshold nesting")
    if checkpoint_count and state.checkpoint_event_counts[-1] == trajectory.event_count:
        if state.checkpoint_rows[-1] != _rows_from_trajectory(trajectory):
            raise ValueError("current rows disagree with the current checkpoint row")
    if snapshot_count and state.snapshot_event_counts[-1] == trajectory.event_count:
        current_heights = tuple(arm.heights for arm in trajectory.arms)
        if state.snapshot_heights[-1] != current_heights:
            raise ValueError("current heights disagree with the current snapshot")
    return _RecoveryState(
        generation=state.generation,
        trajectory=trajectory,
        checkpoint_event_counts=tuple(state.checkpoint_event_counts),
        checkpoint_rows=tuple(tuple(tuple(row) for row in rows) for rows in state.checkpoint_rows),
        snapshot_checkpoint_indices=tuple(state.snapshot_checkpoint_indices),
        snapshot_event_counts=tuple(state.snapshot_event_counts),
        snapshot_heights=tuple(tuple(tuple(heights) for heights in snapshot) for snapshot in state.snapshot_heights),
    )


def _new_state(binding: OneCellCheckpointBinding) -> _RecoveryState:
    trajectory = _CERTIFIED_START_TRAJECTORY(
        root_seed=binding.root_seed,
        boundary_law=binding.boundary_law,
        width=binding.width,
        threshold_schedule=binding.threshold_schedule,
    )
    return _RecoveryState(0, trajectory, (), (), (), (), ())


def _next_recovery_boundary(*, current_event_count: int, terminal_event_count: int) -> int:
    """Return the next strict global cadence boundary, capped at terminal."""

    current = _require_uint(current_event_count, maximum=_U64_MAX, label="current_event_count")
    terminal = _require_uint(terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
    if current > terminal:
        raise ValueError("current_event_count must not exceed terminal_event_count")
    if current == terminal:
        return terminal
    return min(terminal, (current // _CADENCE + 1) * _CADENCE)


def _planned_compiled_stops(
    *, current_event_count: int, terminal_event_count: int, checkpoint_event_counts: tuple[int, ...]
) -> tuple[int, ...]:
    boundary = _next_recovery_boundary(
        current_event_count=current_event_count,
        terminal_event_count=terminal_event_count,
    )
    stops = tuple(value for value in checkpoint_event_counts if current_event_count < value <= boundary)
    if not stops or stops[-1] != boundary:
        stops += (boundary,)
    return stops


def _validated_task_path(value: object) -> str:
    if type(value) is not str:
        raise TypeError("task_directory must be a built-in string")
    if not os.path.isabs(value) or os.path.normpath(value) != value or value == "/":
        raise ValueError("task_directory must be an absolute normalized dedicated path")
    if any(
        part in {"", ".", ".."}
        or any(ord(char) < 32 or 127 <= ord(char) <= 159 or 0xD800 <= ord(char) <= 0xDFFF for char in part)
        for part in value.split("/")[1:]
    ):
        raise ValueError("task_directory contains a forbidden path component")
    return value


def _open_task_directory(path: str) -> int:
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", directory_flags)
    try:
        for component in path.split("/")[1:]:
            next_descriptor = os.open(component, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            raise OSError("task path is not a directory")
        return descriptor
    except OSError as error:
        os.close(descriptor)
        raise OneCellCheckpointValidationError("task_directory failed descriptor-anchored validation") from error


def _open_lock(task_descriptor: int) -> int:
    descriptor: int | None = None
    try:
        try:
            descriptor = os.open(
                "task.lock",
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=task_descriptor,
            )
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
        except FileExistsError:
            descriptor = os.open("task.lock", os.O_RDWR | os.O_NOFOLLOW, dir_fd=task_descriptor)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()
        ):
            raise OSError("task.lock is not a private single-link regular file")
        flock(descriptor, LOCK_EX)
        return descriptor
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise OneCellCheckpointValidationError("persistent task lock validation failed") from error


def _generation_from_text(text: str) -> int:
    generation = int(text)
    if not 1 <= generation <= _U64_MAX:
        raise _FatalArtifact("checkpoint generation is outside [1, 2**64-1]")
    return generation


def _inventory(task_descriptor: int) -> tuple[set[str], tuple[int, ...], int, bool]:
    try:
        names = set(os.listdir(task_descriptor))
    except OSError as error:
        raise _FatalArtifact("task inventory could not be read") from error
    manifest_generations: set[int] = set()
    high_water = 0
    final_manifest = False
    for name in names:
        if name == "task.lock":
            continue
        checkpoint_match = _CHECKPOINT_NAME.fullmatch(name)
        if checkpoint_match is not None:
            generation = _generation_from_text(checkpoint_match.group(1))
            high_water = max(high_water, generation)
            if checkpoint_match.group(2) == "manifest.json":
                manifest_generations.add(generation)
            continue
        if name in _FINAL_NAMES:
            final_manifest = final_manifest or name == "final.manifest.json"
            continue
        temporary_match = _TEMP_NAME.fullmatch(name)
        if temporary_match is not None:
            target = temporary_match.group(1)
            target_match = _CHECKPOINT_NAME.fullmatch(target)
            if target_match is not None:
                high_water = max(high_water, _generation_from_text(target_match.group(1)))
            continue
        raise _FatalArtifact(f"unexpected or malformed task entry: {name!r}")
    return names, tuple(sorted(manifest_generations)), high_water, final_manifest


def _repair_managed_install_links(task_descriptor: int) -> None:
    """Close the link/install crash window for an exact managed temporary."""

    try:
        names = set(os.listdir(task_descriptor))
        repaired = False
        for temporary in names:
            match = _TEMP_NAME.fullmatch(temporary)
            if match is None:
                continue
            target = match.group(1)
            if target not in names:
                continue
            target_info = os.stat(target, dir_fd=task_descriptor, follow_symlinks=False)
            temporary_info = os.stat(temporary, dir_fd=task_descriptor, follow_symlinks=False)
            same_private_install = (
                stat.S_ISREG(target_info.st_mode)
                and stat.S_ISREG(temporary_info.st_mode)
                and target_info.st_dev == temporary_info.st_dev
                and target_info.st_ino == temporary_info.st_ino
                and target_info.st_nlink == temporary_info.st_nlink == 2
                and stat.S_IMODE(target_info.st_mode) == 0o600
                and target_info.st_uid == os.geteuid()
            )
            if same_private_install:
                os.unlink(temporary, dir_fd=task_descriptor)
                repaired = True
        if repaired:
            os.fsync(task_descriptor)
        for temporary in os.listdir(task_descriptor):
            if _TEMP_NAME.fullmatch(temporary) is None:
                continue
            info = os.stat(temporary, dir_fd=task_descriptor, follow_symlinks=False)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid()
            ):
                raise _FatalArtifact("managed temporary is not a private single-link regular file")
    except OSError as error:
        raise _FatalArtifact("managed install-link crash recovery failed") from error


def _read_file(
    task_descriptor: int,
    name: str,
    *,
    maximum: int,
    manifest: bool = False,
    expected_size: int | None = None,
) -> bytes:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(name, flags, dir_fd=task_descriptor)
    except OSError as error:
        failure = _FatalArtifact if manifest else _CandidateError
        raise failure(f"member {name!r} could not be opened without following links") from error
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            failure = _FatalArtifact if manifest else _CandidateError
            raise failure(f"member {name!r} is not a single-link regular file")
        if stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
            failure = _FatalArtifact if manifest else _CandidateError
            raise failure(f"member {name!r} is not a private owner file")
        if not 0 <= info.st_size <= maximum:
            failure = _FatalArtifact if manifest else _CandidateError
            raise failure(f"member {name!r} exceeds its parser ceiling")
        if expected_size is not None and info.st_size != expected_size:
            failure = _FatalArtifact if manifest else _CandidateError
            raise failure(f"member {name!r} held size disagrees with its manifest")
        remaining = info.st_size
        chunks: list[bytes] = []
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1 << 20))
            if not chunk:
                raise _CandidateError(f"member {name!r} ended before its held size")
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise _CandidateError(f"member {name!r} changed while held")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _strict_json(payload: bytes) -> object:
    def reject_constant(value: str) -> object:
        raise ValueError(f"nonfinite JSON value {value!r} is forbidden")

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        decoded = payload.decode("utf-8")
        value = json.loads(decoded, parse_constant=reject_constant, object_pairs_hook=unique_object)
        if payload != _canonical_json(value, newline=True):
            raise ValueError("stored JSON is not compact sorted-key canonical JSON with one LF")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as error:
        raise ValueError("stored JSON is not strict UTF-8 JSON") from error
    return value


def _checkpoint_names(generation: int) -> dict[str, str]:
    prefix = f"checkpoint.{generation:020d}"
    return {
        "arrays": f"{prefix}.arrays.u64le",
        "configuration": f"{prefix}.configuration.bin",
        "scientific_identity": f"{prefix}.scientific-identity.bin",
        "state": f"{prefix}.state.json",
        "manifest": f"{prefix}.manifest.json",
    }


def _final_names() -> dict[str, str]:
    return {
        "arrays": "final.arrays.u64le",
        "configuration": "final.configuration.bin",
        "scientific_identity": "final.scientific-identity.bin",
        "state": "final.state.json",
        "manifest": "final.manifest.json",
    }


def _append_section(
    sections: list[dict[str, object]],
    words: list[int],
    *,
    name: str,
    shape: tuple[int, ...],
    values: tuple[int, ...],
) -> None:
    product = 1
    for dimension in shape:
        if type(dimension) is not int or dimension < 0:
            raise AssertionError("internal section dimension is malformed")
        product *= dimension
    if product != len(values):
        raise AssertionError("internal section shape does not match its word payload")
    if any(type(value) is not int or not 0 <= value <= _U64_MAX for value in values):
        raise AssertionError("internal section contains a non-u64 word")
    sections.append(
        {
            "dtype": "<u8",
            "name": name,
            "offset_words": len(words),
            "shape": list(shape),
            "word_count": product,
        }
    )
    words.extend(values)


def _encode_words(words: list[int]) -> bytes:
    if len(words) > _ARRAY_LIMIT // 8:
        raise OverflowError("checkpoint array member exceeds the 64 MiB closed-codec ceiling")
    payload = bytearray(8 * len(words))
    for index, value in enumerate(words):
        payload[8 * index : 8 * index + 8] = value.to_bytes(8, "little")
    return bytes(payload)


def _recovery_payloads(
    state: _RecoveryState,
    *,
    binding: OneCellCheckpointBinding,
) -> tuple[bytes, bytes]:
    trajectory = state.trajectory
    arm_count = len(trajectory.arms)
    checkpoint_count = len(state.checkpoint_event_counts)
    snapshot_count = len(state.snapshot_checkpoint_indices)
    sections: list[dict[str, object]] = []
    words: list[int] = []
    current_heights = tuple(value for arm in trajectory.arms for value in arm.heights)
    current_rows = tuple(value for row in _rows_from_trajectory(trajectory) for value in row)
    histogram = _histogram_words(trajectory)
    checkpoint_rows = tuple(value for rows in state.checkpoint_rows for row in rows for value in row)
    snapshot_heights = tuple(value for snapshot in state.snapshot_heights for heights in snapshot for value in heights)
    _append_section(
        sections,
        words,
        name="current_heights",
        shape=(arm_count, binding.width),
        values=current_heights,
    )
    _append_section(sections, words, name="current_rows", shape=(arm_count, 33), values=current_rows)
    _append_section(
        sections,
        words,
        name="current_histogram",
        shape=(len(histogram) // 3, 3),
        values=histogram,
    )
    _append_section(
        sections,
        words,
        name="checkpoint_event_counts",
        shape=(checkpoint_count,),
        values=state.checkpoint_event_counts,
    )
    _append_section(
        sections,
        words,
        name="checkpoint_rows",
        shape=(checkpoint_count, arm_count, 33),
        values=checkpoint_rows,
    )
    _append_section(
        sections,
        words,
        name="snapshot_checkpoint_indices",
        shape=(snapshot_count,),
        values=state.snapshot_checkpoint_indices,
    )
    _append_section(
        sections,
        words,
        name="snapshot_event_counts",
        shape=(snapshot_count,),
        values=state.snapshot_event_counts,
    )
    _append_section(
        sections,
        words,
        name="snapshot_heights",
        shape=(snapshot_count, arm_count, binding.width),
        values=snapshot_heights,
    )
    state_record = {
        "arm_count": arm_count,
        "checkpoint_count": checkpoint_count,
        "current_event_count": trajectory.event_count,
        "generation": state.generation,
        "next_event_ordinal": trajectory.event_count,
        "profile": "tetris-pre-one-cell-checkpoint-state@1",
        "seam_equality_applicable": binding.boundary_law is OneCellBoundaryLaw.PERIODIC,
        "sections": sections,
        "snapshot_count": snapshot_count,
        "terminal_event_count": binding.terminal_event_count,
        "width": binding.width,
    }
    state_bytes = _canonical_json(state_record, newline=True)
    if len(state_bytes) > _JSON_LIMIT:
        raise OverflowError("checkpoint state JSON exceeds its 1 MiB ceiling")
    return state_bytes, _encode_words(words)


def _final_payloads(
    state: _RecoveryState,
    *,
    binding: OneCellCheckpointBinding,
) -> tuple[bytes, bytes]:
    arm_count = len(binding.threshold_schedule)
    sections: list[dict[str, object]] = []
    words: list[int] = []
    checkpoint_rows = tuple(value for rows in state.checkpoint_rows for row in rows for value in row)
    snapshot_heights = tuple(value for snapshot in state.snapshot_heights for heights in snapshot for value in heights)
    histogram = _histogram_words(state.trajectory)
    _append_section(
        sections,
        words,
        name="checkpoint_event_counts",
        shape=(512,),
        values=state.checkpoint_event_counts,
    )
    _append_section(
        sections,
        words,
        name="checkpoint_rows",
        shape=(512, arm_count, 33),
        values=checkpoint_rows,
    )
    _append_section(
        sections,
        words,
        name="snapshot_checkpoint_indices",
        shape=(16,),
        values=state.snapshot_checkpoint_indices,
    )
    _append_section(
        sections,
        words,
        name="snapshot_event_counts",
        shape=(16,),
        values=state.snapshot_event_counts,
    )
    _append_section(
        sections,
        words,
        name="snapshot_heights",
        shape=(16, arm_count, binding.width),
        values=snapshot_heights,
    )
    _append_section(
        sections,
        words,
        name="final_histogram",
        shape=(len(histogram) // 3, 3),
        values=histogram,
    )
    state_record = {
        "arm_count": arm_count,
        "checkpoint_count": 512,
        "profile": "tetris-pre-one-cell-final-state@1",
        "seam_equality_applicable": binding.boundary_law is OneCellBoundaryLaw.PERIODIC,
        "sections": sections,
        "snapshot_count": 16,
        "terminal_event_count": binding.terminal_event_count,
        "width": binding.width,
    }
    state_bytes = _canonical_json(state_record, newline=True)
    if len(state_bytes) > _JSON_LIMIT:
        raise OverflowError("final state JSON exceeds its 1 MiB ceiling")
    return state_bytes, _encode_words(words)


def _member_records(payloads: dict[str, tuple[str, bytes]]) -> dict[str, dict[str, object]]:
    return {
        label: {
            "filename": payloads[label][0],
            "sha256": _sha256(payloads[label][1]),
            "size_bytes": len(payloads[label][1]),
        }
        for label in _MEMBER_KEYS
    }


def _write_exclusive(task_descriptor: int, target: str, payload: bytes) -> None:
    temporary = f".{target}.{os.urandom(16).hex()}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=task_descriptor,
        )
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        written = 0
        while written < len(payload):
            written += os.write(descriptor, view[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.link(
            temporary,
            target,
            src_dir_fd=task_descriptor,
            dst_dir_fd=task_descriptor,
            follow_symlinks=False,
        )
        os.unlink(temporary, dir_fd=task_descriptor)
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise _FatalArtifact(f"exclusive publication failed for {target!r}") from error


def _publish_payload_bundle(
    task_descriptor: int,
    *,
    payloads: dict[str, tuple[str, bytes]],
    manifest_name: str,
    manifest_bytes: bytes,
) -> None:
    try:
        for label in ("configuration", "scientific_identity", "state", "arrays"):
            _write_exclusive(task_descriptor, payloads[label][0], payloads[label][1])
        os.fsync(task_descriptor)
        _write_exclusive(task_descriptor, manifest_name, manifest_bytes)
        os.fsync(task_descriptor)
    except _FatalArtifact:
        raise
    except OSError as error:
        raise _FatalArtifact("bundle durability publication failed") from error


def _read_manifest_object(task_descriptor: int, name: str) -> dict[str, object]:
    try:
        payload = _read_file(task_descriptor, name, maximum=_JSON_LIMIT, manifest=True)
        value = _strict_json(payload)
    except (ValueError, _CandidateError, _FatalArtifact) as error:
        raise _FatalArtifact(f"manifest {name!r} is unreadable or noncanonical") from error
    if type(value) is not dict:
        raise _FatalArtifact(f"manifest {name!r} is not a JSON object")
    return value


def _checkpoint_manifest_header(
    task_descriptor: int,
    *,
    generation: int,
    terminal_event_count: int,
    request_identity: dict[str, object],
) -> dict[str, object]:
    name = _checkpoint_names(generation)["manifest"]
    manifest = _read_manifest_object(task_descriptor, name)
    if set(manifest) != {
        "current_event_count",
        "generation",
        "members",
        "next_event_ordinal",
        "profile",
        "request_identity",
        "status",
    }:
        raise _FatalArtifact("checkpoint manifest has an unknown schema")
    if (
        manifest.get("profile") != "tetris-ballistic/pre-one-cell-checkpoint@1"
        or manifest.get("status") != "checkpoint"
        or type(manifest.get("generation")) is not int
        or manifest.get("generation") != generation
        or type(manifest.get("current_event_count")) is not int
        or type(manifest.get("next_event_ordinal")) is not int
        or manifest.get("current_event_count") != manifest.get("next_event_ordinal")
        or not 0 <= manifest.get("current_event_count") <= terminal_event_count
    ):
        raise _FatalArtifact("checkpoint manifest header is malformed")
    if _canonical_json(manifest.get("request_identity")) != _canonical_json(request_identity):
        raise _FatalArtifact("checkpoint request identity does not match this binding")
    return manifest


def _final_manifest_header(
    task_descriptor: int,
    *,
    request_identity: dict[str, object],
) -> dict[str, object]:
    manifest = _read_manifest_object(task_descriptor, "final.manifest.json")
    if set(manifest) != {"members", "profile", "request_identity", "status"}:
        raise _FatalArtifact("final manifest has an unknown schema")
    if (
        manifest.get("profile") != "tetris-ballistic/pre-one-cell-final@1"
        or manifest.get("status") != "complete"
        or _canonical_json(manifest.get("request_identity")) != _canonical_json(request_identity)
    ):
        raise _FatalArtifact("final manifest header or request identity is malformed")
    return manifest


def _member_payloads(
    task_descriptor: int,
    *,
    manifest: dict[str, object],
    expected_names: dict[str, str],
    binding: OneCellCheckpointBinding,
    final: bool,
) -> dict[str, bytes]:
    members = manifest.get("members")
    if type(members) is not dict or set(members) != set(_MEMBER_KEYS):
        raise _CandidateError("manifest member table is malformed")

    def validated_record(label: str) -> dict[str, object]:
        record = members[label]
        if type(record) is not dict or set(record) != {"filename", "sha256", "size_bytes"}:
            raise _CandidateError("manifest member record is malformed")
        filename = record.get("filename")
        digest = record.get("sha256")
        size = record.get("size_bytes")
        if type(filename) is not str or filename != expected_names[label]:
            raise _CandidateError("manifest member filename is not its fixed literal")
        if type(digest) is not str or _HEX64.fullmatch(digest) is None:
            raise _CandidateError("manifest member digest is malformed")
        if type(size) is not int or size < 0:
            raise _CandidateError("manifest member size is malformed")
        maximum = _ARRAY_LIMIT if label == "arrays" else _JSON_LIMIT
        if size > maximum:
            raise _CandidateError("manifest member size exceeds its parser ceiling")
        return record

    payloads: dict[str, bytes] = {}
    first_opaque_candidate: _CandidateError | None = None
    for label, expected in (
        ("configuration", binding.configuration_bytes),
        ("scientific_identity", binding.scientific_identity_bytes),
    ):
        try:
            record = validated_record(label)
            filename = record["filename"]
            digest = record["sha256"]
            size = record["size_bytes"]
            if type(filename) is not str or type(digest) is not str or type(size) is not int:
                raise AssertionError("validated member record types changed")
            payload = _read_file(
                task_descriptor,
                filename,
                maximum=_JSON_LIMIT,
                expected_size=size,
            )
            if len(payload) != size or _sha256(payload) != digest:
                raise _CandidateError("manifest member size or checksum does not match")
        except _CandidateError as error:
            if first_opaque_candidate is None:
                first_opaque_candidate = error
            continue
        if payload != expected:
            raise _FatalArtifact(f"rechecksummed {label} bytes contradict request identity")
        payloads[label] = payload
    if first_opaque_candidate is not None:
        raise first_opaque_candidate

    state_record = validated_record("state")
    state_filename = state_record["filename"]
    state_digest = state_record["sha256"]
    state_size = state_record["size_bytes"]
    if type(state_filename) is not str or type(state_digest) is not str or type(state_size) is not int:
        raise AssertionError("validated state record types changed")
    state_payload = _read_file(
        task_descriptor,
        state_filename,
        maximum=_JSON_LIMIT,
        expected_size=state_size,
    )
    if len(state_payload) != state_size or _sha256(state_payload) != state_digest:
        raise _CandidateError("manifest state size or checksum does not match")
    payloads["state"] = state_payload

    array_record = validated_record("arrays")
    array_size = array_record["size_bytes"]
    if type(array_size) is not int:
        raise AssertionError("validated array size type changed")
    try:
        _preflight_array_layout(
            state_bytes=payloads["state"],
            declared_array_size=array_size,
            binding=binding,
            final=final,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise _CandidateError("state metadata failed before raw-array allocation") from error
    filename = array_record["filename"]
    digest = array_record["sha256"]
    if type(filename) is not str or type(digest) is not str:
        raise AssertionError("validated array record types changed")
    payload = _read_file(
        task_descriptor,
        filename,
        maximum=_ARRAY_LIMIT,
        expected_size=array_size,
    )
    if len(payload) != array_size or _sha256(payload) != digest:
        raise _CandidateError("manifest array size or checksum does not match")
    payloads["arrays"] = payload
    return payloads


def _exact_int(value: object, *, label: str, minimum: int = 0, maximum: int = _U64_MAX) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} is not an exact integer in range")
    return value


def _layout_sections(
    state_record: dict[str, object],
    *,
    expected_names: tuple[str, ...],
    expected_shapes: tuple[tuple[int, ...] | None, ...],
    array_bytes: bytes | None = None,
    array_size_bytes: int | None = None,
) -> dict[str, tuple[tuple[int, ...], tuple[int, ...]]]:
    sections = state_record.get("sections")
    if type(sections) is not list or len(sections) != len(expected_names):
        raise ValueError("state sections have the wrong count")
    metadata: list[tuple[str, tuple[int, ...], int, int]] = []
    next_offset = 0
    max_words = _ARRAY_LIMIT // 8
    for index, (entry, expected_name, expected_shape) in enumerate(zip(sections, expected_names, expected_shapes)):
        if type(entry) is not dict or set(entry) != {"dtype", "name", "offset_words", "shape", "word_count"}:
            raise ValueError("state section record has an unknown schema")
        if entry.get("dtype") != "<u8" or entry.get("name") != expected_name:
            raise ValueError("state section dtype or name is not frozen")
        shape_value = entry.get("shape")
        if type(shape_value) is not list or not shape_value:
            raise ValueError("state section shape must be a nonempty JSON array")
        shape = tuple(_exact_int(value, label=f"section {index} dimension") for value in shape_value)
        if expected_shape is not None and shape != expected_shape:
            raise ValueError("state section shape does not match the closed layout")
        product = 1
        for dimension in shape:
            product *= dimension
            if product > max_words:
                raise ValueError("state section product exceeds the parser ceiling")
        offset = _exact_int(entry.get("offset_words"), label="section offset", maximum=max_words)
        count = _exact_int(entry.get("word_count"), label="section word_count", maximum=max_words)
        if offset != next_offset or count != product:
            raise ValueError("state section offsets or word counts are not contiguous")
        next_offset += count
        if next_offset > max_words:
            raise ValueError("state layout exceeds the parser ceiling")
        metadata.append((expected_name, shape, offset, count))
    if array_bytes is not None:
        actual_size = len(array_bytes)
    elif type(array_size_bytes) is int:
        actual_size = array_size_bytes
    else:
        raise AssertionError("layout validation requires held bytes or an exact declared size")
    if actual_size != 8 * next_offset:
        raise ValueError("raw array length does not close the declared sections")
    if array_bytes is None:
        return {name: (shape, ()) for name, shape, _, _ in metadata}
    words = tuple(
        int.from_bytes(array_bytes[offset : offset + 8], "little") for offset in range(0, len(array_bytes), 8)
    )
    return {name: (shape, words[offset : offset + count]) for name, shape, offset, count in metadata}


def _preflight_array_layout(
    *,
    state_bytes: bytes,
    declared_array_size: int,
    binding: OneCellCheckpointBinding,
    final: bool,
) -> None:
    value = _strict_json(state_bytes)
    if type(value) is not dict:
        raise ValueError("state metadata must be a JSON object")
    arm_count = len(binding.threshold_schedule)
    sections = value.get("sections")
    if type(sections) is not list:
        raise ValueError("state metadata has no exact section array")
    if (
        type(value.get("width")) is not int
        or value.get("width") != binding.width
        or type(value.get("terminal_event_count")) is not int
        or value.get("terminal_event_count") != binding.terminal_event_count
        or type(value.get("seam_equality_applicable")) is not bool
        or value.get("seam_equality_applicable") is not (binding.boundary_law is OneCellBoundaryLaw.PERIODIC)
    ):
        raise ValueError("state metadata binding scalars are malformed")
    if final:
        if set(value) != {
            "arm_count",
            "checkpoint_count",
            "profile",
            "seam_equality_applicable",
            "sections",
            "snapshot_count",
            "terminal_event_count",
            "width",
        }:
            raise ValueError("final state metadata has an unknown schema")
        if (
            type(value.get("arm_count")) is not int
            or value.get("arm_count") != arm_count
            or value.get("profile") != "tetris-pre-one-cell-final-state@1"
            or type(value.get("checkpoint_count")) is not int
            or value.get("checkpoint_count") != 512
            or type(value.get("snapshot_count")) is not int
            or value.get("snapshot_count") != 16
            or len(sections) != 6
        ):
            raise ValueError("final state metadata counts are malformed")
        histogram_index = 5
        names = _FINAL_SECTION_NAMES
        fixed_shapes: tuple[tuple[int, ...] | None, ...] = (
            (512,),
            (512, arm_count, 33),
            (16,),
            (16,),
            (16, arm_count, binding.width),
            None,
        )
    else:
        if set(value) != {
            "arm_count",
            "checkpoint_count",
            "current_event_count",
            "generation",
            "next_event_ordinal",
            "profile",
            "seam_equality_applicable",
            "sections",
            "snapshot_count",
            "terminal_event_count",
            "width",
        }:
            raise ValueError("checkpoint state metadata has an unknown schema")
        checkpoint_count = _exact_int(value.get("checkpoint_count"), label="checkpoint_count", maximum=512)
        snapshot_count = _exact_int(value.get("snapshot_count"), label="snapshot_count", maximum=16)
        current = _exact_int(value.get("current_event_count"), label="current_event_count")
        next_event = _exact_int(value.get("next_event_ordinal"), label="next_event_ordinal")
        _exact_int(value.get("generation"), label="generation", minimum=1)
        if (
            type(value.get("arm_count")) is not int
            or value.get("arm_count") != arm_count
            or value.get("profile") != "tetris-pre-one-cell-checkpoint-state@1"
            or current != next_event
            or current > binding.terminal_event_count
            or len(sections) != 8
        ):
            raise ValueError("checkpoint state metadata counts are malformed")
        histogram_index = 2
        names = _RECOVERY_SECTION_NAMES
        fixed_shapes = (
            (arm_count, binding.width),
            (arm_count, 33),
            None,
            (checkpoint_count,),
            (checkpoint_count, arm_count, 33),
            (snapshot_count,),
            (snapshot_count,),
            (snapshot_count, arm_count, binding.width),
        )
    histogram_entry = sections[histogram_index]
    if type(histogram_entry) is not dict or type(histogram_entry.get("shape")) is not list:
        raise ValueError("state histogram metadata is malformed")
    histogram_shape = histogram_entry["shape"]
    if len(histogram_shape) != 2 or type(histogram_shape[0]) is not int:
        raise ValueError("state histogram shape is malformed")
    histogram_rows = _exact_int(
        histogram_shape[0],
        label="histogram row count",
        maximum=_ARRAY_LIMIT // 24,
    )
    shapes = list(fixed_shapes)
    shapes[histogram_index] = (histogram_rows, 3)
    _layout_sections(
        value,
        expected_names=names,
        expected_shapes=tuple(shapes),
        array_size_bytes=declared_array_size,
    )


def _rows_from_flat(values: tuple[int, ...], *, outer: int, arms: int) -> tuple[tuple[tuple[int, ...], ...], ...]:
    result = []
    offset = 0
    for _ in range(outer):
        rows = []
        for _ in range(arms):
            rows.append(tuple(values[offset : offset + 33]))
            offset += 33
        result.append(tuple(rows))
    if offset != len(values):
        raise ValueError("row array has trailing words")
    return tuple(result)


def _heights_from_flat(
    values: tuple[int, ...],
    *,
    outer: int,
    arms: int,
    width: int,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    result = []
    offset = 0
    for _ in range(outer):
        snapshot = []
        for _ in range(arms):
            snapshot.append(tuple(values[offset : offset + width]))
            offset += width
        result.append(tuple(snapshot))
    if offset != len(values):
        raise ValueError("height array has trailing words")
    return tuple(result)


def _decode_recovery_state(
    *,
    generation: int,
    state_bytes: bytes,
    array_bytes: bytes,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
) -> _RecoveryState:
    value = _strict_json(state_bytes)
    if type(value) is not dict:
        raise ValueError("checkpoint state must be a JSON object")
    if set(value) != {
        "arm_count",
        "checkpoint_count",
        "current_event_count",
        "generation",
        "next_event_ordinal",
        "profile",
        "seam_equality_applicable",
        "sections",
        "snapshot_count",
        "terminal_event_count",
        "width",
    }:
        raise ValueError("checkpoint state has an unknown schema")
    arm_count = len(binding.threshold_schedule)
    checkpoint_count = _exact_int(value.get("checkpoint_count"), label="checkpoint_count", maximum=512)
    snapshot_count = _exact_int(value.get("snapshot_count"), label="snapshot_count", maximum=16)
    current = _exact_int(value.get("current_event_count"), label="current_event_count")
    next_event = _exact_int(value.get("next_event_ordinal"), label="next_event_ordinal")
    if (
        value.get("profile") != "tetris-pre-one-cell-checkpoint-state@1"
        or value.get("generation") != generation
        or type(value.get("generation")) is not int
        or value.get("arm_count") != arm_count
        or type(value.get("arm_count")) is not int
        or value.get("width") != binding.width
        or type(value.get("width")) is not int
        or value.get("terminal_event_count") != binding.terminal_event_count
        or type(value.get("terminal_event_count")) is not int
        or current != next_event
        or type(value.get("seam_equality_applicable")) is not bool
        or value.get("seam_equality_applicable") is not (binding.boundary_law is OneCellBoundaryLaw.PERIODIC)
    ):
        raise ValueError("checkpoint state scalar identity is malformed")
    raw_sections = value["sections"]
    if type(raw_sections) is not list or len(raw_sections) != 8:
        raise ValueError("checkpoint state section inventory is malformed")
    histogram_entry = raw_sections[2]
    if type(histogram_entry) is not dict or type(histogram_entry.get("shape")) is not list:
        raise ValueError("checkpoint histogram metadata is malformed")
    histogram_shape = histogram_entry["shape"]
    if len(histogram_shape) != 2 or type(histogram_shape[0]) is not int:
        raise ValueError("checkpoint histogram shape is malformed")
    histogram_rows = _exact_int(histogram_shape[0], label="histogram row count", maximum=_ARRAY_LIMIT // 24)
    expected_shapes = (
        (arm_count, binding.width),
        (arm_count, 33),
        (histogram_rows, 3),
        (checkpoint_count,),
        (checkpoint_count, arm_count, 33),
        (snapshot_count,),
        (snapshot_count,),
        (snapshot_count, arm_count, binding.width),
    )
    sections = _layout_sections(
        value,
        expected_names=_RECOVERY_SECTION_NAMES,
        expected_shapes=expected_shapes,
        array_bytes=array_bytes,
    )
    current_heights_flat = sections["current_heights"][1]
    current_heights = tuple(
        tuple(current_heights_flat[index * binding.width : (index + 1) * binding.width]) for index in range(arm_count)
    )
    current_rows_flat = sections["current_rows"][1]
    current_rows = tuple(tuple(current_rows_flat[index * 33 : (index + 1) * 33]) for index in range(arm_count))
    trajectory = _trajectory_from_words(
        binding=binding,
        event_count=current,
        heights=current_heights,
        rows=current_rows,
        histogram_words=sections["current_histogram"][1],
    )
    state = _RecoveryState(
        generation=generation,
        trajectory=trajectory,
        checkpoint_event_counts=sections["checkpoint_event_counts"][1],
        checkpoint_rows=_rows_from_flat(sections["checkpoint_rows"][1], outer=checkpoint_count, arms=arm_count),
        snapshot_checkpoint_indices=sections["snapshot_checkpoint_indices"][1],
        snapshot_event_counts=sections["snapshot_event_counts"][1],
        snapshot_heights=_heights_from_flat(
            sections["snapshot_heights"][1],
            outer=snapshot_count,
            arms=arm_count,
            width=binding.width,
        ),
    )
    return _validate_recovery_state(state, binding=binding, schedule=schedule)


def _decode_final_state(
    *,
    state_bytes: bytes,
    array_bytes: bytes,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
) -> _RecoveryState:
    value = _strict_json(state_bytes)
    if type(value) is not dict:
        raise ValueError("final state must be a JSON object")
    if set(value) != {
        "arm_count",
        "checkpoint_count",
        "profile",
        "seam_equality_applicable",
        "sections",
        "snapshot_count",
        "terminal_event_count",
        "width",
    }:
        raise ValueError("final state has an unknown schema")
    arm_count = len(binding.threshold_schedule)
    if (
        value.get("profile") != "tetris-pre-one-cell-final-state@1"
        or value.get("arm_count") != arm_count
        or type(value.get("arm_count")) is not int
        or value.get("checkpoint_count") != 512
        or type(value.get("checkpoint_count")) is not int
        or value.get("snapshot_count") != 16
        or type(value.get("snapshot_count")) is not int
        or value.get("terminal_event_count") != binding.terminal_event_count
        or type(value.get("terminal_event_count")) is not int
        or value.get("width") != binding.width
        or type(value.get("width")) is not int
        or type(value.get("seam_equality_applicable")) is not bool
        or value.get("seam_equality_applicable") is not (binding.boundary_law is OneCellBoundaryLaw.PERIODIC)
    ):
        raise ValueError("final state scalar identity is malformed")
    raw_sections = value["sections"]
    if type(raw_sections) is not list or len(raw_sections) != 6:
        raise ValueError("final section inventory is malformed")
    histogram_entry = raw_sections[5]
    if type(histogram_entry) is not dict or type(histogram_entry.get("shape")) is not list:
        raise ValueError("final histogram metadata is malformed")
    histogram_shape = histogram_entry["shape"]
    if len(histogram_shape) != 2 or type(histogram_shape[0]) is not int:
        raise ValueError("final histogram shape is malformed")
    histogram_rows = _exact_int(histogram_shape[0], label="final histogram rows", maximum=_ARRAY_LIMIT // 24)
    sections = _layout_sections(
        value,
        expected_names=_FINAL_SECTION_NAMES,
        expected_shapes=(
            (512,),
            (512, arm_count, 33),
            (16,),
            (16,),
            (16, arm_count, binding.width),
            (histogram_rows, 3),
        ),
        array_bytes=array_bytes,
    )
    checkpoint_rows = _rows_from_flat(sections["checkpoint_rows"][1], outer=512, arms=arm_count)
    snapshot_heights = _heights_from_flat(
        sections["snapshot_heights"][1], outer=16, arms=arm_count, width=binding.width
    )
    trajectory = _trajectory_from_words(
        binding=binding,
        event_count=binding.terminal_event_count,
        heights=snapshot_heights[-1],
        rows=checkpoint_rows[-1],
        histogram_words=sections["final_histogram"][1],
    )
    state = _RecoveryState(
        generation=0,
        trajectory=trajectory,
        checkpoint_event_counts=sections["checkpoint_event_counts"][1],
        checkpoint_rows=checkpoint_rows,
        snapshot_checkpoint_indices=sections["snapshot_checkpoint_indices"][1],
        snapshot_event_counts=sections["snapshot_event_counts"][1],
        snapshot_heights=snapshot_heights,
    )
    return _validate_recovery_state(state, binding=binding, schedule=schedule)


def _load_checkpoint_candidate(
    task_descriptor: int,
    *,
    generation: int,
    manifest: dict[str, object],
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
) -> _RecoveryState:
    names = _checkpoint_names(generation)
    payloads = _member_payloads(
        task_descriptor,
        manifest=manifest,
        expected_names=names,
        binding=binding,
        final=False,
    )
    if payloads["configuration"] != binding.configuration_bytes:
        raise _FatalArtifact("rechecksummed checkpoint configuration bytes contradict request identity")
    if payloads["scientific_identity"] != binding.scientific_identity_bytes:
        raise _FatalArtifact("rechecksummed checkpoint scientific identity contradicts request identity")
    try:
        state = _decode_recovery_state(
            generation=generation,
            state_bytes=payloads["state"],
            array_bytes=payloads["arrays"],
            binding=binding,
            schedule=schedule,
        )
    except (TypeError, ValueError, OverflowError, AssertionError) as error:
        raise _CandidateError("checkpoint state failed closed-codec or scientific recertification") from error
    current = manifest["current_event_count"]
    if current != state.trajectory.event_count or not 0 <= current <= binding.terminal_event_count:
        raise _CandidateError("checkpoint manifest and state event ordinals disagree")
    return state


def _load_final(
    task_descriptor: int,
    *,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
    request_identity: dict[str, object],
) -> _RecoveryState:
    try:
        manifest = _final_manifest_header(task_descriptor, request_identity=request_identity)
        payloads = _member_payloads(
            task_descriptor,
            manifest=manifest,
            expected_names=_final_names(),
            binding=binding,
            final=True,
        )
        if payloads["configuration"] != binding.configuration_bytes:
            raise _FatalArtifact("final configuration bytes contradict request identity")
        if payloads["scientific_identity"] != binding.scientific_identity_bytes:
            raise _FatalArtifact("final scientific identity bytes contradict request identity")
        return _decode_final_state(
            state_bytes=payloads["state"],
            array_bytes=payloads["arrays"],
            binding=binding,
            schedule=schedule,
        )
    except (TypeError, ValueError, OverflowError, AssertionError, _CandidateError, _FatalArtifact) as error:
        raise OneCellCheckpointValidationError("present final manifest or member is invalid") from error


def _discover_recovery(
    task_descriptor: int,
    *,
    manifest_generations: tuple[int, ...],
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
    request_identity: dict[str, object],
) -> tuple[_RecoveryState | None, bool, tuple[_RecoveryState, ...]]:
    manifests: dict[int, dict[str, object]] = {}
    try:
        for generation in manifest_generations:
            manifests[generation] = _checkpoint_manifest_header(
                task_descriptor,
                generation=generation,
                terminal_event_count=binding.terminal_event_count,
                request_identity=request_identity,
            )
    except _FatalArtifact as error:
        raise OneCellCheckpointValidationError("checkpoint manifest identity is not trustworthy") from error

    valid: list[_RecoveryState] = []
    corrupt_generations: set[int] = set()
    for generation in reversed(manifest_generations):
        try:
            valid.append(
                _load_checkpoint_candidate(
                    task_descriptor,
                    generation=generation,
                    manifest=manifests[generation],
                    binding=binding,
                    schedule=schedule,
                )
            )
        except _CandidateError:
            corrupt_generations.add(generation)
        except _FatalArtifact as error:
            raise OneCellCheckpointValidationError("checkpoint member violates the fatal trust boundary") from error
    if manifest_generations and not valid:
        raise OneCellCheckpointValidationError("no valid committed recovery generation remains")
    if not valid:
        return None, False, ()
    selected = valid[0]
    used_fallback = any(generation > selected.generation for generation in corrupt_generations)
    return selected, used_fallback, tuple(valid)


def _advance_to_recovery_boundary(
    *,
    state: _RecoveryState,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
    interruption_flag: OneCellInterruptionFlag | None,
) -> tuple[_RecoveryState, bool]:
    """Advance through certified stops to one cadence boundary or interruption."""

    trajectory = _snapshot_trajectory(state.trajectory)
    checkpoint_events = list(state.checkpoint_event_counts)
    checkpoint_rows = list(state.checkpoint_rows)
    snapshot_indices = list(state.snapshot_checkpoint_indices)
    snapshot_events = list(state.snapshot_event_counts)
    snapshot_heights = list(state.snapshot_heights)
    starting_event = trajectory.event_count
    stops = _planned_compiled_stops(
        current_event_count=starting_event,
        terminal_event_count=binding.terminal_event_count,
        checkpoint_event_counts=schedule.checkpoint_event_counts,
    )
    for stop in stops:
        if stop == trajectory.event_count:
            continue
        if interruption_flag is not None and interruption_flag.requested:
            break
        advanced = _CERTIFIED_COMPILED_ADVANCE(
            trajectory=trajectory,
            stop_event_ordinal=stop,
        )
        trajectory = _snapshot_trajectory(advanced)
        if (
            trajectory.event_count != stop
            or trajectory.root_seed != binding.root_seed
            or trajectory.boundary_law is not binding.boundary_law
            or trajectory.width != binding.width
            or trajectory.threshold_schedule != binding.threshold_schedule
        ):
            raise AssertionError("compiled Slice 6 delegate returned a record for a different stop")
        next_checkpoint_index = len(checkpoint_events)
        if next_checkpoint_index < 512 and stop == schedule.checkpoint_event_counts[next_checkpoint_index]:
            checkpoint_events.append(stop)
            checkpoint_rows.append(_rows_from_trajectory(trajectory))
            next_snapshot_index = len(snapshot_indices)
            if (
                next_snapshot_index < 16
                and next_checkpoint_index == schedule.snapshot_checkpoint_indices[next_snapshot_index]
            ):
                snapshot_indices.append(next_checkpoint_index)
                snapshot_events.append(stop)
                snapshot_heights.append(tuple(arm.heights for arm in trajectory.arms))
        if interruption_flag is not None and interruption_flag.requested:
            break
    result = _RecoveryState(
        generation=state.generation,
        trajectory=trajectory,
        checkpoint_event_counts=tuple(checkpoint_events),
        checkpoint_rows=tuple(checkpoint_rows),
        snapshot_checkpoint_indices=tuple(snapshot_indices),
        snapshot_event_counts=tuple(snapshot_events),
        snapshot_heights=tuple(snapshot_heights),
    )
    return _validate_recovery_state(
        result, binding=binding, schedule=schedule
    ), trajectory.event_count != starting_event


def _checkpoint_manifest_bytes(
    state: _RecoveryState,
    *,
    binding: OneCellCheckpointBinding,
    request_identity: dict[str, object],
) -> tuple[dict[str, tuple[str, bytes]], bytes]:
    names = _checkpoint_names(state.generation)
    state_bytes, array_bytes = _recovery_payloads(state, binding=binding)
    payloads = {
        "arrays": (names["arrays"], array_bytes),
        "configuration": (names["configuration"], binding.configuration_bytes),
        "scientific_identity": (names["scientific_identity"], binding.scientific_identity_bytes),
        "state": (names["state"], state_bytes),
    }
    manifest = {
        "current_event_count": state.trajectory.event_count,
        "generation": state.generation,
        "members": _member_records(payloads),
        "next_event_ordinal": state.trajectory.event_count,
        "profile": "tetris-ballistic/pre-one-cell-checkpoint@1",
        "request_identity": request_identity,
        "status": "checkpoint",
    }
    manifest_bytes = _canonical_json(manifest, newline=True)
    if len(manifest_bytes) > _JSON_LIMIT:
        raise OverflowError("checkpoint manifest exceeds its 1 MiB ceiling")
    return payloads, manifest_bytes


def _publish_checkpoint(
    task_descriptor: int,
    *,
    state: _RecoveryState,
    generation: int,
    binding: OneCellCheckpointBinding,
    schedule: OneCellCheckpointSchedule,
    request_identity: dict[str, object],
) -> _RecoveryState:
    candidate = _RecoveryState(
        generation=generation,
        trajectory=state.trajectory,
        checkpoint_event_counts=state.checkpoint_event_counts,
        checkpoint_rows=state.checkpoint_rows,
        snapshot_checkpoint_indices=state.snapshot_checkpoint_indices,
        snapshot_event_counts=state.snapshot_event_counts,
        snapshot_heights=state.snapshot_heights,
    )
    candidate = _validate_recovery_state(candidate, binding=binding, schedule=schedule)
    payloads, manifest_bytes = _checkpoint_manifest_bytes(
        candidate,
        binding=binding,
        request_identity=request_identity,
    )
    names = _checkpoint_names(generation)
    try:
        _publish_payload_bundle(
            task_descriptor,
            payloads=payloads,
            manifest_name=names["manifest"],
            manifest_bytes=manifest_bytes,
        )
        manifest = _checkpoint_manifest_header(
            task_descriptor,
            generation=generation,
            terminal_event_count=binding.terminal_event_count,
            request_identity=request_identity,
        )
        return _load_checkpoint_candidate(
            task_descriptor,
            generation=generation,
            manifest=manifest,
            binding=binding,
            schedule=schedule,
        )
    except (_CandidateError, _FatalArtifact) as error:
        raise OneCellCheckpointValidationError("new checkpoint failed publication readback") from error


def _is_private_regular(task_descriptor: int, name: str) -> bool:
    try:
        info = os.stat(name, dir_fd=task_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and stat.S_IMODE(info.st_mode) == 0o600
        and info.st_uid == os.geteuid()
    )


def _remove_generation(task_descriptor: int, generation: int) -> None:
    names = _checkpoint_names(generation)
    manifest = names["manifest"]
    try:
        if manifest in os.listdir(task_descriptor):
            if not _is_private_regular(task_descriptor, manifest):
                raise _FatalArtifact("retention manifest is not an exact private regular file")
            os.unlink(manifest, dir_fd=task_descriptor)
            os.fsync(task_descriptor)
        for label in _MEMBER_KEYS:
            name = names[label]
            if _is_private_regular(task_descriptor, name):
                os.unlink(name, dir_fd=task_descriptor)
        os.fsync(task_descriptor)
    except OSError as error:
        raise _FatalArtifact("checkpoint retention cleanup failed") from error


def _apply_retention(
    task_descriptor: int,
    *,
    keep_generations: set[int],
) -> None:
    try:
        names, _, _, _ = _inventory(task_descriptor)
        observed = {
            _generation_from_text(match.group(1))
            for name in names
            if (match := _CHECKPOINT_NAME.fullmatch(name)) is not None
        }
        for generation in sorted(observed - keep_generations):
            _remove_generation(task_descriptor, generation)
        remaining = set(os.listdir(task_descriptor))
        for name in remaining:
            temporary = _TEMP_NAME.fullmatch(name)
            if temporary is None:
                continue
            target_match = _CHECKPOINT_NAME.fullmatch(temporary.group(1))
            if target_match is None:
                continue
            generation = _generation_from_text(target_match.group(1))
            if generation not in keep_generations and _is_private_regular(task_descriptor, name):
                os.unlink(name, dir_fd=task_descriptor)
        os.fsync(task_descriptor)
    except (_FatalArtifact, OSError) as error:
        raise OneCellCheckpointValidationError("checkpoint retention did not complete safely") from error


def _progress(
    *,
    task_path: str,
    manifest_name: str,
    disposition: str,
    state: _RecoveryState,
    used_fallback: bool,
) -> OneCellCheckpointProgress:
    return OneCellCheckpointProgress(
        disposition=disposition,
        trajectory=state.trajectory,
        generation=state.generation,
        checkpoint_count=len(state.checkpoint_event_counts),
        snapshot_count=len(state.snapshot_checkpoint_indices),
        used_fallback=used_fallback,
        manifest_path=os.path.join(task_path, manifest_name),
    )


def _final_manifest_bytes(
    state: _RecoveryState,
    *,
    binding: OneCellCheckpointBinding,
    request_identity: dict[str, object],
) -> tuple[dict[str, tuple[str, bytes]], bytes]:
    names = _final_names()
    state_bytes, array_bytes = _final_payloads(state, binding=binding)
    payloads = {
        "arrays": (names["arrays"], array_bytes),
        "configuration": (names["configuration"], binding.configuration_bytes),
        "scientific_identity": (names["scientific_identity"], binding.scientific_identity_bytes),
        "state": (names["state"], state_bytes),
    }
    manifest = {
        "members": _member_records(payloads),
        "profile": "tetris-ballistic/pre-one-cell-final@1",
        "request_identity": request_identity,
        "status": "complete",
    }
    manifest_bytes = _canonical_json(manifest, newline=True)
    if len(manifest_bytes) > _JSON_LIMIT:
        raise OverflowError("final manifest exceeds its 1 MiB ceiling")
    return payloads, manifest_bytes


def _publish_or_adopt_final(
    task_descriptor: int,
    *,
    payloads: dict[str, tuple[str, bytes]],
    manifest_bytes: bytes,
) -> None:
    try:
        present = set(os.listdir(task_descriptor))
        rebuild = False
        for label in _MEMBER_KEYS:
            name, expected = payloads[label]
            if name not in present:
                continue
            maximum = _ARRAY_LIMIT if label == "arrays" else _JSON_LIMIT
            info = os.stat(name, dir_fd=task_descriptor, follow_symlinks=False)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid()
            ):
                raise _FatalArtifact("uncommitted final payload is nonregular or linked")
            if info.st_size != len(expected) or info.st_size > maximum:
                rebuild = True
                continue
            actual = _read_file(
                task_descriptor,
                name,
                maximum=maximum,
                expected_size=len(expected),
            )
            if actual != expected:
                rebuild = True
        if rebuild:
            for label in _MEMBER_KEYS:
                name = payloads[label][0]
                if name in present:
                    if not _is_private_regular(task_descriptor, name):
                        raise _FatalArtifact("mismatching final debris is not safely removable")
                    os.unlink(name, dir_fd=task_descriptor)
            os.fsync(task_descriptor)
            present = set(os.listdir(task_descriptor))
        for label in ("configuration", "scientific_identity", "state", "arrays"):
            name, payload = payloads[label]
            if name not in present:
                _write_exclusive(task_descriptor, name, payload)
        os.fsync(task_descriptor)
        _write_exclusive(task_descriptor, "final.manifest.json", manifest_bytes)
        os.fsync(task_descriptor)
    except (_CandidateError, _FatalArtifact):
        raise
    except OSError as error:
        raise _FatalArtifact("final payload adoption/publication failed") from error


def _cleanup_final_temporaries(task_descriptor: int) -> None:
    try:
        for name in os.listdir(task_descriptor):
            match = _TEMP_NAME.fullmatch(name)
            if match is None or not match.group(1).startswith("final."):
                continue
            if not _is_private_regular(task_descriptor, name):
                raise _FatalArtifact("managed final temporary is not safely removable")
            os.unlink(name, dir_fd=task_descriptor)
        os.fsync(task_descriptor)
    except OSError as error:
        raise _FatalArtifact("managed final temporary cleanup failed") from error


def advance_one_cell_checkpoint_generation(
    *,
    task_directory: str,
    binding: OneCellCheckpointBinding,
    interruption_flag: OneCellInterruptionFlag | None = None,
) -> OneCellCheckpointProgress:
    """Validate, advance at most one cadence, and durably publish recovery."""

    _assert_authority()
    task_path = _validated_task_path(task_directory)
    selected_binding = _snapshot_binding(binding)
    if interruption_flag is not None and type(interruption_flag) is not OneCellInterruptionFlag:
        raise TypeError("interruption_flag must be an exact OneCellInterruptionFlag or None")
    schedule = build_one_cell_checkpoint_schedule(terminal_event_count=selected_binding.terminal_event_count)
    request_identity = _request_identity(selected_binding, schedule)
    task_descriptor = _open_task_directory(task_path)
    lock_descriptor: int | None = None
    try:
        lock_descriptor = _open_lock(task_descriptor)
        try:
            _, manifest_generations, high_water, final_present = _inventory(task_descriptor)
            _repair_managed_install_links(task_descriptor)
        except _FatalArtifact as error:
            raise OneCellCheckpointValidationError("task inventory is outside the closed namespace") from error
        if final_present:
            _load_final(
                task_descriptor,
                binding=selected_binding,
                schedule=schedule,
                request_identity=request_identity,
            )
            raise OneCellCheckpointValidationError("a valid final manifest prohibits further advancement")
        selected, used_fallback, valid_states = _discover_recovery(
            task_descriptor,
            manifest_generations=manifest_generations,
            binding=selected_binding,
            schedule=schedule,
            request_identity=request_identity,
        )
        starting = selected if selected is not None else _new_state(selected_binding)
        requested_before_work = interruption_flag is not None and interruption_flag.requested
        likely_write = selected is None or (
            not requested_before_work
            and (starting.trajectory.event_count < selected_binding.terminal_event_count or used_fallback)
        )
        if likely_write and high_water == _U64_MAX:
            raise OverflowError("checkpoint generation ordinal is exhausted")

        advanced = starting
        moved = False
        if not requested_before_work and starting.trajectory.event_count < selected_binding.terminal_event_count:
            advanced, moved = _advance_to_recovery_boundary(
                state=starting,
                binding=selected_binding,
                schedule=schedule,
                interruption_flag=interruption_flag,
            )
        requested_after_work = interruption_flag is not None and interruption_flag.requested
        should_publish = selected is None or moved or (used_fallback and not requested_after_work)
        if should_publish:
            if high_water == _U64_MAX:
                raise OverflowError("checkpoint generation ordinal is exhausted")
            generation = high_water + 1
            durable = _publish_checkpoint(
                task_descriptor,
                state=advanced,
                generation=generation,
                binding=selected_binding,
                schedule=schedule,
                request_identity=request_identity,
            )
            keep = {durable.generation}
            if selected is not None:
                keep.add(selected.generation)
            _apply_retention(task_descriptor, keep_generations=keep)
        else:
            durable = starting
            if not used_fallback and len(valid_states) > 2:
                _apply_retention(
                    task_descriptor,
                    keep_generations={state.generation for state in valid_states[:2]},
                )
        requested_at_linearization = interruption_flag is not None and interruption_flag.requested
        if requested_at_linearization:
            disposition = "requeue-required"
        elif durable.trajectory.event_count == selected_binding.terminal_event_count:
            disposition = "terminal"
        else:
            disposition = "ready"
        return _progress(
            task_path=task_path,
            manifest_name=_checkpoint_names(durable.generation)["manifest"],
            disposition=disposition,
            state=durable,
            used_fallback=used_fallback,
        )
    finally:
        if lock_descriptor is not None:
            flock(lock_descriptor, LOCK_UN)
            os.close(lock_descriptor)
        os.close(task_descriptor)


def publish_one_cell_final(
    *,
    task_directory: str,
    binding: OneCellCheckpointBinding,
) -> OneCellCheckpointProgress:
    """Publish or validate the separate deterministic final completion bundle."""

    _assert_authority()
    task_path = _validated_task_path(task_directory)
    selected_binding = _snapshot_binding(binding)
    schedule = build_one_cell_checkpoint_schedule(terminal_event_count=selected_binding.terminal_event_count)
    request_identity = _request_identity(selected_binding, schedule)
    task_descriptor = _open_task_directory(task_path)
    lock_descriptor: int | None = None
    try:
        lock_descriptor = _open_lock(task_descriptor)
        try:
            _, manifest_generations, _, final_present = _inventory(task_descriptor)
            _repair_managed_install_links(task_descriptor)
        except _FatalArtifact as error:
            raise OneCellCheckpointValidationError("task inventory is outside the closed namespace") from error
        if final_present:
            final_state = _load_final(
                task_descriptor,
                binding=selected_binding,
                schedule=schedule,
                request_identity=request_identity,
            )
            try:
                _cleanup_final_temporaries(task_descriptor)
            except _FatalArtifact as error:
                raise OneCellCheckpointValidationError("final temporary cleanup failed") from error
            return OneCellCheckpointProgress(
                disposition="reused",
                trajectory=final_state.trajectory,
                generation=0,
                checkpoint_count=512,
                snapshot_count=16,
                used_fallback=False,
                manifest_path=os.path.join(task_path, "final.manifest.json"),
            )
        selected, used_fallback, _ = _discover_recovery(
            task_descriptor,
            manifest_generations=manifest_generations,
            binding=selected_binding,
            schedule=schedule,
            request_identity=request_identity,
        )
        if (
            selected is None
            or selected.trajectory.event_count != selected_binding.terminal_event_count
            or len(selected.checkpoint_event_counts) != 512
            or len(selected.snapshot_checkpoint_indices) != 16
        ):
            raise OneCellCheckpointValidationError("final publication requires a complete terminal recovery")
        payloads, manifest_bytes = _final_manifest_bytes(
            selected,
            binding=selected_binding,
            request_identity=request_identity,
        )
        try:
            _publish_or_adopt_final(
                task_descriptor,
                payloads=payloads,
                manifest_bytes=manifest_bytes,
            )
        except _FatalArtifact as error:
            raise OneCellCheckpointValidationError("final bundle could not be safely published") from error
        final_state = _load_final(
            task_descriptor,
            binding=selected_binding,
            schedule=schedule,
            request_identity=request_identity,
        )
        try:
            _cleanup_final_temporaries(task_descriptor)
        except _FatalArtifact as error:
            raise OneCellCheckpointValidationError("final temporary cleanup failed") from error
        return OneCellCheckpointProgress(
            disposition="complete",
            trajectory=final_state.trajectory,
            generation=0,
            checkpoint_count=512,
            snapshot_count=16,
            used_fallback=used_fallback,
            manifest_path=os.path.join(task_path, "final.manifest.json"),
        )
    finally:
        if lock_descriptor is not None:
            flock(lock_descriptor, LOCK_UN)
            os.close(lock_descriptor)
        os.close(task_descriptor)
