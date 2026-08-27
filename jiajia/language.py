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
