"""Independent adversarial certificate for PRE one-cell checkpoints."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import re
import shutil
import stat
import textwrap
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as reference_engine
import tetris_ballistic.engine.one_cell_checkpoint as checkpoint_module
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_checkpoint import (
    OneCellCheckpointBinding,
    OneCellCheckpointProgress,
    OneCellCheckpointSchedule,
    OneCellCheckpointValidationError,
    OneCellInterruptionFlag,
    advance_one_cell_checkpoint_generation,
    build_one_cell_checkpoint_schedule,
    publish_one_cell_final,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SOFTWARE_PARENT = "70d0c5d1a7a8cdc62a2ef1ad1b255f8ff4f43a4b"
_U64_SPACE = 1 << 64
_U64_MASK = _U64_SPACE - 1
_PRIMARY = (0, 1, 2, 5, 10, 25, 50, 100)
_B1 = (0, 5, 50, 100)
_B2_FULL = (5, 50, 90, 95, 98, 99)
_B2_HIGH = (90, 95, 98, 99)
_SCHEDULES = (_PRIMARY, _B1, _B2_FULL, _B2_HIGH)
_LAW_IDS = (
    "periodic-v1",
    "hard-wall-legacy-asymmetric-v1",
    "hard-wall-reflection-symmetric-v1",
)
_LAWS = tuple(OneCellBoundaryLaw(value) for value in _LAW_IDS)
_DECLARED_HORIZONS = (
    17_378,
    98_304,
    556_092,
    3_145_728,
    17_794_925,
    100_663_296,
    196_608,
    1_112_184,
    6_291_456,
    35_589_850,
    201_326_592,
    55_000,
    172_800,
    300_000,
    832_500,
    1_720_000,
    3_000_000,
    4_680_000,
    9_600_000,
    17_000_000,
)
_SNAPSHOT_INDICES = (0, 34, 68, 102, 136, 170, 204, 238, 273, 307, 341, 375, 409, 443, 477, 511)

_GROUP = "pre-one-cell-discovery-v1"
_DOMAIN = b"tetris-kpz/semantic-philox4x64-10-v1\0"
_M0 = 0xD2E7470EE14C6C93
_M1 = 0xCA5A826395121157
_W0 = 0x9E3779B97F4A7C15
_W1 = 0xBB67AE8584CAA73B

_SCHEDULE_FIELDS = (
    "terminal_event_count",
    "checkpoint_event_counts",
    "snapshot_checkpoint_indices",
    "snapshot_event_counts",
    "checkpoint_vector_sha256",
    "snapshot_vector_sha256",
)
_BINDING_FIELDS = (
    "root_seed",
    "boundary_law",
    "width",
    "threshold_schedule",
    "terminal_event_count",
    "configuration_bytes",
    "scientific_identity_bytes",
    "software_commit",
)
_PROGRESS_FIELDS = (
    "disposition",
    "trajectory",
    "generation",
    "checkpoint_count",
    "snapshot_count",
    "used_fallback",
    "manifest_path",
)
_PUBLIC_API = [
    "OneCellCheckpointValidationError",
    "OneCellCheckpointBinding",
    "OneCellCheckpointSchedule",
    "OneCellCheckpointProgress",
    "OneCellInterruptionFlag",
    "build_one_cell_checkpoint_schedule",
    "advance_one_cell_checkpoint_generation",
    "publish_one_cell_final",
]


class _HostileInt(int):
    pass


class _HostileBytes(bytes):
    pass


class _HostileString(str):
    pass


def _canonical_json(value: object, *, newline: bool = False) -> bytes:
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


# This schedule oracle calls no production schedule helper and makes its
# rounding decision solely through the frozen integer inequalities.
def _oracle_rounded_power(*, base: int, exponent: int) -> int:
    scaled = (1 << 383) * pow(base, exponent)
    low = 0
    high = base
    while low <= high:
        candidate = (low + high) // 2
        left = pow(2 * candidate - 1, 383)
        right = pow(2 * candidate + 1, 383)
        if left <= scaled < right:
            return candidate
        if scaled < left:
            high = candidate - 1
        else:
            low = candidate + 1
    raise AssertionError("exact schedule rounding candidate was not found")


def _oracle_schedule(terminal: int) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...], str, str]:
    midpoint = (terminal + 1) // 2
    early_terminal = midpoint - 1
    early = [1]
    for index in range(1, 384):
        rounded = _oracle_rounded_power(base=early_terminal, exponent=index)
        early.append(
            min(
                early_terminal - (383 - index),
                max(early[-1] + 1, rounded),
            )
        )
    assert early[-1] == early_terminal
    late = tuple(midpoint + (index * (terminal - midpoint)) // 127 for index in range(128))
    checkpoints = tuple(early) + late
    snapshot_events = tuple(checkpoints[index] for index in _SNAPSHOT_INDICES)
    checkpoint_preimage = _canonical_json(
        {
            "event_counts": checkpoints,
            "profile": "tetris-pre-one-cell-checkpoint-vector@1",
        }
    )
    snapshot_preimage = _canonical_json(
        {
            "checkpoint_indices": _SNAPSHOT_INDICES,
            "event_counts": snapshot_events,
            "profile": "tetris-pre-one-cell-snapshot-vector@1",
        }
    )
    return checkpoints, _SNAPSHOT_INDICES, snapshot_events, _sha256(checkpoint_preimage), _sha256(snapshot_preimage)


# The scientific oracle below independently implements key derivation,
# Philox, exact rejection mapping, the three boundary laws, and every retained
# accumulator. It imports no production RNG, transition, or trajectory helper.
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


def _oracle_uniform(*, root_seed: int, stream_name: str, event: int, bound: int) -> int:
    key = _oracle_key(root_seed, stream_name)
    quotient = _U64_SPACE // bound
    limit = quotient * bound
    rejection = 0
    while True:
        word = _oracle_philox((event, rejection, 0, 0), key)[0]
        if word < limit:
            return word // quotient
        rejection += 1


def _empty_oracle_arm(*, law_id: str, threshold: int, width: int) -> dict[str, object]:
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


def _oracle_transition(
    *, law_id: str, heights: tuple[int, ...], launch: int, sticky: bool
) -> tuple[tuple[int, ...], int, bool, int, int, bool | None]:
    width = len(heights)
    vertical = heights[launch] + 1
    if law_id == "periodic-v1":
        left = heights[(launch - 1) % width]
        right = heights[(launch + 1) % width]
        left_eligible = right_eligible = True
    else:
        left = heights[launch - 1] if launch > 0 else None
        right = heights[launch + 1] if launch < width - 1 else None
        left_eligible = launch > (1 if law_id == "hard-wall-legacy-asymmetric-v1" else 0)
        right_eligible = launch < width - 1
    post = vertical
    if sticky and left_eligible:
        assert left is not None
        post = max(post, left)
    if sticky and right_eligible:
        assert right is not None
        post = max(post, right)
    gap = post - vertical
    trigger = sticky and gap > 0
    left_causal = trigger and left_eligible and left == post
    right_causal = trigger and right_eligible and right == post
    causal = 3 if left_causal and right_causal else 1 if left_causal else 2 if right_causal else 0
    mask = (
        int(post == vertical)
        + 2 * int(left is not None and left == post)
        + 4 * int(right is not None and right == post)
    )
    seam = bool((launch == 0 and mask & 2) or (launch == width - 1 and mask & 4)) if law_id == "periodic-v1" else None
    result = list(heights)
    result[launch] = post
    return tuple(result), gap, trigger, causal, mask, seam


def _oracle_step(
    arms: tuple[dict[str, object], ...],
    *,
    root_seed: int,
    law_id: str,
    width: int,
    event: int,
) -> tuple[dict[str, object], ...]:
    launch = _oracle_uniform(root_seed=root_seed, stream_name="launch", event=event, bound=width)
    contact = _oracle_uniform(root_seed=root_seed, stream_name="contact", event=event, bound=100)
    next_arms = []
    for original in arms:
        arm = {
            **original,
            "causal_counts": list(original["causal_counts"]),
            "causal_gap_sums": list(original["causal_gap_sums"]),
            "endpoint_equality_mask_counts": [
                list(original["endpoint_equality_mask_counts"][0]),
                list(original["endpoint_equality_mask_counts"][1]),
            ],
            "gap_histogram": dict(original["gap_histogram"]),
        }
        sticky = contact < arm["threshold"]
        before = arm["heights"]
        after, gap, trigger, causal, mask, seam = _oracle_transition(
            law_id=law_id,
            heights=before,
            launch=launch,
            sticky=sticky,
        )
        old_height = before[launch]
        new_height = after[launch]
        arm["heights"] = after
        arm["event_count"] += 1
        arm["height_sum"] += new_height - old_height
        arm["height_square_sum"] += new_height * new_height - old_height * old_height
        arm["void_volume"] += gap
        arm["endpoint_selected_count"] += int(sticky)
        arm["positive_gap_trigger_count"] += int(trigger)
        arm["gap_sum"] += gap
        arm["maximum_gap"] = max(arm["maximum_gap"], gap)
        arm["causal_counts"][causal] += 1
        arm["causal_gap_sums"][causal] += gap
        arm["endpoint_equality_mask_counts"][int(sticky)][mask] += 1
        arm["gap_histogram"][gap] = arm["gap_histogram"].get(gap, 0) + 1
        if seam is not None:
            arm["seam_equality_count"] += int(seam)
        next_arms.append(arm)
    return tuple(next_arms)


def _oracle_prefixes(
    *,
    root_seed: int,
    law_id: str,
    width: int,
    schedule: tuple[int, ...],
    stops: tuple[int, ...],
) -> dict[int, tuple[dict[str, object], ...]]:
    wanted = set(stops)
    arms = tuple(_empty_oracle_arm(law_id=law_id, threshold=threshold, width=width) for threshold in schedule)
    result = {0: arms} if 0 in wanted else {}
    for event in range(max(stops, default=0)):
        arms = _oracle_step(arms, root_seed=root_seed, law_id=law_id, width=width, event=event)
        if event + 1 in wanted:
            result[event + 1] = arms
    assert set(result) == wanted
    return result


def _oracle_run(
    *, root_seed: int, law_id: str, width: int, schedule: tuple[int, ...], stop: int
) -> tuple[dict[str, object], ...]:
    return _oracle_prefixes(
        root_seed=root_seed,
        law_id=law_id,
        width=width,
        schedule=schedule,
        stops=(stop,),
    )[stop]


def _assert_matches_oracle(progress: OneCellCheckpointProgress) -> None:
    trajectory = progress.trajectory
    expected = _oracle_run(
        root_seed=trajectory.root_seed,
        law_id=trajectory.boundary_law.value,
        width=trajectory.width,
        schedule=trajectory.threshold_schedule,
        stop=trajectory.event_count,
    )
    for actual, oracle in zip(trajectory.arms, expected):
        assert actual.threshold == oracle["threshold"]
        assert actual.heights == oracle["heights"]
        assert actual.event_count == oracle["event_count"]
        assert actual.height_sum == oracle["height_sum"]
        assert actual.height_square_sum == oracle["height_square_sum"]
        assert actual.void_volume == oracle["void_volume"]
        assert actual.endpoint_selected_count == oracle["endpoint_selected_count"]
        assert actual.positive_gap_trigger_count == oracle["positive_gap_trigger_count"]
        assert actual.gap_sum == oracle["gap_sum"]
        assert actual.maximum_gap == oracle["maximum_gap"]
        assert actual.causal_counts == tuple(oracle["causal_counts"])
        assert actual.causal_gap_sums == tuple(oracle["causal_gap_sums"])
        assert actual.endpoint_equality_mask_counts == tuple(
            tuple(row) for row in oracle["endpoint_equality_mask_counts"]
        )
        assert actual.gap_histogram == tuple(sorted(oracle["gap_histogram"].items()))
        assert actual.seam_equality_count == oracle["seam_equality_count"]


def _binding(**overrides: object) -> OneCellCheckpointBinding:
    values: dict[str, object] = {
        "root_seed": 7,
        "boundary_law": OneCellBoundaryLaw.PERIODIC,
        "width": 3,
        "threshold_schedule": _PRIMARY,
        "terminal_event_count": 769,
        "configuration_bytes": b"synthetic-checkpoint-config-v1\n",
        "scientific_identity_bytes": b"synthetic-checkpoint-identity-v1\n",
        "software_commit": _SOFTWARE_PARENT,
    }
    values.update(overrides)
    return OneCellCheckpointBinding(**values)


def _new_task(root: Path, name: str = "task") -> Path:
    path = root / name
    path.mkdir(mode=0o700)
    return path


def _advance(task: Path, binding: OneCellCheckpointBinding, flag: OneCellInterruptionFlag | None = None):
    return advance_one_cell_checkpoint_generation(
        task_directory=str(task),
        binding=binding,
        interruption_flag=flag,
    )


def _manifest_path(task: Path, generation: int) -> Path:
    return task / f"checkpoint.{generation:020d}.manifest.json"


def _member_path(task: Path, generation: int, suffix: str) -> Path:
    return task / f"checkpoint.{generation:020d}.{suffix}"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_canonical(path: Path, value: object) -> None:
    path.write_bytes(_canonical_json(value, newline=True))
    path.chmod(0o600)


def _assert_strict_canonical_json(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    assert payload.endswith(b"\n")
    assert not payload.endswith(b"\n\n")
    value = json.loads(payload)
    assert payload == _canonical_json(value, newline=True)
    return value


def _replace_member(task: Path, generation: int, label: str, payload: bytes) -> None:
    manifest_path = _manifest_path(task, generation)
    manifest = _load_json(manifest_path)
    entry = manifest["members"][label]
    target = task / entry["filename"]
    target.write_bytes(payload)
    target.chmod(0o600)
    entry["sha256"] = _sha256(payload)
    entry["size_bytes"] = len(payload)
    _write_canonical(manifest_path, manifest)


def _decode_generation(
    task: Path, generation: int
) -> tuple[dict[str, object], dict[str, tuple[tuple[int, ...], tuple[int, ...]]]]:
    manifest = _load_json(_manifest_path(task, generation))
    state = _load_json(task / manifest["members"]["state"]["filename"])
    array_bytes = (task / manifest["members"]["arrays"]["filename"]).read_bytes()
    assert len(array_bytes) % 8 == 0
    words = tuple(int.from_bytes(array_bytes[index : index + 8], "little") for index in range(0, len(array_bytes), 8))
    decoded = {}
    for section in state["sections"]:
        offset = section["offset_words"]
        count = section["word_count"]
        decoded[section["name"]] = (tuple(section["shape"]), words[offset : offset + count])
    return state, decoded


def _clone_generation(task: Path, source: int, target: int) -> None:
    source_manifest = _load_json(_manifest_path(task, source))
    target_manifest = json.loads(json.dumps(source_manifest))
    target_manifest["generation"] = target
    for label, entry in target_manifest["members"].items():
        source_name = entry["filename"]
        suffix = source_name.split(f"checkpoint.{source:020d}.", 1)[1]
        target_name = f"checkpoint.{target:020d}.{suffix}"
        payload = (task / source_name).read_bytes()
        if label == "state":
            state = json.loads(payload)
            state["generation"] = target
            payload = _canonical_json(state, newline=True)
        target_path = task / target_name
        target_path.write_bytes(payload)
        target_path.chmod(0o600)
        entry["filename"] = target_name
        entry["sha256"] = _sha256(payload)
        entry["size_bytes"] = len(payload)
    _write_canonical(_manifest_path(task, target), target_manifest)


def _oracle_row(arm: dict[str, object]) -> tuple[int, ...]:
    square_sum = arm["height_square_sum"]
    seam_scratch = arm["seam_equality_count"] or 0
    return (
        arm["height_sum"],
        square_sum >> 64,
        square_sum & _U64_MASK,
        arm["void_volume"],
        arm["endpoint_selected_count"],
        arm["positive_gap_trigger_count"],
        arm["gap_sum"],
        arm["maximum_gap"],
        *arm["causal_counts"],
        *arm["causal_gap_sums"],
        *arm["endpoint_equality_mask_counts"][0],
        *arm["endpoint_equality_mask_counts"][1],
        seam_scratch,
    )


def _copy_task(template: Path, root: Path, name: str) -> Path:
    destination = root / name
    shutil.copytree(template, destination)
    return destination


@pytest.fixture(scope="session")
def terminal_template(tmp_path_factory) -> tuple[Path, OneCellCheckpointBinding]:
    task = _new_task(tmp_path_factory.mktemp("slice7-terminal"))
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    initial = _advance(task, binding, flag)
    assert initial.disposition == "requeue-required"
    assert initial.trajectory.event_count == 0
    assert initial.generation == 1
    terminal = _advance(task, binding)
    assert terminal.disposition == "terminal"
    assert terminal.trajectory.event_count == 769
    assert terminal.generation == 2
    return task, binding


@pytest.fixture
def terminal_task(tmp_path, terminal_template) -> tuple[Path, OneCellCheckpointBinding]:
    template, binding = terminal_template
    return _copy_task(template, tmp_path, "terminal-task"), binding


@pytest.fixture
def final_task(tmp_path, terminal_template) -> tuple[Path, OneCellCheckpointBinding]:
    template, binding = terminal_template
    task = _copy_task(template, tmp_path, "final-task")
    result = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert result.disposition == "complete"
    return task, binding


def test_public_surface_and_record_contracts(tmp_path) -> None:
    assert checkpoint_module.__all__ == _PUBLIC_API
    assert tuple(field.name for field in fields(OneCellCheckpointSchedule)) == _SCHEDULE_FIELDS
    assert tuple(field.name for field in fields(OneCellCheckpointBinding)) == _BINDING_FIELDS
    assert tuple(field.name for field in fields(OneCellCheckpointProgress)) == _PROGRESS_FIELDS
    assert issubclass(OneCellCheckpointValidationError, RuntimeError)
    for function in (
        build_one_cell_checkpoint_schedule,
        advance_one_cell_checkpoint_generation,
        publish_one_cell_final,
    ):
        assert all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in inspect.signature(function).parameters.values()
        )
    schedule = build_one_cell_checkpoint_schedule(terminal_event_count=769)
    with pytest.raises(FrozenInstanceError):
        schedule.terminal_event_count = 770
    binding = _binding()
    with pytest.raises(FrozenInstanceError):
        binding.width = 4
    task = _new_task(tmp_path)
    flag = OneCellInterruptionFlag()
    flag.request()
    progress = _advance(task, binding, flag)
    with pytest.raises(FrozenInstanceError):
        progress.generation = 9
    with pytest.raises(TypeError):
        build_one_cell_checkpoint_schedule(769)
    with pytest.raises(TypeError):
        advance_one_cell_checkpoint_generation(str(task), binding)
    with pytest.raises(TypeError):
        publish_one_cell_final(str(task), binding)
    with pytest.raises(TypeError):
        OneCellCheckpointBinding(
            7,
            OneCellBoundaryLaw.PERIODIC,
            3,
            _PRIMARY,
            769,
            b"config",
            b"identity",
            _SOFTWARE_PARENT,
        )
    with pytest.raises(ValueError):
        OneCellCheckpointSchedule(
            terminal_event_count=769,
            checkpoint_event_counts=(1,) * 512,
            snapshot_checkpoint_indices=_SNAPSHOT_INDICES,
            snapshot_event_counts=(1,) * 16,
            checkpoint_vector_sha256="0" * 64,
            snapshot_vector_sha256="0" * 64,
        )
    with pytest.raises(ValueError):
        OneCellCheckpointProgress(
            disposition="forged",
            trajectory=progress.trajectory,
            generation=progress.generation,
            checkpoint_count=progress.checkpoint_count,
            snapshot_count=progress.snapshot_count,
            used_fallback=False,
            manifest_path=progress.manifest_path,
        )


def test_exact_schedule_minimum_and_digest_preimages() -> None:
    with pytest.raises(ValueError):
        build_one_cell_checkpoint_schedule(terminal_event_count=768)
    actual = build_one_cell_checkpoint_schedule(terminal_event_count=769)
    expected = _oracle_schedule(769)
    assert (
        actual.checkpoint_event_counts,
        actual.snapshot_checkpoint_indices,
        actual.snapshot_event_counts,
        actual.checkpoint_vector_sha256,
        actual.snapshot_vector_sha256,
    ) == expected
    assert len(actual.checkpoint_event_counts) == 512
    assert len(actual.snapshot_event_counts) == 16
    assert actual.checkpoint_event_counts[0] == 1
    assert actual.checkpoint_event_counts[383:385] == (384, 385)
    assert actual.checkpoint_event_counts[-1] == 769
    assert all(left < right for left, right in zip(actual.checkpoint_event_counts, actual.checkpoint_event_counts[1:]))


def test_global_cadence_planner_never_crosses_observation_or_2pow20_seams() -> None:
    cadence = 1 << 20
    assert (
        checkpoint_module._next_recovery_boundary(current_event_count=0, terminal_event_count=cadence - 1)
        == cadence - 1
    )
    assert checkpoint_module._next_recovery_boundary(current_event_count=0, terminal_event_count=cadence) == cadence
    assert checkpoint_module._next_recovery_boundary(current_event_count=0, terminal_event_count=cadence + 1) == cadence
    assert (
        checkpoint_module._next_recovery_boundary(current_event_count=cadence - 1, terminal_event_count=cadence + 1)
        == cadence
    )
    assert (
        checkpoint_module._next_recovery_boundary(current_event_count=cadence, terminal_event_count=cadence + 1)
        == cadence + 1
    )
    assert (
        checkpoint_module._next_recovery_boundary(current_event_count=cadence + 1, terminal_event_count=cadence + 1)
        == cadence + 1
    )

    checkpoints = (1, cadence - 1, cadence, cadence + 1)
    assert checkpoint_module._planned_compiled_stops(
        current_event_count=0,
        terminal_event_count=cadence + 1,
        checkpoint_event_counts=checkpoints,
    ) == (1, cadence - 1, cadence)
    assert checkpoint_module._planned_compiled_stops(
        current_event_count=cadence - 1,
        terminal_event_count=cadence + 1,
        checkpoint_event_counts=checkpoints,
    ) == (cadence,)
    assert checkpoint_module._planned_compiled_stops(
        current_event_count=cadence,
        terminal_event_count=cadence + 1,
        checkpoint_event_counts=checkpoints,
    ) == (cadence + 1,)
    assert checkpoint_module._planned_compiled_stops(
        current_event_count=17,
        terminal_event_count=31,
        checkpoint_event_counts=(1, 11, 23),
    ) == (23, 31)


def test_full_literal_vector_document_kats_match_independent_oracle() -> None:
    document = (_REPO_ROOT / "docs/PRE-ONE-CELL-CHECKPOINT-VECTORS.md").read_text(encoding="utf-8")
    cases = (
        ("## Full minimum-boundary KAT: `N=769`", "## Full declared large-horizon KAT", 769),
        ("## Full declared large-horizon KAT: `N=100663296`", "## Scope", 100_663_296),
    )
    for heading, following, terminal in cases:
        section = document.split(heading, 1)[1].split(following, 1)[0]
        literals = {}
        for name in (
            "checkpoint_event_counts",
            "snapshot_checkpoint_indices",
            "snapshot_event_counts",
        ):
            match = re.search(rf"{name} = (\(.*?\n\))", section, flags=re.DOTALL)
            assert match is not None
            literals[name] = ast.literal_eval(match.group(1))
        expected = _oracle_schedule(terminal)
        assert literals["checkpoint_event_counts"] == expected[0]
        assert literals["snapshot_checkpoint_indices"] == expected[1]
        assert literals["snapshot_event_counts"] == expected[2]
        hashes = re.findall(r"`([0-9a-f]{64})`", section)
        assert hashes[-2:] == [expected[3], expected[4]]


@pytest.mark.slow
def test_exact_schedule_oracle_covers_every_declared_horizon() -> None:
    vector_document = (_REPO_ROOT / "docs/PRE-ONE-CELL-CHECKPOINT-VECTORS.md").read_text(encoding="utf-8")
    documented = {
        int(terminal.replace(",", "")): (checkpoint_hash, snapshot_hash)
        for terminal, checkpoint_hash, snapshot_hash in re.findall(
            r"^\| ([0-9,]+) \| `([0-9a-f]{64})` \| `([0-9a-f]{64})` \|$",
            vector_document,
            flags=re.MULTILINE,
        )
    }
    assert tuple(documented) == _DECLARED_HORIZONS
    for terminal in _DECLARED_HORIZONS:
        actual = build_one_cell_checkpoint_schedule(terminal_event_count=terminal)
        expected = _oracle_schedule(terminal)
        assert (
            actual.checkpoint_event_counts,
            actual.snapshot_checkpoint_indices,
            actual.snapshot_event_counts,
            actual.checkpoint_vector_sha256,
            actual.snapshot_vector_sha256,
        ) == expected
        midpoint = (terminal + 1) // 2
        assert actual.checkpoint_event_counts[383] == midpoint - 1
        assert actual.checkpoint_event_counts[384] == midpoint
        assert actual.checkpoint_event_counts[-1] == terminal
        assert documented[terminal] == expected[3:]


@pytest.mark.parametrize(
    "overrides,error",
    [
        ({"root_seed": True}, TypeError),
        ({"root_seed": _HostileInt(7)}, TypeError),
        ({"root_seed": -1}, ValueError),
        ({"root_seed": 1 << 128}, ValueError),
        ({"boundary_law": "periodic-v1"}, TypeError),
        ({"width": True}, TypeError),
        ({"width": 2}, ValueError),
        ({"width": 1025}, ValueError),
        ({"threshold_schedule": list(_PRIMARY)}, TypeError),
        ({"threshold_schedule": (0, 1, 2, 5, 10, 25, 50, True)}, TypeError),
        ({"threshold_schedule": (0, 5, 100)}, ValueError),
        ({"terminal_event_count": 768}, ValueError),
        ({"terminal_event_count": True}, TypeError),
        ({"configuration_bytes": bytearray(b"x")}, TypeError),
        ({"configuration_bytes": _HostileBytes(b"x")}, TypeError),
        ({"configuration_bytes": b""}, ValueError),
        ({"configuration_bytes": b"x" * (1_048_576 + 1)}, ValueError),
        ({"scientific_identity_bytes": b""}, ValueError),
        ({"scientific_identity_bytes": b"x" * (1_048_576 + 1)}, ValueError),
        ({"software_commit": _HostileString("0" * 40)}, TypeError),
        ({"software_commit": "A" * 40}, ValueError),
        ({"software_commit": "0" * 39}, ValueError),
    ],
)
def test_binding_rejects_hostile_inputs(overrides, error) -> None:
    with pytest.raises(error):
        _binding(**overrides)


@pytest.mark.parametrize("bad", [True, 769.0, "769", object()])
def test_schedule_rejects_hostile_types(bad) -> None:
    with pytest.raises(TypeError):
        build_one_cell_checkpoint_schedule(terminal_event_count=bad)


def test_binding_rejects_protocol_product_overflow() -> None:
    with pytest.raises(ValueError):
        _binding(width=1024, terminal_event_count=1 << 63)


def test_flag_is_latched_and_signal_compatible() -> None:
    flag = OneCellInterruptionFlag()
    assert flag.requested is False
    flag.request()
    flag.request()
    flag(10, object())
    assert flag.requested is True
    with pytest.raises(AttributeError):
        flag.requested = False
    for method_name in ("request", "__call__"):
        tree = ast.parse(textwrap.dedent(inspect.getsource(getattr(OneCellInterruptionFlag, method_name))))
        assert not any(isinstance(node, (ast.Call, ast.Raise, ast.With, ast.Try)) for node in ast.walk(tree))
        stores = [node for node in ast.walk(tree) if isinstance(node, (ast.Assign, ast.AnnAssign))]
        assert len(stores) == 1


def test_pre_requested_flag_commits_once_and_never_runs_numerics(tmp_path) -> None:
    task = _new_task(tmp_path)
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    first = _advance(task, binding, flag)
    inode = (task / "task.lock").stat().st_ino
    names = sorted(path.name for path in task.iterdir())
    second = _advance(task, binding, flag)
    assert first.disposition == second.disposition == "requeue-required"
    assert first.trajectory.event_count == second.trajectory.event_count == 0
    assert first.generation == second.generation == 1
    assert sorted(path.name for path in task.iterdir()) == names
    assert (task / "task.lock").stat().st_ino == inode


def test_terminal_generation_matches_independent_scalar_oracle(terminal_task) -> None:
    task, binding = terminal_task
    result = _advance(task, binding)
    assert result.disposition == "terminal"
    assert result.generation == 2
    assert result.checkpoint_count == 512
    assert result.snapshot_count == 16
    assert result.used_fallback is False
    _assert_matches_oracle(result)


def test_request_identity_and_member_inventory_are_exact(terminal_task) -> None:
    task, binding = terminal_task
    manifest = _assert_strict_canonical_json(_manifest_path(task, 2))
    assert set(manifest) == {
        "current_event_count",
        "generation",
        "members",
        "next_event_ordinal",
        "profile",
        "request_identity",
        "status",
    }
    assert manifest["profile"] == "tetris-ballistic/pre-one-cell-checkpoint@1"
    assert manifest["status"] == "checkpoint"
    assert manifest["current_event_count"] == manifest["next_event_ordinal"] == 769
    assert manifest["generation"] == 2
    request = manifest["request_identity"]
    assert set(request) == {"profile", "record", "sha256"}
    assert request["profile"] == "tetris-pre-one-cell-checkpoint-request@1"
    assert request["sha256"] == _sha256(_canonical_json(request["record"]))
    record = request["record"]
    assert set(record) == {
        "boundary_law",
        "checkpoint_vector_sha256",
        "configuration_sha256",
        "configuration_size_bytes",
        "counter_fields",
        "coupling_group",
        "rng_algorithm",
        "root_seed_decimal",
        "scientific_identity_sha256",
        "scientific_identity_size_bytes",
        "snapshot_vector_sha256",
        "software_commit",
        "stream_order",
        "terminal_event_count",
        "threshold_schedule",
        "width",
    }
    assert record["root_seed_decimal"] == str(binding.root_seed)
    assert record["boundary_law"] == binding.boundary_law.value
    assert tuple(record["threshold_schedule"]) == binding.threshold_schedule
    assert record["rng_algorithm"] == "semantic-philox4x64-10-v1"
    assert record["coupling_group"] == _GROUP
    assert record["stream_order"] == ["launch", "contact"]
    assert record["counter_fields"] == [
        "event-ordinal-zero-based",
        "rejection-ordinal",
        "zero",
        "zero",
    ]
    assert record["configuration_sha256"] == _sha256(binding.configuration_bytes)
    assert record["scientific_identity_sha256"] == _sha256(binding.scientific_identity_bytes)
    assert set(manifest["members"]) == {"arrays", "configuration", "scientific_identity", "state"}
    expected_names = {
        "arrays": "checkpoint.00000000000000000002.arrays.u64le",
        "configuration": "checkpoint.00000000000000000002.configuration.bin",
        "scientific_identity": "checkpoint.00000000000000000002.scientific-identity.bin",
        "state": "checkpoint.00000000000000000002.state.json",
    }
    for label, entry in manifest["members"].items():
        assert set(entry) == {"filename", "sha256", "size_bytes"}
        assert entry["filename"] == expected_names[label]
        member = task / entry["filename"]
        assert member.is_file()
        assert member.stat().st_nlink == 1
        assert member.stat().st_mode & 0o777 == 0o600
        payload = member.read_bytes()
        assert len(payload) == entry["size_bytes"]
        assert _sha256(payload) == entry["sha256"]
        assert label in {"arrays", "configuration", "scientific_identity", "state"}
    assert (task / expected_names["configuration"]).read_bytes() == binding.configuration_bytes
    assert (task / expected_names["scientific_identity"]).read_bytes() == binding.scientific_identity_bytes
    state = _assert_strict_canonical_json(task / expected_names["state"])
    assert set(state) == {
        "arm_count",
        "checkpoint_count",
        "current_event_count",
        "generation",
        "next_event_ordinal",
        "profile",
        "seam_equality_applicable",
        "sections",
        "snapshot_count",
        "terminal_event_count",
        "width",
    }
    assert state["profile"] == "tetris-pre-one-cell-checkpoint-state@1"
    assert [section["name"] for section in state["sections"]] == [
        "current_heights",
        "current_rows",
        "current_histogram",
        "checkpoint_event_counts",
        "checkpoint_rows",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_heights",
    ]
    offset = 0
    for section in state["sections"]:
        assert set(section) == {"dtype", "name", "offset_words", "shape", "word_count"}
        assert section["dtype"] == "<u8"
        assert section["offset_words"] == offset
        product = 1
        for extent in section["shape"]:
            assert type(extent) is int and extent >= 0
            product *= extent
        assert section["word_count"] == product
        offset += product
    assert (task / expected_names["arrays"]).stat().st_size == 8 * offset


@pytest.mark.parametrize("substitution", ["bool", "float"])
def test_canonical_request_identity_numeric_type_substitution_is_fatal(terminal_task, substitution) -> None:
    task, binding = terminal_task
    manifest_path = _manifest_path(task, 2)
    manifest = _load_json(manifest_path)
    record = manifest["request_identity"]["record"]
    if substitution == "bool":
        assert record["threshold_schedule"][1] == 1
        record["threshold_schedule"][1] = True
    else:
        assert record["terminal_event_count"] == binding.terminal_event_count
        record["terminal_event_count"] = float(binding.terminal_event_count)
    manifest["request_identity"]["sha256"] = _sha256(_canonical_json(record))
    _write_canonical(manifest_path, manifest)

    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


def _assert_persisted_matches_oracle(*, task: Path, binding: OneCellCheckpointBinding, generation: int) -> None:
    state, sections = _decode_generation(task, generation)
    assert state["checkpoint_count"] == 512
    assert state["snapshot_count"] == 16
    assert tuple(sections) == (
        "current_heights",
        "current_rows",
        "current_histogram",
        "checkpoint_event_counts",
        "checkpoint_rows",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_heights",
    )
    checkpoint_shape, checkpoint_words = sections["checkpoint_event_counts"]
    assert checkpoint_shape == (512,)
    expected_schedule = _oracle_schedule(binding.terminal_event_count)
    assert checkpoint_words == expected_schedule[0]
    row_shape, row_words = sections["checkpoint_rows"]
    assert row_shape == (512, len(binding.threshold_schedule), 33)
    snapshot_indices = sections["snapshot_checkpoint_indices"][1]
    snapshot_events = sections["snapshot_event_counts"][1]
    assert snapshot_indices == expected_schedule[1]
    assert snapshot_events == expected_schedule[2]
    snapshot_shape, snapshot_words = sections["snapshot_heights"]
    assert snapshot_shape == (16, len(binding.threshold_schedule), binding.width)

    replay_cache = _oracle_prefixes(
        root_seed=binding.root_seed,
        law_id=binding.boundary_law.value,
        width=binding.width,
        schedule=binding.threshold_schedule,
        stops=checkpoint_words,
    )
    row_offset = 0
    for event in checkpoint_words:
        arms = replay_cache[event]
        for arm in arms:
            assert row_words[row_offset : row_offset + 33] == _oracle_row(arm)
            row_offset += 33
    snapshot_offset = 0
    for event in snapshot_events:
        for arm in replay_cache[event]:
            expected_heights = arm["heights"]
            assert snapshot_words[snapshot_offset : snapshot_offset + binding.width] == expected_heights
            snapshot_offset += binding.width
    current_heights = sections["current_heights"][1]
    current_rows = sections["current_rows"][1]
    terminal_arms = replay_cache[binding.terminal_event_count]
    assert current_heights == tuple(value for arm in terminal_arms for value in arm["heights"])
    assert current_rows == tuple(value for arm in terminal_arms for value in _oracle_row(arm))


@pytest.mark.slow
def test_every_persisted_row_and_snapshot_matches_independent_scalar_replay(terminal_task) -> None:
    task, binding = terminal_task
    _assert_persisted_matches_oracle(task=task, binding=binding, generation=2)


@pytest.mark.slow
def test_all_laws_and_schedules_match_independent_scalar_oracle(tmp_path) -> None:
    for law_index, law in enumerate(_LAWS):
        for schedule_index, schedule in enumerate(_SCHEDULES):
            task = _new_task(tmp_path, f"law-{law_index}-schedule-{schedule_index}")
            binding = _binding(
                root_seed=100 + 11 * law_index + schedule_index,
                boundary_law=law,
                width=3 + (schedule_index % 2),
                threshold_schedule=schedule,
            )
            result = _advance(task, binding)
            assert result.disposition == "terminal"
            _assert_matches_oracle(result)
            _assert_persisted_matches_oracle(task=task, binding=binding, generation=result.generation)


def test_matching_checksum_corruption_falls_back_and_heals(terminal_task) -> None:
    task, binding = terminal_task
    arrays = _member_path(task, 2, "arrays.u64le")
    payload = bytearray(arrays.read_bytes())
    payload[len(payload) // 2] ^= 1
    arrays.write_bytes(payload)
    arrays.chmod(0o600)
    result = _advance(task, binding)
    assert result.disposition == "terminal"
    assert result.generation == 3
    assert result.used_fallback is True
    assert sorted(path.name for path in task.glob("checkpoint.*.manifest.json")) == [
        "checkpoint.00000000000000000001.manifest.json",
        "checkpoint.00000000000000000003.manifest.json",
    ]
    _assert_matches_oracle(result)


def test_recomputed_checksum_cannot_bless_corrupt_scientific_state(terminal_task) -> None:
    task, binding = terminal_task
    state = _load_json(_member_path(task, 2, "state.json"))
    current_rows = next(section for section in state["sections"] if section["name"] == "current_rows")
    byte_offset = 8 * current_rows["offset_words"]
    arrays = bytearray(_member_path(task, 2, "arrays.u64le").read_bytes())
    word = int.from_bytes(arrays[byte_offset : byte_offset + 8], "little")
    arrays[byte_offset : byte_offset + 8] = (word + 1).to_bytes(8, "little")
    _replace_member(task, 2, "arrays", bytes(arrays))
    result = _advance(task, binding)
    assert result.used_fallback is True
    assert result.generation == 3
    _assert_matches_oracle(result)


@pytest.mark.parametrize(
    "section_name,word_within_section",
    [
        ("current_heights", 0),
        ("current_rows", 0),
        ("current_histogram", 2),
        ("checkpoint_event_counts", 0),
        ("checkpoint_rows", 0),
        ("snapshot_checkpoint_indices", 0),
        ("snapshot_event_counts", 0),
        ("snapshot_heights", 0),
    ],
)
def test_recomputed_checksum_corruption_in_every_state_section_falls_back(
    terminal_task, section_name, word_within_section
) -> None:
    task, binding = terminal_task
    state = _load_json(_member_path(task, 2, "state.json"))
    section = next(value for value in state["sections"] if value["name"] == section_name)
    word_index = section["offset_words"] + word_within_section
    byte_offset = 8 * word_index
    arrays = bytearray(_member_path(task, 2, "arrays.u64le").read_bytes())
    original = int.from_bytes(arrays[byte_offset : byte_offset + 8], "little")
    arrays[byte_offset : byte_offset + 8] = ((original + 1) & _U64_MASK).to_bytes(8, "little")
    _replace_member(task, 2, "arrays", bytes(arrays))
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.disposition == "requeue-required"
    assert result.generation == 1
    assert result.used_fallback is True


@pytest.mark.parametrize("corruption", ["negative_roughness", "above_geometric_bound"])
def test_rechecksummed_non_snapshot_square_moment_corruption_falls_back(terminal_task, corruption) -> None:
    task, binding = terminal_task
    state, sections = _decode_generation(task, 2)
    checkpoint_index = next(
        index for index in range(state["checkpoint_count"]) if index not in sections["snapshot_checkpoint_indices"][1]
    )
    arm_index = 0
    arm_count = len(binding.threshold_schedule)
    row_start = (checkpoint_index * arm_count + arm_index) * 33
    height_sum = sections["checkpoint_rows"][1][row_start]
    event_count = sections["checkpoint_event_counts"][1][checkpoint_index]
    if corruption == "negative_roughness":
        square = (height_sum * height_sum - 1) // binding.width
        assert binding.width * square < height_sum * height_sum
    else:
        square = binding.width * event_count * event_count + 1
        assert square > binding.width * event_count * event_count

    section = next(value for value in state["sections"] if value["name"] == "checkpoint_rows")
    arrays = bytearray(_member_path(task, 2, "arrays.u64le").read_bytes())
    for row_offset, word in ((1, square >> 64), (2, square & _U64_MASK)):
        byte_offset = 8 * (section["offset_words"] + row_start + row_offset)
        arrays[byte_offset : byte_offset + 8] = word.to_bytes(8, "little")
    _replace_member(task, 2, "arrays", bytes(arrays))

    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.disposition == "requeue-required"
    assert result.generation == 1
    assert result.used_fallback is True


@pytest.mark.parametrize(
    "mutation",
    [
        "big_endian_dtype",
        "signed_dtype",
        "float_dtype",
        "object_dtype",
        "wrong_shape",
        "wrong_offset",
        "wrong_word_count",
        "wrong_section_name",
        "boolean_count",
        "unknown_state_key",
    ],
)
def test_matching_state_layout_corruption_falls_back_before_allocation(terminal_task, mutation) -> None:
    task, binding = terminal_task
    state_path = _member_path(task, 2, "state.json")
    state = _load_json(state_path)
    section = state["sections"][0]
    if mutation == "big_endian_dtype":
        section["dtype"] = ">u8"
    elif mutation == "signed_dtype":
        section["dtype"] = "<i8"
    elif mutation == "float_dtype":
        section["dtype"] = "<f8"
    elif mutation == "object_dtype":
        section["dtype"] = "|O"
    elif mutation == "wrong_shape":
        section["shape"] = [1 << 62, 1 << 62]
    elif mutation == "wrong_offset":
        section["offset_words"] = 1
    elif mutation == "wrong_word_count":
        section["word_count"] += 1
    elif mutation == "wrong_section_name":
        section["name"] = "event_tape"
    elif mutation == "boolean_count":
        state["checkpoint_count"] = True
    else:
        state["unexpected"] = 1
    _replace_member(task, 2, "state", _canonical_json(state, newline=True))
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.disposition == "requeue-required"
    assert result.generation == 1
    assert result.trajectory.event_count == 0
    assert result.used_fallback is True


def test_invalid_state_layout_is_rejected_before_arrays_member_is_opened(terminal_task, monkeypatch) -> None:
    task, binding = terminal_task
    state = _load_json(_member_path(task, 2, "state.json"))
    state["sections"][0]["shape"] = [1 << 62, 1 << 62]
    _replace_member(task, 2, "state", _canonical_json(state, newline=True))
    target_arrays = _member_path(task, 2, "arrays.u64le").name
    opened: list[str] = []
    original_read_file = checkpoint_module._read_file

    def observe_reads(task_descriptor, name, **kwargs):
        opened.append(name)
        return original_read_file(task_descriptor, name, **kwargs)

    monkeypatch.setattr(checkpoint_module, "_read_file", observe_reads)
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)

    assert result.generation == 1
    assert result.used_fallback is True
    assert target_arrays not in opened
    assert _member_path(task, 1, "arrays.u64le").name in opened


@pytest.mark.parametrize("member", ["state", "arrays"])
def test_oversized_member_fails_before_decode_or_allocation(terminal_task, member) -> None:
    task, binding = terminal_task
    suffix = "state.json" if member == "state" else "arrays.u64le"
    target = _member_path(task, 2, suffix)
    ceiling = 1_048_576 if member == "state" else 64 * 1_048_576
    with target.open("wb") as handle:
        handle.truncate(ceiling + 1)
    target.chmod(0o600)
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.generation == 1
    assert result.used_fallback is True


def test_oversized_manifest_is_fatal_before_json_decode(terminal_task) -> None:
    task, binding = terminal_task
    manifest = _manifest_path(task, 2)
    with manifest.open("wb") as handle:
        handle.truncate(1_048_576 + 1)
    manifest.chmod(0o600)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_manifest_member_path_substitution_never_escapes_and_falls_back(terminal_task, tmp_path) -> None:
    task, binding = terminal_task
    outside = tmp_path / "outside-state.json"
    outside.write_bytes(b"preserve")
    manifest_path = _manifest_path(task, 2)
    manifest = _load_json(manifest_path)
    manifest["members"]["state"]["filename"] = "../outside-state.json"
    _write_canonical(manifest_path, manifest)
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.used_fallback is True
    assert result.generation == 1
    assert outside.read_bytes() == b"preserve"


def test_two_invalid_matching_generations_fail_without_restart(terminal_task) -> None:
    task, binding = terminal_task
    for generation in (1, 2):
        arrays = _member_path(task, generation, "arrays.u64le")
        payload = bytearray(arrays.read_bytes())
        payload[-1:] = bytes([payload[-1] ^ 1])
        arrays.write_bytes(payload)
        arrays.chmod(0o600)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


@pytest.mark.parametrize(
    "label,suffix",
    [
        ("configuration", "configuration.bin"),
        ("scientific_identity", "scientific-identity.bin"),
    ],
)
def test_opaque_byte_checksum_corruption_falls_back(terminal_task, label, suffix) -> None:
    task, binding = terminal_task
    member = _member_path(task, 2, suffix)
    payload = bytearray(member.read_bytes())
    payload[0] ^= 1
    member.write_bytes(payload)
    member.chmod(0o600)
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, binding, flag)
    assert result.generation == 1
    assert result.used_fallback is True


@pytest.mark.parametrize(
    "label,suffix",
    [
        ("configuration", "configuration.bin"),
        ("scientific_identity", "scientific-identity.bin"),
    ],
)
def test_rechecksummed_opaque_byte_identity_mismatch_is_fatal(terminal_task, label, suffix) -> None:
    task, binding = terminal_task
    member = _member_path(task, 2, suffix)
    payload = bytearray(member.read_bytes())
    payload[0] ^= 1
    _replace_member(task, 2, label, bytes(payload))
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


@pytest.mark.parametrize(
    "corrupt_label,contradictory_label",
    [
        ("configuration", "scientific_identity"),
        ("scientific_identity", "configuration"),
    ],
)
def test_opaque_checksum_corruption_cannot_mask_other_rechecksummed_contradiction(
    terminal_task, corrupt_label, contradictory_label
) -> None:
    task, binding = terminal_task
    suffixes = {
        "configuration": "configuration.bin",
        "scientific_identity": "scientific-identity.bin",
    }
    corrupt_member = _member_path(task, 2, suffixes[corrupt_label])
    corrupt_payload = bytearray(corrupt_member.read_bytes())
    corrupt_payload[0] ^= 1
    corrupt_member.write_bytes(corrupt_payload)
    corrupt_member.chmod(0o600)

    contradictory_member = _member_path(task, 2, suffixes[contradictory_label])
    contradictory_payload = bytearray(contradictory_member.read_bytes())
    contradictory_payload[0] ^= 1
    _replace_member(task, 2, contradictory_label, bytes(contradictory_payload))

    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


@pytest.mark.parametrize("contradictory_label", ["configuration", "scientific_identity"])
def test_malformed_arrays_record_cannot_mask_rechecksummed_opaque_contradiction(
    terminal_task, contradictory_label
) -> None:
    task, binding = terminal_task
    suffix = {
        "configuration": "configuration.bin",
        "scientific_identity": "scientific-identity.bin",
    }[contradictory_label]
    member = _member_path(task, 2, suffix)
    payload = bytearray(member.read_bytes())
    payload[0] ^= 1
    _replace_member(task, 2, contradictory_label, bytes(payload))
    manifest_path = _manifest_path(task, 2)
    manifest = _load_json(manifest_path)
    manifest["members"]["arrays"] = {"filename": _member_path(task, 2, "arrays.u64le").name}
    _write_canonical(manifest_path, manifest)

    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


def test_well_formed_newest_identity_mismatch_is_fatal_not_fallback(terminal_task) -> None:
    task, binding = terminal_task
    manifest_path = _manifest_path(task, 2)
    manifest = _load_json(manifest_path)
    record = manifest["request_identity"]["record"]
    record["software_commit"] = "0" * 40
    manifest["request_identity"]["sha256"] = _sha256(_canonical_json(record))
    _write_canonical(manifest_path, manifest)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


@pytest.mark.parametrize("mutation", ["duplicate", "noncanonical", "truncated"])
def test_unreadable_or_noncanonical_newest_manifest_is_fatal(terminal_task, mutation) -> None:
    task, binding = terminal_task
    path = _manifest_path(task, 2)
    original = path.read_bytes()
    if mutation == "duplicate":
        path.write_bytes(b'{"status":"checkpoint",' + original[1:])
    elif mutation == "noncanonical":
        path.write_text(json.dumps(json.loads(original), indent=2) + "\n", encoding="utf-8")
    else:
        path.write_bytes(original[: len(original) // 2])
    path.chmod(0o600)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_deeply_nested_manifest_json_normalizes_recursion_failure(terminal_task) -> None:
    task, binding = terminal_task
    path = _manifest_path(task, 2)
    payload = b"[" * 2_000 + b"0" + b"]" * 2_000 + b"\n"
    assert len(payload) < 1_048_576
    path.write_bytes(payload)
    path.chmod(0o600)

    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


@pytest.mark.parametrize("position", ["below", "above"])
def test_matching_identity_manifest_ordinal_outside_terminal_domain_is_fatal(terminal_task, position) -> None:
    task, binding = terminal_task
    path = _manifest_path(task, 2)
    manifest = _load_json(path)
    ordinal = -1 if position == "below" else binding.terminal_event_count + 1
    manifest["current_event_count"] = ordinal
    manifest["next_event_ordinal"] = ordinal
    _write_canonical(path, manifest)

    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not _manifest_path(task, 3).exists()


def test_unknown_manifest_schema_is_fatal_not_fallback(terminal_task) -> None:
    task, binding = terminal_task
    path = _manifest_path(task, 2)
    manifest = _load_json(path)
    manifest["unexpected"] = 1
    _write_canonical(path, manifest)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_checkpoint_manifest_cannot_claim_completion(terminal_task) -> None:
    task, binding = terminal_task
    path = _manifest_path(task, 2)
    manifest = _load_json(path)
    manifest["status"] = "complete"
    _write_canonical(path, manifest)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert not (task / "final.manifest.json").exists()


def test_orphan_high_water_ordinal_is_never_reused(terminal_task) -> None:
    task, binding = terminal_task
    arrays = _member_path(task, 2, "arrays.u64le")
    payload = bytearray(arrays.read_bytes())
    payload[0] ^= 1
    arrays.write_bytes(payload)
    arrays.chmod(0o600)
    orphan = _member_path(task, 8, "arrays.u64le")
    orphan.write_bytes(b"")
    orphan.chmod(0o600)
    temporary = task / (".checkpoint.00000000000000000009.arrays.u64le.00000000000000000000000000000000.tmp")
    temporary.write_bytes(b"")
    temporary.chmod(0o600)
    result = _advance(task, binding)
    assert result.generation == 10
    assert result.used_fallback is True
    assert _manifest_path(task, 10).is_file()


def test_malformed_reserved_temporary_is_fatal(terminal_task) -> None:
    task, binding = terminal_task
    malformed = task / ".checkpoint.00000000000000000009.arrays.u64le.bad.tmp"
    malformed.write_bytes(b"")
    malformed.chmod(0o600)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_exact_final_temporary_is_safe_crash_debris(final_task) -> None:
    task, binding = final_task
    temporary = task / (".final.arrays.u64le." + "0" * 32 + ".tmp")
    temporary.write_bytes(b"partial")
    temporary.chmod(0o600)
    reused = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert reused.disposition == "reused"
    assert not temporary.exists()


@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_unsafe_managed_final_temporary_makes_first_publish_fail(terminal_task, tmp_path, kind) -> None:
    task, binding = terminal_task
    temporary = task / f".final.arrays.u64le.{'b' * 32}.tmp"
    if kind == "symlink":
        outside = tmp_path / "outside-final-temporary"
        outside.write_bytes(b"preserve")
        temporary.symlink_to(outside)
    else:
        os.mkfifo(temporary, mode=0o600)

    with pytest.raises(OneCellCheckpointValidationError):
        publish_one_cell_final(task_directory=str(task), binding=binding)
    assert temporary.exists() or temporary.is_symlink()
    if kind == "symlink":
        assert outside.read_bytes() == b"preserve"


def test_exact_target_and_managed_temporary_install_link_is_repaired_and_resumable(tmp_path) -> None:
    task = _new_task(tmp_path)
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    first = _advance(task, binding, flag)
    assert first.generation == 1

    target = _manifest_path(task, 1)
    temporary = task / f".{target.name}.{'a' * 32}.tmp"
    os.link(target, temporary)
    assert target.stat().st_ino == temporary.stat().st_ino
    assert target.stat().st_nlink == temporary.stat().st_nlink == 2

    resumed = _advance(task, binding)
    assert resumed.disposition == "terminal"
    assert resumed.generation == 2
    assert not temporary.exists()
    assert target.stat().st_nlink == 1


def test_manifest_install_failure_leaves_only_inert_debris_and_never_reuses_ordinal(tmp_path, monkeypatch) -> None:
    task = _new_task(tmp_path)
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    original = checkpoint_module._write_exclusive

    def fail_manifest(task_descriptor, target, payload):
        if target.endswith(".manifest.json"):
            raise OSError("injected manifest install failure")
        return original(task_descriptor, target, payload)

    with monkeypatch.context() as scoped:
        scoped.setattr(checkpoint_module, "_write_exclusive", fail_manifest)
        with pytest.raises(OneCellCheckpointValidationError):
            _advance(task, binding, flag)
    assert not _manifest_path(task, 1).exists()
    retry = _advance(task, binding, flag)
    assert retry.disposition == "requeue-required"
    assert retry.generation == 2
    assert _manifest_path(task, 2).is_file()


@pytest.mark.parametrize("failing_directory_fsync", [1, 2])
def test_directory_fsync_failure_preserves_recoverable_commit_boundary(
    tmp_path, monkeypatch, failing_directory_fsync
) -> None:
    task = _new_task(tmp_path)
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    original_fsync = checkpoint_module.os.fsync
    directory_calls = 0

    def fail_selected(descriptor):
        nonlocal directory_calls
        if stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directory_calls += 1
            if directory_calls == failing_directory_fsync:
                raise OSError("injected directory fsync failure")
        return original_fsync(descriptor)

    with monkeypatch.context() as scoped:
        scoped.setattr(checkpoint_module.os, "fsync", fail_selected)
        with pytest.raises(OneCellCheckpointValidationError):
            _advance(task, binding, flag)
    visible_candidate = _manifest_path(task, 1).exists()
    retry = _advance(task, binding, flag)
    assert retry.disposition == "requeue-required"
    assert retry.generation == (1 if visible_candidate else 2)


def test_discovery_repairs_three_valid_generations_after_post_commit_crash(terminal_task) -> None:
    task, binding = terminal_task
    _clone_generation(task, 2, 3)
    assert len(list(task.glob("checkpoint.*.manifest.json"))) == 3
    result = _advance(task, binding)
    assert result.disposition == "terminal"
    assert result.generation == 3
    assert sorted(path.name for path in task.glob("checkpoint.*.manifest.json")) == [
        "checkpoint.00000000000000000002.manifest.json",
        "checkpoint.00000000000000000003.manifest.json",
    ]


def test_pre_requested_three_generation_recovery_retains_newest_two_before_return(terminal_task) -> None:
    task, binding = terminal_task
    _clone_generation(task, 2, 3)
    flag = OneCellInterruptionFlag()
    flag.request()

    result = _advance(task, binding, flag)

    assert result.disposition == "requeue-required"
    assert result.generation == 3
    assert result.used_fallback is False
    assert sorted(path.name for path in task.glob("checkpoint.*.manifest.json")) == [
        "checkpoint.00000000000000000002.manifest.json",
        "checkpoint.00000000000000000003.manifest.json",
    ]
    assert not list(task.glob("checkpoint.00000000000000000001.*"))
    assert not _manifest_path(task, 4).exists()


def test_generation_ordinal_exhaustion_fails_before_execution(tmp_path) -> None:
    task = _new_task(tmp_path)
    orphan = _member_path(task, _U64_MASK, "arrays.u64le")
    orphan.write_bytes(b"")
    orphan.chmod(0o600)
    with pytest.raises(OverflowError):
        _advance(task, _binding())
    assert not list(task.glob("checkpoint.*.manifest.json"))


def test_final_manifest_is_the_only_completion_marker(terminal_task) -> None:
    task, binding = terminal_task
    assert not (task / "final.manifest.json").exists()
    terminal = _advance(task, binding)
    assert terminal.disposition == "terminal"
    complete = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert complete.disposition == "complete"
    assert complete.generation == 0
    assert complete.checkpoint_count == 512
    assert complete.snapshot_count == 16
    assert complete.manifest_path == str(task / "final.manifest.json")
    assert _load_json(task / "final.manifest.json")["status"] == "complete"
    assert _load_json(task / "final.state.json")["profile"] == "tetris-pre-one-cell-final-state@1"
    assert "generation" not in _load_json(task / "final.state.json")
    _assert_matches_oracle(complete)


def test_final_codec_inventory_is_closed_and_canonical(final_task) -> None:
    task, binding = final_task
    manifest = _assert_strict_canonical_json(task / "final.manifest.json")
    state = _assert_strict_canonical_json(task / "final.state.json")
    assert set(manifest) == {"members", "profile", "request_identity", "status"}
    assert manifest["profile"] == "tetris-ballistic/pre-one-cell-final@1"
    assert manifest["status"] == "complete"
    assert set(manifest["members"]) == {"arrays", "configuration", "scientific_identity", "state"}
    expected_names = {
        "arrays": "final.arrays.u64le",
        "configuration": "final.configuration.bin",
        "scientific_identity": "final.scientific-identity.bin",
        "state": "final.state.json",
    }
    for label, expected_name in expected_names.items():
        entry = manifest["members"][label]
        assert entry["filename"] == expected_name
        payload = (task / expected_name).read_bytes()
        assert entry["size_bytes"] == len(payload)
        assert entry["sha256"] == _sha256(payload)
    assert (task / "final.configuration.bin").read_bytes() == binding.configuration_bytes
    assert (task / "final.scientific-identity.bin").read_bytes() == binding.scientific_identity_bytes
    assert set(state) == {
        "arm_count",
        "checkpoint_count",
        "profile",
        "seam_equality_applicable",
        "sections",
        "snapshot_count",
        "terminal_event_count",
        "width",
    }
    assert state["profile"] == "tetris-pre-one-cell-final-state@1"
    assert state["checkpoint_count"] == 512
    assert state["snapshot_count"] == 16
    assert [section["name"] for section in state["sections"]] == [
        "checkpoint_event_counts",
        "checkpoint_rows",
        "snapshot_checkpoint_indices",
        "snapshot_event_counts",
        "snapshot_heights",
        "final_histogram",
    ]
    final_offset = 0
    for section in state["sections"]:
        assert set(section) == {"dtype", "name", "offset_words", "shape", "word_count"}
        assert section["dtype"] == "<u8"
        assert section["offset_words"] == final_offset
        product = 1
        for extent in section["shape"]:
            assert type(extent) is int and extent >= 0
            product *= extent
        assert section["word_count"] == product
        final_offset += product
    assert (task / "final.arrays.u64le").stat().st_size == 8 * final_offset


def test_final_reuse_is_independent_and_post_completion_advance_fails(final_task) -> None:
    task, binding = final_task
    before = {path.name: path.read_bytes() for path in task.glob("final.*")}
    reused = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert reused.disposition == "reused"
    assert reused.generation == 0
    assert reused.used_fallback is False
    assert {path.name: path.read_bytes() for path in task.glob("final.*")} == before
    _assert_matches_oracle(reused)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_payload_only_final_is_recovered_without_becoming_completion(final_task) -> None:
    task, binding = final_task
    expected = {path.name: path.read_bytes() for path in task.glob("final.*") if path.name != "final.manifest.json"}
    (task / "final.manifest.json").unlink()
    assert not (task / "final.manifest.json").exists()
    recovered = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert recovered.disposition == "complete"
    assert (task / "final.manifest.json").is_file()
    assert {
        path.name: path.read_bytes() for path in task.glob("final.*") if path.name != "final.manifest.json"
    } == expected


def test_mismatching_payload_only_final_is_rebuilt_never_adopted(final_task) -> None:
    task, binding = final_task
    expected_arrays = (task / "final.arrays.u64le").read_bytes()
    (task / "final.manifest.json").unlink()
    corrupt = bytearray(expected_arrays)
    corrupt[0] ^= 1
    (task / "final.arrays.u64le").write_bytes(corrupt)
    (task / "final.arrays.u64le").chmod(0o600)
    result = publish_one_cell_final(task_directory=str(task), binding=binding)
    assert result.disposition == "complete"
    assert (task / "final.arrays.u64le").read_bytes() == expected_arrays


def test_oversized_payload_only_final_is_rebuilt_without_reading_the_debris(terminal_task, monkeypatch) -> None:
    task, binding = terminal_task
    target_name = "final.arrays.u64le"
    target = task / target_name
    oversized_size = 64 * 1_048_576 + 1
    with target.open("wb") as handle:
        handle.truncate(oversized_size)
    target.chmod(0o600)
    original_read_file = checkpoint_module._read_file
    oversized_reads = 0

    def observe_reads(task_descriptor, name, **kwargs):
        nonlocal oversized_reads
        if name == target_name:
            held_size = os.stat(name, dir_fd=task_descriptor, follow_symlinks=False).st_size
            if held_size == oversized_size:
                oversized_reads += 1
        return original_read_file(task_descriptor, name, **kwargs)

    monkeypatch.setattr(checkpoint_module, "_read_file", observe_reads)
    result = publish_one_cell_final(task_directory=str(task), binding=binding)

    assert result.disposition == "complete"
    assert oversized_reads == 0
    assert 0 < target.stat().st_size < oversized_size
    assert (task / "final.manifest.json").is_file()


def test_nonregular_payload_only_final_is_fatal(final_task, tmp_path) -> None:
    task, binding = final_task
    (task / "final.manifest.json").unlink()
    state = task / "final.state.json"
    payload = state.read_bytes()
    state.unlink()
    outside = tmp_path / "outside-final-state"
    outside.write_bytes(payload)
    state.symlink_to(outside)
    with pytest.raises(OneCellCheckpointValidationError):
        publish_one_cell_final(task_directory=str(task), binding=binding)


def test_present_corrupt_final_manifest_is_fatal(final_task) -> None:
    task, binding = final_task
    manifest = task / "final.manifest.json"
    manifest.write_bytes(manifest.read_bytes()[:-3])
    with pytest.raises(OneCellCheckpointValidationError):
        publish_one_cell_final(task_directory=str(task), binding=binding)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_present_final_with_corrupt_member_never_falls_back(final_task) -> None:
    task, binding = final_task
    arrays = task / "final.arrays.u64le"
    payload = bytearray(arrays.read_bytes())
    payload[len(payload) // 2] ^= 1
    arrays.write_bytes(payload)
    arrays.chmod(0o600)
    with pytest.raises(OneCellCheckpointValidationError):
        publish_one_cell_final(task_directory=str(task), binding=binding)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)


def test_valid_final_refuses_every_different_binding(final_task) -> None:
    task, binding = final_task
    different = _binding(configuration_bytes=b"different-config\n")
    assert different != binding
    with pytest.raises(OneCellCheckpointValidationError):
        publish_one_cell_final(task_directory=str(task), binding=different)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, different)


def test_interrupted_and_uninterrupted_final_members_are_byte_identical(tmp_path, terminal_template) -> None:
    interrupted_template, binding = terminal_template
    interrupted = _copy_task(interrupted_template, tmp_path, "interrupted")
    direct = _new_task(tmp_path, "direct")
    direct_terminal = _advance(direct, binding)
    assert direct_terminal.generation == 1
    publish_one_cell_final(task_directory=str(interrupted), binding=binding)
    publish_one_cell_final(task_directory=str(direct), binding=binding)
    assert {path.name: path.read_bytes() for path in interrupted.glob("final.*")} == {
        path.name: path.read_bytes() for path in direct.glob("final.*")
    }


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_nonregular_or_linked_checkpoint_member_is_rejected(terminal_task, tmp_path, kind) -> None:
    task, binding = terminal_task
    target = _member_path(task, 2, "state.json")
    payload = target.read_bytes()
    target.unlink()
    outside = tmp_path / "outside"
    if kind == "symlink":
        outside.write_bytes(payload)
        target.symlink_to(outside)
    elif kind == "hardlink":
        outside.write_bytes(payload)
        outside.chmod(0o600)
        os.link(outside, target)
    else:
        if not hasattr(os, "mkfifo"):
            pytest.skip("FIFO creation is unavailable")
        os.mkfifo(target, mode=0o600)
        import subprocess
        import sys

        code = f"""
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_checkpoint import OneCellCheckpointBinding, OneCellInterruptionFlag, advance_one_cell_checkpoint_generation
b = OneCellCheckpointBinding(
    root_seed={binding.root_seed}, boundary_law=OneCellBoundaryLaw({binding.boundary_law.value!r}),
    width={binding.width}, threshold_schedule={binding.threshold_schedule!r},
    terminal_event_count={binding.terminal_event_count}, configuration_bytes={binding.configuration_bytes!r},
    scientific_identity_bytes={binding.scientific_identity_bytes!r}, software_commit={binding.software_commit!r},
)
f = OneCellInterruptionFlag(); f.request()
r = advance_one_cell_checkpoint_generation(task_directory={str(task)!r}, binding=b, interruption_flag=f)
assert r.generation == 1 and r.used_fallback
"""
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=_REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return
    flag = OneCellInterruptionFlag()
    flag.request()
    fallback = _advance(task, binding, flag)
    assert fallback.disposition == "requeue-required"
    assert fallback.generation == 1
    assert fallback.trajectory.event_count == 0
    assert fallback.used_fallback is True


def test_task_and_ancestor_symlinks_are_rejected(tmp_path) -> None:
    real = _new_task(tmp_path, "real")
    task_link = tmp_path / "task-link"
    task_link.symlink_to(real, target_is_directory=True)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task_link, _binding())
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    child = _new_task(real_parent)
    parent_link = tmp_path / "parent-link"
    parent_link.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(parent_link / child.name, _binding())


def test_task_lock_symlink_is_rejected_without_following(tmp_path) -> None:
    task = _new_task(tmp_path)
    outside = tmp_path / "outside-lock"
    outside.write_bytes(b"preserve")
    (task / "task.lock").symlink_to(outside)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, _binding())
    assert outside.read_bytes() == b"preserve"


def test_fresh_lock_ignores_restrictive_umask_but_existing_wrong_mode_is_not_repaired(tmp_path) -> None:
    binding = _binding()
    flag = OneCellInterruptionFlag()
    flag.request()
    fresh = _new_task(tmp_path, "fresh")
    previous_umask = os.umask(0o777)
    try:
        result = _advance(fresh, binding, flag)
    finally:
        os.umask(previous_umask)
    assert result.generation == 1
    assert stat.S_IMODE((fresh / "task.lock").stat().st_mode) == 0o600

    existing = _new_task(tmp_path, "existing")
    wrong_mode_lock = existing / "task.lock"
    wrong_mode_lock.write_bytes(b"")
    wrong_mode_lock.chmod(0o640)
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(existing, binding, flag)
    assert stat.S_IMODE(wrong_mode_lock.stat().st_mode) == 0o640
    assert not list(existing.glob("checkpoint.*"))


def test_held_directory_descriptor_defeats_path_replacement(tmp_path, monkeypatch) -> None:
    task = _new_task(tmp_path)
    relocated = tmp_path / "relocated-task"
    original_publish = checkpoint_module._publish_payload_bundle
    replaced = False

    def replace_path_then_publish(task_descriptor, **kwargs):
        nonlocal replaced
        if not replaced:
            task.rename(relocated)
            task.mkdir(mode=0o700)
            (task / "attacker-marker").write_bytes(b"preserve")
            replaced = True
        return original_publish(task_descriptor, **kwargs)

    monkeypatch.setattr(checkpoint_module, "_publish_payload_bundle", replace_path_then_publish)
    flag = OneCellInterruptionFlag()
    flag.request()
    result = _advance(task, _binding(), flag)
    assert result.disposition == "requeue-required"
    assert replaced is True
    assert (task / "attacker-marker").read_bytes() == b"preserve"
    assert not list(task.glob("checkpoint.*"))
    assert _manifest_path(relocated, 1).is_file()


@pytest.mark.slow
def test_multiprocess_writer_blocks_on_the_persistent_lock_inode(terminal_task) -> None:
    import subprocess
    import sys
    import time
    from fcntl import LOCK_EX, LOCK_UN, flock

    task, binding = terminal_task
    lock_path = task / "task.lock"
    inode = lock_path.stat().st_ino
    descriptor = os.open(lock_path, os.O_RDWR)
    flock(descriptor, LOCK_EX)
    code = f"""
from tetris_ballistic.engine.one_cell_boundary import OneCellBoundaryLaw
from tetris_ballistic.engine.one_cell_checkpoint import OneCellCheckpointBinding, advance_one_cell_checkpoint_generation
b = OneCellCheckpointBinding(
    root_seed={binding.root_seed},
    boundary_law=OneCellBoundaryLaw({binding.boundary_law.value!r}),
    width={binding.width},
    threshold_schedule={binding.threshold_schedule!r},
    terminal_event_count={binding.terminal_event_count},
    configuration_bytes={binding.configuration_bytes!r},
    scientific_identity_bytes={binding.scientific_identity_bytes!r},
    software_commit={binding.software_commit!r},
)
print("ready", flush=True)
r = advance_one_cell_checkpoint_generation(task_directory={str(task)!r}, binding=b)
assert r.disposition == "terminal"
"""
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "ready"
        time.sleep(0.25)
        assert process.poll() is None
        assert lock_path.stat().st_ino == inode
        flock(descriptor, LOCK_UN)
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, (stdout, stderr)
    finally:
        try:
            flock(descriptor, LOCK_UN)
        finally:
            os.close(descriptor)
        if process.poll() is None:
            process.kill()
            process.communicate()
    assert lock_path.stat().st_ino == inode


@pytest.mark.parametrize("path_form", ["relative", "trailing", "dotdot"])
def test_task_path_must_be_absolute_and_lexically_normal(tmp_path, path_form) -> None:
    task = _new_task(tmp_path)
    if path_form == "relative":
        value = task.name
    elif path_form == "trailing":
        value = f"{task}/"
    else:
        value = f"{task.parent}/unused/../{task.name}"
    with pytest.raises(ValueError):
        advance_one_cell_checkpoint_generation(task_directory=value, binding=_binding())


def test_task_path_rejects_non_string_and_string_subclass(tmp_path) -> None:
    task = _new_task(tmp_path)
    for value in (task, _HostileString(str(task)), True):
        with pytest.raises(TypeError):
            advance_one_cell_checkpoint_generation(task_directory=value, binding=_binding())


@pytest.mark.parametrize(
    "character",
    [
        pytest.param("\x7f", id="del"),
        pytest.param("\x80", id="c1-control"),
        pytest.param("\ud800", id="surrogate"),
    ],
)
def test_task_path_rejects_hostile_code_points_before_filesystem_open(tmp_path, monkeypatch, character) -> None:
    binding = _binding()
    opened = False

    def forbidden_open(_path):
        nonlocal opened
        opened = True
        raise AssertionError("filesystem open must follow lexical validation")

    monkeypatch.setattr(checkpoint_module, "_open_task_directory", forbidden_open)
    value = f"{tmp_path}/hostile-{character}-component"
    with pytest.raises(ValueError):
        advance_one_cell_checkpoint_generation(task_directory=value, binding=binding)
    assert opened is False


def test_unexpected_inventory_and_wrong_mode_fail_closed(terminal_task) -> None:
    task, binding = terminal_task
    unexpected = task / "unrelated.txt"
    unexpected.write_bytes(b"preserve")
    with pytest.raises(OneCellCheckpointValidationError):
        _advance(task, binding)
    assert unexpected.read_bytes() == b"preserve"
    unexpected.unlink()
    state = _member_path(task, 2, "state.json")
    state.chmod(0o644)
    flag = OneCellInterruptionFlag()
    flag.request()
    fallback = _advance(task, binding, flag)
    assert fallback.generation == 1
    assert fallback.used_fallback is True


def test_private_authority_rebinding_fails_before_filesystem_mutation(tmp_path, monkeypatch) -> None:
    task = _new_task(tmp_path)
    binding = _binding()
    monkeypatch.setattr(checkpoint_module, "_CERTIFIED_START_TRAJECTORY", object())
    with pytest.raises(AssertionError):
        _advance(task, binding)
    assert not list(task.iterdir())


def test_module_has_no_forbidden_dependencies_or_root_exports() -> None:
    tree = ast.parse(Path(checkpoint_module.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden = {
        "argparse",
        "joblib",
        "pickle",
        "subprocess",
        "yaml",
        "tetris_ballistic.run_artifacts",
    }
    assert not {name for name in imported if name in forbidden or name.startswith("slurm")}
    for name in _PUBLIC_API:
        assert not hasattr(tetris_ballistic, name)
        assert not hasattr(reference_engine, name)
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert not identifiers & {"Popen", "sbatch", "scontrol", "run_artifacts", "joblib", "pickle"}


def test_roots_import_without_hpc_and_explicit_checkpoint_import_is_clear() -> None:
    import subprocess
    import sys

    code = r"""
import importlib
import sys

sys.modules["numba"] = None
import tetris_ballistic
import tetris_ballistic.engine
assert "tetris_ballistic.engine.one_cell_checkpoint" not in sys.modules
try:
    importlib.import_module("tetris_ballistic.engine.one_cell_checkpoint")
except ImportError as error:
    message = str(error)
    assert "tetris_ballistic.engine.one_cell_checkpoint" in message
    assert "tetris_ballistic[hpc]" in message
else:
    raise AssertionError("explicit checkpoint module imported without Numba")
"""
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_only_allowlisted_slice_paths_are_new_or_modified() -> None:
    # This local-history gate is skipped in source archives and shallow wheels;
    # package membership is certified separately by the release gate.
    if not (_REPO_ROOT / ".git").is_dir():
        pytest.skip("Git history is unavailable")
    import subprocess

    parent_check = subprocess.run(
        ["git", "cat-file", "-e", f"{_SOFTWARE_PARENT}^{{commit}}"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if parent_check.returncode != 0:
        pytest.skip("the frozen software parent is unavailable in this shallow checkout")

    result = subprocess.run(
        ["git", "diff", "--name-only", _SOFTWARE_PARENT, "--"],
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
    changed = {line for line in result.stdout.splitlines() if line}
    changed.update(
        line
        for line in untracked_result.stdout.splitlines()
        if line and not line.startswith((".omx/", ".pi-subagents/"))
    )
    assert changed <= {
        "tetris_ballistic/engine/one_cell_checkpoint.py",
        "tests/test_one_cell_checkpoint.py",
        "docs/PRE-ONE-CELL-CHECKPOINT-VECTORS.md",
        "docs/API-SPEC.md",
        "CHANGELOG.md",
    }
