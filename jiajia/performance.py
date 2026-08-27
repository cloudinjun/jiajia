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
            # judge/side_eye 表情自 pre_actions 延续 700ms —— 死寂冻结
            ("micro_snap_innocent", 700),
            ("slow_blink", 620),
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
            ("micro_guilty_dart", 560),
            ("micro_snap_innocent", 1240),
            ("slow_blink", 560),
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
            # 说完保持审视 640ms 再收
            ("slow_blink", 640),
            ("micro_soft_reset", 900),
        ),
    ),
    "thought_roast_smug": PerformancePhrase(
        pre_actions=(
            ("smug_sway", 360),
            ("inner_side_smirk", 140),
            ("tail_smug_sway", 180),
            ("micro_brow_judge", 120),
        ),
        line_delay_ms=90,
        post_actions=(
            ("inner_side_smirk", 120),
            ("tail_tip_flick", 170),
            ("micro_holding_laugh", 180),
            ("slow_blink", 640),
        ),
    ),
    "grand_dame_whisper_roast": PerformancePhrase(
        pre_actions=(
            ("micro_focus_pause", 140),
            ("thinking_tilt", 520),
            ("paper_whisper_fan", 260),
            ("micro_side_eye", 180),
            ("inner_cover_oops", 120),
        ),
        line_delay_ms=120,
        post_actions=(
            ("tail_smug_sway", 120),
            ("oops_innocent_combo", 740),
            ("slow_blink", 1000),
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
    "cheesy_love_cringe": PerformancePhrase(
        pre_actions=(
            ("inner_cover_oops", 180),
            ("tail_tip_flick", 160),
        ),
        line_delay_ms=90,
        post_actions=(
            ("shake", 160),
            ("tail_frantic_innocent", 180),
            ("oops_innocent_combo", 260),
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
