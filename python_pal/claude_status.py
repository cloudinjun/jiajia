from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time
from typing import Any


IDLE_THRESHOLD = 120
TAIL_BYTES = 4096

TOOL_ACTIVITY: dict[str, str] = {
    "Edit": "editing",
    "Write": "editing",
    "NotebookEdit": "editing",
    "Read": "reading",
    "Grep": "searching",
    "Glob": "searching",
    "Bash": "running",
    "PowerShell": "running",
    "Agent": "thinking",
    "WebSearch": "searching",
    "WebFetch": "reading",
}

ACTIVITY_ZH: dict[str, str] = {
    "editing": "改代码",
    "running": "跑命令",
    "reading": "读文件",
    "searching": "搜索中",
    "thinking": "思考中",
    "idle": "发呆中",
    "offline": "已结束",
}


@dataclass(frozen=True)
class ClaudeSession:
    pid: int
    session_id: str
    project: str
    kind: str
    entrypoint: str
    alive: bool
    activity: str
    idle_seconds: float

    def label(self) -> str:
        return "Desktop" if "desktop" in self.entrypoint else "Code"

    def activity_zh(self) -> str:
        return ACTIVITY_ZH.get(self.activity, self.activity)


@dataclass(frozen=True)
class ClaudeOverview:
    sessions: tuple[ClaudeSession, ...]
    event_id: str

    @property
    def total_alive(self) -> int:
        return sum(1 for s in self.sessions if s.alive)

    @property
    def active_count(self) -> int:
        return sum(1 for s in self.sessions if s.alive and s.activity not in ("idle", "offline"))

    def summary_line(self) -> str:
        alive = [s for s in self.sessions if s.alive]
        if not alive:
            return "没有发现活跃的 Claude 会话。"
        parts = []
        for s in alive:
            parts.append(f"{s.label()}@{s.project}: {s.activity_zh()}")
        return " / ".join(parts)


class ClaudeStatusMonitor:
    def __init__(self) -> None:
        home = Path.home() / ".claude"
        self._sessions_dir = home / "sessions"
        self._projects_dir = home / "projects"

    def sample(self) -> ClaudeOverview:
        sessions = self._scan()
        parts = [f"{s.pid}:{s.activity}" for s in sessions if s.alive]
        return ClaudeOverview(tuple(sessions), "|".join(parts))

    def _scan(self) -> list[ClaudeSession]:
        if not self._sessions_dir.is_dir():
            return []
        results: list[ClaudeSession] = []
        for path in self._sessions_dir.glob("*.json"):
            s = self._read_one(path)
            if s:
                results.append(s)
        return results

    def _read_one(self, path: Path) -> ClaudeSession | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(raw, dict):
            return None

        pid = int(raw.get("pid", 0))
        sid = str(raw.get("sessionId", ""))
        cwd = str(raw.get("cwd", ""))
        kind = str(raw.get("kind", "interactive"))
        entry = str(raw.get("entrypoint", "cli"))
        if not pid or not sid:
            return None

        project = _display_name(cwd)
        alive = _pid_alive(pid)
        if not alive:
            # 进程已退出，清理残留的 session 文件
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            return ClaudeSession(pid, sid, project, kind, entry, False, "offline", 0)

        slug = _project_slug(cwd)
        jsonl = self._projects_dir / slug / f"{sid}.jsonl"
        activity, idle = _check_activity(jsonl)
        return ClaudeSession(pid, sid, project, kind, entry, True, activity, idle)


def _pid_alive(pid: int) -> bool:
    try:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def _project_slug(cwd: str) -> str:
    normalized = cwd.replace("/", "\\")
    if len(normalized) >= 2 and normalized[1] == ":":
        drive = normalized[0]
        rest = normalized[2:].strip("\\").replace("\\", "-")
        return f"{drive}--{rest}"
    return normalized.replace("\\", "-")


def _display_name(cwd: str) -> str:
    parts = cwd.replace("\\", "/").rstrip("/").split("/")
    return parts[-1] if parts else cwd


def _check_activity(jsonl: Path) -> tuple[str, float]:
    try:
        mtime = jsonl.stat().st_mtime
    except OSError:
        return "idle", 9999.0
    idle = time.time() - mtime
    if idle > IDLE_THRESHOLD:
        return "idle", idle
    entry = _tail_jsonl(jsonl)
    if not entry:
        return "thinking", idle
    return _extract_activity(entry), idle


def _tail_jsonl(path: Path) -> dict[str, Any] | None:
    try:
        size = path.stat().st_size
        if size == 0:
            return None
        with open(path, "rb") as f:
            read_size = min(TAIL_BYTES, size)
            f.seek(-read_size, 2)
            data = f.read().decode("utf-8", errors="replace")
        for line in reversed(data.strip().split("\n")):
            line = line.strip()
            if not line:
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return None


def _extract_activity(entry: dict[str, Any]) -> str:
    msg = entry.get("message")
    if not isinstance(msg, dict):
        return "thinking"
    content = msg.get("content")
    if not isinstance(content, list):
        return "thinking"
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name = str(block.get("name", ""))
            # MCP 工具名格式: mcp__server__tool
            base = name.split("__")[-1] if "__" in name else name
            return TOOL_ACTIVITY.get(name, TOOL_ACTIVITY.get(base, "thinking"))
    for block in content:
        if isinstance(block, dict) and block.get("type") == "thinking":
            return "thinking"
    return "thinking" if entry.get("type") == "assistant" else "idle"
