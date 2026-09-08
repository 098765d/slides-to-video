#!/usr/bin/env python3
"""Rasterize a .pptx/.pdf deck into high-resolution PNGs (one per slide).

Usage:
  python3 slides_to_png.py DECK.(pptx|pdf) OUTDIR [--width 1920]

Rendering backend is chosen by platform:
  - Windows + .pptx : PowerPoint COM (win_pptx_to_png.ps1) — no LibreOffice needed.
  - Linux/macOS     : LibreOffice (PPTX -> PDF) + pdftoppm (poppler-utils).
  - PDF everywhere  : pdftoppm (poppler-utils).

Output PNGs are named slide-01.png, slide-02.png, ... at the requested width.
Prints the slide count as the last stdout line:  SLIDES=N
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("deck")
    ap.add_argument("outdir")
    ap.add_argument("--width", type=int, default=1920)
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    deck = os.path.abspath(a.deck)

    if sys.platform == "win32" and deck.lower().endswith(".pptx"):
        ps1 = os.path.join(HERE, "win_pptx_to_png.ps1")
        subprocess.run(
            [
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", ps1,
                "-Deck", deck,
                "-OutDir", a.outdir,
                "-Width", str(a.width),
            ],
            check=True,
        )
        files = sorted(glob.glob(os.path.join(a.outdir, "slide-*.png")))
        print(f"SLIDES={len(files)}")
        return

    if deck.lower().endswith(".pptx"):
        tmp = tempfile.mkdtemp()
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf",
             "--outdir", tmp, deck],
            check=True,
            capture_output=True,
        )
        pdf = glob.glob(os.path.join(tmp, "*.pdf"))[0]
    elif deck.lower().endswith(".pdf"):
        pdf = deck
    else:
        sys.exit("Unsupported input: use .pptx or .pdf")

    subprocess.run(
        ["pdftoppm", "-png", "-r", "300",
         "-scale-to-x", str(a.width), "-scale-to-y", "-1",
         pdf, os.path.join(a.outdir, "slide")],
        check=True,
    )
    files = sorted(glob.glob(os.path.join(a.outdir, "slide-*.png")))
    for i, f in enumerate(files, 1):
        os.rename(f, os.path.join(a.outdir, f"slide-{i:02d}.png"))
    print(f"SLIDES={len(files)}")


if __name__ == "__main__":
    main()
