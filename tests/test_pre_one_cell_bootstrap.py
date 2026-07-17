"""Fresh-process tests for the sealed PRE CLI package bootstrap."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_BOOTSTRAP_MODULE = "tetris_ballistic_pre_one_cell_bootstrap"
_TARGET_MODULES = {
    "run": "tetris_ballistic.scripts.run_pre_one_cell",
    "submit": "tetris_ballistic.scripts.submit_pre_one_cell",
}
_SCRUBBED_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C"}


@pytest.fixture(scope="module")
def installed_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    installation = tmp_path_factory.mktemp("pre-bootstrap-install")
    environment = installation / "environment"
    created = subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(environment)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert created.returncode == 0, created.stderr.decode("utf-8", "replace")
    python = environment / "bin" / "python"
    located = subprocess.run(
        [
            str(python),
            "-I",
            "-B",
            "-u",
            "-X",
            "utf8",
            "-c",
            "import sysconfig; print(sysconfig.get_paths()['purelib'])",
        ],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        timeout=30,
    )
    assert located.returncode == 0, located.stderr.decode("utf-8", "replace")
    purelib = Path(located.stdout.decode("utf-8", "strict").strip())
    for package in ("tetris_ballistic", _BOOTSTRAP_MODULE):
        shutil.copytree(
            _ROOT / package,
            purelib / package,
            ignore=shutil.ignore_patterns("__pycache__", "*.py[co]"),
        )
    return python


def _run_bootstrap(
    *,
    python: Path,
    tmp_path: Path,
    arguments: tuple[str, ...],
) -> subprocess.CompletedProcess[bytes]:
    before = tuple(tmp_path.iterdir())
    completed = subprocess.run(
        [
            str(python),
            "-I",
            "-B",
            "-u",
            "-X",
            "utf8",
            "-m",
            _BOOTSTRAP_MODULE,
            *arguments,
        ],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert tuple(tmp_path.iterdir()) == before
    return completed


@pytest.mark.parametrize("target", tuple(_TARGET_MODULES))
def test_exact_target_runs_headless_under_true_scrubbed_startup(
    tmp_path: Path,
    target: str,
    installed_python: Path,
) -> None:
    completed = _run_bootstrap(
        python=installed_python,
        tmp_path=tmp_path,
        arguments=(target, "--authorization", "/definitely/missing", "--execute"),
    )
    assert completed.returncode == 66
    assert completed.stdout == b""
    assert completed.stderr == b"ERROR[66]: authorization runtime directory does not exist\n"


@pytest.mark.parametrize(
    "target",
    (
        "",
        "Run",
        "run-pre-one-cell",
        "tetris_ballistic.scripts.run_pre_one_cell",
        "tetris_ballistic.scripts.submit_pre_one_cell",
        "status",
    ),
)
def test_forbidden_target_refuses_before_package_or_engine_import(
    tmp_path: Path,
    target: str,
    installed_python: Path,
) -> None:
    completed = _run_bootstrap(
        python=installed_python,
        tmp_path=tmp_path,
        arguments=(target,),
    )
    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr == b"ERROR[64]: unsupported PRE one-cell bootstrap target\n"


def test_absent_target_refuses_before_package_or_engine_import(
    tmp_path: Path,
    installed_python: Path,
) -> None:
    completed = _run_bootstrap(
        python=installed_python,
        tmp_path=tmp_path,
        arguments=(),
    )
    assert completed.returncode == 64
    assert completed.stdout == b""
    assert completed.stderr == b"ERROR[64]: exact PRE one-cell bootstrap target is required\n"


def test_uncontrolled_target_exit_is_converted_to_70(
    tmp_path: Path,
    installed_python: Path,
) -> None:
    script = """
from tetris_ballistic_pre_one_cell_bootstrap import __main__ as bootstrap
bootstrap._load_target = lambda target: (lambda arguments: 67, {}, {})
assert bootstrap.main(("run",)) == 70
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b"ERROR[70]: PRE one-cell CLI returned an invalid exit code\n"
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize("target", tuple(_TARGET_MODULES))
def test_local_instrumentation_proves_exact_modules_and_no_write_attempt(
    tmp_path: Path,
    target: str,
    installed_python: Path,
) -> None:
    expected_modules = {
        "tetris_ballistic",
        "tetris_ballistic.engine",
        "tetris_ballistic.engine.one_cell",
        "tetris_ballistic.engine.one_cell_boundary",
        "tetris_ballistic.engine.one_cell_campaign",
        "tetris_ballistic.engine.one_cell_runner",
        "tetris_ballistic.scripts",
        _TARGET_MODULES[target],
    }
    script = f"""
import builtins
import os
import runpy
import sys

real_open = builtins.open
real_os_open = os.open
real_mkdir = os.mkdir

def guarded_open(file, mode="r", *args, **kwargs):
    if any(flag in mode for flag in ("w", "a", "x", "+")):
        raise AssertionError(f"write through open: {{file!r}} {{mode!r}}")
    return real_open(file, mode, *args, **kwargs)

def guarded_os_open(path, flags, *args, **kwargs):
    forbidden = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
    if flags & forbidden:
        raise AssertionError(f"write through os.open: {{path!r}} {{flags!r}}")
    return real_os_open(path, flags, *args, **kwargs)

def guarded_mkdir(path, *args, **kwargs):
    raise AssertionError(f"mkdir attempt: {{path!r}}")

builtins.open = guarded_open
os.open = guarded_os_open
os.mkdir = guarded_mkdir
sys.argv = [
    {_BOOTSTRAP_MODULE!r},
    {target!r},
    "--authorization",
    "/definitely/missing",
    "--execute",
]
try:
    runpy.run_module({_BOOTSTRAP_MODULE!r}, run_name="__main__")
except SystemExit as error:
    assert error.code == 66, error.code
else:
    raise AssertionError("PRE bootstrap did not terminate through its main entry")

observed = {{
    name
    for name in sys.modules
    if name == "tetris_ballistic" or name.startswith("tetris_ballistic.")
}}
assert observed == {expected_modules!r}, sorted(observed)
forbidden = {{
    name
    for name in sys.modules
    if name == "matplotlib"
    or name.startswith("matplotlib.")
    or name in {{"pyexpat", "_elementtree"}}
    or name == "xml"
    or name.startswith("xml.")
    or name.split(".", 1)[0] in {{"scipy", "joblib", "imageio", "numpy", "numba"}}
}}
assert not forbidden, sorted(forbidden)
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b"ERROR[66]: authorization runtime directory does not exist\n"
    assert tuple(tmp_path.iterdir()) == ()


def test_run_target_import_keeps_runner_behind_cli_signal_boundary(
    tmp_path: Path,
    installed_python: Path,
) -> None:
    script = """
import sys
from tetris_ballistic_pre_one_cell_bootstrap import __main__ as bootstrap
target_main, _package_origins, _expected_paths = bootstrap._load_target("run")
assert callable(target_main)
assert "tetris_ballistic.scripts.run_pre_one_cell" in sys.modules
assert "tetris_ballistic.engine.one_cell_runner" not in sys.modules
assert "tetris_ballistic.engine.one_cell_campaign" not in sys.modules
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""
    assert tuple(tmp_path.iterdir()) == ()


def test_post_main_allows_certified_external_dependency_closure(
    tmp_path: Path,
    installed_python: Path,
) -> None:
    script = """
import sys
import types
from tetris_ballistic_pre_one_cell_bootstrap import __main__ as bootstrap
_target_main, package_origins, expected_paths = bootstrap._load_target("run")
for name in ("numpy", "numba", "scipy", "scipy._lib", "joblib"):
    sys.modules[name] = types.ModuleType(name)
bootstrap._verify_post_main_modules(package_origins, expected_paths)
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize(
    "collision",
    ("tetris_ballistic", "tetris_ballistic.engine", "tetris_ballistic.detached_descendant"),
)
def test_preloaded_tetris_collision_fails_closed(
    tmp_path: Path,
    collision: str,
    installed_python: Path,
) -> None:
    script = f"""
import runpy
import sys
import types
sys.modules[{collision!r}] = types.ModuleType({collision!r})
sys.argv = [
    {_BOOTSTRAP_MODULE!r},
    "run",
    "--authorization",
    "/definitely/missing",
    "--validate-only",
]
try:
    runpy.run_module({_BOOTSTRAP_MODULE!r}, run_name="__main__")
except SystemExit as error:
    assert error.code == 78, error.code
else:
    raise AssertionError("bootstrap accepted a module collision")
assert "tetris_ballistic.engine.one_cell_runner" not in sys.modules
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr.startswith(b"ERROR[78]: PRE one-cell bootstrap failed: bootstrap module collision: ")
    assert tuple(tmp_path.iterdir()) == ()


def test_symlinked_package_path_is_refused(
    tmp_path: Path,
    installed_python: Path,
) -> None:
    real_directory = tmp_path / "real-package"
    real_directory.mkdir()
    linked_directory = tmp_path / "linked-package"
    linked_directory.symlink_to(real_directory, target_is_directory=True)
    script = f"""
from tetris_ballistic_pre_one_cell_bootstrap import __main__ as bootstrap
try:
    bootstrap._require_unlinked_path({str(linked_directory)!r}, directory=True)
except RuntimeError as error:
    assert str(error) == "bootstrap path is linked or noncanonical"
else:
    raise AssertionError("bootstrap accepted a symlinked package directory")
"""
    completed = subprocess.run(
        [str(installed_python), "-I", "-B", "-u", "-X", "utf8", "-c", script],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_SCRUBBED_ENVIRONMENT,
        cwd=tmp_path,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert completed.stdout == b""
    assert completed.stderr == b""


def test_ordinary_root_and_frozen_cli_bytes_are_unchanged() -> None:
    expected = {
        "tetris_ballistic/__init__.py": "43969005018cee0ce0833e9fc219bbe1540a03d6d177f51a59645cf543518770",
        "tetris_ballistic/engine/one_cell_runner.py": (
            "65c327edea629ee434454ea72bbd555ebf53bca52c0e369cccc0f72db4f3920b"
        ),
        "tetris_ballistic/scripts/run_pre_one_cell.py": (
            "8028de350c8981b5b3de93c4be7da9c21cd50887bc62ab16ee39e319dd3d6eed"
        ),
        "tetris_ballistic/scripts/submit_pre_one_cell.py": (
            "12bc06777ddee133f3e550b6c58480acc65a118cc000281743d19b59aa1ec92d"
        ),
    }
    actual = {relative: hashlib.sha256((_ROOT / relative).read_bytes()).hexdigest() for relative in expected}
    assert actual == expected


def test_package_discovery_includes_headless_bootstrap() -> None:
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["tetris_ballistic*"]' in pyproject
    assert (_ROOT / _BOOTSTRAP_MODULE / "__init__.py").is_file()
    assert (_ROOT / _BOOTSTRAP_MODULE / "__main__.py").is_file()
