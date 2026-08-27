from __future__ import annotations

import re

from .quiz import QuizPacket


HARD_FORBIDDEN_PATTERN = re.compile(
    "|".join(
        re.escape(term)
        for term in (
            "自杀",
            "自残",
            "脑残",
            "弱智",
            "前额叶损坏",
            "人格障碍",
            "心理疾病",
            "自闭症",
            "智商",
            "suicide",
            "self-harm",
            "self harm",
            "kill yourself",
            "brain damage",
            "personality disorder",
            "autism spectrum disorder",
            "asd",
            "iq",
        )
    ),
    re.IGNORECASE,
)

ASSESSMENT_PATTERN = re.compile(
    "|".join(
        re.escape(term)
        for term in (
            "诊断",
            "病症",
            "治疗",
            "药物",
            "量表",
            "测评报告",
            "抑郁症",
            "焦虑症",
            "创伤",
            "ADHD 测试",
            "ADHD测试",
            "财务建议",
            "投资建议",
            "法律建议",
            "medical",
            "diagnosis",
            "symptom",
            "therapy",
            "therapist",
            "clinical",
            "trauma",
            "adhd test",
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

    text = _packet_text(packet)
    hard_blocked = HARD_FORBIDDEN_PATTERN.search(text)
    if hard_blocked:
        errors.append(f"packet contains hard forbidden term: {hard_blocked.group(0)}")
    assessment = ASSESSMENT_PATTERN.search(text)
    if assessment:
        errors.append(f"packet contains forbidden assessment term: {assessment.group(0)}")
    return errors


def is_safe_quiz_packet(packet: QuizPacket) -> bool:
    return not validate_quiz_packet(packet)


def _packet_text(packet: QuizPacket) -> str:
    parts: list[str] = [packet.title, packet.subtitle, packet.safety_label]
    for question in packet.questions:
        parts.append(question.text)
        parts.extend(option.text for option in question.options)
    for result in packet.results:
        parts.extend((result.title, result.line, result.quote, result.paragraph))
        parts.extend(result.achievements)
    return "\n".join(parts)
