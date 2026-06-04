from __future__ import annotations

import ctypes
from pathlib import Path
import json
import math
import queue
import random
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

from .actions import ACTION_LABELS, ACTION_MENU_GROUPS
from .brain_ollama import OllamaBrain
from .mood import MoodEngine, FREQUENCY_PRESETS, FREQUENCY_DEFAULT
from .claude_status import ClaudeOverview, ClaudeStatusMonitor
from .codex_status import CodexStatus, CodexStatusMonitor
from .ears import Ears
from .eyes import Eyes
from .soul import Soul
from .state import PalState, Reaction


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
CLAUDE_STATUS_POLL_MS = 8000
LERP_TICK_MS = 18
VISION_REFRESH_MS = 45_000
AMBIENT_MIN_MS = 18_000
AMBIENT_MAX_MS = 45_000
AMBIENT_COOLDOWN_SECONDS = 50
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


class PaperclipPalApp:
    def __init__(self, soul: Soul, project_root: Path) -> None:
        self.soul = soul
        self.project_root = project_root
        self.brain = OllamaBrain(soul, project_root=project_root)
        self.ears = Ears()
        self.eyes = Eyes(model=soul.vision_model)
        self.codex_status = CodexStatusMonitor(project_root / "codex_status.json")
        self.state = PalState()
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
        self._is_blinking = False
        self._mouse_follow_after: str | None = None
        self._mouse_follow_until = 0.0
        self._mouse_follow_cooldown_until = 0.0
        self._pal_scale = (1.0, 1.0)
        self._rebound_after: str | None = None
        self._action_offset = (0.0, 0.0)
        self._large_action_after: str | None = None
        self._large_action_running = False
        self._brain_wait_after: str | None = None
        self._brain_wait_step = 0
        self._bubble_items: list[int] = []
        self._bubble_after: str | None = None
        self._thought_dot_items: list[int] = []
        self._thought_dot_base: list[tuple[float, float, float]] = []
        self._thought_dot_phase = 0
        self._thought_dot_after: str | None = None
        self._last_codex_status_event = ""
        self._last_codex_status: CodexStatus = CodexStatus()
        self._brain_thread: threading.Thread | None = None
        self._line_bank_thread: threading.Thread | None = None
        self._vision_thread: threading.Thread | None = None
        self._last_ambient_signature = ""
        self.claude_monitor = ClaudeStatusMonitor()
        self._last_claude_event = ""
        self._last_claude_alive_pids: set[int] = set()
        self.mood = MoodEngine()
        initial_frequency = self._load_frequency_setting()
        self.mood.set_frequency(initial_frequency)
        self._freq_var = tk.StringVar(value=initial_frequency)
        self._micro_after: str | None = None
        self._companion_after: str | None = None
        self._place_initially()
        self._hide_from_taskbar()
        self._draw_pal()
        self._bind_events()
        self._install_menu()
        self.root.after(50, self._animate)
        self.root.after(120, self._poll_global_mouse)
        self.root.after(100, self._poll_brain)
        self.root.after(1500, self._poll_codex_status)
        self.root.after(3500, self._poll_claude_status)
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
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

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
        c.create_line(
            *_scale_coords(_path_coords(LEFT_BROW_START, LEFT_BROW_CURVES)), smooth=False,
            width=30 * PAL_SCALE, fill=BROW, capstyle=tk.ROUND,
            tags=("pal", "brow"),
        )
        c.create_line(
            *_scale_coords(_path_coords(RIGHT_BROW_START, RIGHT_BROW_CURVES)), smooth=False,
            width=30 * PAL_SCALE, fill=BROW, capstyle=tk.ROUND,
            tags=("pal", "brow"),
        )

    def _reset_pal_geometry(self) -> None:
        look = self._pupil_look
        self.canvas.delete("pal")
        self._pupil_bounds.clear()
        self._pal_scale = (1.0, 1.0)
        self._action_offset = (0.0, 0.0)
        self._bob_x = 0.0
        self._bob_y = 0.0
        self._draw_pal()
        self._pupil_look = look
        self._set_pupil_pose(*look, blink_scale=1.0)

    def _bind_events(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._show_context_menu)
        self.canvas.bind("<Double-Button-1>", lambda _event: self._poke(force=True))

    def _install_menu(self) -> None:
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Say something", command=lambda: self._ask_brain("manual"))
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
        self.menu.add_command(label="Codex status", command=self._show_codex_status)
        self.menu.add_command(label="Claude 状态", command=self._show_claude_status)
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
        self.menu.add_command(label="Quit", command=self.root.destroy)

    def _show_context_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

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

    def _load_frequency_setting(self) -> str:
        try:
            data = json.loads((self.project_root / "settings.json").read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return FREQUENCY_DEFAULT
        key = str(data.get("frequency") or FREQUENCY_DEFAULT)
        valid = {label for label, _mult in FREQUENCY_PRESETS}
        return key if key in valid else FREQUENCY_DEFAULT

    def _save_frequency_setting(self, key: str) -> None:
        path = self.project_root / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
        except (OSError, json.JSONDecodeError):
            data = {}
        data["frequency"] = key
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _schedule_micro(self) -> None:
        interval = self.mood.micro_interval_ms()
        self._micro_after = self.root.after(interval, self._micro_tick)

    def _micro_tick(self) -> None:
        self._micro_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            action = self.mood.pick_micro_behavior()
            if action:
                self._perform_action(action)
        self._schedule_micro()

    def _schedule_companion(self) -> None:
        self._companion_after = self.root.after(self.mood.companion_interval_ms(), self._companion_tick)

    def _companion_tick(self) -> None:
        self._companion_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            multiplier = self.mood.frequency_multiplier
            if random.random() < min(0.86, 0.18 * multiplier):
                self._start_mouse_follow(random.randint(850, 1700))
            if random.random() < min(0.90, 0.20 * multiplier):
                self._perform_action(random.choice(("blink", "peek", "scan", "nod", "wiggle", "thinking_tilt", "smug_sway")))
            if (
                multiplier >= 4.0
                and not self._bubble_items
                and self.state.can_speak(self.mood.ambient_cooldown_seconds())
                and random.random() < 0.24
            ):
                self._ask_brain("ambient")
        self._schedule_companion()

    def _show_codex_status(self) -> None:
        status = self.codex_status.sample()
        if status.status == "unknown":
            self.show_bubble("我还没有收到 Codex 状态。很神秘，也很像没接线。", kind="thought")
            return
        summary = f"：{status.summary}" if status.summary else ""
        stale = " 但这条有点旧了。" if status.stale else ""
        self.show_bubble(f"Codex 现在是 {status.status}{summary}.{stale}", kind="thought")

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
            self.root.geometry(f"+{x}+{y}")
            if self._bubble_items:
                self._position_bubble()
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

    def _ask_brain(self, event: str) -> None:
        if self.state.brain_busy:
            self._perform_action("thinking_tilt")
            return
        self.state.brain_busy = True
        context = self._context(event)
        self._start_brain_wait_animation()

        def worker() -> None:
            reaction = self.brain.react(event, context)
            self.queue.put(reaction)

        self._brain_thread = threading.Thread(target=worker, daemon=True)
        self._brain_thread.start()

    def _context(self, event: str) -> dict[str, object]:
        ear = self.ears.sample().as_dict()
        eye = self.eyes.sample().as_dict()
        codex = self.codex_status.sample().as_dict()
        environment_tags = sorted(
            set(_as_str_list(ear.get("behavior_tags"))) | set(_as_str_list(eye.get("screen_tags")))
        )
        return {
            "event": event,
            "mood": self.state.mood,
            "recent_lines": self.state.recent_lines[-4:],
            "environment_tags": environment_tags,
            **ear,
            **eye,
            **codex,
        }

    def _poll_brain(self) -> None:
        try:
            while True:
                reaction = self.queue.get_nowait()
                self.state.brain_busy = False
                self._stop_brain_wait_animation()
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
        if self._should_announce_codex_status(status):
            reaction = _codex_status_reaction(status)
            self._last_codex_status_event = status.event_id
            self._apply_reaction(reaction)
        self.root.after(CODEX_STATUS_POLL_MS, self._poll_codex_status)

    def _should_announce_codex_status(self, status: CodexStatus) -> bool:
        if status.status in {"unknown", "idle"} or status.stale:
            return False
        if not status.event_id or status.event_id == self._last_codex_status_event:
            return False
        if self.state.brain_busy or self._bubble_items:
            return False
        cooldown = 4 if status.status in {"thinking", "reading", "working", "editing", "running", "testing", "reconnecting"} else 8
        return self.state.can_speak(cooldown)

    def _poll_claude_status(self) -> None:
        overview = self.claude_monitor.sample()
        if overview.event_id != self._last_claude_event:
            reaction = self._claude_change_reaction(overview)
            self._last_claude_event = overview.event_id
            if reaction and not self.state.brain_busy and not self._bubble_items:
                self._apply_reaction(reaction)
        self.root.after(CLAUDE_STATUS_POLL_MS, self._poll_claude_status)

    def _claude_change_reaction(self, overview: ClaudeOverview) -> Reaction | None:
        current_pids = {s.pid for s in overview.sessions if s.alive}
        new_pids = current_pids - self._last_claude_alive_pids
        gone_pids = self._last_claude_alive_pids - current_pids
        self._last_claude_alive_pids = current_pids

        new_sessions = [s for s in overview.sessions if s.pid in new_pids]
        if new_sessions:
            s = new_sessions[0]
            return Reaction(True, f"{s.label()} 在 {s.project} 开工了。希望效率比你高。", "smirk", "scan", "thought")

        if gone_pids:
            return Reaction(True, "一个 Claude 会话收工了。不知道是完成了还是放弃了。", "thinking", "blink", "thought")

        active = [s for s in overview.sessions if s.alive and s.activity not in ("idle", "offline")]
        if active:
            s = active[0]
            return None
        return None

    def _show_claude_status(self) -> None:
        overview = self.claude_monitor.sample()
        self.show_bubble(overview.summary_line(), kind="thought")

    def _apply_reaction(self, reaction: Reaction) -> None:
        self.state.mood = reaction.mood
        self.mood.push_mood(reaction.mood)
        self._perform_action(reaction.action)
        if reaction.should_say and reaction.line:
            self.show_bubble(reaction.line, kind=reaction.bubble)
            self.state.remember_line(reaction.line)

    def _perform_action(self, action: str) -> None:
        if not action or action == "idle":
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

    def _schedule_idle(self, first: bool = False) -> None:
        if first:
            delay = 10_000
        else:
            low = max(8, self.soul.idle_min_seconds)
            high = max(low, self.soul.idle_max_seconds)
            delay = random.randint(low, high) * 1000
        self.root.after(delay, self._idle_tick)

    def _idle_tick(self) -> None:
        if self.state.can_speak(self.soul.cooldown_seconds):
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
        context = self._context("ambient")
        if self._should_ambient_react(context):
            self._ask_brain("ambient")
        self._schedule_ambient()

    def _should_ambient_react(self, context: dict[str, object]) -> bool:
        cooldown = min(AMBIENT_COOLDOWN_SECONDS, self.mood.ambient_cooldown_seconds())
        if self._bubble_items or self.state.brain_busy or not self.state.can_speak(cooldown):
            return False
        tags = set(_as_str_list(context.get("environment_tags")))
        if not tags or "privacy_sensitive" in tags or "app_meeting_or_chat" in tags:
            return False
        if str(context.get("activity_level") or "") == "away":
            return False
        interesting = {
            "rapid_switching",
            "idle_staring",
            "long_focus",
            "blank_document",
            "todo_visible",
            "browser_research",
            "file_sorting",
            "deep_work",
            "app_codex",
            "app_editor",
            "app_terminal",
            "app_file_manager",
        }
        matched = sorted(tags & interesting)
        if not matched:
            return False
        signature = f"{context.get('app_category')}|{context.get('active_process')}|{','.join(matched[:3])}"
        if signature == self._last_ambient_signature:
            return False
        chance = 0.55 if {"rapid_switching", "idle_staring", "blank_document", "todo_visible"} & tags else 0.28
        chance = min(0.88, chance * self.mood.ambient_chance_multiplier())
        if random.random() > chance:
            return False
        self._last_ambient_signature = signature
        return True

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
        self.canvas.move("pal", sway_x - self._bob_x, next_y - self._bob_y)
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
        self.canvas.move("pal", dx - previous_x, dy - previous_y)
        self._action_offset = (dx, dy)

    def _set_pal_scale(self, sx: float, sy: float) -> None:
        previous_x, previous_y = self._pal_scale
        if previous_x == 0 or previous_y == 0:
            previous_x, previous_y = 1.0, 1.0
        self.canvas.scale(
            "pal",
            PAL_CENTER_X,
            PAL_SCALE_CENTER_Y,
            sx / previous_x,
            sy / previous_y,
        )
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
        if not self._dragging and not self._rebound_after and not self._large_action_running:
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

    def _set_pupil_pose(self, dx: float, dy: float, blink_scale: float = 1.0) -> None:
        for item, bounds in self._pupil_bounds.items():
            x1, y1, x2, y2 = bounds
            cx = (x1 + x2) / 2 + dx + self._bob_x
            cy = (y1 + y2) / 2 + dy + self._bob_y
            rx = (x2 - x1) / 2
            ry = max(0.8, (y2 - y1) / 2 * blink_scale)
            self.canvas.coords(item, cx - rx, cy - ry, cx + rx, cy + ry)

    def show_bubble(self, text: str, milliseconds: int = 3200, kind: str = "speech") -> None:
        self._clear_bubble()
        font_spec = THOUGHT_FONT if kind == "thought" else BUBBLE_FONT
        font = tkfont.Font(family=font_spec[0], size=font_spec[1], slant=font_spec[2] if len(font_spec) > 2 else "roman")
        text_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
        pages = _paginate_bubble_text(text, text_width, font)
        self._show_bubble_page(pages, 0, milliseconds, kind)

    def _show_bubble_page(self, pages: list[str], index: int, milliseconds: int, kind: str) -> None:
        self._bubble_after = None
        self._clear_bubble(cancel_after=False)
        if index >= len(pages):
            return
        is_thought = kind == "thought"
        font_spec = THOUGHT_FONT if is_thought else BUBBLE_FONT
        font = tkfont.Font(family=font_spec[0], size=font_spec[1], slant=font_spec[2] if len(font_spec) > 2 else "roman")
        text_width = BUBBLE_WIDTH - BUBBLE_PADDING_X * 2
        wrapped_text = pages[index]
        line_count = max(1, wrapped_text.count("\n") + 1)
        line_height = font.metrics("linespace")
        tail_space = 30 if is_thought else 18
        bubble_height = max(
            BUBBLE_MIN_HEIGHT,
            BUBBLE_PADDING_Y * 2 + line_height * line_count + tail_space,
        )
        self.bubble_canvas.configure(width=BUBBLE_WIDTH, height=bubble_height)
        self._position_bubble(bubble_height)
        self.bubble_root.deiconify()
        self.bubble_root.lift()

        x1, y1 = 4, 4
        x2 = BUBBLE_WIDTH - 4
        y2 = bubble_height - tail_space
        if is_thought:
            thought_items = _thought_bubble(
                self.bubble_canvas,
                x1,
                y1,
                x2,
                y2,
                fill="#f7f5fb",
                outline="#c9c2d7",
                shadow="#c6bfce",
            )
            self._bubble_items.extend(thought_items)
            self._thought_dot_items = thought_items[-3:]
            self._thought_dot_base = [_oval_center_radius(self.bubble_canvas.coords(item)) for item in self._thought_dot_items]
            self._start_thought_dots()
        else:
            tail = (
                BUBBLE_WIDTH / 2 - 12,
                y2,
                BUBBLE_WIDTH / 2 + 12,
                y2,
                BUBBLE_WIDTH / 2,
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
                    fill="#fdfdfd",
                    outline="#d4dee8",
                    shadow="#c4ccd4",
                )
            )
        self._bubble_items.append(
            self.bubble_canvas.create_text(
                BUBBLE_WIDTH / 2,
                y1 + BUBBLE_PADDING_Y + line_height * line_count / 2,
                text=wrapped_text,
                width=text_width,
                fill="#33293a" if is_thought else "#202932",
                font=font_spec,
                justify="center",
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

    def _position_bubble(self, bubble_height: int | None = None) -> None:
        self.root.update_idletasks()
        height = bubble_height
        if height is None:
            height = int(float(self.bubble_canvas.cget("height")))
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = self.root.winfo_x() + PAL_CENTER_X - BUBBLE_WIDTH / 2
        y = self.root.winfo_y() + PAL_PAD_Y - height - BUBBLE_GAP
        x = min(max(8, x), max(8, screen_w - BUBBLE_WIDTH - 8))
        if y < 8:
            y = min(screen_h - height - 8, self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + BUBBLE_GAP)
        self.bubble_root.geometry(f"{BUBBLE_WIDTH}x{height}+{round(x)}+{round(y)}")

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


def _codex_status_reaction(status: CodexStatus) -> Reaction:
    summary = f"：{status.summary}" if status.summary else ""
    if status.status == "thinking":
        return Reaction(True, f"Codex 在想{summary}。它现在看起来像在脑内翻文件夹。", "thinking", "thinking_tilt", "thought")
    if status.status == "reading":
        return Reaction(True, f"Codex 正在读上下文{summary}。先别催，它还在假装记性很好。", "thinking", "scan", "thought")
    if status.status == "working":
        return Reaction(True, f"Codex 正在认真工作{summary}。我会暂时假装不监督。", "thinking", "nod", "thought")
    if status.status == "editing":
        return Reaction(True, f"Codex 正在改文件{summary}。小心，它现在手里有补丁。", "focused", "patrol", "thought")
    if status.status in {"running", "running_command"}:
        return Reaction(True, f"它在跑命令{summary}。现在把紧张交给终端。", "thinking", "scan", "thought")
    if status.status == "testing":
        return Reaction(True, f"Codex 在检查结果{summary}。希望测试不要突然拥有个性。", "thinking", "thinking_tilt", "thought")
    if status.status == "reconnecting":
        return Reaction(True, f"Codex 好像在重连{summary}。网络也有逃避型人格。", "suspicious", "scan", "thought")
    if status.status == "disconnected":
        return Reaction(True, f"Codex 暂时断线了{summary}。夹夹先小声站岗。", "sleepy", "hide", "thought")
    if status.status == "waiting_user":
        return Reaction(True, f"Codex 好像在等你{summary}。我只是一个小文具，我不催。", "smirk", "bob", "speech")
    if status.status == "done":
        return Reaction(True, f"Codex 回来了{summary}。看起来它假装一切都在掌控中。", "smirk", "bob", "speech")
    if status.status == "error":
        return Reaction(True, f"嗯，Codex 遇到报错{summary}。电脑也会表达不同意。", "thinking", "blink", "thought")
    if status.status == "blocked":
        return Reaction(True, f"Codex 卡住了{summary}。这听起来很像需要人类点头。", "thinking", "blink", "speech")
    return Reaction(False)


def _paginate_bubble_text(text: str, max_width: int, font: tkfont.Font) -> list[str]:
    lines = _wrap_bubble_lines(text, max_width, font)
    return [
        "\n".join(lines[index:index + BUBBLE_MAX_LINES])
        for index in range(0, len(lines), BUBBLE_MAX_LINES)
    ] or ["..."]


def _wrap_bubble_lines(text: str, max_width: int, font: tkfont.Font) -> list[str]:
    lines: list[str] = []
    paragraphs = text.strip().splitlines() or [text.strip()]
    for paragraph in paragraphs:
        current = ""
        for char in paragraph:
            candidate = current + char
            if not current or font.measure(candidate) <= max_width:
                current = candidate
                continue

            lines.append(current.rstrip())
            current = char.lstrip()

        if current:
            lines.append(current.rstrip())

    return lines or ["..."]


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


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


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
    shadow: str,
) -> list[int]:
    items = []
    tx1, ty1, tx2, ty2, tx3, ty3 = tail
    items.append(
        _rounded_polygon(
            canvas,
            x1 + 3,
            y1 + 4,
            x2 + 3,
            y2 + 4,
            radius,
            tx1 + 3,
            ty1 + 4,
            tx2 + 3,
            ty2 + 4,
            tx3 + 3,
            ty3 + 4,
            fill=shadow,
            outline="",
            stipple="gray50",
        )
    )
    items.append(
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
    )
    return items


def _thought_bubble(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    fill: str,
    outline: str,
    shadow: str,
) -> list[int]:
    items = [
        _rounded_rect(canvas, x1 + 3, y1 + 4, x2 + 3, y2 + 4, 16, fill=shadow, outline="", stipple="gray50"),
        _rounded_rect(canvas, x1, y1, x2, y2, 16, fill=fill, outline=outline),
    ]
    dots = (
        (BUBBLE_WIDTH / 2 + 8, y2 + 8, 5),
        (BUBBLE_WIDTH / 2 + 1, y2 + 18, 3.5),
        (BUBBLE_WIDTH / 2 - 5, y2 + 25, 2.2),
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
