---
name: font-maker
description: Create original installable fonts from a user's visual idea, handwriting, references, or generated glyph atlas. Use for font ideation, glyph-atlas generation, raster-to-vector conversion, TTF/WOFF2 compilation, and proof specimens; do not trigger for ordinary font recommendations or simple typesetting.
---

# Font Maker

Turn a visual idea into a reproducible font project with source atlases,
individual glyph assets, vector outlines, an installable TTF, a WOFF2 webfont,
and a rendered specimen.

## Choose the scope

- Default to an uppercase `A–Z` feasibility proof when the user wants to test an
  idea quickly. Expand only after the visual system survives a real specimen.
- For a broader first release, use separate atlases for uppercase, lowercase,
  and figures/punctuation. Keeping related glyphs together improves coherence
  without crowding every character into one sheet.
- Treat a generated cursive font as a display prototype unless it has been
  tested and refined for joins, spacing, ambiguous forms, and repeated text.
  Bearings can make strokes nearly meet; production-quality contextual joining
  usually needs entry/exit alternates and OpenType shaping.

## Workflow

1. **Capture the idea.** Use what the user already supplied. If the concept is
   underspecified, read [references/intake.md](references/intake.md) and ask no
   more than three high-leverage questions in one message. Translate ordinary
   language into a concise creative brief; do not require typography jargon.
2. **Define the repertoire.** State the intended use and exact first-pass
   characters. Recommend uppercase `A–Z` for a cheap proof unless the request
   clearly requires more.
3. **Choose references.** Label every supplied image as an edit target,
   handwriting source, structural reference, or mood/style reference. Use only
   images the user owns or is authorized to adapt. Create an original design;
   do not reproduce a commercial font exactly.
4. **Generate atlases.** Read
   [references/atlas-generation.md](references/atlas-generation.md). Prefer the
   available image-generation skill/tool and genuinely transparent output.
   Generate related glyphs together in a known grid and preserve the exact
   requested order. Use one full-sheet retry for ordering errors, then repair
   only bad glyphs using the successful atlas as a reference.
5. **Inspect before compiling.** Confirm visually that every cell contains the
   intended character exactly once, the background has real alpha, no glyph
   touches a neighbor, and cap height/baseline/slant/weight remain coherent.
   Code can validate geometry and alpha; it cannot reliably determine whether
   a stylized `R` was accidentally rendered as a `P`.
6. **Create the manifest.** Read
   [references/manifest.md](references/manifest.md). Store paths relative to the
   manifest when practical so the project remains portable.
7. **Run the deterministic pipeline.** Resolve this skill's folder from the
   available-skills catalog, then run:

   ```sh
   <python-with-dependencies> <skill-dir>/scripts/font_pipeline.py \
     <project>/font-manifest.json --output-dir <project>/output
   ```

   The script crops fixed grid cells, removes disconnected image-generation
   dust, traces alpha masks with Potrace, converts cubic paths to TrueType
   quadratics, compiles TTF/WOFF2, renders a specimen, and validates the cmap,
   outlines, metrics, and WOFF2 round-trip.
8. **Review the specimen, not isolated glyphs.** Check repeated letters, common
   pairs, similar forms (`I/J/L`, `O/Q`, `P/R`, `V/W`), rhythm, joins, and
   legibility at the intended size. Iterate only on demonstrated problems.
9. **Deliver the full project.** Report the atlas, extracted PNG/SVG glyphs,
   TTF, WOFF2, specimen, manifest, prompt, and build report. Clearly distinguish
   a feasibility prototype from a production-ready family.

## Tooling

The compiler requires Python, the packages in
[`scripts/requirements.txt`](scripts/requirements.txt), and the `potrace`
executable on `PATH`. Prefer a project-local virtual environment. Install only
missing dependencies, and run the actual pipeline after installation.

Use [`scripts/make_grid_template.py`](scripts/make_grid_template.py) when the
image model repeatedly omits, duplicates, or reorders glyphs. The template is a
structural reference, not the finished design.

For ordinary direct image generation, follow the available image-generation
skill. If the user explicitly requests an API/CLI implementation, also follow
the current OpenAI documentation and API-key credential-gate skills before any
API-backed build or call. Never print or copy an API key.

## Non-negotiable invariants

- Keep a known mapping from grid cell to Unicode character.
- Request transparency during generation; do not depend on background removal
  when real alpha output is available.
- Use codepoint-based intermediate filenames. `A.png` and `a.png` collide on
  common case-insensitive filesystems.
- Preserve aspect ratio and one scale per atlas. Do not normalize each glyph
  independently; doing so destroys the shared hand.
- A normal outline font has no intrinsic blue/black color. Color belongs to the
  specimen or consuming application unless the user explicitly requests a color
  font.
- Do not claim originality clearance, trademark clearance, or production
  readiness merely because the pipeline succeeded.
