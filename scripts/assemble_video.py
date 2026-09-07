#!/usr/bin/env python3
"""Assemble clean/annotated slide PNGs + cue-level narration into one HD MP4.

The build remains single-pass: every still image and audio block enters one
ffmpeg filtergraph and the complete presentation is encoded once.  This avoids
page-turn flicker and timestamp seams.

Preferred cue-aware usage:
  python3 assemble_video.py SLIDES_DIR AUDIO_DIR OUT.mp4 \
      --cues-dir CUES_DIR

The script automatically reads AUDIO_DIR/manifest.json created by
``tts_narration.py``.  For a narration segment with cue A on slide 8 it uses:

  CUES_DIR/slide-08-A.png

For uncued/base narration it uses the original clean slide PNG.

Legacy per-slide audio named narr_01.mp3, narr_02.mp3, ... is also supported
when no manifest.json exists.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def ffprobe_dur(path: str) -> float:
    return float(
        subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path]
        ).decode().strip()
    )


def slide_path(slides_dir: str, slide_no: int) -> Optional[str]:
    for name in (f"slide-{slide_no:02d}.png", f"slide-{slide_no}.png"):
        p = os.path.join(slides_dir, name)
        if os.path.exists(p):
            return p
    return None


def cue_image(slides_dir: str, cues_dir: Optional[str], slide: int, cue: Optional[str]) -> str:
    clean = slide_path(slides_dir, slide)
    if not clean:
        sys.exit(f"slide {slide}: clean slide PNG not found in {slides_dir}")
    if not cue:
        return clean
    if not cues_dir:
        sys.exit(f"slide {slide} cue [{cue}]: --cues-dir is required")
    p = os.path.join(cues_dir, f"slide-{slide:02d}-{cue}.png")
    if not os.path.exists(p):
        sys.exit(f"slide {slide} cue [{cue}]: annotated PNG not found: {p}")
    return p


def load_manifest(audio_dir: str, manifest_path: Optional[str]) -> Optional[List[Dict[str, object]]]:
    p = manifest_path or os.path.join(audio_dir, "manifest.json")
    if not os.path.exists(p):
        return None
    data = json.loads(Path(p).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        sys.exit("manifest must be a JSON list")
    return data


def cue_segments(
    slides_dir: str,
    audio_dir: str,
    cues_dir: Optional[str],
    manifest: List[Dict[str, object]],
    pad: float,
    cue_pad: float,
    pad_still: float,
) -> List[Dict[str, object]]:
    slides = sorted(glob.glob(os.path.join(slides_dir, "slide-*.png")))
    if not slides:
        sys.exit(f"no slide-*.png in {slides_dir}")
    slide_count = len(slides)

    by_slide: Dict[int, List[Dict[str, object]]] = {}
    for row in manifest:
        slide = int(row["slide"])
        by_slide.setdefault(slide, []).append(row)

    out: List[Dict[str, object]] = []
    for slide in range(1, slide_count + 1):
        rows = sorted(by_slide.get(slide, []), key=lambda r: int(r.get("order", 0)))
        if not rows:
            clean = slide_path(slides_dir, slide)
            if not clean:
                sys.exit(f"slide {slide}: clean slide PNG not found")
            out.append({"slide": slide, "cue": None, "image": clean,
                        "audio": None, "duration": pad_still})
            continue

        for idx, row in enumerate(rows):
            cue = row.get("cue")
            cue_s = str(cue) if cue is not None else None
            audio_name = str(row.get("audio", ""))
            audio = os.path.join(audio_dir, audio_name)
            if not os.path.exists(audio):
                sys.exit(f"slide {slide}: audio not found: {audio}")
            measured = ffprobe_dur(audio)
            extra = pad if idx == len(rows) - 1 else cue_pad
            out.append(
                {
                    "slide": slide,
                    "cue": cue_s,
                    "image": cue_image(slides_dir, cues_dir, slide, cue_s),
                    "audio": audio,
                    "duration": measured + extra,
                }
            )
    return out


def legacy_segments(
    slides_dir: str,
    audio_dir: str,
    pad: float,
    pad_still: float,
) -> List[Dict[str, object]]:
    slides = sorted(glob.glob(os.path.join(slides_dir, "slide-*.png")))
    if not slides:
        sys.exit(f"no slide-*.png in {slides_dir}")
    out: List[Dict[str, object]] = []
    for i, png in enumerate(slides, 1):
        mp3 = os.path.join(audio_dir, f"narr_{i:02d}.mp3")
        if os.path.exists(mp3):
            dur = ffprobe_dur(mp3) + pad
            audio = mp3
        else:
            dur = pad_still
            audio = None
        out.append({"slide": i, "cue": None, "image": png,
                    "audio": audio, "duration": dur})
    return out


def build_ffmpeg(segments: List[Dict[str, object]], a: argparse.Namespace) -> None:
    args = ["ffmpeg", "-y", "-v", "error"]
    fc_parts: List[str] = []
    concat_parts: List[str] = []

    for idx, seg in enumerate(segments, 1):
        image = str(seg["image"])
        audio = seg.get("audio")
        dur = float(seg["duration"])
        vi, ai = (idx - 1) * 2, (idx - 1) * 2 + 1

        args += ["-loop", "1", "-framerate", str(a.fps), "-i", image]
        if audio:
            args += ["-i", str(audio)]
            # Pad enough silence to cover the image duration, then trim exactly.
            fc_parts.append(
                f"[{ai}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
                f"apad=pad_dur={max(1.0, a.pad + a.cue_pad + 1.0):.3f},"
                f"atrim=duration={dur:.3f},asetpts=PTS-STARTPTS[a{idx}];"
            )
        else:
            args += ["-f", "lavfi", "-t", f"{dur:.3f}",
                     "-i", "anullsrc=r=48000:cl=mono"]
            fc_parts.append(
                f"[{ai}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
                f"atrim=duration={dur:.3f},asetpts=PTS-STARTPTS[a{idx}];"
            )

        fc_parts.append(
            f"[{vi}:v]scale={a.width}:{a.height}:force_original_aspect_ratio=decrease,"
            f"pad={a.width}:{a.height}:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"fps={a.fps},format=yuv420p,trim=duration={dur:.3f},"
            f"setpts=PTS-STARTPTS[v{idx}];"
        )
        concat_parts.append(f"[v{idx}][a{idx}]")

    fc_parts.append(
        "".join(concat_parts)
        + f"concat=n={len(segments)}:v=1:a=1[v][a]"
    )
    args += [
        "-filter_complex", "".join(fc_parts),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf),
        "-r", str(a.fps),
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", a.out,
    ]
    subprocess.run(args, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("slides_dir")
    ap.add_argument("audio_dir")
    ap.add_argument("out")
    ap.add_argument("--cues-dir", help="directory containing slide-XX-A.png cue images")
    ap.add_argument("--manifest", help="cue manifest JSON; default AUDIO_DIR/manifest.json")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="ultrafast")
    ap.add_argument("--pad", type=float, default=1.0,
                    help="silence/still time after the last narration cue on each slide")
    ap.add_argument("--cue-pad", type=float, default=0.10,
                    help="small silence/still time between cue blocks on the same slide")
    ap.add_argument("--pad-still", type=float, default=4.0,
                    help="duration for slides without narration")
    a = ap.parse_args()

    manifest = load_manifest(a.audio_dir, a.manifest)
    if manifest is not None:
        segments = cue_segments(
            a.slides_dir, a.audio_dir, a.cues_dir, manifest,
            a.pad, a.cue_pad, a.pad_still,
        )
        mode = "cue-aware"
    else:
        segments = legacy_segments(a.slides_dir, a.audio_dir, a.pad, a.pad_still)
        mode = "legacy-per-slide"

    if not segments:
        sys.exit("no video segments to assemble")
    print(f"MODE={mode} SEGMENTS={len(segments)}")
    build_ffmpeg(segments, a)
    print(f"VIDEO={a.out} DURATION={ffprobe_dur(a.out):.1f}")


if __name__ == "__main__":
    main()
