#!/usr/bin/env python3
"""
Delete RAW/DNG files that have a matching JPG file of the same name.

Walks a folder tree recursively. Within each directory, files are grouped
by their name without extension. If a group contains both a RAW/DNG file
and a JPG file, the RAW/DNG is deleted (the JPG is kept).

Dry-run by default: scans and prints what would be deleted. Pass --delete
to actually remove files and append a JSONL log entry per deleted file
(path, size_bytes) to logs/raw_jpg_dedup_<date>.jsonl. Deletion is
permanent - files are unlinked directly, not moved to Trash.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ----- CONFIG -----
ROOT = os.path.expanduser("~/Pictures/GooglePhotos")
RAW_EXTENSIONS = {
    ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf",
    ".pef", ".srw", ".dcr", ".kdc", ".mrw", ".x3f", ".3fr", ".fff",
    ".iiq", ".mef", ".erf",
}
JPG_EXTENSIONS = {".jpg", ".jpeg"}
EXCLUDE_DIRS = {"logs", "receipts"}
# ---------


def find_raws_to_delete(root: str) -> list[Path]:
    to_delete: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        by_stem: dict[str, list[Path]] = {}
        for name in filenames:
            path = Path(dirpath) / name
            by_stem.setdefault(path.stem, []).append(path)

        for stem, paths in by_stem.items():
            exts = {p.suffix.lower() for p in paths}
            if not (exts & RAW_EXTENSIONS) or not (exts & JPG_EXTENSIONS):
                continue
            to_delete.extend(p for p in paths if p.suffix.lower() in RAW_EXTENSIONS)

    return to_delete


def delete_and_log(raws: list[Path], log_path: str) -> tuple[int, int]:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    deleted = 0
    freed = 0
    with open(log_path, "a") as log:
        for path in raws:
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
                "message": "deleted_raw",
                "path": str(path),
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
    raws = find_raws_to_delete(args.root)
    total_bytes = sum(p.stat().st_size for p in raws)
    print(f"\n{len(raws)} RAW/DNG files with a matching JPG ({total_bytes / (1024 ** 3):.2f} GB)")

    if not args.delete:
        print("\nDry run only. Re-run with --delete to actually delete these files.")
        return

    log_path = os.path.join(
        args.root, "logs", f"raw_jpg_dedup_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    )
    deleted, freed = delete_and_log(raws, log_path)
    print(f"\nDeleted {deleted} files, freed {freed / (1024 ** 3):.2f} GB.")
    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
