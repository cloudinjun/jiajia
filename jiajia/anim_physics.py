"""Animation physics utilities: spring-damper, easing curves, expression tweening.

Provides SpringDamper for natural squash/stretch rebound, a library of easing
functions for per-action curves, and ExpressionTweener for smooth eye/brow
transitions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


# ── Spring-damper ────────────────────────────────────────────────

@dataclass
class SpringDamper:
    """Critically-damped spring for natural rebound physics.

    Usage: call `kick(velocity)` to disturb, then `tick(dt)` each frame.
    `value` oscillates around `target` with natural decay.
    """
    target: float = 1.0
    value: float = 1.0
    velocity: float = 0.0
    stiffness: float = 180.0   # spring constant (higher = snappier)
    damping: float = 12.0      # damping coefficient (higher = less oscillation)

    def kick(self, impulse: float) -> None:
        """Add an impulse velocity."""
        self.velocity += impulse

    def set_target(self, target: float) -> None:
        self.target = target

    def tick(self, dt: float) -> float:
        """Advance by dt seconds, return new value."""
        displacement = self.value - self.target
        # F = -kx - cv  (spring + damping)
        accel = -self.stiffness * displacement - self.damping * self.velocity
        self.velocity += accel * dt
        self.value += self.velocity * dt
        return self.value

    @property
    def at_rest(self) -> bool:
        return abs(self.value - self.target) < 0.002 and abs(self.velocity) < 0.01

    def snap(self) -> None:
        """Instantly settle at target."""
        self.value = self.target
        self.velocity = 0.0


@dataclass
class SquashStretchSpring:
    """Paired springs for X/Y scale that maintain approximate volume.

    When sx compresses, sy expands proportionally and vice versa.
    """
    sx: SpringDamper = field(default_factory=lambda: SpringDamper(target=1.0, stiffness=200.0, damping=14.0))
    sy: SpringDamper = field(default_factory=lambda: SpringDamper(target=1.0, stiffness=200.0, damping=14.0))

    def kick_squash(self, amount: float) -> None:
        """Positive = squash down (sx widens, sy shrinks)."""
        self.sx.kick(amount * 0.6)
        self.sy.kick(-amount)

    def kick_stretch(self, amount: float) -> None:
        """Positive = stretch tall (sx narrows, sy grows)."""
        self.sx.kick(-amount * 0.6)
        self.sy.kick(amount)

    def kick_bounce(self, amount: float) -> None:
        """Symmetric bounce (landing impact)."""
        self.sx.kick(amount)
        self.sy.kick(-amount * 1.2)

    def tick(self, dt: float) -> tuple[float, float]:
        return self.sx.tick(dt), self.sy.tick(dt)

    @property
    def at_rest(self) -> bool:
        return self.sx.at_rest and self.sy.at_rest

    def snap(self) -> None:
        self.sx.snap()
        self.sy.snap()

    @property
    def scale(self) -> tuple[float, float]:
        return self.sx.value, self.sy.value


# ── Easing curves ────────────────────────────────────────────────

def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_in_cubic(t: float) -> float:
    return t ** 3


def ease_in_out_cubic(t: float) -> float:
    if t < 0.5:
        return 4.0 * t * t * t
    return 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0


def ease_out_elastic(t: float) -> float:
    """Elastic overshoot — great for startled/pop animations."""
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    p = 0.35
    return 2.0 ** (-10.0 * t) * math.sin((t - p / 4.0) * (2.0 * math.pi) / p) + 1.0


def ease_out_bounce(t: float) -> float:
    """Bounce — good for celebrate/landing."""
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    elif t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    elif t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    else:
        t -= 2.625 / 2.75
        return 7.5625 * t * t + 0.984375


def ease_in_slow(t: float) -> float:
    """Very slow start — for sleepy/sag motions."""
    return t ** 4


def linear(t: float) -> float:
    return t


# Registry: action name → easing function
EasingFn = type(linear)  # callable alias

ACTION_EASING: dict[str, EasingFn] = {
    "jump": ease_out_bounce,
    "startled_pop": ease_out_elastic,
    "celebrate": ease_out_bounce,
    "happy_bounce": ease_out_bounce,
    "sleepy_sag": ease_in_slow,
    "sulk": ease_in_slow,
    "patrol": linear,
    "smug_sway": ease_in_out_cubic,
    "thinking_tilt": ease_in_out_cubic,
    "shake": linear,
    "dance": ease_in_out_cubic,
    "drop_in": ease_out_bounce,
    "flop": ease_in_cubic,
    "hide": ease_in_cubic,
    "stretch": ease_in_out_cubic,
    "twirl": ease_in_out_cubic,
    "nod": ease_out_cubic,
    "wiggle": ease_out_cubic,
    "tail_wag": ease_out_cubic,
    "spin_jump": ease_out_cubic,
    "excited_spin": ease_in_out_cubic,
    "sneeze": ease_out_cubic,
    "shiver": linear,
    "curious_lean": ease_in_out_cubic,
    "peekaboo": ease_out_cubic,
    "zoomies": ease_out_cubic,
    "moonwalk": ease_in_out_cubic,
    "pounce": ease_out_cubic,
}


def easing_for_action(action: str) -> EasingFn:
    """Look up easing curve for an action, default to ease_out_cubic."""
    return ACTION_EASING.get(action, ease_out_cubic)


# ── Expression tweener ───────────────────────────────────────────

@dataclass
class _TweenChannel:
    """Single float channel that interpolates over N frames."""
    start: float = 0.0
    end: float = 0.0
    frame: int = 0
    total_frames: int = 0

    @property
    def done(self) -> bool:
        return self.frame >= self.total_frames

    def tick(self) -> float:
        if self.total_frames <= 0 or self.frame >= self.total_frames:
            return self.end
        self.frame += 1
        t = self.frame / self.total_frames
        # smooth-step interpolation
        t = t * t * (3.0 - 2.0 * t)
        return self.start + (self.end - self.start) * t

    @property
    def current(self) -> float:
        if self.total_frames <= 0:
            return self.end
        t = self.frame / self.total_frames
        t = t * t * (3.0 - 2.0 * t)
        return self.start + (self.end - self.start) * t


@dataclass
class ExpressionTweener:
    """Smooth interpolation for brow (dx, dy, rotation) and pupil (dx, dy, scale).

    Call `transition_to(...)` to start a tween, then `tick()` each frame
    to get interpolated values.
    """
    # brow: left (dx, dy, rot), right (dx, dy, rot)
    _brow_left: tuple[_TweenChannel, _TweenChannel, _TweenChannel] = field(
        default_factory=lambda: (_TweenChannel(), _TweenChannel(), _TweenChannel())
    )
    _brow_right: tuple[_TweenChannel, _TweenChannel, _TweenChannel] = field(
        default_factory=lambda: (_TweenChannel(), _TweenChannel(), _TweenChannel())
    )
    # pupil: dx, dy, scale
    _pupil: tuple[_TweenChannel, _TweenChannel, _TweenChannel] = field(
        default_factory=lambda: (_TweenChannel(), _TweenChannel(), _TweenChannel(start=1.0, end=1.0))
    )
    tween_frames: int = 3  # number of interpolation frames (at ~50ms/frame = 150ms)

    def transition_brows(
        self,
        current_left: tuple[float, float, float],
        target_left: tuple[float, float, float],
        current_right: tuple[float, float, float],
        target_right: tuple[float, float, float],
    ) -> None:
        n = self.tween_frames
        for ch, s, e in zip(self._brow_left, current_left, target_left, strict=False):
            ch.start, ch.end, ch.frame, ch.total_frames = s, e, 0, n
        for ch, s, e in zip(self._brow_right, current_right, target_right, strict=False):
            ch.start, ch.end, ch.frame, ch.total_frames = s, e, 0, n

    def transition_pupils(
        self,
        current: tuple[float, float, float],
        target: tuple[float, float, float],
    ) -> None:
        n = self.tween_frames
        for ch, s, e in zip(self._pupil, current, target, strict=False):
            ch.start, ch.end, ch.frame, ch.total_frames = s, e, 0, n

    def tick_brows(self) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
        """Returns (left_spec, right_spec) if still tweening, else None."""
        if all(ch.done for ch in (*self._brow_left, *self._brow_right)):
            return None
        left = tuple(ch.tick() for ch in self._brow_left)
        right = tuple(ch.tick() for ch in self._brow_right)
        return left, right  # type: ignore[return-value]

    def tick_pupils(self) -> tuple[float, float, float] | None:
        """Returns (dx, dy, scale) if still tweening, else None."""
        if all(ch.done for ch in self._pupil):
            return None
        return tuple(ch.tick() for ch in self._pupil)  # type: ignore[return-value]

    @property
    def is_tweening(self) -> bool:
        return not all(
            ch.done for ch in (*self._brow_left, *self._brow_right, *self._pupil)
        )
