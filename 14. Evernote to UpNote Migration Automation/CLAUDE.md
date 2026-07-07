# CLAUDE.md — 14. Evernote to UpNote Migration Automation

Developer notes scoped to this folder. See the repo-root `CLAUDE.md` for
general code-style conventions (this folder mostly follows them; the export
wrapper is `bash`, matching `04. TypinatorBackup/typinator_backup.sh`, rather
than the usual Python default, since it's a thin Docker-invocation wrapper).

## What's in here and why

- `enex_utils.py` — pure parsing helper, no I/O side effects beyond reading the
  given file. Reused by both `dedup_checker.py` and `upnote_import_automation.py`.
- `dedup_checker.py` — the safe, fully-tested piece. `snapshot_upnote_db()` /
  `load_existing_titles()` / `match_enex()` / `looks_already_imported()` are all
  imported directly by `upnote_import_automation.py` rather than duplicated.
- `upnote_import_automation.py` — the UI-automation piece. Not fully live-verified
  (see below).
- `run_evernote_export.sh` — thin wrapper, not a reimplementation. All actual
  Evernote-export logic lives in the third-party `evernote-backup` tool.

## UpNote's SQLite schema (confirmed live, 2026-07-02)

Live DB path: `~/Library/Containers/com.getupnote.desktop/Data/Library/Application Support/UpNote/upnote.sqlite3`
(sandboxed app; NOT `~/Library/Application Support/UpNote`). WAL mode — always
copy the `-wal`/`-shm` sidecars alongside the main file when snapshotting, or a
freshly-copied main file alone may be missing recent writes.

`notes` table (relevant columns): `id` (UpNote's own UUIDv7, unrelated to any
Evernote GUID), `title` TEXT, `createdAt`/`updatedAt` DOUBLE (epoch
**milliseconds**, not seconds), `deleted` INTEGER (0/1 — hard-deleted notes are
excluded from `dedup_checker`'s queries), `trashed` INTEGER (soft-deleted; these
ARE currently still counted as "existing" by `dedup_checker` since a trashed note
still occupies that title). 8,700 rows as of this writing.

**Open empirical question**: does UpNote's Evernote-import feature preserve the
original `<created>`/`<updated>` timestamps from the `.enex` file, or stamp new
import-time values? Not yet confirmed either way (no known-already-imported
`.enex` file was available to test against during this session). This only
affects the secondary "timestamp agreement" signal in `dedup_checker.py` — the
primary title-match-rate signal works regardless. If you get a chance: run
`dedup_checker.py --verbose` against an `.enex` file you know was already
imported, and see whether the timestamp-agreement number comes back high (~most
matches) or near-zero. Update this section with the answer once known.

## UpNote's Import UI (live investigation notes, 2026-07-02)

Confirmed via `System Events` (Accessibility permission was already granted to
the calling process for this session — if a fresh environment gets `-1719 "not
allowed assistive access"`, that's a one-time System Settings > Privacy &
Security > Accessibility grant needed, not a code bug):

- UpNote's menu bar: `Apple, UpNote, File, Edit, View, Format, Note, Window`.
- `File` menu items include `Import Notes…`, confirmed clickable via
  `click menu item "Import Notes…" of menu "File" of menu bar item "File" of menu bar 1`.
- Clicking it opens an in-window panel (not a separate OS window) — `windows`
  stayed at a single window named "UpNote" throughout.

**Not confirmed**: the exact accessibility path to the panel's "Select .enex
files" button and the final "Import Notes" confirm button. UpNote's Electron/
Chromium accessibility tree is deeply nested (6+ levels of generic `group`/`UI
element` containers with blank names) and walking it with `entire contents` +
a per-element `repeat` loop to find named buttons took several minutes and never
completed in this session — clearly too slow to ship as-is. `upnote_import_automation.py`
instead uses a single `whose name is "..."` filter clause (querying in one Apple
Event round trip rather than looping client-side), based on the button labels
UpNote's own help docs give for macOS (`Select .enex files` / `Import Notes`) --
**this has not been confirmed to actually find/click those buttons live.**

Also: interrupting a slow AppleScript mid-call while it had UpNote's dialog open
left the app in a state with zero open windows, and a subsequent `quit` AppleEvent
timed out (though the app did eventually quit on its own a bit later, and
relaunched cleanly with `open -a UpNote` — no data was affected either way, since
none of this touches the sqlite file). **Lesson for next time**: don't kill an
in-flight `osascript` process that's mid-interaction with the app; let it finish
or time out on its own.

**Before trusting `upnote_import_automation.py` with a real batch**: run it
against one low-stakes `.enex` file while watching the screen, and be ready to
update `click_select_files_button()` / `click_import_notes_confirm_button()` in
the script if the button names don't match (print the AppleScript error message
— it names which button it couldn't find).

## Safety invariants (do not weaken these without a good reason)

- `dedup_checker.py` and `upnote_import_automation.py` must only ever read a
  **copy** of `upnote.sqlite3` (see `snapshot_upnote_db()`), never the live file.
- `upnote_import_automation.py` must only ever trigger UpNote's own supported
  Import feature via UI actions — never write rows into `notes` directly. Direct
  DB writes would bypass UpNote's own ID generation, notebook/tag linking, and
  attachment handling (see the `notebookLinks`/`tagLinks`/`fileIds` columns,
  which look like they'd need careful, UpNote-internal-format-matching logic to
  populate correctly by hand) — not worth the risk when the supported import path
  already does it correctly.
