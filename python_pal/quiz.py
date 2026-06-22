from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import time
import uuid
from typing import Any


STORE_VERSION = 1


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
    action: str = "snap_innocent"
    mood: str = "smirk"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QuizResultTemplate":
        return cls(
            id=str(data.get("id") or "").strip(),
            metric=str(data.get("metric") or "").strip(),
            title=str(data.get("title") or "").strip(),
            line=str(data.get("line") or data.get("description") or "").strip(),
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
        return session if session.state in {"active", "paused"} else None

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
    session.state = "completed" if session.current_index >= len(packet.questions) else "active"
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
