from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Labels for runtime_brief, per language.
_BRIEF_LABELS_ZH = {
    "nickname": "昵称", "relationship": "关系", "tension": "内在矛盾",
    "allowed": "可戳行为", "forbidden": "禁区", "silence": "沉默规则",
    "states": "情绪动作", "sample": "夹夹味例句", "comfort": "安慰模式",
    "trigger": "触发", "switch_to": "改为",
}
_BRIEF_LABELS_EN = {
    "nickname": "Nickname", "relationship": "Relationship", "tension": "Inner tension",
    "allowed": "Fair game", "forbidden": "Off limits", "silence": "Silence rule",
    "states": "Emotional actions", "sample": "Sample line", "comfort": "Comfort mode",
    "trigger": "triggered by", "switch_to": "switch to",
}


@dataclass
class Soul:
    name: str = "Jiajia"
    nicknames: list[str] = field(default_factory=list)
    vibe: str = "playful"
    persona_core: str = ""
    language: str = "zh-CN"
    text_model: str = "qwen3.5:9b"
    vision_model: str = "qwen3-vl:8b"
    relationship_to_user: list[str] = field(default_factory=list)
    core_tension: list[str] = field(default_factory=list)
    allowed_targets: list[str] = field(default_factory=list)
    forbidden_targets: list[str] = field(default_factory=list)
    emotional_states: dict[str, Any] = field(default_factory=dict)
    silence_rules: list[str] = field(default_factory=list)
    comfort_mode: dict[str, Any] = field(default_factory=dict)
    animation_hooks: dict[str, Any] = field(default_factory=dict)
    sample_dialogue: list[str] = field(default_factory=list)
    style: list[str] = field(default_factory=list)
    catchphrases: list[str] = field(default_factory=list)
    roast_pattern: list[str] = field(default_factory=list)
    innocent_closers: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    poke_responses: list[str] = field(default_factory=list)
    idle_min_seconds: int = 90
    idle_max_seconds: int = 260
    cooldown_seconds: int = 35
    max_line_chars: int = 42

    def runtime_brief(self) -> str:
        # this brief is pasted into the model prompt, so its labels follow the
        # pal's language: English content under Chinese headings used to drag
        # English replies back toward Chinese
        en = str(self.language).startswith("en")
        label = _BRIEF_LABELS_EN if en else _BRIEF_LABELS_ZH
        sep = ", " if en else "、"
        semi = "; " if en else "；"
        lines: list[str] = []
        if self.nicknames:
            lines.append(f"{label['nickname']}: {' / '.join(self.nicknames[:2])}")
        lines.extend(f"{label['relationship']}: {item}" for item in self.relationship_to_user[:2])
        lines.extend(f"{label['tension']}: {item}" for item in self.core_tension[:2])
        if self.allowed_targets:
            lines.append(f"{label['allowed']}: {sep.join(self.allowed_targets[:6])}")
        if self.forbidden_targets:
            lines.append(f"{label['forbidden']}: {sep.join(self.forbidden_targets[:8])}")
        lines.extend(f"{label['silence']}: {item}" for item in self.silence_rules[:3])
        comfort = self._comfort_brief()
        if comfort:
            lines.append(comfort)
        states = self._state_briefs()
        if states:
            lines.append(f"{label['states']}: {semi.join(states)}")
        if self.sample_dialogue:
            lines.append(f"{label['sample']}: {self.sample_dialogue[0]}")
        return "\n".join(lines)

    def _comfort_brief(self) -> str:
        triggers = _list(_dict(self.comfort_mode).get("triggers"))
        style = _list(_dict(self.comfort_mode).get("style"))
        if not triggers and not style:
            return ""
        en = str(self.language).startswith("en")
        label = _BRIEF_LABELS_EN if en else _BRIEF_LABELS_ZH
        parts = []
        if triggers:
            parts.append(f"{label['trigger']} {triggers[0]}")
        if style:
            joined = ", ".join(style[:2]) if en else "、".join(style[:2])
            parts.append(f"{label['switch_to']} {joined}")
        return f"{label['comfort']}: {'; '.join(parts) if en else '；'.join(parts)}"

    def _state_briefs(self) -> list[str]:
        briefs: list[str] = []
        for name in ("innocent", "smug", "suspicious", "guilty"):
            state = _dict(_dict(self.emotional_states).get(name))
            brief = str(state.get("brief") or "").strip()
            action = str(state.get("action") or "").strip()
            if brief and action:
                briefs.append(f"{name}={brief}/{action}")
            elif brief:
                briefs.append(f"{name}={brief}")
        return briefs


def load_soul(path: Path) -> Soul:
    data = _load_yaml(path)
    models = _dict(data.get("models"))
    voice = _dict(data.get("voice"))
    roast_style = _dict(data.get("roast_style"))
    idle = _dict(data.get("idle"))
    poke = _dict(data.get("poke"))
    return Soul(
        name=str(data.get("name") or "Jiajia"),
        nicknames=_list(data.get("nicknames")),
        vibe=str(data.get("vibe") or "playful"),
        persona_core=str(data.get("persona_core") or ""),
        language=str(data.get("language") or "zh-CN"),
        text_model=str(models.get("text") or "qwen3.5:9b"),
        vision_model=str(models.get("vision") or "qwen3-vl:8b"),
        relationship_to_user=_list(data.get("relationship_to_user")),
        core_tension=_list(data.get("core_tension")),
        allowed_targets=_list(data.get("allowed_targets")),
        forbidden_targets=_list(data.get("forbidden_targets")),
        emotional_states=_dict(data.get("emotional_states")),
        silence_rules=_list(data.get("silence_rules")),
        comfort_mode=_dict(data.get("comfort_mode")),
        animation_hooks=_dict(data.get("animation_hooks")),
        sample_dialogue=_list(data.get("sample_dialogue")),
        style=_list(voice.get("style")),
        catchphrases=_list(voice.get("catchphrases")),
        roast_pattern=_list(roast_style.get("pattern")),
        innocent_closers=_list(roast_style.get("innocent_closers")),
        rules=_list(data.get("rules")),
        poke_responses=_list(poke.get("responses")),
        idle_min_seconds=_int(idle.get("min_interval_seconds"), 90),
        idle_max_seconds=_int(idle.get("max_interval_seconds"), 260),
        cooldown_seconds=_int(idle.get("cooldown_seconds"), 35),
        max_line_chars=_int(idle.get("max_line_chars"), 42),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        loaded = yaml.safe_load(text)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return _load_simple_yaml(text)


def _load_simple_yaml(text: str) -> dict[str, Any]:
    lines = [
        (len(raw) - len(raw.lstrip(" ")), raw.strip())
        for raw in text.splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    ]
    value, _ = _parse_block(lines, 0, 0)
    return value if isinstance(value, dict) else {}


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index][0] < indent:
        return {}, index
    if lines[index][1].startswith("- "):
        values: list[Any] = []
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent != indent or not content.startswith("- "):
                break
            values.append(_parse_scalar(content[2:].strip()))
            index += 1
        return values, index

    values: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent != indent or ":" not in content:
            index += 1
            continue
        key, raw_value = content.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        index += 1
        if raw_value:
            values[key] = _parse_scalar(raw_value)
            continue
        child_indent = lines[index][0] if index < len(lines) else indent + 2
        values[key], index = _parse_block(lines, index, child_indent)
    return values, index


def _parse_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "None", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
