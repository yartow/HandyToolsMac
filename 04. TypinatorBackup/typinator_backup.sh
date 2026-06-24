#!/bin/bash

# Typinator Sets Daily Backup
# Backs up .tyset files modified today to "05. Typinator/" and keeps a
# 7-day rolling archive in "90. Backups/", both under BACKUP_BASE.

TYPINATOR_SETS="$HOME/Library/Application Support/Typinator/Sets"

# Auto-detect Google Drive mount regardless of which account is signed in
GDRIVE_ROOT=$(ls -d "$HOME/Library/CloudStorage/GoogleDrive-"* 2>/dev/null | head -1)
if [[ -z "$GDRIVE_ROOT" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: No Google Drive mount found in ~/Library/CloudStorage/" >&2
    exit 1
fi
BACKUP_BASE="$GDRIVE_ROOT/My Drive/08. Software/01. OSX macOS/05. Typinator"
MAX_DAYS=7

TODAY=$(date +%Y-%m-%d)
LAST_RUN_FILE="$BACKUP_BASE/.last_run"

# Compare against last backup run, not midnight — so edits made before a
# missed 5 PM run are still caught on the next login.
if [[ -f "$LAST_RUN_FILE" ]]; then
    SINCE_EPOCH=$(cat "$LAST_RUN_FILE")
else
    SINCE_EPOCH=0
fi

CURRENT_DIR="$BACKUP_BASE"
ARCHIVE_DIR="$BACKUP_BASE/90. Backups/$TODAY"
LOG_FILE="$BACKUP_BASE/backup.log"

mkdir -p "$CURRENT_DIR"
mkdir -p "$ARCHIVE_DIR"

COPIED=0
SKIPPED=0

for file in "$TYPINATOR_SETS"/*.tyset; do
    [[ -d "$file" ]] || continue
    name=$(basename "$file")
    mod_epoch=$(stat -f %m "$file")
    if (( mod_epoch > SINCE_EPOCH )); then
        rm -rf "$CURRENT_DIR/$name"
        cp -rp "$file" "$CURRENT_DIR/$name"
        rm -rf "$ARCHIVE_DIR/$name"
        cp -rp "$file" "$ARCHIVE_DIR/$name"
        echo "[$(date '+%H:%M:%S')] Backed up: $name" >> "$LOG_FILE"
        (( COPIED++ ))
    else
        (( SKIPPED++ ))
    fi
done

date +%s > "$LAST_RUN_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete: $COPIED set(s) copied, $SKIPPED unchanged." >> "$LOG_FILE"

# Remove archive folders older than MAX_DAYS
while IFS= read -r -d '' old_dir; do
    rm -rf "$old_dir"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removed old archive: $(basename "$old_dir")" >> "$LOG_FILE"
done < <(find "$BACKUP_BASE/90. Backups" -mindepth 1 -maxdepth 1 -type d -mtime +"$MAX_DAYS" -print0 2>/dev/null)
