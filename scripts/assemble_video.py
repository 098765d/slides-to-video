#!/usr/bin/env python3
"""Assemble slide PNGs + per-slide mp3 narration into one HD mp4.

Single-pass build: all slides and audio go through ONE ffmpeg filtergraph
(per-segment PTS reset -> concat -> one encode). This is deliberate: it
eliminates seam artifacts (black/green frames, timestamp jumps, "flicker
at page turns") that appear when separately encoded segments are joined
with stream copy. Do NOT switch to encode-segments-then-concat.

Usage:
  python3 assemble_video.py SLIDES_DIR AUDIO_DIR OUT.mp4 \
      [--width 1920] [--height 1080] [--fps 15] [--crf 17] [--pad 1.2]

Missing audio for slide N -> N seconds of silence (--pad-still, default 4s).
Prints:  VIDEO=<path> DURATION=<s>
"""
import argparse, glob, os, re, subprocess, sys

def ffprobe_dur(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path]).decode().strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slides_dir")
    ap.add_argument("audio_dir")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--pad", type=float, default=1.2,
                    help="seconds of still image after narration ends")
    ap.add_argument("--pad-still", type=float, default=4.0,
                    help="duration for slides without narration")
    a = ap.parse_args()

    slides = sorted(glob.glob(os.path.join(a.slides_dir, "slide-*.png")))
    if not slides:
        sys.exit(f"no slide-*.png in {a.slides_dir}")

    args = ["ffmpeg", "-y", "-v", "error"]
    fc, parts = "", []
    for i, png in enumerate(slides, 1):
        mp3 = os.path.join(a.audio_dir, f"narr_{i:02d}.mp3")
        dur = (ffprobe_dur(mp3) + a.pad) if os.path.exists(mp3) else a.pad_still
        vi, ai = (i - 1) * 2, (i - 1) * 2 + 1
        if os.path.exists(mp3):
            args += ["-loop", "1", "-framerate", str(a.fps), "-i", png, "-i", mp3]
            fc += (f"[{ai}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
                   f"apad=pad_dur={a.pad + 1},atrim=duration={dur:.3f},"
                   f"asetpts=PTS-STARTPTS[a{i}];")
        else:
            args += ["-loop", "1", "-framerate", str(a.fps), "-i", png,
                     "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
            fc += (f"[{ai}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
                   f"asetpts=PTS-STARTPTS[a{i}];")
        fc += (f"[{vi}:v]scale={a.width}:{a.height}:force_original_aspect_ratio=decrease,"
               f"pad={a.width}:{a.height}:(ow-iw)/2:(oh-ih)/2:color=white,"
               f"fps={a.fps},format=yuv420p,trim=duration={dur:.3f},"
               f"setpts=PTS-STARTPTS[v{i}];")
        parts.append(f"[v{i}][a{i}]")

    fc += "".join(parts) + f"concat=n={len(slides)}:v=1:a=1[v][a]"
    args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(a.crf),
             "-r", str(a.fps), "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
             "-ac", "2", "-movflags", "+faststart", a.out]
    subprocess.run(args, check=True)
    print(f"VIDEO={a.out} DURATION={ffprobe_dur(a.out):.1f}")

if __name__ == "__main__":
    main()
