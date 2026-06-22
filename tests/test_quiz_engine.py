from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from python_pal.quiz import (
    QuizSession,
    QuizStore,
    choose_result,
    current_question,
    load_quiz_packets,
    record_answer,
    score_packet,
)
from python_pal.quiz_safety import validate_quiz_packet


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class QuizEngineTests(unittest.TestCase):
    def test_fallback_quiz_loads_and_validates(self) -> None:
        packets = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")
        self.assertGreaterEqual(len(packets), 1)
        self.assertEqual(validate_quiz_packet(packets[0]), [])

    def test_session_records_answers_and_scores(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        session = QuizSession.start(packet)
        first_question = current_question(packet, session)
        self.assertIsNotNone(first_question)

        while session.state != "completed":
            question = current_question(packet, session)
            self.assertIsNotNone(question)
            session = record_answer(packet, session, question.options[0].id)

        scores = score_packet(packet, session.answers)
        self.assertEqual(len(session.answers), len(packet.questions))
        self.assertGreater(scores["scheduler"], 0)
        self.assertEqual(choose_result(packet, scores).metric, "scheduler")

    def test_store_round_trips_packet_and_paused_session(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            store = QuizStore(Path(temp_dir) / "quiz_store.json")
            store.upsert_packet(packet)
            loaded = store.next_packet("zh-CN")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.id, packet.id)

            session = QuizSession.start(packet)
            session.state = "paused"
            store.save_session(session)
            restored = store.active_session()
            self.assertIsNotNone(restored)
            self.assertEqual(restored.state, "paused")
            self.assertEqual(restored.packet_id, packet.id)


if __name__ == "__main__":
    unittest.main()
