from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json
from collections import Counter
from typing import Any


@dataclass(frozen=True)
class ClaudeUsageWindow:
    requests: int = 0
    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    models: tuple[str, ...] = field(default_factory=tuple)
    projects: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cache_creation_input_tokens
            + self.cache_read_input_tokens
            + self.output_tokens
        )

    def as_dict(self, prefix: str) -> dict[str, object]:
        return {
            f"{prefix}_requests": self.requests,
            f"{prefix}_input_tokens": self.input_tokens,
            f"{prefix}_cache_creation_input_tokens": self.cache_creation_input_tokens,
            f"{prefix}_cache_read_input_tokens": self.cache_read_input_tokens,
            f"{prefix}_output_tokens": self.output_tokens,
            f"{prefix}_total_tokens": self.total_tokens,
            f"{prefix}_models": list(self.models),
            f"{prefix}_projects": list(self.projects),
        }


@dataclass(frozen=True)
class ClaudeUsageStatus:
    source: str = ""
    updated_at: str = ""
    last_request_at: str = ""
    stale: bool = False
    level: str = "unavailable"
    today: ClaudeUsageWindow = field(default_factory=ClaudeUsageWindow)
    recent_5h: ClaudeUsageWindow = field(default_factory=ClaudeUsageWindow)
    last_request: ClaudeUsageWindow = field(default_factory=ClaudeUsageWindow)
    summary_line: str = "还没有 Claude usage 数据。"
    event_id: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "claude_usage_source": self.source,
            "claude_usage_updated_at": self.updated_at,
            "claude_usage_last_request_at": self.last_request_at,
            "claude_usage_stale": self.stale,
            "claude_usage_level": self.level,
            "claude_usage_summary": self.summary_line,
            "claude_usage_tags": list(self.tags),
            **self.today.as_dict("claude_usage_today"),
            **self.recent_5h.as_dict("claude_usage_recent_5h"),
            **self.last_request.as_dict("claude_usage_last_request"),
        }


class ClaudeUsageMonitor:
    def __init__(
        self,
        claude_home: Path | None = None,
        file_limit: int = 240,
        stale_after_seconds: int = 12 * 60 * 60,
    ) -> None:
        self.claude_home = claude_home or Path.home() / ".claude"
        self.file_limit = file_limit
        self.stale_after_seconds = stale_after_seconds

    def sample(self) -> ClaudeUsageStatus:
        projects_root = self.claude_home / "projects"
        if not projects_root.is_dir():
            return ClaudeUsageStatus()

        now = datetime.now().astimezone()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        recent_start = now - timedelta(hours=5)
        history_start = now - timedelta(days=14)

        try:
            files = sorted(
                projects_root.rglob("*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[: self.file_limit]
        except OSError:
            return ClaudeUsageStatus()

        entries_by_key: dict[str, _UsageEntry] = {}
        latest_mtime = 0.0

        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime < history_start.timestamp():
                continue
            latest_mtime = max(latest_mtime, stat.st_mtime)
            for entry in _iter_usage_entries(path):
                previous = entries_by_key.get(entry.dedupe_key)
                if previous is None or entry.timestamp >= previous.timestamp:
                    entries_by_key[entry.dedupe_key] = entry

        entries = list(entries_by_key.values())
        latest_entry = max(entries, key=lambda entry: entry.timestamp) if entries else None
        if latest_entry is None:
            return ClaudeUsageStatus(
                source="claude_projects",
                updated_at=_mtime_to_iso(latest_mtime),
                summary_line="Claude 本地日志里还没有可统计的 usage。夹夹没有证据，就不装会计。",
                event_id=f"claude_usage_none|{latest_mtime}",
            )

        stale = (now - latest_entry.timestamp).total_seconds() > self.stale_after_seconds
        today_entries = [entry for entry in entries if entry.timestamp >= today_start]
        recent_entries = [entry for entry in entries if entry.timestamp >= recent_start]
        today = _summarize(today_entries)
        recent = _summarize(recent_entries)
        last = _summarize([latest_entry])
        level = _level_for(recent, stale)
        summary = _summary_line(today, recent, last, latest_entry.timestamp, latest_mtime, stale)
        tags = _usage_tags(level)
        return ClaudeUsageStatus(
            source="claude_projects",
            updated_at=_mtime_to_iso(latest_mtime),
            last_request_at=latest_entry.timestamp.isoformat(timespec="seconds"),
            stale=stale,
            level=level,
            today=today,
            recent_5h=recent,
            last_request=last,
            summary_line=summary,
            event_id=f"claude_usage|{level}|{today.requests}|{recent.requests}|{latest_entry.dedupe_key}",
            tags=tags,
        )


@dataclass(frozen=True)
class _UsageEntry:
    timestamp: datetime
    dedupe_key: str
    model: str
    project: str
    input_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    output_tokens: int


def _iter_usage_entries(path: Path) -> list[_UsageEntry]:
    entries: list[_UsageEntry] = []
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if "usage" not in line or '"message"' not in line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = _entry_from_record(raw, path, line_no)
                if entry is not None:
                    entries.append(entry)
    except OSError:
        return []
    return entries


def _entry_from_record(raw: dict[str, Any], path: Path, line_no: int) -> _UsageEntry | None:
    if raw.get("type") != "assistant":
        return None
    message = raw.get("message")
    if not isinstance(message, dict):
        return None
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    timestamp = _parse_timestamp(raw.get("timestamp"))
    if timestamp is None:
        return None
    message_id = _clean_text(message.get("id"), limit=80)
    request_id = _clean_text(raw.get("requestId"), limit=80)
    dedupe_key = message_id or request_id or f"{path}:{line_no}"
    model = _clean_text(message.get("model"), limit=80) or "unknown"
    project = _project_from_record(raw, path)
    input_tokens = _as_int(usage.get("input_tokens"))
    cache_creation_input_tokens = _as_int(usage.get("cache_creation_input_tokens"))
    cache_read_input_tokens = _as_int(usage.get("cache_read_input_tokens"))
    output_tokens = _as_int(usage.get("output_tokens"))
    if input_tokens + cache_creation_input_tokens + cache_read_input_tokens + output_tokens <= 0:
        return None
    return _UsageEntry(
        timestamp=timestamp,
        dedupe_key=dedupe_key,
        model=model,
        project=project,
        input_tokens=input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        output_tokens=output_tokens,
    )


def _summarize(entries: list[_UsageEntry]) -> ClaudeUsageWindow:
    models = Counter(entry.model for entry in entries if entry.model)
    projects = Counter(entry.project for entry in entries if entry.project)
    return ClaudeUsageWindow(
        requests=len(entries),
        input_tokens=sum(entry.input_tokens for entry in entries),
        cache_creation_input_tokens=sum(entry.cache_creation_input_tokens for entry in entries),
        cache_read_input_tokens=sum(entry.cache_read_input_tokens for entry in entries),
        output_tokens=sum(entry.output_tokens for entry in entries),
        models=tuple(model for model, _count in models.most_common(3)),
        projects=tuple(project for project, _count in projects.most_common(3)),
    )


def _level_for(recent: ClaudeUsageWindow, stale: bool) -> str:
    if stale:
        return "stale"
    if recent.requests <= 0:
        return "quiet"
    if recent.total_tokens >= 5_000_000:
        return "heavy"
    if recent.total_tokens >= 1_000_000:
        return "busy"
    return "active"


def _usage_tags(level: str) -> tuple[str, ...]:
    tags = {f"claude_usage_{level}"}
    if level in {"busy", "heavy"}:
        tags.add("claude_usage_busy")
    if level == "heavy":
        tags.add("usage_watch")
    return tuple(sorted(tags))


def _summary_line(
    today: ClaudeUsageWindow,
    recent: ClaudeUsageWindow,
    last: ClaudeUsageWindow,
    last_timestamp: datetime | None,
    latest_mtime: float,
    stale: bool,
) -> str:
    if today.requests <= 0 and recent.requests <= 0:
        if last.requests > 0 and last_timestamp is not None:
            log_note = ""
            if latest_mtime > 0 and datetime.fromtimestamp(latest_mtime).astimezone() > last_timestamp:
                log_note = " 本地日志后来有更新，但没有新的真实 Claude 计费用量；多半是恢复/回放/状态记录。"
            stale_note = " 数据已经有点旧。" if stale else ""
            model = f"，模型 {last.models[0]}" if last.models else ""
            return (
                f"今天和最近5小时没有新的真实 Claude usage。"
                f"最近一次真实记录是 {_format_time_label(last_timestamp)}{model}，约 {_format_tokens(last.total_tokens)} tokens。"
                f"{log_note}{stale_note}"
            )
        return "今天还没有可统计的 Claude usage。它暂时没有账本，只有气质。"
    parts = [
        f"Claude 今日 {today.requests} 次响应，约 {_format_tokens(today.total_tokens)} tokens",
        f"最近5小时 {recent.requests} 次，约 {_format_tokens(recent.total_tokens)}",
    ]
    if recent.models:
        parts.append(f"主模型 {recent.models[0]}")
    elif today.models:
        parts.append(f"主模型 {today.models[0]}")
    if last.output_tokens:
        parts.append(f"最近一次输出 {_format_tokens(last.output_tokens)}")
    if stale:
        parts.append("数据有点旧")
    parts.append("这是本地 token 账，不是官方剩余额度")
    return "；".join(parts) + "。"


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean_text(value, limit=90)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _project_from_record(raw: dict[str, Any], path: Path) -> str:
    cwd = _clean_text(raw.get("cwd"), limit=160)
    if cwd:
        parts = cwd.replace("\\", "/").rstrip("/").split("/")
        return parts[-1] if parts else cwd
    parent = path.parent.name
    return parent.replace("--", ":/").replace("-", "/")[-60:]


def _mtime_to_iso(value: float) -> str:
    if value <= 0:
        return ""
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 10_000:
        return f"{value / 1_000:.0f}k"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def _format_time_label(value: datetime) -> str:
    local = value.astimezone()
    now = datetime.now().astimezone()
    if local.date() == now.date():
        return f"今天 {local.strftime('%H:%M')}"
    yesterday = (now - timedelta(days=1)).date()
    if local.date() == yesterday:
        return f"昨天 {local.strftime('%H:%M')}"
    return local.strftime("%Y-%m-%d %H:%M")


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
