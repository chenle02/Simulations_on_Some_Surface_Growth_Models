"""Numba-compiled primitives for the frozen semantic Philox contract.

This provisional PRE Slice 4 module compiles only the unsigned-integer
Philox4x64-10 bijection, lane-zero event/rejection addressing, and exact
bounded rejection map.  Stream-key derivation remains the certified scalar
host step in :mod:`tetris_ballistic.engine.rng`.

The module is explicit-submodule-only and is not connected to package roots,
legacy simulation paths, trajectories, persistence, or production execution.
It requires the optional ``hpc`` dependency set.
"""

from __future__ import annotations

import numpy as _np

try:
    from numba import njit as _njit
except ImportError as error:  # pragma: no cover - exercised by package smoke gates
    raise ImportError(
        "tetris_ballistic.engine.rng_compiled requires a compatible Numba "
        "installation; install the 'tetris_ballistic[hpc]' extra on a "
        "supported Python interpreter"
    ) from error

from .rng import SemanticDraw as _SemanticDraw

_U64_SPACE = 1 << 64
_U64_MAX_INT = _U64_SPACE - 1

_U64_ZERO = _np.uint64(0)
_U64_ONE = _np.uint64(1)
_U64_MAX = _np.uint64(_U64_MAX_INT)
_U32_MASK = _np.uint64(0xFFFFFFFF)
_U32_SHIFT = _np.uint64(32)

# Random123 Philox4x64 constants.  All compiled arithmetic is unsigned and
# wraps modulo 2**64.
_PHILOX_M0 = _np.uint64(0xD2E7470EE14C6C93)
_PHILOX_M1 = _np.uint64(0xCA5A826395121157)
_PHILOX_W0 = _np.uint64(0x9E3779B97F4A7C15)
_PHILOX_W1 = _np.uint64(0xBB67AE8584CAA73B)


def _require_plain_uint(value: object, *, maximum: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return value


def _require_u64(value: object, *, label: str) -> int:
    return _require_plain_uint(value, maximum=_U64_MAX_INT, label=label)


def _require_uniform_bound(value: object) -> int:
    if type(value) is not int:
        raise TypeError("uniform bound must be a built-in integer")
    if not 1 <= value <= _U64_SPACE:
        raise ValueError("uniform bound must lie in [1, 2**64]")
    return value


def _snapshot_words(
    words: object,
    *,
    length: int,
    label: str,
) -> tuple[int, ...]:
    if type(words) is not tuple or len(words) != length:
        raise TypeError(f"{label} must be a plain {length}-tuple")
    return tuple(_require_u64(word, label=f"{label} word {index}") for index, word in enumerate(words))


def _construct_semantic_draw(
    value: int,
    rejection_ordinal: int,
    _draw_type: type[_SemanticDraw] = _SemanticDraw,
) -> _SemanticDraw:
    """Construct with the import-time certified record authority."""

    return _draw_type(
        value=value,
        accepted_rejection_ordinal=rejection_ordinal,
    )


@_njit(cache=False, fastmath=False)
def _multiply_high_low_kernel(left, right):
    """Return the high and low words of one unsigned 64-by-64 product."""

    left_low = left & _U32_MASK
    left_high = left >> _U32_SHIFT
    right_low = right & _U32_MASK
    right_high = right >> _U32_SHIFT

    product_low_low = left_low * right_low
    product_low_high = left_low * right_high
    product_high_low = left_high * right_low
    product_high_high = left_high * right_high

    middle = (product_low_low >> _U32_SHIFT) + (product_low_high & _U32_MASK) + (product_high_low & _U32_MASK)
    low = (product_low_low & _U32_MASK) | ((middle & _U32_MASK) << _U32_SHIFT)
    high = (
        product_high_high + (product_low_high >> _U32_SHIFT) + (product_high_low >> _U32_SHIFT) + (middle >> _U32_SHIFT)
    )
    return high, low


@_njit(cache=False, fastmath=False)
def _philox4x64_10_kernel(c0, c1, c2, c3, k0, k1):
    """Apply the exact ten-round Random123 Philox4x64 bijection."""

    for round_ordinal in range(10):
        high0, low0 = _multiply_high_low_kernel(_PHILOX_M0, c0)
        high1, low1 = _multiply_high_low_kernel(_PHILOX_M1, c2)
        c0, c1, c2, c3 = (
            high1 ^ c1 ^ k0,
            low1,
            high0 ^ c3 ^ k1,
            low0,
        )
        if round_ordinal != 9:
            k0 += _PHILOX_W0
            k1 += _PHILOX_W1

    return c0, c1, c2, c3


@_njit(cache=False, fastmath=False)
def _raw_u64_kernel(k0, k1, event_ordinal, rejection_ordinal):
    """Return lane zero at ``(event, rejection, 0, 0)``."""

    return _philox4x64_10_kernel(
        event_ordinal,
        rejection_ordinal,
        _U64_ZERO,
        _U64_ZERO,
        k0,
        k1,
    )[0]


@_njit(cache=False, fastmath=False)
def _prepare_bounded_mapping_kernel(n_minus_one):
    """Prepare ``q`` and ``T`` from the private unsigned ``n - 1`` word.

    A threshold word of zero denotes the mathematical threshold ``2**64``.
    The final unsigned flag distinguishes the otherwise unrepresentable
    quotient for the unit bound, whose mapped value is always zero.
    """

    if n_minus_one == _U64_ZERO:
        return _U64_ONE, _U64_ZERO, _U64_ONE
    if n_minus_one == _U64_MAX:
        return _U64_ONE, _U64_ZERO, _U64_ZERO

    bound = n_minus_one + _U64_ONE
    quotient = _U64_MAX // bound
    if _U64_MAX % bound == bound - _U64_ONE:
        quotient += _U64_ONE
    threshold = quotient * bound
    return quotient, threshold, _U64_ZERO


@_njit(cache=False, fastmath=False)
def _map_bounded_word_kernel(word, quotient, threshold, unit_bound):
    """Map one prepared candidate, returning ``(accepted, value)``."""

    if threshold != _U64_ZERO and word >= threshold:
        return False, _U64_ZERO
    if unit_bound != _U64_ZERO:
        return True, _U64_ZERO
    return True, word // quotient


@_njit(cache=False, fastmath=False)
def _uniform_below_kernel(k0, k1, event_ordinal, n_minus_one, initial_rejection):
    """Run the counter-addressed rejection loop entirely in nopython code."""

    quotient, threshold, unit_bound = _prepare_bounded_mapping_kernel(n_minus_one)
    rejection_ordinal = initial_rejection

    while True:
        word = _raw_u64_kernel(k0, k1, event_ordinal, rejection_ordinal)
        accepted, value = _map_bounded_word_kernel(
            word,
            quotient,
            threshold,
            unit_bound,
        )
        if accepted:
            return value, rejection_ordinal, False
        if rejection_ordinal == _U64_MAX:
            return _U64_ZERO, rejection_ordinal, True
        rejection_ordinal += _U64_ONE


def philox4x64_10(
    *,
    counter: tuple[int, int, int, int],
    key: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Apply compiled Philox4x64-10 to exact unsigned word tuples."""

    counter_words = _snapshot_words(counter, length=4, label="counter")
    key_words = _snapshot_words(key, length=2, label="key")
    result = _philox4x64_10_kernel(
        _np.uint64(counter_words[0]),
        _np.uint64(counter_words[1]),
        _np.uint64(counter_words[2]),
        _np.uint64(counter_words[3]),
        _np.uint64(key_words[0]),
        _np.uint64(key_words[1]),
    )
    validated = _snapshot_words(result, length=4, label="compiled Philox result")
    return validated[0], validated[1], validated[2], validated[3]


def raw_u64_from_key(
    *,
    key: tuple[int, int],
    event_ordinal: int,
    rejection_ordinal: int = 0,
) -> int:
    """Return the compiled lane-zero word for a pre-derived stream key."""

    key_words = _snapshot_words(key, length=2, label="key")
    event = _require_u64(event_ordinal, label="event ordinal")
    rejection = _require_u64(rejection_ordinal, label="rejection ordinal")
    result = _raw_u64_kernel(
        _np.uint64(key_words[0]),
        _np.uint64(key_words[1]),
        _np.uint64(event),
        _np.uint64(rejection),
    )
    return _require_u64(result, label="compiled raw word")


def uniform_below_from_key(
    *,
    key: tuple[int, int],
    event_ordinal: int,
    n: int,
) -> _SemanticDraw:
    """Select an exact compiled uniform integer in ``range(n)``."""

    key_words = _snapshot_words(key, length=2, label="key")
    event = _require_u64(event_ordinal, label="event ordinal")
    bound = _require_uniform_bound(n)

    result = _uniform_below_kernel(
        _np.uint64(key_words[0]),
        _np.uint64(key_words[1]),
        _np.uint64(event),
        _np.uint64(bound - 1),
        _U64_ZERO,
    )
    if type(result) is not tuple or len(result) != 3:
        raise TypeError("compiled bounded result must be a plain 3-tuple")
    value = _require_u64(result[0], label="compiled bounded value")
    rejection = _require_u64(result[1], label="compiled accepted rejection ordinal")
    exhausted = result[2]
    if type(exhausted) is not bool:
        raise TypeError("compiled exhaustion flag must be a built-in Boolean")
    if exhausted:
        raise OverflowError("rejection ordinal exhausted without an accepted word")
    if value >= bound:
        raise ValueError("compiled bounded value must lie in range(n)")
    if bound & (bound - 1) == 0 and rejection != 0:
        raise ValueError("a power-of-two bound must accept rejection ordinal zero")
    return _construct_semantic_draw(value, rejection)


__all__ = [
    "philox4x64_10",
    "raw_u64_from_key",
    "uniform_below_from_key",
]
