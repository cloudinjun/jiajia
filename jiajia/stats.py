from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class PalStats:
    """Persistent stats and achievement tracking for Jiajia."""

    total_pokes: int = 0
    total_lines_said: int = 0
    total_reactions: int = 0
    total_roasts: int = 0
    max_poke_streak: int = 0
    max_focus_seconds: float = 0.0
    total_sessions: int = 0
    total_runtime_seconds: float = 0.0
    identities_seen: list[str] = field(default_factory=list)
    achievements_unlocked: list[str] = field(default_factory=list)
    easter_eggs_found: list[str] = field(default_factory=list)
    combo_history: list[str] = field(default_factory=list)
    first_launch_at: float = 0.0
    last_session_at: float = 0.0

    def record_poke(self, streak: int = 1) -> list[str]:
        """Record a poke and return any newly unlocked achievements."""
        self.total_pokes += 1
        if streak > self.max_poke_streak:
            self.max_poke_streak = streak
        return self._check_poke_achievements()

    def record_line(self, is_roast: bool = False) -> None:
        self.total_lines_said += 1
        if is_roast:
            self.total_roasts += 1

    def record_reaction(self) -> None:
        self.total_reactions += 1

    def record_identity(self, identity_id: str) -> None:
        if identity_id and identity_id not in self.identities_seen:
            self.identities_seen.append(identity_id)

    def record_easter_egg(self, egg_id: str) -> bool:
        """Returns True if this is a NEW egg discovery."""
        if egg_id not in self.easter_eggs_found:
            self.easter_eggs_found.append(egg_id)
            return True
        return False

    def record_combo(self, combo_id: str) -> bool:
        if combo_id not in self.combo_history:
            self.combo_history.append(combo_id)
            return True
        return False

    def unlock_achievement(self, achievement_id: str) -> bool:
        if achievement_id not in self.achievements_unlocked:
            self.achievements_unlocked.append(achievement_id)
            return True
        return False

    def summary_text(self, language: str = "zh-CN") -> str:
        if language == "en":
            return (
                f"Pokes: {self.total_pokes} | Lines: {self.total_lines_said} | "
                f"Roasts: {self.total_roasts}\n"
                f"Max poke streak: {self.max_poke_streak} | "
                f"Max focus: {self.max_focus_seconds / 60:.0f} min\n"
                f"Identities seen: {len(self.identities_seen)} | "
                f"Achievements: {len(self.achievements_unlocked)} | "
                f"Easter eggs: {len(self.easter_eggs_found)}"
            )
        return (
            f"戳戳次数: {self.total_pokes} | 说话次数: {self.total_lines_said} | "
            f"毒舌次数: {self.total_roasts}\n"
            f"最长连戳: {self.max_poke_streak} | "
            f"最长专注: {self.max_focus_seconds / 60:.0f} 分钟\n"
            f"见过身份: {len(self.identities_seen)} 个 | "
            f"成就: {len(self.achievements_unlocked)} | "
            f"彩蛋: {len(self.easter_eggs_found)}"
        )

    def _check_poke_achievements(self) -> list[str]:
        new: list[str] = []
        milestones = {
            10: "curious_finger",
            50: "persistent_poker",
            100: "paperclip_bully",
            500: "desktop_percussionist",
        }
        for count, achievement in milestones.items():
            if self.total_pokes >= count and achievement not in self.achievements_unlocked:
                self.achievements_unlocked.append(achievement)
                new.append(achievement)
        return new


# Combo definitions: sequences of actions that trigger special responses
COMBO_DEFINITIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "triple_poke": (("poke", "poke", "poke"), "三连戳！任务也能被你这样推吗？"),
    "poke_then_hide": (("poke", "hide"), "戳完就躲？像极了你对 deadline 的态度。"),
    "dance_celebrate": (("dance", "celebrate"), "连续快乐！难得。"),
}

ACHIEVEMENT_LABELS: dict[str, dict[str, str]] = {
    "curious_finger": {"zh-CN": "好奇的手指 (戳10次)", "en": "Curious Finger (10 pokes)"},
    "persistent_poker": {"zh-CN": "执着的戳客 (戳50次)", "en": "Persistent Poker (50 pokes)"},
    "paperclip_bully": {"zh-CN": "纸夹霸凌者 (戳100次)", "en": "Paperclip Bully (100 pokes)"},
    "desktop_percussionist": {"zh-CN": "桌面打击乐手 (戳500次)", "en": "Desktop Percussionist (500 pokes)"},
    "night_owl": {"zh-CN": "夜猫子 (凌晨3点还在)", "en": "Night Owl (still here at 3 AM)"},
    "focus_master": {"zh-CN": "专注大师 (连续专注2小时)", "en": "Focus Master (2hr focus streak)"},
    "identity_collector": {"zh-CN": "身份收集家 (见过所有身份)", "en": "Identity Collector (all identities seen)"},
}

EASTER_EGG_TRIGGERS: dict[str, str] = {
    "midnight_poke": "在午夜12点整（±30秒）戳夹夹",
    "100_pokes": "累计戳满100次",
    "all_identities": "触发过所有11种身份",
    "friday_5pm": "周五下午5点还在工作",
}


def load_stats(path: Path) -> PalStats:
    if not path.exists():
        stats = PalStats(first_launch_at=time.time())
        save_stats(stats, path)
        return stats
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return PalStats(**{k: v for k, v in data.items() if k in PalStats.__dataclass_fields__})
    except Exception:
        return PalStats(first_launch_at=time.time())


def save_stats(stats: PalStats, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(stats), ensure_ascii=False, indent=2), encoding="utf-8")
