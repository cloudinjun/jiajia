"""The pal is bent steel, not gum.

Three measured properties separate a metal wire from a rubber one, and all
three had drifted:

  * it does not stretch — the inner wire was lengthening by up to 4.4% because
    it was posed by displacing points independently, which lengthens the path
    between them
  * it bends in one arc — the inner wire subtracted a full sine period along
    its length, bowing one way then the other, which is a whip and not an arm
  * it loses energy — the tail's envelope was a trapezoid holding FULL
    amplitude across the middle, so the seventh swing was as big as the first

Both wires are posed by integrating curvature now, so length preservation is
structural rather than corrected after the fact.
"""
from __future__ import annotations

import math
import unittest

from jiajia.pal_geometry import BODY_CURVES, TAIL_CURVES, TAIL_START
from jiajia.pal_motion import (
    INNER_GESTURE_FRAMES,
    METAL_DAMPING,
    TAIL_MOTION_FRAMES,
    TAIL_OSCILLATIONS,
    tail_oscillation_pose,
)
from jiajia.rig_pose import posed_chin_points, posed_tail_points

# A wire may deviate this much from its rest length. Anything above is visible
# as elongation on a 260px wire.
MAX_STRETCH_PERCENT = 0.05
# Turns smaller than this are float noise from the resampler, not real bends.
TURN_EPSILON = 0.004


def _flat(*curve_groups) -> tuple[float, ...]:
    points: list[float] = []
    for group in curve_groups:
        for curve in group:
            for point in curve:
                points.extend(point)
    return tuple(points)


CHIN_BASE = _flat(BODY_CURVES[:2])
TAIL_BASE = (*TAIL_START[:2], *_flat(TAIL_CURVES))


def arc_length(points) -> float:
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def curvature_sign_flips(points) -> int:
    """How many times the wire changes which way it bows. 0 is a C, 1+ is an S."""
    turns: list[int] = []
    for i in range(1, len(points) - 1):
        before = math.atan2(points[i][1] - points[i - 1][1], points[i][0] - points[i - 1][0])
        after = math.atan2(points[i + 1][1] - points[i][1], points[i + 1][0] - points[i][0])
        delta = (after - before + math.pi) % (2 * math.pi) - math.pi
        if abs(delta) > TURN_EPSILON:
            turns.append(1 if delta > 0 else -1)
    return sum(1 for i in range(1, len(turns)) if turns[i] != turns[i - 1])


class InnerWireTests(unittest.TestCase):
    """The inner wire is the pal's hand, made of the same steel as the body."""

    def setUp(self) -> None:
        self.rest = arc_length(posed_chin_points(CHIN_BASE, 0, 0, 0, 0))

    def test_it_never_stretches(self) -> None:
        for name, frames in INNER_GESTURE_FRAMES.items():
            for frame in frames:
                length = arc_length(posed_chin_points(CHIN_BASE, *frame[:4]))
                drift = abs(length - self.rest) / self.rest * 100
                self.assertLess(
                    drift, MAX_STRETCH_PERCENT,
                    f"{name} stretches the wire by {drift:.2f}%; steel does not stretch",
                )

    def test_a_sideways_swing_does_not_lengthen_it(self) -> None:
        """Pure lateral drive is where a displacement model stretches worst."""
        for amount_x in (-24, -12, 12, 24):
            length = arc_length(posed_chin_points(CHIN_BASE, amount_x, 0, 0, 0))
            drift = abs(length - self.rest) / self.rest * 100
            self.assertLess(drift, MAX_STRETCH_PERCENT, f"swing {amount_x} stretched {drift:.2f}%")

    def test_it_bends_in_one_arc_not_an_s(self) -> None:
        for name, frames in INNER_GESTURE_FRAMES.items():
            for frame in frames:
                flips = curvature_sign_flips(posed_chin_points(CHIN_BASE, *frame[:4]))
                self.assertEqual(
                    flips, 0,
                    f"{name} bows both ways ({flips} reversals) — that is a whip, not an arm",
                )

    def test_the_joint_end_stays_put(self) -> None:
        """The core is attached; only the free tip may travel."""
        anchor = posed_chin_points(CHIN_BASE, 0, 0, 0, 0)[-1]
        for name, frames in INNER_GESTURE_FRAMES.items():
            for frame in frames:
                moved = math.dist(posed_chin_points(CHIN_BASE, *frame[:4])[-1], anchor)
                self.assertLess(moved, 0.5, f"{name} detaches the core by {moved:.1f}px")

    def test_gestures_still_have_visible_travel(self) -> None:
        """Killing the stretch must not flatten the acting along with it."""
        tip_rest = posed_chin_points(CHIN_BASE, 0, 0, 0, 0)[0]
        for name, frames in INNER_GESTURE_FRAMES.items():
            travel = max(math.dist(posed_chin_points(CHIN_BASE, *f[:4])[0], tip_rest) for f in frames)
            self.assertGreater(travel, 4.0, f"{name} barely moves ({travel:.1f}px)")


class TailWireTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rest = arc_length(posed_tail_points(TAIL_BASE, 0, 0, 0, 0, 0))

    def test_it_never_stretches(self) -> None:
        for name, frames in TAIL_MOTION_FRAMES.items():
            for frame in frames:
                length = arc_length(posed_tail_points(TAIL_BASE, *frame[:5]))
                drift = abs(length - self.rest) / self.rest * 100
                self.assertLess(drift, MAX_STRETCH_PERCENT, f"{name} stretched {drift:.2f}%")


class DampingTests(unittest.TestCase):
    """Steel loses energy between swings; rubber gives it back."""

    def test_the_envelope_decays_across_the_motion(self) -> None:
        for name, params in TAIL_OSCILLATIONS.items():
            duration = float(params["cycles"]) / float(params["freq"])
            early = tail_oscillation_pose(params, duration * 0.25)
            late = tail_oscillation_pose(params, duration * 0.70)
            self.assertIsNotNone(early)
            self.assertIsNotNone(late)
            assert early is not None and late is not None
            self.assertLess(
                abs(late[0]), abs(early[0]),
                f"{name} swings as hard late as early — a constant-amplitude "
                "wobble is what reads as gum",
            )

    def test_a_late_swing_is_a_fraction_of_the_first(self) -> None:
        """Not merely smaller: visibly smaller, the way a flicked wire settles."""
        for name, params in TAIL_OSCILLATIONS.items():
            duration = float(params["cycles"]) / float(params["freq"])
            early = tail_oscillation_pose(params, duration * 0.25)
            late = tail_oscillation_pose(params, duration * 0.75)
            assert early is not None and late is not None
            if abs(early[0]) < 1e-6:
                continue
            ratio = abs(late[0]) / abs(early[0])
            self.assertLess(ratio, 0.75, f"{name} keeps {ratio:.0%} of its swing; too springy")

    def test_damping_is_on_by_default(self) -> None:
        """A new oscillator must inherit metal, not opt into it."""
        self.assertGreater(METAL_DAMPING, 0.0)
        params = {"freq": 2.0, "amp": 10.0, "cycles": 3.0, "attack": 0.1, "decay": 0.1}
        duration = 1.5
        early = tail_oscillation_pose(params, duration * 0.25)
        late = tail_oscillation_pose(params, duration * 0.70)
        assert early is not None and late is not None
        self.assertLess(abs(late[0]), abs(early[0]))


if __name__ == "__main__":
    unittest.main()
