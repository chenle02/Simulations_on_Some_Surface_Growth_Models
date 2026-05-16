#!/bin/bash
#
# Slurm-array template for tetris-ballistic experiments.
#
# Copy + edit this file into your experiment dir, then submit with:
#     sbatch experiments/exp14/job_array.slurm
#
# Adjust --array, --time, --mem, --partition to your cluster.
# Auburn Easley defaults shown.
#
#SBATCH --job-name=tetris_bd
#SBATCH --array=0-299%50           # 300 tasks, max 50 concurrent
#SBATCH --cpus-per-task=1
#SBATCH --time=04:00:00            # per-task time budget
#SBATCH --mem=4gb                  # per-task memory
#SBATCH --partition=abebeas_std    # Auburn Easley dept partition
#SBATCH --output=logs/job_%A_%a.out
#SBATCH --error=logs/job_%A_%a.err
#SBATCH --mail-type=FAIL           # only mail on failure (avoid 10K success emails)
#SBATCH --mail-user=le.chen@auburn.edu

set -euo pipefail

# Locate the repo root from the submitted job (works from anywhere on the cluster).
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# Activate the venv.
if [[ -f .venv/bin/activate ]]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Configure paths. The grid spec MUST live next to this Slurm script.
EXP_DIR="$(dirname "$0")"
GRID_SPEC="$EXP_DIR/grid.yaml"
OUT_DIR="$EXP_DIR/results"

mkdir -p logs "$OUT_DIR"

echo "================================================================"
echo "Slurm: job=$SLURM_JOB_ID task=$SLURM_ARRAY_TASK_ID host=$(hostname)"
echo "Repo: $REPO_ROOT @ $(git rev-parse --short HEAD)"
echo "Grid: $GRID_SPEC"
echo "Out:  $OUT_DIR"
echo "================================================================"

# Run ONE cell. Idempotent — re-running the array (e.g. after preemption)
# just skips completed cells.
python -m tetris_ballistic.scripts.run_one_cell \
    --task-id "$SLURM_ARRAY_TASK_ID" \
    --grid-spec "$GRID_SPEC" \
    --out-dir "$OUT_DIR"

echo "Task $SLURM_ARRAY_TASK_ID done."
