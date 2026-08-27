"""Timing rules, checked against the choreography that actually runs.

The first version of this file imported the phrase table from performance.py
and passed while the real thing was broken. `_run_performance_phrase` asks the
manifest first and returns the moment it scheduled anything, so for every
primary phrase the performance.py table was unreachable. Re-timing it changed
nothing on screen, and a green suite said otherwise.

So these tests load jiajia/animations.yaml — the live source — and there is a
test below that fails if that stops being the live source.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from jiajia.action_timing import action_duration_ms
from jiajia.animation_manifest import load_animation_manifest
from jiajia.performance import MIN_READABLE_FRACTION, PERFORMANCE_PHRASES, PRIMARY_PERFORMANCE_IDS

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "jiajia" / "animations.yaml"
MANIFEST = load_animation_manifest(MANIFEST_PATH)


def step_budget_ms(step) -> int:
    """How long this step really gets before the next one starts."""
    if step.duration_ms:
        return step.duration_ms
    if step.wait_action_duration and step.action:
        return max(0, action_duration_ms(step.action) - max(0, step.overlap_ms))
    return 0


class ManifestTimingTests(unittest.TestCase):
    def test_no_body_beat_is_cut_below_the_readable_floor(self) -> None:
        offenders = []
        for name, definition in MANIFEST.performances.items():
            for step in definition.sequence:
                if not step.action:
                    continue
                real = action_duration_ms(step.action)
                if not real:
                    continue  # face-only: reads on the first frame
                if step.wait_action_duration and not step.duration_ms:
                    continue  # waiting for it by definition
                budget = step_budget_ms(step)
                if budget < real * MIN_READABLE_FRACTION:
                    offenders.append(
                        f"{name}/{step.action}: {budget}ms of {real}ms "
                        f"({budget / real:.0%}, floor {MIN_READABLE_FRACTION:.0%})"
                    )
        self.assertFalse(offenders, "beats cut below readability:\n  " + "\n  ".join(offenders))

    def test_no_phrase_starts_the_same_body_action_twice(self) -> None:
        """Restarting replays the entry instead of letting the mood settle."""
        for name, definition in MANIFEST.performances.items():
            body = [
                step.action
                for step in definition.sequence
                if step.action and action_duration_ms(step.action)
            ]
            self.assertEqual(
                len(body), len(set(body)), f"{name} starts the same body action twice: {body}",
            )

    def test_awaiting_steps_do_not_also_declare_a_duration(self) -> None:
        """duration_ms wins over wait_action_duration, so both together is a silent no-op."""
        for name, definition in MANIFEST.performances.items():
            for step in definition.sequence:
                if step.wait_action_duration and step.duration_ms:
                    self.fail(
                        f"{name}/{step.action}: wait_action_duration is ignored because "
                        f"duration_ms={step.duration_ms} takes precedence"
                    )

    def test_overlap_never_outlasts_the_action(self) -> None:
        for name, definition in MANIFEST.performances.items():
            for step in definition.sequence:
                if not (step.wait_action_duration and step.overlap_ms):
                    continue
                real = action_duration_ms(step.action)
                self.assertLess(
                    step.overlap_ms, real,
                    f"{name}/{step.action}: {step.overlap_ms}ms overlap on a {real}ms action "
                    "would skip it entirely",
                )


class SingleSourceTests(unittest.TestCase):
    """Guard the mistake that made the first version of this file useless."""

    def test_the_manifest_defines_every_primary_phrase(self) -> None:
        """If it does, the manifest is the path that runs and this file is aimed right."""
        for name in PRIMARY_PERFORMANCE_IDS:
            self.assertIn(
                name, MANIFEST.performances,
                f"{name} is missing from the manifest, so it would silently fall back "
                "to a table these tests do not check",
            )

    def test_the_fallback_table_is_derived_not_authored(self) -> None:
        """Two hand-written choreographies drift; one of them then goes unseen."""
        for name in PRIMARY_PERFORMANCE_IDS:
            definition = MANIFEST.performances[name]
            manifest_actions = [s.action for s in definition.sequence if s.action]
            phrase = PERFORMANCE_PHRASES[name]
            fallback_actions = [a for a, _ms in (*phrase.pre_actions, *phrase.post_actions)]
            self.assertEqual(
                fallback_actions, manifest_actions,
                f"{name}: the fallback table has drifted from the manifest",
            )

    def test_runtime_prefers_the_manifest(self) -> None:
        """The ordering that makes the manifest authoritative, asserted in source.

        _run_performance_phrase plays the manifest and returns early on success;
        only then does PERFORMANCE_PHRASES get a look in. If that order flips,
        these tests are checking the wrong data again.
        """
        source = (Path(__file__).resolve().parents[1] / "jiajia" / "body.py").read_text(
            encoding="utf-8"
        )
        start = source.index("def _run_performance_phrase")
        # to the next method at the same indent, so the window cannot go stale
        nxt = source.find("\n    def ", start + 1)
        body = source[start:nxt if nxt != -1 else len(source)]
        play_at = body.index("self.animation_player.play(")
        fallback_at = body.index("PERFORMANCE_PHRASES.get(")
        self.assertLess(
            play_at, fallback_at,
            "the fallback table is consulted before the manifest; the audited "
            "source is no longer the source that runs",
        )


class StepAdvanceTests(unittest.TestCase):
    """The rule the manifest timings depend on."""

    def _callbacks(self, durations: dict[str, int]):
        from jiajia.animation_player import AnimationCallbacks

        return AnimationCallbacks(
            after=lambda _ms, _cb: "",
            action=lambda _a: None,
            bubble=lambda _r: None,
            eyes=lambda _e: None,
            brows=lambda _b: None,
            reset_expression=lambda: None,
            stop_cursor_follow=lambda: None,
            duration_of=lambda a: durations.get(a, 0),
        )

    def _advance(self, step, durations):
        from jiajia.animation_player import _step_advance

        return _step_advance(step, True, self._callbacks(durations))

    def test_declared_duration_wins(self) -> None:
        from jiajia.animation_manifest import AnimationStep

        step = AnimationStep(action="smug_sway", duration_ms=360, wait_action_duration=True)
        self.assertEqual(self._advance(step, {"smug_sway": 1090}), 360)

    def test_await_uses_the_real_duration(self) -> None:
        from jiajia.animation_manifest import AnimationStep

        step = AnimationStep(action="smug_sway", wait_action_duration=True)
        self.assertEqual(self._advance(step, {"smug_sway": 1090}), 1090)

    def test_overlap_shortens_the_await(self) -> None:
        from jiajia.animation_manifest import AnimationStep

        step = AnimationStep(action="smug_sway", wait_action_duration=True, overlap_ms=200)
        self.assertEqual(self._advance(step, {"smug_sway": 1090}), 890)

    def test_unknown_action_does_not_stall_the_phrase(self) -> None:
        from jiajia.animation_manifest import AnimationStep

        step = AnimationStep(action="not_an_action", wait_action_duration=True)
        self.assertEqual(self._advance(step, {}), 0)


if __name__ == "__main__":
    unittest.main()
