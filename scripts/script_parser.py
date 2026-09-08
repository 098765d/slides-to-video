#!/usr/bin/env python3
"""Shared narration-script parsing for the slides-to-video pipeline.

Both annotate_slides.py and tts_narration.py consume the same
``## Slide N`` / ``**Say:**`` format.  Keeping the parser here means cue
validation and TTS segmentation can never drift apart.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set

SLIDE_RE = re.compile(r"^##\s+Slide\s+(\d+)\b", re.M)
CUE_RE = re.compile(r"\[([A-Z])\]")
BRACKET_RE = re.compile(r"\[[^\]]*\]")

_SAY_RE = re.compile(
    r"\*\*Say:\*\*\s*(.*?)(?=\n\*\*[A-Za-z][^\n]*?:\*\*|\n---|\Z)",
    re.S,
)


def extract_say(block: str, slide_no: int) -> str:
    m = _SAY_RE.search(block)
    if not m:
        sys.exit(f"Slide {slide_no}: no '**Say:**' block found")
    return m.group(1).strip()


def clean_spoken(text: str) -> str:
    # All bracket metadata is non-spoken once visual cues have been parsed.
    text = BRACKET_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def split_cues(say: str) -> List[Dict[str, object]]:
    """Split spoken content into ordered cue blocks.

    A [A-Z] marker begins a block that stays active until the next marker.
    Text before the first marker becomes a base block with cue=None.
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
    """Return one record per spoken cue block.

    Each record carries: slide, order, cue, occurrence, tag, text.
    """
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


def parse_used_cues(path: str) -> Dict[int, Set[str]]:
    """Return the [A-Z] cue markers used inside each slide's **Say:** block."""
    used: Dict[int, Set[str]] = {}
    for rec in parse_script(path):
        cue = rec["cue"]
        if cue is not None:
            used.setdefault(int(rec["slide"]), set()).add(str(cue))
    return used
