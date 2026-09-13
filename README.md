# Slides to Video

把一份静态幻灯片变成带旁白和视觉提示的 MP4。你只需要把任务用自然语言告诉 AI Agent，由 Agent 按流程完成：理解幻灯片、安排讲解顺序、标出观众应该看的位置、生成语音并合成视频。

Turn a static slide deck into a narrated MP4 with visual cues. Describe the task in natural language and let an AI agent analyze the slides, plan the narration, point to the important areas, generate voice-over, and assemble the video.

## 你需要什么 | What you need

- 一个支持安装 Skill 的 AI Agent，例如 **Codex、MiMo Code、Grok** 等。
- Agent 至少具备一个**视觉大模型**，能够读取 PPTX/PDF 转出的幻灯片图片。
- 你的幻灯片文件地址，以及希望使用的语音方式（例如 Edge TTS 或你所在平台支持的 TTS）。

You need an agent that can install Skills and has at least one vision-capable model. Codex, MiMo Code, Grok, and similar agents can use this Skill.

## 演示视频 | Demo video

点击下方视频即可在 GitHub 中打开并播放演示：  
Click the link below to watch the complete demo on GitHub.

[https://github.com/098765d/slides-to-video/releases/download/untagged-26aba6022cad1fa46369/DemoVideo_20260913_17282823.mp4](https://github.com/user-attachments/assets/f15a732f-f7da-41d6-9081-14a2844f6571)

## 推荐使用方式 | Recommended workflow

### 1. 在 Agent 中安装 Skill | Install the Skill

把下面这句话直接发送给 Agent：

```text
从 GitHub 仓库安装 slides-to-video Skill：
https://github.com/098765d/slides-to-video
```

Send the same request in English if preferred:

```text
Install the slides-to-video Skill from this GitHub repository:
https://github.com/098765d/slides-to-video
```

### 2. 让 Agent 根据幻灯片生成视频 | Ask the Agent to make the video

将文件地址、讲解目标和语音要求一次告诉 Agent。例如：

```text
请使用 slides-to-video Skill，根据以下幻灯片生成带旁白和视觉提示的 MP4：
文件：C:\\path\\to\\my-deck.pptx
用途：给团队做 10 分钟项目汇报
要求：先讲每页主旨，再在讲到图表或关键数字时用红框或红点提示
语音：使用中文女声；如果默认 TTS 不可用，请使用当前 Agent 可用的 TTS
输出：保存为 C:\\path\\to\\output.mp4
完成后检查音画是否同步，并告诉我输出文件位置
```

English example:

```text
Use the slides-to-video Skill to turn this deck into a narrated MP4:
Deck: /path/to/my-deck.pptx
Purpose: a 10-minute project update for my team
Narration: explain the main point of each slide, then highlight charts and key numbers with a red box or dot
Voice: use an English female voice, or the TTS available in this agent
Output: /path/to/output.mp4
Check audio-video synchronization before finishing and report the output path
```

### 3. 根据需要继续修改 | Iterate in conversation

你可以继续用自然语言提出修改：

```text
把第 4 页的旁白缩短到 30 秒。
把第 7 页的红框移到右侧柱状图。
语速放慢，改用更正式的语气。
重新生成视频并覆盖上一版。
```

You can refine the result conversationally:

```text
Shorten slide 4 to 30 seconds.
Move the cue on slide 7 to the bar chart on the right.
Use a slower, more formal speaking style, then rebuild the video.
```

## 视频是怎样保持同步的 | How synchronization works

Agent 会把一页幻灯片拆成多个画面：原始画面用于介绍整页，带红点或红框的画面用于讲解具体内容。每个画面对应一段音频，图片停留时间由该段音频的实际时长决定。

The agent can split one slide into a base frame and cue frames. Each frame maps to exactly one audio clip, and the measured audio duration determines how long that frame stays on screen.

![Audio-video alignment](assets/audio%20video%20alignment.png)

视觉提示只是在原始幻灯片上叠加红点或红框，不会重绘或改写幻灯片内容。  
Cues are drawn over the original slide, so the slide content remains unchanged.

![Pipeline](assets/pipeline.png)

## 输入与输出 | Inputs and outputs

- **输入 | Input**：PPTX 或 PDF、讲解目标、语言和语音偏好
- **输出 | Output**：带旁白、视觉提示和同步时间轴的 MP4
- **中间结果 | Intermediate files**：幻灯片 PNG、视觉锚点、分段音频和时间清单（由 Agent 管理）

## 如果 Agent 需要手动运行 | If the agent asks for commands

通常无需手动执行命令。若 Agent 要求检查环境，请确保安装了 `ffmpeg`、`ffprobe`，以及用于渲染幻灯片的 PowerPoint、LibreOffice 或 Poppler。

No manual commands are normally required. If the agent asks you to prepare the environment, install `ffmpeg`, `ffprobe`, and the slide-rendering tools available for your platform.

更多旁白写作建议见 [references/script-guide.md](references/script-guide.md)。


