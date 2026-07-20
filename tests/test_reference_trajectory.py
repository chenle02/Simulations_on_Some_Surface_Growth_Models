"""S2 exit certificate for the bounded reference trajectory surface."""

from __future__ import annotations

import ast
import hashlib
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

import tetris_ballistic
import tetris_ballistic.engine as engine_package
import tetris_ballistic.engine.reference_trajectory as trajectory_module
from tetris_ballistic.engine.accumulation import accumulate_event, start_event_accumulator
from tetris_ballistic.engine.binding import ReferenceEventPlacement
from tetris_ballistic.engine.event import (
    ConditionalWeightedLaw,
    TetrominoEventLaw,
    TetrominoEventSelection,
    select_event,
)
from tetris_ballistic.engine.reference import place_one
from tetris_ballistic.engine.reference_trajectory import (
    ReferenceCheckpoint,
    ReferenceTrajectory,
    ReferenceTrajectoryConfig,
    advance_reference_trajectory,
    build_reference_checkpoint_schedule,
    canonical_json_bytes,
    reconstruct_reference_checkpoint,
    reconstruct_reference_checkpoints,
    start_reference_trajectory,
)
from tetris_ballistic.engine.selection import (
    DeclaredStreamSet,
    ExactWeightedLaw,
    UniformIntegerLaw,
    select_uniform,
    select_weighted,
)
from tetris_ballistic.engine.state import SparseAggregate
from tetris_ballistic.models import FAMILY_ORIENTATION_IDS, GEOMETRY_BY_ID, ContactKind

_FAMILIES = ("i", "lj", "o", "sz", "t")
_CONTACTS = ("supported-v1", "edge-first-contact-v1")
_SOFTWARE_COMMIT = "e4434788f75c8090ebb042e6d413e7f730a3a7e9"
_HORIZONTAL = {
    "i": (3, 1),
    "lj": (3, 3, 1, 1, 3, 1, 1, 3),
    "o": (1,),
    "sz": (3, 1, 3, 1),
    "t": (3, 1, 3, 1),
}


def _law(
    width: int,
    *,
    morphology: int = 0,
    horizontal: int = 0,
    contact: int = 0,
) -> TetrominoEventLaw:
    family_counts = (1, 0, 0, 0, 0) if morphology == 0 else (1, 0, 0, 0, 1)
    orientation_laws = tuple(
        ExactWeightedLaw(
            orientation_ids,
            _HORIZONTAL[family] if horizontal else (1,) * len(orientation_ids),
        )
        for family, orientation_ids in FAMILY_ORIENTATION_IDS.items()
    )
    contact_counts = (1, 0) if contact == 0 else (0, 1)
    return TetrominoEventLaw(
        family_law=ExactWeightedLaw(_FAMILIES, family_counts),
        orientation_laws=ConditionalWeightedLaw(_FAMILIES, orientation_laws),
        launch_law=UniformIntegerLaw(width),
        contact_law=ExactWeightedLaw(_CONTACTS, contact_counts),
    )


def _config(
    *,
    width: int = 5,
    root_seed: int = 0,
    morphology: int = 1,
    horizontal: int = 1,
    contact: int = 1,
) -> ReferenceTrajectoryConfig:
    schedule = build_reference_checkpoint_schedule(terminal_event_count=769)
    return ReferenceTrajectoryConfig(
        model_law_id=f"test-law-w{width}-m{morphology}-o{horizontal}-c{contact}",
        plan_id="s2-reference-closure-test@1",
        software_commit=_SOFTWARE_COMMIT,
        root_seed=root_seed,
        coupling_group_id="s2-reference-test",
        law=_law(width, morphology=morphology, horizontal=horizontal, contact=contact),
        width=width,
        terminal_event_count=769,
        checkpoint_schedule=schedule,
    )


def _manual_prefix(config: ReferenceTrajectoryConfig, stop: int):
    """Independent orchestration from lower certified selection/placement units."""

    accumulator = start_event_accumulator(
        empty_state=SparseAggregate.empty(config.width),
        root_seed=config.root_seed,
        coupling_group_id=config.coupling_group_id,
        law=config.law,
    )
    streams = DeclaredStreamSet(("family", "orientation", "launch", "contact"))
    while accumulator.event_count < stop:
        address = {
            "root_seed": config.root_seed,
            "coupling_group_id": config.coupling_group_id,
            "event_ordinal": accumulator.event_count,
            "declared_streams": streams,
        }
        family = select_weighted(
            **address,
            stream_name="family",
            law=config.law.family_law,
        )
        orientation = select_weighted(
            **address,
            stream_name="orientation",
            law=config.law.orientation_laws.law_for(family.outcome_id),
        )
        launch = select_uniform(
            **address,
            stream_name="launch",
            law=config.law.launch_law,
        )
        contact = select_weighted(
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
        placement = place_one(
            accumulator.current_state,
            GEOMETRY_BY_ID[selection.geometry_id],
            selection.launch_x,
            ContactKind(selection.contact_id),
        )
        event = ReferenceEventPlacement(selection=selection, placement=placement)
        accumulator = accumulate_event(accumulator=accumulator, event=event)
    return accumulator


def test_public_surface_is_explicit_only_and_has_no_later_route_imports() -> None:
    assert trajectory_module.__all__ == [
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
    for module in (tetris_ballistic, engine_package):
        for name in trajectory_module.__all__:
            assert not hasattr(module, name)
    tree = ast.parse(Path(trajectory_module.__file__).read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported.update(
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert not any(fragment in name for name in imported for fragment in ("scheduler", "subprocess", "simulation"))
    assert not any(name in trajectory_module.__dict__ for name in ("Path", "open", "SimulationConfig"))


def test_pre_compatible_schedule_is_exact_strict_and_pinned() -> None:
    schedule = build_reference_checkpoint_schedule(terminal_event_count=769)
    assert len(schedule.event_ordinals) == 512
    assert schedule.event_ordinals[:5] == (1, 2, 3, 4, 5)
    assert schedule.event_ordinals[383:386] == (384, 385, 388)
    assert schedule.event_ordinals[-1] == 769
    assert all(left < right for left, right in zip(schedule.event_ordinals, schedule.event_ordinals[1:]))
    assert schedule.vector_sha256 == "47b85984ab7903f48a0e06437c3f3c8a297b82db683287bc1e515d624933aeaa"
    with pytest.raises(ValueError, match="at least 769"):
        build_reference_checkpoint_schedule(terminal_event_count=768)


def test_canonical_json_profile_is_exact_integer_only() -> None:
    assert canonical_json_bytes({"z": [2, 1], "a": "é"}) == b'{"a":"\xc3\xa9","z":[2,1]}\n'
    for forbidden in (None, True, False, 1.0, {"nested": [0, None]}):
        with pytest.raises(TypeError, match="boolean|float|non-canonical"):
            canonical_json_bytes(forbidden)


def test_typed_config_bounds_and_identity_fail_before_trajectory_start(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config()
    with pytest.raises(ValueError, match="launch upper bound"):
        replace(config, width=6)
    with pytest.raises(ValueError, match="checkpoint schedule horizon"):
        replace(config, terminal_event_count=770)
    with pytest.raises(ValueError, match="rng_algorithm"):
        replace(config, rng_algorithm="wrong")
    with pytest.raises(ValueError, match="Git object"):
        replace(config, software_commit="0" * 39)
    with pytest.raises(ValueError, match="width must be at least 3|launch upper bound"):
        replace(config, width=2)

    def forbidden_selection(**_kwargs: object) -> object:
        pytest.fail("invalid stop reached event selection")

    trajectory = start_reference_trajectory(config=config)
    monkeypatch.setattr(trajectory_module, "select_event", forbidden_selection)
    with pytest.raises(ValueError, match="between current and terminal"):
        advance_reference_trajectory(trajectory=trajectory, stop_event_ordinal=770)


def test_driver_matches_independent_composition_and_chunk_routing() -> None:
    config = _config(root_seed=17)
    uninterrupted = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config), stop_event_ordinal=12
    )
    chunked = start_reference_trajectory(config=config)
    for stop in (1, 1, 4, 9, 12):
        chunked = advance_reference_trajectory(trajectory=chunked, stop_event_ordinal=stop)
    assert chunked == uninterrupted
    assert uninterrupted.accumulator == _manual_prefix(config, 12)
    assert tuple(item.event_ordinal for item in uninterrupted.checkpoints) == tuple(range(1, 13))
    assert uninterrupted.final_manifest is None


def test_golden_rng_mapping_and_checkpoint_bytes_are_pinned() -> None:
    config = _config(width=5, root_seed=0, morphology=1, horizontal=1, contact=1)
    first = select_event(
        root_seed=config.root_seed,
        coupling_group_id=config.coupling_group_id,
        event_ordinal=0,
        law=config.law,
    )
    assert (
        first.family_id,
        first.geometry_id,
        first.launch_x,
        first.contact_id,
        first.family.draw.accepted_rejection_ordinal,
        first.orientation.draw.accepted_rejection_ordinal,
        first.launch.draw.accepted_rejection_ordinal,
        first.contact.draw.accepted_rejection_ordinal,
    ) == ("t", "tetromino.t.00", 4, "edge-first-contact-v1", 0, 0, 0, 0)
    declared = DeclaredStreamSet(("family", "orientation", "launch", "contact"))
    unequal = tuple(
        select_uniform(
            root_seed=0,
            coupling_group_id="paired-main",
            event_ordinal=1,
            declared_streams=declared,
            stream_name="launch",
            law=UniformIntegerLaw(bound),
        )
        for bound in (2, (1 << 63) + 1)
    )
    assert tuple((item.value, item.draw.accepted_rejection_ordinal) for item in unequal) == (
        (1, 0),
        (8264810105833175493, 1),
    )
    trajectory = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config), stop_event_ordinal=2
    )
    assert trajectory.checkpoints[-1].sha256 == "db58b3982d3a76c1d93f55df486e265a6cdfd84a21f0e8b44af638d10219db45"


def test_checkpoint_reconstructs_every_accumulator_field_and_resumes() -> None:
    config = _config(root_seed=23)
    prefix = advance_reference_trajectory(trajectory=start_reference_trajectory(config=config), stop_event_ordinal=20)
    checkpoint = prefix.checkpoints[-1]
    reconstructed = reconstruct_reference_checkpoint(
        payload=checkpoint.payload,
        expected_config=config,
        expected_sha256=checkpoint.sha256,
    )
    assert reconstructed == prefix.accumulator
    resumed = ReferenceTrajectory(
        config=config,
        accumulator=reconstructed,
        checkpoints=prefix.checkpoints,
        final_manifest=None,
    )
    resumed = advance_reference_trajectory(trajectory=resumed, stop_event_ordinal=31)
    uninterrupted = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config), stop_event_ordinal=31
    )
    assert resumed == uninterrupted


def test_checkpoint_parser_rejects_byte_identity_inventory_and_state_tampering() -> None:
    config = _config()
    trajectory = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config), stop_event_ordinal=3
    )
    checkpoint = trajectory.checkpoints[-1]
    with pytest.raises(ValueError, match="expected identity"):
        reconstruct_reference_checkpoint(
            payload=checkpoint.payload,
            expected_config=config,
            expected_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="canonical|trailing"):
        payload = checkpoint.payload[:-1] + b" \n"
        reconstruct_reference_checkpoint(
            payload=payload,
            expected_config=config,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    record = json.loads(checkpoint.payload)
    record["accumulator"]["current_state"]["shape"] = [0, 2]
    payload = canonical_json_bytes(record)
    with pytest.raises(ValueError, match="shape"):
        reconstruct_reference_checkpoint(
            payload=payload,
            expected_config=config,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    record = json.loads(checkpoint.payload)
    occupied = record["accumulator"]["current_state"]["occupied"]
    record["accumulator"]["current_state"]["occupied"] = list(reversed(occupied))
    state_bytes = canonical_json_bytes(record["accumulator"]["current_state"]["occupied"])
    record["accumulator"]["current_state"]["checksum_sha256"] = hashlib.sha256(state_bytes).hexdigest()
    payload = canonical_json_bytes(record)
    with pytest.raises(ValueError, match="lexicographically sorted"):
        reconstruct_reference_checkpoint(
            payload=payload,
            expected_config=config,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    record = json.loads(checkpoint.payload)
    record["unexpected"] = 1
    payload = canonical_json_bytes(record)
    with pytest.raises(ValueError, match="inventory"):
        reconstruct_reference_checkpoint(
            payload=payload,
            expected_config=config,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    other = replace(config, plan_id="different-plan")
    with pytest.raises(ValueError, match="task identity"):
        reconstruct_reference_checkpoint(
            payload=checkpoint.payload,
            expected_config=other,
            expected_sha256=checkpoint.sha256,
        )


def test_independent_replay_rejects_coherent_false_history_and_mixed_inventory() -> None:
    config = _config(root_seed=0)
    first = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config), stop_event_ordinal=1
    ).checkpoints[-1]
    record = json.loads(first.payload)
    accumulator = record["accumulator"]
    accumulator["family_counts"] = [["i", 1], ["lj", 0], ["o", 0], ["sz", 0], ["t", 0]]
    accumulator["orientation_counts"] = [
        [orientation_id, int(orientation_id == "tetromino.i.00")]
        for orientation_ids in FAMILY_ORIENTATION_IDS.values()
        for orientation_id in orientation_ids
    ]
    accumulator["topology_joint_counts"][0][0][0] = "tetromino.i.00"
    payload = canonical_json_bytes(record)
    with pytest.raises(ValueError, match="independent deterministic replay"):
        reconstruct_reference_checkpoint(
            payload=payload,
            expected_config=config,
            expected_sha256=hashlib.sha256(payload).hexdigest(),
        )

    own = advance_reference_trajectory(trajectory=start_reference_trajectory(config=config), stop_event_ordinal=3)
    forged_first = ReferenceCheckpoint(
        event_ordinal=1,
        payload=payload,
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    with pytest.raises(ValueError, match="independent deterministic replay"):
        ReferenceTrajectory(
            config=config,
            accumulator=own.accumulator,
            checkpoints=(forged_first, *own.checkpoints[1:]),
            final_manifest=None,
        )
    with pytest.raises(ValueError, match="independent deterministic replay"):
        replace(own, checkpoints=(forged_first, *own.checkpoints[1:]))

    other_config = _config(root_seed=1)
    other = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=other_config), stop_event_ordinal=3
    )
    with pytest.raises(ValueError, match="configuration bytes|identity"):
        ReferenceTrajectory(
            config=config,
            accumulator=own.accumulator,
            checkpoints=other.checkpoints,
            final_manifest=None,
        )


def test_all_transformed_orientations_and_contacts_round_trip_through_trajectory() -> None:
    cases = 0
    schedule = build_reference_checkpoint_schedule(terminal_event_count=769)
    for family, orientation_ids in FAMILY_ORIENTATION_IDS.items():
        for orientation_id in orientation_ids:
            orientation_laws = tuple(
                ExactWeightedLaw(
                    branch_ids,
                    tuple(
                        int(branch_id == orientation_id) if branch_family == family else 1 for branch_id in branch_ids
                    ),
                )
                for branch_family, branch_ids in FAMILY_ORIENTATION_IDS.items()
            )
            for contact_index in range(2):
                law = TetrominoEventLaw(
                    family_law=ExactWeightedLaw(
                        _FAMILIES,
                        tuple(int(candidate == family) for candidate in _FAMILIES),
                    ),
                    orientation_laws=ConditionalWeightedLaw(_FAMILIES, orientation_laws),
                    launch_law=UniformIntegerLaw(5),
                    contact_law=ExactWeightedLaw(
                        _CONTACTS,
                        tuple(int(index == contact_index) for index in range(2)),
                    ),
                )
                config = ReferenceTrajectoryConfig(
                    model_law_id=f"all-orientations-{orientation_id}-c{contact_index}",
                    plan_id="s2-reference-transformed-geometry-test@1",
                    software_commit=_SOFTWARE_COMMIT,
                    root_seed=cases,
                    coupling_group_id="s2-reference-transformed-geometry-test",
                    law=law,
                    width=5,
                    terminal_event_count=769,
                    checkpoint_schedule=schedule,
                )
                actual = advance_reference_trajectory(
                    trajectory=start_reference_trajectory(config=config),
                    stop_event_ordinal=1,
                )
                assert actual.accumulator == _manual_prefix(config, 1)
                checkpoint = actual.checkpoints[-1]
                assert (
                    reconstruct_reference_checkpoint(
                        payload=checkpoint.payload,
                        expected_config=config,
                        expected_sha256=checkpoint.sha256,
                    )
                    == actual.accumulator
                )
                cases += 1
    assert cases == 19 * 2 == 38


@pytest.mark.slow
def test_exhaustive_small_state_trajectory_surface_against_direct_certified_composition() -> None:
    cases = 0
    for morphology in range(2):
        for horizontal in range(2):
            for contact in range(2):
                for width in (5, 6):
                    for root_seed in range(4):
                        config = _config(
                            width=width,
                            root_seed=root_seed,
                            morphology=morphology,
                            horizontal=horizontal,
                            contact=contact,
                        )
                        for stop in range(5):
                            actual = advance_reference_trajectory(
                                trajectory=start_reference_trajectory(config=config),
                                stop_event_ordinal=stop,
                            )
                            assert actual.accumulator == _manual_prefix(config, stop)
                            cases += 1
    assert cases == 8 * 2 * 4 * 5 == 320


@pytest.mark.slow
def test_randomized_differential_prefixes_and_adversarial_factor_laws() -> None:
    generator = random.Random(0x5A2C10)
    for _ in range(256):
        width = generator.choice((5, 6))
        morphology = generator.randrange(2)
        horizontal = generator.randrange(2)
        contact = generator.randrange(2)
        root = generator.randrange(1 << 128)
        stop = generator.randrange(1, 17)
        config = _config(
            width=width,
            root_seed=root,
            morphology=morphology,
            horizontal=horizontal,
            contact=contact,
        )
        actual = advance_reference_trajectory(
            trajectory=start_reference_trajectory(config=config), stop_event_ordinal=stop
        )
        assert actual.accumulator == _manual_prefix(config, stop)
        reconstructed = reconstruct_reference_checkpoint(
            payload=actual.checkpoints[-1].payload,
            expected_config=config,
            expected_sha256=actual.checkpoints[-1].sha256,
        )
        assert reconstructed == actual.accumulator


@pytest.mark.slow
def test_terminal_512_checkpoint_manifest_and_all_round_trips() -> None:
    config = _config(root_seed=101)
    prefix = advance_reference_trajectory(
        trajectory=start_reference_trajectory(config=config),
        stop_event_ordinal=256,
    )
    restored_prefix = reconstruct_reference_checkpoint(
        payload=prefix.checkpoints[-1].payload,
        expected_config=config,
        expected_sha256=prefix.checkpoints[-1].sha256,
    )
    trajectory = advance_reference_trajectory(
        trajectory=ReferenceTrajectory(
            config=config,
            accumulator=restored_prefix,
            checkpoints=prefix.checkpoints,
            final_manifest=None,
        ),
        stop_event_ordinal=config.terminal_event_count,
    )
    assert len(trajectory.checkpoints) == 512
    assert trajectory.final_manifest is not None
    manifest = json.loads(trajectory.final_manifest)
    assert manifest["status"] == "complete"
    assert manifest["terminal_event_count"] == 769
    assert manifest["checkpoint_vector_sha256"] == config.checkpoint_schedule.vector_sha256
    assert manifest["final_checkpoint_sha256"] == trajectory.checkpoints[-1].sha256
    with pytest.raises(ValueError, match="final_manifest"):
        replace(trajectory, final_manifest=b"{}\n")
    reconstructed = reconstruct_reference_checkpoints(
        checkpoints=trajectory.checkpoints,
        expected_config=config,
    )
    assert tuple(item.event_count for item in reconstructed) == config.checkpoint_schedule.event_ordinals


@pytest.mark.slow
def test_ratified_8_by_2_by_4_by_256_exit_sweep() -> None:
    events = 0
    final_signatures = set()
    for morphology in range(2):
        for horizontal in range(2):
            for contact in range(2):
                for width in (5, 6):
                    for root_seed in range(4):
                        config = _config(
                            width=width,
                            root_seed=root_seed,
                            morphology=morphology,
                            horizontal=horizontal,
                            contact=contact,
                        )
                        trajectory = advance_reference_trajectory(
                            trajectory=start_reference_trajectory(config=config),
                            stop_event_ordinal=256,
                        )
                        final = trajectory.checkpoints[-1]
                        assert (
                            reconstruct_reference_checkpoint(
                                payload=final.payload,
                                expected_config=config,
                                expected_sha256=final.sha256,
                            )
                            == trajectory.accumulator
                        )
                        final_signatures.add(final.sha256)
                        events += trajectory.accumulator.event_count
    assert events == 8 * 2 * 4 * 256 == 16_384
    assert len(final_signatures) == 64
