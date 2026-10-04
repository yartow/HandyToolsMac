#!/usr/bin/env python3
"""Flag scanned comic book pages in a photo library via CLIP zero-shot classification.

Detection only — never deletes or moves anything. Writes a CSV of every image
with its predicted label and confidence so results can be reviewed before any
deletion decision is made.
"""
import csv
import sys
from pathlib import Path

import open_clip
import torch
from PIL import Image

# ----- CONFIG -----
LIBRARY_DIR = Path("/Users/andrewyong/Pictures/GooglePhotos/library")
OUTPUT_CSV = Path(__file__).parent / "comic_page_candidates.csv"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
MODEL_NAME = "ViT-B-32"
PRETRAINED = "laion2b_s34b_b79k"
LABELS = [
    "a scanned comic book page with illustrated panels, cartoon drawings, and speech bubbles",
    "a real photograph of people, places, or objects",
    "a screenshot of a phone or computer screen",
    "a scanned document or receipt with printed text",
]
COMIC_LABEL_INDEX = 0
COMIC_THRESHOLD = 0.999  # calibrated against a 500-file random sample: genuine
# comic pages scored >=0.999999, the closest false positives (photographed
# book covers/worksheets/cards) topped out at 0.998.
# ---------


def load_model():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    tokenizer = open_clip.get_tokenizer(MODEL_NAME)
    model = model.to(device).eval()
    text_features = model.encode_text(tokenizer(LABELS).to(device))
    text_features /= text_features.norm(dim=-1, keepdim=True)
    return model, preprocess, text_features, device


def classify(path: Path, model, preprocess, text_features, device) -> tuple[str, float]:
    image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0).to(device)
    with torch.no_grad():
        image_features = model.encode_image(image)
        image_features /= image_features.norm(dim=-1, keepdim=True)
        probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)[0]
    best_idx = probs.argmax().item()
    return LABELS[best_idx], probs[best_idx].item(), probs[COMIC_LABEL_INDEX].item()


def iter_candidate_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]


def main() -> None:
    explicit_files: list[Path] = []
    limit = None
    output_csv = OUTPUT_CSV
    if len(sys.argv) > 1 and sys.argv[1] == "--file-list":
        with open(sys.argv[2]) as f:
            explicit_files = [Path(line.strip()) for line in f if line.strip()]
        if len(sys.argv) > 3 and sys.argv[3] == "--out":
            output_csv = Path(sys.argv[4])
    elif len(sys.argv) > 1 and sys.argv[1].isdigit():
        limit = int(sys.argv[1])
    else:
        explicit_files = [Path(a) for a in sys.argv[1:] if Path(a).is_file()]

    print("Loading CLIP model...")
    model, preprocess, text_features, device = load_model()
    print(f"Using device: {device}")

    files = explicit_files if explicit_files else iter_candidate_files(LIBRARY_DIR)
    if limit and not explicit_files:
        files = files[:limit]
    print(f"Classifying {len(files)} file(s)...")

    from tqdm import tqdm

    rows = []
    for path in tqdm(files, unit=" files"):
        try:
            label, confidence, comic_prob = classify(path, model, preprocess, text_features, device)
        except Exception as e:
            print(f"Skipped (unreadable): {path} ({e})")
            continue
        flagged = comic_prob >= COMIC_THRESHOLD
        rows.append({"path": str(path), "predicted_label": label, "confidence": f"{confidence:.6f}", "comic_prob": f"{comic_prob:.6f}", "flagged": flagged})

    rows.sort(key=lambda r: float(r["comic_prob"]), reverse=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "predicted_label", "confidence", "comic_prob", "flagged"])
        writer.writeheader()
        writer.writerows(rows)

    flagged_count = sum(1 for r in rows if r["flagged"])
    print(f"\n{flagged_count} of {len(rows)} flagged as comic pages (comic_prob >= {COMIC_THRESHOLD}).")
    print(f"Full results: {output_csv}")


if __name__ == "__main__":
    main()
