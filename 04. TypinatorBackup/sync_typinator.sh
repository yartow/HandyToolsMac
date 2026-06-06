#!/bin/bash
set -euo pipefail

RCLONE_REMOTE="gdrive:TypinatorBackup"
LOCAL_PATH="$HOME/Library/Application Support/Typinator"
LOG_FILE="$HOME/Library/Logs/typinator-sync.log"
LOG_MAX_BYTES=1048576
RCLONE_STATE_DIR="$HOME/.cache/rclone/bisync"

rotate_log() {
    if [[ -f "$LOG_FILE" ]]; then
        local size
        size=$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
        if (( size > LOG_MAX_BYTES )); then
            local lines
            lines=$(wc -l < "$LOG_FILE")
            tail -n $(( lines / 2 )) "$LOG_FILE" > "${LOG_FILE}.tmp" \
                && mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi
}

log() {
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

mkdir -p "$(dirname "$LOG_FILE")"
rotate_log

log "------------------------------------------------"
log "Starting Typinator sync"
log "Local:  $LOCAL_PATH"
log "Remote: $RCLONE_REMOTE"
log "Host:   $(hostname)"

if ! command -v rclone &>/dev/null; then
    log "ERROR: rclone not found. Install with: brew install rclone"
    exit 1
fi

if [[ ! -d "$LOCAL_PATH" ]]; then
    log "ERROR: Typinator folder not found at: $LOCAL_PATH"
    exit 1
fi

REMOTE_NAME="${RCLONE_REMOTE%%:*}"
if ! rclone listremotes 2>/dev/null | grep -q "^${REMOTE_NAME}:"; then
    log "ERROR: rclone remote '${REMOTE_NAME}' not configured. Run: rclone config"
    exit 1
fi

EXTRA_FLAGS=""
if [[ ! -d "$RCLONE_STATE_DIR" ]] || [[ -z "$(ls -A "$RCLONE_STATE_DIR" 2>/dev/null)" ]]; then
    log "First run detected -- using --resync (Drive wins on true conflicts this run only)"
    EXTRA_FLAGS="--resync"
fi

log "Running rclone bisync..."

rclone bisync \
    "$LOCAL_PATH" \
    "$RCLONE_REMOTE" \
    --conflict-resolve newer \
    --conflict-loser delete \
    --resilient \
    --transfers 4 \
    --checkers 8 \
    --log-file "$LOG_FILE" \
    --log-level INFO \
    $EXTRA_FLAGS

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log "Sync completed successfully."
elif [[ $EXIT_CODE -eq 2 ]]; then
    log "WARNING: Sync completed with non-critical errors. Check log for details."
else
    log "ERROR: Sync failed (exit $EXIT_CODE)."
    log "To recover from corrupted state: delete $RCLONE_STATE_DIR and re-run."
    exit $EXIT_CODE
fi

log "Done."