# enex-pdf-textify

Makes PDFs inside your Evernote `.enex` export files searchable once you import them
into UpNote — including scanned/image-only PDFs, via automatic OCR.

## Why this exists

UpNote's search only looks at a note's **title and typed content** — it does not read
the text hidden inside attached PDF files. So a PDF sitting in a note as an attachment
is invisible to search, no matter how many times you search for a phrase you know is
in there.

This tool fixes that *before* you import: it opens each `.enex` file, finds every PDF
attached to every note, extracts its text, and appends that text as a plain,
clearly-labeled section at the bottom of the note itself. The original PDF attachment
is left completely untouched (still viewable inline in UpNote) — you just also get a
searchable text copy sitting next to it in the note body.

**Digital PDFs** (real text layer) are handled directly with Apache PDFBox.
**Scanned/image-only PDFs** are handled automatically: the tool detects when a PDF has
no usable text layer and runs it through [OCRmyPDF](https://github.com/ocrmypdf/ocrmypdf)
(Tesseract OCR under the hood) before extracting text again. This happens transparently —
no flag needed — but it's much slower than direct extraction, so expect a large export
full of scans to take a while (see "Long-running batch jobs" below). Language packs
installed: English and Dutch (`eng+nld`); see "Setup — option B: Docker" to add more.

## Setup — option A: plain Java + Maven

1. Install a JDK (17+) and Maven if you don't have them already.
2. From this folder, build the runnable jar:

   ```bash
   mvn package
   ```

   This downloads Apache PDFBox and produces `target/enex-pdf-textify-1.0.jar`.

**Note:** this route gives you direct PDF text extraction only. The OCR fallback shells
out to the `ocrmypdf` CLI, which isn't installed by this route — install it yourself
(e.g. `brew install ocrmypdf` on macOS, or your Linux distro's package) if you want OCR
without Docker. Scanned PDFs will just print a `[WARN] ... no text could be extracted`
and be skipped if `ocrmypdf` isn't on your `PATH`.

## Setup — option B: Docker (recommended)

No local Java/Maven/Tesseract needed — the image bundles the JRE, PDFBox, `ocrmypdf`,
Tesseract, and the `eng` + `nld` language packs. Runtime base image is
`debian:bookworm-slim`, not Alpine — Alpine/musl makes OCRmyPDF's Python and native
dependency chain (Tesseract, Ghostscript, qpdf) much more fragile to install, so this
image trades a bit of size for reliability.

1. Build the image (from this folder):
   ```bash
   docker build -t enex-pdf-textify .
   ```

2. Put the `.enex` file(s) you want to process in a local folder, e.g. `./enex-in`,
   and create an empty `./enex-out` folder for the results.

3. Run it, mounting those folders into the container's expected `/data/in` and `/data/out`:
   ```bash
   docker run --rm -v "$(pwd)/enex-in:/data/in" -v "$(pwd)/enex-out:/data/out" enex-pdf-textify
   ```
   (On Windows PowerShell, replace `$(pwd)` with `${PWD}`.)

   This always runs in folder mode (every `*.enex` in `enex-in` gets processed into
   `enex-out`). If you want to point at different paths, override the default args:
   ```bash
   docker run --rm -v "$(pwd):/data" enex-pdf-textify /data/notebook.enex /data/notebook-textified.enex
   ```

   To add more OCR languages, edit the `tesseract-ocr-*` packages and the
   `--language eng+nld` argument in `OcrMyPdfRunner.java`, then rebuild the image.

## Usage (Java/Maven route)

**Single file:**
```bash
java -jar target/enex-pdf-textify-1.0.jar path/to/notebook.enex path/to/notebook-textified.enex
```

**Whole folder of exported notebooks at once** (recommended, since you export each
Evernote notebook as its own `.enex` file):
```bash
java -jar target/enex-pdf-textify-1.0.jar path/to/enex-folder path/to/output-folder
```
Every `*.enex` file in the input folder gets processed and written to the output
folder under the same filename.

Then import the files in the *output* folder into UpNote as you normally would
(File > Import Notes > Evernote, select all the processed files, enable "Use file
name as notebook").

## Long-running batch jobs

OCR over a large personal Evernote export can realistically take hours to days,
depending on how many scanned PDFs you have. The tool is built for that:

- **Resumable:** before processing each `.enex` file, it checks whether the output
  file already exists and is newer than the input. If so, it prints `[SKIP]` and
  moves on — so killing and restarting the job (or a container restart) doesn't
  reprocess everything from scratch.
- **Progress output:** each PDF that needs OCR prints when it starts and how long it
  took; each file prints a one-line summary (`X notes, Y PDFs, Z used OCR, W still blank`)
  when done.
- For a run you expect to take a long time, launch it detached so it survives a closed
  terminal, e.g.:
  ```bash
  nohup docker run --rm -v "$(pwd)/enex-in:/data/in" -v "$(pwd)/enex-out:/data/out" enex-pdf-textify > progress.log 2>&1 &
  ```
  or run it inside `tmux`/`screen`. Check on it later with `tail -f progress.log`.

## Running on a home server

Since this can take a while, you may want to run it on a machine that's always on
(e.g. a Mac Mini running Linux) instead of your laptop. Because Docker images are
tied to a CPU architecture, the reliable way to do this is:

1. Copy or `git clone` this whole project folder onto the server.
2. Run `docker build` and `docker run` **on the server itself**.

Don't build the image on your Mac laptop and try to move the built image over —
if the server's CPU architecture differs from your laptop's (e.g. Apple Silicon vs.
Intel, or vice versa), the image won't run there. Building from source directly on
the target machine sidesteps that entirely.

## What it does to a note, concretely

If a note has a PDF called `contract.pdf` attached, after processing the note body
will end up with an extra section at the bottom like:

```text
--- Extracted text from: contract.pdf ---
[... full text of the PDF, line by line ...]
```

That text is now ordinary note content, so UpNote's normal search will match it.

## Alternatives considered

Before building this, two API-based alternatives were checked:

- **Evernote API**: Evernote's own developer docs state that developer tokens are
  "currently unavailable except for proven necessity" — in practice this API isn't
  obtainable for a personal/hobby project. Scripting directly against Evernote to pull
  notes isn't a realistic option; exporting `.enex` files through the regular Evernote
  client remains the way in.
- **UpNote API**: UpNote has no import/automation API. The only bulk-import path is the
  GUI's manual multi-file `.enex` picker (Settings > Import from Evernote), which has
  real limits worth knowing before a huge batch import: no file over 20MB, no note over
  300,000 characters, and once your account is near ~20,000 notes or 10GB of attachments,
  imports are capped at 50 notes at a time.

Given both of those are closed off, pre-processing your exported `.enex` files locally
with this tool — then importing the results through UpNote's GUI — is the best available
option, not just the simplest one.

## Before running on everything

Try it on one or two `.enex` files first, import those into a scratch notebook in
UpNote, and confirm:
- The notes look right (original content + PDF attachment + new text section).
- Search actually finds phrases from inside the PDFs, including ones you know were
  scanned rather than digital.

Once you're happy with the result, run it across all your exported notebooks.
