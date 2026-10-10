#!/usr/bin/env python3
"""Compile transparent grid atlases into a prototype TTF/WOFF2 font.

The input contract is documented in ../references/manifest.md. Potrace performs
the bitmap-to-Bezier conversion; FontTools builds and validates the font.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
from collections import deque
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path.parser import parse_path
from fontTools.ttLib import TTFont


POTRACE_UNITS_PER_PIXEL = 10.0
DEFAULT_UNITS_PER_EM = 1000
DEFAULT_ASCENT = 820
DEFAULT_DESCENT = -220


def fail(message: str) -> None:
    raise ValueError(message)


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if not isinstance(data.get("family_name"), str) or not data["family_name"].strip():
        fail("manifest requires a non-empty family_name")
    atlases = data.get("atlases")
    if not isinstance(atlases, list) or not atlases:
        fail("manifest requires a non-empty atlases array")

    seen_chars: set[str] = set()
    seen_names: set[str] = set()
    manifest_dir = path.parent.resolve()

    for atlas in atlases:
        if not isinstance(atlas, dict):
            fail("every atlas entry must be an object")
        name = atlas.get("name")
        characters = atlas.get("characters")
        if not isinstance(name, str) or not name:
            fail("every atlas requires a unique non-empty name")
        if name in seen_names:
            fail(f"duplicate atlas name: {name}")
        seen_names.add(name)
        if not isinstance(characters, str) or not characters:
            fail(f"atlas {name} requires a non-empty characters string")
        if " " in characters:
            fail(f"atlas {name}: omit space from visual characters; space is generated")
        duplicates = seen_chars.intersection(characters)
        if duplicates:
            fail(f"characters repeated across atlases: {sorted(duplicates)!r}")
        if len(set(characters)) != len(characters):
            fail(f"atlas {name} repeats a character")
        seen_chars.update(characters)

        columns = atlas.get("columns")
        rows = atlas.get("rows")
        if not isinstance(columns, int) or not isinstance(rows, int) or columns < 1 or rows < 1:
            fail(f"atlas {name}: columns and rows must be positive integers")
        if columns * rows < len(characters):
            fail(f"atlas {name}: grid has fewer cells than characters")
        raw_path = atlas.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            fail(f"atlas {name} requires path")
        resolved = Path(raw_path)
        if not resolved.is_absolute():
            resolved = manifest_dir / resolved
        atlas["_resolved_path"] = str(resolved.resolve())

    lines = data.get("specimen_lines")
    if lines is not None:
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            fail("specimen_lines must be an array of strings")
        unsupported = set("".join(lines)) - seen_chars - {" "}
        if unsupported:
            fail(f"specimen_lines contain characters absent from the font: {sorted(unsupported)!r}")

    data["_characters"] = "".join(atlas["characters"] for atlas in atlases)
    return data


def connected_components(mask: np.ndarray) -> list[tuple[int, np.ndarray]]:
    """Return 8-connected components sorted by descending area."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, np.ndarray]] = []

    for start_y, start_x in zip(*np.nonzero(mask)):
        if seen[start_y, start_x]:
            continue
        queue = deque([(int(start_y), int(start_x))])
        seen[start_y, start_x] = True
        points: list[tuple[int, int]] = []
        while queue:
            y, x = queue.popleft()
            points.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and mask[ny, nx]
                        and not seen[ny, nx]
                    ):
                        seen[ny, nx] = True
                        queue.append((ny, nx))
        coords = np.asarray(points, dtype=np.int32)
        components.append((len(points), coords))
    return sorted(components, key=lambda item: item[0], reverse=True)


def clean_glyph(
    cell: Image.Image, alpha_threshold: int
) -> tuple[Image.Image, np.ndarray, tuple[int, int, int, int], int]:
    rgba = np.asarray(cell.convert("RGBA")).copy()
    initial = rgba[:, :, 3] >= alpha_threshold
    components = connected_components(initial)
    if not components:
        fail("a mapped cell contains no visible glyph")

    largest_area = components[0][0]
    # Dust filtering must not discard the main component of a small glyph.
    minimum_area = min(largest_area, max(24, round(largest_area * 0.018)))
    kept = [coords for area, coords in components if area >= minimum_area]
    mask = np.zeros_like(initial, dtype=bool)
    for coords in kept:
        mask[coords[:, 0], coords[:, 1]] = True

    ys, xs = np.nonzero(mask)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    rgba[:, :, 3] = np.where(mask, rgba[:, :, 3], 0)
    return Image.fromarray(rgba, mode="RGBA"), mask, bbox, len(kept)


def trace_mask(mask: np.ndarray, pgm_path: Path, svg_path: Path) -> None:
    bitmap = np.where(mask, 0, 255).astype(np.uint8)
    Image.fromarray(bitmap, mode="L").save(pgm_path)
    subprocess.run(
        [
            "potrace",
            str(pgm_path),
            "--svg",
            "--output",
            str(svg_path),
            "--turdsize",
            "12",
            "--alphamax",
            "1.0",
            "--opttolerance",
            "0.35",
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def raw_recording_from_potrace(svg_path: Path) -> tuple[RecordingPen, tuple[float, float, float, float]]:
    """Read raw path units, intentionally excluding Potrace's wrapper transform."""
    root = ElementTree.fromstring(svg_path.read_bytes())
    pen = RecordingPen()
    path_count = 0
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "path" and element.get("d"):
            parse_path(element.get("d"), pen)
            path_count += 1
    if path_count == 0:
        fail(f"Potrace produced no path in {svg_path}")
    bounds_pen = BoundsPen(None)
    pen.replay(bounds_pen)
    if bounds_pen.bounds is None:
        fail(f"no contour bounds in {svg_path}")
    return pen, bounds_pen.bounds


def codepoint_stem(character: str) -> str:
    width = 4 if ord(character) <= 0xFFFF else 6
    return f"u{ord(character):0{width}X}"


def glyph_name(character: str) -> str:
    width = 4 if ord(character) <= 0xFFFF else 6
    prefix = "uni" if width == 4 else "u"
    return f"{prefix}{ord(character):0{width}X}"


def empty_glyph():
    return TTGlyphPen(None).glyph()


def ps_safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9-]+", "", value.replace(" ", "-"))
    return cleaned or "GeneratedFont"


def extract_and_trace(
    manifest: dict[str, Any], output_dir: Path
) -> list[dict[str, Any]]:
    glyph_dir = output_dir / "glyphs"
    png_dir = glyph_dir / "png"
    mask_dir = glyph_dir / "mask"
    svg_dir = glyph_dir / "svg"
    for directory in (png_dir, mask_dir, svg_dir):
        directory.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for atlas_spec in manifest["atlases"]:
        atlas_path = Path(atlas_spec["_resolved_path"])
        if not atlas_path.is_file():
            fail(f"atlas not found: {atlas_path}")
        source = Image.open(atlas_path)
        atlas = source.convert("RGBA")
        alpha_low, alpha_high = atlas.getchannel("A").getextrema()
        if alpha_low == alpha_high:
            fail(f"atlas {atlas_spec['name']} has no varying alpha channel")
        if alpha_low > 0:
            fail(f"atlas {atlas_spec['name']} has no fully transparent pixels")

        columns = atlas_spec["columns"]
        rows = atlas_spec["rows"]
        x_edges = [round(index * atlas.width / columns) for index in range(columns + 1)]
        y_edges = [round(index * atlas.height / rows) for index in range(rows + 1)]
        atlas_records: list[dict[str, Any]] = []

        for index, character in enumerate(atlas_spec["characters"]):
            row, col = divmod(index, columns)
            cell_box = (x_edges[col], y_edges[row], x_edges[col + 1], y_edges[row + 1])
            cell = atlas.crop(cell_box)
            threshold = int(atlas_spec.get("alpha_threshold", 36))
            cleaned, mask, bbox, component_count = clean_glyph(cell, threshold)
            stem = codepoint_stem(character)
            png_path = png_dir / f"{stem}.png"
            pgm_path = mask_dir / f"{stem}.pgm"
            svg_path = svg_dir / f"{stem}.svg"
            cleaned.save(png_path)
            trace_mask(mask, pgm_path, svg_path)
            record = {
                "character": character,
                "codepoint": f"U+{ord(character):04X}",
                "glyph_name": glyph_name(character),
                "atlas": atlas_spec["name"],
                "row": row,
                "col": col,
                "cell_box": list(cell_box),
                "cell_size": list(cell.size),
                "bbox": list(bbox),
                "ink_pixels": int(mask.sum()),
                "component_count": component_count,
                "svg_path": str(svg_path),
            }
            records.append(record)
            atlas_records.append(record)

        baseline_inset = float(atlas_spec.get("baseline_inset", 7))
        row_baselines: dict[int, float] = {}
        for row in range(rows):
            bottoms = [record["bbox"][3] for record in atlas_records if record["row"] == row]
            if bottoms:
                row_baselines[row] = statistics.median(bottoms) - baseline_inset
        height_samples = [
            row_baselines[record["row"]] - record["bbox"][1]
            for record in atlas_records
        ]
        source_height = statistics.median(height_samples)
        if source_height <= 0:
            fail(f"atlas {atlas_spec['name']} produced an invalid height estimate")
        target_height = float(atlas_spec.get("target_height", 700))
        atlas_scale = target_height / source_height
        for record in atlas_records:
            cell_height = record["cell_size"][1]
            record["baseline_source_y"] = (
                cell_height - row_baselines[record["row"]]
            ) * POTRACE_UNITS_PER_PIXEL
            record["font_scale"] = atlas_scale / POTRACE_UNITS_PER_PIXEL
            record["atlas_source_height"] = source_height
            record["atlas_target_height"] = target_height

    return records


def build_font(
    manifest: dict[str, Any], records: list[dict[str, Any]], output_dir: Path
) -> tuple[Path, Path | None]:
    build_dir = output_dir / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    units_per_em = int(manifest.get("units_per_em", DEFAULT_UNITS_PER_EM))
    ascent = int(manifest.get("ascent", DEFAULT_ASCENT))
    descent = int(manifest.get("descent", DEFAULT_DESCENT))
    left_bearing = int(manifest.get("left_bearing", 12))
    right_bearing = int(manifest.get("right_bearing", 6))
    space_width = int(manifest.get("space_width", 330))

    glyph_order = [".notdef", "space", *(record["glyph_name"] for record in records)]
    glyphs = {".notdef": empty_glyph(), "space": empty_glyph()}
    metrics = {".notdef": (600, 0), "space": (space_width, 0)}
    cmap = {32: "space"}

    for record in records:
        source_pen, bounds = raw_recording_from_potrace(Path(record["svg_path"]))
        min_x, _min_y, max_x, _max_y = bounds
        font_scale = record["font_scale"]
        transform = (
            font_scale,
            0,
            0,
            font_scale,
            left_bearing - min_x * font_scale,
            -record["baseline_source_y"] * font_scale,
        )
        glyph_pen = TTGlyphPen(None)
        quadratic_pen = Cu2QuPen(glyph_pen, max_err=1.0, reverse_direction=False)
        source_pen.replay(TransformPen(quadratic_pen, transform))
        name = record["glyph_name"]
        glyphs[name] = glyph_pen.glyph()
        advance = round((max_x - min_x) * font_scale + left_bearing + right_bearing)
        metrics[name] = (max(advance, 120), left_bearing)
        cmap[ord(record["character"])] = name
        record["source_bounds"] = [round(value, 3) for value in bounds]
        record["advance_width"] = metrics[name][0]

    family = manifest["family_name"].strip()
    style = str(manifest.get("style_name", "Regular")).strip() or "Regular"
    version = str(manifest.get("version", "0.1"))
    base_name = f"{ps_safe(family)}-{ps_safe(style)}"
    ttf_path = build_dir / f"{base_name}.ttf"

    builder = FontBuilder(units_per_em, isTTF=True)
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=ascent, descent=descent)
    builder.setupNameTable(
        {
            "familyName": family,
            "styleName": style,
            "uniqueFontIdentifier": f"{base_name}-Prototype-{version}",
            "fullName": f"{family} {style}",
            "psName": base_name,
            "version": f"Version {version}; generated atlas prototype",
        }
    )
    builder.setupOS2(
        sTypoAscender=ascent,
        sTypoDescender=descent,
        usWinAscent=max(ascent, 0),
        usWinDescent=abs(min(descent, 0)),
        sxHeight=int(manifest.get("x_height", 500)),
        sCapHeight=int(manifest.get("cap_height", 700)),
    )
    builder.setupPost()
    builder.setupMaxp()
    builder.save(ttf_path)

    woff2_path: Path | None = build_dir / f"{base_name}.woff2"
    try:
        web_font = TTFont(ttf_path)
        web_font.flavor = "woff2"
        web_font.save(woff2_path)
    except ImportError:
        woff2_path = None
    return ttf_path, woff2_path


def default_specimen_lines(manifest: dict[str, Any]) -> list[str]:
    characters = manifest["_characters"]
    title = "".join(character for character in manifest["family_name"].upper() if character in characters or character == " ")
    lines = [title] if title.strip() else []
    lines.extend(characters[index : index + 26] for index in range(0, len(characters), 26))
    return [line for line in lines if line]


def fit_font(font_path: Path, text: str, target_width: int, max_size: int) -> ImageFont.FreeTypeFont:
    size = max_size
    while size > 20:
        font = ImageFont.truetype(font_path, size=size)
        if font.getlength(text) <= target_width:
            return font
        size -= 2
    return ImageFont.truetype(font_path, size=size)


def render_specimen(manifest: dict[str, Any], font_path: Path, output_dir: Path) -> Path:
    lines = manifest.get("specimen_lines") or default_specimen_lines(manifest)
    width = 2200
    height = max(900, 330 + len(lines) * 210)
    paper = manifest.get("background_color", "#F4EFE6")
    ink = manifest.get("ink_color", "#123DD6")
    image = Image.new("RGB", (width, height), paper)
    draw = ImageDraw.Draw(image)
    ui = ImageFont.load_default(size=26)
    ui_small = ImageFont.load_default(size=20)
    label = f"{manifest['family_name']} / PROTOTYPE {manifest.get('version', '0.1')}"
    draw.text((100, 65), label.upper(), fill="#756F67", font=ui)
    draw.text((width - 100, 70), "GENERATED · TRACED · COMPILED", fill="#756F67", font=ui_small, anchor="ra")
    draw.line((100, 115, width - 100, 115), fill="#CCC4B9", width=2)

    y = 175
    for index, line in enumerate(lines):
        max_size = 235 if index == 0 else 150
        font = fit_font(font_path, line, width - 200, max_size)
        draw.text((100, y), line, fill=ink, font=font)
        y += 250 if index == 0 else 195

    specimen_path = output_dir / "build" / f"{ps_safe(manifest['family_name'])}-specimen.png"
    image.save(specimen_path)
    return specimen_path


def validate_font(
    manifest: dict[str, Any], font_path: Path, woff2_path: Path | None
) -> dict[str, Any]:
    expected_codepoints = {32, *(ord(character) for character in manifest["_characters"])}
    expected_glyphs = len(expected_codepoints) + 1  # plus .notdef
    checked: list[str] = []
    for path in [font_path, woff2_path]:
        if path is None:
            continue
        font = TTFont(path)
        if set(font.getBestCmap()) != expected_codepoints:
            fail(f"cmap mismatch in {path}")
        if font["maxp"].numGlyphs != expected_glyphs:
            fail(f"glyph-count mismatch in {path}")
        for character in manifest["_characters"]:
            name = font.getBestCmap()[ord(character)]
            glyph = font["glyf"][name]
            if glyph.numberOfContours <= 0:
                fail(f"empty outline for {character!r} in {path}")
            if glyph.yMin < -4000 or glyph.yMax > 4000 or glyph.xMax - glyph.xMin > 6000:
                fail(f"implausible outline scale for {character!r} in {path}")
        checked.append(path.suffix.lstrip(".").upper())
    return {
        "status": "PASS",
        "formats_checked": checked,
        "mapped_codepoints": len(expected_codepoints),
        "outline_glyphs": len(manifest["_characters"]),
    }


def run(manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    if shutil.which("potrace") is None:
        fail("potrace is required on PATH")
    manifest = load_manifest(manifest_path.resolve())
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    records = extract_and_trace(manifest, output_dir)
    font_path, woff2_path = build_font(manifest, records, output_dir)
    specimen_path = render_specimen(manifest, font_path, output_dir)
    validation = validate_font(manifest, font_path, woff2_path)
    report = {
        "family_name": manifest["family_name"],
        "style_name": manifest.get("style_name", "Regular"),
        "font": str(font_path),
        "woff2": str(woff2_path) if woff2_path else None,
        "specimen": str(specimen_path),
        "validation": validation,
        "glyphs": records,
    }
    report_path = output_dir / "build" / "build-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    result = run(args.manifest, args.output_dir)
    print(json.dumps({key: value for key, value in result.items() if key != "glyphs"}, indent=2))
