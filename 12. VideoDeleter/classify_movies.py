#!/usr/bin/env python3
"""
Classify deleted videos as full-length movies vs. personal clips.

Reads video_deleter.py's JSONL deletion log(s) and appends a CSV of
entries that look like downloaded movies rather than home videos. Fully
automatic, no manual review step - the rule is intentionally conservative
(folder + filename heuristics only), so it will under-match unusual movie
titles and over-match nothing it isn't confident about. Re-run any time;
existing rows in the CSV (including any added by hand) are preserved as-is
and never re-classified - only newly matched paths not already present are
appended.
"""

import argparse
import csv
import glob
import json
import os
import re
from typing import List, Optional, Tuple

# ----- CONFIG -----

ROOT = os.path.expanduser("~/Pictures/GooglePhotos")
MOVIE_MIN_DURATION = 1200.0  # 20 minutes
MOVIE_DIR_NAME = "Archive"

PERSONAL_RE = re.compile(
    r"^(video-\d{4}-\d{2}-\d{2}|MVI_\d+|VID-\d{8}|IMG_\d+|TRIM_\d+|DSC\d+|GOPR\d+|PXL_\d+|\d{8}_\d+$)",
    re.IGNORECASE,
)
RELEASE_TAG_RE = re.compile(
    r"720p|1080p|2160p|480p|BluRay|BRRip|BDRip|WEB-?DL|WEBRip|HDRip|DVDRip|HDTV|x264|x265|XviD|YIFY|YTS|\[[A-Za-z0-9.]+\]",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")
TITLE_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z']*$")

# ---------


def looks_like_movie_title(stem: str) -> bool:
    if RELEASE_TAG_RE.search(stem):
        return True
    words = [w for w in re.split(r"[.\s_-]+", stem) if w]
    alpha_words = [w for w in words if TITLE_WORD_RE.match(w) and len(w) >= 3]
    has_year = bool(YEAR_RE.search(stem))
    return len(alpha_words) >= 2 and (has_year or len(alpha_words) >= 3)


def is_movie(path: str) -> bool:
    fname = os.path.basename(path)
    if PERSONAL_RE.search(fname):
        return False
    stem = os.path.splitext(fname)[0]
    in_movie_dir = f"{os.sep}{MOVIE_DIR_NAME}{os.sep}" in path
    return in_movie_dir or looks_like_movie_title(stem)


def load_existing_csv(out_path: str) -> List[Tuple[str, float, int]]:
    if not os.path.exists(out_path):
        return []
    rows = []
    with open(out_path, newline="") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for line_num, row in enumerate(r, start=2):
            if len(row) < 3:
                print(f"  [WARN] {out_path}:{line_num}: expected 3 columns, got {len(row)} -- skipping")
                continue
            try:
                rows.append((row[0], float(row[1]), int(row[2])))
            except ValueError:
                print(f"  [WARN] {out_path}:{line_num}: unparseable score/class -- skipping")
    return rows


def load_deleted_entries(log_paths: List[str]) -> List[Tuple[str, float, int]]:
    entries = []
    for log_path in log_paths:
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("message") != "deleted_video":
                    continue
                dur = entry.get("duration_seconds")
                if dur is None:
                    continue
                entries.append((entry["path"], dur, entry.get("size_bytes", 0)))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=ROOT, help="Folder whose logs/ dir to read")
    parser.add_argument("--min-duration", type=float, default=MOVIE_MIN_DURATION,
                         help="Minimum duration in seconds to qualify as a movie")
    parser.add_argument("--out", default=None,
                         help="Output CSV path (default: <root>/logs/deleted_movies.csv)")
    args = parser.parse_args()

    log_glob = os.path.join(args.root, "logs", "video_delete_*.jsonl")
    log_paths = sorted(glob.glob(log_glob))
    if not log_paths:
        print(f"No log files matched {log_glob}")
        return

    out_path = args.out or os.path.join(args.root, "logs", "deleted_movies.csv")

    existing = load_existing_csv(out_path)
    existing_paths = {p for p, _, _ in existing}

    entries = load_deleted_entries(log_paths)
    matched = [(p, d, s) for p, d, s in entries if d >= args.min_duration and is_movie(p)]
    new_rows = [(p, d, s) for p, d, s in matched if p not in existing_paths]

    merged = existing + new_rows
    merged.sort(key=lambda r: -r[1])

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path", "duration_seconds", "size_bytes"])
        for p, d, s in merged:
            w.writerow([p, d, s])

    total = sum(s for _, _, s in merged)
    print(f"Read {len(entries)} deleted-video entries from {len(log_paths)} log file(s)")
    print(f"{len(existing)} existing rows kept, {len(new_rows)} new rows appended")
    print(f"{len(merged)} total ({total / (1024**3):.2f} GB)")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
