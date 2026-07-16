"""Contract tests for the explicit PRE submission-side CLI.

The runner boundary is monkeypatched throughout; no test contacts Slurm or
creates a production submission claim.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from tetris_ballistic.engine import one_cell_runner as runner
from tetris_ballistic.scripts import submit_pre_one_cell as cli

_AUTHORIZATION = "/private/authorizations/pre-one-cell"
_LAUNCH_SHA256 = "a" * 64
_DIAGNOSTIC = re.compile(rb"ERROR\[[0-9]{2}\]: [^\r\n]*\n\Z")


def _launch() -> SimpleNamespace:
    return SimpleNamespace(launch_sha256=_LAUNCH_SHA256)


def _unexpected(*args: object, **kwargs: object) -> object:
    del args, kwargs
    pytest.fail("forbidden submission CLI effect was reached")


def _assert_failure_output(
    captured: pytest.CaptureResult[bytes],
    *,
    code: int,
) -> None:
    assert captured.out == b""
    assert len(captured.err) <= 4096
    assert captured.err.startswith(f"ERROR[{code:02d}]: ".encode("ascii"))
    assert _DIAGNOSTIC.fullmatch(captured.err)
    captured.err.decode("ascii", "strict")
    assert b"Traceback" not in captured.err


def test_main_has_one_optional_argv_parameter_and_no_in_job_or_legacy_imports() -> None:
    parameters = tuple(inspect.signature(cli.main).parameters.values())
    assert tuple(parameter.name for parameter in parameters) == ("argv",)
    assert parameters[0].default is None

    source = Path(cli.__file__).read_text(encoding="utf-8")
    assert "run_one_cell" not in source
    assert "run_batch" not in source
    assert "run_artifacts" not in source
    assert "one_cell_checkpoint" not in source
    assert "subprocess" not in source
    assert "signal" not in source


def test_validate_only_outputs_only_the_launch_digest(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    calls: list[str] = []

    def load(*, authorization_path: str) -> SimpleNamespace:
        calls.append(f"load:{authorization_path}")
        return _launch()

    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", load)
    monkeypatch.setattr(cli._runner, "submit_one_cell_launch", _unexpected)

    result = cli.main(("--authorization", _AUTHORIZATION, "--validate-only"))

    assert result == 0
    assert calls == [f"load:{_AUTHORIZATION}"]
    captured = capsysbinary.readouterr()
    assert captured.out == _LAUNCH_SHA256.encode("ascii") + b"\n"
    assert captured.err == b""


def test_execute_outputs_only_accepted_array_job_id(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    launch = _launch()
    calls: list[object] = []

    def load(*, authorization_path: str) -> SimpleNamespace:
        calls.append(("load", authorization_path))
        return launch

    def submit(*, launch: object) -> SimpleNamespace:
        calls.append(("submit", launch))
        return SimpleNamespace(array_job_id="4294967295")

    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", load)
    monkeypatch.setattr(cli._runner, "submit_one_cell_launch", submit)

    result = cli.main(("--execute", "--authorization", _AUTHORIZATION))

    assert result == 0
    assert calls == [("load", _AUTHORIZATION), ("submit", launch)]
    captured = capsysbinary.readouterr()
    assert captured.out == b"4294967295\n"
    assert captured.err == b""


def test_fixture_submission_refusal_has_no_success_output(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    launch = _launch()
    calls: list[str] = []
    monkeypatch.setattr(
        cli._runner,
        "load_one_cell_launch_authority",
        lambda *, authorization_path: calls.append("load") or launch,
    )

    def refuse(*, launch: object) -> object:
        calls.append("submit-refuse")
        raise runner.OneCellRunnerAuthorizationError(
            "fixture launch is permanently nonexecuting",
            exit_code=77,
        )

    monkeypatch.setattr(cli._runner, "submit_one_cell_launch", refuse)

    result = cli.main(("--authorization", _AUTHORIZATION, "--execute"))

    assert result == 77
    assert calls == ["load", "submit-refuse"]
    _assert_failure_output(capsysbinary.readouterr(), code=77)


@pytest.mark.parametrize(
    "arguments",
    (
        (),
        ("--authorization", "relative", "--validate-only"),
        ("--authorization", _AUTHORIZATION),
        ("--execute",),
        (
            "--authorization",
            _AUTHORIZATION,
            "--authorization",
            _AUTHORIZATION,
            "--execute",
        ),
        (
            "--authorization",
            _AUTHORIZATION,
            "--validate-only",
            "--execute",
        ),
        ("--authorization", _AUTHORIZATION, "--list-tasks"),
        ("--authorization", _AUTHORIZATION, "--explain-task", "0"),
        ("--authorization", _AUTHORIZATION, "--partition", "compute"),
        ("--authorization", _AUTHORIZATION, "--execute", object()),
    ),
)
def test_usage_failures_are_exact_and_never_load_authority(
    arguments: tuple[object, ...],
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", _unexpected)

    result = cli.main(arguments)  # type: ignore[arg-type]

    assert result == 64
    _assert_failure_output(capsysbinary.readouterr(), code=64)


@pytest.mark.parametrize(
    ("error", "code"),
    (
        (runner.OneCellRunnerValidationError("bad canonical input"), 65),
        (runner.OneCellRunnerAuthorizationError("missing", exit_code=66), 66),
        (runner.OneCellSchedulerError("rejected", exit_code=69), 69),
        (runner.OneCellSchedulerError("unknown", exit_code=75), 75),
        (OSError("disk failure"), 74),
        (ValueError("hostile type"), 65),
        (RuntimeError("private invariant"), 70),
    ),
)
def test_controlled_failures_have_frozen_exit_and_diagnostic(
    error: BaseException,
    code: int,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    def fail(*, authorization_path: str) -> object:
        del authorization_path
        raise error

    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", fail)

    result = cli.main(("--authorization", _AUTHORIZATION, "--validate-only"))

    assert result == code
    _assert_failure_output(capsysbinary.readouterr(), code=code)


def test_submission_failure_is_forwarded_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    monkeypatch.setattr(
        cli._runner,
        "load_one_cell_launch_authority",
        lambda *, authorization_path: _launch(),
    )

    def fail(*, launch: object) -> object:
        del launch
        raise runner.OneCellSchedulerError(
            "ambiguous \u2603\n" + "x" * 10_000,
            exit_code=75,
        )

    monkeypatch.setattr(cli._runner, "submit_one_cell_launch", fail)

    result = cli.main(("--authorization", _AUTHORIZATION, "--execute"))

    assert result == 75
    captured = capsysbinary.readouterr()
    _assert_failure_output(captured, code=75)
    assert b"\\u2603" in captured.err
