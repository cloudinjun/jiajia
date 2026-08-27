from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime
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
from typing import Callable, NotRequired, TypedDict

from .activity import ActivityPolicy, policy_for_frequency
from .actions import ACTION_LABELS, ACTION_MENU_GROUPS
from .alive import AliveCue, AliveLayer
from .anim_physics import (
    SquashStretchSpring, ExpressionTweener, easing_for_action,
)
from .animation_resolver import AnimationResolver, ResolvedAnimation
from .animation_manifest import load_animation_manifest
from .animation_player import AnimationCallbacks, AnimationPlayer
from .brain_ollama import OllamaBrain
from .chat import ChatSession, PalChatBrain, build_chat_context, detect_chat_command, local_status_reaction
from .claude_account_usage import ClaudeAccountUsageMonitor, ClaudeAccountUsageStatus, format_reset_in as format_claude_account_reset_in
from .decorations import DecorationDefinition, load_decoration_manifest
from .mood import MoodEngine, FREQUENCY_PRESETS, FREQUENCY_DEFAULT
from .claude_status import ClaudeOverview, ClaudeSession, ClaudeStatusMonitor
from .claude_usage import ClaudeUsageMonitor, ClaudeUsageStatus
from .codex_status import CodexStatus, CodexStatusMonitor
from .codex_usage import CodexUsageMonitor, CodexUsageStatus, format_reset_in
from .decision import DecisionEngine, DecisionResult
from .ears import Ears
from .event_log import EventLog
from .eyes import Eyes
from .hardware_status import HardwareSnapshot, HardwareStatusMonitor
from .interruptibility import Interruptibility, assess_interruptibility
from .openai_billing import OpenAIBillingMonitor, OpenAIBillingStatus
from .care import CareEngine
from .particles import ParticleEmitter
from .i18n import I18n
from .language import LANGUAGE_OPTIONS, language_label, normalize_language, soul_path_for_language
from .performance import PERFORMANCE_PHRASES, phrase_for_reaction
from .quiz import (
    QuizPacket,
    QuizSession,
    QuizStore,
    choose_result,
    current_question,
    load_quiz_packets,
    record_answer,
    score_packet,
)
from .quiz_safety import validate_quiz_packet
from .prop_shapes import (
    ACTION_FACE_SCRIPTS,
    ACTION_PROP_CUES,
    EYE_FX_SHAPES,
    FACE_DECALS,
    GRIP_POINTS,
    PROP_SHAPES,
    SHAPE_FX,
    apply_shape_fx,
    build_prop_timeline,
    inertia_step,
    prop_cue_duration_ms,
    transform_shape,
)
from .rig_pose import bend_point, posed_chin_points, posed_tail_points
from .soul import Soul, load_soul
from .state import PalState, Reaction
from .stats import PalStats, load_stats, save_stats
from .svg_canvas import draw_svg_asset
from .world import MoodSnapshot, WorldState


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
QUIZ_FIRST_HEARTBEAT_MS = 90_000
QUIZ_INTERVAL_MS = {
    "quiet": 60 * 60 * 1000,
    "normal": 30 * 60 * 1000,
    "active": 16 * 60 * 1000,
    "hyper": 9 * 60 * 1000,
}
QUIZ_DAILY_LIMIT = {"quiet": 0, "normal": 1, "active": 2, "hyper": 3}
QUIZ_CARD_WIDTH = 360
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
USAGE_BADGE_WIDTH = 104
USAGE_BADGE_HEIGHT = 32
USAGE_BADGE_BOTTOM_GAP = 14
STATUS_BADGES: dict[str, tuple[str, str, str]] = {
    "codex_waiting": ("C", "#f0b429", "circle"),
    "hardware_hot": ("°", "#d86b6b", "circle"),
    "usage_low": ("%", "#e4a03b", "circle"),
    "focus_mode": ("F", "#7c8db5", "circle"),
    "do_not_disturb": ("D", "#7c8db5", "circle"),
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
PAL_HIT_MARGIN_X = 70
PAL_HIT_MARGIN_Y = 58
CODEX_STATUS_POLL_MS = 2500
CODEX_USAGE_POLL_MS = 60_000
CLAUDE_STATUS_POLL_MS = 8000
CLAUDE_USAGE_POLL_MS = 120_000
CLAUDE_ACCOUNT_USAGE_POLL_MS = 60_000
OPENAI_BILLING_POLL_MS = 30 * 60 * 1000
HARDWARE_STATUS_POLL_MS = 5000
# follow-through: the tail tip plays the pose this far behind the root, so the
# wire bends through motion instead of swinging as one rigid piece
TAIL_TIP_LAG_MS = 130
# body bend channel: (lean, hunch) in px at the very top of the character;
# lean shears sideways with the feet planted, hunch>0 slumps, hunch<0 lifts
BodyBend = tuple[float, float]
BODY_BEND_NEUTRAL: BodyBend = (0.0, 0.0)
VISION_FIRST_REFRESH_MS = 5 * 60 * 1000
VISION_REFRESH_MS = 10 * 60 * 1000
VISION_BUSY_RETRY_MS = 5 * 60 * 1000
LINE_BANK_FIRST_MAINTENANCE_MS = 15 * 60 * 1000
LINE_BANK_REFRESH_MS = 6 * 60 * 60 * 1000
LINE_BANK_BUSY_RETRY_MS = 10 * 60 * 1000
AMBIENT_MIN_MS = 18_000
AMBIENT_MAX_MS = 45_000
AMBIENT_COOLDOWN_SECONDS = 50
LOW_STIMULUS_IDLE_ACTIONS = ("blink", "peek", "nod", "micro_soften")
COMMON_IDLE_ACTIONS = ("blink", "peek", "scan", "thinking_tilt", "nod", "wiggle", "tail_wag", "curious_lean")
MID_IDLE_ACTIONS = ("stretch", "sleepy_sag", "smug_sway", "patrol", "mini_hop_shift", "shiver")
RARE_IDLE_ACTIONS = ("twirl", "flop", "hide", "dance", "relocate_hop", "sneeze", "peekaboo", "excited_spin", "spin_jump", "moonwalk", "zoomies", "pounce", "tail_raise_excited", "tail_question_hook")
LARGE_IDLE_ACTIONS = {"jump", "flop", "melt", "dance", "twirl", "stretch", "sleepy_sag", "sulk", "hide", "celebrate", "spin_jump", "excited_spin", "peekaboo", "sneeze"}
ACTION_SHADOW_ACTIONS = {"jump", "happy_bounce", "celebrate", "dance", "flop", "melt", "sleepy_sag", "sulk", "startled_pop", "spin_jump", "excited_spin", "peekaboo", "sneeze", "shiver"}
# measured from the keyframes each move action builds (distances are random,
# the beat lengths are not)
MOVE_ACTION_DURATIONS: dict[str, int] = {
    "twist_scoot": 270, "mini_hop_shift": 325, "relocate_hop": 555,
    "roast_and_scoot": 660, "retreat_to_corner": 570, "drop_in": 1030,
    "zoomies": 930, "moonwalk": 860, "pounce": 720,
}
MOVE_IDLE_ACTIONS = {"twist_scoot", "mini_hop_shift", "relocate_hop", "roast_and_scoot", "retreat_to_corner", "drop_in", "zoomies", "moonwalk", "pounce"}
ActionFrame = tuple[float, float, float, float, int]
ActionFrames = tuple[ActionFrame, ...]
ActionActingCue = tuple[str, str, int, bool]
TailPose = tuple[float, float, float, float, float]
TailFrame = tuple[float, float, float, float, float, int]
TailFrames = tuple[TailFrame, ...]
InnerPose = tuple[float, float, float, float]
InnerFrame = tuple[float, float, float, float, int]
InnerFrames = tuple[InnerFrame, ...]
PropFrame = tuple[float, float, float, float, int]
PropFrames = tuple[PropFrame, ...]


@dataclass(frozen=True)
class VisualStatePlan:
    state: str
    performance: str
    action: str
    lifecycle: str
    minimum_ms: int
    priority: int
    interruptible: bool
    source: str


@dataclass
class AppearanceState:
    costume_id: str = ""
    phase: str = "plain"
    language_mode: str = "zh-CN"


class PaperPropCue(TypedDict):
    decoration: str
    duration: int
    eyes: str
    brows: str
    frames: PropFrames
    tail: NotRequired[str]
    inner: NotRequired[str]


class _WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _WinRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _WinMonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _WinRect),
        ("rcWork", _WinRect),
        ("dwFlags", ctypes.c_ulong),
    ]


TAIL_NEUTRAL_POSE: TailPose = (0.0, 0.0, 0.0, 0.0, 0.0)
INNER_NEUTRAL_POSE: InnerPose = (0.0, 0.0, 0.0, 0.0)
ACTION_FRAMES: dict[str, ActionFrames] = {
    # 卡通跳跃：蓄力蹲→弹射拉伸→顶点滞空漂浮→落地压扁→双段回弹 (~840ms)
    "jump": (
        (0, 8, 1.22, 0.72, 150),
        (0, -42, 0.80, 1.30, 100),
        (0, -46, 0.94, 1.08, 90),
        (0, -44, 0.96, 1.04, 110),
        (0, -12, 1.02, 0.98, 90),
        (0, 7, 1.30, 0.68, 80),
        (0, -8, 0.92, 1.10, 80),
        (0, 3, 1.08, 0.94, 60),
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
    # 跳舞：左右律动带下拍压扁，后半段加大幅度，最后小跳收尾 (~1150ms)
    "dance": (
        (-10, -8, 1.06, 0.94, 120),
        (0, 2, 1.10, 0.92, 70),
        (10, -8, 0.94, 1.06, 120),
        (0, 2, 1.10, 0.92, 70),
        (-12, -12, 1.02, 1.00, 130),
        (0, 3, 1.12, 0.90, 70),
        (12, -12, 0.98, 1.02, 130),
        (0, 2, 1.08, 0.94, 70),
        (-6, -16, 0.92, 1.10, 110),
        (0, 4, 1.14, 0.88, 80),
        (0, -2, 0.98, 1.03, 80),
        (0, 0, 1.0, 1.0, 90),
    ),
    # 转身：微离地水平翻转，背面短暂定格，落地轻触 (~650ms)
    "twirl": (
        (0, -4, 0.42, 1.10, 85),
        (0, -7, -0.42, 1.10, 85),
        (0, -9, -1.0, 1.04, 150),
        (0, -6, -0.42, 1.08, 85),
        (0, -2, 0.42, 1.08, 85),
        (0, 2, 1.06, 0.94, 70),
        (0, 0, 1.0, 1.0, 90),
    ),
    # 伸懒腰：慢压→大拉伸→顶点微颤→享受停顿→弹回 (~1330ms)
    "stretch": (
        (0, 8, 1.14, 0.82, 180),
        (0, -4, 0.84, 1.30, 320),
        (0, -3, 0.83, 1.32, 140),
        (0, -2, 0.85, 1.28, 140),
        (0, -2, 0.88, 1.24, 260),
        (0, 4, 1.10, 0.88, 120),
        (0, -1, 0.96, 1.04, 90),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 颤抖：可读的左右摆，振幅逐渐衰减到静止 (~770ms)
    # 半周期 65-80ms——再快就成视觉噪声了
    "shake": (
        (-13, -2, 1.05, 0.96, 70),
        (13, 2, 0.95, 1.05, 70),
        (-11, -1, 1.04, 0.97, 65),
        (11, 1, 0.96, 1.04, 65),
        (-8, -1, 1.03, 0.98, 70),
        (8, 1, 0.97, 1.03, 70),
        (-5, 0, 1.02, 0.99, 80),
        (5, 0, 0.98, 1.02, 80),
        (-2, 0, 1.01, 1.0, 90),
        (0, 0, 1.0, 1.0, 110),
    ),
    # 开心弹跳：无蓄力直接双弹，轻快但看得清 (320ms)
    "happy_bounce": (
        (0, -18, 0.94, 1.08, 100),
        (0, -4, 1.06, 0.94, 70),
        (0, -10, 0.97, 1.04, 90),
        (0, 0, 1.0, 1.0, 60),
    ),
    # 点头：纵向三次，末次最轻，撑得住举牌确认的时长 (620ms)
    "nod": (
        (0, 10, 1.04, 0.92, 120),
        (0, 2, 1.0, 1.0, 80),
        (0, 8, 1.03, 0.94, 120),
        (0, 2, 1.0, 1.0, 80),
        (0, 5, 1.02, 0.96, 110),
        (0, 0, 1.0, 1.0, 110),
    ),
    # 歪头想事：单次歪头→长停顿（够读完自己举的问号牌）→慢回正
    "thinking_tilt": (
        (-6, 0, 0.92, 1.06, 180),
        (-8, 2, 0.90, 1.08, 640),
        (-7, 2, 0.91, 1.07, 220),
        (-4, 1, 0.95, 1.04, 160),
        (0, 0, 1.0, 1.0, 110),
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
    # 受惊膨胀：瞬间均匀膨大→定格（警示牌还砸在头顶）→慢缩回
    "startled_pop": (
        (0, -6, 1.30, 1.30, 40),
        (0, -8, 1.28, 1.28, 280),
        (0, -6, 1.20, 1.20, 140),
        (0, -4, 1.12, 1.12, 130),
        (0, -2, 1.05, 1.05, 110),
        (0, 0, 1.0, 1.0, 90),
    ),
    # 得意慢摆：不对称，delay 加倍
    "smug_sway": (
        # 头歪开、眼锁死：先向注视方向虚晃，再倒向反侧并长停——
        # 身体倾角与 smug_half 瞳孔(-2.8)始终反向，欠感来自这个对立。
        (-4, 1, 0.98, 1.01, 150),
        (9, -1, 1.03, 0.99, 240),
        (7, 0, 1.01, 1.0, 400),
        (3, 0, 1.0, 1.0, 160),
        (0, 0, 1.0, 1.0, 140),
    ),
    # 委屈：缩向一侧+微颤+长停留（撑满头顶乌云淋雨的整场戏）
    "sulk": (
        (-3, 6, 0.94, 0.92, 120),
        (-5, 14, 0.88, 0.82, 150),
        (-6, 16, 0.86, 0.80, 100),
        (-4, 14, 0.88, 0.82, 100),
        (-5, 15, 0.87, 0.81, 640),
        (-4, 14, 0.88, 0.82, 320),
        (-2, 8, 0.94, 0.92, 170),
        (0, 0, 1.0, 1.0, 130),
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
    # 巡逻：匀速平移无缩放，端点停顿举镜观察
    "patrol": (
        (-20, 0, 1.0, 1.0, 220),
        (-20, 0, 1.0, 1.0, 280),
        (0, 0, 1.0, 1.0, 160),
        (20, 0, 1.0, 1.0, 220),
        (20, 0, 1.0, 1.0, 280),
        (0, 0, 1.0, 1.0, 160),
    ),
    # 庆祝：跳高→空中左右扭三下→落地→开心补一个小跳 (~940ms)
    "celebrate": (
        (0, 6, 1.20, 0.78, 90),
        (0, -36, 0.88, 1.16, 110),
        (-10, -33, 0.92, 1.08, 100),
        (10, -31, 1.08, 0.92, 100),
        (-8, -33, 0.94, 1.06, 100),
        (0, -8, 0.96, 1.04, 80),
        (0, 5, 1.18, 0.80, 70),
        (0, -14, 0.94, 1.08, 90),
        (0, 3, 1.08, 0.92, 60),
        (0, -2, 0.98, 1.02, 60),
        (0, 0, 1.0, 1.0, 70),
    ),
    # 转体跳：蓄力→跳起穿越翻面→镜像顶点亮相→翻回落地压扁→回弹 (~920ms)
    "spin_jump": (
        (0, 8, 1.22, 0.72, 140),
        (0, -38, 0.90, 1.16, 90),
        (0, -48, 0.30, 1.10, 62),
        (0, -50, -0.90, 1.06, 72),
        (0, -46, -1.0, 1.05, 130),
        (0, -32, -0.30, 1.06, 62),
        (0, -16, 0.90, 1.05, 72),
        (0, 7, 1.26, 0.72, 80),
        (0, -4, 0.94, 1.07, 80),
        (0, 0, 1.0, 1.0, 80),
    ),
    # 兴奋转圈：两次翻转但每一面都看得清→小落地→骄傲亮相 (~1120ms)
    "excited_spin": (
        (0, -3, 1.12, 0.92, 90),
        (0, -6, 0.30, 1.06, 85),
        (0, -7, -1.0, 1.02, 100),
        (0, -6, -0.30, 1.04, 80),
        (0, -7, 1.0, 1.02, 95),
        (0, -6, 0.30, 1.05, 80),
        (0, -7, -1.0, 1.02, 100),
        (0, -4, -0.30, 1.04, 85),
        (0, -5, 0.95, 1.06, 95),
        (0, 3, 1.10, 0.92, 90),
        (0, -2, 0.98, 1.03, 100),
        (0, 0, 1.0, 1.0, 120),
    ),
    # 打喷嚏：仰头吸气越吸越大→猛地向前下方喷出→反弹晃两下→委屈缓神 (~1400ms)
    "sneeze": (
        (0, -2, 0.97, 1.04, 200),
        (-2, -6, 0.90, 1.14, 240),
        (-3, -8, 0.86, 1.20, 160),
        (4, 14, 1.32, 0.66, 60),
        (2, 6, 0.94, 1.06, 90),
        (1, 9, 1.10, 0.88, 90),
        (0, 3, 0.97, 1.02, 110),
        (0, 5, 1.0, 0.96, 320),
        (0, 0, 1.0, 1.0, 130),
    ),
    # 发抖：缩成一小团颤抖，振幅渐减后慢慢展开 (~940ms)
    "shiver": (
        (0, 4, 0.94, 0.94, 100),
        (-4, 5, 0.93, 0.93, 60),
        (4, 4, 0.95, 0.93, 60),
        (-4, 5, 0.93, 0.94, 62),
        (4, 4, 0.95, 0.93, 62),
        (-3, 5, 0.94, 0.94, 68),
        (3, 4, 0.95, 0.94, 68),
        (-2, 4, 0.95, 0.95, 76),
        (2, 4, 0.96, 0.95, 76),
        (0, 2, 0.97, 0.97, 150),
        (0, 0, 1.0, 1.0, 160),
    ),
    # 好奇探身：朝一侧倾身拉长凑近→定住观察→微调→缩回 (~1350ms)
    "curious_lean": (
        (4, 0, 1.03, 0.98, 130),
        (12, -2, 1.13, 0.94, 240),
        (14, -3, 1.15, 0.93, 520),
        (13, -2, 1.14, 0.94, 180),
        (6, -1, 1.06, 0.98, 150),
        (0, 0, 1.0, 1.0, 130),
    ),
    # 躲猫猫：快速缩下去→憋住悬念→猛地弹出来→开心落定 (~1420ms)
    "peekaboo": (
        (0, 10, 1.10, 0.84, 90),
        (0, 30, 0.72, 0.44, 110),
        (0, 32, 0.70, 0.42, 620),
        (0, 34, 0.76, 0.40, 120),
        (0, -26, 0.86, 1.24, 90),
        (0, -20, 1.0, 1.10, 140),
        (0, 6, 1.12, 0.88, 80),
        (0, -3, 0.97, 1.04, 80),
        (0, 0, 1.0, 1.0, 90),
    ),
}

IDENTITY_STATE_CUES: dict[str, dict[str, object]] = {
    "default_pal": {"mood": "smirk", "action": "blink", "eyes": "round", "brows": "innocent", "hold_ms": 1800},
    "task_auditor": {"mood": "suspicious", "action": "thinking_tilt", "eyes": "side_eye", "brows": "judge", "hold_ms": 3200},
    "agent_supervisor": {"mood": "thinking", "action": "scan", "decoration": "status_dot", "eyes": "side_eye", "brows": "judge", "hold_ms": 4200},
    "thermal_technician": {"mood": "startled", "action": "shake", "decoration": "heat_puffs", "eyes": "round", "brows": "guilty", "hold_ms": 4800},
    "usage_accountant": {"mood": "focused", "action": "scan", "decoration": "usage_bar", "eyes": "side_eye", "brows": "soft", "hold_ms": 4400},
    "focus_companion": {"mood": "innocent", "action": "blink", "eyes": "soft", "brows": "soft", "hold_ms": 3600},
    "sleepy_clip": {"mood": "sleepy", "action": "sleepy_sag", "decoration": "z_symbol", "eyes": "sleepy_slit", "brows": "droop", "hold_ms": 9000},
    "bug_coroner": {"mood": "suspicious", "action": "scan", "decoration": "tiny_warning", "eyes": "side_eye", "brows": "judge", "hold_ms": 4600},
    "critic_clip": {"mood": "smirk", "action": "thinking_tilt", "decoration": "annotation_circle", "eyes": "side_eye", "brows": "judge", "hold_ms": 3600},
    "tab_warden": {"mood": "suspicious", "action": "patrol", "decoration": "tab_bar", "eyes": "side_eye", "brows": "judge", "hold_ms": 4400},
    "gremlin_clip": {"mood": "smug", "action": "smug_sway", "eyes": "side_eye", "brows": "proud", "hold_ms": 3600},
    "meltdown_clip": {"mood": "sulky", "action": "melt", "decoration": "tiny_warning", "eyes": "peek_up", "brows": "sulk", "hold_ms": 5200},
}

ACTION_DECORATION_CUES: dict[str, tuple[str, int]] = {
    "sleepy_sag": ("z_symbol", 4200),
    "flop": ("paper_pillow", 4200),
    "hide": ("paper_oops_cover", 3600),
    "dance": ("paper_stage", 4200),
    "celebrate": ("paper_stage", 4400),
    "shake": ("paper_fan", 3200),
}

PAPER_PROP_ACTIONS: dict[str, PaperPropCue] = {
    "paper_blanket": {
        "decoration": "draft_blanket",
        "duration": 6500,
        "eyes": "sleepy_slit",
        "brows": "droop",
        "tail": "tail_sleepy_droop",
        "inner": "inner_droop",
        "frames": ((0, 10, 1.04, 0.86, 180), (0, 4, 1.0, 0.94, 260), (0, 0, 1.0, 1.0, 180)),
    },
    "paper_surfboard": {
        "decoration": "paper_surfboard",
        "duration": 4600,
        "eyes": "wide",
        "brows": "proud",
        "tail": "tail_wag",
        "frames": ((-8, -5, 0.96, 1.06, 170), (10, -7, 1.04, 0.98, 210), (-4, -4, 0.98, 1.02, 180), (0, 0, 1.0, 1.0, 160)),
    },
    "paper_peek_curtain": {
        "decoration": "paper_peek_curtain",
        "duration": 5200,
        "eyes": "peek_up",
        "brows": "guilty",
        "tail": "tail_guilty_tuck",
        "inner": "inner_shy_retract",
        "frames": ((0, 2, 0.96, 0.98, 180), (0, 0, 1.0, 1.0, 220)),
    },
    "paper_fan": {
        "decoration": "paper_fan",
        "duration": 4200,
        "eyes": "smug_half",
        "brows": "skeptical",
        "tail": "tail_tip_flick",
        "frames": ((2, 0, 1.0, 1.0, 130), (-2, 0, 1.0, 1.0, 135), (1, 0, 1.0, 1.0, 125), (0, 0, 1.0, 1.0, 150)),
    },
    "paper_whisper_fan": {
        "decoration": "paper_whisper_fan",
        "duration": 5600,
        "eyes": "smug_half",
        "brows": "smug_arch",
        "tail": "tail_smug_sway",
        "inner": "inner_cover_oops",
        "frames": ((-2, 1, 0.98, 1.02, 160), (2, -1, 1.01, 0.99, 180), (0, 0, 1.0, 1.0, 180)),
    },
    "paper_oops_cover": {
        "decoration": "paper_oops_cover",
        "duration": 4200,
        "eyes": "guilty_round",
        "brows": "innocent",
        "tail": "tail_frantic_innocent",
        "inner": "inner_cover_oops",
        "frames": ((-3, 1, 0.98, 1.02, 120), (0, 0, 1.0, 1.0, 160)),
    },
    "paper_tent": {
        "decoration": "paper_tent",
        "duration": 5400,
        "eyes": "peek_up",
        "brows": "sulk",
        "tail": "tail_guilty_tuck",
        "inner": "inner_shy_retract",
        "frames": ((0, 7, 0.90, 0.82, 220), (0, 3, 0.95, 0.90, 280), (0, 0, 1.0, 1.0, 220)),
    },
    "paper_pillow": {
        "decoration": "paper_pillow",
        "duration": 5200,
        "eyes": "sleepy_slit",
        "brows": "droop",
        "tail": "tail_sleepy_droop",
        "inner": "inner_droop",
        "frames": ((-8, 15, 1.10, 0.72, 220), (-4, 8, 1.04, 0.82, 260), (0, 0, 1.0, 1.0, 220)),
    },
    "paper_stage": {
        "decoration": "paper_stage",
        "duration": 4600,
        "eyes": "round",
        "brows": "proud",
        "tail": "tail_wag",
        "frames": ((0, -10, 0.94, 1.10, 140), (0, 4, 1.08, 0.88, 110), (0, -4, 0.98, 1.04, 120), (0, 0, 1.0, 1.0, 120)),
    },
}

ACTION_ANTICIPATION_FRAMES: dict[str, ActionFrames] = {
    "jump": ((0, 12, 1.18, 0.70, 110),),
    "happy_bounce": ((0, 7, 1.12, 0.82, 75),),
    "celebrate": ((0, 8, 1.18, 0.76, 85),),
    "flop": ((0, -5, 0.92, 1.10, 75),),
    "dance": ((0, 5, 1.10, 0.88, 75),),
    "twirl": ((0, 0, 1.18, 0.90, 85),),
    "stretch": ((0, 10, 1.12, 0.80, 100),),
    "shake": ((4, 0, 1.03, 0.98, 80),),
    "thinking_tilt": ((4, 0, 1.03, 0.98, 90),),
    "sleepy_sag": ((0, -4, 0.94, 1.08, 95),),
    "startled_pop": ((0, 3, 0.86, 0.86, 65),),
    "smug_sway": ((4, 0, 1.02, 0.98, 90),),
    "sulk": ((2, -2, 0.98, 1.02, 60),),
    "hide": ((-4, -2, 1.04, 1.02, 65),),
    "patrol": ((0, 0, 0.98, 1.02, 65),),
    "spin_jump": ((0, 11, 1.16, 0.74, 100),),
    "excited_spin": ((0, 4, 1.10, 0.90, 80),),
    "curious_lean": ((-3, 0, 0.98, 1.01, 90),),
    "pounce": ((-4, 3, 1.08, 0.92, 130),),
}

ACTION_FOLLOW_THROUGH_FRAMES: dict[str, ActionFrames] = {
    "jump": ((0, 8, 1.18, 0.78, 70), (0, -3, 0.96, 1.05, 80), (0, 0, 1.0, 1.0, 70)),
    "happy_bounce": ((0, 4, 1.10, 0.88, 65), (0, -2, 0.98, 1.03, 70), (0, 0, 1.0, 1.0, 70)),
    "celebrate": ((0, 6, 1.16, 0.82, 75), (0, -4, 0.97, 1.04, 75), (0, 0, 1.0, 1.0, 75)),
    "flop": ((0, 30, 1.34, 0.46, 160), (0, 10, 1.10, 0.82, 120), (0, 0, 1.0, 1.0, 120)),
    "dance": ((0, -4, 0.98, 1.04, 80), (0, 0, 1.0, 1.0, 80)),
    "twirl": ((0, -1, 0.74, 1.08, 80), (0, 0, 1.0, 1.0, 95)),
    "stretch": ((0, -2, 0.92, 1.10, 80), (0, 5, 1.08, 0.90, 80), (0, 0, 1.0, 1.0, 90)),
    "shake": ((-3, 0, 1.02, 0.98, 55), (0, 0, 1.0, 1.0, 70)),
    "thinking_tilt": ((-2, 1, 0.97, 1.03, 120), (0, 0, 1.0, 1.0, 100)),
    "sleepy_sag": ((0, 18, 1.08, 0.72, 180), (0, 4, 0.98, 0.92, 120), (0, 0, 1.0, 1.0, 120)),
    "startled_pop": ((0, -2, 1.12, 1.12, 85), (0, 2, 0.96, 0.96, 85), (0, 0, 1.0, 1.0, 85)),
    "smug_sway": ((-4, 0, 0.98, 1.02, 110), (0, 0, 1.0, 1.0, 100)),
    "sulk": ((-4, 12, 0.90, 0.84, 180), (-1, 5, 0.96, 0.92, 120), (0, 0, 1.0, 1.0, 120)),
    "hide": ((10, 16, 0.78, 0.70, 160), (3, 5, 0.92, 0.90, 130), (0, 0, 1.0, 1.0, 110)),
    "patrol": ((0, 0, 1.02, 0.98, 70), (0, 0, 1.0, 1.0, 80)),
    "spin_jump": ((0, 6, 1.16, 0.82, 70), (0, -3, 0.97, 1.04, 70), (0, 0, 1.0, 1.0, 70)),
    "excited_spin": ((0, 2, 1.06, 0.95, 70), (0, 0, 1.0, 1.0, 80)),
    "shiver": ((0, 1, 0.99, 0.99, 90), (0, 0, 1.0, 1.0, 100)),
}

ACTION_ACTING_CUES: dict[str, ActionActingCue] = {
    "jump": ("wide", "guilty", 1400, False),
    "happy_bounce": ("sparkle", "proud", 1700, False),
    "celebrate": ("sparkle", "proud", 2200, False),
    "dance": ("wide", "laugh", 1800, False),
    "twirl": ("wide", "proud", 1600, False),
    "stretch": ("soft", "soft", 1800, False),
    "shake": ("wide", "guilty", 1400, False),
    "thinking_tilt": ("curious", "curious", 2200, False),
    "sleepy_sag": ("sleepy_slit", "droop", 3200, False),
    "startled_pop": ("startled_dot", "panic", 1600, False),
    "smug_sway": ("smug_half", "smug_arch", 2300, False),
    "sulk": ("peek_up", "sulk", 2600, False),
    "hide": ("peek_up", "guilty", 2200, False),
    "flop": ("wide", "guilty", 1800, False),
    "melt": ("guilty_round", "sulk", 2800, False),
    "patrol": ("side_eye", "judge", 1700, False),
    "scan": ("suspicious_slit", "skeptical", 1700, False),
    "peek": ("peek_up", "soft", 1600, False),
    "wiggle": ("wide", "guilty", 1200, False),
    "tail_wag": ("proud", "proud", 1600, False),
    "tail_idle_slow": ("soft", "soft", 1200, False),
    "tail_tip_flick": ("suspicious_slit", "skeptical", 1300, False),
    "tail_smug_sway": ("smug_half", "smug_arch", 1800, False),
    "tail_guilty_tuck": ("guilty_round", "innocent", 1500, False),
    "tail_sleepy_droop": ("sleepy_slit", "droop", 2100, False),
    "tail_alert_snap": ("startled_dot", "panic", 1500, False),
    "tail_frantic_innocent": ("innocent_round", "innocent", 1500, False),
    "inner_cover_oops": ("innocent_round", "innocent", 1500, False),
    "inner_side_smirk": ("smug_half", "skeptical", 1400, False),
    "inner_shy_retract": ("guilty_round", "innocent", 1500, False),
    "inner_droop": ("sleepy_slit", "droop", 1800, False),
    "oops_innocent_combo": ("wide", "innocent", 1700, False),
    "britclip_enter": ("wide", "proud", 5200, False),
    "britclip_exit": ("guilty_round", "innocent", 2200, False),
    "tip_hat": ("wide", "innocent", 1500, False),
    "bow_tie_check": ("smug_half", "proud", 1500, False),
    "cane_tap": ("side_eye", "proud", 1400, False),
    "polite_bow": ("soft", "proud", 1400, False),
    "british_gentleman_suit_up": ("wide", "proud", 4200, False),
    "hat_tip_oops": ("wide", "innocent", 1500, False),
    "roast_and_scoot": ("round", "innocent", 1700, False),
    "retreat_to_corner": ("peek_up", "sulk", 2200, False),
    "drop_in": ("wide", "innocent", 1600, False),
    "spin_jump": ("sparkle", "proud", 1800, False),
    "excited_spin": ("sparkle", "laugh", 1900, False),
    "sneeze": ("guilty_round", "innocent", 2000, True),
    "shiver": ("guilty_round", "sulk", 1900, False),
    "curious_lean": ("curious", "curious", 2400, False),
    "peekaboo": ("wide", "laugh", 2000, False),
    "zoomies": ("sparkle", "laugh", 2000, False),
    "moonwalk": ("smug_half", "smug_arch", 2000, False),
    "pounce": ("suspicious_slit", "judge", 1600, False),
}

# ── tail oscillators ─────────────────────────────────────────────
# Swinging tail motions are continuous oscillations, not keyframes: a cat's
# tail is a pendulum with an envelope, and the time phase drives the traveling
# wave directly so the swing rolls root-to-tip instead of beating against it.
#   freq: Hz · amp: px at the envelope peak · cycles: how many full swings
#   attack/decay: fraction of the duration spent ramping in/out
#   curl/droop/tuck: static channels faded with the envelope

# ── tail-as-hand ─────────────────────────────────────────────────
# When the tail is HOLDING something it stops being a tail: no wagging, no
# whip. It extends into a steady carry position and only breathes — the tiny
# sway of a hand keeping an object level.

TAIL_HAND_POSE: TailPose = (2.0, 3.2, 0.0, 0.0, 1.8)


def tail_hand_pose(t_seconds: float) -> TailPose:
    """Steady carry pose with a gentle keeping-it-level micro-sway."""
    s = math.sin(t_seconds * 2.4) * 0.9 + math.sin(t_seconds * 1.1) * 0.4
    return (
        TAIL_HAND_POSE[0] + s,
        TAIL_HAND_POSE[1] + s * 0.2,
        TAIL_HAND_POSE[2],
        TAIL_HAND_POSE[3],
        TAIL_HAND_POSE[4],
    )


# "wave": spatial frequency in π units along the wire. ONE bend = half a sine
# period (π), so wave 1.0 ≈ a single C-curve and ~1.35 lets an S flash through
# at speed — never more. A real cat tops out at one S even when lashing; the
# tip-lag follow-through already adds its own hint of extra curvature.
# "engage": (start, full) arc-length progress where the swing participates.
# Omitted = whole tail swings from the shoulder. A tip motion — ringing a
# bell, flicking at something — moves from the wrist out and leaves the rest
# of the wire standing still.
TAIL_TIP_ENGAGE = (0.58, 0.95)

TAIL_OSCILLATIONS: dict[str, dict[str, object]] = {
    "tail_wag": {"freq": 2.4, "amp": 13.0, "cycles": 3.5, "attack": 0.16, "decay": 0.28, "curl": 1.6, "wave": 1.15},
    "tail_smug_sway": {"freq": 0.85, "amp": 7.0, "cycles": 2.0, "attack": 0.22, "decay": 0.3, "curl": 4.5, "wave": 0.85},
    "tail_idle_slow": {"freq": 0.5, "amp": 4.5, "cycles": 1.0, "attack": 0.3, "decay": 0.35, "curl": 1.0, "wave": 0.8},
    # a flick is still a SWING: the whole wire carries it, the tip snaps most
    "tail_tip_flick": {"freq": 2.6, "amp": 10.0, "cycles": 2.0, "attack": 0.12, "decay": 0.35, "curl": 2.0, "wave": 1.0},
    "tail_frantic_innocent": {"freq": 2.9, "amp": 13.0, "cycles": 4.0, "attack": 0.12, "decay": 0.3, "wave": 1.35},
    # ringing a bell held in the tail tip: a wrist shake, not an arm swing.
    # amp is high because only the last ~40% of wire bends — calibrated so the
    # tip travels ~9px (ring) / ~5px (jingle) while the rest stands still
    "tail_bell_ring": {"freq": 3.4, "amp": 53.0, "cycles": 3.0, "attack": 0.1, "decay": 0.3, "wave": 0.7, "engage": TAIL_TIP_ENGAGE},
    "tail_bell_jingle": {"freq": 1.1, "amp": 29.0, "cycles": 1.5, "attack": 0.25, "decay": 0.35, "wave": 0.7, "engage": TAIL_TIP_ENGAGE},
}


def tail_oscillation_pose(params: dict[str, object], t_seconds: float, duration_override: float = 0.0):
    """Sample a tail oscillation at time t.

    Returns (sway_envelope, curl, droop, tuck, stiffen, phase) — the sway
    value is the ENVELOPE amplitude; the time phase feeds posed_tail_points'
    s_phase so the spatial wave and the swing are one traveling wave.
    Returns None when the oscillation has finished.
    """
    freq = float(params["freq"])
    duration = duration_override or float(params["cycles"]) / freq
    if t_seconds >= duration:
        return None
    attack = max(0.05, float(params.get("attack", 0.2))) * duration
    decay = max(0.05, float(params.get("decay", 0.3))) * duration
    if t_seconds < attack:
        env = _smoothstep(t_seconds / attack)
    elif t_seconds > duration - decay:
        env = _smoothstep((duration - t_seconds) / decay)
    else:
        env = 1.0
    phase = -2.0 * math.pi * freq * t_seconds  # wave travels root → tip
    return (
        float(params["amp"]) * env,
        float(params.get("curl", 0.0)) * env,
        float(params.get("droop", 0.0)) * env,
        float(params.get("tuck", 0.0)) * env,
        float(params.get("stiffen", 0.0)) * env,
        phase,
    )


# ── tail postures ────────────────────────────────────────────────
# A tail doesn't only swing — it POSES. From the cat reference: excited tails
# stand straight up with a quivering tip, playful tails curl into a question
# hook, defensive tails go rigid and bristle. Ease in, hold with a quiver,
# ease out.
#   pose: target 5-channel pose · quiver_amp/freq: tip tremble while held
#   hold_ms: time at full pose

TAIL_POSTURES: dict[str, dict[str, object]] = {
    "tail_raise_excited": {"pose": (1.5, 2.0, 0.0, 0.0, 14.0), "quiver_amp": 1.6, "quiver_freq": 5.5, "hold_ms": 1600},
    "tail_question_hook": {"pose": (2.0, 6.5, 0.0, 5.0, 2.0), "quiver_amp": 0.8, "quiver_freq": 1.2, "hold_ms": 1800},
    "tail_bristle": {"pose": (0.5, 1.0, 0.0, 0.0, 11.0), "quiver_amp": 1.3, "quiver_freq": 6.5, "hold_ms": 1300},
}

_POSTURE_ENTER_S = 0.26
_POSTURE_EXIT_S = 0.30


def tail_posture_pose(params: dict[str, object], t_seconds: float):
    """Sample a tail posture at time t: ease in → quivering hold → ease out.

    Returns a 5-channel pose, or None when finished.
    """
    hold_s = float(params.get("hold_ms", 1500)) / 1000.0
    total = _POSTURE_ENTER_S + hold_s + _POSTURE_EXIT_S
    if t_seconds >= total:
        return None
    if t_seconds < _POSTURE_ENTER_S:
        w = _smoothstep(t_seconds / _POSTURE_ENTER_S)
    elif t_seconds > _POSTURE_ENTER_S + hold_s:
        w = _smoothstep((total - t_seconds) / _POSTURE_EXIT_S)
    else:
        w = 1.0
    pose = params["pose"]
    quiver = (
        float(params.get("quiver_amp", 0.0))
        * math.sin(2.0 * math.pi * float(params.get("quiver_freq", 5.0)) * t_seconds)
        * w
    )
    return (
        pose[0] * w + quiver,
        pose[1] * w,
        pose[2] * w,
        pose[3] * w,
        pose[4] * w,
    )


TAIL_MOTION_FRAMES: dict[str, TailFrames] = {
    "tail_guilty_tuck": (
        (0, 0, 0, 0, 0, 40),
        (-2, -3, 0, 9, 0, 150),
        (-1, -4, 0, 12, 0, 360),
        (2, 2, 0, 4, 0, 150),
        (0, 0, 0, 0, 0, 180),
    ),
    "tail_sleepy_droop": (
        (0, 0, 0, 0, 0, 40),
        (-1, -2, 7, 1, 0, 280),
        (1, -1, 13, 0, 0, 620),
        (0, -1, 9, 0, 0, 280),
        (0, 0, 0, 0, 0, 220),
    ),
    "tail_alert_snap": (
        (0, 0, 0, 0, 0, 40),
        (1, 4, 0, 0, 13, 70),
        (-5, -3, 0, 0, 7, 75),
        (3, 2, 0, 0, 4, 80),
        (0, 0, 0, 0, 0, 160),
    ),
}

INNER_GESTURE_FRAMES: dict[str, InnerFrames] = {
    "inner_cover_oops": (
        (0, 0, 0, 0, 45),
        (5, 16, -4, 7, 95),
        (-2, 12, 3, 8, 85),
        (3, 15, -2, 6, 130),
        (0, 7, 1, 4, 120),
        (0, 0, 0, 0, 140),
    ),
    "inner_side_smirk": (
        (0, 0, 0, 0, 45),
        (10, 4, 4, -1, 120),
        (4, 2, 2, 1, 180),
        (0, 0, 0, 0, 150),
    ),
    "inner_shy_retract": (
        (0, 0, 0, 0, 45),
        (-8, 10, -3, 5, 120),
        (-6, 8, -5, 8, 260),
        (0, 3, -2, 3, 120),
        (0, 0, 0, 0, 150),
    ),
    "inner_droop": (
        (0, 0, 0, 0, 45),
        (-1, -9, -1, -4, 220),
        (1, -12, 1, -7, 420),
        (0, -5, 0, -3, 180),
        (0, 0, 0, 0, 180),
    ),
    # --- hand gestures ---
    "inner_wave": (
        (0, 0, 0, 0, 40),
        (12, 6, 5, 2, 100),      # reach out right
        (-10, 7, -4, 3, 110),    # sweep left
        (11, 5, 4, 1, 105),      # sweep right
        (-8, 6, -3, 2, 110),     # sweep left
        (4, 3, 2, 1, 120),       # settle
        (0, 0, 0, 0, 130),
    ),
    "inner_point": (
        (0, 0, 0, 0, 40),
        (0, 14, 0, 6, 110),      # extend upward firmly
        (2, 16, 1, 7, 280),      # hold with micro-drift
        (1, 12, 0, 5, 140),      # retract slightly
        (0, 0, 0, 0, 140),
    ),
    "inner_facepalm": (
        (0, 0, 0, 0, 40),
        (3, 18, -2, 10, 120),    # reach up fast
        (1, 20, -1, 12, 400),    # press and hold (exasperation)
        (2, 14, 0, 8, 160),      # slowly peel away
        (0, 4, 0, 2, 130),
        (0, 0, 0, 0, 140),
    ),
    "inner_thumbs_up": (
        (0, 0, 0, 0, 40),
        (0, 18, 0, 8, 120),      # extend upward stiffly
        (1, 20, -1, 9, 320),     # hold proud
        (0, 10, 0, 5, 140),      # lower
        (0, 0, 0, 0, 130),
    ),
    # --- mouth gestures ---
    "inner_yawn": (
        (0, 0, 0, 0, 60),
        (0, -3, 0, -1, 180),     # mouth starts to open
        (-1, -10, 1, -5, 320),   # wide open yawn
        (1, -12, -1, -6, 500),   # hold open, slight drift
        (0, -6, 0, -3, 240),     # closing
        (0, -1, 0, 0, 160),      # almost closed
        (0, 0, 0, 0, 120),
    ),
    "inner_chew": (
        (0, 0, 0, 0, 35),
        (2, -6, -1, -2, 75),     # chomp down
        (-1, -1, 1, 0, 65),      # open
        (3, -7, -2, -3, 70),     # chomp again offset
        (-2, -2, 1, -1, 60),     # open
        (1, -5, 0, -2, 70),      # smaller chomp
        (0, 0, 0, 0, 100),
    ),
    "inner_fidget": (
        (0, 0, 0, 0, 40),
        (3, 1, -1, 0, 78),       # tap right
        (-2, -1, 1, 0, 72),      # tap left
        (4, 2, -2, 1, 85),       # tap right bigger
        (-1, 0, 0, 0, 70),       # back
        (2, -1, 1, -1, 80),      # tap right-down
        (-3, 1, -1, 0, 75),      # tap left-up
        (0, 0, 0, 0, 100),
    ),
}

ACTION_TAIL_MOTIONS: dict[str, str] = {
    "happy_bounce": "tail_wag",
    "celebrate": "tail_wag",
    "dance": "tail_wag",
    "jump": "tail_alert_snap",
    "wiggle": "tail_tip_flick",
    "shake": "tail_bristle",
    "startled_pop": "tail_bristle",
    "smug_sway": "tail_smug_sway",
    "thinking_tilt": "tail_tip_flick",
    "sulk": "tail_guilty_tuck",
    "hide": "tail_guilty_tuck",
    "roast_and_scoot": "tail_guilty_tuck",
    "retreat_to_corner": "tail_guilty_tuck",
    "sleepy_sag": "tail_sleepy_droop",
    "flop": "tail_sleepy_droop",
    "melt": "tail_sleepy_droop",
    "stretch": "tail_idle_slow",
    "patrol": "tail_tip_flick",
    "spin_jump": "tail_alert_snap",
    "excited_spin": "tail_wag",
    "sneeze": "tail_alert_snap",
    "shiver": "tail_guilty_tuck",
    "curious_lean": "tail_tip_flick",
    "peekaboo": "tail_frantic_innocent",
    "zoomies": "tail_wag",
    "moonwalk": "tail_smug_sway",
    "pounce": "tail_tip_flick",
}

# inner core (hand/mouth) gestures triggered by actions
ACTION_INNER_GESTURES: dict[str, str] = {
    "happy_bounce": "inner_wave",
    "celebrate": "inner_thumbs_up",
    "dance": "inner_wave",
    "smug_sway": "inner_side_smirk",
    "thinking_tilt": "inner_fidget",
    "sulk": "inner_droop",
    "hide": "inner_cover_oops",
    "sleepy_sag": "inner_yawn",
    "flop": "inner_droop",
    "melt": "inner_droop",
    "startled_pop": "inner_facepalm",
    "shake": "inner_fidget",
    "roast_and_scoot": "inner_thumbs_up",
    "stretch": "inner_yawn",
    "excited_spin": "inner_wave",
    "sneeze": "inner_cover_oops",
    "shiver": "inner_fidget",
    "peekaboo": "inner_wave",
    "moonwalk": "inner_side_smirk",
}

# --- inline performance data, kept module-level so offline renderers can read it ---
# melt: sink into a puddle, hold, then recover
MELT_SINK_FRAMES: ActionFrames = (
    (0, 0, 1.03, 0.92, 120),
    (0, 0, 1.00, 0.82, 150),
    (0, 0, 0.94, 0.68, 180),
    (0, 0, 0.88, 0.52, 190),
    (0, 0, 0.82, 0.38, 210),
    (0, 0, 1.05, 0.26, 220),
    (0, 0, 1.32, 0.20, 230),
    (0, 0, 1.58, 0.16, 230),
    (0, 0, 1.72, 0.12, 240),
)
MELT_PUDDLE_HOLD_MS = 1900
MELT_RECOVERY_FRAMES: ActionFrames = (
    (0, 0, 1.58, 0.16, 220),
    (0, 0, 1.32, 0.24, 240),
    (0, 0, 1.05, 0.48, 260),
    (0, 0, 0.94, 0.78, 240),
    (0, 0, 1.0, 1.0, 260),
)
# wiggle: (sx, sy, delay_ms)
WIGGLE_FRAMES: tuple[tuple[float, float, int], ...] = (
    (1.13, 0.88, 55),
    (0.93, 1.08, 70),
    (1.04, 0.97, 60),
    (1.0, 1.0, 1),
)
# blink / slow blink: (pupil_blink_scale, delay_ms)
BLINK_FRAMES: tuple[tuple[float, int], ...] = (
    (0.55, 25), (0.18, 30), (0.06, 55), (0.30, 30), (0.65, 30), (1.0, 1),
)
SLOW_BLINK_FRAMES: tuple[tuple[float, int], ...] = (
    (0.55, 110), (0.18, 120), (0.06, 240), (0.35, 130), (0.7, 120), (1.0, 90),
)
# scan / guilty dart: pupil look targets
SCAN_LOOK_TARGETS: tuple[tuple[float, float], ...] = (
    (-3.0, -0.3), (3.0, -0.2), (-2.2, 0.4), (2.4, 0.2), (0.0, 0.0),
)
SCAN_LOOK_HOLD_MS = 215  # paced to the magnifier sweep
GUILTY_DART_SEQUENCE: tuple[tuple[float, float, int], ...] = (
    (0.0, -0.3, 110),
    (-3.2, 0.5, 150),
    (-3.2, 0.5, 430),
    (-1.2, 0.1, 260),
    (0.0, -0.1, 290),
)

# per-action body bend performances: (lean, hunch, delay_ms). lean>0 leans
# toward screen right, hunch>0 slumps the shoulders, hunch<0 lifts the chest.
# These run in parallel with ACTION_FRAMES, adding head-tilt body language the
# squash/offset channels cannot express.
ACTION_BODY_BEND: dict[str, tuple[tuple[float, float, int], ...]] = {
    "thinking_tilt": ((-7, 1, 200), (-9, 2, 480), (-4, 1, 180), (0, 0, 150)),
    "curious_lean": ((10, -2, 260), (13, -3, 620), (5, -1, 210), (0, 0, 160)),
    "sneeze": ((-6, -4, 430), (-8, -5, 210), (10, 6, 90), (4, 2, 170), (0, 0, 240)),
    "dance": ((-8, -1, 190), (8, -1, 190), (-9, -2, 200), (9, -2, 200), (-6, -1, 190), (6, -1, 190), (0, 0, 180)),
    "smug_sway": ((6, -2, 240), (8, -2, 500), (3, -1, 210), (0, 0, 170)),
    "sulk": ((-3, 5, 270), (-4, 7, 540), (-2, 4, 230), (0, 0, 190)),
    "sleepy_sag": ((0, 4, 320), (-2, 7, 440), (1, 6, 400), (0, 0, 260)),
    "stretch": ((0, 3, 200), (0, -6, 420), (0, -7, 480), (0, -2, 220), (0, 0, 170)),
    "celebrate": ((-6, -3, 190), (6, -3, 210), (-5, -2, 210), (0, 0, 190)),
    "moonwalk": ((-9, -2, 280), (-9, -2, 560), (0, 0, 220)),
    "patrol": ((5, 0, 330), (-5, 0, 330), (5, 0, 330), (-5, 0, 330), (0, 0, 210)),
    "zoomies": ((10, 0, 160), (-10, 0, 200), (10, 0, 180), (-8, 0, 200), (0, 0, 170)),
    "pounce": ((-7, 4, 350), (12, -2, 150), (4, 0, 190), (0, 0, 150)),
    "hide": ((4, 6, 210), (6, 9, 520), (2, 4, 220), (0, 0, 190)),
    "nod": ((0, 4, 150), (0, 1, 110), (0, 3, 150), (0, 0, 130)),
    "happy_bounce": ((0, -3, 160), (0, 1, 120), (0, -2, 150), (0, 0, 130)),
    "shake": ((-6, 0, 90), (6, 0, 90), (-4, 0, 90), (4, 0, 95), (0, 0, 130)),
    "startled_pop": ((0, -5, 120), (0, -4, 260), (0, 0, 200)),
}

# actions that fire their own particle burst (preset, delay_ms into the action)
ACTION_SELF_PARTICLES: dict[str, tuple[str, int]] = {
    "sneeze": ("sweat", 620),
    "peekaboo": ("exclaim", 940),
    "excited_spin": ("sparkle", 150),
    "spin_jump": ("stars", 330),
    "shiver": ("sweat", 200),
    "zoomies": ("dust", 180),
    "moonwalk": ("note", 260),
    "pounce": ("dust", 420),
}























class PaperclipPalApp:
    def __init__(self, soul: Soul, project_root: Path) -> None:
        self.project_root = project_root
        self.soul = soul
        self.project_root = project_root
        self.i18n = I18n(language=soul.language)
        self.pal_stats = load_stats(project_root / "memory" / "stats.json")
        self.pal_stats.total_sessions += 1
        self.pal_stats.last_session_at = time.time()
        self.brain = OllamaBrain(soul, project_root=project_root)
        self.chat_brain = PalChatBrain(soul)
        self.chat_session = ChatSession()
        self.ears = Ears()
        self._eyes: Eyes | None = None
        self._eyes_model = soul.vision_model
        self.codex_status = CodexStatusMonitor(project_root / "codex_status.json")
        self.codex_usage = CodexUsageMonitor(project_root / "codex_usage_status.json")
        self.hardware_status = HardwareStatusMonitor()
        self.claude_account_usage = ClaudeAccountUsageMonitor(project_root / "claude_account_status.json")
        self.openai_billing = OpenAIBillingMonitor(project_root / "settings.json")
        self.event_log = EventLog(project_root / "memory" / "event_log.jsonl")
        self.quiz_store = QuizStore(project_root / "python_pal" / "quiz_store.json")
        self._last_quiz_debug = ""
        self.state = PalState()
        self.alive = AliveLayer()
        self.decision = DecisionEngine()
        self.animation_player = AnimationPlayer(load_animation_manifest(project_root / "python_pal" / "animations.yaml"))
        self.animation_resolver = AnimationResolver(set(self.animation_player.manifest.performances))
        self.decorations = load_decoration_manifest(project_root / "python_pal" / "decorations.yaml")
        self.queue: queue.Queue[Reaction] = queue.Queue()
        self.status_queue: queue.Queue[Reaction] = queue.Queue()
        self.root = tk.Tk()
        self.root.title(soul.name)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT)
        self.root.configure(bg=TRANSPARENT)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
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
        self._anim_t = 0.0  # legacy-tick time base (advances 1.0 per 50ms equivalent)
        self._breath_depth = 3.0
        self._pupil_bounds: dict[int, tuple[float, float, float, float]] = {}
        self._sclera_bounds: dict[int, tuple[float, float, float, float]] = {}
        self._lid_items: list[int] = []  # wire-colored rects that cover eyes when closing
        self._eye_openness: float = 1.0  # 1.0 = fully open, 0.0 = fully closed
        self._eye_target_openness: float = 1.0
        self._chin_wire: int = 0
        self._chin_base_coords: tuple[float, ...] = ()
        self._chin_idle_phase: float = 0.0
        self._chin_syllable_phase: float = 0.0  # secondary phase for talk rhythm
        self._chin_syllable_amp: float = 1.0     # random per-syllable amplitude
        self._chin_pause_timer: int = 0           # frames until next micro-pause ends
        self._chin_mode: str = "idle"  # idle|talk|chew|yawn|mumble|cover|wave|point|fidget|think|sulk
        self._inner_pose: InnerPose = INNER_NEUTRAL_POSE
        self._inner_gesture_after: list[str] = []
        self._inner_gesture_active = False
        self._cheek_items: list[int] = []
        self._cheek_visible: bool = False
        self._pupil_look = (0.0, 0.0)
        self._pupil_size_scale = 1.0
        self._brow_base_coords: dict[int, tuple[float, ...]] = {}
        self.tail_wire = 0
        self._tail_base_coords: tuple[float, ...] = ()
        self._tail_wag_after: list[str] = []
        self._tail_pose: TailPose = TAIL_NEUTRAL_POSE
        self._tail_pose_trail: deque[tuple[float, TailPose]] = deque(maxlen=64)
        self._tail_osc_active = False
        self._tail_wave_factor: float | None = None
        self._tail_engage: tuple[float, float] | None = None
        self._tail_hand_mode = False
        self._tail_hand_started = 0.0
        self._body_wire: int = 0
        self._body_base_coords: tuple[float, ...] = ()
        self._body_bend: BodyBend = BODY_BEND_NEUTRAL
        self._bend_after: list[str] = []
        self._action_prop_items: list[int] = []
        self._action_prop_after: list[str] = []
        self._action_prop_pending: str | None = None
        self._action_prop_over_face = False
        self._tail_tip_point: tuple[float, float] = (0.0, 0.0)
        self._eye_fx_items: list[int] = []
        self._eye_fx_state: tuple[str | None, str | None] = (None, None)
        self._face_decal_items: list[int] = []
        self._drag_prev: tuple[int, float] | None = None
        self._pupil_blink_scale: float = 1.0
        self._tail_s_phase: float = 0.0
        self._tail_mode: str = "long"  # "short" or "long"
        self._is_blinking = False
        self._mouse_follow_after: str | None = None
        self._mouse_follow_until = 0.0
        self._mouse_follow_cooldown_until = 0.0
        self._secret_judge_until = 0.0
        self._pal_scale = (1.0, 1.0)
        self._rebound_after: str | None = None
        self._action_offset = (0.0, 0.0)
        self._spring = SquashStretchSpring()
        self._spring_active = False
        self._expr_tweener = ExpressionTweener(tween_frames=3)
        self._current_brow_spec: tuple[tuple[float, float, float], tuple[float, float, float]] = (
            (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
        )
        self._current_pupil_spec: tuple[float, float, float] = (0.0, 0.0, 1.0)
        self._shadow_item: int = 0
        self._tail_idle_phase: float = 0.0
        self._doze_stage: int = 0  # 0=normal, 1=drooping, 2=asleep, 3=waking
        self._doze_timer: float = 0.0
        self._last_active_time: float = time.time()
        self._large_action_after: str | None = None
        self._large_action_running = False
        self._window_move_after: str | None = None
        self._window_move_running = False
        self._shadow_action = ""
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
        self._decoration_items: dict[str, list[int]] = {"costume": [], "identity": [], "state": [], "temporary": []}
        self._melt_puddle_items: list[int] = []
        self._active_identity_id = ""
        self._active_identity_addons: tuple[str, ...] = ()
        self._decoration_after: list[str] = []
        self._delayed_decoration_after: list[str] = []
        self._decoration_anim_after: list[str] = []
        self._sleep_blanket_visible = False
        self._gentleman_prop_items: list[int] = []
        self._gentleman_hat_items: list[int] = []
        self._prop_anim_after: list[str] = []
        self._demo_after: list[str] = []
        self._particles = ParticleEmitter(self.canvas)
        self._chat_window: tk.Toplevel | None = None
        self._chat_entry: tk.Entry | None = None
        self._chat_thread: threading.Thread | None = None
        self._quiz_window: tk.Toplevel | None = None
        self._quiz_after: str | None = None
        self._quiz_result_after: str | None = None
        self._last_quiz_offer_at: float = 0.0
        self._quiz_offer_day: date = date.today()
        self._quiz_offers_today: int = 0
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
        self.claude_usage = ClaudeUsageMonitor()
        self._last_claude_event = ""
        self._last_claude_alive_pids: set[int] = set()
        self._last_claude_sessions_by_pid: dict[int, ClaudeSession] = {}
        self._recent_claude_status_fragments: list[str] = []
        self._last_claude_usage_status: ClaudeUsageStatus = ClaudeUsageStatus()
        self._last_claude_account_usage_status: ClaudeAccountUsageStatus = ClaudeAccountUsageStatus()
        self._last_claude_account_usage_event = ""
        self._logged_claude_account_usage_event = ""
        self._last_claude_account_usage_announcement_at = 0.0
        self._last_openai_billing_status: OpenAIBillingStatus = OpenAIBillingStatus()
        self._last_openai_billing_event = ""
        self._last_openai_billing_announcement_at = 0.0
        self._openai_billing_thread: threading.Thread | None = None
        self._performance_after: list[str] = []
        self._expression_after: list[str] = []
        self._last_animation_debug = "not played yet"
        self._last_idle_animation_debug = "idle animation not selected yet"
        self._last_alive_debug = self.alive.debug_text()
        self._alive_after: list[str] = []
        self._visual_state_name = "idle"
        self._visual_state_until = 0.0
        self._visual_state_priority = 0
        self._visual_state_interruptible = True
        self._visual_state_lifecycle = "loop"
        self._visual_state_after: str | None = None
        self._pending_visual_reaction: tuple[Reaction, bool, VisualStatePlan] | None = None
        self._recent_idle_actions: list[str] = []
        self._last_large_idle_action_at = 0.0
        self._last_move_idle_action_at = 0.0
        self._last_identity_idle_action_at = 0.0
        self.appearance = AppearanceState(language_mode=normalize_language(self.soul.language))
        self.mood = MoodEngine()
        initial_frequency = self._load_frequency_setting()
        self.mood.set_frequency(initial_frequency)
        self._freq_var = tk.StringVar(value=initial_frequency)
        self._identity_var = tk.StringVar(value=self._load_identity_setting())
        self._language_var = tk.StringVar(value=normalize_language(self.soul.language))
        self._focus_var = tk.BooleanVar(value=False)
        self._tail_mode_var = tk.StringVar(value=self._tail_mode)
        self._quiet_until = 0.0
        self._micro_after: str | None = None
        self._companion_after: str | None = None
        self._care_after: str | None = None
        # -- proactive care --
        self._care_engine = CareEngine(language=soul.language)
        # -- poke escalation --
        self._poke_count: int = 0
        self._last_poke_at: float = 0.0
        self._poke_cooldown_until: float = 0.0
        # -- running joke memory --
        self._running_joke_topic: str = ""
        self._running_joke_count: int = 0
        self._place_initially()
        self._hide_from_taskbar()
        self._draw_pal()
        self._sync_language_costume(play_enter=False)
        if normalize_language(self.soul.language) == "en":
            self._clear_non_costume_decorations()
        else:
            self._refresh_identity_decorations()
        self._bind_events()
        self._install_menu()
        self._load_quiz_fallbacks()
        self.root.after(ANIM_TICK_MS, self._animate)
        self.root.after(120, self._poll_global_mouse)
        self.root.after(100, self._poll_brain)
        self.root.after(1500, self._poll_codex_status)
        self.root.after(6000, self._poll_codex_usage)
        self.root.after(3500, self._poll_claude_status)
        self.root.after(7500, self._poll_claude_usage)
        self.root.after(8000, self._poll_claude_account_usage)
        self.root.after(9000, self._poll_openai_billing)
        self.root.after(4200, self._poll_hardware_status)
        self._schedule_blink()
        self._schedule_look()
        self._schedule_idle(first=True)
        self._schedule_ambient(first=True)
        self.root.after(LINE_BANK_FIRST_MAINTENANCE_MS, self._maintain_line_bank)
        self.root.after(VISION_FIRST_REFRESH_MS, self._refresh_eyes)
        self.root.after(2000, self._schedule_micro)
        self.root.after(3000, self._schedule_companion)
        self.root.after(3500, self._check_daily_greeting)
        self.root.after(60_000, self._schedule_care)
        self._schedule_quiz_heartbeat(first=True)
        self.root.after(650, lambda: self.show_bubble("你看起来很忙。主要是在避免开始。", 5200))

    def run(self) -> None:
        self.root.mainloop()

    @property
    def eyes(self) -> Eyes:
        """Lazy-init: Eyes (Ollama VLM) is only created on first access."""
        if self._eyes is None:
            self._eyes = Eyes(model=self._eyes_model)
        return self._eyes

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

    def _monitor_bounds_for_point(self, x: float, y: float) -> tuple[int, int, int, int]:
        if self._user32 and self.root.tk.call("tk", "windowingsystem") == "win32":
            try:
                point = _WinPoint(round(x), round(y))
                monitor = self._user32.MonitorFromPoint(point, 2)  # nearest monitor
                if monitor:
                    info = _WinMonitorInfo()
                    info.cbSize = ctypes.sizeof(_WinMonitorInfo)
                    if self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                        rect = info.rcWork
                        if rect.right > rect.left and rect.bottom > rect.top:
                            return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
            except Exception:
                pass
        return self._desktop_bounds()

    def _pal_screen_point(self, x: float = PAL_CENTER_X, y: float = PAL_SCALE_CENTER_Y) -> tuple[float, float]:
        self.root.update_idletasks()
        return (self.root.winfo_x() + x, self.root.winfo_y() + y)

    def _pal_monitor_bounds(self) -> tuple[int, int, int, int]:
        x, y = self._pal_screen_point()
        return self._monitor_bounds_for_point(x, y)

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
        # --- chin (inner end) --- split first curve as independent joint
        chin_coords = tuple(_scale_coords(_path_coords(BODY_START, (BODY_CURVES[0],))))
        self._chin_wire = c.create_line(
            *chin_coords, smooth=False,
            width=30 * PAL_SCALE, fill=WIRE, capstyle=tk.ROUND,
            joinstyle=tk.ROUND, tags=("pal", "wire", "chin"),
        )
        self._chin_base_coords = chin_coords
        # --- main body (adapts to tail mode) ---
        body_start_pt = BODY_CURVES[0][2]  # endpoint of first curve
        if self._tail_mode == "long":
            body_main_curves = BODY_CURVES[1:-2]
            tail_start = TAIL_LONG_START
            tail_curves = TAIL_LONG_CURVES
        else:
            body_main_curves = BODY_CURVES[1:-1]
            tail_start = TAIL_SHORT_START
            tail_curves = TAIL_SHORT_CURVES
        body_coords = _scale_coords(_path_coords(body_start_pt, body_main_curves))
        self._body_wire = c.create_line(
            *body_coords, smooth=False,
            width=30 * PAL_SCALE, fill=WIRE, capstyle=tk.ROUND,
            joinstyle=tk.ROUND, tags=("pal", "wire"),
        )
        self._body_base_coords = tuple(body_coords)
        # --- tail — high-res sampling for S-curve wave ---
        tail_coords = tuple(_scale_coords(_path_coords(tail_start, tail_curves, steps=36)))
        self.tail_wire = c.create_line(
            *tail_coords, smooth=False,
            width=30 * PAL_SCALE, fill=WIRE, capstyle=tk.ROUND,
            joinstyle=tk.ROUND, tags=("pal", "wire", "tail"),
        )
        self._tail_base_coords = tail_coords
        self._tail_tip_point = (tail_coords[-2], tail_coords[-1])
        left_sclera_bounds = _oval_bounds(57, 154.726, 57)
        right_sclera_bounds = _oval_bounds(213, 195.226, 57, 56.5)
        left_sclera = c.create_oval(*left_sclera_bounds, fill=EYE_WHITE, outline="", tags=("pal", "eye"))
        right_sclera = c.create_oval(*right_sclera_bounds, fill=EYE_WHITE, outline="", tags=("pal", "eye"))
        self._sclera_bounds = {
            left_sclera: left_sclera_bounds,
            right_sclera: right_sclera_bounds,
        }
        left_pupil_bounds = _oval_bounds(64, 154.726, 39)
        right_pupil_bounds = _oval_bounds(203, 192.726, 39)
        self.left_pupil = c.create_oval(*left_pupil_bounds, fill=PUPIL, outline="", tags=("pal", "pupil"))
        self.right_pupil = c.create_oval(*right_pupil_bounds, fill=PUPIL, outline="", tags=("pal", "pupil"))
        self._pupil_bounds = {
            self.left_pupil: left_pupil_bounds,
            self.right_pupil: right_pupil_bounds,
        }
        # eyelid overlays — arc-shaped, hidden in default state
        tint = HARDWARE_TINTS.get(self._hardware_tint_level, WIRE)
        for sb in (left_sclera_bounds, right_sclera_bounds):
            x1, y1, x2, y2 = sb
            lid = c.create_arc(
                x1 - 2, y1 - 2, x2 + 2, y2 + 2,
                start=0, extent=180, style=tk.CHORD,
                fill=tint, outline="", tags=("pal", "lid"),
                state="hidden",
            )
            self._lid_items.append(lid)
        for lid in self._lid_items:
            c.tag_raise(lid, "pupil")
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
        # cheek blush circles (hidden initially, shown for emotional expressions)
        left_cheek = _oval_bounds(20, 210, 22, 16)
        right_cheek = _oval_bounds(245, 250, 22, 16)
        for cb in (left_cheek, right_cheek):
            item = c.create_oval(*cb, fill=CHEEK_BLUSH, outline="", tags=("pal", "cheek"), state="hidden")
            self._cheek_items.append(item)
        # z-ordering: tail/chin behind eyes
        self.canvas.tag_lower(self.tail_wire, "eye")
        if self._chin_wire:
            self.canvas.tag_lower(self._chin_wire, "eye")
        self._apply_hardware_tint()

    def _reset_pal_geometry(self, preserve_tail: bool = False) -> None:
        # preserve_tail: finish callbacks of a PREVIOUS action must not kill a
        # tail animation the CURRENT action just started (osc ticks re-attach
        # to the redrawn wire on their next frame)
        if not preserve_tail:
            self._cancel_tail_wag(reset=False)
        self._cancel_inner_gesture(reset=False)
        self._cancel_bend(reset=False)
        self._body_bend = BODY_BEND_NEUTRAL
        self._body_wire = 0
        self._body_base_coords = ()
        # eye FX / decal items carry the "pal" tag and die with the redraw
        self._eye_fx_items.clear()
        self._eye_fx_state = (None, None)
        self._face_decal_items.clear()
        look = self._pupil_look
        self._particles.clear()
        self._clear_melt_puddle()
        self._clear_decorations()
        self.canvas.delete("pal")
        self.canvas.delete("melt_puddle")
        self.canvas.delete("shadow")
        self._shadow_item = 0
        self._shadow_action = ""
        self._pupil_bounds.clear()
        self._sclera_bounds.clear()
        self._lid_items.clear()
        self._cheek_items.clear()
        self._cheek_visible = False
        self._eye_openness = 1.0
        self._eye_target_openness = 1.0
        self.tail_wire = 0
        self._tail_base_coords = ()
        if not preserve_tail:
            self._tail_pose = TAIL_NEUTRAL_POSE
        self._chin_wire = 0
        self._chin_base_coords = ()
        self._inner_pose = INNER_NEUTRAL_POSE
        self._inner_gesture_active = False
        self._pal_scale = (1.0, 1.0)
        self._action_offset = (0.0, 0.0)
        self._bob_x = 0.0
        self._bob_y = 0.0
        self._draw_pal()
        self._redraw_costume_static()
        if self._active_identity_addons:
            self._set_decorations(self._active_identity_addons, lifetime="identity")
        self.canvas.tag_raise("decoration")
        self._pupil_look = look
        self._set_pupil_pose(*look, blink_scale=1.0)
        self._apply_hardware_tint()
        # an in-flight emotion prop survives the redraw; restore its layering
        if self._action_prop_items:
            self.canvas.tag_raise("action_prop")
            if not self._action_prop_over_face:
                self._raise_face_over_costume()

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._poke(force=True))

    def _install_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Talk to 夹夹", command=self._open_chat_input)
        self.menu.add_command(label="Say something", command=lambda: self._ask_brain("manual"))
        self.menu.add_command(label="Poke", command=lambda: self._poke(force=True))

        status_menu = tk.Menu(self.menu, tearoff=False)
        status_menu.add_command(label="Status overview", command=self._show_status_overview)
        status_menu.add_separator()
        status_menu.add_command(label="Codex status", command=self._show_codex_status)
        status_menu.add_command(label="Codex usage", command=self._show_codex_usage)
        status_menu.add_command(label="Claude status", command=self._show_claude_status)
        status_menu.add_command(label="Claude usage", command=self._show_claude_usage)
        status_menu.add_command(label="Claude account usage", command=self._show_claude_account_usage)
        status_menu.add_command(label="OpenAI API billing", command=self._show_openai_billing)
        status_menu.add_command(label="Hardware status", command=self._show_hardware_status)
        status_menu.add_separator()
        status_menu.add_command(label="Last events", command=self._show_last_events)
        status_menu.add_command(label="Morning digest", command=self._show_morning_digest)
        self.menu.add_cascade(label="Status", menu=status_menu)

        action_menu = tk.Menu(self.menu, tearoff=False)
        action_menu.add_command(label="Boredom line", command=lambda: self._ask_brain("bored"))
        action_menu.add_command(label="土味情话", command=self._ask_cheesy_love)
        action_menu.add_command(label="Absurd quiz / 小测验", command=lambda: self._offer_absurd_quiz(force=True))
        action_menu.add_separator()
        for group_label, action_ids in ACTION_MENU_GROUPS:
            group_menu = tk.Menu(action_menu, tearoff=False)
            for action_id in action_ids:
                group_menu.add_command(
                    label=ACTION_LABELS[action_id],
                    command=lambda action_id=action_id: self._perform_action(action_id),
                )
            action_menu.add_cascade(label=group_label, menu=group_menu)
        self.menu.add_cascade(label="Actions", menu=action_menu)

        mode_menu = tk.Menu(self.menu, tearoff=False)
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
        mode_menu.add_cascade(label="Identity", menu=identity_menu)
        language_menu = tk.Menu(self.menu, tearoff=False)
        for language, label in LANGUAGE_OPTIONS:
            language_menu.add_radiobutton(
                label=label,
                variable=self._language_var,
                value=language,
                command=lambda language=language: self._set_language(language),
            )
        mode_menu.add_cascade(label="Language / \u8bed\u8a00", menu=language_menu)
        freq_menu = tk.Menu(self.menu, tearoff=False)
        for label, _mult in FREQUENCY_PRESETS:
            freq_menu.add_radiobutton(
                label=label,
                variable=self._freq_var,
                value=label,
                command=lambda k=label: self._set_frequency(k),
            )
        mode_menu.add_cascade(label="活跃度", menu=freq_menu)
        tail_menu = tk.Menu(self.menu, tearoff=False)
        tail_menu.add_radiobutton(
            label="Short (tip only)",
            variable=self._tail_mode_var,
            value="short",
            command=lambda: self._set_tail_mode("short"),
        )
        tail_menu.add_radiobutton(
            label="Long (cat tail)",
            variable=self._tail_mode_var,
            value="long",
            command=lambda: self._set_tail_mode("long"),
        )
        mode_menu.add_cascade(label="Tail", menu=tail_menu)
        mode_menu.add_separator()
        mode_menu.add_command(label="Quiet 30 min", command=lambda: self._quiet_for(30 * 60))
        mode_menu.add_checkbutton(label="Focus mode", variable=self._focus_var, command=self._toggle_focus_mode)
        mode_menu.add_command(label="Summon / resume", command=self._resume_auto_reactions)
        self.menu.add_cascade(label="Mode", menu=mode_menu)

        debug_menu = tk.Menu(self.menu, tearoff=False)
        preview_menu = tk.Menu(debug_menu, tearoff=False)
        for performance_id in sorted(self.animation_player.manifest.performances):
            preview_menu.add_command(
                label=performance_id,
                command=lambda performance_id=performance_id: self._preview_performance(performance_id),
            )
        debug_menu.add_cascade(label="Animation Preview", menu=preview_menu)
        debug_menu.add_separator()
        debug_menu.add_command(label="Scripted demo", command=self._run_scripted_demo)
        debug_menu.add_command(label="Debug last decision", command=self._show_last_decision_debug)
        debug_menu.add_command(label="Last chat context", command=self._show_last_chat_context)
        debug_menu.add_command(label="Debug animation", command=self._show_last_animation_debug)
        debug_menu.add_command(label="Debug aliveness", command=self._show_alive_debug)
        debug_menu.add_command(label="Debug identity", command=self._show_identity_debug)
        self.menu.add_cascade(label="Developer", menu=debug_menu)

        self.menu.add_separator()
        self.menu.add_command(label="退出", command=self._quit)

    def _show_context_menu(self, event: tk.Event) -> None:
        self._popup_context_menu()

    def _popup_context_menu(self) -> None:
        self.root.update_idletasks()
        left, top, right, bottom = self._pal_monitor_bounds()
        pal_left, pal_mid_y = self._pal_screen_point(PAL_PAD_X, PAL_PAD_Y + PAL_HEIGHT * 0.48)
        pal_right, _ = self._pal_screen_point(PAL_PAD_X + PAL_WIDTH, PAL_PAD_Y + PAL_HEIGHT * 0.48)
        try:
            self.menu.update_idletasks()
            menu_w = max(220, int(self.menu.winfo_reqwidth()))
            menu_h = max(280, int(self.menu.winfo_reqheight()))
        except tk.TclError:
            menu_w = 240
            menu_h = 420

        if pal_right + 12 + menu_w <= right - 8:
            x = pal_right + 12
        else:
            x = pal_left - menu_w - 12
        y = pal_mid_y - 24
        x_high = max(left + 8, right - menu_w - 8)
        y_high = max(top + 8, bottom - menu_h - 8)
        x = min(max(left + 8, x), x_high)
        y = min(max(top + 8, y), y_high)
        try:
            self.menu.tk_popup(round(x), round(y))
        finally:
            self.menu.grab_release()

    def _show_status_overview(self) -> None:
        reaction = local_status_reaction("status_overview", self._build_chat_context())
        if reaction:
            self._apply_reaction(reaction, force=True)

    def _quit(self) -> None:
        self._stop_brain_wait_animation()
        self._stop_chat_wait_feedback(clear_bubble=True)
        self._cancel_performance_phrase()
        self._cancel_tail_wag(reset=False)
        self._cancel_delayed_decoration_cues()
        self._clear_gentleman_props()
        self._clear_decorations("temporary")
        self._particles.clear()
        self._cancel_scripted_demo()
        for attr in (
            "_mouse_follow_after",
            "_rebound_after",
            "_large_action_after",
            "_window_move_after",
            "_hardware_tint_after",
            "_status_badge_after",
            "_visual_state_after",
            "_micro_after",
            "_companion_after",
            "_care_after",
            "_quiz_after",
            "_quiz_result_after",
        ):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, attr, None)
        if self._chat_window and self._chat_window.winfo_exists():
            try:
                self._chat_window.destroy()
            except tk.TclError:
                pass
        if self._quiz_window and self._quiz_window.winfo_exists():
            try:
                self._quiz_window.destroy()
            except tk.TclError:
                pass
        try:
            self.bubble_root.destroy()
        except tk.TclError:
            pass
        self.root.destroy()

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

    def _load_quiz_fallbacks(self) -> None:
        loaded = 0
        errors: list[str] = []
        try:
            packets = load_quiz_packets(self.project_root / "python_pal" / "quizzes.yaml")
        except Exception as exc:
            self._last_quiz_debug = f"fallback load failed: {exc}"
            return
        for packet in packets:
            packet_errors = validate_quiz_packet(packet)
            if packet_errors:
                errors.append(f"{packet.id or '<missing>'}: {'; '.join(packet_errors[:3])}")
                continue
            self.quiz_store.upsert_packet(packet)
            loaded += 1
        if errors:
            self._last_quiz_debug = f"loaded {loaded} quiz packet(s); rejected: " + " | ".join(errors)
        else:
            self._last_quiz_debug = f"loaded {loaded} quiz packet(s)"

    def _schedule_quiz_heartbeat(self, first: bool = False) -> None:
        if self._quiz_after:
            try:
                self.root.after_cancel(self._quiz_after)
            except tk.TclError:
                pass
        policy = self._activity_policy()
        delay = QUIZ_FIRST_HEARTBEAT_MS if first else QUIZ_INTERVAL_MS.get(policy.tier, QUIZ_INTERVAL_MS["normal"])
        self._quiz_after = self.root.after(delay, self._quiz_heartbeat)

    def _quiz_heartbeat(self) -> None:
        self._quiz_after = None
        try:
            if self._quiz_should_offer():
                self._offer_absurd_quiz(force=False)
        finally:
            self._schedule_quiz_heartbeat()

    def _quiz_should_offer(self) -> bool:
        today = date.today()
        if today != self._quiz_offer_day:
            self._quiz_offer_day = today
            self._quiz_offers_today = 0
        policy = self._activity_policy()
        daily_limit = QUIZ_DAILY_LIMIT.get(policy.tier, 1)
        if daily_limit <= 0 or self._quiz_offers_today >= daily_limit:
            return False
        if (
            self._focus_var.get()
            or self._quiet_remaining_seconds() > 0
            or self.state.brain_busy
            or self._bubble_items
            or self._quiz_window
            or self._dragging
            or self._large_action_running
            or self._window_move_running
        ):
            return False
        if self.quiz_store.active_session() is not None:
            return False
        if self.quiz_store.next_packet(normalize_language(self.soul.language)) is None:
            return False
        interval = QUIZ_INTERVAL_MS.get(policy.tier, QUIZ_INTERVAL_MS["normal"]) / 1000
        if time.time() - self._last_quiz_offer_at < interval:
            return False
        chance = {"normal": 0.18, "active": 0.36, "hyper": 0.58}.get(policy.tier, 0.0)
        return random.random() < chance

    def _offer_absurd_quiz(self, force: bool = False) -> None:
        self._load_quiz_fallbacks()
        active_session = self.quiz_store.active_session()
        if active_session is not None:
            packet = self.quiz_store.get_packet(active_session.packet_id)
            if packet is None:
                self.quiz_store.clear_session()
            else:
                self._show_quiz_resume_offer(packet, active_session)
                return

        packet = self.quiz_store.next_packet(normalize_language(self.soul.language))
        if packet is None:
            self.show_bubble("我还没有可用的小测验。题库空得很有态度。", milliseconds=3600, kind="thought")
            return
        if not force:
            self._last_quiz_offer_at = time.time()
            self._quiz_offers_today += 1
        self._perform_action("thinking_tilt")
        self._open_quiz_card(
            packet.title,
            f"{packet.subtitle}\n\n夹夹可以问你 {len(packet.questions)} 个很不严肃的问题。",
            [
                ("开始", lambda packet=packet: self._start_quiz(packet)),
                ("稍后", self._dismiss_quiz_window),
                ("今天别考我", self._dismiss_quiz_today),
            ],
        )

    def _show_quiz_resume_offer(self, packet: QuizPacket, session: QuizSession) -> None:
        self._open_quiz_card(
            packet.title,
            f"上次的小测验停在第 {session.current_index + 1} 题。它没有忘，主要是 JSON 没忘。",
            [
                ("继续", lambda packet=packet, session=session: self._resume_quiz(packet, session)),
                ("重新开始", lambda packet=packet: self._start_quiz(packet)),
                ("放弃", self._abandon_quiz),
            ],
        )

    def _start_quiz(self, packet: QuizPacket) -> None:
        session = QuizSession.start(packet)
        self.quiz_store.save_session(session)
        self._perform_action("fake_innocent")
        self._show_quiz_question(packet, session)

    def _resume_quiz(self, packet: QuizPacket, session: QuizSession) -> None:
        session.state = "active"
        session.updated_at = time.time()
        self.quiz_store.save_session(session)
        self._show_quiz_question(packet, session)

    def _show_quiz_question(self, packet: QuizPacket, session: QuizSession) -> None:
        question = current_question(packet, session)
        if question is None:
            self._show_quiz_result_delay(packet, session)
            return
        total = len(packet.questions)
        body = f"{session.current_index + 1}/{total}\n{question.text}"
        buttons: list[tuple[str, Callable[[], None]]] = []
        for option in question.options:
            label = f"{option.id.upper()}. {option.text}"
            buttons.append((label, lambda option_id=option.id: self._handle_quiz_answer(option_id)))
        buttons.extend(
            [
                ("暂停", self._pause_quiz),
                ("放弃", self._abandon_quiz),
            ]
        )
        self._open_quiz_card(packet.title, body, buttons)

    def _handle_quiz_answer(self, option_id: str) -> None:
        session = self.quiz_store.active_session()
        if session is None:
            self._dismiss_quiz_window()
            return
        packet = self.quiz_store.get_packet(session.packet_id)
        if packet is None:
            self.quiz_store.clear_session()
            self._dismiss_quiz_window()
            return
        try:
            session = record_answer(packet, session, option_id)
        except ValueError:
            self.show_bubble("这个选项不在题目里。夹夹暂时不接受平行宇宙答案。", milliseconds=3600, kind="thought")
            return
        if session.state == "completed":
            self.quiz_store.save_session(session)
            self._show_quiz_result_delay(packet, session)
            return
        self.quiz_store.save_session(session)
        self._show_quiz_question(packet, session)

    def _pause_quiz(self) -> None:
        session = self.quiz_store.active_session()
        if session is not None:
            session.state = "paused"
            session.updated_at = time.time()
            self.quiz_store.save_session(session)
        self._dismiss_quiz_window()
        self.show_bubble("先暂停。题目会待在本地 JSON 里，像一只很小的备案。", milliseconds=3600, kind="thought")

    def _abandon_quiz(self) -> None:
        self.quiz_store.clear_session()
        self._dismiss_quiz_window()
        self._perform_action("fake_sulk")
        self.show_bubble("放弃成功。夹夹尊重逃生路线。", milliseconds=3200, kind="thought")

    def _show_quiz_result_delay(self, packet: QuizPacket, session: QuizSession) -> None:
        self._dismiss_quiz_window()
        self._perform_action("thinking_tilt")
        self.show_bubble("正在把答案塞进荒谬统计学。请稍等，它需要装得很严谨。", milliseconds=2600, kind="thought")
        if self._quiz_result_after:
            try:
                self.root.after_cancel(self._quiz_result_after)
            except tk.TclError:
                pass
        self._quiz_result_after = self.root.after(
            1500,
            lambda packet=packet, session=session: self._show_quiz_result(packet, session),
        )

    def _show_quiz_result(self, packet: QuizPacket, session: QuizSession) -> None:
        self._quiz_result_after = None
        scores = score_packet(packet, session.answers)
        result = choose_result(packet, scores)
        self.quiz_store.clear_session()
        self._perform_action(result.action or "snap_innocent")
        score_line = " / ".join(f"{metric}:{scores.get(metric, 0)}" for metric in packet.metrics)
        self._open_quiz_card(
            result.title,
            f"{result.line}\n\n分数只是装饰：{score_line}",
            [
                ("收到", self._dismiss_quiz_window),
                ("再测一次", lambda packet=packet: self._start_quiz(packet)),
            ],
        )

    def _dismiss_quiz_today(self) -> None:
        policy = self._activity_policy()
        self._quiz_offers_today = QUIZ_DAILY_LIMIT.get(policy.tier, 1)
        self._dismiss_quiz_window()
        self.show_bubble("今天不考。夹夹把试卷折起来了，姿态很专业。", milliseconds=3200, kind="thought")

    def _dismiss_quiz_window(self) -> None:
        if self._quiz_window:
            try:
                self._quiz_window.destroy()
            except tk.TclError:
                pass
        self._quiz_window = None

    def _open_quiz_card(
        self,
        title: str,
        body: str,
        buttons: list[tuple[str, Callable[[], None]]],
    ) -> None:
        self._dismiss_quiz_window()
        window = tk.Toplevel(self.root)
        self._quiz_window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg="#d4dee8")
        window.bind("<Escape>", lambda _event: self._dismiss_quiz_window())
        window.protocol("WM_DELETE_WINDOW", self._dismiss_quiz_window)

        shell = tk.Frame(window, bg="#d4dee8", padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        inner = tk.Frame(shell, bg="#fdfdfd", padx=12, pady=11)
        inner.pack(fill="both", expand=True)
        tk.Label(
            inner,
            text=title,
            bg="#fdfdfd",
            fg="#202932",
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 10, "bold"),
            wraplength=QUIZ_CARD_WIDTH - 36,
        ).pack(fill="x")
        tk.Label(
            inner,
            text=body,
            bg="#fdfdfd",
            fg="#3a4652",
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 9),
            wraplength=QUIZ_CARD_WIDTH - 36,
        ).pack(fill="x", pady=(7, 8))
        for label, command in buttons:
            tk.Button(
                inner,
                text=label,
                command=command,
                anchor="w",
                justify="left",
                relief="flat",
                bd=0,
                padx=9,
                pady=5,
                bg="#eef2f7",
                fg="#202932",
                activebackground="#dfe7f0",
                activeforeground="#202932",
                font=("Microsoft YaHei UI", 9),
                wraplength=QUIZ_CARD_WIDTH - 54,
            ).pack(fill="x", pady=2)

        self._hide_window_from_taskbar(window)
        self._position_quiz_window(window)
        window.deiconify()
        window.lift()

    def _position_quiz_window(self, window: tk.Toplevel) -> None:
        try:
            window.update_idletasks()
            width = QUIZ_CARD_WIDTH
            height = min(max(190, int(window.winfo_reqheight())), 520)
            left, top, right, bottom = self._pal_monitor_bounds()
            x = self.root.winfo_x() + PAL_CENTER_X - width / 2
            y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + 12
            if y + height > bottom - 8:
                y = self.root.winfo_y() + PAL_PAD_Y - height - 12
            x = min(max(left + 8, x), max(left + 8, right - width - 8))
            y = min(max(top + 8, y), max(top + 8, bottom - height - 8))
            window.geometry(_geometry_with_size(width, height, x, y))
        except tk.TclError:
            return

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
        interruptibility = self._interruptibility(world)
        context = build_chat_context(
            world,
            activity_mode=self._freq_var.get(),
            activity_tier=policy.tier,
            focus_mode=bool(self._focus_var.get()),
            quiet_remaining_seconds=self._quiet_remaining_seconds(),
        )
        context.update(interruptibility.as_context())
        context["alive"] = self.alive.as_context()
        context["language_mode"] = normalize_language(self.soul.language)
        context["appearance"] = {
            "costume_id": self.appearance.costume_id,
            "phase": self.appearance.phase,
            "language_mode": self.appearance.language_mode,
        }
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
            self._popup_context_menu()
        self._global_left_down = left_down
        self._global_right_down = right_down
        self.root.after(GLOBAL_MOUSE_POLL_MS, self._poll_global_mouse)

    def _point_in_pal_hitbox(self, x_root: int, y_root: int) -> bool:
        self.root.update_idletasks()
        left = self.root.winfo_x() + PAL_PAD_X - PAL_HIT_MARGIN_X
        top = self.root.winfo_y() + PAL_PAD_Y - PAL_HIT_MARGIN_Y
        right = self.root.winfo_x() + PAL_PAD_X + PAL_WIDTH + PAL_HIT_MARGIN_X
        bottom = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + PAL_HIT_MARGIN_Y
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

    def _set_tail_mode(self, mode: str) -> None:
        if mode == self._tail_mode:
            return
        self._tail_mode = mode
        self._tail_mode_var.set(mode)
        self._reset_pal_geometry()

    def _set_language(self, language: str) -> None:
        key = normalize_language(language, fallback=normalize_language(self.soul.language))
        self._language_var.set(key)
        if key == normalize_language(self.soul.language):
            if key == "en" and self.appearance.costume_id != "britclip":
                self._enter_britclip_costume()
            return
        self._save_language_setting(key)
        self._reload_language_runtime(key)
        line = (
            "Language switched to English. Britclip protocol: genderless, courteous, and unfortunately still judgmental."
            if key == "en"
            else "\u8bed\u8a00\u5207\u56de\u4e2d\u6587\u3002\u540c\u4e00\u53ea\u5939\u5939\uff0c\u5634\u6b20\u9891\u7387\u4e0d\u53d8\u3002"
        )
        if key == "en":
            self._enter_britclip_costume()
            self._prop_anim_after.append(self.root.after(1900, lambda: self.show_bubble(line, milliseconds=5200, kind="thought")))
        else:
            self._exit_britclip_costume()
            self._prop_anim_after.append(self.root.after(1550, lambda: self.show_bubble(line, milliseconds=3600, kind="thought")))

    def _reload_language_runtime(self, language: str) -> None:
        package_root = self.project_root / "python_pal"
        soul = load_soul(soul_path_for_language(package_root, language))
        soul.language = normalize_language(language)
        self.soul = soul
        self.i18n.set_language(soul.language)
        self.brain = OllamaBrain(soul, project_root=self.project_root)
        self.chat_brain = PalChatBrain(soul)
        self.chat_session = ChatSession()
        self._care_engine = CareEngine(language=soul.language)
        self._eyes_model = soul.vision_model
        self._eyes = None
        self.root.title(soul.name)
        self._identity_var.set(self._valid_identity_id(self._identity_var.get()))
        self._install_menu()
        if normalize_language(language) == "en":
            self._clear_non_costume_decorations()
        else:
            self._refresh_identity_decorations()

    def _sync_language_costume(self, play_enter: bool = False) -> None:
        language = normalize_language(self.soul.language)
        self.appearance.language_mode = language
        if language == "en":
            if play_enter:
                self._enter_britclip_costume()
            else:
                self._equip_britclip_static()
            return
        if self.appearance.costume_id == "britclip":
            if play_enter:
                self._exit_britclip_costume()
            else:
                self._clear_gentleman_props()
                self.appearance = AppearanceState(language_mode=language)

    def _enter_britclip_costume(self) -> None:
        self._clear_non_costume_decorations()
        self._perform_action("britclip_enter")

    def _exit_britclip_costume(self) -> None:
        if self.appearance.costume_id == "britclip" or self._gentleman_prop_items:
            self._perform_action("britclip_exit")
            return
        self._perform_action("micro_snap_innocent")
        self.appearance = AppearanceState(language_mode=normalize_language(self.soul.language))

    def _equip_britclip_static(self) -> None:
        self._clear_non_costume_decorations()
        self._clear_gentleman_props()
        self.appearance = AppearanceState(
            costume_id="britclip",
            phase="equipped",
            language_mode="en",
        )
        self._draw_gentleman_cane()
        self._draw_britclip_bow_tie()
        self._draw_bowler_hat(*self._gentleman_hat_head_anchor(), scale=1.18)
        self._raise_face_over_costume()
        self._set_brow_pose("proud")
        self._set_eye_pose("side_eye")

    def _redraw_costume_static(self) -> None:
        if self.appearance.costume_id == "britclip":
            phase = self.appearance.phase
            self._equip_britclip_static()
            self.appearance.phase = phase if phase != "plain" else "equipped"

    def _set_identity(self, identity_id: str) -> None:
        key = self._valid_identity_id(identity_id)
        self._identity_var.set(key)
        self._save_identity_setting(key)
        if key == "auto":
            self._active_identity_id = ""
            self._hide_sleep_blanket()
        self._refresh_identity_decorations()
        if key == "auto":
            self.show_bubble("身份切回 Auto。夹夹会按场景换班。", milliseconds=2600, kind="thought")
            return
        pack = self.brain.identities.get(key)
        self._play_identity_state_cue(pack.id, pack.default_mood)
        self.show_bubble(f"身份切到 {pack.display_name}。", milliseconds=2600, kind="thought")

    def _play_identity_state_cue(self, identity_id: str, default_mood: str = "idle") -> None:
        self._cancel_delayed_decoration_cues()
        if identity_id != "sleepy_clip":
            self._hide_sleep_blanket()
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
            if event.startswith(("codex_usage", "claude_usage", "openai_billing", "chat_usage", "chat_claude_usage", "chat_openai_billing", "demo_usage")) or bubble.startswith("usage_"):
                return "usage_accountant"
            if event.startswith(("codex_", "claude_", "chat_codex", "chat_claude", "demo_codex")) or bubble.startswith(("codex_", "claude_")):
                return "agent_supervisor"
            if reaction.mood in {"sleepy", "sulky"}:
                return "sleepy_clip"
        return "default_pal"

    def _refresh_identity_decorations(self, reaction: Reaction | None = None) -> None:
        pack = self._current_identity_pack(reaction)
        self._active_identity_id = pack.id
        if self.appearance.costume_id == "britclip":
            self._active_identity_addons = ()
            self._clear_decorations("identity")
            if pack.id != "sleepy_clip" and self._doze_stage < 2:
                self._hide_sleep_blanket()
            return
        addons = tuple(addon for addon in pack.visual_addons if self.decorations.get(addon))
        self._active_identity_addons = addons
        self._set_decorations(addons, lifetime="identity")
        if pack.id != "sleepy_clip" and self._doze_stage < 2:
            self._hide_sleep_blanket()

    def _set_decorations(self, decoration_ids: tuple[str, ...] | list[str], lifetime: str = "identity") -> None:
        self._clear_decorations(lifetime)
        for decoration_id in decoration_ids:
            definition = self.decorations.get(decoration_id)
            if definition:
                self._draw_decoration(definition, lifetime=lifetime)

    def _clear_non_costume_decorations(self) -> None:
        self._cancel_delayed_decoration_cues()
        for lifetime in ("identity", "state", "temporary"):
            self._clear_decorations(lifetime)
        self._active_identity_addons = ()
        self._sleep_blanket_visible = False

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

    def _queue_sleep_blanket(self, delay_ms: int = 9000) -> None:
        holder: list[str] = []

        def fire() -> None:
            if holder and holder[0] in self._delayed_decoration_after:
                self._delayed_decoration_after.remove(holder[0])
            if self._doze_stage >= 2:
                self._show_sleep_blanket()

        after_id = self.root.after(max(0, delay_ms), fire)
        holder.append(after_id)
        self._delayed_decoration_after.append(after_id)

    def _show_sleep_blanket(self) -> None:
        if self._sleep_blanket_visible:
            return
        decoration_ids = ["draft_blanket"]
        if self._should_show_sleep_cap():
            decoration_ids.append("sleepy_cap")
        self._set_decorations(decoration_ids, lifetime="state")
        self._sleep_blanket_visible = True

    def _hide_sleep_blanket(self) -> None:
        if not self._sleep_blanket_visible:
            return
        self._clear_decorations("state")
        self._sleep_blanket_visible = False

    def _should_show_sleep_cap(self) -> bool:
        hour = datetime.now().hour
        return hour >= 22 or hour < 7

    def _cancel_delayed_decoration_cues(self) -> None:
        for after_id in self._delayed_decoration_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._delayed_decoration_after.clear()

    def _clear_decorations(self, lifetime: str | None = None) -> None:
        self._cancel_decoration_animations()
        lifetimes = (lifetime,) if lifetime else tuple(self._decoration_items)
        for key in lifetimes:
            for item in self._decoration_items.get(key, []):
                try:
                    self.canvas.delete(item)
                except tk.TclError:
                    pass
            self._decoration_items[key] = []
            if key == "state":
                self._sleep_blanket_visible = False
            if key == "costume":
                self._gentleman_prop_items.clear()
                self._gentleman_hat_items.clear()
        if lifetime is None or lifetime == "temporary":
            self._clear_melt_puddle()
            if lifetime is None:
                self._cancel_delayed_decoration_cues()
            if lifetime is None or lifetime == "temporary":
                for after_id in self._decoration_after:
                    try:
                        self.root.after_cancel(after_id)
                    except tk.TclError:
                        pass
                self._decoration_after.clear()
        if lifetime is None:
            self._cancel_prop_anim_after()
            self._gentleman_prop_items.clear()
            self._gentleman_hat_items.clear()

    def _cancel_decoration_animations(self) -> None:
        for after_id in self._decoration_anim_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._decoration_anim_after.clear()

    def _cancel_prop_anim_after(self, reset_body: bool = True) -> None:
        for after_id in self._prop_anim_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._prop_anim_after.clear()
        if reset_body:
            self._set_action_offset(0.0, 0.0)
            self._set_pal_scale(1.0, 1.0)

    def _clear_gentleman_props(self, cancel_timers: bool = True) -> None:
        if cancel_timers:
            self._cancel_prop_anim_after()
        item_ids = set(self._gentleman_prop_items)
        for item in item_ids:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        if item_ids:
            for key, items in self._decoration_items.items():
                self._decoration_items[key] = [item for item in items if item not in item_ids]
        self._gentleman_prop_items.clear()
        self._gentleman_hat_items.clear()

    def _register_gentleman_props(self, items: list[int], *, hat: bool = False, lifetime: str = "costume") -> None:
        if not items:
            return
        self._gentleman_prop_items.extend(items)
        if hat:
            self._gentleman_hat_items = list(items)
        self._decoration_items.setdefault(lifetime, []).extend(items)
        for item in items:
            self.canvas.addtag_withtag("decoration", item)
            self.canvas.addtag_withtag("gentleman_prop", item)
        self.canvas.tag_raise("decoration")

    def _clear_melt_puddle(self) -> None:
        for item in getattr(self, "_melt_puddle_items", []):
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._melt_puddle_items = []

    def _draw_melt_puddle(self, progress: float) -> None:
        self._clear_melt_puddle()
        p = _clamp(progress, 0.0, 1.0)
        if p < 0.18:
            return
        eased = _ease_out_cubic((p - 0.18) / 0.82)
        cx, cy = self._actor_point(PAL_CENTER_X, PAL_SCALE_PIVOT_Y + 3)
        rx = 14 + 50 * eased
        ry = 2.5 + 7.5 * eased
        tint = HARDWARE_TINTS.get(self._hardware_tint_level, WIRE)
        pale = "#c8c8c8"
        highlight = "#ededed"
        brow = BROW
        items = [
            self.canvas.create_oval(cx - rx, cy - ry, cx + rx, cy + ry, fill=tint, outline=""),
        ]
        if p > 0.42:
            items.append(
                self.canvas.create_oval(
                    cx - rx * 0.42,
                    cy - ry * 1.55,
                    cx + rx * 0.22,
                    cy + ry * 0.20,
                    fill=pale,
                    outline="",
                )
            )
        if p > 0.62:
            eye_y = cy - ry * 0.62
            eye_r = 3.6 + 2.0 * eased
            items.extend(
                [
                    self.canvas.create_oval(cx - rx * 0.30 - eye_r, eye_y - eye_r, cx - rx * 0.30 + eye_r, eye_y + eye_r, fill=brow, outline=""),
                    self.canvas.create_oval(cx + rx * 0.20 - eye_r, eye_y - eye_r * 0.9, cx + rx * 0.20 + eye_r, eye_y + eye_r * 0.9, fill=brow, outline=""),
                    self.canvas.create_line(cx - rx * 0.45, eye_y - 10, cx - rx * 0.12, eye_y - 8, fill=brow, width=3.2, capstyle=tk.ROUND),
                    self.canvas.create_line(cx + rx * 0.02, eye_y - 8, cx + rx * 0.38, eye_y - 6, fill=brow, width=3.2, capstyle=tk.ROUND),
                ]
            )
        if p > 0.72:
            items.append(
                self.canvas.create_oval(
                    cx - rx * 0.66,
                    cy - ry * 0.70,
                    cx - rx * 0.18,
                    cy + ry * 0.12,
                    fill=highlight,
                    outline="",
                )
            )
        self._melt_puddle_items = items
        for item in items:
            self.canvas.addtag_withtag("melt_puddle", item)
            try:
                self.canvas.tag_lower(item, "pal")
            except tk.TclError:
                pass

    def _pal_source_point(self, x: float, y: float) -> tuple[float, float]:
        return self._actor_point(*_source_point(x, y))

    def _gentleman_hat_head_anchor(self) -> tuple[float, float]:
        return self._pal_source_point(151.0, -8.0)

    def _gentleman_tail_anchor(self) -> tuple[float, float]:
        if self.tail_wire:
            bbox = self.canvas.bbox(self.tail_wire)
            if bbox:
                return (bbox[2] + 10, bbox[1] + 10)
        return self._pal_source_point(301.0, 250.726)

    def _draw_bowler_hat(self, cx: float, cy: float, scale: float = 1.0) -> list[int]:
        s = scale
        dark = BROW
        band = "#76505a"
        items = [
            self.canvas.create_oval(cx - 12 * s, cy - 13 * s, cx + 12 * s, cy + 8 * s, fill=dark, outline=""),
            _rounded_rect(self.canvas, cx - 13 * s, cy - 3 * s, cx + 13 * s, cy + 9 * s, 5 * s, fill=dark, outline=""),
            self.canvas.create_line(cx - 9 * s, cy + 1 * s, cx + 9 * s, cy + 1 * s, fill=band, width=3.2 * s, capstyle=tk.ROUND),
            _rounded_rect(self.canvas, cx - 20 * s, cy + 7 * s, cx + 20 * s, cy + 13 * s, 4 * s, fill=dark, outline=""),
        ]
        self._register_gentleman_props(items, hat=True)
        return items

    def _draw_gentleman_whiskers(self) -> list[int]:
        white = "#fbfaf5"
        mx, my = self._pal_source_point(150.0, 226.0)
        items = [
            self.canvas.create_line(
                mx - 26, my - 2, mx - 13, my + 8, mx - 2, my + 2,
                fill=white, width=7.5, smooth=True, splinesteps=10, capstyle=tk.ROUND,
            ),
            self.canvas.create_line(
                mx + 3, my + 2, mx + 16, my + 8, mx + 29, my - 2,
                fill=white, width=7.5, smooth=True, splinesteps=10, capstyle=tk.ROUND,
            ),
        ]
        items.extend(
            [
                self.canvas.create_line(mx - 21, my - 5, mx - 2, my + 2, fill="#ebe6dd", width=2.6, smooth=True, splinesteps=10, capstyle=tk.ROUND),
                self.canvas.create_line(mx + 3, my + 2, mx + 23, my - 5, fill="#ebe6dd", width=2.6, smooth=True, splinesteps=10, capstyle=tk.ROUND),
            ]
        )
        self._register_gentleman_props(items)
        return items

    def _draw_gentleman_tie(self) -> list[int]:
        dark = BROW
        tie = "#8b3144"
        tx, ty = self._pal_source_point(151.0, 309.0)
        items = [
            self.canvas.create_polygon(tx - 6, ty - 8, tx + 6, ty - 8, tx + 4, ty + 2, tx - 4, ty + 2, fill=dark, outline=""),
            self.canvas.create_polygon(tx - 5, ty + 1, tx + 5, ty + 1, tx + 8, ty + 27, tx, ty + 36, tx - 8, ty + 27, fill=tie, outline=""),
        ]
        self._register_gentleman_props(items)
        return items

    def _draw_britclip_bow_tie(self) -> list[int]:
        bow = "#8b3144"
        knot = BROW
        tx, ty = self._pal_source_point(151.0, 306.0)
        items = [
            self.canvas.create_polygon(
                tx - 6, ty, tx - 27, ty - 10, tx - 25, ty + 11, tx - 6, ty + 4,
                fill=bow, outline="",
            ),
            self.canvas.create_polygon(
                tx + 6, ty, tx + 27, ty - 10, tx + 25, ty + 11, tx + 6, ty + 4,
                fill=bow, outline="",
            ),
            self.canvas.create_oval(tx - 7, ty - 6, tx + 7, ty + 8, fill=knot, outline=""),
        ]
        self._register_gentleman_props(items)
        return items

    def _draw_gentleman_cane(self) -> list[int]:
        cane = "#5f4540"
        brass = "#9d7a3c"
        cx, cy = self._pal_source_point(305.0, 336.0)
        items = [
            self.canvas.create_line(
                cx + 4,
                cy - 43,
                cx - 13,
                cy - 43,
                cx - 17,
                cy - 31,
                cx - 6,
                cy - 24,
                cx + 5,
                cy - 30,
                fill=cane,
                width=5.0,
                smooth=True,
                splinesteps=12,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            ),
            self.canvas.create_line(cx + 4, cy - 31, cx + 4, cy + 57, fill=cane, width=5.0, capstyle=tk.ROUND),
            self.canvas.create_line(cx - 4, cy + 57, cx + 12, cy + 57, fill=brass, width=3.8, capstyle=tk.ROUND),
        ]
        self._register_gentleman_props(items)
        return items

    def _draw_gentleman_static_props(self) -> list[int]:
        items: list[int] = []
        items.extend(self._draw_gentleman_cane())
        items.extend(self._draw_britclip_bow_tie())
        return items

    def _raise_face_over_costume(self) -> None:
        for tag in ("eye", "pupil", "lid", "brow", "cheek"):
            try:
                self.canvas.tag_raise(tag)
            except tk.TclError:
                pass

    def _prop_items_center(self, items: list[int]) -> tuple[float, float] | None:
        boxes = [self.canvas.bbox(item) for item in items]
        boxes = [box for box in boxes if box]
        if not boxes:
            return None
        return (
            (min(box[0] for box in boxes) + max(box[2] for box in boxes)) / 2,
            (min(box[1] for box in boxes) + max(box[3] for box in boxes)) / 2,
        )

    def _move_prop_items_to(self, items: list[int], cx: float, cy: float) -> None:
        center = self._prop_items_center(items)
        if not center:
            return
        dx = cx - center[0]
        dy = cy - center[1]
        for item in items:
            try:
                self.canvas.move(item, dx, dy)
            except tk.TclError:
                pass

    def _animate_prop_path(
        self,
        items: list[int],
        end: tuple[float, float],
        *,
        control: tuple[float, float] | None = None,
        duration_ms: int = 650,
        delay_ms: int = 0,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        steps = max(1, round(duration_ms / LERP_TICK_MS))
        state: dict[str, tuple[float, float] | None] = {"start": None, "control": control}

        def tick(index: int = 0) -> None:
            if state["start"] is None:
                start = self._prop_items_center(items)
                if not start:
                    return
                state["start"] = start
                if state["control"] is None:
                    state["control"] = ((start[0] + end[0]) / 2, min(start[1], end[1]) - 26)
            start = state["start"]
            path_control = state["control"]
            if start is None or path_control is None:
                return
            if index >= steps:
                self._move_prop_items_to(items, *end)
                if on_done:
                    on_done()
                return
            t = _ease_out_sine((index + 1) / steps)
            inv = 1.0 - t
            x = inv * inv * start[0] + 2 * inv * t * path_control[0] + t * t * end[0]
            y = inv * inv * start[1] + 2 * inv * t * path_control[1] + t * t * end[1]
            self._move_prop_items_to(items, x, y)
            self._prop_anim_after.append(self.root.after(LERP_TICK_MS, lambda: tick(index + 1)))

        if delay_ms > 0:
            self._prop_anim_after.append(self.root.after(delay_ms, tick))
        else:
            tick()

    def _run_prop_body_frames(self, frames: PropFrames) -> None:
        if not frames or self._large_action_running or self._window_move_running:
            return
        start = [self._action_offset[0], self._action_offset[1], self._pal_scale[0], self._pal_scale[1]]
        targets = frames

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(targets):
                self._set_action_offset(0.0, 0.0)
                self._set_pal_scale(1.0, 1.0)
                return
            dx, dy, sx, sy, delay = targets[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                start[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = _smoothstep((si + 1) / n)
            self._set_action_offset(start[0] + (dx - start[0]) * t, start[1] + (dy - start[1]) * t)
            self._set_pal_scale(start[2] + (sx - start[2]) * t, start[3] + (sy - start[3]) * t)
            self._prop_anim_after.append(self.root.after(LERP_TICK_MS, lambda: step(fi, si + 1)))

        step()

    def _draw_decoration(self, definition: DecorationDefinition, lifetime: str = "identity") -> None:
        x, y = self._decoration_anchor(definition)
        color = definition.color
        items: list[int] = []
        shape = definition.shape_type
        paper = "#fffdfd"
        main_w = 3.4
        detail_w = 2.1

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

        if definition.asset:
            asset_path = Path(definition.asset)
            if not asset_path.is_absolute():
                asset_path = self.project_root / asset_path
            items.extend(
                draw_svg_asset(
                    self.canvas,
                    asset_path,
                    x,
                    y,
                    scale=max(0.1, definition.asset_scale),
                    current_color=color,
                )
            )
        elif shape == "terminal_box":
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
        elif shape == "code_badge":
            items.extend([
                card(x, y, x + 30, y + 19, 6, fill="#eefbf5", width=detail_w),
                line(x + 8, y + 7, x + 5, y + 10, x + 8, y + 13, width=detail_w, smooth=True),
                line(x + 22, y + 7, x + 25, y + 10, x + 22, y + 13, width=detail_w, smooth=True),
                line(x + 13, y + 14, x + 18, y + 5, width=detail_w),
            ])
        elif shape == "clipboard":
            items.extend([
                card(x + 2, y + 3, x + 27, y + 34, 5, fill="#f8fff9", width=detail_w),
                _rounded_rect(self.canvas, x + 9, y, x + 20, y + 7, 3, fill=paper, outline=color, width=detail_w),
                line(x + 8, y + 15, x + 11, y + 18, x + 17, y + 11, width=detail_w, smooth=True),
                line(x + 8, y + 26, x + 21, y + 25, width=detail_w),
            ])
        elif shape == "coin":
            items.extend([
                self.canvas.create_oval(x + 1, y + 1, x + 25, y + 25, fill="#f2f7ff", outline=color, width=main_w),
                self.canvas.create_text(x + 13, y + 13, text="$", fill=color, font=("Arial", 12, "bold")),
            ])
        elif shape == "clock":
            items.extend([
                self.canvas.create_oval(x + 1, y + 1, x + 25, y + 25, fill=paper, outline=color, width=main_w),
                line(x + 13, y + 13, x + 13, y + 6, width=detail_w),
                line(x + 13, y + 13, x + 19, y + 16, width=detail_w),
            ])
        elif shape == "moon":
            items.extend([
                self.canvas.create_oval(x + 1, y + 1, x + 25, y + 25, fill="#f7f8ff", outline=color, width=detail_w),
                self.canvas.create_oval(x + 9, y - 1, x + 29, y + 23, fill=TRANSPARENT, outline=""),
                line(x + 20, y + 24, x + 25, y + 27, width=detail_w),
            ])
        elif shape == "sleep_cap":
            cap_fill = "#ECECEC"
            brim_fill = "#F7F7F7"
            angle = math.radians(12)
            pivot = (x + 15, y + 18)

            def rotate(px: float, py: float) -> tuple[float, float]:
                ox, oy = pivot
                dx = px - ox
                dy = py - oy
                return (
                    ox + dx * math.cos(angle) - dy * math.sin(angle),
                    oy + dx * math.sin(angle) + dy * math.cos(angle),
                )

            def rotated_coords(points: list[tuple[float, float]]) -> list[float]:
                coords: list[float] = []
                for px, py in points:
                    rx, ry = rotate(px, py)
                    coords.extend((rx, ry))
                return coords

            brim_left = rotate(x + 2, y + 20)
            brim_right = rotate(x + 27, y + 20)
            pom_x, pom_y = rotate(x + 33, y + 15)
            items.extend([
                self.canvas.create_polygon(
                    *rotated_coords(
                        [
                            (x + 4, y + 18),
                            (x + 13, y + 5),
                            (x + 27, y + 9),
                            (x + 29, y + 17),
                            (x + 23, y + 20),
                        ]
                    ),
                    fill=cap_fill,
                    outline=color,
                    width=main_w,
                    smooth=True,
                    splinesteps=10,
                ),
                line(*brim_left, *brim_right, fill=color, width=main_w + 7),
                line(*brim_left, *brim_right, fill=brim_fill, width=main_w + 2),
                self.canvas.create_oval(pom_x - 5, pom_y - 5, pom_x + 5, pom_y + 5, fill=cap_fill, outline=color, width=main_w),
            ])
        elif shape == "draft_blanket":
            paper_fill = "#fffdfd"
            line_fill = "#d7dee8"
            fold_fill = "#f3f5f8"
            items.extend([
                self.canvas.create_polygon(
                    x + 2,
                    y + 9,
                    x + 37,
                    y + 4,
                    x + 44,
                    y + 36,
                    x + 7,
                    y + 42,
                    fill=paper_fill,
                    outline=color,
                    width=main_w,
                    smooth=True,
                    splinesteps=8,
                ),
                self.canvas.create_polygon(
                    x + 31,
                    y + 5,
                    x + 38,
                    y + 12,
                    x + 34,
                    y + 16,
                    fill=fold_fill,
                    outline=color,
                    width=detail_w,
                ),
                line(x + 9, y + 17, x + 31, y + 14, fill=line_fill, width=detail_w),
                line(x + 10, y + 25, x + 36, y + 22, fill=line_fill, width=detail_w),
                line(x + 12, y + 33, x + 28, y + 31, fill=line_fill, width=detail_w),
            ])
        elif shape == "paper_surfboard":
            paper_fill = "#fff4cf"
            line_fill = "#d7dee8"
            items.extend([
                self.canvas.create_polygon(
                    x + 0, y + 18,
                    x + 24, y + 6,
                    x + 58, y + 7,
                    x + 82, y + 18,
                    x + 58, y + 30,
                    x + 20, y + 28,
                    fill=paper_fill,
                    outline=color,
                    width=main_w,
                    smooth=True,
                    splinesteps=10,
                ),
                line(x + 18, y + 19, x + 62, y + 18, fill=line_fill, width=detail_w),
                line(x + 62, y + 7, x + 66, y + 29, fill="#7cc7e8", width=detail_w),
            ])
        elif shape == "paper_peek_curtain":
            paper_fill = "#fff4cf"
            line_fill = "#d7dee8"
            items.extend([
                self.canvas.create_polygon(x + 0, y + 0, x + 54, y + 2, x + 50, y + 19, x + 3, y + 20, fill=paper_fill, outline=color, width=main_w),
                self.canvas.create_polygon(x + 2, y + 34, x + 52, y + 33, x + 56, y + 62, x + 0, y + 60, fill=paper_fill, outline=color, width=main_w),
                line(x + 8, y + 10, x + 43, y + 9, fill=line_fill, width=detail_w),
                line(x + 8, y + 44, x + 44, y + 43, fill=line_fill, width=detail_w),
                line(x + 9, y + 52, x + 39, y + 51, fill=line_fill, width=detail_w),
            ])
        elif shape == "paper_fan":
            paper_fill = "#fff4cf"
            fold_fill = "#fff9df"
            pivot = (x + 7, y + 29)
            blades = [
                ((x + 6, y + 29), (x + 10, y + 6), (x + 18, y + 27)),
                ((x + 8, y + 29), (x + 24, y + 2), (x + 23, y + 29)),
                ((x + 9, y + 30), (x + 40, y + 5), (x + 29, y + 32)),
                ((x + 9, y + 30), (x + 53, y + 14), (x + 32, y + 35)),
            ]
            for index, blade in enumerate(blades):
                coords = [coord for point in blade for coord in point]
                items.append(self.canvas.create_polygon(*coords, fill=paper_fill if index % 2 else fold_fill, outline=color, width=detail_w))
            for px, py in ((x + 11, y + 7), (x + 24, y + 3), (x + 40, y + 6), (x + 53, y + 15)):
                items.append(line(*pivot, px, py, fill="#d9c783", width=detail_w))
            items.append(self.canvas.create_oval(x + 3, y + 25, x + 12, y + 34, fill="#d9c783", outline=color, width=detail_w))
        elif shape == "paper_whisper_fan":
            paper_fill = "#fff4cf"
            fold_fill = "#fff9df"
            rib = "#d9c783"
            pivot = (x + 30, y + 44)
            blades = [
                ((x + 30, y + 44), (x + 7, y + 29), (x + 15, y + 18), (x + 31, y + 36)),
                ((x + 30, y + 44), (x + 15, y + 18), (x + 31, y + 10), (x + 35, y + 37)),
                ((x + 30, y + 44), (x + 31, y + 10), (x + 48, y + 13), (x + 39, y + 38)),
                ((x + 30, y + 44), (x + 48, y + 13), (x + 61, y + 26), (x + 43, y + 40)),
            ]
            for index, blade in enumerate(blades):
                coords = [coord for point in blade for coord in point]
                items.append(self.canvas.create_polygon(*coords, fill=paper_fill if index % 2 else fold_fill, outline=color, width=detail_w, smooth=True, splinesteps=8))
            items.append(self.canvas.create_arc(x + 5, y + 9, x + 63, y + 62, start=30, extent=126, outline=color, width=main_w, style=tk.ARC))
            for px, py in ((x + 8, y + 29), (x + 16, y + 18), (x + 31, y + 10), (x + 48, y + 13), (x + 61, y + 26)):
                items.append(line(*pivot, px, py, fill=rib, width=detail_w))
            items.extend([
                self.canvas.create_oval(x + 25, y + 39, x + 35, y + 49, fill=rib, outline=color, width=detail_w),
                line(x + 12, y + 30, x + 52, y + 24, fill="#d7dee8", width=1.4, smooth=True),
                line(x + 17, y + 36, x + 47, y + 31, fill="#d7dee8", width=1.4, smooth=True),
            ])
        elif shape == "paper_oops_cover":
            paper_fill = "#fff4cf"
            line_fill = "#d7dee8"
            items.extend([
                self.canvas.create_polygon(
                    x + 3, y + 2,
                    x + 39, y + 0,
                    x + 44, y + 49,
                    x + 0, y + 51,
                    fill=paper_fill,
                    outline=color,
                    width=main_w,
                ),
                line(x + 9, y + 13, x + 35, y + 12, fill=line_fill, width=detail_w),
                line(x + 9, y + 23, x + 36, y + 22, fill=line_fill, width=detail_w),
                line(x + 10, y + 33, x + 32, y + 32, fill=line_fill, width=detail_w),
            ])
        elif shape == "paper_tent":
            paper_fill = "#fff4cf"
            fold_fill = "#fff9df"
            items.extend([
                self.canvas.create_polygon(x + 2, y + 54, x + 28, y + 4, x + 42, y + 54, fill=fold_fill, outline=color, width=main_w),
                self.canvas.create_polygon(x + 28, y + 4, x + 72, y + 18, x + 42, y + 54, fill=paper_fill, outline=color, width=main_w),
                line(x + 28, y + 7, x + 28, y + 48, fill="#d7dee8", width=detail_w),
                line(x + 44, y + 26, x + 63, y + 31, fill="#d7dee8", width=detail_w),
            ])
        elif shape == "paper_pillow":
            paper_fill = "#fff4cf"
            line_fill = "#d7dee8"
            items.extend([
                self.canvas.create_polygon(
                    x + 2, y + 18,
                    x + 19, y + 5,
                    x + 62, y + 7,
                    x + 76, y + 24,
                    x + 57, y + 38,
                    x + 13, y + 36,
                    fill=paper_fill,
                    outline=color,
                    width=main_w,
                    smooth=True,
                    splinesteps=10,
                ),
                line(x + 18, y + 17, x + 58, y + 18, fill=line_fill, width=detail_w),
                line(x + 18, y + 27, x + 54, y + 28, fill=line_fill, width=detail_w),
            ])
        elif shape == "paper_stage":
            paper_fill = "#fff4cf"
            line_fill = "#d7dee8"
            items.extend([
                self.canvas.create_polygon(
                    x + 0, y + 9,
                    x + 86, y + 8,
                    x + 75, y + 32,
                    x + 11, y + 34,
                    fill=paper_fill,
                    outline=color,
                    width=main_w,
                    smooth=True,
                    splinesteps=8,
                ),
                line(x + 11, y + 15, x + 75, y + 14, fill=line_fill, width=detail_w),
                line(x + 42, y + 9, x + 43, y + 33, fill="#e6d090", width=detail_w),
                line(x + 6, y + 34, x + 80, y + 32, width=detail_w),
            ])
        elif shape == "bug_mark":
            items.extend([
                self.canvas.create_oval(x + 8, y + 7, x + 22, y + 23, fill="#fff4f4", outline=color, width=detail_w),
                line(x + 15, y + 6, x + 15, y + 24, width=detail_w),
                line(x + 6, y + 11, x + 1, y + 8, width=detail_w),
                line(x + 6, y + 19, x + 1, y + 22, width=detail_w),
                line(x + 24, y + 11, x + 30, y + 8, width=detail_w),
                line(x + 24, y + 19, x + 30, y + 22, width=detail_w),
            ])
        elif shape == "palette":
            items.extend([
                self.canvas.create_oval(x + 1, y + 3, x + 29, y + 27, fill="#fff7f5", outline=color, width=detail_w),
                self.canvas.create_oval(x + 17, y + 13, x + 25, y + 21, fill=paper, outline=""),
                self.canvas.create_oval(x + 8, y + 10, x + 12, y + 14, fill="#f0b429", outline=""),
                self.canvas.create_oval(x + 14, y + 8, x + 18, y + 12, fill="#4f7ecf", outline=""),
                self.canvas.create_oval(x + 9, y + 17, x + 13, y + 21, fill="#42a96b", outline=""),
            ])
        elif shape == "tab_stack":
            for index, fill in enumerate(("#f9f6ff", "#f2f7ff", "#fffdfd")):
                items.append(card(x + index * 5, y + index * 5, x + 28 + index * 5, y + 16 + index * 5, 5, fill=fill, width=detail_w))
        elif shape == "bandage":
            items.extend([
                _rounded_rect(self.canvas, x, y + 7, x + 35, y + 21, 7, fill="#fff7f5", outline=color, width=detail_w),
                line(x + 10, y + 9, x + 18, y + 19, width=detail_w),
                line(x + 18, y + 9, x + 10, y + 19, width=detail_w),
                self.canvas.create_oval(x + 25, y + 13, x + 28, y + 16, fill=color, outline=""),
            ])

        if items:
            decoration_scale = 1.0 if definition.asset else (1.58 if shape == "sleep_cap" else DECORATION_SCALE)
            if decoration_scale != 1.0:
                for item in items:
                    self.canvas.scale(item, x, y, decoration_scale, decoration_scale)
            self._apply_actor_transform_to_items(items)
            for item in items:
                self.canvas.addtag_withtag("decoration", item)
                if shape == "sleep_cap":
                    self.canvas.addtag_withtag("under_brow_decoration", item)
            self._decoration_items.setdefault(lifetime, []).extend(items)
            self.canvas.tag_raise("decoration")
            self._animate_decoration_entrance(items, pulse=definition.pulse)
            if self.canvas.find_withtag("under_brow_decoration"):
                self.canvas.tag_lower("under_brow_decoration", "brow")
                self.canvas.tag_raise("brow")

    def _animate_decoration_entrance(self, items: list[int], *, pulse: bool = False) -> None:
        bbox = self.canvas.bbox(*items)
        if not bbox:
            return
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        current = [0.72]
        for item in items:
            self.canvas.scale(item, cx, cy, current[0], current[0])
        frames = ((1.16, 46), (0.96, 58), (1.04, 64), (1.0, 72))

        def step(index: int = 0) -> None:
            if index >= len(frames):
                if pulse:
                    self._animate_decoration_pulse(items, loops=3)
                return
            target, delay = frames[index]
            bbox_now = self.canvas.bbox(*items)
            if not bbox_now:
                return
            center_x = (bbox_now[0] + bbox_now[2]) / 2
            center_y = (bbox_now[1] + bbox_now[3]) / 2
            factor = target / current[0]
            for item_id in items:
                try:
                    self.canvas.scale(item_id, center_x, center_y, factor, factor)
                except tk.TclError:
                    return
            current[0] = target
            self._schedule_decoration_animation(delay, lambda: step(index + 1))

        step()

    def _animate_decoration_pulse(self, items: list[int], *, loops: int = 2) -> None:
        total = max(1, loops * 14)
        current = [1.0]

        def step(index: int = 0) -> None:
            if index >= total:
                return
            bbox = self.canvas.bbox(*items)
            if not bbox:
                return
            target = 1.0 + math.sin(index / total * loops * math.tau) * 0.055
            factor = target / current[0]
            cx = (bbox[0] + bbox[2]) / 2
            cy = (bbox[1] + bbox[3]) / 2
            for item_id in items:
                try:
                    self.canvas.scale(item_id, cx, cy, factor, factor)
                except tk.TclError:
                    return
            current[0] = target
            self._schedule_decoration_animation(42, lambda: step(index + 1))

        step()

    def _schedule_decoration_animation(self, delay_ms: int, callback: Callable[[], None]) -> None:
        holder: list[str] = []

        def fire() -> None:
            if holder and holder[0] in self._decoration_anim_after:
                self._decoration_anim_after.remove(holder[0])
            callback()

        after_id = self.root.after(max(0, delay_ms), fire)
        holder.append(after_id)
        self._decoration_anim_after.append(after_id)

    def _apply_actor_transform_to_items(self, items: list[int]) -> None:
        sx, sy = self._pal_scale
        if sx != 1.0 or sy != 1.0:
            for item in items:
                self.canvas.scale(item, PAL_CENTER_X, PAL_SCALE_PIVOT_Y, sx, sy)
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
        self.canvas.scale("pal", PAL_CENTER_X, PAL_SCALE_PIVOT_Y, sx, sy)
        self.canvas.scale("decoration", PAL_CENTER_X, PAL_SCALE_PIVOT_Y, sx, sy)

    def _actor_point(self, x: float, y: float) -> tuple[float, float]:
        lean, hunch = self._body_bend
        if lean or hunch:
            x, y = bend_point(x, y, lean, hunch, pivot_y=PAL_SCALE_PIVOT_Y, top_y=PAL_PAD_Y)
        sx, sy = self._pal_scale
        actor_dx = self._action_offset[0] + self._bob_x
        actor_dy = self._action_offset[1] + self._bob_y
        return (
            PAL_CENTER_X + (x - PAL_CENTER_X) * sx + actor_dx,
            PAL_SCALE_PIVOT_Y + (y - PAL_SCALE_PIVOT_Y) * sy + actor_dy,
        )

    def _actor_coords(self, coords: tuple[float, ...] | list[float]) -> list[float]:
        transformed: list[float] = []
        for index in range(0, len(coords), 2):
            x, y = self._actor_point(coords[index], coords[index + 1])
            transformed.extend((x, y))
        return transformed

    def _actor_oval_bounds(
        self,
        bounds: tuple[float, float, float, float],
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        rx_scale: float = 1.0,
        ry_scale: float = 1.0,
    ) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = bounds
        cx = (x1 + x2) / 2 + dx
        cy = (y1 + y2) / 2 + dy
        sx, sy = self._pal_scale
        tx, ty = self._actor_point(cx, cy)
        rx = (x2 - x1) / 2 * sx * rx_scale
        ry = (y2 - y1) / 2 * sy * ry_scale
        return tx - rx, ty - ry, tx + rx, ty + ry

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
        return not self._interruptibility().allow_speech

    def _interruptibility(self, world: WorldState | None = None) -> Interruptibility:
        activity = world.user_activity if world else self.ears.sample()
        return assess_interruptibility(
            activity,
            focus_mode=bool(self._focus_var.get()),
            quiet_remaining_seconds=self._quiet_remaining_seconds(),
        )

    def _quiet_remaining_seconds(self) -> float:
        return max(0.0, self._quiet_until - time.time())

    def _activity_policy(self) -> ActivityPolicy:
        return policy_for_frequency(self._freq_var.get())

    def _adaptive_poll_ms(self, base_ms: int) -> int:
        """Double poll interval when user is away to save resources."""
        try:
            if self._care_engine.state.was_away:
                return min(base_ms * 3, 300_000)
        except AttributeError:
            pass
        return base_ms

    def _load_frequency_setting(self) -> str:
        data = self._load_settings()
        key = str(data.get("frequency") or FREQUENCY_DEFAULT)
        valid = {label for label, _mult in FREQUENCY_PRESETS}
        return key if key in valid else FREQUENCY_DEFAULT

    def _save_frequency_setting(self, key: str) -> None:
        self._save_setting("frequency", key)

    def _save_language_setting(self, language: str) -> None:
        self._save_setting("language", normalize_language(language))

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

    def _save_stats(self) -> None:
        try:
            save_stats(self.pal_stats, self.project_root / "memory" / "stats.json")
        except Exception:
            pass

    def _schedule_micro(self) -> None:
        interval = self.mood.micro_interval_ms()
        self._micro_after = self.root.after(interval, self._micro_tick)

    def _micro_tick(self) -> None:
        self._micro_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            interruptibility = self._interruptibility()
            if not interruptibility.allow_speech:
                if interruptibility.allow_animation and random.random() < 0.18:
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
            interruptibility = self._interruptibility()
            if not interruptibility.allow_speech:
                if interruptibility.allow_animation and random.random() < 0.28:
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
                self._ask_brain("ambient", allow_live=False)
        self._schedule_companion()

    # ── daily greeting ──────────────────────────────────────────────

    def _check_daily_greeting(self) -> None:
        today_str = date.today().isoformat()
        settings = self._load_settings()
        last_seen = str(settings.get("last_seen_date") or "")
        self._save_setting("last_seen_date", today_str)
        result = self._care_engine.daily_greeting(last_seen, today_str)
        if result:
            line, mood, action = result
            self._say_care_line(line, mood=mood, action=action, event="daily_greeting")

    # ── proactive care (delegated to CareEngine) ───────────────────

    _CARE_TICK_MS = 60_000

    def _schedule_care(self) -> None:
        self._care_after = self.root.after(self._CARE_TICK_MS, self._care_tick)

    def _care_tick(self) -> None:
        self._care_after = None
        try:
            self._update_care_state()
        except Exception:
            pass
        self._schedule_care()

    def _update_care_state(self) -> None:
        now = time.time()
        cs = self._care_engine.state
        context = self.ears.sample()
        is_active = context.activity_level == "active"
        is_away = context.activity_level == "away"
        busy = bool(self._bubble_items or self.state.brain_busy)

        if is_away:
            if not cs.was_away:
                cs.last_away_at = now
                cs.was_away = True
            cs.continuous_work_start = now
            cs.care_3h_announced = False
            return

        if cs.was_away and is_active:
            away_duration = now - cs.last_away_at if cs.last_away_at else 0
            cs.was_away = False
            cs.continuous_work_start = now
            cs.care_3h_announced = False
            if away_duration >= 300 and now - cs.care_welcome_back_announced_at > 1800 and not busy:
                cs.care_welcome_back_announced_at = now
                self._say_care_line(self._care_engine.welcome_back_line(), mood="innocent", action="happy_bounce", event="care_welcome_back")
                return

        work_seconds = now - cs.continuous_work_start
        if work_seconds >= 10800 and not cs.care_3h_announced and not busy:
            cs.care_3h_announced = True
            self._say_care_line(self._care_engine.care_3h_line(), mood="innocent", action="nod", event="care_3h_work")
            return

        hour = datetime.now().hour
        if (hour >= 23 or hour < 5) and not cs.care_late_night_announced and is_active and not busy:
            cs.care_late_night_announced = True
            self._say_care_line(self._care_engine.late_night_line(), mood="sleepy", action="sleepy_sag", event="care_late_night")
            return

        if 6 <= hour <= 8:
            cs.care_late_night_announced = False

        # achievement tracking
        focus_secs = context.focus_seconds
        if focus_secs > cs.session_max_focus_seconds:
            cs.session_max_focus_seconds = focus_secs
        switches = context.window_switches_per_minute
        cs.session_window_switches = max(cs.session_window_switches, switches)

        if cs.session_max_focus_seconds >= 7200 and not cs.achievement_2h_focus_announced and not busy:
            cs.achievement_2h_focus_announced = True
            self._say_care_line(self._care_engine.focus_2h_line(), mood="smirk", action="celebrate", event="achievement_2h_focus")
            return

        if cs.session_window_switches >= 12 and not cs.achievement_rapid_switch_announced and not busy:
            cs.achievement_rapid_switch_announced = True
            self._say_care_line(self._care_engine.rapid_switch_line(), mood="suspicious", action="startled_pop", event="achievement_rapid_switch")
            return

    def _say_care_line(self, line: str, mood: str = "innocent", action: str = "nod", event: str = "care") -> None:
        reaction = Reaction(should_say=True, line=line, mood=mood, action=action, bubble="speech", event=event)
        self._apply_reaction(reaction)

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
        cue = ACTION_PROP_CUES.get(action)
        if cue and cue.get("held") and cue.get("tail_style") == "wag":
            return prop_cue_duration_ms(action) + 160
        osc = TAIL_OSCILLATIONS.get(action)
        if osc:
            return round(float(osc["cycles"]) / float(osc["freq"]) * 1000) + 160
        posture = TAIL_POSTURES.get(action)
        if posture:
            return round((_POSTURE_ENTER_S + _POSTURE_EXIT_S) * 1000) + int(posture["hold_ms"]) + 180
        tail_frames = TAIL_MOTION_FRAMES.get(action)
        if tail_frames:
            return sum(frame[-1] for frame in tail_frames) + 140
        inner_frames = INNER_GESTURE_FRAMES.get(action)
        if inner_frames:
            return sum(frame[-1] for frame in inner_frames) + 130
        if action == "oops_innocent_combo":
            return 1500
        if action in {"britclip_enter", "british_gentleman_suit_up"}:
            return 3200
        if action == "britclip_exit":
            return 2300
        if action == "hat_tip_oops":
            return 950
        if action == "scan":
            return SCAN_LOOK_HOLD_MS * len(SCAN_LOOK_TARGETS)
        if action == "wiggle":
            return sum(f[2] for f in WIGGLE_FRAMES)
        if action == "blink":
            return 150
        if action in MOVE_IDLE_ACTIONS:
            return MOVE_ACTION_DURATIONS.get(action, 760)
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
        self._apply_reaction(reaction, force=True)

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
        self._drag_prev = None
        self._cancel_bend(reset=False)
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
            # dangle physics: the body trails behind the drag direction like
            # something held from above, proportional to pointer velocity
            now = time.monotonic()
            if self._drag_prev is not None:
                prev_x, prev_t = self._drag_prev
                dt = max(1e-3, now - prev_t)
                velocity_x = (x_root - prev_x) / dt
                target_lean = _clamp(-velocity_x * 0.022, -16.0, 16.0)
                lean = self._body_bend[0] + (target_lean - self._body_bend[0]) * 0.35
                self._set_body_bend(lean, self._body_bend[1] * 0.8)
            self._drag_prev = (x_root, now)
            # periodic drag struggle
            if self._anim_tick % 9 == 0:
                self._drag_struggle()

    def _finish_drag(self) -> None:
        if self._drag_start is None:
            return
        if not self._dragging:
            self._poke()
        else:
            self._start_mouse_follow(1300, force=True)
            self._settle_drag_lean()
        self._drag_start = None
        self._drag_origin = None
        self._dragging = False
        self._drag_prev = None

    def _settle_drag_lean(self) -> None:
        """Pendulum settle after a drag: overshoot once, rebound, come to rest."""
        lean = self._body_bend[0]
        self._cancel_bend(reset=False)
        if abs(lean) < 0.6:
            self._bend_transition_to(BODY_BEND_NEUTRAL, 160)
            return
        self._bend_transition_to(
            (-lean * 0.45, 0.0),
            170,
            lambda: self._bend_transition_to(
                (lean * 0.18, 0.0),
                190,
                lambda: self._bend_transition_to(BODY_BEND_NEUTRAL, 230),
            ),
        )

    _POKE_ESCALATION = [
        (1, "poke"),
        (3, "poke"),        # normal poke for first 3
        (5, "repeated_poke"),  # escalate at 5+
        (8, "poke_meltdown"),  # full meltdown at 8+
    ]

    def _poke(self, force: bool = False) -> None:
        now = time.time()
        if now - self._last_poke_at < 8:
            self._poke_count += 1
        else:
            self._poke_count = 1
        self._last_poke_at = now

        # escalation: different event names trigger different lines
        event = "poke"
        if self._poke_count >= 8:
            event = "poke"
            self._emit_particles("sweat")
            self._perform_action("melt")
        elif self._poke_count >= 5:
            event = "poke"
            self._emit_particles("exclaim")
            self._wiggle()
        elif self._poke_count >= 3:
            self._wiggle()
            self._emit_particles("sparkle")
        else:
            self._wiggle()

        self._start_mouse_follow(1600, force=True)
        new_achievements = self.pal_stats.record_poke(self._poke_count)
        self._save_stats()
        if force or self.state.can_speak(4):
            self._ask_brain(event)

    def _ask_cheesy_love(self) -> None:
        self._ask_brain("bored", allow_live=False, extra_tags=("cheesy_love",))

    def _ask_brain(
        self,
        event: str,
        world: WorldState | None = None,
        allow_live: bool = True,
        extra_tags: tuple[str, ...] = (),
    ) -> None:
        if self.state.brain_busy:
            self._perform_action("thinking_tilt")
            return
        self.state.brain_busy = True
        context = self._context(event, world)
        if extra_tags:
            tags = list(context.get("environment_tags") or [])
            tags.extend(extra_tags)
            context["environment_tags"] = sorted(set(str(tag) for tag in tags if str(tag)))
        self._start_brain_wait_animation()

        def worker() -> None:
            reaction = self.brain.react(event, context, allow_live=allow_live)
            reaction.event = "cheesy_love" if "cheesy_love" in extra_tags else event
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
            claude_usage=self._last_claude_usage_status,
            claude_account_usage=self._last_claude_account_usage_status,
            openai_billing=self._last_openai_billing_status,
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
        world_state = world or self._world_state()
        context = world_state.as_context(event)
        identity_id = self._identity_var.get()
        if identity_id and identity_id != "auto":
            context["identity_id"] = identity_id
        focus_mode = bool(self._focus_var.get())
        quiet_remaining = self._quiet_remaining_seconds()
        policy = self._activity_policy()
        interruptibility = self._interruptibility(world_state)
        context["pal_focus_mode"] = focus_mode
        context["pal_quiet_remaining_seconds"] = round(quiet_remaining, 1)
        context["poke_count"] = self._poke_count
        context["recent_lines"] = self.state.recent_lines[-5:]
        context["activity_tier"] = policy.tier
        context["activity_alert_threshold"] = policy.alert_threshold
        context["alive"] = self.alive.as_context()
        context.update(interruptibility.as_context())
        if focus_mode or quiet_remaining > 0:
            tags = list(context.get("environment_tags") or [])
            tags.append("focus_mode" if focus_mode else "quiet_mode")
            context["environment_tags"] = sorted(set(str(tag) for tag in tags if str(tag)))
        else:
            tags = list(context.get("environment_tags") or [])
            tags.append(f"activity_{policy.tier}")
            if not interruptibility.allow_speech:
                tags.append(f"interrupt_{interruptibility.mode}")
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
        try:
            while True:
                reaction = self.status_queue.get_nowait()
                self._apply_reaction(reaction)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_brain)

    def _start_brain_wait_animation(self) -> None:
        self._stop_brain_wait_animation()
        self._brain_wait_step = 0
        self._apply_alive_cue(self.alive.observe_wait("brain"))
        self._brain_wait_after = self.root.after(80, self._brain_wait_tick)

    def _stop_brain_wait_animation(self) -> None:
        if self._brain_wait_after:
            self.root.after_cancel(self._brain_wait_after)
            self._brain_wait_after = None

    def _start_chat_wait_feedback(self) -> None:
        self._stop_chat_wait_feedback(clear_bubble=False)
        self._chat_wait_step = 0
        self._chat_wait_started_at = time.time()
        self._apply_alive_cue(self.alive.observe_wait("chat"))
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
            self.root.after(LINE_BANK_BUSY_RETRY_MS, self._maintain_line_bank)
            return

        def worker() -> None:
            try:
                self.brain.maintain_line_bank(target_count=36)
            except Exception:
                return

        self._line_bank_thread = threading.Thread(target=worker, daemon=True)
        self._line_bank_thread.start()
        self.root.after(LINE_BANK_REFRESH_MS, self._maintain_line_bank)

    def _refresh_eyes(self) -> None:
        if self._vision_thread and self._vision_thread.is_alive():
            self.root.after(VISION_BUSY_RETRY_MS, self._refresh_eyes)
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
        self.root.after(self._adaptive_poll_ms(CODEX_STATUS_POLL_MS), self._poll_codex_status)

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
        self.root.after(self._adaptive_poll_ms(CODEX_USAGE_POLL_MS), self._poll_codex_usage)

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
        self._apply_reaction(_codex_usage_reaction(status, manual=True), force=True)

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
        self.root.after(self._adaptive_poll_ms(CLAUDE_STATUS_POLL_MS), self._poll_claude_status)

    def _poll_claude_usage(self) -> None:
        self._last_claude_usage_status = self.claude_usage.sample()
        self.root.after(self._adaptive_poll_ms(CLAUDE_USAGE_POLL_MS), self._poll_claude_usage)

    def _show_claude_usage(self) -> None:
        status = self.claude_usage.sample()
        self._last_claude_usage_status = status
        self._apply_reaction(_claude_usage_reaction(status, manual=True), force=True)

    def _poll_claude_account_usage(self) -> None:
        status = self.claude_account_usage.sample()
        self._last_claude_account_usage_status = status
        if self._should_log_claude_account_usage(status):
            self._logged_claude_account_usage_event = status.event_id
            self._log_event("claude_account_usage", status.level, _usage_event_level(status.level), status.summary_line)
        if self._should_announce_claude_account_usage(status):
            self._last_claude_account_usage_event = status.event_id
            self._last_claude_account_usage_announcement_at = time.time()
            self._apply_reaction(_claude_account_usage_reaction(status))
        self.root.after(self._adaptive_poll_ms(CLAUDE_ACCOUNT_USAGE_POLL_MS), self._poll_claude_account_usage)

    def _should_log_claude_account_usage(self, status: ClaudeAccountUsageStatus) -> bool:
        if status.level in {"unavailable", "normal"} or status.stale:
            return False
        return bool(status.event_id and status.event_id != self._logged_claude_account_usage_event)

    def _should_announce_claude_account_usage(self, status: ClaudeAccountUsageStatus) -> bool:
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
        is_new_event = bool(status.event_id and status.event_id != self._last_claude_account_usage_event)
        if is_new_event and self._last_claude_account_usage_announcement_at <= 0:
            return self.state.can_speak(8)
        if status.level == "watch":
            return is_new_event and self.state.can_speak(cooldown)
        if status.level in {"reset_soon", "refilled"}:
            return is_new_event and self.state.can_speak(8)
        if status.level in {"low", "critical"}:
            return self.state.can_speak(cooldown) and time.time() - self._last_claude_account_usage_announcement_at >= cooldown
        return False

    def _show_claude_account_usage(self) -> None:
        status = self.claude_account_usage.sample()
        self._last_claude_account_usage_status = status
        self._apply_reaction(_claude_account_usage_reaction(status, manual=True), force=True)

    def _poll_openai_billing(self) -> None:
        self._start_openai_billing_sample(manual=False)
        self.root.after(self._adaptive_poll_ms(OPENAI_BILLING_POLL_MS), self._poll_openai_billing)

    def _start_openai_billing_sample(self, manual: bool) -> None:
        if self._openai_billing_thread and self._openai_billing_thread.is_alive():
            if manual:
                self.show_bubble("OpenAI API 账本正在翻页。它不是慢，是在保持财务尊严。", milliseconds=4200, kind="usage_thought")
            return
        if manual:
            self.show_bubble("我去查 OpenAI API 账本。小文具翻账，本质上很严肃。", milliseconds=3600, kind="usage_thought")
            self._perform_action("thinking_tilt")

        def worker() -> None:
            status = self.openai_billing.sample()
            self._last_openai_billing_status = status
            if manual:
                reaction = _openai_billing_reaction(status, manual=True)
                reaction.event = f"manual_{reaction.event or 'openai_billing'}"
                self.status_queue.put(reaction)
                return
            if self._should_announce_openai_billing(status):
                self._last_openai_billing_event = status.event_id
                self._last_openai_billing_announcement_at = time.time()
                self.status_queue.put(_openai_billing_reaction(status))

        self._openai_billing_thread = threading.Thread(target=worker, daemon=True)
        self._openai_billing_thread.start()

    def _should_announce_openai_billing(self, status: OpenAIBillingStatus) -> bool:
        if self._auto_reactions_paused():
            return False
        if status.level not in {"low", "over_budget"}:
            return False
        if self.state.brain_busy or self._bubble_items:
            return False
        if not status.event_id or status.event_id == self._last_openai_billing_event:
            return False
        cooldown = 6 * 60 * 60 if status.level == "low" else 2 * 60 * 60
        return self.state.can_speak(cooldown) and time.time() - self._last_openai_billing_announcement_at >= cooldown

    def _show_openai_billing(self) -> None:
        self._start_openai_billing_sample(manual=True)

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
        self.root.after(self._adaptive_poll_ms(HARDWARE_STATUS_POLL_MS), self._poll_hardware_status)

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
        self._apply_reaction(_hardware_status_reaction(snapshot, manual=True), force=True)

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
        for lid in self._lid_items:
            try:
                self.canvas.itemconfigure(lid, fill=fill)
            except tk.TclError:
                pass

    def _set_codex_usage_badge(self, status: CodexUsageStatus) -> None:
        self._clear_codex_usage_badge()
        if status.level not in {"watch", "low", "critical", "reset_soon"}:
            return
        percent = status.usage_remaining_percent
        if percent is None:
            return
        color = CODEX_USAGE_COLORS.get(status.level, CODEX_USAGE_COLORS["watch"])
        width, height = USAGE_BADGE_WIDTH, USAGE_BADGE_HEIGHT
        x = (self.width - width) / 2
        y = self.height - height - USAGE_BADGE_BOTTOM_GAP
        fill_width = max(6, round((width - 12) * percent / 100))
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
                    x + 6,
                    y + 20,
                    x + 6 + fill_width,
                    y + 26,
                    fill=color,
                    outline="",
                ),
                self.canvas.create_rectangle(
                    x + 6,
                    y + 20,
                    x + width - 6,
                    y + 26,
                    fill="",
                    outline="#d7e2f4",
                    width=1,
                ),
                self.canvas.create_text(
                    x + 8,
                    y + 10,
                    anchor="w",
                    text=f"CODEX {percent:.0f}%",
                    fill="#20304f",
                    font=("Microsoft YaHei UI", 8, "bold"),
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
        badge_radius = 10
        badge_step = 25
        start_x = self.width - 17
        y = 21
        for index, badge_id in enumerate(badge_ids[:6]):
            label, fill, shape = STATUS_BADGES[badge_id]
            cx = start_x - index * badge_step
            if shape == "triangle":
                item = self.canvas.create_polygon(
                    cx,
                    y - badge_radius,
                    cx - badge_radius - 1,
                    y + badge_radius,
                    cx + badge_radius + 1,
                    y + badge_radius,
                    fill=fill,
                    outline="#ffffff",
                    width=1,
                    tags=("status_badge", "status_badge_shape"),
                )
            else:
                item = self.canvas.create_oval(
                    cx - badge_radius,
                    y - badge_radius,
                    cx + badge_radius,
                    y + badge_radius,
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
                font=("Microsoft YaHei UI", 8, "bold"),
                tags=("status_badge",),
            )
            self._status_badge_items.extend([item, text])
        self._pulse_status_badges()

    def _status_badge_ids(self) -> list[str]:
        badges: list[str] = []
        interruptibility = self._interruptibility()
        if not interruptibility.allow_badges:
            return badges
        if self._focus_var.get() or self._quiet_remaining_seconds() > 0:
            badges.append("focus_mode")
        elif interruptibility.mode != "open":
            badges.append("do_not_disturb")
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
        self._apply_reaction(reaction, force=True)

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
        remaining_ms = max(0, round((self._visual_state_until - time.time()) * 1000))
        pending = self._pending_visual_reaction[0].event if self._pending_visual_reaction else "none"
        gate = (
            "visual gate:\n"
            f"active: {self._visual_state_name}\n"
            f"lifecycle: {self._visual_state_lifecycle}\n"
            f"priority: {self._visual_state_priority}\n"
            f"interruptible: {self._visual_state_interruptible}\n"
            f"remaining_ms: {remaining_ms}\n"
            f"pending: {pending}"
        )
        appearance = (
            "appearance:\n"
            f"costume: {self.appearance.costume_id or 'none'}\n"
            f"phase: {self.appearance.phase}\n"
            f"language: {self.appearance.language_mode}"
        )
        text = f"{self._last_animation_debug}\n\n{gate}\n\n{appearance}\n\nidle scheduler:\n{self._last_idle_animation_debug}"
        self.show_bubble(text, milliseconds=9000, kind="thought")

    def _show_alive_debug(self) -> None:
        self.show_bubble(self._last_alive_debug, milliseconds=9000, kind="thought")

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

    def _resolve_visual_state_plan(self, reaction: Reaction) -> VisualStatePlan:
        manifest = self.animation_player.manifest
        action = _anim_key(reaction.action) or "blink"
        state = manifest.state_for_reaction(reaction.mood, action, reaction.bubble)
        agent_key = self._agent_visual_key_for_reaction(reaction)
        agent_visual = manifest.agent_visual(agent_key) if agent_key else None
        if agent_visual and state == "idle":
            state = agent_key
        performance = (
            _anim_key(reaction.performance)
            or manifest.performance_for_state(state)
            or phrase_for_reaction(reaction.mood, action, reaction.bubble)
        )
        source = "reaction"

        if agent_visual and not reaction.performance:
            resolved = self.animation_resolver.resolve(agent_visual.animation, fallback=performance or action)
            if resolved.performance and (not performance or performance not in manifest.performances):
                performance = resolved.performance
                source = f"agent:{agent_key}"
            elif resolved.action and action in {"", "idle", "blink"}:
                action = resolved.action
                source = f"agent:{agent_key}"

        logical_state = manifest.states.get(_anim_key(state))
        definition = manifest.performance(performance) if performance else None
        lifecycle = (
            (definition.lifecycle if definition else "")
            or (logical_state.lifecycle if logical_state else "")
            or "oneshot_return"
        )
        minimum_ms = max(
            definition.minimum_ms if definition else 0,
            logical_state.minimum_ms if logical_state else 0,
            agent_visual.minimum_ms if agent_visual else 0,
            self._estimated_visual_duration_ms(performance, action),
        )
        priority = max(
            logical_state.priority if logical_state else 0,
            agent_visual.priority if agent_visual else 0,
            _reaction_visual_priority(reaction),
        )
        interruptible = True
        if logical_state and not logical_state.interruptible:
            interruptible = False
        if agent_visual and not agent_visual.interruptible:
            interruptible = False
        if lifecycle == "transition_to_state":
            interruptible = False

        return VisualStatePlan(
            state=state,
            performance=performance,
            action=action,
            lifecycle=lifecycle,
            minimum_ms=minimum_ms,
            priority=priority,
            interruptible=interruptible,
            source=source,
        )

    def _estimated_visual_duration_ms(self, performance: str, action: str) -> int:
        definition = self.animation_player.manifest.performance(performance) if performance else None
        if definition:
            elapsed = 0
            for step in definition.sequence:
                if step.pause_ms:
                    elapsed += step.pause_ms
                    continue
                scheduled = bool(step.action or step.eyes or step.brows or step.bubble or step.reset)
                if scheduled or step.duration_ms:
                    elapsed += step.duration_ms
            return elapsed
        return self._animation_duration_ms(action)

    def _agent_visual_key_for_reaction(self, reaction: Reaction) -> str:
        event = (reaction.event or "").lower()
        for prefix in ("codex_", "claude_"):
            if event.startswith(prefix):
                return _agent_visual_key(event.removeprefix(prefix))
        if event.startswith("chat_codex_"):
            return _agent_visual_key(event.removeprefix("chat_codex_"))
        if event.startswith("chat_claude_"):
            return _agent_visual_key(event.removeprefix("chat_claude_"))
        return ""

    def _should_defer_visual_reaction(self, reaction: Reaction, plan: VisualStatePlan, force: bool) -> bool:
        if force or _is_direct_reaction(reaction):
            return False
        now = time.time()
        if now >= self._visual_state_until:
            return False
        if plan.priority > self._visual_state_priority and (self._visual_state_interruptible or plan.priority >= 50):
            return False
        self._queue_pending_visual_reaction(reaction, force, plan)
        remaining_ms = max(0, round((self._visual_state_until - now) * 1000))
        self._last_animation_debug = (
            f"event: {reaction.event or 'unknown'}\n"
            f"state: {plan.state}\n"
            f"performance: {plan.performance or 'none'}\n"
            f"lifecycle: {plan.lifecycle}\n"
            f"source: deferred:{plan.source}\n"
            f"priority: {plan.priority} <= active {self._visual_state_priority}\n"
            f"wait_ms: {remaining_ms}\n"
            f"active_state: {self._visual_state_name}\n"
            f"active_interruptible: {self._visual_state_interruptible}"
        )
        return True

    def _queue_pending_visual_reaction(self, reaction: Reaction, force: bool, plan: VisualStatePlan) -> None:
        if self._pending_visual_reaction:
            _old_reaction, _old_force, old_plan = self._pending_visual_reaction
            if old_plan.priority > plan.priority:
                return
        self._pending_visual_reaction = (reaction, force, plan)
        self._ensure_visual_state_release_timer()

    def _mark_visual_state(self, plan: VisualStatePlan) -> None:
        now = time.time()
        hold_ms = max(0, plan.minimum_ms)
        self._visual_state_name = plan.state or "idle"
        self._visual_state_until = now + hold_ms / 1000
        self._visual_state_priority = plan.priority
        self._visual_state_interruptible = plan.interruptible
        self._visual_state_lifecycle = plan.lifecycle
        self._ensure_visual_state_release_timer()

    def _ensure_visual_state_release_timer(self) -> None:
        if self._visual_state_after:
            try:
                self.root.after_cancel(self._visual_state_after)
            except tk.TclError:
                pass
            self._visual_state_after = None
        delay_ms = max(0, round((self._visual_state_until - time.time()) * 1000)) + 20
        self._visual_state_after = self.root.after(delay_ms, self._release_visual_state)

    def _release_visual_state(self) -> None:
        self._visual_state_after = None
        if time.time() < self._visual_state_until:
            self._ensure_visual_state_release_timer()
            return
        self._visual_state_priority = 0
        self._visual_state_interruptible = True
        self._visual_state_lifecycle = "loop"
        pending = self._pending_visual_reaction
        self._pending_visual_reaction = None
        if pending:
            reaction, force, _plan = pending
            self._apply_reaction(reaction, force=force)

    # (eye_style, brow_style, show_cheek_blush)
    _MOOD_EXPRESSION: dict[str, tuple[str, str, bool]] = {
        "smirk": ("smug_half", "smug_arch", False),
        "smug": ("side_eye", "smug_arch", True),
        "suspicious": ("suspicious_slit", "skeptical", False),
        "guilty": ("guilty_round", "guilty", True),
        "innocent": ("innocent_round", "innocent", True),
        "startled": ("startled_dot", "panic", False),
        "sleepy": ("sleepy_slit", "droop", False),
        "focused": ("narrow", "flat", False),
        "sulky": ("peek_up", "sulk", False),
        "thinking": ("curious", "curious", False),
        "happy": ("sparkle", "innocent", True),
        "proud": ("round", "smug_arch", True),
        "done": ("round", "laugh", True),
        "excited": ("sparkle", "innocent", True),
        "shy": ("soft", "guilty", True),
        "annoyed": ("narrow", "angry", False),
        "worried": ("worried_wide", "worried", False),
        "playful": ("curious", "smug_arch", True),
    }

    def _apply_reaction(self, reaction: Reaction, force: bool = False) -> None:
        plan = self._resolve_visual_state_plan(reaction)
        if self._should_defer_visual_reaction(reaction, plan, force):
            return
        self._pending_visual_reaction = None

        self._cancel_performance_phrase()
        self._cancel_alive_after()
        self.state.mood = reaction.mood
        self.mood.push_mood(reaction.mood)
        self.pal_stats.record_reaction()
        if reaction.line:
            is_roast = reaction.mood in {"smirk", "smug", "suspicious"}
            self.pal_stats.record_line(is_roast=is_roast)
        state = plan.state
        performance = plan.performance
        self._mark_visual_state(plan)
        alive_cue = self.alive.observe_reaction(reaction, performance=performance, state=state)
        # apply mood-based expression
        expr = self._MOOD_EXPRESSION.get(reaction.mood)
        if expr:
            self._transition_expression(expr[0], expr[1], hold_ms=2400)
            self._set_cheek_blush(expr[2] if len(expr) > 2 else False)
        # chin mode follows mood — hand/mouth dual mapping
        if reaction.mood in ("guilty", "shy"):
            self.set_chin_mode("cover")
        elif reaction.mood in ("thinking",):
            self.set_chin_mode("think")
        elif reaction.mood in ("sulky", "bored"):
            self.set_chin_mode("sulk")
        elif reaction.mood in ("sleepy",):
            self.set_chin_mode("yawn")
        elif reaction.mood in ("nervous", "worried"):
            self.set_chin_mode("fidget")
        elif reaction.mood in ("happy", "excited"):
            self._run_inner_gesture("inner_wave")
        elif reaction.mood in ("smug", "proud"):
            self._run_inner_gesture("inner_thumbs_up")
        elif reaction.mood in ("frustrated", "annoyed"):
            self._run_inner_gesture("inner_facepalm")
        self._apply_alive_cue(alive_cue)
        self._refresh_identity_decorations(reaction)
        self._maybe_show_reaction_decoration(reaction)
        self._maybe_flash_hardware_tint(reaction)
        self._refresh_status_badges()
        self._log_event(
            "pal",
            reaction.event or "reaction",
            _reaction_event_level(reaction),
            reaction.line,
            performance or reaction.action,
        )
        if performance and reaction.should_say and reaction.line:
            self._maybe_emit_particles(reaction.mood, reaction.action)
            self._run_performance_phrase(performance, reaction, state)
            return
        self._last_animation_debug = (
            f"event: {reaction.event or 'unknown'}\n"
            f"state: {state}\n"
            "performance: none\n"
            f"lifecycle: {plan.lifecycle}\n"
            f"minimum_ms: {plan.minimum_ms}\n"
            f"priority: {plan.priority}\n"
            "source: action\n"
            "steps: 0\n"
            f"fallback_action: {plan.action or reaction.action or 'none'}\n"
            "fallback_reason: no_performance_or_no_line"
        )
        self._perform_action(plan.action)
        self._maybe_emit_particles(reaction.mood, plan.action)
        if reaction.should_say and reaction.line:
            self.show_bubble(reaction.line, kind=reaction.bubble)
            self.state.remember_line(reaction.line)

    def _maybe_show_reaction_decoration(self, reaction: Reaction) -> None:
        event = (reaction.event or "").lower()
        bubble = (reaction.bubble or "").lower()
        if event.startswith(("hardware_", "chat_hardware", "demo_hardware")) or bubble.startswith("hardware_"):
            self._show_temporary_decoration("heat_puffs", 4200)
            self._show_temporary_decoration("paper_fan", 3800)
        if event.startswith(("codex_usage", "claude_usage", "openai_billing", "chat_usage", "chat_claude_usage", "chat_openai_billing", "demo_usage")) or bubble.startswith("usage_"):
            self._show_temporary_decoration("usage_bar", 4200)
        if "reset_soon" in event or "reset_wait" in event:
            self._show_temporary_decoration("reset_clock", 4200)
        if reaction.performance in {"cold_arrow_then_innocent", "roast_and_scoot"} or reaction.mood in {"smirk", "smug"}:
            self._show_temporary_decoration("annotation_circle", 2600)
        if reaction.action in {"hide", "oops_innocent_combo", "inner_cover_oops"} or reaction.performance in {"cold_arrow_then_innocent", "fake_innocent"}:
            self._show_temporary_decoration("paper_oops_cover", 3200)
        if reaction.performance == "cheesy_love_cringe":
            self._show_temporary_decoration("paper_oops_cover", 3600)
        if reaction.action in {"dance", "celebrate", "happy_bounce"} or reaction.performance in {"tiny_celebrate", "holding_laugh"}:
            self._show_temporary_decoration("paper_stage", 3600)
        if reaction.action == "flop":
            self._show_temporary_decoration("paper_pillow", 4200)
        if reaction.action == "peek":
            self._show_temporary_decoration("paper_peek_curtain", 3600)
        if reaction.mood in {"sleepy", "sulky"}:
            self._show_temporary_decoration("z_symbol", 3200)
        if any(key in event for key in ("error", "blocked", "critical", "overloaded")):
            self._show_temporary_decoration("tiny_warning", 4200)
        if any(key in event for key in ("error", "blocked", "test_failed", "crash", "exception")):
            self._show_temporary_decoration("bug_marker", 4200)

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

    def _apply_alive_cue(self, cue: AliveCue) -> None:
        self._cancel_alive_after()
        self._last_alive_debug = cue.debug_text()
        if cue.eyes or cue.brows:
            self._transition_expression(cue.eyes or "round", cue.brows or "neutral", hold_ms=cue.hold_ms)
        if cue.attention in {"user", "mouse"} and not self._dragging:
            self._start_mouse_follow(min(max(cue.hold_ms, 700), 1800), force=True)
        elif cue.attention == "status":
            self._stop_mouse_follow()
            self._set_eye_pose("side_eye")
        elif cue.attention == "inward":
            self._stop_mouse_follow()
        elif cue.attention == "down":
            self._stop_mouse_follow()
            self._set_eye_pose("peek_up")
        if cue.after_action:
            self._alive_after.append(
                self.root.after(cue.after_delay_ms, lambda action=cue.after_action: self._perform_action(action))
            )
        if cue.residue:
            self._alive_after.append(
                self.root.after(
                    cue.residue_delay_ms,
                    lambda residue=cue.residue, hold_ms=cue.residue_hold_ms: self._apply_emotional_residue(residue, hold_ms),
                )
            )

    def _apply_emotional_residue(self, residue: str, hold_ms: int = 1600) -> None:
        if self.state.brain_busy or self._dragging:
            return
        expressions = {
            "innocent": ("wide", "innocent", "cover"),
            "watching": ("side_eye", "soft", "idle"),
            "soft": ("soft", "soft", "idle"),
            "thinking": ("soft", "soft", "think"),
            "sleepy": ("half_closed", "soft", "idle"),
            "sulk": ("peek_up", "sulk", "sulk"),
            "proud": ("round", "proud", "idle"),
        }
        expr = expressions.get(residue)
        if not expr:
            return
        eyes, brows, chin = expr
        self._transition_expression(eyes, brows, hold_ms=hold_ms)
        self.set_chin_mode(chin)

    def _cancel_alive_after(self) -> None:
        for after_id in self._alive_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._alive_after.clear()

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
        self._cancel_inner_gesture(reset=True)

    def _prepare_action_acting(self, action: str) -> None:
        cue = ACTION_ACTING_CUES.get(action)
        if not cue:
            return
        eyes, brows, hold_ms, blush = cue
        self._transition_expression(eyes, brows, hold_ms=hold_ms)
        if blush:
            self._set_cheek_blush(True)

    def _perform_action(self, action: str) -> None:
        if not action or action == "idle":
            return
        self_particles = ACTION_SELF_PARTICLES.get(action)
        if self_particles:
            preset, delay_ms = self_particles
            self.root.after(delay_ms, lambda p=preset: self._emit_particles(p))
        # a new action reclaims the tail immediately; if it carries a prop,
        # _start_action_prop re-enters hand mode 30ms later
        self._tail_hand_mode = False
        self._run_action_prop(action)
        prop_actions = {
            "oops_innocent_combo",
            "britclip_enter",
            "britclip_exit",
            "british_gentleman_suit_up",
            "hat_tip_oops",
            "tip_hat",
            "bow_tie_check",
            "cane_tap",
            "polite_bow",
        }
        if action in {"melt", "meltdown"}:
            self._run_melt_action()
            return
        if action in PAPER_PROP_ACTIONS:
            self._run_paper_prop_action(action)
            return
        is_tail_action = (
            action in TAIL_MOTION_FRAMES
            or action in TAIL_OSCILLATIONS
            or action in TAIL_POSTURES
        )
        if not is_tail_action and action not in INNER_GESTURE_FRAMES and action not in prop_actions:
            self._cancel_tail_wag(reset=True)
        if is_tail_action:
            self._prepare_action_acting(action)
            motion, dur = self._tail_motion_for_action(action)
            self._run_tail_motion(motion, dur)
            return
        if action in INNER_GESTURE_FRAMES:
            self._prepare_action_acting(action)
            self._run_inner_gesture(action)
            return
        if action == "oops_innocent_combo":
            self._run_oops_innocent_combo()
            return
        if action in {"britclip_enter", "british_gentleman_suit_up"}:
            self._run_british_gentleman_suit_up()
            return
        if action == "britclip_exit":
            self._run_british_gentleman_suit_down()
            return
        if action in {"hat_tip_oops", "tip_hat"}:
            self._run_hat_tip_oops()
            return
        if action == "bow_tie_check":
            self._run_tail_motion("tail_tip_flick")
            self._set_brow_pose("proud")
            return
        if action == "cane_tap":
            self._run_tail_motion("tail_tip_flick")
            self._emit_particles("dust")
            return
        if action == "polite_bow":
            self._run_large_action(ACTION_FRAMES["nod"], "polite_bow")
            return
        if action in MOVE_IDLE_ACTIONS:
            self._run_window_move_action(action)
            return
        if action.startswith("micro_"):
            self._perform_micro_action(action)
            return
        if action == "bob":
            self._run_large_action(ACTION_FRAMES["nod"], "nod")
            return
        if action == "wiggle":
            self._prepare_action_acting(action)
            self._wiggle()
            return
        if action == "blink":
            self._blink()
            return
        if action == "slow_blink":
            self._slow_blink()
            return
        if action == "peek":
            self._prepare_action_acting(action)
            self._start_mouse_follow(1500, force=True)
            self._start_tail_for_action(action)
            self._start_inner_for_action(action)
            return
        if action == "scan":
            self._prepare_action_acting(action)
            self._scan()
            self._start_tail_for_action(action)
            self._start_inner_for_action(action)
            return
        frames = ACTION_FRAMES.get(action)
        if frames:
            self._run_large_action(frames, action)
            self._start_inner_for_action(action)

    def _run_paper_prop_action(self, action: str) -> None:
        cue = PAPER_PROP_ACTIONS.get(action)
        if not cue:
            return
        duration = int(cue.get("duration") or 4200)
        decoration = str(cue.get("decoration") or "")
        if decoration:
            self._show_temporary_decoration(decoration, duration)
        eyes = str(cue.get("eyes") or "")
        brows = str(cue.get("brows") or "")
        if eyes or brows:
            self._transition_expression(eyes or "round", brows or "neutral", max(800, duration - 400))
        tail = str(cue.get("tail") or "")
        if tail:
            self._run_tail_motion(tail)
        inner = str(cue.get("inner") or "")
        if inner:
            self._run_inner_gesture(inner)
        frames = cue.get("frames")
        if isinstance(frames, tuple):
            self._run_prop_body_frames(frames)

    def _run_tail_wag(self) -> None:
        self._run_tail_motion("tail_wag")

    def _start_tail_for_action(self, action: str) -> None:
        motion = ACTION_TAIL_MOTIONS.get(action)
        if motion:
            override, dur = self._tail_motion_for_action(action)
            self._run_tail_motion(override if override != action else motion, dur)

    def _start_inner_for_action(self, action: str) -> None:
        gesture = ACTION_INNER_GESTURES.get(action)
        if gesture:
            self._run_inner_gesture(gesture)

    def _tail_motion_for_action(self, action: str) -> tuple[str, float]:
        """Tail motion for an action, honouring a prop it rings or twirls.

        A prop held at the tip overrides the motion (ringing a bell is a wrist
        shake, not an arm swing) and pins the tail's duration to the prop's, so
        the tail never keeps moving after the prop is gone.
        """
        cue = ACTION_PROP_CUES.get(action)
        if cue and cue.get("held") and cue.get("tail_style") == "wag":
            motion = str(cue.get("tail_motion") or action)
            return motion, prop_cue_duration_ms(action) / 1000.0
        return action, 0.0

    def _run_tail_motion(self, motion: str, duration_s: float = 0.0) -> None:
        if not self.tail_wire:
            return
        # a hand that is carrying something does not wag
        if self._tail_hand_mode:
            return
        if motion in TAIL_OSCILLATIONS:
            self._run_tail_oscillation(TAIL_OSCILLATIONS[motion], motion, duration_s)
            return
        if motion in TAIL_POSTURES:
            self._run_tail_posture(TAIL_POSTURES[motion])
            return
        frames = TAIL_MOTION_FRAMES.get(motion)
        if not frames:
            return
        self._cancel_tail_wag(reset=False)

        def finish() -> None:
            self._tail_wag_after.clear()
            if motion in {"tail_wag", "tail_smug_sway"}:
                self._schedule_expression_reset(900)

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._tail_transition_to(TAIL_NEUTRAL_POSE, 140, finish)
                return
            sway, curl, droop, tuck, stiffen, delay = frames[index]
            target: TailPose = (sway, curl, droop, tuck, stiffen)
            self._tail_transition_to(target, delay, lambda: step(index + 1))

        step()

    def _run_tail_oscillation(self, params: dict[str, object], motion: str = "", duration_s: float = 0.0) -> None:
        """Drive the tail as a continuous damped pendulum — the cat-tail swing.

        The oscillator owns `_tail_s_phase` while running, so the swing IS the
        traveling wave (root leads, tip follows) instead of two sine sources
        beating against each other.
        """
        self._cancel_tail_wag(reset=False)
        self._tail_osc_active = True
        self._tail_wave_factor = params.get("wave")
        self._tail_engage = params.get("engage")
        start = time.monotonic()
        start_pose = self._tail_pose
        phase0 = self._tail_s_phase
        total_s = duration_s or float(params["cycles"]) / float(params["freq"])
        attack_s = max(0.05, float(params.get("attack", 0.2))) * total_s

        def finish() -> None:
            self._tail_osc_active = False
            self._tail_wave_factor = None
            self._tail_engage = None
            self._tail_wag_after.clear()
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 160)
            if motion in {"tail_wag", "tail_smug_sway"}:
                self._schedule_expression_reset(900)

        def tick() -> None:
            t = time.monotonic() - start
            sample = tail_oscillation_pose(params, t, duration_s)
            if sample is None:
                finish()
                return
            sway, curl, droop, tuck, stiffen, phase = sample
            # blend out of whatever pose the tail held when the swing began
            blend = _smoothstep(min(1.0, t / attack_s)) if attack_s > 0 else 1.0
            pose = (
                start_pose[0] * (1.0 - blend) + sway,
                start_pose[1] * (1.0 - blend) + curl,
                start_pose[2] * (1.0 - blend) + droop,
                start_pose[3] * (1.0 - blend) + tuck,
                start_pose[4] * (1.0 - blend) + stiffen,
            )
            self._tail_s_phase = phase0 + phase
            self._set_tail_pose(*pose)
            self._tail_wag_after.append(self.root.after(LERP_TICK_MS, tick))

        tick()

    def _run_tail_posture(self, params: dict[str, object]) -> None:
        """Hold an expressive tail posture (raised, hooked, bristled)."""
        self._cancel_tail_wag(reset=False)
        self._tail_osc_active = True  # owns the tail like an oscillation
        start = time.monotonic()
        start_pose = self._tail_pose

        def finish() -> None:
            self._tail_osc_active = False
            self._tail_wag_after.clear()
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 180)

        def tick() -> None:
            t = time.monotonic() - start
            sample = tail_posture_pose(params, t)
            if sample is None:
                finish()
                return
            blend = _smoothstep(min(1.0, t / _POSTURE_ENTER_S))
            pose = tuple(
                start_pose[i] * (1.0 - blend) + sample[i] for i in range(5)
            )
            self._set_tail_pose(*pose)  # type: ignore[arg-type]
            self._tail_wag_after.append(self.root.after(LERP_TICK_MS, tick))

        tick()

    def _tail_transition_to(
        self,
        target: TailPose,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._tail_pose
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_tail_pose(*target)
                if on_done:
                    on_done()
                return
            # smoothstep: zero velocity at both ends, so direction reversals
            # between wag keyframes swing like a pendulum instead of snapping
            t = _smoothstep((index + 1) / steps)
            pose = tuple(start[i] + (target[i] - start[i]) * t for i in range(5))
            self._set_tail_pose(*pose)  # type: ignore[arg-type]
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._tail_wag_after.append(after_id)

        tick()

    def _cancel_tail_wag(self, reset: bool = True) -> None:
        for after_id in self._tail_wag_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._tail_wag_after.clear()
        self._tail_osc_active = False
        self._tail_wave_factor = None
        self._tail_engage = None
        if reset:
            self._set_tail_pose(*TAIL_NEUTRAL_POSE)

    def _set_tail_wag_amount(self, amount: float) -> None:
        self._set_tail_pose(sway=amount)

    def _run_inner_gesture(self, gesture: str) -> None:
        frames = INNER_GESTURE_FRAMES.get(gesture)
        if not frames or not self._chin_wire:
            return
        self._cancel_inner_gesture(reset=False)
        self._inner_gesture_active = True

        def finish() -> None:
            self._inner_gesture_after.clear()
            self._inner_gesture_active = False

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._inner_transition_to(INNER_NEUTRAL_POSE, 130, finish)
                return
            tip_x, tip_y, mid_x, mid_y, delay = frames[index]
            self._inner_transition_to((tip_x, tip_y, mid_x, mid_y), delay, lambda: step(index + 1))

        step()

    def _inner_transition_to(
        self,
        target: InnerPose,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._inner_pose
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_chin_amount(*target)
                if on_done:
                    on_done()
                return
            t = _ease_out_sine((index + 1) / steps)
            pose = tuple(start[i] + (target[i] - start[i]) * t for i in range(4))
            self._set_chin_amount(*pose)  # type: ignore[arg-type]
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._inner_gesture_after.append(after_id)

        tick()

    def _cancel_inner_gesture(self, reset: bool = True) -> None:
        for after_id in self._inner_gesture_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._inner_gesture_after.clear()
        self._inner_gesture_active = False
        if reset:
            self._set_chin_amount(*INNER_NEUTRAL_POSE)

    def _run_british_gentleman_suit_up(self) -> None:
        if self._dragging:
            return
        self._clear_non_costume_decorations()
        self.appearance = AppearanceState(
            costume_id="britclip",
            phase="entering",
            language_mode="en",
        )
        self._clear_gentleman_props()
        self._stop_mouse_follow()
        self._prepare_action_acting("britclip_enter")
        self._set_eye_pose("side_eye")
        self._set_brow_pose("proud")
        self._prop_anim_after.append(self.root.after(1050, self._draw_britclip_bow_tie))
        self._prop_anim_after.append(self.root.after(1750, self._draw_gentleman_cane))
        hat_start = self._gentleman_tail_anchor()
        hat_end = self._gentleman_hat_head_anchor()
        hat_items = self._draw_bowler_hat(*hat_start, scale=1.22)
        self._run_tail_motion("tail_alert_snap")
        self._run_inner_gesture("inner_side_smirk")
        self._run_prop_body_frames(
            (
                (0.0, 0.0, 1.0, 1.0, 80),
                (-6.0, 4.0, 0.92, 1.07, 320),
                (-10.0, 2.0, 0.89, 1.10, 720),
                (-4.0, -1.0, 0.97, 1.03, 320),
                (0.0, 0.0, 1.0, 1.0, 280),
            )
        )
        self._animate_prop_path(
            hat_items,
            hat_end,
            control=(hat_end[0] + 48, hat_end[1] - 62),
            duration_ms=850,
            delay_ms=300,
            on_done=lambda: (self._run_tail_motion("tail_smug_sway"), self._raise_face_over_costume()),
        )
        self._prop_anim_after.append(self.root.after(1500, lambda: self._run_tail_motion("tail_smug_sway") if self._gentleman_prop_items else None))
        self._prop_anim_after.append(self.root.after(2350, lambda: self._run_tail_motion("tail_tip_flick") if self._gentleman_prop_items else None))
        self._prop_anim_after.append(self.root.after(2550, lambda: self._run_large_action(ACTION_FRAMES["nod"], "polite_bow")))
        self._prop_anim_after.append(self.root.after(3100, self._finish_britclip_enter))
        self._schedule_expression_reset(5200)

    def _finish_britclip_enter(self) -> None:
        self.appearance = AppearanceState(
            costume_id="britclip",
            phase="equipped",
            language_mode="en",
        )
        self._raise_face_over_costume()

    def _run_british_gentleman_suit_down(self) -> None:
        if self._dragging:
            return
        if not self._gentleman_prop_items:
            self.appearance = AppearanceState(language_mode=normalize_language(self.soul.language))
            return
        self.appearance.phase = "exiting"
        self._stop_mouse_follow()
        self._set_brow_pose("guilty")
        self._set_eye_pose("round")
        self._run_inner_gesture("inner_shy_retract")
        self._run_tail_motion("tail_alert_snap")
        self._run_prop_body_frames(
            (
                (0.0, 0.0, 1.0, 1.0, 80),
                (-5.0, 3.0, 0.93, 1.06, 260),
                (-8.0, 1.0, 0.90, 1.09, 520),
                (-2.0, 0.0, 0.98, 1.02, 220),
                (0.0, 0.0, 1.0, 1.0, 200),
            )
        )
        hat_items = list(self._gentleman_hat_items)
        if hat_items:
            tail = self._gentleman_tail_anchor()
            self._animate_prop_path(
                hat_items,
                tail,
                control=(tail[0] + 8, min(tail[1], self._gentleman_hat_head_anchor()[1]) - 52),
                duration_ms=1250,
                delay_ms=180,
                on_done=lambda: self._prop_anim_after.append(
                    self.root.after(360, self._finish_britclip_exit)
                ),
            )
        else:
            self._prop_anim_after.append(self.root.after(900, self._finish_britclip_exit))
        self._schedule_expression_reset(1900)

    def _finish_britclip_exit(self) -> None:
        self._clear_gentleman_props(cancel_timers=False)
        self.appearance = AppearanceState(language_mode=normalize_language(self.soul.language))

    def _run_hat_tip_oops(self) -> None:
        if self._dragging:
            return
        if not self._gentleman_hat_items:
            self._clear_gentleman_props()
            self._draw_gentleman_static_props()
            self._draw_bowler_hat(*self._gentleman_hat_head_anchor(), scale=1.0)
            self._raise_face_over_costume()
            if self.appearance.costume_id != "britclip":
                self._prop_anim_after.append(self.root.after(2400, self._clear_gentleman_props))
        hat_items = list(self._gentleman_hat_items)
        if not hat_items:
            return
        self._prepare_action_acting("hat_tip_oops")
        self._run_tail_motion("tail_tip_flick")
        self._run_inner_gesture("inner_cover_oops")
        head = self._gentleman_hat_head_anchor()
        tipped = (head[0] + 18, head[1] - 17)
        self._animate_prop_path(
            hat_items,
            tipped,
            control=(head[0] + 32, head[1] - 35),
            duration_ms=260,
        )
        self._animate_prop_path(
            hat_items,
            head,
            control=(head[0] + 26, head[1] - 27),
            duration_ms=340,
            delay_ms=320,
        )
        self._schedule_expression_reset(1500)

    def _run_oops_innocent_combo(self) -> None:
        self._stop_mouse_follow()
        self._set_brow_pose("innocent")
        self._pupil_look = (0.0, 0.0)
        self._set_pupil_pose(0.0, -0.1, size_scale=1.12)
        self._run_inner_gesture("inner_cover_oops")
        self._run_tail_motion("tail_frantic_innocent")
        if normalize_language(self.soul.language) == "en":
            self._performance_after.append(self.root.after(120, self._run_hat_tip_oops))
        timeline: tuple[tuple[int, Callable[[], None]], ...] = (
            (70, lambda: self._animate_look((-2.8, -0.15))),
            (150, self._blink),
            (250, lambda: self._animate_look((2.7, -0.05))),
            (360, self._blink),
            (480, lambda: self._animate_look((-1.2, 0.3))),
            (590, lambda: self._animate_look((0.0, 0.0))),
            (690, self._blink),
        )
        for delay, callback in timeline:
            self._performance_after.append(self.root.after(delay, callback))
        self._schedule_expression_reset(1400)

    def _idle_tail_pose(self) -> TailPose:
        phase = self._tail_idle_phase
        long = self._tail_mode == "long"
        # long tail: broader, lazier sway — the length amplifies visually
        # short tail: tighter, snappier
        # resting amplitudes stay small so the idle tail hugs the original
        # silhouette; actions and moods bring the big bends
        if long:
            amp = 0.34 + self.mood.energy * 0.30
            sway = (
                math.sin(phase * 0.42) * amp
                + math.sin(phase * 0.97) * amp * 0.18
                + math.sin(phase * 1.73) * amp * 0.06
            )
            curl = math.sin(phase * 0.35) * 0.38
        else:
            amp = 0.20 + self.mood.energy * 0.24
            sway = math.sin(phase * 0.72) * amp + math.sin(phase * 1.55) * amp * 0.12
            curl = math.sin(phase * 0.48) * 0.30
        droop = 0.0
        tuck = 0.0
        stiffen = 0.0
        mood = (self.state.mood or "").lower()
        if mood in {"smirk", "smug", "proud", "happy", "done"}:
            sway *= 1.45 if not long else 1.2
            curl += 1.4 if not long else 1.2
        elif mood in {"sleepy", "bored"} or self._doze_stage >= 1:
            sway *= 0.35 if long else 0.45
            curl -= 0.5
            droop = (5.0 if long else 3.4) + math.sin(phase * 0.38) * 0.6
        elif mood in {"sulky", "guilty", "shy"}:
            sway *= 0.45 if long else 0.55
            curl -= 0.8
            tuck = (3.6 if long else 2.4) + math.sin(phase * 0.5) * 0.4
        elif mood in {"startled", "worried"}:
            sway *= 0.75
            stiffen = 2.4
        return (sway, curl, droop, tuck, stiffen)

    def _set_tail_pose(
        self,
        sway: float = 0.0,
        curl: float = 0.0,
        droop: float = 0.0,
        tuck: float = 0.0,
        stiffen: float = 0.0,
    ) -> None:
        self._tail_pose = (sway, curl, droop, tuck, stiffen)
        if not self.tail_wire or not self._tail_base_coords:
            return
        now = time.monotonic()
        self._tail_pose_trail.append((now, self._tail_pose))
        tip_pose = self._sample_tail_trail(now - TAIL_TIP_LAG_MS / 1000.0)
        posed = posed_tail_points(
            self._tail_base_coords,
            sway, curl, droop, tuck, stiffen,
            tail_mode=self._tail_mode,
            s_phase=self._tail_s_phase,
            tip_pose=tip_pose,
            wave_factor=self._tail_wave_factor,
            engage=self._tail_engage,
        )
        coords: list[float] = []
        for x, y in posed:
            coords.extend(self._actor_point(x, y))
        self.canvas.coords(self.tail_wire, *coords)
        # the tail tip doubles as a hand: held props are anchored here
        self._tail_tip_point = (coords[-2], coords[-1])

    def _sample_tail_trail(self, target_time: float) -> TailPose:
        """Return the tail pose as it was at target_time (for tip follow-through)."""
        trail = self._tail_pose_trail
        while len(trail) >= 2 and trail[1][0] <= target_time:
            trail.popleft()
        if not trail:
            return self._tail_pose
        first_time, first_pose = trail[0]
        if first_time >= target_time or len(trail) < 2:
            return first_pose
        second_time, second_pose = trail[1]
        span = second_time - first_time
        t = (target_time - first_time) / span if span > 0 else 1.0
        return tuple(first_pose[i] + (second_pose[i] - first_pose[i]) * t for i in range(5))  # type: ignore[return-value]

    # ── body bend channel ────────────────────────────────────────
    # Lean/hunch body language on top of the squash/offset channels. The bend
    # is folded into _actor_point, so eyes, brows, pupils, tail, and inner core
    # all follow it; only the body wire needs an explicit re-place.

    def _set_body_bend(self, lean: float, hunch: float) -> None:
        if (lean, hunch) == self._body_bend:
            return
        self._body_bend = (lean, hunch)
        self._apply_body_bend()

    def _apply_body_bend(self) -> None:
        """Re-place every absolutely-positioned part so it follows the bend."""
        if self._body_wire and self._body_base_coords:
            self.canvas.coords(self._body_wire, *self._actor_coords(self._body_base_coords))
        self._set_eye_openness(self._eye_openness)
        self._apply_brow_spec(*self._current_brow_spec)
        if self.tail_wire and self._tail_base_coords:
            self._set_tail_pose(*self._tail_pose)
        if self._chin_wire and self._chin_base_coords:
            self._set_chin_amount(*self._inner_pose)

    def _run_bend_motion(self, action: str) -> None:
        frames = ACTION_BODY_BEND.get(action)
        if not frames:
            # no bend script: ease any leftover bend back to neutral
            if self._body_bend != BODY_BEND_NEUTRAL and not self._bend_after:
                self._bend_transition_to(BODY_BEND_NEUTRAL, 180)
            return
        self._cancel_bend(reset=False)

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._bend_after.clear()
                return
            lean, hunch, delay = frames[index]
            self._bend_transition_to((lean, hunch), delay, lambda: step(index + 1))

        step()

    def _bend_transition_to(
        self,
        target: BodyBend,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._body_bend
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_body_bend(*target)
                if on_done:
                    on_done()
                return
            t = _smoothstep((index + 1) / steps)
            self._set_body_bend(
                start[0] + (target[0] - start[0]) * t,
                start[1] + (target[1] - start[1]) * t,
            )
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._bend_after.append(after_id)

        tick()

    def _cancel_bend(self, reset: bool = True) -> None:
        for after_id in self._bend_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._bend_after.clear()
        if reset:
            self._set_body_bend(*BODY_BEND_NEUTRAL)

    # ── emotion prop layer ───────────────────────────────────────
    # Every action carries an animated prop that performs the emotion (halo,
    # rain cloud, trophy, umbrella…). Shapes and timelines live in
    # prop_shapes.py and are shared with the GIF renderer.

    def _run_action_prop(self, action: str) -> None:
        cue = ACTION_PROP_CUES.get(action)
        if not cue or self._dragging:
            return
        # start one frame later so action dispatch (which may rebuild the
        # canvas via _reset_pal_geometry) cannot delete a just-drawn prop
        if self._action_prop_pending:
            try:
                self.root.after_cancel(self._action_prop_pending)
            except tk.TclError:
                pass
        self._action_prop_pending = self.root.after(
            30, lambda: self._start_action_prop(cue, action)
        )

    def _start_action_prop(self, cue: dict, action: str = "") -> None:
        self._action_prop_pending = None
        self._clear_action_prop()
        shape_key = str(cue.get("shape"))
        shape = PROP_SHAPES.get(shape_key)
        if not shape:
            return
        self._schedule_face_script(action)
        origin = _source_point(*cue["anchor"])
        timeline = build_prop_timeline(cue)
        items = self._create_prop_items(shape)
        self._action_prop_items = items
        held = bool(cue.get("held"))
        # worn props AND held props stay on top (a thing in the hand covers
        # the face when raised to it); only floating props go behind the face
        self._action_prop_over_face = bool(cue.get("over_face")) or held
        if not self._action_prop_over_face:
            self._raise_face_over_costume()
        grip = tuple(cue.get("grip_offset", (0.0, 0.0)))
        # held props attach and rotate at their natural grip point
        pivot = GRIP_POINTS.get(shape_key, (0.0, 0.0)) if held else (0.0, 0.0)
        # tail-as-hand: while carrying, the tail extends into a steady hold
        # instead of wagging — unless the tail itself is the performer
        # (bell ringing, pen twirling), marked tail_style "wag"
        if held and cue.get("tail_style", "hand") == "hand":
            self._cancel_tail_wag(reset=False)
            self._tail_hand_mode = True
            self._tail_hand_started = time.monotonic()
            self._tail_transition_to(TAIL_HAND_POSE, 220, self._tail_wag_after.clear)
        self._place_action_prop(items, shape, origin, timeline[0][:5], held=held, grip=grip, pivot=pivot)
        self._drive_action_prop(items, shape_key, shape, origin, timeline, held=held, grip=grip, pivot=pivot)

    def _schedule_face_script(self, action: str) -> None:
        """Stage the eyes/brows/gaze along the prop's story beats.

        Overrides the static acting cue: the face notices the prop, reacts at
        the story's peak, and lands an aftermath beat. Beats may carry
        micro-expression extras — pupil size, staged blinks, single-brow
        overrides, brow tremble, explicit eyelid level. Timers share the
        prop's lifecycle so an interrupted prop also stops its face script.
        """
        script = ACTION_FACE_SCRIPTS.get(action)
        if not script:
            return
        frame_total = sum(f[4] for f in ACTION_FRAMES.get(action, ())) or 1600

        def fire(eyes: str, brows: str, look, hold: int, extras) -> None:
            if eyes or brows:
                self._transition_expression(eyes or "round", brows or "neutral", hold_ms=hold)
            if look is not None and not self._is_blinking:
                self._animate_look(look)
            ex = extras or {}
            if "openness" in ex:
                self._eye_target_openness = float(ex["openness"])
            blink = ex.get("blink")
            if blink == "quick":
                self._blink()
            elif blink == "slow":
                self._slow_blink()
            elif blink == "double":
                self._blink()
                self._action_prop_after.append(self.root.after(260, self._blink))
            elif blink == "flutter":
                self._blink_flutter()
            if "tremble" in ex:
                self._brow_tremble(int(ex["tremble"]))
            # shaped pupils / wink / decal / blush: cleared automatically on
            # beats that do not declare them
            self._set_eye_fx(ex.get("pupil_shape"), ex.get("wink"))
            self._set_face_decal(ex.get("decal"))
            self._set_cheek_blush(bool(ex.get("blush")))
            # single-brow overrides and pupil sizing land after the 150ms
            # expression tween so they refine the pose instead of fighting it
            if "brow_l" in ex or "brow_r" in ex:
                base = self._BROW_MAP.get(brows or "neutral", self._BROW_MAP["neutral"])
                left = tuple(ex.get("brow_l", base[0]))
                right = tuple(ex.get("brow_r", base[1]))
                self._action_prop_after.append(
                    self.root.after(220, lambda l=left, r=right: self._apply_brow_spec(l, r))
                )
            if "pupil" in ex:
                scale = float(ex["pupil"])
                base_scale = self._EYE_MAP.get(eyes or "round", self._EYE_MAP["round"])[2]
                self._action_prop_after.append(
                    self.root.after(
                        220,
                        lambda s=base_scale * scale: self._set_pupil_pose(
                            *self._pupil_look, size_scale=s
                        ),
                    )
                )

        for i, frame in enumerate(script):
            at_ms, eyes, brows, look = frame[0], frame[1], frame[2], frame[3]
            extras = frame[4] if len(frame) > 4 else None
            next_at = script[i + 1][0] if i + 1 < len(script) else max(frame_total, at_ms) + 600
            hold = max(400, next_at - at_ms + 300)
            if at_ms <= 0:
                fire(eyes, brows, look, hold, extras)
            else:
                self._action_prop_after.append(
                    self.root.after(
                        at_ms,
                        lambda e=eyes, b=brows, lk=look, h=hold, x=extras: fire(e, b, lk, h, x),
                    )
                )

    # ── eye FX & face decals (distilled from the expression sheets) ──

    def _set_eye_fx(self, shape_key: str | None, wink: str | None = None) -> None:
        """Replace the round pupils with shaped ones (star/heart/spiral/x/…).

        `wink` closes one eye with a smiling arc; it combines with or without
        a shape for the other eye. Passing (None, None) restores round pupils.
        """
        if (shape_key, wink) == self._eye_fx_state:
            return
        self._eye_fx_state = (shape_key, wink)
        for item in self._eye_fx_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._eye_fx_items.clear()
        pupil_items = list(self._pupil_bounds)
        if not shape_key and not wink:
            for item in pupil_items:
                try:
                    self.canvas.itemconfigure(item, state="normal")
                except tk.TclError:
                    pass
            return
        shapes = EYE_FX_SHAPES.get(shape_key or "", (None, None))
        smile = EYE_FX_SHAPES["closed_smile"][0]
        per_eye = [shapes[0], shapes[1]]
        if wink == "l":
            per_eye[0] = smile
        elif wink == "r":
            per_eye[1] = smile
        for side, (item, prims) in enumerate(zip(pupil_items, per_eye)):
            if prims is None:
                continue
            try:
                self.canvas.itemconfigure(item, state="hidden")
            except tk.TclError:
                pass
            for prim in prims:
                self._eye_fx_items.append(self._create_face_prim(prim, tag="eye_fx"))
        self._place_eye_fx()

    def _place_eye_fx(self) -> None:
        """Position eye-FX shapes at each pupil's current center."""
        if not self._eye_fx_items:
            return
        shapes = EYE_FX_SHAPES.get(self._eye_fx_state[0] or "", (None, None))
        smile = EYE_FX_SHAPES["closed_smile"][0]
        per_eye = [shapes[0], shapes[1]]
        if self._eye_fx_state[1] == "l":
            per_eye[0] = smile
        elif self._eye_fx_state[1] == "r":
            per_eye[1] = smile
        sx, sy = (abs(v) or 1.0 for v in self._pal_scale)
        dx, dy = self._pupil_look
        item_iter = iter(self._eye_fx_items)
        for bounds, prims in zip(self._pupil_bounds.values(), per_eye):
            if prims is None:
                continue
            b = self._actor_oval_bounds(bounds, dx=dx, dy=dy)
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            for prim in prims:
                item = next(item_iter, None)
                if item is None:
                    return
                self._place_face_prim(item, prim, cx, cy, sx, sy)

    def _set_face_decal(self, key: str | None) -> None:
        """Hang a small symbol on the face (tear, sweat, shock rays, …)."""
        for item in self._face_decal_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._face_decal_items.clear()
        decal = FACE_DECALS.get(key or "")
        if not decal:
            return
        ax, ay = self._actor_point(*_source_point(*decal["anchor"]))
        sx, sy = (abs(v) or 1.0 for v in self._pal_scale)
        for prim in decal["prims"]:
            item = self._create_face_prim(prim, tag="face_decal")
            self._face_decal_items.append(item)
            self._place_face_prim(item, prim, ax, ay, sx, sy)
        self._raise_face_over_costume()
        for item in self._face_decal_items:
            try:
                self.canvas.tag_raise(item)
            except tk.TclError:
                pass

    def _create_face_prim(self, prim, tag: str) -> int:
        kind = prim[0]
        if kind == "line":
            return self.canvas.create_line(
                0, 0, 1, 1, fill=prim[3], width=prim[2],
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
                smooth=len(prim[1]) > 2, splinesteps=8,
                tags=("pal", tag),
            )
        if kind == "polygon":
            return self.canvas.create_polygon(
                0, 0, 1, 1, 2, 2, fill=prim[2] or "", outline=prim[3] or "",
                width=max(0.1, prim[4]), smooth=False, tags=("pal", tag),
            )
        _k, _cx, _cy, _rx, _ry, fill, outline, width = prim
        return self.canvas.create_oval(
            0, 0, 1, 1, fill=fill or "", outline=outline or "",
            width=max(0.1, width), tags=("pal", tag),
        )

    def _place_face_prim(self, item: int, prim, cx: float, cy: float, sx: float, sy: float) -> None:
        kind = prim[0]
        try:
            if kind in ("line", "polygon"):
                coords: list[float] = []
                for x, y in prim[1]:
                    coords.extend((cx + x * sx, cy + y * sy))
                self.canvas.coords(item, *coords)
            else:
                _k, ox, oy, rx, ry, _fill, _outline, _width = prim
                tx, ty = cx + ox * sx, cy + oy * sy
                self.canvas.coords(item, tx - rx * sx, ty - ry * sy, tx + rx * sx, ty + ry * sy)
        except tk.TclError:
            pass

    def _clear_face_fx(self) -> None:
        self._set_eye_fx(None, None)
        self._set_face_decal(None)
        self._set_cheek_blush(False)

    def _blink_flutter(self) -> None:
        """Rapid shallow eyelid flutter — overwhelmed, dazzled, or overcaffeinated."""
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        frames = ((0.5, 40), (0.9, 45), (0.4, 40), (0.85, 45), (0.5, 40), (1.0, 1))

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _brow_tremble(self, duration_ms: int) -> None:
        """Small fast brow shudder — cold, dread, or barely holding it together."""
        base = self._current_brow_spec
        end_at = time.monotonic() + duration_ms / 1000.0

        def tick() -> None:
            if time.monotonic() >= end_at or self._dragging:
                self._apply_brow_spec(*base)
                return
            jl = random.uniform(-0.45, 0.45)
            jr = random.uniform(-0.45, 0.45)
            left = (base[0][0], base[0][1] + jl, base[0][2])
            right = (base[1][0], base[1][1] + jr, base[1][2])
            self._apply_brow_spec(left, right)
            self._action_prop_after.append(self.root.after(65, tick))

        tick()

    def _create_prop_items(self, shape) -> list[int]:
        items: list[int] = []
        for prim in shape:
            kind = prim[0]
            if kind == "line":
                items.append(self.canvas.create_line(
                    0, 0, 1, 1, fill=prim[3], width=prim[2],
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    smooth=len(prim[1]) > 2, splinesteps=8,
                    tags=("action_prop",),
                ))
            elif kind == "polygon":
                _k, _pts, fill, outline, width = prim
                items.append(self.canvas.create_polygon(
                    0, 0, 1, 1, 2, 2, fill=fill or "", outline=outline or "",
                    width=max(0.1, width), tags=("action_prop",),
                ))
            elif kind == "oval":
                _k, _cx, _cy, _rx, _ry, fill, outline, width = prim
                items.append(self.canvas.create_oval(
                    0, 0, 1, 1, fill=fill or "", outline=outline or "",
                    width=max(0.1, width), tags=("action_prop",),
                ))
        return items

    def _place_action_prop(
        self,
        items: list[int],
        shape,
        origin: tuple[float, float],
        pose,
        update_colors: bool = False,
        held: bool = False,
        grip: tuple[float, float] = (0.0, 0.0),
        pivot: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        posed = transform_shape(shape, tuple(pose), pivot=pivot)
        if held:
            # gripped by the tail tip: ride the tail's live position and skip
            # the body squash transform (a held object keeps its own shape)
            base_x = self._tail_tip_point[0] + grip[0]
            base_y = self._tail_tip_point[1] + grip[1]

            def project(x: float, y: float) -> tuple[float, float]:
                return (base_x + x, base_y + y)

            rsx = rsy = 1.0
        else:
            def project(x: float, y: float) -> tuple[float, float]:
                return self._actor_point(origin[0] + x, origin[1] + y)

            rsx, rsy = (abs(v) for v in self._pal_scale)
        for item, prim in zip(items, posed):
            kind = prim[0]
            try:
                if kind == "line" or kind == "polygon":
                    pts = prim[1]
                    coords: list[float] = []
                    for x, y in pts:
                        coords.extend(project(x, y))
                    self.canvas.coords(item, *coords)
                    if update_colors:
                        if kind == "line":
                            self.canvas.itemconfigure(item, fill=prim[3])
                        else:
                            self.canvas.itemconfigure(item, fill=prim[2] or "", outline=prim[3] or "")
                elif kind == "oval":
                    _k, cx, cy, rx, ry, fill, outline, _width = prim
                    tx, ty = project(cx, cy)
                    self.canvas.coords(item, tx - rx * rsx, ty - ry * rsy, tx + rx * rsx, ty + ry * rsy)
                    if update_colors:
                        self.canvas.itemconfigure(item, fill=fill or "", outline=outline or "")
            except tk.TclError:
                pass

    def _drive_action_prop(
        self, items: list[int], shape_key: str, shape, origin, timeline,
        held: bool = False, grip: tuple[float, float] = (0.0, 0.0),
        pivot: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        state = list(timeline[0][:5])
        started = time.monotonic()
        has_fx = shape_key in SHAPE_FX
        physics = {"extra": 0.0, "dx": timeline[0][0]}

        def run_frame(fi: int) -> None:
            if fi >= len(timeline):
                self._clear_action_prop()
                return
            dx, dy, rot, scale, squash, delay = timeline[fi]
            steps = max(1, round(delay / LERP_TICK_MS))

            def tick(si: int = 0) -> None:
                if si >= steps:
                    state[:] = [dx, dy, rot, scale, squash]
                    run_frame(fi + 1)
                    return
                t = _smoothstep((si + 1) / steps)
                pose_dx = state[0] + (dx - state[0]) * t
                # carried-object inertia: swing opposite to horizontal motion
                physics["extra"] = inertia_step(
                    physics["extra"], physics["dx"], pose_dx, LERP_TICK_MS / 1000.0
                )
                physics["dx"] = pose_dx
                pose = (
                    pose_dx,
                    state[1] + (dy - state[1]) * t,
                    state[2] + (rot - state[2]) * t + physics["extra"],
                    state[3] + (scale - state[3]) * t,
                    state[4] + (squash - state[4]) * t,
                )
                frame_shape = shape
                if has_fx:
                    frame_shape = apply_shape_fx(shape_key, shape, time.monotonic() - started)
                self._place_action_prop(
                    items, frame_shape, origin, pose,
                    update_colors=has_fx, held=held, grip=grip, pivot=pivot,
                )
                self._action_prop_after.append(self.root.after(LERP_TICK_MS, lambda: tick(si + 1)))

            tick()

        run_frame(1)

    def _clear_action_prop(self) -> None:
        for after_id in self._action_prop_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._action_prop_after.clear()
        for item in self._action_prop_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._action_prop_items.clear()
        self._clear_face_fx()
        if self._tail_hand_mode:
            self._tail_hand_mode = False
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 200, self._tail_wag_after.clear)

    def _set_chin_amount(
        self,
        amount_x: float,
        amount_y: float = 0.0,
        mid_x: float = 0.0,
        mid_y: float = 0.0,
    ) -> None:
        """Displace the inner core with virtual mid/tip anchors. Positive y curls upward."""
        self._inner_pose = (amount_x, amount_y, mid_x, mid_y)
        if not self._chin_wire or not self._chin_base_coords:
            return
        posed = posed_chin_points(self._chin_base_coords, amount_x, amount_y, mid_x, mid_y)
        coords: list[float] = []
        for x, y in posed:
            coords.extend(self._actor_point(x, y))
        self.canvas.coords(self._chin_wire, *coords)

    def _settle_chin_pose(self, target: InnerPose, strength: float = 0.34) -> None:
        # caller strengths are tuned for the legacy 50ms heartbeat
        strength = _per_tick(_clamp(strength, 0.0, 1.0))
        pose = tuple(self._inner_pose[i] + (target[i] - self._inner_pose[i]) * strength for i in range(4))
        self._set_chin_amount(*pose)  # type: ignore[arg-type]

    def set_chin_mode(self, mode: str) -> None:
        """Set chin animation mode: idle|talk|chew|yawn|mumble|cover|wave|point|fidget|think|sulk."""
        self._chin_mode = mode
        if mode == "talk":
            # reset syllable state for fresh speech
            self._chin_syllable_phase = 0.0
            self._chin_syllable_amp = 1.0
            self._chin_pause_timer = 0

    def _perform_micro_action(self, action: str) -> None:
        if action == "micro_focus_pause":
            self._stop_mouse_follow()
            self._set_brow_pose("soft")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.94)
            self._animate_look((0.0, 0.0))
        elif action == "micro_side_eye":
            self._set_brow_pose("skeptical")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.98)
            self._animate_look((-3.1, 0.35))
            self._run_tail_motion("tail_tip_flick")
        elif action == "micro_brow_judge":
            self._set_brow_pose("judge")
        elif action == "micro_snap_innocent":
            self._stop_mouse_follow()
            self._set_brow_pose("innocent")
            self._pupil_look = (0.0, 0.0)
            self._set_pupil_pose(0.0, -0.2, size_scale=1.14)
            self._run_tail_motion("tail_guilty_tuck")
            self._schedule_expression_reset(1200)
        elif action == "micro_caught_guilty":
            self._stop_mouse_follow()
            self._set_brow_pose("worried")
            self._pupil_look = (0.0, -0.1)
            self._set_pupil_pose(0.0, -0.1, size_scale=1.10)
            self._run_tail_motion("tail_guilty_tuck")
            self._schedule_expression_reset(1400)
        elif action == "micro_holding_laugh":
            self._set_brow_pose("smug_arch")
            self._set_pupil_pose(0.45, -0.1, size_scale=0.88)
            self._run_tail_motion("tail_smug_sway")
        elif action == "micro_peek_up":
            self._set_brow_pose("droop")
            self._set_pupil_pose(1.9, -0.75, size_scale=0.92)
            self._run_tail_motion("tail_sleepy_droop")
        elif action == "micro_soften":
            self._set_brow_pose("soft")
            self._set_pupil_pose(0.0, 0.0, size_scale=0.96)
        elif action == "micro_tiny_proud":
            self._set_brow_pose("proud")
            self._set_pupil_pose(-0.35, -0.25, size_scale=1.02)
        elif action == "micro_guilty_dart":
            self._guilty_dart()
        elif action == "micro_slow_blink":
            self._slow_blink()
        elif action == "micro_soft_reset":
            self._reset_expression_pose()

    def _set_eye_pose(self, pose: str) -> None:
        # (dx, dy, pupil_scale, eye_openness)
        poses: dict[str, tuple[float, float, float, float]] = {
            "neutral": (0.0, 0.0, 1.0, 1.0),
            "side_eye": (-3.1, 0.35, 0.92, 0.78),
            "round": (0.0, 0.0, 1.08, 1.0),
            "soft": (0.0, 0.0, 0.96, 0.8),
            "peek_up": (1.9, -0.75, 0.92, 0.75),
            "narrow": (0.0, 0.6, 0.7, 0.55),
            "wide": (0.0, -0.3, 1.15, 1.0),
            "half_closed": (0.0, 0.5, 0.7, 0.35),
            "closed": (0.0, 0.0, 0.5, 0.0),
            "proud": (-0.35, -0.25, 1.02, 1.0),
            "innocent_round": (0.0, -0.35, 1.18, 1.0),
            "guilty_round": (0.0, -0.10, 1.12, 1.0),
            "smug_half": (-2.8, 0.45, 0.80, 0.58),
            "suspicious_slit": (-2.2, 0.45, 0.74, 0.52),
            "worried_wide": (0.35, -0.15, 1.08, 1.0),
            "sleepy_slit": (0.0, 0.55, 0.62, 0.26),
            "curious": (1.15, -0.30, 1.04, 0.94),
            "startled_dot": (0.0, -0.40, 0.72, 1.0),
        }
        dx, dy, scale, openness = poses.get(pose, poses["neutral"])
        self._pupil_look = (dx, dy)
        self._eye_target_openness = openness
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
            "smug_arch": ((0.0, -1.7, -0.10), (0.0, -0.9, 0.08)),
            "skeptical": ((-0.4, 1.2, -0.10), (0.4, -0.8, 0.10)),
            "angry": ((-0.7, 2.8, -0.18), (0.7, 2.5, 0.18)),
            "worried": ((0.0, 2.2, 0.10), (0.0, 2.0, -0.10)),
            "droop": ((0.0, 2.4, 0.04), (0.0, 2.2, -0.04)),
            "curious": ((0.0, -1.6, -0.06), (0.0, 0.2, 0.06)),
            "flat": ((0.0, 0.2, 0.0), (0.0, 0.2, 0.0)),
            "panic": ((0.0, -2.6, 0.12), (0.0, -2.3, -0.12)),
        }
        left_spec, right_spec = poses.get(pose, poses["neutral"])
        for item, spec in ((self.left_brow, left_spec), (self.right_brow, right_spec)):
            base = self._brow_base_coords.get(item)
            if base:
                self.canvas.coords(item, *self._actor_coords(_brow_pose_coords(base, *spec)))
        self._current_brow_spec = (left_spec, right_spec)

    def _schedule_expression_reset(self, delay_ms: int) -> None:
        self._expression_after.append(self.root.after(delay_ms, self._reset_expression_pose))

    def _reset_expression_pose(self) -> None:
        self._cancel_expression_after(reset=False)
        if self._doze_stage >= 1 or self.state.mood == "sleepy":
            self._set_brow_pose("droop")
            self._set_eye_pose("sleepy_slit")
            self._set_cheek_blush(False)
            if self._chin_mode != "talk":
                self.set_chin_mode("sulk")
            return
        self._set_brow_pose("neutral")
        self._set_pupil_pose(*self._pupil_look, size_scale=1.0)
        self._eye_target_openness = 1.0
        self._set_cheek_blush(False)
        if self._chin_mode != "talk":
            self.set_chin_mode("idle")

    # (dx, dy, pupil_scale, eye_openness)
    _EYE_MAP: dict[str, tuple[float, float, float, float]] = {
        "round": (0.0, 0.0, 1.0, 1.0),
        "side_eye": (-3.1, 0.35, 0.85, 0.78),
        "soft": (0.0, 0.4, 0.82, 0.75),
        "peek_up": (0.0, -1.6, 0.75, 0.7),
        "narrow": (0.0, 0.8, 0.65, 0.45),
        "wide": (0.0, -0.4, 1.25, 1.0),
        "half_closed": (0.0, 0.6, 0.65, 0.3),
        "closed": (0.0, 0.0, 0.4, 0.0),
        "sparkle": (0.0, -0.2, 1.18, 1.0),  # excited / delighted
        "proud": (-0.35, -0.25, 1.02, 1.0),
        "innocent_round": (0.0, -0.35, 1.18, 1.0),
        "guilty_round": (0.0, -0.10, 1.12, 1.0),
        "smug_half": (-2.8, 0.45, 0.80, 0.58),
        "suspicious_slit": (-2.2, 0.45, 0.74, 0.52),
        "worried_wide": (0.35, -0.15, 1.08, 1.0),
        "sleepy_slit": (0.0, 0.55, 0.62, 0.26),
        "curious": (1.15, -0.30, 1.04, 0.94),
        "startled_dot": (0.0, -0.40, 0.72, 1.0),
    }
    _BROW_MAP: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
        "neutral": ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
        "soft": ((0.0, -1.0, 0.0), (0.0, -0.7, 0.0)),
        "judge": ((-0.6, 2.4, -0.12), (0.4, 1.7, 0.12)),
        "innocent": ((0.0, -3.0, 0.04), (0.0, -2.4, -0.04)),
        "guilty": ((0.0, 3.2, 0.07), (0.0, 2.8, -0.07)),
        "laugh": ((0.0, 2.0, -0.03), (0.0, 1.6, 0.03)),
        "sulk": ((0.0, 3.4, -0.05), (0.0, 2.8, 0.05)),
        "proud": ((0.0, -2.0, -0.08), (0.0, -1.6, 0.08)),
        "smug_arch": ((0.0, -2.2, -0.12), (0.0, -1.2, 0.10)),
        "skeptical": ((-0.6, 1.8, -0.12), (0.5, -1.0, 0.12)),
        "angry": ((-0.9, 3.2, -0.20), (0.9, 3.0, 0.20)),
        "worried": ((0.0, 3.0, 0.12), (0.0, 2.8, -0.12)),
        "droop": ((0.0, 3.0, 0.06), (0.0, 2.8, -0.06)),
        "curious": ((0.0, -2.0, -0.08), (0.0, 0.3, 0.08)),
        "flat": ((0.0, 0.3, 0.0), (0.0, 0.3, 0.0)),
        "panic": ((0.0, -3.0, 0.14), (0.0, -2.6, -0.14)),
    }

    def _transition_expression(self, eyes: str, brows: str, hold_ms: int = 1800) -> None:
        """Smoothly tween to a new expression with automatic reset after hold_ms."""
        self._cancel_expression_after(reset=False)
        target_eye_4 = self._EYE_MAP.get(eyes, self._EYE_MAP["round"])
        target_eye = target_eye_4[:3]  # (dx, dy, scale) for pupil tweener
        target_openness = target_eye_4[3]
        target_brow = self._BROW_MAP.get(brows, self._BROW_MAP["neutral"])
        # start tweens from current state
        self._expr_tweener.transition_pupils(self._current_pupil_spec, target_eye)
        self._expr_tweener.transition_brows(
            self._current_brow_spec[0], target_brow[0],
            self._current_brow_spec[1], target_brow[1],
        )
        # smooth eye openness transition
        self._eye_target_openness = target_openness
        # update targets for tracking
        self._pupil_look = (target_eye[0], target_eye[1])
        self._current_pupil_spec = target_eye
        self._current_brow_spec = target_brow
        self._schedule_expression_reset(hold_ms)

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
            self._eye_target_openness = 1.0

    def _schedule_idle(self, first: bool = False) -> None:
        if first:
            delay = 10_000
        else:
            low = max(8, self.soul.idle_min_seconds)
            high = max(low, self.soul.idle_max_seconds)
            delay = random.randint(low, high) * 1000
        self.root.after(delay, self._idle_tick)

    def _idle_tick(self) -> None:
        if self._doze_stage >= 2:
            self._schedule_idle()
            return
        policy = self._activity_policy()
        idle_cooldown = max(12, round(self.soul.cooldown_seconds * policy.cooldown_multiplier))
        if (
            not self._auto_reactions_paused()
            and policy.ambient_enabled
            and self.state.can_speak(idle_cooldown)
        ):
            context = self.ears.sample()
            if context.idle_seconds > 75 and random.random() < 0.70:
                self._ask_brain("bored", allow_live=False)
            elif context.idle_seconds > 15 or random.random() < 0.35:
                self._ask_brain("idle", allow_live=False)
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
        interruptibility = self._interruptibility()
        if not interruptibility.allow_speech:
            self.decision.last_decision = DecisionResult(
                False,
                event="ambient",
                reason=interruptibility.reason,
                pattern="interruptibility",
                reaction_style="silent_watch",
                blocked_rules=[f"interruptibility:{interruptibility.mode}"],
            )
            if interruptibility.allow_animation and not self._dragging and not self._large_action_running:
                self._apply_alive_cue(self.alive.observe_silence("ambient", interruptibility.reason))
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
            self._ask_brain("ambient", world, allow_live=False)
        self._schedule_ambient()

    def _animate(self) -> None:
        self._anim_tick += 1
        self._anim_t += ANIM_TICK_SCALE
        self.mood.tick()
        rate = self.mood.breath_rate()
        self._bob_phase += rate * ANIM_TICK_SCALE
        if self._bob_phase >= 1.0:
            self._bob_phase -= 1.0
            base = self.mood.breath_depth_base()
            self._breath_depth = base + random.uniform(-0.15, 0.25)
        breath = _breath_curve(self._bob_phase)
        next_y = -breath * self._breath_depth * 0.55
        sway_amp = 0.18 + self.mood.energy * 0.20 + min(0.36, max(0.0, self.mood.frequency_multiplier - 1.0) * 0.08)
        # layered sway: slow drift + faster wobble for organic feel
        sway_x = math.sin(self._anim_t * 0.026) * sway_amp + math.sin(self._anim_t * 0.061) * sway_amp * 0.16
        self._move_actor_items(sway_x - self._bob_x, next_y - self._bob_y)
        self._bob_x = sway_x
        self._bob_y = next_y
        # spring-damper overlay (soft rebound after actions)
        if self._spring_active:
            sx, sy = self._spring.tick(ANIM_TICK_MS / 1000.0)
            if self._spring.at_rest:
                self._spring_active = False
                self._spring.snap()
            elif not self._large_action_running and not self._window_move_running:
                self._set_pal_scale(sx, sy)
        # idle micro-lean: weight shifts subtly even when standing still
        if (
            not self._bend_after
            and not self._dragging
            and not self._large_action_running
            and not self._window_move_running
        ):
            idle_lean = math.sin(self._anim_t * 0.019) * (0.8 + self.mood.energy * 1.4)
            idle_hunch = math.sin(self._anim_t * 0.011 + 1.7) * 0.7
            if self._doze_stage >= 1:
                idle_hunch += 3.0
            self._set_body_bend(idle_lean, idle_hunch)
        # tail idle sway — layered frequencies for organic curl
        self._tail_idle_phase += 0.045 * ANIM_TICK_SCALE
        # long tail: slower wave propagation for graceful serpentine
        # (an active oscillation owns the wave phase; do not fight it)
        if not self._tail_osc_active:
            self._tail_s_phase += (0.038 if self._tail_mode == "long" else 0.055) * ANIM_TICK_SCALE
        if self._tail_hand_mode and self.tail_wire and not self._tail_wag_after:
            # carrying: steady hold with a keeping-it-level micro-sway
            self._set_tail_pose(*tail_hand_pose(time.monotonic() - self._tail_hand_started))
        elif not self._tail_wag_after and self.tail_wire and not self._large_action_running:
            self._set_tail_pose(*self._idle_tail_pose())
        # chin idle animation — mode-dependent (hand/mouth dual system)
        self._chin_idle_phase += 0.032 * ANIM_TICK_SCALE
        if self._chin_wire and not self._large_action_running and not self._inner_gesture_active:
            mode = self._chin_mode
            if mode == "talk":
                # --- enhanced talk: syllable bursts + micro-pauses ---
                self._chin_syllable_phase += 0.12 * ANIM_TICK_SCALE
                # micro-pause: occasional silent breath gap
                if self._chin_pause_timer > 0:
                    self._chin_pause_timer -= 1
                    self._settle_chin_pose((0.0, 0.4, 0.0, 0.2), 0.45)
                else:
                    # random pause trigger roughly every 2s
                    if random.random() < 0.025 * ANIM_TICK_SCALE:
                        self._chin_pause_timer = random.randint(5, 11)
                    # randomize syllable amplitude every ~0.4s
                    if self._anim_tick % 12 == 0:
                        self._chin_syllable_amp = random.uniform(0.6, 1.4)
                    amp = self._chin_syllable_amp
                    # primary jaw oscillation with syllable modulation
                    jaw = math.sin(self._chin_syllable_phase * 2.8) * 1.3 * amp
                    # secondary lateral wobble for liveliness
                    cx = math.sin(self._chin_syllable_phase * 1.9) * 1.0 * amp
                    cy = 2.2 * amp + jaw * 0.6
                    # slight head-tilt via mid_x
                    mx = math.sin(self._chin_idle_phase * 0.55) * 0.7
                    self._settle_chin_pose((cx, cy, mx - cx * 0.3, cy * 0.3), 0.52)
            elif mode == "chew":
                # sharp asymmetric biting — fast choppy vertical
                chew_phase = self._chin_idle_phase * 3.2
                chomp = abs(math.sin(chew_phase)) ** 0.6 * (-7.0)
                offset = math.sin(chew_phase * 0.7) * 2.0
                self._settle_chin_pose((offset, chomp, -offset * 0.3, chomp * 0.4), 0.55)
            elif mode == "yawn":
                # slow arc: open → hold → close, driven by phase
                yawn_t = (math.sin(self._chin_idle_phase * 0.25) + 1.0) * 0.5
                opening = math.sin(yawn_t * math.pi) ** 1.5 * (-12.0)
                drift = math.sin(self._chin_idle_phase * 0.4) * 0.6
                self._settle_chin_pose((drift, opening, -drift * 0.2, opening * 0.5), 0.32)
            elif mode == "mumble":
                # barely visible: tiny rapid movements
                mx = math.sin(self._chin_idle_phase * 3.5) * 0.4
                my = math.sin(self._chin_idle_phase * 4.1) * 0.3 + 0.5
                self._settle_chin_pose((mx, my, -mx * 0.2, my * 0.3), 0.40)
            elif mode == "cover":
                # curl upward toward eyes (hand covering mouth)
                hold_drift = math.sin(self._chin_idle_phase * 0.5) * 0.4
                self._settle_chin_pose((1.0 + hold_drift, 8.0, -2.2, 5.0), 0.38)
            elif mode == "wave":
                # hand: side-to-side sweep, greeting
                sweep = math.sin(self._chin_idle_phase * 2.1) * 10.0
                lift = 5.0 + math.sin(self._chin_idle_phase * 1.3) * 1.5
                self._settle_chin_pose((sweep, lift, -sweep * 0.3, lift * 0.4), 0.48)
            elif mode == "point":
                # hand: extend upward firmly with micro-drift
                drift = math.sin(self._chin_idle_phase * 0.6) * 0.5
                self._settle_chin_pose((drift, 14.0, 0.0, 6.0), 0.36)
            elif mode == "fidget":
                # hand: nervous rapid random tapping
                fx = math.sin(self._chin_idle_phase * 4.7) * 2.5 + math.sin(self._chin_idle_phase * 7.3) * 1.2
                fy = math.sin(self._chin_idle_phase * 5.2) * 1.5
                self._settle_chin_pose((fx, fy, -fx * 0.3, fy * 0.2), 0.50)
            elif mode == "think":
                # slight upward tilt, gentle drift (hand on chin)
                drift = math.sin(self._chin_idle_phase * 0.7) * 0.9
                self._settle_chin_pose((drift, 2.8, -drift * 0.35, 1.2), 0.34)
            elif mode == "sulk":
                # droop down
                droop = -5.0 + math.sin(self._chin_idle_phase * 0.3) * 0.4
                self._settle_chin_pose((0.0, droop, 0.0, droop * 0.56), 0.30)
            else:
                # idle: subtle drift + rare spontaneous micro-gestures
                amp = 0.28 + self.mood.energy * 0.24
                drift = math.sin(self._chin_idle_phase * 0.8) * amp
                self._settle_chin_pose((drift, 0.0, -drift * 0.25, 0.0), 0.36)
                # spontaneous hand micro-gesture (wave/fidget) in high-energy idle
                if self._anim_tick % 300 == 0 and self.mood.energy > 0.6:
                    if random.random() < 0.15:
                        gesture = random.choice(["inner_wave", "inner_fidget", "inner_thumbs_up"])
                        self._run_inner_gesture(gesture)
        # idle micro-expressions: small gaze checks often enough to feel alive, not noisy.
        if self._anim_tick % 90 == 0 and not self._large_action_running and self._doze_stage == 0:
            if random.random() < 0.25:
                dx = random.uniform(-0.9, 0.9)
                dy = random.uniform(-0.45, 0.35)
                self._animate_look((dx, dy))
        # expression tweening
        if self._expr_tweener.is_tweening:
            brow_result = self._expr_tweener.tick_brows()
            if brow_result:
                left_spec, right_spec = brow_result
                self._apply_brow_spec(left_spec, right_spec)
            pupil_result = self._expr_tweener.tick_pupils()
            if pupil_result:
                dx, dy, scale = pupil_result
                self._set_pupil_pose(dx, dy, size_scale=scale)
        # smooth eye openness interpolation
        if abs(self._eye_openness - self._eye_target_openness) > 0.01:
            speed = _per_tick(0.18) if self._eye_target_openness < self._eye_openness else _per_tick(0.22)
            self._eye_openness += (self._eye_target_openness - self._eye_openness) * speed
            if abs(self._eye_openness - self._eye_target_openness) < 0.02:
                self._eye_openness = self._eye_target_openness
            self._set_eye_openness(self._eye_openness)
        # shadow depth
        self._update_shadow()
        # doze detection
        self._update_doze()
        self.root.after(ANIM_TICK_MS, self._animate)

    def _wiggle(self) -> None:
        if self._large_action_running:
            return
        self._spring.kick_squash(2.5)
        self._spring_active = True
        self._cancel_tail_wag(reset=True)
        frames = WIGGLE_FRAMES
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
            self._reset_pal_geometry()

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._reset_pal_geometry()
                self._rebound_after = None
                self._start_tail_for_action("wiggle")
                return
            sx, sy, delay = frames[index]
            self._set_pal_scale(sx, sy)
            self._rebound_after = self.root.after(delay, lambda: step(index + 1))

        step()

    def _run_large_action(self, frames: ActionFrames, action_name: str = "") -> None:
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting(action_name)
        self._start_tail_for_action(action_name)
        self._start_inner_for_action(action_name)
        self._run_bend_motion(action_name)
        self._shadow_action = action_name if action_name in ACTION_SHADOW_ACTIONS else ""
        self._large_action_running = True
        ease = easing_for_action(action_name)

        jittered = _jitter_frames(_acting_frames(frames, action_name))
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
            t = ease((si + 1) / n)
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

    def _run_melt_action(self) -> None:
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting("melt")
        self._start_tail_for_action("melt")
        self._start_inner_for_action("melt")
        self._emit_particles("sweat")
        self._shadow_action = "melt"
        self._large_action_running = True
        frames: ActionFrames = MELT_SINK_FRAMES
        state = [0.0, 0.0, 1.0, 1.0]
        recovery_frames: ActionFrames = MELT_RECOVERY_FRAMES

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(frames):
                self._draw_melt_puddle(1.0)
                self._large_action_after = self.root.after(MELT_PUDDLE_HOLD_MS, recover)
                return
            dx, dy, sx, sy, delay = frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            phase = (si + 1) / n
            ease = phase ** 3 if fi < 5 else _ease_out_cubic(phase)
            self._set_action_offset(
                state[0] + (dx - state[0]) * ease,
                state[1] + (dy - state[1]) * ease,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * ease,
                state[3] + (sy - state[3]) * ease,
            )
            progress = (fi + phase) / len(frames)
            self._draw_melt_puddle(progress)
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        def recover(fi: int = 0, si: int = 0) -> None:
            if fi >= len(recovery_frames):
                self._finish_melt_action()
                return
            dx, dy, sx, sy, delay = recovery_frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                recover(fi + 1, 0)
                return
            phase = (si + 1) / n
            ease = phase * phase * (3.0 - 2.0 * phase)
            self._set_action_offset(
                state[0] + (dx - state[0]) * ease,
                state[1] + (dy - state[1]) * ease,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * ease,
                state[3] + (sy - state[3]) * ease,
            )
            progress = (fi + phase) / len(recovery_frames)
            self._draw_melt_puddle(1.0 - progress * 0.72)
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: recover(_fi, _si + 1),
            )

        step()

    def _finish_melt_action(self) -> None:
        self._large_action_after = None
        self._large_action_running = False
        self._shadow_action = ""
        self._clear_melt_puddle()
        self._spring.snap()
        self._spring_active = False
        self._reset_pal_geometry(preserve_tail=True)
        self._transition_expression("guilty_round", "innocent", hold_ms=1200)

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
                (dx, 0, 1.0, 1.0, 90),
                (dx, -1, 0.99, 1.02, 220),   # freeze: nothing happened
                (dx, 0, 1.0, 1.0, 160),
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
        elif action == "zoomies":
            # 猫式疯跑：冲刺仍要读得出「跑过去」的过程——每程 120-150ms，
            # 急停后钉一拍再折返
            span = direction * random.randint(60, 90)
            frames = (
                (span * 0.5, -6, 0.88, 1.10, 130),
                (span, 0, 1.14, 0.90, 110),
                (span, 0, 1.0, 1.0, 90),
                (-span * 0.35, -6, 0.88, 1.10, 150),
                (-span * 0.6, 0, 1.14, 0.90, 110),
                (-span * 0.6, 0, 1.0, 1.0, 90),
                (0, -6, 0.92, 1.06, 130),
                (0, 0, 1.0, 1.0, 120),
            )
        elif action == "moonwalk":
            # 太空步：翻面背对行进方向滑走，节奏性起伏，到位再翻回来
            dx = direction * random.randint(55, 95)
            frames = (
                (0, 0, -1.0, 1.0, 110),
                (dx * 0.3, 3, -1.06, 0.94, 140),
                (dx * 0.45, -2, -0.98, 1.03, 110),
                (dx * 0.7, 3, -1.06, 0.94, 140),
                (dx * 0.85, -2, -0.98, 1.03, 110),
                (dx, 0, -1.0, 1.0, 120),
                (dx, 0, 1.0, 1.0, 130),
            )
        elif action == "pounce":
            # 猛扑：压低蓄力扭两下，向前跃出一小段落地
            dx = direction * random.randint(45, 85)
            frames = (
                (-direction * 6, 4, 1.12, 0.84, 200),
                (-direction * 8, 5, 1.14, 0.82, 150),
                (dx * 0.7, -22, 0.86, 1.18, 110),
                (dx, 6, 1.18, 0.82, 90),
                (dx, -4, 0.96, 1.05, 80),
                (dx, 0, 1.0, 1.0, 90),
            )
        elif action == "drop_in":
            self._run_drop_in()
            return
        else:
            return
        self._run_window_move(frames, action)

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
        # a canopy descent: drifting down with a sway, then a soft touchdown
        self._run_window_move(
            (
                (-4, dy * 0.20, 0.97, 1.05, 200),
                (5, dy * 0.45, 0.98, 1.04, 210),
                (-4, dy * 0.70, 0.98, 1.03, 200),
                (2, dy * 0.92, 0.99, 1.02, 170),
                (0, dy + 6, 1.10, 0.86, 90),
                (0, dy - 3, 0.97, 1.04, 80),
                (0, dy, 1.0, 1.0, 80),
            ),
            "drop_in",
        )

    def _run_window_move(self, frames: ActionFrames, action_name: str = "") -> None:
        if not frames:
            return
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting(action_name)
        self._start_tail_for_action(action_name)
        self._start_inner_for_action(action_name)
        self._run_bend_motion(action_name)
        self.root.update_idletasks()
        start_x = self.root.winfo_x()
        start_y = self.root.winfo_y()
        frames = self._clamped_window_frames(_acting_frames(frames, action_name), start_x, start_y)
        self._window_move_running = True
        ease = easing_for_action(action_name)
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
            t = ease((si + 1) / n)
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
        self._spring.kick_bounce(2.2)
        self._spring_active = True
        self._reset_pal_geometry(preserve_tail=True)
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
        # scale toward the clamped endpoint, then clamp every intermediate
        # frame too so mid-action dashes (zoomies, pounce) stay on screen
        return tuple(
            (
                _clamp(start_x + dx * ratio_x, left, max_x) - start_x,
                _clamp(start_y + dy * ratio_y, top, max_y) - start_y,
                sx,
                sy,
                delay,
            )
            for dx, dy, sx, sy, delay in frames
        )

    def _cancel_large_action(self) -> None:
        if self._large_action_after:
            self.root.after_cancel(self._large_action_after)
            self._large_action_after = None
        if self._large_action_running:
            self._finish_large_action()

    def _finish_large_action(self) -> None:
        self._large_action_after = None
        self._large_action_running = False
        self._shadow_action = ""
        self._clear_melt_puddle()
        self._spring.kick_bounce(1.8)
        self._spring_active = True
        self._reset_pal_geometry(preserve_tail=True)

    def _set_action_offset(self, dx: float, dy: float) -> None:
        previous_x, previous_y = self._action_offset
        self._move_actor_items(dx - previous_x, dy - previous_y)
        self._action_offset = (dx, dy)

    def _set_pal_scale(self, sx: float, sy: float) -> None:
        # mirror flips interpolate sx through zero; Tk refuses a zero scale
        # factor and the broken callback chain would wedge the action state
        if abs(sx) < 0.01:
            sx = 0.01 if sx >= 0 else -0.01
        if abs(sy) < 0.01:
            sy = 0.01 if sy >= 0 else -0.01
        previous_x, previous_y = self._pal_scale
        if previous_x == 0 or previous_y == 0:
            previous_x, previous_y = 1.0, 1.0
        self._scale_actor_items(sx / previous_x, sy / previous_y)
        self._pal_scale = (sx, sy)

    def _apply_brow_spec(
        self,
        left_spec: tuple[float, float, float],
        right_spec: tuple[float, float, float],
    ) -> None:
        """Apply raw brow offset/rotation without going through pose lookup."""
        for item, spec in ((self.left_brow, left_spec), (self.right_brow, right_spec)):
            base = self._brow_base_coords.get(item)
            if base:
                self.canvas.coords(item, *self._actor_coords(_brow_pose_coords(base, *spec)))
        self._current_brow_spec = (left_spec, right_spec)

    def _update_shadow(self) -> None:
        """Draw a temporary contact shadow only for physical action beats."""
        if not self._shadow_action or self._dragging or self._window_move_running:
            self._hide_shadow()
            return
        action_dy = self._action_offset[1] + self._bob_y

        if self._shadow_action == "melt":
            contact = _clamp(1.0 - self._pal_scale[1], 0.0, 1.0)
            rx = 24 + contact * 34
            ry = 4.0 + contact * 4.0
            strength = 0x18 + round(contact * 0x14)
        elif self._shadow_action in {"flop", "sleepy_sag", "sulk"}:
            contact = _clamp(action_dy / 28.0, 0.0, 1.0)
            rx = 18 + contact * 16
            ry = 3.5 + contact * 2.0
            strength = 0x16 + round(contact * 0x18)
        else:
            lift = max(0.0, -action_dy)
            contact = _clamp(action_dy / 10.0, 0.0, 1.0)
            shrink = max(0.24, 1.0 - lift / 78.0)
            rx = 22 * shrink + contact * 5
            ry = 5.2 * shrink + contact * 1.4
            strength = max(0x12, min(0x42, round(0x38 * shrink + contact * 0x0a)))

        if rx < 7 or ry < 1.5:
            self._hide_shadow()
            return
        cx = PAL_CENTER_X + self._bob_x + self._action_offset[0]
        cy = PAL_PAD_Y + PAL_HEIGHT + 4
        color = f"#{strength:02x}{strength:02x}{strength:02x}"
        if self._shadow_item:
            self.canvas.coords(
                self._shadow_item,
                cx - rx, cy - ry, cx + rx, cy + ry,
            )
            self.canvas.itemconfigure(self._shadow_item, fill=color, outline="")
        else:
            self._shadow_item = self.canvas.create_oval(
                cx - rx, cy - ry, cx + rx, cy + ry,
                fill=color, outline="", tags=("shadow",),
            )
            self.canvas.tag_lower("shadow")

    def _hide_shadow(self) -> None:
        if not self._shadow_item:
            return
        try:
            self.canvas.delete(self._shadow_item)
        except tk.TclError:
            pass
        self._shadow_item = 0

    def _update_doze(self) -> None:
        """Progressive doze sequence when user is idle for extended periods."""
        now = time.time()
        # Throttle ears.sample() — only check every ~2 seconds
        if self._anim_tick % 60 != 0 and self._doze_stage < 3:
            return
        try:
            idle_secs = self.ears.sample().idle_seconds
        except Exception:
            idle_secs = 0
        if idle_secs < 30:
            if self._doze_stage > 0:
                if self._doze_stage >= 2:
                    self._spring.kick_stretch(3.0)
                    self._spring_active = True
                    self._transition_expression("wide", "innocent", 2000)
                    self._emit_particles("exclaim")
                else:
                    self._reset_expression_pose()
                self._doze_stage = 0
                self._hide_sleep_blanket()
            self._last_active_time = now
            return
        idle_duration = now - self._last_active_time
        if self._doze_stage == 0 and idle_duration > 120:
            # stage 1: drowsy — eyes half-closed, brows drooping, yawn
            self._doze_stage = 1
            self._transition_expression("sleepy_slit", "droop", 120_000)
            self._run_inner_gesture("inner_yawn")
            self.set_chin_mode("sulk")
        elif self._doze_stage == 1 and idle_duration > 240:
            # stage 2: fully asleep — eyes closed, zzz particles
            self._doze_stage = 2
            self._transition_expression("closed", "droop", 600_000)
            self.set_chin_mode("sulk")
            self._emit_particles("zzz")
            self._show_sleep_blanket()
        elif self._doze_stage == 2:
            # periodic zzz while sleeping
            self._show_sleep_blanket()
            if self._anim_tick % 300 == 0:
                self._emit_particles("zzz")
            if idle_secs < 10:
                # wake up!
                self._doze_stage = 3
                self._doze_timer = now
                self._spring.kick_stretch(3.0)
                self._spring_active = True
                self._transition_expression("wide", "innocent", 2000)
                self._emit_particles("exclaim")
        elif self._doze_stage == 3 and now - self._doze_timer > 2:
            self._doze_stage = 0
            self._last_active_time = now
            self._hide_sleep_blanket()

    def _drag_struggle(self) -> None:
        """Small wiggle while being dragged — the pal 'struggles'."""
        if not self._dragging:
            return
        self._spring.kick_squash(0.8)
        self._spring_active = True

    def _emit_particles(self, preset: str = "sparkle") -> None:
        cx, cy = self._particle_anchor(preset)
        self._particles.emit(cx, cy, preset)

    def _particle_anchor(self, preset: str) -> tuple[float, float]:
        anchors = {
            "zzz": (PAL_PAD_X + PAL_WIDTH * 0.95, PAL_PAD_Y - 10),
            "dust": (PAL_CENTER_X, PAL_PAD_Y + PAL_HEIGHT * 1.04),
            "sweat": (PAL_PAD_X + PAL_WIDTH * 1.02, PAL_PAD_Y + PAL_HEIGHT * 0.31),
            "exclaim": (PAL_PAD_X + PAL_WIDTH * 0.62, PAL_PAD_Y - 16),
            "question": (PAL_PAD_X + PAL_WIDTH * 0.88, PAL_PAD_Y - 10),
            "confetti": (PAL_CENTER_X, PAL_PAD_Y + PAL_HEIGHT * 0.03),
            "stars": (PAL_PAD_X + PAL_WIDTH * 0.95, PAL_PAD_Y + PAL_HEIGHT * 0.08),
            "sparkle": (PAL_PAD_X + PAL_WIDTH * 0.94, PAL_PAD_Y + PAL_HEIGHT * 0.10),
            "hearts": (PAL_PAD_X + PAL_WIDTH * 0.78, PAL_PAD_Y - 6),
            "angry": (PAL_PAD_X + PAL_WIDTH * 0.72, PAL_PAD_Y - 8),
            "question_pop": (PAL_PAD_X + PAL_WIDTH * 0.88, PAL_PAD_Y - 8),
            "idea_burst": (PAL_PAD_X + PAL_WIDTH * 0.82, PAL_PAD_Y - 10),
            "red_x": (PAL_PAD_X + PAL_WIDTH * 0.72, PAL_PAD_Y - 4),
            "dizzy": (PAL_CENTER_X, PAL_PAD_Y - 8),
            "blush": (PAL_CENTER_X, PAL_PAD_Y + PAL_HEIGHT * 0.42),
        }
        x, y = anchors.get(preset, (PAL_CENTER_X, PAL_SCALE_CENTER_Y))
        return self._actor_point(x, y)

    def _maybe_emit_particles(self, mood: str, action: str) -> None:
        _PARTICLE_MAP: dict[str, str] = {
            "celebrate": "confetti",
            "happy_bounce": "sparkle",
            "jump": "stars",
            "startled_pop": "exclaim",
            "dance": "confetti",
            "sleepy_sag": "zzz",
            "shake": "sweat",
            "sulk": "dust",
            "flop": "dust",
            "melt": "sweat",
            "roast_and_scoot": "stars",
            "drop_in": "dust",
            "shiver": "sweat",
            "stretch": "dust",
            "yawn": "zzz",
            "thinking_tilt": "question_pop",
            "scan": "question_pop",
            "hide": "blush",
            "hat_tip_oops": "blush",
            "oops_innocent_combo": "blush",
            "spin_jump": "stars",
            "excited_spin": "confetti",
            "sneeze": "sweat",
            "peekaboo": "exclaim",
            "curious_lean": "question_pop",
            "zoomies": "dust",
            "moonwalk": "note",
            "pounce": "dust",
        }
        _MOOD_PARTICLES: dict[str, str] = {
            "done": "confetti",
            "excited": "confetti",
            "happy": "sparkle",
            "thinking": "idea_burst",
            "suspicious": "question_pop",
            "annoyed": "red_x",
            "worried": "sweat",
            "startled": "exclaim",
            "guilty": "blush",
            "shy": "blush",
            "sulky": "dust",
        }
        preset = _PARTICLE_MAP.get(action) or _MOOD_PARTICLES.get(mood)
        if preset:
            self._emit_particles(preset)

    def _blink(self) -> None:
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        # eased close/open: quick shut, brief hold, softer reopen
        frames = BLINK_FRAMES

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _slow_blink(self) -> None:
        """轻蔑式慢眨眼：较快合上、闭住停顿、缓缓睁开。放完冷箭后的"我说完了"。"""
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        frames = SLOW_BLINK_FRAMES

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _guilty_dart(self) -> None:
        """被抓包眼神回环：瞟你一眼 → 迅速移开 → 定住 → 慢慢飘回来。"""
        if self._large_action_running:
            return
        self._stop_mouse_follow()
        sequence = GUILTY_DART_SEQUENCE

        def step(index: int = 0) -> None:
            if index >= len(sequence) or self._large_action_running:
                return
            dx, dy, hold = sequence[index]
            self._pupil_look = (dx, dy)
            if not self._is_blinking:
                self._set_pupil_pose(dx, dy)
            self.root.after(hold, lambda: step(index + 1))

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
            and self._doze_stage < 1
            and time.time() >= self._mouse_follow_until
        ):
            if self._should_start_selective_mouse_follow():
                self._start_mouse_follow(random.randint(850, 1500))
            elif self._maybe_secret_judge():
                pass
            else:
                self._animate_look(self._pick_look_target())
        self._schedule_look()

    def _maybe_secret_judge(self) -> bool:
        """idle 时偶尔偷偷审判用户；鼠标一靠近就瞬间装乖。"""
        if random.random() >= 0.10:
            return False
        if self._is_pointer_near_pal() or self._bubble_items or self.state.brain_busy:
            return False
        self._secret_judge_until = time.time() + random.uniform(1.8, 3.2)
        self._set_brow_pose("judge")
        self._set_eye_pose("side_eye")
        self._secret_judge_tick()
        return True

    def _secret_judge_tick(self) -> None:
        if self._large_action_running or self._dragging or time.time() >= self._secret_judge_until:
            self._secret_judge_until = 0.0
            self._reset_expression_pose()
            return
        if self._is_pointer_near_pal():
            # 被抓包：切回无辜的速度快得可疑，然后补一个慢眨眼。
            self._secret_judge_until = 0.0
            self._perform_micro_action("micro_snap_innocent")
            self._expression_after.append(self.root.after(700, self._slow_blink))
            return
        self._expression_after.append(self.root.after(120, self._secret_judge_tick))

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
        targets = SCAN_LOOK_TARGETS

        def step(index: int = 0) -> None:
            if index >= len(targets) or self._is_blinking or self._large_action_running:
                return
            dx, dy = targets[index]
            self._pupil_look = (dx, dy)
            self._set_pupil_pose(dx, dy)
            self.root.after(SCAN_LOOK_HOLD_MS, lambda: step(index + 1))

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
        self._pupil_blink_scale = blink_scale
        openness = self._eye_openness
        for item, bounds in self._pupil_bounds.items():
            ry_scale = max(0.04, blink_scale * self._pupil_size_scale * openness)
            self.canvas.coords(
                item,
                *self._actor_oval_bounds(
                    bounds,
                    dx=dx,
                    dy=dy,
                    rx_scale=self._pupil_size_scale,
                    ry_scale=ry_scale,
                ),
            )
        # shaped pupils ride along with the gaze
        self._place_eye_fx()

    def _set_eye_openness(self, openness: float) -> None:
        """Set eye openness: 1.0=fully open, 0.0=fully closed.

        Uses arc-shaped eyelid overlays that follow the eye curvature.
        Hidden entirely in default (fully open) state.
        """
        openness = max(0.0, min(1.0, openness))
        self._eye_openness = openness
        # squash sclera ovals
        for item, bounds in self._sclera_bounds.items():
            self.canvas.coords(
                item,
                *self._actor_oval_bounds(bounds, ry_scale=max(0.06, openness)),
            )
        # position arc eyelids
        sclera_list = list(self._sclera_bounds.values())
        for i, lid in enumerate(self._lid_items):
            if i >= len(sclera_list):
                break
            if openness >= 0.95:
                self.canvas.itemconfigure(lid, state="hidden")
            else:
                self.canvas.itemconfigure(lid, state="normal")
                x1, y1, x2, y2 = self._actor_oval_bounds(sclera_list[i])
                # arc extent: wider as eye closes, centered on top (90 deg)
                extent = 360.0 * (1.0 - openness)
                start = 90.0 - extent / 2.0
                self.canvas.itemconfigure(lid, start=start, extent=extent)
                self.canvas.coords(lid, x1 - 2, y1 - 2, x2 + 2, y2 + 2)
        # refresh pupil pose to apply new openness scaling; keep the current
        # blink closure so mid-blink refreshes do not pop the pupil open
        self._set_pupil_pose(*self._pupil_look, blink_scale=self._pupil_blink_scale)

    def _set_cheek_blush(self, visible: bool, color: str | None = None) -> None:
        """Show or hide cheek blush ovals."""
        if visible == self._cheek_visible and color is None:
            return
        self._cheek_visible = visible
        state = "normal" if visible else "hidden"
        for item in self._cheek_items:
            try:
                self.canvas.itemconfigure(item, state=state)
                if color:
                    self.canvas.itemconfigure(item, fill=color)
            except tk.TclError:
                pass

    def show_bubble(self, text: str, milliseconds: int = 3200, kind: str = "speech") -> None:
        self._clear_bubble()
        # chin talks during speech bubbles
        is_thought, _fill, _outline, _text_fill = _bubble_style(kind)
        if not is_thought:
            self.set_chin_mode("talk")
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
        anchor_x, _anchor_y = self._pal_screen_point(PAL_CENTER_X, PAL_PAD_Y + PAL_HEIGHT * 0.35)
        left, top, right, bottom = self._monitor_bounds_for_point(anchor_x, _anchor_y)
        x = anchor_x - width / 2
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
        if self._chin_mode == "talk":
            self.set_chin_mode("idle")


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


def _reaction_visual_priority(reaction: Reaction) -> int:
    event = (reaction.event or "").lower()
    if any(key in event for key in ("error", "critical", "overloaded")):
        return 55
    if any(key in event for key in ("permission", "waiting_user", "blocked")):
        return 45
    if event.startswith(("poke", "chat_", "manual_", "demo_", "preview_")):
        return 42
    if any(key in event for key in ("usage_low", "usage_critical", "hardware_hot")):
        return 36
    if any(key in event for key in ("done", "refilled", "celebrate")):
        return 28
    if reaction.mood in {"sulky", "startled"}:
        return 34
    if reaction.mood in {"smirk", "smug", "suspicious"}:
        return 26
    return 12


def _is_direct_reaction(reaction: Reaction) -> bool:
    event = (reaction.event or "").lower()
    return event.startswith(
        (
            "chat",
            "poke",
            "manual_",
            "demo_",
            "preview_",
            "focus_",
            "quiet_",
            "resume_",
            "identity_",
        )
    )


def _agent_visual_key(status: str) -> str:
    key = _anim_key(status)
    if key in {"running", "working", "running_command", "testing", "tool_use", "tool_running"}:
        return "running_tool"
    if key in {"reading", "searching", "started"}:
        return "thinking"
    if key in {"blocked", "waiting", "wait_user", "needs_user"}:
        return "waiting_user"
    if key in {"permission_request", "needs_permission", "approval", "approve"}:
        return "permission"
    if key in {"precompact", "postcompact", "compact", "compacted"}:
        return "compacting"
    if key in {"disconnected", "disconnect", "stale"}:
        return "reconnecting"
    if key in {"ended", "complete", "completed", "success"}:
        return "done"
    if key in {"failed", "blocked_error"}:
        return "error"
    return key


def _anim_key(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


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


def _claude_usage_reaction(status: ClaudeUsageStatus, manual: bool = False) -> Reaction:
    if status.level == "unavailable":
        return Reaction(
            True,
            status.summary_line or "还没有 Claude usage 数据。夹夹暂时没有账本，只有眉毛。",
            "sleepy",
            "blink",
            "claude_speech" if manual else "claude_thought",
            "fake_sulk",
            event="claude_usage_unavailable",
        )

    line = status.summary_line
    if status.level == "heavy":
        line += " 账本有点厚，Claude 看起来不是在工作，是在燃烧上下文。"
        mood, action, performance = "sulky", "sleepy_sag", "usage_low_sag"
    elif status.level == "busy":
        line += " 它很忙，忙得很有订阅制软件的气质。"
        mood, action, performance = "suspicious", "scan", "suspicious_observe"
    elif status.level == "active":
        line += " 有动静，但还没到需要摆出会计脸。"
        mood, action, performance = "thinking", "thinking_tilt", "quiet_companion"
    elif status.level == "quiet":
        line += " 它今天暂时比较安静。安静得像在等你先犯错。"
        mood, action, performance = "innocent", "blink", "quiet_companion"
    else:
        line += " 数据有点旧，夹夹先不拿旧账吓唬你。"
        mood, action, performance = "sleepy", "blink", "fake_sulk"

    return Reaction(
        True,
        line,
        mood,
        action,
        "claude_speech" if manual else "claude_thought",
        performance,
        decision_reason=f"claude_usage={status.level}",
        event=f"claude_usage_{status.level}",
    )


def _claude_account_usage_reaction(status: ClaudeAccountUsageStatus, manual: bool = False) -> Reaction:
    if status.level == "unavailable":
        line = status.summary_line or "还没有 claude_account_status.json。夹夹暂时不知道 Claude 账号饭量。"
        return Reaction(
            True,
            line,
            "sleepy",
            "blink",
            "usage_thought",
            "quiet_companion",
            event="claude_account_usage_unavailable",
        )

    percent = _format_usage_percent(status.usage_remaining_percent)
    reset_label = format_claude_account_reset_in(status.reset_in_seconds)
    reset_suffix = f" {reset_label}后回血。" if reset_label and reset_label != "现在" else ""
    if reset_label == "现在":
        reset_suffix = " 现在应该回血。"

    choices = {
        "normal": (
            (f"Claude 账号还有 {percent}%。额度充裕，想聊就聊。{reset_suffix}",),
            "innocent",
            ("blink", "nod"),
            "quiet_companion",
            "usage_thought",
        ),
        "watch": (
            (
                f"Claude 账号还剩 {percent}%。不急，但可以留个心眼。{reset_suffix}",
                f"Claude 还有 {percent}%。建议节制，但不至于恐慌。{reset_suffix}",
            ),
            "thinking",
            ("scan", "peek", "thinking_tilt"),
            "suspicious_observe",
            "usage_thought",
        ),
        "low": (
            (
                f"Claude 账号只剩 {percent}%。长对话先缓缓。{reset_suffix}",
                f"还剩 {percent}%。Claude 的额度正在用微笑提醒你别聊了。{reset_suffix}",
            ),
            "suspicious",
            ("thinking_tilt", "sulk", "scan"),
            "fake_sulk",
            "usage_speech",
        ),
        "critical": (
            (
                f"Claude 账号剩 {percent}%。再聊下去就要被限速了。{reset_suffix}",
                f"只剩 {percent}%。Claude 快没饭了，先让它歇会儿。{reset_suffix}",
            ),
            "sulky",
            ("flop", "shake", "sleepy_sag"),
            "fake_sulk",
            "usage_speech",
        ),
        "reset_soon": (
            (
                f"还剩 {reset_label}回血。先别开新长对话，等饭点。",
                f"Claude 账号 {reset_label}后回血。再忍忍就有额度了。",
            ),
            "thinking",
            ("peek", "nod", "smug_sway"),
            "quiet_companion",
            "usage_thought",
        ),
        "refilled": (
            (
                f"回血了。Claude 账号额度恢复，可以继续聊。",
                f"额度回来了。Claude 又可以正常营业。",
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
        decision_reason=f"claude_account_usage={status.level}",
        event=f"claude_account_usage_{status.level}",
    )


def _openai_billing_reaction(status: OpenAIBillingStatus, manual: bool = False) -> Reaction:
    line = status.summary_line
    if status.level in {"key_missing", "permission_missing", "unavailable"}:
        return Reaction(
            True,
            line,
            "sleepy",
            "blink",
            "usage_speech" if manual else "usage_thought",
            "fake_sulk",
            decision_reason=f"openai_billing={status.level}",
            event=f"openai_billing_{status.level}",
        )

    if status.level == "over_budget":
        line += " 现在每一次 API 调用都在账本上留下脚印，还是带泥的。"
        mood, action, performance = "sulky", "sleepy_sag", "usage_low_sag"
    elif status.level == "low":
        line += " 剩得不多了。夹夹建议先别让模型写史诗，写小条就行。"
        mood, action, performance = "suspicious", "thinking_tilt", "fake_sulk"
    elif status.level == "watch":
        line += " 还没危险，但已经适合把会计夹叫出来站岗。"
        mood, action, performance = "thinking", "scan", "suspicious_observe"
    elif status.level == "costs_only":
        line += " 要算余额，请在 settings.json 或环境变量里设月预算。"
        mood, action, performance = "thinking", "scan", "quiet_companion"
    else:
        line += " 暂时不像会把钱包咬出洞。"
        mood, action, performance = "innocent", "blink", "quiet_companion"
    return Reaction(
        True,
        line,
        mood,
        action,
        "usage_speech" if manual or status.level in {"low", "over_budget"} else "usage_thought",
        performance,
        decision_reason=f"openai_billing={status.level}",
        event=f"openai_billing_{status.level}",
    )


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
