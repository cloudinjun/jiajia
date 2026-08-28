"""The bubble hugs its text; nothing else is allowed to live inside it.

The complaint that motivated this: bubbles showing a third of dead width on the
right, with the previous thought bubble's three trail dots blinking in the
corner. The current layout shrink-wraps per page, so the dead-width symptom
cannot come from this code — but nothing asserted that, so nothing would notice
a regression either. Now the invariant is pinned: for any text, the bubble page
is at most a small fixed slack wider than its widest wrapped line, and wide
enough that Tk's own wrapping never re-wraps our lines (a second wrap is how
text ends up narrower than its bubble).

These tests need a Tk instance for font metrics; they skip cleanly where no
display is available.
"""
from __future__ import annotations

import unittest

try:  # pragma: no cover - environment probe
    import tkinter as tk
    import tkinter.font as tkfont

    _ROOT = tk.Tk()
    _ROOT.withdraw()
    _TK_OK = True
except Exception:
    _TK_OK = False

from jiajia.body import (
    BUBBLE_FONT,
    BUBBLE_PADDING_X,
    BUBBLE_WIDTH,
    THOUGHT_FONT,
    _bubble_page_width,
    _paginate_bubble_text,
)

SAMPLE_LINES = (
    "I have opinions. They're structural.",
    "Empty document. Full of potential. Zero of action.",
    "The graphics card is trying very hard. Hard enough that I'm considering a call.",
    "好，我折起来 30 分钟。",
    "你专注挺久了。我先把嘴折起来一点。",
    "Still here. Still folded.",
    "The cursor has been in that same spot for a while. Very decisive. "
    "Three windows open. One of them might even be the task.",
)

# _bubble_page_width grants widest + 12; anything past that is dead width.
MAX_SLACK_PX = 14


def _font_for(spec: tuple) -> tkfont.Font:
    slant = spec[2] if len(spec) > 2 else "roman"
    return tkfont.Font(family=spec[0], size=spec[1], slant=slant)


@unittest.skipUnless(_TK_OK, "no display for Tk font metrics")
class BubbleTightnessTests(unittest.TestCase):
    def test_every_page_hugs_its_widest_line(self) -> None:
        """Dead width to the right of the text is the bug being pinned."""
        for spec in (BUBBLE_FONT, THOUGHT_FONT):
            font = _font_for(spec)
            wrap_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
            for text in SAMPLE_LINES:
                for page in _paginate_bubble_text(text, wrap_width, font):
                    widest = max(
                        (font.measure(line) for line in page.splitlines() if line),
                        default=0,
                    )
                    text_area = _bubble_page_width(page, font) - BUBBLE_PADDING_X * 2
                    self.assertLessEqual(
                        text_area - widest, MAX_SLACK_PX,
                        f"{text[:30]!r}: {text_area - widest}px of dead width "
                        f"(area {text_area}, text {widest})",
                    )

    def test_tk_never_rewraps_our_lines(self) -> None:
        """create_text(width=...) wraps again; our lines must all fit inside it.

        A line wider than the text area gets a second, tighter wrap from Tk,
        which is exactly how rendered text ends up narrower than the bubble
        that was measured for it.
        """
        for spec in (BUBBLE_FONT, THOUGHT_FONT):
            font = _font_for(spec)
            wrap_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
            for text in SAMPLE_LINES:
                for page in _paginate_bubble_text(text, wrap_width, font):
                    text_area = _bubble_page_width(page, font) - BUBBLE_PADDING_X * 2
                    for line in page.splitlines():
                        self.assertLessEqual(
                            font.measure(line), text_area,
                            f"{line!r} overflows its text area and would re-wrap",
                        )

    def test_short_quips_stay_on_one_line(self) -> None:
        """The screenshot case: a ~250px quip must not break into a ragged pair."""
        font = _font_for(BUBBLE_FONT)
        wrap_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
        pages = _paginate_bubble_text("I have opinions. They're structural.", wrap_width, font)
        self.assertEqual(len(pages), 1)
        self.assertNotIn("\n", pages[0], "a one-breath quip wrapped raggedly")


class ThoughtDotHygieneTests(unittest.TestCase):
    """The trail dots are the only blinking three-element drawing in the app.

    Any copy of them surviving into a later bubble means the animator outlived
    its items; the animator must die on the first dead item rather than keep
    running.
    """

    def test_clear_bubble_stops_the_animator(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "jiajia" / "body.py").read_text(
            encoding="utf-8"
        )
        start = source.index("def _clear_bubble")
        nxt = source.find("\n    def ", start + 1)
        body = source[start:nxt if nxt != -1 else start + 2000]
        for needle in ("_thought_dot_after", "_thought_dot_items.clear()", "_thought_dot_base.clear()"):
            self.assertIn(needle, body, f"_clear_bubble no longer resets {needle}")

    def test_animator_dies_on_a_dead_item(self) -> None:
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "jiajia" / "body.py").read_text(
            encoding="utf-8"
        )
        start = source.index("def _animate_thought_dots")
        body = source[start:source.index("\n    def ", start + 1)]
        self.assertIn(
            "except tk.TclError", body,
            "a stale animator must stop, not keep blinking in the next bubble's corner",
        )


if __name__ == "__main__":
    unittest.main()
