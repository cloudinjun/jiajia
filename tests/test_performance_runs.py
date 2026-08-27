"""Channel ownership: who is allowed to write to the pal right now.

Before this, cancellation was "whoever writes next wins". A finished
performance's delayed callback could still reset the expression, clear the prop
or zero the tail of the performance that had replaced it, and cancelling a
phrase tore down channels without checking whether a newer phrase had taken
them over. Neither raised anything; both just looked like the pal glitching.
"""
from __future__ import annotations

import unittest

from jiajia.performance_run import CHANNELS, RunRegistry


class ChannelOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = RunRegistry()

    def test_a_run_owns_what_it_claims(self) -> None:
        run = self.registry.begin("smug_but_caught")
        self.registry.claim(run, "body", "face")
        self.assertTrue(self.registry.owns(run, "body"))
        self.assertTrue(self.registry.owns(run, "face"))
        self.assertFalse(self.registry.owns(run, "tail"))

    def test_a_later_run_takes_the_channel_over(self) -> None:
        first = self.registry.begin("fake_sulk")
        self.registry.claim(first, "body", "tail")
        second = self.registry.begin("tiny_celebrate")
        self.registry.claim(second, "body")

        self.assertFalse(
            self.registry.owns(first, "body"),
            "the superseded run must not keep writing to the body",
        )
        self.assertTrue(self.registry.owns(second, "body"))

    def test_cancelling_returns_only_channels_still_held(self) -> None:
        """Tearing down a channel a newer run took over is the bug, not the fix."""
        first = self.registry.begin("fake_sulk")
        self.registry.claim(first, "body", "tail", "prop")
        second = self.registry.begin("tiny_celebrate")
        self.registry.claim(second, "body")

        released = self.registry.cancel(first)
        self.assertEqual(released, {"tail", "prop"})
        self.assertNotIn("body", released, "would have torn down the new run's body")
        self.assertTrue(self.registry.owns(second, "body"))

    def test_a_cancelled_run_can_no_longer_write(self) -> None:
        run = self.registry.begin("grand_dame_whisper_roast")
        self.registry.claim(run, "face")
        self.registry.cancel(run)
        self.assertFalse(self.registry.owns(run, "face"))
        self.assertFalse(self.registry.is_current(run))

    def test_unowned_work_is_not_gated(self) -> None:
        """Idle and ambient motion has no run, and must not be blocked."""
        self.assertTrue(self.registry.owns(None, "body"))
        self.assertTrue(self.registry.is_current(None))
        self.assertEqual(self.registry.cancel(None), set())

    def test_unknown_channels_are_ignored_not_owned(self) -> None:
        run = self.registry.begin("x")
        self.registry.claim(run, "costume")
        self.assertNotIn("costume", run.owned)
        self.assertEqual(self.registry.cancel(run), set())

    def test_persistent_layers_are_not_performance_channels(self) -> None:
        """A finishing phrase must not be able to strip the pal's costume."""
        for name in ("costume", "identity", "identity_decoration", "status_badge"):
            self.assertNotIn(name, CHANNELS)

    def test_run_ids_are_unique(self) -> None:
        ids = {self.registry.begin(f"p{i}").run_id for i in range(5)}
        self.assertEqual(len(ids), 5)

    def test_cancel_current_targets_the_live_run(self) -> None:
        first = self.registry.begin("a")
        self.registry.claim(first, "body")
        second = self.registry.begin("b")
        self.registry.claim(second, "tail")
        self.assertEqual(self.registry.cancel_current(), {"tail"})
        self.assertIsNone(self.registry.current)


class PlayerChainTests(unittest.TestCase):
    """The phrase advances step by step, so a dead run stops scheduling."""

    def _player(self):
        from pathlib import Path

        from jiajia.animation_manifest import load_animation_manifest
        from jiajia.animation_player import AnimationPlayer

        path = Path(__file__).resolve().parents[1] / "jiajia" / "animations.yaml"
        return AnimationPlayer(load_animation_manifest(path))

    def _callbacks(self, log, alive, clock):
        from jiajia.animation_player import AnimationCallbacks
        from jiajia.action_timing import action_duration_ms

        def after(delay, callback):
            clock.append((delay, callback))
            return f"after{len(clock)}"

        return AnimationCallbacks(
            after=after,
            action=lambda a: log.append(a),
            bubble=lambda _r: log.append("<line>"),
            eyes=lambda _e: None,
            brows=lambda _b: None,
            reset_expression=lambda: None,
            stop_cursor_follow=lambda: None,
            duration_of=action_duration_ms,
            still_current=lambda: alive[0],
        )

    def test_a_cancelled_run_stops_mid_phrase(self) -> None:
        from jiajia.state import Reaction

        log: list[str] = []
        alive = [True]
        clock: list[tuple[int, object]] = []
        player = self._player()
        player.play(
            "thought_roast_smug", Reaction(True, "line"), self._callbacks(log, alive, clock)
        )

        # drain a few scheduled steps
        for _ in range(3):
            if not clock:
                break
            _delay, callback = clock.pop(0)
            callback()
        started = len(log)
        self.assertGreater(started, 0, "the phrase never started")

        alive[0] = False
        while clock:
            _delay, callback = clock.pop(0)
            callback()
        self.assertEqual(
            len(log), started,
            "a preempted phrase kept performing after it was superseded",
        )

    def test_the_whole_phrase_is_not_queued_up_front(self) -> None:
        """Queuing everything at once is what made cancellation unreliable."""
        from jiajia.state import Reaction

        log: list[str] = []
        clock: list[tuple[int, object]] = []
        player = self._player()
        player.play(
            "grand_dame_whisper_roast", Reaction(True, "line"),
            self._callbacks(log, [True], clock),
        )
        self.assertEqual(
            len(clock), 1,
            "play() scheduled the phrase up front instead of chaining step by step",
        )


if __name__ == "__main__":
    unittest.main()
