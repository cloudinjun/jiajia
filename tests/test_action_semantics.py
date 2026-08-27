"""Rules about what an action is allowed to MEAN, not just whether it runs.

Every failure here was a real bug: a blink that played a fake-innocent skit, a
"low-pressure companionship" loop that rang an alarm clock, a tail group whose
GIFs showed props instead of tails, and an alert snap that crossed 63px in
425ms with no hold. None of them raised an error or failed a test — they just
looked wrong, which is the hardest kind of bug to notice in an animation
library. These assertions make that class of mistake loud.
"""
from __future__ import annotations

import math
import unittest

from jiajia.actions import ACTION_LABELS, ACTION_MENU_GROUPS
from jiajia.pal_geometry import TAIL_CURVES, TAIL_START
from jiajia.animation_resolver import ANIMATION_ALIASES
from jiajia.pal_motion import (
    ACTION_FRAMES, ACTION_TAIL_MOTIONS, INNER_GESTURE_FRAMES, INNER_MID_LIMIT,
    TAIL_MOTION_FRAMES,
)
from jiajia.performance import PERFORMANCE_PHRASES
from jiajia.prop_shapes import (
    ACTION_FACE_SCRIPTS,
    ACTION_PROP_CUES,
    DEFAULT_PROP_ACTIONS,
    SCENARIO_PROP_CUES,
)
from jiajia.rig_pose import posed_tail_points

# Brow poses that read as alarm rather than as a mood.
PANIC_BROWS = frozenset({"panic", "worried"})
# Face decals that shout instead of act.
LOUD_DECALS = frozenset({"shock_lines", "star_ring", "tears", "sweat", "pale"})


def _flat_tail() -> tuple[float, ...]:
    pts = [TAIL_START[0], TAIL_START[1]]
    for curve in TAIL_CURVES:
        for point in curve:
            pts.extend(point)
    return tuple(pts)


def _pose_at(frames, t_ms: float):
    """Linear interpolation across (sway, curl, droop, tuck, stiffen, dur)."""
    acc = 0.0
    prev = frames[0][:5]
    for frame in frames:
        dur = frame[5]
        if t_ms <= acc + dur or frame is frames[-1]:
            k = min(1.0, max(0.0, (t_ms - acc) / max(1.0, dur)))
            return tuple(prev[i] + (frame[i] - prev[i]) * k for i in range(5))
        acc += dur
        prev = frame[:5]
    return frames[-1][:5]


def tail_kinematics(name: str) -> dict[str, float]:
    """Tip travel, peak speed and longest hold for a keyframed tail gesture."""
    frames = TAIL_MOTION_FRAMES[name]
    total = sum(f[5] for f in frames)
    base = _flat_tail()
    step = 1000 / 60.0
    samples = []
    t = 0.0
    while t <= total:
        sway, curl, droop, tuck, stiffen = _pose_at(frames, t)
        tip = posed_tail_points(base, sway, curl, droop, tuck, stiffen)[-1]
        samples.append((t, tip[0], tip[1]))
        t += step

    peak = 0.0
    hold = run = 0.0
    for i in range(1, len(samples)):
        dt_s = (samples[i][0] - samples[i - 1][0]) / 1000.0
        dist = math.hypot(samples[i][1] - samples[i - 1][1], samples[i][2] - samples[i - 1][2])
        peak = max(peak, dist / dt_s)
        if dist < 0.35:
            run += samples[i][0] - samples[i - 1][0]
        else:
            hold = max(hold, run)
            run = 0.0
    return {"total_ms": float(total), "peak_px_s": peak, "hold_ms": max(hold, run)}


class NeutralActionTests(unittest.TestCase):
    """Some actions have to mean nothing, or nothing else can mean anything."""

    NEUTRAL = ("blink", "nod", "peek", "sleepy_sag", "tail_idle_slow")

    def test_neutral_actions_carry_no_default_prop(self) -> None:
        for action in self.NEUTRAL:
            self.assertNotIn(
                action, ACTION_PROP_CUES,
                f"{action} is the baseline other actions are read against; a prop makes it a scene",
            )

    def test_blink_stays_a_blink(self) -> None:
        script = ACTION_FACE_SCRIPTS["blink"]
        brows = {frame[2] for frame in script if frame[2]}
        self.assertEqual(brows, {"neutral"}, f"blink drifted into an expression: {brows}")
        for frame in script:
            look = frame[3]
            self.assertIn(look, (None, (0.0, 0.0)), f"a blink does not glance around: {look}")
        self.assertLessEqual(script[-1][0], 400, "a blink is a beat, not a performance")


class SleepAndComfortTests(unittest.TestCase):
    """Rest scenarios must not contain a jump scare."""

    RESTFUL = ("sleepy_sag", "tail_sleepy_droop")

    def test_restful_actions_have_no_panic(self) -> None:
        for action in self.RESTFUL:
            brows = {frame[2] for frame in ACTION_FACE_SCRIPTS[action] if frame[2]}
            self.assertFalse(
                brows & PANIC_BROWS,
                f"{action} is a rest action but panics: {sorted(brows & PANIC_BROWS)}",
            )

    def test_quiet_companion_is_actually_quiet(self) -> None:
        """comfort runs this on a loop, so anything startling repeats forever."""
        phrase = PERFORMANCE_PHRASES["quiet_companion"]
        for action, _ms in (*phrase.pre_actions, *phrase.post_actions):
            self.assertNotIn(
                action, ACTION_PROP_CUES,
                f"quiet_companion plays {action}, which brings a prop into a looping rest scene",
            )
            for frame in ACTION_FACE_SCRIPTS.get(action, ()):
                self.assertNotIn(
                    frame[2], PANIC_BROWS,
                    f"quiet_companion plays {action}, which panics on a loop",
                )

    def test_the_alarm_still_exists_somewhere(self) -> None:
        """Splitting the skit out must not quietly delete it."""
        self.assertIn("alarm_jolt", ACTION_LABELS)
        brows = {frame[2] for frame in ACTION_FACE_SCRIPTS["alarm_jolt"] if frame[2]}
        self.assertTrue(brows & PANIC_BROWS, "alarm_jolt lost the jolt")
        self.assertIn("alarm_jolt", ACTION_PROP_CUES, "the alarm clock is the point of alarm_jolt")


class TailIdentityTests(unittest.TestCase):
    """The tail group exists to show the tail."""

    def _tail_actions(self) -> tuple[str, ...]:
        for group, names in ACTION_MENU_GROUPS:
            if group == "Tail":
                return names
        raise AssertionError("no Tail group")

    def test_tail_actions_show_a_tail_not_a_prop(self) -> None:
        for action in self._tail_actions():
            self.assertNotIn(
                action, ACTION_PROP_CUES,
                f"{action}'s preview would show its prop rather than the tail",
            )

    def test_no_tail_action_turns_the_tail_into_a_hand_by_default(self) -> None:
        for action, cue in ACTION_PROP_CUES.items():
            self.assertFalse(
                cue.get("held") and cue.get("tail_style") == "wag",
                f"{action} makes the tail a hand by default, which unteaches the tail",
            )

    def test_alert_snap_is_a_pose_not_a_pop(self) -> None:
        k = tail_kinematics("tail_alert_snap")
        self.assertGreaterEqual(k["total_ms"], 900, "too short to read as a reaction")
        self.assertLessEqual(k["total_ms"], 1400, "an alert should not outstay its meaning")
        self.assertLess(k["peak_px_s"], 400, "the tip teleports rather than moves")
        self.assertGreaterEqual(k["hold_ms"], 200, "the hold is where 'alert' is actually read")

    def test_no_tail_gesture_outruns_the_frame_rate(self) -> None:
        """A 30fps GIF cannot show a move that finishes in two frames."""
        for name in TAIL_MOTION_FRAMES:
            k = tail_kinematics(name)
            self.assertLess(
                k["peak_px_s"], 400,
                f"{name} peaks at {k['peak_px_s']:.0f}px/s, which pops at 30fps",
            )

    def test_short_body_actions_do_not_borrow_a_long_alert_tail(self) -> None:
        alert_ms = tail_kinematics("tail_alert_snap")["total_ms"]
        borrowers = {a for a, m in ACTION_TAIL_MOTIONS.items() if m == "tail_alert_snap"}
        self.assertFalse(
            borrowers,
            f"{sorted(borrowers)} borrow a {alert_ms:.0f}ms alert pose they cannot pay for",
        )


AGENT_STATES = (
    "thinking_loop", "tool_working", "paper_editing", "paper_sorting",
    "waiting_stare", "permission_request", "reconnect_scan", "error_autopsy",
)


def motion_fingerprint(action: str) -> tuple[int, int, int, int]:
    """Coarse (travel_x, travel_y, shape_change, longest_hold) for an action."""
    frames = ACTION_FRAMES[action]
    return (
        round(max(abs(f[0]) for f in frames)),
        round(max(abs(f[1]) for f in frames)),
        round(max(abs(f[2] - 1) + abs(f[3] - 1) for f in frames) * 100),
        max(f[4] for f in frames),
    )


class AgentStateTests(unittest.TestCase):
    """A configured state the viewer cannot tell apart is not a state."""

    def test_agent_states_have_their_own_motion(self) -> None:
        for state in AGENT_STATES:
            self.assertIn(state, ACTION_FRAMES, f"{state} has no motion of its own")
            self.assertNotIn(
                state, ANIMATION_ALIASES,
                f"{state} still aliases to {ANIMATION_ALIASES.get(state)!r} instead of moving itself",
            )

    def test_no_two_agent_states_look_the_same(self) -> None:
        seen: dict[tuple[int, int, int, int], str] = {}
        for state in AGENT_STATES:
            print_ = motion_fingerprint(state)
            clash = seen.get(print_)
            self.assertIsNone(
                clash, f"{state} and {clash} share a motion fingerprint {print_}",
            )
            seen[print_] = state

    def test_agent_states_differ_from_the_actions_they_replaced(self) -> None:
        """They used to BE these; identical motion would mean nothing changed."""
        for state in AGENT_STATES:
            for old in ("patrol", "thinking_tilt"):
                self.assertNotEqual(
                    motion_fingerprint(state), motion_fingerprint(old),
                    f"{state} is indistinguishable from {old}",
                )


class InnerWireTests(unittest.TestCase):
    """The inner wire is a hand that covers the mouth, and stays there.

    It may hold something, but it never carries it away: the wire keeps its
    place and only the tip articulates. The rig exposes that directly — the
    amount_* channels move the free tip, the mid_* channels bow the whole wire
    outward. Letting mid_* grow turns the core into a second arm, which is how
    it had acquired a wave, a point and a thumbs-up.
    """

    def test_only_the_tip_moves(self) -> None:
        for name, frames in INNER_GESTURE_FRAMES.items():
            mid = max(abs(f[2]) + abs(f[3]) for f in frames)
            self.assertLessEqual(
                mid, INNER_MID_LIMIT,
                f"{name} bows the wire by {mid:.0f} (limit {INNER_MID_LIMIT:.0f}); "
                "it is swinging away from the mouth instead of articulating",
            )

    def test_the_tip_still_carries_the_gesture(self) -> None:
        """Clamping mid must not flatten the expression along with it."""
        for name, frames in INNER_GESTURE_FRAMES.items():
            tip = max(abs(f[0]) + abs(f[1]) for f in frames)
            self.assertGreater(tip, INNER_MID_LIMIT, f"{name} has no tip movement left")

    def test_every_gesture_returns_to_rest(self) -> None:
        """A hand that stops mid-gesture reads as a frozen limb."""
        for name, frames in INNER_GESTURE_FRAMES.items():
            self.assertEqual(
                tuple(frames[-1][:4]), (0, 0, 0, 0),
                f"{name} ends displaced instead of back at the mouth",
            )


class PropLayerTests(unittest.TestCase):
    """A prop should be the cause of a movement, not a caption for it."""

    def test_props_are_opt_in(self) -> None:
        self.assertLess(
            len(ACTION_PROP_CUES), len(SCENARIO_PROP_CUES) / 2,
            "props drifted back to being the default for most actions",
        )
        self.assertEqual(set(ACTION_PROP_CUES), set(DEFAULT_PROP_ACTIONS) & set(SCENARIO_PROP_CUES))

    def test_the_catalogue_keeps_everything(self) -> None:
        """Decoupling must not lose prop work; it only stops auto-attaching it."""
        for action in DEFAULT_PROP_ACTIONS:
            self.assertIn(action, SCENARIO_PROP_CUES)
        self.assertGreater(len(SCENARIO_PROP_CUES), 40)

    def test_no_single_prop_dominates_the_defaults(self) -> None:
        """The halo used to appear in seven actions, which taught the halo."""
        shapes = [cue.get("shape") for cue in ACTION_PROP_CUES.values()]
        for shape in set(shapes):
            self.assertLessEqual(
                shapes.count(shape), 2,
                f"{shape} is the default in {shapes.count(shape)} actions; it becomes the meaning",
            )


class FaceScriptTests(unittest.TestCase):
    def test_every_pose_reference_resolves(self) -> None:
        """An unknown pose name silently falls back instead of raising."""
        from jiajia.body import JiajiaApp

        eyes = set(JiajiaApp._EYE_MAP)
        brows = set(JiajiaApp._BROW_MAP)
        for action, frames in ACTION_FACE_SCRIPTS.items():
            for frame in frames:
                if frame[1]:
                    self.assertIn(frame[1], eyes, f"{action} uses unknown eye pose {frame[1]!r}")
                if frame[2]:
                    self.assertIn(frame[2], brows, f"{action} uses unknown brow pose {frame[2]!r}")

    def test_loud_decals_stay_rare(self) -> None:
        loud = {
            action
            for action, frames in ACTION_FACE_SCRIPTS.items()
            if any((frame[4] or {}).get("decal") in LOUD_DECALS for frame in frames)
        }
        self.assertLessEqual(
            len(loud), len(ACTION_FACE_SCRIPTS) // 4,
            f"symbolic decals stopped being emphasis and became vocabulary: {sorted(loud)}",
        )


if __name__ == "__main__":
    unittest.main()
