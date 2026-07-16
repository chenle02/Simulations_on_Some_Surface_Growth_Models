"""Independent certification for exact scalar PRE one-cell trajectories."""

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

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.one_cell_boundary as one_cell_boundary
import tetris_ballistic.engine.one_cell_coupling as one_cell_coupling
import tetris_ballistic.engine.one_cell_trajectory as one_cell_trajectory
import tetris_ballistic.engine.rng as semantic_rng
from tetris_ballistic.engine.one_cell_boundary import (
    OneCellBoundaryLaw,
    transition_one_cell_boundary,
)
from tetris_ballistic.engine.one_cell_coupling import OneCellCoupledEventSelection
from tetris_ballistic.engine.one_cell_trajectory import (
    OneCellScalarArmAccumulator,
    OneCellScalarTrajectory,
    advance_one_cell_scalar_chunk,
    start_one_cell_scalar_trajectory,
)
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.selection import UniformSelection

_REPO_ROOT = Path(__file__).resolve().parents[1]
_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1
_U64_MASK = _U64_MAX
_THRESHOLDS = (0, 1, 2, 5, 10, 25, 50, 100)
_B1_THRESHOLDS = (0, 5, 50, 100)
_B2_FULL_THRESHOLDS = (5, 50, 90, 95, 98, 99)
_B2_HIGH_THRESHOLDS = (90, 95, 98, 99)
_THRESHOLD_SCHEDULES = (
    _THRESHOLDS,
    _B1_THRESHOLDS,
    _B2_FULL_THRESHOLDS,
    _B2_HIGH_THRESHOLDS,
)
_GROUP = "pre-one-cell-discovery-v1"
_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"
_M0 = 0xD2E7470EE14C6C93
_M1 = 0xCA5A826395121157
_W0 = 0x9E3779B97F4A7C15
_W1 = 0xBB67AE8584CAA73B

_LAW_IDS = (
    "periodic-v1",
    "hard-wall-legacy-asymmetric-v1",
    "hard-wall-reflection-symmetric-v1",
)
_LAWS = tuple(OneCellBoundaryLaw(law_id) for law_id in _LAW_IDS)

_ARM_FIELD_NAMES = (
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
_TRAJECTORY_FIELD_NAMES = (
    "root_seed",
    "boundary_law",
    "width",
    "event_count",
    "arms",
)

# Complete literal trajectory snapshots. Each arm row is
# (threshold, heights, S, Q, V, endpoint, trigger, max_gap, causal counts,
# causal gap sums, flattened False/True equality-mask counts, histogram, seam).
_PINNED_N7_PERIODIC = (
    (
        0,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        0,
    ),
    (
        1,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        0,
    ),
    (
        2,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        0,
    ),
    (
        5,
        (4, 4, 1),
        9,
        33,
        2,
        1,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        0,
    ),
    (
        10,
        (4, 4, 1),
        9,
        33,
        2,
        2,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 4, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        0,
    ),
    (
        25,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        50,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        100,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
)

_PINNED_N7_HARD_WALL = (
    (
        0,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        None,
    ),
    (
        1,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        None,
    ),
    (
        2,
        (2, 4, 1),
        7,
        21,
        0,
        0,
        0,
        0,
        (7, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 7, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 7),),
        None,
    ),
    (
        5,
        (4, 4, 1),
        9,
        33,
        2,
        1,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        None,
    ),
    (
        10,
        (4, 4, 1),
        9,
        33,
        2,
        2,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 4, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        None,
    ),
    (
        25,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        50,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        100,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
)

_PINNED_N50_PERIODIC = (
    (
        0,
        (17, 17, 16),
        50,
        834,
        0,
        0,
        0,
        0,
        (50, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 34, 0, 7, 0, 5, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 50),),
        10,
    ),
    (
        1,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 32, 0, 5, 0, 9, 0, 3, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        10,
    ),
    (
        2,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 32, 0, 5, 0, 9, 0, 3, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        10,
    ),
    (
        5,
        (19, 19, 19),
        57,
        1083,
        7,
        6,
        3,
        3,
        (47, 0, 2, 1),
        (0, 0, 5, 2),
        (0, 25, 0, 7, 0, 8, 0, 4, 0, 3, 0, 0, 2, 0, 1, 0),
        ((0, 47), (2, 2), (3, 1)),
        8,
    ),
    (
        10,
        (19, 19, 19),
        57,
        1083,
        7,
        8,
        3,
        3,
        (47, 0, 2, 1),
        (0, 0, 5, 2),
        (0, 23, 0, 7, 0, 8, 0, 4, 0, 5, 0, 0, 2, 0, 1, 0),
        ((0, 47), (2, 2), (3, 1)),
        8,
    ),
    (
        25,
        (19, 20, 20),
        59,
        1161,
        9,
        15,
        5,
        3,
        (45, 0, 4, 1),
        (0, 0, 6, 3),
        (0, 18, 0, 5, 0, 9, 0, 3, 0, 6, 0, 1, 4, 3, 1, 0),
        ((0, 45), (1, 2), (2, 2), (3, 1)),
        7,
    ),
    (
        50,
        (22, 22, 21),
        65,
        1409,
        15,
        24,
        9,
        3,
        (41, 2, 4, 3),
        (0, 3, 5, 7),
        (0, 14, 0, 3, 0, 6, 0, 3, 0, 10, 2, 3, 4, 1, 3, 1),
        ((0, 41), (1, 5), (2, 2), (3, 2)),
        11,
    ),
    (
        100,
        (23, 23, 22),
        68,
        1542,
        18,
        50,
        9,
        4,
        (41, 1, 5, 3),
        (0, 1, 11, 6),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 23, 1, 7, 5, 4, 3, 7),
        ((0, 41), (1, 3), (2, 4), (3, 1), (4, 1)),
        12,
    ),
)

_PINNED_N50_LEGACY = (
    (
        0,
        (17, 17, 16),
        50,
        834,
        0,
        0,
        0,
        0,
        (50, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 40, 0, 6, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 50),),
        None,
    ),
    (
        1,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 41, 0, 1, 0, 5, 0, 2, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        None,
    ),
    (
        2,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 41, 0, 1, 0, 5, 0, 2, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        None,
    ),
    (
        5,
        (19, 18, 18),
        55,
        1009,
        5,
        6,
        3,
        2,
        (47, 1, 2, 0),
        (0, 2, 3, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 1, 1, 2, 0, 0, 0),
        ((0, 47), (1, 1), (2, 2)),
        None,
    ),
    (
        10,
        (19, 18, 18),
        55,
        1009,
        5,
        8,
        3,
        2,
        (47, 1, 2, 0),
        (0, 2, 3, 0),
        (0, 29, 0, 7, 0, 5, 0, 1, 0, 4, 1, 1, 2, 0, 0, 0),
        ((0, 47), (1, 1), (2, 2)),
        None,
    ),
    (
        25,
        (19, 19, 19),
        57,
        1083,
        7,
        15,
        4,
        3,
        (46, 1, 3, 0),
        (0, 3, 4, 0),
        (0, 21, 0, 4, 0, 8, 0, 2, 0, 7, 1, 2, 3, 1, 0, 1),
        ((0, 46), (1, 2), (2, 1), (3, 1)),
        None,
    ),
    (
        50,
        (20, 19, 19),
        58,
        1122,
        8,
        24,
        5,
        3,
        (45, 1, 4, 0),
        (0, 3, 5, 0),
        (0, 16, 0, 4, 0, 6, 0, 0, 0, 14, 1, 3, 2, 1, 2, 1),
        ((0, 45), (1, 3), (2, 1), (3, 1)),
        None,
    ),
    (
        100,
        (21, 21, 20),
        62,
        1282,
        12,
        50,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 25, 2, 10, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
)

_PINNED_N50_CORRECTED = (
    (
        0,
        (17, 17, 16),
        50,
        834,
        0,
        0,
        0,
        0,
        (50, 0, 0, 0),
        (0, 0, 0, 0),
        (0, 40, 0, 6, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        ((0, 50),),
        None,
    ),
    (
        1,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 41, 0, 1, 0, 5, 0, 2, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        None,
    ),
    (
        2,
        (17, 17, 17),
        51,
        867,
        1,
        1,
        1,
        1,
        (49, 1, 0, 0),
        (0, 1, 0, 0),
        (0, 41, 0, 1, 0, 5, 0, 2, 0, 0, 1, 0, 0, 0, 0, 0),
        ((0, 49), (1, 1)),
        None,
    ),
    (
        5,
        (19, 19, 18),
        56,
        1046,
        6,
        6,
        3,
        2,
        (47, 2, 1, 0),
        (0, 4, 2, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 2, 1, 1, 0, 0, 0),
        ((0, 47), (2, 3)),
        None,
    ),
    (
        10,
        (19, 19, 18),
        56,
        1046,
        6,
        8,
        3,
        2,
        (47, 2, 1, 0),
        (0, 4, 2, 0),
        (0, 29, 0, 7, 0, 5, 0, 1, 0, 4, 2, 1, 1, 0, 0, 0),
        ((0, 47), (2, 3)),
        None,
    ),
    (
        25,
        (19, 19, 19),
        57,
        1083,
        7,
        15,
        4,
        3,
        (46, 1, 3, 0),
        (0, 3, 4, 0),
        (0, 21, 0, 4, 0, 8, 0, 2, 0, 7, 1, 2, 3, 1, 0, 1),
        ((0, 46), (1, 2), (2, 1), (3, 1)),
        None,
    ),
    (
        50,
        (20, 20, 19),
        59,
        1161,
        9,
        24,
        6,
        3,
        (44, 2, 2, 2),
        (0, 4, 3, 2),
        (0, 16, 0, 4, 0, 6, 0, 0, 0, 14, 2, 3, 2, 0, 2, 1),
        ((0, 44), (1, 4), (2, 1), (3, 1)),
        None,
    ),
    (
        100,
        (21, 21, 20),
        62,
        1282,
        12,
        50,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 25, 2, 10, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
)

_PINNED_B2_N7_PERIODIC = (
    (
        5,
        (4, 4, 1),
        9,
        33,
        2,
        1,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        0,
    ),
    (
        50,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        90,
        (4, 4, 4),
        12,
        48,
        5,
        6,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 1, 0, 0, 0, 0, 0, 0, 0, 3, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        95,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        98,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
    (
        99,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 0, 1, 1),
        (0, 0, 2, 3),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 1, 1, 0, 1, 0),
        ((0, 5), (2, 1), (3, 1)),
        1,
    ),
)

_PINNED_B2_N7_HARD_WALL = (
    (
        5,
        (4, 4, 1),
        9,
        33,
        2,
        1,
        1,
        2,
        (6, 0, 1, 0),
        (0, 0, 2, 0),
        (0, 5, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0),
        ((0, 6), (2, 1)),
        None,
    ),
    (
        50,
        (4, 4, 4),
        12,
        48,
        5,
        4,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 3, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        90,
        (4, 4, 4),
        12,
        48,
        5,
        6,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 1, 0, 0, 0, 0, 0, 0, 0, 3, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        95,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        98,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
    (
        99,
        (4, 4, 4),
        12,
        48,
        5,
        7,
        2,
        3,
        (5, 1, 1, 0),
        (0, 3, 2, 0),
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 1, 1, 1, 0, 0, 0),
        ((0, 5), (2, 1), (3, 1)),
        None,
    ),
)

_PINNED_B2_N50_PERIODIC = (
    (
        5,
        (19, 19, 19),
        57,
        1083,
        7,
        6,
        3,
        3,
        (47, 0, 2, 1),
        (0, 0, 5, 2),
        (0, 25, 0, 7, 0, 8, 0, 4, 0, 3, 0, 0, 2, 0, 1, 0),
        ((0, 47), (2, 2), (3, 1)),
        8,
    ),
    (
        50,
        (22, 22, 21),
        65,
        1409,
        15,
        24,
        9,
        3,
        (41, 2, 4, 3),
        (0, 3, 5, 7),
        (0, 14, 0, 3, 0, 6, 0, 3, 0, 10, 2, 3, 4, 1, 3, 1),
        ((0, 41), (1, 5), (2, 2), (3, 2)),
        11,
    ),
    (
        90,
        (23, 23, 22),
        68,
        1542,
        18,
        44,
        9,
        4,
        (41, 1, 5, 3),
        (0, 1, 11, 6),
        (0, 3, 0, 2, 0, 1, 0, 0, 0, 20, 1, 5, 5, 3, 3, 7),
        ((0, 41), (1, 3), (2, 4), (3, 1), (4, 1)),
        12,
    ),
    (
        95,
        (23, 23, 22),
        68,
        1542,
        18,
        46,
        9,
        4,
        (41, 1, 5, 3),
        (0, 1, 11, 6),
        (0, 2, 0, 1, 0, 1, 0, 0, 0, 21, 1, 6, 5, 3, 3, 7),
        ((0, 41), (1, 3), (2, 4), (3, 1), (4, 1)),
        12,
    ),
    (
        98,
        (23, 23, 22),
        68,
        1542,
        18,
        49,
        9,
        4,
        (41, 1, 5, 3),
        (0, 1, 11, 6),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 23, 1, 6, 5, 4, 3, 7),
        ((0, 41), (1, 3), (2, 4), (3, 1), (4, 1)),
        12,
    ),
    (
        99,
        (23, 23, 22),
        68,
        1542,
        18,
        49,
        9,
        4,
        (41, 1, 5, 3),
        (0, 1, 11, 6),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 23, 1, 6, 5, 4, 3, 7),
        ((0, 41), (1, 3), (2, 4), (3, 1), (4, 1)),
        12,
    ),
)

_PINNED_B2_N50_LEGACY = (
    (
        5,
        (19, 18, 18),
        55,
        1009,
        5,
        6,
        3,
        2,
        (47, 1, 2, 0),
        (0, 2, 3, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 1, 1, 2, 0, 0, 0),
        ((0, 47), (1, 1), (2, 2)),
        None,
    ),
    (
        50,
        (20, 19, 19),
        58,
        1122,
        8,
        24,
        5,
        3,
        (45, 1, 4, 0),
        (0, 3, 5, 0),
        (0, 16, 0, 4, 0, 6, 0, 0, 0, 14, 1, 3, 2, 1, 2, 1),
        ((0, 45), (1, 3), (2, 1), (3, 1)),
        None,
    ),
    (
        90,
        (21, 21, 20),
        62,
        1282,
        12,
        44,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 3, 0, 2, 0, 1, 0, 0, 0, 22, 2, 8, 5, 6, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        95,
        (21, 21, 20),
        62,
        1282,
        12,
        46,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 2, 0, 1, 0, 1, 0, 0, 0, 23, 2, 9, 5, 6, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        98,
        (21, 21, 20),
        62,
        1282,
        12,
        49,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 25, 2, 9, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        99,
        (21, 21, 20),
        62,
        1282,
        12,
        49,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 25, 2, 9, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
)

_PINNED_B2_N50_CORRECTED = (
    (
        5,
        (19, 19, 18),
        56,
        1046,
        6,
        6,
        3,
        2,
        (47, 2, 1, 0),
        (0, 4, 2, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 2, 1, 1, 0, 0, 0),
        ((0, 47), (2, 3)),
        None,
    ),
    (
        50,
        (20, 20, 19),
        59,
        1161,
        9,
        24,
        6,
        3,
        (44, 2, 2, 2),
        (0, 4, 3, 2),
        (0, 16, 0, 4, 0, 6, 0, 0, 0, 14, 2, 3, 2, 0, 2, 1),
        ((0, 44), (1, 4), (2, 1), (3, 1)),
        None,
    ),
    (
        90,
        (21, 21, 20),
        62,
        1282,
        12,
        44,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 3, 0, 2, 0, 1, 0, 0, 0, 22, 2, 8, 5, 6, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        95,
        (21, 21, 20),
        62,
        1282,
        12,
        46,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 2, 0, 1, 0, 1, 0, 0, 0, 23, 2, 9, 5, 6, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        98,
        (21, 21, 20),
        62,
        1282,
        12,
        49,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 25, 2, 9, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
    (
        99,
        (21, 21, 20),
        62,
        1282,
        12,
        49,
        7,
        3,
        (43, 2, 5, 0),
        (0, 4, 8, 0),
        (0, 0, 0, 1, 0, 0, 0, 0, 0, 25, 2, 9, 5, 7, 0, 1),
        ((0, 43), (1, 3), (2, 3), (3, 1)),
        None,
    ),
)

_PINNED_ROOT_ZERO_PROJECTIONS = {
    ("periodic-v1", 7): _PINNED_N7_PERIODIC,
    ("periodic-v1", 50): _PINNED_N50_PERIODIC,
    ("hard-wall-legacy-asymmetric-v1", 7): _PINNED_N7_HARD_WALL,
    ("hard-wall-legacy-asymmetric-v1", 50): _PINNED_N50_LEGACY,
    ("hard-wall-reflection-symmetric-v1", 7): _PINNED_N7_HARD_WALL,
    ("hard-wall-reflection-symmetric-v1", 50): _PINNED_N50_CORRECTED,
}

_PINNED_B2_ROOT_ZERO_PROJECTIONS = {
    ("periodic-v1", 7): _PINNED_B2_N7_PERIODIC,
    ("periodic-v1", 50): _PINNED_B2_N50_PERIODIC,
    ("hard-wall-legacy-asymmetric-v1", 7): _PINNED_B2_N7_HARD_WALL,
    ("hard-wall-legacy-asymmetric-v1", 50): _PINNED_B2_N50_LEGACY,
    ("hard-wall-reflection-symmetric-v1", 7): _PINNED_B2_N7_HARD_WALL,
    ("hard-wall-reflection-symmetric-v1", 50): _PINNED_B2_N50_CORRECTED,
}


class _IntSubclass(int):
    pass


class _TupleSubclass(tuple):
    pass


# The oracle below intentionally calls no production RNG, selector, boundary,
# trajectory, accumulator, or observable function. Its state is made only of
# built-in integers, strings, tuples, lists, and dictionaries.
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
        p0 = _M0 * c0
        p1 = _M1 * c2
        hi0, lo0 = p0 >> 64, p0 & _U64_MASK
        hi1, lo1 = p1 >> 64, p1 & _U64_MASK
        c0, c1, c2, c3 = hi1 ^ c1 ^ k0, lo1, hi0 ^ c3 ^ k1, lo0
        if round_index != 9:
            k0 = (k0 + _W0) & _U64_MASK
            k1 = (k1 + _W1) & _U64_MASK
    return c0, c1, c2, c3


def _oracle_uniform(*, root_seed: int, stream_name: str, event_ordinal: int, upper_bound: int) -> tuple[int, int]:
    key = _oracle_key(root_seed, stream_name)
    quotient = _U64_SPACE // upper_bound
    limit = quotient * upper_bound
    rejection_ordinal = 0
    while True:
        word = _oracle_philox((event_ordinal, rejection_ordinal, 0, 0), key)[0]
        if word < limit:
            return word // quotient, rejection_ordinal
        rejection_ordinal += 1


def _oracle_selection(*, root_seed: int, width: int, event_ordinal: int) -> tuple[int, int, int, int]:
    launch, launch_rejection = _oracle_uniform(
        root_seed=root_seed,
        stream_name="launch",
        event_ordinal=event_ordinal,
        upper_bound=width,
    )
    contact, contact_rejection = _oracle_uniform(
        root_seed=root_seed,
        stream_name="contact",
        event_ordinal=event_ordinal,
        upper_bound=100,
    )
    return launch, contact, launch_rejection, contact_rejection


def _oracle_transition(
    law_id: str,
    heights: tuple[int, ...],
    *,
    launch_x: int,
    sticky: bool,
) -> tuple[tuple[int, ...], int, bool, str, int, bool | None]:
    width = len(heights)
    launch_pre = heights[launch_x]
    vertical = launch_pre + 1
    if law_id == "periodic-v1":
        left = heights[(launch_x - 1) % width]
        right = heights[(launch_x + 1) % width]
        left_eligible = right_eligible = True
    else:
        left = heights[launch_x - 1] if launch_x > 0 else None
        right = heights[launch_x + 1] if launch_x < width - 1 else None
        left_eligible = launch_x > (1 if law_id == "hard-wall-legacy-asymmetric-v1" else 0)
        right_eligible = launch_x < width - 1

    post = vertical
    if sticky:
        if left_eligible:
            assert left is not None
            post = max(post, left)
        if right_eligible:
            assert right is not None
            post = max(post, right)
    gap = post - vertical
    trigger = sticky and gap > 0
    if trigger:
        left_causal = left_eligible and left == post
        right_causal = right_eligible and right == post
        if left_causal and right_causal:
            causal = "both"
        elif left_causal:
            causal = "left"
        elif right_causal:
            causal = "right"
        else:  # pragma: no cover - excluded by the recurrence
            raise AssertionError("positive gap lacks a causal neighbor")
    else:
        causal = "none"

    equality_mask = (
        int(post == vertical)
        + 2 * int(left is not None and left == post)
        + 4 * int(right is not None and right == post)
    )
    seam = (
        bool((launch_x == 0 and equality_mask & 2) or (launch_x == width - 1 and equality_mask & 4))
        if law_id == "periodic-v1"
        else None
    )
    post_heights = list(heights)
    post_heights[launch_x] = post
    return tuple(post_heights), gap, trigger, causal, equality_mask, seam


def _oracle_empty_arm(law_id: str, threshold: int, width: int) -> dict[str, object]:
    return {
        "boundary_law": law_id,
        "threshold": threshold,
        "heights": (0,) * width,
        "event_count": 0,
        "height_sum": 0,
        "height_square_sum": 0,
        "void_volume": 0,
        "endpoint_selected_count": 0,
        "positive_gap_trigger_count": 0,
        "gap_sum": 0,
        "maximum_gap": 0,
        "causal_counts": [0, 0, 0, 0],
        "causal_gap_sums": [0, 0, 0, 0],
        "endpoint_equality_mask_counts": [[0] * 8, [0] * 8],
        "gap_histogram": {},
        "seam_equality_count": 0 if law_id == "periodic-v1" else None,
    }


def _oracle_copy_arm(arm: dict[str, object]) -> dict[str, object]:
    return {
        **arm,
        "causal_counts": list(arm["causal_counts"]),
        "causal_gap_sums": list(arm["causal_gap_sums"]),
        "endpoint_equality_mask_counts": [
            list(arm["endpoint_equality_mask_counts"][0]),
            list(arm["endpoint_equality_mask_counts"][1]),
        ],
        "gap_histogram": dict(arm["gap_histogram"]),
    }


def _oracle_fold_arm(arm: dict[str, object], *, launch_x: int, contact_value: int) -> dict[str, object]:
    next_arm = _oracle_copy_arm(arm)
    sticky = contact_value < next_arm["threshold"]
    pre_heights = next_arm["heights"]
    post_heights, gap, trigger, causal, equality_mask, seam = _oracle_transition(
        next_arm["boundary_law"],
        pre_heights,
        launch_x=launch_x,
        sticky=sticky,
    )
    old_height = pre_heights[launch_x]
    new_height = post_heights[launch_x]
    causal_index = {"none": 0, "left": 1, "right": 2, "both": 3}[causal]
    next_arm["heights"] = post_heights
    next_arm["event_count"] += 1
    next_arm["height_sum"] += new_height - old_height
    next_arm["height_square_sum"] += new_height * new_height - old_height * old_height
    next_arm["void_volume"] += gap
    next_arm["endpoint_selected_count"] += int(sticky)
    next_arm["positive_gap_trigger_count"] += int(trigger)
    next_arm["gap_sum"] += gap
    next_arm["maximum_gap"] = max(next_arm["maximum_gap"], gap)
    next_arm["causal_counts"][causal_index] += 1
    next_arm["causal_gap_sums"][causal_index] += gap
    next_arm["endpoint_equality_mask_counts"][int(sticky)][equality_mask] += 1
    next_arm["gap_histogram"][gap] = next_arm["gap_histogram"].get(gap, 0) + 1
    if seam is not None:
        next_arm["seam_equality_count"] += int(seam)
    return next_arm


def _oracle_start(
    law_id: str,
    width: int,
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
) -> tuple[dict[str, object], ...]:
    return tuple(_oracle_empty_arm(law_id, threshold, width) for threshold in threshold_schedule)


def _oracle_from_tape(
    law_id: str,
    width: int,
    tape: tuple[tuple[int, int], ...],
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
) -> tuple[dict[str, object], ...]:
    arms = _oracle_start(law_id, width, threshold_schedule)
    for launch_x, contact_value in tape:
        arms = tuple(_oracle_fold_arm(arm, launch_x=launch_x, contact_value=contact_value) for arm in arms)
    return arms


def _oracle_real(
    *,
    root_seed: int,
    law_id: str,
    width: int,
    stop: int,
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
) -> tuple[tuple[dict[str, object], ...], tuple[tuple[int, int, int, int], ...]]:
    tape = tuple(_oracle_selection(root_seed=root_seed, width=width, event_ordinal=event) for event in range(stop))
    arms = _oracle_from_tape(
        law_id,
        width,
        tuple((launch, contact) for launch, contact, _, _ in tape),
        threshold_schedule,
    )
    return arms, tape


def _freeze_oracle_arm(arm: dict[str, object]) -> dict[str, object]:
    return {
        **arm,
        "causal_counts": tuple(arm["causal_counts"]),
        "causal_gap_sums": tuple(arm["causal_gap_sums"]),
        "endpoint_equality_mask_counts": tuple(tuple(row) for row in arm["endpoint_equality_mask_counts"]),
        "gap_histogram": tuple(sorted(arm["gap_histogram"].items())),
    }


def _oracle_projection(arm: dict[str, object]) -> tuple[object, ...]:
    frozen = _freeze_oracle_arm(arm)
    return (
        frozen["threshold"],
        frozen["heights"],
        frozen["height_sum"],
        frozen["height_square_sum"],
        frozen["void_volume"],
        frozen["endpoint_selected_count"],
        frozen["positive_gap_trigger_count"],
        frozen["maximum_gap"],
        frozen["causal_counts"],
        frozen["causal_gap_sums"],
        tuple(value for row in frozen["endpoint_equality_mask_counts"] for value in row),
        frozen["gap_histogram"],
        frozen["seam_equality_count"],
    )


def _production_projection(arm: OneCellScalarArmAccumulator) -> tuple[object, ...]:
    return (
        arm.threshold,
        arm.heights,
        arm.height_sum,
        arm.height_square_sum,
        arm.void_volume,
        arm.endpoint_selected_count,
        arm.positive_gap_trigger_count,
        arm.maximum_gap,
        arm.causal_counts,
        arm.causal_gap_sums,
        tuple(value for row in arm.endpoint_equality_mask_counts for value in row),
        arm.gap_histogram,
        arm.seam_equality_count,
    )


def _assert_arm_matches_oracle(arm: OneCellScalarArmAccumulator, expected: dict[str, object]) -> None:
    expected = _freeze_oracle_arm(expected)
    assert arm.boundary_law.value == expected["boundary_law"]
    for name in _ARM_FIELD_NAMES[1:]:
        assert getattr(arm, name) == expected[name], name
    assert arm.width == len(arm.heights)
    assert arm.roughness_numerator == arm.width * arm.height_square_sum - arm.height_sum**2


def _assert_trajectory_matches_oracle(
    trajectory: OneCellScalarTrajectory,
    expected_arms: tuple[dict[str, object], ...],
) -> None:
    assert trajectory.event_count == expected_arms[0]["event_count"]
    assert trajectory.width == len(expected_arms[0]["heights"])
    expected_schedule = tuple(int(arm["threshold"]) for arm in expected_arms)
    assert trajectory.threshold_schedule == expected_schedule
    assert tuple(arm.threshold for arm in trajectory.arms) == expected_schedule
    for arm, expected in zip(trajectory.arms, expected_arms):
        _assert_arm_matches_oracle(arm, expected)
    _assert_structural_laws(trajectory)


def _assert_structural_laws(trajectory: OneCellScalarTrajectory) -> None:
    previous_endpoint = -1
    previous_heights = (-1,) * trajectory.width
    for arm in trajectory.arms:
        n = arm.event_count
        assert arm.boundary_law is trajectory.boundary_law
        assert n == trajectory.event_count
        assert arm.height_sum == sum(arm.heights)
        assert arm.height_square_sum == sum(height * height for height in arm.heights)
        assert arm.void_volume == arm.height_sum - n == arm.gap_sum
        assert arm.roughness_numerator >= 0
        assert all(0 <= height <= n for height in arm.heights)
        assert sum(arm.causal_counts) == n
        assert arm.causal_counts[0] == n - arm.positive_gap_trigger_count
        assert sum(arm.causal_counts[1:]) == arm.positive_gap_trigger_count
        assert arm.causal_gap_sums[0] == 0
        assert sum(arm.causal_gap_sums) == arm.void_volume
        assert sum(sum(row) for row in arm.endpoint_equality_mask_counts) == n
        assert sum(arm.endpoint_equality_mask_counts[1]) == arm.endpoint_selected_count
        assert arm.endpoint_equality_mask_counts[0][0] == 0
        assert arm.endpoint_equality_mask_counts[1][0] == 0
        assert arm.positive_gap_trigger_count <= arm.endpoint_selected_count <= n
        if n == 0:
            assert arm.gap_histogram == ()
        else:
            assert arm.gap_histogram[0][0] == 0
            assert all(left[0] < right[0] for left, right in zip(arm.gap_histogram, arm.gap_histogram[1:]))
            assert all(gap >= 0 and count > 0 for gap, count in arm.gap_histogram)
            assert sum(count for _, count in arm.gap_histogram) == n
            assert sum(gap * count for gap, count in arm.gap_histogram) == arm.void_volume
            assert sum(count for gap, count in arm.gap_histogram if gap > 0) == arm.positive_gap_trigger_count
            assert arm.gap_histogram[-1][0] == arm.maximum_gap
        if trajectory.boundary_law is OneCellBoundaryLaw.PERIODIC:
            assert type(arm.seam_equality_count) is int
            assert 0 <= arm.seam_equality_count <= n
        else:
            assert arm.seam_equality_count is None
        assert arm.endpoint_selected_count >= previous_endpoint
        assert all(current >= previous for current, previous in zip(arm.heights, previous_heights))
        previous_endpoint = arm.endpoint_selected_count
        previous_heights = arm.heights
    arms_by_threshold = {arm.threshold: arm for arm in trajectory.arms}
    if zero_arm := arms_by_threshold.get(0):
        assert zero_arm.endpoint_selected_count == 0
        assert zero_arm.positive_gap_trigger_count == 0
        assert zero_arm.void_volume == 0
        assert zero_arm.height_sum == trajectory.event_count
    if hundred_arm := arms_by_threshold.get(100):
        assert hundred_arm.endpoint_selected_count == trajectory.event_count


def _start(
    law: OneCellBoundaryLaw = OneCellBoundaryLaw.PERIODIC,
    width: int = 3,
    root_seed: int = 0,
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
):
    return start_one_cell_scalar_trajectory(
        root_seed=root_seed,
        boundary_law=law,
        width=width,
        threshold_schedule=threshold_schedule,
    )


def _run(
    stop: int,
    *,
    law: OneCellBoundaryLaw = OneCellBoundaryLaw.PERIODIC,
    width: int = 3,
    root_seed: int = 0,
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
) -> OneCellScalarTrajectory:
    return advance_one_cell_scalar_chunk(
        trajectory=_start(
            law=law,
            width=width,
            root_seed=root_seed,
            threshold_schedule=threshold_schedule,
        ),
        stop_event_ordinal=stop,
    )


def _run_tape(
    law: OneCellBoundaryLaw,
    width: int,
    tape: tuple[tuple[int, int], ...],
    threshold_schedule: tuple[int, ...] = _THRESHOLDS,
) -> OneCellScalarTrajectory:
    trajectory = _start(law=law, width=width, threshold_schedule=threshold_schedule)
    for launch_x, contact_value in tape:
        trajectory = one_cell_trajectory._advance_selected_event(
            trajectory=trajectory,
            launch_x=launch_x,
            contact_value=contact_value,
        )
    return trajectory


def _forged_selection(
    *,
    root_seed: int,
    event_ordinal: int,
    width: int,
    launch_x: int = 1,
    contact_value: int = 5,
) -> OneCellCoupledEventSelection:
    return OneCellCoupledEventSelection(
        root_seed=root_seed,
        event_ordinal=event_ordinal,
        width=width,
        launch=UniformSelection("launch", SemanticDraw(launch_x, 0)),
        contact=UniformSelection("contact", SemanticDraw(contact_value, 0)),
    )


def test_public_surface_signatures_records_and_initial_state_are_exact() -> None:
    assert one_cell_trajectory.__all__ == [
        "OneCellScalarArmAccumulator",
        "OneCellScalarTrajectory",
        "start_one_cell_scalar_trajectory",
        "advance_one_cell_scalar_chunk",
    ]
    assert tuple(field.name for field in fields(OneCellScalarArmAccumulator)) == _ARM_FIELD_NAMES
    assert tuple(field.name for field in fields(OneCellScalarTrajectory)) == _TRAJECTORY_FIELD_NAMES
    for function, names, defaults in (
        (
            start_one_cell_scalar_trajectory,
            ("root_seed", "boundary_law", "width", "threshold_schedule"),
            (inspect.Parameter.empty, inspect.Parameter.empty, inspect.Parameter.empty, _THRESHOLDS),
        ),
        (
            advance_one_cell_scalar_chunk,
            ("trajectory", "stop_event_ordinal"),
            (inspect.Parameter.empty, inspect.Parameter.empty),
        ),
        (
            one_cell_trajectory._advance_selected_event,
            ("trajectory", "launch_x", "contact_value"),
            (inspect.Parameter.empty, inspect.Parameter.empty, inspect.Parameter.empty),
        ),
    ):
        parameters = tuple(inspect.signature(function).parameters.values())
        assert tuple(parameter.name for parameter in parameters) == names
        assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters)
        assert tuple(parameter.default for parameter in parameters) == defaults

    for law, threshold_schedule in product(_LAWS, _THRESHOLD_SCHEDULES):
        trajectory = _start(
            law=law,
            width=5,
            root_seed=_U128_MAX,
            threshold_schedule=threshold_schedule,
        )
        assert trajectory.root_seed == _U128_MAX
        assert trajectory.boundary_law is law
        assert trajectory.width == 5
        assert trajectory.event_count == 0
        assert trajectory.threshold_schedule == threshold_schedule
        assert tuple(arm.threshold for arm in trajectory.arms) == threshold_schedule
        assert len({id(arm) for arm in trajectory.arms}) == len(threshold_schedule)
        assert len({id(arm.heights) for arm in trajectory.arms}) == len(threshold_schedule)
        _assert_structural_laws(trajectory)
        with pytest.raises(FrozenInstanceError):
            trajectory.event_count = 1
        with pytest.raises(FrozenInstanceError):
            trajectory.arms[0].height_sum = 1
        assert not hasattr(trajectory, "__dict__")
        assert not hasattr(trajectory.arms[0], "__dict__")


def test_records_expose_only_frozen_derived_properties() -> None:
    arm_properties = {name for name, value in vars(OneCellScalarArmAccumulator).items() if isinstance(value, property)}
    trajectory_properties = {
        name for name, value in vars(OneCellScalarTrajectory).items() if isinstance(value, property)
    }
    assert arm_properties == {"width", "roughness_numerator"}
    assert trajectory_properties == {"threshold_schedule"}


def test_empty_chunk_is_equal_delegate_free_defensive_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    trajectory = _run(7)

    def forbidden(**_: object) -> object:
        raise AssertionError("empty chunk must be delegate-free")

    monkeypatch.setattr(one_cell_coupling, "select_uniform", forbidden)
    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", forbidden)
    snapshot = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=7)
    assert snapshot == trajectory
    assert snapshot is not trajectory
    assert all(actual is not original for actual, original in zip(snapshot.arms, trajectory.arms))
    assert all(actual.heights is not original.heights for actual, original in zip(snapshot.arms, trajectory.arms))


def test_independent_rng_prefix_and_pinned_root_zero_trajectory_vectors() -> None:
    expected_selections = (
        (1, 79, 0, 0),
        (1, 9, 0, 0),
        (1, 63, 0, 0),
        (0, 2, 0, 0),
        (0, 92, 0, 0),
        (1, 17, 0, 0),
        (2, 24, 0, 0),
    )
    assert tuple(_oracle_selection(root_seed=0, width=3, event_ordinal=i) for i in range(7)) == expected_selections

    for law in _LAWS:
        for stop in (7, 50):
            expected_arms, _ = _oracle_real(root_seed=0, law_id=law.value, width=3, stop=stop)
            actual = _run(stop, law=law)
            assert actual == _run(stop, law=law, threshold_schedule=_THRESHOLDS)
            literal = _PINNED_ROOT_ZERO_PROJECTIONS[(law.value, stop)]
            assert tuple(_oracle_projection(arm) for arm in expected_arms) == literal
            assert tuple(_production_projection(arm) for arm in actual.arms) == literal
            _assert_trajectory_matches_oracle(actual, expected_arms)

            b2_expected, _ = _oracle_real(
                root_seed=0,
                law_id=law.value,
                width=3,
                stop=stop,
                threshold_schedule=_B2_FULL_THRESHOLDS,
            )
            b2_actual = _run(stop, law=law, threshold_schedule=_B2_FULL_THRESHOLDS)
            b2_literal = _PINNED_B2_ROOT_ZERO_PROJECTIONS[(law.value, stop)]
            assert tuple(_oracle_projection(arm) for arm in b2_expected) == b2_literal
            assert tuple(_production_projection(arm) for arm in b2_actual.arms) == b2_literal
            _assert_trajectory_matches_oracle(b2_actual, b2_expected)

    assert sum(len(rows) for rows in _PINNED_ROOT_ZERO_PROJECTIONS.values()) == 48
    assert sum(len(rows) for rows in _PINNED_B2_ROOT_ZERO_PROJECTIONS.values()) == 36

    periodic = _run(50, law=OneCellBoundaryLaw.PERIODIC).arms[3]
    legacy = _run(50, law=OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC).arms[3]
    corrected = _run(50, law=OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC).arms[3]
    assert (periodic.heights, periodic.height_sum, periodic.height_square_sum, periodic.void_volume) == (
        (19, 19, 19),
        57,
        1083,
        7,
    )
    assert (legacy.heights, legacy.height_sum, legacy.height_square_sum, legacy.void_volume) == (
        (19, 18, 18),
        55,
        1009,
        5,
    )
    assert (corrected.heights, corrected.height_sum, corrected.height_square_sum, corrected.void_volume) == (
        (19, 19, 18),
        56,
        1046,
        6,
    )
    assert (
        periodic.endpoint_selected_count,
        periodic.positive_gap_trigger_count,
        periodic.maximum_gap,
        periodic.causal_counts,
        periodic.causal_gap_sums,
        tuple(v for row in periodic.endpoint_equality_mask_counts for v in row),
        periodic.gap_histogram,
        periodic.seam_equality_count,
    ) == (
        6,
        3,
        3,
        (47, 0, 2, 1),
        (0, 0, 5, 2),
        (0, 25, 0, 7, 0, 8, 0, 4, 0, 3, 0, 0, 2, 0, 1, 0),
        ((0, 47), (2, 2), (3, 1)),
        8,
    )
    assert (
        legacy.endpoint_selected_count,
        legacy.positive_gap_trigger_count,
        legacy.maximum_gap,
        legacy.causal_counts,
        legacy.causal_gap_sums,
        tuple(v for row in legacy.endpoint_equality_mask_counts for v in row),
        legacy.gap_histogram,
        legacy.seam_equality_count,
    ) == (
        6,
        3,
        2,
        (47, 1, 2, 0),
        (0, 2, 3, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 1, 1, 2, 0, 0, 0),
        ((0, 47), (1, 1), (2, 2)),
        None,
    )
    assert (
        corrected.endpoint_selected_count,
        corrected.positive_gap_trigger_count,
        corrected.maximum_gap,
        corrected.causal_counts,
        corrected.causal_gap_sums,
        tuple(v for row in corrected.endpoint_equality_mask_counts for v in row),
        corrected.gap_histogram,
        corrected.seam_equality_count,
    ) == (
        6,
        3,
        2,
        (47, 2, 1, 0),
        (0, 4, 2, 0),
        (0, 31, 0, 7, 0, 5, 0, 1, 0, 2, 2, 1, 1, 0, 0, 0),
        ((0, 47), (2, 3)),
        None,
    )

    for law in _LAWS:
        b2 = _run(50, law=law, threshold_schedule=_B2_FULL_THRESHOLDS)
        high_arms = b2.arms[2:]
        expected_heights = (23, 23, 22) if law is OneCellBoundaryLaw.PERIODIC else (21, 21, 20)
        expected_s_q_v = (68, 1542, 18) if law is OneCellBoundaryLaw.PERIODIC else (62, 1282, 12)
        assert tuple(arm.heights for arm in high_arms) == (expected_heights,) * 4
        assert (
            tuple((arm.height_sum, arm.height_square_sum, arm.void_volume) for arm in high_arms)
            == (expected_s_q_v,) * 4
        )
        assert tuple(arm.endpoint_selected_count for arm in high_arms) == (44, 46, 49, 49)


def test_contact_boundary_witnesses_and_schedule_projections_are_exact() -> None:
    contact_witnesses = (
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
    contact_key = _oracle_key(0, "contact")
    for expected_value, event, expected_hex in contact_witnesses:
        raw_word = _oracle_philox((event, 0, 0, 0), contact_key)[0]
        assert f"{raw_word:016x}" == expected_hex
        assert raw_word < (_U64_SPACE // 100) * 100
        _, contact, _, contact_rejection = _oracle_selection(root_seed=0, width=3, event_ordinal=event)
        assert (contact, contact_rejection) == (expected_value, 0)

    neighbor_contacts = (4, 5, 49, 50, 89, 90, 94, 95, 97, 98, 99)
    b2 = _run_tape(
        OneCellBoundaryLaw.PERIODIC,
        3,
        tuple((1, contact) for contact in neighbor_contacts),
        _B2_FULL_THRESHOLDS,
    )
    assert tuple(arm.endpoint_selected_count for arm in b2.arms) == (1, 3, 5, 7, 9, 10)

    for law, width, root_seed, stop in product(_LAWS, (3, 5), (0, 95), (0, 1, 7, 50)):
        primary = _run(stop, law=law, width=width, root_seed=root_seed)
        b1 = _run(
            stop,
            law=law,
            width=width,
            root_seed=root_seed,
            threshold_schedule=_B1_THRESHOLDS,
        )
        b2_full = _run(
            stop,
            law=law,
            width=width,
            root_seed=root_seed,
            threshold_schedule=_B2_FULL_THRESHOLDS,
        )
        b2_high = _run(
            stop,
            law=law,
            width=width,
            root_seed=root_seed,
            threshold_schedule=_B2_HIGH_THRESHOLDS,
        )
        primary_by_threshold = {arm.threshold: arm for arm in primary.arms}
        b2_by_threshold = {arm.threshold: arm for arm in b2_full.arms}
        assert b1.arms == tuple(primary_by_threshold[threshold] for threshold in _B1_THRESHOLDS)
        assert b2_high.arms == tuple(b2_by_threshold[threshold] for threshold in _B2_HIGH_THRESHOLDS)
        assert tuple(b2_by_threshold[threshold] for threshold in (5, 50)) == tuple(
            primary_by_threshold[threshold] for threshold in (5, 50)
        )


@pytest.mark.parametrize(("law", "threshold_schedule"), tuple(product(_LAWS, _THRESHOLD_SCHEDULES)))
def test_every_partition_of_seven_and_every_split_of_fifty(
    law: OneCellBoundaryLaw,
    threshold_schedule: tuple[int, ...],
) -> None:
    uninterrupted_7 = _run(7, law=law, threshold_schedule=threshold_schedule)
    for cut_mask in range(1 << 6):
        stops = [index + 1 for index in range(6) if cut_mask & (1 << index)] + [7]
        trajectory = _start(law=law, threshold_schedule=threshold_schedule)
        for stop in stops:
            trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=stop)
        assert trajectory == uninterrupted_7

    uninterrupted_50 = _run(50, law=law, threshold_schedule=threshold_schedule)
    for split in range(51):
        trajectory = _start(law=law, threshold_schedule=threshold_schedule)
        trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=split)
        trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=split)
        trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=50)
        trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=50)
        assert trajectory == uninterrupted_50

    unit_chunks = _start(law=law, threshold_schedule=threshold_schedule)
    for stop in range(1, 51):
        unit_chunks = advance_one_cell_scalar_chunk(trajectory=unit_chunks, stop_event_ordinal=stop)
    assert unit_chunks == uninterrupted_50


@pytest.mark.parametrize(("law", "threshold_schedule"), tuple(product(_LAWS, _THRESHOLD_SCHEDULES)))
def test_deterministic_longer_chunk_partitions(
    law: OneCellBoundaryLaw,
    threshold_schedule: tuple[int, ...],
) -> None:
    uninterrupted = _run(
        257,
        law=law,
        width=5,
        root_seed=0x0123456789ABCDEF,
        threshold_schedule=threshold_schedule,
    )
    partitions = (
        (257,),
        (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 257),
        (7, 19, 23, 71, 72, 128, 129, 130, 199, 256, 257),
        tuple(range(1, 258, 17)) + (257,),
    )
    for stops in partitions:
        trajectory = _start(
            law=law,
            width=5,
            root_seed=0x0123456789ABCDEF,
            threshold_schedule=threshold_schedule,
        )
        for stop in stops:
            trajectory = advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=stop)
        assert trajectory == uninterrupted


def test_all_14400_one_event_schedule_cases_match_independent_oracle() -> None:
    count = 0
    transitions = 0
    for threshold_schedule, law, width, launch_x, contact_value in product(
        _THRESHOLD_SCHEDULES,
        _LAWS,
        range(3, 6),
        range(5),
        range(100),
    ):
        if launch_x >= width:
            continue
        expected = _oracle_from_tape(
            law.value,
            width,
            ((launch_x, contact_value),),
            threshold_schedule,
        )
        actual = _run_tape(
            law,
            width,
            ((launch_x, contact_value),),
            threshold_schedule,
        )
        _assert_trajectory_matches_oracle(actual, expected)
        count += 1
        transitions += len(threshold_schedule)
    assert count == 14400
    assert transitions == 79200


def test_all_3564_two_event_schedule_tapes_match_independent_oracle() -> None:
    count = 0
    transitions = 0
    representatives = (
        (_THRESHOLDS, (0, 1, 2, 5, 10, 25, 50)),
        (_B1_THRESHOLDS, (0, 5, 50)),
        (_B2_FULL_THRESHOLDS, (0, 5, 50, 90, 95, 98, 99)),
        (_B2_HIGH_THRESHOLDS, (0, 90, 95, 98, 99)),
    )
    for threshold_schedule, contacts_for_schedule in representatives:
        for law, launches, contacts in product(
            _LAWS,
            product(range(3), repeat=2),
            product(contacts_for_schedule, repeat=2),
        ):
            tape = tuple(zip(launches, contacts))
            expected = _oracle_from_tape(law.value, 3, tape, threshold_schedule)
            actual = _run_tape(law, 3, tape, threshold_schedule)
            _assert_trajectory_matches_oracle(actual, expected)
            count += 1
            transitions += 2 * len(threshold_schedule)
    assert count == 3564
    assert transitions == 44388


@pytest.mark.slow
def test_all_67878_three_event_schedule_tapes_match_independent_oracle() -> None:
    count = 0
    transitions = 0
    representatives = (
        (_THRESHOLDS, (0, 1, 2, 5, 10, 25, 50)),
        (_B1_THRESHOLDS, (0, 5, 50)),
        (_B2_FULL_THRESHOLDS, (0, 5, 50, 90, 95, 98, 99)),
        (_B2_HIGH_THRESHOLDS, (0, 90, 95, 98, 99)),
    )
    for threshold_schedule, contacts_for_schedule in representatives:
        for law, launches, contacts in product(
            _LAWS,
            product(range(3), repeat=3),
            product(contacts_for_schedule, repeat=3),
        ):
            tape = tuple(zip(launches, contacts))
            expected = _oracle_from_tape(law.value, 3, tape, threshold_schedule)
            actual = _run_tape(law, 3, tape, threshold_schedule)
            _assert_trajectory_matches_oracle(actual, expected)
            count += 1
            transitions += 3 * len(threshold_schedule)
    assert count == 67878
    assert transitions == 1314630


def test_independent_real_rng_sweep_768_trajectories() -> None:
    trajectories = 0
    transitions = 0
    for root_seed, width, law, threshold_schedule in product(
        range(16),
        (3, 4, 5, 32),
        _LAWS,
        _THRESHOLD_SCHEDULES,
    ):
        expected, _ = _oracle_real(
            root_seed=root_seed,
            law_id=law.value,
            width=width,
            stop=64,
            threshold_schedule=threshold_schedule,
        )
        actual = _run(
            64,
            law=law,
            width=width,
            root_seed=root_seed,
            threshold_schedule=threshold_schedule,
        )
        _assert_trajectory_matches_oracle(actual, expected)
        trajectories += 1
        transitions += 64 * len(threshold_schedule)
    assert trajectories == 768
    assert transitions == 270336


def test_forced_launch_and_contact_rejection_real_route_and_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_raw = semantic_rng.raw_u64
    forced = {("launch", 1), ("contact", 2)}
    calls: list[tuple[str, int, int]] = []

    def raw_u64_with_rejections(
        *,
        root_seed: int,
        coupling_group_id: str,
        stream_name: str,
        event_ordinal: int,
        rejection_ordinal: int = 0,
    ) -> int:
        calls.append((stream_name, event_ordinal, rejection_ordinal))
        if (stream_name, event_ordinal) in forced:
            return _U64_MAX if rejection_ordinal == 0 else 0
        return original_raw(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )

    monkeypatch.setattr(semantic_rng, "raw_u64", raw_u64_with_rejections)
    forced_tape = ((1, 79), (0, 9), (1, 0), (0, 2), (0, 92))
    endpoint_totals = {
        _THRESHOLDS: (0, 1, 1, 2, 3, 3, 3, 5),
        _B1_THRESHOLDS: (0, 2, 3, 5),
        _B2_FULL_THRESHOLDS: (2, 3, 4, 5, 5, 5),
        _B2_HIGH_THRESHOLDS: (4, 5, 5, 5),
    }
    for law, threshold_schedule in product(_LAWS, _THRESHOLD_SCHEDULES):
        uninterrupted = _run(
            5,
            law=law,
            width=3,
            root_seed=0,
            threshold_schedule=threshold_schedule,
        )
        expected = _oracle_from_tape(law.value, 3, forced_tape, threshold_schedule)
        _assert_trajectory_matches_oracle(uninterrupted, expected)
        assert tuple(arm.endpoint_selected_count for arm in uninterrupted.arms) == endpoint_totals[threshold_schedule]
        split = _start(
            law=law,
            width=3,
            root_seed=0,
            threshold_schedule=threshold_schedule,
        )
        for stop in (1, 2, 2, 3, 5):
            split = advance_one_cell_scalar_chunk(trajectory=split, stop_event_ordinal=stop)
        assert split == uninterrupted
    assert ("launch", 1, 0) in calls and ("launch", 1, 1) in calls
    assert ("contact", 2, 0) in calls and ("contact", 2, 1) in calls


@pytest.mark.parametrize("threshold_schedule", _THRESHOLD_SCHEDULES)
def test_selector_once_and_boundary_calls_in_schedule_order(
    threshold_schedule: tuple[int, ...],
) -> None:
    trajectory = _start(threshold_schedule=threshold_schedule)
    selector_calls: list[tuple[int, int, int]] = []

    def selector(*, root_seed: int, event_ordinal: int, width: int) -> OneCellCoupledEventSelection:
        selector_calls.append((root_seed, event_ordinal, width))
        return _forged_selection(
            root_seed=root_seed,
            event_ordinal=event_ordinal,
            width=width,
            launch_x=1,
            contact_value=5,
        )

    selected = one_cell_trajectory._advance_certified_event(
        trajectory,
        0,
        _selector_delegate=selector,
    )
    assert selector_calls == [(0, 0, 3)]

    transition_calls: list[tuple[tuple[int, ...], int, bool]] = []

    def transition_spy(
        *,
        boundary_law: OneCellBoundaryLaw,
        heights: tuple[int, ...],
        launch_x: int,
        sticky_endpoint_selected: bool,
    ) -> object:
        transition_calls.append((heights, launch_x, sticky_endpoint_selected))
        return transition_one_cell_boundary(
            boundary_law=boundary_law,
            heights=heights,
            launch_x=launch_x,
            sticky_endpoint_selected=sticky_endpoint_selected,
        )

    folded = one_cell_trajectory._fold_selected_event(
        trajectory=trajectory,
        launch_x=1,
        contact_value=5,
        _transition_delegate=transition_spy,
    )
    assert folded == selected
    assert len(transition_calls) == len(threshold_schedule)
    assert [sticky for _, _, sticky in transition_calls] == [5 < threshold for threshold in threshold_schedule]
    assert all(heights == (0, 0, 0) and launch_x == 1 for heights, launch_x, _ in transition_calls)


def test_malformed_and_cross_request_delegates_fail_closed_without_mutation() -> None:
    trajectory = _start()

    def malformed_selector(**_: object) -> object:
        return object()

    with pytest.raises(AssertionError, match="invalid record type"):
        one_cell_trajectory._advance_certified_event(
            trajectory,
            0,
            _selector_delegate=malformed_selector,
        )

    def cross_request_selector(*, root_seed: int, event_ordinal: int, width: int) -> OneCellCoupledEventSelection:
        return _forged_selection(
            root_seed=root_seed,
            event_ordinal=event_ordinal + 1,
            width=width,
        )

    with pytest.raises(AssertionError, match="different request"):
        one_cell_trajectory._advance_certified_event(
            trajectory,
            0,
            _selector_delegate=cross_request_selector,
        )

    transition_calls = 0

    def cross_request_transition(
        *,
        boundary_law: OneCellBoundaryLaw,
        heights: tuple[int, ...],
        launch_x: int,
        sticky_endpoint_selected: bool,
    ) -> object:
        nonlocal transition_calls
        transition_calls += 1
        return transition_one_cell_boundary(
            boundary_law=boundary_law,
            heights=heights,
            launch_x=(launch_x + 1) % len(heights),
            sticky_endpoint_selected=sticky_endpoint_selected,
        )

    with pytest.raises(AssertionError, match="different request"):
        one_cell_trajectory._fold_selected_event(
            trajectory=trajectory,
            launch_x=1,
            contact_value=5,
            _transition_delegate=cross_request_transition,
        )
    assert transition_calls == 1
    assert trajectory == _start()

    def malformed_transition(**_: object) -> object:
        return object()

    with pytest.raises(AssertionError, match="invalid record type"):
        one_cell_trajectory._fold_selected_event(
            trajectory=trajectory,
            launch_x=1,
            contact_value=5,
            _transition_delegate=malformed_transition,
        )
    assert trajectory == _start()


def test_synthetic_witnesses_cover_causal_equality_seam_and_legacy_defect() -> None:
    tapes = (
        ((0, 99), (0, 99), (0, 99), (0, 99), (0, 99), (1, 0)),
        ((0, 99), (0, 99), (2, 99), (2, 99), (1, 0)),
        ((2, 99), (0, 0)),
    )
    seen_causal: set[str] = set()
    seen_masks: set[int] = set()
    for law, tape in product(_LAWS, tapes):
        expected = _oracle_from_tape(law.value, 3, tape)
        actual = _run_tape(law, 3, tape)
        _assert_trajectory_matches_oracle(actual, expected)
        for arm in actual.arms:
            seen_causal.update(
                side for side, count in zip(("none", "left", "right", "both"), arm.causal_counts) if count
            )
            seen_masks.update(
                mask for row in arm.endpoint_equality_mask_counts for mask, count in enumerate(row) if count
            )
    assert seen_causal == {"none", "left", "right", "both"}
    assert seen_masks == {1, 2, 3, 4, 5, 6}

    defect_tape = ((0, 99),) * 5 + ((1, 0),)
    legacy = _run_tape(OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC, 3, defect_tape)
    corrected = _run_tape(OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC, 3, defect_tape)
    assert legacy.arms[-1].heights != corrected.arms[-1].heights

    seam_nontrigger = _run_tape(OneCellBoundaryLaw.PERIODIC, 3, ((2, 99), (0, 0)))
    assert seam_nontrigger.arms[0].seam_equality_count > 0
    assert seam_nontrigger.arms[0].positive_gap_trigger_count == 0


def test_exact_types_ranges_and_keyword_only_calls() -> None:
    for bad in (True, 0.0, _IntSubclass(0), "0", None):
        with pytest.raises(TypeError):
            start_one_cell_scalar_trajectory(
                root_seed=bad,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=3,
            )
    for bad in (-1, _U128_MAX + 1):
        with pytest.raises(ValueError):
            start_one_cell_scalar_trajectory(
                root_seed=bad,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=3,
            )
    for bad in ("periodic-v1", 0, None):
        with pytest.raises(TypeError):
            start_one_cell_scalar_trajectory(root_seed=0, boundary_law=bad, width=3)
    for bad in (True, 3.0, _IntSubclass(3), "3", None):
        with pytest.raises(TypeError):
            start_one_cell_scalar_trajectory(
                root_seed=0,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=bad,
            )
    for bad in (2, 1025):
        with pytest.raises(ValueError):
            start_one_cell_scalar_trajectory(
                root_seed=0,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=bad,
            )
    for bad in (
        list(_THRESHOLDS),
        _TupleSubclass(_THRESHOLDS),
        "primary",
        None,
    ):
        with pytest.raises(TypeError):
            start_one_cell_scalar_trajectory(
                root_seed=0,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=3,
                threshold_schedule=bad,
            )
    for bad in (
        (0, 5, 50),
        (0, 5, 50, 99, 100),
        (100, 50, 5, 0),
        (0, 5, 5, 100),
        (0, 5, 50, 90, 95, 98, 99, 100),
        (0, 5, 90, 100),
        (),
    ):
        with pytest.raises(ValueError):
            start_one_cell_scalar_trajectory(
                root_seed=0,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=3,
                threshold_schedule=bad,
            )
    for bad in ((0, 5, 50, True), (0, 5.0, 50, 100), (0, _IntSubclass(5), 50, 100)):
        with pytest.raises(TypeError):
            start_one_cell_scalar_trajectory(
                root_seed=0,
                boundary_law=OneCellBoundaryLaw.PERIODIC,
                width=3,
                threshold_schedule=bad,
            )

    trajectory = _run(2)
    for bad in (True, 2.0, _IntSubclass(2), "2", None):
        with pytest.raises(TypeError):
            advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=bad)
    for bad in (0, 1, _U64_SPACE):
        with pytest.raises(ValueError):
            advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=bad)
    with pytest.raises(TypeError):
        start_one_cell_scalar_trajectory(0, OneCellBoundaryLaw.PERIODIC, 3)
    with pytest.raises(TypeError):
        advance_one_cell_scalar_chunk(trajectory, 3)


def test_bounds_fail_before_selector_and_leave_input_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    trajectory = _run(2)
    original = trajectory
    calls = 0

    def forbidden(**_: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("selector must not be called")

    monkeypatch.setattr(one_cell_coupling, "select_uniform", forbidden)
    for stop in (1, _U64_SPACE, _U64_MAX):
        with pytest.raises(ValueError):
            advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=stop)
    assert calls == 0
    assert trajectory == original


def test_direct_records_recertify_projections_and_reject_forgery() -> None:
    trajectory = _run(7)
    arm = trajectory.arms[3]
    assert replace(arm) == arm
    assert replace(trajectory) == trajectory
    corruptions = (
        {"height_sum": arm.height_sum + 1},
        {"height_square_sum": arm.height_square_sum + 1},
        {"void_volume": arm.void_volume + 1},
        {"gap_sum": arm.gap_sum + 1},
        {"causal_counts": (arm.event_count, 0, 0, 0)},
        {"gap_histogram": ()},
        {"endpoint_equality_mask_counts": ((0,) * 8, (0,) * 8)},
    )
    for changes in corruptions:
        with pytest.raises((TypeError, ValueError)):
            replace(arm, **changes)
    for changes in (
        {"heights": list(arm.heights)},
        {"causal_counts": list(arm.causal_counts)},
        {"endpoint_equality_mask_counts": [list(row) for row in arm.endpoint_equality_mask_counts]},
        {"gap_histogram": [tuple(pair) for pair in arm.gap_histogram]},
    ):
        caller_owned = next(iter(changes.values()))
        before = repr(caller_owned)
        with pytest.raises(TypeError):
            replace(arm, **changes)
        assert repr(caller_owned) == before

    with pytest.raises((TypeError, ValueError)):
        replace(trajectory, event_count=trajectory.event_count + 1)
    with pytest.raises((TypeError, ValueError)):
        replace(trajectory, arms=trajectory.arms[::-1])
    with pytest.raises(TypeError):
        replace(trajectory, arms=list(trajectory.arms))
    partial = object.__new__(OneCellScalarTrajectory)
    with pytest.raises(TypeError):
        advance_one_cell_scalar_chunk(trajectory=partial, stop_event_ordinal=0)

    b2 = _run(7, threshold_schedule=_B2_FULL_THRESHOLDS)
    assert replace(b2) == b2
    assert replace(b2.arms[2]) == b2.arms[2]
    with pytest.raises(ValueError, match="frozen PRE threshold"):
        replace(b2.arms[2], threshold=89)
    with pytest.raises(ValueError, match="four frozen PRE schedules"):
        replace(b2, arms=b2.arms[:-1])
    with pytest.raises(ValueError, match="four frozen PRE schedules"):
        replace(b2, arms=(b2.arms[0], b2.arms[2], *b2.arms[1:2], *b2.arms[3:]))


def test_q_unsigned_128_high_low_round_trip() -> None:
    zero_q = _start().arms[0].height_square_sum
    assert ((zero_q >> 64) << 64) | (zero_q & _U64_MASK) == zero_q == 0

    n = (1 << 62) + 1
    gap = 2 * n
    high_q_arm = OneCellScalarArmAccumulator(
        boundary_law=OneCellBoundaryLaw.PERIODIC,
        threshold=5,
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
    q = high_q_arm.height_square_sum
    high, low = q >> 64, q & _U64_MASK
    assert high > 0
    assert low > 0
    assert (high << 64) | low == q
    assert q <= _U128_MAX


def test_input_is_immutable_when_a_later_arm_delegate_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    trajectory = _run(3)
    original = trajectory
    original_delegate = one_cell_boundary.transition_one_cell_periodic
    calls = 0

    def fail_on_fourth(**kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 4:
            raise RuntimeError("injected fourth-arm failure")
        return original_delegate(**kwargs)

    monkeypatch.setattr(one_cell_boundary, "transition_one_cell_periodic", fail_on_fourth)
    with pytest.raises(RuntimeError, match="fourth-arm"):
        advance_one_cell_scalar_chunk(trajectory=trajectory, stop_event_ordinal=4)
    assert calls == 4
    assert trajectory == original


def test_public_alias_rebinding_does_not_redirect_captured_authorities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = _run(9)

    def forbidden(**_: object) -> object:
        raise AssertionError("rebound public alias must not be used")

    monkeypatch.setattr(one_cell_trajectory, "select_one_cell_coupled_event", forbidden)
    monkeypatch.setattr(one_cell_trajectory, "transition_one_cell_boundary", forbidden)
    monkeypatch.setattr(one_cell_trajectory, "OneCellScalarArmAccumulator", object)
    monkeypatch.setattr(one_cell_trajectory, "OneCellScalarTrajectory", object)
    monkeypatch.setattr(one_cell_trajectory, "OneCellBoundaryLaw", object)
    assert _run(9) == expected


def test_private_authority_rebinding_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    trajectory = _run(3)
    original = trajectory
    corruptions = (
        ("_THRESHOLDS", (0, 1, 2, 5, 10, 25, 50, 99)),
        ("_B1_THRESHOLDS", (0, 5, 50, 99)),
        ("_B2_FULL_THRESHOLDS", (5, 50, 90, 95, 98, 100)),
        ("_B2_HIGH_THRESHOLDS", (90, 95, 98, 100)),
        ("_THRESHOLD_SCHEDULES", tuple(reversed(one_cell_trajectory._THRESHOLD_SCHEDULES))),
        ("_CAUSAL_ORDER", tuple(reversed(one_cell_trajectory._CAUSAL_ORDER))),
        ("_PERIODIC", OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC),
        ("_BOUNDARY_LAWS", tuple(reversed(one_cell_trajectory._BOUNDARY_LAWS))),
        ("_U64_MAX", _U64_SPACE),
        ("_BOUNDARY_LAW_TYPE", object),
        ("_CERTIFIED_SELECT_EVENT", object()),
        ("_ARM_TYPE", object),
        ("_TRAJECTORY_TYPE", object),
    )
    for name, replacement in corruptions:
        with monkeypatch.context() as scoped:
            scoped.setattr(one_cell_trajectory, name, replacement)
            with pytest.raises(AssertionError):
                start_one_cell_scalar_trajectory(
                    root_seed=0,
                    boundary_law=OneCellBoundaryLaw.PERIODIC,
                    width=3,
                )
            with pytest.raises(AssertionError):
                advance_one_cell_scalar_chunk(
                    trajectory=trajectory,
                    stop_event_ordinal=4,
                )
    assert trajectory == original


def test_hash_seed_stability() -> None:
    script = """
import json
from dataclasses import asdict
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_trajectory import start_one_cell_scalar_trajectory, advance_one_cell_scalar_chunk
t = start_one_cell_scalar_trajectory(root_seed=123456789, boundary_law=OneCellBoundaryLaw.PERIODIC, width=5)
t = advance_one_cell_scalar_chunk(trajectory=t, stop_event_ordinal=64)
def enc(x):
    if hasattr(x, 'value'):
        return x.value
    raise TypeError(type(x).__name__)
print(json.dumps(asdict(t), sort_keys=True, separators=(',', ':'), default=enc))
"""
    outputs = []
    for seed in ("0", "1", "777"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_REPO_ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_independent_oracle_call_graph_has_no_production_helpers() -> None:
    source_path = Path(__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    oracle_functions = (
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("_oracle_")
    )
    forbidden_simple_calls = {
        "derive_stream_key",
        "philox4x64_10",
        "raw_u64",
        "uniform_below",
        "select_uniform",
        "select_one_cell_coupled_event",
        "transition_one_cell_periodic",
        "transition_one_cell_boundary",
        "start_one_cell_scalar_trajectory",
        "advance_one_cell_scalar_chunk",
        "OneCellScalarArmAccumulator",
        "OneCellScalarTrajectory",
    }
    forbidden_module_roots = {
        "semantic_rng",
        "one_cell_coupling",
        "one_cell_boundary",
        "one_cell_trajectory",
    }
    for function in oracle_functions:
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if isinstance(call.func, ast.Name):
                assert call.func.id not in forbidden_simple_calls, (function.name, call.func.id)
            elif isinstance(call.func, ast.Attribute):
                root = call.func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    assert root.id not in forbidden_module_roots, (function.name, root.id, call.func.attr)


def test_no_root_exports_and_dependency_guard() -> None:
    for name in one_cell_trajectory.__all__:
        assert not hasattr(tetris_ballistic, name)
        assert not hasattr(reference_engine, name)

    source_path = _REPO_ROOT / "tetris_ballistic/engine/one_cell_trajectory.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    relative_imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level and node.module is not None
    }
    assert relative_imports <= {"one_cell_coupling", "one_cell_boundary"}
    imported_roots = {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }
    forbidden_roots = {
        "numpy",
        "numba",
        "random",
        "tetris_ballistic.tetris_ballistic",
    }
    assert imported_roots.isdisjoint(forbidden_roots)
    source = source_path.read_text(encoding="utf-8")
    assert "endpoint_selected = contact_value < arm.threshold" in source
    for forbidden in (
        ".rng import",
        ".rng_compiled import",
        ".selection import",
        ".one_cell import",
        ".accumulation import",
        ".observables import",
        ".state import",
        ".event import",
        ".binding import",
        ".models import",
        "numpy",
        "numba",
        "sticky_by_threshold",
        "arm_decisions",
    ):
        assert forbidden not in source


def test_parent_authority_digests_are_pinned() -> None:
    expected = {
        "tetris_ballistic/engine/one_cell_coupling.py": "ebf8a2ada59cb176319eab167bef6502811c6d696f93ba60d429921ed26ba6a7",
        "tetris_ballistic/engine/one_cell_boundary.py": "2bc7e184476e46bae25b7878847000664f50e1140a009c7917a802e6022089fb",
        "docs/PRE-ONE-CELL-COUPLING-VECTORS.md": "74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3",
        "docs/PRE-ONE-CELL-BOUNDARY-VECTORS.md": "d70374dc2239fc0c5f44781ef49ee9e0d9cce2ca6e16050678a0057282eee23f",
        "docs/SEMANTIC-RNG-VECTORS.md": "913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34",
        "tetris_ballistic/engine/rng.py": "19dca94ea97fae16278b198505200a5be27d80821dd54c8e454f135390888489",
    }
    for relative_path, digest in expected.items():
        assert hashlib.sha256((_REPO_ROOT / relative_path).read_bytes()).hexdigest() == digest
