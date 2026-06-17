#!/usr/bin/env python3

"""
MusiQScore OverCeeR — FastAPI backend.
Accepts image uploads, transcribes via Claude vision, compiles to PDF via LilyPond,
and optionally uploads results to Google Drive.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

import anthropic
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import gdrive
import transcribe as tr

# --------------------- CONFIG ---------------------

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/output"))
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "/app/credentials.json")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # 10 MB hard limit

# --------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_api_key = os.getenv("ANTHROPIC_API_KEY", "")
if not _api_key:
    print("WARNING: ANTHROPIC_API_KEY is not set — /transcribe will return 503")

_lilypond_available = shutil.which("lilypond") is not None
if not _lilypond_available:
    print("WARNING: lilypond not found in PATH — PDF generation disabled")

_drive_enabled = bool(
    GOOGLE_DRIVE_FOLDER_ID
    and Path(GOOGLE_CREDENTIALS_JSON).exists()
)

app = FastAPI(title="MusiQScore OverCeeR")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path("static") / "index.html").read_text()


@app.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    series_name: str = Form(""),
):
    if not _api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY not configured on server")

    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // (1024*1024)} MB)")

    # Save upload to temp file so transcribe.py can read it by path
    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    stem = Path(file.filename or "page").stem
    unique_stem = f"{stem}_{uuid.uuid4().hex[:6]}"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = Path(tmp.name)

    try:
        client = anthropic.Anthropic(api_key=_api_key)

        try:
            ly_code, warning = tr.transcribe_image(
                client, tmp_path, page_num=1, series_name=series_name.strip()
            )
        except anthropic.AuthenticationError:
            raise HTTPException(401, "Invalid Anthropic API key")
        except anthropic.RateLimitError:
            raise HTTPException(429, "Anthropic rate limit reached — try again later")
        except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
            raise HTTPException(502, f"Anthropic API error: {e}")

        # Write .ly file
        ly_path = OUTPUT_DIR / f"{unique_stem}.ly"
        ly_path.write_text(ly_code, encoding="utf-8")

        # Compile to PDF
        pdf_path: Path | None = None
        if _lilypond_available:
            pdf_path = tr.compile_to_pdf(ly_path, OUTPUT_DIR)

        # Upload to Google Drive
        gdrive_ly = ""
        gdrive_pdf = ""
        if _drive_enabled:
            gdrive_ly = gdrive.upload_file(ly_path, GOOGLE_DRIVE_FOLDER_ID, GOOGLE_CREDENTIALS_JSON)
            if pdf_path:
                gdrive_pdf = gdrive.upload_file(pdf_path, GOOGLE_DRIVE_FOLDER_ID, GOOGLE_CREDENTIALS_JSON)

        return {
            "stem": unique_stem,
            "ly_url": f"/files/{ly_path.name}",
            "pdf_url": f"/files/{pdf_path.name}" if pdf_path else None,
            "gdrive_ly": gdrive_ly,
            "gdrive_pdf": gdrive_pdf,
            "warning": warning,
        }
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/files/{filename}")
async def download_file(filename: str):
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    media_type = "application/pdf" if filename.endswith(".pdf") else "text/plain"
    return FileResponse(path, media_type=media_type, filename=filename)
