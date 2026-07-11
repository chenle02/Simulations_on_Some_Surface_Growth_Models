#!/bin/bash
#
# Exp15 — Nova batch array (deep-substrate tier, L up to 1000).
# 3200 cells, 1 cell/task -> up to 2500 concurrent cores (the nova_short QoS
# per-user cap, shortcap=cpu=2500). ALL cells are heavy (L>=400, >=83s each), so
# the ~13s numba warmup is <15% overhead even at 1 cell/task, and this maximizes
# core usage (~90%+ of idle Nova). nova_short walltime cap is 1 day; each cell is
# <=14 min so this is safe.
# Node-LOCAL numba cache (shared GPFS cache stalls concurrent tasks in D-state).
# Results -> /scratch/.../tetris15; idempotent (finished cells skipped on resubmit).
# Submit:  sbatch experiments/exp15/batch_nova.slurm
#
#SBATCH --job-name=t15_nova
#SBATCH --array=0-3199%2400
#SBATCH --cpus-per-task=1
#SBATCH --time=23:00:00
#SBATCH --mem=8gb
#SBATCH --partition=nova_short
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
N_ARRAYS=3200
mkdir -p /scratch/lzc0090/tetris15/logs "$OUT_DIR" "$NUMBA_CACHE_DIR"
trap 'rm -rf "$NUMBA_CACHE_DIR"' EXIT

echo "=== t15 task $SLURM_ARRAY_TASK_ID / $N_ARRAYS on $(hostname) @ $(git rev-parse --short HEAD) ==="

python3 -u -m tetris_ballistic.scripts.run_batch \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR" \
    --array-index "$SLURM_ARRAY_TASK_ID" \
    --n-arrays "$N_ARRAYS"
