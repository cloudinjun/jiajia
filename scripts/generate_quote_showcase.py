"""Combine every quote GIF for one language into a single showcase wall.

    python scripts/generate_quote_showcase.py --language en
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw

from generate_demo_gifs import FRAME_MS, STAGE_H, STAGE_W, load_text_font, save_gif
from generate_quote_gifs import (
    GALLERY_FILENAME,
    QUOTE_FRAMES,
    default_out,
    quote_demos,
    selected_entries,
    write_index,
)


GALLERY_COLUMNS = 3
GALLERY_BACKGROUND = "#e8edf2"
BRAND_BACKGROUND = "#202932"
BRAND_ACCENTS = ("#10a37f", "#d97757", "#6b5b95")


def draw_brand_tile(image: Image.Image, tile_index: int, quote_count: int) -> None:
    column = tile_index % GALLERY_COLUMNS
    row = tile_index // GALLERY_COLUMNS
    left = column * STAGE_W
    top = row * STAGE_H
    draw = ImageDraw.Draw(image)
    draw.rectangle((left, top, left + STAGE_W, top + STAGE_H), fill=BRAND_BACKGROUND)

    title_font = load_text_font("JIAJIA", 20)
    count_font = load_text_font(f"{quote_count} ROASTS", 10)
    line_font = load_text_font("ONE CLIP. ZERO FILTER.", 8)
    draw.text((left + 30, top + 106), "JIAJIA", font=title_font, fill="#ffffff")
    draw.text((left + 32, top + 190), f"{quote_count} ROASTS", font=count_font, fill="#c7d1da")
    draw.text((left + 32, top + 234), "ONE CLIP. ZERO FILTER.", font=line_font, fill="#c7d1da")
    for offset, color in enumerate(BRAND_ACCENTS):
        x = left + 32 + offset * 48
        draw.rounded_rectangle((x, top + 292, x + 34, top + 300), radius=4, fill=color)


def build_showcase(source_dir: Path, language: str) -> Path:
    demos = quote_demos(language)
    rows = math.ceil((len(demos) + 1) / GALLERY_COLUMNS)
    size = (GALLERY_COLUMNS * STAGE_W, rows * STAGE_H)
    sources = [Image.open(source_dir / f"{demo.slug}.gif") for demo in demos]
    frames: list[Image.Image] = []

    try:
        for source, demo in zip(sources, demos, strict=True):
            if source.n_frames != QUOTE_FRAMES:
                raise ValueError(
                    f"{demo.slug}.gif has {source.n_frames} frames; expected {QUOTE_FRAMES}"
                )

        for frame_index in range(QUOTE_FRAMES):
            canvas = Image.new("RGB", size, GALLERY_BACKGROUND)
            for tile_index, source in enumerate(sources):
                source.seek(frame_index)
                left = (tile_index % GALLERY_COLUMNS) * STAGE_W
                top = (tile_index // GALLERY_COLUMNS) * STAGE_H
                canvas.paste(source.convert("RGB"), (left, top))
            draw_brand_tile(canvas, len(demos), len(demos))
            frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE))
    finally:
        for source in sources:
            source.close()

    output = source_dir / GALLERY_FILENAME
    save_gif(frames, output, disposal=2)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one GIF containing every Jiajia roast quote.")
    parser.add_argument("--language", choices=("zh", "en"), default="en")
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()

    language: str = args.language
    source_dir: Path = args.source or default_out(language)
    output = build_showcase(source_dir, language)
    write_index(source_dir, selected_entries(language), language)
    print(
        f"wrote {output} ({GALLERY_COLUMNS} columns, {QUOTE_FRAMES} frames, "
        f"{QUOTE_FRAMES * FRAME_MS / 1000:.1f}s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
