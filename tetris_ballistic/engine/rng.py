"""Exact counter-addressed RNG primitives for the slow reference engine.

This provisional S2.2 module implements the frozen
``semantic-philox4x64-10-v1`` transition-RNG contract.  It is deliberately
stateless and is not routed through the package root, configuration objects,
legacy simulation paths, trajectories, or production execution.

The generator is a scientific reproducibility primitive, not a cryptographic
random-number generator.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import gcd

SEMANTIC_RNG_CONTRACT_ID = "semantic-philox4x64-10-v1"

_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"
_U64_MODULUS = 1 << 64
_U64_MAX = _U64_MODULUS - 1
_U128_MAX = (1 << 128) - 1
_U32_MAX = (1 << 32) - 1

# Random123 Philox4x64 constants.  Arithmetic on key words is modulo 2**64.
_PHILOX_M0 = 0xD2E7470EE14C6C93
_PHILOX_M1 = 0xCA5A826395121157
_PHILOX_W0 = 0x9E3779B97F4A7C15
_PHILOX_W1 = 0xBB67AE8584CAA73B


def _require_plain_uint(value: object, *, maximum: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return value


def _require_u64(value: object, *, label: str) -> int:
    return _require_plain_uint(value, maximum=_U64_MAX, label=label)


def _length_prefixed_utf8(value: object, *, label: str) -> bytes:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    if not value:
        raise ValueError(f"{label} must be nonempty")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must be valid UTF-8 text") from error
    if len(encoded) > _U32_MAX:
        raise ValueError(f"{label} UTF-8 encoding is too long")
    return len(encoded).to_bytes(4, "big") + encoded


@dataclass(frozen=True, slots=True)
class SemanticDraw:
    """A selected value and the zero-based rejection ordinal it accepted."""

    value: int
    accepted_rejection_ordinal: int

    def __post_init__(self) -> None:
        _require_u64(self.value, label="draw value")
        _require_u64(
            self.accepted_rejection_ordinal,
            label="accepted rejection ordinal",
        )


def derive_stream_key(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
) -> tuple[int, int]:
    """Derive two big-endian Philox key words from the frozen domain bytes.

    ``root_seed`` is encoded as exactly 16 unsigned big-endian bytes.  The
    nonempty group and stream names are strict UTF-8 byte strings prefixed by
    four-byte big-endian lengths. Code points are encoded exactly without
    implicit Unicode normalization.
    """

    root = _require_plain_uint(root_seed, maximum=_U128_MAX, label="root seed")
    preimage = b"".join(
        (
            _DOMAIN,
            root.to_bytes(16, "big"),
            _length_prefixed_utf8(coupling_group_id, label="coupling group ID"),
            _length_prefixed_utf8(stream_name, label="stream name"),
        )
    )
    digest_prefix = sha256(preimage).digest()[:16]
    return (
        int.from_bytes(digest_prefix[:8], "big"),
        int.from_bytes(digest_prefix[8:], "big"),
    )


def _snapshot_word_tuple(
    words: object,
    *,
    length: int,
    label: str,
) -> tuple[int, ...]:
    if type(words) is not tuple or len(words) != length:
        raise TypeError(f"{label} must be a plain {length}-tuple")
    return tuple(_require_u64(word, label=f"{label} word {index}") for index, word in enumerate(words))


def _multiply_high_low(left: int, right: int) -> tuple[int, int]:
    product = left * right
    return product >> 64, product & _U64_MAX


def philox4x64_10(
    counter: tuple[int, int, int, int],
    key: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Apply the exact ten-round Random123 Philox4x64 bijection."""

    c0, c1, c2, c3 = _snapshot_word_tuple(counter, length=4, label="counter")
    k0, k1 = _snapshot_word_tuple(key, length=2, label="key")

    for round_index in range(10):
        hi0, lo0 = _multiply_high_low(_PHILOX_M0, c0)
        hi1, lo1 = _multiply_high_low(_PHILOX_M1, c2)
        c0, c1, c2, c3 = (
            hi1 ^ c1 ^ k0,
            lo1,
            hi0 ^ c3 ^ k1,
            lo0,
        )
        if round_index != 9:
            k0 = (k0 + _PHILOX_W0) & _U64_MAX
            k1 = (k1 + _PHILOX_W1) & _U64_MAX

    return c0, c1, c2, c3


def raw_u64(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    rejection_ordinal: int = 0,
) -> int:
    """Return lane zero at counter ``(event, rejection, 0, 0)``."""

    event = _require_u64(event_ordinal, label="event ordinal")
    rejection = _require_u64(rejection_ordinal, label="rejection ordinal")
    key = derive_stream_key(root_seed, coupling_group_id, stream_name)
    return philox4x64_10((event, rejection, 0, 0), key)[0]


def uniform_below(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    n: int,
) -> SemanticDraw:
    """Select an exact uniform integer in ``range(n)`` by rejection mapping."""

    if type(n) is not int:
        raise TypeError("uniform bound must be a built-in integer")
    if not 1 <= n <= _U64_MODULUS:
        raise ValueError("uniform bound must lie in [1, 2**64]")

    # Validate every identity/counter input even when a patched test oracle is
    # used for ``raw_u64`` or the bound makes the selected value degenerate.
    _require_plain_uint(root_seed, maximum=_U128_MAX, label="root seed")
    _length_prefixed_utf8(coupling_group_id, label="coupling group ID")
    _length_prefixed_utf8(stream_name, label="stream name")
    event = _require_u64(event_ordinal, label="event ordinal")

    quotient = _U64_MODULUS // n
    threshold = quotient * n
    rejection = 0
    while True:
        word = _require_u64(
            raw_u64(
                root_seed=root_seed,
                coupling_group_id=coupling_group_id,
                stream_name=stream_name,
                event_ordinal=event,
                rejection_ordinal=rejection,
            ),
            label="raw word",
        )
        if word < threshold:
            return SemanticDraw(
                value=word // quotient,
                accepted_rejection_ordinal=rejection,
            )
        if rejection == _U64_MAX:
            raise OverflowError("rejection ordinal exhausted without an accepted word")
        rejection += 1


def _snapshot_categorical_counts(counts: object) -> tuple[int, ...]:
    if type(counts) not in (list, tuple):
        raise TypeError("categorical counts must be a plain list or tuple")
    if not counts:
        raise ValueError("categorical counts must not be empty")

    snapshot: list[int] = []
    total = 0
    common_divisor = 0
    for index, count in enumerate(counts):
        if type(count) is not int:
            raise TypeError(f"categorical count {index} must be a built-in integer")
        if count < 0:
            raise ValueError(f"categorical count {index} must be nonnegative")
        total += count
        if total > _U64_MODULUS:
            raise ValueError("categorical count sum must not exceed 2**64")
        if count:
            common_divisor = gcd(common_divisor, count)
        snapshot.append(count)

    if total == 0:
        raise ValueError("categorical counts must contain a positive count")
    if common_divisor != 1:
        raise ValueError("positive categorical counts must have greatest common divisor one")
    return tuple(snapshot)


def categorical_index(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    counts: tuple[int, ...] | list[int],
) -> SemanticDraw:
    """Select an index from an ordered canonical integer-count vector."""

    canonical_counts = _snapshot_categorical_counts(counts)
    selected = uniform_below(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        stream_name=stream_name,
        event_ordinal=event_ordinal,
        n=sum(canonical_counts),
    )

    cumulative = 0
    for index, count in enumerate(canonical_counts):
        cumulative += count
        if selected.value < cumulative:
            return SemanticDraw(
                value=index,
                accepted_rejection_ordinal=selected.accepted_rejection_ordinal,
            )

    raise AssertionError("validated categorical interval search did not terminate")


__all__ = [
    "SEMANTIC_RNG_CONTRACT_ID",
    "SemanticDraw",
    "categorical_index",
    "derive_stream_key",
    "philox4x64_10",
    "raw_u64",
    "uniform_below",
]
