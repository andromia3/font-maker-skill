# Glyph atlas generation

Read this when generating or repairing atlas images.

## Sheet strategy

Use related glyphs together:

- uppercase: `ABCDEFGHIJKLMNOPQRSTUVWXYZ`, 7 columns × 4 rows;
- lowercase: `abcdefghijklmnopqrstuvwxyz`, 7 columns × 4 rows;
- digits: `0123456789`, 5 columns × 2 rows;
- punctuation/symbols: choose an explicit ordered string and a grid sized for it.

Leave unused final cells empty. Do not include explanatory labels inside the
image. The manifest, not model-written annotations, owns the cell mapping.

## Prompt scaffold

Adapt this to the creative brief. Preserve the exact character string and grid.

```text
Use case: stylized-concept
Asset type: production glyph atlas for an original installable display font
Primary request: Create exactly these characters once each, in this exact order:
"<CHARACTERS>". Arrange them left-to-right, top-to-bottom in an invisible
<COLUMNS>-column by <ROWS>-row grid. Leave unused final cells completely empty.
Every glyph stays isolated inside its equal-size cell, fully visible, centered,
and generously padded. No glyph may touch a neighboring cell.

Creative direction: <MEDIUM, PERSONALITY, SKELETON, SLANT, STROKE, RHYTHM>
Consistency: one coherent writer/designer, one tool, one scale, one cap/x-height,
one baseline system, and consistent entry/exit behavior across the full atlas.
Scene/backdrop: genuinely transparent background with real alpha; no paper,
canvas, backdrop, shadow, or rectangle.
Text (verbatim): "<CHARACTERS>"
Constraints: correct identity and order; no omitted, duplicated, substituted,
invented, or explanatory characters; no grid lines, labels, title, watermark, or
logo; preserve legibility at the intended size.
Avoid: <BRIEF'S AVOID LIST>
```

For cursive, request a consistent short entry and exit stroke at the same
baseline, while keeping every glyph physically separate in the atlas.

## References

- A handwriting source controls the mark-making and personal rhythm.
- A structural template controls identity, cell position, scale, and order.
- A mood reference controls atmosphere/material, not letter identity.
- A successful prior atlas controls family consistency during targeted repairs.

State these roles explicitly in the generation prompt. If a local template is
used with the built-in image-generation tool, inspect it first as required by the
image-generation skill.

## Structural template fallback

Generate a neutral transparent template when ordering repeatedly fails:

```sh
<python> <skill-dir>/scripts/make_grid_template.py \
  --characters "ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
  --columns 7 --rows 4 --size 2048x1152 \
  --output <project>/uppercase-template.png
```

Use it as a structural reference and tell the model to preserve identity and
position while replacing the neutral glyph design. The template can bias the
skeleton, so prefer a clean prompt-only first attempt for highly original work.

## Inspection gate

Before compiling, verify:

- exact count, identity, and order;
- genuine alpha and transparent unused cells;
- no grid lines, labels, background, or neighboring overlaps;
- coherent height, baseline, slant, weight, stroke texture, and counters;
- sufficient padding around every cell;
- distinguishable similar glyphs.

If only a few glyphs fail, use the good atlas as a reference and generate a small
repair sheet in known order. Do not silently map a wrong image to the requested
Unicode character.
