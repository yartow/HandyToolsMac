# Evernote to UpNote Migration Automation

Cuts out the babysitting in the Evernote → UpNote migration: bulk-exports every
notebook in one go, checks whether a given `.enex` file has already been imported
into UpNote, and (optionally) queues up multiple files for automatic import.

If you just want to run this without reading all the technical details below, see
**[GETTING_STARTED.md](GETTING_STARTED.md)**.

## The pipeline

```
Evernote  --[run_evernote_export.sh]-->  enex-in/  --[13. OCR tool]-->  enex-out/
                                                                           |
                                                          dedup_checker.py checks each file
                                                                           |
                                                    upnote_import_automation.py imports the new ones
                                                                           v
                                                                        UpNote
```

The OCR/searchability step is the separate `13. Add OCR to PDF within Enex` tool
(unchanged) — this folder only covers getting files into and out of that step faster.

## Files

- **`enex_utils.py`** — shared helper, parses an `.enex` file and yields each
  note's title/created/updated timestamp (converted to epoch-ms to match UpNote's
  database format). Streams the file rather than loading it fully into memory,
  since `.enex` files can have large inline base64 PDF attachments.

- **`dedup_checker.py`** — tells you whether a given `.enex` file's notes already
  exist in UpNote.
  ```
  python3 dedup_checker.py path/to/file-or-folder.enex [--verbose]
  ```
  Copies UpNote's local database to a temp location first — **it never opens or
  modifies the live database file.** Reports, per file, what fraction of its note
  titles already exist in UpNote (the primary signal) and, among those, what
  fraction also agree on created-date (a secondary, confirming signal — see the
  open question about this in `CLAUDE.md`).

- **`upnote_import_automation.py`** — queues `.enex` files for import into UpNote,
  one after another, waiting for each to actually finish (rather than you watching
  for it) before starting the next. Skips files `dedup_checker`'s logic considers
  already imported.
  ```
  python3 upnote_import_automation.py path/to/enex-out/ [--force]
  ```
  Only ever drives UpNote's own built-in "File > Import Notes > Evernote" feature
  via the same clicks you'd make yourself — **no direct database writes.**
  **Run this on one low-stakes file first, watching the screen**, before trusting
  it with a large batch — see `CLAUDE.md` for why.

- **`run_evernote_export.sh`** — wraps the [`evernote-backup`](https://github.com/vzhd1701/evernote-backup)
  Docker image's `sync`/`export` steps with an automatic retry loop for Evernote's
  API rate limit, so a large account's export doesn't require you to notice a stall
  and manually rerun it.
  ```
  ./run_evernote_export.sh [data-dir] [export-dir]
  ```
  Requires `evernote-backup init-db` to have been run once already (one-time,
  interactive Evernote login) — see GETTING_STARTED.md.

## Safety boundaries

- Duplicate detection and import-completion detection **only ever read a copied
  snapshot** of UpNote's `upnote.sqlite3` — never the live file. Zero risk to your
  existing notes from either of those.
- Import automation only ever triggers UpNote's own supported Import feature via
  UI actions (clicks/keystrokes) — it does not write to the database directly and
  does not reimplement Evernote-import logic itself.
- Export uses `evernote-backup`'s legitimate OAuth login against your own Evernote
  account — not scraping, not a shared/misused credential.

## Known limitations / things to verify yourself

- The exact button names `upnote_import_automation.py` looks for ("Select .enex
  files", "Import Notes") come from UpNote's own help documentation, not a full
  live-click-through test — see `CLAUDE.md` for exactly what was and wasn't
  confirmed. Do a supervised first run.
- Whether UpNote preserves a note's original Evernote `created`/`updated` timestamp
  on import is currently an open question (see `CLAUDE.md`). `dedup_checker.py`'s
  primary signal (title match) works either way; the timestamp-agreement number is
  just a bonus confirming signal for now.
- `run_evernote_export.sh`'s rate-limit retry logic matches on the text "rate limit"
  in `evernote-backup`'s output; if a future version of that tool changes its
  wording, the retry loop won't trigger and you'll see a normal failure instead.
