# Paperclip Pal Native Decoration Style v1

Paperclip Pal decorations should look like small doodles that belong to the
paperclip character, not like UI toolbar icons attached to a floating widget.
Imported icon packs may be used directly when they already match the native
Canvas/SVG doodle style.

## Core Rule

Every decoration must feel like it was drawn with the same soft marker that drew
the paperclip: round, low-detail, slightly handmade, and subordinate to the
eyes, brows, and wire body.

## Stroke System

- Main accessory stroke: `2.5`
- Detail stroke: `1.5`
- Always use round caps and round joins for lines.
- Avoid hard rectangles. Use rounded cards, capsules, loops, and soft marks.
- Avoid font glyphs inside decorations. Replace `>`, `!`, and `Z` with drawn
  marks.

## Color System

- The body stays gray/white with dark brown eyes and brows.
- Each identity gets one accent color at a time.
- Decoration fill should usually be near-white paper: `#fffdfd`.
- Do not mix multiple strong accent colors on the same identity prop.

## Complexity Budget

Each small decoration should have at most:

- One main silhouette.
- One or two internal marks.
- No tiny text.
- No detailed product-icon structure.

## Decoration Classes

- `identity_prop`: persistent prop that says what role the pal is cosplaying.
- `state_mark`: light, temporary mark that says what is happening now.
- `performance_accent`: short-lived acting effect tied to a performance phrase.

An identity should normally have one resident prop. Temporary marks can appear
when the event requires them, but they should not stack into a HUD.

## First Native Pass

The first pass standardizes these runtime decorations:

- `tiny_terminal`: rounded terminal sticker, no text glyphs.
- `tiny_checklist`: soft paper scrap with drawn checks.
- `thermometer_icon`: chunky round thermometer doodle.
- `tiny_ledger`: small clipped receipt, not a product icon.
- `red_pen`: loose red pen stroke / marker prop.
- `z_symbol`: drawn sleepy zigzag, not a font glyph.
