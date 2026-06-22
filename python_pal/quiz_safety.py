from __future__ import annotations

import re

from .quiz import QuizPacket


FORBIDDEN_PATTERN = re.compile(
    "|".join(
        re.escape(term)
        for term in (
            "诊断",
            "病症",
            "治疗",
            "药物",
            "抑郁",
            "焦虑",
            "创伤",
            "人格障碍",
            "心理疾病",
            "自闭",
            "智商",
            "财务建议",
            "投资建议",
            "法律建议",
            "medical",
            "diagnosis",
            "therapy",
            "therapist",
            "depression",
            "anxiety",
            "trauma",
            "autism",
            "adhd",
            "iq",
            "legal advice",
            "financial advice",
        )
    ),
    re.IGNORECASE,
)


def validate_quiz_packet(packet: QuizPacket) -> list[str]:
    errors: list[str] = []
    if not packet.id:
        errors.append("packet id is required")
    if packet.safety_label != "entertainment_only":
        errors.append("safety_label must be entertainment_only")
    if len(packet.questions) < 6 or len(packet.questions) > 10:
        errors.append("packet must contain 6-10 questions")
    if len(packet.metrics) != 6:
        errors.append("packet must define exactly 6 metrics")
    if len(set(packet.metrics)) != len(packet.metrics):
        errors.append("metrics must be unique")
    if len(packet.results) < 3:
        errors.append("packet must contain at least 3 result templates")

    metric_set = set(packet.metrics)
    for question in packet.questions:
        if not question.id:
            errors.append("question id is required")
        if not question.text:
            errors.append(f"question {question.id or '?'} text is required")
        if len(question.options) != 4:
            errors.append(f"question {question.id or '?'} must contain exactly 4 options")
        option_ids: set[str] = set()
        for option in question.options:
            if not option.id:
                errors.append(f"question {question.id or '?'} has an option without id")
            if option.id in option_ids:
                errors.append(f"question {question.id or '?'} has duplicate option id {option.id}")
            option_ids.add(option.id)
            unknown_metrics = set(option.scores) - metric_set
            if unknown_metrics:
                errors.append(
                    f"question {question.id or '?'} option {option.id or '?'} scores unknown metrics: "
                    + ", ".join(sorted(unknown_metrics))
                )

    for result in packet.results:
        if result.metric and result.metric not in metric_set:
            errors.append(f"result {result.id or '?'} uses unknown metric {result.metric}")

    blocked = FORBIDDEN_PATTERN.search(_packet_text(packet))
    if blocked:
        errors.append(f"packet contains forbidden assessment term: {blocked.group(0)}")
    return errors


def is_safe_quiz_packet(packet: QuizPacket) -> bool:
    return not validate_quiz_packet(packet)


def _packet_text(packet: QuizPacket) -> str:
    parts: list[str] = [packet.title, packet.subtitle, packet.safety_label]
    for question in packet.questions:
        parts.append(question.text)
        parts.extend(option.text for option in question.options)
    for result in packet.results:
        parts.extend((result.title, result.line))
    return "\n".join(parts)
