"""The pal and its bubble rise together, and keep rising.

The bug being pinned: the pal's `-topmost` was set once at startup and never
again, while the bubble re-lifted itself on every show. Windows orders the
topmost band by most-recent insertion, so the bubble kept floating above other
windows while the pal sank behind them — the two halves of one character in
different layers of the desktop.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "jiajia"
BODY = (ROOT / "body.py").read_text(encoding="utf-8")
WINDOW = (ROOT / "pal_window.py").read_text(encoding="utf-8")


def method_body(source: str, name: str) -> str:
    start = source.index(f"def {name}")
    nxt = source.find("\n    def ", start + 1)
    return source[start:nxt if nxt != -1 else start + 4000]


class StackingTests(unittest.TestCase):
    def test_bubble_show_raises_the_pair_not_just_the_bubble(self) -> None:
        body = method_body(BODY, "_show_bubble_page")
        self.assertIn(
            "_assert_windows_on_top", body,
            "showing a bubble must raise the pal with it",
        )
        self.assertNotIn(
            "self.bubble_root.lift()", body,
            "a bubble-only lift is how the pal got left behind",
        )

    def test_topmost_is_reasserted_periodically(self) -> None:
        """topmost decays on Windows; a one-shot at startup is not a state."""
        body = method_body(BODY, "_animate(self)")
        self.assertIn("_assert_windows_on_top", body)

    def test_reassert_never_steals_focus(self) -> None:
        body = method_body(WINDOW, "_assert_windows_on_top")
        self.assertIn(
            "SWP_NOACTIVATE", body,
            "raising the pet must never take the user's keyboard focus",
        )

    def test_reassert_orders_pal_below_bubble(self) -> None:
        """Pal first, bubble second: the last insertion wins the band."""
        body = method_body(WINDOW, "_assert_windows_on_top")
        pal_at = body.index("self.root")
        bubble_at = body.index("self.bubble_root")
        self.assertLess(pal_at, bubble_at)

    def test_a_hidden_bubble_is_not_raised(self) -> None:
        """SetWindowPos on a withdrawn window must not flash it onto screen."""
        body = method_body(WINDOW, "_assert_windows_on_top")
        self.assertIn("withdrawn", body)

    def test_the_win32_path_has_a_tk_fallback(self) -> None:
        body = method_body(WINDOW, "_assert_windows_on_top")
        self.assertIn("SetWindowPos", body)
        self.assertIn('attributes("-topmost", True)', body)


if __name__ == "__main__":
    unittest.main()
