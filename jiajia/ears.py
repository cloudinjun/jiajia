from __future__ import annotations

from dataclasses import dataclass, field
import ctypes
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None


@dataclass
class EarContext:
    active_window_title: str = ""
    active_process: str = ""
    app_category: str = "unknown"
    focus_seconds: float = 0.0
    idle_seconds: float = 0.0
    window_switches_per_minute: int = 0
    activity_level: str = "active"
    is_fullscreen: bool = False
    behavior_tags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "active_window_title": self.active_window_title,
            "active_process": self.active_process,
            "app_category": self.app_category,
            "focus_seconds": round(self.focus_seconds, 1),
            "idle_seconds": round(self.idle_seconds, 1),
            "window_switches_per_minute": self.window_switches_per_minute,
            "activity_level": self.activity_level,
            "is_fullscreen": self.is_fullscreen,
            "behavior_tags": self.behavior_tags,
        }


class Ears:
    """Low-risk ambient signals: no key text, no clipboard, no hidden logging."""

    def __init__(self) -> None:
        self._last_signature = ""
        self._focus_started_at = time.time()
        self._switch_times: list[float] = []

    def sample(self) -> EarContext:
        now = time.time()
        title = _foreground_window_title()
        process = _foreground_process_name()
        is_fullscreen = _foreground_is_fullscreen()
        category = _app_category(process, title)
        signature = f"{process}|{title}"
        if signature != self._last_signature:
            self._last_signature = signature
            self._focus_started_at = now
            self._switch_times.append(now)
            self._switch_times = [stamp for stamp in self._switch_times if now - stamp <= 60]

        idle = _idle_seconds()
        focus_seconds = max(0.0, now - self._focus_started_at)
        switches = len(self._switch_times)
        activity = _activity_level(idle)
        tags = _behavior_tags(category, process, title, focus_seconds, idle, switches, activity, is_fullscreen)
        return EarContext(
            active_window_title=_safe_title(title, category),
            active_process=process,
            app_category=category,
            focus_seconds=focus_seconds,
            idle_seconds=idle,
            window_switches_per_minute=switches,
            activity_level=activity,
            is_fullscreen=is_fullscreen,
            behavior_tags=tags,
        )


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def _idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    elapsed_ms = ctypes.windll.kernel32.GetTickCount() - info.dwTime
    return max(0.0, elapsed_ms / 1000.0)


def _foreground_window_handle() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


def _foreground_window_title() -> str:
    hwnd = _foreground_window_handle()
    if not hwnd:
        return ""
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value[:200]


def _foreground_process_name() -> str:
    hwnd = _foreground_window_handle()
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    if psutil:
        try:
            return str(psutil.Process(pid.value).name())
        except Exception:
            pass
    return _process_name_from_path(pid.value)


def _foreground_is_fullscreen() -> bool:
    hwnd = _foreground_window_handle()
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    try:
        user32.MonitorFromWindow.restype = wintypes.HMONITOR
    except AttributeError:
        user32.MonitorFromWindow.restype = ctypes.c_void_p
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    monitor = user32.MonitorFromWindow(hwnd, 2)
    if not monitor:
        return False
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return False
    tolerance = 2
    return (
        abs(rect.left - info.rcMonitor.left) <= tolerance
        and abs(rect.top - info.rcMonitor.top) <= tolerance
        and abs(rect.right - info.rcMonitor.right) <= tolerance
        and abs(rect.bottom - info.rcMonitor.bottom) <= tolerance
    )


def _process_name_from_path(pid: int) -> str:
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(260)
        buffer = ctypes.create_unicode_buffer(size.value)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    return ""


def _app_category(process: str, title: str) -> str:
    text = f"{process} {title}".lower()
    groups = (
        ("codex", ("codex",)),
        ("editor", ("code.exe", "cursor", "pycharm", "webstorm", "sublime", "notepad++", "notepad.exe", "obsidian")),
        ("terminal", ("windowsterminal", "powershell", "cmd.exe", "pwsh", "wezterm", "alacritty")),
        ("browser", ("chrome", "msedge", "firefox", "brave", "opera")),
        ("file_manager", ("explorer.exe",)),
        ("meeting_or_chat", ("teams", "zoom", "slack", "discord", "wechat", "weixin", "qq.exe", "telegram", "mail", "outlook")),
        ("music", ("spotify", "music.ui", "foobar", "cloudmusic", "netease")),
        ("design", ("figma", "photoshop", "illustrator", "blender", "rhino", "fusion360")),
        ("game", ("steam", "unity", "unreal", "game")),
    )
    for category, needles in groups:
        if any(needle in text for needle in needles):
            return category
    return "unknown"


def _activity_level(idle_seconds: float) -> str:
    if idle_seconds >= 90:
        return "away"
    if idle_seconds >= 18:
        return "idle"
    return "active"


def _time_tags() -> list[str]:
    now = datetime.now()
    hour = now.hour
    tags: list[str] = []
    if 6 <= hour <= 11:
        tags.append("morning")
    elif 12 <= hour <= 17:
        tags.append("afternoon")
    elif 18 <= hour <= 22:
        tags.append("evening")
    else:
        tags.append("late_night")
    weekday = now.weekday()
    if weekday >= 5:
        tags.append("weekend")
    if weekday == 0:
        tags.append("monday")
    return tags


def _behavior_tags(
    category: str,
    process: str,
    title: str,
    focus_seconds: float,
    idle_seconds: float,
    switches_per_minute: int,
    activity: str,
    is_fullscreen: bool,
) -> list[str]:
    tags = {f"app_{category}", activity}
    tags.update(_time_tags())
    text = f"{process} {title}".lower()
    if switches_per_minute >= 8:
        tags.add("rapid_switching")
    if focus_seconds >= 300 and idle_seconds < 10:
        tags.add("long_focus")
    if focus_seconds >= 90 and idle_seconds >= 18:
        tags.add("idle_staring")
    if category == "browser" and switches_per_minute >= 4:
        tags.add("browser_research")
    if category in {"editor", "codex"} and focus_seconds >= 120:
        tags.add("deep_work")
    if category == "file_manager" and focus_seconds >= 45:
        tags.add("file_sorting")
    if "todo" in text or "task" in text or "任务" in text:
        tags.add("todo_visible")
    if "untitled" in text or "无标题" in text or "blank" in text:
        tags.add("blank_document")
    if category == "meeting_or_chat":
        tags.add("privacy_sensitive")
    if is_fullscreen:
        tags.add("fullscreen")
    return sorted(tags)


def _safe_title(title: str, category: str) -> str:
    clean = " ".join(title.split())
    if not clean:
        return ""
    if category == "meeting_or_chat":
        return "[chat or meeting window]"
    privacy_markers = ("password", "密码", "验证码", "token", "secret", "private", "dm", "message")
    lowered = clean.lower()
    if any(marker in lowered for marker in privacy_markers):
        return "[private window]"
    return clean[:120]
