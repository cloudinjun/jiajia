from __future__ import annotations

from dataclasses import dataclass, field
import random

from .world import WorldState


INTERESTING_AMBIENT_TAGS = {
    "rapid_switching",
    "idle_staring",
    "long_focus",
    "blank_document",
    "todo_visible",
    "browser_research",
    "file_sorting",
    "deep_work",
    "app_codex",
    "app_editor",
    "app_terminal",
    "app_file_manager",
    "codex_waiting_user",
    "claude_active",
}

HIGH_SIGNAL_TAGS = {
    "rapid_switching",
    "idle_staring",
    "blank_document",
    "todo_visible",
    "codex_waiting_user",
}

QUIET_TAGS = {
    "long_focus",
    "deep_work",
}

PRIVACY_TAGS = {
    "privacy_sensitive",
    "app_meeting_or_chat",
    "meeting_or_chat",
}


@dataclass(frozen=True)
class DecisionResult:
    should_react: bool
    event: str = ""
    reason: str = ""
    pattern: str = "none"
    reaction_style: str = "none"
    cooldown_seconds: int = 0
    matched_tags: list[str] = field(default_factory=list)
    blocked_rules: list[str] = field(default_factory=list)

    def debug_text(self) -> str:
        blocked = ", ".join(self.blocked_rules) if self.blocked_rules else "none"
        matched = ", ".join(self.matched_tags) if self.matched_tags else "none"
        return (
            f"event: {self.event or 'none'}\n"
            f"decision: {'react' if self.should_react else 'skip'}\n"
            f"pattern: {self.pattern}\n"
            f"style: {self.reaction_style}\n"
            f"reason: {self.reason}\n"
            f"matched_tags: {matched}\n"
            f"cooldown_seconds: {self.cooldown_seconds}\n"
            f"blocked_rules: {blocked}"
        )


class DecisionEngine:
    def __init__(self) -> None:
        self.last_decision = DecisionResult(False, reason="not sampled yet")
        self._last_ambient_signature = ""

    def ambient_decision(
        self,
        world: WorldState,
        cooldown_seconds: int,
        chance_multiplier: float,
        bubble_visible: bool,
    ) -> DecisionResult:
        tags = set(world.environment_tags)
        matched = sorted(tags & INTERESTING_AMBIENT_TAGS)
        blocked: list[str] = []

        if bubble_visible:
            blocked.append("bubble_visible")
        if world.pal.brain_busy:
            blocked.append("brain_busy")
        if not world.pal.can_speak(cooldown_seconds):
            blocked.append("cooldown")
        if not tags:
            blocked.append("no_environment_tags")
        if tags & PRIVACY_TAGS:
            blocked.append("privacy_or_meeting")
        if world.user_activity.activity_level == "away":
            blocked.append("user_away")
        if not matched:
            blocked.append("no_interesting_pattern")

        pattern, style = self._classify_world(world, tags)
        signature = self._ambient_signature(world, matched)
        if signature and signature == self._last_ambient_signature:
            blocked.append("same_ambient_signature")

        if blocked:
            self.last_decision = DecisionResult(
                False,
                event="ambient",
                reason=self._reason_for_world(world, tags),
                pattern=pattern,
                reaction_style=style,
                cooldown_seconds=cooldown_seconds,
                matched_tags=matched,
                blocked_rules=blocked,
            )
            return self.last_decision

        chance = 0.55 if tags & HIGH_SIGNAL_TAGS else 0.28
        if tags & QUIET_TAGS and not (tags & HIGH_SIGNAL_TAGS):
            chance *= 0.38
        chance = min(0.88, chance * chance_multiplier)
        if random.random() > chance:
            self.last_decision = DecisionResult(
                False,
                event="ambient",
                reason=f"chance gate skipped at {chance:.2f}",
                pattern=pattern,
                reaction_style=style,
                cooldown_seconds=cooldown_seconds,
                matched_tags=matched,
                blocked_rules=["chance_gate"],
            )
            return self.last_decision

        self._last_ambient_signature = signature
        self.last_decision = DecisionResult(
            True,
            event="ambient",
            reason=self._reason_for_world(world, tags),
            pattern=pattern,
            reaction_style=style,
            cooldown_seconds=cooldown_seconds,
            matched_tags=matched,
        )
        return self.last_decision

    def _classify_world(self, world: WorldState, tags: set[str]) -> tuple[str, str]:
        if "codex_waiting_user" in tags:
            return "coding_agent_waiting", "notify_with_snark"
        if tags & {"rapid_switching", "browser_research"}:
            return "task_avoidance", "suspicious_soft_roast"
        if tags & {"blank_document", "todo_visible", "idle_staring"}:
            return "stuck_idle", "gentle_nudge"
        if tags & QUIET_TAGS:
            return "deep_focus", "silence_or_tiny_support"
        if world.claude.active_count:
            return "coding_agent_active", "quiet_observation"
        return "ambient_context", "light_observation"

    def _reason_for_world(self, world: WorldState, tags: set[str]) -> str:
        bits = [
            f"idle={round(world.user_activity.idle_seconds, 1)}s",
            f"focus={round(world.user_activity.focus_seconds, 1)}s",
            f"switches={world.user_activity.window_switches_per_minute}/min",
            f"app={world.user_activity.app_category}",
        ]
        if world.codex.status not in {"unknown", "idle"}:
            bits.append(f"codex={world.codex.status}")
        if world.claude.total_alive:
            bits.append(f"claude_active={world.claude.active_count}/{world.claude.total_alive}")
        if tags:
            bits.append("tags=" + ",".join(sorted(tags)[:6]))
        return "; ".join(bits)

    def _ambient_signature(self, world: WorldState, matched: list[str]) -> str:
        if not matched:
            return ""
        return (
            f"{world.user_activity.app_category}|"
            f"{world.user_activity.active_process}|"
            f"{world.codex.status}|"
            f"{world.claude.active_count}|"
            f"{','.join(matched[:3])}"
        )
