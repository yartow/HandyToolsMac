# MangaDex Bulk Downloader

Download manga chapters from [MangaDex](https://mangadex.org) as CBZ files, either by searching for a title or via a direct URL.

## Requirements

```bash
pip install requests tqdm
```

## Usage

```
python3 mangadex_bulk_download.py (-s TITLE | --url URL) [CHAPTERS] [-l LANG] [-u SITE]
```

### Arguments

| Argument | Description |
|---|---|
| `-s TITLE` | Search for a manga by title |
| `--url URL` | Use a direct MangaDex title URL |
| `CHAPTERS` | Chapter range to download (default: `all`) |
| `-l LANG` | Language code or name (default: `en`) |
| `-u SITE` | Site to search on (default: `mangadex.org`) |

### Chapter range formats

| Format | Downloads |
|---|---|
| `all` | Every available chapter |
| `5` | Chapter 5 only |
| `1-10` | Chapters 1 through 10 |
| `1,3,5-8` | Chapters 1, 3, and 5 through 8 |

## Examples

**Search and download all chapters:**
```bash
python3 mangadex_bulk_download.py -s "One Piece"
```

**Search and download a range:**
```bash
python3 mangadex_bulk_download.py -s "One Piece" 1-10
```

**Download a single chapter:**
```bash
python3 mangadex_bulk_download.py -s "Naruto" 5
```

**Download in a different language:**
```bash
python3 mangadex_bulk_download.py -s "One Piece" -l ja
python3 mangadex_bulk_download.py -s "One Piece" -l japanese
```

**Use a direct MangaDex URL:**
```bash
python3 mangadex_bulk_download.py --url https://mangadex.org/title/a96676be-9137-4fea-a2b4-33c9f5f9fa70
```

**Direct URL with chapter range:**
```bash
python3 mangadex_bulk_download.py --url https://mangadex.org/title/a96676be-9137-4fea-a2b4-33c9f5f9fa70 5-20
```

## Search results

When multiple results are found, you will be prompted to pick one:

```
Searching for "One Piece" on mangadex.org (language: en) ...

I've found these results:
1. One Piece
2. One Piece Party
3. One Piece: Wanted!

Which one do you mean? Type in the number:
```

Enter the number and press Enter. Type `0` to quit.

## Output

Chapters are saved as `.cbz` files (comic archives readable by most comic readers) in a folder named `MangaDex_<id>` in your current working directory:

```
MangaDex_a9667be/
├── Chapter 0001.cbz
├── Chapter 0002.cbz
└── Chapter 0003 - Romance Dawn.cbz
```

## Supported languages

Pass either the code or the full name with `-l`:

| Code | Language |
|---|---|
| `en` | English |
| `ja` | Japanese |
| `fr` | French |
| `de` | German |
| `es` | Spanish |
| `pt` | Portuguese |
| `it` | Italian |
| `ru` | Russian |
| `zh` | Chinese |
| `ko` | Korean |
