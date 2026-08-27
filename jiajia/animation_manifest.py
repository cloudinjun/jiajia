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
    # Wait for the action to actually finish instead of guessing how long it
    # takes. A hardcoded duration_ms that is shorter than the real action means
    # the next step starts on top of one still running, and whichever channel
    # it touches — body, tail, inner wire, prop — gets cancelled mid-motion.
    await_action: bool = False
    # Deliberate overlap, subtracted from the awaited duration, so a phrase can
    # blend rather than always landing on a hard cut.
    overlap_ms: int = 0


@dataclass(frozen=True)
class PerformanceDefinition:
    name: str
    kind: str = "procedural"
    lifecycle: str = "oneshot_return"
    source_state: str = ""
    target_state: str = ""
    source_costume: str = ""
    target_costume: str = ""
    minimum_ms: int = 0
    fallback_action: str = "idle"
    locks_cursor_follow: bool = False
    sequence: tuple[AnimationStep, ...] = ()


@dataclass(frozen=True)
class LogicalState:
    name: str
    performance: str = ""
    fallback_action: str = "idle"
    meaning: str = ""
    lifecycle: str = ""
    minimum_ms: int = 0
    priority: int = 0
    interruptible: bool = True
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentStateVisual:
    name: str
    animation: str = ""
    minimum_ms: int = 0
    priority: int = 0
    interruptible: bool = True


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
    agent_visuals: dict[str, AgentStateVisual] = field(default_factory=dict)
    state_aliases: dict[str, str] = field(default_factory=dict)

    def canonical_state(self, state: str) -> str:
        key = _key(state)
        if not key:
            return "idle"
        if key in self.state_aliases:
            return self.state_aliases[key]
        return key if key in self.states else "idle"

    def state_for_reaction(self, mood: str, action: str, bubble: str) -> str:
        mood = _key(mood)
        action = _key(action)
        bubble = _key(bubble)
        for rule in self.rules:
            if rule.matches(mood, action, bubble):
                return self.canonical_state(rule.state)
        return self.canonical_state(mood)

    def performance_for_state(self, state: str) -> str:
        logical_state = self.states.get(self.canonical_state(state))
        return logical_state.performance if logical_state else ""

    def fallback_action_for_state(self, state: str) -> str:
        logical_state = self.states.get(self.canonical_state(state))
        return logical_state.fallback_action if logical_state else "idle"

    def performance(self, name: str) -> PerformanceDefinition | None:
        return self.performances.get(_key(name))

    def agent_visual(self, name: str) -> AgentStateVisual | None:
        return self.agent_visuals.get(_key(name))


def load_animation_manifest(path: Path) -> AnimationManifest:
    data = _load_yaml(path) if path.exists() else {}
    states = {
        _key(name): LogicalState(
            name=_key(name),
            performance=_key(_dict(raw).get("performance")),
            fallback_action=_key(_dict(raw).get("fallback_action")) or "idle",
            meaning=str(_dict(raw).get("meaning") or ""),
            lifecycle=_key(_dict(raw).get("lifecycle")),
            minimum_ms=_int(_dict(raw).get("minimum_ms"), 0),
            priority=_int(_dict(raw).get("priority"), 0),
            interruptible=bool(_dict(raw).get("interruptible", True)),
            aliases=tuple(_key_list(_dict(raw).get("aliases"))),
        )
        for name, raw in _dict(data.get("logical_states")).items()
    }
    rules = tuple(_parse_rule(raw) for raw in _list(data.get("state_rules")) if isinstance(raw, dict))
    performances = {
        _key(name): _parse_performance(_key(name), raw)
        for name, raw in _dict(data.get("performance_phrases")).items()
    }
    agent_visuals = {
        _key(name): _parse_agent_visual(_key(name), raw)
        for name, raw in _dict(data.get("agent_state_visuals")).items()
    }
    return AnimationManifest(
        states=states,
        rules=rules,
        performances=performances,
        agent_visuals=agent_visuals,
        state_aliases=_state_aliases(states),
    )


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
        lifecycle=_key(data.get("lifecycle")) or "oneshot_return",
        source_state=_key(data.get("source_state")),
        target_state=_key(data.get("target_state")),
        source_costume=_key(data.get("source_costume")),
        target_costume=_key(data.get("target_costume")),
        minimum_ms=_int(data.get("minimum_ms"), 0),
        fallback_action=_key(data.get("fallback_action")) or "idle",
        locks_cursor_follow=bool(data.get("locks_cursor_follow", False)),
        sequence=sequence,
    )


def _parse_agent_visual(name: str, raw: object) -> AgentStateVisual:
    data = _dict(raw)
    return AgentStateVisual(
        name=name,
        animation=_key(data.get("animation")) or "idle_breathe",
        minimum_ms=_int(data.get("minimum_ms"), 0),
        priority=_int(data.get("priority"), 0),
        interruptible=bool(data.get("interruptible", True)),
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
        await_action=bool(raw.get("await_action", False)),
        overlap_ms=_int(raw.get("overlap_ms"), 0),
    )


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _key_list(value: object) -> list[str]:
    return [_key(item) for item in _list(value) if _key(item)]


def _state_aliases(states: dict[str, LogicalState]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for name, state in states.items():
        for alias in state.aliases:
            aliases[alias] = name
    return aliases


def _int(value: object, fallback: int) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return fallback
