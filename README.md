# slides-to-video

Turn any PPTX or PDF slide deck into a narrated 1080p video — with
**visually grounded narration**, **selective visual cues** (red laser dot or red
rectangle), **a human review gate before speech**, and **single-pass ffmpeg
assembly**.

The narration does not read slides aloud. It sounds like a presenter who
understands the deck, uses its visual evidence, and points at the right region
when that helps comprehension.

---

## Install

Open **MiMoCode** and just type:

> install the `slides-to-video` skill from the GitHub repo:
> `https://github.com/<your-username>/slides-to-video`

Replace the URL with your repo address. That's the whole install — no config
file to edit. (The skill itself needs a few system tools to run; see
[Requirements](#requirements).)

---

## What it does

<p align="center">
  <img src="assets/pipeline.png" alt="Pipeline: PPTX/PDF → slide PNGs → visual anchors → cue-aware narration → cue PNGs + per-cue TTS → single-pass ffmpeg → 1080p MP4" width="100%">
</p>

No PowerPoint animations, no GUI automation, no mouse tracking, no OCR, and no
word-level speech timing.

Each run also builds a deck-level **story spine** (hook → context → method →
proof → insight → action) and tags every slide with a role, so the narration
advances an argument instead of paraphrasing slides.

---

## How it works

| # | Step | Produces | Script |
|---|---|---|---|
| 1 | Rasterize the deck | `slides/slide-01..N.png` | `slides_to_png.py` |
| 2 | Inspect slides + record visual anchors | `visual_notes.yaml` | — |
| 3 | Write cue-aware narration | `narration_script.md` | — |
| 4 | Render cue PNGs (one frame per cue) | `cues/slide-XX-A.png` | `annotate_slides.py` |
| 5 | **User review gate** — approve, or edit and loop back | approval | — |
| 6 | Synthesize per-cue audio | `audio/*.mp3` + `manifest.json` | `tts_narration.py` |
| 7 | Assemble one video | `<Deck Name> — Video.mp4` | `assemble_video.py` |
| 8 | Verify + deliver | duration, resolution, QA | `ffprobe` |

The pipeline is linear, but the **human sits in the loop**: after the cue
previews are rendered (step 4) and before any speech is synthesized (step 6),
you review the script, the anchors, and the annotated frames.

---

## Core principles

1. **The rendered slide is the ground truth.** Narration is written against the
   slide image, not extracted text. If there is no vision, spatial claims are
   dropped rather than invented.

2. **One anchor = one cue = one annotated frame = one audio segment.** These four
   are deterministically bound, so nothing needs word-level alignment — each cue
   frame is shown only while its cue audio plays:

<p align="center">
  <img src="assets/cue-timeline.png" alt="Cue binding on the timeline: a spoken cue links its anchor, annotated frame, and audio clip; frame and audio share the same block duration" width="100%">
</p>

3. **Cue style follows target shape.** A *point* (button, data point, label,
   diagram node) is a red laser dot; an *area* (table column, chart, key-value
   card, whole figure) is a 2–3 px red rectangle.

4. **Audio is the master clock.** Each frame's hold time equals its measured TTS
   duration plus a small cue pad.

5. **Encode once.** All frames and audio go through one ffmpeg filtergraph, which
   avoids page-turn flicker and timestamp seams.

6. **Human review before any TTS spend.** Script, anchors, and cue previews are
   reviewed first; TTS defaults to the free `edge-tts` provider.

---

## Visual cue styles

<p align="center">
  <img src="assets/cue-styles.png" alt="Two cue styles: a clean slide, a red laser dot on a point, and a red rectangle around an area" width="100%">
</p>

| Target type | Example | Anchor fields | Drawn as |
|---|---|---|---|
| Point | button, data point, label, diagram node | `target: [x, y]` | red laser dot |
| Area | table column/rows, chart, key card, figure | `shape: rectangle` + `box: [x, y, w, h]` | red rectangle, 2–3 px stroke |

Coordinates are normalized from 0 to 1 (`x, y` = top-left corner of the box,
`w, h` = normalized width/height).

```yaml
slides:
  - slide: 8
    title: Model evaluation
    visuals:
      - id: A
        location: left
        element: confusion matrix (whole figure)
        shape: rectangle
        box: [0.12, 0.30, 0.40, 0.42]

      - id: B
        location: middle-right
        element: missed detections card
        target: [0.62, 0.66]
```

---

## Quick start

> On Windows use `python` instead of `python3`.

```bash
# 1. rasterize (dense slides: use --width 2560)
python3 scripts/slides_to_png.py deck.pptx build/slides --width 1920
```

Create `build/visual_notes.yaml` (see above) and `build/narration_script.md`:

```markdown
## Slide 2 — Results
**Say:**
[A] The chart on the left shows the main pattern in the result.

[B] The summary card on the upper right gives the number to remember.
```

```bash
# 2. render cue PNGs (also validates cue/anchors)
python3 scripts/annotate_slides.py build/slides build/visual_notes.yaml build/cues \
  --script build/narration_script.md

# 3. STOP — review narration_script.md, visual_notes.yaml, build/cues/

# 4. synthesize audio (edge-tts default; voice auto-detected)
python3 scripts/tts_narration.py build/narration_script.md build/audio

# 5. assemble one video
python3 scripts/assemble_video.py build/slides build/audio output.mp4 \
  --cues-dir build/cues
```

`assemble_video.py` reads `build/audio/manifest.json` automatically.

---

## Repository layout

```text
slides-to-video/
├── SKILL.md                      the agent-facing skill (workflow + hard rules)
├── README.md                     this file
├── requirements.txt              Python dependencies
├── assets/
│   ├── pipeline.png              pipeline overview
│   ├── cue-timeline.png          cue binding on the timeline
│   └── cue-styles.png            laser dot vs red rectangle
├── scripts/
│   ├── slides_to_png.py          PPTX/PDF → high-res slide PNGs (Windows: PowerPoint COM; Linux: LibreOffice+poppler)
│   ├── win_pptx_to_png.ps1       Windows PPTX → PNG via PowerPoint COM
│   ├── script_parser.py          shared narration-script parser (annotate + TTS)
│   ├── annotate_slides.py        anchors → cue PNGs (laser dot / red rectangle)
│   ├── tts_narration.py          cue script → per-cue MP3s + manifest.json
│   └── assemble_video.py         clean/cue PNGs + manifest → single-pass MP4
├── references/
│   ├── script-guide.md           narration + cue-style guidance
│   └── architecture.md           rationale, data model, principles
└── examples/
    ├── visual_notes.example.yaml
    └── narration_script.example.md
```

| File | Role |
|---|---|
| `SKILL.md` | The skill instructions an agent follows end to end (stages + hard rules). |
| `scripts/slides_to_png.py` | Rasterizes the deck to PNGs — PPTX via PowerPoint COM on Windows, or LibreOffice + `pdftoppm` on Linux/macOS. |
| `scripts/script_parser.py` | Single source of truth for parsing the `## Slide N` / `**Say:**` narration format; shared so annotation and TTS never drift. |
| `scripts/annotate_slides.py` | Turns anchors into cue PNGs: `target` → laser dot, `shape: rectangle` + `box` → red rectangle. Also validates that every script cue has an anchor. |
| `scripts/tts_narration.py` | Splits the script into cue blocks, synthesizes one MP3 per block (`edge-tts` default), and writes `manifest.json` with measured durations. |
| `scripts/assemble_video.py` | Reads slides + cue PNGs + `manifest.json` and encodes one MP4 in a single ffmpeg filtergraph. |
| `references/script-guide.md` | Detailed guidance for writing grounded, presenter-quality narration and choosing cue styles. |
| `references/architecture.md` | Why the design looks this way: data model, principles, and rejected alternatives. |

---

## Requirements

**System tools**

`ffmpeg` and `ffprobe` are required everywhere (audio probing + final encoding).

- **Windows**: PPTX rendering uses installed Microsoft PowerPoint (COM) — no
  extra install. PDF rendering needs `poppler` (`pdftoppm`).
- **Linux / macOS**: install LibreOffice (PPTX → PDF) and poppler (`pdftoppm`).

```bash
# Linux / macOS
sudo apt update
sudo apt install -y ffmpeg poppler-utils libreoffice
```

**Python packages** (`pip install -r requirements.txt`)

| Package | Purpose |
|---|---|
| `edge-tts` | default free TTS (requires network to Microsoft's online service) |
| `Pillow` | drawing cue PNGs (laser dot / red rectangle) |
| `PyYAML` | reading `visual_notes.yaml` |

---

## TTS configuration

Three backends; the default is **edge-tts** (free, no API key).

**edge-tts (default)** — voice auto-detected if omitted (`zh-CN-YunxiNeural` for
Chinese, `en-US-AndrewNeural` otherwise):

```bash
python3 scripts/tts_narration.py build/narration_script.md build/audio
```

**MiMo TTS (native)** — borrow this instance's speech model via the capability
API; the only preset voice is `Chloe`:

```bash
mimo llm-server issue --capability speech --json   # prints base_url + a one-time token
TTS_API_KEY="<token>" python3 scripts/tts_narration.py build/narration_script.md build/audio \
  --provider openai --base-url <base_url> --model xiaomi/mimo-v2.5-tts --voice Chloe
```

**Custom OpenAI-compatible `/audio/speech`** — keep credentials in env vars,
never in files:

```bash
export TTS_API_KEY="..." TTS_BASE_URL="https://host/v1" TTS_MODEL="tts-model"
python3 scripts/tts_narration.py build/narration_script.md build/audio \
  --provider openai --voice default
```

---

## Troubleshooting

| Problem | Action |
|---|---|
| Slide text looks soft | render source slides at 2560/3840 px |
| Script cue has no anchor | fix `visual_notes.yaml` or remove the cue |
| Dot/rectangle in the wrong place | correct `target` / `box` |
| Dot/rectangle covers text | nudge the point, or shrink/relocate the box |
| Narration says "on the right" incorrectly | rewrite using only grounded anchors |
| Narration sounds like slide reading | reinspect the slide, explain meaning/action |
| `edge-tts` fails | retry, check network, or use a compatible provider |
| Custom TTS returns 401 | check runtime key; never save it in the repo |
| Video flickers | confirm single-pass `assemble_video.py` is used |
| Long encode times out | run assembly in background and poll the log |

---

## Security

Never commit API keys. Use runtime environment variables or CLI arguments only.
