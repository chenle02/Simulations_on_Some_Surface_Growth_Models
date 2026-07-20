"""Bounded, explicit-only S2 reference trajectories and checkpoint bytes.

This module is the slow correctness oracle for the ratified tetromino event
semantics.  It deliberately exposes no CLI, filesystem writer, scheduler,
legacy adapter, or production execution route.  Checkpoints are immutable
canonical byte values; callers decide whether and where to persist them.
"""

from __future__ import annotations

import hashlib
import json
import math
from contextvars import ContextVar
from dataclasses import dataclass, fields

from ..models import GEOMETRY_BY_ID, ContactKind
from .accumulation import ReferenceEventAccumulator, accumulate_event, start_event_accumulator
from .binding import ReferenceEventPlacement, place_selected_event
from .event import ConditionalWeightedLaw, TetrominoEventLaw, TetrominoEventSelection, select_event
from .reference import ContactFaceKind, place_one
from .selection import (
    DeclaredStreamSet,
    ExactWeightedLaw,
    UniformIntegerLaw,
    select_uniform,
    select_weighted,
)
from .state import SparseAggregate

__all__ = [
    "ReferenceCheckpointSchedule",
    "ReferenceTrajectoryConfig",
    "ReferenceCheckpoint",
    "ReferenceTrajectory",
    "build_reference_checkpoint_schedule",
    "canonical_json_bytes",
    "start_reference_trajectory",
    "advance_reference_trajectory",
    "reconstruct_reference_checkpoint",
    "reconstruct_reference_checkpoints",
]

_U64_MAX = (1 << 64) - 1
_U128_MAX = (1 << 128) - 1
_RNG_ALGORITHM = "semantic-philox4x64-10-v1"
_CONFIG_PROFILE = "tetris-ballistic/reference-trajectory-config@1"
_CHECKPOINT_PROFILE = "tetris-ballistic/reference-checkpoint@1"
_MANIFEST_PROFILE = "tetris-ballistic/reference-trajectory-manifest@1"
_SCHEDULE_PROFILE = "tetris-ballistic/reference-checkpoint-vector@1"
_CERTIFIED_START_ACCUMULATOR = start_event_accumulator
_CERTIFIED_ACCUMULATE_EVENT = accumulate_event
_CERTIFIED_SELECT_WEIGHTED = select_weighted
_CERTIFIED_SELECT_UNIFORM = select_uniform
_CERTIFIED_PLACE_ONE = place_one
_CERTIFIED_STREAMS = DeclaredStreamSet(("family", "orientation", "launch", "contact"))
_INTERNAL_TRAJECTORY_CONSTRUCTION = ContextVar("internal_reference_trajectory_construction", default=False)


def _require_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _require_uint(value: object, *, maximum: int, label: str) -> int:
    result = _require_int(value, label=label)
    if not 0 <= result <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return result


def _require_text(value: object, *, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be a built-in string")
    if not value:
        raise ValueError(f"{label} must be nonempty")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError(f"{label} must be valid UTF-8") from error
    return value


def _require_sha256(value: object, *, label: str) -> str:
    text = _require_text(value, label=label)
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return text


def _require_commit(value: object) -> str:
    text = _require_text(value, label="software_commit")
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError("software_commit must be a full lowercase Git object ID")
    return text


def _validate_json_tree(value: object, *, label: str = "value") -> None:
    if type(value) in (str, int):
        return
    if type(value) is bool or type(value) is float:
        raise TypeError(f"{label} must not contain booleans or floats")
    if type(value) is list:
        for index, item in enumerate(value):
            _validate_json_tree(item, label=f"{label}[{index}]")
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"{label} keys must be built-in strings")
            _validate_json_tree(item, label=f"{label}.{key}")
        return
    raise TypeError(f"{label} contains a non-canonical JSON type")


def canonical_json_bytes(value: object) -> bytes:
    """Return the ratified UTF-8/sorted/compact/exact-integer JSON profile."""

    _validate_json_tree(value)
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _rounded_root_power(*, base: int, exponent: int) -> int:
    """Exact PRE round-half-up(base**(exponent/383))."""

    scaled = (1 << 383) * pow(base, exponent)
    hint = max(1, min(base, int(math.exp(math.log(base) * exponent / 383.0) + 0.5)))

    def too_high(candidate: int) -> bool:
        return scaled < pow(2 * candidate - 1, 383)

    def too_low(candidate: int) -> bool:
        return scaled >= pow(2 * candidate + 1, 383)

    if not too_high(hint) and not too_low(hint):
        return hint
    if too_high(hint):
        high = hint
        step = 1
        low = max(0, high - step)
        while low > 0 and too_high(low):
            high = low
            step *= 2
            low = max(0, high - step)
    else:
        low = hint
        step = 1
        high = min(base, low + step)
        while high < base and too_low(high):
            low = high
            step *= 2
            high = min(base, low + step)
    while low <= high:
        candidate = (low + high) // 2
        if too_high(candidate):
            high = candidate - 1
        elif too_low(candidate):
            low = candidate + 1
        else:
            return candidate
    raise AssertionError("exact checkpoint rounding candidate was not found")


def _schedule_values(terminal: int) -> tuple[tuple[int, ...], str]:
    midpoint = (terminal + 1) // 2
    early_terminal = midpoint - 1
    early = [1]
    for index in range(1, 384):
        rounded = _rounded_root_power(base=early_terminal, exponent=index)
        early.append(min(early_terminal - (383 - index), max(early[-1] + 1, rounded)))
    late = tuple(midpoint + index * (terminal - midpoint) // 127 for index in range(128))
    event_ordinals = tuple(early) + late
    digest = _sha256(canonical_json_bytes({"event_ordinals": list(event_ordinals), "profile": _SCHEDULE_PROFILE}))
    return event_ordinals, digest


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceCheckpointSchedule:
    terminal_event_count: int
    event_ordinals: tuple[int, ...]
    vector_sha256: str

    def __post_init__(self) -> None:
        terminal = _require_uint(self.terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
        if terminal < 769:
            raise ValueError("terminal_event_count must be at least 769 for 512 strictly increasing checkpoints")
        if type(self.event_ordinals) is not tuple or any(type(value) is not int for value in self.event_ordinals):
            raise TypeError("event_ordinals must be a built-in tuple of built-in integers")
        digest = _require_sha256(self.vector_sha256, label="vector_sha256")
        if (self.event_ordinals, digest) != _schedule_values(terminal):
            raise ValueError("schedule fields do not match the frozen 512-checkpoint construction")


def build_reference_checkpoint_schedule(*, terminal_event_count: int) -> ReferenceCheckpointSchedule:
    terminal = _require_uint(terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
    if terminal < 769:
        raise ValueError("terminal_event_count must be at least 769 for 512 strictly increasing checkpoints")
    event_ordinals, digest = _schedule_values(terminal)
    return ReferenceCheckpointSchedule(
        terminal_event_count=terminal,
        event_ordinals=event_ordinals,
        vector_sha256=digest,
    )


def _law_record(law: TetrominoEventLaw) -> dict[str, object]:
    return {
        "contact": {"counts": list(law.contact_law.counts), "outcome_ids": list(law.contact_law.outcome_ids)},
        "family": {"counts": list(law.family_law.counts), "outcome_ids": list(law.family_law.outcome_ids)},
        "launch_upper_bound": law.launch_law.upper_bound,
        "orientations": [
            {
                "branch_id": branch_id,
                "counts": list(branch_law.counts),
                "outcome_ids": list(branch_law.outcome_ids),
            }
            for branch_id, branch_law in zip(law.orientation_laws.branch_ids, law.orientation_laws.branch_laws)
        ],
    }


def _law_from_record(value: object) -> TetrominoEventLaw:
    record = _dict(value, label="law")
    _expect_keys(record, ("contact", "family", "launch_upper_bound", "orientations"), label="law")
    family = _dict(record.get("family"), label="law.family")
    contact = _dict(record.get("contact"), label="law.contact")
    _expect_keys(family, ("counts", "outcome_ids"), label="law.family")
    _expect_keys(contact, ("counts", "outcome_ids"), label="law.contact")
    orientations = _list(record.get("orientations"), label="law.orientations")
    branch_ids: list[str] = []
    branch_laws: list[ExactWeightedLaw] = []
    for index, item in enumerate(orientations):
        branch = _dict(item, label=f"law.orientations[{index}]")
        _expect_keys(
            branch,
            ("branch_id", "counts", "outcome_ids"),
            label=f"law.orientations[{index}]",
        )
        branch_ids.append(_require_text(branch.get("branch_id"), label="orientation branch ID"))
        branch_laws.append(
            ExactWeightedLaw(
                tuple(_text_list(branch.get("outcome_ids"), label="orientation outcome IDs")),
                tuple(_int_list(branch.get("counts"), label="orientation counts")),
            )
        )
    return TetrominoEventLaw(
        family_law=ExactWeightedLaw(
            tuple(_text_list(family.get("outcome_ids"), label="family outcome IDs")),
            tuple(_int_list(family.get("counts"), label="family counts")),
        ),
        orientation_laws=ConditionalWeightedLaw(tuple(branch_ids), tuple(branch_laws)),
        launch_law=UniformIntegerLaw(_require_int(record.get("launch_upper_bound"), label="launch upper bound")),
        contact_law=ExactWeightedLaw(
            tuple(_text_list(contact.get("outcome_ids"), label="contact outcome IDs")),
            tuple(_int_list(contact.get("counts"), label="contact counts")),
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceTrajectoryConfig:
    model_law_id: str
    plan_id: str
    software_commit: str
    root_seed: int
    coupling_group_id: str
    law: TetrominoEventLaw
    width: int
    terminal_event_count: int
    checkpoint_schedule: ReferenceCheckpointSchedule
    rng_algorithm: str = _RNG_ALGORITHM

    def __post_init__(self) -> None:
        model_law_id = _require_text(self.model_law_id, label="model_law_id")
        plan_id = _require_text(self.plan_id, label="plan_id")
        software_commit = _require_commit(self.software_commit)
        root_seed = _require_uint(self.root_seed, maximum=_U128_MAX, label="root_seed")
        group = _require_text(self.coupling_group_id, label="coupling_group_id")
        if type(self.law) is not TetrominoEventLaw:
            raise TypeError("law must be a TetrominoEventLaw")
        law = _law_from_record(_law_record(self.law))
        width = _require_int(self.width, label="width")
        if width < 3:
            raise ValueError("width must be at least 3")
        terminal = _require_uint(self.terminal_event_count, maximum=_U64_MAX, label="terminal_event_count")
        if terminal >= 1 << 64 or width * terminal >= 1 << 64 or width * terminal * terminal >= 1 << 128:
            raise ValueError("trajectory bounds L*N and L*N^2 exceed their frozen unsigned domains")
        if law.launch_law.upper_bound != width:
            raise ValueError("law launch upper bound must equal width")
        if type(self.checkpoint_schedule) is not ReferenceCheckpointSchedule:
            raise TypeError("checkpoint_schedule must be a ReferenceCheckpointSchedule")
        schedule = ReferenceCheckpointSchedule(
            terminal_event_count=self.checkpoint_schedule.terminal_event_count,
            event_ordinals=self.checkpoint_schedule.event_ordinals,
            vector_sha256=self.checkpoint_schedule.vector_sha256,
        )
        if terminal != schedule.terminal_event_count:
            raise ValueError("terminal_event_count must equal the checkpoint schedule horizon")
        if self.rng_algorithm != _RNG_ALGORITHM:
            raise ValueError(f"rng_algorithm must be {_RNG_ALGORITHM!r}")
        object.__setattr__(self, "model_law_id", model_law_id)
        object.__setattr__(self, "plan_id", plan_id)
        object.__setattr__(self, "software_commit", software_commit)
        object.__setattr__(self, "root_seed", root_seed)
        object.__setattr__(self, "coupling_group_id", group)
        object.__setattr__(self, "law", law)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "terminal_event_count", terminal)
        object.__setattr__(self, "checkpoint_schedule", schedule)
        object.__setattr__(self, "rng_algorithm", _RNG_ALGORITHM)


def _config_record(config: ReferenceTrajectoryConfig) -> dict[str, object]:
    return {
        "checkpoint_event_ordinals": list(config.checkpoint_schedule.event_ordinals),
        "checkpoint_vector_sha256": config.checkpoint_schedule.vector_sha256,
        "coupling_group_id": config.coupling_group_id,
        "law": _law_record(config.law),
        "model_law_id": config.model_law_id,
        "plan_id": config.plan_id,
        "profile": _CONFIG_PROFILE,
        "rng_algorithm": config.rng_algorithm,
        "root_seed": config.root_seed,
        "software_commit": config.software_commit,
        "terminal_event_count": config.terminal_event_count,
        "width": config.width,
    }


def _config_bytes(config: ReferenceTrajectoryConfig) -> bytes:
    return canonical_json_bytes(_config_record(config))


def _payload_claims_config_and_ordinal(
    *, payload: bytes, config: ReferenceTrajectoryConfig, event_ordinal: int
) -> bool:
    """Cheaply bind an inventory member before the full terminal replay.

    The exact canonical writer form is checked at reconstruction/terminal
    closure.  This prefilter prevents mixed-task inventories without parsing
    every growing checkpoint during each bounded prefix advance.
    """

    configuration = _config_bytes(config)[:-1]
    configuration_digest = _sha256(configuration + b"\n").encode("ascii")
    identity = b'"configuration":' + configuration + b',"configuration_sha256":"' + configuration_digest + b'"'
    ordinal = f',"next_event_ordinal":{event_ordinal},"profile":"{_CHECKPOINT_PROFILE}"'.encode()
    return identity in payload and ordinal in payload


def _count_rows(value: tuple[tuple[object, int], ...]) -> list[object]:
    rows: list[object] = []
    for key, count in value:
        if type(key) is tuple:
            encoded_key: object = [_json_key_part(part) for part in key]
        elif isinstance(key, ContactFaceKind):
            encoded_key = key.value
        else:
            encoded_key = key
        rows.append([encoded_key, count])
    return rows


def _json_key_part(value: object) -> object:
    if type(value) is tuple:
        return [_json_key_part(item) for item in value]
    if isinstance(value, ContactFaceKind):
        return value.value
    return value


def _state_record(state: SparseAggregate) -> dict[str, object]:
    cells = [[x, y] for x, y in sorted(state.occupied)]
    cell_bytes = canonical_json_bytes(cells)
    return {
        "checksum_sha256": _sha256(cell_bytes),
        "dtype": "python-int-pairs-v1",
        "occupied": cells,
        "shape": [len(cells), 2],
        "width": state.width,
    }


def _accumulator_record(accumulator: ReferenceEventAccumulator) -> dict[str, object]:
    record: dict[str, object] = {}
    simple = {
        "root_seed",
        "coupling_group_id",
        "width",
        "event_count",
        "occupied_mass",
        "height_sum",
        "height_square_sum",
        "below_envelope_volume",
        "void_count",
        "seam_lateral_face_count",
        "contacting_piece_cell_count",
        "contacted_aggregate_cell_count",
        "contacted_support_site_count",
        "contacted_support_column_count",
        "events_with_floor_support_face",
        "events_with_aggregate_support_face",
        "height_sum_delta",
        "height_square_sum_delta",
        "void_count_delta",
    }
    count_fields = {
        "family_counts",
        "orientation_counts",
        "contact_counts",
        "contact_face_kind_counts",
        "causal_face_kind_counts",
        "landing_gap_counts",
        "support_cluster_counts",
        "support_arc_span_counts",
        "support_gap_signature_counts",
        "pre_envelope_height_counts",
        "post_envelope_height_counts",
        "envelope_change_counts",
        "contact_gap_delta_counts",
    }
    for record_field in fields(ReferenceEventAccumulator):
        name = record_field.name
        value = getattr(accumulator, name)
        if name in simple:
            record[name] = value
        elif name == "current_state":
            record[name] = _state_record(value)
        elif name == "law":
            continue
        elif name in count_fields:
            record[name] = _count_rows(value)
        elif name == "topology_joint_counts":
            record[name] = [
                [_json_key_part(key), count, void_sum, roughness_sum] for key, count, void_sum, roughness_sum in value
            ]
        else:
            raise AssertionError(f"unhandled accumulator field {name!r}")
    return record


def _checkpoint_record(config: ReferenceTrajectoryConfig, accumulator: ReferenceEventAccumulator) -> dict[str, object]:
    configuration = _config_record(config)
    return {
        "accumulator": _accumulator_record(accumulator),
        "configuration": configuration,
        "configuration_sha256": _sha256(canonical_json_bytes(configuration)),
        "next_event_ordinal": accumulator.event_count,
        "profile": _CHECKPOINT_PROFILE,
    }


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceCheckpoint:
    event_ordinal: int
    payload: bytes
    sha256: str

    def __post_init__(self) -> None:
        event = _require_uint(self.event_ordinal, maximum=_U64_MAX, label="checkpoint event_ordinal")
        if type(self.payload) is not bytes:
            raise TypeError("checkpoint payload must be bytes")
        digest = _require_sha256(self.sha256, label="checkpoint sha256")
        if _sha256(self.payload) != digest:
            raise ValueError("checkpoint SHA-256 does not match its payload")
        object.__setattr__(self, "event_ordinal", event)


@dataclass(frozen=True, slots=True, kw_only=True)
class ReferenceTrajectory:
    config: ReferenceTrajectoryConfig
    accumulator: ReferenceEventAccumulator
    checkpoints: tuple[ReferenceCheckpoint, ...]
    final_manifest: bytes | None

    def __post_init__(self) -> None:
        if type(self.config) is not ReferenceTrajectoryConfig:
            raise TypeError("config must be a ReferenceTrajectoryConfig")
        if type(self.accumulator) is not ReferenceEventAccumulator:
            raise TypeError("accumulator must be a ReferenceEventAccumulator")
        if type(self.checkpoints) is not tuple or any(
            type(value) is not ReferenceCheckpoint for value in self.checkpoints
        ):
            raise TypeError("checkpoints must be a tuple of ReferenceCheckpoint values")
        if self.accumulator.event_count > self.config.terminal_event_count:
            raise ValueError("accumulator lies beyond the configured terminal event")
        if (
            self.accumulator.root_seed != self.config.root_seed
            or self.accumulator.coupling_group_id != self.config.coupling_group_id
            or self.accumulator.law != self.config.law
            or self.accumulator.width != self.config.width
        ):
            raise ValueError("accumulator does not match the trajectory configuration identity")
        expected = tuple(
            value for value in self.config.checkpoint_schedule.event_ordinals if value <= self.accumulator.event_count
        )
        if tuple(checkpoint.event_ordinal for checkpoint in self.checkpoints) != expected:
            raise ValueError("checkpoint inventory does not equal the reached configured schedule")
        if any(
            not _payload_claims_config_and_ordinal(
                payload=checkpoint.payload,
                config=self.config,
                event_ordinal=checkpoint.event_ordinal,
            )
            for checkpoint in self.checkpoints
        ):
            raise ValueError("checkpoint inventory contains a mismatched configuration or ordinal identity")
        if self.checkpoints and self.checkpoints[-1].event_ordinal == self.accumulator.event_count:
            if self.checkpoints[-1] != _make_checkpoint(self.config, self.accumulator):
                raise ValueError("latest checkpoint payload does not match the trajectory accumulator")
        internally_validated = _INTERNAL_TRAJECTORY_CONSTRUCTION.get()
        if not internally_validated and self.checkpoints:
            if self.checkpoints[-1].event_ordinal != self.accumulator.event_count:
                raise ValueError("an externally assembled resume must stand exactly at its latest checkpoint")
            replayed = reconstruct_reference_checkpoints(
                checkpoints=self.checkpoints,
                expected_config=self.config,
            )
            if replayed[-1] != self.accumulator:
                raise ValueError("externally assembled checkpoint inventory does not reconstruct its accumulator")
        if self.final_manifest is None:
            if self.accumulator.event_count == self.config.terminal_event_count:
                raise ValueError("a terminal trajectory requires its sole completion manifest")
        else:
            if type(self.final_manifest) is not bytes:
                raise TypeError("final_manifest must be bytes or None")
            if self.accumulator.event_count != self.config.terminal_event_count:
                raise ValueError("only a terminal trajectory may have a completion manifest")
            if self.final_manifest != _make_manifest(self.config, self.checkpoints):
                raise ValueError("final_manifest does not match the exact completed checkpoint inventory")
            reconstructed = reconstruct_reference_checkpoints(
                checkpoints=self.checkpoints,
                expected_config=self.config,
            )
            if reconstructed[-1] != self.accumulator:
                raise ValueError("terminal checkpoint replay does not match the trajectory accumulator")


def start_reference_trajectory(*, config: ReferenceTrajectoryConfig) -> ReferenceTrajectory:
    if type(config) is not ReferenceTrajectoryConfig:
        raise TypeError("config must be a ReferenceTrajectoryConfig")
    accumulator = start_event_accumulator(
        empty_state=SparseAggregate.empty(config.width),
        root_seed=config.root_seed,
        coupling_group_id=config.coupling_group_id,
        law=config.law,
    )
    return _construct_trajectory(
        config=config,
        accumulator=accumulator,
        checkpoints=(),
        final_manifest=None,
    )


def _construct_trajectory(
    *,
    config: ReferenceTrajectoryConfig,
    accumulator: ReferenceEventAccumulator,
    checkpoints: tuple[ReferenceCheckpoint, ...],
    final_manifest: bytes | None,
) -> ReferenceTrajectory:
    token = _INTERNAL_TRAJECTORY_CONSTRUCTION.set(True)
    try:
        return ReferenceTrajectory(
            config=config,
            accumulator=accumulator,
            checkpoints=checkpoints,
            final_manifest=final_manifest,
        )
    finally:
        _INTERNAL_TRAJECTORY_CONSTRUCTION.reset(token)


def _make_checkpoint(config: ReferenceTrajectoryConfig, accumulator: ReferenceEventAccumulator) -> ReferenceCheckpoint:
    payload = canonical_json_bytes(_checkpoint_record(config, accumulator))
    return ReferenceCheckpoint(event_ordinal=accumulator.event_count, payload=payload, sha256=_sha256(payload))


def _make_manifest(config: ReferenceTrajectoryConfig, checkpoints: tuple[ReferenceCheckpoint, ...]) -> bytes:
    return canonical_json_bytes(
        {
            "checkpoint_inventory": [[item.event_ordinal, item.sha256] for item in checkpoints],
            "checkpoint_vector_sha256": config.checkpoint_schedule.vector_sha256,
            "configuration_sha256": _sha256(_config_bytes(config)),
            "final_checkpoint_sha256": checkpoints[-1].sha256,
            "profile": _MANIFEST_PROFILE,
            "status": "complete",
            "terminal_event_count": config.terminal_event_count,
        }
    )


def advance_reference_trajectory(*, trajectory: ReferenceTrajectory, stop_event_ordinal: int) -> ReferenceTrajectory:
    """Advance to one absolute stop, failing all bounds before mutation."""

    if type(trajectory) is not ReferenceTrajectory:
        raise TypeError("trajectory must be a ReferenceTrajectory")
    stop = _require_uint(stop_event_ordinal, maximum=_U64_MAX, label="stop_event_ordinal")
    config = trajectory.config
    if not trajectory.accumulator.event_count <= stop <= config.terminal_event_count:
        raise ValueError("stop_event_ordinal must lie between current and terminal event counts")
    # Repeat the three ratified bounds at the mutation boundary even though the
    # frozen config already certified them.
    if stop >= 1 << 64 or config.width * stop >= 1 << 64 or config.width * stop * stop >= 1 << 128:
        raise ValueError("trajectory stop exceeds its frozen arithmetic bounds")
    accumulator = trajectory.accumulator
    checkpoints = list(trajectory.checkpoints)
    checkpoint_set = set(config.checkpoint_schedule.event_ordinals)
    while accumulator.event_count < stop:
        selection = select_event(
            root_seed=config.root_seed,
            coupling_group_id=config.coupling_group_id,
            event_ordinal=accumulator.event_count,
            law=config.law,
        )
        event = place_selected_event(state=accumulator.current_state, selection=selection)
        accumulator = accumulate_event(accumulator=accumulator, event=event)
        if accumulator.event_count in checkpoint_set:
            checkpoints.append(_make_checkpoint(config, accumulator))
    checkpoint_tuple = tuple(checkpoints)
    manifest = _make_manifest(config, checkpoint_tuple) if stop == config.terminal_event_count else None
    return _construct_trajectory(
        config=config,
        accumulator=accumulator,
        checkpoints=checkpoint_tuple,
        final_manifest=manifest,
    )


def _dict(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise TypeError(f"{label} must be a JSON object with string keys")
    return value


def _expect_keys(record: dict[str, object], expected: tuple[str, ...], *, label: str) -> None:
    if tuple(sorted(record)) != tuple(sorted(expected)):
        raise ValueError(f"{label} inventory does not match the frozen schema")


def _list(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        raise TypeError(f"{label} must be a JSON array")
    return value


def _text_list(value: object, *, label: str) -> list[str]:
    return [_require_text(item, label=f"{label}[{index}]") for index, item in enumerate(_list(value, label=label))]


def _int_list(value: object, *, label: str) -> list[int]:
    return [_require_int(item, label=f"{label}[{index}]") for index, item in enumerate(_list(value, label=label))]


def _parse_canonical(payload: bytes) -> dict[str, object]:
    if type(payload) is not bytes:
        raise TypeError("checkpoint payload must be bytes")
    if not payload.endswith(b"\n") or payload.endswith(b"\n\n"):
        raise ValueError("checkpoint payload must have exactly one trailing newline")

    def object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("checkpoint JSON contains a duplicate object key")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_float=lambda _value: (_ for _ in ()).throw(ValueError("floats are forbidden")),
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite values are forbidden")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("checkpoint payload is not strict UTF-8 JSON") from error
    record = _dict(value, label="checkpoint")
    if canonical_json_bytes(record) != payload:
        raise ValueError("checkpoint payload is not in canonical byte form")
    return record


def _state_from_record(value: object) -> SparseAggregate:
    record = _dict(value, label="state")
    _expect_keys(record, ("checksum_sha256", "dtype", "occupied", "shape", "width"), label="state")
    if record.get("dtype") != "python-int-pairs-v1":
        raise ValueError("state dtype does not match the frozen checkpoint profile")
    width = _require_int(record.get("width"), label="state width")
    cells_value = _list(record.get("occupied"), label="state occupied")
    cells: list[tuple[int, int]] = []
    for index, item in enumerate(cells_value):
        pair = _int_list(item, label=f"state occupied[{index}]")
        if len(pair) != 2:
            raise ValueError("state occupied entries must have shape (2,)")
        cells.append((pair[0], pair[1]))
    if cells != sorted(cells) or len(cells) != len(set(cells)):
        raise ValueError("state occupied cells must be duplicate-free and strictly lexicographically sorted")
    if record.get("shape") != [len(cells), 2]:
        raise ValueError("state array shape does not match occupied data")
    if _require_sha256(record.get("checksum_sha256"), label="state checksum") != _sha256(
        canonical_json_bytes([[x, y] for x, y in cells])
    ):
        raise ValueError("state checksum does not match occupied bytes")
    return SparseAggregate(width=width, occupied=frozenset(cells))


def _pairs(value: object, *, label: str, key_decoder) -> tuple[tuple[object, int], ...]:
    result: list[tuple[object, int]] = []
    for index, item in enumerate(_list(value, label=label)):
        row = _list(item, label=f"{label}[{index}]")
        if len(row) != 2:
            raise ValueError(f"{label} rows must have length two")
        result.append((key_decoder(row[0]), _require_int(row[1], label=f"{label} count")))
    return tuple(result)


def _tuple_key(value: object) -> tuple[object, ...]:
    return tuple(_tuple_key(item) if type(item) is list else item for item in _list(value, label="tuple key"))


def _accumulator_from_record(value: object, *, config: ReferenceTrajectoryConfig) -> ReferenceEventAccumulator:
    record = _dict(value, label="accumulator")
    scalar_names = {
        "root_seed",
        "coupling_group_id",
        "width",
        "event_count",
        "occupied_mass",
        "height_sum",
        "height_square_sum",
        "below_envelope_volume",
        "void_count",
        "seam_lateral_face_count",
        "contacting_piece_cell_count",
        "contacted_aggregate_cell_count",
        "contacted_support_site_count",
        "contacted_support_column_count",
        "events_with_floor_support_face",
        "events_with_aggregate_support_face",
        "height_sum_delta",
        "height_square_sum_delta",
        "void_count_delta",
    }
    count_fields = {
        "family_counts",
        "orientation_counts",
        "contact_counts",
        "landing_gap_counts",
        "support_cluster_counts",
        "support_arc_span_counts",
        "support_gap_signature_counts",
        "pre_envelope_height_counts",
        "post_envelope_height_counts",
        "envelope_change_counts",
        "contact_gap_delta_counts",
    }
    expected_fields = tuple(field.name for field in fields(ReferenceEventAccumulator) if field.name != "law")
    _expect_keys(record, expected_fields, label="accumulator")
    kwargs: dict[str, object] = {name: record.get(name) for name in scalar_names}
    kwargs["law"] = config.law
    kwargs["current_state"] = _state_from_record(record.get("current_state"))
    for name in count_fields:
        kwargs[name] = _pairs(
            record.get(name), label=name, key_decoder=lambda item: _tuple_key(item) if type(item) is list else item
        )
    face_by_value = {kind.value: kind for kind in ContactFaceKind}
    for name in ("contact_face_kind_counts", "causal_face_kind_counts"):
        kwargs[name] = _pairs(
            record.get(name),
            label=name,
            key_decoder=lambda item: face_by_value.get(item, item),
        )
    topology: list[tuple[object, int, int, int]] = []
    for index, item in enumerate(_list(record.get("topology_joint_counts"), label="topology_joint_counts")):
        row = _list(item, label=f"topology_joint_counts[{index}]")
        if len(row) != 4:
            raise ValueError("topology_joint_counts rows must have length four")
        topology.append((_tuple_key(row[0]), *(_require_int(part, label="topology total") for part in row[1:])))
    kwargs["topology_joint_counts"] = tuple(topology)
    return ReferenceEventAccumulator(**kwargs)  # type: ignore[arg-type]


def _config_from_record(value: object) -> ReferenceTrajectoryConfig:
    record = _dict(value, label="configuration")
    _expect_keys(
        record,
        (
            "checkpoint_event_ordinals",
            "checkpoint_vector_sha256",
            "coupling_group_id",
            "law",
            "model_law_id",
            "plan_id",
            "profile",
            "rng_algorithm",
            "root_seed",
            "software_commit",
            "terminal_event_count",
            "width",
        ),
        label="configuration",
    )
    if record.get("profile") != _CONFIG_PROFILE:
        raise ValueError("configuration profile is not recognized")
    terminal = _require_int(record.get("terminal_event_count"), label="terminal_event_count")
    schedule = ReferenceCheckpointSchedule(
        terminal_event_count=terminal,
        event_ordinals=tuple(_int_list(record.get("checkpoint_event_ordinals"), label="checkpoint event ordinals")),
        vector_sha256=_require_sha256(record.get("checkpoint_vector_sha256"), label="checkpoint vector SHA-256"),
    )
    return ReferenceTrajectoryConfig(
        model_law_id=_require_text(record.get("model_law_id"), label="model_law_id"),
        plan_id=_require_text(record.get("plan_id"), label="plan_id"),
        software_commit=_require_commit(record.get("software_commit")),
        root_seed=_require_int(record.get("root_seed"), label="root_seed"),
        coupling_group_id=_require_text(record.get("coupling_group_id"), label="coupling_group_id"),
        law=_law_from_record(record.get("law")),
        width=_require_int(record.get("width"), label="width"),
        terminal_event_count=terminal,
        checkpoint_schedule=schedule,
        rng_algorithm=_require_text(record.get("rng_algorithm"), label="rng_algorithm"),
    )


def _decode_checkpoint_payload(
    *, payload: bytes, expected_config: ReferenceTrajectoryConfig, expected_sha256: str
) -> ReferenceEventAccumulator:
    """Authenticate and structurally decode one payload without replay."""

    if type(expected_config) is not ReferenceTrajectoryConfig:
        raise TypeError("expected_config must be a ReferenceTrajectoryConfig")
    digest = _require_sha256(expected_sha256, label="expected_sha256")
    if _sha256(payload) != digest:
        raise ValueError("checkpoint payload SHA-256 does not match the expected identity")
    record = _parse_canonical(payload)
    _expect_keys(
        record,
        ("accumulator", "configuration", "configuration_sha256", "next_event_ordinal", "profile"),
        label="checkpoint",
    )
    if record.get("profile") != _CHECKPOINT_PROFILE:
        raise ValueError("checkpoint profile is not recognized")
    configuration_record = _dict(record.get("configuration"), label="configuration")
    configuration_bytes = canonical_json_bytes(configuration_record)
    if _require_sha256(record.get("configuration_sha256"), label="configuration_sha256") != _sha256(
        configuration_bytes
    ):
        raise ValueError("checkpoint configuration digest does not match its bytes")
    reconstructed_config = _config_from_record(configuration_record)
    if reconstructed_config != expected_config or configuration_bytes != _config_bytes(expected_config):
        raise ValueError("checkpoint configuration bytes do not match the expected task identity")
    accumulator = _accumulator_from_record(record.get("accumulator"), config=expected_config)
    next_event = _require_int(record.get("next_event_ordinal"), label="next_event_ordinal")
    if accumulator.event_count != next_event:
        raise ValueError("next event ordinal does not match the reconstructed accumulator")
    if (
        accumulator.root_seed != expected_config.root_seed
        or accumulator.coupling_group_id != expected_config.coupling_group_id
        or accumulator.law != expected_config.law
        or accumulator.width != expected_config.width
    ):
        raise ValueError("reconstructed accumulator violates the expected scientific/RNG identity")
    return accumulator


def _replay_event(
    accumulator: ReferenceEventAccumulator, config: ReferenceTrajectoryConfig
) -> ReferenceEventAccumulator:
    """Replay through lower certified primitives, bypassing writer composition."""

    address = {
        "root_seed": config.root_seed,
        "coupling_group_id": config.coupling_group_id,
        "event_ordinal": accumulator.event_count,
        "declared_streams": _CERTIFIED_STREAMS,
    }
    family = _CERTIFIED_SELECT_WEIGHTED(
        **address,
        stream_name="family",
        law=config.law.family_law,
    )
    orientation = _CERTIFIED_SELECT_WEIGHTED(
        **address,
        stream_name="orientation",
        law=config.law.orientation_laws.law_for(family.outcome_id),
    )
    launch = _CERTIFIED_SELECT_UNIFORM(
        **address,
        stream_name="launch",
        law=config.law.launch_law,
    )
    contact = _CERTIFIED_SELECT_WEIGHTED(
        **address,
        stream_name="contact",
        law=config.law.contact_law,
    )
    selection = TetrominoEventSelection(
        root_seed=config.root_seed,
        coupling_group_id=config.coupling_group_id,
        event_ordinal=accumulator.event_count,
        law=config.law,
        family=family,
        orientation=orientation,
        launch=launch,
        contact=contact,
    )
    placement = _CERTIFIED_PLACE_ONE(
        accumulator.current_state,
        GEOMETRY_BY_ID[selection.geometry_id],
        selection.launch_x,
        ContactKind(selection.contact_id),
    )
    event = ReferenceEventPlacement(selection=selection, placement=placement)
    return _CERTIFIED_ACCUMULATE_EVENT(accumulator=accumulator, event=event)


def reconstruct_reference_checkpoints(
    *, checkpoints: tuple[ReferenceCheckpoint, ...], expected_config: ReferenceTrajectoryConfig
) -> tuple[ReferenceEventAccumulator, ...]:
    """Independently replay and validate an ordered checkpoint inventory once.

    Unlike the writer, this path ignores every persisted summary while
    recomputing the deterministic prefix from the authenticated configuration.
    Persisted accumulator records are accepted only when every field equals the
    independently replayed certified prefix.
    """

    if type(expected_config) is not ReferenceTrajectoryConfig:
        raise TypeError("expected_config must be a ReferenceTrajectoryConfig")
    if type(checkpoints) is not tuple or not checkpoints:
        raise TypeError("checkpoints must be a nonempty tuple of ReferenceCheckpoint values")
    if any(type(checkpoint) is not ReferenceCheckpoint for checkpoint in checkpoints):
        raise TypeError("checkpoints must contain exact ReferenceCheckpoint values")
    ordinals = tuple(checkpoint.event_ordinal for checkpoint in checkpoints)
    if any(left >= right for left, right in zip(ordinals, ordinals[1:])):
        raise ValueError("checkpoint replay inventory must be strictly increasing")
    schedule = expected_config.checkpoint_schedule.event_ordinals
    if any(ordinal not in schedule for ordinal in ordinals):
        raise ValueError("checkpoint replay inventory contains an unconfigured ordinal")
    if ordinals[-1] > expected_config.terminal_event_count:
        raise ValueError("checkpoint replay inventory exceeds the terminal event count")

    decoded = tuple(
        _decode_checkpoint_payload(
            payload=checkpoint.payload,
            expected_config=expected_config,
            expected_sha256=checkpoint.sha256,
        )
        for checkpoint in checkpoints
    )
    if any(actual.event_count != ordinal for actual, ordinal in zip(decoded, ordinals)):
        raise ValueError("checkpoint wrapper ordinal does not match its authenticated payload")

    replayed = _CERTIFIED_START_ACCUMULATOR(
        empty_state=SparseAggregate.empty(expected_config.width),
        root_seed=expected_config.root_seed,
        coupling_group_id=expected_config.coupling_group_id,
        law=expected_config.law,
    )
    results: list[ReferenceEventAccumulator] = []
    next_index = 0
    while replayed.event_count < ordinals[-1]:
        replayed = _replay_event(replayed, expected_config)
        if replayed.event_count == ordinals[next_index]:
            if replayed != decoded[next_index]:
                raise ValueError(
                    f"checkpoint {replayed.event_count} summaries do not match independent deterministic replay"
                )
            results.append(replayed)
            next_index += 1
            if next_index == len(ordinals):
                break
    if next_index != len(ordinals):
        raise AssertionError("checkpoint replay did not reach the complete requested inventory")
    return tuple(results)


def reconstruct_reference_checkpoint(
    *, payload: bytes, expected_config: ReferenceTrajectoryConfig, expected_sha256: str
) -> ReferenceEventAccumulator:
    """Independently replay, authenticate, and reconstruct one checkpoint."""

    decoded = _decode_checkpoint_payload(
        payload=payload,
        expected_config=expected_config,
        expected_sha256=expected_sha256,
    )
    checkpoint = ReferenceCheckpoint(
        event_ordinal=decoded.event_count,
        payload=payload,
        sha256=expected_sha256,
    )
    return reconstruct_reference_checkpoints(
        checkpoints=(checkpoint,),
        expected_config=expected_config,
    )[0]
