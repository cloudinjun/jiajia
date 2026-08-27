from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from python_pal.quiz import load_quiz_packets
from python_pal.quiz_safety import validate_quiz_packet


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QuizSafetyTests(unittest.TestCase):
    def test_rejects_non_entertainment_label(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        bad = replace(packet, safety_label="assessment")
        self.assertIn("safety_label must be entertainment_only", validate_quiz_packet(bad))

    def test_rejects_forbidden_assessment_terms(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        bad = replace(packet, title="你的焦虑诊断是什么")
        errors = validate_quiz_packet(bad)
        self.assertTrue(any("forbidden" in error for error in errors))

    def test_rejects_wrong_option_count(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        question = replace(packet.questions[0], options=packet.questions[0].options[:3])
        bad = replace(packet, questions=[question, *packet.questions[1:]])
        errors = validate_quiz_packet(bad)
        self.assertTrue(any("exactly 4 options" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
