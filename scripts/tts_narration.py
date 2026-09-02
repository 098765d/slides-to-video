#!/usr/bin/env python3
"""Turn a per-slide narration script into one mp3 per slide.

Script format (markdown):
  ## Slide N — <title>
  **Say:**
  <spoken text; [pause]/[slow down] cues are stripped automatically>

Usage:
  # default free provider (edge-tts, no API key)
  python3 tts_narration.py script.md OUTDIR --voice en-US-AndrewNeural

  # custom OpenAI-compatible TTS API (e.g. Mimo); never hard-code keys
  python3 tts_narration.py script.md OUTDIR --provider openai \
      --base-url https://api.example.com/v1 --api-key "$KEY" \
      --model mimo-tts --voice default

Prints one line per slide:  slide N -> FILE (X.Xs)
"""
import argparse, os, re, subprocess, sys, time, urllib.request, json

def parse_script(path):
    text = open(path, encoding="utf-8").read()
    blocks = re.split(r"\n## Slide ", "\n" + text)[1:]
    out = {}
    for b in blocks:
        n = int(re.match(r"(\d+)", b).group(1))
        m = re.search(r"\*\*Say:\*\*\s*\n(.*?)(?=\n\*\*[A-Z]|\n---|\n## |\Z)", b, re.S)
        if not m:
            sys.exit(f"Slide {n}: no '**Say:**' block found")
        t = re.sub(r"\[[^\]]*\]", "", m.group(1))          # strip [cues]
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            out[n] = t
    if not out:
        sys.exit("No narration found. Check the script format.")
    return dict(sorted(out.items()))

def synth_edge(text, voice, rate, out):
    subprocess.run(["edge-tts", "--voice", voice, "--rate", rate,
                    "--text", text, "--write-media", out],
                   check=True, capture_output=True)

def synth_openai(text, voice, rate, out, base_url, api_key, model):
    body = json.dumps({"model": model, "voice": voice, "input": text}).encode()
    req = urllib.request.Request(base_url.rstrip("/") + "/audio/speech",
                                 data=body,
                                 headers={"Authorization": f"Bearer {api_key}",
                                          "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        open(out, "wb").write(r.read())

def duration(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", path]).decode().strip())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("outdir")
    ap.add_argument("--provider", choices=["edge", "openai"], default="edge")
    ap.add_argument("--voice", required=True)
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--base-url", default=os.environ.get("TTS_BASE_URL"))
    ap.add_argument("--api-key", default=os.environ.get("TTS_API_KEY"))
    ap.add_argument("--model", default=os.environ.get("TTS_MODEL"))
    a = ap.parse_args()

    if a.provider == "openai" and not (a.base_url and a.api_key and a.model):
        sys.exit("provider=openai needs --base-url, --api-key, --model "
                 "(or TTS_BASE_URL / TTS_API_KEY / TTS_MODEL env vars)")

    os.makedirs(a.outdir, exist_ok=True)
    for n, text in parse_script(a.script).items():
        out = os.path.join(a.outdir, f"narr_{n:02d}.mp3")
        for attempt in (1, 2):
            try:
                if a.provider == "edge":
                    synth_edge(text, a.voice, a.rate, out)
                else:
                    synth_openai(text, a.voice, a.rate, out,
                                 a.base_url, a.api_key, a.model)
                break
            except Exception as e:
                if attempt == 2:
                    sys.exit(f"slide {n}: TTS failed twice: {e}")
                time.sleep(2)
        print(f"slide {n} -> {out} ({duration(out):.1f}s)")

if __name__ == "__main__":
    main()
