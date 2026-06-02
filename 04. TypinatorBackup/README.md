# Typinator Daily Backup

Automatically backs up Typinator sets that were modified today to Google Drive every day at 5 PM. A rolling 7-day archive is kept for recovery.

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

Open `typinator_backup.sh` and adjust the variables at the top:

| Variable | Default | Description |
|---|---|---|
| `TYPINATOR_SETS` | `~/Library/Application Support/Typinator/Sets` | Where Typinator stores your sets |
| `BACKUP_BASE` | `My Drive/08. Software/01. OSX macOS/05. Typinator` | Destination folder on Google Drive |
| `MAX_DAYS` | `7` | How many days of archive to keep in `90. Backups/` |

The schedule (default 17:00) is set in `com.yartow.typinator-backup.plist` under `StartCalendarInterval > Hour`.

## Installation

**1. Copy the launchd agent (requires sudo because LaunchAgents is root-owned):**

```bash
sudo cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist \
   ~/Library/LaunchAgents/
```

**2. Load it (use `bootstrap` for macOS Ventura and later):**

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

**3. Verify it is loaded:**

```bash
launchctl list | grep typinator
```

You should see a line with `com.yartow.typinator-backup` and `-` in the PID column.

## Running the backup manually

```bash
bash ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/typinator_backup.sh
```

Check `05. Typinator/backup.log` afterwards to see what was copied.

## Changing the schedule

Edit `com.yartow.typinator-backup.plist`, update `Hour` (and optionally `Minute`), then reload:

```bash
launchctl bootout gui/$(id -u)/com.yartow.typinator-backup
sudo cp ~/Documents/GitHub/HandyToolsMac/04.\ TypinatorBackup/com.yartow.typinator-backup.plist \
   ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

## Uninstalling

```bash
launchctl bootout gui/$(id -u)/com.yartow.typinator-backup
sudo rm ~/Library/LaunchAgents/com.yartow.typinator-backup.plist
```

## Logs

Each run appends to `05. Typinator/backup.log`. Console output (if any) goes to `/tmp/typinator-backup.out` and errors to `/tmp/typinator-backup.err`.
