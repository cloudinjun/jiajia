from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass
class Reaction:
    should_say: bool = True
    line: str = ""
    mood: str = "smirk"
    action: str = "idle"
    bubble: str = "speech"
    performance: str = ""
    decision_reason: str = ""
    event: str = ""


@dataclass
class PalState:
    mood: str = "idle"
    last_spoke_at: float = 0.0
    recent_lines: list[str] = field(default_factory=list)
    brain_busy: bool = False

    def can_speak(self, cooldown_seconds: int) -> bool:
        return time.time() - self.last_spoke_at >= cooldown_seconds and not self.brain_busy

    def remember_line(self, line: str) -> None:
        self.last_spoke_at = time.time()
        clean = line.strip()
        if clean:
            self.recent_lines.append(clean)
            self.recent_lines = self.recent_lines[-8:]
