#!/bin/bash
#
# Exp14 — Department array (Dept-tier priority on abebeas/mathdep nodes).
# Covers the EVEN half of the 0..3599 task space via a stride-2 offset.
# Submit:  sbatch experiments/exp14/job_array_dept.slurm
#
#SBATCH --job-name=tetris14_dept
#SBATCH --array=0-1799%48
#SBATCH --cpus-per-task=1
#SBATCH --time=08:00:00
#SBATCH --mem=4gb
#SBATCH --partition=abebeas_std,mathdep_bg2
#SBATCH --requeue
#SBATCH --output=logs/dept_%A_%a.out
#SBATCH --error=logs/dept_%A_%a.err
#SBATCH --mail-type=FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -euo pipefail

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi

EXP_DIR="$(dirname "$0")"
GRID_SPEC="$EXP_DIR/grid.yaml"
OUT_DIR="$EXP_DIR/results"
mkdir -p logs "$OUT_DIR"

TASK_ID=$(( 2 * SLURM_ARRAY_TASK_ID ))

echo "================================================================"
echo "Dept: job=$SLURM_JOB_ID array_idx=$SLURM_ARRAY_TASK_ID -> cell=$TASK_ID host=$(hostname)"
echo "Repo: $REPO_ROOT @ $(git rev-parse --short HEAD)"
echo "================================================================"

python -m tetris_ballistic.scripts.run_one_cell \
    --task-id "$TASK_ID" \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR"

echo "Cell $TASK_ID done."
