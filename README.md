# slides-to-video

Turn any slide deck (PPTX / PDF) into a **narrated HD video**, end to end — with zero page-turn flicker.

把 PPT/PDF 课件一键变成带配音讲解的 1080p 高清视频：自动写讲稿 → 你审阅修改 → 免费 TTS 配音 → 单次编码合成，翻页不闪烁。

![principle](assets/principle.png)

## Why this skill exists

Most "slides → video" pipelines encode each slide into a separate mp4 segment and then concatenate them. That creates timestamp discontinuities, keyframe misalignment and pixel-format mismatches at segment boundaries — which the human eye sees as **flicker / black frames at page turns**.

This skill assembles the whole video in **one single ffmpeg filtergraph pass** (per-segment PTS reset → concat filter → one encode). There are no seams, so there is no flicker — by construction, not by luck.

## The pipeline

```
deck.pptx/pdf ──► slides_to_png.py ──► slide-01..N.png (1920px+)
       │
       └─► LLM writes narration_script.md ──► ★ USER REVIEW GATE ★
                                                  │ approved
                                                  ▼
                              tts_narration.py ──► narr_01..N.mp3
                                                  │
                              assemble_video.py ──► 1080p H.264/AAC mp4
```

**The script is the master clock**: each slide stays on screen exactly as long as its measured TTS audio + 1.2s breathing room. Audio and video can never drift apart.

## Features

- 🎤 **Free TTS by default** — [edge-tts](https://pypi.org/project/edge-tts/), no API key needed, works in any environment (Grok / Mimo / Codex / Claude / Kimi)
- 👨 **Male voice by default**, scenario-matched voice table (professional / warm / authoritative / lively, zh + en)
- 🔌 **Bring your own TTS API** — paste an OpenAI-compatible key in your query (`"把这ppt变成视频，用我的 tts api key=sk-..."`) and it switches to your provider. Keys live only in env vars — **never written to disk**
- 📝 **Human-in-the-loop script gate** — the narration script is saved as plain markdown, you review/edit it, and only then does voice synthesis begin
- 🖥️ **True HD** — 1920×1080 default; text-dense decks can rasterize at 2560/3840 for crisp small text
- 🧩 **Minimal** — 3 scripts, 2 reference docs. No framework, no config files, no magic

## Usage (as an agent skill)

Drop this folder into your agent's skills directory (e.g. `.agents/skills/`), then just ask:

> "把这门课的 ppt 变成带讲解的视频" — uses free edge-tts, default male voice

> "我想用 mimo tts api key=sk-xxx 把这ppt变成视频" — uses your OpenAI-compatible TTS

The agent will: rasterize the deck → draft the script → **show you the script path and wait for your OK** → synthesize per-slide audio → assemble the video → verify sync → hand you the mp4.

## Usage (standalone scripts)

```bash
pip install edge-tts        # free default TTS
apt install ffmpeg poppler-utils libreoffice   # system deps

# 1. Rasterize
python3 scripts/slides_to_png.py deck.pdf build/slides --width 1920

# 2. Write build/narration_script.md yourself — format:
#    ## Slide 1 — Title
#    **[~20s]**
#    **Say:** 大家好，今天……

# 3. TTS
python3 scripts/tts_narration.py build/narration_script.md build/audio \
    --provider edge --voice zh-CN-YunxiNeural

# 4. Assemble (background nohup for long decks)
python3 scripts/assemble_video.py build/slides build/audio out.mp4 \
    --width 1920 --height 1080 --fps 15 --crf 17 --pad 1.2
```

## Voice table (edge-tts)

| Scenario 场景 | 中文 | English |
|---|---|---|
| 专业培训·产品讲解 (默认男声) | zh-CN-YunxiNeural | en-US-AndrewNeural |
| 温柔亲和·onboarding | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| 沉稳权威·汇报 | zh-CN-YunjianNeural | en-US-GuyNeural |
| 活泼轻快·营销 | zh-CN-XiaoyiNeural | en-US-AriaNeural |

## Repo layout

```
├── SKILL.md                  # agent workflow (5 stages, hard rules)
├── README.md
├── scripts/
│   ├── slides_to_png.py      # deck → per-slide PNG
│   ├── tts_narration.py      # script.md → per-slide mp3 (edge | openai-compatible)
│   └── assemble_video.py     # slides + audio → single-pass flicker-free mp4
├── references/
│   ├── script-guide.md       # how to write TTS-friendly narration
│   └── architecture.md       # 原理图 + 设计图 (mermaid)
└── assets/                   # diagram PNGs
```

## Design diagram

![design](assets/design.png)

## Security note

Never commit API keys. This skill reads keys only from `--api-key` / `TTS_API_KEY` env vars at runtime. If you ever pasted a key into a chat, rotate it.

## License

MIT
