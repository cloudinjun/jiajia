"""Render a curated gallery of Jiajia's real Chinese roast lines.

Every demo points to an entry ID in ``jiajia/locales/zh_seeds.yaml`` so the
public GIF copy cannot silently drift away from the runtime line bank.

    python scripts/generate_quote_gifs.py
    python scripts/generate_quote_gifs.py --check
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from PIL import Image, ImageDraw

from generate_demo_gifs import (
    BROW,
    CODEX,
    FRAME_MS,
    SS,
    USAGE,
    load_text_font,
    render_frame,
    save_gif,
    talk_level,
)


SOURCE_PATH = REPO_ROOT / "jiajia" / "locales" / "zh_seeds.yaml"
DEFAULT_OUT = REPO_ROOT / "docs" / "media" / "quotes"
RENDER_VERSION = 1
QUOTE_FRAMES = 64


@dataclass(frozen=True)
class QuoteDemo:
    slug: str
    source_id: str
    scene: str
    accent: str


QUOTE_DEMOS = (
    QuoteDemo("professional-truth", "22deccb74a7f5339", "自我介绍", BROW),
    QuoteDemo("encouragement-no-evidence", "635589d8ae6b585c", "虚假鼓励", USAGE),
    QuoteDemo("working-not-starting", "3b0fbf1fa82bdcc2", "拖延", "#d97757"),
    QuoteDemo("deadline-waiting", "5c27c592d0279a0e", "Deadline", "#d97757"),
    QuoteDemo("blank-document-filename", "a3729b6430c99dc7", "空白文档", USAGE),
    QuoteDemo("todo-you-present", "6627827b35c43e5f", "TODO", "#d97757"),
    QuoteDemo("window-switching-escape", "6968a5fc6d094399", "窗口切换", USAGE),
    QuoteDemo("twelve-tabs", "03922166461afea8", "浏览器研究", USAGE),
    QuoteDemo("negative-code-output", "82eb16789502be99", "写代码", CODEX),
    QuoteDemo("two-ai-one-human", "708018774250152d", "AI 协作", CODEX),
    QuoteDemo("late-night-control", "7fec497d89bc4df9", "深夜工作", "#6b5b95"),
    QuoteDemo("poke-vs-task", "bf6de2cf5a14a472", "戳夹夹", BROW),
    QuoteDemo("save-anxiety-icon", "2544bb7dc961ce3a", "冷知识", USAGE),
    QuoteDemo("final-final-v3", "8d02d0ee5c255479", "文件命名", "#d97757"),
)


def load_source_entries() -> dict[str, dict[str, object]]:
    data = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return {
        str(entry["id"]): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }


def selected_entries() -> dict[str, dict[str, object]]:
    source = load_source_entries()
    missing = [demo.source_id for demo in QUOTE_DEMOS if demo.source_id not in source]
    if missing:
        raise ValueError(f"quote demo source IDs missing from {SOURCE_PATH}: {missing}")
    return {demo.slug: source[demo.source_id] for demo in QUOTE_DEMOS}


def wrap_quote(text: str, max_width: int = 238) -> str:
    font = load_text_font(text, 16)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    current = ""
    closing = "，。！？；：、,.!?;:)）]】"
    for char in text:
        candidate = current + char
        if current and measure.textlength(candidate, font=font) > max_width * SS and char not in closing:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    if len(lines) > 2:
        raise ValueError(f"quote needs more than two lines: {text!r}")
    return "\n".join(lines)


def render_quote(demo: QuoteDemo, entry: dict[str, object]) -> list[Image.Image]:
    text = wrap_quote(str(entry["line"]))
    bubble = str(entry.get("bubble") or "speech")
    action_key = str(entry.get("action") or "blink")
    mood = str(entry.get("mood") or "smirk")
    frames: list[Image.Image] = []

    for index in range(QUOTE_FRAMES):
        phase = index / QUOTE_FRAMES
        body, eye, brows, tail = quote_pose(action_key, mood, phase, index)
        frames.append(
            render_frame(
                action=body,
                eye=eye,
                brows=brows,
                tail_wag=tail,
                bubble=(bubble, text, demo.accent),
                talk_level=talk_level(phase) if bubble == "speech" and index < 42 else 0,
            )
        )
    return frames


def quote_pose(
    action_key: str,
    mood: str,
    phase: float,
    frame_index: int,
) -> tuple[tuple[float, float, float, float], str, str, float]:
    cycle = math.sin(phase * math.tau)
    syllable = math.sin(phase * math.tau * 8)
    body = (cycle * 0.7, -abs(syllable) * 1.2, 1.0, 1.0)

    if action_key == "smug_sway":
        body = (cycle * 5.0, 1.0, 1.0 + cycle * 0.018, 1.0 - cycle * 0.012)
    elif action_key == "thinking_tilt":
        body = (-4.0 + cycle * 1.8, 1.5 + cycle * 0.8, 0.95, 1.05)
    elif action_key == "scan":
        body = (cycle * 2.0, 0.0, 1.0, 1.0)
    elif action_key == "nod":
        nod = abs(math.sin(phase * math.tau * 2))
        body = (0.0, nod * 3.2, 1.0 + nod * 0.012, 1.0 - nod * 0.018)
    elif action_key == "sleepy_sag":
        body = (cycle * 0.5, 8.0 + cycle * 2.0, 1.03, 0.90)
    elif action_key == "wiggle":
        body = (math.sin(phase * math.tau * 3) * 2.8, 0.0, 0.99, 1.01)

    eye = {
        "innocent": "wide",
        "smug": "side_eye",
        "smirk": "side_eye",
        "suspicious": "side_eye",
        "thinking": "neutral",
        "guilty": "wide",
        "sleepy": "sleepy",
    }.get(mood, "round")
    brows = {
        "innocent": "innocent",
        "smug": "judge",
        "smirk": "judge",
        "suspicious": "judge",
        "thinking": "soft",
        "guilty": "guilty",
        "sleepy": "asleep",
    }.get(mood, "soft")
    if frame_index in {44, 45} and eye != "sleepy":
        eye = "blink"

    tail_amplitude = 5.0 if mood in {"smug", "smirk"} else 2.5
    tail = math.sin(phase * math.tau * 2) * tail_amplitude
    return body, eye, brows, tail


def quote_signature(demo: QuoteDemo, entry: dict[str, object]) -> str:
    values = (
        demo.slug,
        demo.source_id,
        demo.scene,
        demo.accent,
        str(entry.get("line") or ""),
        str(entry.get("mood") or ""),
        str(entry.get("action") or ""),
        str(entry.get("bubble") or ""),
        str(RENDER_VERSION),
        str(QUOTE_FRAMES),
        str(FRAME_MS),
    )
    return hashlib.sha256("|".join(values).encode("utf-8")).hexdigest()[:16]


def build_manifest(entries: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    chosen = entries or selected_entries()
    return {
        "render_version": RENDER_VERSION,
        "frame_ms": FRAME_MS,
        "quotes": {
            demo.slug: {
                "source_id": demo.source_id,
                "signature": quote_signature(demo, chosen[demo.slug]),
            }
            for demo in QUOTE_DEMOS
        },
    }


def write_index(out_dir: Path, entries: dict[str, dict[str, object]]) -> None:
    lines = [
        "# Jiajia Roast GIFs",
        "",
        "Generated from the live Chinese line bank.",
        "",
        "| Scene | Preview |",
        "|---|---|",
    ]
    for demo in QUOTE_DEMOS:
        quote = str(entries[demo.slug]["line"])
        lines.append(f"| {demo.scene} | ![{quote}]({demo.slug}.gif) |")
    lines += [
        "",
        "Regenerate: `python scripts/generate_quote_gifs.py`",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def check_outputs(out_dir: Path, expected: dict[str, object]) -> int:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"stale: no manifest at {manifest_path}")
        return 1
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if current != expected:
        problems.append("manifest does not match the selected line-bank entries")
    for demo in QUOTE_DEMOS:
        if not (out_dir / f"{demo.slug}.gif").exists():
            problems.append(f"missing GIF: {demo.slug}.gif")
    if problems:
        print("\n".join(f"- {problem}" for problem in problems))
        print("run: python scripts/generate_quote_gifs.py")
        return 1
    print(f"in sync — {len(QUOTE_DEMOS)} quote GIFs")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Jiajia roast quote GIFs.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    entries = selected_entries()
    expected = build_manifest(entries)
    if args.check:
        return check_outputs(args.out, expected)

    args.out.mkdir(parents=True, exist_ok=True)
    for demo in QUOTE_DEMOS:
        frames = render_quote(demo, entries[demo.slug])
        save_gif(frames, args.out / f"{demo.slug}.gif", disposal=2)
        print(f"{demo.slug:28s} {len(frames) * FRAME_MS / 1000:.1f}s")

    expected_slugs = {demo.slug for demo in QUOTE_DEMOS}
    for gif in args.out.glob("*.gif"):
        if gif.stem not in expected_slugs:
            gif.unlink()
            print(f"removed stale {gif.name}")

    (args.out / "manifest.json").write_text(
        json.dumps(expected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_index(args.out, entries)
    print(f"wrote {len(QUOTE_DEMOS)} quote GIFs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
