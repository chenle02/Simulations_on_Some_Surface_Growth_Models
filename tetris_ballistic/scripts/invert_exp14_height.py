#!/usr/bin/env python3
"""One-time correction of exp14 reduced npz: row-index -> physical height.

exp14 was simulated with post-e7ba915 code that stored ``AvergeHeight`` as the
mean ROW-INDEX (measured from the top), which DECREASES as the pile grows,
instead of the physical mean height (see FINDING-kernel-height-inversion.md).
The reduced npz inherited this inverted ``hbar`` verbatim.

Physical mean height is ``grid_height - hbar`` where
``grid_height = round(L * ceil(3*sqrt(L)))`` (the exp14 ``ratio: auto,
sat_margin: 3`` grid). Verified against the raw joblib ``.height`` attribute for
6 spot-checked cells (exact match).

This script rewrites each ``pct_NN/L_LLLL.npz`` in place:
  hbar        := grid_height - hbar          (now ascending physical height)
  hbar_max    := mean(hbar, axis=0)[-1]      (recomputed)
  saturated   := hbar_max >= L**1.5          (recomputed with correct height)
  height_grid := grid_height                 (new field, records the conversion)

Idempotent: a cell whose ``hbar`` is already ascending (or already carries
``height_grid``) is skipped. Each rewritten cell is verified: ascending +
starts near 0.

Usage:
    python -m tetris_ballistic.scripts.invert_exp14_height --dir <traces/exp14>
    python -m tetris_ballistic.scripts.invert_exp14_height --dir ... --dry-run
"""

import argparse
import glob
import os

import numpy as np

from tetris_ballistic.kpz_analysis import exp14_grid_height_for_width


def grid_height_for_L(L: int) -> int:
    """Compatibility alias for the shared exp14 grid-height contract."""

    return exp14_grid_height_for_width(L)


def invert_cell(path: str, dry_run: bool) -> str:
    d = dict(np.load(path))
    L = int(d["L"])
    hbar = d["hbar"]
    mean_hbar = hbar.mean(axis=0)
    already = ("height_grid" in d) or bool(mean_hbar[0] < mean_hbar[-1])
    if already:
        return "skip (already physical)"

    Hg = grid_height_for_L(L)
    hbar_phys = (Hg - hbar).astype(np.float32)
    mean_phys = hbar_phys.mean(axis=0)
    # Correctness gate: physical height must rise from ~0 and be non-decreasing.
    if not (mean_phys[0] < 5.0 and mean_phys[-1] > mean_phys[0]
            and bool(np.all(np.diff(mean_phys) >= -1e-3))):
        raise ValueError(
            f"{path}: inversion did NOT yield ascending physical height "
            f"(start={mean_phys[0]:.2f}, end={mean_phys[-1]:.2f}, Hg={Hg})"
        )
    hbar_max = float(mean_phys[-1])
    d["hbar"] = hbar_phys
    d["hbar_max"] = np.float32(hbar_max)
    d["saturated"] = np.bool_(hbar_max >= L ** 1.5)
    d["height_grid"] = np.int32(Hg)
    if not dry_run:
        tmp = path + ".tmp"
        np.savez_compressed(tmp, **d)
        os.replace(tmp + ".npz", path)
    return (f"inverted Hg={Hg} hbar_max={hbar_max:.1f} "
            f"sat={bool(hbar_max >= L ** 1.5)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, help="traces/exp14 npz root")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    paths = sorted(glob.glob(os.path.join(args.dir, "**", "*.npz"), recursive=True))
    if not paths:
        raise SystemExit(f"no npz under {args.dir}")
    n_inv = n_skip = 0
    for p in paths:
        msg = invert_cell(p, args.dry_run)
        print(f"{'[dry] ' if args.dry_run else ''}{os.path.relpath(p, args.dir)}: {msg}")
        if msg.startswith("inverted"):
            n_inv += 1
        else:
            n_skip += 1
    print(f"\n{'DRY-RUN ' if args.dry_run else ''}done: {n_inv} inverted, {n_skip} skipped, {len(paths)} total")


if __name__ == "__main__":
    main()
