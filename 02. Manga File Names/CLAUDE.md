# 02. Manga File Names — Developer Notes

Two standalone download scripts for manga sites. Each saves chapters as CBZ files.

---

## Scripts

### `mangafreak_download.py`

Downloads from MangaFreak. Accepts two URL forms:

| URL form | Example |
|---|---|
| Series page | `https://ww2.mangafreak.me/Manga/Mf_Ghost` |
| Chapter page | `https://ww2.mangafreak.me/Read1_Mf_Ghost_7` |

The series page form is preferred — it fetches the full chapter list upfront so the script always knows the exact chapter count. Chapter URLs with `--chapters all` also fetch the chapter list first (no more "stop at 404" iteration).

**Key functions:**
- `classify_url()` — detects URL type and extracts origin/name/chapter
- `_discover_slug()` — scans series page links to find the `Read1_` slug
- `fetch_chapter_list()` — three-strategy fallback for finding all chapters
- `download_chapter()` — fetches one chapter and packages it as a CBZ

**Output:** `Read1_<SeriesName>/Chapter_NNNN.cbz` in the current directory.

### `mangadex_bulk_download.py`

Downloads from MangaDex via the public API. Accepts title search, manga ID, or direct URL. Supports checkpoint/resume for failed downloads.

**Output:** `<MangaTitle>/Chapter NNNN - Title.cbz` in the current directory.

---

## Shared conventions

- CBZ files are ZIP archives of page images sorted by filename.
- Already-downloaded CBZ files are skipped on re-run.
- `--delay` controls politeness sleep between chapter requests (default 1s).
- `--debug` dumps all `<img>` tags on the first page — use this when `No images found` appears.

---

## Dependencies

```bash
pip install requests beautifulsoup4 tqdm
```

(`tqdm` not required by `mangadex_bulk_download.py`.)
