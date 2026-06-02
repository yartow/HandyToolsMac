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

Pass the URL of **any** chapter of the series — the script derives the series slug and chapter number from it automatically.

### Arguments

| Argument | Description |
|---|---|
| `URL` | URL of any chapter (e.g. `.../Read1_Mf_Ghost_1`) |
| `--list` | List all chapter numbers and titles, then exit |
| `--chapters RANGE` | Chapter range to download (default: the chapter in the URL) |
| `--delay SECS` | Seconds to wait between chapters (default: `1`) |
| `--debug` | Dump all `<img>` tags found on the page and exit |

### Chapter range formats

| Format | Downloads |
|---|---|
| _(omitted)_ | Only the chapter in the URL |
| `5` | Chapter 5 only |
| `1-10` | Chapters 1 through 10 |
| `all` | Every chapter, stopping at the first 404 |

---

## Examples

**List all chapters with titles:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --list
```

**Download a single chapter:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1
```

**Download a range:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters 1-10
```

**Download everything:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters all
```

**Slow down requests to avoid rate limiting:**
```bash
python3 mangafreak_download.py https://ww2.mangafreak.me/Read1_Mf_Ghost_1 --chapters all --delay 3
```

---

## Listing chapters

`--list` fetches and displays all available chapter numbers and titles before any download:

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

It tries three strategies in order to find the chapter list:
1. **Series index page** — derives the manga page URL from the slug (e.g. `/Manga/Mf_Ghost`) and scrapes the chapter list there
2. **Chapter select dropdown** — falls back to the reader page and reads a `<select>` dropdown if one exists
3. **Link scan** — scans any chapter-shaped links on the reader page itself

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
