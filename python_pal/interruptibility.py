from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .ears import EarContext


SLEEP_START_HOUR = 23
SLEEP_END_HOUR = 7


@dataclass(frozen=True)
class Interruptibility:
    mode: str = "open"
    reason: str = "open"
    allow_speech: bool = True
    allow_animation: bool = True
    allow_badges: bool = True
    allow_critical_alerts: bool = True
    visual_only_critical: bool = False

    def as_context(self) -> dict[str, object]:
        return {
            "interruptibility_mode": self.mode,
            "interruptibility_reason": self.reason,
            "allow_speech": self.allow_speech,
            "allow_animation": self.allow_animation,
            "allow_badges": self.allow_badges,
            "allow_critical_alerts": self.allow_critical_alerts,
            "visual_only_critical": self.visual_only_critical,
        }


def assess_interruptibility(
    activity: EarContext,
    focus_mode: bool = False,
    quiet_remaining_seconds: float = 0.0,
    now: datetime | None = None,
) -> Interruptibility:
    if activity.app_category == "meeting_or_chat":
        return Interruptibility(
            mode="meeting",
            reason="active app is chat/meeting",
            allow_speech=False,
            allow_animation=False,
            allow_badges=False,
            visual_only_critical=True,
        )
    if activity.is_fullscreen or "fullscreen" in activity.behavior_tags:
        return Interruptibility(
            mode="fullscreen",
            reason="foreground window is fullscreen",
            allow_speech=False,
            allow_animation=False,
            allow_badges=False,
            visual_only_critical=True,
        )
    if focus_mode:
        return Interruptibility(
            mode="focus",
            reason="focus mode is enabled",
            allow_speech=False,
            allow_animation=True,
            allow_badges=True,
            visual_only_critical=True,
        )
    if quiet_remaining_seconds > 0:
        return Interruptibility(
            mode="quiet",
            reason=f"quiet mode has {round(quiet_remaining_seconds)}s remaining",
            allow_speech=False,
            allow_animation=True,
            allow_badges=True,
            visual_only_critical=True,
        )
    if _is_sleep_hours(now):
        return Interruptibility(
            mode="sleep_hours",
            reason="local time is inside sleep hours",
            allow_speech=False,
            allow_animation=True,
            allow_badges=True,
            visual_only_critical=True,
        )
    if _looks_like_focused_input(activity):
        return Interruptibility(
            mode="focused_input",
            reason="recent input in one focused work window",
            allow_speech=False,
            allow_animation=True,
            allow_badges=True,
            visual_only_critical=True,
        )
    return Interruptibility()


def _is_sleep_hours(now: datetime | None = None) -> bool:
    hour = (now or datetime.now()).hour
    return hour >= SLEEP_START_HOUR or hour < SLEEP_END_HOUR


def _looks_like_focused_input(activity: EarContext) -> bool:
    if activity.idle_seconds > 2.5 or activity.focus_seconds < 25:
        return False
    if activity.app_category not in {"codex", "editor", "terminal", "browser", "design"}:
        return False
    if activity.window_switches_per_minute >= 4:
        return False
    return True
