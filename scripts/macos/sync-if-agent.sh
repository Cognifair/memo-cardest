#!/bin/sh
# Sync all installed Memo skill roots. Runs outside the DSH sandbox via launchd.
set -u

LOG_DIR="$HOME/Library/Logs/MemoCardest"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/sync.log"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG"
}

PYTHON="${MEMO_PYTHON:-$(command -v python3 || true)}"
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    log "error: python3 not found"
    exit 1
fi

log "run: sync all installed Memo roots"
for root in "$HOME/.agents/skills" "$HOME/.codex/skills" "$HOME/.claude/skills" "$HOME/.workbuddy/skills"; do
    script="$root/memo-cardest/scripts/check_updates.py"
    if [ ! -f "$script" ]; then
        log "skip: $root has no memo-cardest"
        continue
    fi
    log "sync: $root"
    "$PYTHON" -B "$script" --root "$root" sync >> "$LOG" 2>&1
    log "exit: $root -> $?"
done
