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
    # How long an action really runs. Supplied by the app because only it can
    # resolve aliases and read the frame tables; defaults to 0 so a caller that
    # does not provide one simply falls back to the declared durations.
    duration_of: Callable[[str], int] = lambda _action: 0


@dataclass(frozen=True)
class AnimationDebug:
    event: str = ""
    state: str = "idle"
    performance: str = ""
    lifecycle: str = ""
    source_costume: str = ""
    target_costume: str = ""
    duration_ms: int = 0
    minimum_ms: int = 0
    fallback_action: str = ""
    fallback_reason: str = ""
    source: str = "none"
    step_count: int = 0

    def text(self) -> str:
        return (
            f"event: {self.event or 'unknown'}\n"
            f"state: {self.state}\n"
            f"performance: {self.performance or 'none'}\n"
            f"lifecycle: {self.lifecycle or 'unknown'}\n"
            f"source_costume: {self.source_costume or 'none'}\n"
            f"target_costume: {self.target_costume or 'none'}\n"
            f"duration_ms: {self.duration_ms}\n"
            f"minimum_ms: {self.minimum_ms}\n"
            f"source: {self.source}\n"
            f"steps: {self.step_count}\n"
            f"fallback_action: {self.fallback_action or 'none'}\n"
            f"fallback_reason: {self.fallback_reason or 'none'}"
        )


def _step_advance(step, scheduled: bool, callbacks: AnimationCallbacks) -> int:
    """How long to wait before starting the next step.

    A declared duration_ms always wins, because that is an explicit directorial
    choice. Otherwise, if the step awaits its action, ask how long the action
    actually takes rather than assuming the author guessed right — that guess
    is what let the next step cut into a running one.
    """
    if step.duration_ms:
        return step.duration_ms
    if step.await_action and step.action:
        real = max(0, int(callbacks.duration_of(step.action)))
        if real:
            return max(0, real - max(0, step.overlap_ms))
    return 0 if not scheduled else 0


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
                lifecycle="unknown",
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
                lifecycle=definition.lifecycle,
                source_costume=definition.source_costume,
                target_costume=definition.target_costume,
                minimum_ms=definition.minimum_ms,
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
                lifecycle=definition.lifecycle,
                source_costume=definition.source_costume,
                target_costume=definition.target_costume,
                minimum_ms=definition.minimum_ms,
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

            elapsed += _step_advance(step, scheduled, callbacks)

        self.last_debug = AnimationDebug(
            event=event,
            state=state or "idle",
            performance=definition.name,
            lifecycle=definition.lifecycle,
            source_costume=definition.source_costume,
            target_costume=definition.target_costume,
            duration_ms=elapsed,
            minimum_ms=definition.minimum_ms,
            fallback_action=definition.fallback_action or reaction.action,
            source="manifest",
            step_count=len(definition.sequence),
        )
        return after_ids
