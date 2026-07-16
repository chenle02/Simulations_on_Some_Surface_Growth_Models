"""Independent Slice 4 certification for the compiled semantic RNG core.

The arbitrary-precision oracle in this file is derived directly from the
frozen Philox4x64-10 and quotient/rejection laws.  It does not call the scalar
or compiled implementation.  Random123's three upstream known answers and
the literal project/PRE vectors remain the primary fixed authorities.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import sys
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest
from numba import types as numba_types
from numba.core.errors import TypingError

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.rng as scalar_rng
import tetris_ballistic.engine.rng_compiled as compiled_rng
from tetris_ballistic.engine.rng import SemanticDraw
from tetris_ballistic.engine.rng_compiled import philox4x64_10, raw_u64_from_key, uniform_below_from_key

_U64_SPACE = 1 << 64
_U64_MAX = _U64_SPACE - 1
_U128_MAX = (1 << 128) - 1
_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"

# Deliberately repeated from the frozen Random123 law, never imported from the
# implementation under test.
_PHILOX_M0 = 0xD2E7470EE14C6C93
_PHILOX_M1 = 0xCA5A826395121157
_PHILOX_W0 = 0x9E3779B97F4A7C15
_PHILOX_W1 = 0xBB67AE8584CAA73B


def _oracle_derive_key(root_seed: int, coupling_group_id: str, stream_name: str) -> tuple[int, int]:
    group = coupling_group_id.encode("utf-8")
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
    digest = sha256(preimage).digest()
    return int.from_bytes(digest[:8], "big"), int.from_bytes(digest[8:16], "big")


def _oracle_philox4x64_10(counter: tuple[int, int, int, int], key: tuple[int, int]) -> tuple[int, int, int, int]:
    """Apply Philox using Python's arbitrary-precision integer arithmetic."""

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
    return c0, c1, c2, c3


def _oracle_raw_u64(*, key: tuple[int, int], event_ordinal: int, rejection_ordinal: int = 0) -> int:
    return _oracle_philox4x64_10((event_ordinal, rejection_ordinal, 0, 0), key)[0]


def _oracle_uniform_below(
    *, key: tuple[int, int], event_ordinal: int, n: int, initial_rejection: int = 0
) -> tuple[int, int]:
    quotient = _U64_SPACE // n
    threshold = quotient * n
    rejection = initial_rejection
    while rejection < _U64_SPACE:
        word = _oracle_raw_u64(key=key, event_ordinal=event_ordinal, rejection_ordinal=rejection)
        if word < threshold:
            return word // quotient, rejection
        rejection += 1
    raise OverflowError("independent oracle exhausted the unsigned 64-bit rejection counter")


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
def test_compiled_core_matches_all_three_upstream_random123_known_answers(
    counter: tuple[int, int, int, int],
    key: tuple[int, int],
    expected: tuple[int, int, int, int],
) -> None:
    assert _oracle_philox4x64_10(counter, key) == expected
    actual = philox4x64_10(counter=counter, key=key)
    assert actual == expected
    assert type(actual) is tuple
    assert all(type(word) is int for word in actual)


_DOCUMENTED_PROJECT_FULL_OUTPUTS = (
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
    _DOCUMENTED_PROJECT_FULL_OUTPUTS,
)
def test_all_four_documented_project_full_outputs(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    rejection_ordinal: int,
    expected_key: tuple[int, int],
    expected_output: tuple[int, int, int, int],
) -> None:
    assert _oracle_derive_key(root_seed, coupling_group_id, stream_name) == expected_key
    counter = (event_ordinal, rejection_ordinal, 0, 0)
    assert _oracle_philox4x64_10(counter, expected_key) == expected_output
    assert philox4x64_10(counter=counter, key=expected_key) == expected_output
    assert (
        raw_u64_from_key(
            key=expected_key,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )
        == expected_output[0]
    )


_SUPPLEMENTARY_FIXED_KEY_RAW_ROWS = (
    (0, "root-superblock-000", "family", 0, (0x19A83E984B4A5059, 0xEBC32BDA16F60722), 0x75AB473CEF3D469F),
    (_U128_MAX, "α/β", "接触", _U64_MAX, (0x3718D77CA93BB0CE, 0x04128E4BC36A2115), 0xB2F4AB39B39341AF),
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
    _SUPPLEMENTARY_FIXED_KEY_RAW_ROWS,
)
def test_three_supplementary_fixed_project_key_raw_rows(
    root_seed: int,
    coupling_group_id: str,
    stream_name: str,
    event_ordinal: int,
    expected_key: tuple[int, int],
    expected_raw: int,
) -> None:
    assert _oracle_derive_key(root_seed, coupling_group_id, stream_name) == expected_key
    assert _oracle_raw_u64(key=expected_key, event_ordinal=event_ordinal) == expected_raw
    assert raw_u64_from_key(key=expected_key, event_ordinal=event_ordinal) == expected_raw


_BOUNDARY_KEY = (0x19A83E984B4A5059, 0xEBC32BDA16F60722)
_BOUNDARY_MAPPINGS = (
    (1, 0),
    (2, 0),
    (3, 1),
    (257, 118),
    ((1 << 63) + 1, 0x75AB473CEF3D469F),
    (_U64_MAX, 0x75AB473CEF3D469F),
    (_U64_SPACE, 0x75AB473CEF3D469F),
)


@pytest.mark.parametrize(("n", "expected_value"), _BOUNDARY_MAPPINGS)
def test_all_seven_documented_boundary_sized_mappings(n: int, expected_value: int) -> None:
    assert _oracle_uniform_below(key=_BOUNDARY_KEY, event_ordinal=0, n=n) == (expected_value, 0)
    draw = uniform_below_from_key(key=_BOUNDARY_KEY, event_ordinal=0, n=n)
    assert type(draw) is SemanticDraw
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, 0)


_DOCUMENTED_BOUNDED_ROWS = (
    ((0x1682C41740E367DC, 0xD803DC8CB13639CA), 0, 5, 3, 0),
    ((0x9E291B64FE60DA0C, 0x857F38FC86CF72E4), 42, 17, 11, 0),
    ((0x042F32C7E8336EBF, 0x74E762C7FB4C5033), 0, 4, 3, 0),
    ((0xEC843C817F1FDDBD, 0x4C47480A694A88D9), _U64_MAX, _U64_SPACE, 10231637573218554332, 0),
    ((0x7684ED50B1B61903, 0xFE9EAA6304697D0B), 0, (1 << 63) + 1, 7255411166493364322, 1),
)


@pytest.mark.parametrize(
    ("key", "event_ordinal", "n", "expected_value", "expected_rejection"),
    _DOCUMENTED_BOUNDED_ROWS,
)
def test_all_five_documented_bounded_rows(
    key: tuple[int, int],
    event_ordinal: int,
    n: int,
    expected_value: int,
    expected_rejection: int,
) -> None:
    assert _oracle_uniform_below(key=key, event_ordinal=event_ordinal, n=n) == (
        expected_value,
        expected_rejection,
    )
    draw = uniform_below_from_key(key=key, event_ordinal=event_ordinal, n=n)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, expected_rejection)


_EXACT_SELECTION_UNIFORM_ROWS = (
    (
        (0x9E291B64FE60DA0C, 0x857F38FC86CF72E4),
        42,
        17,
        0xACD7B7CD13C14731,
        11,
        0,
    ),
    (
        (0x7684ED50B1B61903, 0xFE9EAA6304697D0B),
        0,
        2,
        0xE2160DF4A6D93AD1,
        1,
        0,
    ),
    (
        (0x7684ED50B1B61903, 0xFE9EAA6304697D0B),
        0,
        (1 << 63) + 1,
        0xE2160DF4A6D93AD1,
        0x64B06603DE3D5062,
        1,
    ),
    (
        (0x7684ED50B1B61903, 0xFE9EAA6304697D0B),
        0,
        _U64_SPACE,
        0xE2160DF4A6D93AD1,
        0xE2160DF4A6D93AD1,
        0,
    ),
)


@pytest.mark.parametrize(
    ("key", "event_ordinal", "n", "expected_first_word", "expected_value", "expected_rejection"),
    _EXACT_SELECTION_UNIFORM_ROWS,
)
def test_every_normative_exact_selection_uniform_row_at_the_compiled_layer(
    key: tuple[int, int],
    event_ordinal: int,
    n: int,
    expected_first_word: int,
    expected_value: int,
    expected_rejection: int,
) -> None:
    assert _oracle_raw_u64(key=key, event_ordinal=event_ordinal) == expected_first_word
    assert raw_u64_from_key(key=key, event_ordinal=event_ordinal) == expected_first_word
    assert _oracle_uniform_below(key=key, event_ordinal=event_ordinal, n=n) == (
        expected_value,
        expected_rejection,
    )
    draw = uniform_below_from_key(key=key, event_ordinal=event_ordinal, n=n)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, expected_rejection)


_CATEGORICAL_UNDERLYING_ROWS = (
    ("fixed-zero-slots", _BOUNDARY_KEY, 0, (0, 1, 0), 0),
    ("fixed-all-one", _BOUNDARY_KEY, 0, (1, 1, 1), 1),
    ("fixed-half-open", _BOUNDARY_KEY, 0, (0, 2, 0, 3), 2),
    ("fixed-full-space", _BOUNDARY_KEY, 0, (1, 0, _U64_MAX), 0x75AB473CEF3D469F),
    ("fixed-257", _BOUNDARY_KEY, 0, (0, 118, 0, 139), 118),
    ("project-family", (0x1682C41740E367DC, 0xD803DC8CB13639CA), 0, (1, 1, 1, 1, 1), 3),
    ("project-contact", (0x042F32C7E8336EBF, 0x74E762C7FB4C5033), 0, (1, 3), 3),
    ("project-contact-zero-slots", (0x042F32C7E8336EBF, 0x74E762C7FB4C5033), 0, (0, 3, 1, 0), 3),
    (
        "project-orientation",
        (0x880A4ABA48949BD0, 0xAAEBCAB941D72A82),
        0,
        (1, 1, 1, 1, 1, 1, 1, 1),
        7,
    ),
    ("project-degenerate", (0x3E81B9DD5F5CA413, 0xE807F9BC3B611381), 9, (1,), 0),
)


@pytest.mark.parametrize(
    ("case_id", "key", "event_ordinal", "counts", "expected_uniform"),
    _CATEGORICAL_UNDERLYING_ROWS,
    ids=[row[0] for row in _CATEGORICAL_UNDERLYING_ROWS],
)
def test_every_categorical_vector_at_the_compiled_bounded_layer(
    case_id: str,
    key: tuple[int, int],
    event_ordinal: int,
    counts: tuple[int, ...],
    expected_uniform: int,
) -> None:
    del case_id
    n = sum(counts)
    assert _oracle_uniform_below(key=key, event_ordinal=event_ordinal, n=n) == (expected_uniform, 0)
    draw = uniform_below_from_key(key=key, event_ordinal=event_ordinal, n=n)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_uniform, 0)


_PRE_LAUNCH_KEY = (0x81BA8E755EA8A360, 0xF829A74D482F4EBB)
_PRE_CONTACT_KEY = (0x6C00B0C4102C9848, 0x4373AA5DF7EF12BD)


@pytest.mark.parametrize(
    ("stream_name", "expected_key", "expected_raw"),
    (
        ("launch", _PRE_LAUNCH_KEY, 0x6F7A7D3D95AA5E68),
        ("contact", _PRE_CONTACT_KEY, 0xCBF5C12A6FEE559E),
    ),
)
def test_both_pre_root_zero_stream_keys_and_raw_words(
    stream_name: str, expected_key: tuple[int, int], expected_raw: int
) -> None:
    assert _oracle_derive_key(0, "pre-one-cell-discovery-v1", stream_name) == expected_key
    assert _oracle_raw_u64(key=expected_key, event_ordinal=0) == expected_raw
    assert raw_u64_from_key(key=expected_key, event_ordinal=0) == expected_raw


def test_pre_root_zero_event_zero_contact_mapping_is_normative() -> None:
    assert _oracle_uniform_below(key=_PRE_CONTACT_KEY, event_ordinal=0, n=100) == (79, 0)
    draw = uniform_below_from_key(key=_PRE_CONTACT_KEY, event_ordinal=0, n=100)
    assert (draw.value, draw.accepted_rejection_ordinal) == (79, 0)


_PRE_CAMPAIGN_WIDTHS = (
    (32, 13),
    (50, 21),
    (64, 27),
    (80, 34),
    (100, 43),
    (128, 55),
    (150, 65),
    (200, 87),
    (250, 108),
    (256, 111),
    (300, 130),
    (400, 174),
    (500, 217),
    (512, 222),
    (1024, 445),
)


@pytest.mark.parametrize(("width", "expected_launch"), _PRE_CAMPAIGN_WIDTHS)
def test_all_fifteen_pre_campaign_width_rows(width: int, expected_launch: int) -> None:
    assert _oracle_uniform_below(key=_PRE_LAUNCH_KEY, event_ordinal=0, n=width) == (expected_launch, 0)
    draw = uniform_below_from_key(key=_PRE_LAUNCH_KEY, event_ordinal=0, n=width)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_launch, 0)


_PRE_CONTACT_BOUNDARIES = (
    (23, 0, 0x019AB06E6D647A86),
    (153, 1, 0x043DB201A9973A5D),
    (3, 2, 0x066653BC2AA19546),
    (55, 4, 0x0BFB25192B17F92E),
    (24, 5, 0x0F3558266A1ECB4C),
    (1, 9, 0x1918F1660387FA79),
    (42, 10, 0x19E67647A5038BA7),
    (6, 24, 0x3F52C476D5D5F065),
    (41, 25, 0x41E28830E2FACF93),
    (45, 49, 0x7DAAF3E15F89F819),
    (216, 50, 0x81E81F92C924DD8F),
    (43, 99, 0xFED165AE9ECF81FF),
)


@pytest.mark.parametrize(("event_ordinal", "expected_contact", "expected_raw"), _PRE_CONTACT_BOUNDARIES)
def test_all_twelve_pre_strict_contact_boundary_rows(
    event_ordinal: int, expected_contact: int, expected_raw: int
) -> None:
    assert _oracle_raw_u64(key=_PRE_CONTACT_KEY, event_ordinal=event_ordinal) == expected_raw
    assert raw_u64_from_key(key=_PRE_CONTACT_KEY, event_ordinal=event_ordinal) == expected_raw
    assert _oracle_uniform_below(key=_PRE_CONTACT_KEY, event_ordinal=event_ordinal, n=100) == (
        expected_contact,
        0,
    )
    draw = uniform_below_from_key(key=_PRE_CONTACT_KEY, event_ordinal=event_ordinal, n=100)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_contact, 0)


def test_pre_unequal_width_chain_accepts_at_ordinal_two_without_shifting_addresses() -> None:
    expected_words = (0xC2361DB490F49873, 0xA4E089425B0398F4, 0x29A2134F7BE99C8D)
    for rejection_ordinal, expected_word in enumerate(expected_words):
        assert (
            raw_u64_from_key(
                key=_PRE_LAUNCH_KEY,
                event_ordinal=6,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )
        assert (
            _oracle_raw_u64(
                key=_PRE_LAUNCH_KEY,
                event_ordinal=6,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )

    later_before = raw_u64_from_key(key=_PRE_LAUNCH_KEY, event_ordinal=7)
    contact_before = raw_u64_from_key(key=_PRE_CONTACT_KEY, event_ordinal=6)
    rows = ((64, 48, 0), (100, 75, 0), ((1 << 63) + 1, 2999981533884423309, 2))
    for width, expected_value, expected_rejection in rows:
        assert _oracle_uniform_below(key=_PRE_LAUNCH_KEY, event_ordinal=6, n=width) == (
            expected_value,
            expected_rejection,
        )
        draw = uniform_below_from_key(key=_PRE_LAUNCH_KEY, event_ordinal=6, n=width)
        assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, expected_rejection)
    assert later_before == raw_u64_from_key(key=_PRE_LAUNCH_KEY, event_ordinal=7) == 0x4C65426535B61D1A
    assert contact_before == raw_u64_from_key(key=_PRE_CONTACT_KEY, event_ordinal=6) == 0x3F52C476D5D5F065


_COMPLETE_EVENT_CANONICAL_ROWS = (
    ("family", (0x1682C41740E367DC, 0xD803DC8CB13639CA), 5, 0x9FC97B3E13CEE41B, 3),
    ("orientation", (0x880A4ABA48949BD0, 0xAAEBCAB941D72A82), 4, 0xFFC7FB838D848799, 3),
    ("launch", (0x65201116FBAEE492, 0xA3DB3ED24879EF5E), 17, 0x40AF7280B937935A, 4),
    ("contact", (0x042F32C7E8336EBF, 0x74E762C7FB4C5033), 2, 0xCDCC6E52E762825F, 1),
)


@pytest.mark.parametrize(
    ("stream_name", "expected_key", "n", "expected_raw", "expected_value"),
    _COMPLETE_EVENT_CANONICAL_ROWS,
)
def test_all_four_normative_complete_event_stream_rows_at_the_compiled_layer(
    stream_name: str,
    expected_key: tuple[int, int],
    n: int,
    expected_raw: int,
    expected_value: int,
) -> None:
    assert _oracle_derive_key(0, "paired-main", stream_name) == expected_key
    assert _oracle_raw_u64(key=expected_key, event_ordinal=0) == expected_raw
    assert raw_u64_from_key(key=expected_key, event_ordinal=0) == expected_raw
    assert _oracle_uniform_below(key=expected_key, event_ordinal=0, n=n) == (expected_value, 0)
    draw = uniform_below_from_key(key=expected_key, event_ordinal=0, n=n)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, 0)


def test_complete_event_unequal_bound_chain_and_future_address_are_normative() -> None:
    launch_key = (0x65201116FBAEE492, 0xA3DB3ED24879EF5E)
    expected_words = (0x853FE237A36163CC, 0x72B281009E3EB9C5)
    for rejection_ordinal, expected_word in enumerate(expected_words):
        assert (
            _oracle_raw_u64(
                key=launch_key,
                event_ordinal=1,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )
        assert (
            raw_u64_from_key(
                key=launch_key,
                event_ordinal=1,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )

    future_event_before = raw_u64_from_key(key=launch_key, event_ordinal=2)
    assert _oracle_raw_u64(key=launch_key, event_ordinal=2) == 0xD997D7678FD2D614
    other_streams_before = tuple(
        raw_u64_from_key(key=key, event_ordinal=1)
        for _, key, _, _, _ in _COMPLETE_EVENT_CANONICAL_ROWS
        if key != launch_key
    )
    for n, expected_value, expected_rejection in (
        (2, 1, 0),
        ((1 << 63) + 1, 0x72B281009E3EB9C5, 1),
    ):
        assert _oracle_uniform_below(key=launch_key, event_ordinal=1, n=n) == (
            expected_value,
            expected_rejection,
        )
        draw = uniform_below_from_key(key=launch_key, event_ordinal=1, n=n)
        assert (draw.value, draw.accepted_rejection_ordinal) == (expected_value, expected_rejection)

    assert future_event_before == raw_u64_from_key(key=launch_key, event_ordinal=2) == 0xD997D7678FD2D614
    assert other_streams_before == tuple(
        raw_u64_from_key(key=key, event_ordinal=1)
        for _, key, _, _, _ in _COMPLETE_EVENT_CANONICAL_ROWS
        if key != launch_key
    )


def test_documented_generic_rejection_chain_accepts_at_ordinal_one() -> None:
    key = (0x7684ED50B1B61903, 0xFE9EAA6304697D0B)
    other_stream_key = (0x52D2452ECB73F32F, 0x8509D39F91CA4B56)
    root_seed = 0x0123456789ABCDEFFEDCBA9876543210
    assert _oracle_derive_key(root_seed, "rejection-test", "launch") == key
    assert _oracle_derive_key(root_seed, "rejection-test", "contact") == other_stream_key
    assert raw_u64_from_key(key=key, event_ordinal=0, rejection_ordinal=0) == 0xE2160DF4A6D93AD1
    assert raw_u64_from_key(key=key, event_ordinal=0, rejection_ordinal=1) == 0x64B06603DE3D5062
    next_event_before = raw_u64_from_key(key=key, event_ordinal=1)
    other_stream_before = raw_u64_from_key(key=other_stream_key, event_ordinal=0)
    draw = uniform_below_from_key(key=key, event_ordinal=0, n=(1 << 63) + 1)
    assert (draw.value, draw.accepted_rejection_ordinal) == (0x64B06603DE3D5062, 1)
    assert next_event_before == raw_u64_from_key(key=key, event_ordinal=1) == 0x1FD434BDEEAE4AA1
    assert other_stream_before == raw_u64_from_key(key=other_stream_key, event_ordinal=0) == 0x2E8FDCFFAC1C2195


def test_audit_rejection_chain_accepts_at_ordinal_five_and_is_address_local() -> None:
    contact_key = (0xB8F557776024F7A7, 0x18C6E95AD47DDC8B)
    launch_key = (0x29E7E4E430307E41, 0xC866526E0B0BE4D0)
    expected_words = (
        0xD067A4B6D387C47B,
        0xC8E66D786B591323,
        0xA4AA97456A5CD3E2,
        0xE0E748FBCBC33456,
        0xA3FBB0E492EAAFCB,
        0x25443A3D1347F4FE,
    )
    for rejection_ordinal, expected_word in enumerate(expected_words):
        assert (
            raw_u64_from_key(
                key=contact_key,
                event_ordinal=6,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )
        assert (
            _oracle_raw_u64(
                key=contact_key,
                event_ordinal=6,
                rejection_ordinal=rejection_ordinal,
            )
            == expected_word
        )

    later_before = raw_u64_from_key(key=contact_key, event_ordinal=7)
    other_stream_before = raw_u64_from_key(key=launch_key, event_ordinal=6)
    draw = uniform_below_from_key(key=contact_key, event_ordinal=6, n=(1 << 63) + 1)
    assert (draw.value, draw.accepted_rejection_ordinal) == (expected_words[-1], 5)
    assert later_before == raw_u64_from_key(key=contact_key, event_ordinal=7) == 0xEAF8CC164F6F2F87
    assert other_stream_before == raw_u64_from_key(key=launch_key, event_ordinal=6) == 0x60C7C112C1B23ED0


@pytest.mark.parametrize(
    ("n", "expected_quotient", "expected_threshold"),
    (
        (3, _U64_SPACE // 3, (_U64_SPACE // 3) * 3),
        (100, _U64_SPACE // 100, (_U64_SPACE // 100) * 100),
        ((1 << 63) + 1, 1, (1 << 63) + 1),
        (_U64_MAX, 1, _U64_MAX),
    ),
)
def test_private_mapping_accepts_t_minus_one_and_rejects_t_and_maximum_word(
    n: int, expected_quotient: int, expected_threshold: int
) -> None:
    quotient, threshold, unit_bound = compiled_rng._prepare_bounded_mapping_kernel(np.uint64(n - 1))
    assert type(quotient) is int
    assert type(threshold) is int
    assert type(unit_bound) is int
    assert (quotient, threshold, unit_bound) == (expected_quotient, expected_threshold, 0)

    accepted_below, value_below = compiled_rng._map_bounded_word_kernel(
        np.uint64(expected_threshold - 1),
        np.uint64(quotient),
        np.uint64(threshold),
        np.uint64(0),
    )
    accepted_at, rejected_value = compiled_rng._map_bounded_word_kernel(
        np.uint64(expected_threshold),
        np.uint64(quotient),
        np.uint64(threshold),
        np.uint64(0),
    )
    accepted_max, rejected_max_value = compiled_rng._map_bounded_word_kernel(
        np.uint64(_U64_MAX),
        np.uint64(quotient),
        np.uint64(threshold),
        np.uint64(0),
    )
    assert (accepted_below, value_below) == (True, (expected_threshold - 1) // quotient)
    assert accepted_at is False
    assert accepted_max is False
    assert type(rejected_value) is int
    assert type(rejected_max_value) is int


@pytest.mark.parametrize("n", (2, 4, 1 << 32, 1 << 63, _U64_SPACE))
def test_private_power_of_two_mapping_represents_mathematical_threshold_two_to_64(n: int) -> None:
    quotient, threshold, unit_bound = compiled_rng._prepare_bounded_mapping_kernel(np.uint64(n - 1))
    assert (quotient, threshold, unit_bound) == (_U64_SPACE // n, 0, 0)
    accepted, value = compiled_rng._map_bounded_word_kernel(
        np.uint64(_U64_MAX),
        np.uint64(quotient),
        np.uint64(threshold),
        np.uint64(0),
    )
    assert (accepted, value) == (True, n - 1)


def test_private_unit_bound_encoding_maps_every_word_to_zero() -> None:
    quotient, threshold, unit_bound = compiled_rng._prepare_bounded_mapping_kernel(np.uint64(0))
    assert unit_bound == 1
    for word in (0, 1, 0x75AB473CEF3D469F, _U64_MAX):
        accepted, value = compiled_rng._map_bounded_word_kernel(
            np.uint64(word),
            np.uint64(quotient),
            np.uint64(threshold),
            np.uint64(1),
        )
        assert (accepted, value) == (True, 0)


def test_real_private_kernel_fails_before_rejection_counter_wrap() -> None:
    # This literal maximum-address candidate is above T=2**63+1, so starting
    # at the final rejection ordinal must report exhaustion without wrapping.
    value, rejection, exhausted = compiled_rng._uniform_below_kernel(
        np.uint64(0xEC843C817F1FDDBD),
        np.uint64(0x4C47480A694A88D9),
        np.uint64(_U64_MAX),
        np.uint64(1 << 63),
        np.uint64(_U64_MAX),
    )
    assert (value, rejection, exhausted) == (0, _U64_MAX, True)
    assert type(value) is int
    assert type(rejection) is int
    assert type(exhausted) is bool


def test_public_mapper_turns_private_exhaustion_into_a_fail_closed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def exhausted_kernel(*args: object) -> tuple[int, int, bool]:
        assert len(args) == 5
        return 0, _U64_MAX, True

    monkeypatch.setattr(compiled_rng, "_uniform_below_kernel", exhausted_kernel)
    with pytest.raises(OverflowError, match="rejection ordinal exhausted"):
        uniform_below_from_key(key=(0, 0), event_ordinal=0, n=3)


def _sweep_u64(index: int, lane: int) -> int:
    payload = b"slice-4-independent-sweep-v1\0" + index.to_bytes(4, "big") + lane.to_bytes(1, "big")
    return int.from_bytes(sha256(payload).digest()[:8], "big")


def test_deterministic_independent_arbitrary_precision_philox_and_mulhilo_sweep() -> None:
    for index in range(10_000):
        left = _sweep_u64(index, 0)
        right = _sweep_u64(index, 1)
        product = left * right
        actual_high, actual_low = compiled_rng._multiply_high_low_kernel(np.uint64(left), np.uint64(right))
        assert (actual_high, actual_low) == (product >> 64, product & _U64_MAX)

        counter = tuple(_sweep_u64(index, lane) for lane in range(4))
        key = (_sweep_u64(index, 4), _sweep_u64(index, 5))
        expected = _oracle_philox4x64_10(counter, key)  # type: ignore[arg-type]
        assert philox4x64_10(counter=counter, key=key) == expected  # type: ignore[arg-type]


def test_deterministic_independent_arbitrary_precision_raw_and_bounded_sweep() -> None:
    fixed_bounds = (1, 2, 3, 5, 17, 100, 257, 1 << 32, (1 << 63) + 1, _U64_MAX, _U64_SPACE)
    for index in range(10_000):
        key = (_sweep_u64(index, 0), _sweep_u64(index, 1))
        event_ordinal = _sweep_u64(index, 2)
        rejection_ordinal = _sweep_u64(index, 3)
        assert raw_u64_from_key(
            key=key,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        ) == _oracle_raw_u64(
            key=key,
            event_ordinal=event_ordinal,
            rejection_ordinal=rejection_ordinal,
        )

        n = fixed_bounds[index % len(fixed_bounds)]
        expected = _oracle_uniform_below(key=key, event_ordinal=event_ordinal, n=n)
        draw = uniform_below_from_key(key=key, event_ordinal=event_ordinal, n=n)
        assert (draw.value, draw.accepted_rejection_ordinal) == expected


def test_compiled_results_also_cross_check_the_certified_scalar_host_evidence() -> None:
    addresses = (
        (0, "paired-main", "family", 0, 5),
        (0x0123456789ABCDEFFEDCBA9876543210, "rejection-test", "launch", 0, (1 << 63) + 1),
        (0, "pre-one-cell-discovery-v1", "contact", 42, 100),
    )
    for root_seed, group, stream, event_ordinal, n in addresses:
        key = _oracle_derive_key(root_seed, group, stream)
        assert scalar_rng.derive_stream_key(root_seed, group, stream) == key
        assert raw_u64_from_key(key=key, event_ordinal=event_ordinal) == _oracle_raw_u64(
            key=key,
            event_ordinal=event_ordinal,
        )
        assert scalar_rng.raw_u64(
            root_seed=root_seed,
            coupling_group_id=group,
            stream_name=stream,
            event_ordinal=event_ordinal,
        ) == raw_u64_from_key(key=key, event_ordinal=event_ordinal)
        expected = _oracle_uniform_below(key=key, event_ordinal=event_ordinal, n=n)
        scalar_draw = scalar_rng.uniform_below(
            root_seed=root_seed,
            coupling_group_id=group,
            stream_name=stream,
            event_ordinal=event_ordinal,
            n=n,
        )
        compiled_draw = uniform_below_from_key(key=key, event_ordinal=event_ordinal, n=n)
        assert (scalar_draw.value, scalar_draw.accepted_rejection_ordinal) == expected
        assert (compiled_draw.value, compiled_draw.accepted_rejection_ordinal) == expected


class _HostileInt(int):
    def __index__(self) -> int:
        raise AssertionError("hostile integer was coerced")


class _HostileTuple(tuple[object, ...]):
    def __len__(self) -> int:
        raise AssertionError("hostile tuple length was read")

    def __iter__(self):
        raise AssertionError("hostile tuple was iterated")


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
        ((np.uint64(0), 0, 0, 0), (0, 0)),
        ((0, 0, 0, 0), (-1, 0)),
        ((0, 0, 0, 0), (0, 1 << 64)),
        ((0, 0, 0, 0), (True, 0)),
        ((0, 0, 0, 0), (np.uint64(0), 0)),
    ),
)
def test_public_philox_rejects_malformed_exact_types_and_shapes(counter: object, key: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(counter=counter, key=key)  # type: ignore[arg-type]


def test_public_philox_rejects_hostile_subclasses_without_using_them() -> None:
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(counter=_HostileTuple((0, 0, 0, 0)), key=(0, 0))  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(counter=(0, 0, 0, 0), key=_HostileTuple((0, 0)))  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        philox4x64_10(counter=(_HostileInt(0), 0, 0, 0), key=(0, 0))


@pytest.mark.parametrize(
    ("key", "event_ordinal", "rejection_ordinal"),
    (
        ([], 0, 0),
        ((0,), 0, 0),
        ((0, 0, 0), 0, 0),
        ((True, 0), 0, 0),
        ((np.uint64(0), 0), 0, 0),
        ((0, 0), -1, 0),
        ((0, 0), 1 << 64, 0),
        ((0, 0), True, 0),
        ((0, 0), np.uint64(0), 0),
        ((0, 0), 0, -1),
        ((0, 0), 0, 1 << 64),
        ((0, 0), 0, False),
        ((0, 0), 0, np.uint64(0)),
    ),
)
def test_public_raw_rejects_malformed_exact_types(
    key: object, event_ordinal: object, rejection_ordinal: object
) -> None:
    with pytest.raises((TypeError, ValueError)):
        raw_u64_from_key(
            key=key,  # type: ignore[arg-type]
            event_ordinal=event_ordinal,  # type: ignore[arg-type]
            rejection_ordinal=rejection_ordinal,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("n", (0, -1, (1 << 64) + 1, True, 1.0, np.uint64(1)))
def test_public_bounded_mapper_rejects_invalid_or_nonexact_bounds(n: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        uniform_below_from_key(key=(0, 0), event_ordinal=0, n=n)  # type: ignore[arg-type]


def test_key_and_ordinal_boundaries_reject_hostile_subclasses_before_use() -> None:
    with pytest.raises((TypeError, ValueError)):
        raw_u64_from_key(key=_HostileTuple((0, 0)), event_ordinal=0)  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        raw_u64_from_key(key=(0, 0), event_ordinal=_HostileInt(0))
    with pytest.raises((TypeError, ValueError)):
        uniform_below_from_key(key=(0, 0), event_ordinal=0, n=_HostileInt(1))


def test_compiled_bounded_result_reuses_the_immutable_semantic_draw_type() -> None:
    draw = uniform_below_from_key(key=_BOUNDARY_KEY, event_ordinal=0, n=257)
    assert type(draw) is SemanticDraw
    assert (draw.value, draw.accepted_rejection_ordinal) == (118, 0)
    with pytest.raises((FrozenInstanceError, AttributeError)):
        draw.value = 119  # type: ignore[misc]


def test_all_three_public_entry_points_are_keyword_only() -> None:
    with pytest.raises(TypeError):
        philox4x64_10((0, 0, 0, 0), (0, 0))  # type: ignore[misc]
    with pytest.raises(TypeError):
        raw_u64_from_key((0, 0), 0, 0)  # type: ignore[misc]
    with pytest.raises(TypeError):
        uniform_below_from_key((0, 0), 0, 3)  # type: ignore[misc]


def test_invalid_public_inputs_fail_before_any_compiled_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def forbidden(*_: object) -> object:
        calls.append("compiled dispatch")
        raise AssertionError("invalid input reached a compiled dispatcher")

    monkeypatch.setattr(compiled_rng, "_philox4x64_10_kernel", forbidden)
    monkeypatch.setattr(compiled_rng, "_raw_u64_kernel", forbidden)
    monkeypatch.setattr(compiled_rng, "_uniform_below_kernel", forbidden)
    with pytest.raises(TypeError):
        philox4x64_10(counter=(True, 0, 0, 0), key=(0, 0))
    with pytest.raises(TypeError):
        raw_u64_from_key(key=(0, 0), event_ordinal=True)
    with pytest.raises(ValueError):
        uniform_below_from_key(key=(0, 0), event_ordinal=0, n=0)
    assert calls == []


def test_public_wrappers_reject_malformed_private_dispatch_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compiled_rng, "_philox4x64_10_kernel", lambda *_: (0, 0, 0, True))
    with pytest.raises(TypeError, match="compiled Philox result"):
        philox4x64_10(counter=(0, 0, 0, 0), key=(0, 0))

    monkeypatch.setattr(compiled_rng, "_raw_u64_kernel", lambda *_: np.uint64(0))
    with pytest.raises(TypeError, match="compiled raw word"):
        raw_u64_from_key(key=(0, 0), event_ordinal=0)

    malformed_bounded_results = (
        ([0, 0, False], 3),
        ((0, 0), 3),
        ((True, 0, False), 3),
        ((0, _U64_SPACE, False), 3),
        ((0, 0, 0), 3),
        ((3, 0, False), 3),
        ((_U64_MAX, 0, False), 1),
        ((0, 1, False), 1),
        ((0, 1, False), 2),
        ((0, 1, False), 4),
        ((0, 1, False), 1 << 63),
        ((0, 1, False), _U64_SPACE),
    )
    for malformed, bound in malformed_bounded_results:
        monkeypatch.setattr(compiled_rng, "_uniform_below_kernel", lambda *_, result=malformed: result)
        with pytest.raises((TypeError, ValueError)):
            uniform_below_from_key(key=(0, 0), event_ordinal=0, n=bound)


def test_public_alias_and_scalar_authority_rebinding_cannot_change_saved_compiled_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("rebound authority was called")

    monkeypatch.setattr(compiled_rng, "philox4x64_10", forbidden)
    monkeypatch.setattr(compiled_rng, "raw_u64_from_key", forbidden)
    monkeypatch.setattr(compiled_rng, "uniform_below_from_key", forbidden)
    monkeypatch.setattr(compiled_rng, "_SemanticDraw", object())
    monkeypatch.setattr(scalar_rng, "SemanticDraw", object())
    monkeypatch.setattr(scalar_rng, "philox4x64_10", forbidden)
    monkeypatch.setattr(scalar_rng, "raw_u64", forbidden)
    monkeypatch.setattr(scalar_rng, "uniform_below", forbidden)

    assert philox4x64_10(counter=(0, 0, 0, 0), key=(0, 0)) == _RANDOM123_PHILOX4X64_10_KATS[0][2]
    assert raw_u64_from_key(key=_BOUNDARY_KEY, event_ordinal=0) == 0x75AB473CEF3D469F
    draw = uniform_below_from_key(key=_BOUNDARY_KEY, event_ordinal=0, n=257)
    assert type(draw) is SemanticDraw
    assert (draw.value, draw.accepted_rejection_ordinal) == (118, 0)


def _compile_every_private_dispatcher() -> tuple[object, ...]:
    compiled_rng._multiply_high_low_kernel(np.uint64(1), np.uint64(2))
    compiled_rng._philox4x64_10_kernel(*(np.uint64(0) for _ in range(6)))
    compiled_rng._raw_u64_kernel(*(np.uint64(0) for _ in range(4)))
    quotient, threshold, unit_bound = compiled_rng._prepare_bounded_mapping_kernel(np.uint64(99))
    compiled_rng._map_bounded_word_kernel(
        np.uint64(0),
        np.uint64(quotient),
        np.uint64(threshold),
        np.uint64(unit_bound),
    )
    compiled_rng._uniform_below_kernel(*(np.uint64(0) for _ in range(5)))
    return (
        compiled_rng._multiply_high_low_kernel,
        compiled_rng._philox4x64_10_kernel,
        compiled_rng._raw_u64_kernel,
        compiled_rng._prepare_bounded_mapping_kernel,
        compiled_rng._map_bounded_word_kernel,
        compiled_rng._uniform_below_kernel,
    )


def test_every_numerical_kernel_has_unsigned_nopython_signatures_only() -> None:
    dispatchers = _compile_every_private_dispatcher()
    for dispatcher in dispatchers:
        assert dispatcher.signatures
        assert len(dispatcher.nopython_signatures) == len(dispatcher.signatures)
        assert dispatcher.targetoptions.get("nopython") is True
        assert not dispatcher.targetoptions.get("fastmath", False)
        for signature in dispatcher.signatures:
            assert all(argument == numba_types.uint64 for argument in signature)
            overload = dispatcher.overloads[signature]
            assert overload.objectmode is False
            assert "float" not in str(overload.signature.return_type).lower()


def test_private_dispatchers_fail_closed_on_malformed_calls_without_new_signatures() -> None:
    dispatchers = _compile_every_private_dispatcher()
    calls = (
        (compiled_rng._multiply_high_low_kernel, (np.uint64(0), object())),
        (compiled_rng._philox4x64_10_kernel, (*(np.uint64(0) for _ in range(5)), object())),
        (compiled_rng._raw_u64_kernel, (*(np.uint64(0) for _ in range(3)), object())),
        (compiled_rng._prepare_bounded_mapping_kernel, (object(),)),
        (compiled_rng._map_bounded_word_kernel, (*(np.uint64(0) for _ in range(3)), object())),
        (compiled_rng._uniform_below_kernel, (*(np.uint64(0) for _ in range(4)), object())),
    )
    before = {id(dispatcher): tuple(dispatcher.signatures) for dispatcher in dispatchers}
    for dispatcher, arguments in calls:
        with pytest.raises((TypeError, ValueError, TypingError)):
            dispatcher(*arguments)
    for dispatcher in dispatchers:
        assert tuple(dispatcher.signatures) == before[id(dispatcher)]

    with pytest.raises(TypeError):
        compiled_rng._philox4x64_10_kernel(*(np.uint64(0) for _ in range(5)))
    with pytest.raises(TypeError):
        compiled_rng._uniform_below_kernel(*(np.uint64(0) for _ in range(6)))


def test_explicit_submodule_has_exact_exports_and_no_root_exports() -> None:
    expected = ["philox4x64_10", "raw_u64_from_key", "uniform_below_from_key"]
    assert compiled_rng.__all__ == expected
    assert not hasattr(compiled_rng, "SEMANTIC_RNG_CONTRACT_ID")
    for root in (tetris_ballistic, reference_engine):
        for name in expected:
            assert not hasattr(root, name)


def test_compiled_module_dependency_and_call_graph_guards() -> None:
    source = Path(inspect.getsourcefile(compiled_rng) or "").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "_kernel_1x1" not in source

    forbidden_scalar_helpers = {
        "categorical_index",
        "derive_stream_key",
        "philox4x64_10",
        "raw_u64",
        "uniform_below",
    }
    imported_from_scalar: set[str] = set()
    plain_imports: set[str] = set()
    from_imports: set[tuple[str | None, int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"rng", "tetris_ballistic.engine.rng"}:
            imported_from_scalar.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            from_imports.update((node.module, node.level, alias.name) for alias in node.names)
        if isinstance(node, ast.Import):
            plain_imports.update(alias.name for alias in node.names)
            assert all(alias.name not in {"random", "secrets"} for alias in node.names)
        if isinstance(node, ast.Attribute):
            assert not (
                node.attr == "random" and isinstance(node.value, ast.Name) and node.value.id in {"_np", "np", "numpy"}
            )
    assert plain_imports == {"numpy"}
    assert from_imports == {
        ("__future__", 0, "annotations"),
        ("numba", 0, "njit"),
        ("rng", 1, "SemanticDraw"),
    }
    assert imported_from_scalar == {"SemanticDraw"}
    assert forbidden_scalar_helpers.isdisjoint(imported_from_scalar)

    called_names = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert forbidden_scalar_helpers.isdisjoint(called_names)

    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    uniform_kernel = functions["_uniform_below_kernel"]
    calls = [
        node.func.id
        for node in ast.walk(uniform_kernel)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "_raw_u64_kernel" in calls
    assert "_map_bounded_word_kernel" in calls
    assert calls.index("_raw_u64_kernel") < calls.index("_map_bounded_word_kernel")


def test_package_and_engine_roots_import_without_the_optional_numba_extra() -> None:
    code = """
import importlib
import sys

sys.modules["numba"] = None
import tetris_ballistic
import tetris_ballistic.engine

assert "tetris_ballistic.engine.rng_compiled" not in sys.modules
try:
    importlib.import_module("tetris_ballistic.engine.rng_compiled")
except ImportError as error:
    assert "hpc" in str(error)
else:
    raise AssertionError("the explicit compiled submodule unexpectedly imported without Numba")
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def test_results_are_independent_of_python_hash_seed_in_subprocesses() -> None:
    code = """
import json
from tetris_ballistic.engine.rng_compiled import philox4x64_10, raw_u64_from_key, uniform_below_from_key

key = (0x19A83E984B4A5059, 0xEBC32BDA16F60722)
raw = raw_u64_from_key(key=key, event_ordinal=0)
bounded = uniform_below_from_key(key=key, event_ordinal=0, n=257)
kat = philox4x64_10(counter=(0, 0, 0, 0), key=(0, 0))
print(json.dumps({
    "bounded": [bounded.value, bounded.accepted_rejection_ordinal],
    "kat": kat,
    "raw": raw,
}, sort_keys=True, separators=(",", ":")))
"""
    expected = json.dumps(
        {
            "bounded": [118, 0],
            "kat": [
                0x16554D9ECA36314C,
                0xDB20FE9D672D0FDC,
                0xD7E772CEE186176B,
                0x7E68B68AEC7BA23B,
            ],
            "raw": 0x75AB473CEF3D469F,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    project_root = Path(__file__).resolve().parents[1]
    outputs: list[str] = []
    for hash_seed in ("1", "8675309", "random"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = hash_seed
        environment["NUMBA_NUM_THREADS"] = "1"
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


def test_independent_oracle_does_not_call_scalar_or_compiled_rng_helpers() -> None:
    oracle_globals = {
        name
        for function in (_oracle_derive_key, _oracle_philox4x64_10, _oracle_raw_u64, _oracle_uniform_below)
        for name in function.__code__.co_names
    }
    assert not oracle_globals.intersection(
        {
            "scalar_rng",
            "compiled_rng",
            "SemanticDraw",
            "derive_stream_key",
            "philox4x64_10",
            "raw_u64",
            "raw_u64_from_key",
            "uniform_below",
            "uniform_below_from_key",
        }
    )


def test_conformance_receipt_and_parent_vector_digests_are_pinned() -> None:
    repository = Path(__file__).resolve().parents[1]
    semantic_vectors = repository / "docs" / "SEMANTIC-RNG-VECTORS.md"
    exact_selection_vectors = repository / "docs" / "EXACT-SELECTION-VECTORS.md"
    complete_event_vectors = repository / "docs" / "COMPLETE-EVENT-SELECTION-VECTORS.md"
    pre_vectors = repository / "docs" / "PRE-ONE-CELL-COUPLING-VECTORS.md"
    receipt = (repository / "docs" / "PRE-ONE-CELL-COMPILED-RNG-VECTORS.md").read_text(encoding="utf-8")

    assert sha256(semantic_vectors.read_bytes()).hexdigest() == (
        "913258f0cf07ab5c666778dec3263e2bc4af53830f2bda3d1689c4ab83518c34"
    )
    assert sha256(pre_vectors.read_bytes()).hexdigest() == (
        "74c1ab6e80befdc322bbc5a36efb91c2fa3f74d9e9f8c14bae3aa389b2b1eba3"
    )
    assert sha256(exact_selection_vectors.read_bytes()).hexdigest() == (
        "324f43f4a42a0bcf71af01eb1aab32d7c219b986d3bdd67cc888f2f5ed6f21a9"
    )
    assert sha256(complete_event_vectors.read_bytes()).hexdigest() == (
        "331a445c5dc278a79a61bfb6d89eaadf7ed4ec9763036d8a4602d4c1615f2839"
    )
    for required in (
        "9545ff6413f258be2f04c1d319d99aaef7521150",
        "aab5ebabf40003f63d6d87b24cbd2c8a02652e00cf8bad64226fd50586929183",
        "56-row base manifest",
        "EXACT-SELECTION-VECTORS.md",
        "COMPLETE-EVENT-SELECTION-VECTORS.md",
        "three supplementary",
        "ordinals one, two, and five",
        "n - 1",
        "_kernel_1x1.py",
    ):
        assert required in receipt
