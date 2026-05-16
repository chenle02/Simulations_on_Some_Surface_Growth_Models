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

Resume: if the output joblib already exists, exit 0 silently.

Grid spec (YAML):
    piece_config: piece_19_combined_percentage_{pct}  # template; {pct} substituted
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
import os
import sys
from pathlib import Path

import joblib
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))
from tetris_ballistic.tetris_ballistic import Tetris_Ballistic


def load_grid_spec(path: str) -> dict:
    """Read and validate the grid.yaml describing the (pct, L, seed) sweep."""
    with open(path) as f:
        spec = yaml.safe_load(f)
    required = {"piece_config", "pcts", "widths", "seeds"}
    missing = required - set(spec.keys())
    if missing:
        raise ValueError(f"grid spec {path} missing required keys: {missing}")
    spec.setdefault("ratio", 10)
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

    Currently supports the piece_19_combined_percentage_{pct} pattern
    used in exp13: all pieces are [0,0] except Piece-19 = [100-pct, pct].
    Extend this when new piece-config templates are added.
    """
    piece_config = spec["piece_config"]
    if piece_config == "piece_19_combined" or piece_config.startswith("piece_19_combined_percentage"):
        density = {f"Piece-{i}": [0, 0] for i in range(20)}
        density["Piece-19"] = [100 - pct, pct]
        return density
    raise NotImplementedError(
        f"piece_config={piece_config!r} not yet supported. "
        f"Extend build_density() in tetris_ballistic/scripts/run_one_cell.py."
    )


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


def run_cell(spec: dict, pct: int, L: int, seed: int, out_dir: str,
             flat: bool = False) -> Path:
    """Run one cell. Returns the joblib output path. Idempotent if file exists."""
    joblib_path, yaml_path = cell_output_paths(
        out_dir, pct, L, seed, flat=flat, basename=spec.get("output_basename")
    )
    joblib_path.parent.mkdir(parents=True, exist_ok=True)

    if joblib_path.exists():
        print(f"[skip] {joblib_path} already exists", flush=True)
        return joblib_path

    ratio = spec["ratio"]
    height = L * ratio
    steps = ratio * L * L
    density = build_density(spec, pct)

    print(
        f"[run ] pct={pct} L={L} seed={seed} "
        f"height={height} steps={steps} → {joblib_path}",
        flush=True,
    )
    tb = Tetris_Ballistic(
        width=L, height=height, steps=steps, seed=seed, density=density
    )
    tb.Simulate()

    snapshot_path = str(joblib_path) + ".tmp"
    joblib.dump(tb, snapshot_path)
    os.replace(snapshot_path, joblib_path)
    tb.save_config(str(yaml_path))
    return joblib_path


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
