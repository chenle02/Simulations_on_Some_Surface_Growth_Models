"""Batch accounting uses managed dispositions rather than file mtimes."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from tetris_ballistic.run_artifacts import CellDisposition
from tetris_ballistic.scripts import run_batch


def _spec():
    return {
        "piece_config": "piece_19_combined_percentage",
        "pcts": [50],
        "widths": [5],
        "seeds": [0, 1],
        "ratio": 2,
    }


def _argv(tmp_path):
    return [
        "run_batch",
        "--grid-spec",
        "unused.yaml",
        "--out-dir",
        str(tmp_path),
        "--start",
        "0",
        "--stop",
        "2",
    ]


def test_batch_counts_explicit_created_and_reused_dispositions(tmp_path, monkeypatch, capsys) -> None:
    dispositions = iter([CellDisposition.CREATED, CellDisposition.REUSED])
    monkeypatch.setattr(run_batch, "load_grid_spec", lambda _path: _spec())
    monkeypatch.setattr(run_batch, "_warm_up_kernel", lambda: None)
    monkeypatch.setattr(
        run_batch,
        "run_cell_result",
        lambda *args, **kwargs: SimpleNamespace(disposition=next(dispositions)),
    )
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))

    run_batch.main()

    assert "1 run, 1 skipped, 0 failed" in capsys.readouterr().out


def test_batch_persistence_failure_is_counted_and_exits_nonzero(tmp_path, monkeypatch, capsys) -> None:
    calls = 0

    def fail_second(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("persistence failed")
        return SimpleNamespace(disposition=CellDisposition.CREATED)

    monkeypatch.setattr(run_batch, "load_grid_spec", lambda _path: _spec())
    monkeypatch.setattr(run_batch, "_warm_up_kernel", lambda: None)
    monkeypatch.setattr(run_batch, "run_cell_result", fail_second)
    monkeypatch.setattr(sys, "argv", _argv(tmp_path))

    with pytest.raises(SystemExit) as error:
        run_batch.main()

    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "persistence failed" in output
    assert "1 run, 0 skipped, 1 failed" in output
