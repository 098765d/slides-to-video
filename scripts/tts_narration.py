#!/usr/bin/env python3
"""Synthesize a cue-aware narration script into one MP3 per visual cue block.

Cue markers such as [A] and [B] are control metadata and are never spoken.
Other bracketed delivery cues such as [pause] and [breathe] are also stripped.
Text before the first visual cue becomes an uncued/base narration block.

Default provider is edge-tts.  Default voice is auto-detected from the script
language (zh-CN-YunxiNeural for Chinese, en-US-AndrewNeural otherwise) unless
--voice is given.

Outputs:
  slide-08-A-01.mp3
  slide-08-B-01.mp3
  slide-09-base-01.mp3
  manifest.json
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
from typing import Dict, List

from script_parser import parse_script

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def default_voice(text: str) -> str:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return "en-US-AndrewNeural"
    cjk = sum(1 for c in chars if CJK_RE.match(c))
    return "zh-CN-YunxiNeural" if cjk / len(chars) > 0.2 else "en-US-AndrewNeural"


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
    ap.add_argument("--voice", default=None,
                    help="voice name; default is auto-detected from the script language")
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

    segments = parse_script(a.script)
    if a.voice is None:
        a.voice = default_voice(" ".join(str(s["text"]) for s in segments))

    os.makedirs(a.outdir, exist_ok=True)
    manifest: List[Dict[str, object]] = []

    for seg in segments:
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
