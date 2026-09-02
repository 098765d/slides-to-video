#!/usr/bin/env python3
"""Rasterize a .pptx/.pdf deck into high-resolution PNGs (one per slide).

Usage:
  python3 slides_to_png.py DECK.(pptx|pdf) OUTDIR [--width 1920]

Requires: libreoffice (for .pptx input), pdftoppm (poppler-utils).
Output PNGs are named slide-01.png, slide-02.png, ... at the requested width.
Prints the slide count as the last stdout line:  SLIDES=N
"""
import argparse, glob, os, subprocess, sys, tempfile

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("outdir")
    ap.add_argument("--width", type=int, default=1920)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    deck = os.path.abspath(a.deck)

    if deck.lower().endswith(".pptx"):
        tmp = tempfile.mkdtemp()
        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf",
                        "--outdir", tmp, deck], check=True, capture_output=True)
        pdf = glob.glob(os.path.join(tmp, "*.pdf"))[0]
    elif deck.lower().endswith(".pdf"):
        pdf = deck
    else:
        sys.exit("Unsupported input: use .pptx or .pdf")

    # -scale-to-x keeps aspect ratio; -png writes slide-1.png ... zero-padded per poppler
    subprocess.run(["pdftoppm", "-png", "-r", "300",
                    "-scale-to-x", str(a.width), "-scale-to-y", "-1",
                    pdf, os.path.join(a.outdir, "slide")], check=True)
    files = sorted(glob.glob(os.path.join(a.outdir, "slide-*.png")))
    # normalize to zero-padded two-digit names for stable sorting
    for i, f in enumerate(files, 1):
        os.rename(f, os.path.join(a.outdir, f"slide-{i:02d}.png"))
    print(f"SLIDES={len(files)}")

if __name__ == "__main__":
    main()
