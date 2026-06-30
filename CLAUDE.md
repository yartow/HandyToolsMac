# HandyToolsMac — Developer Notes

## Repository Overview

A collection of standalone utility scripts and tools for macOS and Linux.
Each tool lives in its own numbered directory and is self-contained.

---

## Code Style (all tools)

- Shebang: `#!/usr/bin/env python3`
- Module docstring immediately after shebang
- CONFIG block delimited by `# ----- CONFIG -----` / `# ---------` comments
- Type hints on all functions
- `print()`-based progress (no logging framework)
- No comments unless the WHY is non-obvious

---

## 04. TypinatorBackup

Shell script (`typinator_backup.sh`) that runs daily via a launchd agent. Two phases:

1. **Backup (local → Drive):** copies `.tyset` packages modified since the last run to `BACKUP_BASE` and a dated archive under `90. Backups/`. Pruned after `MAX_DAYS` days.
2. **Import (Drive → local):** pulls Drive copies that are newer than the local file, but **only for sets that were active in Typinator at the time of the run**. Each set is removed from Typinator's internal registry via AppleScript before the file swap — this prevents duplicate entries on restart. Import is skipped entirely if Typinator is not running.

### Multi-Mac / shared Drive

Multiple Macs can point at the same `BACKUP_BASE` folder on Drive without conflicting:

- A per-machine marker file (`.last_run_<hostname>`) tracks each Mac's last backup epoch independently — two machines never overwrite each other's marker.
- The import phase is purely timestamp-based (Drive mod time vs local mod time) and requires no coordination between machines.
- Dated archive folders under `90. Backups/` are keyed by date and are written independently; no locking is needed.

### Sensitive files

- `.env` and `credentials.json` are gitignored — never commit them.
- The launchd plist (`com.yartow.typinator-backup.plist`) contains a hardcoded absolute path; this is unavoidable for launchd but contains no secrets.
