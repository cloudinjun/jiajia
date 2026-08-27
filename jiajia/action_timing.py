"""How long an action actually runs — the single answer, for everyone.

This used to live only as a method on the app, which meant anything outside a
running window (the phrase audit, the tests, the fallback phrase table) had to
fake an app object to ask the question. Three callers each faking it their own
way is how two different ideas of "how long is this action" get to exist.

The app method now delegates here, so the sequencer, the audit and the tests are
all reading the same number.
"""
from __future__ import annotations

from .animation_resolver import AnimationResolver

from .pal_motion import (
    _POSTURE_ENTER_S,
    _POSTURE_EXIT_S,
    ACTION_FRAMES,
    INNER_GESTURE_FRAMES,
    MOVE_ACTION_DURATIONS,
    MELT_PUDDLE_HOLD_MS,
    MELT_RECOVERY_FRAMES,
    MELT_SINK_FRAMES,
    MOVE_IDLE_ACTIONS,
    PAPER_PROP_ACTIONS,
    SCAN_LOOK_HOLD_MS,
    SCAN_LOOK_TARGETS,
    TAIL_MOTION_FRAMES,
    TAIL_OSCILLATIONS,
    TAIL_POSTURES,
    WIGGLE_FRAMES,
)
from .prop_shapes import ACTION_PROP_CUES, prop_cue_duration_ms

# Durations for actions whose motion is not a frame table.
_FIXED_MS: dict[str, int] = {
    "oops_innocent_combo": 1500,
    "britclip_enter": 3200,
    "british_gentleman_suit_up": 3200,
    "britclip_exit": 2300,
    "hat_tip_oops": 950,
    "blink": 150,
}

_DEFAULT_RESOLVER = AnimationResolver()



def _as_float(value: object, default: float = 0.0) -> float:
    """Read a number out of an authored table without trusting it.

    The motion tables are hand-edited data, so a malformed cell should fall
    back to a sane duration rather than raising in the middle of a performance.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


def action_duration_ms(action_or_name: str, resolver: AnimationResolver | None = None) -> int:
    """Milliseconds the action runs for. 0 means face-only or unknown.

    A 0 is meaningful, not a failure: micro expressions land on their first
    frame and then hold, so they have no travel time to wait for.
    """
    resolved = (resolver or _DEFAULT_RESOLVER).resolve(action_or_name)
    action = resolved.action or action_or_name

    frames = ACTION_FRAMES.get(action)
    if frames:
        return sum(frame[-1] for frame in frames)

    # a prop held in the tail tip pins the tail's duration to the prop's
    cue = ACTION_PROP_CUES.get(action)
    if cue and cue.get("held") and cue.get("tail_style") == "wag":
        return prop_cue_duration_ms(action) + 160

    osc = TAIL_OSCILLATIONS.get(action)
    if osc:
        freq = _as_float(osc.get("freq"))
        if freq:
            return round(_as_float(osc.get("cycles")) / freq * 1000) + 160

    posture = TAIL_POSTURES.get(action)
    if posture:
        return round((_POSTURE_ENTER_S + _POSTURE_EXIT_S) * 1000) + _as_int(posture.get("hold_ms")) + 180

    tail_frames = TAIL_MOTION_FRAMES.get(action)
    if tail_frames:
        return sum(frame[-1] for frame in tail_frames) + 140

    inner_frames = INNER_GESTURE_FRAMES.get(action)
    if inner_frames:
        return sum(frame[-1] for frame in inner_frames) + 130

    # A paper prop has two clocks: the body movement that raises it, and how
    # long the paper then stays up. Sequencing cares about the first — that is
    # the part a following step can cut into. The decoration outliving the beat
    # is deliberate, and belongs to its own channel.
    paper = PAPER_PROP_ACTIONS.get(action)
    if paper:
        frames = paper.get("frames") or ()
        if frames:
            return sum(int(frame[-1]) for frame in frames)

    # melt is sink + puddle hold + recovery, not one frame table
    if action in {"melt", "meltdown"}:
        return (
            sum(int(f[-1]) for f in MELT_SINK_FRAMES)
            + int(MELT_PUDDLE_HOLD_MS)
            + sum(int(f[-1]) for f in MELT_RECOVERY_FRAMES)
        )

    if action in _FIXED_MS:
        return _FIXED_MS[action]
    if action == "scan":
        return SCAN_LOOK_HOLD_MS * len(SCAN_LOOK_TARGETS)
    if action == "wiggle":
        return sum(frame[2] for frame in WIGGLE_FRAMES)
    if action in MOVE_IDLE_ACTIONS:
        return MOVE_ACTION_DURATIONS.get(action, 760)
    return 0
