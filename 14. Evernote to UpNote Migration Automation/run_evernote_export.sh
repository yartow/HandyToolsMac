#!/bin/bash

# Bulk-exports every Evernote notebook to .enex, via evernote-backup
# (https://github.com/vzhd1701/evernote-backup), run through its Docker image.
# Assumes `evernote-backup init-db` has already been run once (one-time,
# interactive OAuth login -- see GETTING_STARTED.md). This script only
# automates the two steps that would otherwise require you to babysit them:
# retrying `sync` automatically if Evernote's API rate-limits it mid-run, then
# exporting every notebook to .enex once sync finishes.

set -euo pipefail

# ----- CONFIG -----
DATA_DIR="${1:-$(pwd)/evernote-backup-data}"
EXPORT_DIR="${2:-$(pwd)/enex-in}"
IMAGE="vzhd1701/evernote-backup:latest"
MAX_SYNC_RETRIES=20
RETRY_SLEEP_SECONDS=900  # 15 minutes -- safely longer than Evernote's typical rate-limit windows
# ---------

if [[ ! -d "$DATA_DIR" ]] || [[ -z "$(ls -A "$DATA_DIR" 2>/dev/null)" ]]; then
    echo "ERROR: $DATA_DIR doesn't exist or is empty." >&2
    echo "Run 'evernote-backup init-db' once first (one-time login) -- see GETTING_STARTED.md." >&2
    exit 1
fi

mkdir -p "$EXPORT_DIR"
SYNC_LOG=$(mktemp)
trap 'rm -f "$SYNC_LOG"' EXIT

echo "[$(date '+%H:%M:%S')] Starting sync (first run can take a long time for a large account)..."
attempt=1
while true; do
    if docker run --rm -t -v "$DATA_DIR":/tmp "$IMAGE" sync 2>&1 | tee "$SYNC_LOG"; then
        echo "[$(date '+%H:%M:%S')] Sync completed."
        break
    fi

    if grep -qi "rate limit" "$SYNC_LOG"; then
        if (( attempt >= MAX_SYNC_RETRIES )); then
            echo "[$(date '+%H:%M:%S')] ERROR: still rate-limited after $MAX_SYNC_RETRIES retries. Giving up -- rerun this script later." >&2
            exit 1
        fi
        echo "[$(date '+%H:%M:%S')] Evernote rate limit hit (attempt $attempt/$MAX_SYNC_RETRIES) -- waiting ${RETRY_SLEEP_SECONDS}s before retrying..."
        sleep "$RETRY_SLEEP_SECONDS"
        attempt=$((attempt + 1))
        continue
    fi

    echo "[$(date '+%H:%M:%S')] ERROR: sync failed for a reason other than rate limiting -- see log above." >&2
    exit 1
done

echo "[$(date '+%H:%M:%S')] Exporting every notebook to $EXPORT_DIR ..."
docker run --rm -t -v "$DATA_DIR":/tmp -v "$EXPORT_DIR":/export "$IMAGE" export /export

echo "[$(date '+%H:%M:%S')] Done. .enex files are in: $EXPORT_DIR"
