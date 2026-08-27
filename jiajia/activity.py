from __future__ import annotations

from dataclasses import dataclass

from .mood import FREQUENCY_DEFAULT, normalize_frequency


ALL_CODEX_STATUSES = frozenset(
    {
        "thinking",
        "reading",
        "working",
        "editing",
        "running",
        "running_command",
        "testing",
        "reconnecting",
        "disconnected",
        "waiting_user",
        "done",
        "error",
        "blocked",
    }
)

ALL_CLAUDE_EVENTS = frozenset(
    {
        "started",
        "ended",
        "editing",
        "running",
        "searching",
        "reading",
        "thinking",
        "idle",
        "overview",
        "no_session",
    }
)


@dataclass(frozen=True)
class ActivityPolicy:
    key: str
    tier: str
    speech_frequency: float
    animation_frequency: float
    proactive_detection: float
    alert_threshold: str
    ambient_enabled: bool
    companion_chatter_chance: float
    mouse_follow_chance: float
    companion_action_chance: float
    cooldown_multiplier: float
    codex_statuses: frozenset[str]
    claude_events: frozenset[str]
    hardware_levels: frozenset[str]
    usage_levels: frozenset[str]
    usage_low_percent_threshold: float
    usage_watch_percent_threshold: float

    def allows_codex_status(self, status: str) -> bool:
        return status in self.codex_statuses

    def allows_claude_event(self, event: str) -> bool:
        normalized = event.removeprefix("claude_")
        return normalized in self.claude_events

    def allows_hardware_level(self, level: str) -> bool:
        return level in self.hardware_levels

    def allows_usage(self, level: str, percent: float | None) -> bool:
        if level == "low" and percent is not None:
            return level in self.usage_levels and percent <= self.usage_low_percent_threshold
        if level == "watch" and percent is not None:
            return level in self.usage_levels and percent <= self.usage_watch_percent_threshold
        return level in self.usage_levels


POLICIES: dict[str, ActivityPolicy] = {
    "quiet": ActivityPolicy(
        key="quiet",
        tier="quiet",
        speech_frequency=0.2,
        animation_frequency=0.45,
        proactive_detection=0.0,
        alert_threshold="critical_only",
        ambient_enabled=False,
        companion_chatter_chance=0.0,
        mouse_follow_chance=0.04,
        companion_action_chance=0.08,
        cooldown_multiplier=2.2,
        codex_statuses=frozenset({"waiting_user", "error", "blocked"}),
        claude_events=frozenset(),
        hardware_levels=frozenset({"overloaded"}),
        usage_levels=frozenset({"critical"}),
        usage_low_percent_threshold=0.0,
        usage_watch_percent_threshold=0.0,
    ),
    "normal": ActivityPolicy(
        key="normal",
        tier="normal",
        speech_frequency=1.0,
        animation_frequency=1.0,
        proactive_detection=0.75,
        alert_threshold="important_changes",
        ambient_enabled=True,
        companion_chatter_chance=0.04,
        mouse_follow_chance=0.14,
        companion_action_chance=0.18,
        cooldown_multiplier=1.0,
        codex_statuses=frozenset({"waiting_user", "done", "error", "blocked", "disconnected"}),
        claude_events=frozenset({"started", "ended"}),
        hardware_levels=frozenset({"hot", "overloaded"}),
        usage_levels=frozenset({"low", "critical", "reset_soon", "refilled"}),
        usage_low_percent_threshold=20.0,
        usage_watch_percent_threshold=0.0,
    ),
    "active": ActivityPolicy(
        key="active",
        tier="active",
        speech_frequency=1.45,
        animation_frequency=1.6,
        proactive_detection=1.2,
        alert_threshold="early_warning",
        ambient_enabled=True,
        companion_chatter_chance=0.14,
        mouse_follow_chance=0.28,
        companion_action_chance=0.38,
        cooldown_multiplier=0.75,
        codex_statuses=ALL_CODEX_STATUSES,
        claude_events=ALL_CLAUDE_EVENTS,
        hardware_levels=frozenset({"warm", "hot", "overloaded", "cooling"}),
        usage_levels=frozenset({"watch", "low", "critical", "reset_soon", "refilled"}),
        usage_low_percent_threshold=30.0,
        usage_watch_percent_threshold=40.0,
    ),
    "hyper": ActivityPolicy(
        key="hyper",
        tier="hyper",
        speech_frequency=2.1,
        animation_frequency=2.3,
        proactive_detection=1.8,
        alert_threshold="personality_mode",
        ambient_enabled=True,
        companion_chatter_chance=0.28,
        mouse_follow_chance=0.52,
        companion_action_chance=0.66,
        cooldown_multiplier=0.55,
        codex_statuses=ALL_CODEX_STATUSES,
        claude_events=ALL_CLAUDE_EVENTS,
        hardware_levels=frozenset({"warm", "hot", "overloaded", "cooling"}),
        usage_levels=frozenset({"watch", "low", "critical", "reset_soon", "refilled"}),
        usage_low_percent_threshold=30.0,
        usage_watch_percent_threshold=60.0,
    ),
}


def policy_for_frequency(key: str) -> ActivityPolicy:
    """Look up a policy by activity key, tolerating the older Chinese keys."""
    return POLICIES.get(normalize_frequency(key), POLICIES[FREQUENCY_DEFAULT])
