#!/usr/bin/env python3
"""Create a transparent neutral glyph-grid reference image."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def parse_size(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError("size must look like 2048x1152") from error
    if width < 256 or height < 256:
        raise argparse.ArgumentTypeError("both dimensions must be at least 256")
    return width, height


def choose_font(size: int, explicit: Path | None) -> ImageFont.FreeTypeFont:
    candidates = [
        explicit,
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return ImageFont.truetype(candidate, size=size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default(size=size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--characters", required=True)
    parser.add_argument("--columns", type=int, required=True)
    parser.add_argument("--rows", type=int)
    parser.add_argument("--size", type=parse_size, default=(2048, 1152))
    parser.add_argument("--font", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.columns < 1:
        parser.error("columns must be positive")
    rows = args.rows or math.ceil(len(args.characters) / args.columns)
    if rows < 1 or rows * args.columns < len(args.characters):
        parser.error("grid has fewer cells than characters")

    width, height = args.size
    cell_width = width / args.columns
    cell_height = height / rows
    font = choose_font(round(cell_height * 0.58), args.font)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    for index, character in enumerate(args.characters):
        row, col = divmod(index, args.columns)
        center_x = (col + 0.5) * cell_width
        center_y = (row + 0.5) * cell_height
        draw.text(
            (center_x, center_y),
            character,
            font=font,
            fill=(20, 20, 20, 255),
            anchor="mm",
            stroke_width=0,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
