---
name: slides-to-video
description: >
  Turn a slide deck (PPTX or PDF) into a narrated HD video, end to end:
  rasterize slides → draft a voiceover script → let the user review/edit it →
  TTS per slide → assemble into one 1080p MP4 with zero page-turn flicker.
  Use when a user asks to convert slides/PPT/课件/幻灯片 into a video, 视频讲解,
  narrated walkthrough, user-guide video, or "把这ppt变成视频".
  Default TTS is the free edge-tts (default male voice, matched to the deck's
  scenario); the user may instead paste their own OpenAI-compatible TTS API
  (base_url + api key, e.g. Mimo/Grok/Codex) in the query.
---

# Slides → Narrated HD Video

Minimal pipeline, 5 stages. All scripts live in `scripts/` next to this file.
Working dir for every run: `/mnt/agents/output/video_build_<deckname>/` (call it `$BUILD`).

## Hard rules (read first)

1. **Script gate.** After Stage 2 you MUST tell the user where the script file is and ask them to review/edit it. Do NOT run TTS until they approve (or say "直接继续"). This is a human-in-the-loop checkpoint, not a formality.
2. **Never persist API keys.** A key pasted in the query is used only as a runtime CLI arg / env var (`--api-key` / `TTS_API_KEY`). Never write it into any file, script, log, or narration text. Never echo it back in full.
3. **Single-pass assembly.** `assemble_video.py` builds the whole video in one ffmpeg filtergraph pass. Do NOT replace it with encode-per-slide-then-concat — that is exactly what causes flicker/black frames at page turns.
4. **HD = 1920×1080.** Default. Never go below 1280×720.

## Stage 0 — Parse the request

From the user's query + attachments determine:

- `DECK`: path to .pptx or .pdf
- `LANG`: script/narration language = user's language (zh / en / …)
- `SCENARIO`: deck type → voice pick (see voice table)
- TTS provider:
  - User pasted `api key` / `api_key=...` / `key=sk-...` → provider `openai`. Extract `key`; ask base_url ONLY if not inferable (mimo → their endpoint; when unknown, ask once).
  - Otherwise → provider `edge` (free, offline-auth, no key needed).
- Voice: user-specified > scenario-matched (table below) > **default male**.

### Voice table (edge-tts, free)

| Scenario | zh voice | en voice |
|---|---|---|
| default / 专业培训·产品讲解 (male) | zh-CN-YunxiNeural | en-US-AndrewNeural |
| 温柔亲和· onboarding·客户向 (female) | zh-CN-XiaoxiaoNeural | en-US-JennyNeural |
| 沉稳权威·汇报·政策解读 (male, deep) | zh-CN-YunjianNeural | en-US-GuyNeural |
| 活泼轻快·营销宣传 (female) | zh-CN-XiaoyiNeural | en-US-AriaNeural |

List more with `edge-tts --list-voices`. Custom provider: use the user's `voice`/`model` if given, else their provider default.

## Stage 1 — Rasterize slides

```bash
python3 scripts/slides_to_png.py DECK $BUILD/slides --width 1920
```

Prints `SLIDES=N`; outputs `slide-01.png …` at 1920px wide. Check N is plausible; spot-check one image renders correctly. For text-dense decks (small tables, code), rasterize sharper — `--width 2560` (or 3840); assembly downscales, small text stays crisp.

## Stage 2 — Draft narration script → USER GATE

Write the script yourself (or one writer subagent for decks > 20 slides) following
`references/script-guide.md`. Format contract (the TTS parser depends on it):

```markdown
## Slide N — <title>
**[~Xs]**
**Say:** <spoken text, [pause] and [breathe] cues allowed>
```

Save to `$BUILD/narration_script.md`. Then STOP and tell the user:

> 讲稿已生成：`<path>`（共 N 段，预计 X 分钟）。请查看/直接修改该文件；回复"OK"或"继续"我就开始配音合成视频。

Only proceed on approval. If they edited the file, re-read it — never use your cached copy.

## Stage 3 — TTS per slide

```bash
# default free path
pip install edge-tts   # once per environment
python3 scripts/tts_narration.py $BUILD/narration_script.md $BUILD/audio \
    --provider edge --voice zh-CN-YunxiNeural --rate +0%

# user-provided API (key from query, runtime only)
TTS_API_KEY='sk-...' python3 scripts/tts_narration.py $BUILD/narration_script.md $BUILD/audio \
    --provider openai --base-url <their_base_url> --model <model> --voice <voice>
```

Outputs `narr_01.mp3 …`, prints per-slide seconds. Retry failures once (`--rate -5%` if a segment overruns its slide budget badly). Missing audio is acceptable — assembly pads a still.

## Stage 4 — Assemble (background for long decks)

```bash
python3 scripts/assemble_video.py \
    $BUILD/slides $BUILD/audio "$BUILD/<Deck Name> — Video.mp4" \
    --width 1920 --height 1080 --fps 15 --crf 17 --pad 1.2
```

Decks ≥ 10 slides on slow CPUs exceed a single call timeout. Run in background:

```bash
nohup python3 scripts/assemble_video.py ... > $BUILD/encode.log 2>&1 &
# poll: tail -1 $BUILD/encode.log  until  "VIDEO=... DURATION=..."
```

Per-slide screen time = measured TTS duration + `--pad` (default 1.2s). Flicker-free by construction — see `references/architecture.md`.

## Stage 5 — Verify & deliver

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 OUT.mp4   # ≈ Σ audio + pads
ffprobe -v error -select_streams v -show_entries stream=width,height,nb_frames -of csv=p=0 OUT.mp4
```

Extract 2–3 frames near slide boundaries (`ffmpeg -ss T -i OUT.mp4 -frames:v 1 f.png`) and confirm the right slide shows — catches sync drift. Then give the user the mp4 path, total duration, and the script path again.

## Failure quick table

| Symptom | Fix |
|---|---|
| `edge-tts` 403/网络失败 | retry once; else ask user for their TTS API |
| Custom API 401 | key wrong/expired — ask once, never store it |
| Encode exceeds tool timeout | background `nohup` + poll log (Stage 4) |
| Flicker at page turns | you switched to segment-concat — revert to single-pass (rule 3) |
| Slide text unreadable | re-rasterize `--width 2560`, keep H.264 crf ≤ 18 |

## Files

- `scripts/slides_to_png.py` — deck → PNG per slide (LibreOffice + pdftoppm)
- `scripts/tts_narration.py` — script.md → per-slide mp3 (edge / openai-compatible)
- `scripts/assemble_video.py` — slides + audio → single-pass flicker-free MP4
- `references/script-guide.md` — how to write the narration script
- `references/architecture.md` — 原理图 + 设计图 (why it's built this way)
