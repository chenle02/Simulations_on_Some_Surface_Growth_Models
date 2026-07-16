"""Authorization-gated in-job CLI for the PRE one-cell runner."""

from __future__ import annotations

import os
import re
import signal
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import BinaryIO, TextIO

_CONTROLLED_FAILURE_CODES = frozenset({64, 65, 66, 69, 70, 74, 75, 76, 77, 78})
_CANONICAL_UINT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_MAX_DIAGNOSTIC_BYTES = 4_096

# Tests that imported the runner first may patch this already-loaded module.
# A fresh CLI process deliberately leaves it absent: execution must block
# SIGUSR1 before importing any runner code.
_runner = sys.modules.get("tetris_ballistic.engine.one_cell_runner")
_runner_error_types: tuple[type[BaseException], ...] = ()


class _CliUsageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _ParsedArguments:
    authorization: str
    mode: str
    array_position: int | None


def _load_runner() -> object:
    global _runner_error_types

    from tetris_ballistic.engine import one_cell_runner

    _runner_error_types = (
        one_cell_runner.OneCellRunnerValidationError,
        one_cell_runner.OneCellRunnerAuthorizationError,
        one_cell_runner.OneCellSchedulerError,
    )
    return one_cell_runner


def _require_authorization_path(value: object) -> str:
    if type(value) is not str or not value.startswith("/"):
        raise _CliUsageError("--authorization requires an absolute directory")
    if value.startswith("//") or value != os.path.normpath(value):
        raise _CliUsageError("--authorization requires a normalized absolute directory")
    if "\x00" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise _CliUsageError("--authorization contains a control character")
    return value


def _parse_arguments(arguments: tuple[object, ...]) -> _ParsedArguments:
    authorization: str | None = None
    mode: str | None = None
    array_position: int | None = None
    offset = 0
    while offset < len(arguments):
        argument = arguments[offset]
        if type(argument) is not str:
            raise _CliUsageError("arguments must be built-in strings")
        if argument == "--authorization":
            if authorization is not None or offset + 1 >= len(arguments):
                raise _CliUsageError("--authorization must appear exactly once")
            authorization = _require_authorization_path(arguments[offset + 1])
            offset += 2
            continue
        if argument in {"--validate-only", "--list-tasks", "--execute"}:
            if mode is not None:
                raise _CliUsageError("exactly one mode is required")
            mode = argument[2:]
            offset += 1
            continue
        if argument == "--explain-task":
            if mode is not None or offset + 1 >= len(arguments):
                raise _CliUsageError("--explain-task requires one array position")
            position_text = arguments[offset + 1]
            if type(position_text) is not str or _CANONICAL_UINT.fullmatch(position_text) is None:
                raise _CliUsageError("--explain-task requires a canonical nonnegative integer")
            mode = "explain-task"
            array_position = int(position_text)
            offset += 2
            continue
        raise _CliUsageError(f"unsupported argument: {argument}")
    if authorization is None:
        raise _CliUsageError("--authorization must appear exactly once")
    if mode is None:
        raise _CliUsageError("exactly one mode is required")
    return _ParsedArguments(
        authorization=authorization,
        mode=mode,
        array_position=array_position,
    )


def _run(parsed: _ParsedArguments) -> bytes:
    runner = _load_runner()
    launch = runner.load_one_cell_launch_authority(authorization_path=parsed.authorization)
    if parsed.mode == "validate-only":
        return launch.launch_sha256.encode("ascii") + b"\n"
    if parsed.mode == "list-tasks":
        runner.list_one_cell_launch_tasks(launch=launch)
        return runner._ordered_tasks_bytes_for_cli(launch=launch)
    if parsed.mode == "explain-task":
        assert parsed.array_position is not None
        return (
            runner.explain_one_cell_launch_task(
                launch=launch,
                array_position=parsed.array_position,
            )
            + b"\n"
        )
    if parsed.mode == "execute":
        claim_bytes, receipt_bytes = runner._load_submission_handshake_for_cli(launch=launch)
        authorization = runner.authorize_one_cell_slurm_task(
            launch=launch,
            submission_claim_bytes=claim_bytes,
            submission_receipt_bytes=receipt_bytes,
        )
        runner.run_one_cell_authorized_task(authorization=authorization)
        return b""
    raise AssertionError("parsed mode is outside the frozen vocabulary")


def _failure_code(error: BaseException) -> int:
    if isinstance(error, _CliUsageError):
        return 64
    if _runner_error_types and isinstance(error, _runner_error_types):
        exit_code = getattr(error, "exit_code", None)
        if type(exit_code) is int and exit_code in _CONTROLLED_FAILURE_CODES:
            return exit_code
        return 70
    if isinstance(error, (TypeError, ValueError, UnicodeError)):
        return 65
    if isinstance(error, OSError):
        return 74
    return 70


def _safe_error_message(error: BaseException) -> str:
    try:
        message = str(error)
    except Exception:
        message = type(error).__name__
    message = " ".join(message.split())
    if not message:
        message = type(error).__name__
    return message.encode("ascii", "backslashreplace").decode("ascii")


def _diagnostic(error: BaseException, *, forced_code: int | None = None) -> tuple[int, bytes]:
    code = _failure_code(error) if forced_code is None else forced_code
    prefix = f"ERROR[{code:02d}]: ".encode("ascii")
    message = _safe_error_message(error).encode("ascii")
    available = _MAX_DIAGNOSTIC_BYTES - len(prefix) - 1
    return code, prefix + message[:available] + b"\n"


def _write_bytes(stream: BinaryIO | TextIO, payload: bytes, *, encoding: str) -> None:
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        buffer.write(payload)
        buffer.flush()
        return
    stream.write(payload.decode(encoding))  # type: ignore[arg-type]
    stream.flush()


def _emit_failure(error: BaseException, *, forced_code: int | None = None) -> int:
    code, payload = _diagnostic(error, forced_code=forced_code)
    try:
        _write_bytes(sys.stderr, payload, encoding="ascii")
    except Exception:
        pass
    return code


def _execute_main(arguments: tuple[object, ...]) -> int:
    try:
        prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGUSR1})
    except Exception as error:
        return _emit_failure(error, forced_code=78)
    output = b""
    failure: BaseException | None = None
    try:
        parsed = _parse_arguments(arguments)
        output = _run(parsed)
    except Exception as error:
        failure = error
    finally:
        try:
            signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
        except Exception as error:
            restoration_failure: BaseException | None = error
            failure = error
        else:
            restoration_failure = None

    if failure is not None:
        forced_code = 78 if restoration_failure is not None else None
        return _emit_failure(failure, forced_code=forced_code)
    try:
        if output:
            _write_bytes(sys.stdout, output, encoding="utf-8")
    except Exception as error:
        return _emit_failure(error, forced_code=74)
    return 0


def _inspection_main(arguments: tuple[object, ...]) -> int:
    try:
        parsed = _parse_arguments(arguments)
        output = _run(parsed)
    except Exception as error:
        return _emit_failure(error)
    try:
        if output:
            _write_bytes(sys.stdout, output, encoding="utf-8")
    except Exception as error:
        return _emit_failure(error, forced_code=74)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = tuple(sys.argv[1:] if argv is None else argv)
    except Exception as error:
        return _emit_failure(error, forced_code=64)
    if any(type(argument) is str and argument == "--execute" for argument in arguments):
        return _execute_main(arguments)
    return _inspection_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
