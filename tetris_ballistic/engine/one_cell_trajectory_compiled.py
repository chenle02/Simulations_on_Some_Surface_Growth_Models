"""Numba-compiled multi-arm chunks for the PRE one-cell trajectory.

This provisional explicit-submodule surface advances the immutable scalar
Slice 5 records through a private unsigned array representation.  Stream-key
derivation and record reconstruction remain exact host operations; all event
selection, boundary recurrence, and accumulator arithmetic run in Numba
nopython code.  The module performs no persistence, configuration, legacy
dispatch, campaign routing, or acquisition.
"""

from __future__ import annotations

import numpy as _np

try:
    from numba import njit as _njit
    from numba import types as _numba_types
    from numba.typed import Dict as _NumbaDict

    from .rng_compiled import (
        _multiply_high_low_kernel as _certified_multiply_high_low_kernel,
    )
    from .rng_compiled import _uniform_below_kernel as _certified_uniform_below_kernel
except ImportError as error:  # pragma: no cover - exercised by package smoke gates
    raise ImportError(
        "tetris_ballistic.engine.one_cell_trajectory_compiled requires a "
        "compatible Numba installation; install the 'tetris_ballistic[hpc]' "
        "extra on a supported Python interpreter"
    ) from error

from .one_cell_boundary import OneCellBoundaryLaw
from .one_cell_trajectory import OneCellScalarArmAccumulator, OneCellScalarTrajectory
from .rng import derive_stream_key as _derive_stream_key

__all__ = ["advance_one_cell_compiled_chunk"]

_U64_MODULUS = 1 << 64
_U64_MAX_INT = _U64_MODULUS - 1
_U128_MODULUS = 1 << 128
_U128_MAX_INT = _U128_MODULUS - 1
_MIN_WIDTH = 3
_MAX_WIDTH = 1024
_GROUP_ID = "pre-one-cell-discovery-v1"

_PRIMARY_SCHEDULE = (0, 1, 2, 5, 10, 25, 50, 100)
_B1_SCHEDULE = (0, 5, 50, 100)
_B2_FULL_SCHEDULE = (5, 50, 90, 95, 98, 99)
_B2_HIGH_SCHEDULE = (90, 95, 98, 99)
_SCHEDULES = (
    _PRIMARY_SCHEDULE,
    _B1_SCHEDULE,
    _B2_FULL_SCHEDULE,
    _B2_HIGH_SCHEDULE,
)

_SCHEDULE_PRIMARY_CODE = 0
_SCHEDULE_B1_CODE = 1
_SCHEDULE_B2_FULL_CODE = 2
_SCHEDULE_B2_HIGH_CODE = 3

_LAW_PERIODIC_CODE = 0
_LAW_HARD_WALL_LEGACY_CODE = 1
_LAW_HARD_WALL_CORRECTED_CODE = 2

_ERROR_NONE = 0
_ERROR_PROTOCOL = 1
_ERROR_REJECTION_EXHAUSTED = 2
_ERROR_ARITHMETIC = 3

_SCALAR_HEIGHT_SUM = 0
_SCALAR_VOID_VOLUME = 1
_SCALAR_ENDPOINT_COUNT = 2
_SCALAR_TRIGGER_COUNT = 3
_SCALAR_MAXIMUM_GAP = 4
_SCALAR_SEAM_SCRATCH = 5
_SCALAR_Q_HIGH = 6
_SCALAR_Q_LOW = 7

_U64_ZERO = _np.uint64(0)
_U64_ONE = _np.uint64(1)
_U64_MAX = _np.uint64(_U64_MAX_INT)
_CONTACT_N_MINUS_ONE = _np.uint64(99)

_BOUNDARY_LAW_TYPE = OneCellBoundaryLaw
_ARM_TYPE = OneCellScalarArmAccumulator
_TRAJECTORY_TYPE = OneCellScalarTrajectory
_NUMPY_MODULE = _np
_NUMBA_DICT_TYPE = _NumbaDict
_NUMBA_TYPES_MODULE = _numba_types
_CERTIFIED_DERIVE_STREAM_KEY = _derive_stream_key
_CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL = _certified_multiply_high_low_kernel
_CERTIFIED_UNIFORM_BELOW_KERNEL = _certified_uniform_below_kernel

_PERIODIC = _BOUNDARY_LAW_TYPE.PERIODIC
_HARD_WALL_LEGACY = _BOUNDARY_LAW_TYPE.HARD_WALL_LEGACY_ASYMMETRIC
_HARD_WALL_CORRECTED = _BOUNDARY_LAW_TYPE.HARD_WALL_REFLECTION_SYMMETRIC
_BOUNDARY_LAWS = (_PERIODIC, _HARD_WALL_LEGACY, _HARD_WALL_CORRECTED)


def _assert_contract_integrity(
    *,
    _boundary_law_type: object = _BOUNDARY_LAW_TYPE,
    _arm_type: object = _ARM_TYPE,
    _trajectory_type: object = _TRAJECTORY_TYPE,
    _numpy_module: object = _NUMPY_MODULE,
    _numba_dict_type: object = _NUMBA_DICT_TYPE,
    _numba_types_module: object = _NUMBA_TYPES_MODULE,
    _derive_key: object = _CERTIFIED_DERIVE_STREAM_KEY,
    _multiply_kernel: object = _CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL,
    _uniform_kernel: object = _CERTIFIED_UNIFORM_BELOW_KERNEL,
    _periodic: object = _PERIODIC,
    _legacy: object = _HARD_WALL_LEGACY,
    _corrected: object = _HARD_WALL_CORRECTED,
    _primary_schedule: object = _PRIMARY_SCHEDULE,
    _b1_schedule: object = _B1_SCHEDULE,
    _b2_full_schedule: object = _B2_FULL_SCHEDULE,
    _b2_high_schedule: object = _B2_HIGH_SCHEDULE,
    _schedules: object = _SCHEDULES,
) -> None:
    """Fail closed if a captured scientific authority was rebound."""

    if (
        _BOUNDARY_LAW_TYPE is not _boundary_law_type
        or _ARM_TYPE is not _arm_type
        or _TRAJECTORY_TYPE is not _trajectory_type
        or _NUMPY_MODULE is not _numpy_module
        or _np is not _numpy_module
        or _NUMBA_DICT_TYPE is not _numba_dict_type
        or _NumbaDict is not _numba_dict_type
        or _NUMBA_TYPES_MODULE is not _numba_types_module
        or _numba_types is not _numba_types_module
        or _CERTIFIED_DERIVE_STREAM_KEY is not _derive_key
        or _CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL is not _multiply_kernel
        or _CERTIFIED_UNIFORM_BELOW_KERNEL is not _uniform_kernel
    ):
        raise AssertionError("captured Slice 4/5 authority objects have been rebound")
    if (
        _PERIODIC is not _periodic
        or _HARD_WALL_LEGACY is not _legacy
        or _HARD_WALL_CORRECTED is not _corrected
        or type(_BOUNDARY_LAWS) is not tuple
        or _BOUNDARY_LAWS != (_periodic, _legacy, _corrected)
    ):
        raise AssertionError("compiled boundary identities do not match the frozen protocol")
    if (
        type(_U64_MODULUS) is not int
        or _U64_MODULUS != 1 << 64
        or type(_U64_MAX_INT) is not int
        or _U64_MAX_INT != (1 << 64) - 1
        or type(_U128_MODULUS) is not int
        or _U128_MODULUS != 1 << 128
        or type(_U128_MAX_INT) is not int
        or _U128_MAX_INT != (1 << 128) - 1
    ):
        raise AssertionError("compiled unsigned bounds do not match the frozen protocol")
    if type(_MIN_WIDTH) is not int or _MIN_WIDTH != 3 or type(_MAX_WIDTH) is not int or _MAX_WIDTH != 1024:
        raise AssertionError("compiled width bounds do not match the frozen protocol")
    if type(_GROUP_ID) is not str or _GROUP_ID != "pre-one-cell-discovery-v1":
        raise AssertionError("compiled coupling group does not match the frozen protocol")
    if (
        type(_SCHEDULES) is not tuple
        or _PRIMARY_SCHEDULE is not _primary_schedule
        or _B1_SCHEDULE is not _b1_schedule
        or _B2_FULL_SCHEDULE is not _b2_full_schedule
        or _B2_HIGH_SCHEDULE is not _b2_high_schedule
        or _SCHEDULES is not _schedules
        or _SCHEDULES
        != (
            (0, 1, 2, 5, 10, 25, 50, 100),
            (0, 5, 50, 100),
            (5, 50, 90, 95, 98, 99),
            (90, 95, 98, 99),
        )
        or any(type(schedule) is not tuple for schedule in _SCHEDULES)
        or any(type(threshold) is not int for schedule in _SCHEDULES for threshold in schedule)
    ):
        raise AssertionError("compiled schedules do not match the frozen protocol")
    integer_constants = (
        (_SCHEDULE_PRIMARY_CODE, 0),
        (_SCHEDULE_B1_CODE, 1),
        (_SCHEDULE_B2_FULL_CODE, 2),
        (_SCHEDULE_B2_HIGH_CODE, 3),
        (_LAW_PERIODIC_CODE, 0),
        (_LAW_HARD_WALL_LEGACY_CODE, 1),
        (_LAW_HARD_WALL_CORRECTED_CODE, 2),
        (_ERROR_NONE, 0),
        (_ERROR_PROTOCOL, 1),
        (_ERROR_REJECTION_EXHAUSTED, 2),
        (_ERROR_ARITHMETIC, 3),
    )
    if any(type(actual) is not int or actual != expected for actual, expected in integer_constants):
        raise AssertionError("compiled law, schedule, or status codes do not match the frozen protocol")
    scalar_columns = (
        (_SCALAR_HEIGHT_SUM, 0),
        (_SCALAR_VOID_VOLUME, 1),
        (_SCALAR_ENDPOINT_COUNT, 2),
        (_SCALAR_TRIGGER_COUNT, 3),
        (_SCALAR_MAXIMUM_GAP, 4),
        (_SCALAR_SEAM_SCRATCH, 5),
        (_SCALAR_Q_HIGH, 6),
        (_SCALAR_Q_LOW, 7),
    )
    if any(type(actual) is not int or actual != expected for actual, expected in scalar_columns):
        raise AssertionError("compiled scalar columns do not match the frozen protocol")
    unsigned_words = (
        (_U64_ZERO, 0),
        (_U64_ONE, 1),
        (_U64_MAX, _U64_MAX_INT),
        (_CONTACT_N_MINUS_ONE, 99),
    )
    if any(type(actual) is not _np.uint64 or int(actual) != expected for actual, expected in unsigned_words):
        raise AssertionError("compiled unsigned word constants do not match the frozen protocol")


def _require_plain_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _require_uint(value: object, *, maximum: int, label: str) -> int:
    result = _require_plain_int(value, label=label)
    if not 0 <= result <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return result


def _snapshot_trajectory(value: object) -> OneCellScalarTrajectory:
    _assert_contract_integrity()
    if type(value) is not _TRAJECTORY_TYPE:
        raise TypeError("trajectory must be a OneCellScalarTrajectory")
    try:
        return _TRAJECTORY_TYPE(
            root_seed=value.root_seed,
            boundary_law=value.boundary_law,
            width=value.width,
            event_count=value.event_count,
            arms=value.arms,
        )
    except AttributeError as error:
        raise TypeError("trajectory must be fully initialized") from error


def _validate_stop(trajectory: OneCellScalarTrajectory, value: object) -> int:
    stop = _require_uint(value, maximum=_U64_MAX_INT, label="stop_event_ordinal")
    if stop < trajectory.event_count:
        raise ValueError("stop_event_ordinal must not precede trajectory.event_count")
    if trajectory.width * stop >= _U64_MODULUS:
        raise ValueError("width * stop_event_ordinal must be less than 2**64")
    if trajectory.width * stop * stop >= _U128_MODULUS:
        raise ValueError("width * stop_event_ordinal**2 must be less than 2**128")
    return stop


def _schedule_code(trajectory: OneCellScalarTrajectory) -> int:
    thresholds = tuple(arm.threshold for arm in trajectory.arms)
    for code, schedule in enumerate(_SCHEDULES):
        if thresholds == schedule:
            return code
    raise ValueError("trajectory arms must equal one complete frozen threshold schedule")


def _law_code(law: OneCellBoundaryLaw) -> int:
    if law is _PERIODIC:
        return _LAW_PERIODIC_CODE
    if law is _HARD_WALL_LEGACY:
        return _LAW_HARD_WALL_LEGACY_CODE
    if law is _HARD_WALL_CORRECTED:
        return _LAW_HARD_WALL_CORRECTED_CODE
    raise AssertionError("validated trajectory contains an unknown boundary law")


def _snapshot_derived_key(value: object, *, label: str) -> tuple[int, int]:
    if type(value) is not tuple or len(value) != 2:
        raise AssertionError(f"{label} key derivation returned a malformed key")
    try:
        first = _require_uint(value[0], maximum=_U64_MAX_INT, label=f"{label} key word 0")
        second = _require_uint(value[1], maximum=_U64_MAX_INT, label=f"{label} key word 1")
    except (TypeError, ValueError) as error:
        raise AssertionError(f"{label} key derivation returned malformed words") from error
    return first, second


def _derive_chunk_keys(root_seed: int) -> tuple[tuple[int, int], tuple[int, int]]:
    launch = _snapshot_derived_key(
        _CERTIFIED_DERIVE_STREAM_KEY(root_seed, _GROUP_ID, "launch"),
        label="launch",
    )
    contact = _snapshot_derived_key(
        _CERTIFIED_DERIVE_STREAM_KEY(root_seed, _GROUP_ID, "contact"),
        label="contact",
    )
    return launch, contact


@_njit(cache=False, fastmath=False)
def _add_u128_words_kernel(left_high, left_low, right_high, right_low):
    """Add two high-first unsigned-128 word pairs with overflow evidence."""

    low = left_low + right_low
    carry = low < left_low
    high_without_carry = left_high + right_high
    if high_without_carry < left_high:
        return _U64_ZERO, _U64_ZERO, True
    high = high_without_carry + (_U64_ONE if carry else _U64_ZERO)
    if high < high_without_carry:
        return _U64_ZERO, _U64_ZERO, True
    return high, low, False


@_njit(cache=False, fastmath=False)
def _subtract_u128_words_kernel(left_high, left_low, right_high, right_low):
    """Subtract two high-first unsigned-128 word pairs with underflow evidence."""

    borrow = left_low < right_low
    if left_high < right_high or (left_high == right_high and borrow):
        return _U64_ZERO, _U64_ZERO, True
    low = left_low - right_low
    high = left_high - right_high - (_U64_ONE if borrow else _U64_ZERO)
    return high, low, False


def _make_replace_square_sum_kernel(multiply_kernel):
    """Close the packed-Q update over the captured certified multiplier."""

    captured_multiply = multiply_kernel

    @_njit(cache=False, fastmath=False)
    def replace_square_sum(q_high, q_low, old_height, new_height):
        new_high, new_low = captured_multiply(new_height, new_height)
        old_high, old_low = captured_multiply(old_height, old_height)
        delta_high, delta_low, underflow = _subtract_u128_words_kernel(
            new_high,
            new_low,
            old_high,
            old_low,
        )
        if underflow:
            return _U64_ZERO, _U64_ZERO, True
        result_high, result_low, overflow = _add_u128_words_kernel(
            q_high,
            q_low,
            delta_high,
            delta_low,
        )
        return result_high, result_low, overflow

    return replace_square_sum


_replace_square_sum_kernel = _make_replace_square_sum_kernel(_CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL)


@_njit(cache=False, fastmath=False)
def _add_u64_checked_kernel(left, right):
    result = left + right
    return result, result < left


@_njit(cache=False, fastmath=False)
def _arm_count_for_schedule_kernel(schedule_code):
    if schedule_code == _np.uint64(_SCHEDULE_PRIMARY_CODE):
        return 8
    if schedule_code == _np.uint64(_SCHEDULE_B1_CODE):
        return 4
    if schedule_code == _np.uint64(_SCHEDULE_B2_FULL_CODE):
        return 6
    if schedule_code == _np.uint64(_SCHEDULE_B2_HIGH_CODE):
        return 4
    return 0


@_njit(cache=False, fastmath=False)
def _threshold_for_arm_kernel(schedule_code, arm_index):
    if schedule_code == _np.uint64(_SCHEDULE_PRIMARY_CODE):
        if arm_index == 0:
            return _np.uint64(0), False
        if arm_index == 1:
            return _np.uint64(1), False
        if arm_index == 2:
            return _np.uint64(2), False
        if arm_index == 3:
            return _np.uint64(5), False
        if arm_index == 4:
            return _np.uint64(10), False
        if arm_index == 5:
            return _np.uint64(25), False
        if arm_index == 6:
            return _np.uint64(50), False
        if arm_index == 7:
            return _np.uint64(100), False
        return _U64_ZERO, True
    if schedule_code == _np.uint64(_SCHEDULE_B1_CODE):
        if arm_index == 0:
            return _np.uint64(0), False
        if arm_index == 1:
            return _np.uint64(5), False
        if arm_index == 2:
            return _np.uint64(50), False
        if arm_index == 3:
            return _np.uint64(100), False
        return _U64_ZERO, True
    if schedule_code == _np.uint64(_SCHEDULE_B2_FULL_CODE):
        if arm_index == 0:
            return _np.uint64(5), False
        if arm_index == 1:
            return _np.uint64(50), False
        if arm_index == 2:
            return _np.uint64(90), False
        if arm_index == 3:
            return _np.uint64(95), False
        if arm_index == 4:
            return _np.uint64(98), False
        if arm_index == 5:
            return _np.uint64(99), False
        return _U64_ZERO, True
    if schedule_code == _np.uint64(_SCHEDULE_B2_HIGH_CODE):
        if arm_index == 0:
            return _np.uint64(90), False
        if arm_index == 1:
            return _np.uint64(95), False
        if arm_index == 2:
            return _np.uint64(98), False
        if arm_index == 3:
            return _np.uint64(99), False
        return _U64_ZERO, True
    return _U64_ZERO, True


def _make_chunk_kernel(uniform_dispatcher):
    """Build the exact chunk body around one nopython uniform dispatcher."""

    captured_uniform = uniform_dispatcher
    captured_replace_square_sum = _replace_square_sum_kernel

    @_njit(cache=False, fastmath=False)
    def chunk_kernel(
        launch_key_0,
        launch_key_1,
        contact_key_0,
        contact_key_1,
        start_event,
        stop_event,
        law_code,
        schedule_code,
        heights,
        scalars,
        causal_counts,
        causal_gap_sums,
        equality_counts,
        histogram,
    ):
        expected_arm_count = _arm_count_for_schedule_kernel(schedule_code)
        if expected_arm_count == 0:
            return (
                _np.uint64(_ERROR_PROTOCOL),
                start_event,
                _U64_ZERO,
                _U64_ZERO,
            )
        if law_code > _np.uint64(_LAW_HARD_WALL_CORRECTED_CODE):
            return (
                _np.uint64(_ERROR_PROTOCOL),
                start_event,
                _U64_ZERO,
                _U64_ZERO,
            )
        if start_event > stop_event:
            return (
                _np.uint64(_ERROR_PROTOCOL),
                start_event,
                _U64_ZERO,
                _U64_ZERO,
            )
        if (
            heights.shape[0] != expected_arm_count
            or heights.shape[1] < _MIN_WIDTH
            or heights.shape[1] > _MAX_WIDTH
            or scalars.shape[0] != expected_arm_count
            or scalars.shape[1] != 8
            or causal_counts.shape[0] != expected_arm_count
            or causal_counts.shape[1] != 4
            or causal_gap_sums.shape[0] != expected_arm_count
            or causal_gap_sums.shape[1] != 4
            or equality_counts.shape[0] != expected_arm_count
            or equality_counts.shape[1] != 2
            or equality_counts.shape[2] != 8
        ):
            return (
                _np.uint64(_ERROR_PROTOCOL),
                start_event,
                _U64_ZERO,
                _U64_ZERO,
            )

        for arm_index in range(expected_arm_count):
            _, invalid_threshold = _threshold_for_arm_kernel(schedule_code, arm_index)
            if invalid_threshold:
                return (
                    _np.uint64(_ERROR_PROTOCOL),
                    start_event,
                    _np.uint64(arm_index),
                    _U64_ZERO,
                )
            if law_code != _np.uint64(_LAW_PERIODIC_CODE) and scalars[arm_index, _SCALAR_SEAM_SCRATCH] != _U64_ZERO:
                return (
                    _np.uint64(_ERROR_PROTOCOL),
                    start_event,
                    _np.uint64(arm_index),
                    _U64_ZERO,
                )
        for key in histogram:
            if key[0] >= _np.uint64(expected_arm_count):
                return (
                    _np.uint64(_ERROR_PROTOCOL),
                    start_event,
                    key[0],
                    _U64_ZERO,
                )

        width = heights.shape[1]
        event = start_event
        while event < stop_event:
            launch, launch_rejection, launch_exhausted = captured_uniform(
                launch_key_0,
                launch_key_1,
                event,
                _np.uint64(width - 1),
                _U64_ZERO,
            )
            if launch_exhausted:
                return (
                    _np.uint64(_ERROR_REJECTION_EXHAUSTED),
                    event,
                    _U64_ZERO,
                    launch_rejection,
                )
            contact, contact_rejection, contact_exhausted = captured_uniform(
                contact_key_0,
                contact_key_1,
                event,
                _CONTACT_N_MINUS_ONE,
                _U64_ZERO,
            )
            if contact_exhausted:
                return (
                    _np.uint64(_ERROR_REJECTION_EXHAUSTED),
                    event,
                    _U64_ONE,
                    contact_rejection,
                )
            if launch >= _np.uint64(width) or contact >= _np.uint64(100):
                return (
                    _np.uint64(_ERROR_PROTOCOL),
                    event,
                    _U64_ZERO,
                    _U64_ZERO,
                )

            launch_index = int(launch)
            for arm_index in range(expected_arm_count):
                threshold, invalid_threshold = _threshold_for_arm_kernel(schedule_code, arm_index)
                if invalid_threshold:
                    return (
                        _np.uint64(_ERROR_PROTOCOL),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                old_height = heights[arm_index, launch_index]
                if old_height == _U64_MAX:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                vertical_height = old_height + _U64_ONE

                left_exists = False
                right_exists = False
                left_eligible = False
                right_eligible = False
                left_height = _U64_ZERO
                right_height = _U64_ZERO
                if law_code == _np.uint64(_LAW_PERIODIC_CODE):
                    left_index = width - 1 if launch_index == 0 else launch_index - 1
                    right_index = 0 if launch_index == width - 1 else launch_index + 1
                    left_height = heights[arm_index, left_index]
                    right_height = heights[arm_index, right_index]
                    left_exists = True
                    right_exists = True
                    left_eligible = True
                    right_eligible = True
                else:
                    if launch_index > 0:
                        left_exists = True
                        left_height = heights[arm_index, launch_index - 1]
                    if launch_index < width - 1:
                        right_exists = True
                        right_height = heights[arm_index, launch_index + 1]
                        right_eligible = True
                    if law_code == _np.uint64(_LAW_HARD_WALL_LEGACY_CODE):
                        left_eligible = launch_index > 1
                    else:
                        left_eligible = launch_index > 0

                endpoint_selected = contact < threshold
                new_height = vertical_height
                if endpoint_selected:
                    if left_eligible and left_height > new_height:
                        new_height = left_height
                    if right_eligible and right_height > new_height:
                        new_height = right_height

                delta_s = new_height - old_height
                delta_v = new_height - vertical_height
                positive_gap = endpoint_selected and delta_v > _U64_ZERO

                causal_index = 0
                if positive_gap:
                    left_causal = left_eligible and left_height == new_height
                    right_causal = right_eligible and right_height == new_height
                    if left_causal and right_causal:
                        causal_index = 3
                    elif left_causal:
                        causal_index = 1
                    elif right_causal:
                        causal_index = 2
                    else:
                        return (
                            _np.uint64(_ERROR_PROTOCOL),
                            event,
                            _np.uint64(arm_index),
                            _U64_ZERO,
                        )

                equality_mask = 0
                if new_height == vertical_height:
                    equality_mask += 1
                if left_exists and left_height == new_height:
                    equality_mask += 2
                if right_exists and right_height == new_height:
                    equality_mask += 4
                if equality_mask == 0 or equality_mask > 7:
                    return (
                        _np.uint64(_ERROR_PROTOCOL),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                height_sum, overflow = _add_u64_checked_kernel(
                    scalars[arm_index, _SCALAR_HEIGHT_SUM],
                    delta_s,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                void_volume, overflow = _add_u64_checked_kernel(
                    scalars[arm_index, _SCALAR_VOID_VOLUME],
                    delta_v,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                endpoint_count, overflow = _add_u64_checked_kernel(
                    scalars[arm_index, _SCALAR_ENDPOINT_COUNT],
                    _U64_ONE if endpoint_selected else _U64_ZERO,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                trigger_count, overflow = _add_u64_checked_kernel(
                    scalars[arm_index, _SCALAR_TRIGGER_COUNT],
                    _U64_ONE if positive_gap else _U64_ZERO,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                q_high, q_low, q_failure = captured_replace_square_sum(
                    scalars[arm_index, _SCALAR_Q_HIGH],
                    scalars[arm_index, _SCALAR_Q_LOW],
                    old_height,
                    new_height,
                )
                if q_failure:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                causal_count, overflow = _add_u64_checked_kernel(
                    causal_counts[arm_index, causal_index],
                    _U64_ONE,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                causal_gap_sum, overflow = _add_u64_checked_kernel(
                    causal_gap_sums[arm_index, causal_index],
                    delta_v,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )
                endpoint_index = 1 if endpoint_selected else 0
                equality_count, overflow = _add_u64_checked_kernel(
                    equality_counts[arm_index, endpoint_index, equality_mask],
                    _U64_ONE,
                )
                if overflow:
                    return (
                        _np.uint64(_ERROR_ARITHMETIC),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                seam_scratch = scalars[arm_index, _SCALAR_SEAM_SCRATCH]
                if law_code == _np.uint64(_LAW_PERIODIC_CODE):
                    seam_equality = (launch_index == 0 and left_exists and left_height == new_height) or (
                        launch_index == width - 1 and right_exists and right_height == new_height
                    )
                    seam_scratch, overflow = _add_u64_checked_kernel(
                        seam_scratch,
                        _U64_ONE if seam_equality else _U64_ZERO,
                    )
                    if overflow:
                        return (
                            _np.uint64(_ERROR_ARITHMETIC),
                            event,
                            _np.uint64(arm_index),
                            _U64_ZERO,
                        )
                elif seam_scratch != _U64_ZERO:
                    return (
                        _np.uint64(_ERROR_PROTOCOL),
                        event,
                        _np.uint64(arm_index),
                        _U64_ZERO,
                    )

                histogram_key = (_np.uint64(arm_index), delta_v)
                if histogram_key in histogram:
                    histogram_count, overflow = _add_u64_checked_kernel(
                        histogram[histogram_key],
                        _U64_ONE,
                    )
                    if overflow:
                        return (
                            _np.uint64(_ERROR_ARITHMETIC),
                            event,
                            _np.uint64(arm_index),
                            _U64_ZERO,
                        )
                else:
                    histogram_count = _U64_ONE

                heights[arm_index, launch_index] = new_height
                scalars[arm_index, _SCALAR_HEIGHT_SUM] = height_sum
                scalars[arm_index, _SCALAR_VOID_VOLUME] = void_volume
                scalars[arm_index, _SCALAR_ENDPOINT_COUNT] = endpoint_count
                scalars[arm_index, _SCALAR_TRIGGER_COUNT] = trigger_count
                if delta_v > scalars[arm_index, _SCALAR_MAXIMUM_GAP]:
                    scalars[arm_index, _SCALAR_MAXIMUM_GAP] = delta_v
                scalars[arm_index, _SCALAR_SEAM_SCRATCH] = seam_scratch
                scalars[arm_index, _SCALAR_Q_HIGH] = q_high
                scalars[arm_index, _SCALAR_Q_LOW] = q_low
                causal_counts[arm_index, causal_index] = causal_count
                causal_gap_sums[arm_index, causal_index] = causal_gap_sum
                equality_counts[arm_index, endpoint_index, equality_mask] = equality_count
                histogram[histogram_key] = histogram_count

            if event == _U64_MAX:
                return (
                    _np.uint64(_ERROR_ARITHMETIC),
                    event,
                    _U64_ZERO,
                    _U64_ZERO,
                )
            event += _U64_ONE

        return _np.uint64(_ERROR_NONE), event, _U64_ZERO, _U64_ZERO

    return chunk_kernel


_COMPILED_CHUNK_KERNEL = _make_chunk_kernel(_CERTIFIED_UNIFORM_BELOW_KERNEL)


@_njit(cache=False, fastmath=False)
def _histogram_items_kernel(histogram):
    """Copy the sparse map to unsigned arrays for exact host reconstruction."""

    keys = _np.empty((len(histogram), 2), dtype=_np.uint64)
    counts = _np.empty(len(histogram), dtype=_np.uint64)
    index = 0
    for key, count in histogram.items():
        keys[index, 0] = key[0]
        keys[index, 1] = key[1]
        counts[index] = count
        index += 1
    return keys, counts


def _validate_unsigned_array(
    value: object,
    *,
    shape: tuple[int, ...],
    label: str,
) -> _np.ndarray:
    if type(value) is not _np.ndarray:
        raise AssertionError(f"{label} must be an exact NumPy array")
    if value.dtype != _np.dtype(_np.uint64) or not value.dtype.isnative:
        raise AssertionError(f"{label} must use native-endian uint64")
    if value.shape != shape:
        raise AssertionError(f"{label} has a malformed shape")
    if not value.flags.c_contiguous:
        raise AssertionError(f"{label} must be C-contiguous")
    return value


def _validate_compiled_state(
    *,
    heights: object,
    scalars: object,
    causal_counts: object,
    causal_gap_sums: object,
    equality_counts: object,
    arm_count: int,
    width: int,
) -> tuple[_np.ndarray, _np.ndarray, _np.ndarray, _np.ndarray, _np.ndarray]:
    arrays = (
        _validate_unsigned_array(heights, shape=(arm_count, width), label="heights"),
        _validate_unsigned_array(scalars, shape=(arm_count, 8), label="scalars"),
        _validate_unsigned_array(causal_counts, shape=(arm_count, 4), label="causal_counts"),
        _validate_unsigned_array(causal_gap_sums, shape=(arm_count, 4), label="causal_gap_sums"),
        _validate_unsigned_array(equality_counts, shape=(arm_count, 2, 8), label="equality_counts"),
    )
    for index, left in enumerate(arrays):
        for right in arrays[index + 1 :]:
            if _np.shares_memory(left, right):
                raise AssertionError("compiled state arrays must not alias")
    return arrays


def _pack_compiled_state(trajectory: OneCellScalarTrajectory):
    arm_count = len(trajectory.arms)
    heights = _np.empty((arm_count, trajectory.width), dtype=_np.uint64, order="C")
    scalars = _np.zeros((arm_count, 8), dtype=_np.uint64, order="C")
    causal_counts = _np.empty((arm_count, 4), dtype=_np.uint64, order="C")
    causal_gap_sums = _np.empty((arm_count, 4), dtype=_np.uint64, order="C")
    equality_counts = _np.empty((arm_count, 2, 8), dtype=_np.uint64, order="C")
    histogram = _NumbaDict.empty(
        key_type=_numba_types.UniTuple(_numba_types.uint64, 2),
        value_type=_numba_types.uint64,
    )

    for arm_index, arm in enumerate(trajectory.arms):
        heights[arm_index, :] = arm.heights
        scalars[arm_index, _SCALAR_HEIGHT_SUM] = arm.height_sum
        scalars[arm_index, _SCALAR_VOID_VOLUME] = arm.void_volume
        scalars[arm_index, _SCALAR_ENDPOINT_COUNT] = arm.endpoint_selected_count
        scalars[arm_index, _SCALAR_TRIGGER_COUNT] = arm.positive_gap_trigger_count
        scalars[arm_index, _SCALAR_MAXIMUM_GAP] = arm.maximum_gap
        scalars[arm_index, _SCALAR_SEAM_SCRATCH] = arm.seam_equality_count or 0
        scalars[arm_index, _SCALAR_Q_HIGH] = arm.height_square_sum >> 64
        scalars[arm_index, _SCALAR_Q_LOW] = arm.height_square_sum & _U64_MAX_INT
        causal_counts[arm_index, :] = arm.causal_counts
        causal_gap_sums[arm_index, :] = arm.causal_gap_sums
        equality_counts[arm_index, :, :] = arm.endpoint_equality_mask_counts
        for gap, count in arm.gap_histogram:
            histogram[(_np.uint64(arm_index), _np.uint64(gap))] = _np.uint64(count)

    validated = _validate_compiled_state(
        heights=heights,
        scalars=scalars,
        causal_counts=causal_counts,
        causal_gap_sums=causal_gap_sums,
        equality_counts=equality_counts,
        arm_count=arm_count,
        width=trajectory.width,
    )
    return (*validated, histogram)


def _unpack_compiled_state(
    *,
    source: OneCellScalarTrajectory,
    stop: int,
    schedule: tuple[int, ...],
    heights: object,
    scalars: object,
    causal_counts: object,
    causal_gap_sums: object,
    equality_counts: object,
    histogram: object,
) -> OneCellScalarTrajectory:
    arm_count = len(schedule)
    arrays = _validate_compiled_state(
        heights=heights,
        scalars=scalars,
        causal_counts=causal_counts,
        causal_gap_sums=causal_gap_sums,
        equality_counts=equality_counts,
        arm_count=arm_count,
        width=source.width,
    )
    heights_array, scalars_array, causal_array, causal_gap_array, equality_array = arrays

    histogram_rows: list[list[tuple[int, int]]] = [[] for _ in range(arm_count)]
    try:
        histogram_keys, histogram_counts = _histogram_items_kernel(histogram)
    except (AttributeError, TypeError, ValueError) as error:
        raise AssertionError("compiled histogram is malformed") from error
    if (
        type(histogram_keys) is not _np.ndarray
        or histogram_keys.dtype != _np.dtype(_np.uint64)
        or not histogram_keys.dtype.isnative
        or histogram_keys.ndim != 2
        or histogram_keys.shape[1] != 2
        or not histogram_keys.flags.c_contiguous
        or type(histogram_counts) is not _np.ndarray
        or histogram_counts.dtype != _np.dtype(_np.uint64)
        or not histogram_counts.dtype.isnative
        or histogram_counts.shape != (histogram_keys.shape[0],)
        or not histogram_counts.flags.c_contiguous
    ):
        raise AssertionError("compiled histogram snapshot arrays are malformed")
    for key, value in zip(histogram_keys, histogram_counts):
        try:
            arm_index = int(key[0])
            gap = int(key[1])
            count = int(value)
        except (TypeError, ValueError, OverflowError) as error:
            raise AssertionError("compiled histogram contains malformed entries") from error
        if not 0 <= arm_index < arm_count or not 0 <= gap <= _U64_MAX_INT or not 1 <= count <= _U64_MAX_INT:
            raise AssertionError("compiled histogram contains out-of-range entries")
        histogram_rows[arm_index].append((gap, count))

    arms: list[OneCellScalarArmAccumulator] = []
    try:
        for arm_index, threshold in enumerate(schedule):
            seam_scratch = int(scalars_array[arm_index, _SCALAR_SEAM_SCRATCH])
            if source.boundary_law is not _PERIODIC and seam_scratch != 0:
                raise AssertionError("hard-wall compiled seam scratch must remain zero")
            q = (int(scalars_array[arm_index, _SCALAR_Q_HIGH]) << 64) | int(scalars_array[arm_index, _SCALAR_Q_LOW])
            arms.append(
                _ARM_TYPE(
                    boundary_law=source.boundary_law,
                    threshold=threshold,
                    heights=tuple(int(value) for value in heights_array[arm_index]),
                    event_count=stop,
                    height_sum=int(scalars_array[arm_index, _SCALAR_HEIGHT_SUM]),
                    height_square_sum=q,
                    void_volume=int(scalars_array[arm_index, _SCALAR_VOID_VOLUME]),
                    endpoint_selected_count=int(scalars_array[arm_index, _SCALAR_ENDPOINT_COUNT]),
                    positive_gap_trigger_count=int(scalars_array[arm_index, _SCALAR_TRIGGER_COUNT]),
                    gap_sum=int(scalars_array[arm_index, _SCALAR_VOID_VOLUME]),
                    maximum_gap=int(scalars_array[arm_index, _SCALAR_MAXIMUM_GAP]),
                    causal_counts=tuple(int(value) for value in causal_array[arm_index]),
                    causal_gap_sums=tuple(int(value) for value in causal_gap_array[arm_index]),
                    endpoint_equality_mask_counts=tuple(
                        tuple(int(value) for value in row) for row in equality_array[arm_index]
                    ),
                    gap_histogram=tuple(sorted(histogram_rows[arm_index])),
                    seam_equality_count=seam_scratch if source.boundary_law is _PERIODIC else None,
                )
            )
        result = _TRAJECTORY_TYPE(
            root_seed=source.root_seed,
            boundary_law=source.boundary_law,
            width=source.width,
            event_count=stop,
            arms=tuple(arms),
        )
    except AssertionError:
        raise
    except (TypeError, ValueError, OverflowError) as error:
        raise AssertionError("compiled result failed exact Slice 5 reconstruction") from error
    return result


def _raise_kernel_failure(result: object) -> None:
    if type(result) is not tuple or len(result) != 4:
        raise AssertionError("compiled chunk returned malformed status evidence")
    try:
        code, event, arm, detail = (int(value) for value in result)
    except (TypeError, ValueError, OverflowError) as error:
        raise AssertionError("compiled chunk returned malformed status words") from error
    if code == _ERROR_REJECTION_EXHAUSTED:
        stream = "launch" if arm == 0 else "contact"
        raise OverflowError(f"compiled {stream} rejection ordinal exhausted at event {event} (last rejection {detail})")
    if code == _ERROR_ARITHMETIC:
        raise OverflowError(f"compiled unsigned arithmetic failed at event {event}, arm {arm}")
    if code != _ERROR_NONE:
        raise AssertionError(f"compiled chunk rejected private protocol state at event {event}, arm {arm}")


def _advance_compiled_chunk_with_kernel(
    *,
    trajectory: OneCellScalarTrajectory,
    stop_event_ordinal: int,
    kernel: object,
) -> OneCellScalarTrajectory:
    """Private certification route for one factory-specialized dispatcher."""

    _assert_contract_integrity()
    if not callable(kernel):
        raise TypeError("kernel must be callable")
    snapshot = _snapshot_trajectory(trajectory)
    stop = _validate_stop(snapshot, stop_event_ordinal)
    schedule_code = _schedule_code(snapshot)
    law_code = _law_code(snapshot.boundary_law)
    if stop == snapshot.event_count:
        return snapshot

    launch_key, contact_key = _derive_chunk_keys(snapshot.root_seed)
    heights, scalars, causal_counts, causal_gap_sums, equality_counts, histogram = _pack_compiled_state(snapshot)
    status = kernel(
        _np.uint64(launch_key[0]),
        _np.uint64(launch_key[1]),
        _np.uint64(contact_key[0]),
        _np.uint64(contact_key[1]),
        _np.uint64(snapshot.event_count),
        _np.uint64(stop),
        _np.uint64(law_code),
        _np.uint64(schedule_code),
        heights,
        scalars,
        causal_counts,
        causal_gap_sums,
        equality_counts,
        histogram,
    )
    _raise_kernel_failure(status)
    return _unpack_compiled_state(
        source=snapshot,
        stop=stop,
        schedule=_SCHEDULES[schedule_code],
        heights=heights,
        scalars=scalars,
        causal_counts=causal_counts,
        causal_gap_sums=causal_gap_sums,
        equality_counts=equality_counts,
        histogram=histogram,
    )


def _assert_runtime_integrity(
    *,
    _add_u128_kernel: object = _add_u128_words_kernel,
    _subtract_u128_kernel: object = _subtract_u128_words_kernel,
    _add_u64_kernel: object = _add_u64_checked_kernel,
    _arm_count_kernel: object = _arm_count_for_schedule_kernel,
    _threshold_kernel: object = _threshold_for_arm_kernel,
    _snapshot: object = _snapshot_trajectory,
    _stop_validator: object = _validate_stop,
    _schedule_selector: object = _schedule_code,
    _law_selector: object = _law_code,
    _key_deriver: object = _derive_chunk_keys,
    _packer: object = _pack_compiled_state,
    _unpacker: object = _unpack_compiled_state,
    _failure_handler: object = _raise_kernel_failure,
    _advance_with_kernel: object = _advance_compiled_chunk_with_kernel,
    _array_validator: object = _validate_unsigned_array,
    _state_validator: object = _validate_compiled_state,
    _kernel: object = _COMPILED_CHUNK_KERNEL,
    _q_kernel: object = _replace_square_sum_kernel,
    _histogram_snapshot_kernel: object = _histogram_items_kernel,
) -> None:
    _assert_contract_integrity()
    if (
        _add_u128_words_kernel is not _add_u128_kernel
        or _subtract_u128_words_kernel is not _subtract_u128_kernel
        or _add_u64_checked_kernel is not _add_u64_kernel
        or _arm_count_for_schedule_kernel is not _arm_count_kernel
        or _threshold_for_arm_kernel is not _threshold_kernel
        or _snapshot_trajectory is not _snapshot
        or _validate_stop is not _stop_validator
        or _schedule_code is not _schedule_selector
        or _law_code is not _law_selector
        or _derive_chunk_keys is not _key_deriver
        or _pack_compiled_state is not _packer
        or _unpack_compiled_state is not _unpacker
        or _raise_kernel_failure is not _failure_handler
        or _advance_compiled_chunk_with_kernel is not _advance_with_kernel
        or _validate_unsigned_array is not _array_validator
        or _validate_compiled_state is not _state_validator
        or _COMPILED_CHUNK_KERNEL is not _kernel
        or _replace_square_sum_kernel is not _q_kernel
        or _histogram_items_kernel is not _histogram_snapshot_kernel
    ):
        raise AssertionError("private compiled trajectory authorities have been rebound")


def advance_one_cell_compiled_chunk(
    *,
    trajectory: OneCellScalarTrajectory,
    stop_event_ordinal: int,
) -> OneCellScalarTrajectory:
    """Advance exactly ``[trajectory.event_count, stop_event_ordinal)``."""

    _assert_runtime_integrity()
    return _advance_compiled_chunk_with_kernel(
        trajectory=trajectory,
        stop_event_ordinal=stop_event_ordinal,
        kernel=_COMPILED_CHUNK_KERNEL,
    )
