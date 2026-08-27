"""Audit every action: duration, motion model, and a one-line semantic summary.

Each action's GIF must be describable in one plain sentence — "夹夹戴上墨镜",
"夹夹眨眼并摇铃铛". If the summary reads as a shrug, the action's layers do not
agree on what it means and it needs redesign.

    python scripts/audit_actions.py            # full table
    python scripts/audit_actions.py --warn     # only the problems
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from python_pal import body as B
from python_pal.actions import ACTION_LABELS
from python_pal.prop_shapes import (
    ACTION_FACE_SCRIPTS,
    ACTION_PROP_CUES,
    build_prop_timeline,
    prop_cue_duration_ms,
)

# what each prop reads as, in plain words
PROP_WORDS = {
    "coffee_mug": "端咖啡抿一口", "broom": "拿扫帚扫地", "magnifier": "举放大镜查看",
    "flag": "挥小旗", "white_flag": "举白旗投降", "headphones": "戴上耳机",
    "question_sign": "举问号牌", "check_sign": "举对勾牌", "alert_sign": "顶着警示牌",
    "rain_cloud": "头顶乌云淋雨", "alarm_clock": "被闹钟吵", "thermometer": "举温度计爆表",
    "sunglasses": "戴上墨镜", "halo": "顶着光环装无辜", "binoculars": "举望远镜瞭望",
    "trophy": "高举奖杯", "star_wand": "挥星星棒", "pinwheel": "转风车",
    "tissue": "抽纸巾", "snowflake": "被雪花冻着", "bell": "摇铃铛", "pen": "转笔",
    "suitcase": "拎行李箱", "umbrella": "撑伞", "parachute": "乘滑翔伞降落",
    "energy_drink": "灌能量饮料",
}

# face beats worth naming in a summary
EYE_WORDS = {
    "sparkle": "眼睛发亮", "closed": "闭上眼", "startled_dot": "瞳孔一缩",
    "smug_half": "眯眼得意", "suspicious_slit": "眯眼审视", "sleepy_slit": "眼皮沉沉",
    "innocent_round": "睁圆眼装无辜", "guilty_round": "心虚圆眼", "worried_wide": "担心睁大眼",
    "wide": "瞪大眼", "peek_up": "抬眼偷看", "curious": "好奇张望", "narrow": "眯起眼",
    "proud": "骄傲眯眼", "half_closed": "半闭眼", "round": "圆眼", "soft": "眼神放软",
}
EXTRA_WORDS = {
    "wink": "wink", "blink": "眨眼", "pupil_shape": "瞳孔变形",
    "decal": "挂表情符号", "tremble": "眉毛发抖", "blush": "脸红",
}
PUPIL_SHAPE_WORDS = {
    "star": "星星眼", "heart": "心形眼", "spiral": "螺旋眼", "x": "XX眼",
    "line": "死鱼眼", "squeeze": "挤眼", "closed_smile": "笑成弯月眼",
}
DECAL_WORDS = {
    "tear": "挂泪", "tears": "泪流满面", "sweat": "冒汗", "pale": "脸色发青",
    "shock_lines": "冒惊吓线", "sigh": "叹气", "star_ring": "头顶转星星",
}
TAIL_WORDS = {
    "tail_wag": "摇尾巴", "tail_smug_sway": "得意慢摆尾", "tail_idle_slow": "尾巴轻晃",
    "tail_tip_flick": "尾尖一甩", "tail_frantic_innocent": "尾巴慌乱狂甩",
    "tail_bell_ring": "尾尖摇铃", "tail_bell_jingle": "尾尖轻响铃",
    "tail_guilty_tuck": "尾巴心虚内收", "tail_sleepy_droop": "尾巴垂下",
    "tail_alert_snap": "尾巴警觉一弹", "tail_raise_excited": "尾巴兴奋竖起",
    "tail_question_hook": "尾巴弯成问号", "tail_bristle": "尾巴炸毛僵直",
}


def body_duration_ms(action: str) -> int:
    frames = B.ACTION_FRAMES.get(action)
    if frames:
        return sum(f[4] for f in B._acting_frames(frames, action))
    return B.PaperclipPalApp._animation_duration_ms(_Dummy(), action)  # type: ignore[arg-type]


class _Dummy:
    """Minimal stand-in so the duration lookup can run without a window."""
    animation_resolver = type("R", (), {"resolve": staticmethod(
        lambda n: type("A", (), {"action": n, "performance": ""})())})()


def tail_motion_for(action: str) -> tuple[str, str]:
    cue = ACTION_PROP_CUES.get(action)
    if cue and cue.get("held") and cue.get("tail_style") == "wag":
        return str(cue.get("tail_motion") or action), "pinned to prop"
    if cue and cue.get("held"):
        return "(hand mode: steady carry)", "hand"
    linked = B.ACTION_TAIL_MOTIONS.get(action)
    if action in B.TAIL_OSCILLATIONS or action in B.TAIL_POSTURES or action in B.TAIL_MOTION_FRAMES:
        return action, "self"
    return (linked or ""), "linked"


def tail_model(motion: str) -> str:
    if motion in B.TAIL_OSCILLATIONS:
        p = B.TAIL_OSCILLATIONS[motion]
        tip = " tip-only" if p.get("engage") else ""
        return f"osc {p['freq']}Hz x{p['cycles']}{tip}"
    if motion in B.TAIL_POSTURES:
        return "posture hold"
    if motion in B.TAIL_MOTION_FRAMES:
        return "keyframe pose"
    if motion.startswith("("):
        return "hand"
    return "-"


def summarize(action: str) -> str:
    """One plain sentence for what this GIF shows."""
    bits: list[str] = []
    cue = ACTION_PROP_CUES.get(action)
    if cue:
        word = PROP_WORDS.get(str(cue["shape"]))
        if word:
            bits.append(word)

    script = ACTION_FACE_SCRIPTS.get(action, ())
    face_bits: list[str] = []
    for frame in script:
        ex = frame[4] if len(frame) > 4 and frame[4] else {}
        if "pupil_shape" in ex:
            face_bits.append(PUPIL_SHAPE_WORDS.get(ex["pupil_shape"], ""))
        if ex.get("wink"):
            face_bits.append("wink")
        if "decal" in ex:
            face_bits.append(DECAL_WORDS.get(ex["decal"], ""))
    # the peak expression: the beat with the most extras
    if script:
        peak = max(script, key=lambda f: len(f[4]) if len(f) > 4 and f[4] else 0)
        w = EYE_WORDS.get(peak[1])
        if w:
            face_bits.insert(0, w)
    for b in face_bits:
        if b and b not in bits:
            bits.append(b)

    motion, _kind = tail_motion_for(action)
    tw = TAIL_WORDS.get(motion)
    if tw and tw not in bits:
        # a tail action is ABOUT the tail: lead with it
        if action.startswith("tail_"):
            bits.insert(0, tw)
        else:
            bits.append(tw)

    if not bits:
        bits.append(ACTION_LABELS.get(action, action))
    return "夹夹" + "、".join(bits[:3])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn", action="store_true", help="only list problems")
    args = ap.parse_args()

    problems: list[str] = []
    rows: list[tuple[str, ...]] = []
    for action in sorted(ACTION_LABELS):
        cue = ACTION_PROP_CUES.get(action)
        prop_ms = prop_cue_duration_ms(action) if cue else 0
        try:
            body_ms = body_duration_ms(action)
        except Exception:
            body_ms = 0
        motion, kind = tail_motion_for(action)
        model = tail_model(motion)
        script = ACTION_FACE_SCRIPTS.get(action, ())
        face_ms = script[-1][0] if script else 0
        summary = summarize(action)

        # audit rules
        has_body_motion = action in B.ACTION_FRAMES or action in B.MOVE_IDLE_ACTIONS
        # a move action's body beat is travel inside a longer prop story
        # (carrying the suitcase before and after the hop), so it gets slack
        floor = 0.28 if action in B.MOVE_IDLE_ACTIONS else 0.55
        if cue and body_ms and prop_ms and has_body_motion:
            ratio = body_ms / prop_ms
            if ratio < floor:
                problems.append(f"{action}: body {body_ms}ms is only {ratio:.0%} of prop {prop_ms}ms (body quits early)")
            if ratio > 2.2:
                problems.append(f"{action}: body {body_ms}ms is {ratio:.0%} of prop {prop_ms}ms (prop gone, body still going)")
        if cue and face_ms and face_ms > prop_ms + 400:
            problems.append(f"{action}: face script runs {face_ms}ms past a {prop_ms}ms prop")
        if cue and not script:
            problems.append(f"{action}: has a prop but no face script")
        if not cue and action in ACTION_LABELS and action not in {"melt"}:
            pass
        rows.append((action, f"{body_ms}", f"{prop_ms}", f"{face_ms}", model, summary))

    if not args.warn:
        w = [max(len(r[i]) for r in rows) for i in range(6)]
        print(f"{'action':{w[0]}}  {'body':>{w[1]}}  {'prop':>{w[2]}}  {'face':>{w[3]}}  {'tail model':{w[4]}}  summary")
        print("-" * (sum(w) + 20))
        for r in rows:
            print(f"{r[0]:{w[0]}}  {r[1]:>{w[1]}}  {r[2]:>{w[2]}}  {r[3]:>{w[3]}}  {r[4]:{w[4]}}  {r[5]}")

    print(f"\n{len(problems)} problem(s):")
    for p in problems:
        print(" -", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
