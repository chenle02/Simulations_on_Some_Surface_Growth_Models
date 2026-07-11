#!/bin/bash
#
# Exp15 — Nova batch array (deep-substrate tier, L up to 1000).
# Uses the EXACT configuration proven by exp14 (which completed 5000 cells
# cleanly): nova_long + BATCHED tasks (many cells/task) + node-local numba cache.
# 3200 cells / 400 tasks = 8 cells/task, capped by longcap (cpu=420) so ~400
# run concurrently. A high-concurrency 1-cell/task nova_short variant STALLED
# (0 cells after 10 min, 0-byte logs) — likely GPFS/import contention at ~1350
# simultaneous fresh Python+numba starts; batching on nova_long avoids it.
# Node-LOCAL numba cache (shared GPFS cache stalls concurrent tasks in D-state).
# Results -> /scratch/.../tetris15; idempotent (finished cells skipped on resubmit).
# Submit:  sbatch experiments/exp15/batch_nova.slurm
#
#SBATCH --job-name=t15_nova
#SBATCH --array=0-399
#SBATCH --cpus-per-task=1
#SBATCH --time=20:00:00
#SBATCH --mem=8gb
#SBATCH --partition=nova_long
#SBATCH --requeue
#SBATCH --output=/scratch/lzc0090/tetris15/logs/t15_%A_%a.out
#SBATCH --error=/scratch/lzc0090/tetris15/logs/t15_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -uo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"
export NUMBA_CACHE_DIR="${SLURM_TMPDIR:-/tmp}/numba_${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"

GRID_SPEC="$REPO_ROOT/experiments/exp15/grid.yaml"
OUT_DIR="/scratch/lzc0090/tetris15/results"
N_ARRAYS=400
mkdir -p /scratch/lzc0090/tetris15/logs "$OUT_DIR" "$NUMBA_CACHE_DIR"
trap 'rm -rf "$NUMBA_CACHE_DIR"' EXIT

echo "=== t15 task $SLURM_ARRAY_TASK_ID / $N_ARRAYS on $(hostname) @ $(git rev-parse --short HEAD) ==="

python3 -u -m tetris_ballistic.scripts.run_batch \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR" \
    --array-index "$SLURM_ARRAY_TASK_ID" \
    --n-arrays "$N_ARRAYS"
