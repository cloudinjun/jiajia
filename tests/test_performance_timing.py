"""A phrase may cut an action short, but not so short that nothing reads.

Phrases were authored as a list of effects to switch on, each with a guessed
delay, and nothing checked those guesses against how long the actions really
run. Measured, 20 steps were getting under 45% of their action and the worst
got 5% — a 2.5s tail sway started and cut after 120ms. On screen that is a
twitch, not a beat, and no test or error reported it.

Face-only micro actions are exempt: they set an expression, which reads on the
first frame and then holds, so a 120ms beat is honest. Body, tail and
inner-wire actions have to travel, so they need a real share of their duration.
"""
from __future__ import annotations

import unittest

from jiajia.body import JiajiaApp
from jiajia.performance import (
    MIN_READABLE_FRACTION,
    PERFORMANCE_PHRASES,
    PRIMARY_PERFORMANCE_IDS,
)


class _DurationProbe:
    """Minimal stand-in so durations resolve without opening a window."""

    animation_resolver = type("R", (), {"resolve": staticmethod(
        lambda name: type("A", (), {"action": name, "performance": ""})()
    )})()


def real_duration_ms(action: str) -> int:
    """How long the action actually runs. 0 means face-only."""
    try:
        return int(JiajiaApp._animation_duration_ms(_DurationProbe(), action))
    except Exception:  # noqa: BLE001 - an unknown action is simply not a body action
        return 0


class PhraseTimingTests(unittest.TestCase):
    def test_no_body_beat_is_cut_below_the_readable_floor(self) -> None:
        offenders = []
        for name in PRIMARY_PERFORMANCE_IDS:
            phrase = PERFORMANCE_PHRASES[name]
            for action, given in (*phrase.pre_actions, *phrase.post_actions):
                real = real_duration_ms(action)
                if not real:
                    continue  # face-only, reads immediately
                if given < real * MIN_READABLE_FRACTION:
                    offenders.append(
                        f"{name}/{action}: {given}ms of {real}ms "
                        f"({given / real:.0%}, floor {MIN_READABLE_FRACTION:.0%})"
                    )
        self.assertFalse(offenders, "phrase beats cut below readability:\n  " + "\n  ".join(offenders))

    def test_no_phrase_restarts_the_same_action(self) -> None:
        """Restarting an action replays its entry rather than letting it settle.

        fake_sulk used to start `sulk` twice, which re-ran the rain cloud and
        the face narrative instead of holding the mood.
        """
        for name in PRIMARY_PERFORMANCE_IDS:
            phrase = PERFORMANCE_PHRASES[name]
            body = [
                action
                for action, _ms in (*phrase.pre_actions, *phrase.post_actions)
                if real_duration_ms(action)
            ]
            self.assertEqual(
                len(body), len(set(body)),
                f"{name} starts the same body action twice: {body}",
            )

    def test_every_primary_phrase_still_exists(self) -> None:
        for name in PRIMARY_PERFORMANCE_IDS:
            self.assertIn(name, PERFORMANCE_PHRASES)
            phrase = PERFORMANCE_PHRASES[name]
            self.assertTrue(
                phrase.pre_actions or phrase.post_actions,
                f"{name} was emptied rather than rewritten",
            )


class AwaitActionTests(unittest.TestCase):
    """The manifest player can now wait for an action instead of guessing."""

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

    def test_declared_duration_wins(self) -> None:
        """An explicit duration is a directorial choice and must be honoured."""
        from jiajia.animation_manifest import AnimationStep
        from jiajia.animation_player import _step_advance

        step = AnimationStep(action="smug_sway", duration_ms=360, await_action=True)
        self.assertEqual(_step_advance(step, True, self._callbacks({"smug_sway": 1090})), 360)

    def test_await_uses_the_real_duration(self) -> None:
        from jiajia.animation_manifest import AnimationStep
        from jiajia.animation_player import _step_advance

        step = AnimationStep(action="smug_sway", await_action=True)
        self.assertEqual(_step_advance(step, True, self._callbacks({"smug_sway": 1090})), 1090)

    def test_overlap_shortens_the_await(self) -> None:
        from jiajia.animation_manifest import AnimationStep
        from jiajia.animation_player import _step_advance

        step = AnimationStep(action="smug_sway", await_action=True, overlap_ms=200)
        self.assertEqual(_step_advance(step, True, self._callbacks({"smug_sway": 1090})), 890)

    def test_unknown_action_does_not_stall_the_phrase(self) -> None:
        from jiajia.animation_manifest import AnimationStep
        from jiajia.animation_player import _step_advance

        step = AnimationStep(action="not_an_action", await_action=True)
        self.assertEqual(_step_advance(step, True, self._callbacks({})), 0)


if __name__ == "__main__":
    unittest.main()
