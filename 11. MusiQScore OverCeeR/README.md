# MusiQScore OverCeeR

Photograph a lead sheet (right-hand melody + chord symbols) with your phone, upload it to the web UI, and get back a compiled PDF and an editable LilyPond `.ly` file.

All processing happens on your home server (Mac Mini, Kubuntu). Clients — phone, MBP, anything with a browser — just upload photos and download results.

---

## How It Works

```
Phone/MBP  →  upload image via browser  →  FastAPI backend (Docker)
                                              ├─ Claude vision API  →  .ly file
                                              ├─ LilyPond  →  .pdf file
                                              └─ Google Drive API  →  your Drive folder
```

---

## Requirements

- **Server**: Docker + Docker Compose (Mac Mini / any Linux machine)
- **API key**: Anthropic API key (`ANTHROPIC_API_KEY`)
- **Google Drive** (optional): Google Cloud service account JSON

---

## Setup

### 1. Clone and enter the directory

```bash
git clone <repo>
cd "HandyToolsMac/11. MusiQScore OverCeeR"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in ANTHROPIC_API_KEY (and GOOGLE_DRIVE_FOLDER_ID if using Drive)
```

### 3. Google Drive setup (optional)

Skip this section if you don't need automatic Drive uploads.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a project
2. Enable the **Google Drive API**
3. Create a **Service Account** (IAM & Admin → Service Accounts)
4. Download the JSON key → save as `credentials.json` in this directory
5. In Google Drive, right-click your target folder → Share → paste the service account email (ends in `@...gserviceaccount.com`) → give Editor access
6. Copy the folder ID from the Drive URL (`/folders/<FOLDER_ID>`) into `.env`

### 4. Start the server

```bash
docker-compose up -d --build
```

The server starts on port `8000`. Check it:

```bash
docker-compose logs -f
```

---

## Usage

### Mobile or MBP — browser

1. Open `http://<server-ip>:8000` in your browser
2. Tap the upload zone and pick a photo (JPG, PNG, or HEIC)
3. Tap **Transcribe**
4. Download the `.ly` (editable source) and/or `.pdf` (compiled score)
5. If Drive is configured, links to the files on Google Drive also appear

To find your server IP on Kubuntu: `ip addr show | grep "inet "` or check your router.

### MBP — batch CLI (multiple photos at once)

```bash
pip install requests tqdm
python cli/client.py ~/Desktop/sheet_photos/ --server http://192.168.1.50:8000
```

Options:
```
python cli/client.py <photos_dir>
  --server  Backend URL (default: http://localhost:8000)
  -o        Local output directory (default: ./output)
  --delay   Seconds between uploads (default: 2.0)
```

---

## Output Files

| File | Description |
|------|-------------|
| `output/<name>.ly` | LilyPond source — open and edit in any text editor |
| `output/<name>.pdf` | Compiled score — ready to print |

To re-compile a `.ly` file after editing (requires LilyPond installed locally):

```bash
# macOS
brew install lilypond
lilypond output/page1.ly
```

---

## Editing the LilyPond Output

LilyPond files are plain text. Common edits:

```lilypond
\version "2.22.0"
\score {
  <<
    \new ChordNames {
      \chordmode {
        c1:maj7  f1:7  g1:m7  c1:7   % chord symbols above staff
      }
    }
    \new Staff {
      \clef treble \key c \major \time 4/4
      e4 g a b  c'2 b4 a  % notes
    }
  >>
  \layout { }
}
```

Chord syntax quick reference:

| Written | LilyPond |
|---------|----------|
| Cm7 | `c1:m7` |
| F/A | `f1/a` |
| Bb | `bes1` |
| Fmaj7 | `f1:maj7` |
| G7 | `g1:7` |
| Eb | `ees1` |
| Dm7b5 | `d1:m7.5-` |

---

## Troubleshooting

**"ANTHROPIC_API_KEY not configured"** — edit `.env` and restart: `docker-compose restart`

**PDF is null in response** — LilyPond compile failed. Download the `.ly` file to see what Claude generated; it may have a syntax error. Edit and recompile manually.

**HEIC photos not working** — Claude accepts HEIC directly. If you still get errors, convert to JPEG first (`sips -s format jpeg photo.heic --out photo.jpg` on macOS).

**Can't reach server from phone** — make sure both devices are on the same network. Use the server's local IP (e.g. `192.168.1.50`), not `localhost`.
