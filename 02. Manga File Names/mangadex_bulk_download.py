#!/usr/bin/env python3
"""
MangaDex bulk chapter downloader

Usage examples:
  python3 mangadex_bulk_download.py -s "One Piece"
  python3 mangadex_bulk_download.py -s "One Piece" 1-10
  python3 mangadex_bulk_download.py -s "Naruto" -l ja all
  python3 mangadex_bulk_download.py --id a96676be-9137-4fea-a2b4-33c9f5f9fa70
  python3 mangadex_bulk_download.py --id a96676be-9137-4fea-a2b4-33c9f5f9fa70 1-10
  python3 mangadex_bulk_download.py --url https://mangadex.org/title/<id> 5-20
  python3 mangadex_bulk_download.py -s "One Piece" --list
  python3 mangadex_bulk_download.py --resume "One Piece/checkpoint.json"
"""

import json
import re
import sys
import time
import zipfile
import argparse
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from tqdm import tqdm


BASE_URL = "https://api.mangadex.org"
SLEEP_BETWEEN_CHAPTERS = 1.0

LANGUAGE_MAP = {
    "en": "en", "english": "en",
    "ja": "ja", "japanese": "ja",
    "fr": "fr", "french": "fr",
    "de": "de", "german": "de",
    "es": "es", "spanish": "es",
    "pt": "pt", "portuguese": "pt",
    "it": "it", "italian": "it",
    "ru": "ru", "russian": "ru",
    "zh": "zh", "chinese": "zh",
    "ko": "ko", "korean": "ko",
}

session = requests.Session()
session.headers.update({"User-Agent": "MangaDex-Bulk-Downloader/1.0"})


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def search_manga(title: str, language: str = "en") -> List[Dict]:
    params = {
        "title": title,
        "limit": 20,
        "includes[]": ["cover_art"],
        "order[relevance]": "desc",
        "availableTranslatedLanguage[]": language,
    }
    r = session.get(f"{BASE_URL}/manga", params=params)
    r.raise_for_status()
    return r.json()["data"]


def get_manga_by_id(manga_id: str) -> Dict:
    r = session.get(f"{BASE_URL}/manga/{manga_id}", params={"includes[]": ["cover_art"]})
    r.raise_for_status()
    return r.json()["data"]


def extract_id_from_url(url: str) -> Optional[str]:
    match = re.search(r"mangadex\.org/title/([a-f0-9-]{36})", url)
    return match.group(1) if match else None


def get_title(manga: Dict) -> str:
    attrs = manga["attributes"]
    titles = attrs.get("title", {})
    return titles.get("en") or next(iter(titles.values()), "Unknown")


def safe_dirname(title: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "", title)
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Unknown"


def pick_manga(results: List[Dict]) -> str:
    print("\nI've found these results:")
    for i, m in enumerate(results, 1):
        title = get_title(m)
        alts = m["attributes"].get("altTitles", [])
        alt_str = ""
        if alts:
            alt_vals = list(alts[0].values())
            if alt_vals:
                alt_str = f" ({alt_vals[0]})"
        print(f"{i}. {title}{alt_str}")

    print()
    while True:
        choice = input("Which one do you mean? Type in the number: ").strip()
        if choice == "0":
            sys.exit(0)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                return results[idx]["id"]
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(results)} (or 0 to quit).")


def get_chapters(manga_id: str, languages: List[str]) -> List[Dict]:
    offset = 0
    limit = 100
    chapters = []
    while True:
        params = {
            "manga": manga_id,
            "translatedLanguage[]": languages,
            "limit": limit,
            "offset": offset,
            "order[chapter]": "asc",
            "includeFutureUpdates": "0",
        }
        r = session.get(f"{BASE_URL}/chapter", params=params)
        r.raise_for_status()
        data = r.json()
        chapters.extend(data["data"])
        if len(data["data"]) < limit:
            break
        offset += limit
        time.sleep(0.2)
    return chapters


def list_chapters(chapters: List[Dict], manga_title: str, lang: str):
    print(f"\nAvailable chapters for '{manga_title}' ({lang}):\n")
    for c in chapters:
        attrs = c["attributes"]
        num = attrs.get("chapter") or "?"
        title = attrs.get("title") or ""
        group_rel = next(
            (r for r in c.get("relationships", []) if r["type"] == "scanlation_group"),
            None,
        )
        group = ""
        if group_rel and group_rel.get("attributes"):
            group = f"  [{group_rel['attributes'].get('name', '')}]"
        suffix = f" — {title}" if title else ""
        print(f"  Ch {num:<8}{suffix}{group}")
    print(f"\nTotal: {len(chapters)} chapter(s)")


def _chap_num(chapter: Dict) -> float:
    try:
        return float(chapter["attributes"]["chapter"] or "0")
    except (ValueError, TypeError):
        return 0.0


def filter_chapters(chapters: List[Dict], range_input: str) -> List[Dict]:
    if range_input == "all":
        return chapters

    selected = []
    for part in range_input.replace(" ", "").split(","):
        if "-" in part:
            start, end = part.split("-", 1)
            lo, hi = float(start), float(end)
            selected.extend(c for c in chapters if lo <= _chap_num(c) <= hi)
        else:
            target = float(part)
            selected.extend(c for c in chapters if _chap_num(c) == target)
    return selected


# ---------------------------------------------------------------------------
# Checkpoint file
# ---------------------------------------------------------------------------

def checkpoint_path(out_dir: Path) -> Path:
    """Return a non-existing checkpoint path, incrementing if needed."""
    base = out_dir / "checkpoint.json"
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = out_dir / f"checkpoint_{n}.json"
        if not candidate.exists():
            return candidate
        n += 1


def write_checkpoint(
    out_dir: Path,
    run_info: Dict,
    failed: List[Dict],
    incomplete: List[Dict],
):
    """
    Write a human-readable JSON checkpoint file.

    failed entries:   {"chapter_num", "chapter_id", "reason"}
    incomplete entries: {"chapter_num", "chapter_id", "folder", "missing_images",
                         "image_urls"}
    """
    path = checkpoint_path(out_dir)

    total_issues = len(failed) + len(incomplete)
    resume_cmd = (
        f"python3 mangadex_bulk_download.py --resume \"{path}\""
    )

    data = {
        "_notes": [
            "This is a MangaDex downloader checkpoint file.",
            "It was created because one or more chapters could not be fully downloaded.",
            f"To retry all failed/incomplete chapters, run: {resume_cmd}",
            "Image URLs below are point-in-time and may have expired.",
            "The image filenames are stable — use them to locate pages on MangaDex manually.",
        ],
        "checkpoint_version": 1,
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "resume_command": resume_cmd,
        "run": run_info,
        "summary": {
            "total_requested": run_info.get("total_requested", "?"),
            "total_downloaded_ok": run_info.get("total_requested", 0) - total_issues,
            "failed_chapters": len(failed),
            "incomplete_chapters": len(incomplete),
        },
        "failed_chapters": failed,
        "incomplete_chapters": incomplete,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return path


def load_checkpoint(checkpoint_file: Path) -> Dict:
    return json.loads(checkpoint_file.read_text())


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------

def download_chapter(
    chapter: Dict,
    out_dir: Path,
    run_info: Dict,
) -> Dict:
    """
    Returns a result dict:
      status:  "ok" | "already_exists" | "failed" | "incomplete"
      chapter_num, chapter_id
      reason:  set on "failed"
      missing_images: list of {filename, url} on "incomplete"
      folder:  str path on "incomplete"
    """
    chap_id = chapter["id"]
    chap_num = chapter["attributes"]["chapter"] or "0"
    title = chapter["attributes"]["title"] or ""
    title_suffix = f" - {title}" if title else ""
    result_base = {"chapter_num": chap_num, "chapter_id": chap_id}

    cbz_path = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}.cbz"
    if cbz_path.exists():
        print(f"Already downloaded: {cbz_path.name} — skipping.")
        return {**result_base, "status": "already_exists"}

    # Fetch at-home server URL with retries
    data = None
    for attempt in range(4):
        try:
            r = session.get(f"{BASE_URL}/at-home/server/{chap_id}", timeout=30)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if attempt == 3:
                reason = f"server URL unavailable: {e}"
                print(f"\nFailed to get server URL for chapter {chap_num}: {e}")
                return {**result_base, "status": "failed", "reason": reason}
            time.sleep(3 * (attempt + 1))

    base_url = data["baseUrl"]
    chapter_hash = data["chapter"]["hash"]
    images = data["chapter"]["data"]

    chap_folder = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}"
    chap_folder.mkdir(parents=True, exist_ok=True)

    # Thread-local sessions for parallel downloads
    _local = threading.local()

    def get_session():
        if not hasattr(_local, "session"):
            s = requests.Session()
            s.headers.update({"User-Agent": "MangaDex-Bulk-Downloader/1.0"})
            _local.session = s
        return _local.session

    def fetch_image(img: str):
        url = f"{base_url}/data/{chapter_hash}/{img}"
        local_path = chap_folder / img
        if local_path.exists():
            return img, local_path, None  # (name, path, error)
        s = get_session()
        for attempt in range(3):
            try:
                resp = s.get(url, timeout=20)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
                return img, local_path, None
            except Exception as e:
                if attempt == 2:
                    tqdm.write(f"  Failed: {img}: {e}")
                    return img, None, {"filename": img, "url": url, "error": str(e)}
                time.sleep(1)

    results_by_idx = [None] * len(images)
    with tqdm(total=len(images), desc=f"Ch {chap_num}", leave=False) as bar:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(fetch_image, img): idx
                for idx, img in enumerate(images)
            }
            for future in as_completed(futures):
                results_by_idx[futures[future]] = future.result()
                bar.update(1)

    good_paths = [r[1] for r in results_by_idx if r and r[1] is not None]
    missing = [r[2] for r in results_by_idx if r and r[2] is not None]

    if missing:
        # Leave folder on disk; do not create CBZ
        print(
            f"  Chapter {chap_num}: {len(missing)} page(s) failed — "
            "folder kept, no CBZ created."
        )
        return {
            **result_base,
            "status": "incomplete",
            "folder": str(chap_folder),
            "missing_images": missing,
        }

    # All pages downloaded — pack into CBZ and clean up
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(good_paths, key=lambda x: x.name):
            z.write(p, p.name)

    for p in good_paths:
        p.unlink()
    try:
        chap_folder.rmdir()
    except OSError:
        pass

    print(f"Saved: {cbz_path.name}")
    return {**result_base, "status": "ok"}


# ---------------------------------------------------------------------------
# Resume from checkpoint
# ---------------------------------------------------------------------------

def resume_checkpoint(checkpoint_file: Path):
    print(f"Resuming from: {checkpoint_file}")
    data = load_checkpoint(checkpoint_file)
    run_info = data["run"]

    manga_id = run_info["manga_id"]
    manga_title = run_info["manga_title"]
    lang = run_info["language"]
    out_dir = checkpoint_file.parent

    print(f"Manga: {manga_title}  |  Language: {lang}")

    failed_ids = {e["chapter_id"] for e in data.get("failed_chapters", [])}
    incomplete_ids = {e["chapter_id"] for e in data.get("incomplete_chapters", [])}
    retry_ids = failed_ids | incomplete_ids

    if not retry_ids:
        print("No chapters to retry in this checkpoint.")
        return

    print(f"Retrying {len(retry_ids)} chapter(s)...")

    all_chapters = get_chapters(manga_id, [lang])
    to_retry = [c for c in all_chapters if c["id"] in retry_ids]

    # For incomplete chapters, remove images already on disk from missing list
    # (the folder is still there; fetch_image will skip existing files)

    new_failed: List[Dict] = []
    new_incomplete: List[Dict] = []

    for i, chap in enumerate(to_retry, 1):
        chap_num = chap["attributes"]["chapter"]
        print(f"\n[{i}/{len(to_retry)}] Retrying chapter {chap_num}")
        result = download_chapter(chap, out_dir, run_info)
        if result["status"] == "failed":
            new_failed.append({"chapter_num": result["chapter_num"],
                                "chapter_id": result["chapter_id"],
                                "reason": result["reason"]})
        elif result["status"] == "incomplete":
            new_incomplete.append({"chapter_num": result["chapter_num"],
                                    "chapter_id": result["chapter_id"],
                                    "folder": result["folder"],
                                    "missing_images": result["missing_images"]})
        time.sleep(SLEEP_BETWEEN_CHAPTERS)

    _print_and_save_summary(
        out_dir, run_info, new_failed, new_incomplete,
        total=len(to_retry),
        source=f"resumed from {checkpoint_file.name}",
    )


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download manga chapters from MangaDex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -s "One Piece"
  %(prog)s -s "One Piece" 1-10
  %(prog)s -s "Naruto" -l ja all
  %(prog)s -s "One Piece" --list
  %(prog)s --id a96676be-9137-4fea-a2b4-33c9f5f9fa70
  %(prog)s --id a96676be-9137-4fea-a2b4-33c9f5f9fa70 1-10
  %(prog)s --url https://mangadex.org/title/<id> 5-20
  %(prog)s --resume "One Piece/checkpoint.json"
        """,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-s", "--search", metavar="TITLE", help="Search for a manga by title")
    source.add_argument("--id", metavar="MANGA_ID", help="Use a MangaDex manga ID directly")
    source.add_argument("--url", metavar="URL", help="Direct MangaDex title URL")
    source.add_argument("--resume", metavar="CHECKPOINT", help="Resume from a checkpoint file")

    parser.add_argument("-u", "--site", metavar="SITE", default="mangadex.org",
                        help="Site to search on (default: mangadex.org)")
    parser.add_argument("-l", "--language", metavar="LANG", default="en",
                        help="Language code or name (default: en)")
    parser.add_argument("chapters", nargs="?", default="all", metavar="CHAPTERS",
                        help="Chapter range: all, 5, 1-10, or 1,3,5-8 (default: all)")
    parser.add_argument("--list", action="store_true",
                        help="List available chapters and exit without downloading")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Summary + checkpoint writing
# ---------------------------------------------------------------------------

def _print_and_save_summary(
    out_dir: Path,
    run_info: Dict,
    failed: List[Dict],
    incomplete: List[Dict],
    total: int,
    source: str = "run",
):
    ok_count = total - len(failed) - len(incomplete)
    print(f"\nAll done! Files saved in: {out_dir}")
    print(f"\nSummary ({source}):")
    print(f"  Downloaded OK : {ok_count}/{total}")
    if failed:
        print(f"  Failed        : {len(failed)} chapter(s)")
        for e in failed:
            print(f"    Ch {e['chapter_num']}: {e['reason']}")
    if incomplete:
        print(f"  Incomplete    : {len(incomplete)} chapter(s)")
        for e in incomplete:
            n_missing = len(e["missing_images"])
            print(f"    Ch {e['chapter_num']}: {n_missing} page(s) missing — folder kept")

    if failed or incomplete:
        run_info["total_requested"] = total
        cp = write_checkpoint(out_dir, run_info, failed, incomplete)
        print(f"\nCheckpoint written: {cp}")
        print(f"To retry:  python3 mangadex_bulk_download.py --resume \"{cp}\"")
    else:
        print("  All chapters downloaded successfully.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()

    if args.resume:
        resume_checkpoint(Path(args.resume))
        return

    lang = LANGUAGE_MAP.get(args.language.lower(), args.language.lower())

    # Resolve manga ID and title
    if args.url:
        manga_id = extract_id_from_url(args.url)
        if not manga_id:
            print(f"Could not extract a MangaDex title ID from: {args.url}")
            sys.exit(1)
        manga = get_manga_by_id(manga_id)
        manga_title = get_title(manga)
        print(f"Using: {manga_title}")
    elif args.id:
        manga_id = args.id.strip()
        manga = get_manga_by_id(manga_id)
        manga_title = get_title(manga)
        print(f"Using: {manga_title}")
    else:
        site = args.site.lower().rstrip("/")
        if "mangadex" not in site:
            print(f"Warning: only mangadex.org is supported. Ignoring -u {args.site}.")

        print(f'Searching for "{args.search}" on mangadex.org (language: {lang}) ...')
        results = search_manga(args.search, lang)

        if not results:
            print("No results found.")
            sys.exit(1)

        if len(results) == 1:
            manga_id = results[0]["id"]
            manga_title = get_title(results[0])
            print(f"Found: {manga_title}")
        else:
            manga_id = pick_manga(results)
            manga = get_manga_by_id(manga_id)
            manga_title = get_title(manga)

        print(f"\nTo access this manga directly next time, use:")
        print(f"  python3 mangadex_bulk_download.py --id {manga_id}\n")

    print("Fetching chapter list...")
    chapters = get_chapters(manga_id, [lang])

    if not chapters:
        print(f"No chapters found for language '{lang}'.")
        sys.exit(1)

    if args.list:
        list_chapters(chapters, manga_title, lang)
        sys.exit(0)

    selected = filter_chapters(chapters, args.chapters)

    if not selected:
        print(f"No chapters match '{args.chapters}'.")
        sys.exit(1)

    print(f"Will download {len(selected)} chapter(s).")

    out_dir = Path.cwd() / safe_dirname(manga_title)
    out_dir.mkdir(exist_ok=True)

    # Reconstruct the effective command for the checkpoint file
    effective_cmd = f"mangadex_bulk_download.py --id {manga_id} -l {lang} {args.chapters}"

    run_info = {
        "manga_id": manga_id,
        "manga_title": manga_title,
        "language": lang,
        "requested_chapters": args.chapters,
        "effective_command": effective_cmd,
        "total_requested": len(selected),
    }

    failed: List[Dict] = []
    incomplete: List[Dict] = []

    for i, chap in enumerate(selected, 1):
        chap_num = chap["attributes"]["chapter"]
        print(f"\n[{i}/{len(selected)}] Downloading chapter {chap_num}")
        result = download_chapter(chap, out_dir, run_info)
        if result["status"] == "failed":
            failed.append({
                "chapter_num": result["chapter_num"],
                "chapter_id": result["chapter_id"],
                "reason": result["reason"],
            })
        elif result["status"] == "incomplete":
            incomplete.append({
                "chapter_num": result["chapter_num"],
                "chapter_id": result["chapter_id"],
                "folder": result["folder"],
                "missing_images": result["missing_images"],
            })
        time.sleep(SLEEP_BETWEEN_CHAPTERS)

    _print_and_save_summary(
        out_dir, run_info, failed, incomplete,
        total=len(selected),
    )


if __name__ == "__main__":
    main()
