"""Render one GIF per Jiajia action.

Every action listed in `jiajia.actions.ACTION_LABELS` gets a GIF under
`docs/media/actions/`, driven by the same keyframe tables, easing curves and
pose math the live app uses. Regenerate whenever actions are added, retimed, or
removed:

    python scripts/generate_action_gifs.py

`--check` verifies the folder is in sync with the code (used to catch GIFs that
went stale after a keyframe edit) without rewriting anything:

    python scripts/generate_action_gifs.py --check

Requires Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PIL import Image, ImageDraw, ImageFont

from jiajia import body as B
from jiajia.actions import ACTION_LABELS, ACTION_DESCRIPTIONS, ACTION_MENU_GROUPS
from jiajia.anim_physics import easing_for_action
from jiajia.prop_shapes import (
    ACTION_FACE_SCRIPTS,
    ACTION_PROP_CUES,
    EYE_FX_SHAPES,
    FACE_DECALS,
    GRIP_POINTS,
    PROP_SHAPES,
    SHAPE_FX,
    apply_shape_fx,
    build_prop_timeline,
    inertia_step,
    transform_shape,
)
from jiajia.rig_pose import bend_point, posed_chin_points, posed_tail_points


# ── stage ────────────────────────────────────────────────────────

STAGE_W, STAGE_H = 300, 262
SS = 3                      # supersample factor
FRAME_MS = 33               # matches the runtime heartbeat (~30fps)
RENDER_VERSION = 17          # bump when the renderer itself changes how frames look
BG = "#ffffff"
LABEL_COLOR = "#8a919a"
STROKE_W = 30 * B.PAL_SCALE

# The runtime lays the character out inside a padded canvas; recenter it here.
# REST_TOP leaves headroom for jumps (~50px of lift) without clipping.
REST_TOP = 62
OFFSET_X = STAGE_W / 2 - B.PAL_CENTER_X
OFFSET_Y = REST_TOP - B.PAL_PAD_Y


Pose = dict


# ── base geometry (identical splits to JiajiaApp._draw_pal) ─

# the runtime defaults to the "long" tail mode; render with the same split
TAIL_MODE = "long"
CHIN_BASE = tuple(B._scale_coords(B._path_coords(B.BODY_START, (B.BODY_CURVES[0],))))
BODY_BASE = tuple(B._scale_coords(B._path_coords(B.BODY_CURVES[0][2], B.BODY_CURVES[1:-2])))
TAIL_BASE = tuple(B._scale_coords(B._path_coords(B.TAIL_LONG_START, B.TAIL_LONG_CURVES, steps=36)))
TAIL_LAG_FRAMES = max(1, round(B.TAIL_TIP_LAG_MS / FRAME_MS))
TAIL_S_PHASE_STEP = 0.038 * B.ANIM_TICK_SCALE  # long-mode wave speed
LEFT_BROW_BASE = tuple(B._scale_coords(B._path_coords(B.LEFT_BROW_START, B.LEFT_BROW_CURVES)))
RIGHT_BROW_BASE = tuple(B._scale_coords(B._path_coords(B.RIGHT_BROW_START, B.RIGHT_BROW_CURVES)))
LEFT_SCLERA = B._oval_bounds(57, 154.726, 57)
RIGHT_SCLERA = B._oval_bounds(213, 195.226, 57, 56.5)
LEFT_PUPIL = B._oval_bounds(64, 154.726, 39)
RIGHT_PUPIL = B._oval_bounds(203, 192.726, 39)

NEUTRAL_EYE = (0.0, 0.0, 1.0, 1.0)          # dx, dy, pupil scale, openness
NEUTRAL_BROW = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


def neutral_pose() -> Pose:
    return {
        "body": (0.0, 0.0, 1.0, 1.0),
        "tail": (0.0, 0.0, 0.0, 0.0, 0.0),
        "inner": (0.0, 0.0, 0.0, 0.0),
        "eye": NEUTRAL_EYE,
        "brow": NEUTRAL_BROW,
        "blink": 1.0,
        "s_phase": 0.0,
    }


# ── timeline helpers ─────────────────────────────────────────────

def _interpolate(frames, ease, arity: int, start=None):
    """Expand (v0..vn, delay_ms) keyframes into per-frame value tuples."""
    values: list[tuple[float, ...]] = []
    current = start if start is not None else tuple([0.0] * arity)
    for frame in frames:
        target = tuple(float(v) for v in frame[:arity])
        delay = frame[arity]
        steps = max(1, round(delay / FRAME_MS))
        for step in range(steps):
            t = ease((step + 1) / steps)
            values.append(tuple(current[i] + (target[i] - current[i]) * t for i in range(arity)))
        current = target
    return values


def _hold(values: list, count: int) -> list:
    """Repeat the last value so a performance can rest before looping."""
    if not values or count <= 0:
        return values
    return values + [values[-1]] * count


def _pad_to(values: list, length: int, fill):
    if len(values) >= length:
        return values[:length]
    tail = values[-1] if values else fill
    return values + [tail] * (length - len(values))


def body_track(action: str, frames=None, ease=None) -> list[tuple[float, ...]]:
    """Body (dx, dy, sx, sy) track including anticipation and follow-through."""
    raw = frames if frames is not None else B.ACTION_FRAMES.get(action)
    if not raw:
        return []
    return _interpolate(B._acting_frames(raw, action), ease or easing_for_action(action), 4,
                        start=(0.0, 0.0, 1.0, 1.0))


def tail_track(motion: str):
    """Tail pose track. Returns (poses, phases-or-None, wave_factor-or-None).

    Oscillating motions sample the shared cat-tail pendulum: the time phase
    drives the traveling wave, so `phases` overrides the frame's s_phase; the
    wave factor sets how many bends the swing carries (energy-dependent).
    """
    osc = B.TAIL_OSCILLATIONS.get(motion)
    if osc:
        poses, phases = [], []
        i = 0
        while True:
            sample = B.tail_oscillation_pose(osc, i * FRAME_MS / 1000.0)
            if sample is None:
                break
            poses.append(sample[:5])
            phases.append(sample[5])
            i += 1
        # ease back to neutral like the runtime's 160ms release
        release = _interpolate(((0.0, 0.0, 0.0, 0.0, 0.0, 160),), B._smoothstep, 5,
                               start=poses[-1] if poses else None)
        poses += release
        phases += [phases[-1] if phases else 0.0] * len(release)
        return poses, phases, osc.get("wave")
    posture = B.TAIL_POSTURES.get(motion)
    if posture:
        poses = []
        i = 0
        while True:
            sample = B.tail_posture_pose(posture, i * FRAME_MS / 1000.0)
            if sample is None:
                break
            poses.append(sample)
            i += 1
        release = _interpolate(((0.0, 0.0, 0.0, 0.0, 0.0, 180),), B._smoothstep, 5,
                               start=poses[-1] if poses else None)
        return poses + release, None, None
    frames = B.TAIL_MOTION_FRAMES.get(motion)
    if not frames:
        return [], None, None
    track = _interpolate(frames, B._ease_out_sine, 5)
    # runtime always eases back to neutral when the sequence ends
    track += _interpolate(((0.0, 0.0, 0.0, 0.0, 0.0, 140),), B._ease_out_sine, 5,
                          start=track[-1] if track else None)
    return track, None, None


def inner_track(gesture: str) -> list[tuple[float, ...]]:
    frames = B.INNER_GESTURE_FRAMES.get(gesture)
    if not frames:
        return []
    track = _interpolate(frames, B._ease_out_sine, 4)
    track += _interpolate(((0.0, 0.0, 0.0, 0.0, 130),), B._ease_out_sine, 4,
                          start=track[-1] if track else None)
    return track


def bend_track(action: str) -> list[tuple[float, ...]]:
    """Body lean/hunch track, mirroring the runtime's smoothstep transitions."""
    frames = B.ACTION_BODY_BEND.get(action)
    if not frames:
        return []
    return _interpolate(frames, B._smoothstep, 2)


def prop_track(action: str):
    """Emotion-prop pose track: (poses, anchor, shape_key, over_face).

    The runtime spawns the prop one heartbeat after the action starts; the
    30ms offset is invisible at GIF scale, so the track starts at frame 0.
    Carried-object inertia is baked into the rotations, matching the runtime.
    """
    cue = ACTION_PROP_CUES.get(action)
    if not cue:
        return None
    timeline = build_prop_timeline(cue)
    poses = _interpolate(timeline, B._smoothstep, 5, start=timeline[0][:5])
    extra, prev_dx = 0.0, timeline[0][0]
    swung = []
    for dx, dy, rot, scale, squash in poses:
        extra = inertia_step(extra, prev_dx, dx, FRAME_MS / 1000.0)
        prev_dx = dx
        swung.append((dx, dy, rot + extra, scale, squash))
    return (swung, cue["anchor"], str(cue["shape"]), bool(cue.get("over_face")),
            bool(cue.get("held")), tuple(cue.get("grip_offset", (0.0, 0.0))))


_FACE_TWEEN_MS = 180

# staged blink events compiled to per-frame eyelid multipliers (33ms frames)
_BLINK_CURVES = {
    "quick": (0.5, 0.15, 0.5, 0.9),
    "double": (0.5, 0.15, 0.6, 1.0, 1.0, 0.5, 0.15, 0.6, 0.9),
    "slow": (0.75, 0.5, 0.25, 0.08, 0.08, 0.08, 0.25, 0.5, 0.72, 0.9),
    "flutter": (0.5, 0.9, 0.4, 0.85, 0.5, 1.0),
}


def face_tracks(script, length: int):
    """Per-frame eye-spec, brow-spec, gaze, and blink from a staged script.

    Beats may carry micro-expression extras: pupil size, explicit eyelid
    openness, single-brow overrides, brow tremble, and blink events. Stage
    switches tween over _FACE_TWEEN_MS; a look of None keeps the caller's
    existing gaze.
    """
    stages = []
    for frame in script:
        at_ms, eyes, brows, look = frame[0], frame[1], frame[2], frame[3]
        ex = frame[4] if len(frame) > 4 and frame[4] else {}
        eye = list(B.JiajiaApp._EYE_MAP.get(eyes, NEUTRAL_EYE))
        if "pupil" in ex:
            eye[2] *= float(ex["pupil"])
        if "openness" in ex:
            eye[3] = float(ex["openness"])
        brow = B.JiajiaApp._BROW_MAP.get(brows, NEUTRAL_BROW)
        brow = (tuple(ex.get("brow_l", brow[0])), tuple(ex.get("brow_r", brow[1])))
        stages.append((at_ms, tuple(eye), brow, look, ex))

    def lerp(a, b, t):
        return a + (b - a) * t

    # blink events → per-frame eyelid multiplier
    blink_mul = [1.0] * length
    for at_ms, _e, _b, _lk, ex in stages:
        curve = _BLINK_CURVES.get(ex.get("blink", ""))
        if not curve:
            continue
        start = round(at_ms / FRAME_MS) + 2   # lands just after the tween starts
        for j, v in enumerate(curve):
            if 0 <= start + j < length:
                blink_mul[start + j] = min(blink_mul[start + j], v)
        # a double blink event repeats naturally via its longer curve

    eye_out, brow_out, look_out = [], [], []
    for i in range(length):
        t_ms = i * FRAME_MS
        idx = 0
        for s, stage in enumerate(stages):
            if t_ms >= stage[0]:
                idx = s
        at, eye, brow, look, ex = stages[idx]
        if idx > 0 and t_ms - at < _FACE_TWEEN_MS:
            k = B._smoothstep((t_ms - at) / _FACE_TWEEN_MS)
            p = stages[idx - 1]
            eye = tuple(lerp(p[1][j], eye[j], k) for j in range(4))
            brow = tuple(
                tuple(lerp(p[2][s][j], brow[s][j], k) for j in range(3)) for s in range(2)
            )
            if look is not None and p[3] is not None:
                look = (lerp(p[3][0], look[0], k), lerp(p[3][1], look[1], k))
        # brow tremble: deterministic fast shudder inside its window
        tremble = ex.get("tremble")
        if tremble and 0 <= t_ms - at < tremble:
            j = math.sin(i * 2.9) * 0.45
            brow = ((brow[0][0], brow[0][1] + j, brow[0][2]),
                    (brow[1][0], brow[1][1] - j * 0.8, brow[1][2]))
        eye_out.append(eye)
        brow_out.append(brow)
        look_out.append(look)
    fx_out = []
    for i in range(length):
        t_ms = i * FRAME_MS
        idx = 0
        for s, stage in enumerate(stages):
            if t_ms >= stage[0]:
                idx = s
        ex = stages[idx][4]
        fx_out.append((ex.get("pupil_shape"), ex.get("wink"), ex.get("decal"),
                       bool(ex.get("blush"))))
    return eye_out, brow_out, look_out, blink_mul, fx_out


def look_track(targets, hold_ms: int) -> list[tuple[float, float]]:
    """Pupil look targets snap, then hold — the runtime does not tween these."""
    frames = max(1, round(hold_ms / FRAME_MS))
    out: list[tuple[float, float]] = []
    for dx, dy in targets:
        out.extend([(dx, dy)] * frames)
    return out


def breathing(count: int, depth: float = 2.2) -> list[tuple[float, ...]]:
    """Idle bob so expression-only actions are not rendered on a frozen body."""
    out = []
    for i in range(count):
        phase = (i * B.ANIM_TICK_SCALE * 0.012) % 1.0
        out.append((math.sin(i * 0.03) * 0.4, -B._breath_curve(phase) * depth * 0.55, 1.0, 1.0))
    return out


# ── per-action timeline construction ─────────────────────────────

def _expression(action: str) -> tuple[tuple[float, float, float, float], tuple]:
    cue = B.ACTION_ACTING_CUES.get(action)
    if not cue:
        return NEUTRAL_EYE, NEUTRAL_BROW
    eyes, brows, _hold_ms, _blush = cue
    eye = B.JiajiaApp._EYE_MAP.get(eyes, NEUTRAL_EYE)
    brow = B.JiajiaApp._BROW_MAP.get(brows, NEUTRAL_BROW)
    return eye, brow


def _window_move_frames(action: str) -> tuple | None:
    """Rebuild the runtime's window-move keyframes deterministically.

    Mirrors JiajiaApp._run_window_move_action, which picks a random
    distance per call; a fixed seed keeps GIFs reproducible.
    """
    random.seed(f"paperclip-{action}")
    direction = 1
    if action == "twist_scoot":
        dx = direction * 16
        return ((-direction * 4, 0, 0.96, 1.04, 60), (dx, 0, 1.06, 0.94, 130), (dx, 0, 1.0, 1.0, 80))
    if action == "mini_hop_shift":
        dx = direction * 36
        return ((0, 8, 1.14, 0.78, 80), (dx * 0.55, -18, 0.90, 1.16, 95),
                (dx, 4, 1.07, 0.90, 80), (dx, 0, 1.0, 1.0, 70))
    if action == "relocate_hop":
        dx = direction * 60
        return ((0, 10, 1.18, 0.74, 110), (dx * 0.42, -42, 0.88, 1.22, 130),
                (dx * 0.78, -34, 0.94, 1.10, 120), (dx, 8, 1.10, 0.86, 95), (dx, 0, 1.0, 1.0, 100))
    if action == "roast_and_scoot":
        dx = direction * 15
        return ((-direction * 3, 0, 0.98, 1.04, 70), (dx, 0, 1.05, 0.94, 120), (dx, 0, 1.0, 1.0, 80))
    if action == "retreat_to_corner":
        dx, dy = -70.0, 22.0
        return ((dx * 0.12, 0, 0.96, 1.04, 90), (dx * 0.42, dy * 0.35, 0.90, 0.96, 130),
                (dx * 0.72, dy * 0.70, 0.86, 0.92, 130), (dx, dy, 0.92, 0.94, 120),
                (dx, dy, 1.0, 1.0, 100))
    if action == "drop_in":
        dy = 60.0
        return ((0, -dy, 1.0, 1.0, 1), (0, -dy * 0.45, 0.92, 1.12, 120),
                (0, 10, 1.14, 0.78, 95), (0, -4, 0.96, 1.05, 85), (0, 0, 1.0, 1.0, 80))
    if action == "zoomies":
        span = direction * 70
        return ((span * 0.5, -6, 0.88, 1.10, 90), (span, 0, 1.12, 0.90, 80),
                (span * 0.4, -8, 0.90, 1.08, 90), (-span * 0.35, -6, 0.88, 1.10, 100),
                (-span * 0.6, 0, 1.12, 0.90, 80), (-span * 0.2, -8, 0.92, 1.06, 90),
                (0, 0, 1.0, 1.0, 110))
    if action == "moonwalk":
        dx = direction * 72
        return ((0, 0, -1.0, 1.0, 110), (dx * 0.3, 3, -1.06, 0.94, 140),
                (dx * 0.45, -2, -0.98, 1.03, 110), (dx * 0.7, 3, -1.06, 0.94, 140),
                (dx * 0.85, -2, -0.98, 1.03, 110), (dx, 0, -1.0, 1.0, 120),
                (dx, 0, 1.0, 1.0, 130))
    if action == "pounce":
        dx = direction * 62
        return ((-direction * 6, 4, 1.12, 0.84, 200), (-direction * 8, 5, 1.14, 0.82, 150),
                (dx * 0.7, -22, 0.86, 1.18, 110), (dx, 6, 1.18, 0.82, 90),
                (dx, -4, 0.96, 1.05, 80), (dx, 0, 1.0, 1.0, 90))
    return None


# actions whose visible performance is expression + tail/inner only
_MICRO_EXPRESSIONS: dict[str, tuple[str, str, str]] = {
    # action: (eye pose key, brow pose key, tail motion)
    "micro_focus_pause": ("soft", "soft", ""),
    "micro_side_eye": ("side_eye", "skeptical", "tail_tip_flick"),
    "micro_brow_judge": ("side_eye", "judge", ""),
    "micro_snap_innocent": ("innocent_round", "innocent", "tail_guilty_tuck"),
    "micro_caught_guilty": ("guilty_round", "worried", "tail_guilty_tuck"),
    "micro_holding_laugh": ("smug_half", "smug_arch", "tail_smug_sway"),
    "micro_peek_up": ("peek_up", "droop", "tail_sleepy_droop"),
    "micro_soften": ("soft", "soft", ""),
    "micro_tiny_proud": ("proud", "proud", ""),
    "micro_soft_reset": ("round", "neutral", ""),
}

# costume / prop actions: the props themselves are runtime canvas items, so the
# GIF shows the body performance and expression beat those sequences drive.
_COSTUME_BODY_FRAMES: dict[str, tuple] = {
    "britclip_enter": ((0.0, 0.0, 1.0, 1.0, 80), (-6.0, 4.0, 0.92, 1.07, 320),
                       (-10.0, 2.0, 0.89, 1.10, 720), (-4.0, -1.0, 0.97, 1.03, 320),
                       (0.0, 0.0, 1.0, 1.0, 280)),
    "britclip_exit": ((0.0, 0.0, 1.0, 1.0, 80), (-5.0, 3.0, 0.93, 1.06, 260),
                      (-8.0, 1.0, 0.90, 1.09, 520), (-2.0, 0.0, 0.98, 1.02, 220),
                      (0.0, 0.0, 1.0, 1.0, 200)),
}


def build_timeline(action: str) -> tuple[list[Pose], str]:
    """Return (frames, coverage) for one action.

    coverage: full | body | expression — how much of the runtime performance the
    GIF can show (props and particles are canvas-only and are not drawn).
    """
    eye, brow = _expression(action)
    tail_motion = B.ACTION_TAIL_MOTIONS.get(action, "")
    inner_gesture = B.ACTION_INNER_GESTURES.get(action, "")
    body: list[tuple[float, ...]] = []
    look: list[tuple[float, float]] = []
    blink: list[float] = []
    coverage = "full"

    if action in B.ACTION_FRAMES:
        body = body_track(action)
    elif action in {"melt", "meltdown"}:
        sink = body_track(action, B.MELT_SINK_FRAMES, lambda t: t ** 3)
        hold = [sink[-1]] * max(1, round(B.MELT_PUDDLE_HOLD_MS / FRAME_MS))
        recover = _interpolate(B.MELT_RECOVERY_FRAMES, B._smoothstep, 4, start=sink[-1])
        body = sink + hold + recover
        tail_motion = tail_motion or "tail_sleepy_droop"
    elif action == "wiggle":
        frames = tuple((0.0, 0.0, sx, sy, d) for sx, sy, d in B.WIGGLE_FRAMES)
        body = body_track(action, frames)
    elif action in B.PAPER_PROP_ACTIONS:
        cue = B.PAPER_PROP_ACTIONS[action]
        body = body_track(action, cue["frames"], B._ease_out_sine)
        tail_motion = str(cue.get("tail") or "")
        inner_gesture = str(cue.get("inner") or "")
        eye = B.JiajiaApp._EYE_MAP.get(str(cue.get("eyes") or ""), eye)
        brow = B.JiajiaApp._BROW_MAP.get(str(cue.get("brows") or ""), brow)
        coverage = "body"  # the paper prop itself is a runtime canvas item
    elif action in B.MOVE_IDLE_ACTIONS:
        frames = _window_move_frames(action)
        if frames:
            body = body_track(action, frames)
    elif action in _COSTUME_BODY_FRAMES:
        body = body_track(action, _COSTUME_BODY_FRAMES[action], B._ease_out_sine)
        tail_motion = tail_motion or ("tail_alert_snap" if action == "britclip_enter" else "tail_alert_snap")
        inner_gesture = inner_gesture or ("inner_side_smirk" if action == "britclip_enter" else "inner_shy_retract")
        coverage = "body"  # hat / bow tie / cane are runtime canvas items
    elif action in {"tip_hat", "hat_tip_oops", "bow_tie_check", "cane_tap"}:
        body = body_track(action, ((0, 2, 1.02, 0.98, 140), (0, -2, 0.99, 1.02, 180),
                                   (0, 0, 1.0, 1.0, 160)), B._ease_out_sine)
        tail_motion = tail_motion or "tail_tip_flick"
        inner_gesture = inner_gesture or ("inner_cover_oops" if "oops" in action else "")
        coverage = "body"
    elif action in {"polite_bow", "nod", "bob"}:
        body = body_track("nod", B.ACTION_FRAMES["nod"])

    if (action in B.TAIL_MOTION_FRAMES or action in B.TAIL_OSCILLATIONS
            or action in B.TAIL_POSTURES):
        tail_motion = action
    if action in B.INNER_GESTURE_FRAMES:
        inner_gesture = action

    if action in ("blink", "fake_innocent_blink"):
        blink = [v for v, d in B.BLINK_FRAMES for _ in range(max(1, round(d / FRAME_MS)))]
    elif action == "slow_blink":
        blink = [v for v, d in B.SLOW_BLINK_FRAMES for _ in range(max(1, round(d / FRAME_MS)))]
    elif action == "scan":
        look = look_track(B.SCAN_LOOK_TARGETS, B.SCAN_LOOK_HOLD_MS)
    elif action == "peek":
        look = look_track(((2.4, -0.6), (2.4, -0.6), (0.6, -0.3), (0.0, 0.0)), 240)
    elif action == "micro_guilty_dart":
        look = [(dx, dy) for dx, dy, hold in B.GUILTY_DART_SEQUENCE
                for _ in range(max(1, round(hold / FRAME_MS)))]
    elif action == "oops_innocent_combo":
        look = look_track(((0.0, 0.0), (-2.8, -0.15), (2.7, -0.05), (-1.2, 0.3), (0.0, 0.0)), 190)
        eye = B.JiajiaApp._EYE_MAP["innocent_round"]
        brow = B.JiajiaApp._BROW_MAP["innocent"]
        tail_motion = "tail_frantic_innocent"
        inner_gesture = "inner_cover_oops"

    if action in _MICRO_EXPRESSIONS:
        eye_key, brow_key, micro_tail = _MICRO_EXPRESSIONS[action]
        eye = B.JiajiaApp._EYE_MAP.get(eye_key, eye)
        brow = B.JiajiaApp._BROW_MAP.get(brow_key, brow)
        tail_motion = tail_motion or micro_tail

    # tail-as-hand: while carrying (non-wag-style held cue), the tail holds a
    # steady carry pose with a micro-sway instead of running any wag motion
    cue_for_action = ACTION_PROP_CUES.get(action)
    hand_mode = bool(cue_for_action and cue_for_action.get("held")
                     and cue_for_action.get("tail_style", "hand") == "hand")
    if hand_mode:
        tail_motion = ""
    tail, tail_phases, tail_wave = tail_track(tail_motion) if tail_motion else ([], None, None)
    inner = inner_track(inner_gesture) if inner_gesture else []
    bend = bend_track(action)
    prop = prop_track(action)
    prop_poses = prop[0] if prop else []
    face = ACTION_FACE_SCRIPTS.get(action)
    face_len = round((face[-1][0] + 500) / FRAME_MS) if face else 0

    length = max(len(body), len(tail), len(inner), len(look), len(blink), len(bend),
                 len(prop_poses), face_len, 1)
    if not body:
        body = breathing(length)
        coverage = "body" if coverage == "body" else "expression"
    length = max(length, len(body))

    body = _pad_to(body, length, (0.0, 0.0, 1.0, 1.0))
    if hand_mode:
        # ease into the carry pose over ~220ms, then breathe with it
        tail = []
        for i in range(length):
            t = i * FRAME_MS / 1000.0
            target = B.tail_hand_pose(t)
            blend = B._smoothstep(min(1.0, (i * FRAME_MS) / 220.0))
            tail.append(tuple(v * blend for v in target))
    tail = _pad_to(tail, length, (0.0,) * 5) if tail else [(0.0,) * 5] * length
    inner = _pad_to(inner, length, (0.0,) * 4) if inner else [(0.0,) * 4] * length
    has_special_look = bool(look)
    look = _pad_to(look, length, (eye[0], eye[1])) if look else [(eye[0], eye[1])] * length
    blink = _pad_to(blink, length, 1.0) if blink else [1.0] * length
    bend = _pad_to(bend, length, (0.0, 0.0)) if bend else [(0.0, 0.0)] * length
    if face:
        face_eye, face_brow, face_look, face_blink, face_fx = face_tracks(face, length)

    frames: list[Pose] = []
    for i in range(length):
        if face:
            # staged face script: eyes/brows act along the prop's story; the
            # gaze uses the stage's look, else any special pupil choreography
            fe = face_eye[i]
            fl = face_look[i]
            if fl is not None:
                ldx, ldy = fl
            elif has_special_look:
                ldx, ldy = look[i]
            else:
                ldx, ldy = fe[0], fe[1]
            frame_eye = (ldx, ldy, fe[2], fe[3])
            frame_brow = face_brow[i]
            frame_blink = blink[i] * face_blink[i]
            frame_fx = face_fx[i]
        else:
            frame_eye = (look[i][0], look[i][1], eye[2], eye[3])
            frame_brow = brow
            frame_blink = blink[i]
            frame_fx = (None, None, None, False)
        frame: Pose = {
            "body": body[i],
            "bend": bend[i],
            "tail": tail[i],
            # follow-through: the tip plays the pose a few frames behind
            "tail_tip": tail[max(0, i - TAIL_LAG_FRAMES)],
            "s_phase_override": (tail_phases[min(i, len(tail_phases) - 1)]
                                 if tail_phases else None),
            "tail_wave": tail_wave,
            "inner": inner[i],
            "eye": frame_eye,
            "brow": frame_brow,
            "blink": frame_blink,
            "face_fx": frame_fx,
            "s_phase": i * TAIL_S_PHASE_STEP,
        }
        if prop and i < len(prop_poses):
            frame["prop"] = (prop[2], prop_poses[i], prop[1], prop[3],
                             i * FRAME_MS / 1000.0, prop[4], prop[5])
        frames.append(frame)
    # the prop has fully exited by the end; never freeze its last pose
    if frames and "prop" in frames[-1]:
        frames[-1] = {k: v for k, v in frames[-1].items() if k != "prop"}
    # rest beat so the loop reads as a performance, not a stutter
    frames = _hold(frames, max(4, round(320 / FRAME_MS)))
    return frames, coverage


# ── drawing ──────────────────────────────────────────────────────

def _to_stage(
    x: float,
    y: float,
    body: tuple[float, ...],
    bend: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    lean, hunch = bend
    if lean or hunch:
        x, y = bend_point(x, y, lean, hunch, pivot_y=B.PAL_SCALE_PIVOT_Y, top_y=B.PAL_PAD_Y)
    dx, dy, sx, sy = body
    tx = B.PAL_CENTER_X + (x - B.PAL_CENTER_X) * sx + dx
    ty = B.PAL_SCALE_PIVOT_Y + (y - B.PAL_SCALE_PIVOT_Y) * sy + dy
    return ((tx + OFFSET_X) * SS, (ty + OFFSET_Y) * SS)


def _stroke(draw, points, color, width=STROKE_W) -> None:
    if len(points) < 2:
        return
    w = max(1, round(width * SS))
    draw.line(points, fill=color, width=w, joint="curve")
    r = w / 2
    for x, y in (points[0], points[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)


def _oval(draw, bounds, body, fill, *, dx=0.0, dy=0.0, rx_scale=1.0, ry_scale=1.0,
          bend=(0.0, 0.0)) -> None:
    x1, y1, x2, y2 = bounds
    cx, cy = (x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy
    # bend shifts the center only (the ovals are circles riding the sheared
    # spine); radii scale with the body like the runtime's _actor_oval_bounds
    tx, ty = _to_stage(cx, cy, body, bend)
    _dx, _dy, sx, sy = body
    rx = abs((x2 - x1) / 2 * rx_scale * sx) * SS
    ry = abs((y2 - y1) / 2 * ry_scale * sy) * SS
    if rx < 0.5 or ry < 0.5:
        return
    draw.ellipse((tx - rx, ty - ry, tx + rx, ty + ry), fill=fill)


def _draw_local_prims(draw, prims, cx: float, cy: float, sx: float, sy: float) -> None:
    """Draw face-FX primitives centered on a stage point (local px * SS)."""
    for prim in prims:
        kind = prim[0]
        if kind == "line":
            _k, points, width, color = prim
            pts = [(cx + x * sx * SS, cy + y * sy * SS) for x, y in points]
            _stroke(draw, pts, color, width=width)
        elif kind == "polygon":
            _k, points, fill, outline, width = prim
            pts = [(cx + x * sx * SS, cy + y * sy * SS) for x, y in points]
            if fill:
                draw.polygon(pts, fill=fill)
            if outline and width > 0:
                _stroke(draw, [*pts, pts[0]], outline, width=width)
        elif kind == "oval":
            _k, ox, oy, rx, ry, fill, outline, width = prim
            tx, ty = cx + ox * sx * SS, cy + oy * sy * SS
            box = (tx - rx * sx * SS, ty - ry * sy * SS, tx + rx * sx * SS, ty + ry * sy * SS)
            if fill:
                draw.ellipse(box, fill=fill)
            if outline and width > 0:
                draw.ellipse(box, outline=outline, width=max(1, round(width * SS)))


def _draw_prop(draw, prop, body, bend, tail_tip_stage=None) -> None:
    shape_key, prop_pose, anchor, _over_face, t_seconds, held, grip = prop
    shape = PROP_SHAPES.get(shape_key)
    if not shape:
        return
    if shape_key in SHAPE_FX:
        shape = apply_shape_fx(shape_key, shape, t_seconds)
    pivot = GRIP_POINTS.get(shape_key, (0.0, 0.0)) if held else (0.0, 0.0)
    if held and tail_tip_stage is not None:
        # gripped by the tail tip: ride the tail, skip the body transform
        base_x = tail_tip_stage[0] + grip[0] * SS
        base_y = tail_tip_stage[1] + grip[1] * SS

        def project(x, y):
            return (base_x + x * SS, base_y + y * SS)

        rsx = rsy = 1.0
    else:
        origin = B._source_point(*anchor)

        def project(x, y):
            return _to_stage(origin[0] + x, origin[1] + y, body, bend)

        _dx, _dy, rsx, rsy = body
    for prim in transform_shape(shape, tuple(prop_pose), pivot=pivot):
        kind = prim[0]
        if kind == "line":
            _k, points, width, color = prim
            pts = [project(x, y) for x, y in points]
            _stroke(draw, pts, color, width=width)
        elif kind == "polygon":
            _k, points, fill, outline, width = prim
            pts = [project(x, y) for x, y in points]
            if fill:
                draw.polygon(pts, fill=fill)
            if outline and width > 0:
                _stroke(draw, [*pts, pts[0]], outline, width=width)
        elif kind == "oval":
            _k, cx, cy, rx, ry, fill, outline, width = prim
            tx, ty = project(cx, cy)
            prx = abs(rx * rsx) * SS
            pry = abs(ry * rsy) * SS
            if prx < 0.4 or pry < 0.4:
                continue
            box = (tx - prx, ty - pry, tx + prx, ty + pry)
            if fill:
                draw.ellipse(box, fill=fill)
            if outline and width > 0:
                draw.ellipse(box, outline=outline, width=max(1, round(width * SS)))


def render_frame(pose: Pose, label: str = "") -> Image.Image:
    image = Image.new("RGB", (STAGE_W * SS, STAGE_H * SS), BG)
    draw = ImageDraw.Draw(image)
    body = pose["body"]
    bend = pose.get("bend", (0.0, 0.0))
    prop = pose.get("prop")

    # inner core sits behind the body wire, like the runtime layer order
    chin_pts = posed_chin_points(CHIN_BASE, *pose["inner"])
    _stroke(draw, [_to_stage(x, y, body, bend) for x, y in chin_pts], B.WIRE)

    body_pts = [(BODY_BASE[i], BODY_BASE[i + 1]) for i in range(0, len(BODY_BASE), 2)]
    _stroke(draw, [_to_stage(x, y, body, bend) for x, y in body_pts], B.WIRE)

    phase_override = pose.get("s_phase_override")
    tail_pts = posed_tail_points(
        TAIL_BASE, *pose["tail"],
        tail_mode=TAIL_MODE,
        s_phase=phase_override if phase_override is not None else pose["s_phase"],
        tip_pose=pose.get("tail_tip"),
        wave_factor=pose.get("tail_wave"),
    )
    _stroke(draw, [_to_stage(x, y, body, bend) for x, y in tail_pts], B.WIRE)

    # held/floating props ride in front of the body but behind the face —
    # matching the runtime layering (only wearables cover the face)
    # floating props go behind the face; held props (in the hand) and worn
    # props draw on top of everything — a raised mug covers the face
    if prop and not prop[3] and not prop[5]:
        tail_tip_stage = _to_stage(*tail_pts[-1], body, bend)
        _draw_prop(draw, prop, body, bend, tail_tip_stage)

    eye_dx, eye_dy, pupil_scale, openness = pose["eye"]
    fx_shape, fx_wink, fx_decal, fx_blush = pose.get("face_fx", (None, None, None, False))

    if fx_blush:
        for cx, cy in ((57, 208), (213, 248)):
            bx, by = _to_stage(cx * B.PAL_SCALE + B.PAL_PAD_X, cy * B.PAL_SCALE + B.PAL_PAD_Y, body, bend)
            draw.ellipse((bx - 7 * SS, by - 3.4 * SS, bx + 7 * SS, by + 3.4 * SS), fill="#ffb3b3")

    # per-eye rendering: a wink closes one eye; shaped pupils replace round ones
    shaped = EYE_FX_SHAPES.get(fx_shape or "", (None, None))
    smile = EYE_FX_SHAPES["closed_smile"][0]
    per_eye = [shaped[0], shaped[1]]
    if fx_wink == "l":
        per_eye[0] = smile
    elif fx_wink == "r":
        per_eye[1] = smile

    for side, (sclera, bounds) in enumerate(((LEFT_SCLERA, LEFT_PUPIL), (RIGHT_SCLERA, RIGHT_PUPIL))):
        lid = max(0.06, openness)
        _oval(draw, sclera, body, B.EYE_WHITE, ry_scale=lid, bend=bend)
        prims = per_eye[side]
        if prims is not None:
            x1, y1, x2, y2 = bounds
            cx, cy = _to_stage((x1 + x2) / 2 + eye_dx * B.PAL_SCALE,
                               (y1 + y2) / 2 + eye_dy * B.PAL_SCALE, body, bend)
            _dxb, _dyb, bsx, bsy = body
            _draw_local_prims(draw, prims, cx, cy, abs(bsx), abs(bsy))
        else:
            pupil_ry = max(0.04, pose["blink"] * pupil_scale * openness)
            _oval(draw, bounds, body, B.PUPIL,
                  dx=eye_dx * B.PAL_SCALE, dy=eye_dy * B.PAL_SCALE,
                  rx_scale=pupil_scale, ry_scale=pupil_ry, bend=bend)

    if fx_decal and fx_decal in FACE_DECALS:
        decal = FACE_DECALS[fx_decal]
        ax, ay = decal["anchor"]
        cx, cy = _to_stage(ax * B.PAL_SCALE + B.PAL_PAD_X, ay * B.PAL_SCALE + B.PAL_PAD_Y, body, bend)
        _dxb, _dyb, bsx, bsy = body
        _draw_local_prims(draw, decal["prims"], cx, cy, abs(bsx), abs(bsy))

    left_spec, right_spec = pose["brow"]
    for base, spec in ((LEFT_BROW_BASE, left_spec), (RIGHT_BROW_BASE, right_spec)):
        coords = B._brow_pose_coords(base, *spec)
        pts = [_to_stage(coords[i], coords[i + 1], body, bend) for i in range(0, len(coords), 2)]
        _stroke(draw, pts, B.BROW)

    # worn props (sunglasses, headphones, tissue) and held props go over the face
    if prop and (prop[3] or prop[5]):
        tail_tip_stage = _to_stage(*tail_pts[-1], body, bend) if prop[5] else None
        _draw_prop(draw, prop, body, bend, tail_tip_stage)

    if label:
        font = _load_font(12)
        draw.text((12 * SS, (STAGE_H - 20) * SS), label, font=font, fill=LABEL_COLOR)

    return image.resize((STAGE_W, STAGE_H), Image.Resampling.LANCZOS)


def _load_font(size: int):
    for candidate in (Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/arial.ttf")):
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size * SS)
    return ImageFont.load_default()


def save_gif(frames: list[Image.Image], path: Path) -> None:
    # the art is flat vector — 32 colors is visually lossless and ~20% smaller
    quantized = [f.convert("P", palette=Image.Palette.ADAPTIVE, colors=32) for f in frames]
    quantized[0].save(
        path,
        save_all=True,
        append_images=quantized[1:],
        duration=FRAME_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )


# ── signatures (so --check can spot stale GIFs) ──────────────────

def action_signature(action: str) -> str:
    """Hash everything that affects how this action renders."""
    parts = [
        action,
        repr(B.ACTION_FRAMES.get(action)),
        repr(B.ACTION_ANTICIPATION_FRAMES.get(action)),
        repr(B.ACTION_FOLLOW_THROUGH_FRAMES.get(action)),
        repr(B.ACTION_ACTING_CUES.get(action)),
        repr(B.ACTION_TAIL_MOTIONS.get(action)),
        repr(B.ACTION_INNER_GESTURES.get(action)),
        repr(B.TAIL_MOTION_FRAMES.get(action)),
        repr(B.INNER_GESTURE_FRAMES.get(action)),
        repr(B.PAPER_PROP_ACTIONS.get(action)),
        repr(B.ACTION_BODY_BEND.get(action)),
        repr(ACTION_PROP_CUES.get(action)),
        repr(PROP_SHAPES.get(str((ACTION_PROP_CUES.get(action) or {}).get("shape", "")))),
        repr(SHAPE_FX.get(str((ACTION_PROP_CUES.get(action) or {}).get("shape", "")))),
        repr(ACTION_FACE_SCRIPTS.get(action)),
        repr(sorted(EYE_FX_SHAPES)) + repr(sorted(FACE_DECALS)),
        repr(GRIP_POINTS.get(str((ACTION_PROP_CUES.get(action) or {}).get("shape", "")))),
        repr(_window_move_frames(action) if action in B.MOVE_IDLE_ACTIONS else None),
        easing_for_action(action).__name__,
        str(FRAME_MS),
        str(RENDER_VERSION),
        repr(B.TAIL_TIP_EXTENSION),
    ]
    tail = B.ACTION_TAIL_MOTIONS.get(action) or (
        action if (action in B.TAIL_MOTION_FRAMES or action in B.TAIL_OSCILLATIONS
                   or action in B.TAIL_POSTURES) else ""
    )
    inner = B.ACTION_INNER_GESTURES.get(action) or (action if action in B.INNER_GESTURE_FRAMES else "")
    parts.append(repr(B.TAIL_MOTION_FRAMES.get(tail)) + repr(B.TAIL_OSCILLATIONS.get(tail)) + repr(B.TAIL_POSTURES.get(tail)))
    parts.append(repr(B.INNER_GESTURE_FRAMES.get(inner)))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def build_manifest() -> dict:
    return {
        "frame_ms": FRAME_MS,
        "actions": {name: action_signature(name) for name in sorted(ACTION_LABELS)},
    }


# ── index page ───────────────────────────────────────────────────

def write_index(out_dir: Path, coverage: dict[str, str]) -> None:
    lines = [
        "# Action GIF Library",
        "",
        "Every action the pal can perform, rendered from the same keyframe tables,",
        "easing curves, and pose math the live app uses.",
        "",
        "Regenerate after changing any action:",
        "",
        "```powershell",
        "python scripts\\generate_action_gifs.py",
        "```",
        "",
        "`full` = complete performance. `body` = body and expression shown, but the",
        "action also uses runtime-only canvas props (paper, hat, cane). `expression`",
        "= the action is carried by eyes, brows, tail, or inner core over an idle body.",
        "",
    ]
    for group, names in ACTION_MENU_GROUPS:
        listed = [n for n in names if n in ACTION_LABELS]
        if not listed:
            continue
        lines += [f"## {group}", "", "| Action | Preview | Coverage | Notes |", "|---|---|---|---|"]
        for name in listed:
            desc = ACTION_DESCRIPTIONS.get(name, "").replace("|", "/")
            lines.append(
                f"| `{name}` | ![{name}]({name}.gif) | {coverage.get(name, '?')} | {desc} |"
            )
        lines.append("")

    grouped = {n for _g, names in ACTION_MENU_GROUPS for n in names}
    rest = [n for n in sorted(ACTION_LABELS) if n not in grouped]
    if rest:
        lines += ["## Other", "", "| Action | Preview | Coverage | Notes |", "|---|---|---|---|"]
        for name in rest:
            desc = ACTION_DESCRIPTIONS.get(name, "").replace("|", "/")
            lines.append(
                f"| `{name}` | ![{name}]({name}.gif) | {coverage.get(name, '?')} | {desc} |"
            )
        lines.append("")
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ── entry point ──────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Render one GIF per Jiajia action.")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "media" / "actions")
    parser.add_argument("--check", action="store_true",
                        help="Verify GIFs match the current action definitions; write nothing.")
    parser.add_argument("--only", nargs="*", default=None, help="Render only these actions.")
    args = parser.parse_args()

    out_dir: Path = args.out
    manifest_path = out_dir / "manifest.json"
    expected = build_manifest()

    if args.check:
        if not manifest_path.exists():
            print(f"stale: no manifest at {manifest_path} — run generate_action_gifs.py")
            return 1
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
        problems: list[str] = []
        if current.get("frame_ms") != expected["frame_ms"]:
            problems.append("frame rate changed")
        old, new = current.get("actions", {}), expected["actions"]
        for name in sorted(set(new) - set(old)):
            problems.append(f"missing GIF for new action: {name}")
        for name in sorted(set(old) - set(new)):
            problems.append(f"stale GIF for removed action: {name}")
        for name in sorted(set(old) & set(new)):
            if old[name] != new[name]:
                problems.append(f"keyframes changed since render: {name}")
            elif not (out_dir / f"{name}.gif").exists():
                problems.append(f"GIF file missing: {name}.gif")
        if problems:
            print(f"{len(problems)} problem(s):")
            for p in problems:
                print(" -", p)
            print("\nrun: python scripts/generate_action_gifs.py")
            return 1
        print(f"in sync — {len(new)} action GIFs match the current definitions")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    targets = args.only or sorted(ACTION_LABELS)
    coverage: dict[str, str] = {}

    for name in targets:
        if name not in ACTION_LABELS:
            print(f"skip {name}: not a known action")
            continue
        poses, cover = build_timeline(name)
        label = f"{ACTION_LABELS[name]}  ·  {name}"
        frames = [render_frame(pose, label) for pose in poses]
        save_gif(frames, out_dir / f"{name}.gif")
        coverage[name] = cover
        print(f"{name:24s} {len(frames):3d} frames  {len(frames) * FRAME_MS / 1000:.1f}s  [{cover}]")

    if not args.only:
        # drop GIFs for actions that no longer exist
        for gif in out_dir.glob("*.gif"):
            if gif.stem not in ACTION_LABELS:
                gif.unlink()
                print(f"removed stale {gif.name}")
        manifest_path.write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
        write_index(out_dir, coverage)
        print(f"\nwrote {len(coverage)} GIFs + index to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
