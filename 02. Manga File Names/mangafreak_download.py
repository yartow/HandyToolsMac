#!/usr/bin/env python3
"""
MangaFreak chapter downloader

Downloads all page images for one or more chapters and saves them as CBZ files.

Usage:
  python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1
  python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters 1-10
  python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --debug
"""

import re
import sys
import time
import zipfile
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ww2.mangafreak.me/",
}

session = requests.Session()
session.headers.update(HEADERS)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def parse_chapter_url(url: str):
    """
    Extract (base_prefix, series_slug, chapter_number) from a URL like
    https://ww2.mangafreak.me/Read1_Mf_Ghost_7
    Returns (origin, 'Read1_Mf_Ghost', 7)
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.strip("/")

    # Last token separated by _ is expected to be the chapter number
    match = re.match(r"^(.+?)_(\d+)$", path)
    if not match:
        raise ValueError(
            f"Cannot parse chapter number from URL: {url}\n"
            "Expected pattern like /Read1_Mf_Ghost_1"
        )
    slug = match.group(1)
    chapter = int(match.group(2))
    return origin, slug, chapter


def build_chapter_url(origin: str, slug: str, chapter: int) -> str:
    return f"{origin}/{slug}_{chapter}"


# ---------------------------------------------------------------------------
# Page scraping
# ---------------------------------------------------------------------------

# Ordered list of CSS selectors tried in sequence.
# The first one that yields ≥1 <img> tag with a src wins.
IMAGE_SELECTORS = [
    "#chapter_container img",
    "#images img",
    ".chapter-container img",
    ".page-image img",
    ".reader-main img",
    "img.manga-page",
    "img[src*='manga']",
    "img[src*='chapter']",
    "img[src*='.jpg']",
    "img[src*='.png']",
    "img[src*='.webp']",
]


def fetch_page_html(url: str) -> BeautifulSoup:
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def find_images(soup: BeautifulSoup, base_url: str, debug: bool = False) -> list[str]:
    """Return absolute URLs for all chapter page images found on the page."""

    if debug:
        print("\n--- DEBUG: all <img> tags on the page ---")
        for img in soup.find_all("img"):
            print(f"  src={img.get('src', '')}  class={img.get('class', '')}  id={img.get('id', '')}")
        print("--- end img dump ---\n")

    for selector in IMAGE_SELECTORS:
        imgs = soup.select(selector)
        urls = []
        for img in imgs:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            src = src.strip()
            if src and not src.endswith(".gif"):  # skip nav/ui icons
                urls.append(urljoin(base_url, src))
        if urls:
            if debug:
                print(f"Matched selector: {selector!r}  ({len(urls)} images)")
            return urls

    return []


def find_next_chapter_link(soup: BeautifulSoup, base_url: str) -> str | None:
    """
    Look for a 'Next chapter' / 'Chapter N' link below the reader.
    Returns an absolute URL or None.
    """
    # Strategy 1: anchor whose text looks like "Chapter N"
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).lower()
        if re.search(r"chapter\s+\d+", text) and "next" not in text.lower():
            # could be current; skip
            pass
        if "next chapter" in text or re.search(r"chapter\s+\d+", text):
            href = a["href"].strip()
            if href and not href.startswith("javascript"):
                return urljoin(base_url, href)

    # Strategy 2: any link whose href matches the slug_N pattern and is > current
    return None


# ---------------------------------------------------------------------------
# Downloading
# ---------------------------------------------------------------------------

def download_image(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30, stream=True)
            r.raise_for_status()
            dest.write_bytes(r.content)
            return True
        except Exception as e:
            if attempt == 2:
                print(f"  Failed: {url} — {e}")
            time.sleep(1)
    return False


def save_cbz(image_paths: list[Path], cbz_path: Path):
    with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(image_paths, key=lambda x: x.name):
            z.write(p, p.name)
    for p in image_paths:
        p.unlink()
    image_paths[0].parent.rmdir()


def download_chapter(origin: str, slug: str, chapter: int, out_dir: Path, debug: bool):
    url = build_chapter_url(origin, slug, chapter)
    print(f"\nChapter {chapter}: {url}")

    try:
        soup = fetch_page_html(url)
    except requests.HTTPError as e:
        print(f"  HTTP error {e.response.status_code} — stopping.")
        return False

    images = find_images(soup, url, debug=debug)

    if not images:
        print(
            "  No images found. Try --debug to inspect what's on the page.\n"
            "  The site may require JavaScript — see README for Playwright fallback."
        )
        return False

    print(f"  Found {len(images)} page(s)")

    chap_folder = out_dir / f"Chapter_{chapter:04d}"
    chap_folder.mkdir(parents=True, exist_ok=True)

    img_paths = []
    for idx, img_url in enumerate(tqdm(images, desc=f"Ch {chapter}", leave=False), 1):
        ext = Path(urlparse(img_url).path).suffix or ".jpg"
        dest = chap_folder / f"{idx:03d}{ext}"
        if download_image(img_url, dest):
            img_paths.append(dest)

    if not img_paths:
        print("  All downloads failed.")
        chap_folder.rmdir()
        return False

    cbz_path = out_dir / f"Chapter_{chapter:04d}.cbz"
    save_cbz(img_paths, cbz_path)
    print(f"  Saved: {cbz_path.name}")
    return True


# ---------------------------------------------------------------------------
# Argument parsing & main
# ---------------------------------------------------------------------------

def parse_chapter_range(spec: str, start: int) -> range:
    spec = spec.strip().lower()
    if spec == "all":
        # We don't know the end; caller handles iteration until 404
        return None  # type: ignore
    if "-" in spec:
        a, b = spec.split("-", 1)
        return range(int(a), int(b) + 1)
    return range(int(spec), int(spec) + 1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download manga chapters from MangaFreak as CBZ files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters 1-10
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_5 --chapters all
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --debug
        """,
    )
    parser.add_argument("url", help="URL of any chapter (e.g. .../Read1_Mf_Ghost_1)")
    parser.add_argument(
        "--chapters",
        metavar="RANGE",
        default=None,
        help="Chapter range: 1-10, 5, all (default: just the chapter in the URL)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Dump all <img> tags found on the first page and exit",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        metavar="SECS",
        help="Seconds to wait between chapters (default: 1)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        origin, slug, start_chapter = parse_chapter_url(args.url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    series_name = slug.split("/")[-1]  # e.g. Read1_Mf_Ghost
    out_dir = Path.cwd() / series_name
    out_dir.mkdir(exist_ok=True)

    # Debug mode: inspect first page only, then exit
    if args.debug:
        print(f"Fetching {args.url} ...")
        soup = fetch_page_html(args.url)
        find_images(soup, args.url, debug=True)
        sys.exit(0)

    # Determine which chapters to download
    if args.chapters is None:
        chapters = range(start_chapter, start_chapter + 1)
        download_all = False
    elif args.chapters.strip().lower() == "all":
        chapters = None
        download_all = True
    else:
        chapters = parse_chapter_range(args.chapters, start_chapter)
        download_all = False

    if download_all:
        # Iterate from start_chapter until we hit a 404 / no images
        chapter = start_chapter
        while True:
            ok = download_chapter(origin, slug, chapter, out_dir, debug=False)
            if not ok:
                print(f"\nStopped at chapter {chapter}.")
                break
            chapter += 1
            time.sleep(args.delay)
    else:
        for chapter in chapters:
            download_chapter(origin, slug, chapter, out_dir, debug=False)
            time.sleep(args.delay)

    print(f"\nDone. Files saved in: {out_dir}")


if __name__ == "__main__":
    main()
