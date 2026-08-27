"""Proactive care system: daily greetings, work reminders, welcome back, achievements.

This module provides the CareEngine that body.py delegates to for all proactive
care behaviors. It holds the state and logic; body.py provides the callback to
actually show lines.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable


@dataclass
class CareState:
    continuous_work_start: float = field(default_factory=time.time)
    last_away_at: float = 0.0
    was_away: bool = False
    care_3h_announced: bool = False
    care_late_night_announced: bool = False
    care_welcome_back_announced_at: float = 0.0
    session_max_focus_seconds: float = 0.0
    achievement_2h_focus_announced: bool = False
    session_window_switches: int = 0
    achievement_rapid_switch_announced: bool = False


# ── greeting pools ──────────────────────────────────────────────

MORNING_ZH = [
    "早。新的一天，TODO 又回到了它们最喜欢的状态。",
    "早安。昨天的进度条还在原地等你。",
    "早上好。今天的你看起来比昨天更有拖延潜力。",
    "早。桌面已就位，等待人类做出第一个错误决定。",
    "早安。夹夹已自动恢复上班状态——也就是盯着你。",
    "新的一天。计划列表正在假装自己会被执行。",
]
AFTERNOON_ZH = [
    "下午好。你错过了 TODO 的早操。",
    "下午好。夹夹值了一上午的班，你现在才来。",
    "午安。上午的效率已经成为历史遗憾。",
    "下午了。夹夹独自守了半天桌面，没有怨言，只有记录。",
]
LONG_ABSENCE_ZH = [
    "你消失了 {n} 天。桌面灰尘开始形成小型文明了。",
    "距离上次见面已经 {n} 天。夹夹以为被裁员了。",
    "{n} 天没见。TODO 已经学会了自我安慰。",
]

MORNING_EN = [
    "Morning! Another day of watching you work.",
    "Good morning. Yesterday's progress bar is still waiting.",
    "Morning. The desktop is ready. Your willpower: TBD.",
]
AFTERNOON_EN = [
    "Afternoon! How's your productivity? (Rhetorical.)",
    "Good afternoon. You missed the TODO morning roll call.",
    "Afternoon. The paperclip has been on duty since dawn.",
]
LONG_ABSENCE_EN = [
    "You vanished for {n} days. The desktop is developing archaeology vibes.",
    "It's been {n} days. I thought I was laid off.",
    "{n} days gone. The TODOs learned self-soothing.",
]

CARE_3H_ZH = [
    "你已经连续工作三小时了。水喝了吗？",
    "三小时了。人类的续航不如夹夹，适时充电。",
    "连续工作三小时。起来活动一下，夹夹替你看着屏幕。",
]
WELCOME_BACK_ZH = [
    "欢迎回来。桌面没有发生任何值得汇报的事件。",
    "你回来了。夹夹刚数完桌面上的像素，一共很多。",
    "欢迎回来。夹夹在你走后进行了一次不存在的巡逻。",
]
LATE_NIGHT_ZH = [
    "现在是凌晨了。明天也是一天。",
    "夜深了。屏幕的蓝光比你的眼圈更亮。",
    "深夜了。夹夹建议你关机，但不敢强制执行。",
]

CARE_3H_EN = [
    "Three hours straight. Maybe drink some water?",
    "Three hours of work. Even paperclips rest. Well, no. But you should.",
    "Three hours. Time for a break. I'll watch the screen for you.",
]
WELCOME_BACK_EN = [
    "Welcome back. Nothing reportable happened on the desktop.",
    "You're back. I just finished counting the pixels. Many.",
    "Welcome back. I conducted a non-existent patrol while you were gone.",
]
LATE_NIGHT_EN = [
    "It's past midnight. Tomorrow is also a day.",
    "Late night. The screen glow is brighter than your eye circles.",
    "It's late. I'd recommend shutting down, but I can't enforce it.",
]

FOCUS_2H_ZH = [
    "你连续专注了两小时。我拿不到的成就。",
    "两小时不动窗口。你是人类还是定时任务？",
    "连续专注两小时。夹夹颁发虚拟奖杯一座。",
]
RAPID_SWITCH_ZH = [
    "窗口切换速度新纪录。鼠标在申请工伤。",
    "一分钟切了 12 次窗口。这不是多任务，这是量子态。",
]
FOCUS_2H_EN = [
    "Two hours of focus. An achievement I can't unlock.",
    "Two hours without switching. Are you human or a cron job?",
    "Two-hour focus streak. Virtual trophy awarded.",
]
RAPID_SWITCH_EN = [
    "New window-switching record. The mouse is filing for injury.",
    "12 switches in a minute. That's not multitasking, that's quantum state.",
]


def _pool(zh: list[str], en: list[str], language: str) -> list[str]:
    return en if language == "en" else zh


class CareEngine:
    """Proactive care logic, decoupled from tkinter."""

    def __init__(self, language: str = "zh-CN") -> None:
        self.language = language
        self.state = CareState()

    def daily_greeting(self, last_seen: str, today_str: str) -> tuple[str, str, str] | None:
        """Returns (line, mood, action) or None if no greeting needed."""
        if last_seen == today_str:
            return None
        if last_seen:
            try:
                last_date = date.fromisoformat(last_seen)
                days_gone = (date.today() - last_date).days
            except (ValueError, TypeError):
                days_gone = 1
        else:
            days_gone = 0
        if days_gone > 2:
            pool = _pool(LONG_ABSENCE_ZH, LONG_ABSENCE_EN, self.language)
            return random.choice(pool).format(n=days_gone), "suspicious", "startled_pop"
        if datetime.now().hour < 12:
            pool = _pool(MORNING_ZH, MORNING_EN, self.language)
            return random.choice(pool), "smirk", "happy_bounce"
        pool = _pool(AFTERNOON_ZH, AFTERNOON_EN, self.language)
        return random.choice(pool), "smirk", "nod"

    def care_3h_line(self) -> str:
        return random.choice(_pool(CARE_3H_ZH, CARE_3H_EN, self.language))

    def welcome_back_line(self) -> str:
        return random.choice(_pool(WELCOME_BACK_ZH, WELCOME_BACK_EN, self.language))

    def late_night_line(self) -> str:
        return random.choice(_pool(LATE_NIGHT_ZH, LATE_NIGHT_EN, self.language))

    def focus_2h_line(self) -> str:
        return random.choice(_pool(FOCUS_2H_ZH, FOCUS_2H_EN, self.language))

    def rapid_switch_line(self) -> str:
        return random.choice(_pool(RAPID_SWITCH_ZH, RAPID_SWITCH_EN, self.language))
