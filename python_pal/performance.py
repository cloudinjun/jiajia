from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformancePhrase:
    pre_actions: tuple[tuple[str, int], ...] = ()
    line_delay_ms: int = 0
    post_actions: tuple[tuple[str, int], ...] = ()


PERFORMANCE_PHRASES: dict[str, PerformancePhrase] = {
    "cold_arrow": PerformancePhrase(
        pre_actions=(("thinking_tilt", 260), ("scan", 220)),
        line_delay_ms=180,
        post_actions=(("smug_sway", 360), ("blink", 280)),
    ),
    "snap_innocent": PerformancePhrase(
        pre_actions=(("smug_sway", 260),),
        line_delay_ms=80,
        post_actions=(("blink", 220), ("nod", 220)),
    ),
    "fake_innocent": PerformancePhrase(
        pre_actions=(("blink", 180),),
        line_delay_ms=60,
        post_actions=(("nod", 220),),
    ),
    "guilty_after_roast": PerformancePhrase(
        pre_actions=(("smug_sway", 240),),
        line_delay_ms=80,
        post_actions=(("startled_pop", 300), ("blink", 220)),
    ),
    "tiny_comfort": PerformancePhrase(
        pre_actions=(("sleepy_sag", 220),),
        line_delay_ms=80,
        post_actions=(("nod", 260),),
    ),
}


def phrase_for_reaction(mood: str, action: str, bubble: str) -> str:
    if mood in {"suspicious", "smirk", "smug"} and bubble == "speech":
        return "cold_arrow"
    if mood in {"guilty", "innocent"}:
        return "fake_innocent"
    if mood == "sleepy":
        return "tiny_comfort"
    if action in {"smug_sway", "thinking_tilt"} and bubble == "thought":
        return "snap_innocent"
    return ""
