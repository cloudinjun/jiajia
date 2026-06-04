# Decoration Assets

This folder is for small decorative accessories only. It should not replace or
modify the Paperclip Pal body asset.

## Layout

- `iconpark/icons/`: curated flat SVG accessories for identities and status
  reactions. These are semantic references, not the target runtime look.
- `iconpark/manifest.yaml`: suggested semantic groups for the imported icons.
- `iconpark/LICENSE-IconPark.txt`: upstream Apache-2.0 license text.
- `NATIVE_STYLE.md`: runtime art direction for decorations that should feel
  native to Paperclip Pal.

## Use

Keep imported assets small and traceable. Prefer adding a few useful icons over
vendoring a full icon pack. If an icon is recolored or converted for runtime
use, keep the source SVG here and put generated runtime files in a separate
clearly named folder.

Runtime decorations should follow `NATIVE_STYLE.md`: soft doodle forms, round
caps/joins, low detail, and one accent color at a time.
