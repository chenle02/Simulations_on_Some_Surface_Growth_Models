#!/bin/bash
#SBATCH --job-name=tetris14_tw_reduce
#SBATCH --partition=mathdep_bg2,abebeas_bg2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=120G
#SBATCH --time=08:00:00
# IMPORTANT: canary first with:
#   sbatch --array=0 scripts/easley/reduce_tw_interfaces.sbatch
# An ordinary `sbatch scripts/easley/reduce_tw_interfaces.sbatch` launches all 14.
#SBATCH --array=0-13
#SBATCH --output=/scratch/lzc0090/tetris14/logs/%x-%A_%a.out
#SBATCH --error=/scratch/lzc0090/tetris14/logs/%x-%A_%a.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -euo pipefail

# Explicit priority grid:
#   0-11: pct 90,95,98,99 x L 300,400,500
#   12-13: pct 5,50 x L 300 controls
PCTS=(90 90 90 95 95 95 98 98 98 99 99 99 5 50)
WIDTHS=(300 400 500 300 400 500 300 400 500 300 400 500 300 300)
TASK_ID="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}"
if (( TASK_ID < 0 || TASK_ID >= ${#PCTS[@]} )); then
    echo "invalid array index: $TASK_ID" >&2
    exit 2
fi
PCT="${PCTS[$TASK_ID]}"
WIDTH="${WIDTHS[$TASK_ID]}"

# Lightweight mapping probe used by local tests; never touches data or modules.
if [[ "${TW_MAPPING_ONLY:-0}" == "1" ]]; then
    printf '%s %s\n' "$PCT" "$WIDTH"
    exit 0
fi

REPO_ROOT="${TETRIS_REPO:-$HOME/Dropbox/Simulations_on_Some_Surface_Growth_Models}"
RAW_ROOT="/scratch/$USER/tetris14/results"
TRACE_ROOT="/scratch/$USER/tetris14/traces"
OUTPUT_ROOT="/scratch/$USER/tetris14/tw_interfaces"
mkdir -p "/scratch/$USER/tetris14/logs" "$OUTPUT_ROOT"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

echo "reduce TW interfaces: task=$TASK_ID pct=$PCT L=$WIDTH host=$(hostname)"
python3 -u -m tetris_ballistic.scripts.reduce_tw_interfaces \
    --raw-root "$RAW_ROOT" \
    --trace-root "$TRACE_ROOT" \
    --output-root "$OUTPUT_ROOT" \
    --pct "$PCT" \
    --width "$WIDTH" \
    --q-values 0.15,0.25,0.40
