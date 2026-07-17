"""Enter a sealed PRE CLI without executing legacy package initializers."""

from __future__ import annotations

import importlib
import importlib.machinery
import os
import stat
import sys
import types
from collections.abc import Sequence

_TARGET_MODULES = {
    "run": "tetris_ballistic.scripts.run_pre_one_cell",
    "submit": "tetris_ballistic.scripts.submit_pre_one_cell",
}
_CONTROLLED_EXIT_CODES = frozenset({0, 64, 65, 66, 69, 70, 74, 75, 76, 77, 78})
_MAX_DIAGNOSTIC_BYTES = 4_096
_FORBIDDEN_ENVIRONMENT = frozenset({"LD_LIBRARY_PATH", "MPLCONFIGDIR", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"})
_FORBIDDEN_MODULE_ROOTS = (
    "_elementtree",
    "imageio",
    "joblib",
    "matplotlib",
    "numba",
    "numpy",
    "pyexpat",
    "scipy",
    "xml",
)
_LEGACY_TETRIS_MODULES = frozenset(
    {
        "tetris_ballistic.data_analysis_utilities",
        "tetris_ballistic.image_loader",
        "tetris_ballistic.legacy_adapter",
        "tetris_ballistic.models",
        "tetris_ballistic.retrieve_default_configs",
        "tetris_ballistic.sweep_parameters",
        "tetris_ballistic.tetris_ballistic",
    }
)
_RUNNER_MODULES = frozenset(
    {
        "tetris_ballistic",
        "tetris_ballistic.engine",
        "tetris_ballistic.engine.one_cell",
        "tetris_ballistic.engine.one_cell_boundary",
        "tetris_ballistic.engine.one_cell_campaign",
        "tetris_ballistic.engine.one_cell_runner",
        "tetris_ballistic.scripts",
    }
)


def _diagnostic(code: int, message: str) -> bytes:
    prefix = f"ERROR[{code:02d}]: ".encode("ascii")
    safe_message = " ".join(message.split()).encode("ascii", "backslashreplace")
    available = _MAX_DIAGNOSTIC_BYTES - len(prefix) - 1
    return prefix + safe_message[:available] + b"\n"


def _fail(code: int, message: str) -> int:
    try:
        sys.stderr.buffer.write(_diagnostic(code, message))
        sys.stderr.buffer.flush()
    except Exception:
        pass
    return code


def _require_startup_contract() -> None:
    if sys.flags.isolated != 1 or not sys.dont_write_bytecode or sys.flags.utf8_mode != 1:
        raise RuntimeError("bootstrap requires exact -I -B -X utf8 startup flags")
    if os.environ.get("LANG") != "C" or os.environ.get("LC_ALL") != "C":
        raise RuntimeError("bootstrap requires exact C locale environment")
    present = sorted(_FORBIDDEN_ENVIRONMENT.intersection(os.environ))
    if present:
        raise RuntimeError(f"bootstrap environment contains forbidden key: {present[0]}")


def _require_no_tetris_collision() -> None:
    collisions = sorted(
        name for name in sys.modules if name == "tetris_ballistic" or name.startswith("tetris_ballistic.")
    )
    if collisions:
        raise RuntimeError(f"bootstrap module collision: {collisions[0]}")


def _require_unlinked_path(path: str, *, directory: bool) -> str:
    normalized = os.path.abspath(path)
    if normalized != path or os.path.realpath(normalized) != normalized:
        raise RuntimeError("bootstrap path is linked or noncanonical")
    try:
        metadata = os.lstat(normalized)
    except OSError as error:
        raise RuntimeError("bootstrap path is unavailable") from error
    expected = stat.S_ISDIR(metadata.st_mode) if directory else stat.S_ISREG(metadata.st_mode)
    if not expected:
        raise RuntimeError("bootstrap path has the wrong filesystem type")
    return normalized


def _trusted_path(root: str, relative: str, *, directory: bool) -> str:
    candidate = os.path.abspath(os.path.join(root, relative))
    try:
        within_root = os.path.commonpath((root, candidate)) == root
    except ValueError as error:
        raise RuntimeError("bootstrap path cannot be joined to its installation root") from error
    if not within_root:
        raise RuntimeError("bootstrap path escapes its installation root")
    return _require_unlinked_path(candidate, directory=directory)


def _trusted_paths(target_module: str) -> tuple[dict[str, str | None], dict[str, str]]:
    main_file = _require_unlinked_path(os.path.abspath(__file__), directory=False)
    bootstrap_directory = _require_unlinked_path(os.path.dirname(main_file), directory=True)
    installation_root = _require_unlinked_path(os.path.dirname(bootstrap_directory), directory=True)
    expected_bootstrap = _trusted_path(
        installation_root,
        "tetris_ballistic_pre_one_cell_bootstrap",
        directory=True,
    )
    if bootstrap_directory != expected_bootstrap:
        raise RuntimeError("bootstrap package is outside its exact installation path")
    _trusted_path(installation_root, "tetris_ballistic_pre_one_cell_bootstrap/__init__.py", directory=False)
    expected_main = _trusted_path(
        installation_root,
        "tetris_ballistic_pre_one_cell_bootstrap/__main__.py",
        directory=False,
    )
    if main_file != expected_main:
        raise RuntimeError("bootstrap main module is outside its exact installation path")

    package_directory = _trusted_path(installation_root, "tetris_ballistic", directory=True)
    engine_directory = _trusted_path(installation_root, "tetris_ballistic/engine", directory=True)
    scripts_directory = _trusted_path(installation_root, "tetris_ballistic/scripts", directory=True)
    package_initializer = _trusted_path(installation_root, "tetris_ballistic/__init__.py", directory=False)
    engine_initializer = _trusted_path(installation_root, "tetris_ballistic/engine/__init__.py", directory=False)

    module_files = {
        "tetris_ballistic.engine.one_cell": _trusted_path(
            installation_root, "tetris_ballistic/engine/one_cell.py", directory=False
        ),
        "tetris_ballistic.engine.one_cell_boundary": _trusted_path(
            installation_root,
            "tetris_ballistic/engine/one_cell_boundary.py",
            directory=False,
        ),
        "tetris_ballistic.engine.one_cell_campaign": _trusted_path(
            installation_root,
            "tetris_ballistic/engine/one_cell_campaign.py",
            directory=False,
        ),
        "tetris_ballistic.engine.one_cell_runner": _trusted_path(
            installation_root,
            "tetris_ballistic/engine/one_cell_runner.py",
            directory=False,
        ),
        target_module: _trusted_path(
            installation_root,
            target_module.replace(".", "/") + ".py",
            directory=False,
        ),
    }
    package_origins: dict[str, str | None] = {
        "tetris_ballistic": package_initializer,
        "tetris_ballistic.engine": engine_initializer,
        "tetris_ballistic.scripts": None,
    }
    package_paths = {
        "tetris_ballistic": package_directory,
        "tetris_ballistic.engine": engine_directory,
        "tetris_ballistic.scripts": scripts_directory,
    }
    return package_origins, {**package_paths, **module_files}


def _seed_package(name: str, directory: str, initializer: str | None) -> types.ModuleType:
    spec = importlib.machinery.ModuleSpec(
        name,
        loader=None,
        origin=initializer,
        is_package=True,
    )
    spec.submodule_search_locations = [directory]
    package = types.ModuleType(name)
    package.__file__ = initializer
    package.__loader__ = None
    package.__package__ = name
    package.__path__ = [directory]
    package.__spec__ = spec
    sys.modules[name] = package
    return package


def _seed_headless_package_paths(
    package_origins: dict[str, str | None],
    expected_paths: dict[str, str],
) -> None:
    package = _seed_package(
        "tetris_ballistic",
        expected_paths["tetris_ballistic"],
        package_origins["tetris_ballistic"],
    )
    engine = _seed_package(
        "tetris_ballistic.engine",
        expected_paths["tetris_ballistic.engine"],
        package_origins["tetris_ballistic.engine"],
    )
    scripts = _seed_package(
        "tetris_ballistic.scripts",
        expected_paths["tetris_ballistic.scripts"],
        package_origins["tetris_ballistic.scripts"],
    )
    package.engine = engine
    package.scripts = scripts


def _require_no_legacy_tetris_modules() -> None:
    legacy = sorted(_LEGACY_TETRIS_MODULES.intersection(sys.modules))
    if legacy:
        raise RuntimeError(f"bootstrap imported legacy package module: {legacy[0]}")


def _require_no_forbidden_modules() -> None:
    for name in sys.modules:
        if any(name == root or name.startswith(root + ".") for root in _FORBIDDEN_MODULE_ROOTS):
            raise RuntimeError(f"bootstrap imported forbidden module: {name}")
    _require_no_legacy_tetris_modules()


def _verify_tetris_modules(
    expected_names: frozenset[str],
    package_origins: dict[str, str | None],
    expected_paths: dict[str, str],
) -> None:
    observed_names = frozenset(
        name for name in sys.modules if name == "tetris_ballistic" or name.startswith("tetris_ballistic.")
    )
    if observed_names != expected_names:
        raise RuntimeError("bootstrap imported an unexpected tetris_ballistic module set")
    for name in expected_names:
        module = sys.modules[name]
        spec = getattr(module, "__spec__", None)
        if spec is None:
            raise RuntimeError(f"bootstrap module lacks a specification: {name}")
        if name in package_origins:
            expected_origin = package_origins[name]
            if getattr(module, "__file__", None) != expected_origin or spec.origin != expected_origin:
                raise RuntimeError(f"bootstrap package origin mismatch: {name}")
            if tuple(getattr(module, "__path__", ())) != (expected_paths[name],):
                raise RuntimeError(f"bootstrap package path mismatch: {name}")
        else:
            expected_file = expected_paths[name]
            module_file = getattr(module, "__file__", None)
            if module_file is None or os.path.realpath(module_file) != expected_file:
                raise RuntimeError(f"bootstrap module file mismatch: {name}")
            if spec.origin is None or os.path.realpath(spec.origin) != expected_file:
                raise RuntimeError(f"bootstrap module origin mismatch: {name}")
    _require_no_forbidden_modules()


def _verify_post_main_modules(
    package_origins: dict[str, str | None],
    expected_paths: dict[str, str],
) -> None:
    package_root = expected_paths["tetris_ballistic"]
    names = tuple(name for name in sys.modules if name == "tetris_ballistic" or name.startswith("tetris_ballistic."))
    for name in names:
        module = sys.modules[name]
        spec = getattr(module, "__spec__", None)
        if spec is None:
            raise RuntimeError(f"post-main module lacks a specification: {name}")
        if name in package_origins:
            expected_origin = package_origins[name]
            if getattr(module, "__file__", None) != expected_origin or spec.origin != expected_origin:
                raise RuntimeError(f"post-main package origin mismatch: {name}")
            if tuple(getattr(module, "__path__", ())) != (expected_paths[name],):
                raise RuntimeError(f"post-main package path mismatch: {name}")
            continue
        module_file = getattr(module, "__file__", None)
        if type(module_file) is not str:
            raise RuntimeError(f"post-main module file is unavailable: {name}")
        canonical_file = _require_unlinked_path(os.path.abspath(module_file), directory=False)
        try:
            within_package = os.path.commonpath((package_root, canonical_file)) == package_root
        except ValueError as error:
            raise RuntimeError(f"post-main module path cannot be joined: {name}") from error
        if not within_package:
            raise RuntimeError(f"post-main module escaped the package root: {name}")
        if spec.origin is None or os.path.realpath(spec.origin) != canonical_file:
            raise RuntimeError(f"post-main module origin mismatch: {name}")
    _require_no_legacy_tetris_modules()


def _load_target(
    target: str,
) -> tuple[object, dict[str, str | None], dict[str, str]]:
    target_module = _TARGET_MODULES[target]
    _require_startup_contract()
    _require_no_tetris_collision()
    _require_no_forbidden_modules()
    package_origins, expected_paths = _trusted_paths(target_module)
    _seed_headless_package_paths(package_origins, expected_paths)
    module = importlib.import_module(target_module)
    expected_modules = (
        _RUNNER_MODULES | frozenset({target_module})
        if target == "submit"
        else frozenset(
            {
                "tetris_ballistic",
                "tetris_ballistic.engine",
                "tetris_ballistic.scripts",
                target_module,
            }
        )
    )
    _verify_tetris_modules(
        expected_modules,
        package_origins,
        expected_paths,
    )
    return module.main, package_origins, expected_paths


def main(argv: Sequence[str] | None = None) -> int:
    try:
        arguments = tuple(sys.argv[1:] if argv is None else argv)
    except Exception:
        return _fail(64, "bootstrap arguments are unavailable")
    if not arguments or type(arguments[0]) is not str:
        return _fail(64, "exact PRE one-cell bootstrap target is required")
    target = arguments[0]
    if target not in _TARGET_MODULES:
        return _fail(64, "unsupported PRE one-cell bootstrap target")

    try:
        target_main, package_origins, expected_paths = _load_target(target)
    except Exception as error:
        return _fail(78, f"PRE one-cell bootstrap failed: {error}")
    try:
        exit_code = target_main(arguments[1:])
    except Exception as error:
        return _fail(70, f"PRE one-cell CLI failed outside its boundary: {error}")
    if type(exit_code) is not int or exit_code not in _CONTROLLED_EXIT_CODES:
        return _fail(70, "PRE one-cell CLI returned an invalid exit code")
    try:
        _verify_post_main_modules(package_origins, expected_paths)
    except Exception as error:
        return _fail(78, f"PRE one-cell post-main verification failed: {error}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
