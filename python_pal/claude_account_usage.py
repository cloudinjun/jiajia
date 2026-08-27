from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any


@dataclass(frozen=True)
class ClaudeAccountUsageStatus:
    usage_remaining_percent: float | None = None
    reset_at: str = ""
    reset_in_seconds: float | None = None
    plan: str = ""
    source: str = ""
    updated_at: str = ""
    stale: bool = False
    level: str = "unavailable"
    previous_level: str = ""
    event_id: str = ""
    summary_line: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "claude_account_remaining_percent": _round_or_none(self.usage_remaining_percent),
            "claude_account_reset_at": self.reset_at,
            "claude_account_reset_in_seconds": _round_or_none(self.reset_in_seconds),
            "claude_account_reset_in_label": format_reset_in(self.reset_in_seconds),
            "claude_account_plan": self.plan,
            "claude_account_source": self.source,
            "claude_account_updated_at": self.updated_at,
            "claude_account_stale": self.stale,
            "claude_account_level": self.level,
            "claude_account_summary": self.summary_line,
            "claude_account_tags": list(self.tags),
        }


class ClaudeAccountUsageMonitor:
    def __init__(
        self,
        path: Path,
        stale_after_seconds: int = 6 * 60 * 60,
    ) -> None:
        self.path = path
        self.stale_after_seconds = stale_after_seconds
        self._last_remaining: float | None = None
        self._last_level = "unavailable"

    def sample(self) -> ClaudeAccountUsageStatus:
        try:
            stat = self.path.stat()
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return ClaudeAccountUsageStatus()

        if not isinstance(raw, dict):
            return ClaudeAccountUsageStatus(event_id=str(stat.st_mtime_ns))

        remaining = _percent_or_none(raw.get("usage_remaining_percent"))
        reset_at = _clean_text(raw.get("reset_at"), limit=90)
        reset_in = _reset_in_seconds(reset_at)
        plan = _clean_text(raw.get("plan"), limit=40)
        source = _clean_text(raw.get("source"), limit=40)
        updated_at = _clean_text(raw.get("updated_at"), limit=90)
        stale = bool(raw.get("stale")) or time.time() - stat.st_mtime > self.stale_after_seconds

        level = _level_for(remaining, reset_in, stale)
        if (
            self._last_remaining is not None
            and self._last_remaining < 30
            and remaining is not None
            and remaining >= 70
            and not stale
        ):
            level = "refilled"

        previous = self._last_level
        tags = _usage_tags(level, remaining, reset_in, stale)
        summary = _summary_line(remaining, reset_in, stale)
        signature = f"claude_account|{remaining}|{reset_at}|{updated_at}|{stale}|{stat.st_mtime_ns}"

        self._last_remaining = remaining
        self._last_level = level
        return ClaudeAccountUsageStatus(
            usage_remaining_percent=remaining,
            reset_at=reset_at,
            reset_in_seconds=reset_in,
            plan=plan,
            source=source,
            updated_at=updated_at,
            stale=stale,
            level=level,
            previous_level=previous,
            event_id=signature,
            summary_line=summary,
            tags=tags,
        )


def format_reset_in(seconds: float | None) -> str:
    if seconds is None:
        return ""
    if seconds <= 0:
        return "现在"
    minutes = round(seconds / 60)
    if minutes < 60:
        return f"{minutes}分钟"
    hours = minutes // 60
    rest_minutes = minutes % 60
    if rest_minutes:
        return f"{hours}小时{rest_minutes}分钟"
    return f"{hours}小时"


def _level_for(remaining: float | None, reset_in: float | None, stale: bool) -> str:
    if stale:
        return "unavailable"
    if remaining is None and reset_in is None:
        return "unavailable"
    if remaining is not None:
        if remaining < 10:
            return "critical"
        if remaining < 30:
            if reset_in is not None and 0 <= reset_in <= 30 * 60:
                return "reset_soon"
            return "low"
        if remaining < 60:
            if reset_in is not None and 0 <= reset_in <= 30 * 60:
                return "reset_soon"
            return "watch"
        return "normal"
    if reset_in is not None and 0 <= reset_in <= 30 * 60:
        return "reset_soon"
    return "unavailable"


def _usage_tags(
    level: str,
    remaining: float | None,
    reset_in: float | None,
    stale: bool,
) -> tuple[str, ...]:
    tags = {f"claude_account_{level}"}
    if stale:
        tags.add("usage_stale")
    if remaining is not None:
        if remaining < 30:
            tags.add("usage_low")
        if remaining < 10:
            tags.update({"usage_critical", "critical"})
    if reset_in is not None and 0 <= reset_in <= 30 * 60:
        tags.add("usage_reset_wait")
    if level == "refilled":
        tags.update({"recovery", "refill"})
    return tuple(sorted(tags))


def _summary_line(remaining: float | None, reset_in: float | None, stale: bool) -> str:
    if stale:
        return "Claude 账号 usage 数据有点旧。夹夹先不拿它当新鲜证据。"
    parts = []
    if remaining is not None:
        parts.append(f"Claude 账号还剩 {remaining:.0f}%")
    reset_label = format_reset_in(reset_in)
    if reset_label:
        parts.append(f"{reset_label}后回血" if reset_label != "现在" else "现在应该回血")
    return "，".join(parts) if parts else "还没有 Claude 账号 usage 数据。"


def _reset_in_seconds(value: str) -> float | None:
    if not value:
        return None
    reset_at = _parse_datetime(value)
    if reset_at is None:
        return None
    now = datetime.now().astimezone()
    return max(0.0, (reset_at - now).total_seconds())


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return parsed.astimezone()


def _percent_or_none(value: Any) -> float | None:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(100.0, percent))


def _clean_text(value: Any, limit: int = 80) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _round_or_none(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
