"""Independent certification tests for the S2.2 semantic RNG oracle.

The oracle below is intentionally written from the frozen S1a prose and does
not import constants, validation helpers, or implementation details from the
production module.  Its Philox core is first certified against the three
Philox4x64-10 known-answer tests published by Random123:

https://github.com/DEShawResearch/random123/blob/9545ff6413f258be2f04c1d319d99aaef7521150/tests/kat_vectors
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.rng as semantic_rng
from tetris_ballistic.engine.rng import (
    SEMANTIC_RNG_CONTRACT_ID,
    SemanticDraw,
    categorical_index,
    derive_stream_key,
    philox4x64_10,
    raw_u64,
    uniform_below,
)

_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1
_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"

# Random123 Philox4x64 constants.  These are deliberately repeated here rather
# than imported from the implementation under test.
_PHILOX_M0 = 0xD2E7470EE14C6C93
_PHILOX_M1 = 0xCA5A826395121157
_PHILOX_W0 = 0x9E3779B97F4A7C15
_PHILOX_W1 = 0xBB67AE8584CAA73B


def _oracle_key_preimage(root_seed: int, coupling_group_id: str, stream_name: str) -> bytes:
    group_bytes = coupling_group_id.encode("utf-8")
    stream_bytes = stream_name.encode("utf-8")
    return b"".join(
        (
            _DOMAIN,
            root_seed.to_bytes(16, "big"),
            len(group_bytes).to_bytes(4, "big"),
            group_bytes,
            len(stream_bytes).to_bytes(4, "big"),
            stream_bytes,
        )
    )


def _oracle_derive_stream_key(root_seed: int, coupling_group_id: str, stream_name: str) -> tuple[int, int]:
    prefix = sha256(_oracle_key_preimage(root_seed, coupling_group_id, stream_name)).digest()[:16]
    return (int.from_bytes(prefix[:8], "big"), int.from_bytes(prefix[8:], "big"))


def _oracle_philox4x64_10(counter: tuple[int, int, int, int], key: tuple[int, int]) -> tuple[int, int, int, int]:
    c0, c1, c2, c3 = counter
    k0, k1 = key
    for round_ordinal in range(10):
        product0 = _PHILOX_M0 * c0
        product1 = _PHILOX_M1 * c2
        c0, c1, c2, c3 = (
            ((product1 >> 64) ^ c1 ^ k0) & _U64_MAX,
            product1 & _U64_MAX,
            ((product0 >> 64) ^ c3 ^ k1) & _U64_MAX,
            product0 & _U64_MAX,
        )
        if round_ordinal != 9:
            k0 = (k0 + _PHILOX_W0) & _U64_MAX
            k1 = (k1 + _PHILOX_W1) & _U64_MAX
    return (c0, c1, c2, c3)


def _oracle_raw_u64(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    rejection_ordinal: int = 0,
) -> int:
    key = _oracle_derive_stream_key(root_seed, coupling_group_id, stream_name)
    return _oracle_philox4x64_10((event_ordinal, rejection_ordinal, 0, 0), key)[0]


def _oracle_uniform_below(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    n: int,
) -> tuple[int, int]:
    quotient = _U64_SPACE // n
    threshold = quotient * n
    rejection_ordinal = 0
    while rejection_ordinal < _U64_SPACE:
        candidate = _oracle_raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )
        if candidate < threshold:
            return (candidate // quotient, rejection_ordinal)
        rejection_ordinal += 1
    raise OverflowError("independent oracle exhausted the unsigned 64-bit rejection counter")


def _oracle_categorical_index(
    *,
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    counts: tuple[int, ...] | list[int],
) -> tuple[int, int]:
    uniform_value, rejection_ordinal = _oracle_uniform_below(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        stream_name=stream_name,
        event_ordinal=event_ordinal,
        n=sum(counts),
    )
    cumulative = 0
    for index, count in enumerate(counts):
        cumulative += count
        if uniform_value < cumulative:
            return (index, rejection_ordinal)
    raise AssertionError("a valid categorical vector must contain its mapped uniform value")


_RANDOM123_PHILOX4X64_10_KATS = (
    (
        (0, 0, 0, 0),
        (0, 0),
        (0x16554D9ECA36314C, 0xDB20FE9D672D0FDC, 0xD7E772CEE186176B, 0x7E68B68AEC7BA23B),
    ),
    (
        (_U64_MAX, _U64_MAX, _U64_MAX, _U64_MAX),
        (_U64_MAX, _U64_MAX),
        (0x87B092C3013FE90B, 0x438C3C67BE8D0224, 0x9CC7D7C69CD777B6, 0xA09CAEBF594F0BA0),
    ),
    (
        (0x243F6A8885A308D3, 0x13198A2E03707344, 0xA4093822299F31D0, 0x082EFA98EC4E6C89),
        (0x452821E638D01377, 0xBE5466CF34E90C6C),
        (0xA528F45403E61D95, 0x38C72DBD566E9788, 0xA5A1610E72FD18B5, 0x57BD43B5E52B7FE6),
    ),
)


@pytest.mark.parametrize(("counter", "key", "expected"), _RANDOM123_PHILOX4X64_10_KATS)
def test_philox_core_matches_all_three_official_random123_known_answers(
    counter: tuple[int, int, int, int],
    key: tuple[int, int],
    expected: tuple[int, int, int, int],
) -> None:
    assert _oracle_philox4x64_10(counter, key) == expected
    assert philox4x64_10(counter, key) == expected


def test_contract_identity_is_exact_and_not_an_alias_for_legacy_rng() -> None:
    assert SEMANTIC_RNG_CONTRACT_ID == "semantic-philox4x64-10-v1"
    assert SEMANTIC_RNG_CONTRACT_ID != "legacy-dual-stream-v1"


def test_provisional_rng_symbols_are_not_exported_from_package_or_engine_roots() -> None:
    for root in (tetris_ballistic, reference_engine):
        assert not hasattr(root, "SEMANTIC_RNG_CONTRACT_ID")
        assert not hasattr(root, "SemanticDraw")
        assert not hasattr(root, "derive_stream_key")
        assert not hasattr(root, "philox4x64_10")
        assert not hasattr(root, "raw_u64")
        assert not hasattr(root, "uniform_below")
        assert not hasattr(root, "categorical_index")


_KEY_AND_RAW_VECTORS = (
    (
        0,
        "root-superblock-000",
        "family",
        0,
        (0x19A83E984B4A5059, 0xEBC32BDA16F60722),
        0x75AB473CEF3D469F,
    ),
    (
        _U128_MAX,
        "α/β",
        "接触",
        _U64_MAX,
        (0x3718D77CA93BB0CE, 0x04128E4BC36A2115),
        0xB2F4AB39B39341AF,
    ),
    (
        0x00112233445566778899AABBCCDDEEFF,
        "paired widths L=32,64",
        "contact",
        0x0123456789ABCDEF,
        (0xD0533A5430FCED2F, 0x55D89E426DA3D97A),
        0x5A1C3C9623F36B81,
    ),
)


@pytest.mark.parametrize(
    ("root_seed", "coupling_group_id", "stream_name", "event_ordinal", "expected_key", "expected_raw"),
    _KEY_AND_RAW_VECTORS,
)
def test_key_derivation_and_end_to_end_raw_vectors_are_fixed(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    expected_key: tuple[int, int],
    expected_raw: int,
) -> None:
    assert _oracle_derive_stream_key(root_seed, coupling_group_id, stream_name) == expected_key
    assert derive_stream_key(root_seed, coupling_group_id, stream_name) == expected_key
    assert (
        _oracle_raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
        )
        == expected_raw
    )
    assert (
        raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
        )
        == expected_raw
    )


_DOCUMENTED_PROJECT_RAW_VECTORS = (
    (
        0,
        "paired-main",
        "family",
        0,
        0,
        (0x1682C41740E367DC, 0xD803DC8CB13639CA),
        (0x9FC97B3E13CEE41B, 0xEAD120CBCC65480E, 0xEEDD7C7D8401E708, 0xD2E3C98CFA1E44FB),
    ),
    (
        0x0123456789ABCDEFFEDCBA9876543210,
        "c0e-pure-i",
        "launch",
        42,
        0,
        (0x9E291B64FE60DA0C, 0x857F38FC86CF72E4),
        (0xACD7B7CD13C14731, 0x0AC0CED1323A53D8, 0x607F1CCEE599EF39, 0xCA64C369062051DA),
    ),
    (
        _U128_MAX,
        "independent-arm",
        "contact",
        _U64_MAX,
        _U64_MAX,
        (0xEC843C817F1FDDBD, 0x4C47480A694A88D9),
        (0x8691CE71F2CF45B4, 0xBD6694BE8520464B, 0xAEC41C4237190877, 0xBBEBCB4623A49998),
    ),
    (
        0x80000000000000000000000000000001,
        "paired-α",
        "tie",
        1 << 63,
        7,
        (0x2C2EB2CD1913125E, 0xA8B16CDEFD2E3A6E),
        (0xBE68C64B42393906, 0x4DC66ACCA051A17B, 0xB8913D53897E4CFA, 0x8A0E11C9757843E4),
    ),
)


@pytest.mark.parametrize(
    (
        "root_seed",
        "coupling_group_id",
        "stream_name",
        "event_ordinal",
        "rejection_ordinal",
        "expected_key",
        "expected_output",
    ),
    _DOCUMENTED_PROJECT_RAW_VECTORS,
)
def test_every_documented_project_key_and_full_philox_vector_is_normative(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    rejection_ordinal: int,
    expected_key: tuple[int, int],
    expected_output: tuple[int, int, int, int],
) -> None:
    key = derive_stream_key(root_seed, coupling_group_id, stream_name)
    assert key == expected_key
    assert philox4x64_10((event_ordinal, rejection_ordinal, 0, 0), key) == expected_output
    assert (
        raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )
        == expected_output[0]
    )


def test_key_preimages_freeze_domain_root_and_name_byte_order() -> None:
    assert _oracle_key_preimage(0, "root-superblock-000", "family").hex() == (
        "7465747269732d6b707a2f73656d616e7469632d7068696c6f78347836342d31302d763100"
        "0000000000000000000000000000000000000013726f6f742d7375706572626c6f636b2d303030"
        "0000000666616d696c79"
    )
    assert _oracle_key_preimage(_U128_MAX, "α/β", "接触").hex() == (
        "7465747269732d6b707a2f73656d616e7469632d7068696c6f78347836342d31302d763100"
        "ffffffffffffffffffffffffffffffff00000005ceb12fceb200000006e68ea5e8a7a6"
    )


_BASE_ADDRESS = {
    "root_seed": 0,
    "coupling_group_id": "root-superblock-000",
    "stream_name": "family",
    "event_ordinal": 0,
}


@pytest.mark.parametrize(
    ("n", "expected_value"),
    (
        (1, 0),
        (2, 0),
        (3, 1),
        (257, 118),
        ((1 << 63) + 1, 0x75AB473CEF3D469F),
        (_U64_MAX, 0x75AB473CEF3D469F),
        (_U64_SPACE, 0x75AB473CEF3D469F),
    ),
)
def test_uniform_below_fixed_boundary_vectors(n: int, expected_value: int) -> None:
    assert _oracle_uniform_below(**_BASE_ADDRESS, n=n) == (expected_value, 0)
    draw = uniform_below(**_BASE_ADDRESS, n=n)
    assert type(draw) is SemanticDraw
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, 0)


_DOCUMENTED_BOUNDED_VECTORS = (
    (0, "paired-main", "family", 0, 5, 3, 0),
    (0x0123456789ABCDEFFEDCBA9876543210, "c0e-pure-i", "launch", 42, 17, 11, 0),
    (0, "paired-main", "contact", 0, 4, 3, 0),
    (_U128_MAX, "independent-arm", "contact", _U64_MAX, _U64_SPACE, 10231637573218554332, 0),
    (
        0x0123456789ABCDEFFEDCBA9876543210,
        "rejection-test",
        "launch",
        0,
        (1 << 63) + 1,
        7255411166493364322,
        1,
    ),
)


@pytest.mark.parametrize(
    (
        "root_seed",
        "coupling_group_id",
        "stream_name",
        "event_ordinal",
        "n",
        "expected_value",
        "expected_rejection_ordinal",
    ),
    _DOCUMENTED_BOUNDED_VECTORS,
)
def test_every_documented_bounded_vector_is_normative(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    n: int,
    expected_value: int,
    expected_rejection_ordinal: int,
) -> None:
    draw = uniform_below(
        root_seed=root_seed,
        coupling_group_id=coupling_group_id,
        stream_name=stream_name,
        event_ordinal=event_ordinal,
        n=n,
    )
    assert (draw.value, draw.accepted_rejection_ordinal) == (
        expected_value,
        expected_rejection_ordinal,
    )


def test_documented_rejection_vector_pins_both_candidate_words() -> None:
    address = {
        "root_seed": 0x0123456789ABCDEFFEDCBA9876543210,
        "coupling_group_id": "rejection-test",
        "stream_name": "launch",
        "event_ordinal": 0,
    }
    assert raw_u64(**address, rejection_ordinal=0) == 0xE2160DF4A6D93AD1
    assert raw_u64(**address, rejection_ordinal=1) == 0x64B06603DE3D5062


def test_uniform_below_uses_counter_addressed_rejections_without_shifting_events() -> None:
    address = {
        "root_seed": 0,
        "coupling_group_id": "rejection-audit",
        "stream_name": "contact",
        "event_ordinal": 6,
    }
    expected_words = (
        0xD067A4B6D387C47B,
        0xC8E66D786B591323,
        0xA4AA97456A5CD3E2,
        0xE0E748FBCBC33456,
        0xA3FBB0E492EAAFCB,
        0x25443A3D1347F4FE,
    )
    for rejection_ordinal, expected_word in enumerate(expected_words):
        assert _oracle_raw_u64(**address, rejection_ordinal=rejection_ordinal) == expected_word
        assert raw_u64(**address, rejection_ordinal=rejection_ordinal) == expected_word

    n = (1 << 63) + 1
    assert _oracle_uniform_below(**address, n=n) == (expected_words[-1], 5)
    next_event_before = raw_u64(**{**address, "event_ordinal": 7})
    draw = uniform_below(**address, n=n)
    next_event_after = raw_u64(**{**address, "event_ordinal": 7})
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_words[-1], 5)
    assert next_event_before == next_event_after == _oracle_raw_u64(**{**address, "event_ordinal": 7})


@pytest.mark.parametrize(
    ("counts", "expected_index"),
    (
        ((0, 1, 0), 1),
        ([1, 1, 1], 1),
        ((0, 2, 0, 3), 3),
        ((1, 0, _U64_MAX), 2),
        ((0, 118, 0, 139), 3),
    ),
)
def test_categorical_fixed_vectors_preserve_zero_slots_and_half_open_boundaries(
    counts: tuple[int, ...] | list[int], expected_index: int
) -> None:
    assert _oracle_categorical_index(**_BASE_ADDRESS, counts=counts) == (expected_index, 0)
    draw = categorical_index(**_BASE_ADDRESS, counts=counts)
    assert type(draw) is SemanticDraw
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_index, 0)


_DOCUMENTED_CATEGORICAL_VECTORS = (
    (0, "paired-main", "family", 0, (1, 1, 1, 1, 1), 3, 3),
    (0, "paired-main", "contact", 0, (1, 3), 3, 1),
    (0, "paired-main", "contact", 0, (0, 3, 1, 0), 3, 2),
    (0, "paired-main", "orientation", 0, (1, 1, 1, 1, 1, 1, 1, 1), 7, 7),
    (1, "degenerate", "contact", 9, (1,), 0, 0),
)


@pytest.mark.parametrize(
    (
        "root_seed",
        "coupling_group_id",
        "stream_name",
        "event_ordinal",
        "counts",
        "expected_uniform_value",
        "expected_index",
    ),
    _DOCUMENTED_CATEGORICAL_VECTORS,
)
def test_every_documented_categorical_vector_is_normative(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    counts: tuple[int, ...],
    expected_uniform_value: int,
    expected_index: int,
) -> None:
    address = {
        "root_seed": root_seed,
        "coupling_group_id": coupling_group_id,
        "stream_name": stream_name,
        "event_ordinal": event_ordinal,
    }
    uniform = uniform_below(**address, n=sum(counts))
    categorical = categorical_index(**address, counts=counts)
    assert (uniform.value, uniform.accepted_rejection_ordinal) == (expected_uniform_value, 0)
    assert (categorical.value, categorical.accepted_rejection_ordinal) == (expected_index, 0)


def test_categorical_reports_rejections_from_its_logical_variate() -> None:
    address = {
        "root_seed": 0,
        "coupling_group_id": "rejection-audit",
        "stream_name": "contact",
        "event_ordinal": 6,
    }
    counts = (1 << 63, 1)
    assert _oracle_categorical_index(**address, counts=counts) == (0, 5)
    draw = categorical_index(**address, counts=counts)
    assert (draw.value, draw.accepted_rejection_ordinal) == (0, 5)


def test_semantic_draw_is_an_immutable_value() -> None:
    draw = SemanticDraw(7, 3)
    assert draw.value == 7
    assert draw.accepted_rejection_ordinal == 3
    with pytest.raises((FrozenInstanceError, AttributeError)):
        draw.value = 8  # type: ignore[misc]


@pytest.mark.parametrize(
    ("value", "accepted_rejection_ordinal"),
    ((-1, 0), (1 << 64, 0), (True, 0), (0, -1), (0, 1 << 64), (0, False)),
)
def test_semantic_draw_rejects_noncanonical_words(value: object, accepted_rejection_ordinal: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        SemanticDraw(value, accepted_rejection_ordinal)  # type: ignore[arg-type]


def test_length_prefixes_separate_names_and_every_address_dimension() -> None:
    addresses = (
        (0, "ab", "c", 0, 0),
        (0, "a", "bc", 0, 0),
        (1, "ab", "c", 0, 0),
        (0, "ab", "c", 1, 0),
        (0, "ab", "c", 0, 1),
    )
    production_words = {
        raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )
        for root_seed, coupling_group_id, stream_name, event_ordinal, rejection_ordinal in addresses
    }
    oracle_words = {
        _oracle_raw_u64(
            root_seed=root_seed,
            coupling_group_id=coupling_group_id,
            stream_name=stream_name,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )
        for root_seed, coupling_group_id, stream_name, event_ordinal, rejection_ordinal in addresses
    }
    assert production_words == oracle_words
    assert len(production_words) == len(addresses)


@pytest.mark.parametrize("root_seed", (-1, 1 << 128, True, 1.0))
def test_key_derivation_rejects_noncanonical_root_seeds(root_seed: object) -> None:
    with pytest.raises((TypeError, ValueError, OverflowError)):
        derive_stream_key(root_seed, "group", "stream")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("coupling_group_id", "stream_name"),
    ((1, "stream"), ("group", 1), (b"group", "stream"), ("group", b"stream")),
)
def test_key_derivation_rejects_non_string_names(coupling_group_id: object, stream_name: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        derive_stream_key(0, coupling_group_id, stream_name)  # type: ignore[arg-type]


@pytest.mark.parametrize(("coupling_group_id", "stream_name"), (("", "stream"), ("group", "")))
def test_key_derivation_rejects_empty_names(coupling_group_id: str, stream_name: str) -> None:
    with pytest.raises(ValueError):
        derive_stream_key(0, coupling_group_id, stream_name)


@pytest.mark.parametrize(("coupling_group_id", "stream_name"), (("\ud800", "stream"), ("group", "\udfff")))
def test_key_derivation_rejects_lone_surrogates(coupling_group_id: str, stream_name: str) -> None:
    with pytest.raises((UnicodeEncodeError, ValueError)):
        derive_stream_key(0, coupling_group_id, stream_name)


def test_key_derivation_preserves_exact_unicode_without_normalization() -> None:
    composed = derive_stream_key(0, "paired-main", "caf\N{LATIN SMALL LETTER E WITH ACUTE}")
    decomposed = derive_stream_key(0, "paired-main", "cafe\N{COMBINING ACUTE ACCENT}")
    assert composed != decomposed


def test_key_derivation_rejects_a_name_exceeding_its_u32_length_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic_rng, "_U32_MAX", 2)
    with pytest.raises(ValueError, match="too long"):
        derive_stream_key(0, "abc", "stream")


class _HostileInt(int):
    def __index__(self) -> int:
        raise AssertionError("hostile integer was coerced")

    def to_bytes(self, *args: object, **kwargs: object) -> bytes:
        raise AssertionError("hostile integer was serialized")


class _HostileStr(str):
    def encode(self, *args: object, **kwargs: object) -> bytes:
        raise AssertionError("hostile string was encoded")


class _HostileTuple(tuple[object, ...]):
    def __iter__(self):
        raise AssertionError("hostile tuple was iterated")


class _HostileList(list[object]):
    def __iter__(self):
        raise AssertionError("hostile list was iterated")


def test_key_boundary_rejects_hostile_scalar_subclasses_before_using_them() -> None:
    with pytest.raises((TypeError, ValueError)):
        derive_stream_key(_HostileInt(0), "group", "stream")
    with pytest.raises((TypeError, ValueError)):
        derive_stream_key(0, _HostileStr("group"), "stream")
    with pytest.raises((TypeError, ValueError)):
        derive_stream_key(0, "group", _HostileStr("stream"))


@pytest.mark.parametrize(
    ("counter", "key"),
    (
        ([0, 0, 0, 0], (0, 0)),
        ((0, 0, 0), (0, 0)),
        ((0, 0, 0, 0, 0), (0, 0)),
        ((0, 0, 0, 0), [0, 0]),
        ((0, 0, 0, 0), (0,)),
        ((0, 0, 0, 0), (0, 0, 0)),
        ((-1, 0, 0, 0), (0, 0)),
        (((1 << 64), 0, 0, 0), (0, 0)),
        ((True, 0, 0, 0), (0, 0)),
        ((0.0, 0, 0, 0), (0, 0)),
        ((0, 0, 0, 0), (-1, 0)),
        ((0, 0, 0, 0), (0, 1 << 64)),
        ((0, 0, 0, 0), (True, 0)),
    ),
)
def test_philox_boundary_rejects_malformed_words_and_container_shapes(counter: object, key: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(counter, key)  # type: ignore[arg-type]


def test_philox_boundary_rejects_hostile_subclasses_without_iterating_them() -> None:
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(_HostileTuple((0, 0, 0, 0)), (0, 0))  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10((0, 0, 0, 0), _HostileTuple((0, 0)))  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10((_HostileInt(0), 0, 0, 0), (0, 0))


@pytest.mark.parametrize(
    ("event_ordinal", "rejection_ordinal"),
    ((-1, 0), (1 << 64, 0), (0, -1), (0, 1 << 64), (True, 0), (0, False), (0.0, 0)),
)
def test_raw_word_rejects_invalid_ordinals(event_ordinal: object, rejection_ordinal: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        raw_u64(
            root_seed=0,
            coupling_group_id="group",
            stream_name="stream",
            event_ordinal=event_ordinal,  # type: ignore[arg-type]
            rejection_ordinal=rejection_ordinal,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("n", (0, -1, (1 << 64) + 1, True, 1.0))
def test_uniform_below_rejects_invalid_ranges(n: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        uniform_below(**_BASE_ADDRESS, n=n)  # type: ignore[arg-type]


def test_uniform_below_rejects_a_malformed_word_from_its_raw_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(semantic_rng, "raw_u64", lambda **_: True)
    with pytest.raises(TypeError, match="raw word"):
        uniform_below(**_BASE_ADDRESS, n=3)


def test_uniform_below_fails_before_rejection_counter_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_rejections: list[int] = []

    def reject_every_candidate(**address: object) -> int:
        observed_rejections.append(address["rejection_ordinal"])  # type: ignore[arg-type]
        return 3

    monkeypatch.setattr(semantic_rng, "_U64_MODULUS", 4)
    monkeypatch.setattr(semantic_rng, "_U64_MAX", 3)
    monkeypatch.setattr(semantic_rng, "raw_u64", reject_every_candidate)

    with pytest.raises(OverflowError, match="rejection ordinal exhausted"):
        uniform_below(**_BASE_ADDRESS, n=3)
    assert observed_rejections == [0, 1, 2, 3]


@pytest.mark.parametrize(
    "counts",
    (
        (),
        [],
        (0,),
        (0, 0),
        (-1, 2),
        (1.0,),
        (True,),
        (2, 4),
        (0, 6, 0, 9),
        (_U64_SPACE, 1),
        (_U64_SPACE + 1,),
        {0, 1},
        {"left": 1},
        "1",
        b"1",
    ),
)
def test_categorical_rejects_malformed_or_noncanonical_count_vectors(counts: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        categorical_index(**_BASE_ADDRESS, counts=counts)  # type: ignore[arg-type]


def test_categorical_rejects_hostile_count_subclasses_without_iterating_them() -> None:
    with pytest.raises((TypeError, ValueError)):
        categorical_index(**_BASE_ADDRESS, counts=_HostileTuple((1,)))
    with pytest.raises((TypeError, ValueError)):
        categorical_index(**_BASE_ADDRESS, counts=_HostileList([1]))
    with pytest.raises((TypeError, ValueError)):
        categorical_index(**_BASE_ADDRESS, counts=(_HostileInt(1),))


def test_sampling_entry_points_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        raw_u64(0, "group", "stream", 0, 0)  # type: ignore[misc]
    with pytest.raises(TypeError):
        uniform_below(0, "group", "stream", 0, 3)  # type: ignore[misc]
    with pytest.raises(TypeError):
        categorical_index(0, "group", "stream", 0, (1,))  # type: ignore[misc]


def test_results_are_independent_of_python_hash_seed_in_subprocesses() -> None:
    code = """
import json
from tetris_ballistic.engine.rng import categorical_index, derive_stream_key, raw_u64, uniform_below

key = derive_stream_key(0, "root-superblock-000", "family")
raw = raw_u64(
    root_seed=0,
    coupling_group_id="root-superblock-000",
    stream_name="family",
    event_ordinal=0,
)
bounded = uniform_below(
    root_seed=0,
    coupling_group_id="root-superblock-000",
    stream_name="family",
    event_ordinal=0,
    n=257,
)
categorical = categorical_index(
    root_seed=0,
    coupling_group_id="root-superblock-000",
    stream_name="family",
    event_ordinal=0,
    counts=(0, 118, 0, 139),
)
print(json.dumps({
    "bounded": [bounded.value, bounded.accepted_rejection_ordinal],
    "categorical": [categorical.value, categorical.accepted_rejection_ordinal],
    "key": key,
    "raw": raw,
}, sort_keys=True, separators=(",", ":")))
"""
    expected = json.dumps(
        {
            "bounded": [118, 0],
            "categorical": [3, 0],
            "key": [0x19A83E984B4A5059, 0xEBC32BDA16F60722],
            "raw": 0x75AB473CEF3D469F,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    project_root = Path(__file__).resolve().parents[1]
    outputs = []
    for hash_seed in ("1", "8675309", "random"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=project_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout.strip())
    assert outputs == [expected, expected, expected]


def test_test_oracle_does_not_depend_on_production_rng_helpers() -> None:
    oracle_globals = {
        name
        for function in (
            _oracle_key_preimage,
            _oracle_derive_stream_key,
            _oracle_philox4x64_10,
            _oracle_raw_u64,
            _oracle_uniform_below,
            _oracle_categorical_index,
        )
        for name in function.__code__.co_names
    }
    assert not oracle_globals.intersection(
        {
            "SEMANTIC_RNG_CONTRACT_ID",
            "SemanticDraw",
            "derive_stream_key",
            "philox4x64_10",
            "raw_u64",
            "uniform_below",
            "categorical_index",
            "semantic_rng",
        }
    )
    assert semantic_rng.__name__ == "tetris_ballistic.engine.rng"
