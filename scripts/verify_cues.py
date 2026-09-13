#!/usr/bin/env python3
"""Check rendered cue images with a vision model; downgrade badly placed
rectangles to laser dots.

For every cue image ``slide-XX-<ID>.png`` in CUES_DIR whose anchor exists in
VISUAL_NOTES, one vision call judges the cue placement:

  good          the cue sits on the described element;
  slightly_off  right element, slightly loose or tight margin (accepted, the
                anchor is left untouched);
  bad           clearly misses the element: mostly off it, covering a
                different block, or slicing through the element's content.

A ``bad`` rectangle anchor is downgraded to a laser dot using the point the
model reports inside the element.  A ``bad`` dot anchor is only reported (no
automatic fix is possible).  Nothing else is ever changed automatically - the
model is not allowed to move or reshape a box.

Endpoint (OpenAI-compatible chat completions with image input):

  VERIFY_BASE_URL / VERIFY_API_KEY / VERIFY_MODEL    (or the matching flags)

When no endpoint is configured the script skips and tells you to check the cue
images yourself.

Outputs:
  <notes>.verified.yaml   visual notes with downgrades applied (only written
                          when something changed)
  verify_report.md        one row per cue: verdict, action, reason

Usage:

  python3 scripts/verify_cues.py $BUILD/cues $BUILD/visual_notes.yaml \\
      --report $BUILD/verify_report.md

  # after downgrades, re-render cues from the verified notes:
  python3 scripts/annotate_slides.py $BUILD/slides \\
      $BUILD/visual_notes.verified.yaml $BUILD/cues --script $BUILD/narration_script.md
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import yaml
from PIL import Image

PROMPT = """You are checking ONE rendered slide that has a visual cue drawn on it (image attached).
The cue is supposed to point at this element: "{element}" (location: "{location}").
Cue style: {style}.

Judge ONLY the cue's placement:
- "good": the cue sits on the element as described.
- "slightly_off": the cue is on the right element but its edge or margin is a little loose or tight. This is acceptable.
- "bad": the cue clearly misses the element - mostly off the element, covering a different block, or slicing through the element's content. For a laser dot, "bad" means the dot is not on the element.

Also give one point [x, y] (normalized 0-1, origin top-left) that lies INSIDE the element
(for a rectangle: anywhere inside its area; for a dot: the dot's own position when good).

Reply with ONLY this JSON, no other text:
{{"verdict": "good|slightly_off|bad", "point": [x, y], "why": "one short sentence"}}"""


def load_notes(path: str):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data.get("slides"), list):
        sys.exit("visual_notes.yaml must contain a top-level 'slides:' list")
    return data


def parse_json(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def ask(base_url: str, api_key: str, model: str, prompt: str, image_b64: str) -> str:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + image_b64}},
        ]}],
        "temperature": 0,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=240) as response:
        data = json.loads(response.read().decode())
    return data["choices"][0]["message"]["content"] or ""


def encode_cue(path: Path, max_px: int) -> str:
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.width > max_px:
            height = round(im.height * max_px / im.width)
            im = im.resize((max_px, height), Image.LANCZOS)
        buffer = BytesIO()
        im.save(buffer, "PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode()


def judge_one(args, slide_no: int, item: dict, cue_path: Path, style: str) -> dict:
    prompt = PROMPT.format(
        element=item.get("element", ""),
        location=item.get("location", ""),
        style=style,
    )
    image_b64 = encode_cue(cue_path, args.max_px)
    last_error = ""
    for attempt in (1, 2):
        try:
            raw = ask(args.base_url, args.api_key, args.model, prompt, image_b64)
            verdict = parse_json(raw)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:200]
            if attempt == 2:
                verdict = {"verdict": "error", "point": None, "why": last_error}
            else:
                time.sleep(2)
    return {
        "slide": slide_no,
        "id": str(item.get("id", "?")),
        "element": item.get("element", ""),
        "style": style,
        "verdict": str(verdict.get("verdict", "error")).lower(),
        "point": verdict.get("point"),
        "why": str(verdict.get("why", ""))[:200],
        "cue": cue_path.name,
    }


def apply_downgrade(item: dict, point) -> bool:
    """Turn a bad rectangle anchor into a dot at `point`. Returns True if changed."""
    if not (isinstance(point, (list, tuple)) and len(point) == 2):
        return False
    if not all(isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0 for v in point):
        return False
    item.pop("shape", None)
    item.pop("box", None)
    item["target"] = [round(float(point[0]), 4), round(float(point[1]), 4)]
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cues_dir")
    ap.add_argument("visual_notes")
    ap.add_argument("--out", help="verified yaml path; default <notes>.verified.yaml")
    ap.add_argument("--report", help="report path; default <notes dir>/verify_report.md")
    ap.add_argument("--base-url", default=os.environ.get("VERIFY_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("VERIFY_API_KEY"))
    ap.add_argument("--model", default=os.environ.get("VERIFY_MODEL"))
    ap.add_argument("--max-px", type=int, default=1280,
                    help="downscale cue images before sending (default 1280)")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    notes_path = Path(args.visual_notes)
    notes = load_notes(args.visual_notes)
    cues_dir = Path(args.cues_dir)

    jobs = []
    for slide in notes["slides"]:
        slide_no = int(slide.get("slide", 0))
        for item in slide.get("visuals") or []:
            cue_path = cues_dir / f"slide-{slide_no:02d}-{str(item.get('id', '?')).upper()}.png"
            if not cue_path.exists():
                continue
            style = "rectangle" if item.get("box") is not None else "laser dot"
            jobs.append((slide_no, item, cue_path, style))

    if not jobs:
        sys.exit(f"no cue images found in {cues_dir} matching {args.visual_notes}")

    if not (args.base_url and args.api_key and args.model):
        print(f"{len(jobs)} cue image(s) found, but no vision endpoint is configured")
        print("(set VERIFY_BASE_URL / VERIFY_API_KEY / VERIFY_MODEL, or pass "
              "--base-url/--api-key/--model).")
        print("Check the cue images yourself instead - open them and confirm each "
              "cue contains/points at the element named in visual_notes.yaml.")
        return

    print(f"CHECKING cues={len(jobs)} model={args.model} workers={args.workers}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(
            lambda job: judge_one(args, job[0], job[1], job[2], job[3]), jobs))

    downgraded, manual, errors = 0, 0, 0
    for row in sorted(results, key=lambda r: (r["slide"], r["id"])):
        action = "-"
        if row["verdict"] == "bad":
            if row["style"] == "rectangle":
                item = next(i for s in notes["slides"] if int(s.get("slide", 0)) == row["slide"]
                            for i in (s.get("visuals") or []) if str(i.get("id", "?")).upper() == row["id"])
                if apply_downgrade(item, row["point"]):
                    action = f"-> dot at {item['target']}"
                    downgraded += 1
                else:
                    action = "needs manual fix (no valid point returned)"
                    manual += 1
            else:
                action = "needs manual fix (dot is misplaced)"
                manual += 1
        elif row["verdict"] == "error":
            action = "check failed"
            errors += 1
        row["action"] = action
        print(f"slide {row['slide']:>2} [{row['id']}] {row['style']:9} "
              f"{row['verdict']:12} {action}  {row['why'][:80]}")

    report_path = Path(args.report) if args.report else notes_path.parent / "verify_report.md"
    lines = [
        "# Cue verification report",
        "",
        f"model: `{args.model}` | cues checked: {len(results)} | "
        f"downgraded to dot: {downgraded} | manual: {manual} | errors: {errors}",
        "",
        "| slide | cue | style | verdict | action | reason |",
        "|---|---|---|---|---|---|",
    ]
    for row in sorted(results, key=lambda r: (r["slide"], r["id"])):
        lines.append(
            f"| {row['slide']} | {row['id']} | {row['style']} | {row['verdict']} | "
            f"{row['action']} | {row['why'].replace('|', '/')} |")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if downgraded:
        out_path = Path(args.out) if args.out else notes_path.with_suffix(".verified.yaml")
        out_path.write_text(
            yaml.safe_dump(notes, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        print(f"VERIFIED={out_path} (downgraded {downgraded} box cue(s) to dots)")
        print("re-render cues from the verified notes:")
        print(f"  python3 scripts/annotate_slides.py SLIDES_DIR {out_path} CUES_DIR "
              "--script narration_script.md")
    else:
        print("no downgrades needed; visual notes unchanged")
    print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
