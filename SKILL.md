---
name: slides-to-video
description: >
  Turn a PPTX or PDF slide deck into a narrated HD video with visually grounded
  narration and selective visual cues (red laser dot or red rectangle). Pipeline:
  rasterize slides → inspect + record visual anchors → draft cue-aware narration
  → user review gate → synthesize TTS per cue block (edge-tts by default) →
  generate annotated slide PNGs → assemble one flicker-free H.264/AAC MP4. Use
  for narrated walkthroughs, user guides, training videos, lectures, reports,
  onboarding, product explanation, or any request to convert slides into video.
---

# Slides → Narrated HD Video with Visual Cues

The goal is not to read slide text aloud. The goal is to sound like a competent
presenter who understands the deck, uses its visual evidence, and directs
attention to the correct visual region when that improves comprehension.

The cue system is intentionally simple and general:

```text
visual anchor note → narration cue [A]/[B]/[C] → annotated slide PNG
```

It does not depend on PowerPoint animations, mouse tracking, OCR, or word-level
speech alignment.

Working directory for each run: `$BUILD` (e.g. `video_build_<deckname>/`).

```text
$BUILD/
├── slides/              slide-01.png ...
├── visual_notes.yaml    anchors (laser dot / red rectangle) per slide
├── narration_script.md
├── cues/                slide-08-A.png ...
├── audio/               slide-08-A-01.mp3 ... + manifest.json
└── <Deck Name> — Video.mp4
```

---

## Hard rules

1. **Human review gate.** After narration + visual notes + cue previews are
   ready, stop and ask the user to review before any TTS call.
2. **Never persist API keys.** Runtime keys via CLI args or env vars only.
3. **Single-pass assembly.** Encode the whole video in one ffmpeg filtergraph.
4. **HD output.** 1920×1080 default; never below 1280×720 unless requested.
5. **Visual claims must be grounded.** Any narration referring to a visible
   object/position must match a rendered slide and, when cued, a visual anchor.
6. **Default TTS is edge-tts.** Do not probe the host model registry for speech
   capability. Custom providers only when the user explicitly configures one.

---

# Stage 0 — Parse the request

Determine: `DECK` (.pptx/.pdf), `LANG`, `SCENARIO`, audience, requested
duration, whether visual cues are wanted, and TTS voice.

TTS provider defaults to **edge-tts**. Pick a voice from the table (or list with
`edge-tts --list-voices`):

| Scenario | Chinese | English |
|---|---|---|
| professional training / product explanation | zh-CN-YunxiNeural | en-US-AndrewNeural |
| warm onboarding / customer-facing | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| authoritative report / policy briefing | zh-CN-YunjianNeural | en-US-GuyNeural |
| lively marketing | zh-CN-XiaoyiNeural | en-US-AriaNeural |

If the user explicitly configured a custom OpenAI-compatible TTS, use it (base
URL + model + voice + runtime key). Otherwise stay on edge-tts.

---

# Stage 1 — Rasterize the deck

```bash
python3 scripts/slides_to_png.py DECK $BUILD/slides --width 1920
```

For dense tables, small screenshots, code, or tiny labels, render at 2560 or
3840 px width; final assembly downscales.

Output: `slide-01.png`, `slide-02.png`, ...

---

# Stage 2 — Inspect slides and record visual anchors

The rendered PNGs are reasoning input: inspect them to understand layout,
hierarchy, charts, tables, screenshots, diagrams, comparisons, and what the
audience looks at first. Extracted text helps but is not a substitute.

Inspect in small batches using ~1280 px previews (do not overwrite the
full-resolution source PNGs). First test one representative slide with an
image-capable endpoint; if no vision is available, fall back to text/structure
only and skip spatial cues.

Record anchors in `$BUILD/visual_notes.yaml`. Typical counts: title/divider 0,
normal slide 1–3, complex instructional slide up to 5. Do not annotate
decoration.

## Anchor format

Two cue styles, chosen by target shape:

- **laser dot** (default) — a single point → `target: [x, y]`
- **red rectangle** — an area → `shape: rectangle` + `box: [x, y, w, h]`
  (top-left corner `x, y`, normalized width/height `w, h`; 2–3 px stroke)

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

Required fields: `id` (A–Z), `location` (human-readable), `element` (semantic
description), and exactly one of `target` or `box` (normalized 0–1).

Rule of thumb — **use a rectangle when highlighting an area** (table column or
rows, a whole chart/table, a key-value card, a figure to spotlight); **use a
laser dot when pointing at a point** (button, data point, label, diagram node).

---

# Stage 3 — Draft cue-aware narration

Before drafting, **read `references/script-guide.md`** and apply it. The
non-negotiable quality bar is:

- orient → interpret → act/connect — never recite the slide;
- say what a number/chart/table **means**, not just that it exists;
- add one useful insight per substantive slide, beyond the visible text;
- use concrete values to teach the audience how to read the visual;
- explain unfamiliar methods in 1–3 plain sentences (what / why / takeaway);
- preserve exact names, deadlines, and column/field labels;
- never invent numbers, labels, trends, positions, or conclusions;
- vary pacing: brief on title/dividers, longer on dense/analytical slides.

The full guidance (slide-type heuristics, examples, factual discipline) is in
`references/script-guide.md`.

## Step 0 — Story spine (deck-level logic chain)

Before writing per-slide text, write the deck's story spine in 5–7 lines and give
every slide a `**Role:**` so each one advances the chain instead of merely
describing its content:

```text
Hook → Context → Method → Proof → Insight → Action
```

Roles (one per slide): `hook`, `context`, `method`, `proof`, `insight`,
`action`, `transition`, `reference`, `divider`.

## Script format

```markdown
# <Deck title> — Voiceover Script

**Story spine:**
- Hook — ...
- Context — ...
- Method — ...
- Proof — ...
- Insight — ...
- Action — ...

## Slide 8 — Model evaluation
**Role:** proof
**[~30s]**

**Say:**
[A] The confusion matrix shows how the model performed on the historical cohort.

[B] The value to focus on is missed detections — here it is zero.
```

- `## Slide N` starts a slide block; `**Say:**` holds spoken text.
- `**Role:**` states the slide's job in the story spine; every slide has one.
- `[A]`, `[B]` are visual control markers, not spoken; a cue stays active until
  the next marker.
- Text before the first marker uses the clean slide (uncued/base narration).
- `[pause]`, `[breathe]` are delivery notes, also not spoken.
- `**Visuals:**` / `**Pronounce:**` are reviewer metadata, not TTS text.

Save: `$BUILD/narration_script.md`.

---

# Stage 4 — Render cue PNGs

```bash
python3 scripts/annotate_slides.py \
  $BUILD/slides \
  $BUILD/visual_notes.yaml \
  $BUILD/cues \
  --script $BUILD/narration_script.md
```

Outputs `slide-08-A.png`, etc. `target` anchors become a red laser dot with a
soft glow; `shape: rectangle` anchors become a clean red rectangle. Use one
consistent style per cue type across the deck. This command fails if the script
uses a cue with no matching anchor.

---

# Stage 5 — USER REVIEW GATE

STOP before any TTS. Tell the user where to find:

- `$BUILD/narration_script.md`
- `$BUILD/visual_notes.yaml`
- `$BUILD/cues/` preview images

Proceed only on explicit approval. If the user edits any file, re-read/re-render
it; never reuse a stale cached version.

---

# Stage 6 — Synthesize TTS per cue block

```bash
pip install -r requirements.txt
```

Default (edge-tts; voice auto-detected from script language if omitted):

```bash
python3 scripts/tts_narration.py $BUILD/narration_script.md $BUILD/audio
```

Or pin a voice explicitly:

```bash
python3 scripts/tts_narration.py $BUILD/narration_script.md $BUILD/audio \
  --voice zh-CN-YunxiNeural
```

Custom OpenAI-compatible TTS:

```bash
TTS_API_KEY='...' python3 scripts/tts_narration.py $BUILD/narration_script.md $BUILD/audio \
  --provider openai --base-url <url> --model <model> --voice <voice>
```

Outputs: `slide-08-A-01.mp3`, `slide-09-base-01.mp3`, `manifest.json`.
`manifest.json` records measured TTS duration for every cue block and is the
timing source for assembly. Retry transient failures once.

---

# Stage 7 — Assemble one video

```bash
python3 scripts/assemble_video.py \
  $BUILD/slides \
  $BUILD/audio \
  "$BUILD/<Deck Name> — Video.mp4" \
  --cues-dir $BUILD/cues \
  --width 1920 --height 1080 --fps 15 --crf 17 \
  --pad 1.0 --cue-pad 0.10
```

Cue-level timing: `annotated cue image duration = measured cue TTS duration + cue pad`.
Uncued/base narration uses the clean slide; slides without narration stay still
for `--pad-still` seconds. Everything is encoded in one ffmpeg filtergraph.

For long decks, background the encode and poll the log.

---

# Stage 8 — Verify and deliver

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 OUT.mp4
ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0 OUT.mp4
```

Check: every cue has a matching anchor + PNG; every segment has audio; dots and
rectangles point at the discussed element without covering important text;
uncued narration uses the clean slide; no black frames/flicker. Spot-check one
frame per cue on visually important slides.

Deliver: MP4 path, total duration, narration script path (and visual notes if the
user wants to reuse/edit cues).

---

# Failure quick table

| Symptom | Fix |
|---|---|
| edge-tts network/403 | retry once; otherwise switch provider |
| custom API 401 | key wrong/expired; ask again, never store it |
| script uses [B] but no anchor | fix visual_notes.yaml or remove the cue |
| dot/rectangle in the wrong place | correct `target` / `box` |
| dot/rectangle covers text | nudge the point, or shrink/relocate the box |
| narration = slide reading | reinspect the slide and rewrite around meaning/evidence |
| false "left/right" language | enforce the Visual Reference Contract |
| video flickers | ensure one final ffmpeg filtergraph |
| slide text unreadable | rerender at 2560/3840, keep CRF ≤ 18 |
| encode exceeds timeout | background it and poll the log |

---

# Repository files

```text
slides-to-video/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
│   ├── slides_to_png.py      PPTX/PDF → high-res slide PNGs
│   ├── win_pptx_to_png.ps1   Windows PPTX → PNG via PowerPoint COM
│   ├── script_parser.py      shared narration-script parser (annotate + TTS)
│   ├── annotate_slides.py    anchors → cue PNGs (laser dot / red rectangle)
│   ├── tts_narration.py      cue script → per-cue MP3s + manifest
│   └── assemble_video.py     clean/cue PNGs + manifest → single-pass MP4
├── references/
│   ├── script-guide.md       narration + cue-style guidance
│   └── architecture.md       rationale, data model, principles
└── examples/
    ├── visual_notes.example.yaml
    └── narration_script.example.md
```

- `slides_to_png.py` — PPTX/PDF → high-resolution slide PNGs (Windows: PowerPoint COM; Linux: LibreOffice + poppler);
- `win_pptx_to_png.ps1` — Windows PPTX → PNG via PowerPoint COM (called by `slides_to_png.py`);
- `script_parser.py` — single source of truth for the `## Slide N` / `**Say:**`
  format, shared by annotation and TTS;
- `annotate_slides.py` — visual anchors → cue PNGs (laser dot or red rectangle);
- `tts_narration.py` — cue-aware script → per-cue MP3s + `manifest.json`;
- `assemble_video.py` — clean/cue PNGs + audio manifest → single-pass MP4;
- `script-guide.md` — narration and cue-style guidance;
- `architecture.md` — rationale and component/data-flow documentation.
