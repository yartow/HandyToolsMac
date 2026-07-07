#!/usr/bin/env python3
"""
Delete byte-identical duplicate photos/videos from a folder tree.

Google Takeout exports a full copy of every photo into each album folder
it belongs to, plus another copy into its "Photos from YYYY" date folder.
This script finds files that are exact content duplicates (same size,
same hash) anywhere in the tree and deletes all but one copy.

Keeper selection: within a duplicate group, the copy that lives in a
named album folder is kept over a copy sitting in a generic "Photos from
YYYY" folder, since the album name carries context the date folder
doesn't. Ties are broken by shortest path.

Dry-run by default: scans and hashes, then prints what would be deleted.
Pass --delete to actually remove files and append a JSONL log entry per
deleted file (path, kept path, size_bytes) to logs/photo_dedup_<date>.jsonl.
Deletion is permanent - files are unlinked directly, not moved to Trash.
"""

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# ----- CONFIG -----
ROOT = os.path.expanduser("~/Pictures/GooglePhotos")
MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".gif", ".bmp", ".webp",
    ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf",
    ".mp4", ".mov", ".avi", ".3gp", ".mp",
}
EXCLUDE_DIRS = {"logs", "receipts"}
DATE_FOLDER_RE = re.compile(r"^Photos from \d{4}$", re.IGNORECASE)
CHUNK_SIZE = 1024 * 1024
# ---------


def find_candidates(root: str, exclude_dirs: set) -> list[Path]:
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            if Path(name).suffix.lower() in MEDIA_EXTENSIONS:
                matches.append(Path(dirpath) / name)
    return matches


def file_hash(path: Path) -> str:
    h = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def is_date_folder(path: Path) -> bool:
    return bool(DATE_FOLDER_RE.match(path.parent.name))


def choose_keeper(paths: list[Path]) -> Path:
    return min(paths, key=lambda p: (is_date_folder(p), len(str(p)), str(p)))


def find_duplicate_groups(root: str) -> list[list[Path]]:
    candidates = find_candidates(root, EXCLUDE_DIRS)
    print(f"Found {len(candidates)} media files.")

    by_size: dict[int, list[Path]] = {}
    for path in candidates:
        by_size.setdefault(path.stat().st_size, []).append(path)

    size_groups = [group for group in by_size.values() if len(group) > 1]
    to_hash = sum(len(g) for g in size_groups)
    print(f"{to_hash} files share a size with at least one other file — hashing to confirm duplicates...")

    by_hash: dict[tuple[int, str], list[Path]] = {}
    hashed = 0
    last_print = time.time()
    for group in size_groups:
        size = group[0].stat().st_size
        for path in group:
            digest = file_hash(path)
            by_hash.setdefault((size, digest), []).append(path)
            hashed += 1
            if time.time() - last_print > 5:
                print(f"  hashed {hashed}/{to_hash} files...")
                last_print = time.time()

    return [paths for paths in by_hash.values() if len(paths) > 1]


def delete_and_log(dup_groups: list[list[Path]], log_path: str) -> tuple[int, int]:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    deleted = 0
    freed = 0
    with open(log_path, "a") as log:
        for paths in dup_groups:
            keeper = choose_keeper(paths)
            for path in paths:
                if path == keeper:
                    continue
                size = path.stat().st_size
                try:
                    path.unlink()
                except OSError as e:
                    log.write(json.dumps({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "level": "ERROR",
                        "message": "delete_failed",
                        "path": str(path),
                        "error": str(e),
                    }) + "\n")
                    continue
                deleted += 1
                freed += size
                log.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "INFO",
                    "message": "deleted_duplicate",
                    "path": str(path),
                    "kept_path": str(keeper),
                    "size_bytes": size,
                }) + "\n")
    return deleted, freed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=ROOT, help="Folder to scan recursively")
    parser.add_argument("--delete", action="store_true",
                         help="Actually delete matching files (default is dry-run)")
    args = parser.parse_args()

    if not os.path.isdir(args.root):
        print(f"Directory not found: {args.root}")
        return

    print(f"Scanning {args.root} ...")
    dup_groups = find_duplicate_groups(args.root)
    print(f"Found {len(dup_groups)} groups of true duplicates.")

    total_bytes = 0
    total_files = 0
    for paths in dup_groups:
        keeper = choose_keeper(paths)
        for path in paths:
            if path != keeper:
                total_bytes += path.stat().st_size
                total_files += 1

    print(f"\n{total_files} duplicate files ({total_bytes / (1024 ** 3):.2f} GB)")

    if not args.delete:
        print("\nDry run only. Re-run with --delete to actually delete these files.")
        return

    log_path = os.path.join(
        args.root, "logs", f"photo_dedup_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    )
    deleted, freed = delete_and_log(dup_groups, log_path)
    print(f"\nDeleted {deleted} files, freed {freed / (1024 ** 3):.2f} GB.")
    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
