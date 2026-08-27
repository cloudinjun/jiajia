"""Small continuity layer for Jiajia.

This module does not add new visual complexity. It adds behavioral continuity:
where the pal appears to pay attention, what emotional residue remains after a
reaction, and why the last visible state happened.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time
from typing import Any


STATUS_EVENT_PREFIXES = (
    "codex_",
    "claude_",
    "hardware_",
    "usage_",
    "openai_billing",
    "chat_codex",
    "chat_claude",
    "chat_hardware",
    "chat_usage",
    "chat_openai",
    "demo_codex",
    "demo_hardware",
    "demo_usage",
)

CARE_EVENT_PREFIXES = (
    "care_",
    "daily_greeting",
    "achievement_",
)


@dataclass(frozen=True)
class AliveCue:
    event: str = ""
    mood: str = ""
    performance: str = ""
    delivery_mode: str = "speech"
    attention: str = "user"
    eyes: str = ""
    brows: str = ""
    hold_ms: int = 1800
    residue: str = ""
    residue_delay_ms: int = 0
    residue_hold_ms: int = 1600
    after_action: str = ""
    after_delay_ms: int = 0
    reason: str = ""

    def debug_text(self) -> str:
        return (
            f"event: {self.event or 'unknown'}\n"
            f"mood: {self.mood or 'unknown'}\n"
            f"performance: {self.performance or 'none'}\n"
            f"delivery: {self.delivery_mode}\n"
            f"attention: {self.attention}\n"
            f"expression: {self.eyes or 'unchanged'} / {self.brows or 'unchanged'}\n"
            f"residue: {self.residue or 'none'}\n"
            f"after_action: {self.after_action or 'none'}\n"
            f"reason: {self.reason}"
        )


@dataclass
class AliveSnapshot:
    last_event: str = ""
    last_delivery_mode: str = ""
    last_attention: str = ""
    emotional_residue: str = ""
    residue_until: float = 0.0
    last_reason: str = ""
    recent_events: deque[str] = field(default_factory=lambda: deque(maxlen=8))

    def as_context(self) -> dict[str, object]:
        now = time.time()
        return {
            "last_event": self.last_event,
            "last_delivery_mode": self.last_delivery_mode,
            "last_attention": self.last_attention,
            "emotional_residue": self.emotional_residue if now < self.residue_until else "",
            "last_reason": self.last_reason,
            "recent_events": list(self.recent_events),
        }


class AliveLayer:
    """Maps reactions into small continuity cues.

    The runtime still owns rendering. This layer only decides the acting intent.
    """

    def __init__(self) -> None:
        self.snapshot = AliveSnapshot()
        self._last_cue = AliveCue(reason="not started")

    def observe_wait(self, source: str) -> AliveCue:
        event = f"wait_{source}"
        cue = AliveCue(
            event=event,
            mood="thinking",
            delivery_mode="waiting",
            attention="inward",
            eyes="soft",
            brows="soft",
            hold_ms=1400,
            residue="thinking",
            residue_delay_ms=900,
            residue_hold_ms=1800,
            reason=f"background work started: {source}",
        )
        self._remember(cue)
        return cue

    def observe_silence(self, event: str, reason: str) -> AliveCue:
        cue = AliveCue(
            event=event,
            delivery_mode="silence",
            attention="inward",
            eyes="soft",
            brows="soft",
            hold_ms=1200,
            residue="soft",
            residue_delay_ms=800,
            residue_hold_ms=1600,
            reason=reason,
        )
        self._remember(cue)
        return cue

    def observe_reaction(self, reaction: Any, performance: str = "", state: str = "") -> AliveCue:
        event = str(getattr(reaction, "event", "") or "")
        mood = str(getattr(reaction, "mood", "") or "")
        bubble = str(getattr(reaction, "bubble", "") or "")
        action = str(getattr(reaction, "action", "") or "")
        line = str(getattr(reaction, "line", "") or "")
        should_say = bool(getattr(reaction, "should_say", False))
        reason = str(getattr(reaction, "decision_reason", "") or "")
        delivery = self._delivery_mode(event, mood, bubble, line, should_say)
        attention, eyes, brows, hold_ms = self._attention_expression(delivery, mood, action, performance)
        residue, residue_delay, residue_hold = self._residue(delivery, mood, performance)
        after_action, after_delay = self._after_action(delivery, mood, performance)
        cue = AliveCue(
            event=event,
            mood=mood,
            performance=performance,
            delivery_mode=delivery,
            attention=attention,
            eyes=eyes,
            brows=brows,
            hold_ms=hold_ms,
            residue=residue,
            residue_delay_ms=residue_delay,
            residue_hold_ms=residue_hold,
            after_action=after_action,
            after_delay_ms=after_delay,
            reason=reason or self._fallback_reason(event, delivery, mood, action, performance, state),
        )
        self._remember(cue)
        return cue

    def as_context(self) -> dict[str, object]:
        return self.snapshot.as_context()

    def debug_text(self) -> str:
        return self._last_cue.debug_text()

    def _remember(self, cue: AliveCue) -> None:
        now = time.time()
        self._last_cue = cue
        self.snapshot.last_event = cue.event
        self.snapshot.last_delivery_mode = cue.delivery_mode
        self.snapshot.last_attention = cue.attention
        self.snapshot.emotional_residue = cue.residue
        self.snapshot.residue_until = now + max(0, cue.residue_delay_ms + cue.residue_hold_ms) / 1000
        self.snapshot.last_reason = cue.reason
        if cue.event:
            self.snapshot.recent_events.append(cue.event)

    def _delivery_mode(self, event: str, mood: str, bubble: str, line: str, should_say: bool) -> str:
        event_l = event.lower()
        bubble_l = bubble.lower()
        if not should_say or not line.strip():
            return "silent_action"
        if event_l.startswith(CARE_EVENT_PREFIXES):
            return "care"
        if event_l.startswith(STATUS_EVENT_PREFIXES) or bubble_l.startswith(("codex_", "claude_", "hardware_", "usage_")):
            return "status_thought" if "thought" in bubble_l else "status"
        if "thought" in bubble_l:
            return "thought"
        if mood in {"smirk", "smug", "suspicious"}:
            return "roast"
        if mood in {"sleepy", "focused", "sulky"}:
            return "soft"
        return "speech"

    def _attention_expression(
        self,
        delivery: str,
        mood: str,
        action: str,
        performance: str,
    ) -> tuple[str, str, str, int]:
        if delivery in {"status", "status_thought"}:
            if mood in {"done", "happy", "proud"}:
                return "status", "round", "proud", 2200
            if mood in {"startled", "sulky"}:
                return "status", "wide", "guilty", 2400
            return "status", "side_eye", "judge", 2200
        if delivery == "care":
            if mood == "sleepy" or action == "sleepy_sag":
                return "user", "half_closed", "soft", 3200
            return "user", "soft", "soft", 2600
        if delivery == "roast" or performance in {"cold_arrow_then_innocent", "roast_and_scoot"}:
            return "side_eye", "side_eye", "judge", 1500
        if delivery == "thought":
            return "inward", "soft", "soft", 2400
        if delivery == "waiting":
            return "inward", "soft", "soft", 1600
        if mood in {"guilty", "innocent", "shy"}:
            return "user", "wide", "innocent", 2400
        if mood in {"sleepy", "sulky"}:
            return "down", "peek_up", "sulk", 3000
        if mood in {"happy", "done", "proud"}:
            return "user", "round", "proud", 2400
        return "user", "", "", 1800

    def _residue(self, delivery: str, mood: str, performance: str) -> tuple[str, int, int]:
        if delivery == "roast" or performance in {"cold_arrow_then_innocent", "roast_and_scoot"}:
            return "innocent", 1500, 1900
        if delivery in {"status", "status_thought"}:
            return "watching", 1200, 1800
        if delivery == "care":
            return "soft", 1500, 2200
        if delivery == "thought":
            return "thinking", 1200, 1800
        if mood in {"sleepy", "sulky"}:
            return "sleepy" if mood == "sleepy" else "sulk", 1300, 2400
        if mood in {"happy", "done", "proud"}:
            return "proud", 1400, 1800
        return "", 0, 0

    def _after_action(self, delivery: str, mood: str, performance: str) -> tuple[str, int]:
        if delivery == "roast" or performance in {"cold_arrow_then_innocent", "roast_and_scoot"}:
            return "micro_snap_innocent", 1450
        if delivery in {"status", "status_thought"} and mood in {"done", "happy", "proud"}:
            return "tail_wag", 900
        if delivery == "care" and mood == "sleepy":
            return "blink", 1500
        return "", 0

    def _fallback_reason(self, event: str, delivery: str, mood: str, action: str, performance: str, state: str) -> str:
        parts = [
            f"event={event or 'unknown'}",
            f"delivery={delivery}",
            f"mood={mood or 'unknown'}",
        ]
        if action:
            parts.append(f"action={action}")
        if performance:
            parts.append(f"performance={performance}")
        if state:
            parts.append(f"state={state}")
        return ", ".join(parts)
