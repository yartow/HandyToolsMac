#!/usr/bin/env python3
"""
Delete videos longer than a minimum duration from a folder tree.

Dry-run by default: scans recursively, probes duration with ffprobe, and
prints what would be deleted. Pass --delete to actually remove files and
append a JSONL log entry per deleted file (path, duration_seconds,
size_bytes) so other tools can reconcile their own state against it.
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# ----- CONFIG -----

ROOT = os.path.expanduser("~/Pictures/GooglePhotos")
MIN_DURATION = 5.0
VIDEO_EXTS = {
    ".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv",
    ".flv", ".webm", ".3gp", ".mpg", ".mpeg", ".mts", ".m2ts",
}
EXCLUDE_DIRS = {"logs", "receipts"}
MAX_WORKERS = 8

# ---------


def find_candidates(root: str, exclude_dirs: set) -> List[str]:
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in VIDEO_EXTS:
                matches.append(os.path.join(dirpath, fn))
    return matches


def get_duration(path: str) -> Tuple[str, Optional[float]]:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30,
        )
        val = out.stdout.strip()
        return path, float(val) if val else None
    except Exception:
        return path, None


def scan(root: str, exclude_dirs: set) -> Tuple[List[Tuple[str, float]], List[str]]:
    candidates = find_candidates(root, exclude_dirs)
    print(f"Scanning {len(candidates)} candidate video files with ffprobe...")

    readable: List[Tuple[str, float]] = []
    unreadable: List[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(get_duration, p) for p in candidates]
        for i, fut in enumerate(as_completed(futures), 1):
            path, dur = fut.result()
            if dur is None:
                unreadable.append(path)
            else:
                readable.append((path, dur))
            if i % 500 == 0:
                print(f"  probed {i}/{len(candidates)}")

    return readable, unreadable


def delete_and_log(paths: List[str], durations: dict, log_path: str) -> Tuple[int, int]:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    deleted = 0
    freed = 0
    with open(log_path, "a") as log:
        for p in paths:
            size = os.path.getsize(p)
            try:
                os.remove(p)
            except OSError as e:
                log.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "ERROR",
                    "message": "delete_failed",
                    "path": p,
                    "error": str(e),
                }) + "\n")
                continue
            deleted += 1
            freed += size
            dur = durations.get(p)
            log.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "message": "deleted_video",
                "path": p,
                "duration_seconds": round(dur, 2) if dur is not None else None,
                "duration_unreadable": dur is None,
                "size_bytes": size,
            }) + "\n")
    return deleted, freed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=ROOT, help="Folder to scan recursively")
    parser.add_argument("--min-duration", type=float, default=MIN_DURATION,
                         help="Minimum video duration in seconds to qualify for deletion")
    parser.add_argument("--include-unreadable", action="store_true",
                         help="Also delete videos whose duration ffprobe could not determine")
    parser.add_argument("--delete", action="store_true",
                         help="Actually delete matching files (default is dry-run)")
    args = parser.parse_args()

    readable, unreadable = scan(args.root, EXCLUDE_DIRS)

    to_delete = [(p, d) for p, d in readable if d >= args.min_duration]
    to_delete.sort(key=lambda x: -x[1])

    total_bytes = sum(os.path.getsize(p) for p, _ in to_delete)
    print(f"\n{len(to_delete)} videos >= {args.min_duration}s "
          f"({total_bytes / (1024**3):.2f} GB)")
    print(f"{len(unreadable)} files ffprobe could not read duration for")

    print("\nLongest 10:")
    for p, d in to_delete[:10]:
        print(f"  {d:8.1f}s  {p}")

    paths_to_delete = [p for p, _ in to_delete]
    durations = {p: d for p, d in to_delete}
    if args.include_unreadable:
        paths_to_delete += unreadable

    if not args.delete:
        print("\nDry run only. Re-run with --delete to actually delete these files.")
        return

    log_path = os.path.join(
        args.root, "logs", f"video_delete_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
    )
    deleted, freed = delete_and_log(paths_to_delete, durations, log_path)
    print(f"\nDeleted {deleted} files, freed {freed / (1024**3):.2f} GB.")
    print(f"Log written to {log_path}")


if __name__ == "__main__":
    main()
