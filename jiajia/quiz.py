from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
import uuid
from typing import Any


STORE_VERSION = 1
ACTIVE_SESSION_STATES = {"active", "paused", "completed_waiting_result"}


@dataclass
class QuizOption:
    id: str
    text: str
    scores: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizOption":
        return cls(
            id=str(data.get("id") or "").strip(),
            text=str(data.get("text") or "").strip(),
            scores=_scores(data.get("scores") or data.get("metrics")),
        )


@dataclass
class QuizQuestion:
    id: str
    text: str
    options: list[QuizOption] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizQuestion":
        options = [
            QuizOption.from_dict(item)
            for item in _list_of_dicts(data.get("options"))
        ]
        return cls(
            id=str(data.get("id") or "").strip(),
            text=str(data.get("text") or data.get("prompt") or "").strip(),
            options=options,
        )


@dataclass
class QuizResultTemplate:
    id: str
    metric: str
    title: str
    line: str
    quote: str = ""
    paragraph: str = ""
    achievements: list[str] = field(default_factory=list)
    action: str = "snap_innocent"
    mood: str = "smirk"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizResultTemplate":
        return cls(
            id=str(data.get("id") or "").strip(),
            metric=str(data.get("metric") or "").strip(),
            title=str(data.get("title") or "").strip(),
            line=str(data.get("line") or data.get("description") or "").strip(),
            quote=str(data.get("quote") or "").strip(),
            paragraph=str(data.get("paragraph") or "").strip(),
            achievements=[str(item).strip() for item in _list(data.get("achievements")) if str(item).strip()],
            action=str(data.get("action") or "snap_innocent").strip(),
            mood=str(data.get("mood") or "smirk").strip(),
        )


@dataclass
class QuizPacket:
    id: str
    title: str
    subtitle: str
    language: str
    metrics: list[str]
    questions: list[QuizQuestion]
    results: list[QuizResultTemplate]
    safety_label: str = "entertainment_only"
    source: str = "fallback"
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizPacket":
        metrics = [str(item).strip() for item in _list(data.get("metrics")) if str(item).strip()]
        return cls(
            id=str(data.get("id") or "").strip(),
            title=str(data.get("title") or "").strip(),
            subtitle=str(data.get("subtitle") or "").strip(),
            language=str(data.get("language") or "zh-CN").strip(),
            metrics=metrics,
            questions=[
                QuizQuestion.from_dict(item)
                for item in _list_of_dicts(data.get("questions"))
            ],
            results=[
                QuizResultTemplate.from_dict(item)
                for item in _list_of_dicts(data.get("results"))
            ],
            safety_label=str(data.get("safety_label") or "entertainment_only").strip(),
            source=str(data.get("source") or "fallback").strip(),
            created_at=float(data.get("created_at") or time.time()),
        )


@dataclass
class QuizSession:
    id: str
    packet_id: str
    answers: dict[str, str] = field(default_factory=dict)
    current_index: int = 0
    state: str = "active"
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def start(cls, packet: QuizPacket) -> "QuizSession":
        return cls(id=uuid.uuid4().hex[:12], packet_id=packet.id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizSession":
        answers = {
            str(key): str(value)
            for key, value in dict(data.get("answers") or {}).items()
        }
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            packet_id=str(data.get("packet_id") or ""),
            answers=answers,
            current_index=int(data.get("current_index") or 0),
            state=str(data.get("state") or "active"),
            started_at=float(data.get("started_at") or time.time()),
            updated_at=float(data.get("updated_at") or time.time()),
        )


class QuizStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def packets(self) -> list[QuizPacket]:
        return [
            QuizPacket.from_dict(item)
            for item in _list_of_dicts(self._load_raw().get("packets"))
        ]

    def get_packet(self, packet_id: str) -> QuizPacket | None:
        for packet in self.packets():
            if packet.id == packet_id:
                return packet
        return None

    def upsert_packet(self, packet: QuizPacket) -> None:
        raw = self._load_raw()
        packets = _list_of_dicts(raw.get("packets"))
        packet_data = asdict(packet)
        for index, item in enumerate(packets):
            if str(item.get("id") or "") == packet.id:
                packets[index] = packet_data
                break
        else:
            packets.append(packet_data)
        raw["packets"] = packets
        self._save_raw(raw)

    def next_packet(self, language: str | None = None) -> QuizPacket | None:
        packets = self.packets()
        if language:
            exact = [packet for packet in packets if _lang_key(packet.language) == _lang_key(language)]
            if exact:
                return exact[0]
        return packets[0] if packets else None

    def active_session(self) -> QuizSession | None:
        raw = self._load_raw().get("active_session")
        if not isinstance(raw, dict):
            return None
        session = QuizSession.from_dict(raw)
        return session if session.state in ACTIVE_SESSION_STATES else None

    def save_session(self, session: QuizSession | None) -> None:
        raw = self._load_raw()
        raw["active_session"] = asdict(session) if session else None
        self._save_raw(raw)

    def clear_session(self) -> None:
        self.save_session(None)

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": STORE_VERSION, "packets": [], "active_session": None}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return {"version": STORE_VERSION, "packets": [], "active_session": None}
        if not isinstance(data, dict):
            return {"version": STORE_VERSION, "packets": [], "active_session": None}
        data.setdefault("version", STORE_VERSION)
        data.setdefault("packets", [])
        data.setdefault("active_session", None)
        return data

    def _save_raw(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(self.path)


def load_quiz_packets(path: Path) -> list[QuizPacket]:
    if not path.exists():
        return []
    data = _load_structured(path)
    packets = data.get("quizzes") if isinstance(data, dict) else data
    return [QuizPacket.from_dict(item) for item in _list_of_dicts(packets)]


def current_question(packet: QuizPacket, session: QuizSession) -> QuizQuestion | None:
    if session.current_index < 0 or session.current_index >= len(packet.questions):
        return None
    return packet.questions[session.current_index]


@dataclass
class QuizReport:
    title: str
    percent: int
    quote: str
    paragraph: str
    readings: dict[str, int]
    achievements: list[str]
    result: QuizResultTemplate


def record_answer(packet: QuizPacket, session: QuizSession, option_id: str) -> QuizSession:
    question = current_question(packet, session)
    if question is None:
        session.state = "completed"
        session.updated_at = time.time()
        return session
    allowed = {option.id for option in question.options}
    if option_id not in allowed:
        raise ValueError(f"Unknown quiz option: {option_id}")
    session.answers[question.id] = option_id
    session.current_index += 1
    session.state = "completed_waiting_result" if session.current_index >= len(packet.questions) else "active"
    session.updated_at = time.time()
    return session


def score_packet(packet: QuizPacket, answers: dict[str, str]) -> dict[str, int]:
    scores = {metric: 0 for metric in packet.metrics}
    question_by_id = {question.id: question for question in packet.questions}
    for question_id, option_id in answers.items():
        question = question_by_id.get(question_id)
        if question is None:
            continue
        option = next((item for item in question.options if item.id == option_id), None)
        if option is None:
            continue
        for metric, value in option.scores.items():
            if metric in scores:
                scores[metric] += int(value)
    return scores


def choose_result(packet: QuizPacket, scores: dict[str, int]) -> QuizResultTemplate:
    if not packet.results:
        if str(packet.language or "").startswith("en"):
            return QuizResultTemplate(
                id="fallback",
                metric="",
                title="Result mislaid",
                line="The result card has been clipped away. I claim this is normal statistical loss.",
            )
        return QuizResultTemplate(
            id="fallback",
            metric="",
            title="结果遗失",
            line="结果卡片被夹夹夹走了。它声称这是统计学的正常损耗。",
        )
    ranked = sorted(
        packet.metrics,
        key=lambda metric: (-int(scores.get(metric, 0)), packet.metrics.index(metric)),
    )
    for metric in ranked:
        for result in packet.results:
            if result.metric == metric:
                return result
    return packet.results[0]


def build_report(packet: QuizPacket, scores: dict[str, int]) -> QuizReport:
    english = str(packet.language or "").startswith("en")
    result = choose_result(packet, scores)
    max_score = _estimated_metric_max(packet)
    readings = {
        metric: _percent(int(scores.get(metric, 0)), max_score)
        for metric in packet.metrics
    }
    top_percent = readings.get(result.metric, max(readings.values(), default=0))
    total_percent = _percent(sum(scores.values()), max(1, len(packet.questions) * 3))
    percent = round((top_percent * 0.72) + (total_percent * 0.28))
    quote = result.quote or _default_quote(result.title, percent, english)
    paragraph = result.paragraph or _default_paragraph(result, readings, english)
    achievements = result.achievements[:3] if result.achievements else _default_achievements(packet, readings)
    return QuizReport(
        title=result.title,
        percent=max(0, min(100, percent)),
        quote=quote,
        paragraph=paragraph,
        readings=readings,
        achievements=achievements,
        result=result,
    )


def format_report(report: QuizReport, language: str = "zh-CN") -> str:
    """Render a finished report. The packet's own text is already localised;
    only this surrounding scaffolding needed a language of its own."""
    readings = "\n".join(
        f"- {metric}: {value}%"
        for metric, value in report.readings.items()
    )
    achievements = " / ".join(report.achievements)
    if str(language).startswith("en"):
        return (
            f"Human operating system health: {report.percent}%\n"
            f"{report.quote}\n\n"
            f"{report.paragraph}\n\n"
            f"Six readings:\n{readings}\n\n"
            f"Badges: {achievements}"
        )
    return (
        f"人类操作系统健康度：{report.percent}%\n"
        f"{report.quote}\n\n"
        f"{report.paragraph}\n\n"
        f"六项读数：\n{readings}\n\n"
        f"成就徽章：{achievements}"
    )


def _load_structured(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception as exc:
        raise ValueError(f"Cannot parse quiz data: {path}") from exc


def _estimated_metric_max(packet: QuizPacket) -> int:
    total = 0
    for question in packet.questions:
        best = 0
        for option in question.options:
            if option.scores:
                best = max(best, max(option.scores.values()))
        total += max(1, best)
    return max(1, total)


def _percent(value: int, maximum: int) -> int:
    return max(0, min(100, round(value / max(1, maximum) * 100)))


def _default_quote(title: str, percent: int, english: bool = False) -> str:
    if english:
        if percent >= 76:
            return f"My ruling: {title} runs strong, strong enough to carry a faint scent of process."
        if percent >= 46:
            return f"My ruling: {title} is a clear leaning, with room left for improvised excuses."
        return f"My ruling: {title} is only passing through. It has not occupied you, merely looked in."
    if percent >= 76:
        return f"夹夹判定：{title} 浓度很高，高到已经有一点行政流程的香气。"
    if percent >= 46:
        return f"夹夹判定：{title} 倾向明确，但还保留了人类临场找借口的弹性。"
    return f"夹夹判定：{title} 只是路过。它没有占领你，只是在门口探头。"


def _default_paragraph(
    result: QuizResultTemplate, readings: dict[str, int], english: bool = False
) -> str:
    top = max(readings, key=lambda metric: readings[metric]) if readings else result.metric
    low = min(readings, key=lambda metric: readings[metric]) if readings else result.metric
    if english:
        return (
            f"Your main background temperament lands on {result.title}. This is not an assessment; "
            f"it is a very light sticky note. The {top} reading looks alert, while {low} behaves "
            f"like it was just woken by a manager. On the whole the system still runs, though it "
            f"occasionally mistakes preparation for the work itself."
        )
    return (
        f"你的主要后台气质落在 {result.title}。这不是评价，是一张非常轻的便利贴。"
        f"{top} 指标比较精神，{low} 指标则表现得像刚被老板叫醒。"
        f"总体来说，系统还能运行，只是偶尔会把准备工作误认为工作本身。"
    )


_BADGES_ZH = {
    "scheduler": "流程感过量",
    "cache": "旧资料保温",
    "renderer": "视觉胜利",
    "watchdog": "异常预警员",
    "indexer": "资料囤积许可",
    "screensaver": "低功耗待机",
}

_BADGES_EN = {
    "scheduler": "Excess process",
    "cache": "Keeping old material warm",
    "renderer": "Visual victory",
    "watchdog": "Anomaly early-warning officer",
    "indexer": "Licensed material hoarding",
    "screensaver": "Low-power standby",
}


def _default_achievements(packet: QuizPacket, readings: dict[str, int]) -> list[str]:
    ranked = sorted(packet.metrics, key=lambda metric: readings.get(metric, 0), reverse=True)
    english = str(packet.language or "").startswith("en")
    badges = _BADGES_EN if english else _BADGES_ZH
    suffix = "shining" if english else "发光"
    picked = [badges.get(metric, f"{metric} {suffix}") for metric in ranked[:2]]
    picked.append("No-liability report generated" if english else "无责任报告已生成")
    return picked[:3]


def _lang_key(language: str) -> str:
    value = language.lower()
    if value.startswith("en"):
        return "en"
    if value.startswith("zh"):
        return "zh"
    return value


def _scores(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    scores: dict[str, int] = {}
    for key, value in raw.items():
        try:
            scores[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return scores


def _list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _list_of_dicts(raw: Any) -> list[dict[str, Any]]:
    return [item for item in _list(raw) if isinstance(item, dict)]
