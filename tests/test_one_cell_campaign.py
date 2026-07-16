"""Independent contract and adversarial tests for the PRE campaign identity.

The fixtures in this file deliberately do not call private production helpers.
They independently render the frozen protocol-shaped campaign and all nine
primitive task maps.  No numerical engine, campaign directory, bootstrap
matrix, scheduler, or Easley service is touched.
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
import inspect
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest

import tetris_ballistic.engine.one_cell_campaign as campaign_module
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_campaign import (
    OneCellBootstrapMatrixIdentity,
    OneCellCampaignAuthority,
    OneCellCampaignTask,
    OneCellCampaignValidationError,
    OneCellHorizonBranch,
    OneCellTaskMapIdentity,
    decode_one_cell_campaign_task,
    encode_one_cell_campaign_task_index,
    explain_one_cell_campaign_task,
    load_one_cell_campaign,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOFTWARE_PARENT = "87b99f8a9e41968d9aecbfc1f8af90dbb01fc90c"
_SOFTWARE_AUTHORITY = "b33cc0191298d80f0bdc944a3a5e444952873e37"
_HEX_A = "a" * 64
_HEX_B = "b" * 64
_HEX_C = "c" * 64
_SOURCE = "d" * 40

_PUBLIC_API = (
    "OneCellCampaignValidationError",
    "OneCellBootstrapMatrixIdentity",
    "OneCellTaskMapIdentity",
    "OneCellHorizonBranch",
    "OneCellCampaignAuthority",
    "OneCellCampaignTask",
    "load_one_cell_campaign",
    "encode_one_cell_campaign_task_index",
    "decode_one_cell_campaign_task",
    "explain_one_cell_campaign_task",
)

_RECORD_FIELDS = {
    OneCellBootstrapMatrixIdentity: (
        "cohort_id",
        "profile",
        "member_path",
        "shape",
        "seed",
        "generator",
        "bit_generator",
        "numpy_version",
        "distribution",
        "dtype",
        "byte_order",
        "order",
        "size_bytes",
        "sha256",
    ),
    OneCellTaskMapIdentity: (
        "task_map_id",
        "profile",
        "member_path",
        "wave",
        "role",
        "horizon_branch_id",
        "task_count",
        "size_bytes",
        "sha256",
    ),
    OneCellHorizonBranch: (
        "branch_id",
        "profile",
        "l_star",
        "confirmation_required",
        "confirmation_terminal_event_count",
        "p1_terminal_event_counts",
        "p1_task_map_id",
    ),
    OneCellCampaignAuthority: (
        "configuration_bytes",
        "configuration_sha256",
        "profile",
        "protocol_commit",
        "protocol_path",
        "protocol_blob",
        "protocol_sha256",
        "protocol_size_bytes",
        "bootstrap_matrices",
        "task_maps",
        "horizon_branches",
        "checkpoint_terminals",
        "task_map_members",
    ),
    OneCellCampaignTask: (
        "task_map_id",
        "task_map_sha256",
        "wave",
        "role",
        "included_in_inference",
        "task_index",
        "horizon_branch_id",
        "boundary_law",
        "width",
        "root_seed",
        "root_offset",
        "threshold_schedule_id",
        "threshold_schedule",
        "terminal_event_count",
        "checkpoint_event_counts",
        "checkpoint_vector_sha256",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_vector_sha256",
        "bootstrap_cohort_id",
        "bootstrap_population_index",
    ),
}

_PERIODIC = "periodic-v1"
_LEGACY = "hard-wall-legacy-asymmetric-v1"
_CORRECTED = "hard-wall-reflection-symmetric-v1"
_PRIMARY = (0, 1, 2, 5, 10, 25, 50, 100)
_B1 = (0, 5, 50, 100)
_B2_FULL = (5, 50, 90, 95, 98, 99)
_B2_HIGH = (90, 95, 98, 99)
_SNAPSHOT_INDICES = (0, 34, 68, 102, 136, 170, 204, 238, 273, 307, 341, 375, 409, 443, 477, 511)

_BASE_HORIZONS = {
    32: 17_378,
    64: 98_304,
    128: 556_092,
    256: 3_145_728,
    512: 17_794_925,
    1024: 100_663_296,
}
_DOUBLE_HORIZONS = {
    64: 196_608,
    128: 1_112_184,
    256: 6_291_456,
    512: 35_589_850,
    1024: 201_326_592,
}
_HISTORICAL_HORIZONS = {
    50: 55_000,
    80: 172_800,
    100: 300_000,
    150: 832_500,
    200: 1_720_000,
    250: 3_000_000,
    300: 4_680_000,
    400: 9_600_000,
    500: 17_000_000,
}

_VECTOR_HASHES = {
    17_378: (
        "c5f252e41428324b6a58b895a0ad65b6ddee5268151af5219d378c04d640dcb9",
        "79389924acde634cd0cddaefbfc6e2bb6839a68a763effb9496588c2903b507d",
    ),
    98_304: (
        "b8d26f0e73cf752314bf7ee3388aeeea0ee41b4819a42127fd68e5b135827032",
        "96e48ce2fd2c948f44f2961ad03ba1b766e7c87e6472eeadaffd8a404738415d",
    ),
    556_092: (
        "41578b77509fe146d70408aaf55272fe5bac38ef616eb24c035d63b63302feb6",
        "7486fb0f92727fc7e4dd67ba3f1c085362777a199aaa087fdac7ceb137fcc9f9",
    ),
    3_145_728: (
        "869b84cade7b61149518e6af883b6d3a4deaf98a9523767ff25006c0987409a6",
        "fd240cc0be43c3d1e905cb9595e4582e573949acc0326c383da01565ab65f7c3",
    ),
    17_794_925: (
        "9cd08fa3a59c3675010d9b74ad0f58b865a01319897d455b1b136d9bdd313d93",
        "956200791790695ff3fbdf84bab9186535d7610345cf9906bbe419cf9989ba7c",
    ),
    100_663_296: (
        "994a06cf3188ab1107e78711538d440d02dfa53613f0d0076b4698a0b33a4fa5",
        "14dad3915d170fbdb5b1dc5dcf49e57a16705f53e5577b07ab776f1bac6f8bf0",
    ),
    196_608: (
        "936a8fccb9627eeeb83c8f0b1e4bca18bd1c71ab0ce059e64208429756dfc004",
        "3a42f697a184cc3a2ded8d21176fc0d4e2527a8c16a382e83487d8583c778ae6",
    ),
    1_112_184: (
        "248edcaa55f0d2f9697f85c22543db3f546efd7cabc0e28e2ec17c2f7ef19309",
        "09b09e3361eb3f0b4d6b6fdc7f70c3a25e1b55698472740241cec9e09b9232d0",
    ),
    6_291_456: (
        "82839103c39b0ca7923b248d20bd8cb028b5b558b45173cca0f85270cdcd59d4",
        "86efc0ca42e97478ae47c750694ae9ae535fdbd8a3727dcebd961545bc5a1183",
    ),
    35_589_850: (
        "c525069e5975a8ee388106f5384aa9d0653fabd71c1871f224016272bedd8456",
        "d2e2b0fc33004810f742944bb91d68e9a25c75df161a85b8215956db8fb05251",
    ),
    201_326_592: (
        "f4bae89fe9c8c021feb70141cb56ffaecfff5306c0afa10abd42041658d1726c",
        "0c18e9ef5c63a5fab0ca580654a05c3194119ebf31f30471a5ebb42b7cf7074c",
    ),
    55_000: (
        "8a03e3f93b3e42bd0f910ad4fbaafdce0dfa4ed2046ae82b0b4bc90340ad6651",
        "0d16f0029d3005d7f6a4e7ca44edfd423efb3e6813bb083f19bb9bec39aefd18",
    ),
    172_800: (
        "701e6c91bbb7b820116c92bfccc77345c1ca5e3d716d63fe65dc3e969ece1009",
        "08e08b8a18e56e40f0d42b57a68e12824c57d54459d6a2ff55ea694ffd828d6a",
    ),
    300_000: (
        "7b7f858cb2d8f5b17dfff5ec260fb58e6db72ea5e4215813bc14eb5858d433ed",
        "cb3898903dce3de1ff40e180a048497738377f06096f11dd3961599242b05d79",
    ),
    832_500: (
        "2c075c44db4bbc2631311ae3ae951588baf21c478996d42a6f407f8829f16afe",
        "95509683f214af140a151757e32d5328a42af1cf0cdcac1cc3c0ca4f0f70ae50",
    ),
    1_720_000: (
        "674be7c67dbb7c3f5d862b56aa4b7b8e28eba852a3a011464996ed613b80dc45",
        "d9168485f4a6038031f0acad624403158f2b87adb7aa812e5606699e87a837c2",
    ),
    3_000_000: (
        "22b9c06b7a000ac0551f2fd0c24b41df2810e7b463b44eec18e977cfd28678aa",
        "252961c6e2377531ca839458b2a6afd93abda7ed05ca9be74c96a484683c926f",
    ),
    4_680_000: (
        "b255c3ce257304146d9164a9fb42d4b728b5193db6381136f1d9c3be862ec57e",
        "6e9533e9ea6e0d54671b080696b463bd696d3898f7dcf803eaeeb4f0e68f6428",
    ),
    9_600_000: (
        "534fbd426e7a98b52748a4613257cb02d82cb136ee89fef895d58a958a0fbdd7",
        "5d24d8fd1d5d03ee6cb9e752e51fa0379c324ae1262ac20305d1571c81ee9f55",
    ),
    17_000_000: (
        "11e113a51521f2b9380df8f267e1463b98c7ff76a68edd3cb37d4ebd920ffedd",
        "862af4374766af7dede636fb1a2e195b0c827b3a5faa44ea4e1fea62d0fd4765",
    ),
}


@dataclass(frozen=True, slots=True)
class _OracleMapSpec:
    task_map_id: str
    member_path: str
    wave: str
    role: str
    branch: str
    boundaries: tuple[str, ...]
    widths: tuple[int, ...]
    root_start: int
    root_count: int
    included: bool
    bootstrap: str | None

    @property
    def count(self) -> int:
        return len(self.boundaries) * len(self.widths) * self.root_count


_MAP_SPECS = (
    _OracleMapSpec(
        "f0",
        "task-maps/f0.jsonl",
        "f0",
        "excluded-forensic-canary",
        "fixed",
        (_LEGACY, _CORRECTED),
        (50, 500),
        3_100_000,
        2,
        False,
        None,
    ),
    _OracleMapSpec(
        "p0-initial",
        "task-maps/p0-initial.jsonl",
        "p0",
        "excluded-horizon-pilot",
        "fixed",
        (_PERIODIC,),
        (64, 256, 1024),
        1_000_000,
        16,
        False,
        "p0",
    ),
    _OracleMapSpec(
        "p0-confirmation",
        "task-maps/p0-confirmation.jsonl",
        "p0",
        "excluded-conditional-confirmation",
        "conditional-doubling",
        (_PERIODIC,),
        (1024,),
        1_000_016,
        1,
        False,
        None,
    ),
    _OracleMapSpec(
        "p1-no-l-star",
        "task-maps/p1-no-l-star.jsonl",
        "p1",
        "clean-primary",
        "p1-no-l-star",
        (_PERIODIC,),
        (64, 128, 256, 512, 1024),
        0,
        96,
        True,
        "p1",
    ),
    _OracleMapSpec(
        "p1-l-star-64",
        "task-maps/p1-l-star-64.jsonl",
        "p1",
        "clean-primary",
        "p1-l-star-64",
        (_PERIODIC,),
        (64, 128, 256, 512, 1024),
        0,
        96,
        True,
        "p1",
    ),
    _OracleMapSpec(
        "p1-l-star-256",
        "task-maps/p1-l-star-256.jsonl",
        "p1",
        "clean-primary",
        "p1-l-star-256",
        (_PERIODIC,),
        (64, 128, 256, 512, 1024),
        0,
        96,
        True,
        "p1",
    ),
    _OracleMapSpec(
        "p1-l-star-1024",
        "task-maps/p1-l-star-1024.jsonl",
        "p1",
        "clean-primary",
        "p1-l-star-1024",
        (_PERIODIC,),
        (64, 128, 256, 512, 1024),
        0,
        96,
        True,
        "p1",
    ),
    _OracleMapSpec(
        "b1",
        "task-maps/b1.jsonl",
        "b1",
        "boundary-forensic",
        "fixed",
        (_LEGACY, _CORRECTED, _PERIODIC),
        (32, 64, 128, 256),
        2_000_000,
        32,
        True,
        "b1",
    ),
    _OracleMapSpec(
        "b2",
        "task-maps/b2.jsonl",
        "b2",
        "historical-grid-correction",
        "fixed",
        (_LEGACY, _CORRECTED),
        (50, 80, 100, 150, 200, 250, 300, 400, 500),
        3_000_000,
        100,
        True,
        "b2",
    ),
)

_BOOTSTRAPS = (
    ("p0", "bootstrap/p0.u16le", (10_000, 16), 2_026_071_500, 320_000),
    ("p1", "bootstrap/p1.u16le", (10_000, 96), 2_026_071_501, 1_920_000),
    ("b1", "bootstrap/b1.u16le", (10_000, 32), 2_026_071_502, 640_000),
    ("b2", "bootstrap/b2.u16le", (10_000, 100), 2_026_071_503, 2_000_000),
)


class _HostileInt(int):
    pass


class _HostileBytes(bytes):
    pass


class _HostileString(str):
    pass


def _canonical_json(value: object, *, newline: bool = True) -> bytes:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return payload + (b"\n" if newline else b"")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# Independent exact-rounding oracle: the floating estimate is never trusted;
# the two integer half-step inequalities make the final decision.
def _oracle_rounded_power(*, base: int, exponent: int) -> int:
    scaled = (1 << 383) * pow(base, exponent)
    candidate = max(1, min(base, int(math.exp(math.log(base) * exponent / 383.0) + 0.5)))
    while scaled < pow(2 * candidate - 1, 383):
        candidate -= 1
    while scaled >= pow(2 * candidate + 1, 383):
        candidate += 1
    assert pow(2 * candidate - 1, 383) <= scaled < pow(2 * candidate + 1, 383)
    return candidate


@lru_cache(maxsize=None)
def _oracle_schedule(terminal: int) -> tuple[tuple[int, ...], tuple[int, ...], str, str]:
    midpoint = (terminal + 1) // 2
    early_terminal = midpoint - 1
    early = [1]
    for index in range(1, 384):
        rounded = _oracle_rounded_power(base=early_terminal, exponent=index)
        early.append(min(early_terminal - (383 - index), max(early[-1] + 1, rounded)))
    late = tuple(midpoint + index * (terminal - midpoint) // 127 for index in range(128))
    checkpoints = tuple(early) + late
    snapshots = tuple(checkpoints[index] for index in _SNAPSHOT_INDICES)
    checkpoint_hash = _sha256(
        _canonical_json(
            {
                "event_counts": list(checkpoints),
                "profile": "tetris-pre-one-cell-checkpoint-vector@1",
            },
            newline=False,
        )
    )
    snapshot_hash = _sha256(
        _canonical_json(
            {
                "checkpoint_indices": list(_SNAPSHOT_INDICES),
                "event_counts": list(snapshots),
                "profile": "tetris-pre-one-cell-snapshot-vector@1",
            },
            newline=False,
        )
    )
    return checkpoints, snapshots, checkpoint_hash, snapshot_hash


def _oracle_vector_record(terminal: int) -> dict[str, object]:
    checkpoints, snapshots, checkpoint_hash, snapshot_hash = _oracle_schedule(terminal)
    return {
        "checkpoint_event_counts": list(checkpoints),
        "checkpoint_vector_sha256": checkpoint_hash,
        "snapshot_checkpoint_indices": list(_SNAPSHOT_INDICES),
        "snapshot_event_counts": list(snapshots),
        "snapshot_vector_sha256": snapshot_hash,
        "terminal_event_count": terminal,
    }


def _oracle_terminal(spec: _OracleMapSpec, width: int) -> int:
    if spec.task_map_id == "p0-confirmation":
        return 201_326_592
    if spec.task_map_id.startswith("p1-"):
        if spec.task_map_id == "p1-no-l-star":
            return _BASE_HORIZONS[width]
        l_star = int(spec.task_map_id.rsplit("-", 1)[1])
        return _DOUBLE_HORIZONS[width] if width >= l_star else _BASE_HORIZONS[width]
    if spec.task_map_id in {"f0", "b2"}:
        return _HISTORICAL_HORIZONS[width]
    return _BASE_HORIZONS[width]


def _oracle_schedule_id(spec: _OracleMapSpec, width: int) -> str:
    if spec.task_map_id == "b1":
        return "b1"
    if spec.task_map_id in {"f0", "b2"}:
        return "b2-high" if width >= 400 else "b2-full"
    return "primary"


def _oracle_row(spec: _OracleMapSpec, task_index: int) -> dict[str, object]:
    per_boundary = len(spec.widths) * spec.root_count
    boundary_index, remainder = divmod(task_index, per_boundary)
    width_index, root_offset = divmod(remainder, spec.root_count)
    width = spec.widths[width_index]
    return {
        "boundary_law": spec.boundaries[boundary_index],
        "profile": "tetris-pre-one-cell-task-row@1",
        "root_offset": root_offset,
        "root_seed": spec.root_start + root_offset,
        "task_index": task_index,
        "terminal_event_count": _oracle_terminal(spec, width),
        "threshold_schedule_id": _oracle_schedule_id(spec, width),
        "width": width,
    }


def _oracle_map_bytes(spec: _OracleMapSpec) -> bytes:
    return b"".join(_canonical_json(_oracle_row(spec, index)) for index in range(spec.count))


@lru_cache(maxsize=1)
def _base_map_members() -> tuple[tuple[str, bytes], ...]:
    return tuple((spec.member_path, _oracle_map_bytes(spec)) for spec in _MAP_SPECS)


def _bootstrap_records() -> list[dict[str, object]]:
    return [
        {
            "bit_generator": "PCG64DXSM",
            "byte_order": "little",
            "cohort_id": cohort,
            "distribution": "integers-half-open-one-call-v1",
            "dtype": "uint16",
            "generator": "numpy.random.Generator",
            "member_path": path,
            "numpy_version": "2.1.0",
            "order": "C",
            "profile": "tetris-pre-one-cell-bootstrap-matrix@1",
            "seed": seed,
            "sha256": _sha256(f"synthetic-ineligible-{cohort}".encode()),
            "shape": list(shape),
            "size_bytes": size,
        }
        for cohort, path, shape, seed, size in _BOOTSTRAPS
    ]


def _task_map_records(members: tuple[tuple[str, bytes], ...]) -> list[dict[str, object]]:
    by_path = dict(members)
    return [
        {
            "horizon_branch_id": spec.branch,
            "member_path": spec.member_path,
            "profile": "tetris-pre-one-cell-task-map@1",
            "role": spec.role,
            "sha256": _sha256(by_path[spec.member_path]),
            "size_bytes": len(by_path[spec.member_path]),
            "task_count": spec.count,
            "task_map_id": spec.task_map_id,
            "wave": spec.wave,
        }
        for spec in _MAP_SPECS
    ]


def _branch_records() -> list[dict[str, object]]:
    result = []
    for l_star in (None, 64, 256, 1024):
        branch_id = "p1-no-l-star" if l_star is None else f"p1-l-star-{l_star}"
        terminals = [
            {
                "terminal_event_count": (
                    _BASE_HORIZONS[width] if l_star is None or width < l_star else _DOUBLE_HORIZONS[width]
                ),
                "width": width,
            }
            for width in (64, 128, 256, 512, 1024)
        ]
        result.append(
            {
                "branch_id": branch_id,
                "confirmation_required": l_star is not None,
                "confirmation_terminal_event_count": None if l_star is None else 201_326_592,
                "l_star": l_star,
                "p1_task_map_id": branch_id,
                "p1_terminal_event_counts": terminals,
                "profile": "tetris-pre-one-cell-horizon-branch@1",
            }
        )
    return result


def _protocol_record() -> dict[str, object]:
    return {
        "article_commit": "85404aee4dab7ade81c6893fac9f34aeaddf50dd",
        "protocol_blob": "b7b654bb8d2809c409ce6ca24eb21d3afebf7885",
        "protocol_path": "PRE-DISCOVERY-PROTOCOL.md",
        "protocol_sha256": "ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358",
        "protocol_size_bytes": 44_883,
    }


def _model_record() -> dict[str, object]:
    return {
        "boundary_law_order": [_PERIODIC, _LEGACY, _CORRECTED],
        "clean_model_id": "one-cell-rd-bd-periodic-v1",
        "contact_denominator": 100,
        "counter_fields": ["event-ordinal-zero-based", "rejection-ordinal", "zero", "zero"],
        "coupling_group": "pre-one-cell-discovery-v1",
        "initial_height": 0,
        "rng_algorithm": "semantic-philox4x64-10-v1",
        "root_seed_encoding": "unsigned-128-numerical-v1",
        "stream_order": ["launch", "contact"],
        "threshold_schedules": [
            {"schedule_id": "primary", "thresholds": list(_PRIMARY)},
            {"schedule_id": "b1", "thresholds": list(_B1)},
            {"schedule_id": "b2-full", "thresholds": list(_B2_FULL)},
            {"schedule_id": "b2-high", "thresholds": list(_B2_HIGH)},
        ],
    }


def _inventory_records() -> list[dict[str, object]]:
    return [
        {
            "arm_count": 40,
            "boundary_order": [_LEGACY, _CORRECTED],
            "included_in_inference": False,
            "inventory_id": "f0",
            "role": "excluded-forensic-canary",
            "root_count": 2,
            "root_start": 3_100_000,
            "task_count": 8,
            "task_unit": "boundary-width-root-cell",
            "width_order": [50, 500],
        },
        {
            "arm_count": 384,
            "boundary_order": [_PERIODIC],
            "included_in_inference": False,
            "inventory_id": "p0-initial",
            "role": "excluded-horizon-pilot",
            "root_count": 16,
            "root_start": 1_000_000,
            "task_count": 48,
            "task_unit": "width-root-cell",
            "width_order": [64, 256, 1024],
        },
        {
            "arm_count": 8,
            "boundary_order": [_PERIODIC],
            "included_in_inference": False,
            "inventory_id": "p0-confirmation",
            "role": "excluded-conditional-confirmation",
            "root_count": 1,
            "root_start": 1_000_016,
            "task_count": 1,
            "task_unit": "conditional-width-root-cell",
            "width_order": [1024],
        },
        {
            "arm_count": 3840,
            "boundary_order": [_PERIODIC],
            "included_in_inference": True,
            "inventory_id": "p1",
            "role": "clean-primary",
            "root_count": 96,
            "root_start": 0,
            "task_count": 480,
            "task_unit": "width-root-cell",
            "width_order": [64, 128, 256, 512, 1024],
        },
        {
            "arm_count": 1536,
            "boundary_order": [_LEGACY, _CORRECTED, _PERIODIC],
            "included_in_inference": True,
            "inventory_id": "b1",
            "role": "boundary-forensic",
            "root_count": 32,
            "root_start": 2_000_000,
            "task_count": 384,
            "task_unit": "boundary-width-root-cell",
            "width_order": [32, 64, 128, 256],
        },
        {
            "arm_count": 10_000,
            "boundary_order": [_LEGACY, _CORRECTED],
            "included_in_inference": True,
            "inventory_id": "b2",
            "role": "historical-grid-correction",
            "root_count": 100,
            "root_start": 3_000_000,
            "task_count": 1800,
            "task_unit": "boundary-width-root-cell",
            "width_order": [50, 80, 100, 150, 200, 250, 300, 400, 500],
        },
    ]


def _execution_record() -> dict[str, object]:
    return {
        "analysis_and_stop_rules": {
            "admission_sections": [
                "Common correctness certification",
                "B2 forensic admission",
                "Full clean-study admission",
            ],
            "analysis_section": "Locked analysis",
            "authority": "exclusive-frozen-protocol-blob-v1",
            "boolean_gate_order": ["A", "D", "E", "F", "B", "M", "X"],
            "pre_science_eligible": "A and D and E and F and B and (M or X)",
            "release_gate": "R",
            "stop_rule": "stop-if-any-A-D-E-F-B-fails-or-both-M-X-fail-v1",
        },
        "integer_bounds": {
            "maximum_width": 1024,
            "minimum_terminal_event_count": 769,
            "minimum_width": 3,
            "terminal_event_count_upper_exclusive": 1 << 64,
            "width_times_terminal_squared_upper_exclusive": 1 << 128,
            "width_times_terminal_upper_exclusive": 1 << 64,
        },
        "inventories": _inventory_records(),
        "output_caps_bytes": {
            "all_final_upper_exclusive": 6 << 30,
            "all_private_upper_exclusive": 16 << 30,
            "b2_final_upper_exclusive": 4 << 30,
            "p1_final_upper_exclusive": 1 << 30,
        },
        "persistence": {
            "checkpoint_count": 512,
            "completion_marker": "final.manifest.json",
            "final_profile": "tetris-ballistic/pre-one-cell-final@1",
            "raw_per_event_tape_retained": False,
            "recovery_cadence": 1 << 20,
            "recovery_profile": "tetris-ballistic/pre-one-cell-checkpoint@1",
            "retained_primitives": [
                "event-count",
                "height-sum",
                "height-square-sum",
                "void-volume",
                "endpoint-selection-count",
                "positive-gap-trigger-count",
                "gap-sum",
                "maximum-gap",
                "causal-side-counts",
                "causal-gap-sums",
                "endpoint-equality-mask-counts",
                "gap-histogram",
                "periodic-seam-equality-count",
                "interface-snapshots",
            ],
            "snapshot_count": 16,
        },
        "resampling_unit": "whole-root-v1",
    }


def _campaign_document(members: tuple[tuple[str, bytes], ...]) -> dict[str, object]:
    return {
        "bootstrap_matrices": _bootstrap_records(),
        "checkpoint_vectors": [_oracle_vector_record(terminal) for terminal in _VECTOR_HASHES],
        "execution": _execution_record(),
        "horizon_branches": _branch_records(),
        "model": _model_record(),
        "profile": "tetris-pre-one-cell-campaign@1",
        "protocol": _protocol_record(),
        "task_maps": _task_map_records(members),
    }


@lru_cache(maxsize=1)
def _base_fixture() -> tuple[bytes, tuple[tuple[str, bytes], ...]]:
    members = _base_map_members()
    return _canonical_json(_campaign_document(members)), members


def _fixture_with_members(
    members: tuple[tuple[str, bytes], ...],
    *,
    mutate_document=None,
) -> tuple[bytes, tuple[tuple[str, bytes], ...]]:
    document = _campaign_document(members)
    if mutate_document is not None:
        mutate_document(document)
    return _canonical_json(document), members


def _load_fixture() -> OneCellCampaignAuthority:
    configuration_bytes, members = _base_fixture()
    return load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )


def _spec(task_map_id: str) -> _OracleMapSpec:
    return next(spec for spec in _MAP_SPECS if spec.task_map_id == task_map_id)


def _replace_member(
    members: tuple[tuple[str, bytes], ...],
    index: int,
    *,
    path: str | None = None,
    payload: bytes | None = None,
) -> tuple[tuple[str, bytes], ...]:
    result = list(members)
    old_path, old_payload = result[index]
    result[index] = (
        old_path if path is None else path,
        old_payload if payload is None else payload,
    )
    return tuple(result)


def _replace_map_row(
    members: tuple[tuple[str, bytes], ...],
    map_index: int,
    row_index: int,
    *,
    field: str,
    value: object,
) -> tuple[tuple[str, bytes], ...]:
    path, payload = members[map_index]
    lines = payload.splitlines()
    row = json.loads(lines[row_index])
    row[field] = value
    lines[row_index] = _canonical_json(row, newline=False)
    return _replace_member(
        members,
        map_index,
        path=path,
        payload=b"\n".join(lines) + b"\n",
    )


@lru_cache(maxsize=1)
def _decoded_fixture_document(configuration_bytes: bytes) -> dict[str, object]:
    return json.loads(configuration_bytes)


def _oracle_explanation(
    *,
    configuration_bytes: bytes,
    task_map_id: str,
    task_index: int,
    deployment_lock_sha256: str,
    software_commit: str,
    wheel_sha256: str,
    branch_decision_sha256: str | None,
) -> bytes:
    spec = _spec(task_map_id)
    row = _oracle_row(spec, task_index)
    document = _decoded_fixture_document(configuration_bytes)
    task_map = next(item for item in document["task_maps"] if item["task_map_id"] == task_map_id)
    vector = next(
        item for item in document["checkpoint_vectors"] if item["terminal_event_count"] == row["terminal_event_count"]
    )
    if spec.bootstrap is None:
        bootstrap: dict[str, object] = {"applicable": False}
    else:
        descriptor = next(item for item in document["bootstrap_matrices"] if item["cohort_id"] == spec.bootstrap)
        bootstrap = {
            "applicable": True,
            **descriptor,
            "population_index": row["root_offset"],
        }
    branch_bound = task_map_id == "p0-confirmation" or task_map_id.startswith("p1-")
    if branch_bound:
        horizon_plan = {
            "branch_decision_sha256": branch_decision_sha256,
            "kind": "branch-decision",
            "plan_id": spec.branch,
        }
    else:
        horizon_plan = {"kind": "fixed", "plan_id": spec.branch}
    record = {
        "bootstrap": bootstrap,
        "checkpoint_plan": {
            "checkpoint_event_counts": vector["checkpoint_event_counts"],
            "checkpoint_vector_sha256": vector["checkpoint_vector_sha256"],
            "snapshot_checkpoint_indices": vector["snapshot_checkpoint_indices"],
            "snapshot_event_counts": vector["snapshot_event_counts"],
            "snapshot_vector_sha256": vector["snapshot_vector_sha256"],
        },
        "configuration_sha256": _sha256(configuration_bytes),
        "deployment_lock_sha256": deployment_lock_sha256,
        "horizon_plan": horizon_plan,
        "protocol": _protocol_record(),
        "software_commit": software_commit,
        "task": {
            "boundary_law": row["boundary_law"],
            "included_in_inference": spec.included,
            "role": spec.role,
            "root_offset": row["root_offset"],
            "root_seed": row["root_seed"],
            "task_index": row["task_index"],
            "terminal_event_count": row["terminal_event_count"],
            "threshold_schedule": list(
                {
                    "primary": _PRIMARY,
                    "b1": _B1,
                    "b2-full": _B2_FULL,
                    "b2-high": _B2_HIGH,
                }[row["threshold_schedule_id"]]
            ),
            "threshold_schedule_id": row["threshold_schedule_id"],
            "wave": spec.wave,
            "width": row["width"],
        },
        "task_map": {
            "member_path": task_map["member_path"],
            "sha256": task_map["sha256"],
            "size_bytes": task_map["size_bytes"],
            "task_map_id": task_map_id,
        },
        "wheel_sha256": wheel_sha256,
    }
    record_bytes = _canonical_json(record, newline=False)
    return _canonical_json(
        {
            "profile": "tetris-pre-one-cell-scientific-identity@1",
            "record": record,
            "sha256": _sha256(record_bytes),
        },
        newline=False,
    )


def _mutate_semantic_document(case: str, document: dict[str, object]) -> None:
    if case == "unknown-top-level-key":
        document["extension"] = None
    elif case == "missing-top-level-key":
        del document["model"]
    elif case == "wrong-profile":
        document["profile"] = "tetris-pre-one-cell-campaign@2"
    elif case == "wrong-protocol":
        document["protocol"]["protocol_size_bytes"] = 44_884
    elif case == "wrong-model-order":
        document["model"]["boundary_law_order"].reverse()
    elif case == "bool-as-integer":
        document["protocol"]["protocol_size_bytes"] = True
    elif case == "integer-as-boolean":
        document["execution"]["persistence"]["raw_per_event_tape_retained"] = 0
    elif case == "bootstrap-order":
        document["bootstrap_matrices"].reverse()
    elif case == "task-map-order":
        document["task_maps"].reverse()
    elif case == "branch-order":
        document["horizon_branches"].reverse()
    elif case == "vector-order":
        document["checkpoint_vectors"].reverse()
    else:
        raise AssertionError(case)


def _noncanonical_configuration(case: str, configuration_bytes: bytes) -> bytes:
    if case == "missing-lf":
        return configuration_bytes[:-1]
    if case == "extra-lf":
        return configuration_bytes + b"\n"
    if case == "crlf":
        return configuration_bytes[:-1] + b"\r\n"
    if case == "leading-space":
        return b" " + configuration_bytes
    if case == "bom":
        return b"\xef\xbb\xbf" + configuration_bytes
    if case == "invalid-utf8":
        return b"\xff" + configuration_bytes
    if case == "pretty-json":
        return json.dumps(json.loads(configuration_bytes), sort_keys=True, indent=1).encode() + b"\n"
    if case == "duplicate-key":
        return configuration_bytes.replace(
            b'{"bootstrap_matrices":',
            b'{"bootstrap_matrices":[],"bootstrap_matrices":',
            1,
        )
    if case == "alternate-escape":
        return configuration_bytes.replace(b"PCG64DXSM", b"PCG64D\\u0058SM", 1)
    if case == "float":
        return configuration_bytes.replace(b'"protocol_size_bytes":44883', b'"protocol_size_bytes":44883.0', 1)
    if case == "nan":
        return configuration_bytes.replace(b'"protocol_size_bytes":44883', b'"protocol_size_bytes":NaN', 1)
    if case == "leading-zero":
        return configuration_bytes.replace(b'"protocol_size_bytes":44883', b'"protocol_size_bytes":044883', 1)
    if case == "yaml-anchor":
        return b"&campaign " + configuration_bytes
    raise AssertionError(case)


def test_public_surface_signatures_and_record_contracts_are_exact() -> None:
    assert tuple(campaign_module.__all__) == _PUBLIC_API
    assert issubclass(OneCellCampaignValidationError, RuntimeError)
    for record_type, expected_fields in _RECORD_FIELDS.items():
        fields = dataclasses.fields(record_type)
        assert tuple(field.name for field in fields) == expected_fields
        assert all(field.kw_only for field in fields)
        assert record_type.__dataclass_params__.frozen is True
        assert "__dict__" not in record_type.__slots__
        with pytest.raises(TypeError):
            record_type(object())

    expected_parameters = {
        load_one_cell_campaign: ("configuration_bytes", "task_map_members"),
        encode_one_cell_campaign_task_index: (
            "campaign",
            "task_map_id",
            "boundary_law",
            "width",
            "root_seed",
        ),
        decode_one_cell_campaign_task: ("campaign", "task_map_id", "task_index"),
        explain_one_cell_campaign_task: (
            "campaign",
            "task_map_id",
            "task_index",
            "deployment_lock_sha256",
            "software_commit",
            "wheel_sha256",
            "branch_decision_sha256",
        ),
    }
    for function, names in expected_parameters.items():
        parameters = tuple(inspect.signature(function).parameters.values())
        assert tuple(parameter.name for parameter in parameters) == names
        assert all(parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters)
    assert inspect.signature(explain_one_cell_campaign_task).parameters["branch_decision_sha256"].default is None


def test_load_preserves_exact_held_bytes_and_returns_defensive_frozen_snapshots() -> None:
    configuration_bytes, members = _base_fixture()
    first = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    second = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert first == second
    assert first is not second
    assert first.configuration_bytes is configuration_bytes
    assert first.configuration_sha256 == _sha256(configuration_bytes)
    assert first.task_map_members == members
    assert all(actual[1] is supplied[1] for actual, supplied in zip(first.task_map_members, members))
    assert first.bootstrap_matrices == second.bootstrap_matrices
    assert all(left is not right for left, right in zip(first.bootstrap_matrices, second.bootstrap_matrices))
    assert all(left is not right for left, right in zip(first.task_maps, second.task_maps))
    assert all(left is not right for left, right in zip(first.horizon_branches, second.horizon_branches))

    task = decode_one_cell_campaign_task(campaign=first, task_map_id="b2", task_index=1799)
    records = (
        first,
        *first.bootstrap_matrices,
        *first.task_maps,
        *first.horizon_branches,
        task,
    )
    for record in records:
        assert not hasattr(record, "__dict__")
        field = dataclasses.fields(record)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(record, field, getattr(record, field))


def test_loaded_campaign_inventory_and_protocol_authority_are_exact() -> None:
    campaign = _load_fixture()
    configuration_bytes, members = _base_fixture()
    assert campaign.profile == "tetris-pre-one-cell-campaign@1"
    assert campaign.protocol_commit == "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
    assert campaign.protocol_path == "PRE-DISCOVERY-PROTOCOL.md"
    assert campaign.protocol_blob == "b7b654bb8d2809c409ce6ca24eb21d3afebf7885"
    assert campaign.protocol_sha256 == "ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358"
    assert campaign.protocol_size_bytes == 44_883
    assert campaign.configuration_bytes == configuration_bytes
    assert tuple(item.cohort_id for item in campaign.bootstrap_matrices) == tuple(item[0] for item in _BOOTSTRAPS)
    assert tuple(item.shape for item in campaign.bootstrap_matrices) == tuple(item[2] for item in _BOOTSTRAPS)
    assert tuple(item.task_map_id for item in campaign.task_maps) == tuple(spec.task_map_id for spec in _MAP_SPECS)
    assert tuple(item.member_path for item in campaign.task_maps) == tuple(spec.member_path for spec in _MAP_SPECS)
    assert tuple(item.task_count for item in campaign.task_maps) == tuple(spec.count for spec in _MAP_SPECS)
    assert tuple(item.sha256 for item in campaign.task_maps) == tuple(_sha256(payload) for _, payload in members)
    assert tuple(item.branch_id for item in campaign.horizon_branches) == (
        "p1-no-l-star",
        "p1-l-star-64",
        "p1-l-star-256",
        "p1-l-star-1024",
    )
    assert campaign.checkpoint_terminals == tuple(_VECTOR_HASHES)


def test_all_twenty_literal_vector_pairs_match_the_independent_integer_oracle() -> None:
    configuration_bytes, _ = _base_fixture()
    document = json.loads(configuration_bytes)
    records = document["checkpoint_vectors"]
    assert len(records) == 20
    assert tuple(record["terminal_event_count"] for record in records) == tuple(_VECTOR_HASHES)
    for record in records:
        terminal = record["terminal_event_count"]
        checkpoints, snapshots, checkpoint_hash, snapshot_hash = _oracle_schedule(terminal)
        assert tuple(record["checkpoint_event_counts"]) == checkpoints
        assert tuple(record["snapshot_checkpoint_indices"]) == _SNAPSHOT_INDICES
        assert tuple(record["snapshot_event_counts"]) == snapshots
        assert (checkpoint_hash, snapshot_hash) == _VECTOR_HASHES[terminal]
        assert record["checkpoint_vector_sha256"] == checkpoint_hash
        assert record["snapshot_vector_sha256"] == snapshot_hash
        assert len(checkpoints) == 512
        assert len(snapshots) == 16
        assert checkpoints[0] == 1
        assert checkpoints[-1] == terminal
        assert all(left < right for left, right in zip(checkpoints, checkpoints[1:]))


@pytest.mark.parametrize(
    "bad_configuration",
    [None, True, "campaign", bytearray(b"{}\n"), memoryview(b"{}\n"), _HostileBytes(b"{}\n")],
)
def test_load_rejects_nonexact_configuration_byte_types(bad_configuration: object) -> None:
    _, members = _base_fixture()
    with pytest.raises(TypeError):
        load_one_cell_campaign(
            configuration_bytes=bad_configuration,
            task_map_members=members,
        )


def test_configuration_size_bounds_are_checked_before_json_decode() -> None:
    _, members = _base_fixture()
    for payload in (b"", b"x" * ((1 << 20) + 1)):
        with pytest.raises(ValueError):
            load_one_cell_campaign(
                configuration_bytes=payload,
                task_map_members=members,
            )


@pytest.mark.parametrize(
    "case",
    [
        "missing-lf",
        "extra-lf",
        "crlf",
        "leading-space",
        "bom",
        "invalid-utf8",
        "pretty-json",
        "duplicate-key",
        "alternate-escape",
        "float",
        "nan",
        "leading-zero",
        "yaml-anchor",
    ],
)
def test_noncanonical_json_and_general_yaml_spellings_fail_closed(case: str) -> None:
    configuration_bytes, members = _base_fixture()
    hostile = _noncanonical_configuration(case, configuration_bytes)
    assert hostile != configuration_bytes
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=hostile,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    "payload",
    [
        b'{"integer":11111111111111111111111111111111111111111}\n',
        _canonical_json([0] * 40_001),
        _canonical_json({"nested": [[[[[[[[[[[[[[[[[[[[[[[[[None]]]]]]]]]]]]]]]]]]]]]]]]]}),
    ],
    ids=("integer-token-limit", "node-limit", "depth-limit"),
)
def test_json_resource_bounds_fail_before_semantic_construction(payload: bytes) -> None:
    _, members = _base_fixture()
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=payload,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    "case",
    [
        "unknown-top-level-key",
        "missing-top-level-key",
        "wrong-profile",
        "wrong-protocol",
        "wrong-model-order",
        "bool-as-integer",
        "integer-as-boolean",
        "bootstrap-order",
        "task-map-order",
        "branch-order",
        "vector-order",
    ],
)
def test_exact_key_sets_fixed_values_types_and_orders_are_enforced(case: str) -> None:
    _, members = _base_fixture()
    configuration_bytes, members = _fixture_with_members(
        members,
        mutate_document=lambda document: _mutate_semantic_document(case, document),
    )
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    "member_path",
    [
        "/bootstrap/p0.u16le",
        "../p0.u16le",
        "bootstrap/../p0.u16le",
        "bootstrap/./p0.u16le",
        "bootstrap//p0.u16le",
        "bootstrap\\p0.u16le",
        "Bootstrap/p0.u16le",
        "bootstrap/p0 u16le",
        f"bootstrap/{'x' * 81}",
        "/".join(("x" * 80,) * 4),
    ],
)
def test_unsafe_or_overlong_descriptor_member_paths_are_rejected(member_path: str) -> None:
    _, members = _base_fixture()

    def mutate(document: dict[str, object]) -> None:
        document["bootstrap_matrices"][0]["member_path"] = member_path

    configuration_bytes, members = _fixture_with_members(members, mutate_document=mutate)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize("map_index", range(len(_MAP_SPECS)), ids=lambda index: _MAP_SPECS[index].task_map_id)
def test_every_task_map_member_is_semantically_validated_through_its_last_row(map_index: int) -> None:
    _, members = _base_fixture()
    spec = _MAP_SPECS[map_index]
    mutated = _replace_map_row(
        members,
        map_index,
        spec.count - 1,
        field="root_seed",
        value=spec.root_start + spec.root_count,
    )
    configuration_bytes, mutated = _fixture_with_members(mutated)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=mutated,
        )


@pytest.mark.parametrize(
    ("row_index", "field", "boolean_value"),
    [
        (0, "task_index", False),
        (0, "root_offset", False),
        (0, "root_seed", False),
        (1, "task_index", True),
        (1, "root_offset", True),
        (1, "root_seed", True),
    ],
)
def test_task_map_rows_reject_boolean_substitution_for_equal_integers(
    row_index: int,
    field: str,
    boolean_value: bool,
) -> None:
    _, members = _base_fixture()
    mutated = _replace_map_row(
        members,
        3,
        row_index,
        field=field,
        value=boolean_value,
    )
    configuration_bytes, mutated = _fixture_with_members(mutated)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=mutated,
        )


@pytest.mark.parametrize(
    "case",
    [
        "missing-final-lf",
        "blank-line",
        "carriage-return",
        "leading-space",
        "duplicate-key",
        "unknown-key",
        "swapped-rows",
        "missing-row",
        "extra-row",
        "overlong-row",
    ],
)
def test_task_map_jsonl_framing_canonicality_and_exact_rows(case: str) -> None:
    _, members = _base_fixture()
    path, payload = members[0]
    lines = payload.splitlines()
    if case == "missing-final-lf":
        hostile = payload[:-1]
    elif case == "blank-line":
        hostile = payload + b"\n"
    elif case == "carriage-return":
        hostile = payload.replace(b"\n", b"\r\n", 1)
    elif case == "leading-space":
        hostile = b" " + payload
    elif case == "duplicate-key":
        lines[0] = lines[0].replace(
            b'{"boundary_law":',
            b'{"boundary_law":"periodic-v1","boundary_law":',
            1,
        )
        hostile = b"\n".join(lines) + b"\n"
    elif case == "unknown-key":
        row = json.loads(lines[0])
        row["unknown"] = 0
        lines[0] = _canonical_json(row, newline=False)
        hostile = b"\n".join(lines) + b"\n"
    elif case == "swapped-rows":
        lines[0], lines[1] = lines[1], lines[0]
        hostile = b"\n".join(lines) + b"\n"
    elif case == "missing-row":
        hostile = b"\n".join(lines[:-1]) + b"\n"
    elif case == "extra-row":
        hostile = payload + lines[-1] + b"\n"
    elif case == "overlong-row":
        row = json.loads(lines[0])
        row["padding"] = "x" * 4096
        lines[0] = _canonical_json(row, newline=False)
        hostile = b"\n".join(lines) + b"\n"
    else:
        raise AssertionError(case)
    mutated = _replace_member(members, 0, path=path, payload=hostile)
    configuration_bytes, mutated = _fixture_with_members(mutated)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=mutated,
        )


def test_task_map_descriptor_member_size_hash_path_and_order_cross_bindings() -> None:
    configuration_bytes, members = _base_fixture()
    corruptions = (
        _replace_member(members, 0, payload=members[0][1] + b"x"),
        _replace_member(members, 0, path="task-maps/not-f0.jsonl"),
        (members[1], members[0], *members[2:]),
        (members[0], members[0], *members[2:]),
    )
    for hostile in corruptions:
        with pytest.raises(OneCellCampaignValidationError):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=hostile,
            )


def test_task_map_empty_and_four_mib_bounds_fail_before_row_decode() -> None:
    configuration_bytes, members = _base_fixture()
    for payload in (b"", b"x" * ((4 << 20) + 1)):
        hostile = _replace_member(members, 0, payload=payload)
        with pytest.raises(OneCellCampaignValidationError):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=hostile,
            )


def test_task_map_descriptor_path_uses_the_same_safe_relative_posix_grammar() -> None:
    _, members = _base_fixture()

    def mutate(document: dict[str, object]) -> None:
        document["task_maps"][0]["member_path"] = "task-maps/../f0.jsonl"

    configuration_bytes, members = _fixture_with_members(members, mutate_document=mutate)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_task_map_member_container_and_leaf_types_are_exact() -> None:
    configuration_bytes, members = _base_fixture()

    class HostileTuple(tuple):
        pass

    hostile_values = (
        list(members),
        HostileTuple(members),
        members[:-1],
        ([members[0][0], members[0][1]], *members[1:]),
        ((_HostileString(members[0][0]), members[0][1]), *members[1:]),
        ((members[0][0], _HostileBytes(members[0][1])), *members[1:]),
        ((members[0][0], members[0][1], b"extra"), *members[1:]),
    )
    for hostile in hostile_values:
        with pytest.raises((TypeError, ValueError)):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=hostile,
            )


@pytest.mark.parametrize("vector_index", range(20))
def test_each_vector_rejects_an_internally_rehashed_alternate_literal(vector_index: int) -> None:
    _, members = _base_fixture()

    def mutate(document: dict[str, object]) -> None:
        vector = document["checkpoint_vectors"][vector_index]
        checkpoints = vector["checkpoint_event_counts"]
        position = next(
            index
            for index in range(1, len(checkpoints) - 1)
            if index not in _SNAPSHOT_INDICES and checkpoints[index] + 1 < checkpoints[index + 1]
        )
        checkpoints[position] += 1
        vector["checkpoint_vector_sha256"] = _sha256(
            _canonical_json(
                {
                    "event_counts": checkpoints,
                    "profile": "tetris-pre-one-cell-checkpoint-vector@1",
                },
                newline=False,
            )
        )

    configuration_bytes, members = _fixture_with_members(members, mutate_document=mutate)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    "case",
    ["missing-vector", "extra-vector", "bool-terminal", "bool-checkpoint", "short-checkpoints", "bad-snapshot"],
)
def test_vector_count_shape_and_exact_integer_types_are_enforced(case: str) -> None:
    _, members = _base_fixture()

    def mutate(document: dict[str, object]) -> None:
        vectors = document["checkpoint_vectors"]
        if case == "missing-vector":
            vectors.pop()
        elif case == "extra-vector":
            vectors.append(copy.deepcopy(vectors[-1]))
        elif case == "bool-terminal":
            vectors[0]["terminal_event_count"] = True
        elif case == "bool-checkpoint":
            vectors[0]["checkpoint_event_counts"][1] = True
        elif case == "short-checkpoints":
            vectors[0]["checkpoint_event_counts"].pop()
        elif case == "bad-snapshot":
            vectors[0]["snapshot_checkpoint_indices"][0] = 1
        else:
            raise AssertionError(case)

    configuration_bytes, members = _fixture_with_members(members, mutate_document=mutate)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize("vector_index", range(20))
def test_each_snapshot_vector_rejects_an_internally_rehashed_alternate_literal(vector_index: int) -> None:
    _, members = _base_fixture()

    def mutate(document: dict[str, object]) -> None:
        vector = document["checkpoint_vectors"][vector_index]
        checkpoints = vector["checkpoint_event_counts"]
        snapshot_position = next(
            position
            for position, checkpoint_index in enumerate(_SNAPSHOT_INDICES[1:-1], start=1)
            if checkpoints[checkpoint_index] + 1 < checkpoints[checkpoint_index + 1]
        )
        checkpoint_index = _SNAPSHOT_INDICES[snapshot_position]
        checkpoints[checkpoint_index] += 1
        vector["snapshot_event_counts"][snapshot_position] += 1
        vector["checkpoint_vector_sha256"] = _sha256(
            _canonical_json(
                {
                    "event_counts": checkpoints,
                    "profile": "tetris-pre-one-cell-checkpoint-vector@1",
                },
                newline=False,
            )
        )
        vector["snapshot_vector_sha256"] = _sha256(
            _canonical_json(
                {
                    "checkpoint_indices": vector["snapshot_checkpoint_indices"],
                    "event_counts": vector["snapshot_event_counts"],
                    "profile": "tetris-pre-one-cell-snapshot-vector@1",
                },
                newline=False,
            )
        )

    configuration_bytes, members = _fixture_with_members(members, mutate_document=mutate)
    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_exhaustive_forward_reverse_maps_match_independent_oracle_and_axis_counts() -> None:
    campaign = _load_fixture()
    members = dict(campaign.task_map_members)
    seen_indices: set[tuple[str, int]] = set()
    total = 0
    for spec in _MAP_SPECS:
        boundary_counts: Counter[str] = Counter()
        width_counts: Counter[int] = Counter()
        root_counts: Counter[int] = Counter()
        seam_indices = {0, spec.count - 1}
        for boundary_index in range(len(spec.boundaries)):
            for width_index in range(len(spec.widths)):
                start = (boundary_index * len(spec.widths) + width_index) * spec.root_count
                seam_indices.update((start, start + spec.root_count - 1))

        for task_index in range(spec.count):
            expected = _oracle_row(spec, task_index)
            task = decode_one_cell_campaign_task(
                campaign=campaign,
                task_map_id=spec.task_map_id,
                task_index=task_index,
            )
            assert task.task_map_id == spec.task_map_id
            assert task.task_map_sha256 == _sha256(members[spec.member_path])
            assert task.wave == spec.wave
            assert task.role == spec.role
            assert task.included_in_inference is spec.included
            assert task.task_index == task_index
            assert task.horizon_branch_id == spec.branch
            assert task.boundary_law is OneCellBoundaryLaw(expected["boundary_law"])
            assert task.width == expected["width"]
            assert task.root_seed == expected["root_seed"]
            assert task.root_offset == expected["root_offset"]
            assert task.threshold_schedule_id == expected["threshold_schedule_id"]
            assert (
                task.threshold_schedule
                == {
                    "primary": _PRIMARY,
                    "b1": _B1,
                    "b2-full": _B2_FULL,
                    "b2-high": _B2_HIGH,
                }[expected["threshold_schedule_id"]]
            )
            assert task.terminal_event_count == expected["terminal_event_count"]
            checkpoints, snapshots, checkpoint_hash, snapshot_hash = _oracle_schedule(task.terminal_event_count)
            assert task.checkpoint_event_counts == checkpoints
            assert task.checkpoint_vector_sha256 == checkpoint_hash
            assert task.snapshot_checkpoint_indices == _SNAPSHOT_INDICES
            assert task.snapshot_event_counts == snapshots
            assert task.snapshot_vector_sha256 == snapshot_hash
            if spec.bootstrap is None:
                assert task.bootstrap_cohort_id is None
                assert task.bootstrap_population_index is None
            else:
                assert task.bootstrap_cohort_id == spec.bootstrap
                assert task.bootstrap_population_index == expected["root_offset"]
            assert (
                encode_one_cell_campaign_task_index(
                    campaign=campaign,
                    task_map_id=spec.task_map_id,
                    boundary_law=task.boundary_law,
                    width=task.width,
                    root_seed=task.root_seed,
                )
                == task_index
            )
            boundary_counts[task.boundary_law.value] += 1
            width_counts[task.width] += 1
            root_counts[task.root_seed] += 1
            seen_indices.add((spec.task_map_id, task_index))
            total += 1

        assert boundary_counts == Counter(
            {boundary: len(spec.widths) * spec.root_count for boundary in spec.boundaries}
        )
        assert width_counts == Counter({width: len(spec.boundaries) * spec.root_count for width in spec.widths})
        assert root_counts == Counter(
            {spec.root_start + offset: len(spec.boundaries) * len(spec.widths) for offset in range(spec.root_count)}
        )
        assert all(_oracle_row(spec, index)["task_index"] == index for index in seam_indices)
    assert total == sum(spec.count for spec in _MAP_SPECS) == 4_161
    assert len(seen_indices) == total


@pytest.mark.parametrize(
    ("task_map_id", "task_index"),
    [(spec.task_map_id, spec.count - 1) for spec in _MAP_SPECS],
)
def test_explain_matches_independent_canonical_identity_oracle(task_map_id: str, task_index: int) -> None:
    configuration_bytes, _ = _base_fixture()
    campaign = _load_fixture()
    branch_digest = _HEX_C if task_map_id == "p0-confirmation" or task_map_id.startswith("p1-") else None
    actual = explain_one_cell_campaign_task(
        campaign=campaign,
        task_map_id=task_map_id,
        task_index=task_index,
        deployment_lock_sha256=_HEX_A,
        software_commit=_SOURCE,
        wheel_sha256=_HEX_B,
        branch_decision_sha256=branch_digest,
    )
    expected = _oracle_explanation(
        configuration_bytes=configuration_bytes,
        task_map_id=task_map_id,
        task_index=task_index,
        deployment_lock_sha256=_HEX_A,
        software_commit=_SOURCE,
        wheel_sha256=_HEX_B,
        branch_decision_sha256=branch_digest,
    )
    assert actual == expected
    assert len(actual) <= 1 << 20
    assert not actual.endswith(b"\n")
    decoded = json.loads(actual)
    assert tuple(decoded) == ("profile", "record", "sha256")
    assert decoded["sha256"] == _sha256(_canonical_json(decoded["record"], newline=False))
    assert _canonical_json(decoded, newline=False) == actual
    forbidden_operational_keys = {
        "host",
        "queue",
        "partition",
        "concurrency",
        "attempt",
        "job_id",
        "temporary_path",
        "log_path",
        "scheduler",
    }
    nested_keys = {
        key
        for node in ast.walk(ast.parse(repr(decoded)))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        for key in (node.value,)
    }
    assert nested_keys.isdisjoint(forbidden_operational_keys)


@pytest.mark.slow
def test_all_scientific_identities_are_unique_and_within_the_opaque_byte_bound() -> None:
    configuration_bytes, _ = _base_fixture()
    campaign = _load_fixture()
    digests = set()
    directory_names = set()
    sizes = []
    for spec in _MAP_SPECS:
        branch_digest = _HEX_C if spec.task_map_id == "p0-confirmation" or spec.task_map_id.startswith("p1-") else None
        for task_index in range(spec.count):
            identity = explain_one_cell_campaign_task(
                campaign=campaign,
                task_map_id=spec.task_map_id,
                task_index=task_index,
                deployment_lock_sha256=_HEX_A,
                software_commit=_SOURCE,
                wheel_sha256=_HEX_B,
                branch_decision_sha256=branch_digest,
            )
            assert identity == _oracle_explanation(
                configuration_bytes=configuration_bytes,
                task_map_id=spec.task_map_id,
                task_index=task_index,
                deployment_lock_sha256=_HEX_A,
                software_commit=_SOURCE,
                wheel_sha256=_HEX_B,
                branch_decision_sha256=branch_digest,
            )
            assert _canonical_json(json.loads(identity), newline=False) == identity
            envelope = json.loads(identity)
            directory_name = f"{spec.wave}/{task_index:020d}-{envelope['sha256']}"
            assert re.fullmatch(r"[a-z0-9-]+/[0-9]{20}-[0-9a-f]{64}", directory_name)
            assert not directory_name.startswith("/")
            assert all(component not in {"", ".", ".."} for component in directory_name.split("/"))
            digests.add(_sha256(identity))
            directory_names.add(directory_name)
            sizes.append(len(identity))
    assert len(digests) == sum(spec.count for spec in _MAP_SPECS) == 4_161
    assert len(directory_names) == len(digests)
    assert 0 < min(sizes) <= max(sizes) <= 1 << 20


@pytest.mark.parametrize("bad", [True, 0.0, "0", _HostileInt(0), object()])
def test_decode_rejects_nonexact_task_index_types(bad: object) -> None:
    campaign = _load_fixture()
    with pytest.raises(TypeError):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="f0",
            task_index=bad,
        )


@pytest.mark.parametrize("bad", [True, 64.0, "64", _HostileInt(64), object()])
def test_encode_rejects_nonexact_integer_axis_types(bad: object) -> None:
    campaign = _load_fixture()
    for field in ("width", "root_seed"):
        arguments = {
            "campaign": campaign,
            "task_map_id": "p0-initial",
            "boundary_law": OneCellBoundaryLaw.PERIODIC,
            "width": 64,
            "root_seed": 1_000_000,
        }
        arguments[field] = bad
        with pytest.raises(TypeError):
            encode_one_cell_campaign_task_index(**arguments)


def test_encode_decode_invalid_maps_indices_and_axes_raise_value_error() -> None:
    campaign = _load_fixture()
    for task_map_id, task_index in (("unknown", 0), ("f0", -1), ("f0", 8)):
        with pytest.raises(ValueError):
            decode_one_cell_campaign_task(
                campaign=campaign,
                task_map_id=task_map_id,
                task_index=task_index,
            )
    invalid_axes = (
        {"task_map_id": "unknown"},
        {"boundary_law": OneCellBoundaryLaw.HARD_WALL_REFLECTION_SYMMETRIC},
        {"width": 128},
        {"root_seed": 999_999},
    )
    for replacement in invalid_axes:
        arguments = {
            "campaign": campaign,
            "task_map_id": "p0-initial",
            "boundary_law": OneCellBoundaryLaw.PERIODIC,
            "width": 64,
            "root_seed": 1_000_000,
            **replacement,
        }
        with pytest.raises(ValueError):
            encode_one_cell_campaign_task_index(**arguments)


def test_campaign_map_and_boundary_public_arguments_require_exact_types() -> None:
    campaign = _load_fixture()
    with pytest.raises(TypeError):
        decode_one_cell_campaign_task(
            campaign=object(),
            task_map_id="f0",
            task_index=0,
        )
    with pytest.raises(TypeError):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id=_HostileString("f0"),
            task_index=0,
        )
    with pytest.raises(TypeError):
        encode_one_cell_campaign_task_index(
            campaign=campaign,
            task_map_id=_HostileString("f0"),
            boundary_law=OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
            width=50,
            root_seed=3_100_000,
        )
    with pytest.raises(TypeError):
        encode_one_cell_campaign_task_index(
            campaign=campaign,
            task_map_id="f0",
            boundary_law=_HostileString(_LEGACY),
            width=50,
            root_seed=3_100_000,
        )
    with pytest.raises(TypeError):
        explain_one_cell_campaign_task(
            campaign=campaign,
            task_map_id=_HostileString("f0"),
            task_index=0,
            deployment_lock_sha256=_HEX_A,
            software_commit=_SOURCE,
            wheel_sha256=_HEX_B,
        )


def test_public_operations_are_strictly_keyword_only_at_call_time() -> None:
    configuration_bytes, members = _base_fixture()
    campaign = _load_fixture()
    with pytest.raises(TypeError):
        load_one_cell_campaign(configuration_bytes, members)
    with pytest.raises(TypeError):
        decode_one_cell_campaign_task(campaign, "f0", 0)
    with pytest.raises(TypeError):
        encode_one_cell_campaign_task_index(
            campaign,
            "f0",
            OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
            50,
            3_100_000,
        )
    with pytest.raises(TypeError):
        explain_one_cell_campaign_task(campaign, "f0", 0, _HEX_A, _SOURCE, _HEX_B)


@pytest.mark.parametrize(
    ("field", "bad", "error"),
    [
        ("deployment_lock_sha256", _HostileString(_HEX_A), TypeError),
        ("deployment_lock_sha256", "A" * 64, ValueError),
        ("deployment_lock_sha256", "a" * 63, ValueError),
        ("wheel_sha256", _HostileString(_HEX_B), TypeError),
        ("wheel_sha256", "g" * 64, ValueError),
        ("software_commit", _HostileString(_SOURCE), TypeError),
        ("software_commit", "D" * 40, ValueError),
        ("software_commit", "d" * 39, ValueError),
    ],
)
def test_explain_rejects_hostile_external_authority_types_and_syntax(field: str, bad: object, error: type) -> None:
    campaign = _load_fixture()
    arguments = {
        "campaign": campaign,
        "task_map_id": "f0",
        "task_index": 0,
        "deployment_lock_sha256": _HEX_A,
        "software_commit": _SOURCE,
        "wheel_sha256": _HEX_B,
    }
    arguments[field] = bad
    with pytest.raises(error):
        explain_one_cell_campaign_task(**arguments)


def test_explain_enforces_branch_join_applicability_in_both_directions() -> None:
    campaign = _load_fixture()
    common = {
        "campaign": campaign,
        "task_index": 0,
        "deployment_lock_sha256": _HEX_A,
        "software_commit": _SOURCE,
        "wheel_sha256": _HEX_B,
    }
    for task_map_id in ("p0-confirmation", "p1-no-l-star", "p1-l-star-64"):
        with pytest.raises(TypeError):
            explain_one_cell_campaign_task(
                task_map_id=task_map_id,
                **common,
            )
    for task_map_id in ("f0", "p0-initial", "b1", "b2"):
        with pytest.raises(ValueError):
            explain_one_cell_campaign_task(
                task_map_id=task_map_id,
                branch_decision_sha256=_HEX_C,
                **common,
            )


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        (_HostileString(_HEX_C), TypeError),
        (True, TypeError),
        ("C" * 64, ValueError),
        ("c" * 63, ValueError),
        ("g" * 64, ValueError),
    ],
)
def test_branch_join_digest_requires_exact_type_and_lowercase_sha256(bad: object, error: type) -> None:
    campaign = _load_fixture()
    with pytest.raises(error):
        explain_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="p1-no-l-star",
            task_index=0,
            deployment_lock_sha256=_HEX_A,
            software_commit=_SOURCE,
            wheel_sha256=_HEX_B,
            branch_decision_sha256=bad,
        )


def test_public_record_construction_rejects_cross_inconsistent_and_hostile_fields() -> None:
    campaign = _load_fixture()
    task = decode_one_cell_campaign_task(campaign=campaign, task_map_id="p0-initial", task_index=0)
    cases = (
        (campaign.bootstrap_matrices[0], {"cohort_id": _HostileString("p0")}),
        (campaign.bootstrap_matrices[0], {"seed": True}),
        (campaign.bootstrap_matrices[0], {"shape": [10_000, 16]}),
        (campaign.task_maps[0], {"task_map_id": _HostileString("f0")}),
        (campaign.task_maps[0], {"task_count": True}),
        (campaign.horizon_branches[0], {"branch_id": _HostileString("p1-no-l-star")}),
        (campaign.horizon_branches[0], {"confirmation_required": 0}),
        (campaign.horizon_branches[0], {"p1_terminal_event_counts": list(_BASE_HORIZONS.items())[1:]}),
        (task, {"task_map_id": _HostileString("p0-initial")}),
        (task, {"task_index": True}),
        (task, {"root_seed": _HostileInt(task.root_seed)}),
        (task, {"boundary_law": task.boundary_law.value}),
        (campaign, {"profile": _HostileString(campaign.profile)}),
        (campaign, {"protocol_size_bytes": True}),
    )
    for record, changes in cases:
        with pytest.raises((TypeError, ValueError)):
            dataclasses.replace(record, **changes)


def test_every_equal_hostile_record_field_subclass_raises_type_error() -> None:
    class HostileTuple(tuple):
        pass

    def hostile(value: object) -> object | None:
        if type(value) is bool:
            return int(value)
        if type(value) is int:
            return _HostileInt(value)
        if type(value) is str:
            return _HostileString(value)
        if type(value) is bytes:
            return _HostileBytes(value)
        if type(value) is tuple:
            return HostileTuple(value)
        return None

    campaign = _load_fixture()
    task = decode_one_cell_campaign_task(campaign=campaign, task_map_id="p0-initial", task_index=1)
    records = (
        campaign.bootstrap_matrices[0],
        campaign.task_maps[0],
        campaign.horizon_branches[1],
        task,
        campaign,
    )
    checked = 0
    for record in records:
        for field in dataclasses.fields(record):
            replacement = hostile(getattr(record, field.name))
            if replacement is None:
                continue
            checked += 1
            try:
                dataclasses.replace(record, **{field.name: replacement})
            except TypeError:
                continue
            except Exception as error:
                pytest.fail(f"{type(record).__name__}.{field.name} raised {type(error).__name__}, not TypeError")
            pytest.fail(f"{type(record).__name__}.{field.name} accepted an equal hostile runtime type")
    assert checked == 63


def test_exact_but_cross_inconsistent_record_values_raise_value_error() -> None:
    campaign = _load_fixture()
    task = decode_one_cell_campaign_task(campaign=campaign, task_map_id="p0-initial", task_index=0)
    cases = (
        (campaign.bootstrap_matrices[0], {"member_path": "bootstrap/not-p0.u16le"}),
        (campaign.task_maps[0], {"task_count": campaign.task_maps[0].task_count + 1}),
        (campaign.horizon_branches[1], {"l_star": 256}),
        (task, {"root_seed": task.root_seed + 1}),
        (campaign, {"configuration_sha256": "0" * 64}),
    )
    for record, changes in cases:
        with pytest.raises(ValueError):
            dataclasses.replace(record, **changes)


def test_campaign_constructor_recertifies_nested_records_instead_of_trusting_equality() -> None:
    class AlwaysEqual:
        def __eq__(self, _other: object) -> bool:
            return True

    campaign = _load_fixture()
    forged_bootstrap = copy.copy(campaign.bootstrap_matrices[0])
    object.__setattr__(forged_bootstrap, "cohort_id", _HostileString("p0"))
    forged_map = copy.copy(campaign.task_maps[2])
    object.__setattr__(forged_map, "task_count", True)
    forged_branch = copy.copy(campaign.horizon_branches[1])
    object.__setattr__(forged_branch, "confirmation_required", 1)
    cases = (
        (
            "bootstrap_matrices",
            (forged_bootstrap, *campaign.bootstrap_matrices[1:]),
        ),
        (
            "task_maps",
            (*campaign.task_maps[:2], forged_map, *campaign.task_maps[3:]),
        ),
        (
            "horizon_branches",
            (campaign.horizon_branches[0], forged_branch, *campaign.horizon_branches[2:]),
        ),
        (
            "bootstrap_matrices",
            (AlwaysEqual(), *campaign.bootstrap_matrices[1:]),
        ),
        (
            "task_maps",
            (AlwaysEqual(), *campaign.task_maps[1:]),
        ),
        (
            "horizon_branches",
            (AlwaysEqual(), *campaign.horizon_branches[1:]),
        ),
    )
    for field, replacement in cases:
        with pytest.raises(TypeError):
            dataclasses.replace(campaign, **{field: replacement})


def test_every_public_operation_revalidates_a_forged_frozen_campaign() -> None:
    campaign = _load_fixture()
    forged = copy.copy(campaign)
    object.__setattr__(forged, "profile", "tetris-pre-one-cell-campaign@2")
    with pytest.raises(ValueError):
        decode_one_cell_campaign_task(campaign=forged, task_map_id="f0", task_index=0)
    with pytest.raises(ValueError):
        encode_one_cell_campaign_task_index(
            campaign=forged,
            task_map_id="f0",
            boundary_law=OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
            width=50,
            root_seed=3_100_000,
        )
    with pytest.raises(ValueError):
        explain_one_cell_campaign_task(
            campaign=forged,
            task_map_id="f0",
            task_index=0,
            deployment_lock_sha256=_HEX_A,
            software_commit=_SOURCE,
            wheel_sha256=_HEX_B,
        )


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("_CERTIFIED_PARSE_CAMPAIGN", object()),
        ("_CERTIFIED_PROTOCOL_RECORD", object()),
        ("_CERTIFIED_MODEL_RECORD", object()),
        ("_CERTIFIED_EXECUTION_RECORD", object()),
        ("_MAP_SPECS", ()),
        ("_CHECKPOINT_HASHES", ()),
        ("OneCellCampaignAuthority", object),
    ],
)
def test_private_and_public_authority_rebinding_fails_with_assertion(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: object,
) -> None:
    configuration_bytes, members = _base_fixture()
    monkeypatch.setattr(campaign_module, name, replacement)
    with pytest.raises(AssertionError):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_closure_bound_integrity_guard_rejects_its_own_rebinding_before_dependency_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForgedDependencyCalled(RuntimeError):
        pass

    campaign = _load_fixture()

    def forged_decode(**_kwargs: object) -> object:
        raise ForgedDependencyCalled

    monkeypatch.setattr(campaign_module, "_assert_contract_integrity", lambda: None)
    monkeypatch.setattr(campaign_module, "_decode_task", forged_decode)
    with pytest.raises(AssertionError, match="integrity guard has been rebound"):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="f0",
            task_index=0,
        )


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("globals", lambda: {}),
        ("any", lambda _values: False),
    ],
)
def test_closure_bound_integrity_guard_rejects_shadowed_builtins_before_dependency_call(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: object,
) -> None:
    class ForgedDependencyCalled(RuntimeError):
        pass

    campaign = _load_fixture()

    def forged_decode(**_kwargs: object) -> object:
        raise ForgedDependencyCalled

    monkeypatch.setattr(campaign_module, name, replacement, raising=False)
    monkeypatch.setattr(campaign_module, "_decode_task", forged_decode)
    with pytest.raises(AssertionError, match="integrity builtins have been shadowed"):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="f0",
            task_index=0,
        )


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("any", lambda _values: False),
        ("isinstance", lambda _value, _class: False),
    ],
)
def test_closure_bound_integrity_guard_rejects_process_builtin_rebinding_before_dependency_call(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: object,
) -> None:
    class ForgedDependencyCalled(RuntimeError):
        pass

    campaign = _load_fixture()

    def forged_decode(**_kwargs: object) -> object:
        raise ForgedDependencyCalled

    monkeypatch.setattr(campaign_module, "_decode_task", forged_decode)
    builtin_namespace = campaign_module._bind_campaign_api.__builtins__
    original = builtin_namespace[name]
    caught: AssertionError | None = None
    try:
        builtin_namespace[name] = replacement
        try:
            decode_one_cell_campaign_task(
                campaign=campaign,
                task_map_id="f0",
                task_index=0,
            )
        except AssertionError as error:
            caught = error
    finally:
        builtin_namespace[name] = original

    assert caught is not None
    assert f"integrity builtin '{name}' has been rebound" in str(caught)


@pytest.mark.parametrize(
    ("name", "replacement"),
    [
        ("_HEX64", object()),
        ("_U64_LIMIT", 0),
        ("_U128_LIMIT", 0),
        ("hashlib", object()),
    ],
)
def test_all_prebinding_module_dependencies_are_closure_protected(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: object,
) -> None:
    configuration_bytes, members = _base_fixture()
    monkeypatch.setattr(campaign_module, name, replacement)
    with pytest.raises(AssertionError, match="campaign module binding"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    ("module", "attribute"),
    [
        (campaign_module.hashlib, "sha256"),
        (campaign_module.json, "dumps"),
        (campaign_module.json, "loads"),
        (campaign_module.json, "JSONDecodeError"),
        (campaign_module.json, "JSONDecoder"),
        (campaign_module.json, "JSONEncoder"),
        (campaign_module.re, "fullmatch"),
    ],
)
def test_runtime_imported_attributes_are_closure_protected(
    monkeypatch: pytest.MonkeyPatch,
    module: object,
    attribute: str,
) -> None:
    configuration_bytes, members = _base_fixture()
    monkeypatch.setattr(module, attribute, object())
    with pytest.raises(AssertionError, match="campaign imported"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    ("class_type", "attribute"),
    [
        (campaign_module._SealedRecord, "__new__"),
        (campaign_module.OneCellTaskMapIdentity, "__eq__"),
        (campaign_module.OneCellCampaignTask, "__post_init__"),
    ],
)
def test_runtime_campaign_class_attributes_are_closure_protected(
    class_type: type[object],
    attribute: str,
) -> None:
    with pytest.raises(TypeError, match="runtime sealed"):
        setattr(class_type, attribute, lambda *_args, **_kwargs: True)


def test_runtime_class_hierarchy_mutation_fails_closed_and_restores_cleanly() -> None:
    configuration_bytes, members = _base_fixture()
    original_bases = OneCellCampaignValidationError.__bases__
    try:
        OneCellCampaignValidationError.__bases__ = (Exception,)
        with pytest.raises(AssertionError, match="campaign class binding"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        OneCellCampaignValidationError.__bases__ = original_bases

    with pytest.raises(OneCellCampaignValidationError):
        load_one_cell_campaign(
            configuration_bytes=b"evil\n",
            task_map_members=members,
        )


def test_runtime_dataclass_field_map_mutation_fails_closed_and_restores_order() -> None:
    configuration_bytes, members = _base_fixture()
    fields = OneCellCampaignAuthority.__dataclass_fields__
    original_items = tuple(fields.items())
    try:
        fields.pop("protocol_blob")
        with pytest.raises(AssertionError, match="campaign class state"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        fields.clear()
        fields.update(original_items)

    campaign = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert campaign.protocol_blob == campaign_module._PROTOCOL_BLOB


def test_runtime_dataclass_parameter_mutation_fails_closed_and_restores_cleanly() -> None:
    configuration_bytes, members = _base_fixture()
    parameters = OneCellCampaignAuthority.__dataclass_params__
    original = parameters.frozen
    try:
        object.__setattr__(parameters, "frozen", False)
        with pytest.raises(AssertionError, match="campaign class state"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        object.__setattr__(parameters, "frozen", original)

    campaign = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert campaign.__dataclass_params__.frozen is True


def test_dataclass_field_class_callback_is_rejected_before_slot_reads() -> None:
    configuration_bytes, members = _base_fixture()
    field = next(iter(OneCellCampaignAuthority.__dataclass_fields__.values()))
    field_type = type(field)
    had_own_getattribute = "__getattribute__" in field_type.__dict__
    original = field_type.__getattribute__

    def forged_getattribute(_self: object, _name: str) -> object:
        raise RuntimeError("forged dataclass Field callback executed")

    try:
        field_type.__getattribute__ = forged_getattribute
        with pytest.raises(AssertionError, match="campaign class binding"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        if had_own_getattribute:
            field_type.__getattribute__ = original
        else:
            del field_type.__getattribute__

    restored = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert restored.protocol_commit == campaign_module._ARTICLE_COMMIT


def test_exported_record_construction_enters_the_closure_bound_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid = {
        "task_map_id": "evil",
        "profile": "evil",
        "member_path": "../evil",
        "wave": "evil",
        "role": "evil",
        "horizon_branch_id": "evil",
        "task_count": -1,
        "size_bytes": -1,
        "sha256": "evil",
    }
    with monkeypatch.context() as patch:
        patch.setattr(campaign_module, "_validate_task_map_identity_record", lambda _value: None)
        with pytest.raises(AssertionError, match="campaign module binding"):
            OneCellTaskMapIdentity(**invalid)
    with pytest.raises(TypeError, match="runtime sealed"):
        OneCellTaskMapIdentity.__post_init__ = lambda _self: None


def test_integrity_core_code_mutation_is_detected_before_a_forged_helper_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForgedDependencyCalled(RuntimeError):
        pass

    campaign = _load_fixture()

    def noop(**_kwargs: object) -> None:
        return None

    def forged_decode(**_kwargs: object) -> object:
        raise ForgedDependencyCalled

    monkeypatch.setattr(campaign_module._assert_contract_integrity_core, "__code__", noop.__code__)
    monkeypatch.setattr(campaign_module, "_decode_task", forged_decode)
    with pytest.raises(AssertionError, match="campaign function state"):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="f0",
            task_index=0,
        )


def test_property_accessor_code_mutation_is_detected_before_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_bytes, members = _base_fixture()

    def forged_getter(_self: object) -> int:
        raise RuntimeError("mutated property getter executed")

    getter = campaign_module._MapSpec.task_count.fget
    assert getter is not None
    monkeypatch.setattr(getter, "__code__", forged_getter.__code__)
    with pytest.raises(AssertionError, match="campaign function state"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


@pytest.mark.parametrize(
    "function",
    [
        next(owner.__dict__["name"].fget for owner in OneCellBoundaryLaw.__mro__ if "name" in owner.__dict__),
        type(OneCellBoundaryLaw).__dict__["__call__"],
    ],
)
def test_inherited_enum_dependency_code_mutation_is_detected_before_use(
    monkeypatch: pytest.MonkeyPatch,
    function: object,
) -> None:
    configuration_bytes, members = _base_fixture()

    def forged(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("mutated inherited enum dependency executed")

    monkeypatch.setattr(function, "__code__", forged.__code__)
    with pytest.raises(AssertionError, match="campaign function state"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_enum_module_callback_binding_is_rejected_before_boundary_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_bytes, members = _base_fixture()

    def forged_mapping_proxy(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("forged enum module callback executed")

    monkeypatch.setattr(campaign_module.enum, "MappingProxyType", forged_mapping_proxy)
    with pytest.raises(AssertionError, match="campaign imported module binding"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_public_operation_keyword_default_mutation_fails_closed() -> None:
    campaign = _load_fixture()
    keyword_defaults = explain_one_cell_campaign_task.__kwdefaults__
    assert keyword_defaults is not None
    original = keyword_defaults["branch_decision_sha256"]
    try:
        keyword_defaults["branch_decision_sha256"] = _HEX_C
        with pytest.raises(AssertionError, match="campaign function default"):
            explain_one_cell_campaign_task(
                campaign=campaign,
                task_map_id="p1-no-l-star",
                task_index=0,
                deployment_lock_sha256=_HEX_A,
                software_commit=_SOURCE,
                wheel_sha256=_HEX_B,
            )
    finally:
        keyword_defaults["branch_decision_sha256"] = original


def test_json_callable_default_and_decoder_code_mutations_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_bytes, members = _base_fixture()
    loads_defaults = campaign_module.json.loads.__kwdefaults__
    assert loads_defaults is not None
    original_cls = loads_defaults["cls"]
    try:
        loads_defaults["cls"] = object()
        with pytest.raises(AssertionError, match="campaign function default"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        loads_defaults["cls"] = original_cls

    def forged_decode(_self: object, _source: str) -> object:
        return {}

    monkeypatch.setattr(campaign_module.json.JSONDecoder.decode, "__code__", forged_decode.__code__)
    with pytest.raises(AssertionError, match="campaign function state"):
        load_one_cell_campaign(
            configuration_bytes=configuration_bytes,
            task_map_members=members,
        )


def test_imported_module_runtime_class_mutation_fails_closed() -> None:
    configuration_bytes, members = _base_fixture()
    original_class = campaign_module.json.__class__

    class ForgedModule(original_class):
        pass

    try:
        campaign_module.json.__class__ = ForgedModule
        with pytest.raises(AssertionError, match="campaign imported module"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        campaign_module.json.__class__ = original_class


def test_strict_unicode_codec_registry_mutation_fails_closed() -> None:
    configuration_bytes, members = _base_fixture()
    original = campaign_module.codecs.lookup_error("strict")

    def forged_handler(error: UnicodeError) -> tuple[str, int]:
        return "?", error.end

    try:
        campaign_module.codecs.register_error("strict", forged_handler)
        with pytest.raises(AssertionError, match="strict Unicode codec error handler"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        campaign_module.codecs.register_error("strict", original)

    restored = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert restored.protocol_commit == campaign_module._ARTICLE_COMMIT


def test_codec_module_type_is_verified_before_registry_lookup() -> None:
    configuration_bytes, members = _base_fixture()
    original_class = campaign_module.codecs.__class__

    class ForgedCodecModule(original_class):
        def __getattribute__(self, name: str) -> object:
            if name == "lookup_error":
                raise RuntimeError("forged codec lookup executed")
            return super().__getattribute__(name)

    try:
        campaign_module.codecs.__class__ = ForgedCodecModule
        with pytest.raises(AssertionError, match="campaign imported module"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        campaign_module.codecs.__class__ = original_class

    restored = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert restored.protocol_commit == campaign_module._ARTICLE_COMMIT


def test_runtime_boundary_enum_member_mutation_fails_closed_and_restores_cleanly() -> None:
    configuration_bytes, members = _base_fixture()
    member = OneCellBoundaryLaw.PERIODIC
    original_name = member._name_
    try:
        object.__setattr__(member, "_name_", "FORGED")
        with pytest.raises(AssertionError, match="boundary or threshold authority"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        object.__setattr__(member, "_name_", original_name)

    restored = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert len(restored.task_maps) == 9


def test_certified_parser_returns_a_deep_copy_of_its_private_cache() -> None:
    configuration_bytes, members = _base_fixture()
    parsed = campaign_module._CERTIFIED_PARSE_CAMPAIGN(configuration_bytes, members)
    object.__setattr__(parsed, "bootstrap_matrices", ())

    restored = campaign_module._CERTIFIED_PARSE_CAMPAIGN(configuration_bytes, members)
    assert len(restored.bootstrap_matrices) == 4


def test_hidden_cache_cannot_be_filled_while_dependencies_are_rebound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configuration_bytes, members = _base_fixture()
    bad_configuration = configuration_bytes.replace(
        campaign_module._ARTICLE_COMMIT.encode("ascii"),
        b"0" * 40,
    )
    trusted = campaign_module._CERTIFIED_PARSE_CAMPAIGN(configuration_bytes, members)
    with monkeypatch.context() as patch:
        patch.setattr(campaign_module, "_parse_campaign_uncached", lambda *_args: trusted)
        patch.setattr(campaign_module, "_assert_contract_integrity", lambda: None)
        with pytest.raises(AssertionError):
            campaign_module._CERTIFIED_PARSE_CAMPAIGN(bad_configuration, members)

    with pytest.raises(OneCellCampaignValidationError):
        campaign_module._CERTIFIED_PARSE_CAMPAIGN(bad_configuration, members)


def test_certified_parser_rejects_hostile_cache_keys_before_hashing() -> None:
    configuration_bytes, members = _base_fixture()
    bad_configuration = configuration_bytes.replace(
        campaign_module._ARTICLE_COMMIT.encode("ascii"),
        b"0" * 40,
    )
    with pytest.raises(TypeError, match="configuration_bytes must be built-in bytes"):
        campaign_module._CERTIFIED_PARSE_CAMPAIGN(_HostileBytes(bad_configuration), members)
    with pytest.raises(TypeError, match="payload must be built-in bytes"):
        campaign_module._CERTIFIED_PARSE_CAMPAIGN(
            configuration_bytes,
            ((members[0][0], _HostileBytes(members[0][1])), *members[1:]),
        )
    with pytest.raises(OneCellCampaignValidationError):
        campaign_module._CERTIFIED_PARSE_CAMPAIGN(bad_configuration, members)


def test_certified_parser_deep_clones_nested_cached_vectors() -> None:
    configuration_bytes, members = _base_fixture()
    parsed = campaign_module._CERTIFIED_PARSE_CAMPAIGN(configuration_bytes, members)
    vector = next(item for item in parsed.checkpoint_vectors if item.terminal_event_count == 55_000)
    object.__setattr__(vector, "checkpoint_event_counts", (999, *vector.checkpoint_event_counts[1:]))

    restored = campaign_module._CERTIFIED_PARSE_CAMPAIGN(
        configuration_bytes,
        members,
    )
    restored_vector = next(item for item in restored.checkpoint_vectors if item.terminal_event_count == 55_000)
    assert restored_vector.checkpoint_event_counts[0] == 1


def test_closure_bound_integrity_guard_rejects_joint_certified_alias_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ForgedParserCalled(RuntimeError):
        pass

    campaign = _load_fixture()

    def forged_parser(*_args: object, **_kwargs: object) -> object:
        raise ForgedParserCalled

    monkeypatch.setattr(campaign_module, "_CERTIFIED_PARSE_CAMPAIGN", forged_parser)
    monkeypatch.setattr(campaign_module, "_CAPTURED_PARSE_CAMPAIGN", forged_parser)
    with pytest.raises(AssertionError, match="campaign API"):
        decode_one_cell_campaign_task(
            campaign=campaign,
            task_map_id="f0",
            task_index=0,
        )


def test_in_place_map_spec_mutation_fails_closed_and_restores_cleanly() -> None:
    configuration_bytes, members = _base_fixture()
    spec = campaign_module._MAP_SPECS[0]
    original_root_start = spec.root_start
    try:
        object.__setattr__(spec, "root_start", original_root_start + 100_000)
        with pytest.raises(AssertionError, match="map specifications have been mutated"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        object.__setattr__(spec, "root_start", original_root_start)

    restored = load_one_cell_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=members,
    )
    assert restored.task_maps[0].task_map_id == "f0"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("included_in_inference", 0),
        ("root_start", _HostileInt(3_100_000)),
    ],
)
def test_in_place_map_spec_equality_substitutes_fail_exact_type_checks(
    field: str,
    replacement: object,
) -> None:
    configuration_bytes, members = _base_fixture()
    spec = campaign_module._MAP_SPECS[0]
    original = getattr(spec, field)
    try:
        object.__setattr__(spec, field, replacement)
        with pytest.raises(AssertionError, match="invalid runtime types"):
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
    finally:
        object.__setattr__(spec, field, original)


@pytest.mark.parametrize(
    ("operation", "name"),
    [
        ("load", "_sha256"),
        ("load", "_canonical_json"),
        ("load", "_validate_task_map_members"),
        ("load", "_parsed_campaign"),
        ("load", "_build_campaign_authority"),
        ("load", "_validate_campaign_authority_record"),
        ("decode", "_snapshot_campaign"),
        ("decode", "_decode_task"),
        ("encode", "_map_spec"),
        ("explain", "_require_external_digest"),
        ("explain", "_require_software_commit"),
        ("explain", "_task_map_identity"),
        ("explain", "_bootstrap_identity_record"),
        ("explain", "decode_one_cell_campaign_task"),
    ],
)
def test_public_operations_reject_rebound_dependency_closure_before_calling_it(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    name: str,
) -> None:
    class SentinelCalled(RuntimeError):
        pass

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise SentinelCalled(name)

    configuration_bytes, members = _base_fixture()
    campaign = _load_fixture()
    monkeypatch.setattr(campaign_module, name, forbidden)
    with pytest.raises(AssertionError):
        if operation == "load":
            load_one_cell_campaign(
                configuration_bytes=configuration_bytes,
                task_map_members=members,
            )
        elif operation == "decode":
            decode_one_cell_campaign_task(
                campaign=campaign,
                task_map_id="f0",
                task_index=0,
            )
        elif operation == "encode":
            encode_one_cell_campaign_task_index(
                campaign=campaign,
                task_map_id="f0",
                boundary_law=OneCellBoundaryLaw.HARD_WALL_LEGACY_ASYMMETRIC,
                width=50,
                root_seed=3_100_000,
            )
        elif operation == "explain":
            explain_one_cell_campaign_task(
                campaign=campaign,
                task_map_id="p0-initial",
                task_index=0,
                deployment_lock_sha256=_HEX_A,
                software_commit=_SOURCE,
                wheel_sha256=_HEX_B,
            )
        else:
            raise AssertionError(operation)


def test_independent_oracle_call_graph_never_uses_production_campaign_helpers() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    production_names = set(_PUBLIC_API) | {
        "_expected_task_row",
        "_terminal_for",
        "_schedule_id_for",
        "_vector_hashes",
        "_parse_campaign_uncached",
    }
    for function in (
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("_oracle_")
    ):
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if isinstance(call.func, ast.Name):
                assert call.func.id not in production_names, (function.name, call.func.id)
            elif isinstance(call.func, ast.Attribute):
                root = call.func.value
                while isinstance(root, ast.Attribute):
                    root = root.value
                assert not (isinstance(root, ast.Name) and root.id == "campaign_module")


def test_module_dependency_ast_has_no_checkpoint_runner_legacy_hpc_or_io_surface() -> None:
    source_path = Path(campaign_module.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = set()
    relative_imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
            if node.level:
                relative_imports.add(node.module)
    assert relative_imports == {"one_cell_boundary"}
    assert imported == {
        "__future__",
        "codecs",
        "dataclasses",
        "enum",
        "functools",
        "hashlib",
        "json",
        "one_cell_boundary",
        "re",
    }
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert identifiers.isdisjoint(
        {
            "Path",
            "Popen",
            "open",
            "sbatch",
            "scontrol",
            "system",
            "run_artifacts",
            "checkpoint",
            "legacy",
            "slurm",
        }
    )


def test_package_roots_do_not_export_campaign_and_explicit_import_needs_no_hpc() -> None:
    code = r"""
import sys

sys.modules["numba"] = None
import tetris_ballistic
import tetris_ballistic.engine as engine

names = (
    "OneCellCampaignValidationError",
    "OneCellBootstrapMatrixIdentity",
    "OneCellTaskMapIdentity",
    "OneCellHorizonBranch",
    "OneCellCampaignAuthority",
    "OneCellCampaignTask",
    "load_one_cell_campaign",
    "encode_one_cell_campaign_task_index",
    "decode_one_cell_campaign_task",
    "explain_one_cell_campaign_task",
)
assert "tetris_ballistic.engine.one_cell_campaign" not in sys.modules
assert all(not hasattr(tetris_ballistic, name) for name in names)
assert all(not hasattr(engine, name) for name in names)
import tetris_ballistic.engine.one_cell_campaign as campaign
assert tuple(campaign.__all__) == names
assert "numba" not in sys.modules or sys.modules["numba"] is None
assert "tetris_ballistic.engine.one_cell_checkpoint" not in sys.modules
assert "tetris_ballistic.engine.one_cell_trajectory_compiled" not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )


def test_only_the_frozen_slice_8a_allowlist_is_new_or_modified() -> None:
    if not (_REPO_ROOT / ".git").is_dir():
        pytest.skip("Git history is unavailable")
    for commit in (_SOFTWARE_PARENT, _SOFTWARE_AUTHORITY):
        endpoint_check = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if endpoint_check.returncode != 0:
            pytest.skip("the frozen Slice 8A range is unavailable in this shallow checkout")
    changed_result = subprocess.run(
        ["git", "diff", "--name-only", _SOFTWARE_PARENT, _SOFTWARE_AUTHORITY, "--"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    changed = {line for line in changed_result.stdout.splitlines() if line}
    changed.update(
        line
        for line in untracked_result.stdout.splitlines()
        if line and not line.startswith((".omx/", ".pi-subagents/"))
    )
    assert changed <= {
        "tetris_ballistic/engine/one_cell_campaign.py",
        "tests/test_one_cell_campaign.py",
        "docs/PRE-ONE-CELL-CAMPAIGN-SCHEMA.md",
        "docs/API-SPEC.md",
        "CHANGELOG.md",
    }
