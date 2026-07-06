#!/bin/bash

# Typinator Sets Daily Backup
# Exports .tyset files modified since the last run to Google Drive, then
# imports any sets that are newer on Drive back to the local machine.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

# Defaults — override any of these in .env
TYPINATOR_SETS="${TYPINATOR_SETS:-$HOME/Library/Application Support/Typinator/Sets}"
DRIVE_SUBPATH="${DRIVE_SUBPATH:-08. Software/01. OSX macOS/05. Typinator}"
ARCHIVE_SUBDIR="${ARCHIVE_SUBDIR:-90. Backups}"
MAX_DAYS="${MAX_DAYS:-7}"

# Auto-detect Google Drive mount regardless of which account is signed in
GDRIVE_ROOT=$(find "$HOME/Library/CloudStorage" -maxdepth 1 -name "GoogleDrive-*" -type d 2>/dev/null | head -1)
if [[ -z "$GDRIVE_ROOT" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: No Google Drive mount found in ~/Library/CloudStorage/" >&2
    exit 1
fi
BACKUP_BASE="$GDRIVE_ROOT/My Drive/$DRIVE_SUBPATH"

TODAY=$(date +%Y-%m-%d)
# Per-machine file so two Macs don't corrupt each other's detection window
MACHINE=$(scutil --get LocalHostName 2>/dev/null || hostname -s)
LAST_RUN_FILE="$BACKUP_BASE/.last_run_${MACHINE}"

SINCE_EPOCH=0
if [[ -f "$LAST_RUN_FILE" ]]; then
    raw=$(< "$LAST_RUN_FILE")
    [[ "$raw" =~ ^[0-9]+$ ]] && SINCE_EPOCH=$raw
fi

ARCHIVE_DIR="$BACKUP_BASE/$ARCHIVE_SUBDIR/$TODAY"
LOG_FILE="$BACKUP_BASE/backup.log"

mkdir -p "$BACKUP_BASE"

# ----- EXPORT (local → Drive) -----
COPIED=0
SKIPPED=0
EXPORT_ERRORS=0

for file in "$TYPINATOR_SETS"/*.tyset; do
    [[ -d "$file" ]] || continue
    name=$(basename "$file")
    mod_epoch=$(stat -f %m "$file")
    dest_epoch=0
    [[ -e "$BACKUP_BASE/$name" ]] && dest_epoch=$(stat -f %m "$BACKUP_BASE/$name")
    if (( mod_epoch > SINCE_EPOCH && mod_epoch > dest_epoch )); then
        rm -rf "$BACKUP_BASE/$name"
        if cp -rp "$file" "$BACKUP_BASE/$name"; then
            mkdir -p "$ARCHIVE_DIR"
            rm -rf "$ARCHIVE_DIR/$name"
            cp -rp "$file" "$ARCHIVE_DIR/$name" \
                || echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: archive copy failed for $name" >> "$LOG_FILE"
            echo "[$(date '+%H:%M:%S')] Backed up: $name" >> "$LOG_FILE"
            (( COPIED++ ))
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: failed to copy $name to Drive" | tee -a "$LOG_FILE" >&2
            (( EXPORT_ERRORS++ ))
        fi
    else
        (( SKIPPED++ ))
    fi
done

date +%s > "$LAST_RUN_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup complete: $COPIED set(s) copied, $SKIPPED unchanged, $EXPORT_ERRORS error(s)." >> "$LOG_FILE"

# ----- IMPORT (Drive → local) -----
TYPINATOR_WAS_RUNNING=false
ACTIVE_SETS=""
SKIP_IMPORT=false

if pgrep -xq "Typinator"; then
    TYPINATOR_WAS_RUNNING=true
    ACTIVE_SETS=$(osascript <<'APPLESCRIPT'
tell application "Typinator"
    set output to ""
    repeat with aSet in abbreviation sets
        if enabled of aSet then
            set output to output & (name of aSet) & linefeed
        end if
    end repeat
    return output
end tell
APPLESCRIPT
    )
fi

IMPORTED=0
IMPORT_ERRORS=0

if [[ -z "$ACTIVE_SETS" ]]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Import skipped: Typinator not running or no active sets found." >> "$LOG_FILE"
else
    # Determine which Drive sets qualify: active locally + newer on Drive
    SETS_TO_IMPORT=()
    for drive_file in "$BACKUP_BASE"/*.tyset; do
        [[ -d "$drive_file" ]] || continue
        set_filename=$(basename "$drive_file")
        set_name="${set_filename%.tyset}"
        local_file="$TYPINATOR_SETS/$set_filename"
        printf '%s' "$ACTIVE_SETS" | grep -qxF "$set_name" || continue
        drive_mod=$(stat -f %m "$drive_file")
        local_mod=0
        [[ -e "$local_file" ]] && local_mod=$(stat -f %m "$local_file")
        (( drive_mod > local_mod )) && SETS_TO_IMPORT+=("$set_filename")
    done

    # Delete qualifying sets from Typinator's registry before quitting (prevents duplicates on restart)
    for set_filename in "${SETS_TO_IMPORT[@]}"; do
        set_name="${set_filename%.tyset}"
        osascript <<APPLESCRIPT 2>/dev/null
tell application "Typinator"
    delete (first abbreviation set whose name is "$set_name")
end tell
APPLESCRIPT
        echo "[$(date '+%H:%M:%S')] Removed from Typinator registry: $set_name" >> "$LOG_FILE"
    done

    osascript -e 'tell application "Typinator" to quit'
    for i in {1..10}; do
        pgrep -xq "Typinator" || break
        sleep 1
    done
    if pgrep -xq "Typinator"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Typinator still running after 10s; import skipped." | tee -a "$LOG_FILE" >&2
        SKIP_IMPORT=true
    fi

    if [[ "$SKIP_IMPORT" == false ]]; then
        for set_filename in "${SETS_TO_IMPORT[@]}"; do
            drive_file="$BACKUP_BASE/$set_filename"
            local_file="$TYPINATOR_SETS/$set_filename"
            rm -rf "$local_file"
            if cp -rp "$drive_file" "$local_file"; then
                echo "[$(date '+%H:%M:%S')] Imported: $set_filename" >> "$LOG_FILE"
                (( IMPORTED++ ))
            else
                echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: failed to import $set_filename" | tee -a "$LOG_FILE" >&2
                (( IMPORT_ERRORS++ ))
            fi
        done
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Import complete: $IMPORTED set(s) imported, $IMPORT_ERRORS error(s)." >> "$LOG_FILE"
    fi
fi

# Restart Typinator only if we were the ones that quit it and import ran
[[ "$TYPINATOR_WAS_RUNNING" == true && "$SKIP_IMPORT" == false ]] && open -a Typinator

# Remove archive folders whose name (date) is older than MAX_DAYS
CUTOFF=$(date -v -"${MAX_DAYS}d" +%Y-%m-%d)
while IFS= read -r -d '' old_dir; do
    folder=$(basename "$old_dir")
    if [[ "$folder" < "$CUTOFF" ]]; then
        rm -rf "$old_dir"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Removed old archive: $folder" >> "$LOG_FILE"
    fi
done < <(find "$BACKUP_BASE/$ARCHIVE_SUBDIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

# Keep log bounded to last 1000 lines
if [[ -f "$LOG_FILE" ]]; then
    tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
