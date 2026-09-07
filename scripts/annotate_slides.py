#!/usr/bin/env python3
"""Generate arrow-annotated slide PNGs from visual anchor notes.

The tool keeps the annotation model intentionally simple: each cue points to one
normalized target coordinate on a rendered slide.  An optional normalized
``from`` coordinate can control where the arrow starts; otherwise a sensible
start point is chosen automatically.

Visual notes format (YAML):

slides:
  - slide: 8
    title: Model evaluation
    visuals:
      - id: A
        location: left
        element: confusion matrix
        target: [0.27, 0.53]
      - id: B
        location: middle-right
        element: missed detections card
        target: [0.62, 0.66]
        from: [0.78, 0.48]   # optional

Usage:
  python3 annotate_slides.py SLIDES_DIR visual_notes.yaml OUTDIR
  python3 annotate_slides.py SLIDES_DIR visual_notes.yaml OUTDIR \
      --script narration_script.md

If --script is supplied, cue markers in the script are validated against the
visual notes and only cues actually used by the narration are rendered.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import yaml
from PIL import Image, ImageDraw


SLIDE_RE = re.compile(r"^##\s+Slide\s+(\d+)\b", re.M)
CUE_RE = re.compile(r"\[([A-Z])\]")


def load_notes(path: str) -> Dict[int, Dict[str, dict]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    rows = data.get("slides", data if isinstance(data, list) else None)
    if not isinstance(rows, list):
        sys.exit("visual notes must contain a top-level 'slides:' list")

    out: Dict[int, Dict[str, dict]] = {}
    for slide_row in rows:
        if not isinstance(slide_row, dict) or "slide" not in slide_row:
            sys.exit("each visual-notes slide entry needs a numeric 'slide' field")
        slide_no = int(slide_row["slide"])
        anchors: Dict[str, dict] = {}
        for item in slide_row.get("visuals", []) or []:
            if not isinstance(item, dict):
                sys.exit(f"slide {slide_no}: every visual anchor must be a mapping")
            cue = str(item.get("id", "")).strip().upper()
            if not re.fullmatch(r"[A-Z]", cue):
                sys.exit(f"slide {slide_no}: visual anchor id must be A-Z, got {cue!r}")
            target = item.get("target")
            validate_point(target, f"slide {slide_no} cue {cue} target")
            if "from" in item and item["from"] is not None:
                validate_point(item["from"], f"slide {slide_no} cue {cue} from")
            if cue in anchors:
                sys.exit(f"slide {slide_no}: duplicate visual anchor [{cue}]")
            anchors[cue] = item
        out[slide_no] = anchors
    return out


def validate_point(point: object, label: str) -> None:
    if not (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(isinstance(v, (int, float)) for v in point)
        and all(0.0 <= float(v) <= 1.0 for v in point)
    ):
        sys.exit(f"{label} must be [x, y] with values between 0 and 1")


def parse_used_cues(script_path: str) -> Dict[int, Set[str]]:
    """Return {slide: {A,B,...}} from cue markers inside **Say:** blocks."""
    text = Path(script_path).read_text(encoding="utf-8")
    matches = list(SLIDE_RE.finditer(text))
    used: Dict[int, Set[str]] = {}
    for idx, m in enumerate(matches):
        slide_no = int(m.group(1))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[m.start():end]
        say = re.search(r"\*\*Say:\*\*\s*(.*?)(?=\n\*\*[A-Za-z][^\n]*\*\*:|\n---|\Z)", block, re.S)
        if not say:
            continue
        used[slide_no] = set(CUE_RE.findall(say.group(1)))
    return used


def hex_color(s: str) -> Tuple[int, int, int, int]:
    s = s.strip().lstrip("#")
    if len(s) != 6 or not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        sys.exit("--color must be a 6-digit hex colour such as E63946")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def auto_origin(tx: float, ty: float) -> Tuple[float, float]:
    """Choose a nearby origin that points inward without hugging the edge."""
    dx = -0.18 if tx >= 0.5 else 0.18
    dy = -0.14 if ty >= 0.45 else 0.14
    sx = min(0.92, max(0.08, tx + dx))
    sy = min(0.90, max(0.10, ty + dy))
    return sx, sy


def draw_arrow(
    image: Image.Image,
    start_n: Sequence[float],
    target_n: Sequence[float],
    color: Tuple[int, int, int, int],
    width_ratio: float,
    head_ratio: float,
) -> Image.Image:
    im = image.convert("RGBA")
    draw = ImageDraw.Draw(im)
    w, h = im.size
    sx, sy = float(start_n[0]) * w, float(start_n[1]) * h
    tx, ty = float(target_n[0]) * w, float(target_n[1]) * h

    line_w = max(4, int(round(w * width_ratio)))
    head = max(16, int(round(w * head_ratio)))
    halo_w = line_w + max(4, line_w // 2)

    dx, dy = tx - sx, ty - sy
    length = max(1.0, math.hypot(dx, dy))
    ux, uy = dx / length, dy / length
    px, py = -uy, ux

    # Pull the shaft back slightly so the arrowhead owns the target end.
    bx, by = tx - ux * head * 0.82, ty - uy * head * 0.82
    left = (bx + px * head * 0.48, by + py * head * 0.48)
    right = (bx - px * head * 0.48, by - py * head * 0.48)

    # White halo improves legibility over screenshots, charts and dark areas.
    halo = (255, 255, 255, 235)
    draw.line((sx, sy, bx, by), fill=halo, width=halo_w)
    draw.polygon([left, (tx, ty), right], fill=halo)

    draw.line((sx, sy, bx, by), fill=color, width=line_w)
    draw.polygon([left, (tx, ty), right], fill=color)
    return im


def locate_slide(slides_dir: str, slide_no: int) -> Optional[Path]:
    candidates = [
        Path(slides_dir) / f"slide-{slide_no:02d}.png",
        Path(slides_dir) / f"slide-{slide_no}.png",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slides_dir")
    ap.add_argument("visual_notes")
    ap.add_argument("outdir")
    ap.add_argument("--script", help="optional narration script for cue validation")
    ap.add_argument("--color", default="E63946", help="arrow colour, hex without #")
    ap.add_argument("--width-ratio", type=float, default=0.0055,
                    help="arrow shaft width as a fraction of image width")
    ap.add_argument("--head-ratio", type=float, default=0.020,
                    help="arrowhead size as a fraction of image width")
    ap.add_argument("--copy-clean", action="store_true",
                    help="also copy clean slide PNGs into OUTDIR as slide-XX-base.png")
    a = ap.parse_args()

    notes = load_notes(a.visual_notes)
    used = parse_used_cues(a.script) if a.script else None
    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    color = hex_color(a.color)

    # Validate cue references before writing any outputs.
    if used is not None:
        errors: List[str] = []
        for slide_no, cues in sorted(used.items()):
            anchors = notes.get(slide_no, {})
            for cue in sorted(cues):
                if cue not in anchors:
                    errors.append(f"slide {slide_no}: script uses [{cue}] but visual_notes has no matching anchor")
        if errors:
            sys.exit("visual cue validation failed:\n  - " + "\n  - ".join(errors))

    rendered = 0
    for slide_no, anchors in sorted(notes.items()):
        src = locate_slide(a.slides_dir, slide_no)
        if not src:
            sys.exit(f"slide {slide_no}: could not find rendered slide PNG in {a.slides_dir}")

        if a.copy_clean:
            shutil.copy2(src, outdir / f"slide-{slide_no:02d}-base.png")

        wanted: Iterable[str] = anchors.keys()
        if used is not None:
            wanted = [c for c in anchors if c in used.get(slide_no, set())]

        with Image.open(src) as base:
            for cue in wanted:
                anchor = anchors[cue]
                target = [float(v) for v in anchor["target"]]
                start = anchor.get("from")
                if start is None:
                    start = auto_origin(target[0], target[1])
                annotated = draw_arrow(base, start, target, color,
                                       a.width_ratio, a.head_ratio)
                out = outdir / f"slide-{slide_no:02d}-{cue}.png"
                annotated.convert("RGB").save(out, "PNG", optimize=True)
                rendered += 1
                element = str(anchor.get("element", "")).strip()
                print(f"slide {slide_no} [{cue}] -> {out.name}" + (f" ({element})" if element else ""))

    print(f"CUES={rendered}")


if __name__ == "__main__":
    main()
