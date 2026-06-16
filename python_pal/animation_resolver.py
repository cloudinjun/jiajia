from __future__ import annotations

from dataclasses import dataclass

from .actions import MODEL_ACTIONS


STATE_ANIMATION_ALIASES: dict[str, str] = {
    "standby": "idle",
    "quiet": "idle",
    "neutral": "idle",
    "think": "thinking_loop",
    "thinking": "thinking_loop",
    "waiting": "thinking_loop",
    "processing": "thinking_loop",
    "loading": "thinking_loop",
    "working": "thinking_loop",
    "running": "thinking_loop",
    "listen": "typing_focus",
    "listening": "typing_focus",
    "typing": "typing_focus",
    "input": "typing_focus",
    "user_typing": "typing_focus",
    "compose": "typing_focus",
    "composing": "typing_focus",
    "error": "error_shake",
    "blocked": "error_shake",
    "failed": "error_shake",
    "failure": "error_shake",
    "crash": "error_shake",
    "critical": "error_shake",
    "success": "tiny_celebrate",
    "done": "tiny_celebrate",
    "finished": "tiny_celebrate",
    "complete": "tiny_celebrate",
    "completed": "tiny_celebrate",
    "sleep": "sleep_loop",
    "sleeping": "sleep_loop",
    "asleep": "sleep_loop",
    "sleepy": "sleep_loop",
}

ANIMATION_ALIASES: dict[str, str] = {
    **STATE_ANIMATION_ALIASES,
    "idle_breathe": "idle",
    "blink_innocent": "blink",
    "side_eye": "peek",
    "holding_laugh": "smug_sway",
    "audit_scan": "scan",
    "clipboard_judgement": "thinking_tilt",
    "soft_nudge": "nod",
    "audit_done": "nod",
    "judgement_pause": "thinking_tilt",
    "agent_listening": "typing_focus",
    "agent_listen": "typing_focus",
    "agent_running": "thinking_loop",
    "agent_stuck": "thinking_loop",
    "agent_error": "error_shake",
    "agent_done_smug": "tiny_celebrate",
    "error_pop": "error_shake",
    "warm_idle": "micro_soften",
    "fan_shake": "shake",
    "meltdown": "flop",
    "cooldown_recover": "micro_soft_reset",
    "usage_bar_peek": "scan",
    "low_budget_sag": "sulk",
    "refill_bounce": "happy_bounce",
    "quiet_breathe": "blink",
    "slow_blink": "blink",
    "look_away_respectfully": "peek",
    "tiny_support_bob": "bob",
    "sleep_loop": "sleepy_sag",
    "yawn_to_sleep": "sleepy_sag",
    "wake_startled": "startled_pop",
    "pretend_not_sleeping": "blink",
    "sleepy_sass": "smug_sway",
    "slow_peek": "peek",
    "inspect_corpse": "scan",
    "error_autopsy": "thinking_loop",
    "tiny_stamp": "nod",
    "roast_charge": "thinking_tilt",
    "cold_arrow_heavy": "cold_arrow_then_innocent",
    "red_pen_circle": "thinking_tilt",
    "apology_fake": "blink",
    "layout_side_eye": "peek",
    "window_patrol": "patrol",
    "block_tab": "shake",
    "nope_shake": "shake",
    "boop_escape": "roast_and_scoot",
    "low_power_idle": "sleepy_sag",
    "crawl_back": "sleepy_sag",
    "fake_innocent": "blink",
}


@dataclass(frozen=True)
class ResolvedAnimation:
    requested: str
    kind: str = "action"
    action: str = "blink"
    performance: str = ""
    fallback_reason: str = ""


class AnimationResolver:
    def __init__(self, performances: set[str] | None = None) -> None:
        self.performances = {_key(name) for name in (performances or set()) if _key(name)}
        self.actions = set(MODEL_ACTIONS) | {
            "micro_focus_pause",
            "micro_side_eye",
            "micro_brow_judge",
            "micro_snap_innocent",
            "micro_caught_guilty",
            "micro_holding_laugh",
            "micro_peek_up",
            "micro_soften",
            "micro_tiny_proud",
            "micro_soft_reset",
        }

    def resolve(self, name: str, fallback: str = "blink") -> ResolvedAnimation:
        requested = _key(name)
        fallback_key = _key(fallback) or "blink"
        if not requested or requested == "idle":
            return ResolvedAnimation(requested=requested or "idle", action="idle")
        if requested in self.actions:
            return ResolvedAnimation(requested=requested, action=requested)
        if requested in self.performances:
            return ResolvedAnimation(requested=requested, kind="performance", performance=requested)

        target = _key(ANIMATION_ALIASES.get(requested))
        if target:
            if target in self.performances:
                return ResolvedAnimation(
                    requested=requested,
                    kind="performance",
                    performance=target,
                    fallback_reason=f"alias:{target}",
                )
            if target in self.actions:
                return ResolvedAnimation(requested=requested, action=target, fallback_reason=f"alias:{target}")

        if fallback_key in self.performances:
            return ResolvedAnimation(requested=requested, kind="performance", performance=fallback_key, fallback_reason="missing_alias")
        if fallback_key in self.actions:
            return ResolvedAnimation(requested=requested, action=fallback_key, fallback_reason="missing_alias")
        return ResolvedAnimation(requested=requested, action="blink", fallback_reason="missing_alias")


def _key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
