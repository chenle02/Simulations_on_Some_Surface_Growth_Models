#!/usr/bin/env python3
"""Reduce raw ``.joblib`` runs to compact ``(W, h̄)`` trace archives.

Each ``Tetris_Ballistic`` joblib carries the full L×H final substrate image
(~3 MB) on top of the two 1-D arrays the slope analysis actually needs:
``Fluctuation`` (interface width W) and ``AvergeHeight`` (mean height h̄).
This tool extracts just those two arrays, as ``float32``, and packs all seeds
of one (pct, L) ensemble into a single compressed ``.npz`` — roughly 4× smaller
than the joblib and reanalysis-complete.  These reduced traces are the durable,
git-committable, hash-pinnable input to *any* (present or revised) exponent
estimator, so the slope method can be re-run without re-simulating.

Input layouts (auto-detected):
  hierarchical:  <in>/pct_{pct:02d}/L_{L:04d}/seed_{seed:03d}.joblib
  flat (exp13):  <in>/config_..._percentage_{pct:02d}_w={L}_seed={seed}.joblib

Output:
  <out>/pct_{pct:02d}/L_{L:04d}.npz   with arrays:
      seeds       int32   (n_seeds,)
      final_steps int32   (n_seeds,)
      W           float32 (n_seeds, T_min)   interface width per step
      hbar        float32 (n_seeds, T_min)   mean height per step
  and scalar metadata: pct, L, hbar_max, saturated (h̄_max ≥ L^{3/2}).

Usage:
    python -m tetris_ballistic.scripts.reduce_traces \\
        --in experiments/exp13 --out <data-repo>/traces/exp13
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import defaultdict

import joblib
import numpy as np

_FLAT_RE = re.compile(r"percentage_(\d+)_w=(\d+)_seed=(\d+)\.joblib$")
_HIER_RE = re.compile(r"pct_(\d+)/L_(\d+)/seed_(\d+)\.joblib$")


def discover(in_dir: str) -> dict[tuple[int, int], list[tuple[int, str]]]:
    """Map (pct, L) -> list of (seed, joblib_path), across both layouts."""
    cells: dict[tuple[int, int], list[tuple[int, str]]] = defaultdict(list)
    for path in glob.glob(os.path.join(in_dir, "**", "*.joblib"), recursive=True):
        m = _HIER_RE.search(path) or _FLAT_RE.search(path)
        if not m:
            continue
        pct, L, seed = (int(m.group(i)) for i in (1, 2, 3))
        cells[(pct, L)].append((seed, path))
    for key in cells:
        cells[key].sort()
    return cells


def reduce_cell(seed_paths: list[tuple[int, str]], L: int):
    seeds, finals, w_list, h_list = [], [], [], []
    for seed, path in seed_paths:
        obj = joblib.load(path)
        n = int(obj.FinalSteps)
        seeds.append(seed)
        finals.append(n)
        w_list.append(np.asarray(obj.Fluctuation[:n], dtype=np.float32))
        h_list.append(np.asarray(obj.AvergeHeight[:n], dtype=np.float32))
    t_min = min(len(a) for a in w_list)
    W = np.stack([a[:t_min] for a in w_list])
    H = np.stack([a[:t_min] for a in h_list])
    hbar_max = float(H.mean(axis=0)[-1])
    return {
        "seeds": np.asarray(seeds, dtype=np.int32),
        "final_steps": np.asarray(finals, dtype=np.int32),
        "W": W,
        "hbar": H,
        "pct": np.int32(seed_paths and _pct_of(seed_paths[0][1])),
        "L": np.int32(L),
        "hbar_max": np.float32(hbar_max),
        "saturated": np.bool_(hbar_max >= L ** 1.5),
    }


def _pct_of(path: str) -> int:
    m = _HIER_RE.search(path) or _FLAT_RE.search(path)
    return int(m.group(1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    args = ap.parse_args()

    cells = discover(args.in_dir)
    if not cells:
        sys.exit(f"no joblib runs found under {args.in_dir}")

    total_in = total_out = 0
    for (pct, L), seed_paths in sorted(cells.items()):
        data = reduce_cell(seed_paths, L)
        out_path = os.path.join(args.out_dir, f"pct_{pct:02d}", f"L_{L:04d}.npz")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tmp = out_path + ".tmp"
        np.savez_compressed(tmp, **data)
        os.replace(tmp + ".npz", out_path)
        in_bytes = sum(os.path.getsize(p) for _, p in seed_paths)
        out_bytes = os.path.getsize(out_path)
        total_in += in_bytes
        total_out += out_bytes
        print(f"pct={pct:02d} L={L:>4}: {len(seed_paths):>3} seeds  "
              f"{in_bytes/1e6:6.1f} MB -> {out_bytes/1e6:5.2f} MB  "
              f"{'SAT' if bool(data['saturated']) else 'unsat'}")

    print(f"\nreduced {len(cells)} cells: "
          f"{total_in/1e6:.0f} MB joblib -> {total_out/1e6:.1f} MB npz "
          f"({total_in / max(total_out, 1):.1f}x smaller)")


if __name__ == "__main__":
    main()
