#!/bin/bash
#
# Exp14b — Nova batch array (deep-anchor tier, wide L for KPZ-end pcts).
# Heavy cells (L=400,500), so use MORE array tasks with FEWER cells each to
# avoid stragglers: 800 cells / 200 tasks = 4 cells per task.
# Writes to the SAME /scratch results dir as exp14a; idempotent.
# Submit:  sbatch experiments/exp14b/batch_nova.slurm
#
#SBATCH --job-name=t14b_nova
#SBATCH --array=0-199
#SBATCH --cpus-per-task=1
#SBATCH --time=16:00:00
#SBATCH --mem=8gb
#SBATCH --partition=nova_long
#SBATCH --requeue
#SBATCH --output=/scratch/lzc0090/tetris14/logs/t14b_%A_%a.out
#SBATCH --error=/scratch/lzc0090/tetris14/logs/t14b_%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -uo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"
export NUMBA_CACHE_DIR="/scratch/lzc0090/tetris14/numba_cache"

GRID_SPEC="$REPO_ROOT/experiments/exp14b/grid.yaml"
OUT_DIR="/scratch/lzc0090/tetris14/results"
N_ARRAYS=200
mkdir -p /scratch/lzc0090/tetris14/logs "$OUT_DIR" "$NUMBA_CACHE_DIR"

echo "=== t14b task $SLURM_ARRAY_TASK_ID / $N_ARRAYS on $(hostname) @ $(git rev-parse --short HEAD) ==="

python3 -m tetris_ballistic.scripts.run_batch \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR" \
    --array-index "$SLURM_ARRAY_TASK_ID" \
    --n-arrays "$N_ARRAYS"
