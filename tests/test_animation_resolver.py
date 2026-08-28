"""The resolver is the boundary between model output and the renderer.

Nothing past this point should ever see a name the renderer does not know, so
these are contract tests rather than unit tests: they assert properties that
must hold for every entry in the table, not the behavior of specific inputs.

The shadowing test exists because the behavior evaluation set found four alias
entries that could never fire — the name was also a real action, and the action
lookup runs first. Dead entries in a mapping table are worse than missing ones:
they read as intent that is not actually in effect.
"""
from __future__ import annotations

import unittest

from jiajia.animation_resolver import ANIMATION_ALIASES, AnimationResolver


class AliasTableTest(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = AnimationResolver()

    def test_no_alias_is_shadowed_by_a_real_action(self) -> None:
        """An alias whose key is already an action can never fire."""
        shadowed = sorted(name for name in ANIMATION_ALIASES if name in self.resolver.actions)
        self.assertFalse(
            shadowed,
            "these alias keys are also real actions, so the alias is unreachable "
            f"and should be deleted: {shadowed}",
        )

    def test_every_alias_lands_somewhere_real(self) -> None:
        """An alias pointing at a name nothing knows is a silent failure."""
        resolver = AnimationResolver()
        orphans = sorted(
            f"{source} -> {target}"
            for source, target in ANIMATION_ALIASES.items()
            if target not in resolver.actions
            and resolver.resolve(source).action not in resolver.actions
        )
        self.assertFalse(orphans, f"alias targets that resolve to nothing real: {orphans}")

    def test_no_alias_points_at_itself(self) -> None:
        loops = sorted(k for k, v in ANIMATION_ALIASES.items() if k == v)
        self.assertFalse(loops, f"self-referential aliases: {loops}")


class UnknownInputTest(unittest.TestCase):
    """Whatever the model emits, the renderer receives a name it knows."""

    HOSTILE = (
        "quantum_backflip",
        "do a little dance",
        '{"action": "blink"}',
        "眨眼睛",
        "blinkk",
        "ThinkingTilt",
        "scan(duration=3s)",
        "🤔",
        "../../etc/passwd",
        "42",
        "a" * 200,
        "",
        "   ",
    )

    def setUp(self) -> None:
        self.resolver = AnimationResolver()

    def test_unknown_names_never_reach_the_renderer(self) -> None:
        for raw in self.HOSTILE:
            with self.subTest(raw=raw[:40]):
                resolved = self.resolver.resolve(raw)
                self.assertTrue(
                    resolved.action in self.resolver.actions or resolved.kind == "performance",
                    f"{raw[:40]!r} resolved to {resolved.action!r}, which the renderer does not know",
                )

    def test_resolution_is_deterministic(self) -> None:
        for raw in self.HOSTILE:
            with self.subTest(raw=raw[:40]):
                first = self.resolver.resolve(raw)
                second = self.resolver.resolve(raw)
                self.assertEqual(first.action, second.action)
                self.assertEqual(first.kind, second.kind)

    def test_empty_input_leaves_the_character_alone(self) -> None:
        """Saying nothing must not be turned into a performance."""
        for blank in ("", "   ", "\t"):
            with self.subTest(blank=repr(blank)):
                self.assertEqual(self.resolver.resolve(blank).action, "idle")


if __name__ == "__main__":
    unittest.main()
