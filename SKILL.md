---
name: slides-to-video
description: >
  Turn a slide deck (PPTX or PDF) into a narrated HD video, end to end:
  rasterize slides → draft a presentation-quality voiceover script → let the user
  review/edit it → TTS per slide → assemble into one 1080p MP4 with zero page-turn
  flicker. Use when a user asks to convert slides/PPT/课件/幻灯片 into a video,
  视频讲解, narrated walkthrough, user-guide video, training video, lecture video,
  or "把这ppt变成视频". Default TTS is free edge-tts (scenario-matched voice);
  the user may instead provide an OpenAI-compatible TTS API.
---

# Slides → Narrated HD Video

Minimal pipeline, 5 stages. All scripts live in `scripts/` next to this file.

Working directory for every run:

`/mnt/agents/output/video_build_<deckname>/` (call it `$BUILD`).

## What “good narration” means

The goal is not to turn slide text into speech.

The goal is to sound like a competent presenter who understands the deck and
uses the slide as visual support. Depending on the slide, that may mean:

- guiding attention to a chart, table, diagram, screenshot, highlighted control,
  or comparison;
- interpreting the pattern instead of reading labels;
- explaining why a number matters;
- showing the viewer where to click or what to inspect;
- synthesising several bullets into one idea;
- linking the current slide to the previous or next one;
- or saying very little when the slide is only a divider or reference page.

These are presentation possibilities, **not quotas**.

Do not force every slide to mention a visible element, use a spatial phrase, or
follow the same narration pattern. Let the slide content, purpose, audience,
scenario, and surrounding narrative determine the best delivery.

A simple test:

> If a knowledgeable human presenter were recording this slide, what would they
> naturally say while the audience is looking at it?

That is the target.

## Hard rules (pipeline and safety)

1. **Script gate.** After Stage 2 you MUST tell the user where the script file is
   and ask them to review/edit it. Do NOT run TTS until they approve or explicitly
   say to continue.
2. **Never persist API keys.** A key pasted in the query is used only as a runtime
   CLI arg / env var (`--api-key` / `TTS_API_KEY`). Never write it into a file,
   script, log, or narration text. Never echo it back in full.
3. **Single-pass assembly.** `assemble_video.py` builds the whole video in one
   ffmpeg filtergraph pass. Do NOT replace it with encode-per-slide-then-concat.
4. **HD = 1920×1080 by default.** Never go below 1280×720.

---

## Stage 0 — Parse the request

From the user's query + attachments determine:

- `DECK`: path to `.pptx` or `.pdf`
- `LANG`: narration language
- `SCENARIO`: e.g. user guide, lecture, professional training, report,
  onboarding, marketing, policy briefing
- requested duration, pacing, or audience if stated
- TTS provider:
  - user pasted `api key` / `api_key=...` / `key=sk-...` → provider `openai`
  - otherwise → provider `edge`
- Voice: user-specified > scenario-matched > default male

### Voice table (edge-tts, free)

| Scenario | zh voice | en voice |
|---|---|---|
| default / professional training / product explanation | zh-CN-YunxiNeural | en-US-AndrewNeural |
| warm onboarding / customer-facing | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| authoritative report / policy briefing | zh-CN-YunjianNeural | en-US-GuyNeural |
| lively marketing | zh-CN-XiaoyiNeural | en-US-AriaNeural |

List more with `edge-tts --list-voices`.

For a custom provider, use the user's `voice` / `model` if given, otherwise the
provider default.

---

## Stage 1 — Rasterize slides

```bash
python3 scripts/slides_to_png.py DECK $BUILD/slides --width 1920
```

Prints `SLIDES=N`; outputs `slide-01.png …`.

Check that N is plausible and inspect rendered slides.

For text-dense decks, small tables, screenshots, or code, rasterize sharper with
`--width 2560` or `3840`. Assembly downscales later.

### Rendered slides are part of the reasoning input

Do not treat the rendered PNGs only as video frames.

Use them to understand how the slide communicates:
- visual hierarchy,
- layout,
- highlighted regions,
- chart/table structure,
- screenshot controls,
- diagrams and arrows,
- comparisons,
- repeated visual motifs,
- and what the audience is likely looking at.

Extracted slide text is useful, but it is not a substitute for looking at the
slide.

For a long deck, inspect efficiently: title/divider slides can be scanned
quickly, while dense or visually important slides deserve closer inspection.

---

## Stage 2 — Draft narration script → USER GATE

Write the script yourself (or use one writer subagent for very long decks)
following `references/script-guide.md`.

### Format contract

The TTS parser depends on `## Slide N` and `**Say:**`.

```markdown
# <Deck title> — Voiceover Script

约 X 分钟 · 共 N 段

## Slide 1 — <slide title>
**[~30s]**
**On screen:** <optional one-line visual note for the human reviewer>
**Say:**
<spoken text>

**Pronounce:** <optional pronunciation guidance>

## Slide 2 — ...
```

- Slide numbers must be contiguous from 1.
- `**Say:**` is the only field sent to TTS.
- `[pause]`, `[breathe]`, and similar bracket cues are stripped before TTS.
- `**On screen:**` and `**Pronounce:**` are reviewer aids, not spoken text.

Save to:

`$BUILD/narration_script.md`

### Stage 2A — Understand the presentation before writing sentences

First establish the deck-level story:

- What is the audience supposed to learn, decide, or do?
- Which slides are central and which are transitional?
- Where should explanation be deeper?
- Where should narration be brief?
- What terminology should remain consistent?
- Is the deck a lecture, user guide, report, sales story, or something else?

Then work slide by slide.

For each slide, form an internal understanding of:
- its purpose in the sequence;
- what the audience sees;
- what is already obvious without narration;
- which visual evidence or structure matters;
- what the presenter can add beyond the visible words;
- and how it connects to the surrounding slides.

Do not emit this internal planning unless it is useful in `**On screen:**`.

### Stage 2B — Let the slide choose the speaking style

Possible approaches include:

- **Explain a concept:** synthesise the idea, then clarify what matters.
- **Interpret a chart:** direct attention where useful, describe the relevant
  pattern, and explain its meaning.
- **Walk through a table:** explain how to read it, then focus only on entries
  that matter to the story.
- **Guide a software task:** orient the viewer to visible controls and walk
  through the action in a natural order.
- **Narrate a diagram/process:** follow the logic in a sequence the audience can
  track.
- **Compare alternatives:** make the contrast explicit.
- **Present dashboard metrics:** group related numbers and explain what should
  receive attention.
- **Transition:** connect sections with one or two sentences.
- **Reference/appendix:** briefly explain its purpose or skip detailed narration
  unless the user requested it.

These are flexible strategies. Do not mechanically map every slide to a template.

### Stage 2C — Use visual grounding when it improves comprehension

A real presenter often refers to the screen:

- "The highlighted button here is Download Programme Reports."
- "On the right, the confusion matrix shows the historical validation result."
- "The largest bar is Year 2 GPA."
- "If we look at the first row of the table…"
- "At the bottom of this page, the file log lists the two deliverables."
- "The left and right panels answer different questions."

Use such language naturally when it helps the audience follow along.

Do **not** insert spatial phrases just to prove that the slide was inspected.
Some slides are better explained without any explicit "left/right/top/bottom"
language.

Avoid repeating "as you can see". Vary phrasing as a human presenter would.

### Stage 2D — Narration should add value, not mirror the slide

Weak:

> Accuracy is 96 percent. Missed detections are zero. False alarms are four.

Stronger:

> The historical validation result is shown in the confusion matrix on the
> right. The number I would pay most attention to is missed detections, because
> those are at-risk students the model failed to identify. Here that value is
> zero. The trade-off is four false alarms.

Weak:

> Click Download Programme Reports. Click Details.

Stronger:

> From the Programme Team Console, open Download Programme Reports. On the next
> screen, find your programme under My Programme(s), then use the Details button
> at the end of its row to open the report page.

The stronger versions are not better merely because they are longer. They are
better because they help the audience use the visual information.

### Stage 2E — Be selective

Do not narrate everything simply because it is visible.

A presenter may intentionally ignore:
- decorative elements,
- repeated footer text,
- every value in a dense table,
- every bullet,
- every metric card,
- appendix detail,
- or UI controls that are irrelevant to the task.

Prioritise what serves the presentation's purpose.

### Stage 2F — Keep factual grounding strict

Every specific number, label, UI action, trend, table entry, or spatial claim in
the narration must be supported by the deck or source material.

Do not invent:
- values,
- labels,
- chart trends,
- interface controls,
- screen positions,
- causal explanations,
- or conclusions that are not supported.

If the slide is ambiguous or too small to read reliably, avoid false precision.

### Stage 2G — Keep presentation continuity

The script should sound like one person giving one presentation, not N
independent slide summaries.

Use transitions when they genuinely help:
- "Now that we know how the model performed…"
- "The next question is which students were flagged."
- "This brings us to the Excel file."
- "So far we have looked at the programme-level result."

Do not add a transition automatically just because the slide changed.

### Stage 2H — Pace by importance, not by slide count

If the user provides a time limit, treat it as a deck-level speaking budget.

Spend less time on:
- title pages,
- section dividers,
- repeated context,
- simple navigation,
- appendices.

Spend more time on:
- unfamiliar concepts,
- analytical figures,
- complicated tables,
- multi-step instructions,
- consequential interpretation.

Use approximate spoken rates:
- English: about 2.0–2.3 words/sec
- Chinese: about 3.5–4.5 chars/sec

Do not force every slide into the same duration range when the deck clearly does
not call for it.

### Stage 2I — TTS-friendly writing

Write for speech, not prose.

- Prefer natural sentence lengths.
- Keep acronyms and filenames pronounceable.
- Convert awkward symbols to spoken forms where appropriate.
- Use `[pause]` sparingly.
- Avoid long parenthetical constructions.
- Keep terminology consistent with the deck.
- Avoid obvious AI-writing habits and repetitive framing.

### Stage 2J — Editorial pass

Before saving, read the complete script as one continuous presentation.

Use judgment questions:

- Does this sound like a knowledgeable human presenter?
- Does the narration use visuals intelligently where they help?
- Does it avoid merely reading the slide?
- Are visually complex slides easier to understand after hearing the narration?
- Are some slides appropriately brief?
- Are important points given proportionate time?
- Do software instructions tell the viewer where to act when useful?
- Are transitions natural rather than formulaic?
- Is any wording becoming repetitive?
- Is every factual detail supported?
- Does the whole script fit the requested duration?

These questions guide editing. They are **not pass/fail quotas**.

### Stage 2K — Stop for review

Then STOP and tell the user:

> 讲稿已生成：`<path>`（共 N 段，预计 X 分钟）。请查看/直接修改该文件；
> 回复 "OK" 或 "继续" 我就开始配音合成视频。

Only proceed after approval.

If the user edits the file, re-read it. Never use a cached earlier version.

---

## Stage 3 — TTS per slide

```bash
# default free path
pip install edge-tts

python3 scripts/tts_narration.py \
    $BUILD/narration_script.md \
    $BUILD/audio \
    --provider edge \
    --voice zh-CN-YunxiNeural \
    --rate +0%
```

Custom OpenAI-compatible TTS:

```bash
TTS_API_KEY='sk-...' python3 scripts/tts_narration.py \
    $BUILD/narration_script.md \
    $BUILD/audio \
    --provider openai \
    --base-url <their_base_url> \
    --model <model> \
    --voice <voice>
```

Outputs `narr_01.mp3 …` and prints per-slide duration.

Retry transient failures once.

Missing audio is acceptable; assembly pads a still slide.

---

## Stage 4 — Assemble

```bash
python3 scripts/assemble_video.py \
    $BUILD/slides \
    $BUILD/audio \
    "$BUILD/<Deck Name> — Video.mp4" \
    --width 1920 \
    --height 1080 \
    --fps 15 \
    --crf 17 \
    --pad 1.2
```

Decks ≥ 10 slides on slow CPUs may exceed a single foreground tool timeout.
Run in background when necessary:

```bash
nohup python3 scripts/assemble_video.py ... > $BUILD/encode.log 2>&1 &
# poll until the log contains: VIDEO=... DURATION=...
```

Per-slide screen time:

`measured TTS duration + --pad`

The single filtergraph keeps page turns seamless.

---

## Stage 5 — Verify and deliver

```bash
ffprobe -v error \
    -show_entries format=duration \
    -of csv=p=0 OUT.mp4

ffprobe -v error \
    -select_streams v \
    -show_entries stream=width,height,nb_frames \
    -of csv=p=0 OUT.mp4
```

Extract 2–3 frames near slide boundaries and confirm that the correct slide is
visible at the corresponding narration.

Then give the user:
- the MP4 path,
- total duration,
- and the narration script path.

---

## Failure quick table

| Symptom | Fix |
|---|---|
| `edge-tts` 403 / network failure | retry once; otherwise ask for another TTS provider |
| Custom API 401 | key wrong/expired; ask once, never store it |
| Encode exceeds tool timeout | background `nohup` + poll log |
| Flicker at page turns | revert to single-pass filtergraph assembly |
| Slide text unreadable | rasterize at 2560/3840; keep H.264 CRF ≤ 18 |
| Narration sounds like slide reading | inspect the rendered slide again; rewrite around meaning, evidence, action, or interpretation |
| Narration sounds formulaic | remove repeated templates and unnecessary spatial phrases; let slide purpose drive the wording |
| Narration ignores an important figure/table | revisit the slide visually and decide how a real presenter would use that evidence |
| Narration over-explains visuals | simplify; not every visible element deserves spoken attention |

---

## Files

- `scripts/slides_to_png.py` — deck → PNG per slide
- `scripts/tts_narration.py` — script.md → per-slide mp3
- `scripts/assemble_video.py` — slides + audio → single-pass flicker-free MP4
- `references/script-guide.md` — presentation-quality narration guidance
- `references/architecture.md` — architecture and design rationale
