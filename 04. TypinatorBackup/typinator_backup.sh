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
# Per-machine file so two Macs don't corrupt each other's detection window
MACHINE=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
LAST_RUN_FILE="$BACKUP_BASE/.last_run_${MACHINE}"

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
    dest_epoch=0
    [[ -e "$CURRENT_DIR/$name" ]] && dest_epoch=$(stat -f %m "$CURRENT_DIR/$name")
    if (( mod_epoch > SINCE_EPOCH && mod_epoch > dest_epoch )); then
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

# ----- IMPORT (Drive → local) -----
TYPINATOR_WAS_RUNNING=false
if pgrep -xq "Typinator"; then
    TYPINATOR_WAS_RUNNING=true
    osascript -e 'tell application "Typinator" to quit'
    for i in {1..10}; do
        pgrep -xq "Typinator" || break
        sleep 1
    done
fi

IMPORTED=0
for drive_file in "$CURRENT_DIR"/*.tyset; do
    [[ -d "$drive_file" ]] || continue
    name=$(basename "$drive_file")
    local_file="$TYPINATOR_SETS/$name"
    drive_mod=$(stat -f %m "$drive_file")
    local_mod=0
    [[ -e "$local_file" ]] && local_mod=$(stat -f %m "$local_file")
    if (( drive_mod > local_mod )); then
        rm -rf "$local_file"
        cp -rp "$drive_file" "$local_file"
        echo "[$(date '+%H:%M:%S')] Imported: $name" >> "$LOG_FILE"
        (( IMPORTED++ ))
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Import complete: $IMPORTED set(s) imported." >> "$LOG_FILE"
$TYPINATOR_WAS_RUNNING && open -a Typinator

# Remove archive folders older than MAX_DAYS
while IFS= read -r -d '' old_dir; do
    rm -rf "$old_dir"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removed old archive: $(basename "$old_dir")" >> "$LOG_FILE"
done < <(find "$BACKUP_BASE/90. Backups" -mindepth 1 -maxdepth 1 -type d -mtime +"$MAX_DAYS" -print0 2>/dev/null)
