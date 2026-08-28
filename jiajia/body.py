from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass, replace
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
from typing import ClassVar, NotRequired, TypedDict
from collections.abc import Callable

from .activity import ActivityPolicy, policy_for_frequency
from .actions import ACTION_LABELS, ACTION_MENU_GROUPS, action_label, menu_group_label
from .alive import AliveCue, AliveLayer
from .anim_physics import (
    SquashStretchSpring, ExpressionTweener, easing_for_action,
)
from .animation_resolver import AnimationResolver, ResolvedAnimation
from .animation_manifest import load_animation_manifest
from .animation_player import AnimationCallbacks, AnimationPlayer
from .brain_ollama import OllamaBrain
from .chat import ChatSession, PalChatBrain, build_chat_context, detect_chat_command
from .chat_language import english_status_reaction, status_reaction
from .claude_account_usage import ClaudeAccountUsageMonitor, ClaudeAccountUsageStatus, format_reset_in as format_claude_account_reset_in
from .decorations import DecorationDefinition, load_decoration_manifest
from .mood import (
    FREQUENCY_DEFAULT, FREQUENCY_PRESETS, MoodEngine, frequency_label,
    normalize_frequency,
)
from .claude_status import ClaudeOverview, ClaudeSession, ClaudeStatusMonitor
from .claude_usage import ClaudeUsageMonitor, ClaudeUsageStatus
from .codex_status import CodexStatus, CodexStatusMonitor
from .codex_usage import CodexUsageMonitor, CodexUsageStatus, format_reset_in
from .decision import DecisionEngine, DecisionResult
from .audio_ears import (
    AudioEars, AudioEventDetector, announcement_allowed_for, audio_flavor, audio_line,
)
from .ears import Ears
from .event_log import EventLog
from .eyes import Eyes
from .hardware_status import HardwareSnapshot, HardwareStatusMonitor
from .interruptibility import Interruptibility, assess_interruptibility
from .openai_billing import OpenAIBillingMonitor, OpenAIBillingStatus
from .care import CareEngine
from .particles import ParticleEmitter
from .language import LANGUAGE_OPTIONS, language_label, menu_label, normalize_language, soul_path_for_language
from .performance import PERFORMANCE_PHRASES, phrase_for_reaction
from .performance_run import RunRegistry
from .quiz import (
    QuizPacket,
    QuizSession,
    QuizStore,
    build_report,
    current_question,
    format_report,
    load_quiz_packets,
    record_answer,
    score_packet,
)
from .quiz_safety import validate_quiz_packet
from .pal_geometry import (  # re-exported: scripts and mixins read these here
    ANIM_TICK_MS, ANIM_TICK_SCALE, LERP_TICK_MS,
    BODY_CURVES, BODY_MAIN_CURVES, BODY_START, BROW, CHEEK_BLUSH,
    DECORATION_SCALE, EYE_WHITE, LEFT_BROW_CURVES, LEFT_BROW_START,
    PAL_CANVAS_HEIGHT, PAL_CANVAS_WIDTH, PAL_CENTER_X, PAL_HEIGHT,
    PAL_LOOK_CENTER_X, PAL_LOOK_CENTER_Y, PAL_PAD_X, PAL_PAD_Y, PAL_SCALE,
    PAL_SCALE_CENTER_Y, PAL_SCALE_PIVOT_Y, PAL_SOURCE_HEIGHT, PAL_SOURCE_WIDTH,
    PAL_WIDTH, PUPIL, RIGHT_BROW_CURVES, RIGHT_BROW_START,
    TAIL_CURVES, TAIL_LONG_CURVES, TAIL_LONG_START, TAIL_SHORT_CURVES,
    TAIL_SHORT_START, TAIL_START, TAIL_TIP_EXTENSION, TRANSPARENT, WIRE,
    ActionFrame, ActionFrames,
    _breath_curve, _brow_pose_coords, _clamp, _ease_out_cubic,
    _ease_out_sine, _geometry_position, _geometry_with_size,
    _jitter_frames, _oval_bounds, _oval_center_radius,
    _path_coords, _per_tick, _sample_cubic, _scale_coords, _smoothstep,
    _source_point,
)
from .pal_actions import ActionMixin
from .pal_decor import AppearanceState, DecorMixin
from .pal_idle import IdleMixin
from .pal_panels import PanelMixin
from .pal_canvas import (
    HARDWARE_TINTS, CanvasMixin, _rounded_polygon, _rounded_rect,
    _speech_bubble, _thought_bubble,
)
from .pal_window import (
    GLOBAL_MOUSE_POLL_MS, PAL_HIT_MARGIN_X, PAL_HIT_MARGIN_Y, WindowMixin,
    _WinMonitorInfo, _WinPoint, _WinRect, _button_down, _cursor_position,
    _load_user32,
)
from .pal_motion import (  # re-exported: action layer + GIF renderer read these
    ACTION_ACTING_CUES, ACTION_ANTICIPATION_FRAMES, ACTION_BODY_BEND,
    ACTION_DECORATION_CUES, ACTION_FOLLOW_THROUGH_FRAMES, ACTION_FRAMES,
    ACTION_INNER_GESTURES, ACTION_SELF_PARTICLES, ACTION_SHADOW_ACTIONS,
    ACTION_TAIL_MOTIONS, BLINK_FRAMES, BODY_BEND_NEUTRAL, COMMON_IDLE_ACTIONS,
    GUILTY_DART_SEQUENCE, IDENTITY_STATE_CUES, INNER_GESTURE_FRAMES,
    INNER_NEUTRAL_POSE, LARGE_IDLE_ACTIONS, LOW_STIMULUS_IDLE_ACTIONS,
    MELT_PUDDLE_HOLD_MS, MELT_RECOVERY_FRAMES, MELT_SINK_FRAMES,
    MID_IDLE_ACTIONS, MOVE_ACTION_DURATIONS, MOVE_IDLE_ACTIONS,
    PAPER_PROP_ACTIONS, RARE_IDLE_ACTIONS, SCAN_LOOK_HOLD_MS, SCAN_LOOK_TARGETS,
    SLOW_BLINK_FRAMES, TAIL_HAND_POSE, TAIL_MOTION_FRAMES, TAIL_NEUTRAL_POSE,
    TAIL_OSCILLATIONS, TAIL_POSTURES, TAIL_TIP_ENGAGE, TAIL_TIP_LAG_MS,
    WIGGLE_FRAMES, _POSTURE_ENTER_S, _POSTURE_EXIT_S, _acting_frames,
    _is_neutral_action_frame,
    ActionActingCue, BodyBend, InnerFrame, InnerFrames, InnerPose, PaperPropCue,
    PropFrame, PropFrames, TailFrame, TailFrames, TailPose,
    tail_hand_pose, tail_oscillation_pose, tail_posture_pose,
)
from .prop_shapes import (
    scenario_prop_cue,
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


BUBBLE_WIDTH = 300
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
CODEX_STATUS_POLL_MS = 2500
CODEX_USAGE_POLL_MS = 60_000
AUDIO_POLL_MS = 2500
CLAUDE_STATUS_POLL_MS = 8000
CLAUDE_USAGE_POLL_MS = 120_000
CLAUDE_ACCOUNT_USAGE_POLL_MS = 60_000
OPENAI_BILLING_POLL_MS = 30 * 60 * 1000
HARDWARE_STATUS_POLL_MS = 5000
VISION_FIRST_REFRESH_MS = 5 * 60 * 1000
VISION_REFRESH_MS = 10 * 60 * 1000
VISION_BUSY_RETRY_MS = 5 * 60 * 1000
LINE_BANK_FIRST_MAINTENANCE_MS = 15 * 60 * 1000
LINE_BANK_REFRESH_MS = 6 * 60 * 60 * 1000
LINE_BANK_BUSY_RETRY_MS = 10 * 60 * 1000


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










# ── tail postures ────────────────────────────────────────────────
# A tail doesn't only swing — it POSES. From the cat reference: excited tails
# stand straight up with a quivering tip, playful tails curl into a question
# hook, defensive tails go rigid and bristle. Ease in, hold with a quiver,
# ease out.
#   pose: target 5-channel pose · quiver_amp/freq: tip tremble while held
#   hold_ms: time at full pose



































class JiajiaApp(
    WindowMixin, CanvasMixin, ActionMixin, DecorMixin, PanelMixin, IdleMixin,
):
    def __init__(self, soul: Soul, project_root: Path) -> None:
        self.project_root = project_root
        self.soul = soul
        self.project_root = project_root
        self.pal_stats = load_stats(project_root / "memory" / "stats.json")
        self.pal_stats.total_sessions += 1
        self.pal_stats.last_session_at = time.time()
        self.brain = OllamaBrain(soul, project_root=project_root)
        self.chat_brain = PalChatBrain(soul)
        self.chat_session = ChatSession()
        self.ears = Ears()
        self.audio_ears = AudioEars()
        self._audio_events = AudioEventDetector()
        self._eyes: Eyes | None = None
        self._eyes_model = soul.vision_model
        self.codex_status = CodexStatusMonitor(project_root / "codex_status.json")
        self.codex_usage = CodexUsageMonitor(project_root / "codex_usage_status.json")
        self.hardware_status = HardwareStatusMonitor()
        self.claude_account_usage = ClaudeAccountUsageMonitor(project_root / "claude_account_status.json")
        self.openai_billing = OpenAIBillingMonitor(project_root / "settings.json")
        self._sync_monitor_language()
        self.event_log = EventLog(project_root / "memory" / "event_log.jsonl")
        self.quiz_store = QuizStore(project_root / "jiajia" / "quiz_store.json")
        self._last_quiz_debug = ""
        self.state = PalState()
        self.alive = AliveLayer()
        self.decision = DecisionEngine()
        self.animation_player = AnimationPlayer(load_animation_manifest(project_root / "jiajia" / "animations.yaml"))
        self.animation_resolver = AnimationResolver(set(self.animation_player.manifest.performances))
        self.decorations = load_decoration_manifest(project_root / "jiajia" / "decorations.yaml")
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
        self._sync_monitor_language()
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
        # which run owns which visual channel; see performance_run.py
        self._runs = RunRegistry()
        self._performance_run = None
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
        self.root.after(9000, self._poll_audio)
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
        lang = self.soul.language
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label=menu_label("talk", lang), command=self._open_chat_input)
        self.menu.add_command(label=menu_label("say_something", lang), command=lambda: self._ask_brain("manual"))
        self.menu.add_command(label=menu_label("poke", lang), command=lambda: self._poke(force=True))

        status_menu = tk.Menu(self.menu, tearoff=False)
        status_menu.add_command(label=menu_label("status_overview", lang), command=self._show_status_overview)
        status_menu.add_separator()
        status_menu.add_command(label=menu_label("codex_status", lang), command=self._show_codex_status)
        status_menu.add_command(label=menu_label("codex_usage", lang), command=self._show_codex_usage)
        status_menu.add_command(label=menu_label("claude_status", lang), command=self._show_claude_status)
        status_menu.add_command(label=menu_label("claude_usage", lang), command=self._show_claude_usage)
        status_menu.add_command(label=menu_label("claude_account_usage", lang), command=self._show_claude_account_usage)
        status_menu.add_command(label=menu_label("openai_billing", lang), command=self._show_openai_billing)
        status_menu.add_command(label=menu_label("hardware_status", lang), command=self._show_hardware_status)
        status_menu.add_separator()
        status_menu.add_command(label=menu_label("last_events", lang), command=self._show_last_events)
        status_menu.add_command(label=menu_label("morning_digest", lang), command=self._show_morning_digest)
        self.menu.add_cascade(label=menu_label("status", lang), menu=status_menu)

        action_menu = tk.Menu(self.menu, tearoff=False)
        action_menu.add_command(label=menu_label("boredom_line", lang), command=lambda: self._ask_brain("bored"))
        action_menu.add_command(label=menu_label("cheesy_love", lang), command=self._ask_cheesy_love)
        action_menu.add_command(label=menu_label("quiz", lang), command=lambda: self._offer_absurd_quiz(force=True))
        action_menu.add_separator()
        for group_label, action_ids in ACTION_MENU_GROUPS:
            group_menu = tk.Menu(action_menu, tearoff=False)
            for action_id in action_ids:
                group_menu.add_command(
                    label=action_label(action_id, lang),
                    command=lambda action_id=action_id: self._perform_action(action_id),
                )
            action_menu.add_cascade(label=menu_group_label(group_label, lang), menu=group_menu)
        self.menu.add_cascade(label=menu_label("actions", lang), menu=action_menu)

        mode_menu = tk.Menu(self.menu, tearoff=False)
        identity_menu = tk.Menu(self.menu, tearoff=False)
        identity_menu.add_radiobutton(
            label=menu_label("identity_auto", lang),
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
        mode_menu.add_cascade(label=menu_label("identity", lang), menu=identity_menu)
        language_menu = tk.Menu(self.menu, tearoff=False)
        for language, label in LANGUAGE_OPTIONS:
            language_menu.add_radiobutton(
                label=label,
                variable=self._language_var,
                value=language,
                command=lambda language=language: self._set_language(language),
            )
        mode_menu.add_cascade(label=menu_label("language", lang), menu=language_menu)
        freq_menu = tk.Menu(self.menu, tearoff=False)
        for key, _mult in FREQUENCY_PRESETS:
            freq_menu.add_radiobutton(
                label=frequency_label(key, self.soul.language),
                variable=self._freq_var,
                value=key,
                command=lambda k=key: self._set_frequency(k),
            )
        mode_menu.add_cascade(label=menu_label("activity", lang), menu=freq_menu)
        tail_menu = tk.Menu(self.menu, tearoff=False)
        tail_menu.add_radiobutton(
            label=menu_label("tail_short", lang),
            variable=self._tail_mode_var,
            value="short",
            command=lambda: self._set_tail_mode("short"),
        )
        tail_menu.add_radiobutton(
            label=menu_label("tail_long", lang),
            variable=self._tail_mode_var,
            value="long",
            command=lambda: self._set_tail_mode("long"),
        )
        mode_menu.add_cascade(label=menu_label("tail_menu", lang), menu=tail_menu)
        mode_menu.add_separator()
        mode_menu.add_command(label=menu_label("quiet_30", lang), command=lambda: self._quiet_for(30 * 60))
        mode_menu.add_checkbutton(label=menu_label("focus_mode", lang), variable=self._focus_var, command=self._toggle_focus_mode)
        mode_menu.add_command(label=menu_label("resume", lang), command=self._resume_auto_reactions)
        self.menu.add_cascade(label=menu_label("mode", lang), menu=mode_menu)

        debug_menu = tk.Menu(self.menu, tearoff=False)
        preview_menu = tk.Menu(debug_menu, tearoff=False)
        for performance_id in sorted(self.animation_player.manifest.performances):
            preview_menu.add_command(
                label=performance_id,
                command=lambda performance_id=performance_id: self._preview_performance(performance_id),
            )
        debug_menu.add_cascade(label=menu_label("animation_preview", lang), menu=preview_menu)
        debug_menu.add_separator()
        debug_menu.add_command(label=menu_label("scripted_demo", lang), command=self._run_scripted_demo)
        debug_menu.add_command(label=menu_label("debug_decision", lang), command=self._show_last_decision_debug)
        debug_menu.add_command(label=menu_label("debug_chat_context", lang), command=self._show_last_chat_context)
        debug_menu.add_command(label=menu_label("debug_animation", lang), command=self._show_last_animation_debug)
        debug_menu.add_command(label=menu_label("debug_alive", lang), command=self._show_alive_debug)
        debug_menu.add_command(label=menu_label("debug_identity", lang), command=self._show_identity_debug)
        self.menu.add_cascade(label=menu_label("developer", lang), menu=debug_menu)

        self.menu.add_separator()
        self.menu.add_command(label=menu_label("quit", lang), command=self._quit)

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
        reaction = status_reaction("status_overview", self._build_chat_context())
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
        if key == "hyper":
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

    def _localized_status_reaction(self, command: str, fallback: Reaction) -> Reaction:
        """An automatic status broadcast in the pal's own language.

        English mode reuses the wording written for the chat status commands, so
        there is one English translation of each status level rather than two.
        The event name and bubble come from the fallback because the broadcast
        path uses them for logging and de-duplication, and those must not change
        when the language does.
        """
        if not normalize_language(self.soul.language).startswith("en"):
            return fallback
        try:
            english = english_status_reaction(command, self._build_chat_context())
        except Exception:
            return fallback
        if english is None or not english.line:
            return fallback
        return replace(english, event=fallback.event, bubble=fallback.bubble)

    def _sync_monitor_language(self) -> None:
        """Status monitors build their own broadcast text, so they need the language."""
        language = self.soul.language
        for name in ("codex_usage", "claude_account_usage", "claude_usage", "openai_billing"):
            monitor = getattr(self, name, None)
            if monitor is not None:
                monitor.language = language

    def _reload_language_runtime(self, language: str) -> None:
        package_root = self.project_root / "jiajia"
        soul = load_soul(soul_path_for_language(package_root, language))
        soul.language = normalize_language(language)
        self.soul = soul
        self.brain = OllamaBrain(soul, project_root=self.project_root)
        self.chat_brain = PalChatBrain(soul)
        self.chat_session = ChatSession()
        self._care_engine = CareEngine(language=soul.language)
        self._eyes_model = soul.vision_model
        self._eyes = None
        self.root.title(soul.name)
        self._identity_var.set(self._valid_identity_id(self._identity_var.get()))
        self._sync_monitor_language()
        self._install_menu()
        if normalize_language(language) == "en":
            self._clear_non_costume_decorations()
        else:
            self._refresh_identity_decorations()














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












    def _pal_source_point(self, x: float, y: float) -> tuple[float, float]:
        return self._actor_point(*_source_point(x, y))



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
        return normalize_frequency(data.get("frequency") or FREQUENCY_DEFAULT)

    def _save_frequency_setting(self, key: str) -> None:
        self._save_setting("frequency", key)

    def _save_language_setting(self, language: str) -> None:
        self._save_setting("language", normalize_language(language))




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








    def _show_codex_status(self) -> None:
        status = self.codex_status.sample()
        if status.status == "unknown":
            line = _pick_status_fragment(_CODEX_UNKNOWN_LINES, self._recent_codex_status_fragments)
            self.show_bubble(line, kind="codex_thought")
            return
        reaction = self._localized_status_reaction(
            "status_codex",
            _codex_status_reaction(status, self._recent_codex_status_fragments, manual=True),
        )
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

    _POKE_ESCALATION: ClassVar[list[tuple[int, str]]] = [
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
        self.pal_stats.record_poke(self._poke_count)
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
            audio=self.audio_ears.sample(),
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
            reaction = self._localized_status_reaction(
                "status_codex",
                _codex_status_reaction(status, self._recent_codex_status_fragments),
            )
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
            self._apply_reaction(
                self._localized_status_reaction("status_usage", _codex_usage_reaction(status))
            )
        self.root.after(self._adaptive_poll_ms(CODEX_USAGE_POLL_MS), self._poll_codex_usage)

    def _should_log_codex_usage(self, status: CodexUsageStatus) -> bool:
        if status.level in {"unavailable", "normal"} or status.stale:
            return False
        return bool(status.event_id and status.event_id != self._logged_codex_usage_event)

    def _poll_audio(self) -> None:
        """Hear the room and, when something actually changed, say so once.

        The detector owns the signal judgement (sustains, cooldowns, one event
        at a time); this owns the manners: nothing while auto reactions are
        paused, nothing in a quiet tier, nothing while a bubble is up or the
        brain is talking — and nothing at all during a call, because a bubble
        popping up mid screen-share is an incident, not a companion.
        """
        context = self.audio_ears.sample()
        ear = self.ears.sample()
        event = self._audio_events.observe(context, time.time(), ear.app_category)
        if event and self._should_announce_audio(ear.app_category):
            flavor = self._audio_events.session_flavor
            line = audio_line(event, flavor, self.soul.language)
            if line:
                mood, action = {
                    "audio_started": ("smirk", "curious_lean"),
                    "audio_loud": ("suspicious", "peek"),
                    "audio_marathon": ("thinking", "thinking_tilt"),
                    "audio_ended": ("thinking", "blink"),
                }.get(event, ("smirk", "blink"))
                self._apply_reaction(
                    Reaction(True, line, mood, action, "thought", "", event=event)
                )
        self.root.after(self._adaptive_poll_ms(AUDIO_POLL_MS), self._poll_audio)

    def _should_announce_audio(self, app_category: str) -> bool:
        if not announcement_allowed_for(app_category):
            return False
        if self._auto_reactions_paused():
            return False
        if not self._activity_policy().ambient_enabled:
            return False
        return not (self.state.brain_busy or self._bubble_items)

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
        self._apply_reaction(
            self._localized_status_reaction(
                "status_usage", _codex_usage_reaction(status, manual=True)
            ),
            force=True,
        )

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
        self._apply_reaction(
            self._localized_status_reaction(
                "status_claude_usage", _claude_usage_reaction(status, manual=True)
            ),
            force=True,
        )

    def _poll_claude_account_usage(self) -> None:
        status = self.claude_account_usage.sample()
        self._last_claude_account_usage_status = status
        if self._should_log_claude_account_usage(status):
            self._logged_claude_account_usage_event = status.event_id
            self._log_event("claude_account_usage", status.level, _usage_event_level(status.level), status.summary_line)
        if self._should_announce_claude_account_usage(status):
            self._last_claude_account_usage_event = status.event_id
            self._last_claude_account_usage_announcement_at = time.time()
            self._apply_reaction(
                self._localized_status_reaction(
                    "status_claude_usage", _claude_account_usage_reaction(status)
                )
            )
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
        self._apply_reaction(
            self._localized_status_reaction(
                "status_claude_usage", _claude_account_usage_reaction(status, manual=True)
            ),
            force=True,
        )

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
                reaction = self._localized_status_reaction(
                    "status_openai_billing", _openai_billing_reaction(status, manual=True)
                )
                reaction.event = f"manual_{reaction.event or 'openai_billing'}"
                self.status_queue.put(reaction)
                return
            if self._should_announce_openai_billing(status):
                self._last_openai_billing_event = status.event_id
                self._last_openai_billing_announcement_at = time.time()
                self.status_queue.put(
                    self._localized_status_reaction(
                        "status_openai_billing", _openai_billing_reaction(status)
                    )
                )

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
            self._apply_reaction(
                self._localized_status_reaction(
                    "status_hardware", _hardware_status_reaction(snapshot)
                )
            )
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
        self._apply_reaction(
            self._localized_status_reaction(
                "status_hardware", _hardware_status_reaction(snapshot, manual=True)
            ),
            force=True,
        )

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
        self.show_bubble(
            self.event_log.digest(mark_read=True, language=self.soul.language),
            milliseconds=11000,
            kind="speech",
        )

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
    _MOOD_EXPRESSION: ClassVar[dict[str, tuple[str, str, bool]]] = {
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
        self._last_visual_plan = plan
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
        plan = getattr(self, "_last_visual_plan", None)
        run = self._runs.begin(
            name,
            priority=getattr(plan, "priority", 0),
            interruptible=getattr(plan, "interruptible", True),
            lifecycle=getattr(plan, "lifecycle", ""),
        )
        self._performance_run = run

        def owned(*channels: str):
            """Wrap a channel write so a superseded run cannot perform it."""
            def decorate(fn):
                def guarded(*args, **kwargs):
                    if not self._runs.is_current(run):
                        return None
                    self._runs.claim(run, *channels)
                    return fn(*args, **kwargs)
                return guarded
            return decorate

        # _perform_action drives several channels at once, which is exactly why
        # a stale callback used to be able to reach so far into a new phrase
        callbacks = AnimationCallbacks(
            after=lambda delay, callback: self.root.after(delay, callback),
            action=owned("body", "tail", "inner", "bend", "prop")(self._perform_action),
            bubble=self._show_reaction_line,
            eyes=owned("face")(self._set_eye_pose),
            brows=owned("face")(self._set_brow_pose),
            reset_expression=owned("face")(self._reset_expression_pose),
            stop_cursor_follow=self._stop_mouse_follow,
            duration_of=self._animation_duration_ms,
            still_current=lambda: self._runs.is_current(run),
            scenario_prop=owned("prop")(self._raise_scenario_prop),
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

    def _raise_scenario_prop(self, name: str) -> None:
        """Bring in a prop the action does not carry by default.

        Props were unbound from actions because a prop attached to every action
        does the acting. This is the other half: a scenario that has actually
        earned one names it, and only then does it appear.
        """
        cue = scenario_prop_cue(name)
        if cue:
            self._start_action_prop(cue, name)

    def _cancel_performance_phrase(self) -> None:
        """Stop the current phrase and undo only the channels it still owns.

        This used to cancel the queued callbacks, the expression and the inner
        gesture, and leave the body, window move, tail, bend and prop it had
        started running underneath the next performance. It also could not tell
        whether a channel had since been taken over by a newer run, so tearing
        one down risked damaging the phrase that replaced it.
        """
        for after_id in self._performance_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._performance_after.clear()

        run = getattr(self, "_performance_run", None)
        channels = self._runs.cancel(run) if run is not None else set()
        self._performance_run = None
        if run is None:
            # no run recorded (older path): fall back to the previous behaviour
            self._cancel_expression_after(reset=True)
            self._cancel_inner_gesture(reset=True)
            return

        if "face" in channels:
            self._cancel_expression_after(reset=True)
        if "inner" in channels:
            self._cancel_inner_gesture(reset=True)
        if "body" in channels:
            self._cancel_large_action()
        if "window" in channels:
            self._cancel_window_move()
        if "tail" in channels:
            self._cancel_tail_wag(reset=False)
        if "bend" in channels:
            self._cancel_bend()
        if "prop" in channels:
            self._clear_action_prop()





















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


























    def set_chin_mode(self, mode: str) -> None:
        """Set chin animation mode: idle|talk|chew|yawn|mumble|cover|wave|point|fidget|think|sulk."""
        self._chin_mode = mode
        if mode == "talk":
            # reset syllable state for fresh speech
            self._chin_syllable_phase = 0.0
            self._chin_syllable_amp = 1.0
            self._chin_pause_timer = 0




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
    _EYE_MAP: ClassVar[dict[str, tuple[float, float, float, float]]] = {
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
    _BROW_MAP: ClassVar[dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]] = {
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





    def _animate(self) -> None:
        self._anim_tick += 1
        # topmost decays on Windows (newer topmost windows insert above, shell
        # events demote); re-assert every ~3s so the pet stays a desktop pet
        if self._anim_tick % 90 == 0:
            self._assert_windows_on_top()
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
                if self._anim_tick % 300 == 0 and self.mood.energy > 0.6 and random.random() < 0.15:
                    gesture = random.choice(["inner_wave", "inner_fidget", "inner_thumbs_up"])
                    self._run_inner_gesture(gesture)
        # idle micro-expressions: small gaze checks often enough to feel alive, not noisy.
        if self._anim_tick % 90 == 0 and not self._large_action_running and self._doze_stage == 0 and random.random() < 0.25:
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















    def _pointer_look_target(self) -> tuple[float, float]:
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        local_x = pointer_x - self.root.winfo_x()
        local_y = pointer_y - self.root.winfo_y()
        dx = _clamp((local_x - PAL_LOOK_CENTER_X) / max(1, PAL_WIDTH) * 7.0, -3.4, 3.4)
        dy = _clamp((local_y - PAL_LOOK_CENTER_Y) / max(1, PAL_HEIGHT) * 7.0, -2.4, 2.4)
        return dx, dy








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
        # raise the pal WITH its bubble — lifting only the bubble is how the
        # bubble ended up floating over other windows while the pal stayed
        # buried behind them
        self._assert_windows_on_top()

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
        """Bob the thought-trail dots. Stale-proof by construction.

        These three dots (radii 5 / 3.5 / 2.2, reticking every 95ms) are the
        only blinking three-element drawing in the app, so any leftover copy of
        them inside a later bubble means this animator outlived its items. If a
        dot id is ever dead, stop the whole animation rather than keep poking
        the canvas — a silently dying frame is invisible; a surviving orphan
        blinks in the corner of the next bubble.
        """
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
            try:
                self.bubble_canvas.coords(
                    item,
                    cx - animated_radius,
                    animated_y - animated_radius,
                    cx + animated_radius,
                    animated_y + animated_radius,
                )
            except tk.TclError:
                self._thought_dot_items.clear()
                self._thought_dot_base.clear()
                self._thought_dot_after = None
                return
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
                "回血了。Codex 又能继续装作很能干。",
                "额度回来了。理性也可以顺便回来一点。",
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
                "回血了。Claude 账号额度恢复，可以继续聊。",
                "额度回来了。Claude 又可以正常营业。",
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
    return bool(len(stripped) <= 4 and not any(char.isspace() for char in stripped))


def _bubble_page_duration(text: str, requested_ms: int) -> int:
    readable_chars = len(text.replace("\n", ""))
    line_count = max(1, text.count("\n") + 1)
    natural_ms = BUBBLE_PAGE_MIN_MS + readable_chars * BUBBLE_PAGE_CHAR_MS + (line_count - 1) * 260
    target_ms = max(requested_ms, natural_ms)
    return max(BUBBLE_PAGE_MIN_MS, min(BUBBLE_PAGE_MAX_MS, target_ms))



















