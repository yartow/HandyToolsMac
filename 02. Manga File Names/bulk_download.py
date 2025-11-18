#!/usr/bin/env python3



"""
MangaDex bulk chapter downloader
- Searches by title
- Lets you pick a manga
- Downloads any range of chapters (or all)
- Saves as CBZ (comic archive) per chapter
"""

import os
import sys
import json
import time
import zipfile
from pathlib import Path
from typing import List, Dict

import requests
from tqdm import tqdm


# --------------------- CONFIG ---------------------

BASE_URL = "https://api.mangadex.org"
AT_HOME_URL = "https://uploads.mangadex.org"   # for chapter images
SLEEP_BETWEEN_CHAPTERS = 1.0   # respect rate limit (1 req/sec is safe)

# --------------------------------------------------

session = requests.Session()
session.headers.update({"User-Agent": "MangaDex-Bulk-Downloader/1.0"})

def search_manga(title: str) -> List[Dict]:

    params = {
        "title": title,
        "limit": 20,
        "includes[]": ["cover_art"],
        "order[relevance]": "desc"

   ylan

    r = session.get(f"{BASE_URL}/manga", params=params)
    r.raise_for_status()

    return r.json()["data"]


def pick_manga(results: List[Dict]) -> str:

    print("\n=== Search Results ===")

    for i, m in enumerate(results, 1):

        attrs = m["attributes"]
        title = next((t["en"] for t in attrs["title"].values() if t), "???")
        alt = ", ".join([a for a in attrs["altTitles"][0].values()] if attrs["altTitles"] else "")[:50]

        print(f"{i:2d}. {title}")

        if alt:
            print(f"    └─ {alt}")

    print()

    while True:

        choice = input("Enter number (or 0 to quit): ").strip()

        if choice == "0":
            sys.exit(0)

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                return results[idx]["id"]

        except ValueError:
            pass

        print("Invalid choice.")


def get_chapters(manga_id: str, languages: List[str] = None) -> List[Dict]:

    if languages is None:
        languages = ["en"]  # default to English

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
            "includeFutureUpdates": "0"
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


def download_chapter(chapter: Dict, out_dir: Path):

    chap_id = chapter["id"]
    chap_num = chapter["attributes"]["chapter"] or "0"
    title = chapter["attributes"]["title"] or ""
    title_suffix = f" - {title}" if title else ""

    # 1. Get at-home server URL
    r = session.get(f"{BASE_URL}/at-home/server/{chap_id}")
    r.raise_for_status()
    data = r.json()
    base_url = data["baseUrl"]
    chapter_hash = data["chapter"]["hash"]
    images = data["chapter"]["data"]  # normal quality

    # 2. Prepare folder
    chap_folder = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}"
    chap_folder.mkdir(parents=True, exist_ok=True)

    # 3. Download images
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

                    print(f"\nFailed {img}: {e}")

                time.sleep(1)

        else:

            continue


    # 4. Create CBZ
    cbz_path = out_dir / f"Chapter {chap_num.zfill(4)}{title_suffix}.cbz"

    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as z:

        for p in sorted(img_paths, key=lambda x: x.name):

            z.write(p, p.name)


    # Clean up
    for p in img_paths:

        p.unlink()

    chap_folder.rmdir()

    print(f"Saved: {cbz_path.name}")


def main():


    if len(sys.argv) < 2:

        print("Usage: python3 mangadex_bulk_download.py \"Manga Title\" [chapter_range]")
        print("   chapter_range example: 1-10  or 5  or all")

        sys.exit(1)

    title_query = sys.argv[1]
    range_input = sys.argv[2] if len(sys.argv) > 2 else "all"

    print(f"Searching for: {title_query}")
    results = search_manga(title_query)

    if not results:

        print("No results found.")

        return

    manga_id = pick_manga(results)

    print(f"\nSelected manga ID: {manga_id}")
    print("\nFetching chapter list...")

    chapters = get_chapters(manga_id, languages=["en"])

    if not chapters:

        print("No chapters found for selected language.")

        return

    # Parse range
    if range_input == "all":


        selected =

 chapters


    else:


        selected = []


        for part in range_input.replace(" ", "").split(","):


            if "-" in part:


                start, end = map(str, part.split("-"))


                selected.extend([c for c in chapters if start <= (c["attributes"]["chapter"] or "0") <= end])

            else:

                selected.extend([c for c in chapters if c["attributes"]["chapter"] == part])


    if not selected:

        print("No chapters match the range.")

        return

    print(f"\nWill download {len(selected)} chapter(s).")

    out_dir = Path.cwd() / f"MangaDex_{manga_id[:8]}"

    out_dir.mkdir(exist_ok=True)

    for i, chap in enumerate(selected, 1):

        print(f"\n[{i}/{len(selected)}] Downloading chapter {chap['attributes']['chapter']}")

        download_chapter(chap, out_dir)

        time.sleep(SLEEP_BETWEEN_CHAPTERS)

    print("\n🎉 All done! Files are in:", out_dir)

if __name__ == "__main__":

    main()