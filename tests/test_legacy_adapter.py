from __future__ import annotations

import json
import operator
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import numpy as np
import pytest

from tests.build_legacy_golden import _run
from tetris_ballistic.legacy_adapter import (
    GEOMETRY_ID_TO_LEGACY_PIECE,
    LEGACY_PIECE_GEOMETRY_IDS,
    LEGACY_STATES,
    LegacyState,
    density_from_distribution,
    distribution_from_density,
    state_for,
)
from tetris_ballistic.models import GEOMETRY_BY_ID, ContactKind, normalize_coordinates
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic

FIXTURE = Path(__file__).parent / "fixtures" / "legacy-trajectories-v1.json"

EXPECTED_GEOMETRY_IDS = (
    "tetromino.o.00",
    "tetromino.i.00",
    "tetromino.i.01",
    "tetromino.lj.05",
    "tetromino.lj.07",
    "tetromino.lj.03",
    "tetromino.lj.00",
    "tetromino.lj.06",
    "tetromino.lj.01",
    "tetromino.lj.02",
    "tetromino.lj.04",
    "tetromino.t.00",
    "tetromino.t.01",
    "tetromino.t.02",
    "tetromino.t.03",
    "tetromino.sz.02",
    "tetromino.sz.01",
    "tetromino.sz.00",
    "tetromino.sz.03",
    "baseline.one-cell",
)


def _single_piece_density(piece_id: int, column: int) -> dict[str, list[int]]:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density[f"Piece-{piece_id}"][column] = 1
    return density


def test_all_40_states_have_exact_flattened_identity() -> None:
    assert LEGACY_PIECE_GEOMETRY_IDS == EXPECTED_GEOMETRY_IDS
    assert len(LEGACY_STATES) == 40
    for flat_index, state in enumerate(LEGACY_STATES):
        assert state.flat_index == flat_index
        assert state.piece_id == flat_index // 2
        assert state.legacy_column == flat_index % 2
        assert state.sticky is bool(flat_index % 2)
        expected_contact = ContactKind.FIRST_CONTACT if state.sticky else ContactKind.SUPPORTED
        assert state.contact_kind is expected_contact
        assert state_for(state.geometry_id, state.contact_kind) == state


def test_geometry_reverse_map_is_read_only_and_bijective() -> None:
    assert len(GEOMETRY_ID_TO_LEGACY_PIECE) == 20
    with pytest.raises(TypeError):
        operator.setitem(GEOMETRY_ID_TO_LEGACY_PIECE, "bad", 99)


def test_legacy_piece_map_matches_actual_empty_substrate_deposition(monkeypatch) -> None:
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    for piece_id, geometry_id in enumerate(LEGACY_PIECE_GEOMETRY_IDS):
        simulation = Tetris_Ballistic(
            width=30,
            height=30,
            steps=1,
            seed=7,
            density=_single_piece_density(piece_id, 0),
        )
        with redirect_stdout(StringIO()):
            simulation.Simulate()
        coordinates = normalize_coordinates(
            tuple((int(row), int(column)) for row, column in np.argwhere(simulation.substrate > 0))
        )
        assert coordinates == GEOMETRY_BY_ID[geometry_id].coordinates


def test_density_round_trip_preserves_normalized_joint_weights() -> None:
    density = {f"Piece-{index}": [0, 0] for index in range(20)}
    density["Piece-0"] = [2, 1]
    density["Piece-19"] = [3, 4]
    distribution = distribution_from_density(density)
    round_trip = density_from_distribution(distribution)
    assert round_trip["Piece-0"] == pytest.approx([0.2, 0.1])
    assert round_trip["Piece-19"] == pytest.approx([0.3, 0.4])
    assert sum(sum(pair) for pair in round_trip.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    "density",
    [
        {},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-20": [1, 0]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [1]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [-1, 0]},
        {**{f"Piece-{index}": [0, 0] for index in range(20)}, "Piece-0": [float("nan"), 0]},
    ],
)
def test_invalid_legacy_density_fails_closed(density: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        distribution_from_density(density)


def test_direct_inconsistent_state_construction_fails() -> None:
    with pytest.raises(ValueError, match="disagree"):
        LegacyState(0, 1, False, "tetromino.i.00", ContactKind.SUPPORTED)


def test_json_golden_trajectories_reproduce_current_legacy_engine(monkeypatch) -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["generated_from_git_sha"] == "09b0a53"
    assert fixture["legacy_dispatch_forced"] is True
    monkeypatch.setenv("TETRIS_USE_KERNEL", "0")
    for expected in fixture["cases"]:
        case = {key: expected[key] for key in ("name", "piece_id", "weights", "width", "height", "steps", "seed")}
        assert _run(case) == expected
