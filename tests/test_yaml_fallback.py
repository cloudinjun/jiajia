"""The stdlib YAML fallback must agree with PyYAML on every file we ship.

Jiajia declares no runtime dependencies, so on a machine without PyYAML the
hand-rolled parser in soul.py is what reads the animation tables, the identity
tables and the roast lines. It had been silently disagreeing: flow collections
came back as the string "[a, b]", floats came back as strings, and any quoted
line containing a colon was split into a single-key map. Nothing crashed, so
nothing said so — the app simply behaved differently depending on whether an
unrelated package happened to be installed.

This compares the two parsers on the real files rather than on invented ones,
because the failure was always in a shape a data file actually uses.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from jiajia.soul import _load_simple_yaml

try:
    import yaml
except ImportError:  # pragma: no cover - the environment being tested for
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
SEARCH = ("jiajia", "eval")


def _without_pyyaml(text: str) -> Any:
    """What soul._load_yaml does when the yaml import fails.

    Several .yaml files here are actually JSON, which the real loader tries
    first; the comparison has to take the same route or it tests a path the
    app never uses.
    """
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return _load_simple_yaml(text)
    return loaded if isinstance(loaded, dict) else {}


def _yaml_files() -> list[Path]:
    found: list[Path] = []
    for folder in SEARCH:
        found.extend(sorted((ROOT / folder).rglob("*.yaml")))
    return found


@unittest.skipIf(yaml is None, "PyYAML is not installed, so there is nothing to compare against")
class YamlFallbackParityTest(unittest.TestCase):
    def test_there_are_files_to_check(self) -> None:
        self.assertGreater(len(_yaml_files()), 5, "the search paths found almost nothing")

    def test_fallback_matches_pyyaml_on_every_shipped_file(self) -> None:
        for path in _yaml_files():
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                expected = yaml.safe_load(text)
                if not isinstance(expected, dict):
                    continue
                self.assertEqual(_without_pyyaml(text), expected)


class ScalarShapeTest(unittest.TestCase):
    """The specific shapes that were wrong, kept as their own statement."""

    def test_flow_sequence(self) -> None:
        self.assertEqual(_load_simple_yaml("layers: [left_pupil, right_pupil]"),
                         {"layers": ["left_pupil", "right_pupil"]})

    def test_flow_mapping(self) -> None:
        self.assertEqual(_load_simple_yaml("context: {app_category: editor, idle_seconds: 0.5}"),
                         {"context": {"app_category": "editor", "idle_seconds": 0.5}})

    def test_nested_flow(self) -> None:
        self.assertEqual(_load_simple_yaml("a: {b: [1, 2], c: {d: e}}"),
                         {"a": {"b": [1, 2], "c": {"d": "e"}}})

    def test_float(self) -> None:
        self.assertEqual(_load_simple_yaml("intensity: 0.6"), {"intensity": 0.6})

    def test_words_that_float_would_swallow(self) -> None:
        for word in ("inf", "nan", "infinity", "1.2.3"):
            with self.subTest(word=word):
                self.assertEqual(_load_simple_yaml(f"v: {word}"), {"v": word})

    def test_quoted_line_containing_a_colon_stays_one_line(self) -> None:
        text = "lines:\n  - 'Preliminary cause of death: a very confident change.'\n"
        self.assertEqual(_load_simple_yaml(text),
                         {"lines": ["Preliminary cause of death: a very confident change."]})

    def test_a_real_key_is_still_a_key(self) -> None:
        self.assertEqual(_load_simple_yaml("mood: worried"), {"mood": "worried"})

    def test_key_with_no_value_is_none_not_empty_map(self) -> None:
        self.assertEqual(_load_simple_yaml("style:\n  - Core techniques:\n  - REFRAMING\n"),
                         {"style": [{"Core techniques": None}, "REFRAMING"]})
