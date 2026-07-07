# Getting started (step by step, no assumptions)

This walks through the whole pipeline: Evernote → export → OCR (make PDFs
searchable) → check for duplicates → import into UpNote. Every command below is
meant to be copy-pasted exactly as written, one at a time.

**What you need first**: [Docker Desktop](https://www.docker.com/products/docker-desktop/)
installed and running (you'll see a little whale icon in your menu bar once it's
open), and Terminal (search for "Terminal" in Spotlight — the magnifying glass in
the top-right of your screen, or press Cmd+Space).

## Step 0: Open Terminal and go to this folder

1. Open Terminal.
2. Copy-paste this exact line and press Return (this jumps Terminal into this
   project's folder — adjust if you moved it):
   ```
   cd "$HOME/Documents/GitHub/HandyToolsMac/14. Evernote to UpNote Migration Automation"
   ```
   You'll know it worked if your Terminal prompt now shows that folder name.

## Step 1: One-time Evernote login

You only ever do this once (or again later if it expires).

1. Copy-paste and run:
   ```
   docker run --rm -it -v "$(pwd)/evernote-backup-data":/tmp -p 10500:10500 vzhd1701/evernote-backup:latest init-db
   ```
2. Terminal will print a web address. **Copy that address and open it in your
   browser.** Log into Evernote there like normal (including your 2FA code if you
   use one).
3. Once you see a success message in the browser, go back to Terminal — it should
   finish on its own and drop you back to the prompt.

If this ever stops working (login expired), just run the same command again.

## Step 2: Export everything from Evernote

1. Copy-paste and run:
   ```
   ./run_evernote_export.sh
   ```
2. This can take a **long time** the first time (potentially hours for a big
   account) — that's normal, and you can leave it running and walk away. It
   prints progress as it goes.
3. If you see a message about "rate limit hit", **that's expected, not an
   error** — Evernote is temporarily saying "slow down." The script waits and
   retries automatically. You don't need to do anything.
4. When it's done, you'll see `.enex` files (one per notebook) inside a new
   `enex-in` folder next to this README.

## Step 3: Make PDFs inside those files searchable (OCR)

This step uses the separate tool in the `13. Add OCR to PDF within Enex` folder.

1. Go to that folder:
   ```
   cd "../13. Add OCR to PDF within Enex"
   ```
2. Build it once (only needed the first time, or after an update):
   ```
   docker build -t enex-pdf-textify .
   ```
3. Run it against the files you just exported:
   ```
   docker run --rm -v "$(pwd)/../14. Evernote to UpNote Migration Automation/enex-in:/data/in" -v "$(pwd)/../14. Evernote to UpNote Migration Automation/enex-out:/data/out" enex-pdf-textify
   ```
4. When it's done, go back to this folder:
   ```
   cd "../14. Evernote to UpNote Migration Automation"
   ```
   You'll now have an `enex-out` folder with the final, ready-to-import files.

## Step 4: Check what's already been imported

Before importing, see what's new vs. what you've likely already done before:

```
python3 dedup_checker.py enex-out --verbose
```

You'll get one line per file, like:

```
Groceries.enex: 0/12 (0%) notes already appear in UpNote by title -- looks new
Taxes 2024.enex: 45/45 (100%) notes already appear in UpNote by title, 45/45 also match created-date -- looks already imported
```

This tells you, per notebook, whether it's safe to skip.

## Step 5: Import into UpNote

**Important — the first time, watch the screen while this runs**, since the exact
clicking hasn't been fully tested against your real UpNote yet (see `CLAUDE.md`
for why). If a step doesn't work, it'll print an error naming exactly what it
couldn't find/click, and stop rather than doing something wrong.

1. Make sure UpNote is open (just launch it normally first).
2. Run:
   ```
   python3 upnote_import_automation.py enex-out
   ```
3. It will skip any file it thinks is already imported, and for the rest: open
   UpNote's import dialog, pick the file, click Import, then **wait** (checking
   in the background, not by watching a progress bar) until the import has
   actually finished before moving to the next file. You can walk away once
   you've confirmed the first file worked correctly.

If you ever want to force-import a file even though it looks already imported:
```
python3 upnote_import_automation.py path/to/file.enex --force
```

## If something looks stuck or wrong

- **"osascript is not allowed assistive access"** — go to  System Settings >
  Privacy & Security > Accessibility, and turn on access for Terminal (or
  whichever app you're running these commands from). This is a one-time
  permission macOS requires for any tool that clicks/types on your behalf.
- **UpNote shows no window / seems unresponsive** — this is harmless; your notes
  are safe (they live in a database file, not in the app's open windows). Just
  quit UpNote (Cmd+Q, or Activity Monitor > Force Quit if Cmd+Q doesn't respond)
  and reopen it normally.
- **The import automation prints an error about a button it couldn't find** —
  UpNote's dialog may look slightly different than expected. Do that one file's
  import by hand instead (File > Import Notes > Evernote, as normal), and
  mention the exact error message so the script's button names can be corrected.
