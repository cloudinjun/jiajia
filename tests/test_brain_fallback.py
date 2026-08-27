"""The brain must degrade, never fail.

Ollama is optional. Every path through `react()` has to produce a usable
Reaction whether the model answers correctly, answers with garbage, times out,
or is not installed at all — because the character cannot freeze mid-session
just because a local server is down.

These are fault-injection tests: the network seam (`_post_json`) is replaced
with something that misbehaves in a specific way, and the assertion is always
the same shape — the pal still says something, and the action it picked is one
the renderer knows.

The failure modes here are the ones a local model actually produces: prose
instead of JSON, a `<think>` block, a truncated object, a hallucinated action
name, the wrong language. None of them are hypothetical.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path

from jiajia.animation_resolver import AnimationResolver
from jiajia.brain_ollama import OllamaBrain
from jiajia.soul import load_soul

REPO_ROOT = Path(__file__).resolve().parents[1]


def _chat(content: str) -> dict:
    """Shape a well-formed Ollama /api/chat envelope around arbitrary content."""
    return {"message": {"content": content}}


class BrainFaultInjectionTest(unittest.TestCase):
    """Every hostile response still yields a usable Reaction."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="jiajia-brain-")
        root = Path(self.tmp)
        (root / "jiajia").mkdir(parents=True, exist_ok=True)
        (root / "memory").mkdir(parents=True, exist_ok=True)
        # Real identity data, throwaway line bank: the brain must not write into
        # the developer's actual memory/ while tests run.
        shutil.copy(REPO_ROOT / "jiajia" / "identities.yaml", root / "jiajia" / "identities.yaml")
        shutil.copytree(REPO_ROOT / "jiajia" / "locales", root / "jiajia" / "locales")
        self.soul = load_soul(REPO_ROOT / "jiajia" / "soul.yaml")
        self.brain = OllamaBrain(self.soul, project_root=root)
        self.resolver = AnimationResolver()
        self.calls = 0

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _install(self, responder) -> None:
        def wrapped(path, payload, timeout):  # noqa: ANN001 - test seam
            self.calls += 1
            return responder(path, payload, timeout)

        self.brain._post_json = wrapped  # type: ignore[method-assign]

    def _assert_usable(self, reaction, label: str) -> None:
        self.assertIsNotNone(reaction, f"{label}: react() returned None")
        self.assertTrue(
            reaction.line.strip(),
            f"{label}: produced an empty line, so the bubble would render blank",
        )
        self.assertIn(
            reaction.action,
            self.resolver.actions,
            f"{label}: action {reaction.action!r} is not something the renderer knows",
        )
        self.assertIn(
            reaction.bubble,
            {"speech", "thought"},
            f"{label}: bubble kind {reaction.bubble!r} is not renderable",
        )

    # ------------------------------------------------------------- transport
    def test_connection_refused(self) -> None:
        """Ollama not running is the common case, not an error case."""
        def responder(path, payload, timeout):
            raise urllib.error.URLError("connection refused")

        self._install(responder)
        self._assert_usable(self.brain.react("idle"), "connection refused")

    def test_timeout(self) -> None:
        def responder(path, payload, timeout):
            raise TimeoutError("model took too long")

        self._install(responder)
        self._assert_usable(self.brain.react("idle"), "timeout")

    def test_os_error(self) -> None:
        def responder(path, payload, timeout):
            raise OSError("socket exploded")

        self._install(responder)
        self._assert_usable(self.brain.react("idle"), "OSError")

    # -------------------------------------------------------------- payloads
    def test_prose_instead_of_json(self) -> None:
        """A chatty model ignores the schema and just talks."""
        self._install(lambda *a: _chat("Sure! Here's a fun idea: blink twice."))
        self._assert_usable(self.brain.react("idle"), "prose")

    def test_truncated_json(self) -> None:
        self._install(lambda *a: _chat('{"line": "half a thou'))
        self._assert_usable(self.brain.react("idle"), "truncated JSON")

    def test_empty_content(self) -> None:
        self._install(lambda *a: _chat(""))
        self._assert_usable(self.brain.react("idle"), "empty content")

    def test_envelope_missing_message(self) -> None:
        self._install(lambda *a: {})
        self._assert_usable(self.brain.react("idle"), "missing message key")

    def test_think_block_only(self) -> None:
        """Reasoning models leak <think>; stripping it can leave nothing."""
        self._install(lambda *a: _chat("<think>I should probably blink</think>"))
        self._assert_usable(self.brain.react("idle"), "think block only")

    def test_json_with_wrong_types(self) -> None:
        self._install(lambda *a: _chat(json.dumps({
            "line": 42, "mood": None, "action": ["blink"], "bubble": 7,
        })))
        self._assert_usable(self.brain.react("idle"), "wrong types")

    def test_null_line(self) -> None:
        self._install(lambda *a: _chat(json.dumps({"line": None, "action": "blink"})))
        reaction = self.brain.react("idle")
        self._assert_usable(reaction, "null line")

    # ------------------------------------------------- hallucinated vocabulary
    def test_hallucinated_action_is_normalized(self) -> None:
        """An action name the model invented must not reach the renderer."""
        self._install(lambda *a: _chat(json.dumps({
            "line": "Watch this.", "action": "quantum_backflip", "bubble": "speech",
        })))
        self._assert_usable(self.brain.react("idle"), "hallucinated action")

    def test_known_alias_survives(self) -> None:
        """A documented persona alias should still produce a real action."""
        self._install(lambda *a: _chat(json.dumps({
            "line": "Right then.", "action": "gentleclippy_suit_up", "bubble": "speech",
        })))
        self._assert_usable(self.brain.react("idle"), "persona alias")

    def test_invented_bubble_kind(self) -> None:
        self._install(lambda *a: _chat(json.dumps({
            "line": "Hello.", "action": "blink", "bubble": "hologram",
        })))
        self._assert_usable(self.brain.react("idle"), "invented bubble kind")

    # ----------------------------------------------------------- offline mode
    def test_allow_live_false_never_touches_the_network(self) -> None:
        """Offline is a supported mode, so it must not even try to connect."""
        def responder(path, payload, timeout):
            raise AssertionError("react(allow_live=False) must not call the model")

        self._install(responder)
        reaction = self.brain.react("idle", allow_live=False)
        self._assert_usable(reaction, "allow_live=False")
        self.assertEqual(self.calls, 0, "the network seam was called despite allow_live=False")

    def test_reaction_records_which_path_it_took(self) -> None:
        """Every reaction is traceable in the event log, degraded or not."""
        self._install(lambda *a: _chat(""))
        reaction = self.brain.react("idle", allow_live=False)
        self.assertTrue(
            reaction.decision_reason.strip(),
            "a reaction with no decision_reason cannot be explained after the fact",
        )

    # -------------------------------------------------------- across events
    def test_every_event_degrades_cleanly(self) -> None:
        """No event may depend on the model being reachable."""
        def responder(path, payload, timeout):
            raise urllib.error.URLError("offline")

        self._install(responder)
        for event in ("idle", "poke", "bored", "ambient", "manual", "quiet_mode", "focus_mode"):
            with self.subTest(event=event):
                self._assert_usable(self.brain.react(event), f"event={event}")


class EnglishModeFaultTest(unittest.TestCase):
    """English mode must not leak Chinese even when the model misbehaves."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="jiajia-brain-en-")
        root = Path(self.tmp)
        (root / "jiajia").mkdir(parents=True, exist_ok=True)
        (root / "memory").mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO_ROOT / "jiajia" / "identities.yaml", root / "jiajia" / "identities.yaml")
        shutil.copytree(REPO_ROOT / "jiajia" / "locales", root / "jiajia" / "locales")
        soul = load_soul(REPO_ROOT / "jiajia" / "locales" / "en_soul.yaml")
        soul.language = "en"
        self.brain = OllamaBrain(soul, project_root=root)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_chinese_reply_in_english_mode_is_not_shown(self) -> None:
        """The model ignoring the language instruction is a known failure."""
        self.brain._post_json = lambda *a: _chat(json.dumps({  # type: ignore[method-assign]
            "line": "你今天效率很低。", "action": "blink", "bubble": "speech",
        }))
        reaction = self.brain.react("idle")
        self.assertTrue(reaction.line.strip(), "English mode produced an empty line")
        self.assertTrue(
            reaction.line.isascii(),
            f"Chinese leaked into English mode: {reaction.line!r}",
        )


if __name__ == "__main__":
    unittest.main()
