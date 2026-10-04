#!/usr/bin/env python3
"""Embed Google Takeout sidecar metadata (capture date, GPS) into EXIF.

Standalone extraction of deduplicAYde's exif_backfill.py + sidecars.py logic,
stripped of its Docker/SQLite/round-tracking scaffolding, parameterized to run
against any Takeout library folder.

Gap-fill only: never overwrites a tag a file already has. For each image
missing DateTimeOriginal and/or GPS EXIF, looks up its "<name>.json" Takeout
sidecar (by direct name, by truncated-name "title" index, or by "-edited"
fallback), pulls photoTakenTime/geoData from it, and writes only the missing
tags via a single batched `exiftool -csv=...` pass (one process spawn for the
whole library instead of one per file).
"""
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tqdm import tqdm

# ----- CONFIG -----
LIBRARY_DIR = Path("/Users/andrewyong/Pictures/GooglePhotos/library")
ACCOUNT_TIMEZONE = "Europe/Amsterdam"
CSV_PATH = Path(__file__).parent / "exif_backfill.csv"
EXIF_WRITABLE_SUFFIXES = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".heic", ".heif"}
# ---------

_ACCOUNT_TZ = ZoneInfo(ACCOUNT_TIMEZONE)
_tf = None


def _timezone_finder():
    global _tf
    if _tf is None:
        from timezonefinder import TimezoneFinder
        _tf = TimezoneFinder()
    return _tf


_SIDECAR_TITLE_INDEX: dict[Path, dict[str, Path]] = {}


def sidecar_dir_index(directory: Path) -> dict[str, Path]:
    """Map {lowercase original filename: sidecar path} for one directory.

    Takeout truncates ".supplemental-metadata.json" when the combined path
    would exceed its length limit, so filename-guessing misses those. Every
    sidecar's JSON body still carries the untruncated original filename in
    "title", so scan once per directory and index by that instead.
    """
    if directory in _SIDECAR_TITLE_INDEX:
        return _SIDECAR_TITLE_INDEX[directory]
    index: dict[str, Path] = {}
    for jf in directory.glob("*.json"):
        try:
            with open(jf) as f:
                data = json.load(f)
            title = data.get("title")
            if title:
                index[title.lower()] = jf
        except Exception:
            continue
    _SIDECAR_TITLE_INDEX[directory] = index
    return index


def find_sidecar(path: Path) -> Path | None:
    """Locate path's Takeout JSON sidecar (by file existence only), or None."""
    for sidecar in (path.with_name(path.name + ".json"), path.with_suffix(".json")):
        if sidecar.exists():
            return sidecar

    sidecar = sidecar_dir_index(path.parent).get(path.name.lower())
    if sidecar:
        return sidecar

    destemmed = re.sub(r"_\d+$", "", path.stem)
    if destemmed.endswith("-edited"):
        original = path.with_name(destemmed[: -len("-edited")] + path.suffix)
        if original != path:
            return find_sidecar(original)

    return None


def read_sidecar_json(sidecar: Path) -> dict | None:
    try:
        with open(sidecar) as f:
            return json.load(f)
    except Exception:
        return None


def _has_exif_datetime_original(path: Path) -> bool:
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="EXIF DateTimeOriginal", details=False)
        if tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime"):
            return True
    except Exception:
        pass
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img = Image.open(path)
        exif = getattr(img, "_getexif", lambda: None)()
        if exif:
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == "DateTimeOriginal":
                    return True
    except Exception:
        pass
    return False


def _has_exif_gps(path: Path) -> bool:
    try:
        import exifread
        with open(path, "rb") as f:
            tags = exifread.process_file(f, details=False)
        if any(str(k).startswith("GPS ") for k in tags):
            return True
    except Exception:
        pass
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        img = Image.open(path)
        exif = getattr(img, "_getexif", lambda: None)()
        if exif:
            for tag_id in exif:
                if TAGS.get(tag_id) == "GPSInfo":
                    return True
    except Exception:
        pass
    return False


def _sidecar_datetime_and_geo(path: Path) -> tuple[datetime | None, tuple[float, float] | None]:
    sidecar_path = find_sidecar(path)
    if not sidecar_path:
        return None, None
    data = read_sidecar_json(sidecar_path)
    if not data:
        return None, None
    dt = None
    ts = data.get("photoTakenTime", {}).get("timestamp")
    if ts:
        utc_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        geo = None
        for key in ("geoData", "geoDataExif"):
            g = data.get(key) or {}
            lat, lon = g.get("latitude"), g.get("longitude")
            if lat and lon and (lat != 0 or lon != 0):
                geo = (lat, lon)
                break
        tz = _ACCOUNT_TZ
        if geo:
            tzname = _timezone_finder().timezone_at(lat=geo[0], lng=geo[1])
            if tzname:
                tz = ZoneInfo(tzname)
        dt = utc_dt.astimezone(tz).replace(tzinfo=None)
    else:
        geo = None
    return dt, geo


def iter_candidate_files() -> list[Path]:
    return [
        p for p in LIBRARY_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in EXIF_WRITABLE_SUFFIXES
    ]


def build_csv() -> int:
    files = iter_candidate_files()
    print(f"Candidate scan: {len(files)} image file(s) under {LIBRARY_DIR}")

    rows = []
    for path in tqdm(files, desc="scanning", unit=" files"):
        needs_dt = not _has_exif_datetime_original(path)
        needs_gps = not _has_exif_gps(path)
        if not needs_dt and not needs_gps:
            continue

        dt, geo = _sidecar_datetime_and_geo(path)
        row = {"SourceFile": str(path)}
        wrote_anything = False

        if needs_dt and dt:
            row["DateTimeOriginal"] = dt.strftime("%Y:%m:%d %H:%M:%S")
            wrote_anything = True
        if needs_gps and geo:
            lat, lon = geo
            row["GPSLatitude"] = abs(lat)
            row["GPSLatitudeRef"] = "N" if lat >= 0 else "S"
            row["GPSLongitude"] = abs(lon)
            row["GPSLongitudeRef"] = "E" if lon >= 0 else "W"
            wrote_anything = True

        if wrote_anything:
            rows.append(row)

    fieldnames = ["SourceFile", "DateTimeOriginal", "GPSLatitude", "GPSLatitudeRef", "GPSLongitude", "GPSLongitudeRef"]
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def apply_csv() -> None:
    filelist_path = CSV_PATH.with_name("exif_backfill_files.txt")
    with open(CSV_PATH) as f, open(filelist_path, "w") as out:
        for row in csv.DictReader(f):
            out.write(row["SourceFile"] + "\n")

    print("Applying via exiftool (-overwrite_original_in_place, no backup copies kept)...")
    result = subprocess.run(
        ["exiftool", "-m", f"-csv={CSV_PATH}", "-overwrite_original_in_place", "-@", str(filelist_path)],
        # -m: ignore-minor-errors — several hundred files carry benign structural
        # warnings (e.g. "IFD0 pointer references previous IFD0 directory") that
        # exiftool otherwise refuses to write through even though nothing is lost.
        text=True, capture_output=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


def main() -> None:
    row_count = build_csv()
    print(f"\n{row_count} file(s) need a gap filled. CSV written to: {CSV_PATH}")
    if row_count == 0:
        return
    apply_csv()
    print(f"\nDone: applied EXIF gap-fill to {row_count} file(s).")


if __name__ == "__main__":
    main()
