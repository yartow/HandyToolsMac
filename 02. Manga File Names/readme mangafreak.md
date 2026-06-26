# MangaFreak Chapter Downloader

Download manga chapters from [MangaFreak](https://ww2.mangafreak.me) as CBZ files — single chapter, a range, or everything at once.

## Requirements

```bash
pip install requests beautifulsoup4 tqdm
```

## Usage

```
python3 mangafreak_download.py URL [--list] [--chapters RANGE] [--delay SECS] [--debug]
```

Pass either the **series page URL** (recommended) or any **chapter URL**:

- Series page: `https://ww2.mangafreak.me/Manga/Mf_Ghost`
- Chapter URL: `https://ww2.mangafreak.me/Read1_Mf_Ghost_7`

The series page URL is the simpler form — the script fetches the full chapter list from it so it always knows exactly how many chapters exist.

### Arguments

| Argument | Description |
|---|---|
| `URL` | Series page (`.../Manga/Name`) or any chapter URL (`.../Read1_Name_N`) |
| `--list` | List all chapter numbers and titles, then exit |
| `--chapters RANGE` | Chapter range to download (default: all for series URL; single chapter for chapter URL) |
| `--delay SECS` | Seconds to wait between chapters (default: `1`) |
| `--debug` | Dump all `<img>` tags found on the page and exit |

### Chapter range formats

| Format | Downloads |
|---|---|
| _(omitted)_ | All chapters (series URL) or the single chapter in the URL (chapter URL) |
| `5` | Chapter 5 only |
| `1-10` | Chapters 1 through 10 |
| `all` | Every chapter (uses the chapter list to determine the exact end) |

---

## Examples

**Download everything (preferred):**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost
```

**List all chapters with titles:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost --list
```

**Download a range:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost --chapters 1-10
```

**Download a single chapter (chapter URL form):**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_7
```

**Slow down requests to avoid rate limiting:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Manga/Mf_Ghost --delay 3
```

---

## Listing chapters

`--list` fetches and displays all available chapter numbers and titles:

```
Fetching chapter list…

#         Title
──────────────────────────────────────────────────
Ch.1      The Beginning
Ch.2      Qualifying Round
Ch.3      Race Day
…
Ch.47     Final Lap

47 chapter(s) total.
```

The chapter list is fetched via three strategies in order:
1. **Series index page** — scrapes the `/Manga/Name` page directly
2. **Chapter select dropdown** — reads a `<select>` dropdown on the reader page
3. **Link scan** — scans any chapter-shaped links on the reader page

You can combine `--list` with `--debug` to see which strategy matched and which URLs were tried.

---

## Output

Chapters are saved as `.cbz` files in a folder named after the series slug, in your current directory:

```
Read1_Mf_Ghost/
├── Chapter_0001.cbz
├── Chapter_0002.cbz
└── ...
```

---

## Image selector fallback

The script tries 10 different CSS selectors in order to find page images, covering the most common MangaFreak page layouts. If a chapter prints `No images found`, run with `--debug` to inspect what's on the page:

```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --debug
```

This dumps every `<img>` tag found. If the site layout has changed, paste the output and the correct selector can be added.
