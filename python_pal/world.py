from __future__ import annotations

from dataclasses import dataclass
import time

from .claude_status import ClaudeOverview
from .claude_usage import ClaudeUsageStatus
from .codex_status import CodexStatus
from .codex_usage import CodexUsageStatus
from .ears import EarContext
from .eyes import ScreenContext
from .hardware_status import HardwareSnapshot
from .state import PalState


@dataclass(frozen=True)
class MoodSnapshot:
    key: str
    energy: float
    valence: float
    frequency_multiplier: float

    def as_dict(self) -> dict[str, object]:
        return {
            "mood_key": self.key,
            "mood_energy": round(self.energy, 3),
            "mood_valence": round(self.valence, 3),
            "frequency_multiplier": round(self.frequency_multiplier, 2),
        }


@dataclass(frozen=True)
class WorldState:
    user_activity: EarContext
    screen: ScreenContext
    codex: CodexStatus
    codex_usage: CodexUsageStatus
    claude: ClaudeOverview
    claude_usage: ClaudeUsageStatus
    hardware: HardwareSnapshot
    pal: PalState
    mood: MoodSnapshot
    sampled_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.sampled_at:
            object.__setattr__(self, "sampled_at", time.time())

    @property
    def environment_tags(self) -> list[str]:
        tags = set(self.user_activity.behavior_tags) | set(self.screen.screen_tags)
        if self.codex.status not in {"unknown", "idle"} and not self.codex.stale:
            tags.add(f"codex_{self.codex.status}")
        tags.update(self.codex_usage.tags)
        if self.claude.active_count:
            tags.add("claude_active")
        elif self.claude.total_alive:
            tags.add("claude_idle")
        tags.update(self.claude_usage.tags)
        tags.update(self.hardware.tags)
        return sorted(tags)

    def as_context(self, event: str) -> dict[str, object]:
        return {
            "event": event,
            "mood": self.pal.mood,
            "recent_lines": self.pal.recent_lines[-4:],
            "environment_tags": self.environment_tags,
            **self.user_activity.as_dict(),
            **self.screen.as_dict(),
            **self.codex.as_dict(),
            **self.codex_usage.as_dict(),
            **self.claude_usage.as_dict(),
            **self.hardware.as_dict(),
            "claude_total_alive": self.claude.total_alive,
            "claude_active_count": self.claude.active_count,
            "claude_sessions": [
                {
                    "label": session.label(),
                    "project": session.project,
                    "activity": session.activity,
                    "idle_seconds": round(session.idle_seconds, 1),
                }
                for session in self.claude.sessions
                if session.alive
            ][:4],
            **self.mood.as_dict(),
        }
