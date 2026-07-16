"""Contract tests for the explicit PRE in-job CLI.

All authorities and lifecycle effects are inert monkeypatches.  These tests do
not contact Slurm or execute a scientific campaign cell.
"""

from __future__ import annotations

import ast
import inspect
import re
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tetris_ballistic.engine import one_cell_runner as runner
from tetris_ballistic.scripts import run_pre_one_cell as cli

_AUTHORIZATION = "/private/authorizations/pre-one-cell"
_LAUNCH_SHA256 = "a" * 64
_DIAGNOSTIC = re.compile(rb"ERROR\[[0-9]{2}\]: [^\r\n]*\n\Z")


def _launch() -> SimpleNamespace:
    return SimpleNamespace(launch_sha256=_LAUNCH_SHA256)


def _unexpected(*args: object, **kwargs: object) -> object:
    del args, kwargs
    pytest.fail("forbidden CLI effect was reached")


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


def test_main_has_one_optional_argv_parameter_and_no_legacy_imports() -> None:
    parameters = tuple(inspect.signature(cli.main).parameters.values())
    assert tuple(parameter.name for parameter in parameters) == ("argv",)
    assert parameters[0].default is None

    source = Path(cli.__file__).read_text(encoding="utf-8")
    assert "tetris_ballistic.scripts.run_one_cell" not in source
    assert "tetris_ballistic.scripts.run_batch" not in source
    assert "tetris_ballistic.run_artifacts" not in source
    assert "tetris_ballistic.engine.one_cell_checkpoint" not in source
    assert "subprocess" not in source

    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            assert not (
                node.module == "tetris_ballistic.engine"
                and any(alias.name == "one_cell_runner" for alias in node.names)
            )
    execute_main = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_execute_main"
    )
    first_statement = execute_main.body[0]
    assert isinstance(first_statement, ast.Try)
    mask_assignment = first_statement.body[0]
    assert isinstance(mask_assignment, ast.Assign)
    assert isinstance(mask_assignment.value, ast.Call)
    assert ast.unparse(mask_assignment.value.func) == "signal.pthread_sigmask"
    assert ast.unparse(mask_assignment.value.args[0]) == "signal.SIG_BLOCK"
    assert ast.unparse(mask_assignment.value.args[1]) == "{signal.SIGUSR1}"


def test_execute_masks_before_lazy_runner_import_but_inspection_need_not_mask(
    tmp_path: Path,
) -> None:
    script = r"""
import builtins
import contextlib
import io
import signal
import sys

from tetris_ballistic.scripts import run_pre_one_cell as cli

runner_name = "tetris_ballistic.engine.one_cell_runner"
assert runner_name not in sys.modules
events = []
masked = False
real_import = builtins.__import__

def traced_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == runner_name or (
        name == "tetris_ballistic.engine" and "one_cell_runner" in fromlist
    ):
        events.append(("runner-import", masked))
    return real_import(name, globals, locals, fromlist, level)

def pthread_sigmask(operation, mask):
    global masked
    if operation == signal.SIG_BLOCK:
        masked = True
        events.append(("mask", True))
        return frozenset()
    if operation == signal.SIG_SETMASK:
        events.append(("restore", masked))
        masked = False
        return frozenset()
    raise AssertionError(operation)

builtins.__import__ = traced_import
cli.signal.pthread_sigmask = pthread_sigmask
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        execute_code = cli.main(("--authorization", "/definitely/missing", "--execute"))
    assert execute_code == 66
    assert events[0] == ("mask", True)
    assert ("runner-import", True) in events
    assert events[-1] == ("restore", True)

    events.clear()
    sys.modules.pop(runner_name, None)
    engine = sys.modules.get("tetris_ballistic.engine")
    if engine is not None and hasattr(engine, "one_cell_runner"):
        delattr(engine, "one_cell_runner")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        inspection_code = cli.main(("--authorization", "/definitely/missing", "--validate-only"))
    assert inspection_code == 66
    assert all(event[0] != "mask" for event in events)
    assert ("runner-import", False) in events
finally:
    builtins.__import__ = real_import
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""


def test_validate_only_is_exact_and_does_not_touch_signal_or_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    calls: list[tuple[str, object]] = []

    def load(*, authorization_path: str) -> SimpleNamespace:
        calls.append(("load", authorization_path))
        return _launch()

    monkeypatch.setattr(cli.signal, "pthread_sigmask", _unexpected)
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", load)
    monkeypatch.setattr(cli._runner, "list_one_cell_launch_tasks", _unexpected)
    monkeypatch.setattr(cli._runner, "explain_one_cell_launch_task", _unexpected)
    monkeypatch.setattr(cli._runner, "authorize_one_cell_slurm_task", _unexpected)
    monkeypatch.setattr(cli._runner, "run_one_cell_authorized_task", _unexpected)

    result = cli.main(("--authorization", _AUTHORIZATION, "--validate-only"))

    assert result == 0
    assert calls == [("load", _AUTHORIZATION)]
    captured = capsysbinary.readouterr()
    assert captured.out == _LAUNCH_SHA256.encode("ascii") + b"\n"
    assert captured.err == b""


def test_list_tasks_emits_the_byte_identical_jsonl(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    launch = _launch()
    payload = (
        b'{"array_position":0,"profile":"tetris-pre-one-cell-launch-task@1"}\n'
        b'{"array_position":1,"profile":"tetris-pre-one-cell-launch-task@1"}\n'
    )
    calls: list[str] = []

    monkeypatch.setattr(
        cli._runner,
        "load_one_cell_launch_authority",
        lambda *, authorization_path: calls.append(f"load:{authorization_path}") or launch,
    )
    monkeypatch.setattr(
        cli._runner,
        "list_one_cell_launch_tasks",
        lambda *, launch: calls.append("validate-list") or (),
    )
    monkeypatch.setattr(
        cli._runner,
        "_ordered_tasks_bytes_for_cli",
        lambda *, launch: calls.append("render-list") or payload,
    )

    result = cli.main(("--list-tasks", "--authorization", _AUTHORIZATION))

    assert result == 0
    assert calls == [f"load:{_AUTHORIZATION}", "validate-list", "render-list"]
    captured = capsysbinary.readouterr()
    assert captured.out == payload
    assert captured.err == b""


def test_explain_task_emits_exact_identity_plus_one_lf(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    launch = _launch()
    identity = b'{"profile":"scientific-identity@1","task":7}'
    observed: list[tuple[object, int]] = []
    monkeypatch.setattr(
        cli._runner,
        "load_one_cell_launch_authority",
        lambda *, authorization_path: launch,
    )

    def explain(*, launch: object, array_position: int) -> bytes:
        observed.append((launch, array_position))
        return identity

    monkeypatch.setattr(cli._runner, "explain_one_cell_launch_task", explain)

    result = cli.main(("--authorization", _AUTHORIZATION, "--explain-task", "7"))

    assert result == 0
    assert observed == [(launch, 7)]
    captured = capsysbinary.readouterr()
    assert captured.out == identity + b"\n"
    assert captured.err == b""


def test_execute_blocks_first_restores_last_and_is_silent(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    launch = _launch()
    authorization = object()
    prior_mask = frozenset({signal.SIGINT})
    events: list[object] = []

    def pthread_sigmask(operation: int, mask: object) -> object:
        if operation == signal.SIG_BLOCK:
            events.append(("block", mask))
            return prior_mask
        assert operation == signal.SIG_SETMASK
        events.append(("restore", mask))
        return frozenset()

    def load(*, authorization_path: str) -> SimpleNamespace:
        events.append(("load", authorization_path))
        return launch

    def handshake(*, launch: object) -> tuple[bytes, bytes]:
        events.append(("handshake", launch))
        return b"claim\n", b"receipt\n"

    def authorize(
        *,
        launch: object,
        submission_claim_bytes: bytes,
        submission_receipt_bytes: bytes,
    ) -> object:
        events.append(
            (
                "authorize",
                launch,
                submission_claim_bytes,
                submission_receipt_bytes,
            )
        )
        return authorization

    def run(*, authorization: object) -> object:
        events.append(("run", authorization))
        return object()

    monkeypatch.setattr(cli.signal, "pthread_sigmask", pthread_sigmask)
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", load)
    monkeypatch.setattr(cli._runner, "_load_submission_handshake_for_cli", handshake)
    monkeypatch.setattr(cli._runner, "authorize_one_cell_slurm_task", authorize)
    monkeypatch.setattr(cli._runner, "run_one_cell_authorized_task", run)

    result = cli.main(("--execute", "--authorization", _AUTHORIZATION))

    assert result == 0
    assert events == [
        ("block", {signal.SIGUSR1}),
        ("load", _AUTHORIZATION),
        ("handshake", launch),
        ("authorize", launch, b"claim\n", b"receipt\n"),
        ("run", authorization),
        ("restore", prior_mask),
    ]
    captured = capsysbinary.readouterr()
    assert captured.out == b""
    assert captured.err == b""


def test_execute_fixture_refusal_restores_mask_before_diagnostic_and_has_no_effects(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    events: list[str] = []

    def pthread_sigmask(operation: int, mask: object) -> object:
        del mask
        if operation == signal.SIG_BLOCK:
            events.append("block")
            return frozenset()
        events.append("restore")
        return frozenset()

    def refuse(*, authorization_path: str) -> object:
        assert authorization_path == _AUTHORIZATION
        events.append("load-refuse")
        raise runner.OneCellRunnerAuthorizationError(
            "fixture launch is permanently nonexecuting",
            exit_code=77,
        )

    monkeypatch.setattr(cli.signal, "pthread_sigmask", pthread_sigmask)
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", refuse)
    monkeypatch.setattr(cli._runner, "_load_submission_handshake_for_cli", _unexpected)
    monkeypatch.setattr(cli._runner, "authorize_one_cell_slurm_task", _unexpected)
    monkeypatch.setattr(cli._runner, "run_one_cell_authorized_task", _unexpected)

    result = cli.main(("--authorization", _AUTHORIZATION, "--execute"))

    assert result == 77
    assert events == ["block", "load-refuse", "restore"]
    _assert_failure_output(capsysbinary.readouterr(), code=77)


def test_execute_mask_failure_exits_78_before_authority(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    def fail_mask(operation: int, mask: object) -> object:
        del operation, mask
        raise OSError("pthread mask unavailable")

    monkeypatch.setattr(cli.signal, "pthread_sigmask", fail_mask)
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", _unexpected)

    result = cli.main(("--authorization", _AUTHORIZATION, "--execute"))

    assert result == 78
    _assert_failure_output(capsysbinary.readouterr(), code=78)


def test_restoration_failure_suppresses_success_output_and_exits_78(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    calls = 0

    def pthread_sigmask(operation: int, mask: object) -> object:
        nonlocal calls
        del mask
        calls += 1
        if operation == signal.SIG_BLOCK:
            return frozenset()
        raise OSError("restore failed")

    monkeypatch.setattr(cli.signal, "pthread_sigmask", pthread_sigmask)
    monkeypatch.setattr(
        cli._runner,
        "load_one_cell_launch_authority",
        lambda *, authorization_path: _launch(),
    )
    monkeypatch.setattr(
        cli._runner,
        "_load_submission_handshake_for_cli",
        lambda *, launch: (b"claim\n", b"receipt\n"),
    )
    monkeypatch.setattr(
        cli._runner,
        "authorize_one_cell_slurm_task",
        lambda **kwargs: object(),
    )
    monkeypatch.setattr(
        cli._runner,
        "run_one_cell_authorized_task",
        lambda *, authorization: object(),
    )

    result = cli.main(("--authorization", _AUTHORIZATION, "--execute"))

    assert calls == 2
    assert result == 78
    _assert_failure_output(capsysbinary.readouterr(), code=78)


@pytest.mark.parametrize(
    "arguments",
    (
        (),
        ("--authorization", "relative", "--validate-only"),
        ("--authorization", _AUTHORIZATION),
        ("--validate-only",),
        (
            "--authorization",
            _AUTHORIZATION,
            "--authorization",
            _AUTHORIZATION,
            "--validate-only",
        ),
        (
            "--authorization",
            _AUTHORIZATION,
            "--validate-only",
            "--execute",
        ),
        ("--authorization", _AUTHORIZATION, "--explain-task"),
        ("--authorization", _AUTHORIZATION, "--explain-task", "01"),
        ("--authorization", _AUTHORIZATION, "--explain-task", "-1"),
        ("--authorization", _AUTHORIZATION, "--partition", "compute"),
        ("--authorization", _AUTHORIZATION, "--execute", object()),
    ),
)
def test_usage_failures_are_exact_and_never_load_authority(
    arguments: tuple[object, ...],
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    monkeypatch.setattr(
        cli.signal,
        "pthread_sigmask",
        lambda operation, mask: frozenset(),
    )
    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", _unexpected)

    result = cli.main(arguments)  # type: ignore[arg-type]

    assert result == 64
    _assert_failure_output(capsysbinary.readouterr(), code=64)


@pytest.mark.parametrize(
    ("error", "code"),
    (
        (runner.OneCellRunnerValidationError("bad canonical input"), 65),
        (runner.OneCellRunnerAuthorizationError("missing", exit_code=66), 66),
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


def test_diagnostic_is_ascii_single_line_and_bounded(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    message = "snowman \u2603\n" + "x" * 10_000

    def fail(*, authorization_path: str) -> object:
        del authorization_path
        raise runner.OneCellRunnerAuthorizationError(message, exit_code=76)

    monkeypatch.setattr(cli._runner, "load_one_cell_launch_authority", fail)

    result = cli.main(("--authorization", _AUTHORIZATION, "--validate-only"))

    assert result == 76
    captured = capsysbinary.readouterr()
    _assert_failure_output(captured, code=76)
    assert b"\\u2603" in captured.err
