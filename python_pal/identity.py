from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random
from typing import Any

from .soul import _load_yaml


AUTO_IDENTITY = "auto"
DEFAULT_IDENTITY = "default_pal"


@dataclass(frozen=True)
class IdentityPack:
    id: str
    display_name: str
    purpose: str
    roast_angle: str = ""
    visual_formula: str = ""
    color_accent: str = ""
    default_mood: str = "smirk"
    fallback_action: str = "blink"
    preferred_performance: str = ""
    triggers: tuple[str, ...] = ()
    visual_addons: tuple[str, ...] = ()
    animations: dict[str, str] = field(default_factory=dict)
    lines: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def prompt_brief(self) -> str:
        line = self.pick_line("normal") or self.pick_line("warning")
        bits = [
            f"当前身份: {self.display_name} ({self.id})",
            f"用途: {self.purpose}",
        ]
        if self.roast_angle:
            bits.append(f"吐槽视角: {self.roast_angle}")
        if self.visual_formula:
            bits.append(f"视觉边界: {self.visual_formula}")
        bits.append(
            "动作倾向: "
            f"mood={self.default_mood}, action={self.fallback_action}, "
            f"performance={self.preferred_performance or 'auto'}"
        )
        if line:
            bits.append(f"台词味道: {line}")
        return "\n".join(bits)

    def pick_line(self, level: str = "normal") -> str:
        candidates = self.lines.get(level) or self.lines.get("normal") or ()
        return random.choice(candidates) if candidates else ""

    def line_levels(self) -> tuple[str, ...]:
        return tuple(self.lines.keys())


@dataclass(frozen=True)
class IdentityManifest:
    packs: dict[str, IdentityPack] = field(default_factory=dict)
    default_id: str = DEFAULT_IDENTITY

    def get(self, identity_id: str) -> IdentityPack:
        key = _key(identity_id)
        return self.packs.get(key) or self.packs.get(self.default_id) or _fallback_pack()

    def menu_packs(self) -> list[IdentityPack]:
        return [pack for pack in self.packs.values() if pack.id != self.default_id]

    def select(self, event: str, context: dict[str, object] | None = None) -> IdentityPack:
        context = context or {}
        requested = _key(context.get("identity_id") or context.get("identity"))
        if requested and requested != AUTO_IDENTITY and requested in self.packs:
            return self.packs[requested]

        tags = _context_tags(event, context)
        best = self.get(self.default_id)
        best_score = 0
        for pack in self.packs.values():
            if pack.id == self.default_id:
                continue
            score = _score_pack(pack, tags)
            if score > best_score:
                best = pack
                best_score = score
        return best

    def prompt_brief(self, event: str, context: dict[str, object] | None = None) -> str:
        return self.select(event, context).prompt_brief()

    def level_for(self, event: str, context: dict[str, object] | None, pack: IdentityPack) -> str:
        tags = _context_tags(event, context or {})
        if tags & {"critical", "usage_critical", "gpu_temp_critical", "codex_error", "codex_blocked", "error", "blocked"}:
            if pack.lines.get("critical"):
                return "critical"
        if tags & {"recovery", "codex_done", "done", "refill", "cooldown_recover"}:
            if pack.lines.get("recovery"):
                return "recovery"
        if event in {"ambient", "idle"} and pack.lines.get("warning"):
            return "warning"
        return "normal"

    def catalog_brief(self, limit: int = 12) -> str:
        packs = self.menu_packs()[:limit]
        return "\n".join(f"- {pack.id}: {pack.display_name} | {pack.purpose}" for pack in packs)

    def seed_entries(self) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        for pack in self.packs.values():
            if pack.id == self.default_id:
                continue
            for level in pack.line_levels():
                event = "ambient" if level in {"warning", "critical", "recovery"} else "manual"
                for line in pack.lines.get(level, ()):
                    entries.append(
                        {
                            "event": event,
                            "line": line,
                            "mood": pack.default_mood,
                            "action": pack.fallback_action,
                            "bubble": "thought" if event == "ambient" else "speech",
                            "performance": pack.preferred_performance,
                            "tags": [pack.id, level],
                            "source": "identity_seed",
                        }
                    )
        return entries


def load_identity_manifest(path: Path) -> IdentityManifest:
    data = _load_yaml(path) if path.exists() else {}
    raw_packs = _list(data.get("identities"))
    packs: dict[str, IdentityPack] = {}
    for raw in raw_packs:
        if isinstance(raw, dict):
            pack = _parse_pack(raw)
            packs[pack.id] = pack
    default_id = _key(data.get("default_identity")) or DEFAULT_IDENTITY
    if default_id not in packs:
        fallback = _fallback_pack()
        packs[fallback.id] = fallback
        default_id = fallback.id
    return IdentityManifest(packs=packs, default_id=default_id)


def _parse_pack(raw: dict[str, Any]) -> IdentityPack:
    pack_id = _key(raw.get("id")) or DEFAULT_IDENTITY
    lines = {
        _key(level): tuple(str(item).strip() for item in _list(values) if str(item).strip())
        for level, values in _dict(raw.get("lines")).items()
    }
    return IdentityPack(
        id=pack_id,
        display_name=str(raw.get("display_name") or pack_id),
        purpose=str(raw.get("purpose") or ""),
        roast_angle=str(raw.get("roast_angle") or ""),
        visual_formula=str(raw.get("visual_formula") or ""),
        color_accent=_key(raw.get("color_accent")),
        default_mood=_key(raw.get("default_mood")) or "smirk",
        fallback_action=_key(raw.get("fallback_action")) or "blink",
        preferred_performance=_key(raw.get("preferred_performance")),
        triggers=tuple(_key_list(raw.get("triggers"))),
        visual_addons=tuple(_key_list(raw.get("visual_addons"))),
        animations={_key(key): _key(value) for key, value in _dict(raw.get("animations")).items()},
        lines=lines,
    )


def _score_pack(pack: IdentityPack, tags: set[str]) -> int:
    score = 0
    for trigger in pack.triggers:
        if trigger in tags:
            score += 3 if trigger.startswith("event_") else 10
    if pack.id in tags:
        score += 100
    if pack.default_mood in tags:
        score += 2
    return score


def _context_tags(event: str, context: dict[str, object]) -> set[str]:
    tags = {_key(event), f"event_{_key(event)}"}
    for key in ("environment_tags", "behavior_tags", "screen_tags"):
        value = context.get(key)
        if isinstance(value, list):
            tags.update(_key(item) for item in value if _key(item))
    for key in ("app_category", "active_process", "codex_status"):
        value = _key(context.get(key))
        if value:
            tags.add(value)
            tags.add(f"{key}_{value}")
    if _as_int(context.get("claude_active_count")) > 0:
        tags.add("claude_active")
    return tags


def _fallback_pack() -> IdentityPack:
    return IdentityPack(
        id=DEFAULT_IDENTITY,
        display_name="Default Pal",
        purpose="保持夹夹本体的乖巧嘴欠气质。",
        roast_angle="只戳行为，不戳人。",
        visual_formula="同一只回形针，不加嘴和四肢。",
        default_mood="smirk",
        fallback_action="blink",
        preferred_performance="cold_arrow_then_innocent",
        lines={"normal": ("我只是路过。意见暂时折起来。",)},
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _key_list(value: object) -> list[str]:
    return [_key(item) for item in _list(value) if _key(item)]


def _as_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
