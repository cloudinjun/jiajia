from __future__ import annotations

import unittest

from python_pal.chat import ChatMessage
from python_pal.chat_language import (
    LANGUAGE_EN,
    LANGUAGE_ZH,
    detect_reply_language,
    english_status_reaction,
)


class ChatLanguageTests(unittest.TestCase):
    def test_detects_plain_english_message(self) -> None:
        self.assertEqual(
            detect_reply_language("Hello, what are you doing?"),
            LANGUAGE_EN,
        )

    def test_detects_plain_chinese_message(self) -> None:
        self.assertEqual(
            detect_reply_language("你现在在做什么？"),
            LANGUAGE_ZH,
        )

    def test_explicit_english_mode_wins(self) -> None:
        self.assertEqual(
            detect_reply_language("请回答这个问题", {"language_mode": "en"}),
            LANGUAGE_EN,
        )

    def test_britclip_costume_implies_english(self) -> None:
        self.assertEqual(
            detect_reply_language("...", {"appearance": {"costume_id": "britclip"}}),
            LANGUAGE_EN,
        )

    def test_ambiguous_message_uses_recent_user_language(self) -> None:
        history = (ChatMessage("user", "That seems fine."),)
        self.assertEqual(
            detect_reply_language("...", history=history),
            LANGUAGE_EN,
        )

    def test_english_status_reaction_contains_no_chinese(self) -> None:
        reaction = english_status_reaction(
            "status_codex",
            {
                "codex": {
                    "status": "waiting_user",
                    "summary": "等待用户确认",
                    "stale": False,
                }
            },
        )
        self.assertIsNotNone(reaction)
        assert reaction is not None
        self.assertNotRegex(reaction.line, r"[\u3400-\u4dbf\u4e00-\u9fff]")
        self.assertIn("waiting", reaction.line.lower())


if __name__ == "__main__":
    unittest.main()
