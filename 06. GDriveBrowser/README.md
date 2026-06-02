# GDrive Browser

A WinDirStat-style folder size browser for Google Drive, built with Electron and powered by rclone.

## What it does

- Lists files and folders inside any Google Drive path, sorted by size (largest first)
- Shows a proportional size bar next to each item for quick visual comparison
- Double-click any folder to drill in; click the breadcrumb or press Backspace to go back up
- Fetches directory sizes in the background (up to 3 at a time) and updates the view as they arrive
- Caches results per path so navigating back is instant

## Prerequisites

### 1. Install rclone

```bash
brew install rclone
```

Or see https://rclone.org/install/ for other methods.

### 2. Configure a Google Drive remote named `gdrive`

```bash
rclone config
```

Follow the interactive prompts:
- Choose `n` (new remote)
- Name it exactly **`gdrive`**
- Choose `drive` as the storage type
- Complete the OAuth flow in your browser

Verify it works:
```bash
rclone lsd gdrive:
```

## Install & run

```bash
cd "06. GDriveBrowser"
npm install
npm start
```

## Settings

Click the **⚙** icon in the top-right to change:
- **rclone remote name** — defaults to `gdrive`; change if your remote has a different name
- **Start path** — leave blank to start at the root of the remote; enter a subfolder path (e.g. `Documents/Work`) to open there on launch

Settings are stored in `~/Library/Application Support/gdrive-browser/config.json`.

## Keyboard shortcuts

| Key       | Action          |
|-----------|-----------------|
| Backspace | Go up one level |
| Escape    | Close settings  |

## Notes

- Folder sizes are fetched with `rclone size`, which must traverse all files recursively — large directories can take a while. The app shows a pulsing `…` while calculating.
- Image URLs and folder sizes are cached in memory for the session; quitting and restarting clears the cache.
- The app expects rclone in one of: `PATH`, `/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin`.
