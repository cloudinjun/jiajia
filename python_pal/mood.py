from __future__ import annotations

import math
import random
import time


ENERGY_BASELINE = 0.45
VALENCE_BASELINE = 0.1
DECAY_RATE = 0.002

# 大脑的 mood 字符串 → (energy_delta, valence_delta)
MOOD_IMPULSE: dict[str, tuple[float, float]] = {
    "idle":       ( 0.00,  0.00),
    "smirk":      ( 0.08,  0.15),
    "smug":       ( 0.08,  0.16),
    "happy":      ( 0.15,  0.25),
    "thinking":   ( 0.05, -0.02),
    "sleepy":     (-0.20, -0.05),
    "startled":   ( 0.25, -0.10),
    "proud":      ( 0.10,  0.20),
    "shy":        (-0.05,  0.05),
    "sulky":      (-0.10, -0.20),
    "focused":    ( 0.10,  0.05),
    "bored":      (-0.12, -0.08),
    "done":       (-0.05,  0.15),
    "innocent":   ( 0.02,  0.10),
    "suspicious": ( 0.08, -0.05),
    "guilty":     (-0.05, -0.10),
}

MICRO_BEHAVIORS: dict[str, list[tuple[str, float]]] = {
    "excited":  [("happy_bounce", 3), ("dance", 2), ("celebrate", 1), ("jump", 1)],
    "agitated": [("shake", 3), ("startled_pop", 2), ("patrol", 2)],
    "content":  [("smug_sway", 3), ("nod", 2), ("stretch", 1)],
    "sluggish": [("sleepy_sag", 3), ("flop", 2), ("sulk", 2), ("hide", 1)],
    "neutral":  [("scan", 2), ("thinking_tilt", 2), ("wiggle", 1), ("blink", 2), ("peek", 1)],
}

FREQUENCY_PRESETS: tuple[tuple[str, float], ...] = (
    ("安静", 0.3),
    ("正常", 1.0),
    ("活泼", 2.0),
    ("多动", 4.0),
)
FREQUENCY_DEFAULT = "正常"


class MoodEngine:
    def __init__(self) -> None:
        self.energy = ENERGY_BASELINE
        self.valence = VALENCE_BASELINE
        self._last_tick = time.monotonic()
        self.frequency_key = FREQUENCY_DEFAULT

    @property
    def frequency_multiplier(self) -> float:
        for key, mult in FREQUENCY_PRESETS:
            if key == self.frequency_key:
                return mult
        return 1.0

    def push_mood(self, mood_str: str) -> None:
        de, dv = MOOD_IMPULSE.get(mood_str, (0.0, 0.0))
        self.energy = max(0.0, min(1.0, self.energy + de))
        self.valence = max(-1.0, min(1.0, self.valence + dv))

    def tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
        decay = math.exp(-DECAY_RATE * dt)
        self.energy = ENERGY_BASELINE + (self.energy - ENERGY_BASELINE) * decay
        self.valence = VALENCE_BASELINE + (self.valence - VALENCE_BASELINE) * decay

    def pick_micro_behavior(self) -> str | None:
        self.tick()
        weights = self._zone_weights()
        candidates: list[tuple[str, float]] = []
        for zone, zone_weight in weights.items():
            if zone_weight < 0.05:
                continue
            for action, action_weight in MICRO_BEHAVIORS[zone]:
                candidates.append((action, action_weight * zone_weight))
        if not candidates:
            return None
        actions, ws = zip(*candidates)
        return random.choices(actions, weights=ws, k=1)[0]

    def micro_interval_ms(self) -> int:
        # energy 高→间隔短（更活跃），frequency_multiplier 放大/缩小。
        # 多动模式要真的有陪伴感，所以不能被 3 秒下限卡住。
        base = 11000 - self.energy * 7600
        floor = round(2600 / max(1.0, self.frequency_multiplier))
        jitter = random.randint(-250, 350)
        return max(650, floor, round(base / self.frequency_multiplier) + jitter)

    def companion_interval_ms(self) -> int:
        base = 19000 - self.energy * 9000
        jitter = random.randint(-1200, 1600)
        return max(2200, round(base / max(0.4, self.frequency_multiplier)) + jitter)

    def ambient_cooldown_seconds(self) -> int:
        return max(14, round(58 / max(0.8, self.frequency_multiplier)))

    def ambient_chance_multiplier(self) -> float:
        return min(2.6, 0.75 + self.frequency_multiplier * 0.45)

    def breath_rate(self) -> float:
        return 0.008 + self.energy * 0.008

    def breath_depth_base(self) -> float:
        extra = max(0.0, self.frequency_multiplier - 1.0) * 0.28
        return 2.0 + self.energy * 1.3 + min(1.0, extra)

    def blink_interval_ms(self) -> int:
        base = round(8000 - self.energy * 4500)
        base = round(base / max(1.0, self.frequency_multiplier * 0.55))
        jitter = round(base * 0.3)
        return max(900, base + random.randint(-jitter, jitter))

    def set_frequency(self, key: str) -> None:
        self.frequency_key = key
        if key == "多动":
            self.energy = max(self.energy, 0.82)
            self.valence = max(self.valence, 0.18)
        elif key == "活泼":
            self.energy = max(self.energy, 0.62)

    def _zone_weights(self) -> dict[str, float]:
        e, v = self.energy, self.valence
        return {
            "excited":  max(0.0, e - 0.4) * max(0.0, v + 0.2),
            "agitated": max(0.0, e - 0.4) * max(0.0, -v + 0.2),
            "content":  max(0.0, 0.6 - e) * max(0.0, v + 0.2),
            "sluggish": max(0.0, 0.6 - e) * max(0.0, -v + 0.2),
            "neutral":  0.3,
        }
