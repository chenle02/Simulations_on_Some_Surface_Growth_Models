#!/usr/bin/env python3
"""Run ONE simulation cell from a flat task index.

This is the Slurm-array entry point. Each Slurm array task invokes
this with --task-id = $SLURM_ARRAY_TASK_ID, which is decoded against
the experiment's grid.yaml to determine (piece_config, pct, L, seed).

Output convention (hierarchical, HPC-friendly):
    <out-dir>/pct_{pct:02d}/L_{L:04d}/seed_{seed:03d}.joblib
    <out-dir>/pct_{pct:02d}/L_{L:04d}/seed_{seed:03d}.yaml

Or, with --flat-output, the legacy exp13 layout:
    <out-dir>/{config_basename}_w={L}_seed={seed}.joblib

Resume: reuse only a complete identity/checksum-validated managed bundle.

Grid spec (YAML):
    piece_config: piece_19_combined_percentage
    pcts: [5, 50, 90, 95, 98, 99]
    widths: [50, 80, 100, 150, 200]
    seeds: [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    ratio: 10                # height = L * ratio, steps = ratio * L * L

Usage:
    # Local single task
    python -m tetris_ballistic.scripts.run_one_cell \\
        --task-id 0 --grid-spec experiments/exp14/grid.yaml \\
        --out-dir experiments/exp14/results

    # Slurm array (see experiments/templates/job_array.slurm)
"""

from __future__ import annotations

import argparse
import math
import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.run_artifacts import (
    RunArtifactResult,
    execute_managed_run,
    resolve_engine_route,
)
from tetris_ballistic.tetris_ballistic import _UniqueKeySafeLoader

_GRID_KEYS = frozenset(
    {
        "output_basename",
        "pcts",
        "piece_config",
        "ratio",
        "ratios",
        "sat_margin",
        "seeds",
        "widths",
    }
)
_SUPPORTED_PIECE_CONFIGS = frozenset(
    {"piece_19_combined", "piece_19_combined_percentage"}
)
MAX_GRID_SPEC_BYTES = 1_000_000


@dataclass(frozen=True)
class CellRequest:
    joblib_path: Path
    config_path: Path
    width: int
    height: int
    steps: int
    seed: int
    density: dict[str, list[int]]
    engine_route: str
    semantic_context: dict[str, object]


def _unique_int_list(value: object, *, name: str, minimum: int, maximum: int) -> list[int]:
    if type(value) is not list or not value:
        raise ValueError(f"grid {name} must be a nonempty built-in list")
    if any(type(item) is not int or not minimum <= item <= maximum for item in value):
        raise ValueError(f"grid {name} entries must be integers in [{minimum}, {maximum}]")
    if len(value) != len(set(value)):
        raise ValueError(f"grid {name} entries must be unique")
    return value


def _positive_finite_number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"grid {name} must be finite and positive")
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueError(f"grid {name} must be finite and positive")
    return numeric


def validate_grid_spec(spec: object) -> dict:
    """Return a validated grid snapshot with no duplicate cell identities."""

    if type(spec) is not dict:
        raise ValueError("grid spec must be a built-in mapping")
    required = {"piece_config", "pcts", "widths", "seeds"}
    missing = required - set(spec)
    unexpected = set(spec) - _GRID_KEYS
    if missing or unexpected:
        raise ValueError(
            f"grid spec keys differ: missing={sorted(missing)}, unexpected={sorted(unexpected)}"
        )
    piece_config = spec["piece_config"]
    if type(piece_config) is not str or piece_config not in _SUPPORTED_PIECE_CONFIGS:
        raise ValueError(f"unsupported grid piece_config: {piece_config!r}")
    pcts = _unique_int_list(spec["pcts"], name="pcts", minimum=0, maximum=100)
    widths = _unique_int_list(spec["widths"], name="widths", minimum=1, maximum=2**31 - 1)
    seeds = _unique_int_list(spec["seeds"], name="seeds", minimum=0, maximum=2**32 - 1)

    validated = dict(spec)
    ratio = validated.get("ratio", 10)
    if isinstance(ratio, str):
        if ratio != "auto":
            raise ValueError("grid ratio string must be exactly 'auto'")
    else:
        validated["ratio"] = _positive_finite_number(ratio, name="ratio")
    if "sat_margin" in validated:
        validated["sat_margin"] = _positive_finite_number(
            validated["sat_margin"], name="sat_margin"
        )
    if "ratios" in validated:
        ratios = validated["ratios"]
        if type(ratios) is not dict or not ratios:
            raise ValueError("grid ratios must be a nonempty built-in mapping")
        if any(type(width) is not int or width not in widths for width in ratios):
            raise ValueError("grid ratios keys must be declared built-in integer widths")
        validated["ratios"] = {
            width: _positive_finite_number(value, name=f"ratios[{width}]")
            for width, value in ratios.items()
        }
    if "output_basename" in validated:
        basename = validated["output_basename"]
        if (
            type(basename) is not str
            or not basename
            or basename in {".", ".."}
            or Path(basename).name != basename
        ):
            raise ValueError("grid output_basename must be one safe path component")
        if len(pcts) != 1:
            raise ValueError("grid output_basename would collide across multiple pcts")
    validated["pcts"] = list(pcts)
    validated["widths"] = list(widths)
    validated["seeds"] = list(seeds)
    validated.setdefault("ratio", 10.0)
    return validated


def load_grid_spec_snapshot(path: str | os.PathLike[str]) -> tuple[dict, bytes]:
    """Read one regular grid snapshot and validate those exact bytes."""

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError(f"grid spec {path} is missing or nonregular") from error
    try:
        with os.fdopen(descriptor, "rb") as handle:
            file_stat = os.fstat(handle.fileno())
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"grid spec {path} is not a regular file")
            if file_stat.st_size > MAX_GRID_SPEC_BYTES:
                raise ValueError(f"grid spec {path} exceeds {MAX_GRID_SPEC_BYTES} bytes")
            payload = handle.read(MAX_GRID_SPEC_BYTES + 1)
        text = payload.decode("utf-8")
        spec = yaml.load(text, Loader=_UniqueKeySafeLoader)
    except UnicodeError as error:
        raise ValueError(f"grid spec {path} is not valid UTF-8") from error
    except yaml.YAMLError as error:
        raise ValueError(f"grid spec {path} contains invalid YAML") from error
    return validate_grid_spec(spec), payload


def load_grid_spec(path: str) -> dict:
    """Read and validate the grid.yaml describing the (pct, L, seed) sweep."""

    spec, _payload = load_grid_spec_snapshot(path)
    return spec


def grid_size(spec: dict) -> int:
    return len(spec["pcts"]) * len(spec["widths"]) * len(spec["seeds"])


def decode_task_id(task_id: int, spec: dict) -> tuple[int, int, int]:
    """Map a flat task ID to (pct, L, seed).

    Iteration order: pct outermost, then L, then seed innermost.
    This keeps consecutive task IDs in the same (pct, L) ensemble,
    so a small array (e.g. --array=0-9) gives one complete ensemble.
    """
    pcts = spec["pcts"]
    widths = spec["widths"]
    seeds = spec["seeds"]
    total = len(pcts) * len(widths) * len(seeds)
    if not (0 <= task_id < total):
        raise IndexError(f"task_id {task_id} out of range [0, {total})")
    per_pct = len(widths) * len(seeds)
    pct_idx, rem = divmod(task_id, per_pct)
    L_idx, seed_idx = divmod(rem, len(seeds))
    return pcts[pct_idx], widths[L_idx], seeds[seed_idx]


def build_density(spec: dict, pct: int) -> dict:
    """Construct the Piece-density dict for a given pct.

    Currently supports the exp14/exp15 sticky-fraction convention: all pieces
    are [0,0] except Piece-19 = [100-pct, pct], with state order
    [nonsticky, sticky]. Extend this when new templates are added.
    """
    piece_config = spec["piece_config"]
    if piece_config in _SUPPORTED_PIECE_CONFIGS:
        density = {f"Piece-{i}": [0, 0] for i in range(20)}
        density["Piece-19"] = [100 - pct, pct]
        return density
    raise NotImplementedError(
        f"piece_config={piece_config!r} not yet supported. "
        f"Extend build_density() in tetris_ballistic/scripts/run_one_cell.py."
    )


def ratio_for_L(spec: dict, L: int) -> float:
    """Depth ratio (height = ratio*L, steps = ratio*L^2) for width ``L``.

    Saturation requires height ≳ L^{3/2}, i.e. ratio ≳ k·sqrt(L).  A single
    scalar ``ratio`` therefore leaves wide L under-saturated, so the grid may
    instead give per-L control:

    - ``ratios: {50: 21, 100: 30, ...}``  — explicit per-width mapping;
    - ``ratio: auto`` with ``sat_margin: k`` — ratio = ceil(k·sqrt(L)) so every
      width saturates with margin ``k`` (default k=3);
    - ``ratio: <number>``  — legacy single scalar (back-compatible).
    """
    ratios = spec.get("ratios")
    if ratios is not None and L in ratios:
        return float(ratios[L])
    r = spec.get("ratio", 10)
    if isinstance(r, str) and r.lower() == "auto":
        k = float(spec.get("sat_margin", 3.0))
        return float(math.ceil(k * math.sqrt(L)))
    return float(r)


def cell_output_paths(out_dir: str, pct: int, L: int, seed: int,
                      flat: bool = False, basename: str | None = None) -> tuple[Path, Path]:
    """Resolve the (joblib, yaml-config-snapshot) output paths."""
    out_root = Path(out_dir)
    if flat:
        bn = basename or f"config_pct{pct:02d}"
        return (
            out_root / f"{bn}_w={L}_seed={seed}.joblib",
            out_root / f"{bn}_w={L}_seed={seed}.yaml",
        )
    cell_dir = out_root / f"pct_{pct:02d}" / f"L_{L:04d}"
    return (
        cell_dir / f"seed_{seed:03d}.joblib",
        cell_dir / f"seed_{seed:03d}.yaml",
    )


def prepare_cell_request(
    spec: dict,
    pct: int,
    L: int,
    seed: int,
    out_dir: str,
    *,
    flat: bool = False,
) -> CellRequest:
    """Resolve and canonicalize one grid-declared managed cell request."""

    spec = validate_grid_spec(spec)
    if pct not in spec["pcts"] or L not in spec["widths"] or seed not in spec["seeds"]:
        raise ValueError("requested cell is not declared by the validated grid")
    joblib_path, config_path = cell_output_paths(
        out_dir, pct, L, seed, flat=flat, basename=spec.get("output_basename")
    )
    ratio = ratio_for_L(spec, L)
    height = int(round(L * ratio))
    steps = int(round(ratio * L * L))
    density = build_density(spec, pct)
    return CellRequest(
        joblib_path=joblib_path,
        config_path=config_path,
        width=L,
        height=height,
        steps=steps,
        seed=seed,
        density=density,
        engine_route=resolve_engine_route(density),
        semantic_context={
            "percentage": pct,
            "percentage_semantics": "sticky_fraction_pct",
            "piece_config": spec["piece_config"],
            "producer": "run_one_cell-v1",
        },
    )


def run_cell(spec: dict, pct: int, L: int, seed: int, out_dir: str,
             flat: bool = False) -> Path:
    """Run or validate/reuse one managed cell and return its joblib path."""
    return run_cell_result(spec, pct, L, seed, out_dir, flat=flat).path


def run_cell_result(
    spec: dict,
    pct: int,
    L: int,
    seed: int,
    out_dir: str,
    flat: bool = False,
) -> RunArtifactResult:
    """Run one cell and return its explicit CREATED/REUSED disposition."""

    request = prepare_cell_request(spec, pct, L, seed, out_dir, flat=flat)
    result = execute_managed_run(
        joblib_path=request.joblib_path,
        config_path=request.config_path,
        width=request.width,
        height=request.height,
        steps=request.steps,
        seed=request.seed,
        density=request.density,
        engine_route=request.engine_route,
        semantic_context=request.semantic_context,
        on_start=lambda: print(
            f"[run ] pct={pct} L={L} seed={seed} "
            f"height={request.height} steps={request.steps} → {request.joblib_path}",
            flush=True,
        ),
    )
    if result.reused:
        print(f"[skip] {request.joblib_path} verified and complete", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--task-id", type=int, help="Slurm array task index (0-based)")
    g.add_argument("--pct", type=int, help="Explicit (pct, L, seed) — requires --L and --seed")
    g.add_argument("--list-grid", action="store_true", help="Print the full grid and exit")
    parser.add_argument("--L", type=int, help="With --pct")
    parser.add_argument("--seed", type=int, help="With --pct")
    parser.add_argument("--grid-spec", required=True, help="Path to grid.yaml")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    parser.add_argument("--flat-output", action="store_true",
                        help="Legacy exp13 flat output layout (instead of pct_NN/L_LLLL/seed_SSS)")
    args = parser.parse_args()

    spec = load_grid_spec(args.grid_spec)

    if args.list_grid:
        total = grid_size(spec)
        print(f"Grid size: {total} cells")
        for tid in range(total):
            p, L, s = decode_task_id(tid, spec)
            print(f"  task {tid:5d} → pct={p:2d} L={L:4d} seed={s:3d}")
        return

    if args.task_id is not None:
        pct, L, seed = decode_task_id(args.task_id, spec)
    else:
        if args.L is None or args.seed is None:
            sys.exit("--pct requires --L and --seed")
        pct, L, seed = args.pct, args.L, args.seed

    run_cell(spec, pct, L, seed, args.out_dir, flat=args.flat_output)


if __name__ == "__main__":
    main()
