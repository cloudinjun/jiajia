"""The right-click menu is entirely in the pal's language.

MENU_LABELS used to cover five entries; the other ~30 chrome labels and all 78
action names were hardcoded English, so the Chinese menu was mostly English.
The rules now: every label flows through a bilingual table, every Chinese label
contains Chinese, every English label contains none. The exemptions are values,
not labels: each language's own name in the language picker, and performance
ids in the developer preview, which are debug identifiers.
"""
from __future__ import annotations

import re
import unittest
from typing import ClassVar
from pathlib import Path

from jiajia.actions import (
    ACTION_LABELS,
    ACTION_LABELS_ZH,
    ACTION_MENU_GROUPS,
    MENU_GROUP_LABELS_ZH,
    action_label,
    menu_group_label,
)
from jiajia.language import MENU_LABELS, menu_label

CJK = re.compile(r"[一-鿿]")
ROOT = Path(__file__).resolve().parents[1] / "jiajia"

try:  # pragma: no cover - environment probe
    import tkinter as tk

    _probe_root = tk.Tk()
    _probe_root.destroy()
    _TK_OK = True
except Exception:
    _TK_OK = False


class LabelTableTests(unittest.TestCase):
    def test_chrome_tables_cover_the_same_keys(self) -> None:
        self.assertEqual(set(MENU_LABELS["zh-CN"]), set(MENU_LABELS["en"]))

    def test_chrome_labels_match_their_language(self) -> None:
        for key in MENU_LABELS["zh-CN"]:
            zh = menu_label(key, "zh-CN")
            en = menu_label(key, "en")
            self.assertTrue(CJK.search(zh), f"zh chrome {key}={zh!r} has no Chinese")
            self.assertFalse(CJK.search(en), f"en chrome {key}={en!r} leaks Chinese")

    def test_every_action_has_labels_in_both_languages(self) -> None:
        self.assertEqual(set(ACTION_LABELS_ZH), set(ACTION_LABELS))
        for action in ACTION_LABELS:
            zh = action_label(action, "zh-CN")
            en = action_label(action, "en")
            self.assertTrue(CJK.search(zh), f"zh action {action}={zh!r} has no Chinese")
            self.assertFalse(CJK.search(en), f"en action {action}={en!r} leaks Chinese")

    def test_every_menu_group_has_a_chinese_name(self) -> None:
        for group, _ids in ACTION_MENU_GROUPS:
            self.assertIn(group, MENU_GROUP_LABELS_ZH, f"group {group} untranslated")
            self.assertTrue(CJK.search(menu_group_label(group, "zh-CN")))
            self.assertFalse(CJK.search(menu_group_label(group, "en")))


class MenuSourceTests(unittest.TestCase):
    def test_no_hardcoded_labels_in_the_menu_builder(self) -> None:
        """A literal label is a label only one language can ever see."""
        source = (ROOT / "body.py").read_text(encoding="utf-8")
        start = source.index("def _install_menu")
        body = source[start:source.index("\n    def ", start + 1)]
        hardcoded = re.findall(r'label="([^"]+)"', body)
        self.assertEqual(
            hardcoded, [],
            f"_install_menu hardcodes labels {hardcoded}; route them through menu_label",
        )


@unittest.skipUnless(_TK_OK, "no display for Tk menus")
class BuiltMenuTests(unittest.TestCase):
    """Build the real menu headless in both languages and read every label."""

    def _harvest(self, menu) -> list[str]:
        labels: list[str] = []
        end = menu.index("end")
        if end is None:
            return labels
        for i in range(end + 1):
            if menu.type(i) in ("command", "cascade", "radiobutton", "checkbutton"):
                labels.append(menu.entrycget(i, "label"))
                if menu.type(i) == "cascade":
                    child = menu.nametowidget(menu.entrycget(i, "menu"))
                    labels.extend(self._harvest(child))
        return labels

    def _build(self, root, language: str) -> list[str]:
        from jiajia.body import JiajiaApp

        outer = self

        class Probe:
            def __init__(self) -> None:
                class Soul:
                    pass

                self.soul = Soul()
                self.soul.language = language
                self.root = root
                self._identity_var = tk.StringVar(value="auto")
                self._language_var = tk.StringVar(value=language)
                self._freq_var = tk.StringVar(value="normal")
                self._tail_mode_var = tk.StringVar(value="short")
                self._focus_var = tk.BooleanVar(value=False)

                class Packs:
                    def menu_packs(self):
                        return []

                class Brain:
                    identities = Packs()

                class Manifest:
                    performances: ClassVar[dict] = {}

                class Player:
                    manifest = Manifest()

                self.brain = Brain()
                self.animation_player = Player()

            def __getattr__(self, name):
                return lambda *args, **kwargs: None

        probe = Probe()
        JiajiaApp._install_menu(probe)
        return outer._harvest(probe.menu)

    def test_chinese_menu_is_entirely_chinese(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            labels = self._build(root, "zh-CN")
            # each language's own name in the picker is a value, not a label
            leftovers = [lab for lab in labels if not CJK.search(lab) and lab != "English"]
            self.assertGreater(len(labels), 100, "menu did not fully build")
            self.assertEqual(leftovers, [], f"english left in the Chinese menu: {leftovers}")
        finally:
            root.destroy()

    def test_english_menu_is_entirely_english(self) -> None:
        root = tk.Tk()
        root.withdraw()
        try:
            labels = self._build(root, "en")
            leaks = [lab for lab in labels if CJK.search(lab) and lab != "中文"]
            self.assertGreater(len(labels), 100, "menu did not fully build")
            self.assertEqual(leaks, [], f"chinese left in the English menu: {leaks}")
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
