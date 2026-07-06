# Typinator Daily Backup

Automatically backs up Typinator sets that were modified since the last run to Google Drive every day at 5 PM. A rolling archive is kept for recovery. Works on any Mac that has this repo cloned to `~/Documents/GitHub/HandyToolsMac` and Google Drive mounted.

## Folder structure on Google Drive

```
My Drive/08. Software/01. OSX macOS/05. Typinator/
├── *.tyset               ← always holds the latest version of each changed set
├── .last_run_<hostname>  ← per-machine export marker (safe to delete when decommissioning a Mac)
├── backup.log            ← rolling log, capped at 1000 lines
└── 90. Backups/
    ├── 2026-06-01/       ← dated snapshots, one per day (only created if something changed)
    ├── 2026-05-31/
    └── ...               ← automatically deleted after MAX_DAYS days
```

## Configuration

Copy `.env.example` to `.env` in the same directory and adjust the values:

```bash
cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/.env.example \
   ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/.env
```

`.env` is gitignored so each Mac can have its own values without affecting the repo.

| Variable | Default | Description |
|---|---|---|
| `DRIVE_SUBPATH` | `08. Software/01. OSX macOS/05. Typinator` | Path inside `My Drive/` on Google Drive |
| `ARCHIVE_SUBDIR` | `90. Backups` | Subfolder name for dated archive snapshots |
| `MAX_DAYS` | `7` | Days of dated archives to retain |
| `TYPINATOR_SETS` | `~/Library/Application Support/Typinator/Sets` | Where Typinator stores your sets — leave unset unless yours differs |

The schedule (default 17:00) is set in `com.yartow.typinator-backup.plist` under `StartCalendarInterval > Hour`.

## Installation (repeat on each Mac)

**1. Create your local config (first time only):**

```bash
cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/.env.example \
   ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/.env
# Edit .env if your Google Drive path or preferences differ
```

**2. Update the plist path if your username differs from `andrewyong`:**

The plist contains a hardcoded absolute path. Update it to match your home directory:

```bash
sed -i '' "s|/Users/andrewyong|$HOME|g" \
    ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist
```

**3. Copy the launchd agent:**

```bash
cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist \
   ~/Library/LaunchAgents/
```

**4. Load it (macOS Ventura and later):**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

> **Note:** `RunAtLoad` is set to `true`, so the script runs immediately when the agent is loaded — not just at 17:00. This means a backup and import will trigger right after this command.

**5. Verify it is loaded:**

```bash
launchctl list | grep typinator
```

You should see a line with `com.yartow.typinator-backup` and `-` in the PID column (no PID means it's scheduled but not currently running — that's correct).

## Running the backup manually

```bash
bash ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/typinator_backup.sh
```

Check `backup.log` on Google Drive afterwards to see what was copied.

## Import behaviour (Drive → local)

After the backup phase, the script also pulls sets down from Drive if the Drive copy is newer than the local one. Only sets that are **currently active (enabled) in Typinator** are imported — inactive sets are never touched.

Before importing a set, the script removes it from Typinator's internal registry (via AppleScript) and then quits Typinator, copies the file, and restarts. This prevents Typinator from seeing both the old and new copy of the set and showing it twice.

If Typinator is not running when the script fires, the import phase is skipped entirely (the active-set list cannot be determined safely).

## Multi-Mac behaviour

Each Mac runs its own backup independently at 17:00. Multiple Macs can share the same Drive folder without conflicting:

- **Backup** — each machine only uploads sets modified on *that* machine since the last run, tracked via a per-machine marker file (`.last_run_<hostname>`) in the Drive folder. Two Macs never overwrite each other's marker.
- **Import** — each machine independently compares Drive timestamps against its own local files and only pulls what is newer. There is no locking or coordination needed.
- **Archive** — dated snapshots under `90. Backups/` are written by whichever machine ran last and do not conflict because the folder name is the date.

When you decommission a Mac, its `.last_run_<hostname>` file remains on Drive but is harmless. Delete it manually when convenient.

## Changing the schedule

Edit `com.yartow.typinator-backup.plist`, update `Hour` (and optionally `Minute`), then reload:

```bash
launchctl bootout gui/$(id -u)/com.yartow.typinator-backup
cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

## Uninstalling

```bash
launchctl bootout gui/$(id -u)/com.yartow.typinator-backup
rm ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

## Logs

Each run appends to `backup.log` on Google Drive, automatically trimmed to the last 1000 lines. Console output (if any) goes to `/tmp/typinator-backup.out` and errors to `/tmp/typinator-backup.err`.
