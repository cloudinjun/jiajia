from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .soul import _load_yaml


@dataclass(frozen=True)
class AnimationStep:
    action: str = ""
    eyes: str = ""
    brows: str = ""
    bubble: str = ""
    reset: str = ""
    pause_ms: int = 0
    duration_ms: int = 0


@dataclass(frozen=True)
class PerformanceDefinition:
    name: str
    kind: str = "procedural"
    fallback_action: str = "idle"
    locks_cursor_follow: bool = False
    sequence: tuple[AnimationStep, ...] = ()


@dataclass(frozen=True)
class LogicalState:
    name: str
    performance: str = ""
    fallback_action: str = "idle"
    meaning: str = ""


@dataclass(frozen=True)
class StateRule:
    state: str
    moods: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()
    bubble_shapes: tuple[str, ...] = ()

    def matches(self, mood: str, action: str, bubble: str) -> bool:
        bubble_shape = bubble_shape_for(bubble)
        if self.bubble_shapes and bubble_shape not in self.bubble_shapes:
            return False
        checks: list[bool] = []
        if self.moods:
            checks.append(mood in self.moods)
        if self.actions:
            checks.append(action in self.actions)
        return any(checks) if checks else bool(self.bubble_shapes)


@dataclass(frozen=True)
class AnimationManifest:
    states: dict[str, LogicalState] = field(default_factory=dict)
    rules: tuple[StateRule, ...] = ()
    performances: dict[str, PerformanceDefinition] = field(default_factory=dict)

    def state_for_reaction(self, mood: str, action: str, bubble: str) -> str:
        mood = _key(mood)
        action = _key(action)
        bubble = _key(bubble)
        for rule in self.rules:
            if rule.matches(mood, action, bubble):
                return rule.state
        return mood if mood in self.states else "idle"

    def performance_for_state(self, state: str) -> str:
        logical_state = self.states.get(_key(state))
        return logical_state.performance if logical_state else ""

    def fallback_action_for_state(self, state: str) -> str:
        logical_state = self.states.get(_key(state))
        return logical_state.fallback_action if logical_state else "idle"

    def performance(self, name: str) -> PerformanceDefinition | None:
        return self.performances.get(_key(name))


def load_animation_manifest(path: Path) -> AnimationManifest:
    data = _load_yaml(path) if path.exists() else {}
    states = {
        _key(name): LogicalState(
            name=_key(name),
            performance=_key(_dict(raw).get("performance")),
            fallback_action=_key(_dict(raw).get("fallback_action")) or "idle",
            meaning=str(_dict(raw).get("meaning") or ""),
        )
        for name, raw in _dict(data.get("logical_states")).items()
    }
    rules = tuple(_parse_rule(raw) for raw in _list(data.get("state_rules")) if isinstance(raw, dict))
    performances = {
        _key(name): _parse_performance(_key(name), raw)
        for name, raw in _dict(data.get("performance_phrases")).items()
    }
    return AnimationManifest(states=states, rules=rules, performances=performances)


def bubble_shape_for(bubble: str) -> str:
    value = _key(bubble)
    if value.endswith("thought"):
        return "thought"
    if value.endswith("speech"):
        return "speech"
    return value if value in {"speech", "thought"} else "speech"


def _parse_rule(raw: dict[str, Any]) -> StateRule:
    return StateRule(
        state=_key(raw.get("state")) or "idle",
        moods=tuple(_key_list(raw.get("moods"))),
        actions=tuple(_key_list(raw.get("actions"))),
        bubble_shapes=tuple(_key_list(raw.get("bubble_shapes"))),
    )


def _parse_performance(name: str, raw: object) -> PerformanceDefinition:
    data = _dict(raw)
    sequence = tuple(_parse_step(step) for step in _list(data.get("sequence")) if isinstance(step, dict))
    return PerformanceDefinition(
        name=name,
        kind=_key(data.get("type")) or "procedural",
        fallback_action=_key(data.get("fallback_action")) or "idle",
        locks_cursor_follow=bool(data.get("locks_cursor_follow", False)),
        sequence=sequence,
    )


def _parse_step(raw: dict[str, Any]) -> AnimationStep:
    return AnimationStep(
        action=_key(raw.get("action")),
        eyes=_key(raw.get("eyes")),
        brows=_key(raw.get("brows")),
        bubble=_key(raw.get("bubble")),
        reset=_key(raw.get("reset")),
        pause_ms=_int(raw.get("pause_ms"), 0),
        duration_ms=_int(raw.get("duration_ms"), 0),
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _key_list(value: object) -> list[str]:
    return [_key(item) for item in _list(value) if _key(item)]


def _int(value: object, fallback: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback
