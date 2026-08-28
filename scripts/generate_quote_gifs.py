"""Render a curated gallery of Jiajia's real Chinese roast lines.

Every demo points to an entry ID in ``jiajia/locales/zh_seeds.yaml`` so the
public GIF copy cannot silently drift away from the runtime line bank.

    python scripts/generate_quote_gifs.py
    python scripts/generate_quote_gifs.py --language en
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


QUOTE_ROOT = REPO_ROOT / "docs" / "media" / "quotes"
RENDER_VERSION = 1
QUOTE_FRAMES = 64
GALLERY_FILENAME = "jiajia-roast-showcase.gif"


@dataclass(frozen=True)
class QuoteDemo:
    slug: str
    source_id: str
    scene: str
    accent: str


ZH_QUOTE_DEMOS = (
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

EN_QUOTE_DEMOS = (
    QuoteDemo("professional-truth", "009337c56d2c4d7b", "Self-aware", BROW),
    QuoteDemo("encouragement-no-evidence", "7e781ffa1e69e038", "Encouragement", USAGE),
    QuoteDemo("working-not-starting", "19361a260105d690", "Procrastination", "#d97757"),
    QuoteDemo("deadline-waiting", "df3e3165d52307c5", "Deadline", "#d97757"),
    QuoteDemo("blank-document-filename", "364fcda5778a1b2b", "Blank document", USAGE),
    QuoteDemo("todo-you-present", "5f1cc72d2987b719", "TODO", "#d97757"),
    QuoteDemo("window-switching-escape", "d84a3b3348e37740", "Tab switching", USAGE),
    QuoteDemo("twelve-tabs", "0588f03f24e3f46f", "Browser research", USAGE),
    QuoteDemo("negative-code-output", "b6297ce11b0399fd", "Coding", CODEX),
    QuoteDemo("two-ai-one-human", "8417b866bb5d5111", "AI collaboration", CODEX),
    QuoteDemo("late-night-control", "ab7efd32f2629b6c", "Late-night work", "#6b5b95"),
    QuoteDemo("poke-vs-task", "dd2f3c4d1f72a09a", "Poke", BROW),
    QuoteDemo("save-anxiety-icon", "a5ad99a781e9a7ae", "Cold fact", USAGE),
    QuoteDemo("final-final-v3", "06ccedb81ec51bf2", "File naming", "#d97757"),
)


def quote_demos(language: str) -> tuple[QuoteDemo, ...]:
    return EN_QUOTE_DEMOS if language == "en" else ZH_QUOTE_DEMOS


def source_path(language: str) -> Path:
    prefix = "en" if language == "en" else "zh"
    return REPO_ROOT / "jiajia" / "locales" / f"{prefix}_seeds.yaml"


def default_out(language: str) -> Path:
    return QUOTE_ROOT / "en" if language == "en" else QUOTE_ROOT


def load_source_entries(language: str = "zh") -> dict[str, dict[str, object]]:
    path = source_path(language)
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return {
        str(entry["id"]): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }


def selected_entries(language: str = "zh") -> dict[str, dict[str, object]]:
    demos = quote_demos(language)
    source = load_source_entries(language)
    missing = [demo.source_id for demo in demos if demo.source_id not in source]
    if missing:
        raise ValueError(f"quote demo source IDs missing from {source_path(language)}: {missing}")
    return {demo.slug: source[demo.source_id] for demo in demos}


def wrap_quote(text: str, language: str) -> str:
    font_size = 16 if language == "zh" else 15
    max_width = 238 if language == "zh" else 216
    max_lines = 2 if language == "zh" else 3
    font = load_text_font(text, font_size)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    if language == "en":
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and measure.textlength(candidate, font=font) > max_width * SS:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        if len(lines) > max_lines:
            raise ValueError(f"quote needs more than {max_lines} lines: {text!r}")
        return "\n".join(lines)

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
    if len(lines) > max_lines:
        raise ValueError(f"quote needs more than {max_lines} lines: {text!r}")
    return "\n".join(lines)


def render_quote(demo: QuoteDemo, entry: dict[str, object], language: str) -> list[Image.Image]:
    text = wrap_quote(str(entry["line"]), language)
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


def quote_signature(demo: QuoteDemo, entry: dict[str, object], language: str) -> str:
    values = (
        language,
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


def build_manifest(
    entries: dict[str, dict[str, object]] | None = None,
    language: str = "zh",
) -> dict[str, object]:
    demos = quote_demos(language)
    chosen = entries or selected_entries(language)
    return {
        "language": language,
        "render_version": RENDER_VERSION,
        "frame_ms": FRAME_MS,
        "quotes": {
            demo.slug: {
                "source_id": demo.source_id,
                "signature": quote_signature(demo, chosen[demo.slug], language),
            }
            for demo in demos
        },
    }


def write_index(
    out_dir: Path,
    entries: dict[str, dict[str, object]],
    language: str,
) -> None:
    demos = quote_demos(language)
    title = "Jiajia Roast GIFs — English" if language == "en" else "Jiajia Roast GIFs"
    source_label = "English" if language == "en" else "Chinese"
    lines = [
        f"# {title}",
        "",
        f"Generated from the live {source_label} line bank.",
        "",
    ]
    if (out_dir / GALLERY_FILENAME).exists():
        lines += [
            f"![All {len(demos)} Jiajia roast quotes]({GALLERY_FILENAME})",
            "",
        ]
    lines += [
        "| Scene | Preview |",
        "|---|---|",
    ]
    for demo in demos:
        quote = str(entries[demo.slug]["line"])
        lines.append(f"| {demo.scene} | ![{quote}]({demo.slug}.gif) |")
    sibling_link = "Chinese gallery: [Chinese](../README.md)" if language == "en" else "English gallery: [English](en/README.md)"
    lines += [
        "",
        sibling_link,
        "",
        f"Regenerate: `python scripts/generate_quote_gifs.py --language {language}`",
        "",
    ]
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def check_outputs(
    out_dir: Path,
    expected: dict[str, object],
    demos: tuple[QuoteDemo, ...],
) -> int:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"stale: no manifest at {manifest_path}")
        return 1
    current = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    if current != expected:
        problems.append("manifest does not match the selected line-bank entries")
    for demo in demos:
        if not (out_dir / f"{demo.slug}.gif").exists():
            problems.append(f"missing GIF: {demo.slug}.gif")
    if problems:
        print("\n".join(f"- {problem}" for problem in problems))
        print("run: python scripts/generate_quote_gifs.py")
        return 1
    print(f"in sync — {len(demos)} quote GIFs")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Jiajia roast quote GIFs.")
    parser.add_argument("--language", choices=("zh", "en"), default="zh")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    language: str = args.language
    demos = quote_demos(language)
    out_dir: Path = args.out or default_out(language)
    entries = selected_entries(language)
    expected = build_manifest(entries, language)
    if args.check:
        return check_outputs(out_dir, expected, demos)

    out_dir.mkdir(parents=True, exist_ok=True)
    for demo in demos:
        frames = render_quote(demo, entries[demo.slug], language)
        save_gif(frames, out_dir / f"{demo.slug}.gif", disposal=2)
        print(f"{demo.slug:28s} {len(frames) * FRAME_MS / 1000:.1f}s")

    expected_slugs = {demo.slug for demo in demos} | {Path(GALLERY_FILENAME).stem}
    for gif in out_dir.glob("*.gif"):
        if gif.stem not in expected_slugs:
            gif.unlink()
            print(f"removed stale {gif.name}")

    (out_dir / "manifest.json").write_text(
        json.dumps(expected, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_index(out_dir, entries, language)
    print(f"wrote {len(demos)} quote GIFs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
