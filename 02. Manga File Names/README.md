# MangaDex Bulk Downloader

Download manga chapters from [MangaDex](https://mangadex.org) as CBZ files — by title search, direct URL, or manga ID.

## Requirements

```bash
pip install requests tqdm
```

## Usage

```
python3 mangadex_bulk_download.py (-s TITLE | --id ID | --url URL | --resume FILE) [CHAPTERS] [-l LANG]
```

### Arguments

| Argument | Description |
|---|---|
| `-s TITLE` | Search for a manga by title |
| `--id MANGA_ID` | Use a MangaDex manga ID directly (skip search) |
| `--url URL` | Use a full MangaDex title URL |
| `--resume FILE` | Retry chapters from a checkpoint file |
| `CHAPTERS` | Chapter range to download (default: `all`) |
| `-l LANG` | Language code or name (default: `en`) |
| `--list` | List available chapters without downloading |

### Chapter range formats

| Format | Downloads |
|---|---|
| `all` | Every available chapter |
| `5` | Chapter 5 only |
| `1-10` | Chapters 1 through 10 |
| `1,3,5-8` | Chapters 1, 3, and 5 through 8 |

---

## Examples

**Search and download all chapters:**
```bash
python3 mangadex_bulk_download.py -s "One Piece"
```

**Search and download a range:**
```bash
python3 mangadex_bulk_download.py -s "One Piece" 1-10
```

**List available chapters without downloading:**
```bash
python3 mangadex_bulk_download.py -s "Fullmetal Alchemist" --list
python3 mangadex_bulk_download.py --id dd8a907a-3850-4f95-ba03-ba201a8399e3 --list
```

**Use a direct MangaDex URL:**
```bash
python3 mangadex_bulk_download.py --url "https://mangadex.org/title/dd8a907a-3850-4f95-ba03-ba201a8399e3"
python3 mangadex_bulk_download.py --url "https://mangadex.org/title/dd8a907a-3850-4f95-ba03-ba201a8399e3" 5-20
```

**Use a manga ID directly (fastest, no search step):**
```bash
python3 mangadex_bulk_download.py --id dd8a907a-3850-4f95-ba03-ba201a8399e3
python3 mangadex_bulk_download.py --id dd8a907a-3850-4f95-ba03-ba201a8399e3 50-108
```

**Download in a different language:**
```bash
python3 mangadex_bulk_download.py -s "One Piece" -l ja
python3 mangadex_bulk_download.py --id dd8a907a-... -l french 1-50
```

---

## Search results

When multiple results are found, each one is shown with its MangaDex URL so you can verify the correct entry before selecting:

```
I've found these results:
 1. Fullmetal Alchemist (FMA)
    https://mangadex.org/title/dd8a907a-3850-4f95-ba03-ba201a8399e3
 2. Fullmetal Alchemist (Çelik Simyacı)
    https://mangadex.org/title/f9c9614d-0657-44c6-9c33-47fd58cd51b3
 ...

Which one do you mean? Type in the number:
```

> **Tip:** MangaDex sometimes has multiple entries for the same manga (different scanlations, regions, or duplicate uploads) with very different chapter counts. If `--list` shows far fewer chapters than expected, open the URL shown next to your selection in a browser and compare. Then use `--url` or `--id` with the correct entry.

After selecting, the script prints a direct-access shortcut:

```
To access this manga directly next time, use:
  python3 mangadex_bulk_download.py --id dd8a907a-3850-4f95-ba03-ba201a8399e3
```

---

## Output

Chapters are saved as `.cbz` files in a folder named after the manga in your current directory:

```
Fullmetal Alchemist/
├── Chapter 0001 - Two Alchemists Part 1.cbz
├── Chapter 0002 - Two Alchemists Part 2.cbz
└── ...
```

---

## Checkpoint files

If one or more chapters fail or download incompletely, the script:

- **Does not create a CBZ** for the affected chapter — the partial image folder is left on disk for inspection
- **Writes a checkpoint file** (`checkpoint.json`) in the manga folder
- If a checkpoint file already exists, a new one is created with an incremented name (`checkpoint_1.json`, `checkpoint_2.json`, ...)

### Checkpoint file contents

The checkpoint file is a human-readable JSON file containing:
- The effective command that was run
- Manga ID, title, language, and chapter range
- A per-chapter breakdown of failures, including the image filename and URL for each missing page (so you can check whether the image is actually broken on MangaDex)

Example:
```json
{
  "run": {
    "manga_title": "Hunter x Hunter",
    "requested_chapters": "3-100",
    "effective_command": "mangadex_bulk_download.py --id db692d58-... -l en 3-100"
  },
  "failed_chapters": [
    { "chapter_num": "131", "reason": "server URL unavailable: Connection aborted" }
  ],
  "incomplete_chapters": [
    {
      "chapter_num": "145",
      "folder": "Hunter x Hunter/Chapter 0145",
      "missing_images": [
        { "filename": "page03.jpg", "url": "https://uploads.mangadex.org/...", "error": "522 Server Error" }
      ]
    }
  ]
}
```

> **Note:** Image URLs in the checkpoint are point-in-time and may have expired. The filenames are stable and can be used to find the page on MangaDex manually.

### Resuming from a checkpoint

```bash
python3 mangadex_bulk_download.py --resume "Hunter x Hunter/checkpoint.json"
```

This retries only the failed and incomplete chapters. Already-downloaded CBZ files are skipped automatically.

---

## End-of-run summary

After every run the script prints a summary:

```
Summary:
  Downloaded OK : 96/98
  Failed        : 1 chapter(s)
    Ch 131: server URL unavailable: Connection aborted
  Incomplete    : 1 chapter(s)
    Ch 145: 2 page(s) missing — folder kept

Checkpoint written: Hunter x Hunter/checkpoint.json
To retry:  python3 mangadex_bulk_download.py --resume "Hunter x Hunter/checkpoint.json"
```

---

## Supported languages

Pass either the code or the full name with `-l`:

| Code | Language |
|---|---|
| `en` | English (default) |
| `ja` | Japanese |
| `fr` | French |
| `de` | German |
| `es` | Spanish |
| `pt` | Portuguese |
| `it` | Italian |
| `ru` | Russian |
| `zh` | Chinese |
| `ko` | Korean |
