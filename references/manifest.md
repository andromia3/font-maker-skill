# Font manifest

The deterministic compiler accepts one JSON manifest and one or more atlas PNGs.
Resolve relative atlas paths against the manifest's directory.

## Example

```json
{
  "family_name": "Blue Thread",
  "style_name": "Regular",
  "version": "0.1",
  "ink_color": "#123DD6",
  "background_color": "#F4EFE6",
  "space_width": 330,
  "left_bearing": 12,
  "right_bearing": 6,
  "atlases": [
    {
      "name": "uppercase",
      "path": "assets/uppercase-atlas.png",
      "characters": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
      "columns": 7,
      "rows": 4,
      "target_height": 700,
      "baseline_inset": 7,
      "alpha_threshold": 36
    }
  ],
  "specimen_lines": [
    "BLUE THREAD",
    "QUICK BROWN FOX",
    "PACK MY BOX WITH FIVE DOZEN JUGS"
  ]
}
```

## Fields

Top level:

- `family_name` required; human-facing family name.
- `style_name` optional, default `Regular`.
- `version` optional, default `0.1`.
- `ink_color` and `background_color` affect only the specimen PNG.
- `space_width`, `left_bearing`, `right_bearing` are font units.
- `units_per_em`, `ascent`, and `descent` may override defaults `1000`, `820`,
  and `-220`.
- `atlases` required, non-empty.
- `specimen_lines` optional. If omitted, the compiler creates proof lines from
  the available repertoire.

Each atlas:

- `name` required and unique.
- `path` required PNG path.
- `characters` required ordered Unicode string, one code point per occupied
  cell; do not include empty final cells or space.
- `columns` and `rows` required and must have enough cells.
- `target_height` optional; default `700`. Use about `700` for uppercase, `500`
  for lowercase x-height, and `650` for figures/symbols.
- `baseline_inset` optional, default `7` source pixels. It places the estimated
  baseline slightly above the median bottom edge of non-descending shapes.
- `alpha_threshold` optional, default `36` on a `0–255` alpha channel.

Characters must not repeat across atlases. Intermediate assets use Unicode
codepoint filenames such as `u0041.png` and `u0061.png`, which remain distinct on
case-insensitive filesystems.
