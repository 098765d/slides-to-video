#!/usr/bin/env python3
"""Generate visual cue PNGs from visual anchor notes.

Two cue styles, chosen by each anchor's `shape`:
  - laser (default): a point -> red laser-pointer dot, needs `target: [x, y]`
  - rectangle:       an area -> clean red rectangle, needs `box: [x, y, w, h]`
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict

import yaml
from PIL import Image, ImageDraw

from script_parser import parse_used_cues

LASER_COLOR = (255, 28, 28, 255)
LASER_RADIUS_RATIO = 0.0045
RECT_COLOR = (220, 0, 0, 255)
RECT_WIDTH_RATIO = 0.0015  # ~3 px at 1920 width; scales down correctly

RECT_SHAPES = {"rectangle", "rect", "box"}


def validate_point(point, label: str) -> None:
    if not (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(isinstance(v, (int, float)) for v in point)
        and all(0.0 <= float(v) <= 1.0 for v in point)
    ):
        sys.exit(f"{label} must be [x, y] with values between 0 and 1")


def validate_box(box, label: str) -> None:
    if (
        not (
            isinstance(box, (list, tuple))
            and len(box) == 4
            and all(isinstance(v, (int, float)) for v in box)
            and all(0.0 <= float(v) <= 1.0 for v in box)
        )
        or float(box[0]) + float(box[2]) > 1
        or float(box[1]) + float(box[3]) > 1
    ):
        sys.exit(f"{label} must be [x, y, w, h] within slide bounds")


def load_notes(path: str) -> Dict[int, Dict[str, dict]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    slides = data.get("slides")

    if not isinstance(slides, list):
        sys.exit("visual_notes.yaml must contain a top-level 'slides:' list")

    notes: Dict[int, Dict[str, dict]] = {}

    for slide in slides:
        if not isinstance(slide, dict) or "slide" not in slide:
            sys.exit("each slide entry needs a numeric 'slide' field")

        slide_no = int(slide["slide"])
        anchors: Dict[str, dict] = {}

        for item in slide.get("visuals", []) or []:
            if not isinstance(item, dict):
                sys.exit(f"slide {slide_no}: every visual cue must be a mapping")

            cue = str(item.get("id", "")).strip().upper()
            if not re.fullmatch(r"[A-Z]", cue):
                sys.exit(f"slide {slide_no}: cue id must be one letter A-Z")

            if cue in anchors:
                sys.exit(f"slide {slide_no}: duplicate cue [{cue}]")

            # Normalize two accepted anchor shapes into one flat form:
            #   nested  point:{target:[x,y]}   / area:{shape, box}  (from vision agents)
            #   flat    target:[x,y]           / shape + box        (documented form)
            norm: dict = {"location": item.get("location", ""), "element": item.get("element", "")}
            if isinstance(item.get("point"), dict):
                norm["target"] = item["point"].get("target")
            elif isinstance(item.get("area"), dict):
                norm["shape"] = item["area"].get("shape", "rectangle")
                norm["box"] = item["area"].get("box")
            elif "target" in item:
                norm["target"] = item["target"]
            else:
                norm["shape"] = item.get("shape", "rectangle")
                norm["box"] = item.get("box")

            shape = str(norm.get("shape", "laser")).strip().lower()
            if shape in RECT_SHAPES:
                validate_box(norm.get("box"), f"slide {slide_no} cue {cue} box")
            else:
                validate_point(norm.get("target"), f"slide {slide_no} cue {cue} target")

            anchors[cue] = norm

        notes[slide_no] = anchors

    return notes


def locate_slide(slides_dir: str, slide_no: int) -> Path:
    for name in (
        f"slide-{slide_no:02d}.png",
        f"slide-{slide_no}.png",
    ):
        path = Path(slides_dir) / name
        if path.exists():
            return path

    sys.exit(f"slide {slide_no}: could not find rendered PNG in {slides_dir}")


def draw_laser_pointer(image: Image.Image, target) -> Image.Image:
    """Draw a compact glowing red laser-pointer dot."""
    im = image.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    w, h = im.size
    tx = float(target[0]) * w
    ty = float(target[1]) * h

    radius = max(5, int(round(w * LASER_RADIUS_RATIO)))

    # Soft outer glow.
    for r, alpha in [
        (radius * 3.0, 22),
        (radius * 2.2, 42),
        (radius * 1.6, 78),
    ]:
        draw.ellipse((tx - r, ty - r, tx + r, ty + r), fill=(255, 0, 0, alpha))

    # Bright red laser dot.
    draw.ellipse(
        (tx - radius, ty - radius, tx + radius, ty + radius),
        fill=LASER_COLOR,
    )

    # Small bright centre.
    core = max(2, int(round(radius * 0.34)))
    draw.ellipse(
        (tx - core, ty - core, tx + core, ty + core),
        fill=(255, 215, 215, 255),
    )

    return Image.alpha_composite(im, overlay)


def draw_rectangle(image: Image.Image, box) -> Image.Image:
    """Draw a clean red rectangle around a normalized [x, y, w, h] region."""
    im = image.convert("RGBA")
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = im.size
    x, y, bw, bh = (float(v) for v in box)
    width = max(2, int(round(w * RECT_WIDTH_RATIO)))
    draw.rectangle(
        (x * w, y * h, (x + bw) * w, (y + bh) * h),
        outline=RECT_COLOR,
        width=width,
    )
    return Image.alpha_composite(im, overlay)


def draw_cue(image: Image.Image, anchor: dict) -> Image.Image:
    shape = str(anchor.get("shape", "laser")).strip().lower()
    if shape in RECT_SHAPES:
        return draw_rectangle(image, anchor["box"])
    return draw_laser_pointer(image, anchor["target"])


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
                annotated = draw_cue(base, anchor)

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
