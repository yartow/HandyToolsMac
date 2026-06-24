"""
Sheet Music Preprocessing Tuner
================================
Interactive tool to find the best preprocessing parameters
for your sheet music photos before sending to Claude.

Requirements:
    pip install opencv-python numpy

Usage:
    python sheet_music_tuner.py path/to/your/photo.jpg

Controls:
    - Use the sliders in the "Controls" window to tune parameters
    - The "Preview" window updates in real time
    - Press 's' to save current settings to 'tuner_settings.txt'
    - Press 'e' to export the preprocessed image as 'output_preview.png'
    - Press 'q' to quit
"""

import cv2
import numpy as np
import sys
import json
from pathlib import Path


# ---------------------------------------------------------------------------
# Load image
# ---------------------------------------------------------------------------
def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        print(f"ERROR: Could not load image at '{path}'")
        sys.exit(1)
    # Downscale for display if very large, keep original for export
    return img


def resize_for_display(img: np.ndarray, max_height: int = 900) -> np.ndarray:
    h, w = img.shape[:2]
    if h > max_height:
        scale = max_height / h
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    return img


# ---------------------------------------------------------------------------
# Core preprocessing pipeline
# ---------------------------------------------------------------------------
def preprocess(img_bgr: np.ndarray, params: dict) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1. Bleed-through suppression via background estimation
    #    Large Gaussian blur estimates the background; dividing removes it.
    blur_size = params["bleed_blur"] * 2 + 1          # must be odd
    background = cv2.GaussianBlur(gray, (blur_size, blur_size), 0)
    # Normalize: divide gray by background, scale to 0-255
    bleed_strength = params["bleed_strength"] / 100.0
    if bleed_strength > 0:
        norm = cv2.divide(gray, background, scale=255)
        gray = cv2.addWeighted(gray, 1 - bleed_strength, norm, bleed_strength, 0)

    # 2. Deskew (simple horizontal skew correction via Hough lines)
    if params["deskew"]:
        gray = deskew(gray)

    # 3. Sharpening
    sharp_strength = params["sharp_strength"] / 10.0
    if sharp_strength > 0:
        blurred = cv2.GaussianBlur(gray, (0, 0), 3)
        gray = cv2.addWeighted(gray, 1 + sharp_strength, blurred, -sharp_strength, 0)

    # 4. Adaptive threshold (binarization)
    block = params["thresh_block"] * 2 + 3            # min 3, must be odd
    C     = params["thresh_c"]
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block, C
    )

    # 5. Optional: morphological cleanup to close broken beams
    if params["morph_close"] > 0:
        k = params["morph_close"]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))  # horizontal
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    return binary


def deskew(gray: np.ndarray) -> np.ndarray:
    """Detect dominant angle from Hough lines and rotate to correct skew."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
    if lines is None:
        return gray
    angles = []
    for rho, theta in lines[:, 0]:
        angle = (theta - np.pi / 2) * 180 / np.pi
        if abs(angle) < 10:                           # ignore steep lines
            angles.append(angle)
    if not angles:
        return gray
    median_angle = float(np.median(angles))
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


# ---------------------------------------------------------------------------
# Trackbar helpers
# ---------------------------------------------------------------------------
WINDOW_CTRL    = "Controls  (s=save  e=export  q=quit)"
WINDOW_PREVIEW = "Preview"

# Each entry: (label, min, max, default)
TRACKBAR_DEFS = [
    ("bleed_blur",     1,  50, 21),   # background blur radius (x2+1 = kernel)
    ("bleed_strength", 0, 100, 60),   # 0=off, 100=full bleed removal
    ("sharp_strength", 0,  50, 15),   # sharpening (divided by 10 internally)
    ("thresh_block",   1,  50, 10),   # adaptive threshold block (x2+3)
    ("thresh_c",       0,  30, 10),   # adaptive threshold constant C
    ("morph_close",    0,  10,  0),   # horizontal beam closing (px width)
    ("deskew",         0,   1,  1),   # 0=off, 1=on
]


def create_controls():
    # Create a small black canvas to host the trackbars
    canvas = np.zeros((50, 700), dtype=np.uint8)
    cv2.namedWindow(WINDOW_CTRL, cv2.WINDOW_NORMAL)
    cv2.imshow(WINDOW_CTRL, canvas)
    for name, lo, hi, default in TRACKBAR_DEFS:
        cv2.createTrackbar(name, WINDOW_CTRL, default, hi, lambda x: None)
        cv2.setTrackbarMin(name, WINDOW_CTRL, lo)


def read_params() -> dict:
    return {name: cv2.getTrackbarPos(name, WINDOW_CTRL)
            for name, *_ in TRACKBAR_DEFS}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Usage: python sheet_music_tuner.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    img_orig   = load_image(image_path)
    img_disp   = resize_for_display(img_orig)   # display-size original
    scale      = img_disp.shape[0] / img_orig.shape[0]

    print(f"Loaded: {image_path}  ({img_orig.shape[1]}x{img_orig.shape[0]})")
    print("Adjust sliders. Press 's' to save settings, 'e' to export, 'q' to quit.")

    cv2.namedWindow(WINDOW_PREVIEW, cv2.WINDOW_NORMAL)
    create_controls()

    last_params = {}

    while True:
        params = read_params()

        if params != last_params:
            result = preprocess(img_disp, params)
            # Convert to BGR so OpenCV can display
            preview = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
            cv2.imshow(WINDOW_PREVIEW, preview)
            last_params = params.copy()

        key = cv2.waitKey(50) & 0xFF

        if key == ord('q'):
            print("Quit.")
            break

        elif key == ord('s'):
            out = Path("tuner_settings.txt")
            with open(out, "w") as f:
                f.write("# Sheet Music Tuner — saved parameters\n")
                for k, v in params.items():
                    f.write(f"{k} = {v}\n")
            print(f"Settings saved to {out.resolve()}")
            print("Parameters:", json.dumps(params, indent=2))

        elif key == ord('e'):
            # Export full-resolution processed image
            result_full = preprocess(img_orig, params)
            out = Path("output_preview.png")
            cv2.imwrite(str(out), result_full)
            print(f"Exported full-res preprocessed image to {out.resolve()}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
