#!/usr/bin/env python3
"""Generate pointer-annotated slide PNGs from visual anchor notes.

Each visual cue points to one normalized target coordinate on a rendered slide.

Example visual_notes.yaml:

slides:
  - slide: 8
    visuals:
      - id: A
        element: confusion matrix
        target: [0.27, 0.53]

Usage:
  python3 annotate_slides.py SLIDES_DIR visual_notes.yaml OUTDIR
  python3 annotate_slides.py SLIDES_DIR visual_notes.yaml OUTDIR \
      --script narration_script.md

If --script is supplied, only cues actually used in the narration are rendered.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, Set

import yaml
from PIL import Image, ImageDraw


SLIDE_RE = re.compile(r"^##\s+Slide\s+(\d+)\b", re.M)
CUE_RE = re.compile(r"\[([A-Z])\]")

# Fixed visual style.
POINTER_COLOR = (11, 93, 70, 255)   # #0B5D46
POINTER_SIZE_RATIO = 0.028


def validate_point(point, label: str) -> None:
    if not (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(isinstance(v, (int, float)) for v in point)
        and all(0.0 <= float(v) <= 1.0 for v in point)
    ):
        sys.exit(f"{label} must be [x, y] with values between 0 and 1")


def load_notes(path: str) -> Dict[int, Dict[str, dict]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    slides = data.get("slides")

    if not isinstance(slides, list):
        sys.exit("visual_notes.yaml must contain a top-level 'slides:' list")

    notes: Dict[int, Dict[str, dict]] = {}

    for slide in slides:
        slide_no = int(slide["slide"])
        anchors: Dict[str, dict] = {}

        for item in slide.get("visuals", []) or []:
            cue = str(item.get("id", "")).strip().upper()

            if not re.fullmatch(r"[A-Z]", cue):
                sys.exit(
                    f"slide {slide_no}: cue id must be one letter A-Z"
                )

            validate_point(
                item.get("target"),
                f"slide {slide_no} cue {cue} target",
            )

            if cue in anchors:
                sys.exit(f"slide {slide_no}: duplicate cue [{cue}]")

            anchors[cue] = item

        notes[slide_no] = anchors

    return notes


def parse_used_cues(script_path: str) -> Dict[int, Set[str]]:
    """Return cue markers used inside each slide's **Say:** block."""
    text = Path(script_path).read_text(encoding="utf-8")
    matches = list(SLIDE_RE.finditer(text))
    used: Dict[int, Set[str]] = {}

    for i, match in enumerate(matches):
        slide_no = int(match.group(1))
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.start():end]

        say = re.search(
            r"\*\*Say:\*\*\s*(.*?)(?=\n\*\*[A-Za-z][^\n]*\*\*:|\n---|\Z)",
            block,
            re.S,
        )

        if say:
            used[slide_no] = set(CUE_RE.findall(say.group(1)))

    return used


def locate_slide(slides_dir: str, slide_no: int) -> Path:
    for name in (
        f"slide-{slide_no:02d}.png",
        f"slide-{slide_no}.png",
    ):
        path = Path(slides_dir) / name
        if path.exists():
            return path

    sys.exit(
        f"slide {slide_no}: could not find rendered PNG in {slides_dir}"
    )


def draw_pointer(image: Image.Image, target) -> Image.Image:
    """Draw a compact cursor-style pointer with small attention rays."""
    im = image.convert("RGBA")
    draw = ImageDraw.Draw(im)

    w, _ = im.size
    tx = float(target[0]) * im.width
    ty = float(target[1]) * im.height

    size = max(22, int(round(w * POINTER_SIZE_RATIO)))
    outline_w = max(3, int(round(size * 0.085)))
    ray_w = max(2, int(round(size * 0.065)))

    tip = (tx, ty)

    points = [
        tip,
        (tx - size * 0.16, ty - size * 0.88),
        (tx + size * 0.50, ty - size * 0.28),
        (tx + size * 0.18, ty - size * 0.14),
        (tx + size * 0.40, ty + size * 0.36),
        (tx + size * 0.18, ty + size * 0.46),
        (tx - size * 0.04, ty - size * 0.02),
    ]

    draw.polygon(points, fill=(255, 255, 255, 242))
    draw.line(
        [*points, tip],
        fill=POINTER_COLOR,
        width=outline_w,
        joint="curve",
    )

    rays = [
        (
            (tx - size * 0.27, ty - size * 0.69),
            (tx - size * 0.45, ty - size * 0.89),
        ),
        (
            (tx - size * 0.03, ty - size * 0.84),
            (tx - size * 0.04, ty - size * 1.08),
        ),
        (
            (tx + size * 0.19, ty - size * 0.72),
            (tx + size * 0.34, ty - size * 0.91),
        ),
    ]

    for start, end in rays:
        draw.line(
            [start, end],
            fill=POINTER_COLOR,
            width=ray_w,
        )

    return im


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("slides_dir")
    parser.add_argument("visual_notes")
    parser.add_argument("outdir")
    parser.add_argument(
        "--script",
        help="optional narration script; only used cues will be rendered",
    )
    args = parser.parse_args()

    notes = load_notes(args.visual_notes)
    used = parse_used_cues(args.script) if args.script else None

    # Validate script cues before writing outputs.
    if used is not None:
        errors = []

        for slide_no, cues in sorted(used.items()):
            anchors = notes.get(slide_no, {})

            for cue in sorted(cues):
                if cue not in anchors:
                    errors.append(
                        f"slide {slide_no}: script uses [{cue}] "
                        "but visual_notes has no matching anchor"
                    )

        if errors:
            sys.exit(
                "visual cue validation failed:\n  - "
                + "\n  - ".join(errors)
            )

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rendered = 0

    for slide_no, anchors in sorted(notes.items()):
        src = locate_slide(args.slides_dir, slide_no)

        wanted = anchors.keys()
        if used is not None:
            wanted = [
                cue for cue in anchors
                if cue in used.get(slide_no, set())
            ]

        with Image.open(src) as base:
            for cue in wanted:
                anchor = anchors[cue]
                annotated = draw_pointer(base, anchor["target"])

                out = outdir / f"slide-{slide_no:02d}-{cue}.png"
                annotated.convert("RGB").save(
                    out,
                    "PNG",
                    optimize=True,
                )

                rendered += 1
                element = str(anchor.get("element", "")).strip()

                print(
                    f"slide {slide_no} [{cue}] -> {out.name}"
                    + (f" ({element})" if element else "")
                )

    print(f"CUES={rendered}")


if __name__ == "__main__":
    main()
