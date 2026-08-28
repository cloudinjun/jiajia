from __future__ import annotations

import json
from pathlib import Path

from .i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("zh-CN", "\u4e2d\u6587"),
    ("en", "English"),
)


def normalize_language(value: object, fallback: str = DEFAULT_LANGUAGE) -> str:
    raw = str(value or "").strip()
    aliases = {
        "zh": "zh-CN",
        "zh_cn": "zh-CN",
        "zh-cn": "zh-CN",
        "cn": "zh-CN",
        "\u4e2d\u6587": "zh-CN",
        "chinese": "zh-CN",
        "en-us": "en",
        "en_us": "en",
        "english": "en",
    }
    key = aliases.get(raw.lower(), raw)
    return key if key in SUPPORTED_LANGUAGES else fallback


def language_label(language: str) -> str:
    normalized = normalize_language(language)
    return dict(LANGUAGE_OPTIONS).get(normalized, normalized)


def load_language_setting(project_root: Path, fallback: str = DEFAULT_LANGUAGE) -> str:
    path = project_root / "settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return normalize_language(fallback)
    if not isinstance(data, dict):
        return normalize_language(fallback)
    return normalize_language(data.get("language"), fallback=fallback)


def soul_path_for_language(package_root: Path, language: str) -> Path:
    normalized = normalize_language(language)
    if normalized == "en":
        en_path = package_root / "locales" / "en_soul.yaml"
        if en_path.exists():
            return en_path
    return package_root / "soul.yaml"


def identities_path_for_language(package_root: Path, language: str) -> Path:
    """Identity manifest for a language, falling back to the Chinese one.

    Without this the English mode loaded the Chinese manifest and then had to
    skip identity lines wholesale, which silently removed all twelve identity
    packs from English.
    """
    normalized = normalize_language(language)
    if normalized == "en":
        en_path = package_root / "locales" / "en_identities.yaml"
        if en_path.exists():
            return en_path
    return package_root / "identities.yaml"


# Menu labels that differ by language. Anything not listed here is already
# language-neutral (proper nouns like "Codex", or English terms the Chinese
# menu also uses).
#
# This exists because the menu carried hardcoded Chinese — "Talk to 夹夹",
# "土味情话", "退出" — which stayed Chinese in English mode. The character's
# name is the pal's own, so it is romanised rather than translated.
MENU_LABELS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "talk": "和夹夹聊天",
        "cheesy_love": "土味情话",
        "quiz": "小测验",
        "language": "语言",
        "quit": "退出",
        "say_something": "说句话",
        "poke": "戳一下",
        "status": "状态",
        "status_overview": "状态总览",
        "codex_status": "Codex 状态",
        "codex_usage": "Codex 用量",
        "claude_status": "Claude 状态",
        "claude_usage": "Claude 用量",
        "claude_account_usage": "Claude 账号用量",
        "openai_billing": "OpenAI API 账单",
        "hardware_status": "硬件状态",
        "last_events": "最近事件",
        "morning_digest": "晨报",
        "actions": "动作",
        "boredom_line": "无聊冷话",
        "mode": "模式",
        "identity": "身份",
        "identity_auto": "自动",
        "activity": "活跃度",
        "tail_menu": "尾巴",
        "tail_short": "短尾（只动尖端）",
        "tail_long": "长尾（猫尾）",
        "quiet_30": "安静 30 分钟",
        "focus_mode": "专注模式",
        "resume": "召唤 / 恢复播报",
        "developer": "开发者",
        "animation_preview": "动画预览",
        "scripted_demo": "脚本演示",
        "debug_decision": "调试：上次决策",
        "debug_chat_context": "调试：聊天上下文",
        "debug_animation": "调试：动画",
        "debug_alive": "调试：活性",
        "debug_identity": "调试：身份",
    },
    "en": {
        "talk": "Talk to Jiajia",
        "cheesy_love": "Cheesy line",
        "quiz": "Absurd quiz",
        "language": "Language",
        "quit": "Quit",
        "say_something": "Say something",
        "poke": "Poke",
        "status": "Status",
        "status_overview": "Status overview",
        "codex_status": "Codex status",
        "codex_usage": "Codex usage",
        "claude_status": "Claude status",
        "claude_usage": "Claude usage",
        "claude_account_usage": "Claude account usage",
        "openai_billing": "OpenAI API billing",
        "hardware_status": "Hardware status",
        "last_events": "Last events",
        "morning_digest": "Morning digest",
        "actions": "Actions",
        "boredom_line": "Boredom line",
        "mode": "Mode",
        "identity": "Identity",
        "identity_auto": "Auto",
        "activity": "Activity",
        "tail_menu": "Tail",
        "tail_short": "Short (tip only)",
        "tail_long": "Long (cat tail)",
        "quiet_30": "Quiet 30 min",
        "focus_mode": "Focus mode",
        "resume": "Summon / resume",
        "developer": "Developer",
        "animation_preview": "Animation Preview",
        "scripted_demo": "Scripted demo",
        "debug_decision": "Debug last decision",
        "debug_chat_context": "Last chat context",
        "debug_animation": "Debug animation",
        "debug_alive": "Debug aliveness",
        "debug_identity": "Debug identity",
    },
}


def menu_label(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Display text for a menu entry in the pal's language."""
    lang = "en" if normalize_language(language) == "en" else "zh-CN"
    return MENU_LABELS[lang].get(key, MENU_LABELS["zh-CN"].get(key, key))
