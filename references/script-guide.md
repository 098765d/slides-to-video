# Narration Script Guide

The script is the **master clock**: slide N stays on screen exactly as long as
its narration (plus pad). Write for the ear, not the eye.

## Format contract (parser depends on it)

```markdown
# <Deck title> — Voiceover Script
## Slide 1 — <slide title>
**[~30s]**
**On screen:** <1 line: what the viewer sees — optional, for the human reviewer>
**Say:** <the spoken text>
**Pronounce:** <optional: URL/acronym spell-outs>
## Slide 2 — ...
```

- `## Slide N — …` starts a block; N must be contiguous from 1.
- `**Say:**` is the only field sent to TTS. Everything else is for the human reviewer.
- Cues: `[pause]` (≈0.5s beat), `[breathe]`. Strip ALL other brackets/markdown from Say text.
- Total length line at top: "约 X 分钟 · 共 N 段" helps the reviewer.

## Spoken-style rules

1. **One idea per slide.** Say what the slide *means*, don't read bullets aloud.
2. **Numbers**: write them the way they're spoken. `96.0%` → "百分之九十六";
   URLs → "pappl dot eduhk dot aitch kay slash ee-ay-pee-ar" (and put it in `**Pronounce:**`).
   Same rule for acronyms (`GPA` → "G P A") and filenames — never feed raw
   `A4B0XX_2026_report.html` to TTS; write "A4B0XX 二零二六 report.html".
3. **Length**: ≈ 2.2 words/sec (en) or ≈ 4 chars/sec (zh). 15–45s per slide;
   appendix/title slides can be 8–15s.
4. **Tone matches scenario**: 培训讲解 = warm, steady, second person ("you'll see…");
   汇报 = declarative, numbers first.
5. **Hooks**: first slide says what the viewer gets; complex stats get a
   "[pause] look at the top-right card" beat before the number.
6. **No AI tells**: no "综上所述/值得注意的是" chains, no "I hope this helps",
   no markdown symbols in Say text.

## Review checklist before showing the user

- Every slide 1..N has a block, in order.
- Read Say text aloud once — anything you trip on, rewrite.
- Duration estimate per slide (`**[~Xs]**`) ≈ words ÷ 2.2; flag any slide > 60s.
- After TTS, reconcile `[~Xs]` against measured mp3 durations; a large miss (>30%) means the estimate or the reading speed is off — tell the user.
