from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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
WIRE = "#aeaeae"
EYE_WHITE = "#ececec"
BROW = "#402a32"
PUPIL = "#402a32"
PAL_SCALE = 0.25

EyePose = tuple[float, float, float, float]
BrowPose = tuple[tuple[float, float, float], tuple[float, float, float]]
ActionState = tuple[float, float, float, float]

BODY_START = (124.0, 267.226)
BODY_CURVES = (
    ((124.0, 267.226), (113.008, 384.271), (158.0, 407.226)),
    ((182.5, 419.726), (210.918, 399.226), (206.0, 369.226)),
    ((200.18, 333.727), (196.0, 265.226), (206.0, 202.226)),
    ((214.622, 147.907), (214.983, 149.226), (231.5, 96.7265)),
    ((248.017, 44.2265), (201.0, -1.42701), (148.0, 20.7265)),
    ((72.5, 52.2846), (42.7789, 215.226), (53.4999, 312.226)),
    ((67.2106, 436.276), (101.591, 483.694), (130.0, 509.226)),
    ((169.5, 544.726), (222.497, 545.135), (254.0, 500.226)),
    ((277.5, 466.726), (254.0, 374.226), (257.5, 322.226)),
    ((259.216, 296.726), (275.5, 267.226), (301.0, 250.726)),
)
BODY_MAIN_CURVES = BODY_CURVES[:-1]
TAIL_START = BODY_CURVES[-2][2]
# free tip extension, kept in sync with python_pal.body.TAIL_TIP_EXTENSION
TAIL_TIP_EXTENSION = (
    ((301.0, 250.726), (312.5, 243.0), (319.0, 233.0)),
    ((319.0, 233.0), (325.5, 223.5), (329.5, 211.0)),
)
TAIL_CURVES = (BODY_CURVES[-1], *TAIL_TIP_EXTENSION)
LEFT_BROW_START = (64.0, 56.7265)
LEFT_BROW_CURVES = (
    ((64.0, 56.7265), (81.7087, 52.8505), (93.2292, 52.7265)),
    ((105.734, 52.5919), (125.0, 56.7265), (125.0, 56.7265)),
)
RIGHT_BROW_START = (204.0, 92.7265)
RIGHT_BROW_CURVES = (
    ((204.0, 92.7265), (219.1, 90.4067), (228.302, 92.7265)),
    ((242.828, 96.388), (259.0, 115.726), (259.0, 115.726)),
)

DEMO_ACTION_FRAMES: dict[str, tuple[ActionState, ...]] = {
    "thinking_tilt": (
        (-6, 0, 0.92, 1.06),
        (-8, 2, 0.90, 1.08),
        (-4, 1, 0.95, 1.04),
        (0, 0, 1.0, 1.0),
    ),
    "nod": (
        (0, 10, 1.04, 0.92),
        (0, 2, 1.0, 1.0),
        (0, 8, 1.03, 0.94),
        (0, 0, 1.0, 1.0),
    ),
    "sleepy_sag": (
        (0, 4, 0.98, 0.96),
        (0, 12, 0.96, 0.88),
        (0, 20, 1.04, 0.78),
        (0, 6, 0.96, 0.96),
        (0, 14, 1.02, 0.84),
        (0, 4, 0.98, 0.94),
        (0, 0, 1.0, 1.0),
    ),
    "scan": (
        (-20, 0, 1.0, 1.0),
        (-20, 0, 1.0, 1.0),
        (0, 0, 1.0, 1.0),
        (20, 0, 1.0, 1.0),
        (20, 0, 1.0, 1.0),
        (0, 0, 1.0, 1.0),
    ),
    "smug_sway": (
        (-10, 2, 0.96, 1.02),
        (-6, 0, 0.98, 1.01),
        (8, -1, 1.02, 0.99),
        (4, 0, 1.01, 1.0),
        (0, 0, 1.0, 1.0),
    ),
}

DEMO_ACTION_DELAYS: dict[str, tuple[int, ...]] = {
    "thinking_tilt": (180, 400, 150, 100),
    "nod": (120, 80, 120, 90),
    "sleepy_sag": (200, 250, 300, 80, 250, 100, 120),
    "scan": (200, 150, 140, 200, 150, 140),
    "smug_sway": (200, 180, 200, 160, 140),
}


EYE_POSES: dict[str, EyePose] = {
    "neutral": (0.0, 0.0, 1.0, 1.0),
    "round": (0.0, 0.0, 1.08, 1.0),
    "side_eye": (-3.1, 0.35, 0.98, 1.0),
    "soft": (0.0, 0.25, 0.96, 0.92),
    "peek_up": (1.9, -0.75, 0.92, 1.0),
    "proud": (-0.35, -0.25, 1.02, 1.0),
    "wide": (0.0, -0.25, 1.18, 1.0),
    "sleepy": (0.0, 0.75, 0.92, 0.50),
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
    "asleep": ((0.0, 3.2, -0.04), (0.0, 2.8, 0.04)),
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
    build_hero(args.out / "hero-interaction.gif")
    build_idle(args.out / "idle-breathe.gif")
    build_cold_arrow(args.out / "cold-arrow-then-innocent.gif")
    build_sleepy(args.out / "sleepy-sag.gif")
    build_status(args.out / "status-colors.gif")
    build_tail(args.out / "tail-wag.gif")
    print(f"wrote demo GIFs to {args.out}")


def build_hero(path: Path) -> None:
    frames: list[Image.Image] = []
    prompt = "make a smug face"
    typed_steps = [prompt[:count] for count in range(0, len(prompt) + 1, 2)]

    for _ in range(6):
        frames.append(
            render_frame(
                action=(0, -2, 1.0, 1.0),
                eye="wide",
                brows="innocent",
                input_text="",
                stage_label="1  Type",
                effect="cursor_ping",
            )
        )

    for index, typed in enumerate(typed_steps):
        phase = index / max(1, len(typed_steps) - 1)
        frames.append(
            render_frame(
                action=(math.sin(phase * math.tau) * 0.8, -math.sin(phase * math.pi) * 1.8, 1.0, 1.0),
                eye="round",
                brows="innocent",
                input_text=typed,
                stage_label="1  Type",
                effect="cursor_ping" if index % 3 == 0 else "",
            )
        )

    thinking = action_states("thinking_tilt")
    scan = action_states("scan")
    wait_lines = (
        "Reading intent",
        "Searching mood",
        "Choosing timing",
        "Warming eyebrows",
    )
    for index in range(34):
        states = thinking if index < 18 else scan
        line_text = wait_lines[min(len(wait_lines) - 1, index // 9)]
        dot_text = "." * ((index % 4) + 1)
        frames.append(
            render_frame(
                action=states[index % len(states)],
                eye="side_eye" if index > 12 else "neutral",
                brows="judge" if index > 12 else "soft",
                bubble=("thought", f"{line_text}{dot_text}", USAGE),
                input_text=prompt,
                stage_label="2  Think / search",
                badge=("LLM", USAGE),
                effect="search_rings",
                wire_color="#9fb4d6",
            )
        )

    sway = action_states("smug_sway")
    reply = "I found the face.\nUnfortunately, it was yours."
    for index in range(28):
        eye = "side_eye" if index < 14 else "round"
        brows = "judge" if index < 14 else "innocent"
        frames.append(
            render_frame(
                action=sway[index % len(sway)],
                eye=eye,
                brows=brows,
                bubble=("speech", reply, BROW),
                input_text=prompt,
                stage_label="3  Reply + perform",
                effect="cold_spark" if index < 10 else "",
            )
        )

    frames.extend(
        render_frame(
            action=(0, -1, 0.98, 1.03),
            eye="wide",
            brows="innocent",
            bubble=("speech", "I am only a stationery item.", BROW),
            input_text=prompt,
            stage_label="3  Reply + perform",
            effect="innocent_glow",
        )
        for _ in range(10)
    )
    save_gif(frames, path)


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

    for _ in range(10):
        frames.append(
            render_frame(
                action=(-8, 2, 0.88, 1.10),
                eye="side_eye",
                brows="judge",
                bubble=("thought", "assessing...", BROW),
                effect="cold_spark",
            )
        )

    for index, state in enumerate(tilt_states[:20]):
        eye = "neutral" if index < 8 else "side_eye"
        brows = "soft" if index < 8 else "judge"
        frames.append(render_frame(action=state, eye=eye, brows=brows, effect="cold_spark" if index > 8 else ""))

    for _ in range(8):
        frames.append(
            render_frame(
                action=tilt_states[min(18, len(tilt_states) - 1)],
                eye="side_eye",
                brows="judge",
                bubble=("speech", "This looks like preparation.\nVery decorative.", BROW),
                effect="cold_spark",
            )
        )

    for state in nod_states[:12]:
        frames.append(
            render_frame(
                action=state,
                eye="wide",
                brows="innocent",
                bubble=("speech", "I am only a stationery item.", BROW),
                effect="innocent_glow",
            )
        )

    for _ in range(8):
        frames.append(render_frame(action=(0, -1, 0.98, 1.03), eye="wide", brows="innocent", effect="innocent_glow"))
    save_gif(frames, path)


def build_sleepy(path: Path) -> None:
    frames: list[Image.Image] = []
    for _ in range(10):
        frames.append(
            render_frame(
                action=(0, 25, 1.18, 0.58),
                eye="sleepy",
                brows="asleep",
                decoration="zzz",
                effect="sleep_droop",
                wire_color="#b9b9b9",
            )
        )
    for index, state in enumerate(action_states("sleepy_sag")):
        frames.append(
            render_frame(
                action=state,
                eye="sleepy" if index > 3 else "soft",
                brows="asleep" if index > 3 else "sulk",
                decoration="zzz" if index > 8 else "",
                effect="sleep_droop" if index > 5 else "",
                wire_color="#b9b9b9",
            )
        )
    frames.extend(
        render_frame(
            action=(0, 18, 1.10, 0.70),
            eye="sleepy",
            brows="asleep",
            decoration="zzz",
            effect="sleep_droop",
            wire_color="#b9b9b9",
        )
        for _ in range(12)
    )
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
                effect="status_scan",
                wire_color="#a6c9bc" if index < 27 else "#d4b09e",
            )
        )
    save_gif(frames, path)


def build_tail(path: Path) -> None:
    amounts = [14.0, -15.0, 16.0, -12.0, 10.0, -7.0, 0.0]
    frames: list[Image.Image] = []
    for amount in amounts:
        frames.extend(
            render_frame(
                action=(0, -3, 0.98, 1.04),
                eye="proud",
                brows="proud",
                tail_wag=amount,
                effect="tail_motion",
            )
            for _ in range(3)
        )
    frames.extend(render_frame(eye="wide", brows="innocent", effect="innocent_glow") for _ in range(8))
    save_gif(frames, path)


def action_states(action: str) -> list[ActionState]:
    raw_frames = DEMO_ACTION_FRAMES.get(action, ())
    if not raw_frames:
        return [(0.0, 0.0, 1.0, 1.0)]
    ease = easing_for_action(action)
    states: list[ActionState] = []
    current = (0.0, 0.0, 1.0, 1.0)
    delays = DEMO_ACTION_DELAYS.get(action, (FRAME_MS,) * len(raw_frames))
    for target, delay in zip(raw_frames, delays):
        dx, dy, sx, sy = target
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


def easing_for_action(action: str):
    if action in {"scan"}:
        return linear
    if action in {"sleepy_sag"}:
        return ease_in_slow
    if action in {"smug_sway", "thinking_tilt"}:
        return ease_in_out_cubic
    return ease_out_cubic


def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


def ease_in_slow(t: float) -> float:
    return t**4


def linear(t: float) -> float:
    return t


def render_frame(
    *,
    action: ActionState = (0.0, 0.0, 1.0, 1.0),
    eye: str = "neutral",
    brows: str = "neutral",
    tail_wag: float = 0.0,
    bubble: tuple[str, str, str] | None = None,
    badge: tuple[str, str] | None = None,
    decoration: str = "",
    input_text: str = "",
    stage_label: str = "",
    effect: str = "",
    wire_color: str = WIRE,
) -> Image.Image:
    image = Image.new("RGBA", (STAGE_W * SS, STAGE_H * SS), BG)
    draw = ImageDraw.Draw(image)

    if effect in {"search_rings", "status_scan", "sleep_droop", "cursor_ping"}:
        draw_effect(draw, effect)
    draw_character(draw, action=action, eye=eye, brows=brows, tail_wag=tail_wag, wire_color=wire_color)
    if effect in {"cold_spark", "innocent_glow", "tail_motion"}:
        draw_effect(draw, effect)
    if decoration == "zzz":
        draw_zzz(draw)
    if badge:
        draw_badge(draw, badge[0], badge[1])
    if bubble:
        draw_bubble(draw, bubble[0], bubble[1], bubble[2])
    if input_text or stage_label:
        draw_input_panel(draw, input_text, stage_label)

    return image.resize((STAGE_W, STAGE_H), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE)


def draw_character(
    draw: ImageDraw.ImageDraw,
    *,
    action: ActionState,
    eye: str,
    brows: str,
    tail_wag: float,
    wire_color: str,
) -> None:
    body_points = transform_path(path_points(BODY_START, BODY_MAIN_CURVES), action)
    tail_points = tail_path_points(tail_wag)
    tail_points = transform_path(tail_points, action)
    line(draw, body_points, wire_color, 30 * SOURCE_SCALE)
    line(draw, tail_points, wire_color, 30 * SOURCE_SCALE)

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


def _path_coords(
    start: tuple[float, float],
    curves: tuple[tuple[tuple[float, float], tuple[float, float], tuple[float, float]], ...],
) -> list[float]:
    coords = [start[0], start[1]]
    current = start
    for control_1, control_2, end in curves:
        for x, y in _sample_cubic(current, control_1, control_2, end, steps=18):
            coords.extend((x, y))
        current = end
    return coords


def _sample_cubic(
    start: tuple[float, float],
    control_1: tuple[float, float],
    control_2: tuple[float, float],
    end: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    samples = []
    for step in range(1, steps + 1):
        t = step / steps
        inverse = 1 - t
        x = (
            inverse**3 * start[0]
            + 3 * inverse**2 * t * control_1[0]
            + 3 * inverse * t**2 * control_2[0]
            + t**3 * end[0]
        )
        y = (
            inverse**3 * start[1]
            + 3 * inverse**2 * t * control_1[1]
            + 3 * inverse * t**2 * control_2[1]
            + t**3 * end[1]
        )
        samples.append((x, y))
    return samples


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


def draw_effect(draw: ImageDraw.ImageDraw, effect: str) -> None:
    if effect == "cursor_ping":
        cx, cy = 304 * SS, 398 * SS
        for radius, color in ((5, "#dce7f4"), (9, "#eef3f8")):
            r = radius * SS
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=color, width=2 * SS)
        return

    if effect == "search_rings":
        for radius, color in ((42, "#d9e4f8"), (57, "#edf3ff")):
            x1, y1 = (178 - radius) * SS, (210 - radius) * SS
            x2, y2 = (178 + radius) * SS, (210 + radius) * SS
            draw.arc((x1, y1, x2, y2), start=20, end=315, fill=color, width=3 * SS)
        for x, y, color in ((246, 162, USAGE), (258, 184, "#8ba7de"), (103, 194, "#b9c9e9")):
            draw.ellipse(((x - 4) * SS, (y - 4) * SS, (x + 4) * SS, (y + 4) * SS), fill=color)
        return

    if effect == "status_scan":
        for x in (78, 92, 106):
            draw.line((x * SS, 152 * SS, x * SS, 282 * SS), fill="#e6eef8", width=2 * SS)
        for y in (194, 218, 242):
            draw.line((82 * SS, y * SS, 278 * SS, y * SS), fill="#eef3f7", width=2 * SS)
        return

    if effect == "sleep_droop":
        draw.rounded_rectangle((112 * SS, 314 * SS, 246 * SS, 330 * SS), radius=8 * SS, fill="#eeeeee")
        for x, y, r in ((105, 286, 4), (88, 270, 3), (250, 280, 3)):
            draw.ellipse(((x - r) * SS, (y - r) * SS, (x + r) * SS, (y + r) * SS), fill="#dadada")
        return

    if effect == "cold_spark":
        for points in (
            ((246, 150), (258, 142), (252, 158)),
            ((92, 134), (80, 126), (86, 142)),
            ((272, 218), (286, 214)),
        ):
            scaled = [(x * SS, y * SS) for x, y in points]
            draw.line(scaled, fill="#9c5662", width=3 * SS)
        return

    if effect == "innocent_glow":
        for cx, cy in ((135, 199), (200, 216)):
            r = 25 * SS
            draw.ellipse((cx * SS - r, cy * SS - r, cx * SS + r, cy * SS + r), outline="#f1f1f1", width=3 * SS)
        return

    if effect == "tail_motion":
        for offset, alpha_color in ((0, "#d8d8d8"), (12, "#e6e6e6"), (24, "#efefef")):
            draw.arc(
                ((252 + offset) * SS, 198 * SS, (314 + offset) * SS, 296 * SS),
                start=120,
                end=220,
                fill=alpha_color,
                width=3 * SS,
            )


def draw_input_panel(draw: ImageDraw.ImageDraw, text: str, stage_label: str) -> None:
    label_font = load_font(11)
    input_font = load_font(16)
    x1, y1, x2, y2 = 30 * SS, 360 * SS, 330 * SS, 416 * SS
    draw.rounded_rectangle((x1, y1, x2, y2), radius=13 * SS, fill="#f7f8fa", outline="#d5dde5", width=1 * SS)
    draw.text((45 * SS, 368 * SS), stage_label, font=label_font, fill="#607080")
    draw.rounded_rectangle((44 * SS, 386 * SS, 316 * SS, 407 * SS), radius=9 * SS, fill="#ffffff", outline="#d5dde5", width=1 * SS)
    caret = "|" if len(text) % 2 == 0 else ""
    draw.text((55 * SS, 388 * SS), f"> {text}{caret}", font=input_font, fill=TEXT)


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
