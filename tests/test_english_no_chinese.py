"""English mode must not leak Chinese into anything the user reads.

The pal builds its spoken lines in many places (status monitors, seed banks,
prompts, reaction builders). Each one is a separate chance to forget the
language branch, and a leak is invisible until an English user sees a Chinese
bubble. This sweep calls the text producers directly in English mode and fails
on any CJK character, so a missed branch shows up as a test failure with the
offending string rather than as a surprise on screen.
"""
from __future__ import annotations

import re
import unittest
from dataclasses import replace
from pathlib import Path

from jiajia import claude_account_usage, claude_usage, codex_usage, openai_billing
from jiajia.actions import action_descriptions, action_prompt
from jiajia.activity import POLICIES, policy_for_frequency
from jiajia.chat_language import status_reaction
from jiajia.claude_status import ACTIVITY_ZH, activity_label
from jiajia.event_log import EventRecord, summarize_events
from jiajia.identity import load_identity_manifest
from jiajia.language import identities_path_for_language, soul_path_for_language
from jiajia.line_bank import _seed_entries
from jiajia.mood import FREQUENCY_PRESETS, frequency_label, normalize_frequency
from jiajia.pal_panels import _QUIZ_COPY
from jiajia.performance import performance_prompt
from jiajia.quiz import build_report, format_report, load_quiz_packets
from jiajia.soul import load_soul

CJK = re.compile(r"[㐀-䶿一-鿿　-〿！-～]")
PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "jiajia"


def cjk_in(text: str) -> str:
    """The offending characters, so a failure says what leaked."""
    return "".join(sorted(set(CJK.findall(text or ""))))


class EnglishModeTests(unittest.TestCase):
    def assertNoChinese(self, text: str, where: str) -> None:
        leaked = cjk_in(text)
        self.assertEqual(leaked, "", f"{where} leaked {leaked!r} in: {text!r}")

    def test_codex_usage_summaries(self) -> None:
        cases = [(38.0, 5400.0, False), (4.0, 0.0, False), (None, None, True), (None, None, False)]
        for remaining, reset_in, stale in cases:
            line = codex_usage._summary_line(remaining, reset_in, stale, "en")
            self.assertNoChinese(line, f"codex_usage {remaining}/{reset_in}/{stale}")

    def test_claude_account_usage_summaries(self) -> None:
        cases = [(90.0, 60.0, False), (9.0, 7200.0, False), (None, None, True), (None, None, False)]
        for remaining, reset_in, stale in cases:
            line = claude_account_usage._summary_line(remaining, reset_in, stale, "en")
            self.assertNoChinese(line, f"claude_account_usage {remaining}/{reset_in}/{stale}")

    def test_reset_duration_labels(self) -> None:
        for module in (codex_usage, claude_account_usage):
            for seconds in (0.0, 45.0, 3600.0, 5400.0, 86400.0):
                label = module.format_reset_in(seconds, "en")
                self.assertNoChinese(label, f"{module.__name__}.format_reset_in({seconds})")

    def test_claude_usage_summary_from_live_logs(self) -> None:
        monitor = claude_usage.ClaudeUsageMonitor()
        monitor.language = "en"
        self.assertNoChinese(monitor.sample().summary_line, "claude_usage.sample")
        self.assertNoChinese(claude_usage._empty_log_line("en"), "claude_usage empty log")

    def test_openai_billing_summaries(self) -> None:
        cases = [
            # (month_cost, budget, remaining, snapshot, snapshot_at, since, est, level, kind)
            (12.4, 20.0, 7.6, None, "", None, None, "normal", ""),
            (31.0, 20.0, -11.0, None, "", None, None, "over_budget", ""),
            (4.2, None, None, 50.0, "2026-06-01", 4.2, 45.8, "normal", ""),
            (4.2, None, None, 50.0, "2026-06-01", 60.0, -10.0, "normal", ""),
            (4.2, None, None, 50.0, "", None, None, "normal", ""),
            (4.2, None, None, 50.0, "2026-06-01", None, None, "normal", ""),
            (4.2, None, None, None, "", None, None, "normal", ""),
            (None, None, None, None, "", None, None, "unavailable", "key_missing"),
            (None, None, None, None, "", None, None, "unavailable", "missing_usage_scope"),
            (None, None, None, None, "", None, None, "unavailable", "network_or_parse_error"),
        ]
        for cost, budget, remaining, snap, snap_at, since, est, level, kind in cases:
            line = openai_billing._summary_line(
                cost, budget, remaining, snap, snap_at, since, est, "usd", level, kind, "", "en"
            )
            self.assertNoChinese(line, f"openai_billing {level}/{kind}")

    def test_frequency_labels(self) -> None:
        for key, _mult in FREQUENCY_PRESETS:
            self.assertNoChinese(frequency_label(key, "en"), f"frequency_label({key})")

    def test_prompts_sent_to_the_model(self) -> None:
        self.assertNoChinese(action_prompt("en"), "action_prompt")
        self.assertNoChinese(performance_prompt("en"), "performance_prompt")
        for action, description in action_descriptions("en").items():
            self.assertNoChinese(description, f"action_descriptions[{action}]")

    def test_english_soul_and_identities(self) -> None:
        soul = load_soul(soul_path_for_language(PACKAGE_ROOT, "en"))
        for field in ("name", "persona", "tone", "style"):
            self.assertNoChinese(str(getattr(soul, field, "")), f"soul.{field}")
        identities = identities_path_for_language(PACKAGE_ROOT, "en")
        self.assertTrue(identities.exists(), f"missing english identities at {identities}")
        self.assertNoChinese(identities.read_text(encoding="utf-8"), "en_identities.yaml")

    def test_english_seed_bank(self) -> None:
        seeds = _seed_entries("en")
        self.assertTrue(seeds, "english seed bank is empty")
        for entry in seeds:
            event = str(entry.get("event", "?"))
            self.assertNoChinese(str(entry.get("line", "")), f"en seed [{event}]")

    def test_morning_digest(self) -> None:
        records = [
            EventRecord(
                time="2026-08-25T23:10:00", source="codex", event="waiting_user",
                level="warning", summary="needs a decision", pal_reaction="",
            ),
            EventRecord(
                time="2026-08-26T01:40:00", source="hardware", event="overloaded",
                level="critical", summary="gpu at 97C", pal_reaction="",
            ),
        ]
        self.assertNoChinese(summarize_events(records, "en"), "digest with events")
        self.assertNoChinese(summarize_events([], "en"), "empty digest")

    def test_quiz_dialog_copy(self) -> None:
        for key, (zh, en) in _QUIZ_COPY.items():
            self.assertNoChinese(en, f"_QUIZ_COPY[{key}]")
            self.assertNotEqual(cjk_in(zh), "", f"_QUIZ_COPY[{key}] lost its Chinese")

    def test_claude_activity_labels(self) -> None:
        for activity in ACTIVITY_ZH:
            self.assertNoChinese(activity_label(activity, "en"), f"activity_label({activity})")

    def test_quiz_report_scaffolding(self) -> None:
        """The packet supplies its own localised text; the frame around it is ours.

        An english packet still came back wrapped in Chinese headings, because
        the report renderer had no language of its own.
        """
        packets = load_quiz_packets(PACKAGE_ROOT / "quizzes.yaml")
        self.assertTrue(packets, "no quiz packets to check")
        source = packets[0]
        # strip the packet's own copy so only our scaffolding is under test
        english_packet = replace(source, language="en", results=(), questions=source.questions)
        scores = {metric: 3 for metric in english_packet.metrics}
        report = build_report(english_packet, scores)
        self.assertNoChinese(format_report(report, "en"), "quiz report")

    def test_identity_brief_labels(self) -> None:
        manifest = load_identity_manifest(identities_path_for_language(PACKAGE_ROOT, "en"))
        for pack in manifest.packs.values():
            self.assertNoChinese(pack.prompt_brief("en"), f"identity brief [{pack.id}]")


STATUS_CONTEXT: dict[str, object] = {
    "codex": {"status": "working", "summary": "editing files", "stale": False},
    "codex_usage": {"level": "low", "remaining_percent": 8.0, "reset_in_label": "1h 30m"},
    "claude": {"active_count": 2, "total_alive": 3},
    "claude_usage": {"level": "busy", "recent_5h_requests": 40, "recent_5h_total_tokens": 900000},
    "claude_account": {"level": "watch", "remaining_percent": 44.0, "reset_in_label": "2h", "plan": "Max"},
    "openai_billing": {"level": "over_budget", "month_cost": 31.0, "monthly_budget": 20.0},
    "hardware": {"level": "warm"},
    "activity": {"tier": "normal"},
}

STATUS_COMMANDS = (
    "status_codex",
    "status_claude",
    "status_claude_usage",
    "status_claude_account",
    "status_openai_billing",
    "status_hardware",
    "status_usage",
    "status_overview",
)


class ActivityKeyTests(unittest.TestCase):
    """The activity key is stored, looked up, and displayed by three modules.

    They used to agree only because the key was the Chinese label. Once the key
    became language-independent, a module still comparing against the label
    failed silently: every lookup fell through to the normal policy, so quiet
    and hyper stopped doing anything and nothing raised.
    """

    def test_every_preset_resolves_to_its_own_policy(self) -> None:
        for key, _mult in FREQUENCY_PRESETS:
            policy = policy_for_frequency(key)
            self.assertEqual(policy.key, key, f"{key} resolved to {policy.key}")

    def test_presets_and_policies_cover_the_same_keys(self) -> None:
        self.assertEqual({key for key, _ in FREQUENCY_PRESETS}, set(POLICIES))

    def test_quiet_and_hyper_are_actually_distinct(self) -> None:
        quiet = policy_for_frequency("quiet")
        hyper = policy_for_frequency("hyper")
        self.assertLess(quiet.speech_frequency, hyper.speech_frequency)

    def test_legacy_chinese_keys_still_resolve(self) -> None:
        for legacy, expected in (("安静", "quiet"), ("正常", "normal"), ("活泼", "active"), ("多动", "hyper")):
            self.assertEqual(normalize_frequency(legacy), expected)
            self.assertEqual(policy_for_frequency(legacy).key, expected)

    def test_unknown_key_falls_back_to_normal(self) -> None:
        self.assertEqual(policy_for_frequency("nonsense").key, "normal")


class StatusDispatcherTests(unittest.TestCase):
    """Status answers must follow the pal's language, whoever asks for them."""

    def test_english_context_gets_english_for_every_command(self) -> None:
        context = dict(STATUS_CONTEXT, language_mode="en")
        for command in STATUS_COMMANDS:
            reaction = status_reaction(command, context)
            self.assertIsNotNone(reaction, f"{command} produced no reaction")
            assert reaction is not None
            leaked = cjk_in(reaction.line)
            self.assertEqual(leaked, "", f"{command} leaked {leaked!r} in: {reaction.line!r}")

    def test_chinese_context_still_gets_chinese(self) -> None:
        context = dict(STATUS_CONTEXT, language_mode="zh-CN")
        for command in STATUS_COMMANDS:
            reaction = status_reaction(command, context)
            self.assertIsNotNone(reaction, f"{command} produced no reaction")
            assert reaction is not None
            self.assertNotEqual(cjk_in(reaction.line), "", f"{command} lost its Chinese")

    def test_unknown_command_returns_none_in_both_languages(self) -> None:
        for language in ("en", "zh-CN"):
            context = dict(STATUS_CONTEXT, language_mode=language)
            self.assertIsNone(status_reaction("status_nonsense", context))


if __name__ == "__main__":
    unittest.main()
