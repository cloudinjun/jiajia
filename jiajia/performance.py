from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .action_timing import action_duration_ms
from .animation_manifest import load_animation_manifest


@dataclass(frozen=True)
class PerformancePhrase:
    pre_actions: tuple[tuple[str, int], ...] = ()
    line_delay_ms: int = 0
    post_actions: tuple[tuple[str, int], ...] = ()


# Each entry is (action, ms_before_the_next_step). The ms is a directorial
# choice, but it is bounded by physics: a body, tail or inner-wire action needs
# a real share of its duration before the next step cuts in, or the viewer sees
# a twitch instead of a beat. Face-only micro actions (micro_*, slow_blink) are
# exempt — an expression reads immediately and then holds.
# tests/test_performance_timing.py enforces the floor.
MIN_READABLE_FRACTION = 0.45

# ── the phrase table is DERIVED, not authored ────────────────────────────
# animations.yaml is the choreography. It used to be duplicated here as a second
# hand-timed table, and because _run_performance_phrase asks the manifest first
# and returns as soon as it scheduled anything, this copy was the one nobody
# saw — re-timing it fixed nothing on screen. Deriving it means the fallback
# path plays the same beats as the real one, and there is only one place to edit.

def _phrase_from_definition(definition: object) -> PerformancePhrase:
    """Flatten a manifest sequence into the fallback runner's shape.

    The manifest carries eye/brow/pause steps the fallback runner has no channel
    for; only the action beats and the line position survive the trip.
    """
    pre: list[tuple[str, int]] = []
    post: list[tuple[str, int]] = []
    line_delay = 0
    spoken = False
    for step in getattr(definition, "sequence", ()):
        if getattr(step, "bubble", "") == "speak":
            spoken = True
            line_delay = int(getattr(step, "duration_ms", 0) or 0)
            continue
        action = getattr(step, "action", "")
        if not action:
            continue
        declared = int(getattr(step, "duration_ms", 0) or 0)
        if declared:
            beat = declared
        elif getattr(step, "wait_action_duration", False):
            overlap = int(getattr(step, "overlap_ms", 0) or 0)
            beat = max(0, action_duration_ms(action) - overlap)
        else:
            beat = 0
        (post if spoken else pre).append((action, beat))
    return PerformancePhrase(tuple(pre), line_delay, tuple(post))


def _load_phrases() -> dict[str, PerformancePhrase]:
    manifest_path = Path(__file__).resolve().parent / "animations.yaml"
    try:
        manifest = load_animation_manifest(manifest_path)
    except Exception:  # noqa: BLE001 - a missing manifest must not break import
        return {}
    return {
        name: _phrase_from_definition(definition)
        for name, definition in manifest.performances.items()
    }


PERFORMANCE_PHRASES: dict[str, PerformancePhrase] = _load_phrases()


def phrase_for_reaction(mood: str, action: str, bubble: str) -> str:
    bubble_shape = "thought" if bubble.endswith("thought") else "speech" if bubble.endswith("speech") else bubble
    if mood in {"happy", "proud", "done"} or action in {"happy_bounce", "celebrate"}:
        return "tiny_celebrate"
    if mood in {"sulky", "sulk"} or action in {"sulk", "hide"}:
        return "fake_sulk"
    if mood in {"sleepy", "focused"}:
        return "quiet_companion"
    if mood == "shy" and bubble_shape == "speech":
        return "cheesy_love_cringe"
    if mood == "suspicious" or action in {"scan", "peek", "patrol"}:
        return "suspicious_observe"
    if action in {"roast_and_scoot", "paper_whisper_fan"} and bubble_shape == "speech":
        return "grand_dame_whisper_roast"
    if mood in {"smirk", "smug"} and bubble_shape == "speech":
        return "cold_arrow_then_innocent"
    if mood in {"smirk", "smug"} and bubble_shape == "thought":
        return "thought_roast_smug"
    if mood in {"guilty", "innocent"}:
        return "smug_but_caught" if mood == "guilty" else "quiet_companion"
    if action == "smug_sway" and bubble_shape == "thought":
        return "thought_roast_smug"
    if action == "thinking_tilt" and bubble_shape == "thought":
        return "suspicious_observe"
    return ""


PERFORMANCE_PHRASES.update(
    {
        "cold_arrow": PERFORMANCE_PHRASES["cold_arrow_then_innocent"],
        "cold_arrow_heavy": PERFORMANCE_PHRASES["grand_dame_whisper_roast"],
        "snap_innocent": PERFORMANCE_PHRASES["quiet_companion"],
        "fake_innocent": PERFORMANCE_PHRASES["quiet_companion"],
        "guilty_after_roast": PERFORMANCE_PHRASES["smug_but_caught"],
        "tiny_comfort": PERFORMANCE_PHRASES["quiet_companion"],
        "cheesy_love": PERFORMANCE_PHRASES["cheesy_love_cringe"],
    }
)

PRIMARY_PERFORMANCE_IDS: tuple[str, ...] = (
    "cold_arrow_then_innocent",
    "smug_but_caught",
    "fake_sulk",
    "suspicious_observe",
    "thought_roast_smug",
    "grand_dame_whisper_roast",
    "quiet_companion",
    "tiny_celebrate",
    "cheesy_love_cringe",
)
PERFORMANCE_SCHEMA_VALUE = "|".join((*PRIMARY_PERFORMANCE_IDS, ""))
_PERFORMANCE_PROMPT_ZH = "\n".join(
    (
        "- cold_arrow_then_innocent: 观察停顿、斜眼审判、说冷箭，然后立刻睁大眼装乖。",
        "- smug_but_caught: 得意到一半被发现，僵一下，再假装自己只是小文具。",
        "- fake_sulk: 假委屈塌下去，偷偷看一眼，再继续小幅委屈。",
        "- suspicious_observe: 眉毛压低、扫视、歪头，用于发现拖延或可疑切窗口。",
        "- thought_roast_smug: 脑内毒舌，不捂嘴，眼神和内芯更嚣张，像以为用户听不见。",
        "- quiet_companion: 收起攻击性，慢 blink 和轻点头，适合陪伴或深度专注。",
        "- tiny_celebrate: 小小庆祝，开心但不吵，最后回到乖巧姿态。",
    )
)

# The prompt goes straight to the model, so it has to be in the pal's own
# language — a Chinese-only list pulled English replies back toward Chinese.
_PERFORMANCE_PROMPT_EN = "\n".join(
    (
        "- cold_arrow_then_innocent: observe, pause, side-eye judgement, land the cold line, "
        "then widen the eyes and play innocent immediately.",
        "- smug_but_caught: caught halfway through being smug, freeze, then pretend to be "
        "nothing more than small stationery.",
        "- fake_sulk: collapse into a fake sulk, sneak a look, then keep sulking a little.",
        "- suspicious_observe: brows down, scan, head tilt; for spotting procrastination or "
        "suspicious window-switching.",
        "- thought_roast_smug: inner-monologue roast with no cover-up; eyes and inner core "
        "get cockier, as if the user cannot hear it.",
        "- quiet_companion: put the sharpness away, slow blinks and small nods; for company "
        "or deep focus.",
        "- tiny_celebrate: a small celebration, happy but not loud, then back to a well-behaved pose.",
    )
)

_SHARED_PROMPT_TAIL = (
    "\n- grand_dame_whisper_roast: sharpest spoken roast only; unfold a draft-paper fan at "
    "the mouth/inner-core like a polite gossip whisper, then snap back to fake innocence."
    "\n- cheesy_love_cringe: intentionally corny love line; innocent cover-mouth delivery, "
    "then the pal cringes at itself with shake and frantic tail."
)
_PERFORMANCE_PROMPT_ZH += _SHARED_PROMPT_TAIL
_PERFORMANCE_PROMPT_EN += _SHARED_PROMPT_TAIL


def performance_prompt(language: str = "zh-CN") -> str:
    """The performance-phrase menu in the pal's current language."""
    return _PERFORMANCE_PROMPT_EN if str(language).startswith("en") else _PERFORMANCE_PROMPT_ZH


PERFORMANCE_PROMPT = _PERFORMANCE_PROMPT_ZH
