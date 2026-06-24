# MusiQScore OverCeeR — Developer Notes

Photographs of lead sheets (right-hand piano melody + chord symbols above the staff)
are transcribed to LilyPond source files (`.ly`) and compiled to PDF via LilyPond.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn (Python 3.12) |
| AI transcription | Anthropic Python SDK — `claude-sonnet-4-6` vision |
| Music compilation | LilyPond (installed in Docker image via apt) |
| Cloud storage | Google Drive API v3 (service account, `google-api-python-client`) |
| Containerisation | Docker + Docker Compose |
| Web UI | Vanilla HTML/CSS/JS (no framework) |
| Batch CLI client | Python + requests + tqdm |

## Infrastructure

- **Home server**: Mac Mini i5 (2010), running Kubuntu (Linux). Runs the Docker backend always-on.
- **Clients**: Any device with a browser — mobile phones, MacBook Pro (MBP). No software installation required on clients.
- **Why server-side only**: LilyPond is not available on mobile clients. All transcription and PDF compilation run in the Docker container on the Mac Mini.

## Multi-Platform Access

| Platform | How to use |
|----------|-----------|
| Mobile (iOS/Android) | Open `http://<mac-mini-ip>:8000` in browser → upload photo → download result |
| MBP (single photo) | Same browser URL |
| MBP (bulk/batch) | `python cli/client.py <photos_dir> --server http://<ip>:8000` |

## Key Files

```
├── backend/app.py          FastAPI server — endpoints: /, /transcribe, /files/{name}
├── backend/transcribe.py   Claude vision API call + LilyPond compile
├── backend/gdrive.py       Google Drive upload helper (service account)
├── backend/static/index.html  Web UI
├── cli/client.py           Batch CLI for MBP
├── docker-compose.yml
└── .env.example            Copy to .env; fill ANTHROPIC_API_KEY + GOOGLE_DRIVE_FOLDER_ID
```

## Secrets (never commit)

- `.env` — API keys and Drive folder ID
- `credentials.json` — Google service account JSON (place in this directory)

Both are listed in `.gitignore`.
