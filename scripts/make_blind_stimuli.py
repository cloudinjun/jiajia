"""Build anonymized stimuli for a blind animation-recognition round.

The first round (docs/research/blind-animation-recognition-2026-08-27.md) was
assembled by hand and the temporary files were thrown away, which means the
result could not be reproduced or compared against. This script is that
protocol, written down: same sampling, same anonymization, same layout, so a
second round measures the animation rather than the setup.

What it does, per action:
  - samples N evenly-spaced frames across the whole GIF
  - crops off the caption strip, so the action name cannot leak
  - writes the frames both individually (for local models that take images
    one at a time) and as a single contact sheet (for chat UIs)
  - assigns letters in a shuffled order and writes the key to a separate file

The key is written to key.json, which the operator should not open until after
collecting responses. Everything lands in a directory you can delete.

    python scripts/make_blind_stimuli.py
    python scripts/make_blind_stimuli.py --actions error_autopsy thinking_loop
    python scripts/make_blind_stimuli.py --frames 8 --out ../round2
"""
from __future__ import annotations

import argparse
import json
import random
import string
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GIF_DIR = REPO_ROOT / "docs" / "media" / "actions"

# The four agent states round one covered. Kept as the default so a rerun is
# comparable without having to remember the list.
DEFAULT_ACTIONS = (
    "error_autopsy",
    "thinking_loop",
    "permission_request",
    "waiting_stare",
)

# The renderer draws "Label · action_name" in a strip at the bottom. Cropping a
# fixed band is cruder than measuring it, but it is the same band for every GIF
# the generator produces, and over-cropping only loses empty margin.
CAPTION_STRIP_PX = 34


def _sample_frames(path: Path, count: int):
    from PIL import Image

    with Image.open(path) as im:
        total = getattr(im, "n_frames", 1)
        if total < count:
            raise SystemExit(f"{path.name} has only {total} frames; asked for {count}")
        # Evenly spaced across the whole animation, endpoints included, so the
        # sheet shows the arc rather than clustering at the start.
        picks = [round(i * (total - 1) / (count - 1)) for i in range(count)]
        frames = []
        for index in picks:
            im.seek(index)
            frame = im.convert("RGB")
            width, height = frame.size
            frames.append(frame.crop((0, 0, width, max(1, height - CAPTION_STRIP_PX))))
        return frames


def _contact_sheet(frames, columns: int):
    from PIL import Image

    cell_w, cell_h = frames[0].size
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), "white")
    for i, frame in enumerate(frames):
        sheet.paste(frame, ((i % columns) * cell_w, (i // columns) * cell_h))
    return sheet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actions", nargs="+", default=list(DEFAULT_ACTIONS))
    parser.add_argument("--frames", type=int, default=8, help="frames sampled per action")
    parser.add_argument("--columns", type=int, default=4, help="contact sheet columns")
    parser.add_argument("--out", default=None, help="output directory (default: a sibling of the repo)")
    parser.add_argument("--seed", type=int, default=None, help="fix the letter shuffle for a reproducible round")
    args = parser.parse_args(argv)

    try:
        import PIL  # noqa: F401
    except ImportError:
        raise SystemExit("Pillow is required: python -m pip install \".[media]\"") from None

    out = Path(args.out) if args.out else REPO_ROOT.parent / "jiajia-blind-stimuli"
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    order = list(args.actions)
    rng.shuffle(order)
    letters = string.ascii_uppercase[: len(order)]

    key = {}
    for letter, action in zip(letters, order, strict=True):
        gif = GIF_DIR / f"{action}.gif"
        if not gif.exists():
            raise SystemExit(f"no GIF for {action!r}; run scripts/generate_action_gifs.py first")

        frames = _sample_frames(gif, args.frames)
        stem = out / letter
        stem.mkdir(exist_ok=True)
        for i, frame in enumerate(frames, start=1):
            frame.save(stem / f"{letter}{i}.png")
        _contact_sheet(frames, args.columns).save(out / f"{letter}.png")
        key[letter] = action

    (out / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")

    prompt = (
        "You will see frames sampled in order from one short animation of a\n"
        "paperclip character. Reading order is left to right, top row first.\n\n"
        "Report, without being given any candidate answers:\n"
        "  1. first_reading   - what the character is doing, in your own words\n"
        "  2. system_state    - what state a computer showing this would be in\n"
        "  3. confidence      - 0-100\n"
        "  4. alternative     - the next most likely reading\n"
        "  5. evidence        - the visual details you used\n\n"
        "Answer for this set only. Do not compare it to any other set.\n"
    )
    (out / "prompt.txt").write_text(prompt, encoding="utf-8")

    print(f"wrote {len(order)} anonymized stimuli to {out}")
    print(f"  {args.frames} frames each, {CAPTION_STRIP_PX}px caption strip cropped")
    print(f"  per-frame PNGs in {'/'.join(letters)}/, contact sheets as {letters[0]}.png ...")
    print("  prompt.txt holds the question; key.json holds the answers")
    print("\nDo not open key.json until responses are collected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
