from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .animation_manifest import AnimationManifest, PerformanceDefinition
from .state import Reaction


AfterCallback = Callable[[int, Callable[[], None]], str]


@dataclass(frozen=True)
class AnimationCallbacks:
    after: AfterCallback
    action: Callable[[str], None]
    bubble: Callable[[Reaction], None]
    eyes: Callable[[str], None]
    brows: Callable[[str], None]
    reset_expression: Callable[[], None]
    stop_cursor_follow: Callable[[], None]


@dataclass(frozen=True)
class AnimationDebug:
    event: str = ""
    state: str = "idle"
    performance: str = ""
    fallback_action: str = ""
    fallback_reason: str = ""
    source: str = "none"
    step_count: int = 0

    def text(self) -> str:
        return (
            f"event: {self.event or 'unknown'}\n"
            f"state: {self.state}\n"
            f"performance: {self.performance or 'none'}\n"
            f"source: {self.source}\n"
            f"steps: {self.step_count}\n"
            f"fallback_action: {self.fallback_action or 'none'}\n"
            f"fallback_reason: {self.fallback_reason or 'none'}"
        )


class AnimationPlayer:
    def __init__(self, manifest: AnimationManifest) -> None:
        self.manifest = manifest
        self.last_debug = AnimationDebug(fallback_reason="not played yet")

    def play(
        self,
        performance_id: str,
        reaction: Reaction,
        callbacks: AnimationCallbacks,
        state: str = "",
        event: str = "",
    ) -> list[str]:
        performance_id = performance_id.strip().lower().replace("-", "_")
        definition = self.manifest.performance(performance_id)
        if not definition:
            self.last_debug = AnimationDebug(
                event=event,
                state=state or "idle",
                performance=performance_id,
                fallback_action=reaction.action,
                fallback_reason="missing_performance",
                source="manifest",
            )
            return []
        if definition.kind != "procedural":
            self.last_debug = AnimationDebug(
                event=event,
                state=state or "idle",
                performance=definition.name,
                fallback_action=definition.fallback_action or reaction.action,
                fallback_reason=f"unsupported_type:{definition.kind}",
                source="manifest",
            )
            return []
        if not definition.sequence:
            self.last_debug = AnimationDebug(
                event=event,
                state=state or "idle",
                performance=definition.name,
                fallback_action=definition.fallback_action or reaction.action,
                fallback_reason="empty_sequence",
                source="manifest",
            )
            return []

        if definition.locks_cursor_follow:
            callbacks.stop_cursor_follow()

        after_ids: list[str] = []
        elapsed = 0
        for step in definition.sequence:
            if step.pause_ms:
                elapsed += step.pause_ms
                continue

            scheduled = False
            if step.action:
                after_ids.append(callbacks.after(elapsed, lambda action=step.action: callbacks.action(action)))
                scheduled = True
            if step.eyes:
                after_ids.append(callbacks.after(elapsed, lambda eyes=step.eyes: callbacks.eyes(eyes)))
                scheduled = True
            if step.brows:
                after_ids.append(callbacks.after(elapsed, lambda brows=step.brows: callbacks.brows(brows)))
                scheduled = True
            if step.bubble == "speak":
                after_ids.append(callbacks.after(elapsed, lambda r=reaction: callbacks.bubble(r)))
                scheduled = True
            if step.reset == "expression":
                after_ids.append(callbacks.after(elapsed, callbacks.reset_expression))
                scheduled = True

            elapsed += step.duration_ms if scheduled or step.duration_ms else 0

        self.last_debug = AnimationDebug(
            event=event,
            state=state or "idle",
            performance=definition.name,
            fallback_action=definition.fallback_action or reaction.action,
            source="manifest",
            step_count=len(definition.sequence),
        )
        return after_ids
