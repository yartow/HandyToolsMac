# Typinator Backup — Developer Notes

## Core invariants (do not break)

**Only the latest version of each set is kept in the current folder.**
`BACKUP_BASE/*.tyset` must always contain at most one copy of each set — the most recently modified one across all machines. Before copying a new version in, the old copy is deleted (`rm -rf` then `cp -rp`). Never accumulate multiple versions or renamed duplicates here.

**No duplicate sets anywhere.**
Both the current folder and each dated archive folder under `ARCHIVE_SUBDIR/<date>/` must hold at most one copy of each `.tyset` name. The script deletes the destination before copying, so duplicates cannot build up. Any change that adds a second copy of the same name is a bug.

**Import only brings in sets that are newer than the local copy.**
The import phase compares Drive mod-time against local mod-time and skips files that are not newer. Do not change this to an unconditional copy — that would overwrite locally-edited sets that have not yet been backed up.

**Archive folders are only created when something is actually backed up.**
`mkdir -p "$ARCHIVE_DIR"` runs inside the export loop, on the first successful copy, not unconditionally before the loop. This prevents empty dated folders from accumulating on no-op runs.

**Archive pruning compares the folder name (date string) against a cutoff, not `mtime`.**
Using `-mtime` would skip old archives whose directory metadata was touched by Drive sync. Always compare `$(basename "$old_dir")` lexicographically against `$(date -v -${MAX_DAYS}d +%Y-%m-%d)`.

## Configuration

All user-tunable values live in `.env` (gitignored, sourced by the script at startup). `.env.example` is the canonical reference — keep it in sync whenever a new variable is introduced.

Variables the script currently reads from `.env`:
- `DRIVE_SUBPATH` — path inside `My Drive/` on Google Drive
- `ARCHIVE_SUBDIR` — subfolder name for dated archives (default: `90. Backups`)
- `MAX_DAYS` — days of archives to retain
- `TYPINATOR_SETS` — local Typinator sets directory (optional override)

## Script structure

1. `set -uo pipefail` — catch undefined variables and pipe failures
2. Source `.env` → apply defaults → detect Google Drive mount → build `BACKUP_BASE`
3. Read and validate `LAST_RUN_FILE` into `SINCE_EPOCH` (reject non-numeric content)
4. Export phase: for each `.tyset` modified since `SINCE_EPOCH` and newer than Drive copy:
   - Copy to `BACKUP_BASE` (primary); abort file on `cp` failure, log error, increment `EXPORT_ERRORS`
   - Lazy `mkdir -p "$ARCHIVE_DIR"` on first successful copy
   - Copy to dated archive; log warning on failure but count primary copy as success
5. Write `LAST_RUN_FILE` timestamp
6. Import phase:
   - Quit Typinator; if still running after 10s, log warning and set `SKIP_IMPORT=true`
   - If not skipped: copy any Drive set newer than local; log errors, increment `IMPORT_ERRORS`
   - Restart Typinator only if we quit it and import was not skipped
7. Prune archive folders by folder-name date comparison
8. Trim `backup.log` to last 1000 lines

## Error handling philosophy

- Per-file errors (failed `cp`) are logged and counted but do not abort the run; other files are still processed.
- A failed primary Drive copy does not update the success counter or write the archive copy.
- If Typinator won't quit, import is skipped entirely — never import into Typinator's Sets folder while it is running.
- `LAST_RUN_FILE` is written after export regardless of errors; the `mod_epoch > dest_epoch` guard in the next run prevents re-uploading files that were already successfully copied.
