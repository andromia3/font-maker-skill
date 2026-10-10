"""Synthetic alpha-mask checks; no Potrace, font compilation or image generation."""
import importlib.util
from pathlib import Path
import unittest

from PIL import Image, ImageDraw

path = Path(__file__).resolve().parents[1]/'scripts/font_pipeline.py'
spec = importlib.util.spec_from_file_location('font_pipeline', path)
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)

class GlyphCleanup(unittest.TestCase):
    def test_small_main_component_survives(self):
        image = Image.new('RGBA', (16, 16))
        ImageDraw.Draw(image).rectangle((4, 4, 7, 7), fill=(0, 0, 0, 255))
        _, mask, bbox, count = pipeline.clean_glyph(image, 36)
        self.assertEqual(int(mask.sum()), 16)
        self.assertEqual(bbox, (4, 4, 8, 8))
        self.assertEqual(count, 1)

    def test_large_component_still_discards_small_dust(self):
        image = Image.new('RGBA', (32, 32))
        draw = ImageDraw.Draw(image)
        draw.rectangle((4, 4, 23, 23), fill=(0, 0, 0, 255))
        draw.point((30, 30), fill=(0, 0, 0, 255))
        _, mask, bbox, count = pipeline.clean_glyph(image, 36)
        self.assertEqual(int(mask.sum()), 400)
        self.assertEqual(bbox, (4, 4, 24, 24))
        self.assertEqual(count, 1)

    def test_empty_cell_reports_the_intended_error(self):
        with self.assertRaisesRegex(ValueError, 'no visible glyph'):
            pipeline.clean_glyph(Image.new('RGBA', (16, 16)), 36)

if __name__ == '__main__':
    unittest.main()
