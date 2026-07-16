"""Authorization-gated submission CLI for the PRE one-cell runner."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import BinaryIO, TextIO

from tetris_ballistic.engine import one_cell_runner as _runner

_CONTROLLED_FAILURE_CODES = frozenset({64, 65, 66, 69, 70, 74, 75, 76, 77, 78})
_MAX_DIAGNOSTIC_BYTES = 4_096


class _CliUsageError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _ParsedArguments:
    authorization: str
    execute: bool


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
        if argument in {"--validate-only", "--execute"}:
            if mode is not None:
                raise _CliUsageError("exactly one mode is required")
            mode = argument[2:]
            offset += 1
            continue
        raise _CliUsageError(f"unsupported argument: {argument}")
    if authorization is None:
        raise _CliUsageError("--authorization must appear exactly once")
    if mode is None:
        raise _CliUsageError("exactly one mode is required")
    return _ParsedArguments(authorization=authorization, execute=mode == "execute")


def _run(parsed: _ParsedArguments) -> bytes:
    launch = _runner.load_one_cell_launch_authority(authorization_path=parsed.authorization)
    if not parsed.execute:
        return launch.launch_sha256.encode("ascii") + b"\n"
    outcome = _runner.submit_one_cell_launch(launch=launch)
    return outcome.array_job_id.encode("ascii") + b"\n"


def _failure_code(error: BaseException) -> int:
    if isinstance(error, _CliUsageError):
        return 64
    if isinstance(
        error,
        (
            _runner.OneCellRunnerValidationError,
            _runner.OneCellRunnerAuthorizationError,
            _runner.OneCellSchedulerError,
        ),
    ):
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


def _diagnostic(error: BaseException) -> tuple[int, bytes]:
    code = _failure_code(error)
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


def _emit_failure(error: BaseException) -> int:
    code, payload = _diagnostic(error)
    try:
        _write_bytes(sys.stderr, payload, encoding="ascii")
    except Exception:
        pass
    return code


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = tuple(sys.argv[1:] if argv is None else argv)
        parsed = _parse_arguments(arguments)
        output = _run(parsed)
    except Exception as error:
        return _emit_failure(error)
    try:
        _write_bytes(sys.stdout, output, encoding="utf-8")
    except Exception as error:
        return _emit_failure(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
