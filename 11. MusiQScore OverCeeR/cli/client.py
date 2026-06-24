#!/usr/bin/env python3

"""
MusiQScore OverCeeR — batch CLI client for MBP.
Sends a folder of music sheet photos to the backend server and saves .ly + .pdf locally.
"""

import argparse
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

# --------------------- CONFIG ---------------------

DEFAULT_SERVER = "http://localhost:8000"
DEFAULT_DELAY = 2.0   # seconds between uploads (be kind to the server)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".webp"}

# --------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MusiQScore OverCeeR — batch image → LilyPond/PDF via backend"
    )
    p.add_argument("photos_dir", help="Directory containing music sheet photos")
    p.add_argument("--server", default=DEFAULT_SERVER, help=f"Backend URL (default: {DEFAULT_SERVER})")
    p.add_argument("-o", "--output", default="./output", help="Directory to save downloaded files")
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Seconds between uploads")
    p.add_argument("--series", default="", help="Series name prefix (e.g. OTH)")
    return p.parse_args()


def find_images(directory: Path) -> list[Path]:
    images = sorted(
        (p for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.name.lower()
    )
    return images


def upload_image(server: str, image_path: Path, series_name: str = "") -> dict:
    url = f"{server.rstrip('/')}/transcribe"
    with image_path.open("rb") as fh:
        resp = requests.post(
            url,
            files={"file": (image_path.name, fh)},
            data={"series_name": series_name},
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def download_file(server: str, url_path: str, output_dir: Path) -> Path | None:
    if not url_path:
        return None
    url = f"{server.rstrip('/')}{url_path}"
    filename = url_path.split("/")[-1]
    dest = output_dir / filename
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def main():
    args = parse_args()
    photos_dir = Path(args.photos_dir).expanduser()
    output_dir = Path(args.output).expanduser()
    server = args.server

    if not photos_dir.is_dir():
        print(f"Error: {photos_dir} is not a directory")
        sys.exit(1)

    images = find_images(photos_dir)
    if not images:
        print(f"No images found in {photos_dir}")
        sys.exit(0)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"MusiQScore OverCeeR — Batch Client")
    print(f"Server: {server}")
    if args.series:
        print(f"Series: {args.series}")
    print(f"Found {len(images)} image(s) in {photos_dir}")
    print()

    succeeded = 0
    failed = 0

    for i, img in enumerate(tqdm(images, desc="Processing", unit="image"), 1):
        tqdm.write(f"[{i}/{len(images)}] {img.name} → uploading...")

        try:
            data = upload_image(server, img, series_name=args.series)
        except requests.exceptions.ConnectionError:
            tqdm.write(f"      FAILED: cannot reach {server}")
            failed += 1
            continue
        except requests.exceptions.HTTPError as e:
            tqdm.write(f"      FAILED: {e}")
            failed += 1
            continue
        except Exception as e:
            tqdm.write(f"      FAILED: {e}")
            failed += 1
            continue

        ly_path = download_file(server, data.get("ly_url"), output_dir)
        pdf_path = download_file(server, data.get("pdf_url"), output_dir)

        if ly_path:
            tqdm.write(f"      Saved: {ly_path}")
        if pdf_path:
            tqdm.write(f"      Saved: {pdf_path}")
        if data.get("gdrive_ly"):
            tqdm.write(f"      Drive (.ly):  {data['gdrive_ly']}")
        if data.get("gdrive_pdf"):
            tqdm.write(f"      Drive (PDF):  {data['gdrive_pdf']}")
        if data.get("warning"):
            tqdm.write(f"      Warning: {data['warning']}")

        succeeded += 1

        if i < len(images):
            time.sleep(args.delay)

    print()
    print(f"Done: {succeeded} page(s) processed, {failed} failed")
    if output_dir.exists():
        print(f"Files saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
