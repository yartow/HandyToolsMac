#!/usr/bin/env python3
"""Queues .enex files for import into UpNote, one after another, waiting for
each import to actually finish before starting the next -- and skipping files
dedup_checker reports as already imported.

Only ever triggers UpNote's own built-in "File > Import Notes > Evernote"
feature via UI actions (the same clicks you'd make by hand); never writes to
UpNote's live database. See CLAUDE.md for the safety design and the exact
button names this relies on (not yet fully live-verified -- run your first
file supervised, watching the screen, before trusting this with a big batch).
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from dedup_checker import (
    DEFAULT_UPNOTE_DB,
    load_existing_titles,
    looks_already_imported,
    match_enex,
    snapshot_upnote_db,
)
from enex_utils import iter_enex_files

# ----- CONFIG -----
POLL_INTERVAL_SECONDS = 10
STABLE_SECONDS_REQUIRED = 60  # note count/max(updatedAt) must be unchanged this long to call an import "done"
MAX_WAIT_SECONDS = 60 * 60  # give up waiting after an hour
OSASCRIPT_TIMEOUT_SECONDS = 120
# ---------


def run_applescript(script: str, timeout: int = OSASCRIPT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=["osascript"], returncode=1, stdout="", stderr=f"timed out after {timeout}s")


def trigger_import_dialog() -> None:
    result = run_applescript(
        '''
        tell application "UpNote" to activate
        delay 1
        tell application "System Events"
            tell process "UpNote"
                click menu item "Import Notes…" of menu "File" of menu bar item "File" of menu bar 1
            end tell
        end tell
        '''
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not open UpNote's Import Notes dialog: {result.stderr.strip()}")


def click_select_files_button() -> None:
    result = run_applescript(
        '''
        tell application "System Events"
            tell process "UpNote"
                click (first button of (entire contents of window 1) whose name is "Select .enex files")
            end tell
        end tell
        '''
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Could not find/click the 'Select .enex files' button -- UpNote's dialog layout may "
            f"have changed since this was written: {result.stderr.strip()}"
        )


def select_file_in_open_panel(enex_path: Path) -> None:
    escaped_path = str(enex_path.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    result = run_applescript(
        f'''
        tell application "System Events"
            delay 1
            keystroke "g" using {{command down, shift down}}
            delay 0.5
            keystroke "{escaped_path}"
            delay 0.3
            key code 36
            delay 1
            key code 36
        end tell
        '''
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not select {enex_path} in the file picker: {result.stderr.strip()}")


def click_import_notes_confirm_button() -> None:
    result = run_applescript(
        '''
        tell application "System Events"
            tell process "UpNote"
                click (first button of (entire contents of window 1) whose name is "Import Notes")
            end tell
        end tell
        '''
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not click the final 'Import Notes' confirm button: {result.stderr.strip()}")


def db_signature(db_path: Path) -> Tuple[int, Optional[float]]:
    db_copy = snapshot_upnote_db(db_path)
    try:
        conn = sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True)
        try:
            return conn.execute("SELECT COUNT(*), MAX(updatedAt) FROM notes").fetchone()
        finally:
            conn.close()
    finally:
        shutil.rmtree(db_copy.parent, ignore_errors=True)


def wait_for_import_to_finish(db_path: Path, baseline: Tuple[int, Optional[float]]) -> None:
    changed_from_baseline = False
    stable_since: Optional[float] = None
    last_signature = None
    start = time.monotonic()
    while time.monotonic() - start < MAX_WAIT_SECONDS:
        signature = db_signature(db_path)
        if not changed_from_baseline:
            if signature != baseline:
                changed_from_baseline = True
                last_signature = signature
        elif signature == last_signature:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= STABLE_SECONDS_REQUIRED:
                return
        else:
            stable_since = None
            last_signature = signature
        time.sleep(POLL_INTERVAL_SECONDS)
    print("    [WARN] Timed out waiting for the import to settle -- moving on, but double-check this one.")


def import_file(enex_path: Path, upnote_db: Path) -> None:
    print(f"    [INFO] Triggering UpNote import for {enex_path.name} ...")
    baseline = db_signature(upnote_db)
    trigger_import_dialog()
    time.sleep(1)
    click_select_files_button()
    select_file_in_open_panel(enex_path)
    time.sleep(1)
    click_import_notes_confirm_button()
    print("    [INFO] Import triggered -- waiting for it to finish ...")
    wait_for_import_to_finish(upnote_db, baseline)
    print(f"    [DONE] {enex_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="An .enex file or a folder of .enex files")
    parser.add_argument("--upnote-db", type=Path, default=DEFAULT_UPNOTE_DB)
    parser.add_argument(
        "--force", action="store_true", help="Import even if dedup_checker thinks the file is already imported"
    )
    args = parser.parse_args()

    if not args.upnote_db.exists():
        sys.exit(f"[ERROR] UpNote database not found at {args.upnote_db}")

    for enex_path in iter_enex_files(args.path):
        db_copy = snapshot_upnote_db(args.upnote_db)
        try:
            existing = load_existing_titles(db_copy)
        finally:
            shutil.rmtree(db_copy.parent, ignore_errors=True)

        matches = match_enex(enex_path, existing)
        if not args.force and looks_already_imported(matches):
            print(f"[SKIP] {enex_path.name} -- looks already imported")
            continue

        try:
            import_file(enex_path, args.upnote_db)
        except RuntimeError as e:
            print(f"[ERROR] {enex_path.name}: {e}", file=sys.stderr)
            print("    Stopping here -- fix the issue (see CLAUDE.md) before continuing.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
