# Narration Script Guide

The script is the **master clock**: slide N stays on screen as long as its
narration plus the configured pad.

Write for the ear, but think with the slide.

The objective is a voiceover that sounds like a real presenter using visual
material, not a text-to-speech reading of slide content.

## Format contract

```markdown
# <Deck title> — Voiceover Script

约 X 分钟 · 共 N 段

## Slide 1 — <slide title>
**[~30s]**
**On screen:** <optional: one-line description for the human reviewer>
**Say:**
<spoken text>

**Pronounce:** <optional: URL/acronym/filename guidance>

## Slide 2 — ...
```

- `## Slide N — …` starts a block; N must be contiguous from 1.
- `**Say:**` is the only field sent to TTS.
- Everything else is for the human reviewer.
- Bracket cues such as `[pause]` and `[breathe]` are removed before synthesis.

## Presentation principle

A slide and a voiceover should complement each other.

The viewer can already read the slide. The narrator should contribute something
useful, such as:
- interpretation,
- emphasis,
- visual orientation,
- explanation,
- comparison,
- context,
- reasoning,
- action guidance,
- or transition.

What is useful depends on the slide.

There is no requirement to mention a visual element on every slide. There is no
required count of "left/right" references. There is no fixed narration template.

## Before writing a slide

Silently consider:

- What is this slide doing in the overall story?
- What will the audience naturally look at?
- What is obvious from the slide already?
- What might be misunderstood without explanation?
- Is there a chart/table/screenshot/diagram that should shape the narration?
- What is the one thing the audience should understand, remember, or do?
- What should be left unsaid?
- How does this slide connect to its neighbours?

Use these questions to think, not to generate a checklist in the final script.

## Natural visual grounding

When visual reference helps comprehension, use it.

Examples:

### Chart
> The largest bar here is Year 2 GPA, so this variable contributes much more
> strongly than the others in this example.

### Confusion matrix
> The matrix on the right compares predictions with known outcomes. The number I
> would focus on is missed detections, because those are at-risk students the
> model failed to identify.

### Table
> The table is ranked by correlation. Rather than reading every row, the main
> point is that only courses above the 0.50 threshold appear here.

### Screenshot
> The option we need is highlighted in red. Open Download Programme Reports,
> then find your programme and use the Details button at the end of its row.

### Process diagram
> The workflow starts with the uploaded deck, moves through script review and
> narration, and finishes with a single-pass video assembly.

### Comparison
> The left panel describes the historical validation result, while the right
> panel shows the current cohort prediction.

Use spatial wording only when it genuinely helps the viewer track the screen.

Do not fill every slide with:
> "On the left… on the right… at the bottom…"

And do not repeatedly say:
> "As you can see…"

## Explain rather than recite

Weak:

> Accuracy is 96 percent. Missed detections are zero. False alarms are four.

Stronger:

> The historical validation result shows 96 percent accuracy, but the more
> important figure for this use case is missed detections. Here it is zero,
> meaning no actually at-risk student in this validation example was missed.
> There are four false alarms.

Weak:

> The prediction cohort is 2024. There are 109 students. Five are at risk.

Stronger:

> The summary cards tell us that 109 students were analysed in the 2024 cohort,
> and five were flagged as potentially at risk. The next question is who those
> five students are, which is why the workflow now moves to the Excel file.

## Let slide type influence the delivery

These are heuristics, not templates.

### Title / divider
Usually brief. Establish direction.

### Bullet / concept
Synthesize rather than reading every bullet in sequence.

### Chart
Help the audience notice the pattern, comparison, trend, outlier, or implication
that matters.

### Table
Explain how the table should be read if necessary, then select the rows/columns
needed for the message.

### Dashboard / cards
Group metrics and identify what matters. Do not read every card automatically.

### Screenshot / user guide
Guide the viewer through visible controls and actions. Use labels and location
cues naturally.

### Diagram / process
Follow a logical visual path.

### Comparison
Make the contrast explicit when that is the point.

### Worked example
Walk through the reasoning rather than only stating the answer.

### Appendix / reference
Usually summarise its role or skip detail unless the user asks for it.

## Cross-slide continuity

The presentation should sound continuous.

Useful transitions include:
- "Now that we know how the model performed…"
- "The next question is…"
- "This brings us to…"
- "To identify the individual students…"

But do not attach a transition phrase to every slide mechanically.

## Pacing

Let importance determine time.

Brief:
- title pages,
- section dividers,
- obvious navigation,
- reference slides.

Longer:
- unfamiliar concepts,
- important charts,
- dense tables,
- multi-step user instructions,
- consequential interpretation.

Approximate rates:
- English: about 2.0–2.3 words/sec
- Chinese: about 3.5–4.5 chars/sec

A user-provided overall time limit is more important than any default per-slide
range.

## Spoken style

- Prefer one clear thought at a time.
- Use natural sentence rhythm.
- Avoid dense parenthetical prose.
- Make filenames, acronyms, symbols, and URLs pronounceable.
- Use `[pause]` only when a beat genuinely helps comprehension.
- Keep domain terminology consistent with the slide deck.
- Avoid repetitive AI-style phrases.

## Factual discipline

Do not invent:
- numbers,
- labels,
- trends,
- positions,
- controls,
- causal explanations,
- or conclusions.

If something cannot be read reliably, avoid false precision.

## Final review

Read the complete `**Say:**` text aloud mentally from beginning to end.

Ask:
- Does it sound like a real presenter?
- Does it feel connected across slides?
- Are complex visuals made easier to understand?
- Does the narration add something beyond the visible text?
- Are visual references used when useful, rather than by formula?
- Is any slide over-explained?
- Is any important slide under-explained?
- Are instructions actionable?
- Is anything repetitive?
- Does the total timing fit the user's goal?

These are editorial questions, not numerical requirements.
