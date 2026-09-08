# slides-to-video · 幻灯片转视频

把一份 PPTX / PDF 幻灯片，变成一段带**旁白**和**视觉提示**（红点 / 红框）的 1080p 视频。
Turn any PPTX or PDF deck into a narrated 1080p video with visual cues (red laser dot / red rectangle).

> 它不是照着幻灯片念字，而是像一个懂内容的讲者，讲逻辑、讲含义，并在该看的地方给你圈出来。
> It does not read slides aloud. It narrates like a presenter who understands the deck, explains the meaning, and points at the right region.

---

## 安装 · Install

打开 **MiMoCode**，直接说一句话即可：
Open **MiMoCode** and just say:

> install the `slides-to-video` skill from this GitHub repo: `https://github.com/098765d/slides-to-video`

中文：
> 从这个 GitHub 仓库安装 `slides-to-video` 技能：`https://github.com/098765d/slides-to-video`

无需改任何配置文件；技能运行所需的系统工具见下方 [依赖](#依赖--requirements)。
No config file to edit; see [Requirements](#依赖--requirements) for the system tools it needs.

---

## 它做什么 · What it does

<p align="center">
  <img src="assets/pipeline.png" alt="流程：PPTX/PDF → 幻灯片 PNG → 视觉锚点 → cue 化旁白 → cue PNG + 分段 TTS → 单次 ffmpeg → 1080p MP4" width="100%">
</p>

它先**看懂**幻灯片，再像讲者一样**讲**，而不是照着念。
It first *understands* the slides, then *presents* them — it never just reads them.

- **视觉感知的旁白 / visually grounded narration** —— 对着渲染出来的幻灯片写，而不是对着抽取的文字。
- **选择性视觉提示 / selective cues** —— 红点（点目标）或红框（区域目标），该看哪里就圈哪里。
- **先审后合成 / human review before speech** —— 脚本 + 锚点 + 预览图先给你确认，再合成语音。
- **单次编码 / single-pass ffmpeg** —— 所有帧一次编码，无翻页闪烁。

每次运行还会先搭一条**故事主线**（hook → context → method → proof → insight → action），并给每页标注一个角色（role），让旁白是在**推进论证**，而不是在复述页面。
Each run also builds a deck-level **story spine** (hook → context → method → proof → insight → action) and tags every slide with a role, so the narration advances an argument instead of paraphrasing the slide.

---

## 使用场景 · Use cases

同一个技能，会根据场景自动调整旁白策略和提示方式：
The same skill adapts narration and cues to the scenario:

| 场景 Scenario | 旁白策略 Narration strategy | 示例 Example |
|---|---|---|
| **用户指南** User guide | 引导操作、点出按钮/字段，用语义标签而非坐标 | `[A] Open "Download Programme Reports" in the console. [B] On your programme row, click "Details".` |
| **报告/汇报** Report | 结论先行，用具体数字教读者读图 | `[A] The confusion matrix shows 91 normal and 5 at-risk students classified correctly. [B] Zero missed detections means the model errs on the safe side.` |
| **培训** Training | 步骤化：怎么做 + 为什么 | `[A] Start with the at-risk-prediction column — TRUE means flagged. [B] Then read the predicted GPA to see the estimate.` |
| **产品介绍** Product walkthrough | 价值 → 证据 → 下一步，圈出关键功能 | `[A] This card is the number to remember — 96% accuracy. [B] The chart on the right shows what drives it.` |
| **教学** Lecture | 概念 → 例子 → 含义 | `[A] LASSO shrinks less useful coefficients toward zero, keeping a small set of explainable predictors.` |

`[A]`、`[B]` 是**控制标记**（不会读出来），用来切换"红点/红框标在哪"。
`[A]` and `[B]` are control markers (never spoken) that switch which annotated frame is shown.

---

## 工作原理 · How it works

| # | 步骤 Step | 产物 Produces | 脚本 Script |
|---|---|---|---|
| 1 | Rasterize the deck（栅格化） | `slides/slide-01..N.png` | `slides_to_png.py` |
| 2 | Inspect + record anchors（看图 + 记锚点） | `visual_notes.yaml` | — |
| 3 | Write cue-aware narration（写 cue 化旁白） | `narration_script.md` | — |
| 4 | Render cue PNGs（渲染提示图） | `cues/slide-XX-A.png` | `annotate_slides.py` |
| 5 | **User review gate（人工审核门）** | approval | — |
| 6 | Synthesize per-cue audio（分段合成语音） | `audio/*.mp3` + `manifest.json` | `tts_narration.py` |
| 7 | Assemble one video（合成视频） | `<Deck Name> — Video.mp4` | `assemble_video.py` |
| 8 | Verify + deliver（校验 + 交付） | duration, resolution, QA | `ffprobe` |

**人在环路里 / human in the loop**：在第 4 步生成提示预览图之后、第 6 步合成语音**之前**，你会先审脚本、锚点和预览图；不满意就改，改完再继续。
You review the script, anchors, and cue previews *after* step 4 and *before* any speech is synthesized (step 6); edit and loop back if needed.

---

## 核心原理 · Core principles

1. **渲染图是唯一事实源 / The rendered slide is the ground truth.**
   旁白对着幻灯片图片写，而不是对着抽取的文字；没有视觉能力时就放弃空间描述，绝不瞎编位置。
   Narration is written against the slide image, not extracted text; without vision, spatial claims are dropped rather than invented.

2. **一条锚点 = 一条 cue = 一帧提示图 = 一段音频 / One anchor = one cue = one annotated frame = one audio segment.**
   四者确定性绑定，所以**不需要逐字对齐**——每段提示图只在它那段音频播放时显示：

<p align="center">
  <img src="assets/cue-timeline.png" alt="时间轴上的 cue 绑定：一句 cue 绑定它的锚点、提示帧和音频段；帧与音频同长" width="100%">
</p>

3. **提示样式跟着目标形状走 / Cue style follows target shape.**
   一个**点**（按钮、数据点、标签、节点）用红点；一块**区域**（表格列、图表、关键卡、整张图）用 2–3px 红框。
   A *point* is a red dot; an *area* is a 2–3 px red rectangle.

4. **音频是主时钟 / Audio is the master clock.**
   每帧停留时长 = 实测 TTS 时长 + 一个小间隔。图永远和对应的话同时起、同时止。
   Each frame's hold time equals its measured TTS duration plus a small pad.

5. **只编码一次 / Encode once.**
   所有帧和音频进同一个 ffmpeg filtergraph，避免翻页闪烁和时间戳接缝。
   One ffmpeg filtergraph avoids page-turn flicker and timestamp seams.

6. **花 TTS 之前先有人审 / Human review before any TTS spend.**
   先审脚本、锚点、提示图；TTS 默认用免费的 edge-tts。
   Review first; TTS defaults to the free `edge-tts` provider.

---

## 视觉提示 · Visual cues

<p align="center">
  <img src="assets/cue-styles.png" alt="两种提示：干净页 / 红点标点 / 红框圈区域" width="100%">
</p>

| 目标类型 Target | 例子 Example | 锚点字段 Anchor fields | 画成 Drawn as |
|---|---|---|---|
| 点 Point | 按钮、数据点、标签、节点 | `target: [x, y]` | 红色激光点 red laser dot |
| 区域 Area | 表格列、图表、关键卡、整图 | `shape: rectangle` + `box: [x, y, w, h]` | 红色矩形（2–3px）red rectangle |

坐标都是 0–1 的归一化值（`x, y` 是框的左上角，`w, h` 是宽高）。
Coordinates are normalized 0–1 (`x, y` = top-left corner, `w, h` = width/height).

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

## 快速开始 · Quick start

> Windows 用 `python`；Linux/macOS 用 `python3`。
> On Windows use `python`; on Linux/macOS use `python3`.

```bash
# 1. 栅格化（密集表格/小字可用 --width 2560）
python3 scripts/slides_to_png.py deck.pptx build/slides --width 1920
```

创建 `build/visual_notes.yaml`（见上）和 `build/narration_script.md`：
Create `build/visual_notes.yaml` (above) and `build/narration_script.md`:

```markdown
## Slide 2 — Results
**Say:**
[A] The chart on the left shows the main pattern in the result.

[B] The summary card on the upper right gives the number to remember.
```

```bash
# 2. 渲染提示图（同时校验 cue 与锚点是否一致）
python3 scripts/annotate_slides.py build/slides build/visual_notes.yaml build/cues \
  --script build/narration_script.md

# 3. 停一下 —— 审 narration_script.md、visual_notes.yaml、build/cues/

# 4. 合成语音（默认 edge-tts，音色按语言自动选）
python3 scripts/tts_narration.py build/narration_script.md build/audio

# 5. 合成视频
python3 scripts/assemble_video.py build/slides build/audio output.mp4 \
  --cues-dir build/cues
```

`assemble_video.py` 会自动读取 `build/audio/manifest.json`。

---

## 文件结构 · Repository layout

```text
slides-to-video/
├── SKILL.md                      agent 用的技能说明（流程 + 硬规则）
├── README.md                     本文件 this file
├── requirements.txt              Python 依赖
├── assets/
│   ├── pipeline.png              流程总览 pipeline overview
│   ├── cue-timeline.png          时间轴上的 cue 绑定
│   └── cue-styles.png            红点 vs 红框
├── scripts/
│   ├── slides_to_png.py          幻灯片 → 高清 PNG（Windows 用 PowerPoint COM；Linux 用 LibreOffice+poppler）
│   ├── win_pptx_to_png.ps1       Windows 下 PowerPoint COM 渲染
│   ├── script_parser.py          共享的旁白脚本解析器（标注 + TTS 共用）
│   ├── annotate_slides.py        锚点 → 提示图（红点 / 红框）
│   ├── tts_narration.py          旁白 → 分段 MP3 + manifest.json
│   └── assemble_video.py         帧 + 音频 → 单次 ffmpeg MP4
├── references/
│   ├── script-guide.md           旁白 + 提示样式的详细写作指导
│   └── architecture.md           设计理由、数据模型、原理
└── examples/
    ├── visual_notes.example.yaml
    └── narration_script.example.md
```

| 文件 File | 作用 Role |
|---|---|
| `SKILL.md` | agent 端到端执行的技能说明（各阶段 + 硬规则）。The agent-facing workflow + hard rules. |
| `scripts/slides_to_png.py` | 把幻灯片栅格化成 PNG（Windows：PowerPoint COM；Linux/macOS：LibreOffice+poppler）。 |
| `scripts/script_parser.py` | 解析 `## Slide N` / `**Say:**` 旁白格式的唯一实现，标注和 TTS 共用，保证不漂移。 |
| `scripts/annotate_slides.py` | 锚点 → 提示图：`target` → 红点，`shape: rectangle`+`box` → 红框；并校验每个 cue 都有锚点。 |
| `scripts/tts_narration.py` | 把脚本切成 cue 块、逐块合成 MP3（默认 edge-tts）、写 `manifest.json`（含实测时长）。 |
| `scripts/assemble_video.py` | 读取幻灯片 + 提示图 + manifest，单次 ffmpeg 编码成一个 MP4。 |
| `references/script-guide.md` | 写"讲者级"旁白、选择提示样式的详细指导。 |
| `references/architecture.md` | 为什么这样设计：数据模型、原理、被否掉的方案。 |

---

## 依赖 · Requirements

**系统工具 System tools**

`ffmpeg` 和 `ffprobe` 是**所有平台**都需要的（音频测时长 + 最终编码）。
`ffmpeg` + `ffprobe` are required everywhere (audio probing + final encoding).

- **Windows**：PPTX 渲染用已安装的 Microsoft PowerPoint（COM），无需额外安装；渲染 PDF 才需要 `poppler`。
- **Linux / macOS**：安装 LibreOffice（PPTX→PDF）和 poppler（`pdftoppm`）。

```bash
# Linux / macOS
sudo apt update
sudo apt install -y ffmpeg poppler-utils libreoffice
```

**Python 包 Python packages**（`pip install -r requirements.txt`）

| 包 Package | 用途 Purpose |
|---|---|
| `edge-tts` | 默认免费 TTS（需联网到微软在线服务） |
| `Pillow` | 画提示图（红点 / 红框） |
| `PyYAML` | 读取 `visual_notes.yaml` |

---

## 语音配置 · TTS configuration

三种后端，默认 **edge-tts**（免费、无需 key）。
Three backends; the default is **edge-tts** (free, no key).

**edge-tts（默认）** —— 音色不写就按语言自动选（中文 `zh-CN-YunxiNeural` / 英文 `en-US-AndrewNeural`）：

```bash
python3 scripts/tts_narration.py build/narration_script.md build/audio
```

**MiMo TTS（原生）** —— 通过 capability API 借用本实例的语音模型；唯一预置音色是 `Chloe`：

```bash
mimo llm-server issue --capability speech --json   # 打印 base_url + 一次性 token
TTS_API_KEY="<token>" python3 scripts/tts_narration.py build/narration_script.md build/audio \
  --provider openai --base-url <base_url> --model xiaomi/mimo-v2.5-tts --voice Chloe
```

**自定义 OpenAI 兼容 `/audio/speech`** —— 凭据放环境变量，绝不写进文件：

```bash
export TTS_API_KEY="..." TTS_BASE_URL="https://host/v1" TTS_MODEL="tts-model"
python3 scripts/tts_narration.py build/narration_script.md build/audio \
  --provider openai --voice default
```

---

## 安全 · Security

绝不把 API key 提交进仓库；只通过运行时环境变量或命令行参数传入。
Never commit API keys; use runtime environment variables or CLI arguments only.
