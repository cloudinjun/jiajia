"""Emotion-prop shapes and per-action prop cues, shared by runtime and renderer.

Every action gets an animated held/floating prop that performs the emotion
alongside the body: a question sign for thinking, a halo for fake innocence, a
rain cloud for sulking, a trophy for celebrating, an umbrella for drop-in…

Shapes are flat drawing primitives in local coordinates around the prop's
anchor point. The runtime draws them as Tk canvas items; the GIF renderer draws
the same data with PIL, so prop performances appear identically in both.

Primitive forms (local coordinates, y down):
    ("line", points, width, color)                    points: ((x, y), ...)
    ("polygon", points, fill, outline, width)
    ("oval", cx, cy, rx, ry, fill, outline, width)    # circles stay circles

A prop cue picks a shape, an anchor (source-space 318x550 coordinates), a
motion pattern, and a duration. `build_prop_timeline` expands the pattern into
`(dx, dy, rot_deg, scale, delay_ms)` keyframes: the prop appears at the first
pose and smoothsteps through the rest, then is removed.

Identity/costume props (britclip hat, paper props) are a separate system and
deliberately not covered here.
"""
from __future__ import annotations

import math
from typing import Any


Primitive = tuple
Shape = tuple[Primitive, ...]
PropPose = tuple[float, float, float, float]  # dx, dy, rot_deg, scale
PropTimeline = tuple[tuple[float, float, float, float, int], ...]


# ── shapes ───────────────────────────────────────────────────────

PROP_SHAPES: dict[str, Shape] = {
    # mug with a warm stripe and two steam wisps
    "coffee_mug": (
        ("polygon", ((-11, -2), (11, -2), (9, 16), (-9, 16)), "#fffdfd", "#b9bec7", 2.0),
        ("line", ((-10, 4), (10, 4)), 4.0, "#d97757"),
        ("oval", 0, -2, 11, 3.6, "#f2f2f2", "#b9bec7", 2.0),
        ("line", ((11, 1), (17, 3), (17, 9), (10, 12)), 3.0, "#b9bec7"),
        ("line", ((-4, -8), (-6, -13), (-3, -18)), 2.0, "#d8dee6"),
        ("line", ((3, -9), (1, -14), (4, -20)), 2.0, "#e3e8ee"),
    ),
    # straw broom: shaft, head, binding, bristle strokes
    "broom": (
        ("line", ((0, -30), (0, 12)), 3.2, "#9d7a3c"),
        ("polygon", ((-4, 12), (4, 12), (9, 30), (-9, 30)), "#e4c86e", "#c9a53f", 1.6),
        ("line", ((-4, 12), (4, 12)), 3.4, "#76505a"),
        ("line", ((-5, 19), (-7, 30)), 1.6, "#c9a53f"),
        ("line", ((0, 19), (0, 31)), 1.6, "#c9a53f"),
        ("line", ((5, 19), (7, 30)), 1.6, "#c9a53f"),
    ),
    # magnifier: hollow ring lens, gleam, handle
    "magnifier": (
        ("oval", 0, 0, 13, 13, "", "#6f7b8a", 3.5),
        ("line", ((-6, -7), (-1, -10)), 2.0, "#aeb9c6"),
        ("line", ((9, 9), (20, 20)), 4.0, "#6f7b8a"),
    ),
    # green pennant on a pole with a finial
    "flag": (
        ("line", ((0, 16), (0, -16)), 2.6, "#8a8f98"),
        ("polygon", ((0, -16), (18, -10), (0, -4)), "#6bcb77", "#4ea45e", 1.6),
        ("oval", 0, -17, 2.2, 2.2, "#f0b429", "", 0.0),
    ),
    # surrender flag for the full flop
    "white_flag": (
        ("line", ((0, 16), (0, -16)), 2.6, "#8a8f98"),
        ("polygon", ((0, -16), (18, -10), (0, -4)), "#fffdfd", "#b9bec7", 1.6),
        ("oval", 0, -17, 2.2, 2.2, "#b9bec7", "", 0.0),
    ),
    # headband + two earcups
    "headphones": (
        ("line", ((-20, 2), (-17, -6), (-9, -13), (0, -15), (9, -13), (17, -6), (20, 2)), 4.2, "#5b6270"),
        ("oval", -20, 6, 5, 7, "#454b57", "", 0.0),
        ("oval", 20, 6, 5, 7, "#454b57", "", 0.0),
    ),
    # handheld sign with a question mark
    "question_sign": (
        ("line", ((0, 8), (0, 22)), 2.6, "#9d7a3c"),
        ("polygon", ((-11, -8), (11, -8), (11, 8), (-11, 8)), "#fffdfd", "#8a8f98", 1.6),
        ("line", ((-3, -3), (-2.4, -5), (0, -5.6), (2.4, -5), (3, -3), (2, -1), (0, 0.4), (0, 1.6)), 2.8, "#6f62b8"),
        ("oval", 0, 4.6, 1.3, 1.3, "#6f62b8", "", 0.0),
    ),
    # handheld sign with a check mark
    "check_sign": (
        ("line", ((0, 8), (0, 22)), 2.6, "#9d7a3c"),
        ("polygon", ((-11, -8), (11, -8), (11, 8), (-11, 8)), "#fffdfd", "#8a8f98", 1.6),
        ("line", ((-5.5, -0.5), (-1.5, 3.5), (6, -4.5)), 3.0, "#10a37f"),
    ),
    # warning triangle with an exclamation mark
    "alert_sign": (
        ("polygon", ((0, -11), (11, 8), (-11, 8)), "#ffd93d", "#d4a017", 2.0),
        ("line", ((0, -4), (0, 2)), 2.4, "#7a5b00"),
        ("oval", 0, 5, 1.3, 1.3, "#7a5b00", "", 0.0),
    ),
    # a proper storm cloud — wider than the body, five streaks of rain
    "rain_cloud": (
        ("oval", -12, 1, 8, 6.5, "#a6afbc", "", 0.0),
        ("oval", 0, -3, 10, 8, "#a6afbc", "", 0.0),
        ("oval", 12, 1, 8, 6.5, "#a6afbc", "", 0.0),
        ("polygon", ((-17, 3), (17, 3), (17, 7.5), (-17, 7.5)), "#a6afbc", "", 0.0),
        ("line", ((-12, 10), (-14, 22)), 2.0, "#72b6e8"),
        ("line", ((-6, 11), (-8, 24)), 2.0, "#72b6e8"),
        ("line", ((0, 10), (-2, 23)), 2.0, "#72b6e8"),
        ("line", ((6, 11), (4, 24)), 2.0, "#72b6e8"),
        ("line", ((12, 10), (10, 22)), 2.0, "#72b6e8"),
    ),
    # twin-bell alarm clock
    "alarm_clock": (
        ("oval", -6, -9, 3.5, 3, "#d4a017", "", 0.0),
        ("oval", 6, -9, 3.5, 3, "#d4a017", "", 0.0),
        ("oval", 0, 0, 10, 10, "#fffdfd", "#6f7b8a", 2.5),
        ("line", ((0, 0), (0, -6)), 2.0, "#402a32"),
        ("line", ((0, 0), (4, 2)), 2.0, "#402a32"),
        ("line", ((-7, 8), (-9, 12)), 2.0, "#6f7b8a"),
        ("line", ((7, 8), (9, 12)), 2.0, "#6f7b8a"),
    ),
    # thermometer blowing its top
    "thermometer": (
        ("polygon", ((-2.5, -13), (2.5, -13), (2.5, 8), (-2.5, 8)), "#fffdfd", "#8a8f98", 1.6),
        ("oval", 0, 11, 5, 5, "#d65b4a", "", 0.0),
        ("line", ((0, 8), (0, -10)), 3.0, "#d65b4a"),
        ("line", ((-2, -15), (-4, -18)), 1.6, "#d65b4a"),
        ("line", ((0, -15), (0, -19)), 1.6, "#d65b4a"),
        ("line", ((2, -15), (4, -18)), 1.6, "#d65b4a"),
    ),
    # instant-cool sunglasses
    "sunglasses": (
        ("polygon", ((-16, -4), (-3, -4), (-4, 5), (-15, 5)), "#2f3540", "", 0.0),
        ("polygon", ((3, -4), (16, -4), (15, 5), (4, 5)), "#2f3540", "", 0.0),
        ("line", ((-3, -2), (3, -2)), 2.0, "#2f3540"),
        ("line", ((-13, -2), (-9, 1)), 1.6, "#8f97a5"),
    ),
    # golden innocence halo
    "halo": (
        ("oval", 0, 0, 14, 4.5, "", "#f0c419", 3.0),
    ),
    # binoculars seen head-on: two barrels, centre bridge, big glass fronts
    "binoculars": (
        ("polygon", ((-14, -8), (-4, -8), (-4, 8), (-14, 8)), "#5b6270", "#3d434e", 1.5),
        ("polygon", ((4, -8), (14, -8), (14, 8), (4, 8)), "#5b6270", "#3d434e", 1.5),
        ("polygon", ((-4.5, -3), (4.5, -3), (4.5, 3), (-4.5, 3)), "#454b57", "", 0.0),
        ("oval", 0, -5.5, 2.2, 2.2, "#8f97a5", "", 0.0),          # focus wheel
        ("oval", -9, 0, 4.6, 4.6, "#9fd8ef", "#3d434e", 1.4),     # objective lens
        ("oval", 9, 0, 4.6, 4.6, "#9fd8ef", "#3d434e", 1.4),
        ("line", ((-11, -2.4), (-9.6, -0.9)), 1.4, "#f4fbff"),    # glints
        ("line", ((7, -2.4), (8.4, -0.9)), 1.4, "#f4fbff"),
    ),
    # victory trophy
    "trophy": (
        ("polygon", ((-9, -10), (9, -10), (6, 2), (-6, 2)), "#f0c419", "#c79c12", 1.6),
        ("line", ((-9, -8), (-13, -6), (-11, -1), (-7, 0)), 2.0, "#c79c12"),
        ("line", ((9, -8), (13, -6), (11, -1), (7, 0)), 2.0, "#c79c12"),
        ("polygon", ((-2, 2), (2, 2), (2, 6), (-2, 6)), "#c79c12", "", 0.0),
        ("polygon", ((-7, 6), (7, 6), (7, 10), (-7, 10)), "#a97e0f", "", 0.0),
    ),
    # star-tipped wand
    "star_wand": (
        ("line", ((0, 16), (0, -6)), 2.5, "#b06bd4"),
        ("polygon", ((0, -19), (1.76, -14.4), (6.66, -14.16), (2.85, -10.9), (4.11, -6.34),
                     (0, -9), (-4.11, -6.34), (-2.85, -10.9), (-6.66, -14.16), (-1.76, -14.4)),
         "#ffd93d", "#d4a017", 1.4),
    ),
    # four-blade pinwheel on a stick
    "pinwheel": (
        ("line", ((0, 2), (0, 18)), 2.5, "#9d7a3c"),
        ("polygon", ((0, 0), (12, -4), (4, -12)), "#ff6b6b", "", 0.0),
        ("polygon", ((0, 0), (4, 12), (12, 4)), "#6bcb77", "", 0.0),
        ("polygon", ((0, 0), (-12, 4), (-4, 12)), "#4d96ff", "", 0.0),
        ("polygon", ((0, 0), (-4, -12), (-12, -4)), "#ffd93d", "", 0.0),
        ("oval", 0, 0, 2, 2, "#402a32", "", 0.0),
    ),
    # crumpled tissue
    "tissue": (
        ("polygon", ((-7, -5), (7, -6), (6, 6), (-6, 5)), "#fffdfd", "#c9ced6", 1.6),
        ("line", ((-4, -2), (3, -3)), 1.2, "#dde2e8"),
        ("line", ((-3, 2), (4, 1)), 1.2, "#dde2e8"),
    ),
    # six-spoke snowflake
    "snowflake": (
        ("line", ((0, -9), (0, 9)), 2.0, "#9fd8ef"),
        ("line", ((-7.8, -4.5), (7.8, 4.5)), 2.0, "#9fd8ef"),
        ("line", ((-7.8, 4.5), (7.8, -4.5)), 2.0, "#9fd8ef"),
        ("oval", 0, 0, 1.6, 1.6, "#cfeefc", "", 0.0),
    ),
    # tail-held service bell
    "bell": (
        ("polygon", ((-6, 2), (6, 2), (4, -6), (0, -8), (-4, -6)), "#f0c419", "#c79c12", 1.5),
        ("oval", 0, -8, 1.5, 1.5, "#c79c12", "", 0.0),
        ("line", ((-6, 2), (6, 2)), 2.0, "#c79c12"),
        ("oval", 0, 5, 1.8, 1.8, "#c79c12", "", 0.0),
    ),
    # clicky ballpoint pen
    "pen": (
        ("polygon", ((-1.8, -10), (1.8, -10), (1.8, 6), (-1.8, 6)), "#4d96ff", "#2f6fd0", 1.2),
        ("polygon", ((-1.8, 6), (1.8, 6), (0, 10)), "#2f3540", "", 0.0),
        ("oval", 0, -11, 1.6, 1.6, "#2f6fd0", "", 0.0),
    ),
    # tiny moving-day suitcase
    "suitcase": (
        ("polygon", ((-10, -6), (10, -6), (10, 8), (-10, 8)), "#b06b4a", "#8a4f34", 1.8),
        ("line", ((-4, -6), (-4, -10), (4, -10), (4, -6)), 2.2, "#8a4f34"),
        ("line", ((-10, 1), (10, 1)), 2.0, "#8a4f34"),
    ),
    # paraglider canopy with suspension lines, for floating down
    "parachute": (
        ("polygon", ((-18, 0), (-13, -7), (0, -10), (13, -7), (18, 0),
                     (12, -2), (6, -3), (0, -3.5), (-6, -3), (-12, -2)),
         "#ff8552", "#d0653a", 1.5),
        ("line", ((-16, 0), (-4, 16)), 1.6, "#8a8f98"),
        ("line", ((16, 0), (4, 16)), 1.6, "#8a8f98"),
    ),
    # scalloped umbrella with a crook handle
    "umbrella": (
        ("polygon", ((-14, 0), (-9, -6), (0, -8), (9, -6), (14, 0), (9, -2), (0, -3), (-9, -2)),
         "#ff8552", "#d0653a", 1.5),
        ("line", ((0, -8), (0, -12)), 2.0, "#d0653a"),
        ("line", ((0, -3), (0, 12)), 2.0, "#8a4f34"),
        ("line", ((0, 12), (3, 14), (5, 12)), 2.0, "#8a4f34"),
    ),
    # zoomies fuel
    "energy_drink": (
        ("polygon", ((-6, -9), (6, -9), (6, 9), (-6, 9)), "#6bcb77", "#4ea45e", 1.6),
        ("oval", 0, -9, 6, 2, "#c9ced6", "#8a8f98", 1.2),
        ("polygon", ((1, -4), (-3, 1), (0, 1), (-1, 5), (3, 0), (0, 0)), "#ffd93d", "", 0.0),
        ("oval", 0, -9, 1.5, 1.5, "#8a8f98", "", 0.0),
    ),
}


# ── grip points ──────────────────────────────────────────────────
# The tail tip is the HAND. A held prop attaches at its natural grip — the
# pole's butt, the mug's handle, the suitcase handle — and rotates around
# that point, never around its visual center. Local shape coordinates.

GRIP_POINTS: dict[str, tuple[float, float]] = {
    "flag": (0.0, 16.0),            # pole butt
    "white_flag": (0.0, 16.0),
    "star_wand": (0.0, 16.0),
    "question_sign": (0.0, 22.0),   # stick butt, sign rides above
    "check_sign": (0.0, 22.0),
    "broom": (0.0, -24.0),          # upper shaft, head sweeps below
    "coffee_mug": (17.0, 6.0),      # the handle
    "trophy": (0.0, 10.0),          # under the base — hoisted from below
    "magnifier": (20.0, 20.0),      # end of the handle
    "pen": (0.0, 2.0),              # pinched mid-barrel
    "bell": (0.0, -9.5),            # the top loop
    "pinwheel": (0.0, 18.0),        # stick butt
    "suitcase": (0.0, -10.0),       # the handle
    "energy_drink": (0.0, 2.0),     # gripped around the can
    "thermometer": (0.0, 4.0),      # held mid-tube
}

# ── anchors (source-space 318x550 coordinates) ───────────────────

ANCHOR_OVERHEAD = (150.0, -20.0)     # floating above the head
ANCHOR_HEAD_TOP = (150.0, 58.0)      # resting on the head (headphones)
ANCHOR_FACE_SIDE = (252.0, 208.0)    # raised beside the face
ANCHOR_EYES = (135.0, 175.0)         # across both eyes
ANCHOR_MOUTH = (150.0, 250.0)        # in front of the inner core
ANCHOR_TAIL_SIDE = (262.0, 300.0)    # held by the tail
ANCHOR_BODY_SIDE = (250.0, 330.0)    # low at the right side
ANCHOR_LEFT_SIDE = (52.0, 300.0)     # low at the left side
ANCHOR_GROUND = (140.0, 388.0)       # down at the floor


# ── per-action prop cues ─────────────────────────────────────────
# Every cue names a story pattern — how this prop enters, performs its
# meaning, and leaves. See _pattern_timeline for the choreography.

ACTION_PROP_CUES: dict[str, dict[str, Any]] = {
    # mood / body
    "jump": {"shape": "flag", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.25, "pattern": "brandish", "duration": 1150, "wave_deg": 24},
    "flop": {"shape": "white_flag", "anchor": ANCHOR_BODY_SIDE, "held": True, "size": 1.35, "pattern": "weak_raise", "duration": 1900},
    "melt": {"shape": "thermometer", "anchor": ANCHOR_FACE_SIDE, "held": True, "pattern": "pull_hold", "duration": 3000, "lift": (0, -22)},
    "dance": {"shape": "headphones", "anchor": ANCHOR_HEAD_TOP, "over_face": True, "size": 1.5, "pattern": "wear", "duration": 1900},
    "twirl": {"shape": "sunglasses", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.9, "base_rot": 14, "pattern": "wear", "duration": 1300},
    "stretch": {"shape": "coffee_mug", "anchor": ANCHOR_BODY_SIDE, "held": True, "size": 1.1, "pattern": "sip", "duration": 2100},
    "shake": {"shape": "alert_sign", "anchor": ANCHOR_OVERHEAD, "size": 1.3, "pattern": "slam_in", "duration": 1000},
    "happy_bounce": {"shape": "flag", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.25, "pattern": "brandish", "duration": 1000, "wave_deg": 22},
    "nod": {"shape": "check_sign", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.35, "pattern": "pull_hold", "duration": 900, "lift": (0, -18)},
    "thinking_tilt": {"shape": "question_sign", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.35, "pattern": "pull_hold", "duration": 1450, "lift": (8, -18)},
    "sleepy_sag": {"shape": "alarm_clock", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "ring", "duration": 2300},
    "startled_pop": {"shape": "alert_sign", "anchor": ANCHOR_OVERHEAD, "size": 1.3, "pattern": "slam_in", "duration": 950},
    "smug_sway": {"shape": "sunglasses", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.9, "base_rot": 14, "pattern": "wear", "duration": 1550},
    "sulk": {"shape": "rain_cloud", "anchor": ANCHOR_OVERHEAD, "size": 2.0, "pattern": "float_in", "duration": 2600},
    "hide": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1600},
    "wiggle": {"shape": "bell", "anchor": ANCHOR_TAIL_SIDE, "held": True, "tail_style": "wag", "tail_motion": "tail_bell_ring", "size": 1.25, "pattern": "brandish", "duration": 800, "wave_deg": 20},
    "blink": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 820},
    "peek": {"shape": "binoculars", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.2, "base_rot": 14, "pattern": "scan_hold", "duration": 1350, "sweep_px": 5},
    "scan": {"shape": "magnifier", "anchor": ANCHOR_FACE_SIDE, "held": True, "pattern": "scan_hold", "duration": 1450, "sweep_px": 16},
    "celebrate": {"shape": "trophy", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.35, "pattern": "present", "duration": 1550, "lift": (0, -30)},
    "spin_jump": {"shape": "star_wand", "anchor": ANCHOR_FACE_SIDE, "held": True, "pattern": "brandish", "duration": 1250, "wave_deg": 26},
    "excited_spin": {"shape": "pinwheel", "anchor": ANCHOR_FACE_SIDE, "held": True, "size": 1.2, "pattern": "spin", "duration": 1350, "spins": 2},
    "peekaboo": {"shape": "star_wand", "anchor": ANCHOR_FACE_SIDE, "held": True, "tail_style": "wag", "pattern": "brandish", "duration": 1450, "wave_deg": 24},
    "sneeze": {"shape": "tissue", "anchor": ANCHOR_MOUTH, "over_face": True, "size": 1.7, "pattern": "pluck", "duration": 1750, "toss_exit": True},
    "shiver": {"shape": "snowflake", "anchor": ANCHOR_OVERHEAD, "size": 1.3, "pattern": "drift_in", "duration": 1500},
    "curious_lean": {"shape": "magnifier", "anchor": ANCHOR_FACE_SIDE, "held": True, "pattern": "scan_hold", "duration": 1750, "sweep_px": 9},
    "patrol": {"shape": "binoculars", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.2, "base_rot": 14, "pattern": "scan_hold", "duration": 1600, "sweep_px": 7},
    # tail family
    "tail_wag": {"shape": "bell", "anchor": ANCHOR_TAIL_SIDE, "held": True, "tail_style": "wag", "tail_motion": "tail_bell_ring", "size": 1.25, "pattern": "brandish", "duration": 1100, "wave_deg": 22},
    "tail_idle_slow": {"shape": "bell", "anchor": ANCHOR_TAIL_SIDE, "held": True, "tail_style": "wag", "tail_motion": "tail_bell_jingle", "size": 1.25, "pattern": "brandish", "duration": 1500, "wave_deg": 9},
    "tail_tip_flick": {"shape": "pen", "anchor": ANCHOR_TAIL_SIDE, "held": True, "tail_style": "wag", "size": 1.25, "pattern": "pen_twirl", "duration": 1000},
    "tail_smug_sway": {"shape": "sunglasses", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.9, "base_rot": 14, "pattern": "wear", "duration": 1650},
    "tail_guilty_tuck": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1450},
    "tail_sleepy_droop": {"shape": "alarm_clock", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "ring", "duration": 1950},
    "tail_alert_snap": {"shape": "alert_sign", "anchor": ANCHOR_OVERHEAD, "size": 1.3, "pattern": "slam_in", "duration": 900},
    "tail_frantic_innocent": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1250, "wobble_deg": 10},
    "tail_raise_excited": {"shape": "bell", "anchor": ANCHOR_TAIL_SIDE, "held": True, "tail_style": "wag", "size": 1.25, "pattern": "brandish", "duration": 1900, "wave_deg": 8},
    "tail_question_hook": {"shape": "magnifier", "anchor": ANCHOR_FACE_SIDE, "held": True, "tail_style": "wag", "pattern": "scan_hold", "duration": 2100, "sweep_px": 8},
    "tail_bristle": {"shape": "alert_sign", "anchor": ANCHOR_OVERHEAD, "size": 1.3, "pattern": "slam_in", "duration": 1500},
    # inner family
    "inner_cover_oops": {"shape": "tissue", "anchor": ANCHOR_MOUTH, "over_face": True, "size": 1.7, "pattern": "pluck", "duration": 1250},
    "inner_side_smirk": {"shape": "sunglasses", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.9, "base_rot": 14, "pattern": "wear", "duration": 1050},
    "inner_shy_retract": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1300},
    "inner_droop": {"shape": "rain_cloud", "anchor": ANCHOR_OVERHEAD, "size": 2.0, "pattern": "float_in", "duration": 1900},
    "oops_innocent_combo": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1500, "wobble_deg": 9},
    # movement
    "twist_scoot": {"shape": "broom", "anchor": ANCHOR_GROUND, "held": True, "grip_offset": (0, 18), "pattern": "brandish", "duration": 900, "wave_deg": 14},
    "mini_hop_shift": {"shape": "suitcase", "anchor": ANCHOR_BODY_SIDE, "held": True, "size": 1.3, "pattern": "pull_hold", "duration": 900, "lift": (0, -4)},
    "relocate_hop": {"shape": "suitcase", "anchor": ANCHOR_BODY_SIDE, "held": True, "size": 1.3, "pattern": "pull_hold", "duration": 1100, "lift": (0, -4)},
    "roast_and_scoot": {"shape": "halo", "anchor": ANCHOR_OVERHEAD, "size": 1.25, "pattern": "bloom", "duration": 1000},
    "retreat_to_corner": {"shape": "suitcase", "anchor": ANCHOR_BODY_SIDE, "held": True, "size": 1.3, "pattern": "pull_hold", "duration": 1200, "lift": (0, -4)},
    "drop_in": {"shape": "parachute", "anchor": (150.0, -52.0), "size": 1.9, "pattern": "parachute", "duration": 1300},
    "zoomies": {"shape": "energy_drink", "anchor": ANCHOR_LEFT_SIDE, "held": True, "size": 1.15, "pattern": "sip", "duration": 1000, "toss_exit": True},
    "moonwalk": {"shape": "headphones", "anchor": ANCHOR_HEAD_TOP, "over_face": True, "size": 1.5, "pattern": "wear", "duration": 1100},
    "pounce": {"shape": "binoculars", "anchor": ANCHOR_EYES, "over_face": True, "size": 1.2, "base_rot": 14, "pattern": "scan_hold", "duration": 1000, "sweep_px": 5},
}


# ── shape FX: primitive-level animation (pure, shared) ───────────
# Per-shape effects evaluated from elapsed seconds, applied in local space
# before the pose transform. Entries: (fx_type, prim_index, *params).
#   flag_ripple  (idx, amp, speed)                cloth ripple away from the pole
#   wiggle_trail (idx, amp, speed)                snake a trail line (steam)
#   fall_loop    (idx, dist, period_s, delay_s)   falls and loops (rain), after delay
#   jitter_x     (idx, amp, speed)                primitive vibrates sideways (bells)
#   flash_fill   (idx, colors, speed[, delay_s])  cycle a polygon/oval fill color
#   flash_outline(idx, colors, speed[, delay_s])  cycle an outline color
#   flash_line   (idx, colors, speed[, delay_s])  cycle a line color; hidden before delay
#   rise_line    (idx, tip_to_y, rise_s, delay_s) line tip grows to a target (mercury)
#   rotate_all   (_,  deg_per_s)                  spin the whole shape

_HIDE_OFFSET = 9999.0  # parks a primitive far off-canvas until its moment

SHAPE_FX: dict[str, tuple[tuple, ...]] = {
    "flag": (("flag_ripple", 1, 2.4, 9.0),),
    "white_flag": (("flag_ripple", 1, 2.6, 7.0),),
    "rain_cloud": (
        # the cloud drifts in dry, then the downpour starts
        ("fall_loop", 4, 14.0, 0.95, 0.7),
        ("fall_loop", 5, 14.0, 1.30, 0.85),
        ("fall_loop", 6, 14.0, 1.10, 1.0),
        ("fall_loop", 7, 14.0, 1.22, 0.9),
        ("fall_loop", 8, 14.0, 1.05, 1.05),
    ),
    "coffee_mug": (
        ("wiggle_trail", 4, 1.8, 5.2),
        ("wiggle_trail", 5, 1.8, 6.4),
    ),
    "alert_sign": (("flash_fill", 0, ("#ffd93d", "#ffb02e"), 3.4),),
    "halo": (("flash_outline", 0, ("#f0c419", "#ffdd6b", "#fff1b8", "#ffdd6b"), 2.6),),
    "alarm_clock": (
        ("jitter_x", 0, 1.6, 26.0),
        ("jitter_x", 1, 1.6, 26.0),
    ),
    "thermometer": (
        # mercury climbs first, then the top blows
        ("rise_line", 3, -10.0, 1.9, 0.35),
        ("flash_line", 4, ("#d65b4a", "#ff8a75"), 6.0, 2.2),
        ("flash_line", 5, ("#ff8a75", "#d65b4a"), 6.0, 2.25),
        ("flash_line", 6, ("#d65b4a", "#ff8a75"), 6.0, 2.3),
    ),
    "star_wand": (("flash_fill", 1, ("#ffd93d", "#fff3ae"), 4.2),),
    "snowflake": (("rotate_all", -1, 40.0),),
}


def apply_shape_fx(shape_key: str, shape: Shape, t_seconds: float) -> Shape:
    """Return the shape with its time-based effects applied (local space)."""
    fx_list = SHAPE_FX.get(shape_key)
    if not fx_list:
        return shape
    prims = list(shape)
    for fx in fx_list:
        kind = fx[0]
        if kind == "rotate_all":
            ang = math.radians(fx[2] * t_seconds)
            cos_a, sin_a = math.cos(ang), math.sin(ang)
            rotated: list[Primitive] = []
            for prim in prims:
                if prim[0] == "oval":
                    _k, cx, cy, rx, ry, fill, outline, width = prim
                    rotated.append(("oval", cx * cos_a - cy * sin_a, cx * sin_a + cy * cos_a,
                                    rx, ry, fill, outline, width))
                else:
                    pts = tuple((x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in prim[1])
                    rotated.append((prim[0], pts, *prim[2:]))
            prims = rotated
            continue
        idx = fx[1]
        if idx >= len(prims):
            continue
        prim = prims[idx]
        if kind == "flag_ripple" and prim[0] in ("line", "polygon"):
            _fx, _i, amp, speed = fx
            pts = prim[1]
            max_x = max((abs(x) for x, _y in pts), default=1.0) or 1.0
            new_pts = tuple(
                (x, y + amp * math.sin(speed * t_seconds + x * 0.35) * (abs(x) / max_x))
                for x, y in pts
            )
            prims[idx] = (prim[0], new_pts, *prim[2:])
        elif kind == "wiggle_trail" and prim[0] == "line":
            _fx, _i, amp, speed = fx
            pts = prim[1]
            n = max(1, len(pts) - 1)
            new_pts = tuple(
                (x + amp * math.sin(speed * t_seconds + i * 1.3) * (i / n), y)
                for i, (x, y) in enumerate(pts)
            )
            prims[idx] = ("line", new_pts, *prim[2:])
        elif kind == "fall_loop" and prim[0] == "line":
            _fx, _i, dist, period, delay = fx
            if t_seconds < delay:
                new_pts = tuple((x + _HIDE_OFFSET, y) for x, y in prim[1])
            else:
                phase = ((t_seconds - delay) / period + idx * 0.37) % 1.0
                dy = dist * phase
                new_pts = tuple((x, y + dy) for x, y in prim[1])
            prims[idx] = ("line", new_pts, *prim[2:])
        elif kind == "jitter_x":
            _fx, _i, amp, speed = fx
            dx = amp * math.sin(speed * t_seconds + idx)
            if prim[0] == "oval":
                _k, cx, cy, rx, ry, fill, outline, width = prim
                prims[idx] = ("oval", cx + dx, cy, rx, ry, fill, outline, width)
            else:
                new_pts = tuple((x + dx, y) for x, y in prim[1])
                prims[idx] = (prim[0], new_pts, *prim[2:])
        elif kind == "rise_line" and prim[0] == "line":
            _fx, _i, tip_to, rise_s, delay = fx
            pts = prim[1]
            base_pt, tip_pt = pts[0], pts[-1]
            progress = 0.0 if t_seconds < delay else min(1.0, (t_seconds - delay) / rise_s)
            new_tip = (tip_pt[0], base_pt[1] + (tip_to - base_pt[1]) * progress)
            prims[idx] = ("line", (base_pt, new_tip), *prim[2:])
        elif kind in ("flash_fill", "flash_outline", "flash_line"):
            _fx, _i, colors, speed = fx[:4]
            delay = fx[4] if len(fx) > 4 else 0.0
            if t_seconds < delay:
                if kind == "flash_line" and prim[0] == "line":
                    # not yet: park the burst line off-canvas
                    prims[idx] = ("line", tuple((x + _HIDE_OFFSET, y) for x, y in prim[1]), *prim[2:])
                continue
            color = colors[int((t_seconds - delay) * speed) % len(colors)]
            if kind == "flash_line" and prim[0] == "line":
                prims[idx] = ("line", prim[1], prim[2], color)
            elif kind == "flash_fill":
                if prim[0] == "polygon":
                    prims[idx] = ("polygon", prim[1], color, prim[3], prim[4])
                elif prim[0] == "oval":
                    prims[idx] = ("oval", *prim[1:5], color, prim[6], prim[7])
            elif kind == "flash_outline":
                if prim[0] == "polygon":
                    prims[idx] = ("polygon", prim[1], prim[2], color, prim[4])
                elif prim[0] == "oval":
                    prims[idx] = ("oval", *prim[1:5], prim[5], color, prim[7])
    return tuple(prims)


def inertia_step(
    prev_extra: float,
    prev_dx: float,
    dx: float,
    dt_seconds: float,
    *,
    gain: float = 0.055,
    smoothing: float = 0.35,
    limit: float = 12.0,
) -> float:
    """Carried-object inertia: swing opposite to horizontal motion.

    Returns the new extra rotation (degrees) to add to the prop's pose. Call
    once per rendered frame with the previous result.
    """
    if dt_seconds <= 0:
        return prev_extra
    velocity = (dx - prev_dx) / dt_seconds
    target = max(-limit, min(limit, -velocity * gain))
    return prev_extra + (target - prev_extra) * smoothing


# ── story patterns → timeline expansion (pure, shared) ───────────
# Frames are (dx, dy, rot_deg, scale, squash, delay_ms). squash>0 flattens
# (wide+short), squash<0 narrows (tall+thin) — used for furling, landings,
# and crumpling. The prop appears at the first frame's pose.

PROP_SCALE = 1.65


def build_prop_timeline(cue: dict[str, Any]) -> PropTimeline:
    """Expand a prop cue's story pattern into pose keyframes."""
    size = PROP_SCALE * float(cue.get("size", 1.0))
    base_rot = float(cue.get("base_rot", 0.0))
    frames = list(_pattern_timeline(cue))
    if cue.get("held"):
        # a held prop never leaves the hand: performance displacement shrinks
        # to hand-motion range, the acting comes from rotation and tilt
        frames = [(dx * 0.35, dy * 0.35, rot, scale, squash, delay)
                  for dx, dy, rot, scale, squash, delay in frames]
    if cue.get("toss_exit") and len(frames) >= 2:
        # crumple, then fling it away along a spinning arc
        lx, ly, lrot, _ls, _lsq, _ld = frames[-2]
        frames[-1:] = [
            (lx, ly, lrot + 10, 0.8, 0.35, 110),
            (lx + 34, ly - 28, lrot + 60, 0.75, 0.35, 150),
            (lx + 120, ly + 46, lrot + 160, 0.6, 0.35, 200),
        ]
    return tuple(
        (dx, dy, rot + base_rot, scale * size, squash, delay)
        for dx, dy, rot, scale, squash, delay in frames
    )


def _mid(total: int, used: int) -> int:
    return max(240, total - used)


def _pattern_timeline(cue: dict[str, Any]) -> tuple[tuple[float, float, float, float, float, int], ...]:
    pattern = str(cue.get("pattern", "pull_hold"))
    total = int(cue.get("duration", 1600))

    if pattern == "brandish":
        # whipped out from behind the body, waved with meaning, put away
        deg = float(cue.get("wave_deg", 18))
        mid = _mid(total, 190 + 130 + 170)
        seg = max(95, mid // 4)
        return (
            (-26, 20, -50, 0.5, 0.0, 60),          # tucked behind the body
            (2, -4, 6, 1.06, -0.12, 130),          # whip out — slight overshoot
            (0, -2, -deg, 1.0, 0.0, seg),
            (1, -3, deg, 1.0, 0.0, seg),
            (0, -2, -deg, 1.0, 0.0, seg),
            (1, -3, deg * 0.5, 1.0, 0.0, mid - 3 * seg),
            (-26, 20, -50, 0.5, 0.0, 170),         # put away
        )
    if pattern == "pull_hold":
        # produced from behind, held up steady, tucked back
        lx, ly = cue.get("lift", (0, -14))
        mid = _mid(total, 60 + 150 + 170)
        seg = mid // 3
        return (
            (-24, 18, -40, 0.55, 0.0, 60),
            (lx, ly, 4, 1.05, -0.1, 150),          # up it comes
            (lx, ly - 1, -3, 1.0, 0.0, seg),
            (lx + 1, ly - 2, 2, 1.0, 0.0, seg),
            (lx, ly - 1, -2, 1.0, 0.0, mid - 2 * seg),
            (-24, 18, -35, 0.55, 0.0, 170),
        )
    if pattern == "sip":
        # pull out a drink, raise it to the face, tip it back — twice
        mid = _mid(total, 60 + 160 + 180)
        hold = mid // 4
        return (
            (-22, 22, -30, 0.6, 0.0, 60),
            (0, 2, 0, 1.0, -0.08, 160),            # in hand
            (2, -26, -5, 1.0, 0.0, hold),          # raise toward the face
            (1, -30, -14, 1.0, 0.0, hold),         # tip — glug
            (2, -26, -5, 1.0, 0.0, hold),
            (1, -31, -16, 1.0, 0.0, mid - 3 * hold),  # longer second pull
            (-2, 6, 0, 0.85, 0.0, 180),            # lower, satisfied
        )
    if pattern == "float_in":
        # weather arrives: drifts in from off-screen, hangs, drifts away
        mid = _mid(total, 460 + 420)
        seg = mid // 3
        return (
            (-195, -12, 0, 1.0, 0.0, 60),          # fully off-screen left
            (-48, -4, 2, 1.0, 0.0, 260),           # drifting in
            (0, 0, 0, 1.0, 0.0, 200),              # parks overhead
            (2, 2, -2, 1.0, 0.0, seg),             # hangs there, raining
            (-2, 0, 2, 1.0, 0.0, seg),
            (1, 2, -1, 1.0, 0.0, mid - 2 * seg),
            (70, -6, 3, 1.0, 0.0, 220),            # drifts off
            (195, -14, 4, 1.0, 0.0, 200),
        )
    if pattern == "parachute":
        # canopy already open overhead, swaying through the descent; settles
        # on touchdown, then folds and is whisked away
        mid = _mid(total, 60 + 240 + 240 + 200 + 190 + 200)
        return (
            (0, -14, -8, 1.0, 0.06, 60),           # descending under canopy
            (-7, -8, -14, 1.0, 0.06, 240),         # sways left…
            (7, -10, 14, 1.0, 0.06, 240),          # …sways right
            (-4, -4, -8, 1.0, 0.04, 200),
            (0, 2, 0, 1.0, 0.0, max(200, mid)),    # touchdown, canopy settles
            (0, 6, 0, 0.9, -0.5, 190),             # folds
            (0, -44, 0, 0.8, -0.75, 200),          # whisked away
        )
    if pattern == "unfurl":
        # furled umbrella drops in, pops open with a snap, later furls away
        mid = _mid(total, 60 + 170 + 130 + 90 + 200)
        seg = max(120, mid // 2)
        return (
            (0, -60, 0, 0.9, -0.75, 60),           # furled, high above
            (0, 0, 0, 1.0, -0.75, 170),            # drops to the head
            (0, -2, 0, 1.06, 0.18, 130),           # POP — open, slight over-spread
            (0, 0, 0, 1.0, 0.0, 90),               # settle
            (1, -1, -3, 1.0, 0.0, seg),            # held open
            (-1, 0, 3, 1.0, 0.0, mid - seg),
            (0, -4, 0, 0.95, -0.6, 130),           # furl
            (0, -55, 0, 0.85, -0.75, 200),         # lifted away
        )
    if pattern == "ring":
        # alarm clock: produced overhead, then RINGS — an angry rattle that is
        # still readable (72ms per half-swing; faster smears into noise)
        mid = _mid(total, 60 + 150 + 180)
        ring_seg = 72
        rings = max(4, min(10, mid // ring_seg))
        frames = [
            (0, 34, 0, 0.55, 0.0, 60),             # from below
            (0, 0, 0, 1.05, -0.1, 150),            # hoisted overhead
        ]
        for i in range(rings):
            side = -13 if i % 2 == 0 else 13
            frames.append((0, -1, side, 1.0, 0.06, ring_seg))
        rest = mid - rings * ring_seg
        if rest > 40:
            frames.append((0, 0, 0, 1.0, 0.0, rest))
        frames.append((0, 30, 20, 0.5, 0.0, 180))  # swatted away
        return tuple(frames)
    if pattern == "wear":
        # drops from above onto the face/head, lands with a bounce, later
        # lifted off upward
        mid = _mid(total, 60 + 180 + 110 + 200)
        seg = mid // 2
        return (
            (0, -46, 0, 0.9, 0.0, 60),             # above, incoming
            (0, 0, 0, 1.0, 0.22, 180),             # lands — squish
            (0, 0, 0, 1.0, 0.0, 110),              # settles snug
            (-1, 0, -2, 1.0, 0.0, seg),            # worn
            (1, 0, 2, 1.0, 0.0, mid - seg),
            (0, -50, -8, 0.92, 0.0, 200),          # lifted off
        )
    if pattern == "scan_hold":
        # raised to the eyes, then slowly panning left and right — searching
        px = float(cue.get("sweep_px", 10))
        mid = _mid(total, 60 + 170 + 170)
        seg = mid // 3
        return (
            (0, 30, 8, 0.6, 0.0, 60),              # from below
            (0, 0, 0, 1.0, -0.06, 170),            # up to the eyes
            (-px, 0, -6, 1.0, 0.0, seg),           # pan left…
            (px, 0, 6, 1.0, 0.0, seg),             # …pan right
            (-px * 0.5, 0, -3, 1.0, 0.0, mid - 2 * seg),
            (0, 26, 10, 0.6, 0.0, 170),            # lowered
        )
    if pattern == "bloom":
        # innocence switches on: spins open from a point, hovers, pops away
        wobble = float(cue.get("wobble_deg", 0))
        mid = _mid(total, 60 + 160 + 120)
        seg = mid // 3
        if wobble:
            middle = (
                (0, -2, -wobble, 1.0, 0.0, seg),
                (1, -1, wobble, 1.0, 0.0, seg),
                (0, -2, -wobble * 0.5, 1.0, 0.0, mid - 2 * seg),
            )
        else:
            middle = (
                (0, -2, -3, 1.0, 0.0, seg),
                (0, 1, 3, 1.0, 0.0, seg),
                (0, -1, -2, 1.0, 0.0, mid - 2 * seg),
            )
        return (
            (0, 4, -90, 0.15, 0.0, 60),            # a spark
            (0, -2, 10, 1.08, 0.0, 160),           # spins open wide
            *middle,
            (0, 0, 40, 0.1, 0.0, 120),             # pop — gone
        )
    if pattern == "slam_in":
        # warning sign slams down from above and shudders
        mid = _mid(total, 60 + 110 + 90 + 150)
        return (
            (0, -55, 0, 0.8, 0.0, 60),             # incoming!
            (0, 2, 0, 1.0, 0.3, 110),              # SLAM — flattens
            (0, -4, -5, 1.0, -0.08, 90),           # rebound
            (0, -2, 4, 1.0, 0.0, max(160, mid - 90)),  # shuddering hold (flashing)
            (0, -48, 6, 0.7, 0.0, 150),            # yanked away
        )
    if pattern == "present":
        # trophy hoisted high for the crowd, shown off, hugged back in
        lx, ly = cue.get("lift", (0, -28))
        mid = _mid(total, 60 + 200 + 170)
        seg = mid // 3
        return (
            (-20, 26, -35, 0.55, 0.0, 60),         # from behind
            (lx, ly, 0, 1.1, -0.08, 200),          # hoisted HIGH
            (lx - 2, ly, -7, 1.05, 0.0, seg),      # shown left
            (lx + 2, ly, 7, 1.05, 0.0, seg),       # shown right
            (lx, ly - 2, 0, 1.08, 0.0, mid - 2 * seg),
            (-14, 22, -20, 0.6, 0.0, 170),         # hugged back in
        )
    if pattern == "pluck":
        # tissue snatched out of the air, shaken open, pressed to the face
        mid = _mid(total, 60 + 130 + 100 + 170)
        seg = mid // 2
        return (
            (26, 30, 20, 0.4, -0.4, 60),           # pinched, folded
            (18, -8, -8, 1.0, -0.15, 130),         # snatched up
            (14, -4, 6, 1.05, 0.15, 100),          # shaken open — flap
            (0, 0, -4, 1.0, 0.0, seg),             # pressed to the face
            (1, 1, 3, 1.0, 0.0, mid - seg),
            (10, 16, 15, 0.7, 0.2, 170),           # balled up
        )
    if pattern == "drift_in":
        # a snowflake sways down from above like a falling leaf
        mid = _mid(total, 60 + 250 + 250 + 220)
        seg = max(160, mid)
        return (
            (10, -70, 0, 0.8, 0.0, 60),            # high above
            (-12, -40, 0, 1.0, 0.0, 250),          # sway left…
            (10, -14, 0, 1.0, 0.0, 250),           # …sway right
            (0, 0, 0, 1.0, 0.0, seg),              # hovers (spinning FX)
            (-8, 26, 0, 0.6, 0.0, 220),            # drifts down, melts away
        )
    if pattern == "pen_twirl":
        # pen clicked out, twirled a full turn, clicked away — impatience
        mid = _mid(total, 60 + 120 + 140)
        spin_seg = max(115, (mid - 140) // 2)
        return (
            (-18, 16, -30, 0.55, 0.0, 60),
            (0, -2, 0, 1.05, -0.15, 120),          # click — out
            (0, -3, 180, 1.0, 0.0, spin_seg),      # twirl…
            (0, -3, 360, 1.0, 0.0, spin_seg),      # …full turn
            (0, -2, 360, 1.0, 0.0, max(100, mid - 2 * spin_seg - 140)),
            (-18, 16, 330, 0.55, 0.0, 140),
        )
    if pattern == "weak_raise":
        # the white flag: rises slowly, exhausted, waves feebly, droops
        mid = _mid(total, 60 + 420 + 260)
        seg = mid // 2
        return (
            (0, 30, 25, 0.6, 0.0, 60),             # barely off the ground
            (0, -8, 12, 1.0, 0.0, 420),            # dragged up… so tired
            (1, -9, 4, 1.0, 0.0, seg),             # feeble wave
            (0, -8, 14, 1.0, 0.0, mid - seg),      # gives up mid-wave
            (0, 26, 30, 0.7, 0.0, 260),            # sags back down
        )
    if pattern == "spin":
        # pinwheel: pulled out, then the run makes it spin hard
        spins = max(1, int(cue.get("spins", 2)))
        mid = _mid(total, 60 + 150 + 170)
        seg = mid // 3
        third = spins * 360.0 / 3.0
        return (
            (-24, 18, -40, 0.55, 0.0, 60),
            (0, -2, 0, 1.05, -0.1, 150),
            (0, -2, third, 1.0, 0.0, seg),
            (0, -2, third * 2, 1.0, 0.0, seg),
            (0, -2, third * 3, 1.0, 0.0, mid - 2 * seg),
            (-24, 18, third * 3 - 30, 0.55, 0.0, 170),
        )
    # fallback: simple hold
    mid = _mid(total, 190 + 180)
    seg = mid // 3
    return (
        (0, 14, 0, 0.6, 0.0, 190),
        (0, -2, -3, 1.0, 0.0, seg),
        (0, 1, 3, 1.0, 0.0, seg),
        (0, -1, -2, 1.0, 0.0, mid - 2 * seg),
        (0, 8, 0, 0.6, 0.0, 180),
    )


def transform_shape(shape: Shape, pose, pivot: tuple[float, float] = (0.0, 0.0)) -> Shape:
    """Apply (dx, dy, rot_deg, scale[, squash]) to a shape in local space.

    squash>0 widens and flattens, squash<0 narrows and stretches — volume-ish
    preserving, applied before rotation. `pivot` is the local point that lands
    at (dx, dy) and that rotation swings around — for held props this is the
    grip point, so a flag waves around the pole butt in the tail's grasp.
    """
    dx, dy, rot, scale = pose[0], pose[1], pose[2], pose[3]
    squash = pose[4] if len(pose) > 4 else 0.0
    px, py = pivot
    sx = scale * (1.0 + squash)
    sy = scale * (1.0 - squash * 0.45)
    cos_r = math.cos(math.radians(rot))
    sin_r = math.sin(math.radians(rot))

    def xf(x: float, y: float) -> tuple[float, float]:
        x = (x - px) * sx
        y = (y - py) * sy
        return (x * cos_r - y * sin_r + dx, x * sin_r + y * cos_r + dy)

    out: list[Primitive] = []
    for prim in shape:
        kind = prim[0]
        if kind == "line":
            _k, points, width, color = prim
            out.append(("line", tuple(xf(x, y) for x, y in points), width * scale, color))
        elif kind == "polygon":
            _k, points, fill, outline, width = prim
            out.append(("polygon", tuple(xf(x, y) for x, y in points), fill, outline, width * scale))
        elif kind == "oval":
            _k, cx, cy, rx, ry, fill, outline, width = prim
            ncx, ncy = xf(cx, cy)
            out.append(("oval", ncx, ncy, rx * abs(sx), ry * abs(sy), fill, outline, width * scale))
    return tuple(out)


# ── face scripts: the eyes act WITH the prop ─────────────────────
# Each entry is a staged facial timeline synchronized to the prop's story:
#     (at_ms, eyes, brows, look)
# eyes/brows name poses from the runtime's _EYE_MAP/_BROW_MAP; look is a pupil
# direction (dx, dy) or None to leave the gaze alone. The face should NOTICE
# the prop (glance at it), REACT at the story's peak (startled by the alarm,
# eyes shut while sipping), and land an AFTERMATH beat.
# Actions with their own pupil choreography (scan, blink, oops combo) keep it:
# their scripts stage eyes/brows only.

FaceFrame = tuple[int, str, str, "tuple[float, float] | None"]

# ── eye FX & face decals: the generated expression sheets, distilled ─
# From the reference collections in assets/paperclip: pupils that change SHAPE
# (stars, hearts, spirals, X-eyes, flat-line disdain, >< squeeze), the smiling
# arc of a contented closed eye, and small symbols that hang on the face
# (tears, sweat, pallor lines, shock rays, a halo of dizzy stars).
# Primitives use the prop format, in local px around the pupil center (eye FX)
# or a source-space anchor (decals).

_STAR_PUPIL = (
    ("polygon", ((0, -7), (1.76, -2.43), (6.66, -2.16), (2.85, 0.93), (4.11, 5.66),
                 (0, 3), (-4.11, 5.66), (-2.85, 0.93), (-6.66, -2.16), (-1.76, -2.43)),
     "#402a32", "", 0.0),
)
_HEART_PUPIL = (
    ("polygon", ((0, 6.5), (-5.5, 0.5), (-7, -2.5), (-5.5, -5), (-2.8, -5.5),
                 (0, -3.2), (2.8, -5.5), (5.5, -5), (7, -2.5), (5.5, 0.5)),
     "#ff4d6d", "", 0.0),
)
_SPIRAL_PUPIL = (
    ("line", ((1, 0), (0.75, 1.3), (-1, 1.73), (-2.5, 0), (-1.5, -2.6), (1.75, -3.03),
              (4, 0), (2.25, 3.9), (-2.5, 4.33), (-5.5, 0), (-3, -5.2), (3.25, -5.63), (7, 0)),
     2.0, "#402a32"),
)
_X_PUPIL = (
    ("line", ((-4.5, -4.5), (4.5, 4.5)), 2.6, "#402a32"),
    ("line", ((-4.5, 4.5), (4.5, -4.5)), 2.6, "#402a32"),
)
_LINE_PUPIL = (("line", ((-5, 0), (5, 0)), 3.2, "#402a32"),)
_SMILE_LID = (("line", ((-6, 2), (0, -3.5), (6, 2)), 2.6, "#402a32"),)
_SQUEEZE_L = (("line", ((-4, -4.5), (2.5, 0), (-4, 4.5)), 2.6, "#402a32"),)
_SQUEEZE_R = (("line", ((4, -4.5), (-2.5, 0), (4, 4.5)), 2.6, "#402a32"),)

# key → (left-eye primitives, right-eye primitives); drawn in place of the
# round pupil at the pupil's current position
EYE_FX_SHAPES: dict[str, tuple[Shape, Shape]] = {
    "star": (_STAR_PUPIL, _STAR_PUPIL),
    "heart": (_HEART_PUPIL, _HEART_PUPIL),
    "spiral": (_SPIRAL_PUPIL, _SPIRAL_PUPIL),
    "x": (_X_PUPIL, _X_PUPIL),
    "line": (_LINE_PUPIL, _LINE_PUPIL),
    "closed_smile": (_SMILE_LID, _SMILE_LID),
    "squeeze": (_SQUEEZE_L, _SQUEEZE_R),
}

# face decals: small symbols that hang on the face; anchor in source space
FACE_DECALS: dict[str, dict[str, Any]] = {
    "tear": {
        "anchor": (24.0, 200.0),
        "prims": (
            ("polygon", ((0, -3.5), (2.2, 0), (1.6, 2.6), (0, 3.8), (-1.6, 2.6), (-2.2, 0)),
             "#72b6e8", "#5fa7d8", 1.0),
        ),
    },
    "tears": {
        "anchor": (135.0, 175.0),
        "prims": (
            ("line", ((-19, 2), (-19, 14)), 4.5, "#72b6e8"),
            ("line", ((19, 8), (19, 20)), 4.5, "#72b6e8"),
        ),
    },
    "sweat": {
        "anchor": (268.0, 118.0),
        "prims": (
            ("polygon", ((0, -3.5), (2.2, 0), (1.6, 2.6), (0, 3.8), (-1.6, 2.6), (-2.2, 0)),
             "#9ed7ff", "#72b6e8", 1.0),
        ),
    },
    "pale": {
        "anchor": (135.0, 128.0),
        "prims": (
            ("line", ((-24, -2), (-24, 6)), 1.8, "#9fb8d0"),
            ("line", ((-20, -4), (-20, 6)), 1.8, "#9fb8d0"),
            ("line", ((-16, -2), (-16, 6)), 1.8, "#9fb8d0"),
            ("line", ((14, 7), (14, 15)), 1.8, "#9fb8d0"),
            ("line", ((18, 5), (18, 15)), 1.8, "#9fb8d0"),
            ("line", ((22, 7), (22, 15)), 1.8, "#9fb8d0"),
        ),
    },
    "shock_lines": {
        "anchor": (150.0, -14.0),
        "prims": (
            ("line", ((-11, -4), (-17, -8)), 2.2, "#ff8800"),
            ("line", ((-5, -8), (-8, -15)), 2.2, "#ff8800"),
            ("line", ((0, -9), (0, -17)), 2.2, "#ff8800"),
            ("line", ((5, -8), (8, -15)), 2.2, "#ff8800"),
            ("line", ((11, -4), (17, -8)), 2.2, "#ff8800"),
        ),
    },
    "sigh": {
        "anchor": (92.0, 268.0),
        "prims": (
            ("oval", -3, 0, 4, 3, "#dfe6ee", "#b9c6d4", 1.0),
            ("oval", -9, 3, 3, 2.2, "#e8eef5", "#b9c6d4", 1.0),
            ("oval", -14, 6, 2, 1.6, "#eef3f8", "", 0.0),
        ),
    },
    "star_ring": {
        "anchor": (150.0, -16.0),
        "prims": (
            ("polygon", ((-14, -2), (-12.9, 0.4), (-10.5, 0.6), (-12.2, 2.2), (-11.7, 4.6),
                         (-14, 3.4), (-16.3, 4.6), (-15.8, 2.2), (-17.5, 0.6), (-15.1, 0.4)),
             "#ffd93d", "", 0.0),
            ("polygon", ((0, -6), (1.1, -3.6), (3.5, -3.4), (1.8, -1.8), (2.3, 0.6),
                         (0, -0.6), (-2.3, 0.6), (-1.8, -1.8), (-3.5, -3.4), (-1.1, -3.6)),
             "#ffd93d", "", 0.0),
            ("polygon", ((14, -2), (15.1, 0.4), (17.5, 0.6), (15.8, 2.2), (16.3, 4.6),
                         (14, 3.4), (11.7, 4.6), (12.2, 2.2), (10.5, 0.6), (12.9, 0.4)),
             "#ffd93d", "", 0.0),
            ("line", ((-17, 6), (-6, 8), (6, 8), (17, 6)), 1.4, "#b9a5e8"),
        ),
    },
}


# Rich face frames: (at_ms, eyes, brows, look, extras). extras channels:
#   pupil    0.68..1.18  pupil size (fear shrinks it, interest dilates it)
#   blink    quick | double | slow | flutter   staged blink event at this beat
#   brow_l / brow_r  (dx, dy, rot)  single-brow override (the cocked eyebrow)
#   tremble  ms          brow shudder (cold, dread, holding back tears)
#   openness 0..1        explicit eyelid level (drifting shut, squeezing)
#   pupil_shape          star | heart | spiral | x | line | closed_smile | squeeze
#                        pupils change SHAPE at emotional peaks (EYE_FX_SHAPES)
#   wink     "l" | "r"   one eye closed
#   decal                tear | tears | sweat | pale | shock_lines | sigh | star_ring
#                        a symbol hangs on the face for this beat (FACE_DECALS)
#   blush    True        cheek blush on for this beat

ACTION_FACE_SCRIPTS: dict[str, tuple[FaceFrame, ...]] = {
    # ── halo family: the innocence performance ──
    # blinking too hard, glancing at the halo, checking nobody saw
    "blink": (
        (0, "innocent_round", "innocent", None, {"blink": "double"}),
        (240, "innocent_round", "innocent", (0.8, -1.2), {"pupil": 1.1}),
        (500, "wide", "innocent", (-1.5, -0.3), None),
        (700, "wide", "innocent", (1.5, -0.3), None),
        (900, "innocent_round", "soft", (0.0, -0.2), {"blink": "quick"}),
    ),
    "hide": (
        (0, "guilty_round", "guilty", None, {"pupil": 0.9}),
        (200, "peek_up", "worried", (-2.0, -0.5), None),
        (420, "innocent_round", "innocent", (0.8, -1.2), {"blink": "double"}),
        (760, "innocent_round", "innocent", (0.0, -0.1), {"openness": 0.85, "blush": True}),
    ),
    "tail_guilty_tuck": (
        (0, "guilty_round", "guilty", (0.0, 0.2), {"pupil": 0.9}),
        (280, "innocent_round", "innocent", (0.9, -1.2), None),
        (560, "wide", "innocent", (-1.8, -0.2), {"blink": "double"}),
        (860, "innocent_round", "innocent", (0.0, -0.1), None),
    ),
    "inner_shy_retract": (
        (0, "guilty_round", "guilty", None, {"openness": 0.8}),
        (260, "innocent_round", "innocent", (0.8, -1.2), None),
        (600, "peek_up", "soft", (1.6, -0.6), {"blink": "slow", "blush": True}),
        (950, "peek_up", "soft", (1.2, -0.4), {"openness": 0.7}),
    ),
    "roast_and_scoot": (
        (0, "smug_half", "smug_arch", None, {"brow_r": (0.0, -2.6, 0.12)}),
        (220, "innocent_round", "innocent", (0.7, -1.2), {"blink": "double"}),
        (560, "innocent_round", "innocent", (0.0, -0.2), {"pupil": 1.08}),
    ),
    "tail_raise_excited": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (300, "round", "proud", (2.6, 0.4), None),
        (800, "sparkle", "proud", (0.0, -0.3), {"blink": "quick"}),
        (1500, "sparkle", "laugh", (0.0, -0.2), {"wink": "r"}),
    ),
    "tail_question_hook": (
        (0, "curious", "curious", None, {"pupil": 1.1}),
        (350, "round", "curious", (2.7, 0.3), None),
        (1000, "curious", "curious", (2.5, 0.2), {"brow_l": (-0.4, 1.6, -0.1)}),
        (1600, "round", "soft", (0.0, -0.2), {"blink": "quick"}),
    ),
    "tail_bristle": (
        (0, "wide", "panic", None, {"pupil": 0.8}),
        (150, "startled_dot", "panic", (0.3, -1.3), {"pupil": 0.7, "decal": "shock_lines"}),
        (600, "worried_wide", "worried", (0.2, -1.0), {"tremble": 350, "decal": "sweat"}),
        (1200, "suspicious_slit", "judge", (0.0, -0.2), None),
    ),
    "tail_frantic_innocent": (
        (0, "innocent_round", "innocent", (0.0, -0.2), {"blink": "quick"}),
        (240, "wide", "innocent", (-2.5, -0.4), {"pupil": 0.85}),
        (460, "wide", "innocent", (2.5, -0.4), None),
        (660, "wide", "innocent", (-1.8, -0.3), {"blink": "quick"}),
        (900, "innocent_round", "innocent", (0.0, -0.2), {"blink": "double"}),
    ),
    "oops_innocent_combo": (
        (0, "innocent_round", "innocent", None, {"pupil": 1.1}),
        (350, "wide", "panic", None, {"pupil": 0.8}),
        (650, "wide", "innocent", None, {"tremble": 300}),
        (1000, "innocent_round", "innocent", None, {"blink": "double"}),
    ),
    # ── storm cloud: see it, dread it, endure it, watch it leave ──
    "sulk": (
        (0, "peek_up", "sulk", (0.0, 0.2), {"openness": 0.75}),
        (240, "worried_wide", "worried", (-2.8, -1.0), {"pupil": 1.05}),
        (700, "peek_up", "sulk", (0.4, -1.4), None),
        (1050, "narrow", "sulk", (0.0, 0.3), {"tremble": 350, "decal": "tear"}),
        (1500, "narrow", "sulk", (0.0, 0.4), {"openness": 0.45, "blink": "slow", "decal": "tear"}),
        (2050, "peek_up", "sulk", (2.4, -1.0), None),
    ),
    "inner_droop": (
        (0, "sleepy_slit", "droop", (0.0, 0.2), {"openness": 0.4}),
        (240, "peek_up", "worried", (-2.6, -1.0), None),
        (700, "peek_up", "sulk", (0.4, -1.3), {"tremble": 300, "decal": "tear"}),
        (1150, "narrow", "droop", (0.0, 0.3), {"openness": 0.4, "blink": "slow"}),
    ),
    # ── alarm clock: drifting off → JOLTED → grumpy → dozing again ──
    "sleepy_sag": (
        (0, "sleepy_slit", "droop", None, {"openness": 0.28, "blink": "slow"}),
        (280, "sleepy_slit", "droop", None, {"openness": 0.18}),
        (400, "startled_dot", "panic", (0.3, -1.3), {"pupil": 0.7}),
        (700, "wide", "panic", (0.3, -1.2), {"blink": "quick", "pupil": 0.85}),
        (1000, "worried_wide", "worried", (0.2, -1.1), {"tremble": 400}),
        (1600, "narrow", "judge", (0.2, -1.0), None),
        (1950, "sleepy_slit", "droop", (0.0, 0.2), {"openness": 0.3, "blink": "slow"}),
    ),
    "tail_sleepy_droop": (
        (0, "sleepy_slit", "droop", None, {"openness": 0.3}),
        (380, "startled_dot", "panic", (0.3, -1.3), {"pupil": 0.72}),
        (700, "wide", "worried", (0.2, -1.1), {"blink": "quick"}),
        (1100, "worried_wide", "worried", (0.2, -1.0), {"tremble": 300}),
        (1600, "sleepy_slit", "droop", (0.0, 0.2), {"openness": 0.3, "blink": "slow"}),
    ),
    # ── trophy: eye it, gaze up as it rises, bask, hug it in ──
    "celebrate": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (140, "round", "proud", (2.2, 0.6), None),
        (420, "sparkle", "proud", (2.0, -1.3), {"pupil_shape": "star", "brow_r": (0.0, -2.4, 0.1)}),
        (750, "sparkle", "proud", (1.2, -1.2), None),
        (1000, "sparkle", "laugh", (2.6, -1.2), {"blink": "quick"}),
        (1300, "soft", "proud", (0.0, -0.2), {"openness": 0.8}),
    ),
    # ── signs: read your own sign, then turn to the audience ──
    "thinking_tilt": (
        (0, "curious", "curious", None, {"pupil": 1.08}),
        (300, "curious", "curious", (2.6, -0.6), None),
        (620, "narrow", "skeptical", (2.4, -0.5), {"brow_l": (-0.5, 1.8, -0.14)}),
        (900, "round", "curious", (0.0, -0.2), {"blink": "quick"}),
        (1250, "narrow", "skeptical", (0.0, 0.0), {"tremble": 250}),
    ),
    "nod": (
        (0, "round", "soft", None, None),
        (260, "round", "proud", (2.6, -0.6), {"pupil": 1.06}),
        (560, "proud", "proud", (0.0, -0.2), {"blink": "quick"}),
        (800, "proud", "proud", (0.0, -0.2), {"wink": "r", "brow_r": (0.0, -2.0, 0.08)}),
    ),
    # ── thermometer: watch the mercury climb, alarm at the top, wilt ──
    "melt": (
        (0, "worried_wide", "worried", None, None),
        (320, "round", "worried", (2.6, -0.4), None),
        (1200, "worried_wide", "worried", (2.6, -0.5), {"pupil": 0.9, "tremble": 400, "decal": "sweat"}),
        (2300, "startled_dot", "panic", (2.6, -0.6), {"pupil": 0.68}),
        (2650, "wide", "panic", (0.0, -0.2), {"blink": "quick"}),
        (2900, "round", "droop", (0.0, 0.3), {"pupil_shape": "x"}),
    ),
    # ── coffee: eyes sink shut for the sip, satisfied sparkle after ──
    "stretch": (
        (0, "soft", "soft", None, {"openness": 0.85}),
        (280, "round", "soft", (2.4, 0.6), {"pupil": 1.08}),
        (620, "half_closed", "soft", (1.8, 0.3), {"openness": 0.5}),
        (900, "soft", "soft", None, {"pupil_shape": "closed_smile"}),
        (1350, "half_closed", "soft", None, {"openness": 0.5}),
        (1600, "sparkle", "laugh", (0.0, -0.2), {"pupil_shape": "heart"}),
    ),
    # ── energy drink: chug blind, come up WIRED, eyelids fluttering ──
    "zoomies": (
        (0, "wide", "curious", None, {"pupil": 1.05}),
        (200, "round", "curious", (2.4, 0.5), None),
        (480, "closed", "soft", None, {"openness": 0.0}),
        (820, "wide", "panic", (0.0, -0.4), {"pupil": 0.8}),
        (1000, "sparkle", "panic", (0.0, -0.5), {"pupil_shape": "star", "blink": "flutter"}),
    ),
    # ── sunglasses: spot them dropping, wear them, brows stay cocky ──
    "smug_sway": (
        (0, "smug_half", "smug_arch", None, {"brow_r": (0.0, -2.4, 0.12)}),
        (120, "wide", "curious", (0.2, -1.3), {"pupil": 1.08}),
        (400, "round", "smug_arch", (0.0, 0.0), None),
        (900, "round", "smug_arch", (0.0, 0.0), {"brow_l": (-0.3, -2.4, -0.12)}),
        (1300, "smug_half", "smug_arch", (-1.4, 0.2), {"wink": "l"}),
    ),
    "twirl": (
        (0, "proud", "proud", None, None),
        (120, "wide", "curious", (0.2, -1.3), None),
        (400, "round", "smug_arch", (0.0, 0.0), {"brow_r": (0.0, -2.4, 0.1)}),
        (900, "proud", "proud", (0.0, -0.2), {"wink": "r"}),
    ),
    "tail_smug_sway": (
        (0, "smug_half", "smug_arch", None, {"brow_r": (0.0, -2.4, 0.12)}),
        (140, "wide", "curious", (0.2, -1.3), None),
        (460, "round", "smug_arch", (0.0, 0.0), None),
        (1000, "round", "smug_arch", (0.0, 0.0), {"brow_l": (-0.3, -2.4, -0.12)}),
        (1400, "smug_half", "smug_arch", (-1.4, 0.2), {"blink": "slow"}),
    ),
    "inner_side_smirk": (
        (0, "smug_half", "smug_arch", None, {"brow_r": (0.0, -2.5, 0.14)}),
        (120, "wide", "curious", (0.2, -1.3), None),
        (420, "round", "smug_arch", (0.0, 0.0), None),
        (850, "smug_half", "smug_arch", (-1.2, 0.2), {"blink": "slow"}),
    ),
    # ── headphones: eyes shut, lost in it; brows ride the beat ──
    "dance": (
        (0, "round", "laugh", None, {"pupil": 1.1}),
        (140, "wide", "curious", (0.2, -1.3), None),
        (500, "round", "laugh", None, {"pupil_shape": "closed_smile"}),
        (1100, "round", "laugh", None, {"pupil_shape": "closed_smile", "brow_l": (0.0, 1.2, -0.06), "brow_r": (0.0, -1.6, 0.1)}),
        (1550, "sparkle", "laugh", (0.0, -0.2), {"blink": "quick", "pupil": 1.1}),
    ),
    "moonwalk": (
        (0, "smug_half", "smug_arch", None, None),
        (140, "wide", "curious", (0.2, -1.3), None),
        (520, "round", "laugh", None, {"pupil_shape": "closed_smile"}),
        (1000, "smug_half", "smug_arch", (-1.2, 0.2), {"brow_r": (0.0, -2.3, 0.12)}),
    ),
    # ── magnifier: scrutiny narrows the pupils, one brow knits ──
    "scan": (
        (0, "curious", "curious", None, {"pupil": 1.08}),
        (280, "suspicious_slit", "judge", None, {"pupil": 0.92}),
        (700, "narrow", "judge", None, {"brow_l": (-0.5, 2.0, -0.14)}),
        (1100, "narrow", "skeptical", None, {"blink": "slow"}),
    ),
    "curious_lean": (
        (0, "curious", "curious", None, {"pupil": 1.1}),
        (300, "round", "curious", (2.6, -0.3), None),
        (700, "wide", "curious", (-2.6, -0.2), {"pupil": 1.15}),
        (1150, "round", "curious", (2.6, -0.2), {"blink": "quick"}),
        (1550, "proud", "proud", (0.0, -0.2), None),
    ),
    # ── binoculars cover the eyes: the brows carry the acting ──
    "peek": (
        (0, "curious", "curious", None, None),
        (300, "round", "judge", None, None),
        (700, "round", "judge", None, {"brow_l": (-0.4, 1.6, -0.1)}),
        (1050, "suspicious_slit", "judge", (0.0, 0.0), None),
    ),
    "patrol": (
        (0, "round", "flat", None, None),
        (300, "round", "judge", None, None),
        (800, "round", "judge", None, {"brow_r": (0.4, 1.4, 0.12)}),
        (1300, "suspicious_slit", "judge", (0.0, 0.0), {"blink": "slow"}),
    ),
    "pounce": (
        (0, "suspicious_slit", "judge", None, {"pupil": 0.9}),
        (280, "round", "judge", None, {"pupil": 0.8}),
        (650, "startled_dot", "panic", (0.0, 0.0), {"pupil": 0.7}),
        (850, "wide", "panic", (0.0, -0.2), None),
    ),
    # ── warning sign: pupils snap tiny at the slam, brows tremble ──
    "shake": (
        (0, "wide", "panic", None, {"pupil": 0.9}),
        (100, "startled_dot", "panic", (0.3, -1.4), {"pupil": 0.68, "decal": "shock_lines"}),
        (350, "wide", "panic", (0.3, -1.3), {"blink": "quick"}),
        (600, "worried_wide", "worried", (0.2, -1.2), {"tremble": 350, "decal": "sweat"}),
        (900, "guilty_round", "innocent", (0.0, -0.2), {"blink": "double"}),
    ),
    "startled_pop": (
        (0, "wide", "panic", None, {"pupil": 0.9}),
        (100, "startled_dot", "panic", (0.3, -1.4), {"pupil": 0.68, "decal": "shock_lines"}),
        (350, "wide", "panic", (0.3, -1.3), {"blink": "quick"}),
        (580, "worried_wide", "worried", (0.2, -1.2), {"tremble": 320, "decal": "sweat"}),
        (860, "guilty_round", "innocent", (0.0, -0.2), {"blink": "double"}),
    ),
    "tail_alert_snap": (
        (0, "wide", "panic", None, {"pupil": 0.9}),
        (100, "startled_dot", "panic", (0.3, -1.4), {"pupil": 0.7, "decal": "shock_lines"}),
        (340, "wide", "panic", (0.3, -1.2), {"blink": "quick"}),
        (560, "worried_wide", "worried", (0.2, -1.1), {"tremble": 280, "decal": "sweat"}),
        (800, "guilty_round", "innocent", (0.0, -0.2), {"blink": "double"}),
    ),
    # ── tissue: itchy brow tremble, squeeze shut, sheepish after ──
    "peekaboo": (
        (0, "curious", "curious", None, {"pupil": 1.05}),
        (250, "closed", "soft", None, {"openness": 0.0}),
        (900, "wide", "laugh", (0.0, -0.4), {"pupil": 1.15, "decal": "star_ring"}),
        (1250, "sparkle", "laugh", (0.0, -0.2), {"wink": "r"}),
    ),
    "sneeze": (
        (0, "narrow", "worried", None, {"tremble": 250}),
        (240, "round", "worried", (2.3, 0.4), None),
        (480, "narrow", "worried", None, {"openness": 0.5}),
        (620, "narrow", "worried", None, {"pupil_shape": "squeeze"}),
        (1050, "half_closed", "soft", None, {"openness": 0.5}),
        (1400, "innocent_round", "innocent", (0.0, -0.2), {"blink": "double", "pupil": 1.1}),
    ),
    "inner_cover_oops": (
        (0, "guilty_round", "innocent", None, {"pupil": 0.95}),
        (220, "round", "innocent", (2.3, 0.4), None),
        (480, "wide", "innocent", (-2.2, -0.3), {"pupil": 0.85}),
        (760, "wide", "innocent", (2.2, -0.3), {"blink": "quick"}),
        (1020, "innocent_round", "innocent", (0.0, -0.2), {"blink": "double"}),
    ),
    # ── snowflake: cold brow-shiver, gaze tracks the drifting flake ──
    "shiver": (
        (0, "worried_wide", "worried", None, {"tremble": 400, "decal": "pale"}),
        (240, "round", "worried", (0.5, -1.3), {"decal": "pale"}),
        (560, "round", "worried", (-0.8, -0.9), {"pupil": 1.05}),
        (900, "narrow", "sulk", (0.3, -0.3), {"openness": 0.5, "tremble": 300, "decal": "pale"}),
        (1300, "peek_up", "sulk", (0.0, 0.4), {"blink": "slow"}),
    ),
    # ── flags & wand: glance at it, wave it front-on, cocky brow ──
    "jump": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (180, "round", "proud", (2.5, -0.3), None),
        (480, "sparkle", "proud", (0.0, -0.3), {"blink": "quick"}),
        (750, "sparkle", "laugh", (0.0, -0.2), {"wink": "r", "brow_r": (0.0, -2.2, 0.1)}),
    ),
    "happy_bounce": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (170, "round", "proud", (2.5, -0.3), None),
        (460, "sparkle", "proud", (0.0, -0.3), {"blink": "quick"}),
        (700, "sparkle", "laugh", (0.0, -0.2), {"brow_r": (0.0, -2.2, 0.1)}),
    ),
    "spin_jump": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (180, "round", "proud", (2.5, -0.3), None),
        (520, "sparkle", "proud", (0.0, -0.3), {"blink": "quick"}),
        (800, "sparkle", "laugh", (0.0, -0.2), {"brow_r": (0.0, -2.2, 0.1)}),
    ),
    # ── bell on the tail: watch your own tail ring it, get pleased ──
    "tail_wag": (
        (0, "proud", "proud", None, None),
        (220, "round", "proud", (2.6, 0.6), {"pupil": 1.08}),
        (560, "sparkle", "laugh", (1.8, 0.3), {"blink": "quick"}),
        (850, "sparkle", "laugh", (1.5, 0.3), {"brow_r": (0.0, -2.0, 0.08)}),
    ),
    "wiggle": (
        (0, "round", "soft", None, None),
        (200, "round", "proud", (2.6, 0.6), {"pupil": 1.08}),
        (520, "sparkle", "laugh", (1.8, 0.3), {"blink": "quick"}),
    ),
    "tail_idle_slow": (
        (0, "soft", "soft", None, {"openness": 0.85}),
        (300, "round", "soft", (2.6, 0.6), None),
        (800, "soft", "soft", (0.6, 0.2), {"blink": "slow"}),
    ),
    # ── broom: chore-face, one brow pressed while eyeing the floor ──
    "twist_scoot": (
        (0, "narrow", "flat", None, None),
        (240, "round", "judge", (1.5, 1.2), {"pupil_shape": "line", "brow_l": (-0.4, 1.8, -0.12)}),
        (560, "narrow", "judge", (-1.0, 1.0), None),
        (780, "proud", "proud", (0.0, -0.2), {"blink": "quick"}),
    ),
    # ── pen: impatient, bored half-lid twirl, judgmental click-away ──
    "tail_tip_flick": (
        (0, "suspicious_slit", "skeptical", None, None),
        (240, "round", "flat", (2.5, 0.6), None),
        (520, "round", "flat", (1.8, 0.4), {"pupil_shape": "line"}),
        (820, "narrow", "judge", (0.0, 0.1), {"brow_r": (0.4, 1.2, 0.12)}),
    ),
    # ── white flag: too defeated to keep the eyes open ──
    "flop": (
        (0, "half_closed", "droop", None, {"openness": 0.4}),
        (450, "peek_up", "droop", (2.3, 0.2), {"decal": "tear"}),
        (900, "half_closed", "droop", None, {"openness": 0.2, "blink": "slow"}),
        (1250, "closed", "droop", None, {"openness": 0.0}),
        (1750, "half_closed", "droop", (0.0, 0.3), {"openness": 0.35, "decal": "sigh"}),
    ),
    # ── paraglider: tense descent, pre-landing clench, relieved blink ──
    "drop_in": (
        (0, "wide", "worried", (0.0, -1.2), {"pupil": 0.9}),
        (280, "wide", "worried", (-1.0, -1.0), None),
        (540, "wide", "worried", (1.0, -1.0), {"pupil": 0.85}),
        (830, "startled_dot", "panic", (0.0, -0.5), {"pupil": 0.75}),
        (950, "sparkle", "innocent", (0.0, -0.3), {"blink": "double"}),
        (1200, "round", "soft", (0.0, 0.0), {"pupil_shape": "closed_smile"}),
    ),
    # ── pinwheel: transfixed by the spin until the eyes cross ──
    "excited_spin": (
        (0, "sparkle", "laugh", None, {"pupil": 1.12}),
        (200, "round", "curious", (2.5, -0.2), None),
        (560, "wide", "laugh", (2.3, -0.3), {"pupil_shape": "star"}),
        (900, "wide", "laugh", (2.3, -0.3), {"pupil_shape": "spiral", "decal": "star_ring"}),
        (1150, "sparkle", "laugh", (0.0, -0.2), None),
    ),
    # ── suitcases: check the luggage, set the jaw toward the exit ──
    "mini_hop_shift": (
        (0, "round", "neutral", None, None),
        (240, "round", "soft", (2.4, 0.8), {"pupil": 1.05}),
        (520, "narrow", "flat", (-2.0, 0.0), {"brow_l": (-0.3, 1.4, -0.1)}),
        (760, "round", "flat", (-2.0, 0.0), {"blink": "quick"}),
    ),
    "relocate_hop": (
        (0, "round", "neutral", None, None),
        (260, "round", "soft", (2.4, 0.8), {"pupil": 1.05}),
        (600, "narrow", "flat", (-2.2, 0.0), {"brow_l": (-0.3, 1.4, -0.1)}),
        (900, "round", "flat", (-2.2, 0.0), {"blink": "quick"}),
    ),
    "retreat_to_corner": (
        (0, "peek_up", "sulk", None, {"openness": 0.7}),
        (260, "round", "sulk", (2.4, 0.8), None),
        (600, "peek_up", "sulk", (-2.2, 0.2), {"tremble": 300}),
        (950, "peek_up", "sulk", (-2.2, 0.3), {"openness": 0.6, "blink": "slow"}),
    ),
}


def prop_cue_duration_ms(action: str) -> int:
    cue = ACTION_PROP_CUES.get(action)
    if not cue:
        return 0
    return sum(int(frame[5]) for frame in build_prop_timeline(cue))
