from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any


@dataclass(frozen=True)
class CodexUsageStatus:
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
            "codex_usage_remaining_percent": _round_or_none(self.usage_remaining_percent),
            "codex_usage_reset_at": self.reset_at,
            "codex_usage_reset_in_seconds": _round_or_none(self.reset_in_seconds),
            "codex_usage_reset_in_label": format_reset_in(self.reset_in_seconds),
            "codex_usage_plan": self.plan,
            "codex_usage_source": self.source,
            "codex_usage_updated_at": self.updated_at,
            "codex_usage_stale": self.stale,
            "codex_usage_level": self.level,
            "codex_usage_summary": self.summary_line,
            "codex_usage_tags": list(self.tags),
        }


class CodexUsageMonitor:
    def __init__(
        self,
        path: Path,
        stale_after_seconds: int = 6 * 60 * 60,
        codex_home: Path | None = None,
        session_file_limit: int = 30,
    ) -> None:
        self.path = path
        self.language = "zh-CN"
        self.stale_after_seconds = stale_after_seconds
        self.codex_home = codex_home or Path.home() / ".codex"
        self.session_file_limit = session_file_limit
        self._last_remaining: float | None = None
        self._last_level = "unavailable"

    def sample(self) -> CodexUsageStatus:
        session_status = self._sample_sessions()
        if session_status is not None:
            return session_status
        return self._sample_bridge_file()

    def _sample_bridge_file(self) -> CodexUsageStatus:
        try:
            stat = self.path.stat()
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return CodexUsageStatus()

        if not isinstance(raw, dict):
            return CodexUsageStatus(event_id=str(stat.st_mtime_ns))

        remaining = _percent_or_none(raw.get("usage_remaining_percent"))
        reset_at = _clean_text(raw.get("reset_at"), limit=90)
        reset_in = _reset_in_seconds(reset_at)
        plan = _clean_text(raw.get("plan"), limit=40)
        source = _clean_text(raw.get("source"), limit=40)
        updated_at = _clean_text(raw.get("updated_at"), limit=90)
        stale = bool(raw.get("stale")) or time.time() - stat.st_mtime > self.stale_after_seconds
        signature = f"bridge|{remaining}|{reset_at}|{updated_at}|{stale}|{stat.st_mtime_ns}"
        return self._build_status(remaining, reset_at, reset_in, plan, source, updated_at, stale, signature)

    def _sample_sessions(self) -> CodexUsageStatus | None:
        sessions_root = self.codex_home / "sessions"
        if not sessions_root.exists():
            return None
        try:
            files = sorted(
                sessions_root.rglob("rollout-*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[: self.session_file_limit]
        except OSError:
            return None
        for path in files:
            try:
                stat = path.stat()
            except OSError:
                continue
            extracted = _latest_codex_rate_limit(path)
            if extracted is None:
                continue
            line_no, rate_limit = extracted
            primary = rate_limit.get("primary")
            if not isinstance(primary, dict):
                continue
            used_percent = _percent_or_none(primary.get("used_percent"))
            remaining = 100.0 - used_percent if used_percent is not None else None
            reset_at = _timestamp_to_iso(primary.get("resets_at"))
            reset_in = _reset_in_seconds(reset_at)
            stale = (
                time.time() - stat.st_mtime > self.stale_after_seconds
                or _reset_expired(reset_at, grace_seconds=5 * 60)
            )
            if stale:
                continue
            plan = _clean_text(rate_limit.get("plan_type") or rate_limit.get("limit_name"), limit=40)
            source = "codex_sessions"
            updated_at = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
            signature = f"{source}|{path.name}|{line_no}|{remaining}|{reset_at}|{stat.st_mtime_ns}"
            return self._build_status(remaining, reset_at, reset_in, plan, source, updated_at, stale, signature)
        return None

    def _build_status(
        self,
        remaining: float | None,
        reset_at: str,
        reset_in: float | None,
        plan: str,
        source: str,
        updated_at: str,
        stale: bool,
        event_id: str,
    ) -> CodexUsageStatus:
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
        summary = _summary_line(remaining, reset_in, stale, self.language)
        self._last_remaining = remaining
        self._last_level = level
        return CodexUsageStatus(
            usage_remaining_percent=remaining,
            reset_at=reset_at,
            reset_in_seconds=reset_in,
            plan=plan,
            source=source,
            updated_at=updated_at,
            stale=stale,
            level=level,
            previous_level=previous,
            event_id=event_id,
            summary_line=summary,
            tags=tags,
        )


def format_reset_in(seconds: float | None, language: str = "zh-CN") -> str:
    """A human duration in the pal's language. Empty string means unknown."""
    english = str(language).startswith("en")
    if seconds is None:
        return ""
    if seconds <= 0:
        return "now" if english else "现在"
    minutes = round(seconds / 60)
    if minutes < 60:
        if english:
            return f"{minutes} min"
        return f"{minutes}分钟"
    hours = minutes // 60
    rest_minutes = minutes % 60
    if english:
        return f"{hours}h {rest_minutes}m" if rest_minutes else f"{hours}h"
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
    tags = {f"codex_usage_{level}"}
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


def _summary_line(
    remaining: float | None,
    reset_in: float | None,
    stale: bool,
    language: str = "zh-CN",
) -> str:
    english = str(language).startswith("en")
    if stale:
        if english:
            return "The Codex usage data is stale. I shan't treat it as fresh evidence."
        return "Codex usage 数据有点旧。夹夹先不拿它当新鲜证据。"
    parts = []
    if remaining is not None:
        parts.append(
            f"Codex is at {remaining:.0f}% remaining" if english else f"Codex 还剩 {remaining:.0f}%"
        )
    reset_label = format_reset_in(reset_in, language)
    if reset_label:
        if english:
            parts.append("refill is due now" if reset_label == "now" else f"refills in {reset_label}")
        else:
            parts.append(
                f"{reset_label}后回血" if reset_label != "现在" else "现在应该回血"
            )
    if parts:
        return ("; ".join(parts) + ".") if english else "，".join(parts)
    return "No Codex usage data yet." if english else "还没有 Codex usage 数据。"


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


def _timestamp_to_iso(value: Any) -> str:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return ""
    if timestamp <= 0:
        return ""
    try:
        return datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")
    except (OSError, OverflowError, ValueError):
        return ""


def _reset_expired(value: str, grace_seconds: int) -> bool:
    reset_at = _parse_datetime(value)
    if reset_at is None:
        return False
    return (datetime.now().astimezone() - reset_at).total_seconds() > grace_seconds


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


def _latest_codex_rate_limit(path: Path) -> tuple[int, dict[str, Any]] | None:
    latest: tuple[int, dict[str, Any]] | None = None
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if "token_count" not in line or "rate_limits" not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for rate_limit in _iter_rate_limits(record):
                    limit_id = _clean_text(rate_limit.get("limit_id"), limit=40).lower()
                    if limit_id and limit_id != "codex":
                        continue
                    latest = (line_no, rate_limit)
    except OSError:
        return None
    return latest


def _iter_rate_limits(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            rate_limits = current.get("rate_limits")
            if isinstance(rate_limits, dict):
                found.append(rate_limits)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found
