"""Exact held-byte campaign identity for the frozen PRE one-cell study.

This explicit-only Slice 8A module validates one canonical campaign document
and all nine complete primitive task maps.  It performs no filesystem I/O,
numerical evolution, checkpoint import, runner dispatch, scheduler action, or
scientific acquisition.
"""

from __future__ import annotations

import codecs
import enum
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache

from .one_cell_boundary import OneCellBoundaryLaw

__all__ = [
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
]

_CONFIGURATION_LIMIT = 1 << 20
_TASK_MAP_LIMIT = 4 << 20
_TASK_MAP_LINE_LIMIT = 4096
_SCIENTIFIC_IDENTITY_LIMIT = 1 << 20
_JSON_DEPTH_LIMIT = 24
_JSON_NODE_LIMIT = 40_000
_U64_LIMIT = 1 << 64
_U128_LIMIT = 1 << 128
_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}(?:[A-Za-z0-9.+-]*)?\Z")
_SAFE_MEMBER = re.compile(r"[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)*\Z")
_INTEGER = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")
_CAPTURED_STRICT_ERROR_HANDLER = codecs.lookup_error("strict")

_CAMPAIGN_PROFILE = "tetris-pre-one-cell-campaign@1"
_BOOTSTRAP_PROFILE = "tetris-pre-one-cell-bootstrap-matrix@1"
_TASK_MAP_PROFILE = "tetris-pre-one-cell-task-map@1"
_TASK_ROW_PROFILE = "tetris-pre-one-cell-task-row@1"
_BRANCH_PROFILE = "tetris-pre-one-cell-horizon-branch@1"
_SCIENTIFIC_IDENTITY_PROFILE = "tetris-pre-one-cell-scientific-identity@1"

_ARTICLE_COMMIT = "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
_PROTOCOL_PATH = "PRE-DISCOVERY-PROTOCOL.md"
_PROTOCOL_BLOB = "b7b654bb8d2809c409ce6ca24eb21d3afebf7885"
_PROTOCOL_SHA256 = "ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358"
_PROTOCOL_SIZE_BYTES = 44_883

_BOUNDARY_LAW_TYPE = OneCellBoundaryLaw
_PERIODIC = _BOUNDARY_LAW_TYPE.PERIODIC
_LEGACY = _BOUNDARY_LAW_TYPE.HARD_WALL_LEGACY_ASYMMETRIC
_CORRECTED = _BOUNDARY_LAW_TYPE.HARD_WALL_REFLECTION_SYMMETRIC
_BOUNDARY_ORDER = (_LEGACY, _CORRECTED, _PERIODIC)

_PRIMARY = (0, 1, 2, 5, 10, 25, 50, 100)
_B1 = (0, 5, 50, 100)
_B2_FULL = (5, 50, 90, 95, 98, 99)
_B2_HIGH = (90, 95, 98, 99)
_SCHEDULES = (
    ("primary", _PRIMARY),
    ("b1", _B1),
    ("b2-full", _B2_FULL),
    ("b2-high", _B2_HIGH),
)

_SNAPSHOT_INDICES = (0, 34, 68, 102, 136, 170, 204, 238, 273, 307, 341, 375, 409, 443, 477, 511)
_BASE_HORIZONS = (
    (32, 17_378),
    (64, 98_304),
    (128, 556_092),
    (256, 3_145_728),
    (512, 17_794_925),
    (1024, 100_663_296),
)
_DOUBLE_HORIZONS = (
    (64, 196_608),
    (128, 1_112_184),
    (256, 6_291_456),
    (512, 35_589_850),
    (1024, 201_326_592),
)
_HISTORICAL_HORIZONS = (
    (50, 55_000),
    (80, 172_800),
    (100, 300_000),
    (150, 832_500),
    (200, 1_720_000),
    (250, 3_000_000),
    (300, 4_680_000),
    (400, 9_600_000),
    (500, 17_000_000),
)
_CHECKPOINT_HASHES = (
    (
        17_378,
        "c5f252e41428324b6a58b895a0ad65b6ddee5268151af5219d378c04d640dcb9",
        "79389924acde634cd0cddaefbfc6e2bb6839a68a763effb9496588c2903b507d",
    ),
    (
        98_304,
        "b8d26f0e73cf752314bf7ee3388aeeea0ee41b4819a42127fd68e5b135827032",
        "96e48ce2fd2c948f44f2961ad03ba1b766e7c87e6472eeadaffd8a404738415d",
    ),
    (
        556_092,
        "41578b77509fe146d70408aaf55272fe5bac38ef616eb24c035d63b63302feb6",
        "7486fb0f92727fc7e4dd67ba3f1c085362777a199aaa087fdac7ceb137fcc9f9",
    ),
    (
        3_145_728,
        "869b84cade7b61149518e6af883b6d3a4deaf98a9523767ff25006c0987409a6",
        "fd240cc0be43c3d1e905cb9595e4582e573949acc0326c383da01565ab65f7c3",
    ),
    (
        17_794_925,
        "9cd08fa3a59c3675010d9b74ad0f58b865a01319897d455b1b136d9bdd313d93",
        "956200791790695ff3fbdf84bab9186535d7610345cf9906bbe419cf9989ba7c",
    ),
    (
        100_663_296,
        "994a06cf3188ab1107e78711538d440d02dfa53613f0d0076b4698a0b33a4fa5",
        "14dad3915d170fbdb5b1dc5dcf49e57a16705f53e5577b07ab776f1bac6f8bf0",
    ),
    (
        196_608,
        "936a8fccb9627eeeb83c8f0b1e4bca18bd1c71ab0ce059e64208429756dfc004",
        "3a42f697a184cc3a2ded8d21176fc0d4e2527a8c16a382e83487d8583c778ae6",
    ),
    (
        1_112_184,
        "248edcaa55f0d2f9697f85c22543db3f546efd7cabc0e28e2ec17c2f7ef19309",
        "09b09e3361eb3f0b4d6b6fdc7f70c3a25e1b55698472740241cec9e09b9232d0",
    ),
    (
        6_291_456,
        "82839103c39b0ca7923b248d20bd8cb028b5b558b45173cca0f85270cdcd59d4",
        "86efc0ca42e97478ae47c750694ae9ae535fdbd8a3727dcebd961545bc5a1183",
    ),
    (
        35_589_850,
        "c525069e5975a8ee388106f5384aa9d0653fabd71c1871f224016272bedd8456",
        "d2e2b0fc33004810f742944bb91d68e9a25c75df161a85b8215956db8fb05251",
    ),
    (
        201_326_592,
        "f4bae89fe9c8c021feb70141cb56ffaecfff5306c0afa10abd42041658d1726c",
        "0c18e9ef5c63a5fab0ca580654a05c3194119ebf31f30471a5ebb42b7cf7074c",
    ),
    (
        55_000,
        "8a03e3f93b3e42bd0f910ad4fbaafdce0dfa4ed2046ae82b0b4bc90340ad6651",
        "0d16f0029d3005d7f6a4e7ca44edfd423efb3e6813bb083f19bb9bec39aefd18",
    ),
    (
        172_800,
        "701e6c91bbb7b820116c92bfccc77345c1ca5e3d716d63fe65dc3e969ece1009",
        "08e08b8a18e56e40f0d42b57a68e12824c57d54459d6a2ff55ea694ffd828d6a",
    ),
    (
        300_000,
        "7b7f858cb2d8f5b17dfff5ec260fb58e6db72ea5e4215813bc14eb5858d433ed",
        "cb3898903dce3de1ff40e180a048497738377f06096f11dd3961599242b05d79",
    ),
    (
        832_500,
        "2c075c44db4bbc2631311ae3ae951588baf21c478996d42a6f407f8829f16afe",
        "95509683f214af140a151757e32d5328a42af1cf0cdcac1cc3c0ca4f0f70ae50",
    ),
    (
        1_720_000,
        "674be7c67dbb7c3f5d862b56aa4b7b8e28eba852a3a011464996ed613b80dc45",
        "d9168485f4a6038031f0acad624403158f2b87adb7aa812e5606699e87a837c2",
    ),
    (
        3_000_000,
        "22b9c06b7a000ac0551f2fd0c24b41df2810e7b463b44eec18e977cfd28678aa",
        "252961c6e2377531ca839458b2a6afd93abda7ed05ca9be74c96a484683c926f",
    ),
    (
        4_680_000,
        "b255c3ce257304146d9164a9fb42d4b728b5193db6381136f1d9c3be862ec57e",
        "6e9533e9ea6e0d54671b080696b463bd696d3898f7dcf803eaeeb4f0e68f6428",
    ),
    (
        9_600_000,
        "534fbd426e7a98b52748a4613257cb02d82cb136ee89fef895d58a958a0fbdd7",
        "5d24d8fd1d5d03ee6cb9e752e51fa0379c324ae1262ac20305d1571c81ee9f55",
    ),
    (
        17_000_000,
        "11e113a51521f2b9380df8f267e1463b98c7ff76a68edd3cb37d4ebd920ffedd",
        "862af4374766af7dede636fb1a2e195b0c827b3a5faa44ea4e1fea62d0fd4765",
    ),
)


class OneCellCampaignValidationError(RuntimeError):
    """Untrusted campaign or task-map bytes failed exact validation."""


class _SealedRecordMeta(type):
    """Prevent normal runtime mutation after record classes are initialized."""

    def __setattr__(cls, name: str, value: object, _error: type[TypeError] = TypeError) -> None:
        if cls.__dict__.get("_runtime_sealed", False):
            raise _error("campaign record classes are runtime sealed")
        type.__setattr__(cls, name, value)


class _SealedRecord(metaclass=_SealedRecordMeta):
    """Marker base whose closure-bound construction gate is installed at import."""

    __slots__ = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellBootstrapMatrixIdentity(_SealedRecord):
    cohort_id: str
    profile: str
    member_path: str
    shape: tuple[int, int]
    seed: int
    generator: str
    bit_generator: str
    numpy_version: str
    distribution: str
    dtype: str
    byte_order: str
    order: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _validate_bootstrap_record(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellTaskMapIdentity(_SealedRecord):
    task_map_id: str
    profile: str
    member_path: str
    wave: str
    role: str
    horizon_branch_id: str
    task_count: int
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _validate_task_map_identity_record(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellHorizonBranch(_SealedRecord):
    branch_id: str
    profile: str
    l_star: int | None
    confirmation_required: bool
    confirmation_terminal_event_count: int | None
    p1_terminal_event_counts: tuple[tuple[int, int], ...]
    p1_task_map_id: str

    def __post_init__(self) -> None:
        _validate_branch_record(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellCampaignAuthority(_SealedRecord):
    configuration_bytes: bytes
    configuration_sha256: str
    profile: str
    protocol_commit: str
    protocol_path: str
    protocol_blob: str
    protocol_sha256: str
    protocol_size_bytes: int
    bootstrap_matrices: tuple[OneCellBootstrapMatrixIdentity, ...]
    task_maps: tuple[OneCellTaskMapIdentity, ...]
    horizon_branches: tuple[OneCellHorizonBranch, ...]
    checkpoint_terminals: tuple[int, ...]
    task_map_members: tuple[tuple[str, bytes], ...]

    def __post_init__(self) -> None:
        _validate_campaign_authority_record(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class OneCellCampaignTask(_SealedRecord):
    task_map_id: str
    task_map_sha256: str
    wave: str
    role: str
    included_in_inference: bool
    task_index: int
    horizon_branch_id: str
    boundary_law: OneCellBoundaryLaw
    width: int
    root_seed: int
    root_offset: int
    threshold_schedule_id: str
    threshold_schedule: tuple[int, ...]
    terminal_event_count: int
    checkpoint_event_counts: tuple[int, ...]
    checkpoint_vector_sha256: str
    snapshot_checkpoint_indices: tuple[int, ...]
    snapshot_event_counts: tuple[int, ...]
    snapshot_vector_sha256: str
    bootstrap_cohort_id: str | None
    bootstrap_population_index: int | None

    def __post_init__(self) -> None:
        _validate_campaign_task_record(self)


_VALIDATION_ERROR_TYPE = OneCellCampaignValidationError
_BOOTSTRAP_IDENTITY_TYPE = OneCellBootstrapMatrixIdentity
_TASK_MAP_IDENTITY_TYPE = OneCellTaskMapIdentity
_HORIZON_BRANCH_TYPE = OneCellHorizonBranch
_CAMPAIGN_AUTHORITY_TYPE = OneCellCampaignAuthority
_CAMPAIGN_TASK_TYPE = OneCellCampaignTask


@dataclass(frozen=True, slots=True)
class _MapSpec:
    task_map_id: str
    member_path: str
    wave: str
    role: str
    horizon_branch_id: str
    boundaries: tuple[OneCellBoundaryLaw, ...]
    widths: tuple[int, ...]
    root_start: int
    root_count: int
    included_in_inference: bool
    bootstrap_cohort_id: str | None

    @property
    def task_count(self) -> int:
        return len(self.boundaries) * len(self.widths) * self.root_count


_MAP_SPECS = (
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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
    _MapSpec(
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

_BOOTSTRAP_SPECS = (
    ("p0", "bootstrap/p0.u16le", (10_000, 16), 2_026_071_500, 320_000),
    ("p1", "bootstrap/p1.u16le", (10_000, 96), 2_026_071_501, 1_920_000),
    ("b1", "bootstrap/b1.u16le", (10_000, 32), 2_026_071_502, 640_000),
    ("b2", "bootstrap/b2.u16le", (10_000, 100), 2_026_071_503, 2_000_000),
)

_CAPTURED_MAP_SPECS = _MAP_SPECS
_CAPTURED_MAP_SPEC_TYPE = _MapSpec
_CAPTURED_MAP_SPEC_TASK_COUNT = _MapSpec.task_count
_CAPTURED_MAP_SPEC_VALUES = tuple(
    (
        spec.task_map_id,
        spec.member_path,
        spec.wave,
        spec.role,
        spec.horizon_branch_id,
        tuple(object.__getattribute__(boundary, "_value_") for boundary in spec.boundaries),
        spec.widths,
        spec.root_start,
        spec.root_count,
        spec.included_in_inference,
        spec.bootstrap_cohort_id,
    )
    for spec in _MAP_SPECS
)
_CAPTURED_BOOTSTRAP_SPECS = _BOOTSTRAP_SPECS
_CAPTURED_SCHEDULES = _SCHEDULES
_CAPTURED_BASE_HORIZONS = _BASE_HORIZONS
_CAPTURED_DOUBLE_HORIZONS = _DOUBLE_HORIZONS
_CAPTURED_HISTORICAL_HORIZONS = _HISTORICAL_HORIZONS
_CAPTURED_CHECKPOINT_HASHES = _CHECKPOINT_HASHES


def _assert_contract_integrity_core(
    *,
    module_globals: dict[str, object],
    integrity_error: type[AssertionError],
    module_bindings: tuple[tuple[str, object], ...],
    codec_lookup: object,
    strict_error_handler: object,
    imported_modules: tuple[tuple[object, ...], ...],
    imported_attributes: tuple[tuple[str, object, str, object], ...],
    class_attributes: tuple[tuple[object, ...], ...],
    public_export_list: list[str],
    public_exports: tuple[str, ...],
    protected_aliases: tuple[tuple[str, object], ...],
    authority_functions: tuple[tuple[str, object], ...],
    map_specs: tuple[_MapSpec, ...],
    map_spec_type: type[_MapSpec],
    map_spec_task_count: property,
    map_spec_values: tuple[tuple[object, ...], ...],
    bootstrap_specs: tuple[tuple[object, ...], ...],
    schedules: tuple[tuple[str, tuple[int, ...]], ...],
    base_horizons: tuple[tuple[int, int], ...],
    double_horizons: tuple[tuple[int, int], ...],
    historical_horizons: tuple[tuple[int, int], ...],
    checkpoint_hashes: tuple[tuple[int, str, str], ...],
) -> None:
    """Fail closed if a frozen campaign authority object was rebound or mutated."""

    if module_globals.get("_CAPTURED_MODULE_BINDINGS") is not module_bindings:
        raise integrity_error("captured campaign module bindings have been rebound")
    for name, value in module_bindings:
        if module_globals.get(name) is not value:
            raise integrity_error(f"campaign module binding {name!r} has been rebound")
    for label, module, module_type, bindings, mutable_states in imported_modules:
        if type(module) is not module_type or len(module.__dict__) != len(bindings):
            raise integrity_error(f"campaign imported module {label!r} has been mutated")
        for name, value in bindings:
            if module.__dict__.get(name) is not value:
                raise integrity_error(f"campaign imported module binding {label}.{name} has been rebound")
        for kind, name, value, snapshot in mutable_states:
            if kind == "dict":
                if len(value) != len(snapshot):
                    raise integrity_error(f"campaign imported module state {label}.{name} has been mutated")
                for key, item in snapshot:
                    if value.get(key) is not item:
                        raise integrity_error(f"campaign imported module state {label}.{name}.{key} has been mutated")
            elif kind == "list":
                if len(value) != len(snapshot) or any(
                    current is not expected for current, expected in zip(value, snapshot)
                ):
                    raise integrity_error(f"campaign imported module state {label}.{name} has been mutated")
            else:
                raise integrity_error("campaign imported module snapshot has an unknown kind")
    for label, module, attribute, value in imported_attributes:
        if module.__dict__.get(attribute) is not value:
            raise integrity_error(f"campaign imported binding {label!r} has been rebound")
    if codec_lookup("strict") is not strict_error_handler:
        raise integrity_error("the strict Unicode codec error handler has been rebound")
    for (
        label,
        class_type,
        attributes,
        bases,
        method_resolution_order,
        metaclass,
        mutable_states,
    ) in class_attributes:
        current_attributes = type.__getattribute__(class_type, "__dict__")
        if (
            type(class_type) is not metaclass
            or type.__getattribute__(class_type, "__bases__") != bases
            or type.__getattribute__(class_type, "__mro__") != method_resolution_order
            or len(current_attributes) != len(attributes)
        ):
            raise integrity_error(f"campaign class binding {label!r} has been mutated")
        for attribute, value in attributes:
            if current_attributes.get(attribute) is not value:
                raise integrity_error(f"campaign class binding {label}.{attribute} has been rebound")
        for kind, state_label, value, snapshot in mutable_states:
            if kind == "dict":
                if len(value) != len(snapshot):
                    raise integrity_error(f"campaign class state {label}.{state_label} has been mutated")
                for name, item in snapshot:
                    if value.get(name) is not item:
                        raise integrity_error(f"campaign class state {label}.{state_label}.{name} has been mutated")
            elif kind == "list":
                if len(value) != len(snapshot) or any(
                    current is not expected for current, expected in zip(value, snapshot)
                ):
                    raise integrity_error(f"campaign class state {label}.{state_label} has been mutated")
            elif kind == "slots":
                for name, item in snapshot:
                    if object.__getattribute__(value, name) is not item:
                        raise integrity_error(f"campaign class state {label}.{state_label}.{name} has been mutated")
            else:
                raise integrity_error("campaign class state snapshot has an unknown kind")
    if module_globals.get("__all__") is not public_export_list or tuple(public_export_list) != public_exports:
        raise integrity_error("campaign public export authority has been rebound or mutated")
    if (
        OneCellCampaignValidationError is not _VALIDATION_ERROR_TYPE
        or OneCellBootstrapMatrixIdentity is not _BOOTSTRAP_IDENTITY_TYPE
        or OneCellTaskMapIdentity is not _TASK_MAP_IDENTITY_TYPE
        or OneCellHorizonBranch is not _HORIZON_BRANCH_TYPE
        or OneCellCampaignAuthority is not _CAMPAIGN_AUTHORITY_TYPE
        or OneCellCampaignTask is not _CAMPAIGN_TASK_TYPE
        or OneCellBoundaryLaw is not _BOUNDARY_LAW_TYPE
    ):
        raise integrity_error("public campaign authority aliases have been rebound")
    if (
        _MapSpec is not map_spec_type
        or _MapSpec.task_count is not map_spec_task_count
        or _MAP_SPECS is not map_specs
        or _CAPTURED_MAP_SPECS is not map_specs
        or _CAPTURED_MAP_SPEC_TYPE is not map_spec_type
        or _CAPTURED_MAP_SPEC_TASK_COUNT is not map_spec_task_count
        or _CAPTURED_MAP_SPEC_VALUES is not map_spec_values
        or _BOOTSTRAP_SPECS is not bootstrap_specs
        or _CAPTURED_BOOTSTRAP_SPECS is not bootstrap_specs
        or _SCHEDULES is not schedules
        or _CAPTURED_SCHEDULES is not schedules
        or _BASE_HORIZONS is not base_horizons
        or _CAPTURED_BASE_HORIZONS is not base_horizons
        or _DOUBLE_HORIZONS is not double_horizons
        or _CAPTURED_DOUBLE_HORIZONS is not double_horizons
        or _HISTORICAL_HORIZONS is not historical_horizons
        or _CAPTURED_HISTORICAL_HORIZONS is not historical_horizons
        or _CHECKPOINT_HASHES is not checkpoint_hashes
        or _CAPTURED_CHECKPOINT_HASHES is not checkpoint_hashes
    ):
        raise integrity_error("private campaign authority tables have been rebound")
    current_map_spec_values: list[tuple[object, ...]] = []
    for spec in map_specs:
        if (
            type(spec) is not map_spec_type
            or type(spec.task_map_id) is not str
            or type(spec.member_path) is not str
            or type(spec.wave) is not str
            or type(spec.role) is not str
            or type(spec.horizon_branch_id) is not str
            or type(spec.boundaries) is not tuple
            or any(type(boundary) is not _BOUNDARY_LAW_TYPE for boundary in spec.boundaries)
            or type(spec.widths) is not tuple
            or any(type(width) is not int for width in spec.widths)
            or type(spec.root_start) is not int
            or type(spec.root_count) is not int
            or type(spec.included_in_inference) is not bool
            or (spec.bootstrap_cohort_id is not None and type(spec.bootstrap_cohort_id) is not str)
        ):
            raise integrity_error("private campaign map specifications have invalid runtime types")
        current_map_spec_values.append(
            (
                spec.task_map_id,
                spec.member_path,
                spec.wave,
                spec.role,
                spec.horizon_branch_id,
                tuple(object.__getattribute__(boundary, "_value_") for boundary in spec.boundaries),
                spec.widths,
                spec.root_start,
                spec.root_count,
                spec.included_in_inference,
                spec.bootstrap_cohort_id,
            )
        )
    if tuple(current_map_spec_values) != map_spec_values:
        raise integrity_error("private campaign map specifications have been mutated")
    if (
        _CAPTURED_PROTECTED_ALIASES is not protected_aliases
        or any(module_globals.get(name) is not value for name, value in protected_aliases)
        or _CAPTURED_AUTHORITY_FUNCTIONS is not authority_functions
        or any(module_globals.get(name) is not function for name, function in authority_functions)
        or _CERTIFIED_PROTOCOL_RECORD is not _CAPTURED_PROTOCOL_RECORD
        or _CERTIFIED_MODEL_RECORD is not _CAPTURED_MODEL_RECORD
        or _CERTIFIED_EXECUTION_RECORD is not _CAPTURED_EXECUTION_RECORD
    ):
        raise integrity_error("private campaign authority functions have been rebound")
    if (
        _CAMPAIGN_PROFILE != "tetris-pre-one-cell-campaign@1"
        or _BOOTSTRAP_PROFILE != "tetris-pre-one-cell-bootstrap-matrix@1"
        or _TASK_MAP_PROFILE != "tetris-pre-one-cell-task-map@1"
        or _TASK_ROW_PROFILE != "tetris-pre-one-cell-task-row@1"
        or _BRANCH_PROFILE != "tetris-pre-one-cell-horizon-branch@1"
        or _SCIENTIFIC_IDENTITY_PROFILE != "tetris-pre-one-cell-scientific-identity@1"
        or _ARTICLE_COMMIT != "85404aee4dab7ade81c6893fac9f34aeaddf50dd"
        or _PROTOCOL_PATH != "PRE-DISCOVERY-PROTOCOL.md"
        or _PROTOCOL_BLOB != "b7b654bb8d2809c409ce6ca24eb21d3afebf7885"
        or _PROTOCOL_SHA256 != "ab2f2974daf27f70af76d3039f6ac6c9b2cdecfba30a4c4a2ebd3d3652874358"
        or _PROTOCOL_SIZE_BYTES != 44_883
    ):
        raise integrity_error("campaign profile or protocol authority has been rebound")
    boundary_member_map = type.__getattribute__(_BOUNDARY_LAW_TYPE, "_member_map_")
    boundary_member_names = type.__getattribute__(_BOUNDARY_LAW_TYPE, "_member_names_")
    boundary_value_map = type.__getattribute__(_BOUNDARY_LAW_TYPE, "_value2member_map_")
    if (
        type(boundary_member_map) is not dict
        or tuple(boundary_member_map.items())
        != (
            ("PERIODIC", _PERIODIC),
            ("HARD_WALL_LEGACY_ASYMMETRIC", _LEGACY),
            ("HARD_WALL_REFLECTION_SYMMETRIC", _CORRECTED),
        )
        or type(boundary_member_names) is not list
        or tuple(boundary_member_names)
        != (
            "PERIODIC",
            "HARD_WALL_LEGACY_ASYMMETRIC",
            "HARD_WALL_REFLECTION_SYMMETRIC",
        )
        or type(boundary_value_map) is not dict
        or len(boundary_value_map) != 3
        or boundary_value_map.get("periodic-v1") is not _PERIODIC
        or boundary_value_map.get("hard-wall-legacy-asymmetric-v1") is not _LEGACY
        or boundary_value_map.get("hard-wall-reflection-symmetric-v1") is not _CORRECTED
        or type(object.__getattribute__(_PERIODIC, "_name_")) is not str
        or object.__getattribute__(_PERIODIC, "_name_") != "PERIODIC"
        or type(object.__getattribute__(_LEGACY, "_name_")) is not str
        or object.__getattribute__(_LEGACY, "_name_") != "HARD_WALL_LEGACY_ASYMMETRIC"
        or type(object.__getattribute__(_CORRECTED, "_name_")) is not str
        or object.__getattribute__(_CORRECTED, "_name_") != "HARD_WALL_REFLECTION_SYMMETRIC"
        or type(object.__getattribute__(_PERIODIC, "_value_")) is not str
        or object.__getattribute__(_PERIODIC, "_value_") != "periodic-v1"
        or type(object.__getattribute__(_LEGACY, "_value_")) is not str
        or object.__getattribute__(_LEGACY, "_value_") != "hard-wall-legacy-asymmetric-v1"
        or type(object.__getattribute__(_CORRECTED, "_value_")) is not str
        or object.__getattribute__(_CORRECTED, "_value_") != "hard-wall-reflection-symmetric-v1"
        or _BOUNDARY_ORDER != (_LEGACY, _CORRECTED, _PERIODIC)
        or _SCHEDULES
        != (
            ("primary", (0, 1, 2, 5, 10, 25, 50, 100)),
            ("b1", (0, 5, 50, 100)),
            ("b2-full", (5, 50, 90, 95, 98, 99)),
            ("b2-high", (90, 95, 98, 99)),
        )
    ):
        raise integrity_error("campaign boundary or threshold authority has been rebound")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: object, *, newline: bool) -> bytes:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise OneCellCampaignValidationError("value is not canonical JSON data") from error
    return encoded + (b"\n" if newline else b"")


def _parse_int(text: str) -> int:
    if len(text) > 40 or _INTEGER.fullmatch(text) is None:
        raise OneCellCampaignValidationError("JSON integer is outside the exact canonical grammar")
    return int(text)


def _reject_float(_text: str) -> object:
    raise OneCellCampaignValidationError("floating-point JSON values are forbidden")


def _reject_constant(_text: str) -> object:
    raise OneCellCampaignValidationError("nonfinite JSON values are forbidden")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if type(key) is not str:
            raise OneCellCampaignValidationError("JSON object keys must be built-in strings")
        if key in result:
            raise OneCellCampaignValidationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _check_json_shape(value: object, *, depth: int = 0, counter: list[int] | None = None) -> None:
    if counter is None:
        counter = [0]
    counter[0] += 1
    if counter[0] > _JSON_NODE_LIMIT:
        raise OneCellCampaignValidationError("JSON document contains too many values")
    if depth > _JSON_DEPTH_LIMIT:
        raise OneCellCampaignValidationError("JSON document is nested too deeply")
    if type(value) is dict:
        for key, member in value.items():
            if type(key) is not str:
                raise OneCellCampaignValidationError("JSON object keys must be built-in strings")
            _check_json_shape(member, depth=depth + 1, counter=counter)
    elif type(value) is list:
        for member in value:
            _check_json_shape(member, depth=depth + 1, counter=counter)
    elif type(value) not in (str, int, bool, type(None)):
        raise OneCellCampaignValidationError("JSON value has a forbidden runtime type")


def _decode_canonical_json(
    value: object,
    *,
    label: str,
    size_limit: int,
    newline: bool,
) -> object:
    if type(value) is not bytes:
        raise TypeError(f"{label} must be built-in bytes")
    if not value or len(value) > size_limit:
        raise ValueError(f"{label} must contain 1 through {size_limit} bytes")
    try:
        text = value.decode("utf-8", errors="strict")
        decoded = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_int=_parse_int,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
        _check_json_shape(decoded)
        canonical = _canonical_json(decoded, newline=newline)
    except OneCellCampaignValidationError:
        raise
    except (UnicodeDecodeError, UnicodeEncodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise OneCellCampaignValidationError(f"{label} is not strict canonical JSON") from error
    if canonical != value:
        raise OneCellCampaignValidationError(f"{label} is not encoded in the frozen canonical form")
    return decoded


def _require_exact_dict(value: object, *, keys: tuple[str, ...], label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise OneCellCampaignValidationError(f"{label} must be a JSON object")
    if tuple(sorted(value)) != tuple(sorted(keys)):
        raise OneCellCampaignValidationError(f"{label} has missing or unknown keys")
    return value


def _require_list(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        raise OneCellCampaignValidationError(f"{label} must be a JSON array")
    return value


def _require_str(value: object, *, label: str) -> str:
    if type(value) is not str:
        raise OneCellCampaignValidationError(f"{label} must be a built-in string")
    return value


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise OneCellCampaignValidationError(f"{label} must be a built-in integer")
    return value


def _require_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise OneCellCampaignValidationError(f"{label} must be a built-in Boolean")
    return value


def _require_optional_int(value: object, *, label: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, label=label)


def _require_sha256(value: object, *, label: str) -> str:
    result = _require_str(value, label=label)
    if _HEX64.fullmatch(result) is None:
        raise OneCellCampaignValidationError(f"{label} must be 64 lowercase hexadecimal characters")
    return result


def _require_member_path(value: object, *, label: str) -> str:
    result = _require_str(value, label=label)
    if len(result) > 255 or _SAFE_MEMBER.fullmatch(result) is None:
        raise OneCellCampaignValidationError(f"{label} is not a safe canonical relative POSIX path")
    if any(len(component) > 80 for component in result.split("/")):
        raise OneCellCampaignValidationError(f"{label} contains an overlong path component")
    return result


def _expected_protocol_record() -> dict[str, object]:
    return {
        "article_commit": _ARTICLE_COMMIT,
        "protocol_blob": _PROTOCOL_BLOB,
        "protocol_path": _PROTOCOL_PATH,
        "protocol_sha256": _PROTOCOL_SHA256,
        "protocol_size_bytes": _PROTOCOL_SIZE_BYTES,
    }


def _expected_model_record() -> dict[str, object]:
    return {
        "boundary_law_order": [_PERIODIC.value, _LEGACY.value, _CORRECTED.value],
        "clean_model_id": "one-cell-rd-bd-periodic-v1",
        "contact_denominator": 100,
        "counter_fields": ["event-ordinal-zero-based", "rejection-ordinal", "zero", "zero"],
        "coupling_group": "pre-one-cell-discovery-v1",
        "initial_height": 0,
        "rng_algorithm": "semantic-philox4x64-10-v1",
        "root_seed_encoding": "unsigned-128-numerical-v1",
        "stream_order": ["launch", "contact"],
        "threshold_schedules": [
            {"schedule_id": schedule_id, "thresholds": list(thresholds)} for schedule_id, thresholds in _SCHEDULES
        ],
    }


def _expected_inventories() -> list[dict[str, object]]:
    return [
        {
            "arm_count": 40,
            "boundary_order": [_LEGACY.value, _CORRECTED.value],
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
            "boundary_order": [_PERIODIC.value],
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
            "boundary_order": [_PERIODIC.value],
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
            "boundary_order": [_PERIODIC.value],
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
            "boundary_order": [_LEGACY.value, _CORRECTED.value, _PERIODIC.value],
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
            "boundary_order": [_LEGACY.value, _CORRECTED.value],
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


def _expected_execution_record() -> dict[str, object]:
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
            "terminal_event_count_upper_exclusive": _U64_LIMIT,
            "width_times_terminal_upper_exclusive": _U64_LIMIT,
            "width_times_terminal_squared_upper_exclusive": _U128_LIMIT,
        },
        "inventories": _expected_inventories(),
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


_CERTIFIED_PROTOCOL_RECORD = _expected_protocol_record
_CERTIFIED_MODEL_RECORD = _expected_model_record
_CERTIFIED_EXECUTION_RECORD = _expected_execution_record
_CAPTURED_PROTOCOL_RECORD = _CERTIFIED_PROTOCOL_RECORD
_CAPTURED_MODEL_RECORD = _CERTIFIED_MODEL_RECORD
_CAPTURED_EXECUTION_RECORD = _CERTIFIED_EXECUTION_RECORD


def _map_spec(task_map_id: str) -> _MapSpec:
    for spec in _CAPTURED_MAP_SPECS:
        if spec.task_map_id == task_map_id:
            return spec
    raise ValueError("task_map_id is not one of the nine frozen task maps")


def _schedule(schedule_id: str) -> tuple[int, ...]:
    for candidate_id, thresholds in _SCHEDULES:
        if candidate_id == schedule_id:
            return thresholds
    raise AssertionError("unknown private threshold schedule")


def _terminal_for(*, spec: _MapSpec, width: int) -> int:
    if spec.task_map_id == "p0-confirmation":
        return 201_326_592
    if spec.task_map_id.startswith("p1-"):
        base = dict(_BASE_HORIZONS)[width]
        if spec.task_map_id == "p1-no-l-star":
            return base
        l_star = int(spec.task_map_id.rsplit("-", 1)[1])
        return dict(_DOUBLE_HORIZONS)[width] if width >= l_star else base
    if spec.task_map_id in {"f0", "b2"}:
        return dict(_HISTORICAL_HORIZONS)[width]
    return dict(_BASE_HORIZONS)[width]


def _schedule_id_for(*, spec: _MapSpec, width: int) -> str:
    if spec.task_map_id == "b1":
        return "b1"
    if spec.task_map_id in {"f0", "b2"}:
        return "b2-high" if width >= 400 else "b2-full"
    return "primary"


def _expected_task_row(*, spec: _MapSpec, task_index: int) -> dict[str, object]:
    if type(task_index) is not int:
        raise TypeError("task_index must be a built-in integer")
    if not 0 <= task_index < spec.task_count:
        raise ValueError(f"task_index must lie in [0, {spec.task_count})")
    per_boundary = len(spec.widths) * spec.root_count
    boundary_index, remainder = divmod(task_index, per_boundary)
    width_index, root_offset = divmod(remainder, spec.root_count)
    boundary_law = spec.boundaries[boundary_index]
    width = spec.widths[width_index]
    return {
        "boundary_law": boundary_law.value,
        "profile": _TASK_ROW_PROFILE,
        "root_offset": root_offset,
        "root_seed": spec.root_start + root_offset,
        "task_index": task_index,
        "terminal_event_count": _terminal_for(spec=spec, width=width),
        "threshold_schedule_id": _schedule_id_for(spec=spec, width=width),
        "width": width,
    }


def _vector_hashes(terminal: int) -> tuple[str, str]:
    for candidate, checkpoint_hash, snapshot_hash in _CHECKPOINT_HASHES:
        if candidate == terminal:
            return checkpoint_hash, snapshot_hash
    raise AssertionError("task terminal is outside the 20 frozen checkpoint vectors")


def _bootstrap_spec(cohort_id: str) -> tuple[str, str, tuple[int, int], int, int]:
    for candidate in _CAPTURED_BOOTSTRAP_SPECS:
        if candidate[0] == cohort_id:
            return candidate
    raise ValueError("cohort_id is outside the four bootstrap authorities")


def _validate_bootstrap_record(value: object, *, _integrity_checked: bool = False) -> None:
    if not _integrity_checked:
        _assert_contract_integrity()
    if type(value) is not _BOOTSTRAP_IDENTITY_TYPE:
        raise TypeError("bootstrap identity must be an exact OneCellBootstrapMatrixIdentity")
    string_fields = (
        "cohort_id",
        "profile",
        "member_path",
        "generator",
        "bit_generator",
        "numpy_version",
        "distribution",
        "dtype",
        "byte_order",
        "order",
        "sha256",
    )
    if any(type(getattr(value, field)) is not str for field in string_fields):
        raise TypeError("bootstrap identity text fields must be built-in strings")
    if type(value.shape) is not tuple or any(type(item) is not int for item in value.shape):
        raise TypeError("bootstrap shape must be an exact tuple of built-in integers")
    if type(value.seed) is not int or type(value.size_bytes) is not int:
        raise TypeError("bootstrap seed and size must be built-in integers")
    cohort_id = value.cohort_id
    expected = _bootstrap_spec(cohort_id)
    if (
        value.profile != _BOOTSTRAP_PROFILE
        or value.member_path != expected[1]
        or value.shape != expected[2]
        or value.seed != expected[3]
        or value.generator != "numpy.random.Generator"
        or value.bit_generator != "PCG64DXSM"
        or value.distribution != "integers-half-open-one-call-v1"
        or value.dtype != "uint16"
        or value.byte_order != "little"
        or value.order != "C"
        or value.size_bytes != expected[4]
    ):
        raise ValueError("bootstrap identity does not match the frozen cohort contract")
    if _VERSION.fullmatch(value.numpy_version) is None:
        raise ValueError("numpy_version must be one exact release identity")
    if _HEX64.fullmatch(value.sha256) is None:
        raise ValueError("bootstrap sha256 must be 64 lowercase hexadecimal characters")


def _validate_task_map_identity_record(value: object, *, _integrity_checked: bool = False) -> None:
    if not _integrity_checked:
        _assert_contract_integrity()
    if type(value) is not _TASK_MAP_IDENTITY_TYPE:
        raise TypeError("task-map identity must be an exact OneCellTaskMapIdentity")
    string_fields = (
        "task_map_id",
        "profile",
        "member_path",
        "wave",
        "role",
        "horizon_branch_id",
        "sha256",
    )
    if any(type(getattr(value, field)) is not str for field in string_fields):
        raise TypeError("task-map identity text fields must be built-in strings")
    if type(value.task_count) is not int or type(value.size_bytes) is not int:
        raise TypeError("task-map counts and sizes must be built-in integers")
    spec = _map_spec(value.task_map_id)
    if (
        value.profile != _TASK_MAP_PROFILE
        or value.member_path != spec.member_path
        or value.wave != spec.wave
        or value.role != spec.role
        or value.horizon_branch_id != spec.horizon_branch_id
        or value.task_count != spec.task_count
        or not 1 <= value.size_bytes <= _TASK_MAP_LIMIT
        or _HEX64.fullmatch(value.sha256) is None
    ):
        raise ValueError("task-map identity does not match the frozen map contract")


def _expected_branch(branch_id: str) -> tuple[int | None, tuple[tuple[int, int], ...], bool, int | None, str]:
    if branch_id == "p1-no-l-star":
        return None, tuple(_BASE_HORIZONS[1:]), False, None, branch_id
    if branch_id not in {"p1-l-star-64", "p1-l-star-256", "p1-l-star-1024"}:
        raise ValueError("branch_id is outside the four frozen P1 branches")
    l_star = int(branch_id.rsplit("-", 1)[1])
    terminals = tuple(
        (width, dict(_DOUBLE_HORIZONS)[width] if width >= l_star else terminal)
        for width, terminal in _BASE_HORIZONS[1:]
    )
    return l_star, terminals, True, 201_326_592, branch_id


def _validate_branch_record(value: object, *, _integrity_checked: bool = False) -> None:
    if not _integrity_checked:
        _assert_contract_integrity()
    if type(value) is not _HORIZON_BRANCH_TYPE:
        raise TypeError("horizon branch must be an exact OneCellHorizonBranch")
    if any(type(item) is not str for item in (value.branch_id, value.profile, value.p1_task_map_id)):
        raise TypeError("horizon branch text fields must be built-in strings")
    if value.l_star is not None and type(value.l_star) is not int:
        raise TypeError("l_star must be a built-in integer or None")
    if type(value.confirmation_required) is not bool:
        raise TypeError("confirmation_required must be a built-in Boolean")
    if value.confirmation_terminal_event_count is not None and type(value.confirmation_terminal_event_count) is not int:
        raise TypeError("confirmation terminal must be a built-in integer or None")
    if type(value.p1_terminal_event_counts) is not tuple or any(
        type(pair) is not tuple or len(pair) != 2 or any(type(item) is not int for item in pair)
        for pair in value.p1_terminal_event_counts
    ):
        raise TypeError("P1 terminal counts must be exact integer-pair tuples")
    l_star, terminals, confirmation, confirmation_terminal, map_id = _expected_branch(value.branch_id)
    if (
        value.profile != _BRANCH_PROFILE
        or value.l_star != l_star
        or value.confirmation_required is not confirmation
        or value.confirmation_terminal_event_count != confirmation_terminal
        or value.p1_terminal_event_counts != terminals
        or value.p1_task_map_id != map_id
    ):
        raise ValueError("horizon branch does not match the frozen one-shot rule")


def _validate_campaign_task_record(value: object) -> None:
    _assert_contract_integrity()
    if type(value) is not _CAMPAIGN_TASK_TYPE:
        raise TypeError("task must be an exact OneCellCampaignTask")
    string_fields = (
        "task_map_id",
        "task_map_sha256",
        "wave",
        "role",
        "horizon_branch_id",
        "threshold_schedule_id",
        "checkpoint_vector_sha256",
        "snapshot_vector_sha256",
    )
    if any(type(getattr(value, field)) is not str for field in string_fields):
        raise TypeError("task text fields must be built-in strings")
    if type(value.included_in_inference) is not bool:
        raise TypeError("included_in_inference must be a built-in Boolean")
    integer_fields = (
        "task_index",
        "width",
        "root_seed",
        "root_offset",
        "terminal_event_count",
    )
    if any(type(getattr(value, field)) is not int for field in integer_fields):
        raise TypeError("task scalar fields must be built-in integers")
    if type(value.boundary_law) is not _BOUNDARY_LAW_TYPE:
        raise TypeError("boundary_law must be an exact OneCellBoundaryLaw")
    if type(value.threshold_schedule) is not tuple or any(type(item) is not int for item in value.threshold_schedule):
        raise TypeError("threshold_schedule must be an exact tuple of built-in integers")
    if type(value.checkpoint_event_counts) is not tuple or any(
        type(item) is not int for item in value.checkpoint_event_counts
    ):
        raise TypeError("checkpoint_event_counts must be an exact integer tuple")
    if type(value.snapshot_checkpoint_indices) is not tuple or any(
        type(item) is not int for item in value.snapshot_checkpoint_indices
    ):
        raise TypeError("snapshot_checkpoint_indices must be an exact integer tuple")
    if type(value.snapshot_event_counts) is not tuple or any(
        type(item) is not int for item in value.snapshot_event_counts
    ):
        raise TypeError("snapshot_event_counts must be an exact integer tuple")
    if value.bootstrap_cohort_id is not None and type(value.bootstrap_cohort_id) is not str:
        raise TypeError("bootstrap_cohort_id must be a built-in string or None")
    if value.bootstrap_population_index is not None and type(value.bootstrap_population_index) is not int:
        raise TypeError("bootstrap_population_index must be a built-in integer or None")
    spec = _map_spec(value.task_map_id)
    expected = _expected_task_row(spec=spec, task_index=value.task_index)
    if (
        _HEX64.fullmatch(value.task_map_sha256) is None
        or value.wave != spec.wave
        or value.role != spec.role
        or value.included_in_inference is not spec.included_in_inference
        or value.horizon_branch_id != spec.horizon_branch_id
        or value.boundary_law.value != expected["boundary_law"]
        or value.width != expected["width"]
        or value.root_seed != expected["root_seed"]
        or value.root_offset != expected["root_offset"]
        or value.threshold_schedule_id != expected["threshold_schedule_id"]
        or value.threshold_schedule != _schedule(value.threshold_schedule_id)
        or value.terminal_event_count != expected["terminal_event_count"]
    ):
        raise ValueError("task fields do not match the frozen task-map row")
    if len(value.checkpoint_event_counts) != 512:
        raise ValueError("checkpoint_event_counts must contain exactly 512 integers")
    if value.snapshot_checkpoint_indices != _SNAPSHOT_INDICES:
        raise ValueError("snapshot_checkpoint_indices do not match the frozen vector")
    if len(value.snapshot_event_counts) != 16:
        raise ValueError("snapshot_event_counts must contain exactly 16 integers")
    expected_checkpoint_hash, expected_snapshot_hash = _vector_hashes(value.terminal_event_count)
    checkpoint_hash = _sha256(
        _canonical_json(
            {
                "event_counts": list(value.checkpoint_event_counts),
                "profile": "tetris-pre-one-cell-checkpoint-vector@1",
            },
            newline=False,
        )
    )
    snapshot_hash = _sha256(
        _canonical_json(
            {
                "checkpoint_indices": list(value.snapshot_checkpoint_indices),
                "event_counts": list(value.snapshot_event_counts),
                "profile": "tetris-pre-one-cell-snapshot-vector@1",
            },
            newline=False,
        )
    )
    if (
        value.checkpoint_vector_sha256 != expected_checkpoint_hash
        or checkpoint_hash != expected_checkpoint_hash
        or value.snapshot_vector_sha256 != expected_snapshot_hash
        or snapshot_hash != expected_snapshot_hash
    ):
        raise ValueError("task checkpoint vectors do not match the frozen Slice 7 authority")
    if spec.bootstrap_cohort_id is None:
        if value.bootstrap_cohort_id is not None or value.bootstrap_population_index is not None:
            raise ValueError("noncohort task must use the exact not-applicable bootstrap representation")
    elif value.bootstrap_cohort_id != spec.bootstrap_cohort_id or value.bootstrap_population_index != value.root_offset:
        raise ValueError("task bootstrap population index does not match its cohort root")


@dataclass(frozen=True, slots=True)
class _CheckpointVector:
    terminal_event_count: int
    checkpoint_event_counts: tuple[int, ...]
    checkpoint_vector_sha256: str
    snapshot_checkpoint_indices: tuple[int, ...]
    snapshot_event_counts: tuple[int, ...]
    snapshot_vector_sha256: str


@dataclass(frozen=True, slots=True)
class _ParsedCampaign:
    bootstrap_matrices: tuple[OneCellBootstrapMatrixIdentity, ...]
    task_maps: tuple[OneCellTaskMapIdentity, ...]
    horizon_branches: tuple[OneCellHorizonBranch, ...]
    checkpoint_vectors: tuple[_CheckpointVector, ...]


def _parsed_campaign_values(value: object) -> tuple[object, ...]:
    """Return a deeply immutable, exact-type-checked cache seal."""

    _assert_contract_integrity()
    if type(value) is not _ParsedCampaign:
        raise AssertionError("cached campaign parse has the wrong runtime type")
    if (
        type(value.bootstrap_matrices) is not tuple
        or len(value.bootstrap_matrices) != len(_CAPTURED_BOOTSTRAP_SPECS)
        or any(type(item) is not _BOOTSTRAP_IDENTITY_TYPE for item in value.bootstrap_matrices)
        or type(value.task_maps) is not tuple
        or len(value.task_maps) != len(_CAPTURED_MAP_SPECS)
        or any(type(item) is not _TASK_MAP_IDENTITY_TYPE for item in value.task_maps)
        or type(value.horizon_branches) is not tuple
        or len(value.horizon_branches) != 4
        or any(type(item) is not _HORIZON_BRANCH_TYPE for item in value.horizon_branches)
        or type(value.checkpoint_vectors) is not tuple
        or len(value.checkpoint_vectors) != len(_CAPTURED_CHECKPOINT_HASHES)
        or any(type(item) is not _CheckpointVector for item in value.checkpoint_vectors)
    ):
        raise AssertionError("cached campaign parse has invalid record structure")
    try:
        for identity in value.bootstrap_matrices:
            _validate_bootstrap_record(identity, _integrity_checked=True)
        for identity in value.task_maps:
            _validate_task_map_identity_record(identity, _integrity_checked=True)
        for branch in value.horizon_branches:
            _validate_branch_record(branch, _integrity_checked=True)
    except (TypeError, ValueError, OneCellCampaignValidationError) as error:
        raise AssertionError("cached campaign parse contains an invalid authority record") from error
    for vector in value.checkpoint_vectors:
        if (
            type(vector.terminal_event_count) is not int
            or type(vector.checkpoint_event_counts) is not tuple
            or any(type(item) is not int for item in vector.checkpoint_event_counts)
            or type(vector.checkpoint_vector_sha256) is not str
            or type(vector.snapshot_checkpoint_indices) is not tuple
            or any(type(item) is not int for item in vector.snapshot_checkpoint_indices)
            or type(vector.snapshot_event_counts) is not tuple
            or any(type(item) is not int for item in vector.snapshot_event_counts)
            or type(vector.snapshot_vector_sha256) is not str
        ):
            raise AssertionError("cached campaign parse contains an invalid checkpoint vector")
    return (
        tuple(
            (
                item.cohort_id,
                item.profile,
                item.member_path,
                item.shape,
                item.seed,
                item.generator,
                item.bit_generator,
                item.numpy_version,
                item.distribution,
                item.dtype,
                item.byte_order,
                item.order,
                item.size_bytes,
                item.sha256,
            )
            for item in value.bootstrap_matrices
        ),
        tuple(
            (
                item.task_map_id,
                item.profile,
                item.member_path,
                item.wave,
                item.role,
                item.horizon_branch_id,
                item.task_count,
                item.size_bytes,
                item.sha256,
            )
            for item in value.task_maps
        ),
        tuple(
            (
                item.branch_id,
                item.profile,
                item.l_star,
                item.confirmation_required,
                item.confirmation_terminal_event_count,
                item.p1_terminal_event_counts,
                item.p1_task_map_id,
            )
            for item in value.horizon_branches
        ),
        tuple(
            (
                item.terminal_event_count,
                item.checkpoint_event_counts,
                item.checkpoint_vector_sha256,
                item.snapshot_checkpoint_indices,
                item.snapshot_event_counts,
                item.snapshot_vector_sha256,
            )
            for item in value.checkpoint_vectors
        ),
    )


def _parse_bootstraps(value: object) -> tuple[OneCellBootstrapMatrixIdentity, ...]:
    records = _require_list(value, label="bootstrap_matrices")
    if len(records) != len(_CAPTURED_BOOTSTRAP_SPECS):
        raise OneCellCampaignValidationError("bootstrap_matrices must contain exactly four records")
    parsed = []
    keys = (
        "bit_generator",
        "byte_order",
        "cohort_id",
        "distribution",
        "dtype",
        "generator",
        "member_path",
        "numpy_version",
        "order",
        "profile",
        "seed",
        "sha256",
        "shape",
        "size_bytes",
    )
    for index, (raw, spec) in enumerate(zip(records, _CAPTURED_BOOTSTRAP_SPECS)):
        record = _require_exact_dict(raw, keys=keys, label=f"bootstrap_matrices[{index}]")
        shape = _require_list(record["shape"], label=f"bootstrap_matrices[{index}].shape")
        if len(shape) != 2:
            raise OneCellCampaignValidationError("bootstrap shape must contain exactly two dimensions")
        try:
            identity = _BOOTSTRAP_IDENTITY_TYPE(
                cohort_id=_require_str(record["cohort_id"], label="bootstrap cohort_id"),
                profile=_require_str(record["profile"], label="bootstrap profile"),
                member_path=_require_member_path(record["member_path"], label="bootstrap member_path"),
                shape=tuple(_require_int(item, label="bootstrap shape entry") for item in shape),
                seed=_require_int(record["seed"], label="bootstrap seed"),
                generator=_require_str(record["generator"], label="bootstrap generator"),
                bit_generator=_require_str(record["bit_generator"], label="bootstrap bit_generator"),
                numpy_version=_require_str(record["numpy_version"], label="bootstrap numpy_version"),
                distribution=_require_str(record["distribution"], label="bootstrap distribution"),
                dtype=_require_str(record["dtype"], label="bootstrap dtype"),
                byte_order=_require_str(record["byte_order"], label="bootstrap byte_order"),
                order=_require_str(record["order"], label="bootstrap order"),
                size_bytes=_require_int(record["size_bytes"], label="bootstrap size_bytes"),
                sha256=_require_sha256(record["sha256"], label="bootstrap sha256"),
            )
        except (TypeError, ValueError) as error:
            raise OneCellCampaignValidationError(f"bootstrap_matrices[{index}] is invalid") from error
        if identity.cohort_id != spec[0]:
            raise OneCellCampaignValidationError("bootstrap matrix order is not the frozen cohort order")
        parsed.append(identity)
    return tuple(parsed)


def _parse_task_map_identities(value: object) -> tuple[OneCellTaskMapIdentity, ...]:
    records = _require_list(value, label="task_maps")
    if len(records) != len(_CAPTURED_MAP_SPECS):
        raise OneCellCampaignValidationError("task_maps must contain exactly nine records")
    keys = (
        "horizon_branch_id",
        "member_path",
        "profile",
        "role",
        "sha256",
        "size_bytes",
        "task_count",
        "task_map_id",
        "wave",
    )
    parsed = []
    for index, (raw, spec) in enumerate(zip(records, _CAPTURED_MAP_SPECS)):
        record = _require_exact_dict(raw, keys=keys, label=f"task_maps[{index}]")
        try:
            identity = _TASK_MAP_IDENTITY_TYPE(
                task_map_id=_require_str(record["task_map_id"], label="task-map ID"),
                profile=_require_str(record["profile"], label="task-map profile"),
                member_path=_require_member_path(record["member_path"], label="task-map member_path"),
                wave=_require_str(record["wave"], label="task-map wave"),
                role=_require_str(record["role"], label="task-map role"),
                horizon_branch_id=_require_str(record["horizon_branch_id"], label="task-map branch"),
                task_count=_require_int(record["task_count"], label="task-map task_count"),
                size_bytes=_require_int(record["size_bytes"], label="task-map size_bytes"),
                sha256=_require_sha256(record["sha256"], label="task-map sha256"),
            )
        except (TypeError, ValueError) as error:
            raise OneCellCampaignValidationError(f"task_maps[{index}] is invalid") from error
        if identity.task_map_id != spec.task_map_id:
            raise OneCellCampaignValidationError("task-map descriptor order is not frozen")
        parsed.append(identity)
    return tuple(parsed)


def _parse_branches(
    value: object,
    *,
    task_maps: tuple[OneCellTaskMapIdentity, ...],
) -> tuple[OneCellHorizonBranch, ...]:
    records = _require_list(value, label="horizon_branches")
    branch_ids = ("p1-no-l-star", "p1-l-star-64", "p1-l-star-256", "p1-l-star-1024")
    if len(records) != len(branch_ids):
        raise OneCellCampaignValidationError("horizon_branches must contain exactly four records")
    keys = (
        "branch_id",
        "confirmation_required",
        "confirmation_terminal_event_count",
        "l_star",
        "p1_task_map_id",
        "p1_terminal_event_counts",
        "profile",
    )
    terminal_keys = ("terminal_event_count", "width")
    map_ids = {record.task_map_id for record in task_maps}
    parsed = []
    for index, (raw, branch_id) in enumerate(zip(records, branch_ids)):
        record = _require_exact_dict(raw, keys=keys, label=f"horizon_branches[{index}]")
        terminals_raw = _require_list(
            record["p1_terminal_event_counts"],
            label=f"horizon_branches[{index}].p1_terminal_event_counts",
        )
        terminals = []
        for terminal_index, raw_terminal in enumerate(terminals_raw):
            terminal_record = _require_exact_dict(
                raw_terminal,
                keys=terminal_keys,
                label=f"horizon_branches[{index}].p1_terminal_event_counts[{terminal_index}]",
            )
            terminals.append(
                (
                    _require_int(terminal_record["width"], label="branch width"),
                    _require_int(terminal_record["terminal_event_count"], label="branch terminal"),
                )
            )
        try:
            branch = _HORIZON_BRANCH_TYPE(
                branch_id=_require_str(record["branch_id"], label="branch_id"),
                profile=_require_str(record["profile"], label="branch profile"),
                l_star=_require_optional_int(record["l_star"], label="branch l_star"),
                confirmation_required=_require_bool(
                    record["confirmation_required"], label="branch confirmation_required"
                ),
                confirmation_terminal_event_count=_require_optional_int(
                    record["confirmation_terminal_event_count"],
                    label="branch confirmation_terminal_event_count",
                ),
                p1_terminal_event_counts=tuple(terminals),
                p1_task_map_id=_require_str(record["p1_task_map_id"], label="branch p1_task_map_id"),
            )
        except (TypeError, ValueError) as error:
            raise OneCellCampaignValidationError(f"horizon_branches[{index}] is invalid") from error
        if branch.branch_id != branch_id or branch.p1_task_map_id not in map_ids:
            raise OneCellCampaignValidationError("branch order or task-map cross-binding is invalid")
        parsed.append(branch)
    return tuple(parsed)


def _parse_vectors(value: object) -> tuple[_CheckpointVector, ...]:
    records = _require_list(value, label="checkpoint_vectors")
    if len(records) != len(_CHECKPOINT_HASHES):
        raise OneCellCampaignValidationError("checkpoint_vectors must contain all 20 declared horizons")
    keys = (
        "checkpoint_event_counts",
        "checkpoint_vector_sha256",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_vector_sha256",
        "terminal_event_count",
    )
    parsed = []
    for index, (raw, expected_hashes) in enumerate(zip(records, _CHECKPOINT_HASHES)):
        record = _require_exact_dict(raw, keys=keys, label=f"checkpoint_vectors[{index}]")
        terminal = _require_int(record["terminal_event_count"], label="vector terminal_event_count")
        checkpoints_raw = _require_list(record["checkpoint_event_counts"], label="checkpoint event counts")
        snapshots_raw = _require_list(record["snapshot_event_counts"], label="snapshot event counts")
        indices_raw = _require_list(record["snapshot_checkpoint_indices"], label="snapshot checkpoint indices")
        checkpoints = tuple(_require_int(item, label="checkpoint event count") for item in checkpoints_raw)
        snapshots = tuple(_require_int(item, label="snapshot event count") for item in snapshots_raw)
        indices = tuple(_require_int(item, label="snapshot checkpoint index") for item in indices_raw)
        checkpoint_hash = _require_sha256(record["checkpoint_vector_sha256"], label="checkpoint vector hash")
        snapshot_hash = _require_sha256(record["snapshot_vector_sha256"], label="snapshot vector hash")
        if (
            terminal != expected_hashes[0]
            or len(checkpoints) != 512
            or len(snapshots) != 16
            or indices != _SNAPSHOT_INDICES
            or checkpoints[0] != 1
            or checkpoints[-1] != terminal
            or any(left >= right for left, right in zip(checkpoints, checkpoints[1:]))
            or snapshots != tuple(checkpoints[item] for item in indices)
        ):
            raise OneCellCampaignValidationError("checkpoint literal vectors have invalid shape or order")
        computed_checkpoint_hash = _sha256(
            _canonical_json(
                {
                    "event_counts": list(checkpoints),
                    "profile": "tetris-pre-one-cell-checkpoint-vector@1",
                },
                newline=False,
            )
        )
        computed_snapshot_hash = _sha256(
            _canonical_json(
                {
                    "checkpoint_indices": list(indices),
                    "event_counts": list(snapshots),
                    "profile": "tetris-pre-one-cell-snapshot-vector@1",
                },
                newline=False,
            )
        )
        if (
            checkpoint_hash != expected_hashes[1]
            or computed_checkpoint_hash != expected_hashes[1]
            or snapshot_hash != expected_hashes[2]
            or computed_snapshot_hash != expected_hashes[2]
        ):
            raise OneCellCampaignValidationError("checkpoint literal vector hash is not the Slice 7 authority")
        parsed.append(
            _CheckpointVector(
                terminal,
                checkpoints,
                checkpoint_hash,
                indices,
                snapshots,
                snapshot_hash,
            )
        )
    return tuple(parsed)


def _validate_task_map_bytes(
    *,
    identity: OneCellTaskMapIdentity,
    member_path: object,
    member_bytes: object,
) -> None:
    if type(member_path) is not str:
        raise TypeError("task-map member path must be a built-in string")
    if type(member_bytes) is not bytes:
        raise TypeError("task-map member bytes must be built-in bytes")
    if member_path != identity.member_path:
        raise OneCellCampaignValidationError("task-map member path does not match its descriptor")
    if not member_bytes or len(member_bytes) > _TASK_MAP_LIMIT:
        raise OneCellCampaignValidationError("task-map member size is outside the parser bound")
    if len(member_bytes) != identity.size_bytes or _sha256(member_bytes) != identity.sha256:
        raise OneCellCampaignValidationError("task-map size or hash does not match its descriptor")
    if not member_bytes.endswith(b"\n") or b"\r" in member_bytes:
        raise OneCellCampaignValidationError("task map must use canonical LF-terminated JSONL")
    lines = member_bytes[:-1].split(b"\n")
    if len(lines) != identity.task_count or any(not line for line in lines):
        raise OneCellCampaignValidationError("task-map row count or blank-line contract failed")
    spec = _map_spec(identity.task_map_id)
    for index, line in enumerate(lines):
        if len(line) + 1 > _TASK_MAP_LINE_LIMIT:
            raise OneCellCampaignValidationError("task-map row exceeds the parser bound")
        row = _decode_canonical_json(
            line + b"\n",
            label=f"{member_path} row {index}",
            size_limit=_TASK_MAP_LINE_LIMIT,
            newline=True,
        )
        expected_row = _expected_task_row(spec=spec, task_index=index)
        if type(row) is not dict or line + b"\n" != _canonical_json(expected_row, newline=True):
            raise OneCellCampaignValidationError(f"{member_path} row {index} is not the frozen task")


def _validate_task_map_members(
    value: object,
) -> tuple[tuple[str, bytes], ...]:
    if type(value) is not tuple:
        raise TypeError("task_map_members must be a built-in tuple")
    if len(value) != len(_CAPTURED_MAP_SPECS):
        raise ValueError("task_map_members must contain exactly nine ordered members")
    validated: list[tuple[str, bytes]] = []
    for index, member in enumerate(value):
        if type(member) is not tuple or len(member) != 2:
            raise TypeError(f"task_map_members[{index}] must be an exact (path, bytes) tuple")
        path, member_bytes = member
        if type(path) is not str:
            raise TypeError(f"task_map_members[{index}] path must be a built-in string")
        if type(member_bytes) is not bytes:
            raise TypeError(f"task_map_members[{index}] payload must be built-in bytes")
        validated.append((path, member_bytes))
    return tuple(validated)


def _require_frozen_json_record(
    value: object,
    *,
    expected: dict[str, object],
    label: str,
) -> None:
    _require_exact_dict(value, keys=tuple(expected), label=label)
    if _canonical_json(value, newline=False) != _canonical_json(expected, newline=False):
        raise OneCellCampaignValidationError(f"{label} does not match the frozen protocol")


def _parse_campaign_uncached(
    configuration_bytes: bytes,
    task_map_members: tuple[tuple[str, bytes], ...],
) -> _ParsedCampaign:
    decoded = _decode_canonical_json(
        configuration_bytes,
        label="configuration_bytes",
        size_limit=_CONFIGURATION_LIMIT,
        newline=True,
    )
    record = _require_exact_dict(
        decoded,
        keys=(
            "bootstrap_matrices",
            "checkpoint_vectors",
            "execution",
            "horizon_branches",
            "model",
            "profile",
            "protocol",
            "task_maps",
        ),
        label="campaign configuration",
    )
    if _require_str(record["profile"], label="campaign profile") != _CAMPAIGN_PROFILE:
        raise OneCellCampaignValidationError("campaign profile is not the Slice 8A profile")
    _require_frozen_json_record(
        record["protocol"],
        expected=_CERTIFIED_PROTOCOL_RECORD(),
        label="protocol",
    )
    _require_frozen_json_record(
        record["model"],
        expected=_CERTIFIED_MODEL_RECORD(),
        label="model",
    )
    _require_frozen_json_record(
        record["execution"],
        expected=_CERTIFIED_EXECUTION_RECORD(),
        label="execution",
    )

    bootstraps = _parse_bootstraps(record["bootstrap_matrices"])
    task_maps = _parse_task_map_identities(record["task_maps"])
    branches = _parse_branches(record["horizon_branches"], task_maps=task_maps)
    vectors = _parse_vectors(record["checkpoint_vectors"])

    if len(task_map_members) != len(task_maps):
        raise OneCellCampaignValidationError("the complete nine-member task-map set is required")
    for index, (identity, member) in enumerate(zip(task_maps, task_map_members)):
        path, member_bytes = member
        if path != _CAPTURED_MAP_SPECS[index].member_path:
            raise OneCellCampaignValidationError("task-map members are not in frozen campaign order")
        _validate_task_map_bytes(
            identity=identity,
            member_path=path,
            member_bytes=member_bytes,
        )

    return _ParsedCampaign(
        bootstrap_matrices=bootstraps,
        task_maps=task_maps,
        horizon_branches=branches,
        checkpoint_vectors=vectors,
    )


def _parsed_campaign(
    *,
    configuration_bytes: object,
    task_map_members: object,
) -> tuple[_ParsedCampaign, tuple[tuple[str, bytes], ...]]:
    if type(configuration_bytes) is not bytes:
        raise TypeError("configuration_bytes must be built-in bytes")
    members = _validate_task_map_members(task_map_members)
    return _CERTIFIED_PARSE_CAMPAIGN(configuration_bytes, members), members


def _validate_campaign_authority_record(value: object) -> None:
    _assert_contract_integrity()
    if type(value) is not _CAMPAIGN_AUTHORITY_TYPE:
        raise TypeError("campaign must be an exact OneCellCampaignAuthority")
    if type(value.configuration_bytes) is not bytes:
        raise TypeError("configuration_bytes must be built-in bytes")
    string_fields = (
        "configuration_sha256",
        "profile",
        "protocol_commit",
        "protocol_path",
        "protocol_blob",
        "protocol_sha256",
    )
    if any(type(getattr(value, field)) is not str for field in string_fields):
        raise TypeError("campaign authority text fields must be built-in strings")
    if type(value.protocol_size_bytes) is not int:
        raise TypeError("protocol_size_bytes must be a built-in integer")
    if type(value.bootstrap_matrices) is not tuple or any(
        type(item) is not _BOOTSTRAP_IDENTITY_TYPE for item in value.bootstrap_matrices
    ):
        raise TypeError("bootstrap_matrices must contain exact bootstrap identity records")
    if type(value.task_maps) is not tuple or any(type(item) is not _TASK_MAP_IDENTITY_TYPE for item in value.task_maps):
        raise TypeError("task_maps must contain exact task-map identity records")
    if type(value.horizon_branches) is not tuple or any(
        type(item) is not _HORIZON_BRANCH_TYPE for item in value.horizon_branches
    ):
        raise TypeError("horizon_branches must contain exact horizon-branch records")
    if type(value.checkpoint_terminals) is not tuple or any(
        type(item) is not int for item in value.checkpoint_terminals
    ):
        raise TypeError("checkpoint_terminals must be an exact integer tuple")
    if type(value.task_map_members) is not tuple:
        raise TypeError("task_map_members must be a built-in tuple")
    for identity in value.bootstrap_matrices:
        _validate_bootstrap_record(identity)
    for identity in value.task_maps:
        _validate_task_map_identity_record(identity)
    for branch in value.horizon_branches:
        _validate_branch_record(branch)
    parsed, members = _parsed_campaign(
        configuration_bytes=value.configuration_bytes,
        task_map_members=value.task_map_members,
    )
    expected_terminals = tuple(vector.terminal_event_count for vector in parsed.checkpoint_vectors)
    if (
        value.configuration_sha256 != _sha256(value.configuration_bytes)
        or value.profile != _CAMPAIGN_PROFILE
        or value.protocol_commit != _ARTICLE_COMMIT
        or value.protocol_path != _PROTOCOL_PATH
        or value.protocol_blob != _PROTOCOL_BLOB
        or value.protocol_sha256 != _PROTOCOL_SHA256
        or value.protocol_size_bytes != _PROTOCOL_SIZE_BYTES
        or value.bootstrap_matrices != parsed.bootstrap_matrices
        or value.task_maps != parsed.task_maps
        or value.horizon_branches != parsed.horizon_branches
        or value.checkpoint_terminals != expected_terminals
        or value.task_map_members != members
    ):
        raise ValueError("campaign authority does not match its exact held bytes")


def _clone_bootstrap_identity(value: OneCellBootstrapMatrixIdentity) -> OneCellBootstrapMatrixIdentity:
    cloned = object.__new__(_BOOTSTRAP_IDENTITY_TYPE)
    for field in (
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
    ):
        object.__setattr__(cloned, field, getattr(value, field))
    return cloned


def _clone_task_map_identity(value: OneCellTaskMapIdentity) -> OneCellTaskMapIdentity:
    cloned = object.__new__(_TASK_MAP_IDENTITY_TYPE)
    for field in (
        "task_map_id",
        "profile",
        "member_path",
        "wave",
        "role",
        "horizon_branch_id",
        "task_count",
        "size_bytes",
        "sha256",
    ):
        object.__setattr__(cloned, field, getattr(value, field))
    return cloned


def _clone_horizon_branch(value: OneCellHorizonBranch) -> OneCellHorizonBranch:
    cloned = object.__new__(_HORIZON_BRANCH_TYPE)
    for field in (
        "branch_id",
        "profile",
        "l_star",
        "confirmation_required",
        "confirmation_terminal_event_count",
        "p1_terminal_event_counts",
        "p1_task_map_id",
    ):
        object.__setattr__(cloned, field, getattr(value, field))
    return cloned


def _clone_checkpoint_vector(value: _CheckpointVector) -> _CheckpointVector:
    cloned = object.__new__(_CheckpointVector)
    for field in (
        "terminal_event_count",
        "checkpoint_event_counts",
        "checkpoint_vector_sha256",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_vector_sha256",
    ):
        object.__setattr__(cloned, field, getattr(value, field))
    return cloned


def _clone_parsed_campaign(value: _ParsedCampaign) -> _ParsedCampaign:
    cloned = object.__new__(_ParsedCampaign)
    object.__setattr__(
        cloned,
        "bootstrap_matrices",
        tuple(_clone_bootstrap_identity(item) for item in value.bootstrap_matrices),
    )
    object.__setattr__(
        cloned,
        "task_maps",
        tuple(_clone_task_map_identity(item) for item in value.task_maps),
    )
    object.__setattr__(
        cloned,
        "horizon_branches",
        tuple(_clone_horizon_branch(item) for item in value.horizon_branches),
    )
    object.__setattr__(
        cloned,
        "checkpoint_vectors",
        tuple(_clone_checkpoint_vector(item) for item in value.checkpoint_vectors),
    )
    return cloned


def _build_campaign_authority(
    *,
    configuration_bytes: bytes,
    members: tuple[tuple[str, bytes], ...],
    parsed: _ParsedCampaign,
) -> OneCellCampaignAuthority:
    return _CAMPAIGN_AUTHORITY_TYPE(
        configuration_bytes=configuration_bytes,
        configuration_sha256=_sha256(configuration_bytes),
        profile=_CAMPAIGN_PROFILE,
        protocol_commit=_ARTICLE_COMMIT,
        protocol_path=_PROTOCOL_PATH,
        protocol_blob=_PROTOCOL_BLOB,
        protocol_sha256=_PROTOCOL_SHA256,
        protocol_size_bytes=_PROTOCOL_SIZE_BYTES,
        bootstrap_matrices=tuple(_clone_bootstrap_identity(item) for item in parsed.bootstrap_matrices),
        task_maps=tuple(_clone_task_map_identity(item) for item in parsed.task_maps),
        horizon_branches=tuple(_clone_horizon_branch(item) for item in parsed.horizon_branches),
        checkpoint_terminals=tuple(vector.terminal_event_count for vector in parsed.checkpoint_vectors),
        task_map_members=members,
    )


def _snapshot_campaign(value: object) -> OneCellCampaignAuthority:
    _assert_contract_integrity()
    if type(value) is not _CAMPAIGN_AUTHORITY_TYPE:
        raise TypeError("campaign must be an exact OneCellCampaignAuthority")
    try:
        _validate_campaign_authority_record(value)
    except AttributeError as error:
        raise TypeError("campaign must be fully initialized") from error
    return value


def _task_map_identity(
    parsed: _ParsedCampaign,
    *,
    task_map_id: str,
) -> OneCellTaskMapIdentity:
    for identity in parsed.task_maps:
        if identity.task_map_id == task_map_id:
            return identity
    raise ValueError("task_map_id is not one of the nine frozen task maps")


def _checkpoint_vector(parsed: _ParsedCampaign, *, terminal: int) -> _CheckpointVector:
    for vector in parsed.checkpoint_vectors:
        if vector.terminal_event_count == terminal:
            return vector
    raise AssertionError("task terminal is missing its certified checkpoint vector")


def _bootstrap_identity(
    parsed: _ParsedCampaign,
    *,
    cohort_id: str,
) -> OneCellBootstrapMatrixIdentity:
    for identity in parsed.bootstrap_matrices:
        if identity.cohort_id == cohort_id:
            return identity
    raise AssertionError("task cohort is missing its bootstrap identity")


def _decode_task(
    *,
    parsed: _ParsedCampaign,
    task_map_id: str,
    task_index: int,
) -> OneCellCampaignTask:
    identity = _task_map_identity(parsed, task_map_id=task_map_id)
    spec = _map_spec(task_map_id)
    row = _expected_task_row(spec=spec, task_index=task_index)
    terminal = int(row["terminal_event_count"])
    vector = _checkpoint_vector(parsed, terminal=terminal)
    boundary_law = _BOUNDARY_LAW_TYPE(str(row["boundary_law"]))
    bootstrap_cohort_id = spec.bootstrap_cohort_id
    return _CAMPAIGN_TASK_TYPE(
        task_map_id=identity.task_map_id,
        task_map_sha256=identity.sha256,
        wave=identity.wave,
        role=identity.role,
        included_in_inference=spec.included_in_inference,
        task_index=task_index,
        horizon_branch_id=identity.horizon_branch_id,
        boundary_law=boundary_law,
        width=int(row["width"]),
        root_seed=int(row["root_seed"]),
        root_offset=int(row["root_offset"]),
        threshold_schedule_id=str(row["threshold_schedule_id"]),
        threshold_schedule=_schedule(str(row["threshold_schedule_id"])),
        terminal_event_count=terminal,
        checkpoint_event_counts=vector.checkpoint_event_counts,
        checkpoint_vector_sha256=vector.checkpoint_vector_sha256,
        snapshot_checkpoint_indices=vector.snapshot_checkpoint_indices,
        snapshot_event_counts=vector.snapshot_event_counts,
        snapshot_vector_sha256=vector.snapshot_vector_sha256,
        bootstrap_cohort_id=bootstrap_cohort_id,
        bootstrap_population_index=None if bootstrap_cohort_id is None else int(row["root_offset"]),
    )


def _load_one_cell_campaign_impl(
    *,
    configuration_bytes: bytes,
    task_map_members: tuple[tuple[str, bytes], ...],
) -> OneCellCampaignAuthority:
    """Validate and preserve one exact canonical campaign and all task maps."""

    _assert_contract_integrity()
    parsed, members = _parsed_campaign(
        configuration_bytes=configuration_bytes,
        task_map_members=task_map_members,
    )
    return _build_campaign_authority(
        configuration_bytes=configuration_bytes,
        members=members,
        parsed=parsed,
    )


def _decode_one_cell_campaign_task_impl(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    task_index: int,
) -> OneCellCampaignTask:
    """Decode one zero-based wave-local index into its exact primitive task."""

    _assert_contract_integrity()
    authority = _snapshot_campaign(campaign)
    if type(task_map_id) is not str:
        raise TypeError("task_map_id must be a built-in string")
    if type(task_index) is not int:
        raise TypeError("task_index must be a built-in integer")
    parsed = _CERTIFIED_PARSE_CAMPAIGN(authority.configuration_bytes, authority.task_map_members)
    return _decode_task(parsed=parsed, task_map_id=task_map_id, task_index=task_index)


def _encode_one_cell_campaign_task_index_impl(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    boundary_law: OneCellBoundaryLaw,
    width: int,
    root_seed: int,
) -> int:
    """Encode exact primitive axes into their zero-based wave-local index."""

    _assert_contract_integrity()
    authority = _snapshot_campaign(campaign)
    if type(task_map_id) is not str:
        raise TypeError("task_map_id must be a built-in string")
    if type(boundary_law) is not _BOUNDARY_LAW_TYPE:
        raise TypeError("boundary_law must be an exact OneCellBoundaryLaw")
    if type(width) is not int:
        raise TypeError("width must be a built-in integer")
    if type(root_seed) is not int:
        raise TypeError("root_seed must be a built-in integer")
    spec = _map_spec(task_map_id)
    try:
        boundary_index = next(index for index, law in enumerate(spec.boundaries) if law is boundary_law)
    except StopIteration as error:
        raise ValueError("boundary_law is not present in the selected task map") from error
    try:
        width_index = spec.widths.index(width)
    except ValueError as error:
        raise ValueError("width is not present in the selected task map") from error
    root_offset = root_seed - spec.root_start
    if not 0 <= root_offset < spec.root_count:
        raise ValueError("root_seed is not present in the selected task map")
    task_index = (boundary_index * len(spec.widths) + width_index) * spec.root_count + root_offset
    parsed = _CERTIFIED_PARSE_CAMPAIGN(authority.configuration_bytes, authority.task_map_members)
    decoded = _decode_task(parsed=parsed, task_map_id=task_map_id, task_index=task_index)
    if decoded.boundary_law is not boundary_law or decoded.width != width or decoded.root_seed != root_seed:
        raise AssertionError("campaign index inversion failed closed")
    return task_index


def _require_external_digest(value: object, *, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    if _HEX64.fullmatch(value) is None:
        raise ValueError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _require_software_commit(value: object) -> str:
    if type(value) is not str:
        raise TypeError("software_commit must be a built-in string")
    if _HEX40.fullmatch(value) is None:
        raise ValueError("software_commit must be 40 lowercase hexadecimal characters")
    return value


def _bootstrap_identity_record(
    *,
    parsed: _ParsedCampaign,
    task: OneCellCampaignTask,
) -> dict[str, object]:
    if task.bootstrap_cohort_id is None:
        return {"applicable": False}
    identity = _bootstrap_identity(parsed, cohort_id=task.bootstrap_cohort_id)
    return {
        "applicable": True,
        "bit_generator": identity.bit_generator,
        "byte_order": identity.byte_order,
        "cohort_id": identity.cohort_id,
        "distribution": identity.distribution,
        "dtype": identity.dtype,
        "generator": identity.generator,
        "member_path": identity.member_path,
        "numpy_version": identity.numpy_version,
        "order": identity.order,
        "population_index": task.bootstrap_population_index,
        "profile": identity.profile,
        "seed": identity.seed,
        "sha256": identity.sha256,
        "shape": list(identity.shape),
        "size_bytes": identity.size_bytes,
    }


def _explain_one_cell_campaign_task_impl(
    *,
    campaign: OneCellCampaignAuthority,
    task_map_id: str,
    task_index: int,
    deployment_lock_sha256: str,
    software_commit: str,
    wheel_sha256: str,
    branch_decision_sha256: str | None = None,
) -> bytes:
    """Return compact canonical scientific-identity bytes for one task."""

    _assert_contract_integrity()
    authority = _snapshot_campaign(campaign)
    if branch_decision_sha256 is not None and type(branch_decision_sha256) is not str:
        raise TypeError("branch_decision_sha256 must be a built-in string or None")
    deployment_digest = _require_external_digest(
        deployment_lock_sha256,
        label="deployment_lock_sha256",
    )
    source_commit = _require_software_commit(software_commit)
    wheel_digest = _require_external_digest(wheel_sha256, label="wheel_sha256")
    task = _decode_one_cell_campaign_task_impl(
        campaign=authority,
        task_map_id=task_map_id,
        task_index=task_index,
    )
    parsed = _CERTIFIED_PARSE_CAMPAIGN(authority.configuration_bytes, authority.task_map_members)
    task_map = _task_map_identity(parsed, task_map_id=task.task_map_id)
    branch_bound = task.task_map_id == "p0-confirmation" or task.task_map_id.startswith("p1-")
    if branch_bound:
        branch_digest = _require_external_digest(
            branch_decision_sha256,
            label="branch_decision_sha256",
        )
        horizon_plan: dict[str, object] = {
            "branch_decision_sha256": branch_digest,
            "kind": "branch-decision",
            "plan_id": task.horizon_branch_id,
        }
    else:
        if branch_decision_sha256 is not None:
            raise ValueError("branch_decision_sha256 is forbidden for a fixed-horizon task map")
        horizon_plan = {
            "kind": "fixed",
            "plan_id": task.horizon_branch_id,
        }

    record: dict[str, object] = {
        "bootstrap": _bootstrap_identity_record(parsed=parsed, task=task),
        "checkpoint_plan": {
            "checkpoint_event_counts": list(task.checkpoint_event_counts),
            "checkpoint_vector_sha256": task.checkpoint_vector_sha256,
            "snapshot_checkpoint_indices": list(task.snapshot_checkpoint_indices),
            "snapshot_event_counts": list(task.snapshot_event_counts),
            "snapshot_vector_sha256": task.snapshot_vector_sha256,
        },
        "configuration_sha256": authority.configuration_sha256,
        "deployment_lock_sha256": deployment_digest,
        "horizon_plan": horizon_plan,
        "protocol": _CERTIFIED_PROTOCOL_RECORD(),
        "software_commit": source_commit,
        "task": {
            "boundary_law": task.boundary_law.value,
            "included_in_inference": task.included_in_inference,
            "role": task.role,
            "root_offset": task.root_offset,
            "root_seed": task.root_seed,
            "task_index": task.task_index,
            "terminal_event_count": task.terminal_event_count,
            "threshold_schedule": list(task.threshold_schedule),
            "threshold_schedule_id": task.threshold_schedule_id,
            "wave": task.wave,
            "width": task.width,
        },
        "task_map": {
            "member_path": task_map.member_path,
            "sha256": task_map.sha256,
            "size_bytes": task_map.size_bytes,
            "task_map_id": task_map.task_map_id,
        },
        "wheel_sha256": wheel_digest,
    }
    record_bytes = _canonical_json(record, newline=False)
    identity_bytes = _canonical_json(
        {
            "profile": _SCIENTIFIC_IDENTITY_PROFILE,
            "record": record,
            "sha256": _sha256(record_bytes),
        },
        newline=False,
    )
    if len(identity_bytes) > _SCIENTIFIC_IDENTITY_LIMIT:
        raise AssertionError("scientific identity exceeds the Slice 7 opaque-byte bound")
    return identity_bytes


def _bind_campaign_api(
    *,
    module_globals: dict[str, object],
    builtin_namespace: dict[str, object],
    integrity_error: type[AssertionError],
    module_bindings: tuple[tuple[str, object], ...],
    codec_lookup: object,
    strict_error_handler: object,
    imported_modules: tuple[tuple[object, ...], ...],
    imported_attributes: tuple[tuple[str, object, str, object], ...],
    class_types: tuple[tuple[str, type[object]], ...],
    public_export_list: list[str],
    public_exports: tuple[str, ...],
    protected_aliases: tuple[tuple[str, object], ...],
    authority_functions: tuple[tuple[str, object], ...],
    integrity_core: object,
    map_specs: tuple[_MapSpec, ...],
    map_spec_type: type[_MapSpec],
    map_spec_task_count: property,
    map_spec_values: tuple[tuple[object, ...], ...],
    bootstrap_specs: tuple[tuple[object, ...], ...],
    schedules: tuple[tuple[str, tuple[int, ...]], ...],
    base_horizons: tuple[tuple[int, int], ...],
    double_horizons: tuple[tuple[int, int], ...],
    historical_horizons: tuple[tuple[int, int], ...],
    checkpoint_hashes: tuple[tuple[int, str, str], ...],
    cache_decorator: object,
    parse_uncached: object,
    parsed_values: object,
    clone_parsed: object,
    validate_members: object,
    sealed_record_type: type[object],
    sealed_record_classes: tuple[type[object], ...],
    function_type: type[object],
    load_impl: object,
    decode_impl: object,
    encode_impl: object,
    explain_impl: object,
) -> tuple[object, object, object, object, object, object]:
    """Bind the guarded parser, record constructor, and public operations."""

    protected_builtin_bindings = tuple(
        (name, value) for name, value in builtin_namespace.items() if not name.startswith("__")
    )
    protected_builtin_names = frozenset(name for name, _value in protected_builtin_bindings)

    def function_state(label: str, function: object) -> tuple[object, ...]:
        keyword_defaults = function.__kwdefaults__
        closure = function.__closure__
        all_defaults = (function.__defaults__ or ()) + (
            () if keyword_defaults is None else tuple(keyword_defaults.values())
        )
        return (
            label,
            function,
            function.__code__,
            function.__defaults__,
            keyword_defaults,
            () if keyword_defaults is None else tuple(keyword_defaults.items()),
            tuple((value, tuple(value.items())) for value in all_defaults if type(value) is dict),
            closure,
        )

    base_function_candidates = tuple(
        (name, value) for name, value in module_bindings if type(value) is function_type
    ) + tuple(
        (label, value) for label, _module, _attribute, value in imported_attributes if type(value) is function_type
    )
    for module_label, _module, _module_type, bindings, _mutable_states in imported_modules:
        base_function_candidates += tuple(
            (f"{module_label}.{name}", value) for name, value in bindings if type(value) is function_type
        )

    class_attributes: tuple[tuple[object, ...], ...]
    base_function_states: tuple[tuple[object, ...], ...]
    runtime_function_states: tuple[tuple[object, ...], ...]
    integrity_guard_code: object

    def integrity_guard() -> None:
        if not module_globals.keys().isdisjoint(protected_builtin_names):
            raise integrity_error("campaign integrity builtins have been shadowed")
        for name, value in protected_builtin_bindings:
            if builtin_namespace.get(name) is not value:
                raise integrity_error(f"campaign integrity builtin {name!r} has been rebound")
        if (
            module_globals.get("_assert_contract_integrity") is not integrity_guard
            or module_globals.get("_CERTIFIED_PARSE_CAMPAIGN") is not certified_parse_campaign
            or module_globals.get("_CAPTURED_PARSE_CAMPAIGN") is not certified_parse_campaign
            or module_globals.get("load_one_cell_campaign") is not load_one_cell_campaign
            or module_globals.get("decode_one_cell_campaign_task") is not decode_one_cell_campaign_task
            or module_globals.get("encode_one_cell_campaign_task_index") is not encode_one_cell_campaign_task_index
            or module_globals.get("explain_one_cell_campaign_task") is not explain_one_cell_campaign_task
        ):
            raise integrity_error("campaign API or its integrity guard has been rebound")
        for state in base_function_states + runtime_function_states:
            (
                label,
                function,
                code,
                defaults,
                keyword_defaults,
                keyword_items,
                mutable_default_states,
                closure,
            ) = state
            if (
                function.__code__ is not code
                or function.__defaults__ is not defaults
                or function.__kwdefaults__ is not keyword_defaults
                or function.__closure__ is not closure
            ):
                raise integrity_error(f"campaign function state {label!r} has been rebound")
            if keyword_defaults is not None:
                if len(keyword_defaults) != len(keyword_items):
                    raise integrity_error(f"campaign function defaults {label!r} have been mutated")
                for name, value in keyword_items:
                    if keyword_defaults.get(name) is not value:
                        raise integrity_error(f"campaign function default {label}.{name} has been mutated")
            for mapping, items in mutable_default_states:
                if len(mapping) != len(items):
                    raise integrity_error(f"campaign mutable default {label!r} has been mutated")
                for name, value in items:
                    if mapping.get(name) is not value:
                        raise integrity_error(f"campaign mutable default {label}.{name} has been mutated")
        integrity_core(
            module_globals=module_globals,
            integrity_error=integrity_error,
            module_bindings=module_bindings,
            codec_lookup=codec_lookup,
            strict_error_handler=strict_error_handler,
            imported_modules=imported_modules,
            imported_attributes=imported_attributes,
            class_attributes=class_attributes,
            public_export_list=public_export_list,
            public_exports=public_exports,
            protected_aliases=protected_aliases,
            authority_functions=authority_functions,
            map_specs=map_specs,
            map_spec_type=map_spec_type,
            map_spec_task_count=map_spec_task_count,
            map_spec_values=map_spec_values,
            bootstrap_specs=bootstrap_specs,
            schedules=schedules,
            base_horizons=base_horizons,
            double_horizons=double_horizons,
            historical_horizons=historical_horizons,
            checkpoint_hashes=checkpoint_hashes,
        )

    def enter_integrity_guard() -> None:
        if integrity_guard.__code__ is not integrity_guard_code:
            raise integrity_error("campaign integrity guard code has been mutated")
        integrity_guard()

    def sealed_record_new(class_type: type[object], *_args: object, **_kwargs: object) -> object:
        enter_integrity_guard()
        return object.__new__(class_type)

    sealed_record_type.__new__ = sealed_record_new
    for record_class in sealed_record_classes:
        type.__setattr__(record_class, "_runtime_sealed", True)
    expanded_class_types: list[tuple[str, type[object]]] = []
    for label, class_type in class_types:
        for owner in class_type.__mro__ + type(class_type).__mro__:
            if not any(existing is owner for _existing_label, existing in expanded_class_types):
                expanded_class_types.append((f"{label}:{owner.__name__}", owner))

    def mutable_class_states(class_type: type[object]) -> tuple[tuple[object, ...], ...]:
        states: list[tuple[object, ...]] = []
        for name, value in class_type.__dict__.items():
            if name == "__dataclass_params__":
                slots = type(value).__slots__
                if type(slots) is str:
                    slots = (slots,)
                states.append(
                    (
                        "slots",
                        name,
                        value,
                        tuple((slot, getattr(value, slot)) for slot in slots),
                    )
                )
            if type(value) is dict:
                states.append(("dict", name, value, tuple(value.items())))
                if name == "__dataclass_fields__":
                    for field_name, field in value.items():
                        slots = type(field).__slots__
                        if type(slots) is str:
                            slots = (slots,)
                        states.append(
                            (
                                "slots",
                                f"{name}.{field_name}",
                                field,
                                tuple((slot, getattr(field, slot)) for slot in slots),
                            )
                        )
            elif type(value) is list:
                states.append(("list", name, value, tuple(value)))
        return tuple(states)

    class_attributes = tuple(
        (
            label,
            class_type,
            tuple(class_type.__dict__.items()),
            class_type.__bases__,
            class_type.__mro__,
            type(class_type),
            mutable_class_states(class_type),
        )
        for label, class_type in expanded_class_types
    )
    for (
        class_label,
        _class_type,
        attributes,
        _bases,
        _mro,
        _metaclass,
        _mutable_states,
    ) in class_attributes:
        base_function_candidates += tuple(
            (f"{class_label}.{name}", value) for name, value in attributes if type(value) is function_type
        )
        for name, value in attributes:
            base_function_candidates += tuple(
                (f"{class_label}.{name}.{accessor_name}", accessor)
                for accessor_name, accessor in (
                    ("fget", getattr(value, "fget", None)),
                    ("fset", getattr(value, "fset", None)),
                    ("fdel", getattr(value, "fdel", None)),
                    ("__func__", getattr(value, "__func__", None)),
                )
                if type(accessor) is function_type
            )
    base_function_states = tuple(function_state(label, function) for label, function in base_function_candidates)

    @cache_decorator(maxsize=4)
    def cached_parse_campaign(
        configuration_bytes: bytes,
        task_map_members: tuple[tuple[str, bytes], ...],
    ) -> tuple[_ParsedCampaign, tuple[object, ...]]:
        parsed = parse_uncached(configuration_bytes, task_map_members)
        return parsed, parsed_values(parsed)

    def certified_parse_campaign(
        configuration_bytes: bytes,
        task_map_members: tuple[tuple[str, bytes], ...],
    ) -> _ParsedCampaign:
        enter_integrity_guard()
        if type(configuration_bytes) is not bytes:
            raise TypeError("configuration_bytes must be built-in bytes")
        members = validate_members(task_map_members)
        parsed, expected_values = cached_parse_campaign(configuration_bytes, members)
        if parsed_values(parsed) != expected_values:
            raise integrity_error("cached campaign parse has been mutated")
        return clone_parsed(parsed)

    def load_one_cell_campaign(
        *,
        configuration_bytes: bytes,
        task_map_members: tuple[tuple[str, bytes], ...],
    ) -> OneCellCampaignAuthority:
        """Validate and preserve one exact canonical campaign and all task maps."""

        enter_integrity_guard()
        return load_impl(
            configuration_bytes=configuration_bytes,
            task_map_members=task_map_members,
        )

    def decode_one_cell_campaign_task(
        *,
        campaign: OneCellCampaignAuthority,
        task_map_id: str,
        task_index: int,
    ) -> OneCellCampaignTask:
        """Decode one zero-based wave-local index into its exact primitive task."""

        enter_integrity_guard()
        return decode_impl(
            campaign=campaign,
            task_map_id=task_map_id,
            task_index=task_index,
        )

    def encode_one_cell_campaign_task_index(
        *,
        campaign: OneCellCampaignAuthority,
        task_map_id: str,
        boundary_law: OneCellBoundaryLaw,
        width: int,
        root_seed: int,
    ) -> int:
        """Encode exact primitive axes into their zero-based wave-local index."""

        enter_integrity_guard()
        return encode_impl(
            campaign=campaign,
            task_map_id=task_map_id,
            boundary_law=boundary_law,
            width=width,
            root_seed=root_seed,
        )

    def explain_one_cell_campaign_task(
        *,
        campaign: OneCellCampaignAuthority,
        task_map_id: str,
        task_index: int,
        deployment_lock_sha256: str,
        software_commit: str,
        wheel_sha256: str,
        branch_decision_sha256: str | None = None,
    ) -> bytes:
        """Return compact canonical scientific-identity bytes for one task."""

        enter_integrity_guard()
        return explain_impl(
            campaign=campaign,
            task_map_id=task_map_id,
            task_index=task_index,
            deployment_lock_sha256=deployment_lock_sha256,
            software_commit=software_commit,
            wheel_sha256=wheel_sha256,
            branch_decision_sha256=branch_decision_sha256,
        )

    runtime_function_candidates = (
        ("integrity_guard", integrity_guard),
        ("enter_integrity_guard", enter_integrity_guard),
        ("sealed_record_new", sealed_record_new),
        ("cached_parse_campaign", cached_parse_campaign.__wrapped__),
        ("certified_parse_campaign", certified_parse_campaign),
        ("load_one_cell_campaign", load_one_cell_campaign),
        ("decode_one_cell_campaign_task", decode_one_cell_campaign_task),
        ("encode_one_cell_campaign_task_index", encode_one_cell_campaign_task_index),
        ("explain_one_cell_campaign_task", explain_one_cell_campaign_task),
    )
    runtime_function_states = tuple(function_state(label, function) for label, function in runtime_function_candidates)
    integrity_guard_code = integrity_guard.__code__

    return (
        integrity_guard,
        certified_parse_campaign,
        load_one_cell_campaign,
        decode_one_cell_campaign_task,
        encode_one_cell_campaign_task_index,
        explain_one_cell_campaign_task,
    )


_CAPTURED_PROTECTED_ALIASES = (
    ("OneCellCampaignValidationError", OneCellCampaignValidationError),
    ("_VALIDATION_ERROR_TYPE", _VALIDATION_ERROR_TYPE),
    ("OneCellBootstrapMatrixIdentity", OneCellBootstrapMatrixIdentity),
    ("_BOOTSTRAP_IDENTITY_TYPE", _BOOTSTRAP_IDENTITY_TYPE),
    ("OneCellTaskMapIdentity", OneCellTaskMapIdentity),
    ("_TASK_MAP_IDENTITY_TYPE", _TASK_MAP_IDENTITY_TYPE),
    ("OneCellHorizonBranch", OneCellHorizonBranch),
    ("_HORIZON_BRANCH_TYPE", _HORIZON_BRANCH_TYPE),
    ("OneCellCampaignAuthority", OneCellCampaignAuthority),
    ("_CAMPAIGN_AUTHORITY_TYPE", _CAMPAIGN_AUTHORITY_TYPE),
    ("OneCellCampaignTask", OneCellCampaignTask),
    ("_CAMPAIGN_TASK_TYPE", _CAMPAIGN_TASK_TYPE),
    ("OneCellBoundaryLaw", OneCellBoundaryLaw),
    ("_BOUNDARY_LAW_TYPE", _BOUNDARY_LAW_TYPE),
    ("_CERTIFIED_PROTOCOL_RECORD", _CERTIFIED_PROTOCOL_RECORD),
    ("_CAPTURED_PROTOCOL_RECORD", _CAPTURED_PROTOCOL_RECORD),
    ("_CERTIFIED_MODEL_RECORD", _CERTIFIED_MODEL_RECORD),
    ("_CAPTURED_MODEL_RECORD", _CAPTURED_MODEL_RECORD),
    ("_CERTIFIED_EXECUTION_RECORD", _CERTIFIED_EXECUTION_RECORD),
    ("_CAPTURED_EXECUTION_RECORD", _CAPTURED_EXECUTION_RECORD),
)


_CAPTURED_AUTHORITY_FUNCTIONS = (
    ("_assert_contract_integrity_core", _assert_contract_integrity_core),
    ("_bind_campaign_api", _bind_campaign_api),
    ("_sha256", _sha256),
    ("_canonical_json", _canonical_json),
    ("_parse_int", _parse_int),
    ("_reject_float", _reject_float),
    ("_reject_constant", _reject_constant),
    ("_unique_object", _unique_object),
    ("_check_json_shape", _check_json_shape),
    ("_decode_canonical_json", _decode_canonical_json),
    ("_require_exact_dict", _require_exact_dict),
    ("_require_list", _require_list),
    ("_require_str", _require_str),
    ("_require_int", _require_int),
    ("_require_bool", _require_bool),
    ("_require_optional_int", _require_optional_int),
    ("_require_sha256", _require_sha256),
    ("_require_member_path", _require_member_path),
    ("_expected_protocol_record", _expected_protocol_record),
    ("_expected_model_record", _expected_model_record),
    ("_expected_inventories", _expected_inventories),
    ("_expected_execution_record", _expected_execution_record),
    ("_map_spec", _map_spec),
    ("_schedule", _schedule),
    ("_terminal_for", _terminal_for),
    ("_schedule_id_for", _schedule_id_for),
    ("_expected_task_row", _expected_task_row),
    ("_vector_hashes", _vector_hashes),
    ("_bootstrap_spec", _bootstrap_spec),
    ("_validate_bootstrap_record", _validate_bootstrap_record),
    ("_validate_task_map_identity_record", _validate_task_map_identity_record),
    ("_expected_branch", _expected_branch),
    ("_validate_branch_record", _validate_branch_record),
    ("_validate_campaign_task_record", _validate_campaign_task_record),
    ("_parse_bootstraps", _parse_bootstraps),
    ("_parse_task_map_identities", _parse_task_map_identities),
    ("_parse_branches", _parse_branches),
    ("_parse_vectors", _parse_vectors),
    ("_validate_task_map_bytes", _validate_task_map_bytes),
    ("_validate_task_map_members", _validate_task_map_members),
    ("_require_frozen_json_record", _require_frozen_json_record),
    ("_parsed_campaign_values", _parsed_campaign_values),
    ("_parse_campaign_uncached", _parse_campaign_uncached),
    ("_parsed_campaign", _parsed_campaign),
    ("_validate_campaign_authority_record", _validate_campaign_authority_record),
    ("_clone_bootstrap_identity", _clone_bootstrap_identity),
    ("_clone_task_map_identity", _clone_task_map_identity),
    ("_clone_horizon_branch", _clone_horizon_branch),
    ("_clone_checkpoint_vector", _clone_checkpoint_vector),
    ("_clone_parsed_campaign", _clone_parsed_campaign),
    ("_build_campaign_authority", _build_campaign_authority),
    ("_snapshot_campaign", _snapshot_campaign),
    ("_task_map_identity", _task_map_identity),
    ("_checkpoint_vector", _checkpoint_vector),
    ("_bootstrap_identity", _bootstrap_identity),
    ("_decode_task", _decode_task),
    ("_load_one_cell_campaign_impl", _load_one_cell_campaign_impl),
    ("_decode_one_cell_campaign_task_impl", _decode_one_cell_campaign_task_impl),
    ("_encode_one_cell_campaign_task_index_impl", _encode_one_cell_campaign_task_index_impl),
    ("_require_external_digest", _require_external_digest),
    ("_require_software_commit", _require_software_commit),
    ("_bootstrap_identity_record", _bootstrap_identity_record),
    ("_explain_one_cell_campaign_task_impl", _explain_one_cell_campaign_task_impl),
)

_CAPTURED_PUBLIC_EXPORT_LIST = __all__
_CAPTURED_PUBLIC_EXPORTS = tuple(__all__)
_CAPTURED_IMPORTED_MODULES = tuple(
    (
        label,
        module,
        type(module),
        tuple(module.__dict__.items()),
        tuple(
            ("dict", name, value, tuple(value.items()))
            for name, value in module.__dict__.items()
            if not name.startswith("__") and "cache" not in name.lower() and type(value) is dict
        )
        + tuple(
            ("list", name, value, tuple(value))
            for name, value in module.__dict__.items()
            if not name.startswith("__") and "cache" not in name.lower() and type(value) is list
        ),
    )
    for label, module in (
        ("codecs", codecs),
        ("enum", enum),
        ("hashlib", hashlib),
        ("json", json),
        ("json.decoder", json.decoder),
        ("json.encoder", json.encoder),
        ("json.scanner", json.scanner),
        ("re", re),
    )
)
_CAPTURED_IMPORTED_ATTRIBUTES = (
    ("codecs.lookup_error", codecs, "lookup_error", codecs.lookup_error),
    ("hashlib.sha256", hashlib, "sha256", hashlib.sha256),
    ("json.dumps", json, "dumps", json.dumps),
    ("json.loads", json, "loads", json.loads),
    ("json.JSONDecodeError", json, "JSONDecodeError", json.JSONDecodeError),
    ("json.JSONDecoder", json, "JSONDecoder", json.JSONDecoder),
    ("json.JSONEncoder", json, "JSONEncoder", json.JSONEncoder),
    ("re.fullmatch", re, "fullmatch", re.fullmatch),
)
_CAPTURED_CLASS_TYPES = (
    (
        "dataclasses.Field",
        type(next(iter(OneCellCampaignAuthority.__dataclass_fields__.values()))),
    ),
    ("dataclasses._DataclassParams", type(OneCellCampaignAuthority.__dataclass_params__)),
    ("OneCellCampaignValidationError", OneCellCampaignValidationError),
    ("OneCellBootstrapMatrixIdentity", OneCellBootstrapMatrixIdentity),
    ("OneCellTaskMapIdentity", OneCellTaskMapIdentity),
    ("OneCellHorizonBranch", OneCellHorizonBranch),
    ("OneCellCampaignAuthority", OneCellCampaignAuthority),
    ("OneCellCampaignTask", OneCellCampaignTask),
    ("OneCellBoundaryLaw", OneCellBoundaryLaw),
    ("json.JSONDecodeError", json.JSONDecodeError),
    ("json.JSONDecoder", json.JSONDecoder),
    ("json.JSONEncoder", json.JSONEncoder),
    ("_SealedRecordMeta", _SealedRecordMeta),
    ("_SealedRecord", _SealedRecord),
    ("_MapSpec", _MapSpec),
    ("_CheckpointVector", _CheckpointVector),
    ("_ParsedCampaign", _ParsedCampaign),
)
_CAPTURED_MODULE_BINDINGS = tuple(
    (name, value)
    for name, value in globals().items()
    if not name.startswith("__") and name != "_CAPTURED_MODULE_BINDINGS"
)

(
    _assert_contract_integrity,
    _CERTIFIED_PARSE_CAMPAIGN,
    load_one_cell_campaign,
    decode_one_cell_campaign_task,
    encode_one_cell_campaign_task_index,
    explain_one_cell_campaign_task,
) = _bind_campaign_api(
    module_globals=globals(),
    builtin_namespace=_bind_campaign_api.__builtins__,
    integrity_error=AssertionError,
    module_bindings=_CAPTURED_MODULE_BINDINGS,
    codec_lookup=codecs.lookup_error,
    strict_error_handler=_CAPTURED_STRICT_ERROR_HANDLER,
    imported_modules=_CAPTURED_IMPORTED_MODULES,
    imported_attributes=_CAPTURED_IMPORTED_ATTRIBUTES,
    class_types=_CAPTURED_CLASS_TYPES,
    public_export_list=_CAPTURED_PUBLIC_EXPORT_LIST,
    public_exports=_CAPTURED_PUBLIC_EXPORTS,
    protected_aliases=_CAPTURED_PROTECTED_ALIASES,
    authority_functions=_CAPTURED_AUTHORITY_FUNCTIONS,
    integrity_core=_assert_contract_integrity_core,
    map_specs=_CAPTURED_MAP_SPECS,
    map_spec_type=_CAPTURED_MAP_SPEC_TYPE,
    map_spec_task_count=_CAPTURED_MAP_SPEC_TASK_COUNT,
    map_spec_values=_CAPTURED_MAP_SPEC_VALUES,
    bootstrap_specs=_CAPTURED_BOOTSTRAP_SPECS,
    schedules=_CAPTURED_SCHEDULES,
    base_horizons=_CAPTURED_BASE_HORIZONS,
    double_horizons=_CAPTURED_DOUBLE_HORIZONS,
    historical_horizons=_CAPTURED_HISTORICAL_HORIZONS,
    checkpoint_hashes=_CAPTURED_CHECKPOINT_HASHES,
    cache_decorator=lru_cache,
    parse_uncached=_parse_campaign_uncached,
    parsed_values=_parsed_campaign_values,
    clone_parsed=_clone_parsed_campaign,
    validate_members=_validate_task_map_members,
    sealed_record_type=_SealedRecord,
    sealed_record_classes=(
        _SealedRecord,
        OneCellBootstrapMatrixIdentity,
        OneCellTaskMapIdentity,
        OneCellHorizonBranch,
        OneCellCampaignAuthority,
        OneCellCampaignTask,
    ),
    function_type=type(_assert_contract_integrity_core),
    load_impl=_load_one_cell_campaign_impl,
    decode_impl=_decode_one_cell_campaign_task_impl,
    encode_impl=_encode_one_cell_campaign_task_index_impl,
    explain_impl=_explain_one_cell_campaign_task_impl,
)
_CAPTURED_PARSE_CAMPAIGN = _CERTIFIED_PARSE_CAMPAIGN
