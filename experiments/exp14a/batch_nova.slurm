#!/bin/bash
#
# Exp14a — Nova batch array (crossover tier).
# Each array task runs a BLOCK of cells in one process via run_batch, so the
# ~40s numba JIT compile is paid once per task, not once per cell.
# 4200 cells / 100 array tasks = 42 cells per task.
# Results -> /scratch; idempotent (finished cells are skipped on resubmit).
# Submit:  sbatch experiments/exp14a/batch_nova.slurm
#
#SBATCH --job-name=t14a_nova
#SBATCH --array=0-99
#SBATCH --cpus-per-task=1
#SBATCH --time=12:00:00
#SBATCH --mem=6gb
#SBATCH --partition=nova_long
#SBATCH --requeue
#SBATCH --output=/scratch/lzc0090/tetris14/logs/t14a_%A_%a.out
#SBATCH --error=/scratch/lzc0090/tetris14/logs/t14a_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -uo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"
export NUMBA_CACHE_DIR="/scratch/lzc0090/tetris14/numba_cache"

GRID_SPEC="$REPO_ROOT/experiments/exp14a/grid.yaml"
OUT_DIR="/scratch/lzc0090/tetris14/results"
N_ARRAYS=100
mkdir -p /scratch/lzc0090/tetris14/logs "$OUT_DIR" "$NUMBA_CACHE_DIR"

echo "=== t14a task $SLURM_ARRAY_TASK_ID / $N_ARRAYS on $(hostname) @ $(git rev-parse --short HEAD) ==="

python3 -m tetris_ballistic.scripts.run_batch \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR" \
    --array-index "$SLURM_ARRAY_TASK_ID" \
    --n-arrays "$N_ARRAYS"
