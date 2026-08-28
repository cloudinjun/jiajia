"""Hearing: loudness only, streaks that survive song gaps, silence on failure.

The contract mirrors Ears' "low-risk ambient signals": the meter reads what the
machine PLAYS (one amplitude float from the default render endpoint), never the
microphone, never content. Everything that can fail — no device, headless CI,
non-Windows — must read as an honest "unavailable", never raise.
"""
from __future__ import annotations

import unittest

from jiajia.audio_ears import (
    AUDIBLE_PEAK,
    AUDIO_LINES,
    ENDED_MIN_SESSION_SECONDS,
    STARTED_SUSTAIN_SECONDS,
    LOUD_SUSTAIN_SECONDS,
    AudioEventDetector,
    announcement_allowed_for,
    audio_flavor,
    audio_line,
    LONG_SESSION_SECONDS,
    LONG_SILENCE_SECONDS,
    SESSION_GRACE_SECONDS,
    AudioContext,
    AudioEars,
    audio_tags,
    classify_peak,
)


class ClassificationTests(unittest.TestCase):
    def test_bands(self) -> None:
        self.assertEqual(classify_peak(0.0), "silent")
        self.assertEqual(classify_peak(AUDIBLE_PEAK), "quiet")
        self.assertEqual(classify_peak(0.2), "audible")
        self.assertEqual(classify_peak(0.9), "loud")

    def test_tags_are_keys_not_prose(self) -> None:
        tags = audio_tags("loud", LONG_SESSION_SECONDS, 0.0)
        self.assertEqual(tags, ["audio_playing", "audio_loud", "audio_long_session"])
        self.assertEqual(audio_tags("silent", 0.0, LONG_SILENCE_SECONDS), ["audio_quiet_room"])


class SessionStreakTests(unittest.TestCase):
    """Drive _fold with fake peaks and clocks; no COM involved."""

    def _ears(self) -> AudioEars:
        ears = AudioEars()
        ears._silence_started_at = None  # fresh world, no inherited silence
        return ears

    def test_a_song_gap_does_not_end_the_session(self) -> None:
        ears = self._ears()
        ears._fold(0.3, 1000.0)
        context = ears._fold(0.0, 1000.0 + SESSION_GRACE_SECONDS - 1)
        self.assertTrue(context.playing, "a between-songs gap ended the session")
        context = ears._fold(0.3, 1010.0)
        self.assertAlmostEqual(context.session_seconds, 10.0, places=1)

    def test_a_long_gap_does_end_it(self) -> None:
        ears = self._ears()
        ears._fold(0.3, 1000.0)
        context = ears._fold(0.0, 1000.0 + SESSION_GRACE_SECONDS + 5)
        self.assertFalse(context.playing)
        self.assertEqual(context.session_seconds, 0.0)

    def test_long_listening_earns_the_marathon_tag(self) -> None:
        ears = self._ears()
        ears._fold(0.3, 0.0)
        context = ears._fold(0.3, LONG_SESSION_SECONDS + 1)
        self.assertIn("audio_long_session", context.audio_tags)

    def test_a_long_quiet_room_is_noticed(self) -> None:
        ears = self._ears()
        ears._fold(0.0, 0.0)
        context = ears._fold(0.0, LONG_SILENCE_SECONDS + 1)
        self.assertIn("audio_quiet_room", context.audio_tags)
        self.assertFalse(context.playing)

    def test_unavailable_reads_as_unavailable_not_as_silence_theatre(self) -> None:
        ears = self._ears()
        context = ears._fold(None, 1000.0)
        self.assertFalse(context.available)
        self.assertEqual(context.audio_tags, [])

    def test_sample_never_raises_even_without_a_device(self) -> None:
        ears = AudioEars()
        ears._acquire = lambda: False  # type: ignore[method-assign]
        context = ears.sample()
        self.assertIsInstance(context, AudioContext)
        self.assertFalse(context.available)


class WorldIntegrationTests(unittest.TestCase):
    def test_audio_tags_reach_the_environment(self) -> None:
        """The decision layer reads environment_tags; hearing must land there."""
        from jiajia.claude_account_usage import ClaudeAccountUsageStatus
        from jiajia.claude_status import ClaudeOverview
        from jiajia.claude_usage import ClaudeUsageStatus
        from jiajia.codex_status import CodexStatus
        from jiajia.codex_usage import CodexUsageStatus
        from jiajia.ears import EarContext
        from jiajia.eyes import ScreenContext
        from jiajia.hardware_status import HardwareSnapshot
        from jiajia.openai_billing import OpenAIBillingStatus
        from jiajia.state import PalState
        from jiajia.world import MoodSnapshot, WorldState

        world = WorldState(
            user_activity=EarContext(),
            screen=ScreenContext(),
            codex=CodexStatus(),
            codex_usage=CodexUsageStatus(),
            claude=ClaudeOverview(sessions=(), event_id=""),
            claude_usage=ClaudeUsageStatus(),
            claude_account_usage=ClaudeAccountUsageStatus(),
            openai_billing=OpenAIBillingStatus(),
            hardware=HardwareSnapshot(),
            pal=PalState(),
            mood=MoodSnapshot(key="normal", energy=0.5, valence=0.1, frequency_multiplier=1.0),
            audio=AudioContext(
                available=True, playing=True, peak=0.3, level="audible",
                session_seconds=120.0, silence_seconds=0.0,
                audio_tags=["audio_playing"],
            ),
        )
        self.assertIn("audio_playing", world.environment_tags)
        context = world.as_context("test")
        self.assertEqual(context["audio_level"], "audible")
        self.assertTrue(context["audio_playing"])

    def test_a_default_world_still_builds_without_hearing(self) -> None:
        """audio defaults, so older constructors and tests keep working."""
        from jiajia.world import WorldState
        import dataclasses

        fields = {f.name: f for f in dataclasses.fields(WorldState)}
        self.assertIn("audio", fields)
        self.assertIsNotNone(fields["audio"].default_factory)



class EventDetectorTests(unittest.TestCase):
    """The announcer speaks once, late, and never during a call."""

    def _ctx(self, playing: bool, session: float = 0.0, level: str = "audible") -> AudioContext:
        return AudioContext(
            available=True, playing=playing, peak=0.3 if playing else 0.0,
            level=level if playing else "silent", session_seconds=session,
        )

    def test_a_notification_ding_is_not_music(self) -> None:
        detector = AudioEventDetector()
        self.assertIsNone(detector.observe(self._ctx(True, 3.0), 1000.0))
        self.assertIsNone(detector.observe(self._ctx(False, 0.0), 1006.0))

    def test_started_fires_once_after_the_sustain(self) -> None:
        detector = AudioEventDetector()
        base = 1000.0
        self.assertIsNone(detector.observe(self._ctx(True, 5.0), base))
        event = detector.observe(self._ctx(True, STARTED_SUSTAIN_SECONDS + 1), base + 16)
        self.assertEqual(event, "audio_started")
        self.assertIsNone(
            detector.observe(self._ctx(True, STARTED_SUSTAIN_SECONDS + 10), base + 25),
            "the same session must not be announced twice",
        )

    def test_a_new_session_inside_the_cooldown_stays_quiet(self) -> None:
        detector = AudioEventDetector()
        detector.observe(self._ctx(True, 30.0), 1000.0)  # announces
        detector.observe(self._ctx(False), 1100.0)
        self.assertIsNone(
            detector.observe(self._ctx(True, 30.0), 1200.0),
            "a second remark two minutes later is nagging, not company",
        )

    def test_loud_needs_sustain(self) -> None:
        detector = AudioEventDetector()
        detector._started_for = 940.0  # this session already announced
        self.assertIsNone(detector.observe(self._ctx(True, 60.0, "loud"), 1000.0))
        self.assertEqual(
            detector.observe(self._ctx(True, 72.0, "loud"), 1000.0 + LOUD_SUSTAIN_SECONDS + 1),
            "audio_loud",
        )

    def test_marathon_fires_at_the_threshold_once(self) -> None:
        detector = AudioEventDetector()
        detector._started_for = 1000.0 - LONG_SESSION_SECONDS - 5
        marker_now = 1000.0
        event = detector.observe(self._ctx(True, LONG_SESSION_SECONDS + 5), marker_now)
        self.assertEqual(event, "audio_marathon")
        self.assertIsNone(detector.observe(self._ctx(True, LONG_SESSION_SECONDS + 30), marker_now + 25))

    def test_only_a_real_session_earns_a_goodbye(self) -> None:
        detector = AudioEventDetector()
        detector.observe(self._ctx(True, 30.0), 1000.0)
        self.assertIsNone(
            detector.observe(self._ctx(False), 1030.0),
            "a 30s blip ending is not an event",
        )
        detector2 = AudioEventDetector()
        detector2.observe(self._ctx(True, ENDED_MIN_SESSION_SECONDS + 60), 1000.0)
        self.assertEqual(detector2.observe(self._ctx(False), 1010.0), "audio_ended")

    def test_calls_are_sacred(self) -> None:
        self.assertFalse(announcement_allowed_for("meeting_or_chat"))
        self.assertTrue(announcement_allowed_for("music"))
        self.assertTrue(announcement_allowed_for("unknown"))

    def test_flavor_is_a_guess_from_the_foreground(self) -> None:
        self.assertEqual(audio_flavor("music"), "music")
        self.assertEqual(audio_flavor("browser"), "video")
        self.assertEqual(audio_flavor("game"), "game")
        self.assertEqual(audio_flavor("editor"), "ambient")
        self.assertEqual(audio_flavor("unknown"), "ambient")


class AudioLineTests(unittest.TestCase):
    """User-facing text: full bilingual coverage, honest when unsure."""

    def test_every_pool_is_bilingual(self) -> None:
        import re

        cjk = re.compile(r"[一-鿿]")
        for (event, flavor), (zh_lines, en_lines) in AUDIO_LINES.items():
            self.assertTrue(zh_lines and en_lines, f"({event},{flavor}) empty pool")
            for line in zh_lines:
                self.assertTrue(cjk.search(line), f"zh ({event},{flavor}): {line!r}")
            for line in en_lines:
                self.assertFalse(cjk.search(line), f"en ({event},{flavor}) leaks: {line!r}")

    def test_every_event_has_an_ambient_fallback(self) -> None:
        events = {event for event, _flavor in AUDIO_LINES}
        for event in events:
            self.assertIn((event, "ambient"), AUDIO_LINES, f"{event} has no honest fallback")
            self.assertTrue(audio_line(event, "design", "zh-CN"), f"{event} fallback broken")

    def test_unknown_event_stays_silent(self) -> None:
        self.assertEqual(audio_line("audio_nonsense", "music"), "")


class AnnouncerWiringTests(unittest.TestCase):
    def test_the_poll_exists_and_minds_its_manners(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "jiajia" / "body.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("self._poll_audio)", source, "the audio poll is never scheduled")
        start = source.index("def _should_announce_audio")
        nxt = source.find("\n    def ", start + 1)
        gate = source[start:nxt if nxt != -1 else start + 1500]
        for manner in ("announcement_allowed_for", "_auto_reactions_paused", "ambient_enabled", "brain_busy"):
            self.assertIn(manner, gate, f"the announcer gate lost {manner}")

if __name__ == "__main__":
    unittest.main()
