#!/usr/bin/env python3
"""
MangaFreak chapter downloader

Downloads all page images for one or more chapters and saves them as CBZ files.

Usage:
  python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost
  python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost --chapters 1-10
  python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost --list
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

def classify_url(url: str) -> tuple[str, str, str, int | None]:
    """
    Parse any MangaFreak URL.

    Returns (url_type, origin, name, chapter_or_None) where url_type is
    "series"  for /Manga/SeriesName  (chapter=None)
    "chapter" for /Read1_Slug_N      (chapter=N)
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.strip("/")

    if re.match(r"(?i)Manga/", path):
        series_part = path.split("/", 1)[1]
        return "series", origin, series_part, None

    match = re.match(r"^(.+?)_(\d+)$", path)
    if match:
        return "chapter", origin, match.group(1), int(match.group(2))

    raise ValueError(
        f"Cannot parse URL: {url}\n"
        "Accepted forms:\n"
        "  Series page : https://ww2.mangafreak.me/Manga/Mf_Ghost\n"
        "  Chapter page: https://ww2.mangafreak.me/Read1_Mf_Ghost_1"
    )


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
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
            return BeautifulSoup(r.text, "html.parser")
        except requests.HTTPError:
            raise
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Page fetch error (attempt {attempt + 1}/3): {e} — retrying...")
            time.sleep(3 * (attempt + 1))


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
    cbz_path = out_dir / f"Chapter_{chapter:04d}.cbz"

    if cbz_path.exists():
        print(f"\nChapter {chapter}: already downloaded, skipping.")
        return True

    print(f"\nChapter {chapter}: {url}")

    try:
        soup = fetch_page_html(url)
    except requests.HTTPError as e:
        print(f"  HTTP error {e.response.status_code} — stopping.")
        return False
    except Exception as e:
        print(f"  Failed to fetch page: {e} — stopping.")
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

    save_cbz(img_paths, cbz_path)
    print(f"  Saved: {cbz_path.name}")
    return True


# ---------------------------------------------------------------------------
# Chapter listing
# ---------------------------------------------------------------------------

# (chapter_number_str, title) — number as a string to preserve decimals like "10.5"
ChapterEntry = tuple[str, str]

# Selectors tried in order against the series index page
_CHAPTER_LIST_SELECTORS = [
    ("a", {"href": re.compile(r"Read\d+_")}),   # any anchor whose href looks like a chapter link
]

# Selectors for a <select> dropdown found on the reader page
_SELECT_SELECTORS = [
    'select[name="chapter"]',
    'select.chapter-select',
    'select.selectpicker',
    'select',
]


def _extract_chapter_num(text: str, href: str) -> str | None:
    """Pull a chapter number from anchor text or href."""
    # Prefer text like "Chapter 7" or just "7" / "7.5"
    m = re.search(r"chapter\s*([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if m:
        return m.group(1)
    # Fall back to last numeric token in the href path
    m = re.search(r"_([0-9]+(?:\.[0-9]+)?)/?$", href)
    if m:
        return m.group(1)
    return None


def _clean_title(raw: str, chapter_num: str) -> str:
    """Strip the chapter-number prefix from the title text, if any."""
    # Remove leading "Chapter N" / "Ch.N" / bare number
    cleaned = re.sub(
        rf"^(chapter\s*{re.escape(chapter_num)}[:\s\-–—]*|ch\.?\s*{re.escape(chapter_num)}[:\s\-–—]*)",
        "",
        raw,
        flags=re.I,
    ).strip(" :-–—")
    return cleaned or raw.strip()


def _parse_from_series_page(soup: BeautifulSoup, origin: str) -> list[ChapterEntry]:
    """Extract chapter list from the manga's series/index page."""
    results: list[ChapterEntry] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if not re.search(r"Read\d+_", href):
            continue
        abs_href = urljoin(origin, href)
        # Only keep links that match the chapter-URL pattern (end with _<number>)
        if not re.search(r"_\d+/?$", href):
            continue

        text = a.get_text(" ", strip=True)
        num = _extract_chapter_num(text, href)
        if num is None or num in seen:
            continue
        seen.add(num)
        title = _clean_title(text, num)
        results.append((num, title))

    # Sort ascending by chapter number
    results.sort(key=lambda x: float(x[0]))
    return results


def _parse_from_select(soup: BeautifulSoup) -> list[ChapterEntry]:
    """Extract chapter list from a <select> dropdown on the reader page."""
    for selector in _SELECT_SELECTORS:
        sel = soup.select_one(selector)
        if sel is None:
            continue
        results: list[ChapterEntry] = []
        seen: set[str] = set()
        for opt in sel.find_all("option"):
            value = opt.get("value", "")
            text  = opt.get_text(" ", strip=True)
            num   = _extract_chapter_num(text, value)
            if num is None or num in seen:
                continue
            seen.add(num)
            title = _clean_title(text, num)
            results.append((num, title))
        if results:
            results.sort(key=lambda x: float(x[0]))
            return results
    return []


def _discover_slug(soup: BeautifulSoup) -> str | None:
    """Scan chapter links on a series page to find the Read1_Slug style slug."""
    for a in soup.find_all("a", href=True):
        m = re.search(r"(Read\d+_[^/]+?)_\d+/?$", a["href"])
        if m:
            return m.group(1)
    return None


def fetch_chapter_list(origin: str, slug: str, debug: bool = False) -> list[ChapterEntry]:
    """
    Return all (chapter_number, title) pairs for the series.

    Strategy 1 — Series index page at /Manga/<slug-without-Read1_prefix>
    Strategy 2 — <select> dropdown on chapter 1's reader page
    Strategy 3 — Raw scan: walk chapter 1 page for any chapter-shaped links
    """
    # Derive series slug: "Read1_Mf_Ghost" → "Mf_Ghost"
    series_part = re.sub(r"^Read\d+_", "", slug.split("/")[-1])
    series_url  = f"{origin}/Manga/{series_part}"

    if debug:
        print(f"[list] Trying series page: {series_url}")

    # Strategy 1: series index page
    try:
        soup = fetch_page_html(series_url)
        chapters = _parse_from_series_page(soup, origin)
        if chapters:
            if debug:
                print(f"[list] Found {len(chapters)} chapters via series page")
            return chapters
    except Exception as e:
        if debug:
            print(f"[list] Series page failed: {e}")

    # Strategy 2 & 3: reader page for chapter 1
    reader_url = build_chapter_url(origin, slug, 1)
    if debug:
        print(f"[list] Falling back to reader page: {reader_url}")
    try:
        soup = fetch_page_html(reader_url)
        chapters = _parse_from_select(soup)
        if chapters:
            if debug:
                print(f"[list] Found {len(chapters)} chapters via select dropdown")
            return chapters
        # Strategy 3: any chapter-shaped links on the reader page
        chapters = _parse_from_series_page(soup, origin)
        if chapters:
            if debug:
                print(f"[list] Found {len(chapters)} chapters via link scan on reader page")
            return chapters
    except Exception as e:
        if debug:
            print(f"[list] Reader page failed: {e}")

    return []


def _print_chapter_list(chapters: list[ChapterEntry]):
    if not chapters:
        print(
            "No chapters found. The site may use JavaScript rendering.\n"
            "Try --debug to inspect the raw page."
        )
        return
    width = max(len(c[0]) for c in chapters)
    print(f"\n{'#':<{width + 2}}  Title")
    print("─" * 50)
    for num, title in chapters:
        label = f"Ch.{num}"
        print(f"{label:<{width + 4}}  {title}" if title else label)
    print(f"\n{len(chapters)} chapter(s) total.")


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
  %(prog)s https://ww2.mangafreak.me/Manga/Mf_Ghost              # download all
  %(prog)s https://ww2.mangafreak.me/Manga/Mf_Ghost --list
  %(prog)s https://ww2.mangafreak.me/Manga/Mf_Ghost --chapters 1-10
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1            # single chapter
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters 1-10
  %(prog)s https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --debug
        """,
    )
    parser.add_argument(
        "url",
        help="Series page (.../Manga/Name) or any chapter (.../Read1_Name_1)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all chapter numbers and titles, then exit",
    )
    parser.add_argument(
        "--chapters",
        metavar="RANGE",
        default=None,
        help="Chapter range: 1-10, 5, all (default: all for series URL, single chapter for chapter URL)",
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
        url_type, origin, name, start_chapter = classify_url(args.url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    chapters_list: list[ChapterEntry] | None = None
    slug: str

    if url_type == "series":
        try:
            soup = fetch_page_html(args.url)
        except Exception as e:
            print(f"Error fetching series page: {e}")
            sys.exit(1)
        slug = _discover_slug(soup) or f"Read1_{name}"
        chapters_list = _parse_from_series_page(soup, origin)
        if not chapters_list and not args.list and not args.debug:
            print("No chapters found on series page. Try --debug to inspect the page.")
            sys.exit(1)
        start_chapter = int(float(chapters_list[0][0])) if chapters_list else 1
    else:
        slug = name

    out_dir = Path.cwd() / slug
    out_dir.mkdir(exist_ok=True)

    # List mode
    if args.list:
        if chapters_list is None:
            print("Fetching chapter list…")
            chapters_list = fetch_chapter_list(origin, slug, debug=args.debug)
        _print_chapter_list(chapters_list)
        sys.exit(0)

    # Debug mode: inspect first page only, then exit
    if args.debug:
        target = args.url if url_type == "series" else build_chapter_url(origin, slug, start_chapter)
        print(f"Fetching {target} ...")
        soup = fetch_page_html(target)
        find_images(soup, target, debug=True)
        sys.exit(0)

    # Series URL or --chapters all → use the chapter list so we know the definite end
    use_list = (url_type == "series") or (
        args.chapters is not None and args.chapters.strip().lower() == "all"
    )

    if use_list:
        if chapters_list is None:
            print("Fetching chapter list…")
            chapters_list = fetch_chapter_list(origin, slug, debug=args.debug)
        if not chapters_list:
            print("Could not build chapter list. Try specifying a range with --chapters 1-N.")
            sys.exit(1)

        if args.chapters and args.chapters.strip().lower() != "all":
            allowed: set[int] | None = set(parse_chapter_range(args.chapters, start_chapter))
        else:
            allowed = None

        for num_str, _ in chapters_list:
            num = int(float(num_str))
            if allowed is not None and num not in allowed:
                continue
            download_chapter(origin, slug, num, out_dir, debug=False)
            time.sleep(args.delay)
    else:
        if args.chapters is None:
            chapter_iter: range = range(start_chapter, start_chapter + 1)
        else:
            chapter_iter = parse_chapter_range(args.chapters, start_chapter)
        for chapter in chapter_iter:
            download_chapter(origin, slug, chapter, out_dir, debug=False)
            time.sleep(args.delay)

    print(f"\nDone. Files saved in: {out_dir}")


if __name__ == "__main__":
    main()
