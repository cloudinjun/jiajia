from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .soul import _load_yaml


SUPPORTED_LANGUAGES = ("zh-CN", "en")
DEFAULT_LANGUAGE = "zh-CN"

# UI strings keyed by dotted path, e.g. "menu.actions", "status.idle"
_STRINGS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "menu.actions": "动作",
        "menu.mood": "心情",
        "menu.state": "状态",
        "menu.reactive": "反应",
        "menu.movement": "移动",
        "menu.frequency": "频率",
        "menu.frequency.quiet": "安静",
        "menu.frequency.normal": "正常",
        "menu.frequency.active": "活泼",
        "menu.frequency.hyper": "多动",
        "menu.settings": "设置",
        "menu.debug": "调试",
        "menu.quit": "退出",
        "menu.chat": "聊天",
        "menu.identity": "人格",
        "menu.stats": "统计",
        "status.idle": "发呆中",
        "status.offline": "已结束",
        "status.thinking": "思考中",
        "status.editing": "改代码",
        "status.running": "跑命令",
        "status.reading": "读文件",
        "status.searching": "搜索中",
        "greeting.morning": "早上好！新的一天又可以围观你工作了。",
        "greeting.afternoon": "下午好！你今天效率如何？（修辞问句）",
        "greeting.default": "嗨！好久不见。我一直在这里，以文具的形式。",
        "greeting.long_absence": "你消失了好几天。桌面开始有考古感了。",
        "care.work_3h": "你已经连续工作三小时了。建议休息。我不是关心你，是怕键盘先罢工。",
        "care.welcome_back": "你回来了。桌面恢复了被围观的状态。",
        "care.late_night": "很晚了。文具建议你关机。这不是关心，是节能。",
        "achievement.focus_2h": "连续专注两小时。这个成就解锁得很安静。",
        "achievement.rapid_switch": "切窗口新纪录。效率和注意力分别在两个方向刷新了。",
        "no_claude_sessions": "没有发现活跃的 Claude 会话。",
    },
    "en": {
        "menu.actions": "Actions",
        "menu.mood": "Mood",
        "menu.state": "State",
        "menu.reactive": "Reactive",
        "menu.movement": "Movement",
        "menu.frequency": "Frequency",
        "menu.frequency.quiet": "Quiet",
        "menu.frequency.normal": "Normal",
        "menu.frequency.active": "Active",
        "menu.frequency.hyper": "Hyper",
        "menu.settings": "Settings",
        "menu.debug": "Debug",
        "menu.quit": "Quit",
        "menu.chat": "Chat",
        "menu.identity": "Identity",
        "menu.stats": "Stats",
        "status.idle": "Idle",
        "status.offline": "Offline",
        "status.thinking": "Thinking",
        "status.editing": "Editing",
        "status.running": "Running",
        "status.reading": "Reading",
        "status.searching": "Searching",
        "greeting.morning": "Morning! Another day of watching you work.",
        "greeting.afternoon": "Afternoon! How's your productivity? (Rhetorical.)",
        "greeting.default": "Hi! Long time. I've been here. As stationery.",
        "greeting.long_absence": "You vanished for days. The desktop is developing archaeology vibes.",
        "care.work_3h": "Three hours straight. Maybe take a break. Not that I care — I'm worried about the keyboard.",
        "care.welcome_back": "You're back. The desktop resumes its observed state.",
        "care.late_night": "It's late. This paperclip recommends shutting down. Not concern — energy efficiency.",
        "achievement.focus_2h": "Two hours of focus. Achievement unlocked, quietly.",
        "achievement.rapid_switch": "New window-switching record. Efficiency and attention went in opposite directions.",
        "no_claude_sessions": "No active Claude sessions found.",
    },
}


@dataclass
class I18n:
    """Lightweight i18n registry for UI strings and locale-aware file loading."""

    language: str = DEFAULT_LANGUAGE
    _custom: dict[str, str] = field(default_factory=dict)

    def t(self, key: str, fallback: str = "") -> str:
        """Look up a UI string by dotted key."""
        custom = self._custom.get(key)
        if custom:
            return custom
        lang_strings = _STRINGS.get(self.language, _STRINGS[DEFAULT_LANGUAGE])
        result = lang_strings.get(key)
        if result:
            return result
        # fall back to default language
        if self.language != DEFAULT_LANGUAGE:
            result = _STRINGS[DEFAULT_LANGUAGE].get(key)
            if result:
                return result
        return fallback or key

    def set_language(self, language: str) -> None:
        if language in SUPPORTED_LANGUAGES:
            self.language = language

    def seed_file(self) -> Path:
        """Return the path to the locale-specific seeds YAML."""
        lang_prefix = "en" if self.language == "en" else "zh"
        return Path(__file__).parent / "locales" / f"{lang_prefix}_seeds.yaml"

    def soul_file(self, base_dir: Path) -> Path:
        """Return locale-specific soul.yaml path, falling back to default."""
        if self.language == "en":
            en_path = base_dir / "locales" / "en_soul.yaml"
            if en_path.exists():
                return en_path
        return base_dir / "soul.yaml"

    def identities_file(self, base_dir: Path) -> Path:
        """Return locale-specific identities.yaml path, falling back to default."""
        if self.language == "en":
            en_path = base_dir / "locales" / "en_identities.yaml"
            if en_path.exists():
                return en_path
        return base_dir / "identities.yaml"
