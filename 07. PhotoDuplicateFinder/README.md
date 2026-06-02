# Photo Duplicate Finder

Finds duplicate photos between your Google Drive and Google Photos library. Detects the same photo at different resolutions (e.g. a 2 MP compressed copy in Drive vs the 12 MP original in Photos), keeps the larger file, and lets you delete the smaller one from Google Drive after reviewing.

## How it works

1. **Metadata scan** — lists all photos from Google Drive (and optionally Google Photos) using rclone, with no downloads required
2. **Grouping** — matches photos by normalised filename (e.g. `IMG_2041.jpg` and `IMG_2041.HEIC` are the same group). Groups with files from both sources, or two copies of the same file within Drive, are flagged as duplicates
3. **Size ranking** — within each group, the largest file (by byte size) is marked **Keep**; smaller copies are candidates for deletion
4. **Visual verify** — click **Verify** on any group to download both files and run a perceptual hash (pHash) comparison side-by-side. Hamming distance ≤ 10 = confirmed duplicate
5. **Review & delete** — check the files you want to remove, confirm in the modal, and they are permanently deleted from Google Drive via `rclone deletefile`

> **Note:** Deletion only works for Google Drive files. Google Photos does not support deletion via its API.

## Prerequisites

### 1. rclone installed

```bash
brew install rclone
```

### 2. Google Drive remote named `gdrive`

```bash
rclone config
# n → new remote, name: gdrive, type: drive
# Complete OAuth in browser
```

### 3. Google Photos remote named `gphotos` (optional but recommended)

```bash
rclone config
# n → new remote, name: gphotos, type: Google Photos
# Leave client_id/secret blank, complete OAuth in browser
```

Verify: `rclone lsd gphotos:album`

> Google Photos listing can take several minutes for large libraries (the API paginates at 100 items).

## Install & run

```bash
cd "07. PhotoDuplicateFinder"
npm install
npm start
```

## Usage tips

- **Drive path**: leave blank to scan your entire Drive, or enter a subfolder like `Photos/Camera Roll` to limit the scope
- **Verify before deleting**: always click Verify on a group before checking it for deletion — filename matching alone can occasionally produce false positives
- **HEIC photos**: pHash comparison is not available for HEIC files (Apple format). Use the file size difference as your guide instead
- **After deletion**: deleted files go to Google Drive trash automatically (rclone deletefile moves to trash on Google Drive), so you can recover them within 30 days

## Settings

Settings are stored in `~/Library/Application Support/photo-duplicate-finder/config.json`.
