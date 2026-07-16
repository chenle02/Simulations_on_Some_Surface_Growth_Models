"""Independent certification for compiled PRE one-cell trajectories.

The oracle in this file is deliberately primitive and production-free.  It
owns the four Article schedules, SHA-256 key derivation, Philox, rejection
mapping, all three boundary recurrences, and every retained trajectory fold.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from itertools import product
from pathlib import Path

import numpy as np
import pytest
from numba import carray, njit, types
from numba.extending import intrinsic

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.one_cell_trajectory as scalar_module
import tetris_ballistic.engine.one_cell_trajectory_compiled as compiled_module
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_trajectory import (
    OneCellScalarArmAccumulator,
    OneCellScalarTrajectory,
    advance_one_cell_scalar_chunk,
    start_one_cell_scalar_trajectory,
)
from tetris_ballistic.engine.one_cell_trajectory_compiled import advance_one_cell_compiled_chunk
from tetris_ballistic.engine.rng_compiled import (
    _map_bounded_word_kernel,
    _prepare_bounded_mapping_kernel,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1
_U64_MASK = _U64_MAX
_GROUP = "pre-one-cell-discovery-v1"
_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"
_M0 = 0xD2E7470EE14C6C93
_M1 = 0xCA5A826395121157
_W0 = 0x9E3779B97F4A7C15
_W1 = 0xBB67AE8584CAA73B

# These literals are test authority.  The oracle never reads production
# schedule constants or production endpoint decisions.
_PRIMARY = (0, 1, 2, 5, 10, 25, 50, 100)
_B1 = (0, 5, 50, 100)
_B2_FULL = (5, 50, 90, 95, 98, 99)
_B2_HIGH = (90, 95, 98, 99)
_SCHEDULES = (_PRIMARY, _B1, _B2_FULL, _B2_HIGH)
_DECISION_REPRESENTATIVES = {
    _PRIMARY: (0, 1, 2, 5, 10, 25, 50),
    _B1: (0, 5, 50),
    _B2_FULL: (0, 5, 50, 90, 95, 98, 99),
    _B2_HIGH: (0, 90, 95, 98, 99),
}
_LAW_IDS = (
    "periodic-v1",
    "hard-wall-legacy-asymmetric-v1",
    "hard-wall-reflection-symmetric-v1",
)
_LAWS = tuple(OneCellBoundaryLaw(law_id) for law_id in _LAW_IDS)
_AUDIT_LAUNCH_KEY = np.uint64(0xA11CE)
_AUDIT_CONTACT_KEY = np.uint64(0xC07AC7)
_AUDIT_WORDS = 64

# Primitive arm tuple indices.  Oracle state consists only of built-in scalar
# values and recursively built-in tuples.
_LAW = 0
_THRESHOLD = 1
_HEIGHTS = 2
_N = 3
_S = 4
_Q = 5
_V = 6
_ENDPOINT = 7
_TRIGGER = 8
_GAP_SUM = 9
_MAX_GAP = 10
_CAUSAL = 11
_CAUSAL_GAPS = 12
_EQUALITY = 13
_HISTOGRAM = 14
_SEAM = 15

_ARM_FIELDS = (
    "boundary_law",
    "threshold",
    "heights",
    "event_count",
    "height_sum",
    "height_square_sum",
    "void_volume",
    "endpoint_selected_count",
    "positive_gap_trigger_count",
    "gap_sum",
    "maximum_gap",
    "causal_counts",
    "causal_gap_sums",
    "endpoint_equality_mask_counts",
    "gap_histogram",
    "seam_equality_count",
)
_TRAJECTORY_FIELDS = ("root_seed", "boundary_law", "width", "event_count", "arms")


class _IntSubclass(int):
    pass


@intrinsic
def _uint64_to_void_pointer(typing_context, source_type):
    """Test-only address cast for a mutable nopython audit buffer."""

    del typing_context
    if source_type != types.uint64:
        return None
    signature = types.voidptr(source_type)

    def codegen(context, builder, signature, arguments):
        del signature
        return builder.inttoptr(arguments[0], context.get_value_type(types.voidptr))

    return signature, codegen


# Nothing named _oracle_* below calls a production RNG, selector, boundary,
# trajectory, accumulator, observable, or compiled helper.
def _oracle_key(root_seed: int, stream_name: str) -> tuple[int, int]:
    group = _GROUP.encode("utf-8")
    stream = stream_name.encode("utf-8")
    preimage = b"".join(
        (
            _DOMAIN,
            root_seed.to_bytes(16, "big"),
            len(group).to_bytes(4, "big"),
            group,
            len(stream).to_bytes(4, "big"),
            stream,
        )
    )
    digest = hashlib.sha256(preimage).digest()[:16]
    return int.from_bytes(digest[:8], "big"), int.from_bytes(digest[8:], "big")


def _oracle_philox(counter: tuple[int, int, int, int], key: tuple[int, int]) -> tuple[int, int, int, int]:
    c0, c1, c2, c3 = counter
    k0, k1 = key
    for round_index in range(10):
        product0 = _M0 * c0
        product1 = _M1 * c2
        high0, low0 = product0 >> 64, product0 & _U64_MASK
        high1, low1 = product1 >> 64, product1 & _U64_MASK
        c0, c1, c2, c3 = high1 ^ c1 ^ k0, low1, high0 ^ c3 ^ k1, low0
        if round_index != 9:
            k0 = (k0 + _W0) & _U64_MASK
            k1 = (k1 + _W1) & _U64_MASK
    return c0, c1, c2, c3


def _oracle_uniform(*, root_seed: int, stream_name: str, event_ordinal: int, upper_bound: int) -> tuple[int, int, int]:
    key = _oracle_key(root_seed, stream_name)
    quotient = _U64_SPACE // upper_bound
    limit = quotient * upper_bound
    rejection = 0
    while True:
        raw = _oracle_philox((event_ordinal, rejection, 0, 0), key)[0]
        if raw < limit:
            return raw // quotient, rejection, raw
        rejection += 1


def _oracle_selection(root_seed: int, width: int, event: int) -> tuple[int, int, int, int]:
    launch, launch_rejection, _ = _oracle_uniform(
        root_seed=root_seed,
        stream_name="launch",
        event_ordinal=event,
        upper_bound=width,
    )
    contact, contact_rejection, _ = _oracle_uniform(
        root_seed=root_seed,
        stream_name="contact",
        event_ordinal=event,
        upper_bound=100,
    )
    return launch, contact, launch_rejection, contact_rejection


def _oracle_transition(
    law_id: str,
    heights: tuple[int, ...],
    launch_x: int,
    sticky: bool,
) -> tuple[tuple[int, ...], int, int, int, int, int | None]:
    width = len(heights)
    vertical = heights[launch_x] + 1
    if law_id == "periodic-v1":
        left = heights[(launch_x - 1) % width]
        right = heights[(launch_x + 1) % width]
        left_eligible = True
        right_eligible = True
    else:
        left = heights[launch_x - 1] if launch_x > 0 else None
        right = heights[launch_x + 1] if launch_x < width - 1 else None
        left_eligible = launch_x > (1 if law_id == "hard-wall-legacy-asymmetric-v1" else 0)
        right_eligible = launch_x < width - 1

    post = vertical
    if sticky and left_eligible:
        post = max(post, left)
    if sticky and right_eligible:
        post = max(post, right)
    gap = post - vertical
    trigger = int(sticky and gap > 0)
    left_causal = bool(trigger and left_eligible and left == post)
    right_causal = bool(trigger and right_eligible and right == post)
    causal = 3 if left_causal and right_causal else 1 if left_causal else 2 if right_causal else 0
    equality_mask = (
        int(post == vertical)
        + 2 * int(left is not None and left == post)
        + 4 * int(right is not None and right == post)
    )
    seam = (
        int((launch_x == 0 and bool(equality_mask & 2)) or (launch_x == width - 1 and bool(equality_mask & 4)))
        if law_id == "periodic-v1"
        else None
    )
    updated = list(heights)
    updated[launch_x] = post
    return tuple(updated), gap, trigger, causal, equality_mask, seam


def _oracle_empty_arm(law_id: str, threshold: int, width: int) -> tuple[object, ...]:
    return (
        law_id,
        threshold,
        (0,) * width,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
        (0, 0, 0, 0),
        (0, 0, 0, 0),
        ((0,) * 8, (0,) * 8),
        (),
        0 if law_id == "periodic-v1" else None,
    )


def _oracle_increment(values: tuple[int, ...], index: int, amount: int = 1) -> tuple[int, ...]:
    return values[:index] + (values[index] + amount,) + values[index + 1 :]


def _oracle_histogram_increment(histogram: tuple[tuple[int, int], ...], gap: int) -> tuple[tuple[int, int], ...]:
    result = []
    inserted = False
    for key, count in histogram:
        if key == gap:
            result.append((key, count + 1))
            inserted = True
        else:
            if not inserted and gap < key:
                result.append((gap, 1))
                inserted = True
            result.append((key, count))
    if not inserted:
        result.append((gap, 1))
    return tuple(result)


def _oracle_fold_arm(arm: tuple[object, ...], launch_x: int, contact: int) -> tuple[object, ...]:
    sticky = contact < arm[_THRESHOLD]
    heights, gap, trigger, causal, equality_mask, seam = _oracle_transition(arm[_LAW], arm[_HEIGHTS], launch_x, sticky)
    old_height = arm[_HEIGHTS][launch_x]
    new_height = heights[launch_x]
    equality = (
        _oracle_increment(arm[_EQUALITY][0], equality_mask) if not sticky else arm[_EQUALITY][0],
        _oracle_increment(arm[_EQUALITY][1], equality_mask) if sticky else arm[_EQUALITY][1],
    )
    return (
        arm[_LAW],
        arm[_THRESHOLD],
        heights,
        arm[_N] + 1,
        arm[_S] + new_height - old_height,
        arm[_Q] + new_height * new_height - old_height * old_height,
        arm[_V] + gap,
        arm[_ENDPOINT] + int(sticky),
        arm[_TRIGGER] + trigger,
        arm[_GAP_SUM] + gap,
        max(arm[_MAX_GAP], gap),
        _oracle_increment(arm[_CAUSAL], causal),
        _oracle_increment(arm[_CAUSAL_GAPS], causal, gap),
        equality,
        _oracle_histogram_increment(arm[_HISTOGRAM], gap),
        arm[_SEAM] + seam if seam is not None else None,
    )


def _oracle_from_tape(
    law_id: str,
    width: int,
    schedule: tuple[int, ...],
    tape: tuple[tuple[int, int], ...],
) -> tuple[tuple[object, ...], ...]:
    arms = tuple(_oracle_empty_arm(law_id, threshold, width) for threshold in schedule)
    for launch_x, contact in tape:
        arms = tuple(_oracle_fold_arm(arm, launch_x, contact) for arm in arms)
    return arms


def _oracle_real(
    root_seed: int,
    law_id: str,
    width: int,
    schedule: tuple[int, ...],
    start: int,
    stop: int,
    arms: tuple[tuple[object, ...], ...] | None = None,
) -> tuple[tuple[tuple[object, ...], ...], tuple[tuple[int, int, int, int], ...]]:
    tape4 = tuple(_oracle_selection(root_seed, width, event) for event in range(start, stop))
    tape2 = tuple((launch, contact) for launch, contact, _, _ in tape4)
    if arms is None:
        assert start == 0
        arms = tuple(_oracle_empty_arm(law_id, threshold, width) for threshold in schedule)
    for launch_x, contact in tape2:
        arms = tuple(_oracle_fold_arm(arm, launch_x, contact) for arm in arms)
    return arms, tape4


def _documented_vector_rows() -> dict[tuple[str, int, tuple[int, ...]], tuple[tuple[object, ...], ...]]:
    """Parse every literal persisted arm row without importing scalar tests."""

    path = _REPO_ROOT / "docs/PRE-ONE-CELL-SCALAR-TRAJECTORY-VECTORS.md"
    grouped: dict[tuple[str, int, tuple[int, ...]], list[tuple[object, ...]]] = {}
    current: tuple[str, int, tuple[int, ...]] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### `") and "`N=" in line:
            quoted = line.split("`")
            law_id = quoted[1]
            event_count = int(next(part[2:] for part in quoted if part.startswith("N=")))
            schedule = _B2_FULL if "B2-full" in line else _PRIMARY
            current = law_id, event_count, schedule
            grouped[current] = []
        elif current is not None and line.startswith("A("):
            literal = ast.literal_eval(line[1:])
            (
                threshold,
                heights,
                moments,
                event_counts,
                causal_counts,
                causal_gap_sums,
                equality_false,
                equality_true,
                histogram,
                seam,
            ) = literal
            height_sum, height_square_sum, roughness, void_volume = moments
            endpoint, trigger, gap_sum, maximum_gap = event_counts
            assert 3 * height_square_sum - height_sum * height_sum == roughness
            grouped[current].append(
                (
                    current[0],
                    threshold,
                    heights,
                    current[1],
                    height_sum,
                    height_square_sum,
                    void_volume,
                    endpoint,
                    trigger,
                    gap_sum,
                    maximum_gap,
                    causal_counts,
                    causal_gap_sums,
                    (equality_false, equality_true),
                    histogram,
                    seam,
                )
            )
    return {key: tuple(rows) for key, rows in grouped.items()}


def _production_arm_tuple(arm: OneCellScalarArmAccumulator) -> tuple[object, ...]:
    return (
        arm.boundary_law.value,
        arm.threshold,
        arm.heights,
        arm.event_count,
        arm.height_sum,
        arm.height_square_sum,
        arm.void_volume,
        arm.endpoint_selected_count,
        arm.positive_gap_trigger_count,
        arm.gap_sum,
        arm.maximum_gap,
        arm.causal_counts,
        arm.causal_gap_sums,
        arm.endpoint_equality_mask_counts,
        arm.gap_histogram,
        arm.seam_equality_count,
    )


def _assert_structural_laws(trajectory: OneCellScalarTrajectory) -> None:
    schedule = trajectory.threshold_schedule
    assert schedule in _SCHEDULES
    assert tuple(arm.threshold for arm in trajectory.arms) == schedule
    prior_endpoint = -1
    prior_heights = (-1,) * trajectory.width
    for arm in trajectory.arms:
        n = trajectory.event_count
        assert arm.event_count == n
        assert arm.boundary_law is trajectory.boundary_law
        assert arm.height_sum == sum(arm.heights)
        assert arm.height_square_sum == sum(height * height for height in arm.heights)
        assert arm.void_volume == arm.height_sum - n == arm.gap_sum
        assert arm.roughness_numerator == trajectory.width * arm.height_square_sum - arm.height_sum**2 >= 0
        assert sum(arm.causal_counts) == n
        assert arm.causal_counts[0] == n - arm.positive_gap_trigger_count
        assert sum(arm.causal_counts[1:]) == arm.positive_gap_trigger_count
        assert arm.causal_gap_sums[0] == 0
        assert sum(arm.causal_gap_sums) == arm.void_volume
        assert sum(map(sum, arm.endpoint_equality_mask_counts)) == n
        assert sum(arm.endpoint_equality_mask_counts[1]) == arm.endpoint_selected_count
        assert sum(count for _, count in arm.gap_histogram) == n
        assert sum(gap * count for gap, count in arm.gap_histogram) == arm.void_volume
        assert arm.endpoint_selected_count >= prior_endpoint
        assert all(current >= prior for current, prior in zip(arm.heights, prior_heights))
        assert 0 <= arm.endpoint_selected_count <= n
        if trajectory.boundary_law is OneCellBoundaryLaw.PERIODIC:
            assert type(arm.seam_equality_count) is int
        else:
            assert arm.seam_equality_count is None
        prior_endpoint = arm.endpoint_selected_count
        prior_heights = arm.heights
    if schedule[0] == 0:
        assert trajectory.arms[0].endpoint_selected_count == 0
        assert trajectory.arms[0].void_volume == 0
    if schedule[-1] == 100:
        assert trajectory.arms[-1].endpoint_selected_count == trajectory.event_count


def _assert_matches_oracle(
    trajectory: OneCellScalarTrajectory,
    expected: tuple[tuple[object, ...], ...],
    *,
    root_seed: int,
    law: OneCellBoundaryLaw,
    width: int,
) -> None:
    assert trajectory.root_seed == root_seed
    assert trajectory.boundary_law is law
    assert trajectory.width == width
    assert trajectory.event_count == expected[0][_N]
    assert tuple(_production_arm_tuple(arm) for arm in trajectory.arms) == expected
    for arm in trajectory.arms:
        q_high, q_low = arm.height_square_sum >> 64, arm.height_square_sum & _U64_MASK
        assert 0 <= q_high <= _U64_MAX
        assert 0 <= q_low <= _U64_MAX
        assert (q_high << 64) | q_low == arm.height_square_sum
    _assert_structural_laws(trajectory)


def _start(
    *,
    law: OneCellBoundaryLaw = OneCellBoundaryLaw.PERIODIC,
    width: int = 3,
    root_seed: int = 0,
    schedule: tuple[int, ...] = _PRIMARY,
) -> OneCellScalarTrajectory:
    return start_one_cell_scalar_trajectory(
        root_seed=root_seed,
        boundary_law=law,
        width=width,
        threshold_schedule=schedule,
    )


def _scalar_run(
    stop: int,
    *,
    law: OneCellBoundaryLaw = OneCellBoundaryLaw.PERIODIC,
    width: int = 3,
    root_seed: int = 0,
    schedule: tuple[int, ...] = _PRIMARY,
) -> OneCellScalarTrajectory:
    return advance_one_cell_scalar_chunk(
        trajectory=_start(law=law, width=width, root_seed=root_seed, schedule=schedule),
        stop_event_ordinal=stop,
    )


def _compiled_run(
    stop: int,
    *,
    law: OneCellBoundaryLaw = OneCellBoundaryLaw.PERIODIC,
    width: int = 3,
    root_seed: int = 0,
    schedule: tuple[int, ...] = _PRIMARY,
) -> OneCellScalarTrajectory:
    return advance_one_cell_compiled_chunk(
        trajectory=_start(law=law, width=width, root_seed=root_seed, schedule=schedule),
        stop_event_ordinal=stop,
    )


def _real_prefix_authorities(
    maximum_stop: int,
    *,
    root_seed: int,
    law: OneCellBoundaryLaw,
    width: int,
    schedule: tuple[int, ...],
) -> tuple[tuple[OneCellScalarTrajectory, ...], tuple[tuple[tuple[object, ...], ...], ...]]:
    scalar = _start(law=law, width=width, root_seed=root_seed, schedule=schedule)
    oracle = tuple(_oracle_empty_arm(law.value, threshold, width) for threshold in schedule)
    scalar_prefixes = [scalar]
    oracle_prefixes = [oracle]
    for stop in range(1, maximum_stop + 1):
        scalar = advance_one_cell_scalar_chunk(trajectory=scalar, stop_event_ordinal=stop)
        oracle, _ = _oracle_real(root_seed, law.value, width, schedule, stop - 1, stop, oracle)
        scalar_prefixes.append(scalar)
        oracle_prefixes.append(oracle)
    return tuple(scalar_prefixes), tuple(oracle_prefixes)


def _assert_real_three_way(
    *, root_seed: int, law: OneCellBoundaryLaw, width: int, schedule: tuple[int, ...], stop: int
) -> OneCellScalarTrajectory:
    expected, _ = _oracle_real(root_seed, law.value, width, schedule, 0, stop)
    scalar = _scalar_run(stop, law=law, width=width, root_seed=root_seed, schedule=schedule)
    compiled = _compiled_run(stop, law=law, width=width, root_seed=root_seed, schedule=schedule)
    assert compiled == scalar
    _assert_matches_oracle(compiled, expected, root_seed=root_seed, law=law, width=width)
    return compiled


def _scalar_tape(
    *, law: OneCellBoundaryLaw, width: int, schedule: tuple[int, ...], tape: tuple[tuple[int, int], ...]
) -> OneCellScalarTrajectory:
    trajectory = _start(law=law, width=width, schedule=schedule)
    for launch_x, contact in tape:
        trajectory = scalar_module._advance_selected_event(
            trajectory=trajectory,
            launch_x=launch_x,
            contact_value=contact,
        )
    return trajectory


@njit(cache=False, fastmath=False)
def _encoded_uniform_dispatcher(k0, k1, event, n_minus_one, initial_rejection):
    """Decode a short selected tape from keys without a Python injection path."""

    k0 ^= k1 & np.uint64(0)
    base = np.uint64(100) if n_minus_one == np.uint64(99) else np.uint64(8)
    power = np.uint64(1)
    ordinal = np.uint64(0)
    while ordinal < event:
        power *= base
        ordinal += np.uint64(1)
    value = (k0 // power) % base
    return value, initial_rejection, False


@njit(cache=False, fastmath=False)
def _forced_rejection_uniform_dispatcher(k0, k1, event, n_minus_one, initial_rejection):
    """Map an exact scripted MAX/zero rejection chain through Slice 4."""

    event ^= (k0 | k1) & np.uint64(0)
    is_contact = n_minus_one == np.uint64(99)
    if is_contact:
        if event == np.uint64(0):
            desired = np.uint64(79)
        elif event == np.uint64(1):
            desired = np.uint64(9)
        elif event == np.uint64(2):
            desired = np.uint64(0)
        elif event == np.uint64(3):
            desired = np.uint64(2)
        else:
            desired = np.uint64(92)
    elif event == np.uint64(0):
        desired = np.uint64(1)
    elif event == np.uint64(1):
        desired = np.uint64(0)
    elif event == np.uint64(2):
        desired = np.uint64(1)
    else:
        desired = np.uint64(0)

    quotient, threshold, unit_bound = _prepare_bounded_mapping_kernel(n_minus_one)
    rejection = initial_rejection
    forced = (not is_contact and event == np.uint64(1)) or (is_contact and event == np.uint64(2))
    while True:
        if forced and rejection == np.uint64(0):
            word = np.uint64(_U64_MAX)
        elif forced:
            word = np.uint64(0)
        else:
            word = desired * quotient
        accepted, value = _map_bounded_word_kernel(word, quotient, threshold, unit_bound)
        if accepted:
            return value, rejection, False
        if rejection == np.uint64(_U64_MAX):
            return np.uint64(0), rejection, True
        rejection += np.uint64(1)


@njit(cache=False, fastmath=False)
def _audited_forced_rejection_uniform_dispatcher(k0, k1, event, n_minus_one, initial_rejection):
    """Retain every test-side candidate address in a caller-owned audit buffer."""

    is_contact = n_minus_one == np.uint64(99)
    if is_contact:
        if k0 != _AUDIT_CONTACT_KEY:
            return np.uint64(0), initial_rejection, True
        stream_code = np.uint64(1)
        if event == np.uint64(0):
            desired = np.uint64(79)
        elif event == np.uint64(1):
            desired = np.uint64(9)
        elif event == np.uint64(2):
            desired = np.uint64(0)
        elif event == np.uint64(3):
            desired = np.uint64(2)
        else:
            desired = np.uint64(92)
    else:
        if n_minus_one != np.uint64(2) or k0 != _AUDIT_LAUNCH_KEY:
            return np.uint64(0), initial_rejection, True
        stream_code = np.uint64(0)
        if event == np.uint64(0):
            desired = np.uint64(1)
        elif event == np.uint64(1):
            desired = np.uint64(0)
        elif event == np.uint64(2):
            desired = np.uint64(1)
        else:
            desired = np.uint64(0)

    audit = carray(_uint64_to_void_pointer(k1), _AUDIT_WORDS, dtype=np.uint64)
    quotient, threshold, unit_bound = _prepare_bounded_mapping_kernel(n_minus_one)
    rejection = initial_rejection
    forced = (not is_contact and event == np.uint64(1)) or (is_contact and event == np.uint64(2))
    while True:
        position = int(audit[0])
        offset = 1 + 3 * position
        if offset + 2 >= _AUDIT_WORDS:
            return np.uint64(0), rejection, True
        audit[offset] = stream_code
        audit[offset + 1] = event
        audit[offset + 2] = rejection
        audit[0] = np.uint64(position + 1)

        if forced and rejection == np.uint64(0):
            word = np.uint64(_U64_MAX)
        elif forced:
            word = np.uint64(0)
        else:
            word = desired * quotient
        accepted, value = _map_bounded_word_kernel(word, quotient, threshold, unit_bound)
        if accepted:
            return value, rejection, False
        if rejection == np.uint64(_U64_MAX):
            return np.uint64(0), rejection, True
        rejection += np.uint64(1)


@njit(cache=False, fastmath=False)
def _exhausted_uniform_dispatcher(k0, k1, event, n_minus_one, initial_rejection):
    ignored = k0 | k1 | event | n_minus_one | initial_rejection
    return ignored & np.uint64(0), np.uint64(_U64_MAX), True


@njit(cache=False, fastmath=False)
def _q_crossing_uniform_dispatcher(k0, k1, event, n_minus_one, initial_rejection):
    ignored = (k0 | k1 | event) & np.uint64(0)
    value = np.uint64(99) if n_minus_one == np.uint64(99) else ignored
    return value, initial_rejection, False


_ENCODED_CHUNK_KERNEL = compiled_module._make_chunk_kernel(_encoded_uniform_dispatcher)
_FORCED_REJECTION_CHUNK_KERNEL = compiled_module._make_chunk_kernel(_forced_rejection_uniform_dispatcher)
_AUDITED_FORCED_REJECTION_CHUNK_KERNEL = compiled_module._make_chunk_kernel(
    _audited_forced_rejection_uniform_dispatcher
)
_EXHAUSTED_CHUNK_KERNEL = compiled_module._make_chunk_kernel(_exhausted_uniform_dispatcher)
_Q_CROSSING_CHUNK_KERNEL = compiled_module._make_chunk_kernel(_q_crossing_uniform_dispatcher)


def _compiled_tape(
    *, law: OneCellBoundaryLaw, width: int, schedule: tuple[int, ...], tape: tuple[tuple[int, int], ...]
) -> OneCellScalarTrajectory:
    assert len(tape) <= 3
    source = _start(law=law, width=width, schedule=schedule)
    heights, scalars, causal, causal_gaps, equality, histogram = compiled_module._pack_compiled_state(source)
    launch_code = sum(launch * 8**event for event, (launch, _) in enumerate(tape))
    contact_code = sum(contact * 100**event for event, (_, contact) in enumerate(tape))
    law_code = _LAW_IDS.index(law.value)
    schedule_code = _SCHEDULES.index(schedule)
    status = _ENCODED_CHUNK_KERNEL(
        np.uint64(launch_code),
        np.uint64(0),
        np.uint64(contact_code),
        np.uint64(0),
        np.uint64(0),
        np.uint64(len(tape)),
        np.uint64(law_code),
        np.uint64(schedule_code),
        heights,
        scalars,
        causal,
        causal_gaps,
        equality,
        histogram,
    )
    assert tuple(int(word) for word in status) == (0, len(tape), 0, 0)
    expected = _oracle_from_tape(law.value, width, schedule, tape)
    for arm_index, arm in enumerate(expected):
        assert int(scalars[arm_index, 6]) == arm[_Q] >> 64
        assert int(scalars[arm_index, 7]) == arm[_Q] & _U64_MASK
    return compiled_module._unpack_compiled_state(
        source=source,
        stop=len(tape),
        schedule=schedule,
        heights=heights,
        scalars=scalars,
        causal_counts=causal,
        causal_gap_sums=causal_gaps,
        equality_counts=equality,
        histogram=histogram,
    )


def _compiled_forced_audit(
    *,
    source: OneCellScalarTrajectory,
    stop: int,
    audit: np.ndarray,
) -> OneCellScalarTrajectory:
    heights, scalars, causal, causal_gaps, equality, histogram = compiled_module._pack_compiled_state(source)
    pointer = np.uint64(audit.ctypes.data)
    status = _AUDITED_FORCED_REJECTION_CHUNK_KERNEL(
        _AUDIT_LAUNCH_KEY,
        pointer,
        _AUDIT_CONTACT_KEY,
        pointer,
        np.uint64(source.event_count),
        np.uint64(stop),
        np.uint64(_LAW_IDS.index(source.boundary_law.value)),
        np.uint64(_SCHEDULES.index(source.threshold_schedule)),
        heights,
        scalars,
        causal,
        causal_gaps,
        equality,
        histogram,
    )
    compiled_module._raise_kernel_failure(status)
    return compiled_module._unpack_compiled_state(
        source=source,
        stop=stop,
        schedule=source.threshold_schedule,
        heights=heights,
        scalars=scalars,
        causal_counts=causal,
        causal_gap_sums=causal_gaps,
        equality_counts=equality,
        histogram=histogram,
    )


def _assert_tape_three_way(
    *, law: OneCellBoundaryLaw, width: int, schedule: tuple[int, ...], tape: tuple[tuple[int, int], ...]
) -> None:
    expected = _oracle_from_tape(law.value, width, schedule, tape)
    scalar = _scalar_tape(law=law, width=width, schedule=schedule, tape=tape)
    compiled = _compiled_tape(law=law, width=width, schedule=schedule, tape=tape)
    assert compiled == scalar
    _assert_matches_oracle(compiled, expected, root_seed=0, law=law, width=width)


def test_public_api_records_and_four_schedule_initialization() -> None:
    assert compiled_module.__all__ == ["advance_one_cell_compiled_chunk"]
    parameters = tuple(inspect.signature(advance_one_cell_compiled_chunk).parameters.values())
    assert tuple(parameter.name for parameter in parameters) == ("trajectory", "stop_event_ordinal")
    assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters)
    assert all(parameter.default is inspect.Parameter.empty for parameter in parameters)
    assert tuple(field.name for field in fields(OneCellScalarArmAccumulator)) == _ARM_FIELDS
    assert tuple(field.name for field in fields(OneCellScalarTrajectory)) == _TRAJECTORY_FIELDS

    assert {name for name, value in vars(OneCellScalarTrajectory).items() if isinstance(value, property)} == {
        "threshold_schedule"
    }
    for law, schedule in product(_LAWS, _SCHEDULES):
        trajectory = _start(law=law, width=5, root_seed=_U128_MAX, schedule=schedule)
        assert trajectory.threshold_schedule == schedule
        assert tuple(arm.threshold for arm in trajectory.arms) == schedule
        assert len({id(arm) for arm in trajectory.arms}) == len(schedule)
        assert len({id(arm.heights) for arm in trajectory.arms}) == len(schedule)
        _assert_structural_laws(trajectory)
        with pytest.raises(FrozenInstanceError):
            trajectory.event_count = 1


def test_fast_three_way_smoke_all_laws_and_schedules() -> None:
    for law, schedule in product(_LAWS, _SCHEDULES):
        _assert_real_three_way(root_seed=0, law=law, width=3, schedule=schedule, stop=50)


def test_all_84_persisted_schedule_indexed_rows_replay_three_ways() -> None:
    documented = _documented_vector_rows()
    assert len(documented) == 12
    assert sum(len(rows) for rows in documented.values()) == 84
    assert sum(len(rows) for key, rows in documented.items() if key[2] == _PRIMARY) == 48
    assert sum(len(rows) for key, rows in documented.items() if key[2] == _B2_FULL) == 36

    for (law_id, stop, schedule), rows in documented.items():
        law = OneCellBoundaryLaw(law_id)
        expected, _ = _oracle_real(0, law_id, 3, schedule, 0, stop)
        scalar = _scalar_run(stop, law=law, width=3, root_seed=0, schedule=schedule)
        compiled = _compiled_run(stop, law=law, width=3, root_seed=0, schedule=schedule)
        assert tuple(_production_arm_tuple(arm) for arm in scalar.arms) == rows
        assert tuple(_production_arm_tuple(arm) for arm in compiled.arms) == rows
        assert expected == rows
        assert compiled == scalar
        _assert_matches_oracle(compiled, expected, root_seed=0, law=law, width=3)


def test_exhaustive_one_event_selected_tapes_14400_trajectories() -> None:
    trajectories = 0
    transitions = 0
    for schedule, law, width in product(_SCHEDULES, _LAWS, range(3, 6)):
        for launch_x, contact in product(range(width), range(100)):
            _assert_tape_three_way(
                law=law,
                width=width,
                schedule=schedule,
                tape=((launch_x, contact),),
            )
            trajectories += 1
            transitions += len(schedule)
    assert (trajectories, transitions) == (14400, 79200)


def test_exhaustive_two_event_decision_patterns_3564_trajectories() -> None:
    trajectories = 0
    transitions = 0
    for schedule, law in product(_SCHEDULES, _LAWS):
        representatives = _DECISION_REPRESENTATIVES[schedule]
        for launches, contacts in product(product(range(3), repeat=2), product(representatives, repeat=2)):
            tape = tuple(zip(launches, contacts))
            _assert_tape_three_way(law=law, width=3, schedule=schedule, tape=tape)
            trajectories += 1
            transitions += 2 * len(schedule)
    assert (trajectories, transitions) == (3564, 44388)


@pytest.mark.slow
def test_exhaustive_three_event_decision_patterns_67878_trajectories() -> None:
    trajectories = 0
    transitions = 0
    for schedule, law in product(_SCHEDULES, _LAWS):
        representatives = _DECISION_REPRESENTATIVES[schedule]
        for launches, contacts in product(product(range(3), repeat=3), product(representatives, repeat=3)):
            tape = tuple(zip(launches, contacts))
            _assert_tape_three_way(law=law, width=3, schedule=schedule, tape=tape)
            trajectories += 1
            transitions += 3 * len(schedule)
    assert (trajectories, transitions) == (67878, 1314630)


def test_root_zero_high_threshold_witnesses_and_strict_contact_neighbors() -> None:
    for law in _LAWS:
        full = _assert_real_three_way(root_seed=0, law=law, width=3, schedule=_B2_FULL, stop=50)
        by_threshold = {arm.threshold: arm for arm in full.arms}
        if law is OneCellBoundaryLaw.PERIODIC:
            expected = ((23, 23, 22), 68, 1542, 18)
        else:
            expected = ((21, 21, 20), 62, 1282, 12)
        for threshold, endpoint in zip((90, 95, 98, 99), (44, 46, 49, 49)):
            arm = by_threshold[threshold]
            assert (arm.heights, arm.height_sum, arm.height_square_sum, arm.void_volume) == expected
            assert arm.endpoint_selected_count == endpoint

    witnesses = (
        (4, 55, "0bfb25192b17f92e"),
        (5, 24, "0f3558266a1ecb4c"),
        (49, 45, "7daaf3e15f89f819"),
        (50, 216, "81e81f92c924dd8f"),
        (89, 67, "e3f955d77cf51347"),
        (90, 70, "e85457065d119d2a"),
        (94, 221, "f1f54e9cab7b23d6"),
        (95, 18, "f5c22f4c931abfb3"),
        (97, 7, "fa673b3a532b5051"),
        (98, 135, "fb2f98475c7d4d5e"),
        (99, 43, "fed165ae9ecf81ff"),
    )
    for value, event, raw_hex in witnesses:
        selected, rejection, raw = _oracle_uniform(
            root_seed=0, stream_name="contact", event_ordinal=event, upper_bound=100
        )
        assert (selected, rejection, f"{raw:016x}") == (value, 0, raw_hex)
    assert 98 < 99
    assert not 99 < 99


def test_schedule_projection_invariance_after_every_partition_stop() -> None:
    partitions = ((0, 1, 2, 5, 7, 7, 19, 50), (0, 3, 8, 13, 21, 34, 50, 50))
    for law, stops in product(_LAWS, partitions):
        trajectories = {schedule: _start(law=law, schedule=schedule) for schedule in _SCHEDULES}
        for stop in stops:
            for schedule in _SCHEDULES:
                trajectories[schedule] = advance_one_cell_compiled_chunk(
                    trajectory=trajectories[schedule], stop_event_ordinal=stop
                )
            primary = {arm.threshold: arm for arm in trajectories[_PRIMARY].arms}
            b1 = {arm.threshold: arm for arm in trajectories[_B1].arms}
            full = {arm.threshold: arm for arm in trajectories[_B2_FULL].arms}
            high = {arm.threshold: arm for arm in trajectories[_B2_HIGH].arms}
            assert tuple(b1[t] == primary[t] for t in _B1) == (True,) * 4
            assert tuple(high[t] == full[t] for t in _B2_HIGH) == (True,) * 4
            assert full[5] == primary[5]
            assert full[50] == primary[50]


def test_forced_launch_and_contact_rejection_all_schedules_and_partitions() -> None:
    tape = ((1, 79), (0, 9), (1, 0), (0, 2), (0, 92))
    endpoint_totals = {
        _PRIMARY: (0, 1, 1, 2, 3, 3, 3, 5),
        _B1: (0, 2, 3, 5),
        _B2_FULL: (2, 3, 4, 5, 5, 5),
        _B2_HIGH: (4, 5, 5, 5),
    }
    for law, schedule in product(_LAWS, _SCHEDULES):
        source = _start(law=law, width=3, schedule=schedule)
        uninterrupted = compiled_module._advance_compiled_chunk_with_kernel(
            trajectory=source,
            stop_event_ordinal=5,
            kernel=_FORCED_REJECTION_CHUNK_KERNEL,
        )
        scalar = _scalar_tape(law=law, width=3, schedule=schedule, tape=tape)
        expected = _oracle_from_tape(law.value, 3, schedule, tape)
        assert uninterrupted == scalar
        _assert_matches_oracle(uninterrupted, expected, root_seed=0, law=law, width=3)
        assert tuple(arm.endpoint_selected_count for arm in uninterrupted.arms) == endpoint_totals[schedule]
        assert uninterrupted.event_count == 5
        assert source == _start(law=law, width=3, schedule=schedule)

        partitioned = source
        for stop in (1, 2, 2, 3, 5):
            partitioned = compiled_module._advance_compiled_chunk_with_kernel(
                trajectory=partitioned,
                stop_event_ordinal=stop,
                kernel=_FORCED_REJECTION_CHUNK_KERNEL,
            )
            scalar_prefix = _scalar_tape(law=law, width=3, schedule=schedule, tape=tape[:stop])
            oracle_prefix = _oracle_from_tape(law.value, 3, schedule, tape[:stop])
            assert partitioned == scalar_prefix
            _assert_matches_oracle(partitioned, oracle_prefix, root_seed=0, law=law, width=3)
        assert partitioned == uninterrupted

    expected_dispatches = (
        ((1, 0), (0, 1), (1, 0), (0, 0), (0, 0)),
        ((79, 0), (9, 0), (0, 1), (2, 0), (92, 0)),
    )
    for n_minus_one, expected_stream in zip((2, 99), expected_dispatches):
        actual_stream = []
        for event in range(5):
            value, rejection, exhausted = _forced_rejection_uniform_dispatcher(
                np.uint64(0),
                np.uint64(0),
                np.uint64(event),
                np.uint64(n_minus_one),
                np.uint64(0),
            )
            assert not bool(exhausted)
            actual_stream.append((int(value), int(rejection)))
        assert tuple(actual_stream) == expected_stream

    audit = np.zeros(_AUDIT_WORDS, dtype=np.uint64)
    audited = _compiled_forced_audit(source=_start(schedule=_PRIMARY), stop=5, audit=audit)
    assert audited == _scalar_tape(
        law=OneCellBoundaryLaw.PERIODIC,
        width=3,
        schedule=_PRIMARY,
        tape=tape,
    )
    observed_addresses = tuple(
        tuple(int(word) for word in audit[1 + 3 * index : 4 + 3 * index]) for index in range(int(audit[0]))
    )
    assert observed_addresses == (
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 1, 1),
        (1, 1, 0),
        (0, 2, 0),
        (1, 2, 0),
        (1, 2, 1),
        (0, 3, 0),
        (1, 3, 0),
        (0, 4, 0),
        (1, 4, 0),
    )


def test_rejection_exhaustion_is_atomic_and_names_the_stream() -> None:
    source = _scalar_run(3, schedule=_B1)
    with pytest.raises(OverflowError, match="launch rejection ordinal exhausted"):
        compiled_module._advance_compiled_chunk_with_kernel(
            trajectory=source,
            stop_event_ordinal=4,
            kernel=_EXHAUSTED_CHUNK_KERNEL,
        )
    assert source == _scalar_run(3, schedule=_B1)


def test_all_partitions_of_seven_and_splits_of_fifty() -> None:
    for law, schedule in product(_LAWS, _SCHEDULES):
        scalar_prefixes, oracle_prefixes = _real_prefix_authorities(
            50,
            root_seed=0,
            law=law,
            width=3,
            schedule=schedule,
        )
        uninterrupted7 = _compiled_run(7, law=law, schedule=schedule)
        assert uninterrupted7 == scalar_prefixes[7]
        _assert_matches_oracle(uninterrupted7, oracle_prefixes[7], root_seed=0, law=law, width=3)
        for cut_mask in range(64):
            stops = tuple(index + 1 for index in range(6) if cut_mask & (1 << index)) + (7,)
            trajectory = _start(law=law, schedule=schedule)
            for stop in stops:
                trajectory = advance_one_cell_compiled_chunk(trajectory=trajectory, stop_event_ordinal=stop)
                assert trajectory == scalar_prefixes[stop]
                _assert_matches_oracle(trajectory, oracle_prefixes[stop], root_seed=0, law=law, width=3)
            assert trajectory == uninterrupted7

        uninterrupted50 = _compiled_run(50, law=law, schedule=schedule)
        assert uninterrupted50 == scalar_prefixes[50]
        _assert_matches_oracle(uninterrupted50, oracle_prefixes[50], root_seed=0, law=law, width=3)
        for split in range(51):
            trajectory = _start(law=law, schedule=schedule)
            for stop in (split, split, 50, 50):
                trajectory = advance_one_cell_compiled_chunk(trajectory=trajectory, stop_event_ordinal=stop)
                assert trajectory == scalar_prefixes[stop]
                _assert_matches_oracle(trajectory, oracle_prefixes[stop], root_seed=0, law=law, width=3)
            assert trajectory == uninterrupted50
        unit = _start(law=law, schedule=schedule)
        for stop in range(1, 51):
            unit = advance_one_cell_compiled_chunk(trajectory=unit, stop_event_ordinal=stop)
            assert unit == scalar_prefixes[stop]
            _assert_matches_oracle(unit, oracle_prefixes[stop], root_seed=0, law=law, width=3)
        assert unit == uninterrupted50


@pytest.mark.slow
def test_declared_real_rng_matrix_768_trajectories() -> None:
    trajectories = 0
    transitions = 0
    for root_seed, width, law, schedule in product(range(16), (3, 4, 5, 32), _LAWS, _SCHEDULES):
        _assert_real_three_way(root_seed=root_seed, law=law, width=width, schedule=schedule, stop=64)
        trajectories += 1
        transitions += 64 * len(schedule)
    assert (trajectories, transitions) == (768, 270336)


@pytest.mark.slow
def test_declared_width_root_differential_matrix_1440_trajectories() -> None:
    roots = (0, 95, 1000015, 2000031, 3000099, _U64_MAX, 1 << 64, _U128_MAX)
    widths = (32, 50, 64, 80, 100, 128, 150, 200, 250, 256, 300, 400, 500, 512, 1024)
    trajectories = 0
    transitions = 0
    for root_seed, width, law, schedule in product(roots, widths, _LAWS, _SCHEDULES):
        _assert_real_three_way(root_seed=root_seed, law=law, width=width, schedule=schedule, stop=32)
        trajectories += 1
        transitions += 32 * len(schedule)
    assert (trajectories, transitions) == (1440, 253440)


@pytest.mark.slow
def test_exact_article_b2_and_f0_matrices() -> None:
    hard_walls = _LAWS[1:]
    b2_widths = (50, 80, 100, 150, 200, 250, 300, 400, 500)
    trajectories = 0
    transitions = 0
    for root_seed, law, width in product(range(3000000, 3000100), hard_walls, b2_widths):
        schedule = _B2_FULL if width <= 300 else _B2_HIGH
        _assert_real_three_way(root_seed=root_seed, law=law, width=width, schedule=schedule, stop=32)
        trajectories += 1
        transitions += 32 * len(schedule)
    assert (trajectories, transitions) == (1800, 320000)

    f0_trajectories = 0
    f0_transitions = 0
    for root_seed, law, (width, schedule) in product((3100000, 3100001), hard_walls, ((50, _B2_FULL), (500, _B2_HIGH))):
        _assert_real_three_way(root_seed=root_seed, law=law, width=width, schedule=schedule, stop=32)
        f0_trajectories += 1
        f0_transitions += 32 * len(schedule)
    assert (f0_trajectories, f0_transitions) == (8, 1280)
    assert (trajectories + f0_trajectories, transitions + f0_transitions) == (1808, 321280)


def _long_partition_families() -> tuple[tuple[int, ...], ...]:
    return (
        (257,),
        tuple(range(1, 258)),
        (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 257),
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257),
        (0, 17, 17, 31, 82, 83, 149, 213, 257, 257),
        (0, 9, 23, 24, 99, 107, 178, 249, 257, 257),
        (0, 1, 64, 65, 66, 130, 191, 192, 256, 257),
        (0, 7, 42, 43, 100, 166, 167, 222, 257, 257),
    )


@pytest.mark.slow
def test_declared_long_partition_matrix_768_executions() -> None:
    executions = 0
    transitions = 0
    for root_seed, width, law, schedule in product((0, _U128_MAX), (3, 32, 256, 1024), _LAWS, _SCHEDULES):
        families = _long_partition_families()
        oracle_by_stop = {}
        oracle = tuple(_oracle_empty_arm(law.value, threshold, width) for threshold in schedule)
        scalar_by_stop = {}
        scalar = _start(law=law, width=width, root_seed=root_seed, schedule=schedule)
        current = 0
        for stop in sorted({stop for family in families for stop in family}):
            oracle, _ = _oracle_real(root_seed, law.value, width, schedule, current, stop, oracle)
            oracle_by_stop[stop] = oracle
            scalar = advance_one_cell_scalar_chunk(trajectory=scalar, stop_event_ordinal=stop)
            scalar_by_stop[stop] = scalar
            current = stop
        uninterrupted = None
        for stops in families:
            trajectory = _start(law=law, width=width, root_seed=root_seed, schedule=schedule)
            for stop in stops:
                trajectory = advance_one_cell_compiled_chunk(trajectory=trajectory, stop_event_ordinal=stop)
                assert trajectory == scalar_by_stop[stop]
                _assert_matches_oracle(
                    trajectory,
                    oracle_by_stop[stop],
                    root_seed=root_seed,
                    law=law,
                    width=width,
                )
            if uninterrupted is None:
                uninterrupted = trajectory
            else:
                assert trajectory == uninterrupted
            executions += 1
            transitions += 257 * len(schedule)
    assert (executions, transitions) == (768, 1085568)


def test_empty_chunk_is_defensive_allocation_free_and_input_is_never_mutated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for law, schedule in product(_LAWS, _SCHEDULES):
        original = _scalar_run(7, law=law, schedule=schedule)
        with monkeypatch.context() as scoped:

            def forbidden(*_: object, **__: object) -> object:
                raise AssertionError("empty chunk must not allocate compiled arrays")

            scoped.setattr(compiled_module._np, "empty", forbidden)
            scoped.setattr(compiled_module._np, "zeros", forbidden)
            snapshot = advance_one_cell_compiled_chunk(trajectory=original, stop_event_ordinal=7)
        assert snapshot == original
        assert snapshot is not original
        assert all(actual is not prior for actual, prior in zip(snapshot.arms, original.arms))
        assert all(actual.heights is not prior.heights for actual, prior in zip(snapshot.arms, original.arms))
        assert original == _scalar_run(7, law=law, schedule=schedule)


def test_public_types_ranges_products_and_keyword_only_calls() -> None:
    trajectory = _scalar_run(2)
    for bad in (True, 2.0, _IntSubclass(2), np.uint64(2), "2", None):
        with pytest.raises(TypeError):
            advance_one_cell_compiled_chunk(trajectory=trajectory, stop_event_ordinal=bad)
    for bad in (0, 1, _U64_SPACE):
        with pytest.raises(ValueError):
            advance_one_cell_compiled_chunk(trajectory=trajectory, stop_event_ordinal=bad)
    with pytest.raises(TypeError):
        advance_one_cell_compiled_chunk(trajectory, 3)
    partial = object.__new__(OneCellScalarTrajectory)
    with pytest.raises(TypeError):
        advance_one_cell_compiled_chunk(trajectory=partial, stop_event_ordinal=0)

    start = _start(width=3)
    first_linear_failure = 6148914691236517206
    for stop in (first_linear_failure, _U64_MAX):
        with pytest.raises(ValueError):
            advance_one_cell_compiled_chunk(trajectory=start, stop_event_ordinal=stop)


def test_invalid_public_requests_fail_before_private_dispatch() -> None:
    calls = 0

    def forbidden(*_: object, **__: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("invalid request reached compiled dispatch")

    current = _scalar_run(2)
    for stop in (0, 1, _U64_SPACE, 6148914691236517206):
        with pytest.raises(ValueError):
            compiled_module._advance_compiled_chunk_with_kernel(
                trajectory=current,
                stop_event_ordinal=stop,
                kernel=forbidden,
            )
    partial = object.__new__(OneCellScalarTrajectory)
    with pytest.raises(TypeError):
        compiled_module._advance_compiled_chunk_with_kernel(
            trajectory=partial,
            stop_event_ordinal=2,
            kernel=forbidden,
        )
    assert calls == 0


def test_malformed_records_fail_closed_and_leave_caller_owned_state_unchanged() -> None:
    original = _scalar_run(7, schedule=_B2_FULL)
    corruptions = (
        {"event_count": original.event_count + 1},
        {"arms": original.arms[::-1]},
        {"arms": original.arms[:-1]},
        {"arms": original.arms + (original.arms[-1],)},
    )
    for changes in corruptions:
        with pytest.raises((TypeError, ValueError)):
            forged = replace(original, **changes)
            advance_one_cell_compiled_chunk(trajectory=forged, stop_event_ordinal=8)
    assert original == _scalar_run(7, schedule=_B2_FULL)

    arm = original.arms[0]
    for changes in (
        {"height_sum": arm.height_sum + 1},
        {"height_square_sum": arm.height_square_sum + 1},
        {"gap_histogram": ()},
        {"causal_counts": (arm.event_count, 0, 0, 0)},
    ):
        with pytest.raises((TypeError, ValueError)):
            replace(arm, **changes)


def test_private_unsigned_state_rejects_dtype_shape_layout_and_aliasing() -> None:
    source = _start(schedule=_B2_FULL, width=5)
    heights, scalars, causal, causal_gaps, equality, _ = compiled_module._pack_compiled_state(source)
    good = {
        "heights": heights,
        "scalars": scalars,
        "causal_counts": causal,
        "causal_gap_sums": causal_gaps,
        "equality_counts": equality,
        "arm_count": 6,
        "width": 5,
    }
    hostile = (
        ("heights", heights.astype(np.int64)),
        ("heights", heights.astype(">u8")),
        ("heights", heights[:, ::-1]),
        ("heights", heights.reshape(6, 5, 1)),
        ("scalars", scalars[:, :7]),
        ("causal_counts", causal.astype(np.float64)),
        ("causal_gap_sums", causal_gaps[:, ::-1]),
        ("equality_counts", equality[:, 0, :]),
    )
    for name, value in hostile:
        arguments = {**good, name: value}
        with pytest.raises(AssertionError):
            compiled_module._validate_compiled_state(**arguments)

    backing = np.zeros(80, dtype=np.uint64)
    shared_scalars = np.ndarray(shape=(6, 8), dtype=np.uint64, buffer=backing, offset=0)
    shared_causal = np.ndarray(shape=(6, 4), dtype=np.uint64, buffer=backing, offset=8)
    assert shared_scalars.flags.c_contiguous and shared_causal.flags.c_contiguous
    alias_arguments = {
        **good,
        "scalars": shared_scalars,
        "causal_counts": shared_causal,
    }
    with pytest.raises(AssertionError, match="must not alias"):
        compiled_module._validate_compiled_state(**alias_arguments)


def test_private_kernel_rejects_shape_code_and_histogram_arm_mismatches_before_mutation() -> None:
    source = _start(schedule=_B1)
    heights, scalars, causal, causal_gaps, equality, histogram = compiled_module._pack_compiled_state(source)
    originals = tuple(array.copy() for array in (heights, scalars, causal, causal_gaps, equality))

    def call(*, law_code: int = 0, schedule_code: int = 1, selected_heights: np.ndarray = heights):
        return _ENCODED_CHUNK_KERNEL(
            np.uint64(1),
            np.uint64(0),
            np.uint64(0),
            np.uint64(0),
            np.uint64(0),
            np.uint64(1),
            np.uint64(law_code),
            np.uint64(schedule_code),
            selected_heights,
            scalars,
            causal,
            causal_gaps,
            equality,
            histogram,
        )

    assert int(call(schedule_code=0)[0]) == 1
    assert int(call(law_code=3)[0]) == 1
    assert int(call(selected_heights=heights[:, :2])[0]) == 1
    for actual, expected in zip((heights, scalars, causal, causal_gaps, equality), originals):
        assert np.array_equal(actual, expected)

    histogram[(np.uint64(4), np.uint64(0))] = np.uint64(1)
    assert int(call()[0]) == 1
    for actual, expected in zip((heights, scalars, causal, causal_gaps, equality), originals):
        assert np.array_equal(actual, expected)


def test_private_literal_schedule_and_law_codes_are_exact_and_shape_complete() -> None:
    for schedule_code, schedule in enumerate(_SCHEDULES):
        assert int(compiled_module._arm_count_for_schedule_kernel(np.uint64(schedule_code))) == len(schedule)
        actual = []
        for arm_index in range(len(schedule)):
            threshold, invalid = compiled_module._threshold_for_arm_kernel(np.uint64(schedule_code), arm_index)
            assert not bool(invalid)
            actual.append(int(threshold))
        assert tuple(actual) == schedule
        _, invalid = compiled_module._threshold_for_arm_kernel(np.uint64(schedule_code), len(schedule))
        assert bool(invalid)
    assert int(compiled_module._arm_count_for_schedule_kernel(np.uint64(4))) == 0
    _, invalid = compiled_module._threshold_for_arm_kernel(np.uint64(4), 0)
    assert bool(invalid)
    assert (
        compiled_module._LAW_PERIODIC_CODE,
        compiled_module._LAW_HARD_WALL_LEGACY_CODE,
        compiled_module._LAW_HARD_WALL_CORRECTED_CODE,
    ) == (0, 1, 2)


def test_private_counter_histogram_and_late_arm_overflow_report_without_publishing() -> None:
    source = _start(schedule=_B1)

    def run_with(
        causal_edit: tuple[int, int, int] | None = None,
        histogram_edit: tuple[int, int, int] | None = None,
    ) -> tuple[tuple[int, ...], tuple[np.ndarray, ...]]:
        heights, scalars, causal, causal_gaps, equality, histogram = compiled_module._pack_compiled_state(source)
        if causal_edit is not None:
            arm, stratum, value = causal_edit
            causal[arm, stratum] = np.uint64(value)
        if histogram_edit is not None:
            arm, gap, value = histogram_edit
            histogram[(np.uint64(arm), np.uint64(gap))] = np.uint64(value)
        status = _ENCODED_CHUNK_KERNEL(
            np.uint64(1),
            np.uint64(0),
            np.uint64(0),
            np.uint64(0),
            np.uint64(0),
            np.uint64(1),
            np.uint64(0),
            np.uint64(1),
            heights,
            scalars,
            causal,
            causal_gaps,
            equality,
            histogram,
        )
        return tuple(int(word) for word in status), (heights, scalars, causal, causal_gaps, equality)

    status, _ = run_with(causal_edit=(0, 0, _U64_MAX))
    assert status[:3] == (3, 0, 0)
    status, _ = run_with(histogram_edit=(0, 0, _U64_MAX))
    assert status[:3] == (3, 0, 0)
    status, partially_mutated = run_with(causal_edit=(3, 0, _U64_MAX))
    assert status[:3] == (3, 0, 3)
    assert any(array.any() for array in partially_mutated)
    assert source == _start(schedule=_B1)


def test_malformed_kernel_status_evidence_is_rejected() -> None:
    for malformed in (None, (), (0, 0, 0), [0, 0, 0, 0], (object(), 0, 0, 0)):
        with pytest.raises(AssertionError):
            compiled_module._raise_kernel_failure(malformed)
    with pytest.raises(AssertionError, match="private protocol"):
        compiled_module._raise_kernel_failure((np.uint64(1), np.uint64(4), np.uint64(2), np.uint64(0)))
    with pytest.raises(OverflowError, match="unsigned arithmetic"):
        compiled_module._raise_kernel_failure((np.uint64(3), np.uint64(4), np.uint64(2), np.uint64(0)))


def test_packed_u128_limb_helpers_and_exact_carry_borrow_rows() -> None:
    add_rows = (
        ((0, 0, 0, 1), (0, 1, False)),
        ((0, _U64_MAX, 0, 1), (1, 0, False)),
        ((5, _U64_MAX - 2, 7, 3), (13, 0, False)),
        ((_U64_MAX - 1, _U64_MAX, 0, 1), (_U64_MAX, 0, False)),
        ((_U64_MAX, _U64_MAX, 0, 1), (0, 0, True)),
    )
    for inputs, expected in add_rows:
        actual = compiled_module._add_u128_words_kernel(*(np.uint64(word) for word in inputs))
        assert tuple(int(value) if index < 2 else bool(value) for index, value in enumerate(actual)) == expected

    subtract_rows = (
        ((0, 1, 0, 1), (0, 0, False)),
        ((1, 0, 0, 1), (0, _U64_MAX, False)),
        ((13, 0, 7, 3), (5, _U64_MAX - 2, False)),
        ((0, 0, 0, 1), (0, 0, True)),
    )
    for inputs, expected in subtract_rows:
        actual = compiled_module._subtract_u128_words_kernel(*(np.uint64(word) for word in inputs))
        assert tuple(int(value) if index < 2 else bool(value) for index, value in enumerate(actual)) == expected

    products = (
        ((0, 0), (0, 0)),
        (((1 << 32), (1 << 32)), (1, 0)),
        ((_U64_MAX, _U64_MAX), (_U64_MAX - 1, 1)),
    )
    for inputs, expected in products:
        actual = compiled_module._CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL(np.uint64(inputs[0]), np.uint64(inputs[1]))
        assert tuple(int(word) for word in actual) == expected

    old = (1 << 32) - 1
    rows = (
        ((0, old * old, old, 1 << 32), (1, 0, False)),
        ((1, 0, 1 << 32, (1 << 32) + 1), (1, 8589934593, False)),
    )
    for inputs, expected in rows:
        actual = compiled_module._replace_square_sum_kernel(*(np.uint64(word) for word in inputs))
        assert tuple(int(value) if index < 2 else bool(value) for index, value in enumerate(actual)) == expected

    overflow = compiled_module._replace_square_sum_kernel(
        np.uint64(_U64_MAX),
        np.uint64(_U64_MAX),
        np.uint64(0),
        np.uint64(1),
    )
    assert tuple(int(value) if index < 2 else bool(value) for index, value in enumerate(overflow)) == (
        0,
        0,
        True,
    )

    n = (1 << 62) + 1
    q = 3 * n * n
    assert (q >> 64, q & _U64_MASK) == (3458764513820540929, 9223372036854775811)


def test_structural_prefix_crosses_the_2pow32_q_limb_through_selected_events() -> None:
    old_height = (1 << 32) - 1
    prototype = OneCellScalarArmAccumulator(
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        threshold=90,
        heights=(old_height, 0, 0),
        event_count=old_height,
        height_sum=old_height,
        height_square_sum=old_height * old_height,
        void_volume=0,
        endpoint_selected_count=0,
        positive_gap_trigger_count=0,
        gap_sum=0,
        maximum_gap=0,
        causal_counts=(old_height, 0, 0, 0),
        causal_gap_sums=(0, 0, 0, 0),
        endpoint_equality_mask_counts=((0, old_height, 0, 0, 0, 0, 0, 0), (0,) * 8),
        gap_histogram=((0, old_height),),
        seam_equality_count=0,
    )
    source = OneCellScalarTrajectory(
        root_seed=0,
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        width=3,
        event_count=old_height,
        arms=tuple(replace(prototype, threshold=threshold) for threshold in _B2_HIGH),
    )
    assert (source.arms[0].height_square_sum >> 64, source.arms[0].height_square_sum & _U64_MASK) == (
        0,
        18446744065119617025,
    )

    first = compiled_module._advance_compiled_chunk_with_kernel(
        trajectory=source,
        stop_event_ordinal=old_height + 1,
        kernel=_Q_CROSSING_CHUNK_KERNEL,
    )
    scalar_first = scalar_module._advance_selected_event(trajectory=source, launch_x=0, contact_value=99)
    assert first == scalar_first
    assert first.arms[0].heights[0] == 1 << 32
    assert (first.arms[0].height_square_sum >> 64, first.arms[0].height_square_sum & _U64_MASK) == (1, 0)

    second = compiled_module._advance_compiled_chunk_with_kernel(
        trajectory=first,
        stop_event_ordinal=old_height + 2,
        kernel=_Q_CROSSING_CHUNK_KERNEL,
    )
    scalar_second = scalar_module._advance_selected_event(trajectory=scalar_first, launch_x=0, contact_value=99)
    assert second == scalar_second
    assert second.arms[0].heights[0] == (1 << 32) + 1
    assert (second.arms[0].height_square_sum >> 64, second.arms[0].height_square_sum & _U64_MASK) == (
        1,
        8589934593,
    )


def test_nonzero_high_low_structural_prefix_advances_exactly_without_signed_conversion() -> None:
    n = (1 << 62) + 1
    gap = 2 * n
    prototype = OneCellScalarArmAccumulator(
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        threshold=90,
        heights=(n, n, n),
        event_count=n,
        height_sum=3 * n,
        height_square_sum=3 * n * n,
        void_volume=2 * n,
        endpoint_selected_count=1,
        positive_gap_trigger_count=1,
        gap_sum=2 * n,
        maximum_gap=gap,
        causal_counts=(n - 1, 1, 0, 0),
        causal_gap_sums=(0, gap, 0, 0),
        endpoint_equality_mask_counts=((0, n - 1, 0, 0, 0, 0, 0, 0), (0, 0, 1, 0, 0, 0, 0, 0)),
        gap_histogram=((0, n - 1), (gap, 1)),
        seam_equality_count=0,
    )
    source = OneCellScalarTrajectory(
        root_seed=0,
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        width=3,
        event_count=n,
        arms=tuple(replace(prototype, threshold=threshold) for threshold in _B2_HIGH),
    )
    q = source.arms[0].height_square_sum
    assert (q >> 64, q & _U64_MASK) == (3458764513820540929, 9223372036854775811)
    snapshot = advance_one_cell_compiled_chunk(trajectory=source, stop_event_ordinal=n)
    assert snapshot == source and snapshot is not source

    compiled = compiled_module._advance_compiled_chunk_with_kernel(
        trajectory=source,
        stop_event_ordinal=n + 1,
        kernel=_FORCED_REJECTION_CHUNK_KERNEL,
    )
    scalar = scalar_module._advance_selected_event(
        trajectory=source,
        launch_x=0,
        contact_value=92,
    )
    assert compiled == scalar
    for arm in compiled.arms:
        assert arm.height_square_sum == q + 2 * n + 1
        assert arm.height_square_sum > _U64_MAX


def test_public_alias_rebinding_cannot_redirect_and_private_rebinding_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _compiled_run(9, schedule=_B2_FULL)

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("rebound public alias must not run")

    with monkeypatch.context() as scoped:
        scoped.setattr(compiled_module, "_derive_stream_key", forbidden)
        scoped.setattr(compiled_module, "OneCellScalarTrajectory", object)
        scoped.setattr(compiled_module, "OneCellScalarArmAccumulator", object)
        scoped.setattr(compiled_module, "OneCellBoundaryLaw", object)
        assert _compiled_run(9, schedule=_B2_FULL) == expected

    source = _scalar_run(3)
    corruptions = (
        ("_CERTIFIED_DERIVE_STREAM_KEY", object()),
        ("_CERTIFIED_MULTIPLY_HIGH_LOW_KERNEL", object()),
        ("_CERTIFIED_UNIFORM_BELOW_KERNEL", object()),
        ("_TRAJECTORY_TYPE", object),
        ("_ARM_TYPE", object),
        ("_BOUNDARY_LAWS", tuple(reversed(compiled_module._BOUNDARY_LAWS))),
        ("_SCHEDULES", tuple(reversed(compiled_module._SCHEDULES))),
        ("_SCHEDULE_PRIMARY_CODE", 1),
        ("_LAW_PERIODIC_CODE", 1),
        ("_ERROR_NONE", 1),
        ("_SCALAR_Q_HIGH", 5),
        ("_CONTACT_N_MINUS_ONE", np.uint64(98)),
        ("_COMPILED_CHUNK_KERNEL", object()),
        ("_replace_square_sum_kernel", object()),
    )
    for name, replacement in corruptions:
        with monkeypatch.context() as scoped:
            scoped.setattr(compiled_module, name, replacement)
            with pytest.raises(AssertionError):
                advance_one_cell_compiled_chunk(trajectory=source, stop_event_ordinal=4)
    assert source == _scalar_run(3)


def test_keys_are_derived_once_each_in_launch_contact_order_and_not_for_empty_chunks() -> None:
    code = r"""
import importlib
import tetris_ballistic.engine.rng as rng
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_trajectory import start_one_cell_scalar_trajectory

original = rng.derive_stream_key
calls = []
def spy(root_seed, coupling_group_id, stream_name):
    calls.append((root_seed, coupling_group_id, stream_name))
    return original(root_seed, coupling_group_id, stream_name)
rng.derive_stream_key = spy
compiled = importlib.import_module("tetris_ballistic.engine.one_cell_trajectory_compiled")
t = start_one_cell_scalar_trajectory(
    root_seed=17,
    boundary_law=OneCellBoundaryLaw.PERIODIC,
    width=3,
    threshold_schedule=(5, 50, 90, 95, 98, 99),
)
t = compiled.advance_one_cell_compiled_chunk(trajectory=t, stop_event_ordinal=0)
assert calls == []
t = compiled.advance_one_cell_compiled_chunk(trajectory=t, stop_event_ordinal=1)
assert calls == [
    (17, "pre-one-cell-discovery-v1", "launch"),
    (17, "pre-one-cell-discovery-v1", "contact"),
]
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_roots_import_without_hpc_and_explicit_module_has_clear_import_error() -> None:
    code = r"""
import importlib
import sys

sys.modules["numba"] = None
import tetris_ballistic
import tetris_ballistic.engine
assert "tetris_ballistic.engine.one_cell_trajectory_compiled" not in sys.modules
try:
    importlib.import_module("tetris_ballistic.engine.one_cell_trajectory_compiled")
except ImportError as error:
    message = str(error)
    assert "one_cell_trajectory_compiled" in message
    assert "hpc" in message
else:
    raise AssertionError("explicit compiled trajectory imported without Numba")
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_compiled_dispatchers_are_uint64_nopython_without_fastmath_or_cache() -> None:
    _compiled_run(1)
    _compiled_tape(law=OneCellBoundaryLaw.PERIODIC, width=3, schedule=_B1, tape=((1, 5),))
    compiled_module._add_u128_words_kernel(np.uint64(0), np.uint64(0), np.uint64(0), np.uint64(1))
    dispatchers = (
        compiled_module._COMPILED_CHUNK_KERNEL,
        _ENCODED_CHUNK_KERNEL,
        compiled_module._add_u128_words_kernel,
        compiled_module._subtract_u128_words_kernel,
        compiled_module._replace_square_sum_kernel,
    )
    for dispatcher in dispatchers:
        assert dispatcher.nopython_signatures
        assert dispatcher.targetoptions.get("nopython") is True
        assert dispatcher.targetoptions.get("fastmath", False) is False
        assert dispatcher.targetoptions.get("cache", False) is False
        signatures = " ".join(map(str, dispatcher.nopython_signatures))
        assert "pyobject" not in signatures.lower()
        assert "float" not in signatures.lower()
    chunk_signatures = " ".join(map(str, compiled_module._COMPILED_CHUNK_KERNEL.nopython_signatures))
    assert "uint64" in chunk_signatures
    assert "DictType" in chunk_signatures


def test_results_are_independent_of_python_hash_seed() -> None:
    code = r"""
import hashlib
from dataclasses import asdict
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_trajectory import start_one_cell_scalar_trajectory
from tetris_ballistic.engine.one_cell_trajectory_compiled import advance_one_cell_compiled_chunk

t = start_one_cell_scalar_trajectory(
    root_seed=123456789,
    boundary_law=OneCellBoundaryLaw.PERIODIC,
    width=5,
    threshold_schedule=(90, 95, 98, 99),
)
t = advance_one_cell_compiled_chunk(trajectory=t, stop_event_ordinal=64)
print(hashlib.sha256(repr(asdict(t)).encode()).hexdigest())
"""
    outputs = []
    for seed in ("0", "1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=_REPO_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_no_root_exports_and_ast_dependency_guards() -> None:
    assert not hasattr(tetris_ballistic, "advance_one_cell_compiled_chunk")
    assert not hasattr(reference_engine, "advance_one_cell_compiled_chunk")
    source_path = _REPO_ROOT / "tetris_ballistic/engine/one_cell_trajectory_compiled.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level and node.module is not None
    }
    assert imports <= {"rng", "rng_compiled", "one_cell_boundary", "one_cell_trajectory"}
    for forbidden in (
        "select_one_cell_coupled_event",
        "transition_one_cell_boundary",
        "advance_one_cell_scalar_chunk",
        "_advance_selected_event",
        "uniform_below_from_key",
        "raw_u64_from_key",
        "philox4x64_10(",
        "np.random",
        "numpy.random",
        "fastmath=True",
        "cache=True",
        "tetris_ballistic.tetris_ballistic",
    ):
        assert forbidden not in source


def test_oracle_call_graph_is_production_free() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    forbidden_names = {
        "derive_stream_key",
        "philox4x64_10",
        "raw_u64",
        "uniform_below",
        "select_one_cell_coupled_event",
        "transition_one_cell_boundary",
        "start_one_cell_scalar_trajectory",
        "advance_one_cell_scalar_chunk",
        "advance_one_cell_compiled_chunk",
        "OneCellScalarArmAccumulator",
        "OneCellScalarTrajectory",
    }
    forbidden_aliases = set(forbidden_names)
    forbidden_roots = {"scalar_module", "compiled_module"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for imported in node.names:
                if imported.name in forbidden_names:
                    forbidden_aliases.add(imported.asname or imported.name)
        elif isinstance(node, ast.Import):
            for imported in node.names:
                if imported.name in {
                    "tetris_ballistic.engine.one_cell_trajectory",
                    "tetris_ballistic.engine.one_cell_trajectory_compiled",
                }:
                    forbidden_roots.add(imported.asname or imported.name.split(".")[0])

    local_functions = {
        node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    pending = [name for name in local_functions if name.startswith("_oracle_")]
    inspected: set[str] = set()
    while pending:
        function_name = pending.pop()
        if function_name in inspected:
            continue
        inspected.add(function_name)
        function = local_functions[function_name]
        for name in (
            node for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        ):
            assert name.id not in forbidden_aliases, (function_name, name.id)
            assert name.id not in forbidden_roots, (function_name, name.id)
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if isinstance(call.func, ast.Name) and call.func.id in local_functions:
                pending.append(call.func.id)
            elif isinstance(call.func, ast.Attribute):
                root = call.func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    assert root.id not in forbidden_roots, (function_name, root.id, call.func.attr)

    assert {name for name in local_functions if name.startswith("_oracle_")} <= inspected


def test_pinned_unchanged_input_authorities() -> None:
    expected = {
        "tetris_ballistic/engine/rng_compiled.py": "22dc059d37b04a2dd6099eaef5ba82e0ac218f726c0f4d19b7e2ea1398ebb560",
        "tetris_ballistic/engine/rng.py": "19dca94ea97fae16278b198505200a5be27d80821dd54c8e454f135390888489",
        "tetris_ballistic/engine/one_cell_boundary.py": "2bc7e184476e46bae25b7878847000664f50e1140a009c7917a802e6022089fb",
        "tetris_ballistic/engine/one_cell_coupling.py": "ebf8a2ada59cb176319eab167bef6502811c6d696f93ba60d429921ed26ba6a7",
        "docs/PRE-ONE-CELL-COMPILED-RNG-VECTORS.md": "51900866902cba527b981ec9335bf5112482e91ef6d2dec68ff2fb22ccdffd38",
        "docs/PRE-ONE-CELL-COUPLING-VECTORS.md": "74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3",
        "docs/PRE-ONE-CELL-BOUNDARY-VECTORS.md": "d70374dc2239fc0c5f44781ef49ee9e0d9cce2ca6e16050678a0057282eee23f",
        "docs/SEMANTIC-RNG-VECTORS.md": "913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34",
    }
    for relative_path, digest in expected.items():
        assert hashlib.sha256((_REPO_ROOT / relative_path).read_bytes()).hexdigest() == digest
