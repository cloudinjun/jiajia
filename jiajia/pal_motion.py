"""Animation data tables and tail samplers.

Every keyframe table, pose channel type and tail motion definition lives here
so the action layer and the offline GIF renderer read one source. Pure data
plus two pure samplers — no Tk, no `self`.
"""
from __future__ import annotations

import math
from typing import NotRequired, TypedDict

from .pal_geometry import ActionFrame, ActionFrames, _smoothstep


# follow-through: the tail tip plays the pose this far behind the root, so the
# wire bends through motion instead of swinging as one rigid piece
TAIL_TIP_LAG_MS = 130

# body bend channel: (lean, hunch) in px at the very top of the character;
# lean shears sideways with the feet planted, hunch>0 slumps, hunch<0 lifts
BodyBend = tuple[float, float]

BODY_BEND_NEUTRAL: BodyBend = (0.0, 0.0)

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

ActionActingCue = tuple[str, str, int, bool]

TailPose = tuple[float, float, float, float, float]

TailFrame = tuple[float, float, float, float, float, int]

TailFrames = tuple[TailFrame, ...]

InnerPose = tuple[float, float, float, float]

InnerFrame = tuple[float, float, float, float, int]

InnerFrames = tuple[InnerFrame, ...]

PropFrame = tuple[float, float, float, float, int]

PropFrames = tuple[PropFrame, ...]

class PaperPropCue(TypedDict):
    decoration: str
    duration: int
    eyes: str
    brows: str
    frames: PropFrames
    tail: NotRequired[str]
    inner: NotRequired[str]

TAIL_NEUTRAL_POSE: TailPose = (0.0, 0.0, 0.0, 0.0, 0.0)

INNER_NEUTRAL_POSE: InnerPose = (0.0, 0.0, 0.0, 0.0)

ACTION_FRAMES: dict[str, ActionFrames] = {
    # dozing, then the alarm: one sharp snap up, then sinking back
    # because being woken does not make you awake
    "alarm_jolt": (
        (0, 6, 1.02, 0.94, 200),
        (0, 9, 1.03, 0.92, 200),
        (0, -8, 0.94, 1.12, 130),
        (0, -4, 0.98, 1.06, 160),
        (0, 2, 1.01, 0.98, 240),
        (0, 5, 1.02, 0.96, 400),
        (0, 3, 1.01, 0.97, 300),
        (0, 0, 1.0, 1.0, 200),
    ),

    # ── agent state signatures ───────────────────────────────────
    # One state, one readable movement. These used to alias onto
    # patrol/scan/thinking_tilt, so eight configured states showed up
    # on screen as four.
    "tool_working": (
        (0, 0, 1.0, 1.0, 120),
        (0, -3, 1.0, 1.02, 180),
        (0, 0, 1.0, 1.0, 180),
        (0, -3, 1.0, 1.02, 180),
        (0, 0, 1.0, 1.0, 180),
        (0, -3, 1.0, 1.02, 180),
        (0, 0, 1.0, 1.0, 240),
    ),
    "paper_editing": (
        (0, 3, 1.02, 0.98, 200),
        (-3, 4, 1.02, 0.97, 260),
        (-1, 4, 1.02, 0.97, 200),
        (2, 4, 1.02, 0.97, 260),
        (4, 4, 1.02, 0.97, 200),
        (0, 2, 1.01, 0.99, 240),
        (0, 0, 1.0, 1.0, 160),
    ),
    "waiting_stare": (
        (0, 0, 1.0, 1.0, 300),
        (1, 0, 1.0, 1.0, 900),
        (1, 1, 1.0, 1.0, 700),
        (0, 0, 1.0, 1.0, 400),
    ),
    "permission_request": (
        (0, 0, 1.0, 1.0, 120),
        (0, -4, 1.06, 1.04, 220),
        (0, -6, 1.08, 1.05, 700),
        (0, -5, 1.07, 1.04, 300),
        (0, -2, 1.02, 1.01, 260),
        (0, 0, 1.0, 1.0, 180),
    ),
    "paper_sorting": (
        (0, 0, 1.0, 1.0, 140),
        (-12, 2, 1.0, 1.0, 200),
        (-12, 5, 1.0, 0.97, 240),
        (0, 0, 1.0, 1.0, 200),
        (12, 2, 1.0, 1.0, 200),
        (12, 5, 1.0, 0.97, 240),
        (0, 0, 1.0, 1.0, 220),
    ),
    "reconnect_scan": (
        (0, 0, 1.0, 1.0, 120),
        (-14, 0, 1.0, 1.0, 260),
        (-14, 0, 1.0, 1.0, 100),
        (-10, 0, 0.98, 1.02, 100),
        (-14, 0, 1.0, 1.0, 120),
        (14, 0, 1.0, 1.0, 300),
        (14, 0, 1.0, 1.0, 100),
        (10, 0, 0.98, 1.02, 100),
        (14, 0, 1.0, 1.0, 120),
        (0, 0, 1.0, 1.0, 200),
    ),
    "error_autopsy": (
        (0, 0, 1.0, 1.0, 160),
        (-5, 3, 1.03, 0.98, 340),
        (-7, 5, 1.05, 0.96, 900),
        (-6, 4, 1.04, 0.97, 300),
        (-2, 1, 1.01, 0.99, 260),
        (0, 0, 1.0, 1.0, 180),
    ),
    "thinking_loop": (
        (0, 0, 1.0, 1.0, 200),
        (-4, 1, 0.98, 1.02, 460),
        (-5, 2, 0.97, 1.03, 380),
        (0, 1, 0.99, 1.01, 420),
        (4, 1, 0.98, 1.02, 460),
        (5, 2, 0.97, 1.03, 380),
        (0, 0, 1.0, 1.0, 300),
    ),

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
    "sleepy_clip": {"mood": "sleepy", "action": "sleepy_sag", "eyes": "sleepy_slit", "brows": "droop", "hold_ms": 9000},
    "bug_coroner": {"mood": "suspicious", "action": "scan", "eyes": "side_eye", "brows": "judge", "hold_ms": 4600},
    "critic_clip": {"mood": "smirk", "action": "thinking_tilt", "eyes": "side_eye", "brows": "judge", "hold_ms": 3600},
    "tab_warden": {"mood": "suspicious", "action": "patrol", "decoration": "tab_bar", "eyes": "side_eye", "brows": "judge", "hold_ms": 4400},
    "gremlin_clip": {"mood": "smug", "action": "smug_sway", "eyes": "side_eye", "brows": "proud", "hold_ms": 3600},
    "meltdown_clip": {"mood": "sulky", "action": "melt", "eyes": "peek_up", "brows": "sulk", "hold_ms": 5200},
}

# Action-triggered caption decorations used to live here (sleepy_sag -> Z,
# dance -> stage, hide -> cover paper...). That was the props-are-opt-in
# decision being bypassed from a third location: the prop did the acting again.
# A decoration now needs a stated cause (see pal_decor.reaction_decoration_cues)
# or an explicit performance step; an action alone earns nothing.
ACTION_DECORATION_CUES: dict[str, tuple[str, int]] = {}

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
    # An alert is a POSE, not a vibration. The old version crossed 63px with
    # three direction reversals in 225ms and no hold: at 30fps each leg was
    # about two frames, so it read as the tail teleporting rather than
    # reacting. The shape of a real one is anticipation (coil the other way),
    # one committed straighten, then a long hold — the hold is where the
    # viewer actually reads "alert" — then a delayed tip shudder and a damped
    # release that stops short of neutral, because the pal is still watching.
    "tail_alert_snap": (
        (0, 0, 0, 0, 0, 40),
        (-2, -3, 0, 0, 2, 110),
        (2, 3, 0, 0, 15, 170),
        (2, 3, 0, 0, 15, 300),
        (3, 2, 0, 0, 14, 80),
        (1, 3, 0, 0, 15, 80),
        (2, 3, 0, 0, 12, 200),
        (0, 1, 0, 0, 3, 180),
    ),
}

# The inner wire is a HAND that covers the mouth. It can hold something, but it
# never carries it away: the wire stays put and only the tip articulates. In rig
# terms amount_x/amount_y (tip) carry the gesture, while mid_x/mid_y bow the
# whole wire outward and must stay under INNER_MID_LIMIT. Without that limit the
# core reads as a free arm, which is how it ended up waving, pointing and giving
# a thumbs-up — a second appendage the character is not supposed to have.
INNER_MID_LIMIT = 5.0

INNER_GESTURE_FRAMES: dict[str, InnerFrames] = {
    "inner_cover_oops": (
        (0, 0, 0, 0, 45),
        (5, 18, -2, 3, 95),
        (-2, 14, 1, 3, 85),
        (3, 17, -1, 2, 130),
        (0, 8, 0, 2, 120),
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
        (-8, 11, -2, 2, 120),
        (-7, 9, -3, 2, 260),
        (0, 4, -1, 1, 120),
        (0, 0, 0, 0, 150),
    ),
    "inner_droop": (
        (0, 0, 0, 0, 45),
        (-1, -10, 0, -2, 220),
        (1, -14, 0, -3, 420),
        (0, -6, 0, -1, 180),
        (0, 0, 0, 0, 180),
    ),
    # --- hand gestures ---
    "inner_wave": (
        (0, 0, 0, 0, 40),
        (13, 6, 2, 1, 100),
        (-11, 7, -2, 1, 110),
        (12, 5, 2, 1, 105),
        (-9, 6, -1, 1, 110),
        (4, 3, 1, 0, 120),
        (0, 0, 0, 0, 130),
    ),
    "inner_point": (
        (0, 0, 0, 0, 40),
        (0, 16, 0, 2, 110),
        (2, 18, 1, 2, 280),
        (1, 13, 0, 2, 140),
        (0, 0, 0, 0, 140),
    ),
    "inner_facepalm": (
        (0, 0, 0, 0, 40),
        (3, 20, -1, 3, 120),
        (1, 23, 0, 4, 400),
        (2, 16, 0, 3, 160),
        (0, 5, 0, 1, 130),
        (0, 0, 0, 0, 140),
    ),
    "inner_thumbs_up": (
        (0, 0, 0, 0, 40),
        (0, 20, 0, 3, 120),
        (1, 23, 0, 3, 320),
        (0, 11, 0, 2, 140),
        (0, 0, 0, 0, 130),
    ),
    # --- mouth gestures ---
    "inner_yawn": (
        (0, 0, 0, 0, 60),
        (0, -3, 0, -1, 180),
        (-1, -11, 1, -2, 320),
        (1, -14, -1, -3, 500),
        (0, -7, 0, -2, 240),
        (0, -1, 0, 0, 160),
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
    "jump": "tail_tip_flick",
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
    "spin_jump": "tail_tip_flick",
    "excited_spin": "tail_wag",
    "sneeze": "tail_tip_flick",
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


def _acting_frames(frames: ActionFrames, action_name: str) -> ActionFrames:
    anticipation = ACTION_ANTICIPATION_FRAMES.get(action_name, ())
    follow_through = ACTION_FOLLOW_THROUGH_FRAMES.get(action_name, ())
    if not anticipation and not follow_through:
        return frames
    base = frames
    if follow_through and base and _is_neutral_action_frame(base[-1]):
        base = base[:-1]
    return (*anticipation, *base, *follow_through)


def _is_neutral_action_frame(frame: ActionFrame) -> bool:
    dx, dy, sx, sy, _delay = frame
    return abs(dx) < 0.01 and abs(dy) < 0.01 and abs(sx - 1.0) < 0.01 and abs(sy - 1.0) < 0.01
