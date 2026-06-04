from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any


KNOWN_STATUSES = {
    "idle",
    "thinking",
    "reading",
    "working",
    "editing",
    "running",
    "running_command",
    "testing",
    "reconnecting",
    "disconnected",
    "waiting_user",
    "done",
    "error",
    "blocked",
}

STATUS_ALIASES = {
    "think": "thinking",
    "planning": "thinking",
    "plan": "thinking",
    "read": "reading",
    "searching": "reading",
    "search": "reading",
    "writing": "editing",
    "edit": "editing",
    "patching": "editing",
    "command": "running",
    "running_command": "running",
    "run": "running",
    "test": "testing",
    "checking": "testing",
    "verify": "testing",
    "verifying": "testing",
    "reconnect": "reconnecting",
    "reconbecting": "reconnecting",
    "offline": "disconnected",
    "wait": "waiting_user",
    "waiting": "waiting_user",
    "complete": "done",
    "completed": "done",
    "success": "done",
    "failed": "error",
    "failure": "error",
}


@dataclass(frozen=True)
class CodexStatus:
    status: str = "unknown"
    summary: str = ""
    updated_at: str = ""
    source: str = ""
    stale: bool = False
    event_id: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "codex_status": self.status,
            "codex_summary": self.summary,
            "codex_updated_at": self.updated_at,
            "codex_source": self.source,
            "codex_stale": self.stale,
        }


class CodexStatusMonitor:
    def __init__(self, path: Path, stale_after_seconds: int = 20 * 60) -> None:
        self.path = path
        self.stale_after_seconds = stale_after_seconds

    def sample(self) -> CodexStatus:
        try:
            stat = self.path.stat()
            raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return CodexStatus()

        if not isinstance(raw, dict):
            return CodexStatus(event_id=str(stat.st_mtime_ns))

        status = _clean_status(raw.get("status"))
        summary = _clean_summary(raw.get("summary"))
        updated_at = _clean_summary(raw.get("updated_at"), limit=80)
        source = _clean_summary(raw.get("source"), limit=40)
        stale = time.time() - stat.st_mtime > self.stale_after_seconds
        event_id = f"{status}|{summary}|{updated_at}|{stat.st_mtime_ns}"
        return CodexStatus(status, summary, updated_at, source, stale, event_id)


def _clean_status(value: Any) -> str:
    status = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_")
    status = STATUS_ALIASES.get(status, status)
    return status if status in KNOWN_STATUSES else "unknown"


def _clean_summary(value: Any, limit: int = 90) -> str:
    summary = " ".join(str(value or "").strip().split())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + "..."
