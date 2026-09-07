#!/usr/bin/env python3
"""Synthesize a cue-aware narration script into one MP3 per visual cue block.

Script example:

  ## Slide 8 — Validation
  **Visuals:**
  - [A] left — confusion matrix
  - [B] right — missed detections card
  **Say:**
  [A] The matrix shows how the model performed on a historical cohort.
  [B] The value to focus on is missed detections.

Cue markers such as [A] and [B] are control metadata and are never spoken.
Other bracketed delivery cues such as [pause] and [breathe] are also stripped.
Text before the first visual cue becomes an uncued/base narration block.

Outputs:
  slide-08-A-01.mp3
  slide-08-B-01.mp3
  slide-09-base-01.mp3
  manifest.json

The manifest records slide number, cue id, order, filename, text and measured
TTS duration.  assemble_video.py uses it as the timing source.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


SLIDE_RE = re.compile(r"^##\s+Slide\s+(\d+)\b", re.M)
CUE_RE = re.compile(r"\[([A-Z])\]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")


def extract_say(block: str, slide_no: int) -> str:
    m = re.search(
        r"\*\*Say:\*\*\s*(.*?)(?=\n\*\*[A-Za-z][^\n]*\*\*:|\n---|\Z)",
        block,
        re.S,
    )
    if not m:
        sys.exit(f"Slide {slide_no}: no '**Say:**' block found")
    return m.group(1).strip()


def clean_spoken(text: str) -> str:
    # All bracket metadata is non-spoken after visual cues have been parsed.
    text = BRACKET_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_cues(say: str) -> List[Dict[str, object]]:
    """Split spoken content into ordered cue blocks.

    A cue marker begins a new block and remains active until another cue marker.
    Text before the first marker is a base block with cue=None.
    """
    matches = list(CUE_RE.finditer(say))
    if not matches:
        cleaned = clean_spoken(say)
        return [{"cue": None, "text": cleaned}] if cleaned else []

    segments: List[Dict[str, object]] = []
    if say[: matches[0].start()].strip():
        cleaned = clean_spoken(say[: matches[0].start()])
        if cleaned:
            segments.append({"cue": None, "text": cleaned})

    for idx, match in enumerate(matches):
        cue = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(say)
        cleaned = clean_spoken(say[start:end])
        if cleaned:
            segments.append({"cue": cue, "text": cleaned})
    return segments


def parse_script(path: str) -> List[Dict[str, object]]:
    text = Path(path).read_text(encoding="utf-8")
    matches = list(SLIDE_RE.finditer(text))
    if not matches:
        sys.exit("No '## Slide N' blocks found. Check the script format.")

    out: List[Dict[str, object]] = []
    for idx, m in enumerate(matches):
        slide_no = int(m.group(1))
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = text[m.start():end]
        say = extract_say(block, slide_no)
        cue_counts: Dict[str, int] = {}
        base_count = 0
        for order, seg in enumerate(split_cues(say), 1):
            cue = seg["cue"]
            if cue is None:
                base_count += 1
                occurrence = base_count
                tag = "base"
            else:
                cue_s = str(cue)
                cue_counts[cue_s] = cue_counts.get(cue_s, 0) + 1
                occurrence = cue_counts[cue_s]
                tag = cue_s
            out.append(
                {
                    "slide": slide_no,
                    "order": order,
                    "cue": cue,
                    "occurrence": occurrence,
                    "tag": tag,
                    "text": seg["text"],
                }
            )
    if not out:
        sys.exit("No narration found in the script.")
    return out


def synth_edge(text: str, voice: str, rate: str, out: str) -> None:
    subprocess.run(
        ["edge-tts", "--voice", voice, "--rate", rate,
         "--text", text, "--write-media", out],
        check=True,
        capture_output=True,
    )


def synth_openai(
    text: str,
    voice: str,
    out: str,
    base_url: str,
    api_key: str,
    model: str,
) -> None:
    body = json.dumps({"model": model, "voice": voice, "input": text}).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/audio/speech",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        Path(out).write_bytes(response.read())


def duration(path: str) -> float:
    return float(
        subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path]
        ).decode().strip()
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("outdir")
    ap.add_argument("--provider", choices=["edge", "openai"], default="edge")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--base-url", default=os.environ.get("TTS_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("TTS_API_KEY"))
    ap.add_argument("--model", default=os.environ.get("TTS_MODEL"))
    ap.add_argument("--manifest", help="output manifest path; default OUTDIR/manifest.json")
    a = ap.parse_args()

    if a.provider == "openai" and not (a.base_url and a.api_key and a.model):
        sys.exit(
            "provider=openai needs --base-url, --api-key, --model "
            "(or TTS_BASE_URL / TTS_API_KEY / TTS_MODEL env vars)"
        )

    os.makedirs(a.outdir, exist_ok=True)
    manifest: List[Dict[str, object]] = []

    for seg in parse_script(a.script):
        slide = int(seg["slide"])
        tag = str(seg["tag"])
        occurrence = int(seg["occurrence"])
        filename = f"slide-{slide:02d}-{tag}-{occurrence:02d}.mp3"
        out = os.path.join(a.outdir, filename)
        text = str(seg["text"])

        for attempt in (1, 2):
            try:
                if a.provider == "edge":
                    synth_edge(text, a.voice, a.rate, out)
                else:
                    synth_openai(text, a.voice, out, a.base_url, a.api_key, a.model)
                break
            except Exception as exc:
                if attempt == 2:
                    sys.exit(
                        f"slide {slide} cue {seg['cue'] or 'base'}: "
                        f"TTS failed twice: {exc}"
                    )
                time.sleep(2)

        dur = duration(out)
        record = dict(seg)
        record["audio"] = filename
        record["duration"] = round(dur, 4)
        manifest.append(record)
        print(
            f"slide {slide} [{seg['cue'] or 'base'}] -> {out} ({dur:.1f}s)"
        )

    manifest_path = a.manifest or os.path.join(a.outdir, "manifest.json")
    Path(manifest_path).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"MANIFEST={manifest_path} SEGMENTS={len(manifest)}")


if __name__ == "__main__":
    main()
