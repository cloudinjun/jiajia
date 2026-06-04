from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


MAX_SUMMARY_CHARS = 180


@dataclass(frozen=True)
class EventRecord:
    time: str
    source: str
    event: str
    level: str = "notice"
    summary: str = ""
    pal_reaction: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "time": self.time,
            "source": self.source,
            "event": self.event,
            "level": self.level,
            "summary": self.summary,
            "pal_reaction": self.pal_reaction,
        }

    def short_line(self) -> str:
        label = f"{self.source}:{self.event}"
        detail = f" - {self.summary}" if self.summary else ""
        return f"{_time_label(self.time)} {self.level} {label}{detail}"


class EventLog:
    def __init__(self, path: Path, digest_state_path: Path | None = None) -> None:
        self.path = path
        self.digest_state_path = digest_state_path or path.with_name("digest_state.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        source: str,
        event: str,
        level: str = "notice",
        summary: str = "",
        pal_reaction: str = "",
    ) -> EventRecord:
        record = EventRecord(
            time=_now_iso(),
            source=_clean_key(source),
            event=_clean_key(event),
            level=_clean_key(level) or "notice",
            summary=_clean_summary(summary),
            pal_reaction=_clean_summary(pal_reaction, 80),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
        return record

    def last(self, limit: int = 20) -> list[EventRecord]:
        return self._read_records()[-max(1, limit):]

    def digest(self, mark_read: bool = True) -> str:
        records = self._records_since_last_digest()
        if mark_read:
            self._write_digest_state(_now_iso())
        return summarize_events(records)

    def _records_since_last_digest(self) -> list[EventRecord]:
        last_digest_at = self._last_digest_at()
        records = self._read_records()
        if not last_digest_at:
            return records[-80:]
        return [record for record in records if _parse_time(record.time) > last_digest_at]

    def _read_records(self) -> list[EventRecord]:
        try:
            lines = self.path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            return []
        records: list[EventRecord] = []
        for line in lines[-500:]:
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                records.append(_parse_record(raw))
        return records

    def _last_digest_at(self) -> datetime | None:
        try:
            raw = json.loads(self.digest_state_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        return _parse_time(str(raw.get("last_digest_at") or ""))

    def _write_digest_state(self, timestamp: str) -> None:
        self.digest_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.digest_state_path.write_text(
            json.dumps({"last_digest_at": timestamp}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def summarize_events(records: list[EventRecord]) -> str:
    if not records:
        return "昨晚没有可汇报的状态事件。夹夹很安静，甚至有点像一枚合格文具。"

    total = len(records)
    by_source = _counts(record.source for record in records)
    by_level = _counts(record.level for record in records)
    important = [
        record
        for record in records
        if record.level in {"warning", "critical", "error"}
        or record.event in {"waiting_user", "blocked", "error", "critical", "overloaded", "usage_critical"}
    ]
    done = [record for record in records if record.event in {"done", "refilled", "cooling"}]
    first = records[0]
    last = records[-1]
    lines = [
        f"早。昨晚夹夹记了 {total} 条状态事件，时间从 {_time_label(first.time)} 到 {_time_label(last.time)}。",
        f"来源：{_format_counts(by_source)}。",
    ]
    if by_level:
        lines.append(f"等级：{_format_counts(by_level)}。")
    if important:
        lines.append("要先看这些：")
        for record in important[-4:]:
            lines.append(f"- {record.short_line()}")
    elif done:
        lines.append("没有大事故。几个收尾事件看起来还算体面：")
        for record in done[-3:]:
            lines.append(f"- {record.short_line()}")
    else:
        lines.append("没有明显事故。可以先假装今天很有秩序。")
    return "\n".join(lines)


def _parse_record(raw: dict[str, Any]) -> EventRecord:
    return EventRecord(
        time=str(raw.get("time") or ""),
        source=_clean_key(raw.get("source")),
        event=_clean_key(raw.get("event")),
        level=_clean_key(raw.get("level")) or "notice",
        summary=_clean_summary(raw.get("summary")),
        pal_reaction=_clean_summary(raw.get("pal_reaction"), 80),
    )


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value or "").strip()
        if key:
            counts[key] = counts.get(key, 0) + 1
    return counts


def _format_counts(counts: dict[str, int]) -> str:
    return " / ".join(f"{key} {count}" for key, count in sorted(counts.items()))


def _clean_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")[:80]


def _clean_summary(value: object, limit: int = MAX_SUMMARY_CHARS) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _parse_time(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _time_label(value: str) -> str:
    parsed = _parse_time(value).astimezone()
    if parsed.year <= 1:
        return "unknown"
    return parsed.strftime("%H:%M")
