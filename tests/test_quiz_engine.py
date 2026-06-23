from __future__ import annotations

from pathlib import Path
import inspect
import tempfile
import unittest

from python_pal.body import PaperclipPalApp
from python_pal.quiz import (
    QuizSession,
    QuizStore,
    build_report,
    choose_result,
    current_question,
    format_report,
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

        while session.state != "completed_waiting_result":
            question = current_question(packet, session)
            self.assertIsNotNone(question)
            session = record_answer(packet, session, question.options[0].id)

        scores = score_packet(packet, session.answers)
        self.assertEqual(len(session.answers), len(packet.questions))
        self.assertGreater(scores["scheduler"], 0)
        self.assertEqual(choose_result(packet, scores).metric, "scheduler")

    def test_report_contains_percent_readings_and_badges(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        session = QuizSession.start(packet)
        while session.state != "completed_waiting_result":
            question = current_question(packet, session)
            self.assertIsNotNone(question)
            session = record_answer(packet, session, question.options[0].id)

        report = build_report(packet, score_packet(packet, session.answers))
        formatted = format_report(report)
        self.assertGreaterEqual(report.percent, 0)
        self.assertLessEqual(report.percent, 100)
        self.assertEqual(set(report.readings), set(packet.metrics))
        self.assertEqual(len(report.achievements), 3)
        self.assertIn("人类操作系统健康度", formatted)
        self.assertIn("六项读数", formatted)

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

    def test_completed_waiting_result_survives_store_round_trip(self) -> None:
        packet = load_quiz_packets(PROJECT_ROOT / "python_pal" / "quizzes.yaml")[0]
        with tempfile.TemporaryDirectory() as temp_dir:
            store = QuizStore(Path(temp_dir) / "quiz_store.json")
            store.upsert_packet(packet)
            session = QuizSession.start(packet)
            session.state = "completed_waiting_result"
            store.save_session(session)

            restored = store.active_session()
            self.assertIsNotNone(restored)
            self.assertEqual(restored.state, "completed_waiting_result")
            self.assertEqual(restored.packet_id, packet.id)

    def test_answer_handler_does_not_call_brain_or_ollama(self) -> None:
        source = inspect.getsource(PaperclipPalApp._handle_quiz_answer)
        blocked = ("brain", "ollama", "respond", "_ask_brain", "chat_brain")
        for term in blocked:
            self.assertNotIn(term, source.lower())


if __name__ == "__main__":
    unittest.main()
