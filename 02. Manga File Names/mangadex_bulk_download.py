#!/usr/bin/env python3
"""
MangaDex bulk chapter downloader

Usage examples:
  python3 mangadex_bulk_download.py -s "One Piece"
  python3 mangadex_bulk_download.py -s "One Piece" 1-10
  python3 mangadex_bulk_download.py -s "Naruto" -l ja all
  python3 mangadex_bulk_download.py --id a96676be-9137-4fea-a2b4-33c9f5f9fa70
  python3 mangadex_bulk_download.py --url https://mangadex.org/title/<id> 5-20
  python3 mangadex_bulk_download.py -s "One Piece" --list
"""

import re
import sys
import time
import zipfile
import argparse
from pathlib import Path
from typing import List, Dict, Optional

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
    """Convert a manga title to a safe directory name."""
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
            selected.extend(
                c for c in chapters
                if lo <= _chap_num(c) <= hi
            )
        else:
            target = float(part)
            selected.extend(
                c for c in chapters
                if _chap_num(c) == target
            )
    return selected


def download_chapter(chapter: Dict, out_dir: Path):
    chap_id = chapter["id"]
    chap_num = chapter["attributes"]["chapter"] or "0"
    title = chapter["attributes"]["title"] or ""
    title_suffix = f" - {title}" if title else ""

    cbz_path = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}.cbz"
    if cbz_path.exists():
        print(f"Already downloaded: {cbz_path.name} — skipping.")
        return

    for attempt in range(4):
        try:
            r = session.get(f"{BASE_URL}/at-home/server/{chap_id}", timeout=30)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if attempt == 3:
                print(f"\nFailed to get server URL for chapter {chap_num}: {e}")
                return
            time.sleep(3 * (attempt + 1))
    base_url = data["baseUrl"]
    chapter_hash = data["chapter"]["hash"]
    images = data["chapter"]["data"]

    chap_folder = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}"
    chap_folder.mkdir(parents=True, exist_ok=True)

    img_paths = []
    for img in tqdm(images, desc=f"Ch {chap_num}", leave=False):
        url = f"{base_url}/data/{chapter_hash}/{img}"
        local_path = chap_folder / img

        if local_path.exists():
            img_paths.append(local_path)
            continue

        for attempt in range(3):
            try:
                resp = session.get(url, timeout=30)
                resp.raise_for_status()
                local_path.write_bytes(resp.content)
                img_paths.append(local_path)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"\nFailed to download {img}: {e}")
                time.sleep(1)

    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(img_paths, key=lambda x: x.name):
            z.write(p, p.name)

    for p in img_paths:
        p.unlink()
    chap_folder.rmdir()

    print(f"Saved: {cbz_path.name}")


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
        """,
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("-s", "--search", metavar="TITLE", help="Search for a manga by title")
    source.add_argument("--id", metavar="MANGA_ID", help="Skip search using a MangaDex manga ID directly")
    source.add_argument("--url", metavar="URL", help="Direct MangaDex title URL")

    parser.add_argument(
        "-u", "--site",
        metavar="SITE",
        default="mangadex.org",
        help="Site to search on (default: mangadex.org)",
    )
    parser.add_argument(
        "-l", "--language",
        metavar="LANG",
        default="en",
        help="Language code or name (default: en)",
    )
    parser.add_argument(
        "chapters",
        nargs="?",
        default="all",
        metavar="CHAPTERS",
        help="Chapter range: all, 5, 1-10, or 1,3,5-8 (default: all)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available chapters and exit without downloading",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    lang = LANGUAGE_MAP.get(args.language.lower(), args.language.lower())

    # Resolve manga ID
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
            print(f"Warning: only mangadex.org is supported as a search target. Ignoring -u {args.site}.")

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

    # Fetch chapters
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

    for i, chap in enumerate(selected, 1):
        print(f"\n[{i}/{len(selected)}] Downloading chapter {chap['attributes']['chapter']}")
        download_chapter(chap, out_dir)
        time.sleep(SLEEP_BETWEEN_CHAPTERS)

    print(f"\nAll done! Files saved in: {out_dir}")


if __name__ == "__main__":
    main()
