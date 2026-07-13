#!/usr/bin/env python3
"""
Robust KPZ growth-exponent extraction for sticky/nonsticky ballistic deposition.

Implements the 8-step protocol documented in the SPDEs-wiki project page
``tetris-kpz-slope-extraction.md``.  Each function cites its methodological
origin in the docstring.

References
----------
- Family & Vicsek (1985). J. Phys. A 18, L75.
- Meakin, Ramanlal, Sander, Ball (1986). Phys. Rev. A 34, 5091.
- Baiod, Kessler, Ramanlal, Sander, Savit (1988). Phys. Rev. A 38, 3672.
- Krug & Meakin (1990). J. Phys. A 23, L987.
- Amar & Family (1990). Phys. Rev. A 41, 3399.
- Wendt, Abry, Jaffard (2007). IEEE wavelet-leader bootstrap.
- Pagnani & Parisi (2013). Phys. Rev. E 87, 010102.

Author: Le Chen (le.chen@auburn.edu)
"""

import ast
import math
import os
import re
import stat
import struct
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

import joblib
import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import linregress

REDUCED_INPUT_LAYOUT = "reduced"
LEGACY_FLAT_INPUT_LAYOUT = "legacy-flat"
SUPPORTED_INPUT_LAYOUTS = frozenset(
    {REDUCED_INPUT_LAYOUT, LEGACY_FLAT_INPUT_LAYOUT}
)
_LEGACY_FLAT_NAME = re.compile(
    r"^config_piece_19_combined_percentage_(\d+)_w=(\d+)_seed=(\d+)\.joblib$"
)
_REDUCED_KEYS = frozenset({
    "L",
    "W",
    "final_steps",
    "hbar",
    "hbar_max",
    "pct",
    "saturated",
    "seeds",
})
_REDUCED_HEIGHT_CORRECTED_KEYS = _REDUCED_KEYS | {"height_grid"}
_REDUCED_KEY_VARIANTS = (_REDUCED_KEYS, _REDUCED_HEIGHT_CORRECTED_KEYS)
_MAX_REDUCED_MEMBERS = max(len(keys) for keys in _REDUCED_KEY_VARIANTS)
_MAX_REDUCED_UNCOMPRESSED_BYTES = 8 * 1024**3
_MAX_ENSEMBLE_SEEDS = 1_000_000
_MAX_TRACE_POINTS = 100_000_000
_MAX_NPY_HEADER_BYTES = 64 * 1024
_REDUCED_VALIDATION_CHUNK_POINTS = 1_000_000


@dataclass(frozen=True)
class EnsembleInput:
    """Exact files selected for one slope-analysis ensemble."""

    layout: str
    root: Path
    percentage: int
    L: int
    paths: tuple[Path, ...]
    seeds: tuple[int, ...]


def _require_cell_identity(percentage: object, L: object) -> tuple[int, int]:
    if type(percentage) is not int or not 0 <= percentage <= 100:
        raise ValueError("percentage must be a built-in integer in [0, 100]")
    if type(L) is not int or L <= 0:
        raise ValueError("L must be a positive built-in integer")
    return percentage, L


def _require_input_layout(input_layout: object) -> str:
    if type(input_layout) is not str or input_layout not in SUPPORTED_INPUT_LAYOUTS:
        choices = ", ".join(sorted(SUPPORTED_INPUT_LAYOUTS))
        raise ValueError(f"input_layout must be one of: {choices}")
    return input_layout


def exp14_grid_height_for_width(L: int) -> int:
    """Return the historical exp14 ``ratio:auto, sat_margin:3`` grid height."""

    if type(L) is not int or L <= 0:
        raise ValueError("L must be a positive built-in integer")
    return int(round(L * math.ceil(3.0 * math.sqrt(L))))


def _require_regular_path(path: Path, *, label: str) -> None:
    try:
        file_stat = path.lstat()
    except OSError as error:
        raise ValueError(f"{label} is missing: {path}") from error
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"{label} is not a regular file: {path}")


def _stat_signature(file_stat: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_mode,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
    )


@contextmanager
def _open_regular_binary(path: Path, *, label: str) -> Iterator[BinaryIO]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError(f"{label} is missing or nonregular: {path}") from error
    try:
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            file_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"{label} is not a regular file: {path}")
            yield handle
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def resolve_ensemble_input(
    trace_root: str | os.PathLike[str],
    percentage: int,
    L: int,
    *,
    input_layout: str,
) -> EnsembleInput:
    """Resolve exactly one declared analysis input without layout fallback."""

    percentage, L = _require_cell_identity(percentage, L)
    layout = _require_input_layout(input_layout)
    root = Path(trace_root).resolve()
    if not root.is_dir():
        raise ValueError(f"trace root is not a directory: {root}")

    if layout == REDUCED_INPUT_LAYOUT:
        path = root / f"pct_{percentage:02d}" / f"L_{L:04d}.npz"
        managed = root / f"pct_{percentage:02d}" / f"L_{L:04d}"
        if not path.exists() and managed.is_dir():
            raise ValueError(
                "managed hierarchical raw runs are not direct analysis inputs; "
                "validate and reduce them with tetris_ballistic.scripts.reduce_traces"
            )
        _require_regular_path(path, label="reduced trace")
        seeds = _reduced_seed_inventory(path, percentage, L)
        return EnsembleInput(layout, root, percentage, L, (path,), seeds)

    pattern = (
        f"config_piece_19_combined_percentage_{percentage:02d}_"
        f"w={L}_seed=*.joblib"
    )
    entries: list[tuple[int, Path]] = []
    for path in root.glob(pattern):
        _require_regular_path(path, label="legacy trace")
        match = _LEGACY_FLAT_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"legacy trace name does not match the declared layout: {path}")
        observed_pct, observed_width, seed = map(int, match.groups())
        if (observed_pct, observed_width) != (percentage, L):
            raise ValueError(f"legacy trace identity does not match request: {path}")
        entries.append((seed, path))
    if not entries:
        managed = root / f"pct_{percentage:02d}" / f"L_{L:04d}"
        if managed.is_dir():
            raise ValueError(
                "managed hierarchical raw runs are not direct analysis inputs; "
                "validate and reduce them with tetris_ballistic.scripts.reduce_traces"
            )
        raise ValueError(
            f"no legacy-flat joblib inputs for pct={percentage}, L={L}: {root / pattern}"
        )
    entries.sort(key=lambda item: item[0])
    seeds = tuple(seed for seed, _path in entries)
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"duplicate legacy seed for pct={percentage}, L={L}")
    if any(seed < 0 or seed > 2**32 - 1 for seed in seeds):
        raise ValueError(f"legacy seed is outside [0, 2**32 - 1] for pct={percentage}, L={L}")
    return EnsembleInput(
        layout, root, percentage, L, tuple(path for _seed, path in entries), seeds
    )


def _read_npy_header(
    archive: zipfile.ZipFile, member: zipfile.ZipInfo, *, path: Path
) -> tuple[tuple[int, ...], np.dtype, bool, int]:
    """Parse one bounded NPY header without allocating its array payload."""

    try:
        with archive.open(member, "r") as source:
            if source.read(6) != b"\x93NUMPY":
                raise ValueError(f"reduced trace member is not NPY: {path}:{member.filename}")
            version = source.read(2)
            if len(version) != 2:
                raise ValueError(f"reduced trace NPY version is truncated: {path}")
            major = version[0]
            if major == 1:
                length_bytes = source.read(2)
                header_length = struct.unpack("<H", length_bytes)[0]
                encoding = "latin1"
                prefix_length = 10
            elif major in {2, 3}:
                length_bytes = source.read(4)
                header_length = struct.unpack("<I", length_bytes)[0]
                encoding = "utf-8" if major == 3 else "latin1"
                prefix_length = 12
            else:
                raise ValueError(f"unsupported reduced trace NPY version: {path}")
            if header_length <= 0 or header_length > _MAX_NPY_HEADER_BYTES:
                raise ValueError(f"reduced trace NPY header is outside the size limit: {path}")
            header_bytes = source.read(header_length)
            if len(header_bytes) != header_length:
                raise ValueError(f"reduced trace NPY header is truncated: {path}")
        header = ast.literal_eval(header_bytes.decode(encoding).strip())
    except ValueError:
        raise
    except (OSError, UnicodeError, struct.error, SyntaxError) as error:
        raise ValueError(f"reduced trace NPY header is invalid: {path}") from error
    if type(header) is not dict or set(header) != {"descr", "fortran_order", "shape"}:
        raise ValueError(f"reduced trace NPY header keys differ: {path}")
    shape = header["shape"]
    if (
        type(shape) is not tuple
        or any(type(dimension) is not int or dimension < 0 for dimension in shape)
    ):
        raise ValueError(f"reduced trace NPY shape is invalid: {path}")
    if type(header["fortran_order"]) is not bool:
        raise ValueError(f"reduced trace NPY order flag is invalid: {path}")
    try:
        dtype = np.dtype(header["descr"])
    except (TypeError, ValueError) as error:
        raise ValueError(f"reduced trace NPY dtype is invalid: {path}") from error
    if dtype.hasobject or dtype.fields is not None or dtype.subdtype is not None:
        raise ValueError(f"reduced trace NPY dtype is unsafe: {path}")
    data_bytes = math.prod(shape) * dtype.itemsize
    if member.file_size != prefix_length + header_length + data_bytes:
        raise ValueError(f"reduced trace NPY member size is inconsistent: {path}")
    return shape, dtype, header["fortran_order"], data_bytes


def _validate_reduced_archive_inventory(handle: BinaryIO, *, path: Path) -> None:
    try:
        with zipfile.ZipFile(handle) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            observed_names = set(names)
            expected_name_variants = tuple(
                {f"{name}.npy" for name in keys}
                for keys in _REDUCED_KEY_VARIANTS
            )
            if not any(
                len(members) == len(expected_names)
                and observed_names == expected_names
                for expected_names in expected_name_variants
            ):
                raise ValueError(f"reduced trace archive inventory differs: {path}")
            if len(names) != len(set(names)):
                raise ValueError(f"reduced trace archive has duplicate members: {path}")
            if any(
                member.is_dir()
                or member.flag_bits & 0x1
                or Path(member.filename).name != member.filename
                for member in members
            ):
                raise ValueError(f"reduced trace archive has unsafe members: {path}")
            total_size = sum(member.file_size for member in members)
            if total_size > _MAX_REDUCED_UNCOMPRESSED_BYTES:
                raise ValueError(
                    "reduced trace archive exceeds the uncompressed-size limit "
                    f"({_MAX_REDUCED_UNCOMPRESSED_BYTES} bytes): {path}"
                )
            headers = {
                member.filename.removesuffix(".npy"): _read_npy_header(
                    archive, member, path=path
                )
                for member in members
            }
            expected_dtypes = {
                "L": "<i4",
                "W": "<f4",
                "hbar": "<f4",
                "hbar_max": "<f4",
                "pct": "<i4",
                "saturated": "|b1",
            }
            if "height_grid" in headers:
                expected_dtypes["height_grid"] = "<i4"
            if any(
                headers[name][1].str != dtype
                or headers[name][2]
                for name, dtype in expected_dtypes.items()
            ) or any(
                headers[name][1].str not in {"<i4", "<i8"}
                or headers[name][2]
                for name in ("seeds", "final_steps")
            ):
                raise ValueError(f"reduced trace dtypes or array order differ: {path}")
            seed_shape = headers["seeds"][0]
            if (
                len(seed_shape) != 1
                or not 1 <= seed_shape[0] <= _MAX_ENSEMBLE_SEEDS
                or headers["final_steps"][0] != seed_shape
            ):
                raise ValueError(f"reduced trace seed metadata shapes are invalid: {path}")
            matrix_shape = headers["W"][0]
            if (
                len(matrix_shape) != 2
                or matrix_shape[0] != seed_shape[0]
                or not 2 <= matrix_shape[1] <= _MAX_TRACE_POINTS
                or headers["hbar"][0] != matrix_shape
            ):
                raise ValueError(f"reduced trace matrix headers are invalid: {path}")
            scalar_names = ["L", "hbar_max", "pct", "saturated"]
            if "height_grid" in headers:
                scalar_names.append("height_grid")
            if any(headers[name][0] != () for name in scalar_names):
                raise ValueError(f"reduced trace scalar headers are invalid: {path}")
            total_data_bytes = sum(header[3] for header in headers.values())
            if total_data_bytes > _MAX_REDUCED_UNCOMPRESSED_BYTES:
                raise ValueError(f"reduced trace arrays exceed the memory budget: {path}")
    except ValueError:
        raise
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"reduced trace archive is unreadable: {path}") from error
    finally:
        handle.seek(0)


def _validated_seed_values(seeds: np.ndarray, *, path: Path) -> tuple[int, ...]:
    if seeds.dtype.str not in {"<i4", "<i8"} or seeds.ndim != 1 or not seeds.size:
        raise ValueError(
            f"reduced trace seeds must be a nonempty int32 or int64 vector: {path}"
        )
    if seeds.size > _MAX_ENSEMBLE_SEEDS:
        raise ValueError(f"reduced trace has too many seeds: {path}")
    seed_values = tuple(int(seed) for seed in seeds.tolist())
    if (
        list(seed_values) != sorted(seed_values)
        or len(seed_values) != len(set(seed_values))
        or any(seed < 0 or seed > 2**32 - 1 for seed in seed_values)
    ):
        raise ValueError(f"reduced trace seeds are not a unique ordered inventory: {path}")
    return seed_values


def _validate_reduced_observable_rows(
    W_mat: np.ndarray,
    hbar_mat: np.ndarray,
    *,
    path: Path,
    height_grid: int | None,
) -> None:
    """Validate large trace matrices with fixed-size one-dimensional temporaries."""

    for row_index in range(W_mat.shape[0]):
        width_row = W_mat[row_index]
        height_row = hbar_mat[row_index]
        for start in range(0, width_row.size, _REDUCED_VALIDATION_CHUNK_POINTS):
            stop = min(start + _REDUCED_VALIDATION_CHUNK_POINTS, width_row.size)
            width_chunk = width_row[start:stop]
            height_chunk = height_row[start:stop]
            if not np.all(np.isfinite(width_chunk)) or not np.all(
                np.isfinite(height_chunk)
            ):
                raise ValueError(
                    f"reduced trace matrices contain nonfinite values: {path}"
                )
            if np.any(width_chunk < 0) or np.any(height_chunk < 0):
                raise ValueError(
                    f"reduced trace matrices contain negative observables: {path}"
                )
            if height_grid is not None and np.any(height_chunk > height_grid):
                raise ValueError(
                    f"corrected exp14 reduced trace height_grid is invalid: {path}"
                )
            if (
                start > 0 and height_row[start] < height_row[start - 1]
            ) or np.any(np.diff(height_chunk) < 0):
                raise ValueError(
                    "reduced trace mean-height observables must be "
                    f"nondecreasing: {path}"
                )


def _reduced_seed_inventory(path: Path, percentage: int, L: int) -> tuple[int, ...]:
    """Read the small identity fields without inflating trace matrices."""

    with _open_regular_binary(path, label="reduced trace") as handle:
        before = os.fstat(handle.fileno())
        _validate_reduced_archive_inventory(handle, path=path)
        try:
            with np.load(handle, allow_pickle=False) as trace:
                seeds = np.asarray(trace["seeds"])
                observed_pct = np.asarray(trace["pct"])
                observed_width = np.asarray(trace["L"])
        except Exception as error:
            raise ValueError(f"reduced trace identity cannot be decoded: {path}") from error
        after = os.fstat(handle.fileno())
    if _stat_signature(before) != _stat_signature(after):
        raise ValueError(f"reduced trace changed while its identity was decoded: {path}")
    if (
        observed_pct.shape != ()
        or not np.issubdtype(observed_pct.dtype, np.integer)
        or int(observed_pct.item()) != percentage
        or observed_width.shape != ()
        or not np.issubdtype(observed_width.dtype, np.integer)
        or int(observed_width.item()) != L
    ):
        raise ValueError(f"reduced trace identity does not match its requested cell: {path}")
    return _validated_seed_values(seeds, path=path)


def _load_reduced_ensemble(
    selected: EnsembleInput, percentage: int, L: int
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    path = selected.paths[0]
    with _open_regular_binary(path, label="reduced trace") as handle:
        before = os.fstat(handle.fileno())
        _validate_reduced_archive_inventory(handle, path=path)
        try:
            with np.load(handle, allow_pickle=False) as trace:
                trace_keys = set(trace.files)
                if not any(trace_keys == keys for keys in _REDUCED_KEY_VARIANTS):
                    raise ValueError(f"reduced trace keys differ: {path}")
                seeds = np.asarray(trace["seeds"])
                final_steps = np.asarray(trace["final_steps"])
                W_mat = np.asarray(trace["W"])
                hbar_mat = np.asarray(trace["hbar"])
                observed_pct = np.asarray(trace["pct"])
                observed_width = np.asarray(trace["L"])
                hbar_max = np.asarray(trace["hbar_max"])
                saturated = np.asarray(trace["saturated"])
                height_grid = (
                    np.asarray(trace["height_grid"])
                    if "height_grid" in trace_keys
                    else None
                )
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"reduced trace cannot be decoded: {path}") from error
        after = os.fstat(handle.fileno())
        if _stat_signature(before) != _stat_signature(after):
            raise ValueError(f"reduced trace changed while it was decoded: {path}")

    decoded_seeds = _validated_seed_values(seeds, path=path)
    if decoded_seeds != selected.seeds:
        raise ValueError(f"reduced trace seed inventory changed after resolution: {path}")
    if final_steps.dtype.str not in {"<i4", "<i8"} or final_steps.shape != seeds.shape:
        raise ValueError(
            "reduced trace final_steps must be an int32 or int64 vector matching "
            f"the seed inventory: {path}"
        )
    if W_mat.dtype != np.dtype("float32") or hbar_mat.dtype != np.dtype("float32"):
        raise ValueError(f"reduced trace W and hbar must use float32 dtype: {path}")
    if (
        W_mat.ndim != 2
        or W_mat.shape != hbar_mat.shape
        or W_mat.shape[0] != seeds.size
        or W_mat.shape[1] < 2
    ):
        raise ValueError(f"reduced trace matrices have invalid shapes: {path}")
    if np.any(final_steps <= 0) or int(np.min(final_steps)) != W_mat.shape[1]:
        raise ValueError(
            f"reduced trace length must equal min(final_steps): {path}"
        )
    observed_grid_height = None
    if height_grid is not None:
        expected_grid_height = exp14_grid_height_for_width(L)
        if (
            height_grid.shape != ()
            or height_grid.dtype != np.dtype("int32")
            or int(height_grid.item()) != expected_grid_height
        ):
            raise ValueError(
                f"corrected exp14 reduced trace height_grid is invalid: {path}"
            )
        observed_grid_height = expected_grid_height
    _validate_reduced_observable_rows(
        W_mat,
        hbar_mat,
        path=path,
        height_grid=observed_grid_height,
    )
    if observed_grid_height is not None:
        mean_hbar_start = float(np.mean(hbar_mat[:, 0]))
        mean_hbar_end = float(np.mean(hbar_mat[:, -1]))
        if not mean_hbar_start < 5.0 or not mean_hbar_end > mean_hbar_start:
            raise ValueError(
                f"corrected exp14 reduced trace height convention is invalid: {path}"
            )
    if (
        observed_pct.shape != ()
        or not np.issubdtype(observed_pct.dtype, np.integer)
        or int(observed_pct.item()) != percentage
        or observed_width.shape != ()
        or not np.issubdtype(observed_width.dtype, np.integer)
        or int(observed_width.item()) != L
    ):
        raise ValueError(f"reduced trace identity does not match its requested cell: {path}")
    if hbar_max.shape != () or not np.issubdtype(hbar_max.dtype, np.floating):
        raise ValueError(f"reduced trace hbar_max must be a floating scalar: {path}")
    observed_hbar_max = float(hbar_max.item())
    computed_hbar_max = float(np.mean(hbar_mat[:, -1]))
    if not np.isfinite(observed_hbar_max) or not np.isclose(
        observed_hbar_max, computed_hbar_max, rtol=1e-5, atol=1e-6
    ):
        raise ValueError(f"reduced trace hbar_max is invalid: {path}")
    if saturated.shape != () or saturated.dtype != np.dtype("bool"):
        raise ValueError(f"reduced trace saturated must be a boolean scalar: {path}")
    if bool(saturated.item()) != (observed_hbar_max >= L**1.5):
        raise ValueError(f"reduced trace saturation metadata is inconsistent: {path}")

    W_list = [np.ascontiguousarray(W_mat[index]) for index in range(seeds.size)]
    hbar_list = [np.ascontiguousarray(hbar_mat[index]) for index in range(seeds.size)]
    return W_list, hbar_list


def _load_legacy_flat_ensemble(
    selected: EnsembleInput,
    percentage: int,
    L: int,
    percentage_convention: str,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    W_list: list[np.ndarray] = []
    hbar_list: list[np.ndarray] = []
    for seed, path in zip(selected.seeds, selected.paths):
        try:
            with _open_regular_binary(path, label="legacy trace") as handle:
                before = os.fstat(handle.fileno())
                simulation = joblib.load(handle)
                after = os.fstat(handle.fileno())
                if _stat_signature(before) != _stat_signature(after):
                    raise ValueError(f"legacy trace changed while it was decoded: {path}")
        except ValueError:
            raise
        except Exception as error:
            raise ValueError(f"legacy joblib cannot be decoded: {path}") from error
        observed_width = getattr(simulation, "width", None)
        observed_seed = getattr(simulation, "seed", None)
        if type(observed_width) is not int or observed_width != L:
            raise ValueError(f"legacy trace embedded width does not match request: {path}")
        if type(observed_seed) is not int or observed_seed != seed:
            raise ValueError(f"legacy trace embedded seed does not match filename: {path}")
        config = getattr(simulation, "config_data", None)
        if type(config) is not dict:
            raise ValueError(f"legacy trace lacks a configuration mapping: {path}")
        if config.get("width") != L or config.get("seed") != seed:
            raise ValueError(f"legacy trace configuration identity is inconsistent: {path}")
        weights = []
        for piece in range(20):
            value = config.get(f"Piece-{piece}")
            if type(value) not in {list, tuple} or len(value) != 2:
                raise ValueError(f"legacy trace piece configuration is invalid: {path}")
            try:
                pair = (float(value[0]), float(value[1]))
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError(f"legacy trace piece weights are invalid: {path}") from error
            if not all(np.isfinite(item) and item >= 0 for item in pair):
                raise ValueError(f"legacy trace piece weights are invalid: {path}")
            if piece != 19 and pair != (0.0, 0.0):
                raise ValueError(f"legacy trace is not the piece-19 one-cell model: {path}")
            if piece == 19:
                weights = list(pair)
        total_weight = sum(weights)
        if total_weight <= 0:
            raise ValueError(f"legacy trace piece-19 weights are empty: {path}")
        if percentage_convention == "nonsticky-fraction":
            observed_fraction = weights[0] / total_weight
        elif percentage_convention == "sticky-fraction":
            observed_fraction = weights[1] / total_weight
        else:
            raise ValueError(
                "legacy-flat input requires percentage_convention to be "
                "'nonsticky-fraction' or 'sticky-fraction'"
            )
        if not np.isclose(observed_fraction, percentage / 100.0, rtol=0, atol=1e-12):
            raise ValueError(
                f"legacy trace percentage convention does not match configuration: {path}"
            )
        final_steps = getattr(simulation, "FinalSteps", None)
        if (
            not isinstance(final_steps, (int, np.integer))
            or isinstance(final_steps, (bool, np.bool_))
            or int(final_steps) < 2
        ):
            raise ValueError(f"legacy trace FinalSteps is invalid: {path}")
        n = int(final_steps)
        width_trace = np.asarray(getattr(simulation, "Fluctuation", None))
        height_trace = np.asarray(getattr(simulation, "AvergeHeight", None))
        if (
            width_trace.ndim != 1
            or height_trace.ndim != 1
            or width_trace.size < n
            or height_trace.size < n
            or not (
                np.issubdtype(width_trace.dtype, np.integer)
                or np.issubdtype(width_trace.dtype, np.floating)
            )
            or not (
                np.issubdtype(height_trace.dtype, np.integer)
                or np.issubdtype(height_trace.dtype, np.floating)
            )
        ):
            raise ValueError(f"legacy trace observables are invalid: {path}")
        width_trace = np.ascontiguousarray(width_trace[:n], dtype=float)
        height_trace = np.ascontiguousarray(height_trace[:n], dtype=float)
        if (
            not np.all(np.isfinite(width_trace))
            or not np.all(np.isfinite(height_trace))
            or np.any(width_trace < 0)
            or np.any(height_trace < 0)
        ):
            raise ValueError(f"legacy trace observables are nonfinite or negative: {path}")
        if np.any(np.diff(height_trace) < 0):
            raise ValueError(
                f"legacy trace mean-height observables must be nondecreasing: {path}"
            )
        W_list.append(width_trace)
        hbar_list.append(height_trace)
    return W_list, hbar_list

# ---------------------------------------------------------------------------
#  Step 1-2 — Data loading & ensemble construction
# ---------------------------------------------------------------------------

def load_ensemble(
    trace_root,
    percentage,
    L,
    *,
    input_layout=REDUCED_INPUT_LAYOUT,
    percentage_convention=None,
    resolved_input=None,
):
    """Load all seeds for one (percentage, L) cell.

    Implements **Step 2** (ensemble construction, Baiod et al. 1988: ≥10
    independent runs).

    Parameters
    ----------
    trace_root : str
        Root of one explicit trace layout. Managed hierarchical simulation
        outputs must first be validated and reduced with ``reduce_traces``.
    percentage : int
        Experiment percentage label (5, 50, 90, 95, 98, 99). In exp13 this
        denotes the nonsticky fraction; in exp14 it denotes the sticky
        fraction. Callers must preserve the experiment provenance.
    L : int
        Strip width (50, 80, 100, 150, 200).

    Returns
    -------
    W_list : list[ndarray]
        ``Fluctuation`` array per seed, trimmed to ``FinalSteps``.
    hbar_list : list[ndarray]
        ``AvergeHeight`` array per seed, trimmed to ``FinalSteps``.
    """
    percentage, L = _require_cell_identity(percentage, L)
    layout = _require_input_layout(input_layout)
    selected = resolved_input
    if selected is None:
        selected = resolve_ensemble_input(
            trace_root, percentage, L, input_layout=layout
        )
    if type(selected) is not EnsembleInput:
        raise ValueError("resolved_input must be an EnsembleInput")
    if (
        selected.layout != layout
        or selected.root != Path(trace_root).resolve()
        or selected.percentage != percentage
        or selected.L != L
    ):
        raise ValueError("resolved input does not match the requested root/layout")
    current = resolve_ensemble_input(
        trace_root, percentage, L, input_layout=layout
    )
    if current != selected:
        raise ValueError("analysis input inventory changed after it was resolved")
    if layout == REDUCED_INPUT_LAYOUT:
        result = _load_reduced_ensemble(selected, percentage, L)
    else:
        result = _load_legacy_flat_ensemble(
            selected, percentage, L, percentage_convention
        )
    if (
        resolve_ensemble_input(trace_root, percentage, L, input_layout=layout)
        != selected
    ):
        raise ValueError("analysis input inventory changed while it was loaded")
    return result


def truncate_to_common_length(arrays):
    """Truncate a list of 1-D arrays to the shortest length.

    Variable trace lengths arise because the simulation stops when the
    domain fills (``FinalSteps`` varies across seeds).

    Returns
    -------
    mat : ndarray, shape (n_arrays, min_len)
    min_len : int
    """
    min_len = min(len(a) for a in arrays)
    mat = np.empty((len(arrays), min_len))
    for i, a in enumerate(arrays):
        mat[i] = a[:min_len]
    return mat, min_len


def log_subsample_paired_traces(W_list, hbar_list, max_points=5000):
    """Align and log-subsample paired width/height traces.

    A single index array is applied to every seed and to both observables, so
    the deposited-height clock remains paired with its width measurement.
    Traces with at most ``max_points`` samples are unchanged.  Longer traces
    retain unique, ordered, approximately log-spaced samples including both
    endpoints.  Source dtypes are preserved.

    Returns
    -------
    W_ensemble, hbar_ensemble : ndarray
        Paired matrices with shape ``(n_seeds, n_analysis_points)``.
    original_common_len : int
        Minimum length across both observables and every seed.
    indices : ndarray
        Original trace indices retained for analysis.
    """
    if not W_list or not hbar_list:
        raise ValueError("W_list and hbar_list must be non-empty")
    if len(W_list) != len(hbar_list):
        raise ValueError("W_list and hbar_list must contain the same seeds")
    if max_points < 2:
        raise ValueError("max_points must be at least 2")

    original_common_len = min(
        min(len(trace) for trace in W_list),
        min(len(trace) for trace in hbar_list),
    )
    if original_common_len < 2:
        raise ValueError("traces must contain at least two paired samples")

    if original_common_len <= max_points:
        indices = np.arange(original_common_len, dtype=np.int64)
    else:
        # Reserve one strictly increasing index per requested point, then
        # distribute the remaining index range logarithmically.  This avoids
        # the duplicate-heavy rounding of geomspace on integer indices while
        # retaining dense early-time coverage and both endpoints.
        extra_range = original_common_len - max_points + 1
        log_offsets = np.rint(
            np.geomspace(1, extra_range, num=max_points) - 1
        ).astype(np.int64)
        indices = np.arange(max_points, dtype=np.int64) + log_offsets

    W_ensemble = np.stack([trace[indices] for trace in W_list])
    hbar_ensemble = np.stack([trace[indices] for trace in hbar_list])
    return W_ensemble, hbar_ensemble, original_common_len, indices


def growth_window_slope(W_ensemble, hbar_ensemble, L,
                        hbar_lo=10.0, n_boot=200, ci_level=0.95,
                        rng_seed=42):
    """OLS slope of log W vs log h̄ in the growth window h̄ ∈ [hbar_lo, L^{3/2}/2].

    The Family–Vicsek growth law is ``W ~ t^β`` with ``t`` = the *deposited
    height* h̄ (number of deposited layers), **not** the raw deposition-step
    index.  Lateral sticking and void creation make mean height nonlinear in
    deposited-particle count during the transient, so the growth exponent MUST
    be measured against log h̄.
    See the SPDEs-wiki project page, "Findings 2026-07-11", Finding 2.

    Avoids both the early transient (h̄ < ``hbar_lo`` lattice units) and the
    saturation tail (h̄ > L^{3/2}/2).  Case-resampling bootstrap CI over
    independent runs.

    Returns
    -------
    beta : float — central slope estimate (dlogW / dlog h̄)
    ci_lo, ci_hi : float — bootstrap CI bounds
    """
    hbar_hi = 0.5 * L ** 1.5
    mean_W = np.mean(W_ensemble, axis=0)
    mean_hbar = np.mean(hbar_ensemble, axis=0)
    mask = (mean_hbar >= hbar_lo) & (mean_hbar <= hbar_hi) & (mean_W > 0)
    if mask.sum() < 10:
        mask = (mean_hbar >= hbar_lo) & (mean_W > 0)
    if mask.sum() < 5:
        return np.nan, np.nan, np.nan

    def _fit(w_arr, h_arr):
        # Regress log W against log h̄ (the physically correct time axis),
        # NOT against the deposition-step index.
        w_pos = np.maximum(w_arr, 1e-30)
        h_pos = np.maximum(h_arr, 1e-30)
        return linregress(
            np.log10(h_pos[mask]), np.log10(w_pos[mask])
        ).slope

    beta_center = _fit(mean_W, mean_hbar)

    n_runs = W_ensemble.shape[0]
    rng = np.random.default_rng(rng_seed)
    boot_betas = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        boot_betas[b] = _fit(
            np.mean(W_ensemble[idx], axis=0),
            np.mean(hbar_ensemble[idx], axis=0),
        )

    alpha = 1.0 - ci_level
    ci_lo = float(np.percentile(boot_betas, 100 * alpha / 2))
    ci_hi = float(np.percentile(boot_betas, 100 * (1 - alpha / 2)))
    return float(beta_center), ci_lo, ci_hi


# ---------------------------------------------------------------------------
#  Step 3 — Local-slope curve with bootstrap CI
# ---------------------------------------------------------------------------

def local_slope_bootstrap(W_ensemble, hbar_ensemble, n_eval=200,
                          log_half_width=0.5, n_boot=500, ci_level=0.95,
                          rng_seed=42):
    """Effective growth exponent β_eff(h̄) = dlogW / dlog h̄ with bootstrap CI.

    The independent variable is the deposited height h̄ (Family–Vicsek time
    variable), evaluated on the ensemble-mean h̄ trajectory.  Regressing
    against the deposition-step index instead would contaminate the exponent
    with the transient (see project page, Finding 2).  The effective-exponent
    idea is Wolf–Kertész (1987); the case-resampling bootstrap over independent
    runs follows the Wendt–Abry–Jaffard (2007) philosophy.

    Parameters
    ----------
    W_ensemble : ndarray, shape (n_runs, T)
        Interface width W per run (per deposition step).
    hbar_ensemble : ndarray, shape (n_runs, T)
        Mean height h̄ per run (per deposition step).
    n_eval : int
        Number of log-spaced evaluation points in h̄ (default 200).
    log_half_width : float
        Half-width of the sliding log10(h̄) window in decades (default 0.5).
    n_boot : int
        Bootstrap replicates (default 500).
    ci_level : float
        Confidence level (default 0.95).
    rng_seed : int
        Reproducibility seed.

    Returns
    -------
    eval_log_hbar : ndarray — log10 h̄ evaluation points
    slope_med     : ndarray — median bootstrap β_eff
    slope_lo      : ndarray — lower CI bound
    slope_hi      : ndarray — upper CI bound
    """
    n_runs = W_ensemble.shape[0]
    mean_hbar_full = np.maximum(np.mean(hbar_ensemble, axis=0), 1e-30)
    log_hbar = np.log10(mean_hbar_full)

    lo = np.searchsorted(log_hbar, log_hbar[0] + 0.05, side="left")
    lo = max(lo, 2)
    hi = len(log_hbar) - 1
    eval_log_hbar = np.linspace(log_hbar[lo], log_hbar[hi], n_eval)
    n_pts = len(eval_log_hbar)

    win_lo_idx = np.searchsorted(
        log_hbar, eval_log_hbar - log_half_width, side="left"
    )
    win_hi_idx = np.searchsorted(
        log_hbar, eval_log_hbar + log_half_width, side="right"
    )

    rng = np.random.default_rng(rng_seed)

    def _slopes(log_W, log_h):
        slopes = np.full(n_pts, np.nan)
        for k in range(n_pts):
            a, b = win_lo_idx[k], win_hi_idx[k]
            if b - a < 5:
                continue
            x = log_h[a:b]
            y = log_W[a:b]
            if np.ptp(y) < 1e-12 or np.ptp(x) < 1e-12:
                continue
            n = b - a
            sx = x.sum()
            sy = y.sum()
            sxx = (x * x).sum()
            sxy = (x * y).sum()
            denom = n * sxx - sx * sx
            if abs(denom) < 1e-30:
                continue
            slopes[k] = (n * sxy - sx * sy) / denom
        return slopes

    mean_W = np.maximum(np.mean(W_ensemble, axis=0), 1e-30)
    _ = _slopes(np.log10(mean_W), log_hbar)

    boot_slopes = np.empty((n_boot, n_pts))
    for b in range(n_boot):
        idx = rng.choice(n_runs, size=n_runs, replace=True)
        bW = np.maximum(np.mean(W_ensemble[idx], axis=0), 1e-30)
        bH = np.maximum(np.mean(hbar_ensemble[idx], axis=0), 1e-30)
        boot_slopes[b] = _slopes(np.log10(bW), np.log10(bH))

    alpha = 1.0 - ci_level
    slope_lo = np.nanpercentile(boot_slopes, 100 * alpha / 2, axis=0)
    slope_hi = np.nanpercentile(boot_slopes, 100 * (1 - alpha / 2), axis=0)
    slope_med = np.nanmedian(boot_slopes, axis=0)

    return eval_log_hbar, slope_med, slope_lo, slope_hi


# ---------------------------------------------------------------------------
#  Step 4 — Automatic plateau detection (the one genuinely new piece)
# ---------------------------------------------------------------------------

def detect_plateau(eval_log_hbar, slope_med, slope_lo, slope_hi,
                   deriv_thresh=0.05, ci_width_thresh=0.15,
                   min_log_extent=0.4, log_hbar_lo=None, log_hbar_hi=None):
    """Algorithmic plateau detector for the β_eff(h̄) curve.

    The abscissa is log₁₀ h̄ (deposited height), matching
    :func:`local_slope_bootstrap`.  Finds the longest contiguous h̄ range where:
      (a) |dβ_eff / dlog h̄| < *deriv_thresh*,
      (b) CI width (hi − lo) < *ci_width_thresh*,
      (c) log-extent ≥ *min_log_extent* decades,
      (d) h̄ lies inside the growth window [log_hbar_lo, log_hbar_hi].

    Restricting to the growth window (d) is essential: without an upper bound
    at ≈½L^{3/2} the detector otherwise locks onto the steep early-transient
    flat (β≈0.5) that precedes the true KPZ regime — the classic false-plateau
    failure mode (project page, Finding 2).

    Parameters
    ----------
    eval_log_hbar, slope_med, slope_lo, slope_hi : ndarray
        Output of :func:`local_slope_bootstrap`.
    deriv_thresh : float
        Maximum absolute slope-derivative to qualify as "flat".
    ci_width_thresh : float
        Maximum CI width (slope_hi − slope_lo).
    min_log_extent : float
        Minimum plateau extent in decades of log₁₀ h̄.
    log_hbar_lo, log_hbar_hi : float or None
        Growth-window bounds in log₁₀ h̄.  ``None`` disables that bound.

    Returns
    -------
    tuple (plateau_mask, plateau_beta, (ci_lo, ci_hi))
        or *None* if no plateau is found.
    """
    eval_log_t = eval_log_hbar
    valid = ~np.isnan(slope_med)
    if valid.sum() < 5:
        return None

    d_slope = np.gradient(slope_med, eval_log_t)
    ci_width = slope_hi - slope_lo

    in_window = np.ones_like(eval_log_t, dtype=bool)
    if log_hbar_lo is not None:
        in_window &= eval_log_t >= log_hbar_lo
    if log_hbar_hi is not None:
        in_window &= eval_log_t <= log_hbar_hi

    candidate = (
        valid
        & in_window
        & (np.abs(d_slope) < deriv_thresh)
        & (ci_width < ci_width_thresh)
    )

    # Find longest contiguous qualifying run
    best_start, best_end, best_extent = -1, -1, 0.0
    i = 0
    while i < len(candidate):
        if candidate[i]:
            j = i
            while j < len(candidate) and candidate[j]:
                j += 1
            extent = eval_log_t[j - 1] - eval_log_t[i]
            if extent >= min_log_extent and extent > best_extent:
                best_start, best_end, best_extent = i, j, extent
            i = j
        else:
            i += 1

    if best_start < 0:
        return None

    plateau_mask = np.zeros(len(eval_log_t), dtype=bool)
    plateau_mask[best_start:best_end] = True

    plateau_beta = float(np.nanmedian(slope_med[plateau_mask]))
    plateau_lo = float(np.nanmedian(slope_lo[plateau_mask]))
    plateau_hi = float(np.nanmedian(slope_hi[plateau_mask]))

    return plateau_mask, plateau_beta, (plateau_lo, plateau_hi)


# ---------------------------------------------------------------------------
#  Step 5 — Meakin (1986) range-of-fit cross-validation
# ---------------------------------------------------------------------------

def meakin_range_of_fit(W_ensemble, hbar_ensemble):
    """Two-window cross-validation per Meakin et al. (1986).

    Fit ln W vs ln h̄ on two non-overlapping windows:
      * Window 1: h̄ ∈ [0.01 h_max, 0.1 h_max]
      * Window 2: h̄ ∈ [0.1 h_max, h_max]

    Agreement within SE is a sanity check that the asymptotic regime
    has been reached.

    Returns
    -------
    (slope1, se1), (slope2, se2) : tuple of tuples
    """
    mean_W = np.mean(W_ensemble, axis=0)
    mean_hbar = np.mean(hbar_ensemble, axis=0)

    pos = (mean_W > 0) & (mean_hbar > 0)
    log_W = np.log10(mean_W[pos])
    log_h = np.log10(mean_hbar[pos])
    h = mean_hbar[pos]
    h_max = h[-1]

    results = {}
    windows = {
        "window1": (h >= 0.01 * h_max) & (h <= 0.1 * h_max),
        "window2": (h >= 0.1 * h_max) & (h <= h_max),
    }
    for name, mask in windows.items():
        if mask.sum() < 5:
            results[name] = (np.nan, np.nan)
        else:
            s = linregress(log_h[mask], log_W[mask])
            results[name] = (s.slope, s.stderr)

    return results["window1"], results["window2"]


# ---------------------------------------------------------------------------
#  Step 6 — Multi-L corrections-to-scaling extrapolation
# ---------------------------------------------------------------------------

def extrapolate_to_infinity(L_array, beta_array, beta_err_array):
    """Corrections-to-scaling fit: β_eff(L) = β_∞ + c · L^{-ω}.

    Per Meakin et al. (1986) + Wegner (1972) correction ansatz,
    refined by Pagnani & Parisi (2013).

    Parameters
    ----------
    L_array : ndarray
        Strip widths.
    beta_array : ndarray
        Effective β per L (from plateau detection).
    beta_err_array : ndarray
        Uncertainty on β per L.

    Returns
    -------
    beta_inf : float
    beta_inf_err : float
    popt : tuple (beta_inf, c, omega) or None
    pcov : ndarray or None
    """
    valid = ~np.isnan(beta_array)
    L = L_array[valid].astype(float)
    beta = beta_array[valid]
    sigma = np.maximum(beta_err_array[valid], 1e-6)

    if len(L) < 2:
        w = 1.0 / sigma ** 2
        beta_inf = float(np.average(beta, weights=w))
        beta_inf_err = float(1.0 / np.sqrt(w.sum()))
        return beta_inf, beta_inf_err, None, None

    def model_3p(x, beta_inf, c, omega):
        return beta_inf + c * x ** (-omega)

    def model_2p(x, beta_inf, c):
        return beta_inf + c * x ** (-0.5)

    def _is_sane(popt, pcov):
        beta_inf, err = popt[0], np.sqrt(pcov[0, 0])
        return -1 < beta_inf < 2 and err < 1.0

    # Try 3-parameter fit if ≥4 points
    if len(L) >= 4:
        try:
            popt, pcov = curve_fit(
                model_3p, L, beta, p0=[0.33, -0.5, 0.5],
                sigma=sigma, absolute_sigma=True, maxfev=10000,
            )
            if _is_sane(popt, pcov):
                return float(popt[0]), float(np.sqrt(pcov[0, 0])), popt, pcov
        except Exception:
            pass

    # Fallback: 2-parameter fit with ω fixed at 0.5 (standard BD correction)
    try:
        popt2, pcov2 = curve_fit(
            model_2p, L, beta, p0=[0.33, -0.5],
            sigma=sigma, absolute_sigma=True, maxfev=10000,
        )
        popt_full = np.array([popt2[0], popt2[1], 0.5])
        pcov_full = np.zeros((3, 3))
        pcov_full[:2, :2] = pcov2
        return float(popt2[0]), float(np.sqrt(pcov2[0, 0])), popt_full, pcov_full
    except Exception:
        pass

    w = 1.0 / sigma ** 2
    beta_inf = float(np.average(beta, weights=w))
    beta_inf_err = float(1.0 / np.sqrt(w.sum()))
    return beta_inf, beta_inf_err, None, None
