from __future__ import annotations


ACTION_LABELS: dict[str, str] = {
    "wiggle": "Wiggle",
    "blink": "Blink",
    "peek": "Peek",
    "scan": "Scan",
    "jump": "Jump",
    "flop": "Flop down",
    "dance": "Dance",
    "twirl": "Twirl",
    "stretch": "Stretch",
    "shake": "Shake",
    "happy_bounce": "Happy bounce",
    "nod": "Nod",
    "thinking_tilt": "Thinking tilt",
    "sleepy_sag": "Sleepy sag",
    "startled_pop": "Startled pop",
    "tail_wag": "Tail wag",
    "smug_sway": "Smug sway",
    "sulk": "Sulk",
    "hide": "Hide",
    "patrol": "Patrol",
    "celebrate": "Celebrate",
    "twist_scoot": "Twist scoot",
    "mini_hop_shift": "Mini hop shift",
    "relocate_hop": "Relocate hop",
    "roast_and_scoot": "Roast and scoot",
    "retreat_to_corner": "Retreat to corner",
    "drop_in": "Drop in",
}

ACTION_MENU_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Mood", ("happy_bounce", "dance", "celebrate", "smug_sway", "sulk", "hide")),
    ("State", ("thinking_tilt", "sleepy_sag", "flop", "stretch", "scan", "patrol")),
    ("Reactive", ("wiggle", "blink", "peek", "jump", "twirl", "shake", "startled_pop", "tail_wag", "nod")),
    ("Movement", ("twist_scoot", "mini_hop_shift", "relocate_hop", "roast_and_scoot", "retreat_to_corner", "drop_in")),
)

ACTION_DESCRIPTIONS: dict[str, str] = {
    "idle": "不做额外动作，保持轻微漂浮。",
    "bob": "很轻的点头/上下弹动，适合普通碎碎念。",
    "wiggle": "被戳或欠欠地抖一下，短促。",
    "blink": "睁大眼装无辜或轻轻眨眼。",
    "peek": "眼睛偷瞄鼠标或屏幕角落，适合观察。",
    "scan": "眼睛左右扫视，适合监控、找东西、读屏幕状态。",
    "jump": "明显跳一下，适合开心或突然来劲。",
    "flop": "整只纸夹趴下，适合累了、无语、放弃一秒。",
    "dance": "左右跳舞，适合得意、无聊自娱或庆祝。",
    "twirl": "2D 水平翻转转身，适合装酷或一本正经胡说八道。",
    "stretch": "伸懒腰，适合从 idle 醒来或准备开工。",
    "shake": "快速左右抖，适合紧张、报错、被吓到。",
    "happy_bounce": "轻快弹两下，适合开心、赞同、发现好事。",
    "nod": "点头，适合确认、假装懂了、认真附和。",
    "thinking_tilt": "歪着想一想，适合思考和吐槽前的停顿。",
    "sleepy_sag": "慢慢塌下去再恢复，适合困、无聊、加载太久。",
    "startled_pop": "突然弹高又缩回，适合被戳、提示、意外状态。",
    "tail_wag": "把回形针右侧翘起的尾端轻轻甩两下，适合开心、得意、被逗到。",
    "smug_sway": "得意地小幅左右摆，适合毒舌后装无辜。",
    "sulk": "缩下去闷一下，适合小委屈、小嫌弃、小无语。",
    "hide": "往下躲一躲，适合害羞、心虚、说完冷箭装无辜。",
    "patrol": "左右巡逻，适合等待、监控 Codex 或假装忙。",
    "celebrate": "更夸张的小庆祝，适合完成任务或状态变好。",
}

ACTION_DESCRIPTIONS.update(
    {
        "twist_scoot": "Small twist plus 10-20px scoot; frequent tiny reposition with attitude.",
        "mini_hop_shift": "Small hop shift of 20-50px with squash, arc, and rebound.",
        "relocate_hop": "Medium hop relocation with anticipation, landing squash, and rebound.",
        "roast_and_scoot": "Scoot away after a roast, then snap into fake innocence.",
        "retreat_to_corner": "Retreat toward a screen corner for quiet or self-restraint mode.",
        "drop_in": "Drop into the current station from above with a flat landing squash.",
    }
)

VISIBLE_ACTIONS: tuple[str, ...] = tuple(ACTION_LABELS)
MODEL_ACTIONS: tuple[str, ...] = ("idle", "bob", *VISIBLE_ACTIONS)
ACTION_SCHEMA_VALUE = "|".join(MODEL_ACTIONS)
ACTION_PROMPT = "\n".join(f"- {name}: {description}" for name, description in ACTION_DESCRIPTIONS.items())
