#!/usr/bin/env python3
"""Snap coarse anchor boxes onto the actual content of the rendered slide.

The vision model proposes WHERE an element is (a coarse box); this script makes
the box exact with one deterministic pass:

  1. open a search window around the coarse box (--expand px, default 150);
  2. mask = pixels that are not page-white;
  3. glue content closer than about 2*--glue px into blobs (default 8);
  4. keep the blob overlapping the coarse box the most, plus any blob lying
     fully inside the coarse box (detached captions), and take that union's
     bounding box.

Usage:
  python3 tighten_boxes.py SLIDES_DIR VISUAL_NOTES [--out OUT.yaml]
      [--expand 150] [--glue 8] [--overlay-dir DIR]

Input : slides_dir + visual_notes.yaml (coarse boxes).
Output: a refined yaml (default: <notes>.tight.yaml; the original is never
        modified) and one overlay PNG per affected slide (old box grey, new
        box red).

Always look at the overlays before rendering cues.  The algorithm measures
edges well, but it cannot know which blobs belong to one element; if a box
grew over a neighbouring paragraph, or shrank, correct that box by hand in the
yaml.  Dot anchors (`target:`) are passed through unchanged.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

try:
    from scipy import ndimage
except ImportError:  # pragma: no cover
    sys.exit("tighten_boxes.py needs scipy: pip install scipy")


def locate_slide(slides_dir: str, slide_no: int) -> Path:
    for name in (f"slide-{slide_no:02d}.png", f"slide-{slide_no}.png"):
        path = Path(slides_dir) / name
        if path.exists():
            return path

    sys.exit(f"slide {slide_no}: could not find rendered PNG in {slides_dir}")


def tighten_box(arr: np.ndarray, box_px: tuple, expand: int, glue: int) -> tuple:
    """Return the tightened pixel box for one coarse box."""
    h, w = arr.shape[:2]
    x0 = max(0, box_px[0] - expand)
    y0 = max(0, box_px[1] - expand)
    x1 = min(w - 1, box_px[2] + expand)
    y1 = min(h - 1, box_px[3] + expand)
    win = arr[y0:y1 + 1, x0:x1 + 1]

    mask = (255 - win).max(axis=2) > 10
    blob_labels, blob_count = ndimage.label(
        ndimage.binary_dilation(mask, iterations=glue)
    )

    bx0, by0, bx1, by1 = box_px
    region = (slice(max(0, by0 - y0), by1 - y0), slice(max(0, bx0 - x0), bx1 - x0))

    selected, best = 0, -1
    for i in range(1, blob_count + 1):
        overlap = ((blob_labels == i) & mask)[region].sum()
        if overlap > best:
            best, selected = overlap, i

    keep = {selected}
    for i in range(1, blob_count + 1):
        if i == selected:
            continue
        ys, xs = np.nonzero((blob_labels == i) & mask)
        if ys.size and (
            x0 + xs.min() >= bx0 and x0 + xs.max() <= bx1
            and y0 + ys.min() >= by0 and y0 + ys.max() <= by1
        ):
            keep.add(i)

    ys, xs = np.nonzero(np.isin(blob_labels, list(keep)) & mask)
    return (
        int(x0 + xs.min()),
        int(y0 + ys.min()),
        int(x0 + xs.max()),
        int(y0 + ys.max()),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slides_dir")
    ap.add_argument("visual_notes")
    ap.add_argument("--out", help="refined yaml path; default <notes>.tight.yaml")
    ap.add_argument("--expand", type=int, default=150,
                    help="search window margin around each coarse box, px (default 150)")
    ap.add_argument("--glue", type=int, default=8,
                    help="fusion distance for content blobs, px (default 8)")
    ap.add_argument("--overlay-dir",
                    help="overlay output dir; default <out dir>/tight_overlays")
    ap.add_argument("--no-overlay", action="store_true")
    args = ap.parse_args()

    notes_path = Path(args.visual_notes)
    data = yaml.safe_load(notes_path.read_text(encoding="utf-8")) or {}
    slides = data.get("slides")
    if not isinstance(slides, list):
        sys.exit("visual_notes.yaml must contain a top-level 'slides:' list")

    out_path = Path(args.out) if args.out else notes_path.with_suffix(".tight.yaml")
    overlay_dir = Path(args.overlay_dir) if args.overlay_dir else out_path.parent / "tight_overlays"

    changed = 0
    for slide in slides:
        slide_no = int(slide.get("slide", 0))
        visuals = slide.get("visuals") or []
        boxes = [v for v in visuals if isinstance(v.get("box"), (list, tuple))]
        if not boxes:
            continue

        source = locate_slide(args.slides_dir, slide_no)
        image = Image.open(source).convert("RGB")
        arr = np.asarray(image).astype(int)
        w, h = image.size

        draw = ImageDraw.Draw(image)
        for item in boxes:
            x, y, bw, bh = (float(v) for v in item["box"])
            coarse_px = (
                round(x * w), round(y * h),
                round((x + bw) * w), round((y + bh) * h),
            )
            tight_px = tighten_box(arr, coarse_px, args.expand, args.glue)
            tx0, ty0, tx1, ty1 = tight_px

            draw.rectangle(coarse_px, outline=(150, 150, 150), width=2)
            draw.rectangle(tight_px, outline=(220, 0, 0), width=3)

            new_box = [
                round(tx0 / w, 4), round(ty0 / h, 4),
                round((tx1 - tx0 + 1) / w, 4), round((ty1 - ty0 + 1) / h, 4),
            ]
            old_box = [round(float(v), 4) for v in item["box"]]
            item["box"] = new_box
            changed += 1

            delta = max(
                abs(new_box[i] - old_box[i]) * (w if i % 2 == 0 else h)
                for i in range(2)
            )
            grew = ((new_box[2] * new_box[3]) / max(1e-6, old_box[2] * old_box[3]))
            flag = "  <-- box grew a lot, check overlay" if grew > 2.2 else ""
            print(
                f"slide {slide_no:>2} [{item.get('id', '?')}] "
                f"{old_box} -> {new_box}  (max edge move {delta:.0f}px){flag}"
            )

        if not args.no_overlay:
            overlay_dir.mkdir(parents=True, exist_ok=True)
            image.save(overlay_dir / f"slide-{slide_no:02d}.png",
                       "PNG", optimize=True)

    out_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(f"REFINED={out_path} BOXES={changed}")
    if not args.no_overlay:
        print(f"OVERLAYS={overlay_dir}  (grey = coarse box, red = tightened box; "
              "look at these before rendering cues)")


if __name__ == "__main__":
    main()
