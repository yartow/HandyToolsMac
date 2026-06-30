# Typinator Daily Backup

Automatically backs up Typinator sets that were modified today to Google Drive every day at 5 PM. A rolling 7-day archive is kept for recovery. Works on any Mac that has this repo cloned to `~/Documents/GitHub/HandyToolsMac` and Google Drive mounted.

## Folder structure on Google Drive

```
My Drive/08. Software/01. OSX macOS/05. Typinator/
├── *.tyset               ← always holds today's latest changed sets
└── 90. Backups/
    ├── 2026-06-01/       ← dated snapshots, one per day
    ├── 2026-05-31/
    └── ...               ← automatically deleted after 7 days
```

## Configuration

Open `typinator_backup.sh` and adjust the variables at the top if needed:

| Variable | Default | Description |
|---|---|---|
| `TYPINATOR_SETS` | `~/Library/Application Support/Typinator/Sets` | Where Typinator stores your sets |
| `GDRIVE_ROOT` | auto-detected from `~/Library/CloudStorage/` | Google Drive mount — works regardless of which account is signed in |
| `BACKUP_BASE` | `{GDRIVE_ROOT}/My Drive/08. Software/01. OSX macOS/05. Typinator` | Destination folder on Google Drive |
| `MAX_DAYS` | `7` | How many days of archive to keep in `90. Backups/` |

The schedule (default 17:00) is set in `com.yartow.typinator-backup.plist` under `StartCalendarInterval > Hour`.

## Installation (repeat on each Mac)

**1. Copy the launchd agent:**

```bash
cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist \
   ~/Library/LaunchAgents/
```

**2. Load it (macOS Ventura and later):**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

**3. Verify it is loaded:**

```bash
launchctl list | grep typinator
```

You should see a line with `com.yartow.typinator-backup` and `-` in the PID column (no PID means it's scheduled but not currently running — that's correct).

> The plist uses `$HOME` to find the script, so no path editing is needed on each Mac as long as the repo is cloned to the same relative location (`~/Documents/GitHub/HandyToolsMac`).

## Running the backup manually

```bash
bash ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/typinator_backup.sh
```

Check `05. Typinator/backup.log` afterwards to see what was copied.

## Import behaviour (Drive → local)

After the backup phase, the script also pulls sets down from Drive if the Drive copy is newer than the local one. Only sets that are **currently active (enabled) in Typinator** are imported — inactive sets are never touched.

Before importing a set, the script removes it from Typinator's internal registry (via AppleScript) and then quits Typinator, copies the file, and restarts. This prevents Typinator from seeing both the old and new copy of the set and showing it twice.

If Typinator is not running when the script fires, the import phase is skipped entirely (the active-set list cannot be determined safely).

## Multi-Mac behaviour

Each Mac runs its own backup independently at 17:00. Multiple Macs can share the same Drive folder without conflicting:

- **Backup** — each machine only uploads sets modified on *that* machine since the last run, tracked via a per-machine marker file (`.last_run_<hostname>`) in the Drive folder. Two Macs never overwrite each other's marker.
- **Import** — each machine independently compares Drive timestamps against its own local files and only pulls what is newer. There is no locking or coordination needed.
- **Archive** — dated snapshots under `90. Backups/` are written by whichever machine ran last and do not conflict because the folder name is the date.

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

Each run appends to `05. Typinator/backup.log` on Google Drive. Console output (if any) goes to `/tmp/typinator-backup.out` and errors to `/tmp/typinator-backup.err`.
