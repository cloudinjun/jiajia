"""Shared geometry, colours and frame helpers for Paperclip Pal.

Split out of body.py so the drawing, window, action and decoration layers can
all import the same constants without importing the app class (which would be
circular). Contains no Tk state and no `self` — pure data and pure functions.
"""
from __future__ import annotations

import math
import random


ActionFrame = tuple[float, float, float, float, int]
ActionFrames = tuple[ActionFrame, ...]


TRANSPARENT = "#ff00ff"

WIRE = "#aeaeae"

EYE_WHITE = "#ececec"

BROW = "#402a32"

PUPIL = "#402a32"

CHEEK_BLUSH = "#ffb3b3"     # default blush color

PAL_SCALE = 0.25

PAL_SOURCE_WIDTH = 316

PAL_SOURCE_HEIGHT = 550

PAL_WIDTH = round(PAL_SOURCE_WIDTH * PAL_SCALE)

PAL_HEIGHT = round(PAL_SOURCE_HEIGHT * PAL_SCALE)

PAL_PAD_X = 120

PAL_PAD_Y = 100

PAL_CANVAS_WIDTH = PAL_WIDTH + PAL_PAD_X * 2

PAL_CANVAS_HEIGHT = PAL_HEIGHT + PAL_PAD_Y * 2

DECORATION_SCALE = 1.9

PAL_CENTER_X = PAL_PAD_X + PAL_WIDTH / 2

PAL_SCALE_CENTER_Y = PAL_PAD_Y + PAL_HEIGHT * 0.55

PAL_SCALE_PIVOT_Y = PAL_PAD_Y + PAL_HEIGHT - 2

PAL_LOOK_CENTER_X = PAL_PAD_X + PAL_WIDTH * 0.48

PAL_LOOK_CENTER_Y = PAL_PAD_Y + PAL_HEIGHT * 0.32

LERP_TICK_MS = 18

ANIM_TICK_MS = 33  # main heartbeat (~30fps); legacy phase constants were tuned at 50ms

ANIM_TICK_SCALE = ANIM_TICK_MS / 50.0

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

# --- tail length modes ---
# "short": only the tip segment (curve 9) — quick flicks, alert snaps
# "long":  ascending side + tip (curves 8-9) — cat-like serpentine sway
# Both modes end in a free tip extension that continues the wire past the
# classic silhouette, so wags read beyond the body outline.
# kept gentle: at rest the tail should read like the original silhouette,
# just continued — the drama comes from motion, not from a curled resting
# shape. The free end runs a little longer so the whip has a visible tip.
TAIL_TIP_EXTENSION = (
    ((301.0, 250.726), (312.5, 243.0), (319.0, 233.0)),
    ((319.0, 233.0), (325.5, 223.5), (329.5, 211.0)),
)

TAIL_SHORT_START = BODY_CURVES[-2][2]           # (257.5, 322.226)

TAIL_SHORT_CURVES = (BODY_CURVES[-1], *TAIL_TIP_EXTENSION)

TAIL_LONG_START = BODY_CURVES[-3][2]            # (254.0, 500.226)

TAIL_LONG_CURVES = (*BODY_CURVES[-2:], *TAIL_TIP_EXTENSION)

# legacy aliases
BODY_MAIN_CURVES = BODY_CURVES[:-1]

TAIL_START = TAIL_SHORT_START

TAIL_CURVES = TAIL_SHORT_CURVES

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

_JITTER_DXY = 0.12

_JITTER_SCALE = 0.06

_JITTER_DELAY = 0.10

def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3

def _ease_out_sine(t: float) -> float:
    return math.sin(_clamp(t, 0.0, 1.0) * math.pi / 2)

def _smoothstep(t: float) -> float:
    t = _clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)

def _per_tick(strength: float) -> float:
    """Convert a per-50ms lerp strength to the current heartbeat rate."""
    return 1.0 - (1.0 - strength) ** ANIM_TICK_SCALE

def _breath_curve(phase: float) -> float:
    # 吸气快（0→0.35），呼气慢（0.35→0.75），末尾停顿（0.75→1.0）
    if phase < 0.35:
        t = phase / 0.35
        return math.sin(t * math.pi / 2)
    if phase < 0.75:
        t = (phase - 0.35) / 0.4
        return math.cos(t * math.pi / 2)
    return 0.0

def _jitter_frames(frames: ActionFrames) -> ActionFrames:
    result: list[ActionFrame] = []
    for i, (dx, dy, sx, sy, delay) in enumerate(frames):
        if i == len(frames) - 1:
            result.append((dx, dy, sx, sy, delay))
            continue
        jdx = dx * (1.0 + random.uniform(-_JITTER_DXY, _JITTER_DXY)) if dx else 0.0
        jdy = dy * (1.0 + random.uniform(-_JITTER_DXY, _JITTER_DXY)) if dy else 0.0
        jsx = 1.0 + (sx - 1.0) * (1.0 + random.uniform(-_JITTER_SCALE, _JITTER_SCALE))
        jsy = 1.0 + (sy - 1.0) * (1.0 + random.uniform(-_JITTER_SCALE, _JITTER_SCALE))
        jdelay = max(10, round(delay * (1.0 + random.uniform(-_JITTER_DELAY, _JITTER_DELAY))))
        result.append((jdx, jdy, jsx, jsy, jdelay))
    return tuple(result)


def _geometry_position(x: float, y: float) -> str:
    return f"+{round(x)}+{round(y)}"

def _geometry_with_size(width: float, height: float, x: float, y: float) -> str:
    return f"{round(width)}x{round(height)}{_geometry_position(x, y)}"

def _scale_coords(coords: list[float]) -> list[float]:
    return [
        value * PAL_SCALE + (PAL_PAD_X if index % 2 == 0 else PAL_PAD_Y)
        for index, value in enumerate(coords)
    ]

def _source_point(x: float, y: float) -> tuple[float, float]:
    return (x * PAL_SCALE + PAL_PAD_X, y * PAL_SCALE + PAL_PAD_Y)

def _oval_center_radius(coords: list[float]) -> tuple[float, float, float]:
    x1, y1, x2, y2 = coords
    return (x1 + x2) / 2, (y1 + y2) / 2, min(x2 - x1, y2 - y1) / 2

def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def _brow_pose_coords(base: tuple[float, ...], dx: float, dy: float, tilt: float) -> list[float]:
    xs = [base[i] for i in range(0, len(base), 2)]
    center_x = sum(xs) / max(1, len(xs))
    coords: list[float] = []
    for i in range(0, len(base), 2):
        x = base[i]
        y = base[i + 1]
        coords.extend((x + dx, y + dy + (x - center_x) * tilt))
    return coords

def _oval_bounds(cx: float, cy: float, rx: float, ry: float | None = None) -> tuple[float, float, float, float]:
    radius_y = rx if ry is None else ry
    return (
        (cx - rx) * PAL_SCALE + PAL_PAD_X,
        (cy - radius_y) * PAL_SCALE + PAL_PAD_Y,
        (cx + rx) * PAL_SCALE + PAL_PAD_X,
        (cy + radius_y) * PAL_SCALE + PAL_PAD_Y,
    )

def _path_coords(
    start: tuple[float, float],
    curves: tuple[tuple[tuple[float, float], tuple[float, float], tuple[float, float]], ...],
    steps: int = 18,
) -> list[float]:
    coords = [start[0], start[1]]
    current = start
    for control_1, control_2, end in curves:
        for x, y in _sample_cubic(current, control_1, control_2, end, steps=steps):
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
