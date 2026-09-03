# slides-to-video

Turn any slide deck (PPTX / PDF) into a **narrated HD video**, end to end, with
zero page-turn flicker and a human-reviewable presentation script.

把 PPT/PDF 课件转换成带配音讲解的 1080p 高清视频：

**渲染幻灯片 → 视觉理解与讲稿设计 → 用户审阅 → TTS 配音 → 单次编码合成**

![principle](assets/principle.png)

## Why this skill exists

There are two problems this project tries to solve.

### 1. Video assembly quality

Many slide-to-video pipelines encode each slide into a separate MP4 and then
concatenate the segments. Timestamp discontinuities, keyframe alignment, and
pixel-format differences can create visible flicker or black frames at page
turns.

This project uses **one ffmpeg filtergraph and one final encode**.

### 2. Narration quality

A slide deck is not just text.

Charts, tables, screenshots, highlighted controls, diagrams, layout, and visual
hierarchy often carry the real meaning. A weak narration pipeline extracts the
words and paraphrases them. The revised skill instead asks the agent to inspect
the rendered slide and think like a presenter.

The objective is not to mechanically mention every visual. It is to use visual
material **when it helps the explanation**.

A good presenter may say:

> The confusion matrix on the right shows how the model performed on the
> historical cohort. The key result here is the missed-detection count: it is
> zero.

rather than:

> Accuracy is 96 percent. Missed detections are zero. False alarms are four.

For a user-guide slide:

> Open the highlighted Download Programme Reports tile. On the next screen,
> find your programme and use the Details button at the end of its row.

rather than simply reading the button labels.

## Pipeline

```text
deck.pptx/pdf
      │
      ▼
slides_to_png.py
      │
      ├──────────────► slide-01..N.png ───────────────┐
      │                                               │
      │                                  visual-aware narration
      │                                               │
      │                                               ▼
      │                                      narration_script.md
      │                                               │
      │                                       ★ USER REVIEW ★
      │                                               │ approved
      │                                               ▼
      └─────────────────────────────────────► tts_narration.py
                                                      │
                                                      ▼
                                               narr_01..N.mp3
                                                      │
                       slide PNGs + narration audio ───┤
                                                      ▼
                                             assemble_video.py
                                                      │
                                                      ▼
                                            1080p H.264/AAC MP4
```

**The script is the master clock**: each slide stays on screen for its measured
TTS audio duration plus the configured breathing pad.

## Narration design philosophy

The skill provides **heuristics, not quotas**.

It encourages the agent to:
- inspect the rendered slide instead of relying only on extracted text;
- understand the purpose of each slide in the deck;
- use figures, tables, screenshots, diagrams, and spatial references when they
  make the explanation easier to follow;
- interpret rather than recite;
- vary delivery according to slide type;
- maintain continuity across slides;
- and allocate speaking time according to importance.

It does **not** require:
- one visual reference per slide;
- a fixed number of spatial phrases;
- a mandatory narration template;
- narration of every chart/table;
- or the same duration for every slide.

See `references/script-guide.md`.

## Features

- 🎤 **Free TTS by default** — edge-tts, no API key required
- 👨 **Scenario-matched voices** — professional, warm, authoritative, lively
- 🔌 **OpenAI-compatible TTS support** — runtime key only, never written to disk
- 🧠 **Visual-aware narration planning** — rendered slides influence the script
- 📝 **Human-in-the-loop script gate** — review/edit before speech synthesis
- 🖥️ **1080p output by default**
- 🔍 **2560/3840 rasterization option** for dense slides
- 🎬 **Single-pass flicker-free assembly**
- ⏱️ **Audio-driven slide timing**
- 🧩 **Minimal architecture** — 3 scripts + 2 reference docs

## Usage as an agent skill

Drop the folder into your agent's skills directory, for example:

```text
.agents/skills/slides-to-video/
```

Then ask:

> Turn this PPT into a narrated user-guide video.

or:

> 把这门课的 PPT 变成带讲解的视频。

The agent should:

1. parse the request;
2. rasterize the deck;
3. inspect the rendered slides;
4. draft the narration;
5. stop for user review;
6. synthesize approved narration;
7. assemble one video;
8. verify sync and deliver.

## Usage as standalone scripts

```bash
pip install edge-tts
apt install ffmpeg poppler-utils libreoffice

# 1. Rasterize
python3 scripts/slides_to_png.py deck.pdf build/slides --width 1920

# 2. Write / review build/narration_script.md

# 3. TTS
python3 scripts/tts_narration.py build/narration_script.md build/audio \
    --provider edge --voice en-US-AndrewNeural

# 4. Assemble
python3 scripts/assemble_video.py build/slides build/audio out.mp4 \
    --width 1920 --height 1080 --fps 15 --crf 17 --pad 1.2
```

## Script format

```markdown
# Deck title — Voiceover Script

## Slide 1 — Title
**[~20s]**
**On screen:** Optional reviewer note.
**Say:**
Hello, and welcome...

**Pronounce:** Optional pronunciation guidance.
```

Only `**Say:**` is sent to TTS.

## Voice table

| Scenario | 中文 | English |
|---|---|---|
| Professional training / product explanation | zh-CN-YunxiNeural | en-US-AndrewNeural |
| Warm onboarding | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| Authoritative report | zh-CN-YunjianNeural | en-US-GuyNeural |
| Lively marketing | zh-CN-XiaoyiNeural | en-US-AriaNeural |

## Repository layout

```text
.
├── .gitignore
├── README.md
├── SKILL.md
├── assets/
│   ├── design.png
│   └── principle.png
├── references/
│   ├── architecture.md
│   └── script-guide.md
└── scripts/
    ├── assemble_video.py
    ├── slides_to_png.py
    └── tts_narration.py
```

## Design diagrams

![design](assets/design.png)

The editable architecture description is in `references/architecture.md`.

## Security note

Never commit API keys.

This skill reads custom TTS credentials only from runtime CLI arguments or
environment variables such as `TTS_API_KEY`.

## License

MIT
