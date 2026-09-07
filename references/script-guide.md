# Narration + Visual Cue Script Guide

The goal is a voiceover that sounds like a knowledgeable presenter **and** keeps
spoken references visibly connected to the slide.

The deck is visual communication. The narrator should interpret, orient,
explain, compare, guide actions, or connect ideas rather than merely read text.

The cue system is deliberately small:

**visual anchor note → narration cue marker → arrow-annotated slide PNG**

It is meant to work reliably across arbitrary PPTX/PDF decks without requiring
PowerPoint animations, mouse tracking, OCR pipelines, or word-level timing.

---

## 1. Visual anchor notes

Before writing the narration, inspect the rendered slide image and record only
the visual elements that genuinely help the explanation.

Typical count:

- title/divider: 0 anchors;
- normal content slide: 1–3 anchors;
- unusually complex instructional slide: up to 5 anchors.

Do not annotate decoration, logos, repeated footer text, or every visible object.

Example `visual_notes.yaml`:

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

Each anchor needs:

- `id`: one uppercase letter A–Z;
- `location`: human-readable location used to ground spatial language;
- `element`: semantic description of the visual target;
- `target`: normalized `[x, y]` coordinate between 0 and 1.

Optional:

```yaml
from: [0.83, 0.42]
```

This overrides the automatic arrow start point when the default arrow would
cover content.

Location alone is not enough.

Weak:

```yaml
- id: A
  location: top-right
```

Better:

```yaml
- id: A
  location: top-right
  element: model accuracy card
  target: [0.82, 0.28]
```

---

## 2. Narration format

```markdown
# <Deck title> — Voiceover Script

## Slide 1 — <slide title>
**[~20s]**

**Visuals:**
- [A] left — first chart
- [B] right — summary card

**Say:**
[A] The chart on the left shows the historical pattern that matters for this
comparison.

[B] The summary card on the right gives the current result.

**Pronounce:** <optional pronunciation guidance>
```

Rules:

- `## Slide N` starts a slide block.
- `**Say:**` contains spoken narration.
- `[A]`, `[B]`, `[C]`, etc. are **visual control markers** and are not spoken.
- A cue remains active until the next cue marker.
- Text before the first cue marker is uncued/base narration and uses the clean
  slide image.
- `[pause]`, `[breathe]`, and similar bracketed delivery notes are not spoken.
- `**Visuals:**` and `**Pronounce:**` are reviewer metadata, not TTS text.

---

## 3. Visual Reference Contract

If a spoken sentence explicitly refers to a visible object, it should normally
be grounded to a supplied anchor.

Examples of visually grounded references:

- “the chart on the left”;
- “this value”;
- “the button highlighted here”;
- “the first row of the table”;
- “the final column”;
- “the diagram at the top”;
- “the largest bar”.

The contract is:

```text
spoken claim
    ↕
visual cue id
    ↕
visual anchor note
    ↕
actual rendered-slide evidence
```

If the narration says:

> The card on the right shows five detections.

then the slide must contain a matching anchor identifying that card and its
location.

If the target cannot be established confidently, rewrite without the spatial
claim or omit the claim. Never invent screen position or visual precision just
to sound like a presenter.

---

## 4. Use cues selectively

Cue markers are not quotas.

A cue is useful when it helps the audience answer **where should I look while
hearing this sentence?**

Good uses:

### Chart

```markdown
[A] The largest bar is Year 2 GPA, so this variable contributes much more
strongly than the others in this example.
```

### Confusion matrix

```markdown
[A] The matrix compares predictions with known outcomes.
[B] The number to focus on is missed detections, because those are cases the
model failed to identify.
```

### Table

```markdown
[A] Read the table from this correlation column rather than row by row. Higher
values indicate a stronger association.
```

### Screenshot / software guide

```markdown
[A] Open the Download Reports tile here.
[B] On the next screen, use the Details button at the end of the programme row.
```

### Process diagram

```markdown
[A] The process starts with the source data.
[B] It then moves through the prediction model.
[C] The final output is the programme-level result.
```

Do not use arrows for:

- titles that need no explanation;
- decorative illustrations;
- generic transitions;
- every bullet on a simple text slide;
- visual elements that are not discussed.

---

## 5. Explain rather than recite

Weak:

> Accuracy is 96 percent. Missed detections are zero. False alarms are four.

Stronger:

```markdown
[A] The historical validation result is summarized here. The number I would
pay particular attention to is missed detections, because these are the cases
the model failed to identify. In this example, that value is zero.

[B] The trade-off is four false alarms.
```

The stronger version is not better because it is longer. It is better because
it tells the audience what matters and where to look.

---



## 6. Add presenter value: orient → interpret → act

A useful video script should do more than paraphrase slide text. For each
substantive slide, decide what the audience needs from the narration.

Use this three-part pattern when it fits:

1. **Orient** — tell the viewer what part of the slide matters and what question
   the slide answers.
2. **Interpret** — explain the meaning of the evidence, not just the labels.
3. **Act / connect** — state what the audience should do with that information,
   or how it leads to the next slide.

Example:

Weak:

> This slide has a confusion matrix and an accuracy card.

Stronger:

> The confusion matrix shows how the model performed on a historical cohort.
> Read the rows as actual outcomes and the columns as predictions. In this
> example, 96 of 100 cases are correct, and the key operational result is that no
> actually at-risk student was missed. That gives us a basis for interpreting the
> latest-cohort predictions on the next slide.

The goal is not to make every slide longer. The goal is to add one useful layer
of explanation that the audience cannot get simply by reading the slide.

### Use concrete examples on analytical slides

When a chart, matrix, table, or dashboard contains a small number of meaningful
values, use the actual values to teach the viewer how to read it.

Prefer:

> 91 normal students and 5 at-risk students are on the diagonal, so those 96
> cases were classified correctly. The four off-diagonal cases are false alarms.

Over:

> The diagonal is good and the off-diagonal shows errors.

Do not enumerate every number. Select the minimum set needed to demonstrate how
an unfamiliar visual works.

### Briefly explain unfamiliar methodology

If a slide introduces a model, statistical method, technical metric, or domain
term that the target audience may not know, give a concise explanation before
interpreting the result.

Normally use 1–3 sentences:

- what the method does;
- why it is used in this context;
- what the audience should take from the output.

Example:

> LASSO is a regression method that shrinks less useful coefficients toward
> zero, leaving a smaller set of informative predictors. This is useful here
> because the model remains relatively easy to interpret: the audience can see
> which predictors were retained and how strongly they contribute.

Avoid turning a user guide into a technical lecture.

### Prefer semantic labels over fragile coordinates

For user-guide narration, refer to stable labels such as:

- `At_Risk_Prediction`;
- `Predicted_GPA`;
- `Download Programme Reports`;
- `Details`.

Avoid relying on Excel letters, row numbers, pixel positions, or other layout
coordinates unless the location is guaranteed to be stable and the user needs
it operationally.

For example, prefer:

> Filter `At_Risk_Prediction` to TRUE.

rather than:

> Filter column AJ to TRUE.

### Distinguish related concepts that could otherwise look contradictory

If a deck contains two similar-looking quantities with different meanings, the
narration should explicitly separate them.

Examples:

- an academic definition of an at-risk outcome versus a model-derived
  classification cutoff;
- correlation versus causal effect;
- historical validation performance versus latest-cohort prediction counts.

One concise clarification can prevent a large amount of audience confusion.

### Use organisational and procedural details exactly

For team, department, policy, deadline, or workflow slides, preserve the exact
organisation names, roles, and timing shown in the source material.

Do not generalise a team as "cross-disciplinary" if the slide provides the
specific participating departments. Do not change a deadline such as "within
one month" into a vague "soon".

### One useful insight per important slide

For central slides, try to add one audience-relevant insight beyond the visible
text. Examples include:

- which metric matters most and why;
- what a matrix cell means in practice;
- why a target year was chosen;
- what a model coefficient tells the viewer;
- what the viewer should do next.

This is a judgment rule, not a quota. Divider and appendix slides may need no
extra insight.

### Keep unsupported enrichment out

Do not invent background rationale, research findings, causal claims, or
performance explanations that are not supported by the deck, supplied source
material, or explicit user-provided context.

If the user supplies an additional project rationale that is not written on the
slide, it may be incorporated when requested, but it should not be silently
presented as if it came from the slide itself.


## 7. Let slide type determine delivery

These are heuristics, not templates.

### Title / divider
Usually brief. Often no visual cue.

### Bullet / concept
Synthesize the idea rather than reading every bullet.

### Chart
Direct attention to the relevant pattern, comparison, trend, outlier, or
implication.

### Table
Explain how to read it, then cue only the rows/columns needed for the message.

### Dashboard / metric cards
Group related metrics. Cue only the values that deserve attention.

### Screenshot / user guide
Use cues for the controls or regions where the user must act.

### Diagram / process
Cue the visual sequence in the same logical order as the narration.

### Comparison
Use one cue per side/alternative when the contrast is the point.

### Appendix / reference
Usually summarize its purpose or skip detailed narration.

---

## 8. Cross-slide continuity

The presentation should sound continuous, not like independent slide summaries.

Useful transitions include:

- “Now that we know how the model performed…”
- “The next question is…”
- “This brings us to…”
- “To identify the individual records…”

Do not attach a transition to every slide mechanically.

---

## 9. Pacing

Let importance determine speaking time.

Brief:

- title pages;
- section dividers;
- obvious navigation;
- reference slides.

Longer:

- unfamiliar concepts;
- important figures;
- dense tables;
- multi-step user instructions;
- consequential interpretation.

Approximate rates:

- English: about 2.0–2.3 words/sec;
- Chinese: about 3.5–4.5 chars/sec.

The user’s requested total duration takes priority over defaults.

---

## 10. Factual discipline

Do not invent:

- numbers;
- labels;
- trends;
- positions;
- controls;
- table entries;
- causal explanations;
- or conclusions.

If something cannot be read reliably, avoid false precision.

---

## 11. Final review

Before TTS, review the complete script and visual notes together.

Ask:

- Does the narration sound like a knowledgeable human presenter?
- Does every explicit visual/spatial reference have a matching anchor?
- Does each cue point to the exact thing being discussed?
- Are complex visuals easier to understand after hearing the narration?
- Are cues selective rather than constant?
- Are any arrows likely to cover important content?
- Does the presentation remain coherent across slides?
- Is the total duration appropriate?

These are editorial questions, not numeric quotas.
