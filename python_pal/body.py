from __future__ import annotations

import ctypes
from pathlib import Path
import json
import math
import queue
import random
import re
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from .activity import ActivityPolicy, policy_for_frequency
from .actions import ACTION_LABELS, ACTION_MENU_GROUPS
from .animation_resolver import AnimationResolver, ResolvedAnimation
from .animation_manifest import load_animation_manifest
from .animation_player import AnimationCallbacks, AnimationPlayer
from .brain_ollama import OllamaBrain
from .chat import ChatSession, PalChatBrain, build_chat_context, detect_chat_command, local_status_reaction
from .decorations import DecorationDefinition, load_decoration_manifest
from .mood import MoodEngine, FREQUENCY_PRESETS, FREQUENCY_DEFAULT
from .claude_status import ClaudeOverview, ClaudeSession, ClaudeStatusMonitor
from .codex_status import CodexStatus, CodexStatusMonitor
from .codex_usage import CodexUsageMonitor, CodexUsageStatus, format_reset_in
from .decision import DecisionEngine
from .ears import Ears
from .event_log import EventLog
from .eyes import Eyes
from .hardware_status import HardwareSnapshot, HardwareStatusMonitor
from .performance import PERFORMANCE_PHRASES, phrase_for_reaction
from .soul import Soul
from .state import PalState, Reaction
from .world import MoodSnapshot, WorldState


TRANSPARENT = "#ff00ff"
WIRE = "#aeaeae"
EYE_WHITE = "#ececec"
BROW = "#402a32"
PUPIL = "#402a32"
PAL_SCALE = 0.25
PAL_SOURCE_WIDTH = 316
PAL_SOURCE_HEIGHT = 550
PAL_WIDTH = round(PAL_SOURCE_WIDTH * PAL_SCALE)
PAL_HEIGHT = round(PAL_SOURCE_HEIGHT * PAL_SCALE)
PAL_PAD_X = 54
PAL_PAD_Y = 76
PAL_CANVAS_WIDTH = PAL_WIDTH + PAL_PAD_X * 2
PAL_CANVAS_HEIGHT = PAL_HEIGHT + PAL_PAD_Y * 2
PAL_CENTER_X = PAL_PAD_X + PAL_WIDTH / 2
PAL_SCALE_CENTER_Y = PAL_PAD_Y + PAL_HEIGHT * 0.55
PAL_LOOK_CENTER_X = PAL_PAD_X + PAL_WIDTH * 0.48
PAL_LOOK_CENTER_Y = PAL_PAD_Y + PAL_HEIGHT * 0.32
BUBBLE_WIDTH = 260
BUBBLE_MIN_WIDTH = 150
BUBBLE_MIN_HEIGHT = 72
BUBBLE_MAX_LINES = 5
BUBBLE_PADDING_X = 14
BUBBLE_PADDING_Y = 10
BUBBLE_GAP = 8
BUBBLE_PAGE_GAP_MS = 140
BUBBLE_PAGE_MIN_MS = 2600
BUBBLE_PAGE_MAX_MS = 8200
BUBBLE_PAGE_CHAR_MS = 92
BUBBLE_FONT = ("Microsoft YaHei UI", 11)
THOUGHT_FONT = ("Microsoft YaHei UI", 10, "italic")
BubbleStyle = tuple[bool, str, str, str]
BUBBLE_STYLES: dict[str, BubbleStyle] = {
    "speech": (False, "#fdfdfd", "#d4dee8", "#202932"),
    "thought": (True, "#f7f5fb", "#c9c2d7", "#33293a"),
    "codex_speech": (False, "#eefbf5", "#10a37f", "#123d32"),
    "codex_thought": (True, "#eefbf5", "#10a37f", "#123d32"),
    "claude_speech": (False, "#fff2e8", "#d97757", "#442414"),
    "claude_thought": (True, "#fff2e8", "#d97757", "#442414"),
    "hardware_thought": (True, "#fff4f4", "#d86b6b", "#4b2424"),
    "hardware_speech": (False, "#fff4f4", "#d86b6b", "#4b2424"),
    "usage_thought": (True, "#f2f7ff", "#4f7ecf", "#20304f"),
    "usage_speech": (False, "#f2f7ff", "#4f7ecf", "#20304f"),
}
CODEX_USAGE_COLORS = {
    "normal": "#10a37f",
    "watch": "#4f7ecf",
    "low": "#e4a03b",
    "critical": "#d65b4a",
    "reset_soon": "#10a37f",
    "refilled": "#10a37f",
    "unavailable": "#a8a8a8",
}
STATUS_BADGES: dict[str, tuple[str, str, str]] = {
    "codex_waiting": ("C", "#f0b429", "circle"),
    "hardware_hot": ("°", "#d86b6b", "circle"),
    "usage_low": ("%", "#e4a03b", "circle"),
    "focus_mode": ("F", "#7c8db5", "circle"),
    "error": ("!", "#d65b4a", "triangle"),
    "sleeping": ("Z", "#a8a8a8", "circle"),
}
HARDWARE_TINTS = {
    "normal": WIRE,
    "unavailable": WIRE,
    "busy": "#aeb6c5",
    "cooling": "#b8b8b8",
    "warm": "#caa0a0",
    "hot": "#d86b6b",
    "overloaded": "#bd4343",
}
BLINK_MIN_MS = 3200
BLINK_MAX_MS = 8200
LOOK_MIN_MS = 1200
LOOK_MAX_MS = 3600
MOUSE_FOLLOW_TICK_MS = 75
MOUSE_FOLLOW_COOLDOWN_MS = 1800
MOUSE_FOLLOW_NEAR_RADIUS = 150
GLOBAL_MOUSE_POLL_MS = 24
PAL_HIT_INSET = 6
CODEX_STATUS_POLL_MS = 2500
CODEX_USAGE_POLL_MS = 60_000
CLAUDE_STATUS_POLL_MS = 8000
HARDWARE_STATUS_POLL_MS = 5000
LERP_TICK_MS = 18
VISION_REFRESH_MS = 45_000
AMBIENT_MIN_MS = 18_000
AMBIENT_MAX_MS = 45_000
AMBIENT_COOLDOWN_SECONDS = 50
LOW_STIMULUS_IDLE_ACTIONS = ("blink", "peek", "nod", "micro_soften")
COMMON_IDLE_ACTIONS = ("blink", "peek", "scan", "thinking_tilt", "nod", "wiggle")
MID_IDLE_ACTIONS = ("stretch", "sleepy_sag", "smug_sway", "patrol", "mini_hop_shift")
RARE_IDLE_ACTIONS = ("twirl", "flop", "hide", "dance", "relocate_hop")
LARGE_IDLE_ACTIONS = {"jump", "flop", "dance", "twirl", "stretch", "sleepy_sag", "sulk", "hide", "celebrate"}
MOVE_IDLE_ACTIONS = {"twist_scoot", "mini_hop_shift", "relocate_hop", "roast_and_scoot", "retreat_to_corner", "drop_in"}
BODY_START = (124.0, 267.226)
BODY_CURVES = (
    ((124.0, 267.226), (113.008, 384.271), (158.0, 407.226)),
    ((182.5, 419.726), (210.918, 399.226), (206.0, 369.226)),
    ((200.18, 333.727), (196.0, 265.226), (206.0, 202.226)),
    ((214.622, 147.907), (214.983, 149.226), (231.5, 96.7265)),
    ((248.017, 44.2265), (201.0, -1.42701), (148.0, 20.7265)),
    ((72.5, 52.2846), (42.7789, 215.226), (53.4999, 312.226)),
    ((67.2106, 436.276), (101.591, 483.694), (130.0, 509.226)),
    ((169.5, 544.726), (222.497, 545.135), (254.0, 500.226)),
    ((277.5, 466.726), (254.0, 374.226), (257.5, 322.226)),
    ((259.216, 296.726), (275.5, 267.226), (301.0, 250.726)),
)
LEFT_BROW_START = (64.0, 56.7265)
LEFT_BROW_CURVES = (
    ((64.0, 56.7265), (81.7087, 52.8505), (93.2292, 52.7265)),
    ((105.734, 52.5919), (125.0, 56.7265), (125.0, 56.7265)),
)
RIGHT_BROW_START = (204.0, 92.7265)
RIGHT_BROW_CURVES = (
    ((204.0, 92.7265), (219.1, 90.4067), (228.302, 92.7265)),
    ((242.828, 96.388), (259.0, 115.726), (259.0, 115.726)),
)
ActionFrame = tuple[float, float, float, float, int]
ActionFrames = tuple[ActionFrame, ...]


class _WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
ACTION_FRAMES: dict[str, ActionFrames] = {
    # 卡通跳跃：蓄力蹲→弹射→滞空→落地压扁→回弹 (750ms)
    "jump": (
        (0, 8, 1.22, 0.72, 160),
        (0, -40, 0.82, 1.28, 100),
        (0, -42, 0.92, 1.10, 160),
        (0, -10, 1.04, 0.96, 90),
        (0, 6, 1.28, 0.70, 80),
        (0, -4, 0.94, 1.08, 80),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 瘫倒：极快砸平→超长躺平→缓慢爬起
    "flop": (
        (0, 10, 1.12, 0.80, 50),
        (0, 32, 1.50, 0.35, 80),
        (0, 34, 1.52, 0.32, 500),
        (0, 20, 1.20, 0.60, 180),
        (0, 8, 1.08, 0.88, 120),
        (0, 0, 1.0, 1.0, 100),
    ),
    # 跳舞：固定节拍左右跳，中间有过渡帧 (740ms)
    "dance": (
        (-10, -8, 1.06, 0.94, 120),
        (0, -2, 1.0, 1.0, 60),
        (10, -8, 0.94, 1.06, 120),
        (0, -2, 1.0, 1.0, 60),
        (-8, -10, 1.04, 0.96, 120),
        (0, -2, 1.0, 1.0, 60),
        (8, -10, 0.96, 1.04, 120),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 转身：水平翻转，翻转时短暂定格 (580ms)
    "twirl": (
        (0, -2, 0.42, 1.08, 85),
        (0, -3, -0.42, 1.08, 85),
        (0, -3, -1.0, 1.0, 150),
        (0, -2, -0.42, 1.08, 85),
        (0, -1, 0.42, 1.08, 85),
        (0, 0, 1.0, 1.0, 90),
    ),
    # 伸懒腰：慢压→大拉伸→享受停顿→弹回 (1140ms)
    "stretch": (
        (0, 8, 1.14, 0.82, 180),
        (0, -4, 0.84, 1.30, 320),
        (0, -2, 0.88, 1.24, 350),
        (0, 4, 1.10, 0.88, 120),
        (0, -1, 0.96, 1.04, 90),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 颤抖：快速递减振幅+轻微纵向抖动 (360ms)
    "shake": (
        (-14, -2, 1.06, 0.96, 40),
        (14, 2, 0.94, 1.06, 40),
        (-10, -1, 1.04, 0.97, 40),
        (10, 1, 0.96, 1.04, 40),
        (-6, -1, 1.02, 0.98, 45),
        (6, 1, 0.98, 1.02, 45),
        (-3, 0, 1.01, 0.99, 50),
        (0, 0, 1.0, 1.0, 60),
    ),
    # 开心弹跳：无蓄力直接双弹，轻快但看得清 (320ms)
    "happy_bounce": (
        (0, -18, 0.94, 1.08, 100),
        (0, -4, 1.06, 0.94, 70),
        (0, -10, 0.97, 1.04, 90),
        (0, 0, 1.0, 1.0, 60),
    ),
    # 点头：纯纵向两次，节奏从容 (410ms)
    "nod": (
        (0, 10, 1.04, 0.92, 120),
        (0, 2, 1.0, 1.0, 80),
        (0, 8, 1.03, 0.94, 120),
        (0, 0, 1.0, 1.0, 90),
    ),
    # 歪头想事：单次歪头→长停顿→慢回正
    "thinking_tilt": (
        (-6, 0, 0.92, 1.06, 180),
        (-8, 2, 0.90, 1.08, 400),
        (-4, 1, 0.95, 1.04, 150),
        (0, 0, 1.0, 1.0, 100),
    ),
    # 打盹：渐进下沉→猛醒→再沉→又醒
    "sleepy_sag": (
        (0, 4, 0.98, 0.96, 200),
        (0, 12, 0.96, 0.88, 250),
        (0, 20, 1.04, 0.78, 300),
        (0, 6, 0.96, 0.96, 80),
        (0, 14, 1.02, 0.84, 250),
        (0, 4, 0.98, 0.94, 100),
        (0, 0, 1.0, 1.0, 120),
    ),
    # 受惊膨胀：瞬间均匀膨大→定格→慢缩回
    "startled_pop": (
        (0, -6, 1.30, 1.30, 40),
        (0, -8, 1.28, 1.28, 200),
        (0, -4, 1.14, 1.14, 120),
        (0, -2, 1.06, 1.06, 100),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 得意慢摆：不对称，delay 加倍
    "smug_sway": (
        (-10, 2, 0.96, 1.02, 200),
        (-6, 0, 0.98, 1.01, 180),
        (8, -1, 1.02, 0.99, 200),
        (4, 0, 1.01, 1.0, 160),
        (0, 0, 1.0, 1.0, 140),
    ),
    # 委屈：缩向一侧+微颤+长停留
    "sulk": (
        (-3, 6, 0.94, 0.92, 120),
        (-5, 14, 0.88, 0.82, 150),
        (-6, 16, 0.86, 0.80, 100),
        (-4, 14, 0.88, 0.82, 100),
        (-5, 15, 0.87, 0.81, 300),
        (-2, 8, 0.94, 0.92, 150),
        (0, 0, 1.0, 1.0, 120),
    ),
    # 躲藏：快速缩向右下→探头→又缩回→慢出来
    "hide": (
        (8, 12, 0.86, 0.82, 80),
        (14, 24, 0.62, 0.52, 100),
        (16, 30, 0.50, 0.40, 400),
        (12, 22, 0.70, 0.60, 150),
        (15, 28, 0.54, 0.44, 200),
        (8, 14, 0.80, 0.72, 140),
        (0, 0, 1.0, 1.0, 120),
    ),
    # 巡逻：匀速平移无缩放，端点停顿观察
    "patrol": (
        (-20, 0, 1.0, 1.0, 200),
        (-20, 0, 1.0, 1.0, 150),
        (0, 0, 1.0, 1.0, 140),
        (20, 0, 1.0, 1.0, 200),
        (20, 0, 1.0, 1.0, 150),
        (0, 0, 1.0, 1.0, 140),
    ),
    # 庆祝：跳高→空中左右扭→弹落 (700ms)
    "celebrate": (
        (0, 6, 1.20, 0.78, 90),
        (0, -35, 0.88, 1.16, 110),
        (-10, -32, 0.92, 1.08, 110),
        (10, -30, 1.08, 0.92, 110),
        (0, -8, 0.96, 1.04, 80),
        (0, 5, 1.16, 0.82, 70),
        (0, -3, 0.98, 1.02, 60),
        (0, 0, 1.0, 1.0, 70),
    ),
}

IDENTITY_STATE_CUES: dict[str, dict[str, object]] = {
    "default_pal": {"mood": "smirk", "action": "blink", "eyes": "round", "brows": "innocent", "hold_ms": 1800},
    "task_auditor": {"mood": "suspicious", "action": "thinking_tilt", "eyes": "side_eye", "brows": "judge", "hold_ms": 3200},
    "agent_supervisor": {"mood": "thinking", "action": "scan", "decoration": "status_dot", "eyes": "side_eye", "brows": "judge", "hold_ms": 4200},
    "thermal_technician": {"mood": "startled", "action": "shake", "decoration": "heat_puffs", "eyes": "round", "brows": "guilty", "hold_ms": 4800},
    "usage_accountant": {"mood": "focused", "action": "scan", "decoration": "usage_bar", "eyes": "side_eye", "brows": "soft", "hold_ms": 4400},
    "focus_companion": {"mood": "innocent", "action": "blink", "eyes": "soft", "brows": "soft", "hold_ms": 3600},
    "sleepy_clip": {"mood": "sleepy", "action": "sleepy_sag", "decoration": "z_symbol", "eyes": "soft", "brows": "sulk", "hold_ms": 6500},
    "bug_coroner": {"mood": "suspicious", "action": "scan", "decoration": "tiny_warning", "eyes": "side_eye", "brows": "judge", "hold_ms": 4600},
    "critic_clip": {"mood": "smirk", "action": "thinking_tilt", "decoration": "annotation_circle", "eyes": "side_eye", "brows": "judge", "hold_ms": 3600},
    "tab_warden": {"mood": "suspicious", "action": "patrol", "decoration": "tab_bar", "eyes": "side_eye", "brows": "judge", "hold_ms": 4400},
    "gremlin_clip": {"mood": "smug", "action": "smug_sway", "eyes": "side_eye", "brows": "proud", "hold_ms": 3600},
    "meltdown_clip": {"mood": "sulky", "action": "flop", "decoration": "tiny_warning", "eyes": "peek_up", "brows": "sulk", "hold_ms": 5200},
}

ACTION_DECORATION_CUES: dict[str, tuple[str, int]] = {
    "sleepy_sag": ("z_symbol", 4200),
}

_JITTER_DXY = 0.12
_JITTER_SCALE = 0.06
_JITTER_DELAY = 0.10


def _ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _breath_curve(phase: float) -> float:
    # 吸气快（0→0.35），呼气慢（0.35→0.75），末尾停顿（0.75→1.0）
    if phase < 0.35:
        t = phase / 0.35
        return math.sin(t * math.pi / 2)
    if phase < 0.75:
        t = (phase - 0.35) / 0.4
        return math.cos(t * math.pi / 2)
    return 0.0


def _jitter_frames(frames: ActionFrames) -> ActionFrames:
    result: list[ActionFrame] = []
    for i, (dx, dy, sx, sy, delay) in enumerate(frames):
        if i == len(frames) - 1:
            result.append((dx, dy, sx, sy, delay))
            continue
        jdx = dx * (1.0 + random.uniform(-_JITTER_DXY, _JITTER_DXY)) if dx else 0.0
        jdy = dy * (1.0 + random.uniform(-_JITTER_DXY, _JITTER_DXY)) if dy else 0.0
        jsx = 1.0 + (sx - 1.0) * (1.0 + random.uniform(-_JITTER_SCALE, _JITTER_SCALE))
        jsy = 1.0 + (sy - 1.0) * (1.0 + random.uniform(-_JITTER_SCALE, _JITTER_SCALE))
        jdelay = max(10, round(delay * (1.0 + random.uniform(-_JITTER_DELAY, _JITTER_DELAY))))
        result.append((jdx, jdy, jsx, jsy, jdelay))
    return tuple(result)


def _geometry_position(x: float, y: float) -> str:
    return f"+{round(x)}+{round(y)}"


def _geometry_with_size(width: float, height: float, x: float, y: float) -> str:
    return f"{round(width)}x{round(height)}{_geometry_position(x, y)}"


class PaperclipPalApp:
    def __init__(self, soul: Soul, project_root: Path) -> None:
        self.soul = soul
        self.project_root = project_root
        self.brain = OllamaBrain(soul, project_root=project_root)
        self.chat_brain = PalChatBrain(soul)
        self.chat_session = ChatSession()
        self.ears = Ears()
        self.eyes = Eyes(model=soul.vision_model)
        self.codex_status = CodexStatusMonitor(project_root / "codex_status.json")
        self.codex_usage = CodexUsageMonitor(project_root / "codex_usage_status.json")
        self.hardware_status = HardwareStatusMonitor()
        self.event_log = EventLog(project_root / "memory" / "event_log.jsonl")
        self.state = PalState()
        self.decision = DecisionEngine()
        self.animation_player = AnimationPlayer(load_animation_manifest(project_root / "python_pal" / "animations.yaml"))
        self.animation_resolver = AnimationResolver(set(self.animation_player.manifest.performances))
        self.decorations = load_decoration_manifest(project_root / "python_pal" / "decorations.yaml")
        self.queue: queue.Queue[Reaction] = queue.Queue()
        self.root = tk.Tk()
        self.root.title(soul.name)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)
        self.width = PAL_CANVAS_WIDTH
        self.height = PAL_CANVAS_HEIGHT
        self.canvas = tk.Canvas(
            self.root,
            width=self.width,
            height=self.height,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.bubble_root = tk.Toplevel(self.root)
        self.bubble_root.overrideredirect(True)
        self.bubble_root.attributes("-topmost", True)
        self.bubble_root.attributes("-transparentcolor", TRANSPARENT)
        self.bubble_root.configure(bg=TRANSPARENT)
        self.bubble_canvas = tk.Canvas(
            self.bubble_root,
            width=BUBBLE_WIDTH,
            height=BUBBLE_MIN_HEIGHT,
            bg=TRANSPARENT,
            highlightthickness=0,
            bd=0,
        )
        self.bubble_canvas.pack(fill="both", expand=True)
        self.bubble_root.withdraw()
        self._drag_start: tuple[int, int] | None = None
        self._drag_origin: tuple[int, int] | None = None
        self._dragging = False
        self._global_mouse_claimed = False
        self._global_left_down = False
        self._global_right_down = False
        self._user32 = _load_user32()
        self._bob_phase = 0.0
        self._bob_y = 0.0
        self._bob_x = 0.0
        self._anim_tick = 0
        self._breath_depth = 2.2
        self._pupil_bounds: dict[int, tuple[float, float, float, float]] = {}
        self._pupil_look = (0.0, 0.0)
        self._pupil_size_scale = 1.0
        self._brow_base_coords: dict[int, tuple[float, ...]] = {}
        self._is_blinking = False
        self._mouse_follow_after: str | None = None
        self._mouse_follow_until = 0.0
        self._mouse_follow_cooldown_until = 0.0
        self._pal_scale = (1.0, 1.0)
        self._rebound_after: str | None = None
        self._action_offset = (0.0, 0.0)
        self._large_action_after: str | None = None
        self._large_action_running = False
        self._window_move_after: str | None = None
        self._window_move_running = False
        self._brain_wait_after: str | None = None
        self._brain_wait_step = 0
        self._chat_wait_after: str | None = None
        self._chat_wait_step = 0
        self._chat_wait_started_at = 0.0
        self._bubble_items: list[int] = []
        self._bubble_after: str | None = None
        self._thought_dot_items: list[int] = []
        self._thought_dot_base: list[tuple[float, float, float]] = []
        self._thought_dot_phase = 0
        self._thought_dot_after: str | None = None
        self._usage_badge_items: list[int] = []
        self._status_badge_items: list[int] = []
        self._status_badge_after: str | None = None
        self._status_badge_phase = 0
        self._decoration_items: dict[str, list[int]] = {"identity": [], "state": [], "temporary": []}
        self._active_identity_id = ""
        self._active_identity_addons: tuple[str, ...] = ()
        self._decoration_after: list[str] = []
        self._delayed_decoration_after: list[str] = []
        self._demo_after: list[str] = []
        self._chat_window: tk.Toplevel | None = None
        self._chat_entry: tk.Entry | None = None
        self._chat_thread: threading.Thread | None = None
        self._last_chat_context_debug = ""
        self._last_codex_status_event = ""
        self._last_codex_status: CodexStatus = CodexStatus()
        self._logged_codex_status_event = ""
        self._last_codex_usage_event = ""
        self._last_codex_usage_status: CodexUsageStatus = CodexUsageStatus()
        self._logged_codex_usage_event = ""
        self._last_codex_usage_announcement_at = 0.0
        self._last_hardware_status_event = ""
        self._last_hardware_status: HardwareSnapshot = HardwareSnapshot()
        self._logged_hardware_status_event = ""
        self._last_hardware_announcement_at = 0.0
        self._hardware_tint_level = "normal"
        self._hardware_tint_after: str | None = None
        self._recent_codex_status_fragments: list[str] = []
        self._brain_thread: threading.Thread | None = None
        self._line_bank_thread: threading.Thread | None = None
        self._vision_thread: threading.Thread | None = None
        self.claude_monitor = ClaudeStatusMonitor()
        self._last_claude_event = ""
        self._last_claude_alive_pids: set[int] = set()
        self._last_claude_sessions_by_pid: dict[int, ClaudeSession] = {}
        self._recent_claude_status_fragments: list[str] = []
        self._performance_after: list[str] = []
        self._expression_after: list[str] = []
        self._last_animation_debug = "not played yet"
        self._last_idle_animation_debug = "idle animation not selected yet"
        self._recent_idle_actions: list[str] = []
        self._last_large_idle_action_at = 0.0
        self._last_move_idle_action_at = 0.0
        self._last_identity_idle_action_at = 0.0
        self.mood = MoodEngine()
        initial_frequency = self._load_frequency_setting()
        self.mood.set_frequency(initial_frequency)
        self._freq_var = tk.StringVar(value=initial_frequency)
        self._identity_var = tk.StringVar(value=self._load_identity_setting())
        self._focus_var = tk.BooleanVar(value=False)
        self._quiet_until = 0.0
        self._micro_after: str | None = None
        self._companion_after: str | None = None
        self._place_initially()
        self._hide_from_taskbar()
        self._draw_pal()
        self._refresh_identity_decorations()
        self._bind_events()
        self._install_menu()
        self.root.after(50, self._animate)
        self.root.after(120, self._poll_global_mouse)
        self.root.after(100, self._poll_brain)
        self.root.after(1500, self._poll_codex_status)
        self.root.after(6000, self._poll_codex_usage)
        self.root.after(3500, self._poll_claude_status)
        self.root.after(4200, self._poll_hardware_status)
        self._schedule_blink()
        self._schedule_look()
        self._schedule_idle(first=True)
        self._schedule_ambient(first=True)
        self.root.after(5000, self._maintain_line_bank)
        self.root.after(8000, self._refresh_eyes)
        self.root.after(2000, self._schedule_micro)
        self.root.after(3000, self._schedule_companion)
        self.root.after(650, lambda: self.show_bubble("你看起来很忙。主要是在避免开始。", 5200))

    def run(self) -> None:
        self.root.mainloop()

    def _place_initially(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(40, round(screen_w - PAL_PAD_X - PAL_WIDTH - 84))
        y = max(40, round(screen_h - PAL_PAD_Y - PAL_HEIGHT - 84))
        self.root.geometry(_geometry_with_size(self.width, self.height, x, y))

    def _desktop_bounds(self) -> tuple[int, int, int, int]:
        if self._user32 and self.root.tk.call("tk", "windowingsystem") == "win32":
            try:
                left = int(self._user32.GetSystemMetrics(76))
                top = int(self._user32.GetSystemMetrics(77))
                width = int(self._user32.GetSystemMetrics(78))
                height = int(self._user32.GetSystemMetrics(79))
                if width > 0 and height > 0:
                    return (left, top, left + width, top + height)
            except Exception:
                pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _hide_from_taskbar(self) -> None:
        if self.root.tk.call("tk", "windowingsystem") != "win32":
            return
        self._hide_window_from_taskbar(self.root)
        self._hide_window_from_taskbar(self.bubble_root)

    def _hide_window_from_taskbar(self, window: tk.Tk | tk.Toplevel) -> None:
        try:
            import ctypes

            window.update_idletasks()
            hwnd = window.winfo_id()
            gwl_exstyle = -20
            ws_ex_toolwindow = 0x00000080
            ws_ex_appwindow = 0x00040000
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, gwl_exstyle)
            style = (style | ws_ex_toolwindow) & ~ws_ex_appwindow
            user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        except Exception:
            return

    def _draw_pal(self) -> None:
        c = self.canvas
        c.create_line(
            *_scale_coords(_path_coords(BODY_START, BODY_CURVES)), smooth=False,
            width=30 * PAL_SCALE, fill=WIRE, capstyle=tk.ROUND,
            joinstyle=tk.ROUND, tags=("pal", "wire"),
        )
        c.create_oval(*_oval_bounds(57, 154.726, 57), fill=EYE_WHITE, outline="", tags=("pal", "eye"))
        c.create_oval(*_oval_bounds(213, 195.226, 57, 56.5), fill=EYE_WHITE, outline="", tags=("pal", "eye"))
        left_pupil_bounds = _oval_bounds(64, 154.726, 39)
        right_pupil_bounds = _oval_bounds(203, 192.726, 39)
        self.left_pupil = c.create_oval(*left_pupil_bounds, fill=PUPIL, outline="", tags=("pal", "pupil"))
        self.right_pupil = c.create_oval(*right_pupil_bounds, fill=PUPIL, outline="", tags=("pal", "pupil"))
        self._pupil_bounds = {
            self.left_pupil: left_pupil_bounds,
            self.right_pupil: right_pupil_bounds,
        }
        left_brow_coords = tuple(_scale_coords(_path_coords(LEFT_BROW_START, LEFT_BROW_CURVES)))
        right_brow_coords = tuple(_scale_coords(_path_coords(RIGHT_BROW_START, RIGHT_BROW_CURVES)))
        self.left_brow = c.create_line(
            *left_brow_coords, smooth=False,
            width=30 * PAL_SCALE, fill=BROW, capstyle=tk.ROUND,
            tags=("pal", "brow"),
        )
        self.right_brow = c.create_line(
            *right_brow_coords, smooth=False,
            width=30 * PAL_SCALE, fill=BROW, capstyle=tk.ROUND,
            tags=("pal", "brow"),
        )
        self._brow_base_coords = {
            self.left_brow: left_brow_coords,
            self.right_brow: right_brow_coords,
        }
        self._apply_hardware_tint()

    def _reset_pal_geometry(self) -> None:
        look = self._pupil_look
        self._clear_decorations()
        self.canvas.delete("pal")
        self._pupil_bounds.clear()
        self._pal_scale = (1.0, 1.0)
        self._action_offset = (0.0, 0.0)
        self._bob_x = 0.0
        self._bob_y = 0.0
        self._draw_pal()
        if self._active_identity_addons:
            self._set_decorations(self._active_identity_addons, lifetime="identity")
        self.canvas.tag_raise("decoration")
        self._pupil_look = look
        self._set_pupil_pose(*look, blink_scale=1.0)
        self._apply_hardware_tint()

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._poke(force=True))

    def _install_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Say something", command=lambda: self._ask_brain("manual"))
        self.menu.add_command(label="Talk to 夹夹", command=self._open_chat_input)
        self.menu.add_command(label="Boredom line", command=lambda: self._ask_brain("bored"))
        self.menu.add_command(label="Poke", command=lambda: self._poke(force=True))
        action_menu = tk.Menu(self.menu, tearoff=False)
        for group_label, action_ids in ACTION_MENU_GROUPS:
            group_menu = tk.Menu(action_menu, tearoff=False)
            for action_id in action_ids:
                group_menu.add_command(
                    label=ACTION_LABELS[action_id],
                    command=lambda action_id=action_id: self._perform_action(action_id),
                )
            action_menu.add_cascade(label=group_label, menu=group_menu)
        self.menu.add_cascade(label="Actions", menu=action_menu)
        preview_menu = tk.Menu(self.menu, tearoff=False)
        for performance_id in sorted(self.animation_player.manifest.performances):
            preview_menu.add_command(
                label=performance_id,
                command=lambda performance_id=performance_id: self._preview_performance(performance_id),
            )
        self.menu.add_cascade(label="Animation Preview", menu=preview_menu)
        identity_menu = tk.Menu(self.menu, tearoff=False)
        identity_menu.add_radiobutton(
            label="Auto",
            variable=self._identity_var,
            value="auto",
            command=lambda: self._set_identity("auto"),
        )
        for pack in self.brain.identities.menu_packs():
            identity_menu.add_radiobutton(
                label=pack.display_name,
                variable=self._identity_var,
                value=pack.id,
                command=lambda identity_id=pack.id: self._set_identity(identity_id),
            )
        self.menu.add_cascade(label="Identity", menu=identity_menu)
        self.menu.add_command(label="Codex status", command=self._show_codex_status)
        self.menu.add_command(label="Codex usage", command=self._show_codex_usage)
        self.menu.add_command(label="Claude 状态", command=self._show_claude_status)
        self.menu.add_command(label="Hardware status", command=self._show_hardware_status)
        self.menu.add_command(label="Last events", command=self._show_last_events)
        self.menu.add_command(label="Morning digest", command=self._show_morning_digest)
        self.menu.add_command(label="Scripted demo", command=self._run_scripted_demo)
        self.menu.add_command(label="Debug last decision", command=self._show_last_decision_debug)
        self.menu.add_command(label="Last chat context", command=self._show_last_chat_context)
        self.menu.add_command(label="Debug animation", command=self._show_last_animation_debug)
        self.menu.add_command(label="Debug identity", command=self._show_identity_debug)
        freq_menu = tk.Menu(self.menu, tearoff=False)
        for label, _mult in FREQUENCY_PRESETS:
            freq_menu.add_radiobutton(
                label=label,
                variable=self._freq_var,
                value=label,
                command=lambda k=label: self._set_frequency(k),
            )
        self.menu.add_cascade(label="活跃度", menu=freq_menu)
        self.menu.add_separator()
        self.menu.add_command(label="Quiet 30 min", command=lambda: self._quiet_for(30 * 60))
        self.menu.add_checkbutton(label="Focus mode", variable=self._focus_var, command=self._toggle_focus_mode)
        self.menu.add_command(label="Summon / resume", command=self._resume_auto_reactions)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.root.destroy)

    def _show_context_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _open_chat_input(self) -> None:
        if self._chat_window and self._chat_window.winfo_exists():
            self._chat_window.lift()
            if self._chat_entry:
                self._chat_entry.focus_set()
            return

        self._perform_action("thinking_tilt")
        self._start_mouse_follow(1100, force=True)
        window = tk.Toplevel(self.root)
        self._chat_window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg="#d4dee8")
        window.bind("<Escape>", lambda _event: self._close_chat_input())
        window.protocol("WM_DELETE_WINDOW", self._close_chat_input)

        shell = tk.Frame(window, bg="#d4dee8", padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        inner = tk.Frame(shell, bg="#fdfdfd", padx=9, pady=8)
        inner.pack(fill="both", expand=True)
        entry = tk.Entry(
            inner,
            width=34,
            relief="flat",
            bd=0,
            bg="#fdfdfd",
            fg="#202932",
            insertbackground="#202932",
            font=("Microsoft YaHei UI", 10),
        )
        entry.pack(fill="x")
        entry.bind("<Return>", self._submit_chat_from_entry)
        self._chat_entry = entry
        self._position_chat_input()
        self._hide_window_from_taskbar(window)
        window.deiconify()
        window.lift()
        entry.focus_set()

    def _position_chat_input(self) -> None:
        if not self._chat_window:
            return
        self.root.update_idletasks()
        width = 286
        height = 38
        left, top, right, bottom = self._desktop_bounds()
        x = self.root.winfo_x() + PAL_CENTER_X - width / 2
        y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + 12
        x = min(max(left + 8, x), max(left + 8, right - width - 8))
        if y + height > bottom - 8:
            y = self.root.winfo_y() + PAL_PAD_Y - height - 10
        y = min(max(top + 8, y), max(top + 8, bottom - height - 8))
        self._chat_window.geometry(_geometry_with_size(width, height, x, y))

    def _submit_chat_from_entry(self, _event: tk.Event | None = None) -> None:
        if not self._chat_entry:
            return
        message = self._chat_entry.get().strip()
        self._close_chat_input()
        self._handle_chat_message(message)

    def _close_chat_input(self) -> None:
        if self._chat_window:
            try:
                self._chat_window.destroy()
            except tk.TclError:
                pass
        self._chat_window = None
        self._chat_entry = None

    def _handle_chat_message(self, message: str) -> None:
        message = " ".join(message.split())
        if not message:
            return
        self.chat_session.add("user", message)
        context = self._build_chat_context()
        command = detect_chat_command(message)
        if self._handle_chat_command(command, context):
            return
        if self.state.brain_busy:
            self.show_bubble("我还在想上一句。一个小文具同时多线程，听起来就很危险。", milliseconds=4200, kind="thought")
            self._perform_action("thinking_tilt")
            return

        self.state.brain_busy = True
        self._start_chat_wait_feedback()
        history = self.chat_session.history()

        def worker() -> None:
            reaction = self.chat_brain.respond(message, context, history)
            reaction.event = reaction.event or "chat"
            if reaction.line:
                self.chat_session.add("assistant", reaction.line)
            self.queue.put(reaction)

        self._chat_thread = threading.Thread(target=worker, daemon=True)
        self._chat_thread.start()

    def _handle_chat_command(self, command: str, context: dict[str, object]) -> bool:
        if not command:
            return False
        if command == "quiet_30m":
            self._quiet_for(30 * 60)
            self.chat_session.add("assistant", "好，我折起来 30 分钟。")
            return True
        if command == "focus_on":
            if not self._focus_var.get():
                self._focus_var.set(True)
                self._toggle_focus_mode()
                self.chat_session.add("assistant", "专注模式开启。")
                return True
            reaction = Reaction(True, "已经在专注模式了。夹夹正在低存在感地盯着。", "focused", "blink", "thought", "quiet_companion", event="chat_focus_on")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command == "focus_off":
            if self._focus_var.get():
                self._focus_var.set(False)
                self._toggle_focus_mode()
                self.chat_session.add("assistant", "专注模式关闭。")
                return True
            reaction = Reaction(True, "专注模式本来就没开。夹夹只是看起来很克制。", "innocent", "blink", "thought", "quiet_companion", event="chat_focus_off")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command.startswith("frequency_"):
            label = {
                "frequency_quiet": "安静",
                "frequency_normal": "正常",
                "frequency_active": "活泼",
                "frequency_hyper": "多动",
            }[command]
            self._set_frequency(label)
            reaction = Reaction(
                True,
                f"活跃度切到 {label}。存在感已重新校准，听起来很正规。",
                "smirk" if label in {"活泼", "多动"} else "innocent",
                "happy_bounce" if label == "多动" else "blink",
                "thought",
                "tiny_celebrate" if label == "多动" else "quiet_companion",
                event=f"chat_{command}",
            )
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command == "morning_digest":
            line = self.event_log.digest(mark_read=False)
            reaction = Reaction(True, line, "thinking", "scan", "speech", "suspicious_observe", event="chat_morning_digest")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True

        reaction = local_status_reaction(command, context)
        if reaction:
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        return False

    def _build_chat_context(self) -> dict[str, object]:
        world = self._world_state()
        policy = self._activity_policy()
        context = build_chat_context(
            world,
            activity_mode=self._freq_var.get(),
            activity_tier=policy.tier,
            focus_mode=bool(self._focus_var.get()),
            quiet_remaining_seconds=self._quiet_remaining_seconds(),
        )
        self._last_chat_context_debug = json.dumps(context, ensure_ascii=False, indent=2)
        return context

    def _poll_global_mouse(self) -> None:
        if self._user32 is None:
            return
        cursor = _cursor_position(self._user32)
        if cursor is None:
            self.root.after(GLOBAL_MOUSE_POLL_MS, self._poll_global_mouse)
            return
        left_down = _button_down(self._user32, 0x01)
        right_down = _button_down(self._user32, 0x02)
        if left_down and not self._global_left_down:
            if self._drag_start is None and self._point_in_pal_hitbox(*cursor):
                self._global_mouse_claimed = True
                self._begin_drag(*cursor)
        elif left_down and self._global_mouse_claimed:
            self._continue_drag(*cursor)
        elif not left_down and self._global_left_down and self._global_mouse_claimed:
            self._finish_drag()
            self._global_mouse_claimed = False
        if right_down and not self._global_right_down and self._point_in_pal_hitbox(*cursor):
            self.menu.tk_popup(cursor[0], cursor[1])
        self._global_left_down = left_down
        self._global_right_down = right_down
        self.root.after(GLOBAL_MOUSE_POLL_MS, self._poll_global_mouse)

    def _point_in_pal_hitbox(self, x_root: int, y_root: int) -> bool:
        self.root.update_idletasks()
        left = self.root.winfo_x() + PAL_HIT_INSET
        top = self.root.winfo_y() + PAL_HIT_INSET
        right = self.root.winfo_x() + self.width - PAL_HIT_INSET
        bottom = self.root.winfo_y() + self.height - PAL_HIT_INSET
        return left <= x_root <= right and top <= y_root <= bottom

    def _set_frequency(self, key: str) -> None:
        self.mood.set_frequency(key)
        self._freq_var.set(key)
        self._save_frequency_setting(key)
        if self._micro_after:
            self.root.after_cancel(self._micro_after)
            self._micro_after = None
        if self._companion_after:
            self.root.after_cancel(self._companion_after)
            self._companion_after = None
        self._schedule_micro()
        self._schedule_companion()
        if key == "多动":
            self._perform_action("happy_bounce")
            self._start_mouse_follow(1400, force=True)

    def _set_identity(self, identity_id: str) -> None:
        key = self._valid_identity_id(identity_id)
        self._identity_var.set(key)
        self._save_identity_setting(key)
        if key == "auto":
            self._active_identity_id = ""
        self._refresh_identity_decorations()
        if key == "auto":
            self.show_bubble("身份切回 Auto。夹夹会按场景换班。", milliseconds=2600, kind="thought")
            return
        pack = self.brain.identities.get(key)
        self._play_identity_state_cue(pack.id, pack.default_mood)
        self.show_bubble(f"身份切到 {pack.display_name}。", milliseconds=2600, kind="thought")

    def _play_identity_state_cue(self, identity_id: str, default_mood: str = "idle") -> None:
        self._cancel_delayed_decoration_cues()
        cue = IDENTITY_STATE_CUES.get(identity_id, {})
        mood = str(cue.get("mood") or default_mood or "idle")
        self.state.mood = mood
        self.mood.push_mood(mood)
        self._last_identity_idle_action_at = 0.0
        action = str(cue.get("action") or "")
        action_delay = 0
        if action:
            self._play_idle_animation(action, source="identity_switch")
            action_delay = self._animation_duration_ms(action)
        hold_ms = int(cue.get("hold_ms") or 3200)
        expression_delay = max(80, action_delay + 40)
        decoration = str(cue.get("decoration") or "")
        if decoration:
            self._queue_temporary_decoration(decoration, hold_ms, delay_ms=expression_delay)
        eyes = str(cue.get("eyes") or "")
        brows = str(cue.get("brows") or "")
        if eyes or brows:
            def apply_expression() -> None:
                if brows:
                    self._set_brow_pose(brows)
                if eyes:
                    self._set_eye_pose(eyes)
                self._schedule_expression_reset(hold_ms)

            self._expression_after.append(self.root.after(expression_delay, apply_expression))

    def _current_identity_pack(self, reaction: Reaction | None = None):
        key = self._identity_var.get()
        if key and key != "auto":
            return self.brain.identities.get(key)
        if reaction is None and self._active_identity_id:
            return self.brain.identities.get(self._active_identity_id)
        return self.brain.identities.get(self._identity_id_for_reaction(reaction))

    def _identity_id_for_reaction(self, reaction: Reaction | None = None) -> str:
        if reaction and reaction.decision_reason:
            match = re.search(r"\bidentity=([a-z0-9_]+)", reaction.decision_reason)
            if match:
                return match.group(1)
        if self._focus_var.get() or self._quiet_remaining_seconds() > 0:
            return "focus_companion"
        if reaction:
            event = (reaction.event or "").lower()
            bubble = (reaction.bubble or "").lower()
            if event.startswith(("hardware_", "chat_hardware", "demo_hardware")) or bubble.startswith("hardware_"):
                return "thermal_technician"
            if event.startswith(("codex_usage", "chat_usage", "demo_usage")) or bubble.startswith("usage_"):
                return "usage_accountant"
            if event.startswith(("codex_", "claude_", "chat_codex", "chat_claude", "demo_codex")) or bubble.startswith(("codex_", "claude_")):
                return "agent_supervisor"
            if reaction.mood in {"sleepy", "sulky"}:
                return "sleepy_clip"
        return "default_pal"

    def _refresh_identity_decorations(self, reaction: Reaction | None = None) -> None:
        pack = self._current_identity_pack(reaction)
        self._active_identity_id = pack.id
        addons = tuple(addon for addon in pack.visual_addons if self.decorations.get(addon))
        self._active_identity_addons = addons
        self._set_decorations(addons, lifetime="identity")

    def _set_decorations(self, decoration_ids: tuple[str, ...] | list[str], lifetime: str = "identity") -> None:
        self._clear_decorations(lifetime)
        for decoration_id in decoration_ids:
            definition = self.decorations.get(decoration_id)
            if definition:
                self._draw_decoration(definition, lifetime=lifetime)

    def _show_temporary_decoration(self, decoration_id: str, milliseconds: int = 2600) -> None:
        definition = self.decorations.get(decoration_id)
        if not definition:
            return
        self._draw_decoration(definition, lifetime="temporary")
        self._decoration_after.append(self.root.after(milliseconds, lambda: self._clear_decorations("temporary")))

    def _queue_temporary_decoration(self, decoration_id: str, milliseconds: int = 2600, delay_ms: int = 0) -> None:
        if delay_ms <= 0:
            self._show_temporary_decoration(decoration_id, milliseconds)
            return
        holder: list[str] = []

        def fire() -> None:
            if holder and holder[0] in self._delayed_decoration_after:
                self._delayed_decoration_after.remove(holder[0])
            if self._large_action_running or self._window_move_running:
                after_id = self.root.after(80, fire)
                if holder:
                    holder[0] = after_id
                else:
                    holder.append(after_id)
                self._delayed_decoration_after.append(after_id)
                return
            self._show_temporary_decoration(decoration_id, milliseconds)

        after_id = self.root.after(delay_ms, fire)
        holder.append(after_id)
        self._delayed_decoration_after.append(after_id)

    def _cancel_delayed_decoration_cues(self) -> None:
        for after_id in self._delayed_decoration_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._delayed_decoration_after.clear()

    def _clear_decorations(self, lifetime: str | None = None) -> None:
        lifetimes = (lifetime,) if lifetime else tuple(self._decoration_items)
        for key in lifetimes:
            for item in self._decoration_items.get(key, []):
                try:
                    self.canvas.delete(item)
                except tk.TclError:
                    pass
            self._decoration_items[key] = []
        if lifetime is None or lifetime == "temporary":
            for after_id in self._decoration_after:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
            self._decoration_after.clear()

    def _draw_decoration(self, definition: DecorationDefinition, lifetime: str = "identity") -> None:
        x, y = self._decoration_anchor(definition)
        color = definition.color
        items: list[int] = []
        shape = definition.shape_type
        paper = "#fffdfd"
        main_w = 2.5
        detail_w = 1.5

        def line(*coords: float, fill: str = color, width: float = main_w, smooth: bool = False) -> int:
            return self.canvas.create_line(
                *coords,
                fill=fill,
                width=width,
                smooth=smooth,
                splinesteps=10,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )

        def card(x1: float, y1: float, x2: float, y2: float, radius: float = 7, fill: str = paper, width: float = main_w) -> int:
            return _rounded_rect(self.canvas, x1, y1, x2, y2, radius, fill=fill, outline=color, width=width)

        if shape == "terminal_box":
            items.extend([
                card(x, y + 1, x + 31, y + 23, 7),
                self.canvas.create_oval(x + 5, y + 7, x + 8, y + 10, fill=color, outline=""),
                line(x + 11, y + 11, x + 15, y + 14, x + 11, y + 17, width=detail_w, smooth=True),
                line(x + 18, y + 17, x + 25, y + 17, width=detail_w),
            ])
        elif shape == "status_dot":
            items.append(self.canvas.create_oval(x, y, x + 10, y + 10, fill=color, outline=paper, width=detail_w))
        elif shape == "checklist":
            items.extend([
                card(x + 1, y, x + 25, y + 30, 6),
                line(x + 6, y + 9, x + 9, y + 12, x + 15, y + 6, width=detail_w, smooth=True),
                line(x + 6, y + 20, x + 9, y + 23, x + 15, y + 17, width=detail_w, smooth=True),
                line(x + 16, y + 12, x + 21, y + 11, width=detail_w),
                line(x + 16, y + 22, x + 20, y + 21, width=detail_w),
            ])
        elif shape == "thermometer":
            items.extend([
                line(x + 12, y + 7, x + 12, y + 25, fill=paper, width=8),
                line(x + 12, y + 7, x + 12, y + 25, width=main_w),
                self.canvas.create_oval(x + 5, y + 20, x + 19, y + 34, fill=paper, outline=color, width=main_w),
                line(x + 12, y + 15, x + 12, y + 26, width=detail_w),
                self.canvas.create_oval(x + 9, y + 26, x + 15, y + 32, fill=color, outline=""),
            ])
        elif shape in {"heat_puffs", "heat_wisps"}:
            for x0, y0, x1, y1, x2, y2 in (
                (0, 16, 5, 8, 2, 1),
                (12, 18, 18, 10, 15, 3),
                (25, 15, 30, 8, 27, 1),
            ):
                items.append(
                    self.canvas.create_line(
                        x + x0,
                        y + y0,
                        x + x1,
                        y + y1,
                        x + x2,
                        y + y2,
                        smooth=True,
                        splinesteps=10,
                        fill=color,
                        width=detail_w,
                        capstyle=tk.ROUND,
                    )
                )
        elif shape == "ledger":
            items.extend([
                card(x, y + 1, x + 25, y + 29, 6),
                line(x + 6, y + 7, x + 20, y + 6, width=detail_w),
                line(x + 7, y + 15, x + 18, y + 14, width=detail_w),
                line(x + 7, y + 23, x + 15, y + 22, width=detail_w),
                line(x + 3, y + 4, x + 3, y + 25, width=detail_w),
            ])
        elif shape == "mini_bar":
            percent = self._last_codex_usage_status.usage_remaining_percent
            width = 30
            fill_width = round((width - 7) * max(0.1, min(1.0, (percent or 38) / 100)))
            items.extend([
                card(x, y, x + width, y + 9, 5, width=detail_w),
                line(x + 4, y + 4.5, x + 4 + fill_width, y + 4.5, width=3, fill=color),
            ])
        elif shape == "red_pen":
            items.extend([
                line(x + 1, y + 25, x + 10, y + 15, x + 24, y + 3, width=3, smooth=True),
                line(x + 19, y + 2, x + 28, y - 4, width=main_w),
                line(x + 5, y + 28, x + 16, y + 27, width=detail_w),
            ])
        elif shape in {"annotation_circle", "annotation_mark"}:
            items.extend([
                line(x + 2, y + 24, x + 16, y + 8, x + 27, y + 3, width=3, smooth=True),
                line(x + 5, y + 30, x + 27, y + 30, width=detail_w),
                self.canvas.create_arc(x - 4, y + 7, x + 25, y + 31, start=210, extent=95, outline=color, width=detail_w, style=tk.ARC),
            ])
        elif shape == "z_mark":
            items.extend([
                line(x, y + 4, x + 10, y + 3, x + 2, y + 13, x + 13, y + 12, width=detail_w),
                line(x + 15, y + 1, x + 23, y, x + 17, y + 8, x + 25, y + 8, width=detail_w),
            ])
        elif shape == "warning":
            items.extend([
                self.canvas.create_oval(x + 3, y + 3, x + 23, y + 23, fill=paper, outline=color, width=main_w),
                line(x + 13, y + 8, x + 12, y + 15, width=detail_w),
                self.canvas.create_oval(x + 11, y + 18, x + 14, y + 21, fill=color, outline=""),
            ])
        elif shape == "magnifier":
            items.extend([
                self.canvas.create_oval(x, y, x + 17, y + 17, fill="", outline=color, width=main_w),
                line(x + 13, y + 14, x + 23, y + 24, width=main_w),
            ])
        elif shape == "stamp":
            items.extend([
                card(x, y + 13, x + 27, y + 25, 4, fill="#fff7f5"),
                line(x + 8, y + 13, x + 12, y + 2, x + 17, y + 2, x + 21, y + 13, width=detail_w, smooth=True),
            ])
        elif shape == "lock":
            items.extend([
                self.canvas.create_arc(x + 5, y, x + 21, y + 18, start=0, extent=180, outline=color, width=main_w, style=tk.ARC),
                card(x + 3, y + 10, x + 24, y + 26, 5, fill="#f9f6ff"),
            ])
        elif shape == "tab_bar":
            for index in range(3):
                items.append(card(x + index * 8, y + index * 2, x + 18 + index * 8, y + 11 + index * 2, 4, fill="#f9f6ff", width=detail_w))

        if items:
            self._apply_actor_transform_to_items(items)
            for item in items:
                self.canvas.addtag_withtag("decoration", item)
            self._decoration_items.setdefault(lifetime, []).extend(items)
            self.canvas.tag_raise("decoration")

    def _apply_actor_transform_to_items(self, items: list[int]) -> None:
        sx, sy = self._pal_scale
        if sx != 1.0 or sy != 1.0:
            for item in items:
                self.canvas.scale(item, PAL_CENTER_X, PAL_SCALE_CENTER_Y, sx, sy)
        dx = self._action_offset[0] + self._bob_x
        dy = self._action_offset[1] + self._bob_y
        if dx or dy:
            for item in items:
                self.canvas.move(item, dx, dy)

    def _move_actor_items(self, dx: float, dy: float) -> None:
        if not dx and not dy:
            return
        self.canvas.move("pal", dx, dy)
        self.canvas.move("decoration", dx, dy)

    def _scale_actor_items(self, sx: float, sy: float) -> None:
        self.canvas.scale("pal", PAL_CENTER_X, PAL_SCALE_CENTER_Y, sx, sy)
        self.canvas.scale("decoration", PAL_CENTER_X, PAL_SCALE_CENTER_Y, sx, sy)

    def _decoration_anchor(self, definition: DecorationDefinition) -> tuple[float, float]:
        anchors = {
            "upper_left": (PAL_PAD_X + PAL_WIDTH * 0.04, PAL_PAD_Y + PAL_HEIGHT * 0.08),
            "upper_right": (PAL_PAD_X + PAL_WIDTH * 0.68, PAL_PAD_Y + PAL_HEIGHT * 0.05),
            "above_head": (PAL_PAD_X + PAL_WIDTH * 0.34, PAL_PAD_Y - 12),
            "lower_left": (PAL_PAD_X + PAL_WIDTH * 0.06, PAL_PAD_Y + PAL_HEIGHT * 0.74),
            "right_side": (PAL_PAD_X + PAL_WIDTH * 0.78, PAL_PAD_Y + PAL_HEIGHT * 0.38),
            "around_character": (PAL_PAD_X - 10, PAL_PAD_Y - 6),
        }
        x, y = anchors.get(definition.anchor, anchors["upper_right"])
        return x + definition.dx, y + definition.dy

    def _quiet_for(self, seconds: int) -> None:
        self._quiet_until = time.time() + max(1, seconds)
        self._focus_var.set(False)
        self._clear_bubble()
        self._log_event("user_mode", "quiet", "notice", "Quiet 30 min enabled")
        self._refresh_status_badges()
        self._apply_reaction(
            Reaction(
                True,
                "好，我折起来 30 分钟。不是生气，是办公用品开始自我管理。",
                "sulky",
                "retreat_to_corner",
                "thought",
                "fake_sulk",
                event="quiet_mode",
            )
        )

    def _toggle_focus_mode(self) -> None:
        self._quiet_until = 0.0
        self._clear_bubble()
        if self._focus_var.get():
            self._log_event("user_mode", "focus_on", "notice", "Focus mode enabled")
            self._refresh_status_badges()
            self._apply_reaction(
                Reaction(
                    True,
                    "专注模式。夹夹退到角落，只保留眼睛和一点点审判。",
                    "innocent",
                    "retreat_to_corner",
                    "thought",
                    "quiet_companion",
                    event="focus_mode",
                )
            )
            return
        self._log_event("user_mode", "focus_off", "notice", "Focus mode disabled")
        self._refresh_status_badges()
        self._apply_reaction(
            Reaction(
                True,
                "我回来了。暂时不是弹窗，是文具复职。",
                "smirk",
                "drop_in",
                "thought",
                "tiny_celebrate",
                event="focus_mode_off",
            )
        )

    def _resume_auto_reactions(self) -> None:
        self._quiet_until = 0.0
        self._focus_var.set(False)
        self._clear_bubble()
        self._log_event("user_mode", "resume", "notice", "Automatic reactions resumed")
        self._refresh_status_badges()
        self._apply_reaction(
            Reaction(
                True,
                "收到，自动碎碎念恢复。夹夹会先假装克制三秒。",
                "smirk",
                "happy_bounce",
                "thought",
                "quiet_companion",
                event="resume_auto_reactions",
            )
        )

    def _auto_reactions_paused(self) -> bool:
        return self._focus_var.get() or time.time() < self._quiet_until

    def _quiet_remaining_seconds(self) -> float:
        return max(0.0, self._quiet_until - time.time())

    def _activity_policy(self) -> ActivityPolicy:
        return policy_for_frequency(self._freq_var.get())

    def _load_frequency_setting(self) -> str:
        data = self._load_settings()
        key = str(data.get("frequency") or FREQUENCY_DEFAULT)
        valid = {label for label, _mult in FREQUENCY_PRESETS}
        return key if key in valid else FREQUENCY_DEFAULT

    def _save_frequency_setting(self, key: str) -> None:
        self._save_setting("frequency", key)

    def _load_identity_setting(self) -> str:
        return self._valid_identity_id(str(self._load_settings().get("identity") or "auto"))

    def _save_identity_setting(self, identity_id: str) -> None:
        self._save_setting("identity", self._valid_identity_id(identity_id))

    def _valid_identity_id(self, identity_id: str) -> str:
        key = identity_id.strip().lower().replace("-", "_").replace(" ", "_")
        if key == "auto":
            return key
        return key if key in self.brain.identities.packs else "auto"

    def _load_settings(self) -> dict[str, object]:
        path = self.project_root / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_setting(self, key: str, value: object) -> None:
        path = self.project_root / "settings.json"
        data = self._load_settings()
        data[key] = value
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _schedule_micro(self) -> None:
        interval = self.mood.micro_interval_ms()
        self._micro_after = self.root.after(interval, self._micro_tick)

    def _micro_tick(self) -> None:
        self._micro_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            if self._auto_reactions_paused():
                if random.random() < 0.18:
                    self._play_idle_animation(self._pick_idle_animation(micro=True, low_stimulus=True), source="micro_quiet")
                self._schedule_micro()
                return
            action = self._pick_idle_animation(micro=True)
            if action:
                self._play_idle_animation(action, source="micro")
        self._schedule_micro()

    def _schedule_companion(self) -> None:
        self._companion_after = self.root.after(self.mood.companion_interval_ms(), self._companion_tick)

    def _companion_tick(self) -> None:
        self._companion_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            policy = self._activity_policy()
            if self._auto_reactions_paused():
                if random.random() < 0.28:
                    self._play_idle_animation(self._pick_idle_animation(low_stimulus=True), source="companion_quiet")
                self._schedule_companion()
                return
            if random.random() < policy.mouse_follow_chance:
                self._start_mouse_follow(random.randint(850, 1700))
            if random.random() < policy.companion_action_chance:
                self._play_idle_animation(self._pick_idle_animation(), source="companion")
            if (
                not self._bubble_items
                and self.state.can_speak(max(8, round(self.mood.ambient_cooldown_seconds() * policy.cooldown_multiplier)))
                and random.random() < policy.companion_chatter_chance
            ):
                self._ask_brain("ambient")
        self._schedule_companion()

    def _pick_idle_animation(self, micro: bool = False, low_stimulus: bool = False) -> str:
        if low_stimulus:
            return random.choice(LOW_STIMULUS_IDLE_ACTIONS)

        now = time.time()
        pack = self._current_identity_pack()
        candidates: list[tuple[str, float, str]] = []
        identity_idle = pack.animations.get("idle", "")
        if identity_idle and not micro:
            weight = 4.0 if now - self._last_identity_idle_action_at > 45 else 1.2
            candidates.append((identity_idle, weight, "identity_idle"))
        for action in pack.core_animations:
            candidates.append((action, 2.2 if not micro else 1.2, "identity_core"))

        mood_action = self.mood.pick_micro_behavior()
        if mood_action:
            candidates.append((mood_action, 2.4, "mood"))
        candidates.extend((action, 1.5, "common") for action in COMMON_IDLE_ACTIONS)

        policy = self._activity_policy()
        if not micro or policy.tier in {"active", "hyper"}:
            candidates.extend((action, 0.9, "mid") for action in MID_IDLE_ACTIONS)
        if not micro and policy.tier in {"active", "hyper"}:
            candidates.extend((action, 0.28 if policy.tier == "active" else 0.46, "rare") for action in RARE_IDLE_ACTIONS)

        usable: list[tuple[str, float, str, ResolvedAnimation]] = []
        for name, weight, source in candidates:
            resolved = self.animation_resolver.resolve(name)
            if not self._idle_animation_allowed(resolved, micro=micro):
                continue
            if resolved.requested in self._recent_idle_actions[-5:] or resolved.action in self._recent_idle_actions[-5:]:
                weight *= 0.35
            if resolved.requested in self._recent_idle_actions[-2:] or resolved.action in self._recent_idle_actions[-2:]:
                weight *= 0.18
            if weight > 0.05:
                usable.append((name, weight, source, resolved))

        if not usable:
            return random.choice(LOW_STIMULUS_IDLE_ACTIONS)
        names, weights, sources, resolved_items = zip(*usable)
        choice_index = random.choices(range(len(names)), weights=weights, k=1)[0]
        chosen = names[choice_index]
        resolved = resolved_items[choice_index]
        self._last_idle_animation_debug = self._idle_animation_debug_text(chosen, sources[choice_index], resolved)
        if sources[choice_index].startswith("identity"):
            self._last_identity_idle_action_at = time.time()
        return chosen

    def _idle_animation_allowed(self, resolved: ResolvedAnimation, micro: bool = False) -> bool:
        name = resolved.performance or resolved.action
        if not name or name == "idle":
            return True
        now = time.time()
        if name in LARGE_IDLE_ACTIONS and now - self._last_large_idle_action_at < (35 if micro else 60):
            return False
        if name in MOVE_IDLE_ACTIONS and now - self._last_move_idle_action_at < 180:
            return False
        if self._recent_idle_actions and self._recent_idle_actions[-1] == name:
            return False
        return True

    def _play_idle_animation(self, name: str, source: str = "idle") -> None:
        resolved = self.animation_resolver.resolve(name)
        played = resolved.performance or resolved.action
        if not played or played == "idle":
            self._last_idle_animation_debug = self._idle_animation_debug_text(name, source, resolved)
            return
        if resolved.kind == "performance" and resolved.performance:
            reaction = Reaction(False, "", self.state.mood or "idle", resolved.action or "blink", "thought", resolved.performance, event=f"idle_{source}")
            self._run_performance_phrase(resolved.performance, reaction, state="idle")
        else:
            self._perform_action(resolved.action)
        self._remember_idle_animation(played)
        if source != "identity_switch":
            self._queue_action_decoration_cue(resolved.action)
        self._last_idle_animation_debug = self._idle_animation_debug_text(name, source, resolved)

    def _queue_action_decoration_cue(self, action: str) -> None:
        cue = ACTION_DECORATION_CUES.get(action)
        if not cue:
            return
        decoration_id, milliseconds = cue
        self._queue_temporary_decoration(decoration_id, milliseconds, delay_ms=self._animation_duration_ms(action) + 40)

    def _animation_duration_ms(self, action_or_name: str) -> int:
        resolved = self.animation_resolver.resolve(action_or_name)
        action = resolved.action or action_or_name
        frames = ACTION_FRAMES.get(action)
        if frames:
            return sum(frame[-1] for frame in frames)
        if action == "scan":
            return 850
        if action == "wiggle":
            return 180
        if action == "blink":
            return 150
        if action in MOVE_IDLE_ACTIONS:
            return 760
        return 0

    def _remember_idle_animation(self, played: str) -> None:
        self._recent_idle_actions.append(played)
        self._recent_idle_actions = self._recent_idle_actions[-8:]
        if played in LARGE_IDLE_ACTIONS:
            self._last_large_idle_action_at = time.time()
        if played in MOVE_IDLE_ACTIONS:
            self._last_move_idle_action_at = time.time()

    def _idle_animation_debug_text(self, requested: str, source: str, resolved: ResolvedAnimation) -> str:
        return (
            f"current_identity: {self._active_identity_id or 'default_pal'}\n"
            f"visual_addons: {', '.join(self._active_identity_addons) or 'none'}\n"
            f"selected_idle_animation: {requested}\n"
            f"resolver_result: kind={resolved.kind}, action={resolved.action}, performance={resolved.performance or 'none'}\n"
            f"fallback_reason: {resolved.fallback_reason or 'none'}\n"
            f"source: {source}\n"
            f"recent_idle_actions: {', '.join(self._recent_idle_actions[-8:]) or 'none'}"
        )

    def _show_codex_status(self) -> None:
        status = self.codex_status.sample()
        if status.status == "unknown":
            line = _pick_status_fragment(_CODEX_UNKNOWN_LINES, self._recent_codex_status_fragments)
            self.show_bubble(line, kind="codex_thought")
            return
        reaction = _codex_status_reaction(status, self._recent_codex_status_fragments, manual=True)
        self._apply_reaction(reaction)

    def _on_press(self, event: tk.Event) -> None:
        self._begin_drag(event.x_root, event.y_root)

    def _on_motion(self, event: tk.Event) -> None:
        self._continue_drag(event.x_root, event.y_root)

    def _on_release(self, _event: tk.Event) -> None:
        self._finish_drag()

    def _begin_drag(self, x_root: int, y_root: int) -> None:
        self._drag_start = (x_root, y_root)
        self._drag_origin = (self.root.winfo_x(), self.root.winfo_y())
        self._dragging = False
        self._start_mouse_follow(1200, force=True)

    def _continue_drag(self, x_root: int, y_root: int) -> None:
        if not self._drag_start or not self._drag_origin:
            return
        dx = x_root - self._drag_start[0]
        dy = y_root - self._drag_start[1]
        if abs(dx) + abs(dy) > 8:
            self._dragging = True
        if self._dragging:
            x = self._drag_origin[0] + dx
            y = self._drag_origin[1] + dy
            self.root.geometry(_geometry_position(x, y))
            if self._bubble_items:
                self._position_bubble()
            if self._chat_window:
                self._position_chat_input()
            self._look_at_pointer_now()

    def _finish_drag(self) -> None:
        if self._drag_start is None:
            return
        if not self._dragging:
            self._poke()
        else:
            self._start_mouse_follow(1300, force=True)
        self._drag_start = None
        self._drag_origin = None
        self._dragging = False

    def _poke(self, force: bool = False) -> None:
        self._wiggle()
        self._start_mouse_follow(1600, force=True)
        if force or self.state.can_speak(4):
            self._ask_brain("poke")

    def _ask_brain(self, event: str, world: WorldState | None = None) -> None:
        if self.state.brain_busy:
            self._perform_action("thinking_tilt")
            return
        self.state.brain_busy = True
        context = self._context(event, world)
        self._start_brain_wait_animation()

        def worker() -> None:
            reaction = self.brain.react(event, context)
            reaction.event = event
            self.queue.put(reaction)

        self._brain_thread = threading.Thread(target=worker, daemon=True)
        self._brain_thread.start()

    def _world_state(self) -> WorldState:
        return WorldState(
            user_activity=self.ears.sample(),
            screen=self.eyes.sample(),
            codex=self.codex_status.sample(),
            codex_usage=self._last_codex_usage_status,
            claude=self.claude_monitor.sample(),
            hardware=self._last_hardware_status,
            pal=self.state,
            mood=MoodSnapshot(
                key=self._freq_var.get(),
                energy=self.mood.energy,
                valence=self.mood.valence,
                frequency_multiplier=self.mood.frequency_multiplier,
            ),
        )

    def _context(self, event: str, world: WorldState | None = None) -> dict[str, object]:
        context = (world or self._world_state()).as_context(event)
        identity_id = self._identity_var.get()
        if identity_id and identity_id != "auto":
            context["identity_id"] = identity_id
        focus_mode = bool(self._focus_var.get())
        quiet_remaining = self._quiet_remaining_seconds()
        policy = self._activity_policy()
        context["pal_focus_mode"] = focus_mode
        context["pal_quiet_remaining_seconds"] = round(quiet_remaining, 1)
        context["activity_tier"] = policy.tier
        context["activity_alert_threshold"] = policy.alert_threshold
        if focus_mode or quiet_remaining > 0:
            tags = list(context.get("environment_tags") or [])
            tags.append("focus_mode" if focus_mode else "quiet_mode")
            context["environment_tags"] = sorted(set(str(tag) for tag in tags if str(tag)))
        else:
            tags = list(context.get("environment_tags") or [])
            tags.append(f"activity_{policy.tier}")
            context["environment_tags"] = sorted(set(str(tag) for tag in tags if str(tag)))
        return context

    def _poll_brain(self) -> None:
        try:
            while True:
                reaction = self.queue.get_nowait()
                self.state.brain_busy = False
                self._stop_brain_wait_animation()
                self._stop_chat_wait_feedback()
                self._apply_reaction(reaction)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_brain)

    def _start_brain_wait_animation(self) -> None:
        self._stop_brain_wait_animation()
        self._brain_wait_step = 0
        self._brain_wait_after = self.root.after(80, self._brain_wait_tick)

    def _stop_brain_wait_animation(self) -> None:
        if self._brain_wait_after:
            self.root.after_cancel(self._brain_wait_after)
            self._brain_wait_after = None

    def _start_chat_wait_feedback(self) -> None:
        self._stop_chat_wait_feedback(clear_bubble=False)
        self._chat_wait_step = 0
        self._chat_wait_started_at = time.time()
        self._chat_wait_tick()

    def _stop_chat_wait_feedback(self, clear_bubble: bool = False) -> None:
        if self._chat_wait_after:
            try:
                self.root.after_cancel(self._chat_wait_after)
            except tk.TclError:
                pass
            self._chat_wait_after = None
        self._chat_wait_step = 0
        self._chat_wait_started_at = 0.0
        if clear_bubble:
            self._clear_bubble()

    def _chat_wait_tick(self) -> None:
        self._chat_wait_after = None
        if not self.state.brain_busy:
            return
        elapsed = time.time() - self._chat_wait_started_at if self._chat_wait_started_at else 0.0
        early_steps = (
            ("收到。夹夹把这句话夹住了。", "blink", "thought", 1250),
            ("正在折一份低隐私状态小纸条。", "scan", "thought", 1500),
            ("正在叫醒 Ollama。本地模型起床有仪式感。", "thinking_tilt", "thought", 1750),
            ("模型在想。夹夹先用眉毛维持连接。", "smug_sway", "thought", 1850),
            ("正在等它吐出一句像样的话。要求不高，像样就行。", "patrol", "thought", 2100),
        )
        long_wait_steps = (
            ("还在等。本地脑子正在慢慢把风格拧紧。", "sleepy_sag", "thought", 2300),
            ("它还没回。夹夹没有失联，只是在旁边审判延迟。", "scan", "thought", 2400),
            ("再慢一点，我就要怀疑它在给词语排队。", "thinking_tilt", "thought", 2500),
        )
        if self._chat_wait_step < len(early_steps):
            line, action, bubble, delay = early_steps[self._chat_wait_step]
        else:
            index = (self._chat_wait_step - len(early_steps)) % len(long_wait_steps)
            line, action, bubble, delay = long_wait_steps[index]
            if elapsed >= 18:
                line = f"{line} 已经 {round(elapsed)} 秒了，仪式感略多。"
        if not self._dragging:
            self._perform_action(action)
        self.show_bubble(line, milliseconds=max(2400, delay + 900), kind=bubble)
        self._chat_wait_step += 1
        self._chat_wait_after = self.root.after(delay, self._chat_wait_tick)

    def _brain_wait_tick(self) -> None:
        self._brain_wait_after = None
        if not self.state.brain_busy:
            return
        if not self._dragging:
            sequence = ("thinking_tilt", "scan", "smug_sway", "scan", "nod")
            self._perform_action(sequence[self._brain_wait_step % len(sequence)])
            if self._brain_wait_step in {1, 3}:
                self._start_mouse_follow(900)
            self._brain_wait_step += 1
        self._brain_wait_after = self.root.after(1050, self._brain_wait_tick)

    def _maintain_line_bank(self) -> None:
        if self._line_bank_thread and self._line_bank_thread.is_alive():
            self.root.after(60_000, self._maintain_line_bank)
            return

        def worker() -> None:
            try:
                self.brain.maintain_line_bank()
            except Exception:
                return

        self._line_bank_thread = threading.Thread(target=worker, daemon=True)
        self._line_bank_thread.start()
        self.root.after(20 * 60 * 1000, self._maintain_line_bank)

    def _refresh_eyes(self) -> None:
        if self._vision_thread and self._vision_thread.is_alive():
            self.root.after(10_000, self._refresh_eyes)
            return

        def worker() -> None:
            try:
                self.eyes.refresh()
            except Exception:
                return

        self._vision_thread = threading.Thread(target=worker, daemon=True)
        self._vision_thread.start()
        self.root.after(VISION_REFRESH_MS, self._refresh_eyes)

    def _poll_codex_status(self) -> None:
        status = self.codex_status.sample()
        self._last_codex_status = status
        self._refresh_status_badges()
        if self._should_log_codex_status(status):
            self._logged_codex_status_event = status.event_id
            self._log_event(
                "codex_status",
                status.status,
                _codex_event_level(status.status),
                status.summary or f"Codex {status.status}",
            )
        if self._should_announce_codex_status(status):
            reaction = _codex_status_reaction(status, self._recent_codex_status_fragments)
            self._last_codex_status_event = status.event_id
            self._apply_reaction(reaction)
        self.root.after(CODEX_STATUS_POLL_MS, self._poll_codex_status)

    def _should_log_codex_status(self, status: CodexStatus) -> bool:
        if status.status in {"unknown", "idle"} or status.stale:
            return False
        return bool(status.event_id and status.event_id != self._logged_codex_status_event)

    def _poll_codex_usage(self) -> None:
        status = self.codex_usage.sample()
        self._last_codex_usage_status = status
        self._set_codex_usage_badge(status)
        self._refresh_status_badges()
        if self._should_log_codex_usage(status):
            self._logged_codex_usage_event = status.event_id
            self._log_event("codex_usage", status.level, _usage_event_level(status.level), status.summary_line)
        if self._should_announce_codex_usage(status):
            self._last_codex_usage_event = status.event_id
            self._last_codex_usage_announcement_at = time.time()
            self._apply_reaction(_codex_usage_reaction(status))
        self.root.after(CODEX_USAGE_POLL_MS, self._poll_codex_usage)

    def _should_log_codex_usage(self, status: CodexUsageStatus) -> bool:
        if status.level in {"unavailable", "normal"} or status.stale:
            return False
        return bool(status.event_id and status.event_id != self._logged_codex_usage_event)

    def _should_announce_codex_usage(self, status: CodexUsageStatus) -> bool:
        if self._auto_reactions_paused():
            return False
        policy = self._activity_policy()
        if not policy.allows_usage(status.level, status.usage_remaining_percent):
            return False
        if status.level in {"unavailable", "normal"} or status.stale:
            return False
        if self.state.brain_busy or self._bubble_items:
            return False
        cooldown = {
            "low": 30 * 60,
            "critical": 10 * 60,
            "reset_soon": 20 * 60,
            "refilled": 30 * 60,
        }.get(status.level, 30 * 60)
        cooldown = max(8, round(cooldown * policy.cooldown_multiplier))
        is_new_event = bool(status.event_id and status.event_id != self._last_codex_usage_event)
        if is_new_event and self._last_codex_usage_announcement_at <= 0:
            return self.state.can_speak(8)
        if status.level == "watch":
            return is_new_event and self.state.can_speak(cooldown)
        if status.level in {"reset_soon", "refilled"}:
            return is_new_event and self.state.can_speak(8)
        if status.level in {"low", "critical"}:
            return self.state.can_speak(cooldown) and time.time() - self._last_codex_usage_announcement_at >= cooldown
        return False

    def _show_codex_usage(self) -> None:
        status = self.codex_usage.sample()
        self._last_codex_usage_status = status
        self._set_codex_usage_badge(status)
        self._apply_reaction(_codex_usage_reaction(status, manual=True))

    def _should_announce_codex_status(self, status: CodexStatus) -> bool:
        if self._auto_reactions_paused():
            return False
        policy = self._activity_policy()
        if not policy.allows_codex_status(status.status):
            return False
        if status.status in {"unknown", "idle"} or status.stale:
            return False
        if not status.event_id or status.event_id == self._last_codex_status_event:
            return False
        if self.state.brain_busy or self._bubble_items:
            return False
        base_cooldown = 4 if status.status in {"thinking", "reading", "working", "editing", "running", "testing", "reconnecting"} else 8
        cooldown = max(3, round(base_cooldown * policy.cooldown_multiplier))
        return self.state.can_speak(cooldown)

    def _poll_claude_status(self) -> None:
        overview = self.claude_monitor.sample()
        if overview.event_id != self._last_claude_event:
            reaction = self._claude_change_reaction(overview)
            self._last_claude_event = overview.event_id
            if reaction:
                self._log_event("claude_status", reaction.event or "changed", _reaction_event_level(reaction), reaction.line)
            policy = self._activity_policy()
            if (
                reaction
                and not self._auto_reactions_paused()
                and policy.allows_claude_event(reaction.event)
                and not self.state.brain_busy
                and not self._bubble_items
            ):
                self._apply_reaction(reaction)
        self.root.after(CLAUDE_STATUS_POLL_MS, self._poll_claude_status)

    def _poll_hardware_status(self) -> None:
        snapshot = self.hardware_status.sample()
        self._last_hardware_status = snapshot
        self._refresh_status_badges()
        if self._should_log_hardware_status(snapshot):
            self._logged_hardware_status_event = snapshot.event_id
            self._log_event("hardware", snapshot.level, _hardware_event_level(snapshot.level), snapshot.summary_line)
        if self._should_announce_hardware_status(snapshot):
            self._last_hardware_status_event = snapshot.event_id
            self._last_hardware_announcement_at = time.time()
            self._apply_reaction(_hardware_status_reaction(snapshot))
        self.root.after(HARDWARE_STATUS_POLL_MS, self._poll_hardware_status)

    def _should_log_hardware_status(self, snapshot: HardwareSnapshot) -> bool:
        if snapshot.level in {"normal", "unavailable"}:
            return False
        return bool(snapshot.event_id and snapshot.event_id != self._logged_hardware_status_event)

    def _should_announce_hardware_status(self, snapshot: HardwareSnapshot) -> bool:
        if self._auto_reactions_paused():
            return False
        policy = self._activity_policy()
        if not policy.allows_hardware_level(snapshot.level):
            return False
        if snapshot.level in {"normal", "unavailable"}:
            return False
        if self.state.brain_busy or self._bubble_items:
            return False
        cooldown = {
            "warm": 240,
            "hot": 75,
            "overloaded": 60,
            "cooling": 45,
        }.get(snapshot.level, 180)
        cooldown = max(10, round(cooldown * policy.cooldown_multiplier))
        if snapshot.level in {"hot", "overloaded"}:
            return self.state.can_speak(cooldown) and time.time() - self._last_hardware_announcement_at >= cooldown
        if not snapshot.event_id or snapshot.event_id == self._last_hardware_status_event:
            return False
        return self.state.can_speak(cooldown)

    def _show_hardware_status(self) -> None:
        snapshot = self.hardware_status.sample()
        self._last_hardware_status = snapshot
        self._apply_reaction(_hardware_status_reaction(snapshot, manual=True))

    def _set_hardware_tint(self, level: str) -> None:
        if self._hardware_tint_after:
            try:
                self.root.after_cancel(self._hardware_tint_after)
            except tk.TclError:
                pass
            self._hardware_tint_after = None
        self._hardware_tint_level = level
        self._apply_hardware_tint()

    def _flash_hardware_tint(self, level: str, milliseconds: int = 9000) -> None:
        self._set_hardware_tint(level)
        if level in {"normal", "unavailable"}:
            return
        self._hardware_tint_after = self.root.after(milliseconds, self._clear_hardware_tint)

    def _clear_hardware_tint(self) -> None:
        self._hardware_tint_after = None
        self._hardware_tint_level = "normal"
        self._apply_hardware_tint()
        self._refresh_status_badges()

    def _apply_hardware_tint(self) -> None:
        fill = HARDWARE_TINTS.get(self._hardware_tint_level, WIRE)
        self.canvas.itemconfigure("wire", fill=fill)

    def _set_codex_usage_badge(self, status: CodexUsageStatus) -> None:
        self._clear_codex_usage_badge()
        if status.level not in {"watch", "low", "critical", "reset_soon"}:
            return
        percent = status.usage_remaining_percent
        if percent is None:
            return
        color = CODEX_USAGE_COLORS.get(status.level, CODEX_USAGE_COLORS["watch"])
        x, y = 10, 12
        width, height = 78, 26
        fill_width = max(4, round((width - 8) * percent / 100))
        self._usage_badge_items.extend(
            [
                self.canvas.create_rectangle(
                    x,
                    y,
                    x + width,
                    y + height,
                    fill="#f7fbff",
                    outline=color,
                    width=1,
                ),
                self.canvas.create_rectangle(
                    x + 4,
                    y + 16,
                    x + 4 + fill_width,
                    y + 21,
                    fill=color,
                    outline="",
                ),
                self.canvas.create_rectangle(
                    x + 4,
                    y + 16,
                    x + width - 4,
                    y + 21,
                    fill="",
                    outline="#d7e2f4",
                    width=1,
                ),
                self.canvas.create_text(
                    x + 6,
                    y + 8,
                    anchor="w",
                    text=f"CODEX {percent:.0f}%",
                    fill="#20304f",
                    font=("Microsoft YaHei UI", 7),
                ),
            ]
        )

    def _clear_codex_usage_badge(self) -> None:
        for item in self._usage_badge_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._usage_badge_items.clear()

    def _refresh_status_badges(self) -> None:
        badge_ids = self._status_badge_ids()
        if self._status_badge_after:
            try:
                self.root.after_cancel(self._status_badge_after)
            except tk.TclError:
                pass
            self._status_badge_after = None
        self.canvas.delete("status_badge")
        self._status_badge_items.clear()
        if not badge_ids:
            return
        start_x = self.width - 14
        y = 18
        for index, badge_id in enumerate(badge_ids[:6]):
            label, fill, shape = STATUS_BADGES[badge_id]
            cx = start_x - index * 21
            if shape == "triangle":
                item = self.canvas.create_polygon(
                    cx,
                    y - 8,
                    cx - 9,
                    y + 8,
                    cx + 9,
                    y + 8,
                    fill=fill,
                    outline="#ffffff",
                    width=1,
                    tags=("status_badge", "status_badge_shape"),
                )
            else:
                item = self.canvas.create_oval(
                    cx - 8,
                    y - 8,
                    cx + 8,
                    y + 8,
                    fill=fill,
                    outline="#ffffff",
                    width=1,
                    tags=("status_badge", "status_badge_shape"),
                )
            text = self.canvas.create_text(
                cx,
                y,
                text=label,
                fill="#ffffff",
                font=("Microsoft YaHei UI", 7, "bold"),
                tags=("status_badge",),
            )
            self._status_badge_items.extend([item, text])
        self._pulse_status_badges()

    def _status_badge_ids(self) -> list[str]:
        badges: list[str] = []
        if self._focus_var.get() or self._quiet_remaining_seconds() > 0:
            badges.append("focus_mode")
        if self._last_codex_status.status == "waiting_user":
            badges.append("codex_waiting")
        if self._last_codex_status.status in {"error", "blocked", "disconnected"}:
            badges.append("error")
        if self._hardware_tint_after and self._hardware_tint_level in {"hot", "overloaded"}:
            badges.append("hardware_hot")
        if self._last_codex_usage_status.level in {"low", "critical", "reset_soon"}:
            badges.append("usage_low")
        if self.state.mood in {"sleepy", "sulky"}:
            badges.append("sleeping")
        return badges

    def _pulse_status_badges(self) -> None:
        if not self._status_badge_items:
            self._status_badge_after = None
            return
        self._status_badge_phase += 1
        width = 2 if self._status_badge_phase % 2 else 1
        self.canvas.itemconfigure("status_badge_shape", width=width)
        self._status_badge_after = self.root.after(650, self._pulse_status_badges)

    def _claude_change_reaction(self, overview: ClaudeOverview) -> Reaction | None:
        current_sessions = {s.pid: s for s in overview.sessions if s.alive}
        current_pids = set(current_sessions)
        previous_sessions = self._last_claude_sessions_by_pid
        new_pids = current_pids - set(previous_sessions)
        gone_pids = set(previous_sessions) - current_pids
        changed_pids = {
            pid
            for pid in current_pids & set(previous_sessions)
            if current_sessions[pid].activity != previous_sessions[pid].activity
        }
        self._last_claude_alive_pids = current_pids
        self._last_claude_sessions_by_pid = current_sessions

        if new_pids:
            session = _pick_claude_session([current_sessions[pid] for pid in new_pids])
            return _claude_session_reaction(session, "started", self._recent_claude_status_fragments)

        if gone_pids:
            session = _pick_claude_session([previous_sessions[pid] for pid in gone_pids])
            return _claude_session_reaction(session, "ended", self._recent_claude_status_fragments)

        if changed_pids:
            session = _pick_claude_session([current_sessions[pid] for pid in changed_pids])
            return _claude_session_reaction(session, session.activity, self._recent_claude_status_fragments)
        return None

    def _show_claude_status(self) -> None:
        overview = self.claude_monitor.sample()
        reaction = _claude_overview_reaction(overview, self._recent_claude_status_fragments)
        self._apply_reaction(reaction)

    def _show_last_events(self) -> None:
        events = self.event_log.last(12)
        if not events:
            self.show_bubble("事件日志还是空的。夹夹暂时没有黑匣子，只有眉毛。", milliseconds=5200, kind="thought")
            return
        text = "最近事件：\n" + "\n".join(f"- {event.short_line()}" for event in events)
        self.show_bubble(text, milliseconds=9000, kind="thought")

    def _show_morning_digest(self) -> None:
        self.show_bubble(self.event_log.digest(mark_read=True), milliseconds=11000, kind="speech")

    def _run_scripted_demo(self) -> None:
        self._cancel_scripted_demo()
        self._log_event("demo", "started", "notice", "Scripted demo started")
        self._apply_reaction(
            Reaction(True, "演示开始。夹夹开始装作自己是测试工程师。", "smirk", "drop_in", "speech", "drop_in", event="demo_started")
        )
        steps = (
            (900, lambda: self._demo_codex("running", "Codex running demo", "Codex 开始跑命令。终端负责紧张，夹夹负责围观。", "thinking", "scan", "agent_stuck_stare")),
            (3300, lambda: self._demo_codex("waiting_user", "Waiting for user", "Codex 在等你确认。它等得像一块电子石头。", "suspicious", "thinking_tilt", "agent_stuck_stare")),
            (5700, lambda: self._demo_hardware("overloaded", "GPU 98% / 82C / VRAM 91%", "GPU 98%。我替你熟了一会儿。", "startled", "shake", "hardware_hot_sag")),
            (8100, lambda: self._demo_usage("critical", 8, "reset in 20 minutes", "Codex 只剩 8%。现在每个大活都要过会计。", "sulky", "sulk", "usage_low_sag")),
            (10500, self._demo_focus_on),
            (12800, self._demo_pokes),
            (15400, lambda: self._demo_hardware("cooling", "GPU cooling down", "温度下来了。夹夹恢复成办公用品。", "innocent", "nod", "quiet_companion")),
            (18000, lambda: self._demo_codex("done", "Demo finished", "Codex 说它做完了。听起来像好消息，暂时。", "done", "happy_bounce", "tiny_celebrate")),
        )
        for delay, callback in steps:
            self._demo_after.append(self.root.after(delay, callback))

    def _cancel_scripted_demo(self) -> None:
        for after_id in self._demo_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._demo_after.clear()

    def _demo_codex(self, status: str, summary: str, line: str, mood: str, action: str, performance: str) -> None:
        self._last_codex_status = CodexStatus(status=status, summary=summary, source="demo", event_id=f"demo_codex_{status}_{time.time()}")
        self._refresh_status_badges()
        self._log_event("demo_codex", status, _codex_event_level(status), summary)
        self._apply_reaction(Reaction(True, line, mood, action, "codex_thought", performance, event=f"demo_codex_{status}"))

    def _demo_hardware(self, level: str, summary: str, line: str, mood: str, action: str, performance: str) -> None:
        self._last_hardware_status = HardwareSnapshot(level=level, summary_line=summary, event_id=f"demo_hardware_{level}_{time.time()}")
        self._set_hardware_tint(level)
        self._refresh_status_badges()
        self._log_event("demo_hardware", level, _hardware_event_level(level), summary)
        self._apply_reaction(Reaction(True, line, mood, action, "hardware_thought", performance, event=f"demo_hardware_{level}"))

    def _demo_usage(self, level: str, percent: float, summary: str, line: str, mood: str, action: str, performance: str) -> None:
        self._last_codex_usage_status = CodexUsageStatus(
            usage_remaining_percent=percent,
            level=level,
            summary_line=summary,
            event_id=f"demo_usage_{level}_{time.time()}",
        )
        self._set_codex_usage_badge(self._last_codex_usage_status)
        self._refresh_status_badges()
        self._log_event("demo_usage", level, _usage_event_level(level), summary)
        self._apply_reaction(Reaction(True, line, mood, action, "usage_speech", performance, event=f"demo_usage_{level}"))

    def _demo_focus_on(self) -> None:
        self._focus_var.set(True)
        self._quiet_until = 0.0
        self._refresh_status_badges()
        self._log_event("demo_user_mode", "focus_on", "notice", "Demo focus mode")
        self._apply_reaction(
            Reaction(True, "用户进入专注模式。夹夹退到角落，保留一点点眼神。", "innocent", "retreat_to_corner", "thought", "retreat_to_corner", event="demo_focus_on")
        )

    def _demo_pokes(self) -> None:
        self._focus_var.set(False)
        self._refresh_status_badges()
        self._log_event("demo_user", "poke_3", "notice", "User pokes pal three times")
        self._perform_action("wiggle")
        self._apply_reaction(
            Reaction(True, "你连续戳我三下。任务也能这样被推进就好了。", "smug", "roast_and_scoot", "speech", "roast_and_scoot", event="demo_poke_3")
        )

    def _preview_performance(self, performance_id: str) -> None:
        definition = self.animation_player.manifest.performance(performance_id)
        fallback = definition.fallback_action if definition else "blink"
        reaction = Reaction(
            True,
            f"预览 {performance_id}。如果不好看，先怪占位系统。",
            "thinking",
            fallback,
            "thought",
            performance_id,
            event=f"preview_{performance_id}",
        )
        self._apply_reaction(reaction)

    def _show_last_decision_debug(self) -> None:
        policy = self._activity_policy()
        prefix = (
            f"activity: {policy.key} / {policy.tier}\n"
            f"threshold: {policy.alert_threshold}\n"
        )
        self.show_bubble(prefix + self.decision.last_decision.debug_text(), milliseconds=6800, kind="thought")

    def _show_last_animation_debug(self) -> None:
        text = f"{self._last_animation_debug}\n\nidle scheduler:\n{self._last_idle_animation_debug}"
        self.show_bubble(text, milliseconds=9000, kind="thought")

    def _show_identity_debug(self) -> None:
        context = self._context("manual")
        pack = self.brain.identities.select("manual", context)
        mode = self._identity_var.get()
        prefix = f"mode: {mode}\nselected: {pack.display_name}\n"
        self.show_bubble(prefix + pack.prompt_brief(), milliseconds=7600, kind="thought")

    def _show_last_chat_context(self) -> None:
        text = self._last_chat_context_debug
        if not text:
            text = json.dumps(self._build_chat_context(), ensure_ascii=False, indent=2)
        self.show_bubble(text, milliseconds=10_000, kind="thought")

    def _log_event(
        self,
        source: str,
        event: str,
        level: str = "notice",
        summary: str = "",
        pal_reaction: str = "",
    ) -> None:
        try:
            self.event_log.append(source, event, level, summary, pal_reaction)
        except Exception:
            return

    def _apply_reaction(self, reaction: Reaction) -> None:
        self._cancel_performance_phrase()
        self.state.mood = reaction.mood
        self.mood.push_mood(reaction.mood)
        self._refresh_identity_decorations(reaction)
        self._maybe_show_reaction_decoration(reaction)
        self._maybe_flash_hardware_tint(reaction)
        self._refresh_status_badges()
        state = self.animation_player.manifest.state_for_reaction(reaction.mood, reaction.action, reaction.bubble)
        performance = (
            reaction.performance
            or self.animation_player.manifest.performance_for_state(state)
            or phrase_for_reaction(reaction.mood, reaction.action, reaction.bubble)
        )
        self._log_event(
            "pal",
            reaction.event or "reaction",
            _reaction_event_level(reaction),
            reaction.line,
            performance or reaction.action,
        )
        if performance and reaction.should_say and reaction.line:
            self._run_performance_phrase(performance, reaction, state)
            return
        self._last_animation_debug = (
            f"event: {reaction.event or 'unknown'}\n"
            f"state: {state}\n"
            "performance: none\n"
            "source: action\n"
            "steps: 0\n"
            f"fallback_action: {reaction.action or 'none'}\n"
            "fallback_reason: no_performance_or_no_line"
        )
        self._perform_action(reaction.action)
        if reaction.should_say and reaction.line:
            self.show_bubble(reaction.line, kind=reaction.bubble)
            self.state.remember_line(reaction.line)

    def _maybe_show_reaction_decoration(self, reaction: Reaction) -> None:
        event = (reaction.event or "").lower()
        bubble = (reaction.bubble or "").lower()
        if event.startswith(("hardware_", "chat_hardware", "demo_hardware")) or bubble.startswith("hardware_"):
            self._show_temporary_decoration("heat_puffs", 4200)
        if event.startswith(("codex_usage", "chat_usage", "demo_usage")) or bubble.startswith("usage_"):
            self._show_temporary_decoration("usage_bar", 4200)
        if reaction.performance in {"cold_arrow_then_innocent", "roast_and_scoot"} or reaction.mood in {"smirk", "smug"}:
            self._show_temporary_decoration("annotation_circle", 2600)
        if reaction.mood in {"sleepy", "sulky"}:
            self._show_temporary_decoration("z_symbol", 3200)
        if any(key in event for key in ("error", "blocked", "critical", "overloaded")):
            self._show_temporary_decoration("tiny_warning", 4200)

    def _maybe_flash_hardware_tint(self, reaction: Reaction) -> None:
        event = (reaction.event or "").lower()
        bubble = (reaction.bubble or "").lower()
        if not (event.startswith(("hardware_", "chat_hardware", "demo_hardware")) or bubble.startswith("hardware_")):
            return
        level = self._last_hardware_status.level
        if event.startswith("demo_hardware_"):
            level = event.removeprefix("demo_hardware_").split("_", 1)[0]
        elif event.startswith("hardware_"):
            level = event.removeprefix("hardware_").split("_", 1)[0]
        self._flash_hardware_tint(level, milliseconds=11_000)

    def _run_performance_phrase(self, name: str, reaction: Reaction, state: str = "") -> None:
        callbacks = AnimationCallbacks(
            after=lambda delay, callback: self.root.after(delay, callback),
            action=self._perform_action,
            bubble=self._show_reaction_line,
            eyes=self._set_eye_pose,
            brows=self._set_brow_pose,
            reset_expression=self._reset_expression_pose,
            stop_cursor_follow=self._stop_mouse_follow,
        )
        after_ids = self.animation_player.play(
            name,
            reaction,
            callbacks,
            state=state,
            event=reaction.event,
        )
        if after_ids:
            self._performance_after.extend(after_ids)
            self._last_animation_debug = self.animation_player.last_debug.text()
            return

        phrase = PERFORMANCE_PHRASES.get(name)
        if not phrase:
            self._last_animation_debug = self.animation_player.last_debug.text()
            fallback_action = self.animation_player.manifest.fallback_action_for_state(state) or reaction.action
            self._perform_action(fallback_action)
            self.show_bubble(reaction.line, kind=reaction.bubble)
            self.state.remember_line(reaction.line)
            return

        self._last_animation_debug = (
            f"event: {reaction.event or 'unknown'}\n"
            f"state: {state or 'unknown'}\n"
            f"performance: {name}\n"
            "source: legacy_performance\n"
            f"steps: {len(phrase.pre_actions) + 1 + len(phrase.post_actions)}\n"
            f"fallback_action: {reaction.action or 'none'}\n"
            "fallback_reason: manifest_unavailable"
        )
        elapsed = 0
        for action, delay in phrase.pre_actions:
            self._schedule_performance_action(action, elapsed)
            elapsed += max(0, delay)

        line_delay = elapsed + max(0, phrase.line_delay_ms)
        self._performance_after.append(
            self.root.after(line_delay, lambda: self._show_reaction_line(reaction))
        )

        post_elapsed = line_delay + 120
        for action, delay in phrase.post_actions:
            post_elapsed += max(0, delay)
            self._schedule_performance_action(action, post_elapsed)

    def _show_reaction_line(self, reaction: Reaction) -> None:
        if reaction.should_say and reaction.line:
            self.show_bubble(reaction.line, kind=reaction.bubble)
            self.state.remember_line(reaction.line)

    def _schedule_performance_action(self, action: str, delay_ms: int) -> None:
        self._performance_after.append(self.root.after(delay_ms, lambda: self._perform_action(action)))

    def _cancel_performance_phrase(self) -> None:
        for after_id in self._performance_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._performance_after.clear()
        self._cancel_expression_after(reset=True)

    def _perform_action(self, action: str) -> None:
        if not action or action == "idle":
            return
        if action in {
            "twist_scoot",
            "mini_hop_shift",
            "relocate_hop",
            "roast_and_scoot",
            "retreat_to_corner",
            "drop_in",
        }:
            self._run_window_move_action(action)
            return
        if action.startswith("micro_"):
            self._perform_micro_action(action)
            return
        if action == "bob":
            self._run_large_action(ACTION_FRAMES["nod"])
            return
        if action == "wiggle":
            self._wiggle()
            return
        if action == "blink":
            self._blink()
            return
        if action == "peek":
            self._start_mouse_follow(1500, force=True)
            return
        if action == "scan":
            self._scan()
            return
        frames = ACTION_FRAMES.get(action)
        if frames:
            self._run_large_action(frames)

    def _perform_micro_action(self, action: str) -> None:
        if action == "micro_focus_pause":
            self._stop_mouse_follow()
            self._set_brow_pose("soft")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.94)
            self._animate_look((0.0, 0.0))
        elif action == "micro_side_eye":
            self._set_brow_pose("judge")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.98)
            self._animate_look((-3.1, 0.35))
        elif action == "micro_brow_judge":
            self._set_brow_pose("judge")
        elif action == "micro_snap_innocent":
            self._stop_mouse_follow()
            self._set_brow_pose("innocent")
            self._pupil_look = (0.0, 0.0)
            self._set_pupil_pose(0.0, 0.0, size_scale=1.08)
            self._schedule_expression_reset(1200)
        elif action == "micro_caught_guilty":
            self._stop_mouse_follow()
            self._set_brow_pose("guilty")
            self._pupil_look = (0.0, -0.1)
            self._set_pupil_pose(0.0, -0.1, size_scale=1.10)
            self._schedule_expression_reset(1400)
        elif action == "micro_holding_laugh":
            self._set_brow_pose("laugh")
            self._set_pupil_pose(0.45, -0.1, size_scale=1.03)
        elif action == "micro_peek_up":
            self._set_brow_pose("sulk")
            self._set_pupil_pose(1.9, -0.75, size_scale=0.92)
        elif action == "micro_soften":
            self._set_brow_pose("soft")
            self._set_pupil_pose(0.0, 0.0, size_scale=0.96)
        elif action == "micro_tiny_proud":
            self._set_brow_pose("proud")
            self._set_pupil_pose(-0.35, -0.25, size_scale=1.02)
        elif action == "micro_soft_reset":
            self._reset_expression_pose()

    def _set_eye_pose(self, pose: str) -> None:
        poses: dict[str, tuple[float, float, float]] = {
            "neutral": (0.0, 0.0, 1.0),
            "side_eye": (-3.1, 0.35, 0.98),
            "round": (0.0, 0.0, 1.08),
            "soft": (0.0, 0.0, 0.96),
            "peek_up": (1.9, -0.75, 0.92),
            "proud": (-0.35, -0.25, 1.02),
        }
        dx, dy, scale = poses.get(pose, poses["neutral"])
        self._pupil_look = (dx, dy)
        self._set_pupil_pose(dx, dy, size_scale=scale)

    def _set_brow_pose(self, pose: str) -> None:
        poses: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
            "neutral": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            "soft": ((0.0, -0.7, 0.0), (0.0, -0.5, 0.0)),
            "judge": ((-0.4, 1.7, -0.08), (0.3, 1.2, 0.09)),
            "innocent": ((0.0, -2.0, 0.02), (0.0, -1.6, -0.03)),
            "guilty": ((0.0, 2.3, 0.05), (0.0, 2.0, -0.05)),
            "laugh": ((0.0, 1.4, -0.02), (0.0, 1.2, 0.02)),
            "sulk": ((0.0, 2.6, -0.03), (0.0, 2.1, 0.03)),
            "proud": ((0.0, -1.4, -0.06), (0.0, -1.1, 0.06)),
        }
        left_spec, right_spec = poses.get(pose, poses["neutral"])
        for item, spec in ((self.left_brow, left_spec), (self.right_brow, right_spec)):
            base = self._brow_base_coords.get(item)
            if base:
                self.canvas.coords(item, *_brow_pose_coords(base, *spec))

    def _schedule_expression_reset(self, delay_ms: int) -> None:
        self._expression_after.append(self.root.after(delay_ms, self._reset_expression_pose))

    def _reset_expression_pose(self) -> None:
        self._cancel_expression_after(reset=False)
        self._set_brow_pose("neutral")
        self._set_pupil_pose(*self._pupil_look, size_scale=1.0)

    def _cancel_expression_after(self, reset: bool = True) -> None:
        for after_id in self._expression_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._expression_after.clear()
        if reset:
            self._set_brow_pose("neutral")
            self._set_pupil_pose(*self._pupil_look, size_scale=1.0)

    def _schedule_idle(self, first: bool = False) -> None:
        if first:
            delay = 10_000
        else:
            low = max(8, self.soul.idle_min_seconds)
            high = max(low, self.soul.idle_max_seconds)
            delay = random.randint(low, high) * 1000
        self.root.after(delay, self._idle_tick)

    def _idle_tick(self) -> None:
        policy = self._activity_policy()
        idle_cooldown = max(12, round(self.soul.cooldown_seconds * policy.cooldown_multiplier))
        if (
            not self._auto_reactions_paused()
            and policy.ambient_enabled
            and self.state.can_speak(idle_cooldown)
        ):
            context = self.ears.sample()
            if context.idle_seconds > 75 and random.random() < 0.70:
                self._ask_brain("bored")
            elif context.idle_seconds > 15 or random.random() < 0.35:
                self._ask_brain("idle")
        self._schedule_idle()

    def _schedule_ambient(self, first: bool = False) -> None:
        if first:
            delay = 12_000
        else:
            scaled_min = max(6_000, round(AMBIENT_MIN_MS / max(0.5, self.mood.frequency_multiplier)))
            scaled_max = max(scaled_min + 1_000, round(AMBIENT_MAX_MS / max(0.5, self.mood.frequency_multiplier)))
            delay = random.randint(scaled_min, scaled_max)
        self.root.after(delay, self._ambient_tick)

    def _ambient_tick(self) -> None:
        if self._auto_reactions_paused():
            self._schedule_ambient()
            return
        policy = self._activity_policy()
        if not policy.ambient_enabled:
            self._schedule_ambient()
            return
        world = self._world_state()
        cooldown = max(
            10,
            round(min(AMBIENT_COOLDOWN_SECONDS, self.mood.ambient_cooldown_seconds()) * policy.cooldown_multiplier),
        )
        decision = self.decision.ambient_decision(
            world,
            cooldown_seconds=cooldown,
            chance_multiplier=self.mood.ambient_chance_multiplier() * policy.proactive_detection,
            bubble_visible=bool(self._bubble_items),
        )
        if decision.should_react:
            self._ask_brain("ambient", world)
        self._schedule_ambient()

    def _animate(self) -> None:
        self._anim_tick += 1
        self.mood.tick()
        rate = self.mood.breath_rate()
        self._bob_phase += rate
        if self._bob_phase >= 1.0:
            self._bob_phase -= 1.0
            base = self.mood.breath_depth_base()
            self._breath_depth = base + random.uniform(-0.4, 0.6)
        breath = _breath_curve(self._bob_phase)
        next_y = -breath * self._breath_depth
        sway_amp = 0.45 + self.mood.energy * 0.45 + min(0.9, max(0.0, self.mood.frequency_multiplier - 1.0) * 0.22)
        sway_x = math.sin(self._anim_tick * 0.045) * sway_amp
        self._move_actor_items(sway_x - self._bob_x, next_y - self._bob_y)
        self._bob_x = sway_x
        self._bob_y = next_y
        self.root.after(50, self._animate)

    def _wiggle(self) -> None:
        if self._large_action_running:
            return
        frames = (
            (1.13, 0.88, 42),
            (0.93, 1.08, 54),
            (1.05, 0.96, 45),
            (1.0, 1.0, 1),
        )
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
            self._reset_pal_geometry()

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._reset_pal_geometry()
                self._rebound_after = None
                return
            sx, sy, delay = frames[index]
            self._set_pal_scale(sx, sy)
            self._rebound_after = self.root.after(delay, lambda: step(index + 1))

        step()

    def _run_large_action(self, frames: ActionFrames) -> None:
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._large_action_running = True

        jittered = _jitter_frames(frames)
        state = [0.0, 0.0, 1.0, 1.0]

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(jittered):
                self._finish_large_action()
                return
            dx, dy, sx, sy, delay = jittered[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = _ease_out_cubic((si + 1) / n)
            self._set_action_offset(
                state[0] + (dx - state[0]) * t,
                state[1] + (dy - state[1]) * t,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * t,
                state[3] + (sy - state[3]) * t,
            )
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        step()

    def _run_window_move_action(self, action: str) -> None:
        if self._dragging:
            return
        direction = self._movement_direction()
        if action == "twist_scoot":
            dx = direction * random.randint(10, 20)
            frames: ActionFrames = (
                (-direction * 4, 0, 0.96, 1.04, 60),
                (dx, 0, 1.06, 0.94, 130),
                (dx, 0, 1.0, 1.0, 80),
            )
        elif action == "mini_hop_shift":
            dx = direction * random.randint(24, 48)
            frames = (
                (0, 8, 1.14, 0.78, 80),
                (dx * 0.55, -18, 0.90, 1.16, 95),
                (dx, 4, 1.07, 0.90, 80),
                (dx, 0, 1.0, 1.0, 70),
            )
        elif action == "relocate_hop":
            dx = self._relocation_delta(random.randint(90, 150))
            frames = (
                (0, 10, 1.18, 0.74, 110),
                (dx * 0.42, -42, 0.88, 1.22, 130),
                (dx * 0.78, -34, 0.94, 1.10, 120),
                (dx, 8, 1.10, 0.86, 95),
                (dx, 0, 1.0, 1.0, 100),
            )
        elif action == "roast_and_scoot":
            dx = direction * random.randint(12, 18)
            self._set_brow_pose("innocent")
            self._set_eye_pose("round")
            frames = (
                (-direction * 3, 0, 0.98, 1.04, 70),
                (dx, 0, 1.05, 0.94, 120),
                (dx, 0, 1.0, 1.0, 80),
            )
        elif action == "retreat_to_corner":
            dx, dy = self._corner_retreat_delta()
            frames = (
                (dx * 0.12, 0, 0.96, 1.04, 90),
                (dx * 0.42, dy * 0.35, 0.90, 0.96, 130),
                (dx * 0.72, dy * 0.70, 0.86, 0.92, 130),
                (dx, dy, 0.92, 0.94, 120),
                (dx, dy, 1.0, 1.0, 100),
            )
        elif action == "drop_in":
            self._run_drop_in()
            return
        else:
            return
        self._run_window_move(frames)

    def _run_drop_in(self) -> None:
        if self._dragging:
            return
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        _left, top, _right, _bottom = self._desktop_bounds()
        start_y = max(top, y - 90)
        self.root.geometry(_geometry_position(x, start_y))
        self._position_bubble()
        dy = y - start_y
        self._run_window_move(
            (
                (0, dy * 0.55, 0.92, 1.12, 120),
                (0, dy + 10, 1.14, 0.78, 95),
                (0, dy - 4, 0.96, 1.05, 85),
                (0, dy, 1.0, 1.0, 80),
            )
        )

    def _run_window_move(self, frames: ActionFrames) -> None:
        if not frames:
            return
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self.root.update_idletasks()
        start_x = self.root.winfo_x()
        start_y = self.root.winfo_y()
        frames = self._clamped_window_frames(frames, start_x, start_y)
        self._window_move_running = True
        state = [0.0, 0.0, 1.0, 1.0]

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(frames):
                self._finish_window_move()
                return
            dx, dy, sx, sy, delay = frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = _ease_out_cubic((si + 1) / n)
            next_x = state[0] + (dx - state[0]) * t
            next_y = state[1] + (dy - state[1]) * t
            self.root.geometry(_geometry_position(start_x + next_x, start_y + next_y))
            if self._bubble_items:
                self._position_bubble()
            if self._chat_window:
                self._position_chat_input()
            self._set_pal_scale(
                state[2] + (sx - state[2]) * t,
                state[3] + (sy - state[3]) * t,
            )
            self._window_move_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        step()

    def _cancel_window_move(self) -> None:
        if self._window_move_after:
            self.root.after_cancel(self._window_move_after)
            self._window_move_after = None
        if self._window_move_running:
            self._finish_window_move()

    def _finish_window_move(self) -> None:
        self._window_move_after = None
        self._window_move_running = False
        self._reset_pal_geometry()
        if self._bubble_items:
            self._position_bubble()
        if self._chat_window:
            self._position_chat_input()

    def _movement_direction(self) -> int:
        self.root.update_idletasks()
        center_x = self.root.winfo_x() + self.width / 2
        left, _top, right, _bottom = self._desktop_bounds()
        screen_mid = (left + right) / 2
        if abs(center_x - screen_mid) < 120:
            return random.choice((-1, 1))
        return -1 if center_x > screen_mid else 1

    def _relocation_delta(self, distance: int) -> float:
        return self._movement_direction() * distance

    def _corner_retreat_delta(self) -> tuple[float, float]:
        self.root.update_idletasks()
        left, _top, right, bottom = self._desktop_bounds()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        target_x = left + 18 if current_x < (left + right) / 2 else right - self.width - 18
        target_y = bottom - self.height - 28
        return target_x - current_x, target_y - current_y

    def _clamped_window_frames(self, frames: ActionFrames, start_x: int, start_y: int) -> ActionFrames:
        final_dx, final_dy, _sx, _sy, _delay = frames[-1]
        left, top, right, bottom = self._desktop_bounds()
        max_x = max(left, right - self.width)
        max_y = max(top, bottom - self.height)
        clamped_final_x = _clamp(start_x + final_dx, left, max_x)
        clamped_final_y = _clamp(start_y + final_dy, top, max_y)
        allowed_dx = clamped_final_x - start_x
        allowed_dy = clamped_final_y - start_y
        ratio_x = allowed_dx / final_dx if final_dx else 1.0
        ratio_y = allowed_dy / final_dy if final_dy else 1.0
        return tuple((dx * ratio_x, dy * ratio_y, sx, sy, delay) for dx, dy, sx, sy, delay in frames)

    def _cancel_large_action(self) -> None:
        if self._large_action_after:
            self.root.after_cancel(self._large_action_after)
            self._large_action_after = None
        if self._large_action_running:
            self._finish_large_action()

    def _finish_large_action(self) -> None:
        self._large_action_after = None
        self._large_action_running = False
        self._reset_pal_geometry()

    def _set_action_offset(self, dx: float, dy: float) -> None:
        previous_x, previous_y = self._action_offset
        self._move_actor_items(dx - previous_x, dy - previous_y)
        self._action_offset = (dx, dy)

    def _set_pal_scale(self, sx: float, sy: float) -> None:
        previous_x, previous_y = self._pal_scale
        if previous_x == 0 or previous_y == 0:
            previous_x, previous_y = 1.0, 1.0
        self._scale_actor_items(sx / previous_x, sy / previous_y)
        self._pal_scale = (sx, sy)

    def _blink(self) -> None:
        if self._is_blinking or self._large_action_running:
            return
        self._is_blinking = True
        frames = ((0.35, 35), (0.08, 70), (0.35, 35), (1.0, 1))

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _schedule_blink(self) -> None:
        self.root.after(self.mood.blink_interval_ms(), self._blink_tick)

    def _blink_tick(self) -> None:
        if not self._dragging and not self._rebound_after and not self._large_action_running and not self._window_move_running:
            self._blink()
        self._schedule_blink()

    def _schedule_look(self) -> None:
        self.root.after(random.randint(LOOK_MIN_MS, LOOK_MAX_MS), self._look_tick)

    def _look_tick(self) -> None:
        if (
            not self._dragging
            and not self._is_blinking
            and not self._rebound_after
            and not self._large_action_running
            and not self._window_move_running
            and time.time() >= self._mouse_follow_until
        ):
            if self._should_start_selective_mouse_follow():
                self._start_mouse_follow(random.randint(850, 1500))
            else:
                self._animate_look(self._pick_look_target())
        self._schedule_look()

    def _should_start_selective_mouse_follow(self) -> bool:
        if time.time() < self._mouse_follow_cooldown_until:
            return False
        if not self._is_pointer_near_pal():
            return False
        if self._bubble_items and random.random() < 0.45:
            return True
        return random.random() < 0.35

    def _start_mouse_follow(self, duration_ms: int = 1200, force: bool = False) -> None:
        now = time.time()
        if self._large_action_running or self._is_blinking:
            return
        if not force and now < self._mouse_follow_cooldown_until:
            return
        self._mouse_follow_until = max(self._mouse_follow_until, now + duration_ms / 1000)
        if not self._mouse_follow_after:
            self._mouse_follow_tick()

    def _stop_mouse_follow(self) -> None:
        if self._mouse_follow_after:
            self.root.after_cancel(self._mouse_follow_after)
            self._mouse_follow_after = None
        self._mouse_follow_until = 0.0

    def _mouse_follow_tick(self) -> None:
        self._mouse_follow_after = None
        if time.time() >= self._mouse_follow_until or self._large_action_running or self._is_blinking:
            self._mouse_follow_cooldown_until = time.time() + MOUSE_FOLLOW_COOLDOWN_MS / 1000
            return
        self._look_at_pointer_now()
        self._mouse_follow_after = self.root.after(MOUSE_FOLLOW_TICK_MS, self._mouse_follow_tick)

    def _look_at_pointer_now(self) -> None:
        if self._is_blinking or self._large_action_running:
            return
        dx, dy = self._pointer_look_target()
        start_x, start_y = self._pupil_look
        next_x = start_x + (dx - start_x) * 0.55
        next_y = start_y + (dy - start_y) * 0.55
        self._pupil_look = (next_x, next_y)
        self._set_pupil_pose(next_x, next_y)

    def _pointer_look_target(self) -> tuple[float, float]:
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        local_x = pointer_x - self.root.winfo_x()
        local_y = pointer_y - self.root.winfo_y()
        dx = _clamp((local_x - PAL_LOOK_CENTER_X) / max(1, PAL_WIDTH) * 7.0, -3.4, 3.4)
        dy = _clamp((local_y - PAL_LOOK_CENTER_Y) / max(1, PAL_HEIGHT) * 7.0, -2.4, 2.4)
        return dx, dy

    def _is_pointer_near_pal(self) -> bool:
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        center_x = self.root.winfo_x() + PAL_CENTER_X
        center_y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT * 0.40
        return math.hypot(pointer_x - center_x, pointer_y - center_y) <= MOUSE_FOLLOW_NEAR_RADIUS

    def _scan(self) -> None:
        if self._is_blinking or self._large_action_running:
            return
        targets = ((-3.0, -0.3), (3.0, -0.2), (-2.2, 0.4), (2.4, 0.2), (0.0, 0.0))

        def step(index: int = 0) -> None:
            if index >= len(targets) or self._is_blinking or self._large_action_running:
                return
            dx, dy = targets[index]
            self._pupil_look = (dx, dy)
            self._set_pupil_pose(dx, dy)
            self.root.after(170, lambda: step(index + 1))

        step()

    def _pick_look_target(self) -> tuple[float, float]:
        if self._is_pointer_near_pal() and random.random() < 0.25:
            return self._pointer_look_target()
        return random.uniform(-2.4, 2.4), random.uniform(-1.4, 1.8)

    def _animate_look(self, target: tuple[float, float]) -> None:
        start_x, start_y = self._pupil_look
        target_x, target_y = target
        steps = 8

        def step(index: int = 1) -> None:
            if time.time() < self._mouse_follow_until:
                return
            if index > steps:
                self._pupil_look = (target_x, target_y)
                if not self._is_blinking:
                    self._set_pupil_pose(target_x, target_y)
                return
            t = index / steps
            eased = 1 - (1 - t) ** 3
            dx = start_x + (target_x - start_x) * eased
            dy = start_y + (target_y - start_y) * eased
            self._pupil_look = (dx, dy)
            if not self._is_blinking:
                self._set_pupil_pose(dx, dy)
            self.root.after(45, lambda: step(index + 1))

        step()

    def _set_pupil_pose(
        self,
        dx: float,
        dy: float,
        blink_scale: float = 1.0,
        size_scale: float | None = None,
    ) -> None:
        if size_scale is not None:
            self._pupil_size_scale = max(0.75, min(1.16, size_scale))
        for item, bounds in self._pupil_bounds.items():
            x1, y1, x2, y2 = bounds
            cx = (x1 + x2) / 2 + dx + self._bob_x
            cy = (y1 + y2) / 2 + dy + self._bob_y
            rx = (x2 - x1) / 2 * self._pupil_size_scale
            ry = max(0.8, (y2 - y1) / 2 * blink_scale * self._pupil_size_scale)
            self.canvas.coords(item, cx - rx, cy - ry, cx + rx, cy + ry)

    def show_bubble(self, text: str, milliseconds: int = 3200, kind: str = "speech") -> None:
        self._clear_bubble()
        is_thought, _fill, _outline, _text_fill = _bubble_style(kind)
        font_spec = THOUGHT_FONT if is_thought else BUBBLE_FONT
        font = tkfont.Font(family=font_spec[0], size=font_spec[1], slant=font_spec[2] if len(font_spec) > 2 else "roman")
        text_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
        pages = _paginate_bubble_text(text, text_width, font)
        self._show_bubble_page(pages, 0, milliseconds, kind)

    def _show_bubble_page(self, pages: list[str], index: int, milliseconds: int, kind: str) -> None:
        self._bubble_after = None
        self._clear_bubble(cancel_after=False)
        if index >= len(pages):
            return
        is_thought, fill, outline, text_fill = _bubble_style(kind)
        font_spec = THOUGHT_FONT if is_thought else BUBBLE_FONT
        font = tkfont.Font(family=font_spec[0], size=font_spec[1], slant=font_spec[2] if len(font_spec) > 2 else "roman")
        wrapped_text = pages[index]
        line_count = max(1, wrapped_text.count("\n") + 1)
        line_height = font.metrics("linespace")
        tail_space = 30 if is_thought else 18
        bubble_width = _bubble_page_width(wrapped_text, font)
        text_width = bubble_width - BUBBLE_PADDING_X * 2
        bubble_height = max(
            BUBBLE_MIN_HEIGHT,
            BUBBLE_PADDING_Y * 2 + line_height * line_count + tail_space,
        )
        self.bubble_canvas.configure(width=bubble_width, height=bubble_height)
        self._position_bubble(bubble_height, bubble_width)
        self.bubble_root.deiconify()
        self.bubble_root.lift()

        x1, y1 = 4, 4
        x2 = bubble_width - 4
        y2 = bubble_height - tail_space
        if is_thought:
            thought_items = _thought_bubble(
                self.bubble_canvas,
                x1,
                y1,
                x2,
                y2,
                fill=fill,
                outline=outline,
            )
            self._bubble_items.extend(thought_items)
            self._thought_dot_items = thought_items[-3:]
            self._thought_dot_base = [_oval_center_radius(self.bubble_canvas.coords(item)) for item in self._thought_dot_items]
            self._start_thought_dots()
        else:
            tail = (
                bubble_width / 2 - 12,
                y2,
                bubble_width / 2 + 12,
                y2,
                bubble_width / 2,
                bubble_height - 5,
            )
            self._bubble_items.extend(
                _speech_bubble(
                    self.bubble_canvas,
                    x1,
                    y1,
                    x2,
                    y2,
                    radius=14,
                    tail=tail,
                    fill=fill,
                    outline=outline,
                )
            )
        self._bubble_items.append(
            self.bubble_canvas.create_text(
                x1 + BUBBLE_PADDING_X,
                y1 + BUBBLE_PADDING_Y + line_height * line_count / 2,
                anchor="w",
                text=wrapped_text,
                width=text_width,
                fill=text_fill,
                font=font_spec,
                justify="left",
            )
        )
        if index + 1 < len(pages):
            delay = _bubble_page_duration(wrapped_text, milliseconds)
            self._bubble_after = self.root.after(
                delay + BUBBLE_PAGE_GAP_MS,
                lambda: self._show_bubble_page(pages, index + 1, milliseconds, kind),
            )
        else:
            delay = _bubble_page_duration(wrapped_text, milliseconds)
            self._bubble_after = self.root.after(delay, self._clear_bubble)

    def _start_thought_dots(self) -> None:
        if self._thought_dot_after:
            self.root.after_cancel(self._thought_dot_after)
            self._thought_dot_after = None
        self._thought_dot_phase = 0
        self._animate_thought_dots()

    def _animate_thought_dots(self) -> None:
        if not self._thought_dot_items:
            self._thought_dot_after = None
            return
        self._thought_dot_phase += 1
        for index, item in enumerate(self._thought_dot_items):
            if index >= len(self._thought_dot_base):
                continue
            cx, cy, radius = self._thought_dot_base[index]
            pulse = (math.sin(self._thought_dot_phase * 0.72 - index * 0.9) + 1) / 2
            animated_radius = radius * (0.72 + pulse * 0.42)
            animated_y = cy - pulse * 2.4
            self.bubble_canvas.coords(
                item,
                cx - animated_radius,
                animated_y - animated_radius,
                cx + animated_radius,
                animated_y + animated_radius,
            )
        self._thought_dot_after = self.root.after(95, self._animate_thought_dots)

    def _position_bubble(self, bubble_height: int | None = None, bubble_width: int | None = None) -> None:
        self.root.update_idletasks()
        height = bubble_height
        if height is None:
            height = int(float(self.bubble_canvas.cget("height")))
        width = bubble_width
        if width is None:
            width = int(float(self.bubble_canvas.cget("width")))
        left, top, right, bottom = self._desktop_bounds()
        x = self.root.winfo_x() + PAL_CENTER_X - width / 2
        y = self.root.winfo_y() + PAL_PAD_Y - height - BUBBLE_GAP
        x = min(max(left + 8, x), max(left + 8, right - width - 8))
        if y < top + 8:
            y = min(bottom - height - 8, self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + BUBBLE_GAP)
        y = min(max(top + 8, y), max(top + 8, bottom - height - 8))
        self.bubble_root.geometry(_geometry_with_size(width, height, x, y))

    def _clear_bubble(self, cancel_after: bool = True) -> None:
        if cancel_after and self._bubble_after:
            self.root.after_cancel(self._bubble_after)
        self._bubble_after = None
        if self._thought_dot_after:
            self.root.after_cancel(self._thought_dot_after)
            self._thought_dot_after = None
        for item in self._bubble_items:
            self.bubble_canvas.delete(item)
        self._bubble_items.clear()
        self._thought_dot_items.clear()
        self._thought_dot_base.clear()
        self.bubble_root.withdraw()


def _load_user32() -> object | None:
    try:
        return ctypes.windll.user32
    except AttributeError:
        return None


def _cursor_position(user32: object) -> tuple[int, int] | None:
    point = _WinPoint()
    if not user32.GetCursorPos(ctypes.byref(point)):
        return None
    return (point.x, point.y)


def _button_down(user32: object, virtual_key: int) -> bool:
    return bool(user32.GetAsyncKeyState(virtual_key) & 0x8000)


def _scale_coords(coords: list[float]) -> list[float]:
    return [
        value * PAL_SCALE + (PAL_PAD_X if index % 2 == 0 else PAL_PAD_Y)
        for index, value in enumerate(coords)
    ]


CodexStatusProfile = tuple[tuple[str, ...], str, tuple[str, ...], str, tuple[str, ...]]
ClaudeStatusProfile = tuple[tuple[str, ...], str, tuple[str, ...], str, tuple[str, ...]]


def _codex_event_level(status: str) -> str:
    if status in {"error", "blocked", "disconnected"}:
        return "error"
    if status in {"waiting_user", "reconnecting"}:
        return "warning"
    return "notice"


def _usage_event_level(level: str) -> str:
    if level == "critical":
        return "critical"
    if level in {"low", "reset_soon"}:
        return "warning"
    return "notice"


def _hardware_event_level(level: str) -> str:
    if level == "overloaded":
        return "critical"
    if level == "hot":
        return "warning"
    return "notice"


def _reaction_event_level(reaction: Reaction) -> str:
    event = (reaction.event or "").lower()
    if reaction.mood in {"sulky", "startled"} or any(key in event for key in ("error", "blocked", "critical", "overloaded")):
        return "warning"
    if reaction.mood in {"done", "happy", "proud"} or any(key in event for key in ("done", "refilled", "cooling")):
        return "notice"
    return "notice"


def _codex_usage_reaction(status: CodexUsageStatus, manual: bool = False) -> Reaction:
    if status.level == "unavailable":
        line = status.summary_line or "还没有 codex_usage_status.json。夹夹暂时不知道饭点。"
        return Reaction(
            True,
            line,
            "sleepy",
            "blink",
            "usage_thought",
            "quiet_companion",
            event="codex_usage_unavailable",
        )

    percent = _format_usage_percent(status.usage_remaining_percent)
    reset_label = format_reset_in(status.reset_in_seconds)
    reset_suffix = f" {reset_label}后回血。" if reset_label and reset_label != "现在" else ""
    if reset_label == "现在":
        reset_suffix = " 现在应该回血。"

    choices = {
        "normal": (
            (f"Codex 还有 {percent}%。暂时不用精打细算。{reset_suffix}",),
            "innocent",
            ("blink", "nod"),
            "quiet_companion",
            "usage_thought",
        ),
        "watch": (
            (
                f"还剩 {percent}%。不是贫穷，是需要规划。{reset_suffix}",
                f"Codex 还有 {percent}%。可以用，但不适合铺张。{reset_suffix}",
            ),
            "thinking",
            ("scan", "peek", "thinking_tilt"),
            "suspicious_observe",
            "usage_thought",
        ),
        "low": (
            (
                f"Codex 只剩 {percent}%。现在不适合让它写史诗。{reset_suffix}",
                f"还剩 {percent}%。额度正在用乖巧语气提醒你节制。{reset_suffix}",
            ),
            "suspicious",
            ("thinking_tilt", "sulk", "scan"),
            "fake_sulk",
            "usage_speech",
        ),
        "critical": (
            (
                f"剩 {percent}%。它不是累了，它是快没饭了。{reset_suffix}",
                f"Codex 只剩 {percent}%。现在每个大活都需要先过会计。{reset_suffix}",
            ),
            "sulky",
            ("flop", "shake", "sleepy_sag"),
            "fake_sulk",
            "usage_speech",
        ),
        "reset_soon": (
            (
                f"还剩 {reset_label}回血。先别让它干大活，等饭点。",
                f"reset 快到了，{reset_label}后回血。可以理性地期待一下。",
            ),
            "thinking",
            ("peek", "nod", "smug_sway"),
            "quiet_companion",
            "usage_thought",
        ),
        "refilled": (
            (
                f"回血了。Codex 又能继续装作很能干。",
                f"额度回来了。理性也可以顺便回来一点。",
            ),
            "done",
            ("happy_bounce", "nod", "smug_sway"),
            "tiny_celebrate",
            "usage_speech",
        ),
    }
    lines, mood, actions, performance, bubble = choices.get(status.level, choices["watch"])
    if manual and bubble == "usage_thought":
        bubble = "usage_speech" if status.level in {"low", "critical"} else "usage_thought"
    return Reaction(
        True,
        random.choice(lines).strip(),
        mood,
        random.choice(actions),
        bubble,
        performance,
        decision_reason=f"codex_usage={status.level}",
        event=f"codex_usage_{status.level}",
    )


def _format_usage_percent(percent: float | None) -> str:
    return "未知" if percent is None else f"{percent:.0f}"


def _hardware_status_reaction(snapshot: HardwareSnapshot, manual: bool = False) -> Reaction:
    summary = snapshot.summary_line or "硬件状态暂时没有说话。"
    level = snapshot.level
    if level == "unavailable":
        return Reaction(
            True,
            summary,
            "sleepy",
            "blink",
            "hardware_thought",
            "quiet_companion",
            event="hardware_unavailable",
        )
    if level == "normal":
        line = f"{summary}。夹夹暂时不熟。"
        return Reaction(
            True,
            line,
            "innocent",
            "blink",
            "hardware_thought" if manual else "thought",
            "quiet_companion",
            event="hardware_normal",
        )

    choices = {
        "busy": (
            (
                f"{summary}。它很忙，但温度还没开始表演红温文学。",
                f"{summary}。显存被占得很满，不过这更像忙，不像熟。",
                f"{summary}。电脑在工作，夹夹先不把它渲染成烤箱。",
            ),
            "thinking",
            ("scan", "patrol", "thinking_tilt"),
            "suspicious_observe",
        ),
        "warm": (
            (
                f"{summary}。有点热，夹夹先微微变红，不报警。",
                f"{summary}。电脑开始努力了。努力到我有点粉。",
                f"{summary}。这不是发烧，是硬件在认真冒充冷静。",
            ),
            "startled",
            ("scan", "thinking_tilt", "nod"),
            "suspicious_observe",
        ),
        "hot": (
            (
                f"{summary}。它在烤自己。我只是变红给你看。",
                f"{summary}。电风扇如果有尊严，现在应该在加班。",
                f"{summary}。这份热情有点物理意义了。",
            ),
            "startled",
            ("shake", "flop", "scan"),
            "fake_sulk",
        ),
        "overloaded": (
            (
                f"{summary}。任务们挤成早高峰，夹夹先熟为敬。",
                f"{summary}。内存和显存开始互相踩脚了。",
                f"{summary}。这不是卡顿，是硬件在进行个人奋斗。",
            ),
            "sulky",
            ("flop", "shake", "sleepy_sag"),
            "fake_sulk",
        ),
        "cooling": (
            (
                f"{summary}。温度下来了。我先不熟了。",
                f"{summary}。散热回到文具级别，暂时体面。",
                f"{summary}。电脑退烧了，夹夹恢复成办公用品。",
            ),
            "innocent",
            ("nod", "blink", "happy_bounce"),
            "quiet_companion",
        ),
    }
    lines, mood, actions, performance = choices.get(level, choices["warm"])
    bubble = "hardware_speech" if manual and level in {"busy", "hot", "overloaded"} else "hardware_thought"
    return Reaction(
        True,
        random.choice(lines),
        mood,
        random.choice(actions),
        bubble,
        performance,
        decision_reason=f"hardware={level}",
        event=f"hardware_{level}",
    )


_CODEX_UNKNOWN_LINES = (
    "我还没有收到 Codex 状态。很神秘，也很像没接线。",
    "Codex 状态栏空空的。像一份没有开始的计划。",
    "我暂时看不见 Codex。它可能在很认真地失联。",
    "这里没有 Codex 回声。夹夹先假装镇定。",
)


_CODEX_STALE_TAILS = (
    "这条有点旧，先别当新鲜证据。",
    "它像刚从缓存里醒来。",
    "时间戳不太年轻了。",
)


_CODEX_STATUS_PROFILES: dict[str, CodexStatusProfile] = {
    "thinking": (
        ("Codex 在想{summary}", "Codex 正在脑内排队{summary}", "Codex 进入思考模式{summary}"),
        "thinking",
        ("thinking_tilt", "scan", "nod"),
        "thought",
        (
            "它的脑内文件夹正在小声翻页。",
            "先别催，它正在给思路找出口。",
            "姿势很认真，含金量待观察。",
            "它像把一句话拆成了三层意思。",
            "夹夹先眨眼站岗。",
            "现在空气里有一点点加载味。",
        ),
    ),
    "reading": (
        ("Codex 正在读上下文{summary}", "Codex 在翻记录{summary}", "Codex 正在补课{summary}"),
        "thinking",
        ("scan", "thinking_tilt", "peek"),
        "thought",
        (
            "它努力装作自己从来没忘过。",
            "记忆力正在临时营业。",
            "先让它把线头捡起来。",
            "它看起来像在给上下文排座位。",
            "夹夹不催，夹夹只是盯着。",
            "这一步很像认真，其实也可能是找路。",
        ),
    ),
    "working": (
        ("Codex 正在工作{summary}", "Codex 开始推进{summary}", "Codex 正在处理{summary}"),
        "thinking",
        ("nod", "patrol", "thinking_tilt"),
        "thought",
        (
            "我暂时假装不监督。",
            "它看起来终于和任务正面相遇了。",
            "桌面上出现了罕见的推进迹象。",
            "这不像拖延，夹夹有点不适应。",
            "我先把冷箭收起来半根。",
            "它正在把计划从空气里拽下来。",
        ),
    ),
    "editing": (
        ("Codex 正在改文件{summary}", "Codex 手里有补丁{summary}", "Codex 正在动代码{summary}"),
        "focused",
        ("patrol", "scan", "wiggle"),
        "thought",
        (
            "现在每一笔都可能有后果。",
            "小心，它正在给文件做微整形。",
            "代码被夹住了，暂时不能逃跑。",
            "希望它没有把眼睛也顺手改掉。",
            "补丁正在靠近，表情很无辜。",
            "这一步需要一点信任，和一点备份。",
        ),
    ),
    "running": (
        ("Codex 在跑命令{summary}", "Codex 把事情交给终端了{summary}", "Codex 正在执行命令{summary}"),
        "thinking",
        ("scan", "thinking_tilt", "peek"),
        "thought",
        (
            "现在把紧张交给终端。",
            "黑框框正在替大家承受压力。",
            "希望输出不要突然很有性格。",
            "这时候最适合假装从容。",
            "夹夹看不懂，但夹夹会装。",
            "进度条没有出现，所以焦虑比较自由。",
        ),
    ),
    "testing": (
        ("Codex 在检查结果{summary}", "Codex 正在验收{summary}", "Codex 开始看测试{summary}"),
        "thinking",
        ("thinking_tilt", "scan", "nod"),
        "thought",
        (
            "希望测试不要突然拥有个性。",
            "事实正在准备发表意见。",
            "这一步通常负责打破幻想。",
            "夹夹先把庆祝动作憋住。",
            "输出很快会说明谁在嘴硬。",
            "测试通过前，所有自信都只是预告片。",
        ),
    ),
    "reconnecting": (
        ("Codex 好像在重连{summary}", "Codex 正在找回连接{summary}", "Codex 信号有点飘{summary}"),
        "suspicious",
        ("scan", "peek", "thinking_tilt"),
        "thought",
        (
            "网络也有逃避型人格。",
            "它正在和远方互相假装在线。",
            "连接这件事看起来很需要缘分。",
            "夹夹先守着，不保证优雅。",
            "空气里有一点掉线的礼貌。",
            "它可能只是去很远的地方想了一下。",
        ),
    ),
    "disconnected": (
        ("Codex 暂时断线了{summary}", "Codex 现在不在服务区{summary}", "Codex 的连接断开了{summary}"),
        "sleepy",
        ("hide", "blink", "flop"),
        "thought",
        (
            "夹夹先小声站岗。",
            "这不是沉默，是被迫安静。",
            "桌面突然少了一个会思考的借口。",
            "我会在这里，虽然我只是文具。",
            "先不要慌，慌也可以小一点。",
            "它不说话的时候，任务看起来更诚实了。",
        ),
    ),
    "waiting_user": (
        ("Codex 好像在等你{summary}", "Codex 把球递回来了{summary}", "Codex 需要你点头{summary}"),
        "smirk",
        ("bob", "peek", "smug_sway"),
        "speech",
        (
            "我只是小文具，我不催。",
            "你看，轮到人类承担一点点存在感了。",
            "这一步需要你的许可，不需要你的逃避。",
            "它停住了，像在礼貌地盯着你。",
            "夹夹没有催，只是眼睛比较圆。",
            "你可以慢慢来，但它确实在等。",
        ),
    ),
    "done": (
        ("Codex 回来了{summary}", "Codex 说它做完了{summary}", "Codex 收工了{summary}"),
        "done",
        ("bob", "happy_bounce", "nod"),
        "speech",
        (
            "看起来它假装一切都在掌控中。",
            "成功的样子很短暂，建议立刻验一下。",
            "夹夹先鼓掌半下。",
            "它带着一种刚刚没有迷路的自信。",
            "现在可以开始怀疑它哪里改对了。",
            "这听起来像好消息，暂时。",
        ),
    ),
    "error": (
        ("嗯，Codex 遇到报错{summary}", "Codex 撞到错误了{summary}", "Codex 被电脑反驳了{summary}"),
        "thinking",
        ("blink", "thinking_tilt", "flop"),
        "thought",
        (
            "电脑也会表达不同意。",
            "现实轻轻敲了一下桌面。",
            "这不是失败，是错误比较会说话。",
            "夹夹建议先深呼吸，再怪终端。",
            "它的无辜程度正在上升。",
            "现在最重要的是别把锅递给眉毛。",
        ),
    ),
    "blocked": (
        ("Codex 卡住了{summary}", "Codex 走到门口停下了{summary}", "Codex 需要下一步指令{summary}"),
        "thinking",
        ("blink", "thinking_tilt", "peek"),
        "speech",
        (
            "这听起来很像需要人类点头。",
            "它不是摆烂，是没有钥匙。",
            "夹夹看见了一个小小的岔路口。",
            "现在需要决定，不是再准备一下。",
            "任务没有消失，只是站得很安静。",
            "你一句话，可能比它想十分钟有用。",
        ),
    ),
}


def _codex_status_reaction(
    status: CodexStatus,
    recent_fragments: list[str] | None = None,
    manual: bool = False,
) -> Reaction:
    status_key = "running" if status.status == "running_command" else status.status
    profile = _CODEX_STATUS_PROFILES.get(status_key)
    if not profile:
        return Reaction(False)

    prefixes, mood, actions, bubble, tails = profile
    summary = f"：{status.summary}" if status.summary else ""
    prefix_template = _pick_status_fragment(prefixes, recent_fragments)
    prefix = prefix_template.format(summary=summary, status=status_key)
    tail = _pick_status_fragment(tails, recent_fragments)
    line = f"{prefix}。{tail}"
    if manual and status.stale:
        line = f"{line} {_pick_status_fragment(_CODEX_STALE_TAILS, recent_fragments)}"
    return Reaction(True, line, mood, random.choice(actions), _source_bubble_kind("codex", bubble), event=f"codex_{status_key}")


_CLAUDE_NO_SESSION_LINES = (
    "没有发现活跃的 Claude 会话。桌面突然少了一位假装冷静的同事。",
    "Claude 现在没有露面。任务看起来少了一个借口。",
    "我没有看到 Claude 在跑。空气里只剩人类责任。",
    "Claude 不在场。夹夹先把监督权轻轻捡起来。",
)


_CLAUDE_OVERVIEW_TAILS = (
    "它们看起来各忙各的，也各有一点可疑。",
    "场面很像协作，暂时。",
    "多线程热闹起来了，人类可以先别装没看见。",
    "夹夹负责围观，不负责背锅。",
    "这张桌面现在有一点点办公室味。",
)


_CLAUDE_IDLE_OVERVIEW_TAILS = (
    "大家都安静了。可能是完成了，也可能是在等勇气。",
    "它们没有明显动作。发呆也算一种状态，勉强。",
    "Claude 会话还在，但推进感比较轻。",
    "桌面进入了很礼貌的停顿。",
)


_CLAUDE_SPINNER_WORDS = (
    "Patch-waltzing",
    "Context-combing",
    "Prompt-polishing",
    "Diff-dusting",
    "Token-folding",
    "Stack-sorting",
    "Syntax-squinting",
    "Error-negotiating",
    "Cache-rummaging",
    "Terminal-humming",
    "Plan-unfolding",
    "File-straightening",
    "Trace-stitching",
    "Commit-gazing",
    "Log-tasting",
    "Cursor-drifting",
    "Path-untangling",
    "Todo-stacking",
    "Loop-coaxing",
    "Schema-buffing",
    "Hook-tapping",
    "Line-straightening",
    "Json-massaging",
    "Yaml-teasing",
    "Regex-squinting",
    "Shell-surfacing",
    "Bug-bargaining",
    "Patch-folding",
    "Context-ironing",
    "Token-shuffling",
    "Branch-balancing",
    "Output-sifting",
    "Intent-buffering",
    "Result-smoothing",
    "Stack-tracing",
    "Lint-whispering",
)


_CLAUDE_SPINNER_TAILS = (
    "如果它有 spinner，现在大概写着 {spinner}。",
    "状态词可以叫 {spinner}，听起来就很像认真。",
    "角落里的小字应该是 {spinner}，懂不懂另说。",
    "这一步可以命名为 {spinner}，很高级，也很可疑。",
    "我猜它正在 {spinner}，主要是听起来像在做事。",
    "Claude 味出来了，屏幕边缘仿佛写着 {spinner}。",
)


_CLAUDE_STATUS_PROFILES: dict[str, ClaudeStatusProfile] = {
    "started": (
        ("{label} 在 {project} 开工了", "{label} 出现在 {project}", "新的 {label} 会话进了 {project}"),
        "smirk",
        ("scan", "peek", "nod"),
        "thought",
        (
            "希望效率比你高一点点。",
            "它看起来很专业，先不揭穿。",
            "桌面多了一位会假装镇定的同事。",
            "夹夹先登记一下，不代表信任。",
            "任务突然有了第二个目击者。",
        ),
    ),
    "ended": (
        ("{label} 在 {project} 收工了", "{label} 离开了 {project}", "一个 Claude 会话从 {project} 退场了"),
        "thinking",
        ("blink", "nod", "hide"),
        "thought",
        (
            "不知道是完成了还是体面撤退。",
            "它走得很安静，像结果还没完全负责。",
            "桌面少了一个会解释的声音。",
            "夹夹先不评价，虽然很想。",
            "如果它真的做完了，那就很稀有。",
        ),
    ),
    "editing": (
        ("{label} 在 {project} 改代码", "Claude 在 {project} 动文件了", "{label} 手里现在有改动"),
        "focused",
        ("patrol", "scan", "wiggle"),
        "thought",
        (
            "代码正在接受另一种命运。",
            "希望它比刚才那个人类少犹豫一点。",
            "补丁味飘出来了，夹夹先眯一下眼。",
            "文件被盯上了，逃不掉了。",
            "这一步很像认真，也很像快出事。",
        ),
    ),
    "running": (
        ("{label} 在 {project} 跑命令", "Claude 把 {project} 交给终端了", "{label} 在 {project} 执行东西"),
        "thinking",
        ("scan", "thinking_tilt", "peek"),
        "thought",
        (
            "黑框框又开始承担情绪价值。",
            "终端输出马上会变成现实证词。",
            "夹夹看不懂，但夹夹知道要紧张。",
            "这时候最好不要把自信说太满。",
            "命令在跑，借口也暂时跑不动。",
        ),
    ),
    "reading": (
        ("{label} 在 {project} 读文件", "Claude 在 {project} 翻材料", "{label} 开始补上下文"),
        "thinking",
        ("scan", "thinking_tilt", "nod"),
        "thought",
        (
            "它正在努力假装自己一直都懂。",
            "上下文被翻出来晒太阳了。",
            "先让它读，读完再看它怎么装从容。",
            "文件没有逃跑，但尊严可能会。",
            "夹夹安静三秒，显得很懂事。",
        ),
    ),
    "searching": (
        ("{label} 在 {project} 搜索", "Claude 在 {project} 到处找线索", "{label} 开始翻箱倒柜"),
        "suspicious",
        ("scan", "peek", "thinking_tilt"),
        "thought",
        (
            "它看起来像终于承认自己不知道。",
            "找资料这件事，比嘴硬健康一点。",
            "线索正在被迫出现。",
            "搜索很忙，方向感暂时未知。",
            "夹夹先不说它迷路，先。",
        ),
    ),
    "thinking": (
        ("{label} 在 {project} 思考", "Claude 在 {project} 脑内排队", "{label} 暂时进入沉思"),
        "thinking",
        ("thinking_tilt", "nod", "blink"),
        "thought",
        (
            "它的沉默看起来比人类有条理。",
            "思路可能在路上，也可能刚起床。",
            "夹夹先装作相信这是深度思考。",
            "空气里有一点点计算的味道。",
            "它没有卡住，它只是把卡住包装得更优雅。",
        ),
    ),
    "idle": (
        ("{label} 在 {project} 安静了", "Claude 在 {project} 发呆中", "{label} 暂时没有明显动作"),
        "sleepy",
        ("blink", "hide", "flop"),
        "thought",
        (
            "它可能在等你，也可能在等奇迹。",
            "静止很礼貌，推进就不一定了。",
            "桌面进入了低速燃烧。",
            "夹夹没有催，只是比较清醒。",
            "发呆不是错，太久就像计划。",
        ),
    ),
}


def _claude_change_priority(activity: str) -> int:
    return {
        "editing": 0,
        "running": 1,
        "searching": 2,
        "reading": 3,
        "thinking": 4,
        "idle": 5,
    }.get(activity, 6)


def _pick_claude_session(sessions: list[ClaudeSession]) -> ClaudeSession:
    return sorted(sessions, key=lambda s: (_claude_change_priority(s.activity), s.project, s.pid))[0]


def _claude_session_reaction(
    session: ClaudeSession,
    event: str,
    recent_fragments: list[str] | None = None,
) -> Reaction:
    event_key = event if event in _CLAUDE_STATUS_PROFILES else session.activity
    profile = _CLAUDE_STATUS_PROFILES.get(event_key)
    if not profile:
        return Reaction(False)

    prefixes, mood, actions, bubble, tails = profile
    prefix = _pick_status_fragment(prefixes, recent_fragments).format(
        label=session.label(),
        project=session.project,
        activity=session.activity_zh(),
        idle=_format_idle_seconds(session.idle_seconds),
    )
    tail_template = _pick_status_fragment(_claude_tail_choices(tails, event_key), recent_fragments)
    tail = _format_claude_status_text(tail_template, session, recent_fragments)
    return Reaction(True, f"{prefix}。{tail}", mood, random.choice(actions), _source_bubble_kind("claude", bubble), event=f"claude_{event_key}")


def _claude_overview_reaction(
    overview: ClaudeOverview,
    recent_fragments: list[str] | None = None,
) -> Reaction:
    alive = [s for s in overview.sessions if s.alive]
    if not alive:
        line = _pick_status_fragment(_CLAUDE_NO_SESSION_LINES, recent_fragments)
        return Reaction(True, line, "sleepy", "blink", "claude_thought", event="claude_no_session")

    if len(alive) == 1:
        session = alive[0]
        return _claude_session_reaction(session, session.activity, recent_fragments)

    active = [s for s in alive if s.activity not in ("idle", "offline")]
    focus = _pick_claude_session(active or alive)
    summary = _claude_compact_summary(alive)
    if active:
        prefixes = (
            "Claude 有 {count} 个会话：{summary}",
            "现在有 {count} 个 Claude 会话在场，最忙的是 {focus_project} 里的 {focus_label}",
            "Claude 场面有点热闹：{summary}",
        )
        tails = _CLAUDE_OVERVIEW_TAILS + _CLAUDE_SPINNER_TAILS
        mood, actions = "smirk", ("scan", "peek", "nod")
    else:
        prefixes = (
            "Claude 有 {count} 个会话都安静着",
            "现在 {count} 个 Claude 会话都没明显动作",
            "Claude 会话还在：{summary}",
        )
        tails = _CLAUDE_IDLE_OVERVIEW_TAILS
        mood, actions = "sleepy", ("blink", "hide", "flop")

    prefix = _pick_status_fragment(prefixes, recent_fragments).format(
        count=len(alive),
        summary=summary,
        focus_label=focus.label(),
        focus_project=focus.project,
        focus_activity=focus.activity_zh(),
    )
    tail_template = _pick_status_fragment(tails, recent_fragments)
    tail = _format_claude_status_text(tail_template, focus, recent_fragments)
    return Reaction(True, f"{prefix}。{tail}", mood, random.choice(actions), "claude_thought", event="claude_overview")


def _claude_compact_summary(sessions: list[ClaudeSession]) -> str:
    ordered = sorted(sessions, key=lambda s: (_claude_change_priority(s.activity), s.project, s.pid))
    parts = [f"{s.label()} 在 {s.project} {s.activity_zh()}" for s in ordered[:3]]
    if len(ordered) > 3:
        parts.append(f"另有 {len(ordered) - 3} 个")
    return " / ".join(parts)


def _format_idle_seconds(seconds: float) -> str:
    if seconds < 60:
        return f"{round(seconds)} 秒"
    minutes = round(seconds / 60)
    return f"{minutes} 分钟"


def _claude_tail_choices(tails: tuple[str, ...], event: str) -> tuple[str, ...]:
    if event in {"started", "editing", "running", "reading", "searching", "thinking"}:
        return tails + _CLAUDE_SPINNER_TAILS
    return tails


def _format_claude_status_text(
    template: str,
    session: ClaudeSession,
    recent_fragments: list[str] | None = None,
) -> str:
    spinner = ""
    if "{spinner}" in template:
        spinner = _pick_status_fragment(_CLAUDE_SPINNER_WORDS, recent_fragments)
    return template.format(
        label=session.label(),
        project=session.project,
        activity=session.activity_zh(),
        idle=_format_idle_seconds(session.idle_seconds),
        spinner=spinner,
    )


def _pick_status_fragment(
    fragments: tuple[str, ...],
    recent_fragments: list[str] | None = None,
) -> str:
    if not fragments:
        return ""
    if recent_fragments is None:
        return random.choice(fragments)

    recent_window = set(recent_fragments[-max(1, min(len(fragments) - 1, 8)):])
    choices = [fragment for fragment in fragments if fragment not in recent_window]
    fragment = random.choice(choices or list(fragments))
    recent_fragments.append(fragment)
    del recent_fragments[:-12]
    return fragment


def _source_bubble_kind(source: str, bubble: str) -> str:
    shape = "thought" if bubble == "thought" else "speech"
    if source in {"codex", "claude"}:
        return f"{source}_{shape}"
    return shape


def _bubble_style(kind: str) -> BubbleStyle:
    return BUBBLE_STYLES.get(kind, BUBBLE_STYLES["thought" if kind == "thought" else "speech"])


def _paginate_bubble_text(text: str, max_width: int, font: tkfont.Font) -> list[str]:
    lines = _wrap_bubble_lines(text, max_width, font)
    return [
        "\n".join(lines[index:index + BUBBLE_MAX_LINES])
        for index in range(0, len(lines), BUBBLE_MAX_LINES)
    ] or ["..."]


def _bubble_page_width(text: str, font: tkfont.Font) -> int:
    widest = max((font.measure(line) for line in text.splitlines() if line), default=0)
    natural_width = widest + BUBBLE_PADDING_X * 2 + 12
    return max(BUBBLE_MIN_WIDTH, min(BUBBLE_WIDTH, math.ceil(natural_width)))


def _wrap_bubble_lines(text: str, max_width: int, font: tkfont.Font) -> list[str]:
    lines: list[str] = []
    paragraphs = text.strip().splitlines() or [text.strip()]
    for paragraph in paragraphs:
        paragraph_lines: list[str] = []
        current = ""
        for token in _bubble_wrap_tokens(paragraph):
            if token.isspace():
                if current and not current.endswith(" "):
                    current += " "
                continue

            token = token.lstrip() if not current else token
            if _is_line_leading_punctuation(token):
                if current:
                    if font.measure(current + token) <= max_width or len(current) <= 3:
                        current += token
                    else:
                        steal_count = min(2, len(current) - 3)
                        paragraph_lines.append(current[:-steal_count].rstrip())
                        current = current[-steal_count:] + token
                elif paragraph_lines:
                    paragraph_lines[-1] += token
                else:
                    current = token
                continue
            candidate = current + token
            if not current and font.measure(token) > max_width:
                pieces = _split_oversized_bubble_token(token, max_width, font)
                paragraph_lines.extend(pieces[:-1])
                current = pieces[-1] if pieces else ""
                continue
            if not current or font.measure(candidate.rstrip()) <= max_width:
                current = candidate
                continue

            paragraph_lines.append(current.rstrip())
            if font.measure(token) <= max_width:
                current = token
            else:
                pieces = _split_oversized_bubble_token(token, max_width, font)
                paragraph_lines.extend(pieces[:-1])
                current = pieces[-1] if pieces else ""

        if current:
            paragraph_lines.append(current.rstrip())
        lines.extend(_rebalance_short_wrapped_lines(paragraph_lines, max_width, font))

    return lines or ["..."]


def _bubble_wrap_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    ascii_run = ""
    for char in text:
        if char.isascii() and not char.isspace():
            ascii_run += char
            continue
        if ascii_run:
            tokens.append(ascii_run)
            ascii_run = ""
        tokens.append(" " if char.isspace() else char)
    if ascii_run:
        tokens.append(ascii_run)
    return tokens


def _is_line_leading_punctuation(token: str) -> bool:
    return bool(token) and token[0] in "，。！？；：、）】》”’.,!?;:)]}"


def _split_oversized_bubble_token(token: str, max_width: int, font: tkfont.Font) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if not current or font.measure(candidate) <= max_width:
            current = candidate
            continue
        pieces.append(current)
        current = char
    if current:
        pieces.append(current)
    return pieces


def _rebalance_short_wrapped_lines(lines: list[str], max_width: int, font: tkfont.Font) -> list[str]:
    result = list(lines)
    min_previous_width = max_width * 0.74
    for index in range(1, len(result)):
        current = result[index].strip()
        previous = result[index - 1].rstrip()
        if not _is_short_wrapped_line(current) or len(previous) <= 6:
            continue
        for steal_count in range(min(5, len(previous) - 4), 0, -1):
            borrowed = previous[-steal_count:]
            candidate = borrowed + current
            remaining = previous[:-steal_count].rstrip()
            if remaining and font.measure(remaining) >= min_previous_width and font.measure(candidate) <= max_width:
                result[index - 1] = remaining
                result[index] = candidate
                break
    return result


def _is_short_wrapped_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if len(stripped) <= 2:
        return True
    if len(stripped) <= 4 and not any(char.isspace() for char in stripped):
        return True
    return False


def _bubble_page_duration(text: str, requested_ms: int) -> int:
    readable_chars = len(text.replace("\n", ""))
    line_count = max(1, text.count("\n") + 1)
    natural_ms = BUBBLE_PAGE_MIN_MS + readable_chars * BUBBLE_PAGE_CHAR_MS + (line_count - 1) * 260
    target_ms = max(requested_ms, natural_ms)
    return max(BUBBLE_PAGE_MIN_MS, min(BUBBLE_PAGE_MAX_MS, target_ms))


def _oval_center_radius(coords: list[float]) -> tuple[float, float, float]:
    x1, y1, x2, y2 = coords
    return (x1 + x2) / 2, (y1 + y2) / 2, min(x2 - x1, y2 - y1) / 2


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _brow_pose_coords(base: tuple[float, ...], dx: float, dy: float, tilt: float) -> list[float]:
    xs = [base[i] for i in range(0, len(base), 2)]
    center_x = sum(xs) / max(1, len(xs))
    coords: list[float] = []
    for i in range(0, len(base), 2):
        x = base[i]
        y = base[i + 1]
        coords.extend((x + dx, y + dy + (x - center_x) * tilt))
    return coords


def _oval_bounds(cx: float, cy: float, rx: float, ry: float | None = None) -> tuple[float, float, float, float]:
    radius_y = rx if ry is None else ry
    return (
        (cx - rx) * PAL_SCALE + PAL_PAD_X,
        (cy - radius_y) * PAL_SCALE + PAL_PAD_Y,
        (cx + rx) * PAL_SCALE + PAL_PAD_X,
        (cy + radius_y) * PAL_SCALE + PAL_PAD_Y,
    )


def _path_coords(
    start: tuple[float, float],
    curves: tuple[tuple[tuple[float, float], tuple[float, float], tuple[float, float]], ...],
) -> list[float]:
    coords = [start[0], start[1]]
    current = start
    for control_1, control_2, end in curves:
        for x, y in _sample_cubic(current, control_1, control_2, end, steps=18):
            coords.extend((x, y))
        current = end
    return coords


def _sample_cubic(
    start: tuple[float, float],
    control_1: tuple[float, float],
    control_2: tuple[float, float],
    end: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    samples = []
    for step in range(1, steps + 1):
        t = step / steps
        inverse = 1 - t
        x = (
            inverse**3 * start[0]
            + 3 * inverse**2 * t * control_1[0]
            + 3 * inverse * t**2 * control_2[0]
            + t**3 * end[0]
        )
        y = (
            inverse**3 * start[1]
            + 3 * inverse**2 * t * control_1[1]
            + 3 * inverse * t**2 * control_2[1]
            + t**3 * end[1]
        )
        samples.append((x, y))
    return samples


def _speech_bubble(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    tail: tuple[int, int, int, int, int, int],
    fill: str,
    outline: str,
) -> list[int]:
    tx1, ty1, tx2, ty2, tx3, ty3 = tail
    return [
        _rounded_polygon(
            canvas,
            x1,
            y1,
            x2,
            y2,
            radius,
            tx1,
            ty1,
            tx2,
            ty2,
            tx3,
            ty3,
            fill=fill,
            outline=outline,
        )
    ]


def _thought_bubble(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fill: str,
    outline: str,
) -> list[int]:
    items = [
        _rounded_rect(canvas, x1, y1, x2, y2, 16, fill=fill, outline=outline),
    ]
    center_x = (x1 + x2) / 2
    dots = (
        (center_x + 8, y2 + 8, 5),
        (center_x + 1, y2 + 18, 3.5),
        (center_x - 5, y2 + 25, 2.2),
    )
    for cx, cy, radius in dots:
        items.append(canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill=fill, outline=outline))
    return items


def _rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **kwargs: object,
) -> int:
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)


def _rounded_polygon(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    tx1: int,
    ty1: int,
    tx2: int,
    ty2: int,
    tx3: int,
    ty3: int,
    **kwargs: object,
) -> int:
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        tx2,
        ty2,
        tx3,
        ty3,
        tx1,
        ty1,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)
