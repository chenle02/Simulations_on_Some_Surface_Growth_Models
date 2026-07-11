#!/bin/bash
#
# Easley-side reduce + heartbeat for a finished tetris experiment.
# Reduces the heavy joblib runs on /scratch to compact (W,h-bar) npz IN PLACE on
# the cluster (so the sync-back moves ~GB of npz, not the ~100s-of-GB of joblib),
# then writes a heartbeat.json + EASLEY_COMPUTE_STATUS.md that the Greenwood
# pull script reads. Chain after the compute array:
#   sbatch --dependency=afterany:<ARRAY_JID> scripts/easley/reduce_and_status.sbatch <exp>
# or run standalone once the array is done:
#   sbatch scripts/easley/reduce_and_status.sbatch tetris14
#
#SBATCH --job-name=tetris_reduce
#SBATCH --partition=nova_20,nova_28,nova_long
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=08:00:00
#SBATCH --output=/scratch/lzc0090/%x-%j.out
#SBATCH --error=/scratch/lzc0090/%x-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=le.chen@auburn.edu

set -uo pipefail

EXP="${1:-tetris14}"
REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

module load python/anaconda/3.12.7 2>/dev/null || module load python 2>/dev/null || true
export PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}"

SCRATCH="/scratch/lzc0090/${EXP}"
RESULTS="$SCRATCH/results"
TRACES="$SCRATCH/traces"
HEARTBEAT="$SCRATCH/heartbeat.json"
STATUS="$SCRATCH/EASLEY_COMPUTE_STATUS.md"

echo "=== reduce $EXP: $(find "$RESULTS" -name '*.joblib' 2>/dev/null | wc -l) joblib cells -> $TRACES ==="

python3 -u -m tetris_ballistic.scripts.reduce_traces --in "$RESULTS" --out "$TRACES"

python3 - "$EXP" "$RESULTS" "$TRACES" "$HEARTBEAT" "$STATUS" <<'PY'
import json, sys, time, glob, os
exp, results, traces, hb_path, status_path = sys.argv[1:6]
n_joblib = len(glob.glob(os.path.join(results, "**", "*.joblib"), recursive=True))
n_npz = len(glob.glob(os.path.join(traces, "**", "*.npz"), recursive=True))
npz_bytes = sum(os.path.getsize(p) for p in glob.glob(os.path.join(traces, "**", "*.npz"), recursive=True))
hb = {
    "experiment": exp,
    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "joblib_cells": n_joblib,
    "npz_cells": n_npz,
    "npz_bytes": npz_bytes,
    "reduce_complete": n_npz > 0,
}
open(hb_path, "w").write(json.dumps(hb, indent=2))
md = [
    f"# Easley {exp} compute status",
    "",
    f"Timestamp: `{hb['timestamp_utc']}`",
    "",
    "| joblib cells | npz cells | npz size (MB) | reduced |",
    "|---:|---:|---:|:--:|",
    f"| {n_joblib} | {n_npz} | {npz_bytes/1e6:.1f} | {'yes' if hb['reduce_complete'] else 'no'} |",
    "",
    "Pull the reduced traces with `scripts/easley/pull_traces.sh` on Greenwood/Dell.",
]
open(status_path, "w").write("\n".join(md) + "\n")
print("wrote", hb_path, "and", status_path)
PY

echo "=== done. Reduced traces in $TRACES ready for pull. ==="
