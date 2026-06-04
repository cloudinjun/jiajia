from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PerformancePhrase:
    pre_actions: tuple[tuple[str, int], ...] = ()
    line_delay_ms: int = 0
    post_actions: tuple[tuple[str, int], ...] = ()


PERFORMANCE_PHRASES: dict[str, PerformancePhrase] = {
    "cold_arrow_then_innocent": PerformancePhrase(
        pre_actions=(
            ("micro_focus_pause", 180),
            ("thinking_tilt", 700),
            ("micro_side_eye", 280),
            ("micro_brow_judge", 180),
        ),
        line_delay_ms=160,
        post_actions=(
            ("micro_snap_innocent", 80),
            ("blink", 180),
            ("nod", 260),
        ),
    ),
    "smug_but_caught": PerformancePhrase(
        pre_actions=(
            ("smug_sway", 380),
            ("micro_holding_laugh", 300),
        ),
        line_delay_ms=80,
        post_actions=(
            ("micro_caught_guilty", 90),
            ("micro_snap_innocent", 240),
            ("blink", 180),
        ),
    ),
    "fake_sulk": PerformancePhrase(
        pre_actions=(
            ("sulk", 460),
            ("micro_peek_up", 260),
        ),
        line_delay_ms=120,
        post_actions=(
            ("sulk", 260),
            ("micro_soft_reset", 220),
            ("blink", 160),
        ),
    ),
    "suspicious_observe": PerformancePhrase(
        pre_actions=(
            ("micro_brow_judge", 160),
            ("scan", 650),
            ("micro_side_eye", 260),
            ("thinking_tilt", 480),
        ),
        line_delay_ms=120,
        post_actions=(
            ("micro_soft_reset", 180),
            ("blink", 180),
        ),
    ),
    "quiet_companion": PerformancePhrase(
        pre_actions=(
            ("micro_soften", 160),
            ("sleepy_sag", 380),
        ),
        line_delay_ms=80,
        post_actions=(
            ("blink", 220),
            ("nod", 260),
            ("micro_soft_reset", 240),
        ),
    ),
    "tiny_celebrate": PerformancePhrase(
        pre_actions=(
            ("micro_tiny_proud", 100),
            ("happy_bounce", 320),
        ),
        line_delay_ms=80,
        post_actions=(
            ("micro_snap_innocent", 120),
            ("nod", 220),
        ),
    ),
}


def phrase_for_reaction(mood: str, action: str, bubble: str) -> str:
    bubble_shape = "thought" if bubble.endswith("thought") else "speech" if bubble.endswith("speech") else bubble
    if mood in {"happy", "proud", "done"} or action in {"happy_bounce", "celebrate"}:
        return "tiny_celebrate"
    if mood in {"sulky", "sulk"} or action in {"sulk", "hide"}:
        return "fake_sulk"
    if mood in {"sleepy", "focused"}:
        return "quiet_companion"
    if mood == "suspicious" or action in {"scan", "peek", "patrol"}:
        return "suspicious_observe"
    if mood in {"smirk", "smug"} and bubble_shape == "speech":
        return "cold_arrow_then_innocent"
    if mood in {"guilty", "innocent"}:
        return "smug_but_caught" if mood == "guilty" else "quiet_companion"
    if action in {"smug_sway", "thinking_tilt"} and bubble_shape == "thought":
        return "suspicious_observe"
    return ""


PERFORMANCE_PHRASES.update(
    {
        "cold_arrow": PERFORMANCE_PHRASES["cold_arrow_then_innocent"],
        "snap_innocent": PERFORMANCE_PHRASES["quiet_companion"],
        "fake_innocent": PERFORMANCE_PHRASES["quiet_companion"],
        "guilty_after_roast": PERFORMANCE_PHRASES["smug_but_caught"],
        "tiny_comfort": PERFORMANCE_PHRASES["quiet_companion"],
    }
)

PRIMARY_PERFORMANCE_IDS: tuple[str, ...] = (
    "cold_arrow_then_innocent",
    "smug_but_caught",
    "fake_sulk",
    "suspicious_observe",
    "quiet_companion",
    "tiny_celebrate",
)
PERFORMANCE_SCHEMA_VALUE = "|".join((*PRIMARY_PERFORMANCE_IDS, ""))
PERFORMANCE_PROMPT = "\n".join(
    (
        "- cold_arrow_then_innocent: 观察停顿、斜眼审判、说冷箭，然后立刻睁大眼装乖。",
        "- smug_but_caught: 得意到一半被发现，僵一下，再假装自己只是小文具。",
        "- fake_sulk: 假委屈塌下去，偷偷看一眼，再继续小幅委屈。",
        "- suspicious_observe: 眉毛压低、扫视、歪头，用于发现拖延或可疑切窗口。",
        "- quiet_companion: 收起攻击性，慢 blink 和轻点头，适合陪伴或深度专注。",
        "- tiny_celebrate: 小小庆祝，开心但不吵，最后回到乖巧姿态。",
    )
)
