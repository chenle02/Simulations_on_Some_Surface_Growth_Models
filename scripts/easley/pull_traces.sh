#!/usr/bin/env bash
# pull_traces.sh — Greenwood/Dell-side helper to rsync REDUCED tetris traces
# back from Easley and commit them into the tetris-kpz-data repo.
#
# Pulls only the compact (W,h-bar) npz (~GB), NOT the raw joblib (~100s of GB) —
# run scripts/easley/reduce_and_status.sbatch on Easley FIRST so the npz exist.
#
# Requires: Auburn VPN reachable (Greenwood keepalive service, or GlobalProtect
# on Dell). See Le-AI-Lab/runbooks/greenwood-easley-keepalive.md.
#
# Usage:
#   bash pull_traces.sh                       # one-shot pull of tetris14
#   EXP=tetris15 bash pull_traces.sh          # a different experiment
#   watch -n 600 bash pull_traces.sh          # poll every 10 min
#
set -uo pipefail

REMOTE="${REMOTE:-Easley}"
REMOTE_USER="${REMOTE_USER:-lzc0090}"
EXP="${EXP:-tetris14}"
DATA_REPO="${DATA_REPO:-$HOME/Dropbox/workspace/svn/tetris-kpz-data}"
DEST="$DATA_REPO/traces/${EXP/tetris/exp}"     # tetris14 -> traces/exp14
AUTO_COMMIT="${AUTO_COMMIT:-1}"

SRC="$REMOTE:/scratch/$REMOTE_USER/${EXP}/traces/"

echo "=== $(date) === pull $EXP reduced traces from $REMOTE ==="

if ! timeout 15 ssh -o BatchMode=yes -o ConnectTimeout=8 "$REMOTE" 'true' 2>/dev/null; then
  echo "ERROR: cannot reach $REMOTE (bring up VPN / keepalive)." >&2
  exit 2
fi

# Guard 1: reduction MUST be complete (never pull before reduce-on-Easley ran).
HB=$(ssh "$REMOTE" "cat /scratch/$REMOTE_USER/${EXP}/heartbeat.json 2>/dev/null || echo '{}'")
echo "  heartbeat: $(echo "$HB" | python3 -c "import json,sys;h=json.load(sys.stdin);print({k:h.get(k) for k in ('npz_cells','joblib_cells','reduce_complete','npz_bytes','timestamp_utc')} if h else 'empty')")"
if ! echo "$HB" | python3 -c "import json,sys;sys.exit(0 if json.load(sys.stdin).get('reduce_complete') else 1)" 2>/dev/null; then
  echo "REFUSING: reduction not complete on Easley. Run scripts/easley/reduce_and_status.sbatch ${EXP} first." >&2
  exit 4
fi

# Guard 2: size sanity — refuse if the SOURCE is implausibly large for reduced
# npz (protects against ever pointing SRC at the raw joblib results/ by mistake).
SRC_MB=$(ssh "$REMOTE" "du -sm /scratch/$REMOTE_USER/${EXP}/traces 2>/dev/null | cut -f1" 2>/dev/null || echo 0)
MAX_MB="${MAX_PULL_MB:-60000}"
echo "  source traces size: ${SRC_MB} MB (guard limit ${MAX_MB} MB)"
if [[ "$SRC_MB" -gt "$MAX_MB" ]]; then
  echo "REFUSING: source ${SRC_MB} MB exceeds ${MAX_MB} MB guard. Are you pulling reduced npz, not raw joblib? Override with MAX_PULL_MB=." >&2
  exit 5
fi

mkdir -p "$DEST"
# NEVER --delete against scratch or the repo; only additive pull.
rsync -avz --partial --info=stats1 "$SRC" "$DEST/" || { echo "rsync failed"; exit 3; }

echo "  pulled $(find "$DEST" -name '*.npz' | wc -l) npz files into $DEST"

if [[ "$AUTO_COMMIT" == "1" && -d "$DATA_REPO/.git" ]]; then
  cd "$DATA_REPO"
  if [[ -n "$(git status --porcelain traces/)" ]]; then
    python3 verify.py --update >/dev/null 2>&1 || true
    git add "traces/${EXP/tetris/exp}" MANIFEST.sha256
    git commit -q -m "data(${EXP}): pull reduced (W,h-bar) traces from Easley" \
      && echo "  committed $(git rev-parse --short HEAD)"
  else
    echo "  no new traces to commit"
  fi
fi
