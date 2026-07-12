"""Numba-JIT kernel for the 1x1-only fast path (Phase 4b).

Specialized to the case where the active piece is the 1x1 sticky / non-sticky
mix (piece_19 only, i.e., the `Piece-19` slot is the only non-zero in
``config_data``). This is exactly the exp13 configuration.

For general multi-piece configurations the kernel is bypassed and the
Python dispatch path runs as before.

Bit-equality contract: the kernel takes a pre-generated array of random
positions (``positions[i]`` = column for step i+1) so the RNG sequence
matches the legacy `random.randint(0, width-1)` exactly. The orchestrator
must call ``[random.randint(0, width - 1) for _ in range(steps)]`` before
invoking the kernel, with the same RNG state.

The numba ``@njit`` kernel returns updated arrays; the orchestrator
deserializes them into the standard ``Tetris_Ballistic`` attributes.
"""

from __future__ import annotations

import numpy as np
from numba import njit


@njit(cache=True, fastmath=False)
def simulate_1x1_kernel(width: int, height: int, steps: int,
                        positions: np.ndarray, sticky_flags: np.ndarray,
                        substrate: np.ndarray, heights: np.ndarray):
    """One full 1x1-piece simulation loop, JIT-compiled.

    Parameters
    ----------
    width, height, steps : int
    positions : 1-D int64 array of length ``steps``
        Pre-generated column indices, one per step.
    sticky_flags : 1-D bool array of length ``steps``
        Pre-generated stickiness flag, one per step.
    substrate : 2-D int64 array, shape (height, width), pre-allocated
        Will be mutated in-place (cell writes).
    heights : 1-D int64 array, shape (width,), pre-initialized
        Will be mutated in-place.

    Returns
    -------
    fluctuation, avg_height : float64 arrays of length ``steps``
    final_steps : int (number of steps actually executed; < steps if top reached)
    """
    fluctuation = np.empty(steps, dtype=np.float64)
    avg_height = np.empty(steps, dtype=np.float64)
    final_steps = steps

    for i in range(steps):
        position = positions[i]
        sticky = sticky_flags[i]

        # Compute landing row, matching Update_1x1 exactly:
        # landing_row_outleft  = surface_row(position - 1) + 1  if (pos > 1 AND sticky) else height
        # landing_row_pivot    = surface_row(position)
        # landing_row_outright = surface_row(position + 1) + 1  if (pos < W-1 AND sticky) else height
        # landing_row = min of the three
        #
        # _surface_row(c) returns:
        #   height                if c<0 or c>=W or heights[c] == height-1 (empty column)
        #   heights[c] + 1         otherwise

        if position > 1 and sticky:
            c = position - 1
            if c < 0 or heights[c] == height - 1:
                lr_outleft = height
            else:
                lr_outleft = heights[c] + 1 + 1
        else:
            lr_outleft = height

        c = position
        if heights[c] == height - 1:
            lr_pivot = height
        else:
            lr_pivot = heights[c] + 1

        if position < width - 1 and sticky:
            c = position + 1
            if c >= width or heights[c] == height - 1:
                lr_outright = height
            else:
                lr_outright = heights[c] + 1 + 1
        else:
            lr_outright = height

        landing_row = lr_outleft
        if lr_pivot < landing_row:
            landing_row = lr_pivot
        if lr_outright < landing_row:
            landing_row = lr_outright

        if landing_row < 2:
            final_steps = i
            break

        step_idx = i + 1
        row_idx = landing_row - 1
        substrate[row_idx, position] = step_idx
        # Update heights[position] only: this is the only column touched by 1x1.
        # New heights[col] = row index just above topmost occupied
        #                  = (landing_row - 1) - 1 = landing_row - 2
        # But only if this raised the height.
        new_h = landing_row - 2
        if new_h < heights[position]:
            heights[position] = new_h

        # Compute mean + std of heights. heights is row-index from the TOP,
        # so AvergeHeight is the PHYSICAL mean height = height - mean(heights)
        # (must match tetris_ballistic.py:1807; see FINDING-kernel-height-
        # inversion.md). Population std (divisor W); std is flip-invariant.
        s = 0.0
        for k in range(width):
            s += heights[k]
        mean = s / width
        s2 = 0.0
        for k in range(width):
            d = heights[k] - mean
            s2 += d * d
        avg_height[i] = height - mean
        fluctuation[i] = (s2 / width) ** 0.5

    return fluctuation, avg_height, final_steps


def is_1x1_only(config_data: dict) -> bool:
    """Detect whether this configuration uses ONLY piece 19 (1x1).

    The kernel only handles this case. For mixed configurations,
    the orchestrator falls back to the Python dispatch path.
    """
    for i in range(19):
        weights = config_data.get(f"Piece-{i}", [0, 0])
        if weights[0] != 0 or weights[1] != 0:
            return False
    piece19 = config_data.get("Piece-19", [0, 0])
    return piece19[0] > 0 or piece19[1] > 0
