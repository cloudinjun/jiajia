from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python_pal.anim_physics import easing_for_action
from python_pal.body import (
    ACTION_FRAMES,
    BODY_MAIN_CURVES,
    BODY_START,
    BROW,
    EYE_WHITE,
    LEFT_BROW_CURVES,
    LEFT_BROW_START,
    PAL_SCALE,
    PUPIL,
    RIGHT_BROW_CURVES,
    RIGHT_BROW_START,
    TAIL_CURVES,
    TAIL_START,
    WIRE,
    _path_coords,
)


STAGE_W = 360
STAGE_H = 440
SOURCE_SCALE = 0.44
SOURCE_ORIGIN = (110.0, 132.0)
ACTION_ANCHOR = (158.0, 302.5)
FRAME_MS = 50
SS = 3

CODEX = "#10a37f"
CLAUDE = "#d97757"
USAGE = "#4f7ecf"
TEXT = "#202932"
BG = "#ffffff"

EyePose = tuple[float, float, float, float]
BrowPose = tuple[tuple[float, float, float], tuple[float, float, float]]
ActionState = tuple[float, float, float, float]


EYE_POSES: dict[str, EyePose] = {
    "neutral": (0.0, 0.0, 1.0, 1.0),
    "round": (0.0, 0.0, 1.08, 1.0),
    "side_eye": (-3.1, 0.35, 0.98, 1.0),
    "soft": (0.0, 0.25, 0.96, 0.92),
    "peek_up": (1.9, -0.75, 0.92, 1.0),
    "proud": (-0.35, -0.25, 1.02, 1.0),
    "blink": (0.0, 0.0, 1.0, 0.12),
}

BROW_POSES: dict[str, BrowPose] = {
    "neutral": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    "soft": ((0.0, -0.7, 0.0), (0.0, -0.5, 0.0)),
    "judge": ((-0.4, 1.7, -0.08), (0.3, 1.2, 0.09)),
    "innocent": ((0.0, -2.0, 0.02), (0.0, -1.6, -0.03)),
    "guilty": ((0.0, 2.3, 0.05), (0.0, 2.0, -0.05)),
    "laugh": ((0.0, 1.4, -0.02), (0.0, 1.2, 0.02)),
    "sulk": ((0.0, 2.6, -0.03), (0.0, 2.1, 0.03)),
    "proud": ((0.0, -1.4, -0.06), (0.0, -1.1, 0.06)),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate public demo GIFs for Paperclip Pal.")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/media"),
        help="Output directory for generated GIF files.",
    )
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    build_idle(args.out / "idle-breathe.gif")
    build_cold_arrow(args.out / "cold-arrow-then-innocent.gif")
    build_sleepy(args.out / "sleepy-sag.gif")
    build_status(args.out / "status-colors.gif")
    build_tail(args.out / "tail-wag.gif")
    print(f"wrote demo GIFs to {args.out}")


def build_idle(path: Path) -> None:
    frames: list[Image.Image] = []
    for index in range(72):
        phase = index / 72.0
        bob_y = -math.sin(phase * math.tau) * 3.2
        bob_x = math.sin(phase * math.tau * 0.75) * 1.2
        blink = 28 <= index <= 30
        tail = math.sin(phase * math.tau * 1.3) * 2.2
        frames.append(
            render_frame(
                action=(bob_x, bob_y, 1.0, 1.0),
                eye="blink" if blink else "round",
                brows="innocent",
                tail_wag=tail,
            )
        )
    save_gif(frames, path)


def build_cold_arrow(path: Path) -> None:
    frames: list[Image.Image] = []
    tilt_states = action_states("thinking_tilt")
    nod_states = action_states("nod")

    for index, state in enumerate(tilt_states[:20]):
        eye = "neutral" if index < 8 else "side_eye"
        brows = "soft" if index < 8 else "judge"
        frames.append(render_frame(action=state, eye=eye, brows=brows))

    for _ in range(8):
        frames.append(
            render_frame(
                action=tilt_states[min(18, len(tilt_states) - 1)],
                eye="side_eye",
                brows="judge",
                bubble=("speech", "This looks like preparation.\nVery decorative.", BROW),
            )
        )

    for state in nod_states[:12]:
        frames.append(
            render_frame(
                action=state,
                eye="round",
                brows="innocent",
                bubble=("speech", "I am only a stationery item.", BROW),
            )
        )

    for _ in range(8):
        frames.append(render_frame(eye="round", brows="innocent"))
    save_gif(frames, path)


def build_sleepy(path: Path) -> None:
    frames: list[Image.Image] = []
    for index, state in enumerate(action_states("sleepy_sag")):
        frames.append(
            render_frame(
                action=state,
                eye="soft",
                brows="sulk",
                decoration="zzz" if index > 8 else "",
            )
        )
    frames.extend(render_frame(eye="soft", brows="sulk", decoration="zzz") for _ in range(12))
    save_gif(frames, path)


def build_status(path: Path) -> None:
    frames: list[Image.Image] = []
    scan = action_states("scan")
    for index in range(54):
        if index < 27:
            accent = CODEX
            line = "Codex: running"
            bubble_kind = "thought"
        else:
            accent = CLAUDE
            line = "Claude: working"
            bubble_kind = "thought"
        frames.append(
            render_frame(
                action=scan[index % len(scan)],
                eye="side_eye",
                brows="judge",
                bubble=(bubble_kind, line, accent),
                badge=("C" if index < 27 else "Cl", accent),
            )
        )
    save_gif(frames, path)


def build_tail(path: Path) -> None:
    amounts = [0.0, 7.0, -8.0, 8.5, -6.0, 4.0, 0.0]
    frames: list[Image.Image] = []
    for amount in amounts:
        frames.extend(
            render_frame(eye="proud", brows="proud", tail_wag=amount)
            for _ in range(3)
        )
    frames.extend(render_frame(eye="round", brows="innocent") for _ in range(8))
    save_gif(frames, path)


def action_states(action: str) -> list[ActionState]:
    raw_frames = ACTION_FRAMES.get(action, ())
    if not raw_frames:
        return [(0.0, 0.0, 1.0, 1.0)]
    ease = easing_for_action(action)
    states: list[ActionState] = []
    current = (0.0, 0.0, 1.0, 1.0)
    for target in raw_frames:
        dx, dy, sx, sy, delay = target
        steps = max(1, round(delay / FRAME_MS))
        for step in range(steps):
            t = ease((step + 1) / steps)
            states.append(
                (
                    current[0] + (dx - current[0]) * t,
                    current[1] + (dy - current[1]) * t,
                    current[2] + (sx - current[2]) * t,
                    current[3] + (sy - current[3]) * t,
                )
            )
        current = (dx, dy, sx, sy)
    return states


def render_frame(
    *,
    action: ActionState = (0.0, 0.0, 1.0, 1.0),
    eye: str = "neutral",
    brows: str = "neutral",
    tail_wag: float = 0.0,
    bubble: tuple[str, str, str] | None = None,
    badge: tuple[str, str] | None = None,
    decoration: str = "",
) -> Image.Image:
    image = Image.new("RGBA", (STAGE_W * SS, STAGE_H * SS), BG)
    draw = ImageDraw.Draw(image)

    draw_character(draw, action=action, eye=eye, brows=brows, tail_wag=tail_wag)
    if decoration == "zzz":
        draw_zzz(draw)
    if badge:
        draw_badge(draw, badge[0], badge[1])
    if bubble:
        draw_bubble(draw, bubble[0], bubble[1], bubble[2])

    return image.resize((STAGE_W, STAGE_H), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE)


def draw_character(
    draw: ImageDraw.ImageDraw,
    *,
    action: ActionState,
    eye: str,
    brows: str,
    tail_wag: float,
) -> None:
    body_points = transform_path(path_points(BODY_START, BODY_MAIN_CURVES), action)
    tail_points = tail_path_points(tail_wag)
    tail_points = transform_path(tail_points, action)
    line(draw, body_points, WIRE, 30 * SOURCE_SCALE)
    line(draw, tail_points, WIRE, 30 * SOURCE_SCALE)

    ellipse(draw, oval_bounds(57, 154.726, 57), EYE_WHITE, action)
    ellipse(draw, oval_bounds(213, 195.226, 57, 56.5), EYE_WHITE, action)

    eye_dx, eye_dy, eye_size, blink_scale = EYE_POSES.get(eye, EYE_POSES["neutral"])
    pupil(draw, 64, 154.726, 39, eye_dx, eye_dy, eye_size, blink_scale, action)
    pupil(draw, 203, 192.726, 39, eye_dx, eye_dy, eye_size, blink_scale, action)

    left_pose, right_pose = BROW_POSES.get(brows, BROW_POSES["neutral"])
    left_brow = brow_points(path_points(LEFT_BROW_START, LEFT_BROW_CURVES), left_pose)
    right_brow = brow_points(path_points(RIGHT_BROW_START, RIGHT_BROW_CURVES), right_pose)
    line(draw, transform_path(left_brow, action), BROW, 30 * SOURCE_SCALE)
    line(draw, transform_path(right_brow, action), BROW, 30 * SOURCE_SCALE)


def path_points(start: tuple[float, float], curves: object) -> list[tuple[float, float]]:
    coords = _path_coords(start, curves)  # type: ignore[arg-type]
    return [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]


def tail_path_points(amount: float) -> list[tuple[float, float]]:
    points = path_points(TAIL_START, TAIL_CURVES)
    result: list[tuple[float, float]] = []
    for index, (x, y) in enumerate(points):
        progress = index / max(1, len(points) - 1)
        tip_bias = progress ** 1.35
        x += (amount / PAL_SCALE) * tip_bias
        y += (abs(amount) * 0.14 / PAL_SCALE) * math.sin(progress * math.pi)
        result.append((x, y))
    return result


def transform_path(points: list[tuple[float, float]], action: ActionState) -> list[tuple[float, float]]:
    return [to_stage(transform_actor_point(x, y, action)) for x, y in points]


def transform_actor_point(x: float, y: float, action: ActionState) -> tuple[float, float]:
    dx, dy, sx, sy = action
    ax, ay = ACTION_ANCHOR
    return (
        ax + (x - ax) * sx + dx / PAL_SCALE,
        ay + (y - ay) * sy + dy / PAL_SCALE,
    )


def to_stage(point: tuple[float, float]) -> tuple[float, float]:
    return (
        (SOURCE_ORIGIN[0] + point[0] * SOURCE_SCALE) * SS,
        (SOURCE_ORIGIN[1] + point[1] * SOURCE_SCALE) * SS,
    )


def oval_bounds(cx: float, cy: float, rx: float, ry: float | None = None) -> tuple[float, float, float, float]:
    radius_y = rx if ry is None else ry
    return (cx - rx, cy - radius_y, cx + rx, cy + radius_y)


def ellipse(
    draw: ImageDraw.ImageDraw,
    bounds: tuple[float, float, float, float],
    fill: str,
    action: ActionState,
) -> None:
    x1, y1, x2, y2 = bounds
    p1 = to_stage(transform_actor_point(x1, y1, action))
    p2 = to_stage(transform_actor_point(x2, y2, action))
    draw.ellipse((p1[0], p1[1], p2[0], p2[1]), fill=fill)


def pupil(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    radius: float,
    eye_dx: float,
    eye_dy: float,
    eye_size: float,
    blink_scale: float,
    action: ActionState,
) -> None:
    center = transform_actor_point(cx + eye_dx / PAL_SCALE, cy + eye_dy / PAL_SCALE, action)
    px, py = to_stage(center)
    rx = radius * SOURCE_SCALE * eye_size * SS
    ry = radius * SOURCE_SCALE * eye_size * blink_scale * SS
    draw.ellipse((px - rx, py - ry, px + rx, py + ry), fill=PUPIL)


def brow_points(points: list[tuple[float, float]], pose: tuple[float, float, float]) -> list[tuple[float, float]]:
    dx, dy, tilt = pose
    xs = [x for x, _ in points]
    center_x = sum(xs) / len(xs)
    return [
        (x + dx / PAL_SCALE, y + dy / PAL_SCALE + (x - center_x) * tilt)
        for x, y in points
    ]


def line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, width: float) -> None:
    if len(points) < 2:
        return
    scaled_width = max(1, round(width * SS))
    draw.line(points, fill=fill, width=scaled_width, joint="curve")
    radius = scaled_width / 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def draw_bubble(draw: ImageDraw.ImageDraw, kind: str, text: str, accent: str) -> None:
    font = load_font(18 if "\n" not in text else 16)
    x1, y1, x2, y2 = 38 * SS, 24 * SS, 322 * SS, 110 * SS
    fill = "#fdfdfd" if kind == "speech" else "#f7f5fb"
    draw.rounded_rectangle((x1, y1, x2, y2), radius=12 * SS, fill=fill, outline=accent, width=2 * SS)
    if kind == "thought":
        for cx, cy, r in ((192, 122, 5), (181, 134, 3), (172, 143, 2)):
            draw.ellipse(
                ((cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS),
                fill=fill,
                outline=accent,
                width=1 * SS,
            )
    else:
        draw.polygon(
            [(178 * SS, 110 * SS), (195 * SS, 110 * SS), (186 * SS, 126 * SS)],
            fill=fill,
            outline=accent,
        )
    draw.multiline_text((54 * SS, 43 * SS), text, font=font, fill=TEXT, spacing=4 * SS)


def draw_badge(draw: ImageDraw.ImageDraw, label: str, color: str) -> None:
    font = load_font(13)
    cx, cy, r = 245 * SS, 158 * SS, 16 * SS
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
    text_box = draw.textbbox((0, 0), label, font=font)
    tw, th = text_box[2] - text_box[0], text_box[3] - text_box[1]
    draw.text((cx - tw / 2, cy - th / 2 - 1 * SS), label, font=font, fill="#ffffff")


def draw_zzz(draw: ImageDraw.ImageDraw) -> None:
    font = load_font(22)
    for text, x, y, fill in (("Z", 240, 180, "#a8a8a8"), ("z", 260, 160, "#c0c0c0")):
        draw.text((x * SS, y * SS), text, font=font, fill=fill)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size * SS)
    return ImageFont.load_default()


def save_gif(frames: list[Image.Image], path: Path) -> None:
    if not frames:
        raise ValueError(f"no frames for {path}")
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
    )


if __name__ == "__main__":
    main()
