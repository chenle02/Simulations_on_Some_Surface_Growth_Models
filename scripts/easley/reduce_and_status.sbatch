#!/bin/bash
#
# Easley-side reduce + heartbeat for a finished tetris experiment.
# Reduces the heavy joblib runs on /scratch to compact (W,h-bar) npz IN PLACE on
# the cluster (so the sync-back moves ~GB of npz, not the ~100s-of-GB of joblib),
# then writes a heartbeat.json + EASLEY_COMPUTE_STATUS.md that the Greenwood
# pull script reads. Chain after the compute array:
#   sbatch --dependency=afterany:<ARRAY_JID> scripts/easley/reduce_and_status.sbatch <exp> [grid.yaml ...]
# or run standalone once the array is done:
#   sbatch scripts/easley/reduce_and_status.sbatch tetris14
#
#SBATCH --job-name=tetris_reduce
#SBATCH --partition=bigmem4,bigmem2,amd
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/lzc0090/%x-%j.out
#SBATCH --error=/scratch/lzc0090/%x-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -uo pipefail

EXP="${1:-tetris14}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

shift $(( $# > 0 ? 1 : 0 ))
GRID_SPECS=("$@")
if [[ "${#GRID_SPECS[@]}" -eq 0 ]]; then
  case "$EXP" in
    tetris14) GRID_SPECS=("experiments/exp14a/grid.yaml" "experiments/exp14b/grid.yaml") ;;
    tetris15) GRID_SPECS=("experiments/exp15/grid.yaml") ;;
    *) echo "ERROR: provide one or more declared grid specs for $EXP" >&2; exit 2 ;;
  esac
fi

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

SCRATCH="/scratch/lzc0090/${EXP}"
RESULTS="$SCRATCH/results"
TRACES="$SCRATCH/traces"
HEARTBEAT="$SCRATCH/heartbeat.json"
STATUS="$SCRATCH/EASLEY_COMPUTE_STATUS.md"

python3 - "$EXP" "$HEARTBEAT" "$STATUS" <<'PY' || exit 2
import json, sys
from datetime import datetime, timezone
from tetris_ballistic.run_artifacts import atomic_write_bytes

experiment, heartbeat, status = sys.argv[1:4]
pending = {
    "experiment": experiment,
    "reduce_complete": False,
    "schema_version": "tetris-experiment-completion-v1",
    "state": "running",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
}
atomic_write_bytes(heartbeat, (json.dumps(pending, indent=2, sort_keys=True) + "\n").encode())
atomic_write_bytes(status, f"# Easley {experiment} compute status\n\nReduction audit is running.\n".encode())
PY

echo "=== reduce $EXP: $(find "$RESULTS" -name '*.joblib' 2>/dev/null | wc -l) joblib cells -> $TRACES ==="

STATUS_ARGS=()
for grid_spec in "${GRID_SPECS[@]}"; do
  STATUS_ARGS+=(--grid-spec "$grid_spec")
done
python3 -u -m tetris_ballistic.scripts.reduce_traces \
  --in "$RESULTS" \
  --out "$TRACES" \
  "${STATUS_ARGS[@]}"
REDUCE_RC=$?
echo "reduce exit code: $REDUCE_RC"

python3 -u -m tetris_ballistic.scripts.experiment_status \
  --experiment "$EXP" \
  "${STATUS_ARGS[@]}" \
  --results "$RESULTS" \
  --traces "$TRACES" \
  --heartbeat "$HEARTBEAT" \
  --status "$STATUS" \
  --reduce-rc "$REDUCE_RC"
STATUS_RC=$?

echo "=== done. Reduced traces in $TRACES ready for pull. ==="
exit "$STATUS_RC"
