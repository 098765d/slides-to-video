---
name: slides-to-video
description: >
  Turn a PPTX or PDF slide deck into a narrated HD video with visually grounded
  narration and optional arrow cues. Pipeline: rasterize slides → inspect visual
  structure → create visual anchor notes → draft cue-aware narration → user review
  gate → synthesize TTS per cue block → generate annotated slide PNGs → assemble
  one flicker-free H.264/AAC MP4. Use for narrated walkthroughs, user guides,
  training videos, lectures, reports, onboarding, product explanation, or any
  request to convert slides into video.
---

# Slides → Narrated HD Video with Visual Cues

The goal is not to read slide text aloud.

The goal is to sound like a competent presenter who understands the deck, uses
its visual evidence, and directs attention to the correct visual region when that
improves comprehension.

The cue system is intentionally simple and general:

```text
visual anchor note → narration cue [A]/[B]/[C] → arrow-annotated PNG
```

It does not depend on PowerPoint animations, mouse tracking, OCR, or word-level
speech alignment.

Working directory for each run:

`/mnt/agents/output/video_build_<deckname>/` (call it `$BUILD`).

Recommended structure:

```text
$BUILD/
├── slides/
│   └── slide-01.png ...
├── visual_notes.yaml
├── narration_script.md
├── cues/
│   └── slide-08-A.png ...
├── audio/
│   ├── slide-08-A-01.mp3 ...
│   └── manifest.json
└── <Deck Name> — Video.mp4
```

---

## What good narration means

A slide deck is visual communication, not a text document.

Depending on the slide, good narration may:

- guide attention to a chart, table, diagram, screenshot, button, or metric;
- interpret a pattern rather than recite labels;
- explain why a number matters;
- show the viewer where to click or what to inspect;
- synthesize several bullets into one idea;
- compare two visual regions;
- connect the current slide to the surrounding story;
- or say very little when the slide is only a title/divider/reference page.

These are presentation possibilities, not quotas.

A useful test:

> If a knowledgeable human presenter were recording this slide, what would they
> naturally say while the audience is looking at it, and where would they point?

---

## Hard rules

1. **Human review gate.** After the narration and visual notes are prepared, tell
   the user where they are and ask them to review/edit. Do not run TTS until the
   user approves or explicitly says to continue.
2. **Never persist API keys.** Runtime keys may be passed as CLI args or
   environment variables only. Never write keys into files, scripts, logs, or
   narration text; never echo them back in full.
3. **Single-pass final assembly.** The complete video must be encoded in one
   ffmpeg filtergraph. Do not encode each cue/slide as a separate MP4 and then
   concatenate those MP4s.
4. **HD output.** Default final output is 1920×1080. Never go below 1280×720
   unless the user explicitly requests it.
5. **Visual claims must be grounded.** Any narration that explicitly refers to a
   visible object or screen position must be supported by the rendered slide and,
   when a pointer is used, by a matching visual anchor.
6. **Default TTS is external and decoupled from the host LLM.** If the user has
   not explicitly configured a custom TTS provider, use `edge-tts` directly. Do
   not probe the host model registry for a speech-capable LLM, and do not require
   the reasoning model itself to output audio.
7. **Do not overload vision inspection.** Before inspecting a full deck, test one
   representative slide with an image-capable model. For medium/large decks, use
   lower-resolution vision previews and small batches rather than sending all
   full-resolution slide images to one request/subagent. Never retry a multimodal
   failure indefinitely.

---

# Stage 0 — Parse the request

Determine from the user's request and attachments:

- `DECK`: `.pptx` or `.pdf` input path;
- `LANG`: narration language;
- `SCENARIO`: user guide, lecture, professional training, report, onboarding,
  marketing, policy briefing, etc.;
- target audience;
- requested total duration or pacing, if stated;
- whether visual arrows/pointers are wanted;
- TTS provider and voice.

Default TTS provider: `edge-tts`.

### TTS backend selection

Use an explicit backend decision before any speech-related capability check:

1. If the user explicitly provides a custom OpenAI-compatible TTS configuration,
   use that provider and require its base URL, model, voice, and runtime API key.
2. Otherwise, use `edge-tts` directly.
3. Do **not** query the host LLM/model registry for `speech` capability when the
   selected backend is `edge-tts`. The video skill does not require the reasoning
   model itself to support audio output.

### Suggested edge-tts voices

| Scenario | Chinese | English |
|---|---|---|
| professional training / product explanation | zh-CN-YunxiNeural | en-US-AndrewNeural |
| warm onboarding / customer-facing | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| authoritative report / policy briefing | zh-CN-YunjianNeural | en-US-GuyNeural |
| lively marketing | zh-CN-XiaoyiNeural | en-US-AriaNeural |

List others with:

```bash
edge-tts --list-voices
```

For a custom OpenAI-compatible provider, use the user's model/voice if supplied.

---

# Stage 1 — Rasterize the deck

```bash
python3 scripts/slides_to_png.py DECK $BUILD/slides --width 1920
```

This outputs:

`slide-01.png`, `slide-02.png`, ...

For slides containing dense tables, small screenshots, code, or tiny labels,
rasterize at 2560 or 3840 px width; the final assembly can downscale later.

```bash
python3 scripts/slides_to_png.py DECK $BUILD/slides --width 2560
```

## Rendered slides are reasoning input

Do not treat PNGs only as final video frames.

Inspect them to understand:

- visual hierarchy;
- layout;
- highlighted regions;
- chart/table structure;
- screenshot controls;
- diagrams and arrows;
- comparisons;
- repeated visual motifs;
- and what the audience is likely to look at first.

Extracted slide text may help, but it is not a substitute for looking at the
rendered slide.

For long decks, inspect title/divider slides quickly and spend more attention on
visually dense or consequential slides.

---

# Stage 1A — Prepare and batch visual inspection

The high-resolution PNGs in `$BUILD/slides/` are the source for the final video.
Do not downscale or overwrite them merely to make vision inspection cheaper.

For visual reasoning, create temporary preview copies when the deck is medium,
large, or rendered above 1920 px. A width around **1280 px** is a good default.
Use the original high-resolution slide only when a preview is insufficient for a
dense table, spreadsheet, code sample, or small UI text.

## Vision capability smoke test

Before delegating the whole deck, inspect **one representative slide** with an
image-capable endpoint.

- If the single-slide test succeeds, continue with batched visual inspection.
- If the runtime reports that no image-capable endpoint exists, do not keep
  retrying. Switch to the non-vision fallback below.
- If one slide succeeds but a larger request fails, treat it as a likely scale,
  payload, rate-limit, or provider issue rather than assuming vision is
  unavailable.

Do not infer image capability from a model name alone.

## Default batching

Do not send an entire medium or large deck of full-resolution images to one
vision request or one subagent.

Default: **1–4 slides per batch**, processed sequentially unless the runtime is
known to handle concurrent multimodal requests reliably.

For example, a 19-slide deck should normally be inspected as:

- slides 1–4;
- slides 5–8;
- slides 9–12;
- slides 13–16;
- slides 17–19.

Adaptive retry policy:

1. smoke-test one slide;
2. use ~1280 px previews with batch size 4;
3. if a batch fails, retry once with batch size 2;
4. if it still fails, use ~960 px previews and inspect one slide at a time;
5. if single-slide inspection also fails, stop vision retries and use the
   non-vision fallback.

Never loop indefinitely on multimodal API failures.

## Non-vision fallback

If no usable image-capable endpoint is available:

- continue with extracted slide text and document/PPT structure;
- do not invent visual positions, arrows, or spatial claims such as “on the
  right” unless the position is independently known;
- omit unreliable visual anchors and use the clean slide image for those parts;
- still generate the narrated video;
- tell the user that visual grounding was limited for that run.

Normalized anchor coordinates remain valid across preview and final render
resolutions, so visual notes inferred from a preview can be applied to the
high-resolution source slide.

---

# Stage 1B — Create visual anchor notes

When arrows/pointers would help, create:

`$BUILD/visual_notes.yaml`

The purpose is to record **where the important visual targets are** before the
narration is written.

Typical anchor counts:

- title/divider: 0;
- normal content slide: 1–3;
- unusually complex instructional slide: up to 5.

Do not annotate decorative elements.

## Format

```yaml
slides:
  - slide: 8
    title: Model evaluation
    visuals:
      - id: A
        location: left
        element: confusion matrix
        target: [0.27, 0.53]

      - id: B
        location: middle-right
        element: missed detections card
        target: [0.62, 0.66]

      - id: C
        location: lower-right
        element: false alarms card
        target: [0.78, 0.66]
```

Each anchor must contain:

1. `id` — uppercase A–Z;
2. `location` — human-readable location;
3. `element` — semantic description of the visual object;
4. `target` — normalized `[x, y]` point from 0 to 1.

Example:

`target: [0.75, 0.40]`

means approximately 75% from the left and 40% from the top.

Optional:

```yaml
from: [0.83, 0.42]
```

Use `from` only when the automatic arrow origin would cover important content.

Location alone is insufficient.

Weak:

```yaml
- id: A
  location: top-right
```

Better:

```yaml
- id: A
  location: top-right
  element: accuracy card
  target: [0.82, 0.28]
```

---

# Stage 2 — Draft cue-aware narration → USER GATE

Follow `references/script-guide.md`.

First understand the deck-level story:

- What should the audience learn, decide, or do?
- Which slides are central versus transitional?
- Where should explanation be deeper?
- Which terminology must remain consistent?
- Is this a lecture, user guide, report, sales story, or another format?

Then write slide by slide.

## Narration Quality Contract

The narration must be more than a slide summary. For each substantive slide,
identify:

1. **Audience question** — what should the viewer understand or do here?
2. **Evidence** — which visible number, chart, table, control, or statement
   supports the explanation?
3. **Interpretation** — what does that evidence mean in this context?
4. **Next action / connection** — what should the viewer do next, or how does
   this lead to the next slide?

When useful, follow the pattern:

`orient → interpret → act/connect`

Additional rules:

- analytical slides should use concrete values when those values teach the
  audience how to read the visual;
- unfamiliar methods or metrics should receive a 1–3 sentence plain-language
  explanation, including why they are used;
- user-guide narration should prefer semantic labels over fragile Excel letters,
  row numbers, or coordinates;
- explicitly distinguish concepts that could otherwise appear contradictory,
  such as an outcome definition versus a model-derived classification cutoff;
- preserve exact department names, deadlines, and workflow details from the
  source material;
- central slides should normally add at least one useful interpretation or
  operational insight beyond the visible text, while divider/reference slides
  may remain brief;
- do not add unsupported background claims. If the user provides extra project
  rationale not shown on the slide, use it only when requested and keep source
  discipline clear.


## Script format contract

```markdown
# <Deck title> — Voiceover Script

## Slide 8 — Model evaluation
**[~30s]**

**Visuals:**
- [A] left — confusion matrix
- [B] middle-right — missed detections card

**Say:**
[A] The confusion matrix shows how the model performed on the historical cohort.

[B] The value I would pay particular attention to is missed detections. Here,
that value is zero.

**Pronounce:** <optional pronunciation guidance>
```

Rules:

- slide numbers should be contiguous from 1;
- `[A]`, `[B]`, etc. inside `**Say:**` are visual control markers and are not
  spoken;
- the cue remains active until the next visual cue marker;
- text before the first visual cue is uncued/base narration and uses the clean
  slide;
- `[pause]`, `[breathe]`, etc. are delivery notes and are also not spoken;
- `**Visuals:**` and `**Pronounce:**` are reviewer metadata;
- do not force a cue into every sentence or every slide.

## Visual Reference Contract

For explicit references to a visible object, use:

```text
spoken sentence
    ↕
visual cue id
    ↕
visual_notes.yaml anchor
    ↕
actual rendered-slide evidence
```

If narration says:

> The card on the right shows five detections.

then the rendered slide and `visual_notes.yaml` must support that exact card and
location.

If a visual location cannot be established confidently, rewrite the narration
without the spatial claim or omit the claim.

Never invent labels, coordinates, positions, controls, table entries, chart
trends, or values.

## Let the slide choose the speaking style

Possible approaches:

- concept: synthesize, then clarify what matters;
- chart: point to the relevant pattern and explain its meaning;
- table: explain how to read it, then focus only on useful entries;
- software task: orient the viewer to controls and walk through the action;
- process diagram: follow the visual sequence;
- comparison: make the contrast explicit;
- dashboard: group metrics and identify the important value;
- appendix/reference: briefly explain its role or skip detail.

## Be selective

A presenter may intentionally ignore:

- decorative elements;
- repeated footer text;
- every table row;
- every bullet;
- every metric card;
- irrelevant UI controls;
- appendix detail not needed for the current audience.

## Pacing

Spend less time on title pages, dividers, repeated context, simple navigation,
and appendices.

Spend more time on unfamiliar concepts, analytical figures, dense tables,
multi-step instructions, and consequential interpretation.

Approximate rates:

- English: 2.0–2.3 words/sec;
- Chinese: 3.5–4.5 chars/sec.

## Editorial check

Before saving:

- read the complete narration as one continuous presentation;
- confirm visual references match actual anchors;
- confirm important figures are explained rather than merely read;
- remove repetitive presentation phrases;
- check the estimated total duration.

Save:

`$BUILD/narration_script.md`

---

# Stage 2B — Generate/validate arrow cue PNGs

Before TTS, validate script cue markers against the visual notes and render the
annotated cue images:

```bash
python3 scripts/annotate_slides.py \
  $BUILD/slides \
  $BUILD/visual_notes.yaml \
  $BUILD/cues \
  --script $BUILD/narration_script.md
```

Outputs examples:

```text
slide-08-A.png
slide-08-B.png
slide-12-C.png
```

The default annotation style is one high-contrast arrow with a white halo.

Use a single consistent pointer style across the deck. The goal is simply:

> Look here while this point is being explained.

Do not simulate mouse movement or add unnecessary decorative animations.

If the arrow placement is poor, adjust the anchor's optional `from` coordinate
rather than changing the narration logic.

---

# Stage 2C — USER REVIEW GATE

STOP before any TTS call.

Tell the user where to find:

- `$BUILD/narration_script.md`;
- `$BUILD/visual_notes.yaml`;
- `$BUILD/cues/` preview images.

Ask the user to review/edit the script and, when useful, spot-check the cue PNGs.

Only proceed when the user explicitly approves or says to continue.

If the user edits the script or visual notes, re-read/re-render the current files.
Never use a cached earlier version.

---

# Stage 3 — TTS per cue block

Install dependencies if needed:

```bash
pip install -r requirements.txt
```

Default free provider:

```bash
python3 scripts/tts_narration.py \
  $BUILD/narration_script.md \
  $BUILD/audio \
  --provider edge \
  --voice en-US-AndrewNeural \
  --rate +0%
```

Chinese example:

```bash
python3 scripts/tts_narration.py \
  $BUILD/narration_script.md \
  $BUILD/audio \
  --provider edge \
  --voice zh-CN-YunxiNeural \
  --rate +0%
```

Custom OpenAI-compatible TTS:

```bash
TTS_API_KEY='...' python3 scripts/tts_narration.py \
  $BUILD/narration_script.md \
  $BUILD/audio \
  --provider openai \
  --base-url <base_url> \
  --model <model> \
  --voice <voice>
```

Outputs examples:

```text
audio/
├── slide-08-A-01.mp3
├── slide-08-B-01.mp3
├── slide-09-base-01.mp3
└── manifest.json
```

`manifest.json` is the timing source for assembly. It records the measured TTS
duration for every cue block.

Retry transient failures once.

---

# Stage 4 — Assemble cue images + cue audio

```bash
python3 scripts/assemble_video.py \
  $BUILD/slides \
  $BUILD/audio \
  "$BUILD/<Deck Name> — Video.mp4" \
  --cues-dir $BUILD/cues \
  --width 1920 \
  --height 1080 \
  --fps 15 \
  --crf 17 \
  --pad 1.0 \
  --cue-pad 0.10
```

Cue-level timing is:

```text
annotated cue image duration = measured cue TTS duration + cue pad
```

The final cue on a slide receives the normal slide breathing pad.

Uncued/base narration uses the original clean slide PNG.

Slides with no narration remain as clean still images for `--pad-still` seconds.

The entire presentation must still be assembled in one ffmpeg filtergraph and
encoded once.

For long decks, background execution may be necessary:

```bash
nohup python3 scripts/assemble_video.py ... > $BUILD/encode.log 2>&1 &
```

---

# Stage 5 — Verify and deliver

Basic checks:

```bash
ffprobe -v error \
  -show_entries format=duration \
  -of csv=p=0 OUT.mp4

ffprobe -v error \
  -select_streams v \
  -show_entries stream=width,height,nb_frames \
  -of csv=p=0 OUT.mp4
```

Visual/narration QA:

1. every script cue marker has a matching anchor;
2. every used anchor has a valid normalized target;
3. every used cue has an annotated PNG;
4. every narration segment has corresponding audio;
5. arrows point to the element actually being discussed;
6. arrows do not cover important text;
7. spatial narration matches visible layout;
8. uncued narration uses the clean slide;
9. slide/cue transitions have no black frames or flicker.

For visually important slides, inspect at least one extracted video frame per cue.

Then deliver:

- MP4 path;
- total duration;
- narration script path;
- optionally the visual notes path if the user wants to reuse/edit cues.

---

# Failure quick table

| Symptom | Fix |
|---|---|
| edge-tts network/403 failure | retry once; otherwise use another TTS provider |
| custom API 401 | key wrong/expired; ask again, never store it |
| script uses `[B]` but no B anchor exists | fix `visual_notes.yaml` or remove/rewrite the cue |
| arrow points to wrong place | correct `target`; use optional `from` if needed |
| arrow covers slide text | change `from`, or move target slightly adjacent to the element |
| narration sounds like slide reading | inspect rendered slide again and rewrite around meaning/evidence/action |
| narration has false “left/right” language | enforce the Visual Reference Contract |
| video flickers between cues/slides | ensure one final ffmpeg filtergraph; do not segment-concat MP4 files |
| slide text unreadable | rerender at width 2560/3840; keep final CRF ≤ 18 |
| long encode exceeds timeout | background the assembly and poll its log |

---

# Repository files

```text
slides-to-video/
├── SKILL.md
├── README.md
├── requirements.txt
├── scripts/
│   ├── slides_to_png.py
│   ├── annotate_slides.py
│   ├── tts_narration.py
│   └── assemble_video.py
├── references/
│   ├── script-guide.md
│   └── architecture.md
└── examples/
    ├── visual_notes.example.yaml
    └── narration_script.example.md
```

- `slides_to_png.py` — PPTX/PDF → high-resolution slide PNGs;
- `annotate_slides.py` — visual anchors → arrow cue PNGs;
- `tts_narration.py` — cue-aware script → cue-level MP3s + manifest;
- `assemble_video.py` — clean/cue PNGs + audio manifest → single-pass MP4;
- `script-guide.md` — narration and visual-grounding guidance;
- `architecture.md` — rationale and component/data-flow documentation.
