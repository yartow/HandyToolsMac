#!/usr/bin/env python3
"""Checks whether notes in an .enex file already exist in UpNote, so you can
tell whether a file has already been imported.

Only ever reads a temporary COPY of UpNote's local sqlite3 database -- never
opens or modifies the live file UpNote itself is using.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from enex_utils import iter_enex_files, iter_notes

# ----- CONFIG -----
DEFAULT_UPNOTE_DB = (
    Path.home()
    / "Library/Containers/com.getupnote.desktop/Data/Library/Application Support/UpNote/upnote.sqlite3"
)
TIMESTAMP_TOLERANCE_MS = 2_000  # allow a couple seconds of drift when comparing createdAt
ALREADY_IMPORTED_THRESHOLD = 0.95  # title-match rate at/above which a file is treated as already imported
# ---------


@dataclass(frozen=True)
class NoteMatch:
    title: str
    already_exists: bool
    timestamp_agrees: bool


def snapshot_upnote_db(db_path: Path) -> Path:
    """Snapshots the live sqlite3 db (including any in-flight WAL writes) into
    a temp dir via the SQLite backup API, so the copy can't straddle an
    inconsistent mid-write state the way copying the file(s) directly could.
    The caller is responsible for deleting the returned path's parent dir."""
    tmp_dir = Path(tempfile.mkdtemp(prefix="upnote-dedup-"))
    dest = tmp_dir / db_path.name
    src_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dest_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
    return dest


def load_existing_titles(db_copy: Path) -> Dict[str, List[Tuple[Optional[float], Optional[float]]]]:
    conn = sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT title, createdAt, updatedAt FROM notes WHERE deleted = 0").fetchall()
    finally:
        conn.close()
    existing: Dict[str, List[Tuple[Optional[float], Optional[float]]]] = {}
    for title, created_at, updated_at in rows:
        existing.setdefault(title or "", []).append((created_at, updated_at))
    return existing


def match_enex(
    enex_path: Path, existing: Dict[str, List[Tuple[Optional[float], Optional[float]]]]
) -> List[NoteMatch]:
    matches: List[NoteMatch] = []
    for note in iter_notes(enex_path):
        candidates = existing.get(note.title, [])
        already_exists = bool(candidates)
        timestamp_agrees = already_exists and any(
            note.created_ms is not None
            and created_at is not None
            and abs(created_at - note.created_ms) <= TIMESTAMP_TOLERANCE_MS
            for created_at, _ in candidates
        )
        matches.append(NoteMatch(note.title, already_exists, timestamp_agrees))
    return matches


def title_match_rate(matches: List[NoteMatch]) -> float:
    if not matches:
        return 0.0
    return sum(1 for m in matches if m.already_exists) / len(matches)


def looks_already_imported(matches: List[NoteMatch], threshold: float = ALREADY_IMPORTED_THRESHOLD) -> bool:
    return bool(matches) and title_match_rate(matches) >= threshold


def print_report(enex_path: Path, matches: List[NoteMatch], verbose: bool) -> None:
    if not matches:
        print(f"{enex_path.name}: no notes found")
        return

    total = len(matches)
    title_matches = sum(1 for m in matches if m.already_exists)
    timestamp_agreements = sum(1 for m in matches if m.timestamp_agrees)
    rate = title_matches / total

    if verbose:
        for m in matches:
            if not m.already_exists:
                print(f"    [new] {m.title}")
            elif m.timestamp_agrees:
                print(f"    [title+date match] {m.title}")
            else:
                print(f"    [title match only] {m.title}")

    verdict = (
        "looks already imported" if rate >= ALREADY_IMPORTED_THRESHOLD
        else "looks partially imported" if title_matches
        else "looks new"
    )
    timestamp_note = f", {timestamp_agreements}/{title_matches} also match created-date" if title_matches else ""
    print(
        f"{enex_path.name}: {title_matches}/{total} ({rate:.0%}) notes already appear in UpNote by title"
        f"{timestamp_note} -- {verdict}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="An .enex file or a folder of .enex files")
    parser.add_argument("--upnote-db", type=Path, default=DEFAULT_UPNOTE_DB)
    parser.add_argument("--verbose", action="store_true", help="List each note's match status")
    args = parser.parse_args()

    if not args.upnote_db.exists():
        sys.exit(f"[ERROR] UpNote database not found at {args.upnote_db}")
    if not args.path.exists():
        sys.exit(f"[ERROR] Path not found: {args.path}")

    db_copy = snapshot_upnote_db(args.upnote_db)
    try:
        existing = load_existing_titles(db_copy)
    finally:
        shutil.rmtree(db_copy.parent, ignore_errors=True)

    for enex_path in iter_enex_files(args.path):
        matches = match_enex(enex_path, existing)
        print_report(enex_path, matches, args.verbose)


if __name__ == "__main__":
    main()
