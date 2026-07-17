"""Contract tests for the explicit PRE submission-side CLI.

The runner boundary is monkeypatched throughout; no test contacts Slurm or
creates a production submission claim.
"""

from __future__ import annotations

import hashlib
import inspect
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tetris_ballistic.engine import one_cell_runner as runner
from tetris_ballistic.scripts import submit_pre_one_cell as cli

_AUTHORIZATION = "/private/authorizations/pre-one-cell"
_LAUNCH_SHA256 = "a" * 64
_DIAGNOSTIC = re.compile(rb"ERROR\[[0-9]{2}\]: [^\r\n]*\n\Z")
_ROOT = Path(__file__).resolve().parents[1]


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


def test_administrative_compute_wrapper_is_inert_guarded_and_source_only() -> None:
    wrapper = _ROOT / "scripts" / "easley" / "submit_pre_one_cell.sbatch"
    source = wrapper.read_text(encoding="utf-8")
    assert source.endswith("\n")
    assert "#SBATCH" not in source
    assert "set -euo pipefail" in source
    assert "umask 077" in source
    assert source.count("--authorization") == 1
    assert source.count("--execute") == 1
    assert source.count("tetris_ballistic.scripts.submit_pre_one_cell") == 1
    assert 'kernel_hostname_file="/proc/sys/kernel/hostname"' in source
    assert '"$kernel_hostname" == "$SLURMD_NODENAME"' in source
    assert '"${SLURM_JOB_PARTITION:-}" == "nova_short"' in source
    assert '"${SLURM_JOB_NAME:-}" == "tkpz-admin-submit"' in source
    assert '"${SLURM_MEM_PER_NODE:-}" == "4096"' in source
    assert "node8[0-9][0-9]|node90[0-7]|node92[6-9]|node9[3-7][0-9]|node98[0-2]" in source
    assert "node9[0-7][0-9]" not in source
    assert source.index("kernel_hostname_file=") < source.index("runtime_python_file=")
    assert source.index('"$kernel_hostname" == "$SLURMD_NODENAME"') < source.index("runtime_python_file=")
    for forbidden in (
        "module load",
        "activate",
        "PYTHONPATH",
        "git ",
        "mkdir",
        "trap ",
        "sbatch",
        "scontrol",
        "srun",
        "--account",
        "--qos",
        "run_one_cell.py",
        "run_batch.py",
    ):
        assert forbidden not in source

    syntax = subprocess.run(
        ["/bin/bash", "-n", str(wrapper)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert syntax.returncode == 0, syntax.stderr.decode("utf-8", "replace")
    assert syntax.stdout == b""
    assert syntax.stderr == b""

    manifest = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    declaration = "include scripts/easley/submit_pre_one_cell.sbatch"
    assert manifest.count(declaration) == 1
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "scripts/easley/submit_pre_one_cell.sbatch" not in pyproject


def test_administrative_wrapper_refuses_spoofed_compute_environment_on_login() -> None:
    wrapper = _ROOT / "scripts" / "easley" / "submit_pre_one_cell.sbatch"
    kernel_hostname = Path("/proc/sys/kernel/hostname").read_text(encoding="ascii").strip()
    spoofed_node = "node801" if kernel_hostname != "node801" else "node802"
    completed = subprocess.run(
        ["/bin/bash", str(wrapper), "/definitely/missing"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "LANG": "C",
            "LC_ALL": "C",
            "SLURM_JOB_ID": "1",
            "SLURMD_NODENAME": spoofed_node,
            "SLURM_JOB_NODELIST": spoofed_node,
            "SLURM_JOB_NAME": "tkpz-admin-submit",
            "SLURM_JOB_PARTITION": "nova_short",
            "SLURM_JOB_NUM_NODES": "1",
            "SLURM_NTASKS": "1",
            "SLURM_CPUS_PER_TASK": "1",
            "SLURM_MEM_PER_NODE": "4096",
        },
        timeout=30,
    )
    assert completed.returncode == 78
    assert completed.stdout == b""
    assert completed.stderr == (b"ERROR[78]: the kernel hostname differs from the assigned compute node\n")


def test_administrative_wrapper_does_not_change_certified_scientific_bytes() -> None:
    expected = {
        "tetris_ballistic/engine/one_cell_runner.py": "65c327edea629ee434454ea72bbd555ebf53bca52c0e369cccc0f72db4f3920b",
        "tetris_ballistic/scripts/submit_pre_one_cell.py": "12bc06777ddee133f3e550b6c58480acc65a118cc000281743d19b59aa1ec92d",
        "scripts/easley/run_pre_one_cell.sbatch": "ff64545664ec9b4fb169e1b76197107738ae8d1df19da7fc3c8a971a497ba655",
    }
    actual = {relative: hashlib.sha256((_ROOT / relative).read_bytes()).hexdigest() for relative in expected}
    assert actual == expected
