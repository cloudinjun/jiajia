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
    # Whether this playthrough is still the current one. The chain asks before
    # every step, so a preempted phrase stops scheduling instead of finishing
    # into a pal that has moved on.
    still_current: Callable[[], bool] = lambda: True
    # Raise a catalogue prop for a scenario that has earned one.
    scenario_prop: Callable[[str], None] = lambda _name: None


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
    choice. Otherwise, if the step asks to wait for its action, look up how long
    that action really runs rather than trusting a hand-guessed number — the
    guess is what let the next step cut into a running one.

    This waits for the action's *expected* duration; nothing reports actual
    completion yet. The manifest key is named accordingly.
    """
    if step.duration_ms:
        return step.duration_ms
    if step.wait_action_duration and step.action:
        real = max(0, int(callbacks.duration_of(step.action)))
        if real:
            return max(0, real - max(0, step.overlap_ms))
    return 0

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

        steps = list(definition.sequence)
        after_ids: list[str] = []
        # a rough total for the debug panel; the chain does not depend on it
        elapsed = sum(
            (step.pause_ms or _step_advance(step, True, callbacks)) for step in steps
        )

        def fire(step) -> bool:
            """Apply one step's channel writes. True if it started anything."""
            scheduled = False
            if step.action:
                callbacks.action(step.action)
                scheduled = True
            if step.eyes:
                callbacks.eyes(step.eyes)
                scheduled = True
            if step.brows:
                callbacks.brows(step.brows)
                scheduled = True
            if step.bubble == "speak":
                callbacks.bubble(reaction)
                scheduled = True
            if step.scenario_prop:
                callbacks.scenario_prop(step.scenario_prop)
                scheduled = True
            if step.reset == "expression":
                callbacks.reset_expression()
                scheduled = True
            return scheduled

        def run_from(index: int) -> None:
            if not callbacks.still_current():
                return
            cursor = index
            while cursor < len(steps):
                step = steps[cursor]
                if step.pause_ms:
                    after_ids.append(
                        callbacks.after(step.pause_ms, lambda i=cursor + 1: run_from(i))
                    )
                    return
                scheduled = fire(step)
                delay = _step_advance(step, scheduled, callbacks)
                if delay > 0:
                    after_ids.append(
                        callbacks.after(delay, lambda i=cursor + 1: run_from(i))
                    )
                    return
                cursor += 1

        # the first step runs on the next tick, so the caller can register the
        # run and claim channels before anything writes to them
        after_ids.append(callbacks.after(0, lambda: run_from(0)))

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
