from __future__ import annotations

import math
import random
import time
import tkinter as tk
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Particle presets
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParticlePreset:
    count: int = 8
    lifetime: float = 1.0
    speed_min: float = 20.0
    speed_max: float = 60.0
    size_min: float = 2.0
    size_max: float = 5.0
    gravity: float = 40.0
    spread_angle: float = 360.0
    base_angle: float = 270.0  # up
    colors: tuple[str, ...] = ("#f0b429", "#e4a03b")
    shape: str = "circle"  # circle | star | heart | square | text | question_mark | sweat_drop
    text: str = ""
    fade: bool = True
    drag: float = 0.92
    spawn_radius: float = 8.0


PRESETS: dict[str, ParticlePreset] = {
    "sparkle": ParticlePreset(
        count=10, lifetime=1.0, speed_min=35, speed_max=95,
        size_min=2, size_max=4, gravity=12, spread_angle=320,
        colors=("#ffe066", "#ffd700", "#fff5cc"), shape="star", drag=0.96,
        spawn_radius=12,
    ),
    "confetti": ParticlePreset(
        count=14, lifetime=1.45, speed_min=55, speed_max=120,
        size_min=3, size_max=6, gravity=78, spread_angle=145, base_angle=270,
        colors=("#ff6b6b", "#ffd93d", "#6bcb77", "#4d96ff", "#ff85a1"),
        shape="square", drag=0.965, spawn_radius=14,
    ),
    "dust": ParticlePreset(
        count=7, lifetime=1.35, speed_min=24, speed_max=62,
        size_min=1.5, size_max=3.5, gravity=16, spread_angle=170, base_angle=270,
        colors=("#c0c0c0", "#a0a0a0", "#d8d8d8"), shape="circle", drag=0.91,
        spawn_radius=12,
    ),
    "hearts": ParticlePreset(
        count=5, lifetime=1.25, speed_min=30, speed_max=64,
        size_min=6, size_max=10, gravity=-18, spread_angle=95, base_angle=275,
        colors=("#ff6b8a", "#ff85a1", "#ff4d6d"), shape="heart", drag=0.94,
        spawn_radius=10,
    ),
    "exclaim": ParticlePreset(
        count=3, lifetime=0.85, speed_min=48, speed_max=92,
        size_min=8, size_max=12, gravity=22, spread_angle=70, base_angle=270,
        colors=("#ff4444", "#ff8800"), shape="text", text="!", drag=0.93,
        spawn_radius=8,
    ),
    "stars": ParticlePreset(
        count=7, lifetime=1.15, speed_min=42, speed_max=105,
        size_min=3, size_max=7, gravity=14, spread_angle=300,
        colors=("#ffd700", "#fff44f", "#ffec8b"), shape="star", drag=0.955,
        spawn_radius=12,
    ),
    "zzz": ParticlePreset(
        count=3, lifetime=2.1, speed_min=18, speed_max=34,
        size_min=8, size_max=14, gravity=-10, spread_angle=36, base_angle=305,
        colors=("#a0a0c0", "#8888aa"), shape="text", text="z", drag=0.97,
        spawn_radius=7,
    ),
    "sweat": ParticlePreset(
        count=3, lifetime=0.48, speed_min=46, speed_max=72,
        size_min=4, size_max=6, gravity=105, spread_angle=18, base_angle=318,
        colors=("#72b6e8", "#9ed7ff", "#bce8ff"), shape="sweat_drop", drag=0.93,
        spawn_radius=5,
    ),
    "question": ParticlePreset(
        count=2, lifetime=1.25, speed_min=30, speed_max=58,
        size_min=10, size_max=14, gravity=-12, spread_angle=48, base_angle=292,
        colors=("#b0b0c8", "#9090aa"), shape="question_mark", fade=False, drag=0.95,
        spawn_radius=8,
    ),
    "question_pop": ParticlePreset(
        count=3, lifetime=1.35, speed_min=32, speed_max=66,
        size_min=9, size_max=13, gravity=-16, spread_angle=70, base_angle=290,
        colors=("#8f78d4", "#b09cf0"), shape="question_mark", fade=False, drag=0.95,
        spawn_radius=10,
    ),
    "idea_burst": ParticlePreset(
        count=5, lifetime=1.15, speed_min=36, speed_max=82,
        size_min=5, size_max=9, gravity=10, spread_angle=210, base_angle=275,
        colors=("#ffd93d", "#fff5a8", "#f0b429"), shape="star", drag=0.955,
        spawn_radius=10,
    ),
    "red_x": ParticlePreset(
        count=3, lifetime=0.9, speed_min=38, speed_max=78,
        size_min=8, size_max=12, gravity=18, spread_angle=95, base_angle=275,
        colors=("#d65b4a", "#ff6b6b"), shape="text", text="x", drag=0.93,
        spawn_radius=8,
    ),
    "dizzy": ParticlePreset(
        count=4, lifetime=1.45, speed_min=22, speed_max=48,
        size_min=8, size_max=13, gravity=-6, spread_angle=180, base_angle=260,
        colors=("#6f62b8", "#9a8bd7", "#402a32"), shape="text", text="@", drag=0.96,
        spawn_radius=10,
    ),
    "blush": ParticlePreset(
        count=5, lifetime=1.0, speed_min=10, speed_max=28,
        size_min=3, size_max=6, gravity=6, spread_angle=220, base_angle=285,
        colors=("#ff9fb5", "#ffb3b3", "#ffd1dc"), shape="circle", drag=0.93,
        spawn_radius=11,
    ),
    "note": ParticlePreset(
        count=4, lifetime=1.1, speed_min=14, speed_max=35,
        size_min=8, size_max=12, gravity=-12, spread_angle=80, base_angle=270,
        colors=("#66bbee", "#88ccff", "#aaddff"), shape="text", text="♪", drag=0.93,
    ),
    "angry": ParticlePreset(
        count=4, lifetime=0.85, speed_min=48, speed_max=95,
        size_min=3, size_max=6, gravity=24, spread_angle=180, base_angle=270,
        colors=("#ff4444", "#ff6644", "#cc2222"), shape="star", drag=0.91,
        spawn_radius=10,
    ),
}


# ---------------------------------------------------------------------------
# Particle data
# ---------------------------------------------------------------------------

@dataclass
class _Particle:
    x: float
    y: float
    vx: float
    vy: float
    size: float
    color: str
    life: float
    max_life: float
    shape: str
    text: str
    angle: float = 0.0
    item_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class ParticleEmitter:
    """Lightweight canvas-based particle emitter for Tkinter desktop pets."""

    TICK_MS = 33  # ~30 fps
    VISUAL_SCALE = 2.0

    def __init__(self, canvas: tk.Canvas) -> None:
        self._canvas = canvas
        self._particles: list[_Particle] = []
        self._after_id: str | None = None
        self._running = False
        self._last_tick = 0.0

    # -- public API --

    def emit(
        self,
        cx: float,
        cy: float,
        preset_name: str = "sparkle",
        *,
        count_override: int | None = None,
    ) -> None:
        """Spawn a burst of particles at (cx, cy) using the named preset."""
        preset = PRESETS.get(preset_name, PRESETS["sparkle"])
        n = count_override if count_override is not None else preset.count
        for _ in range(n):
            angle_deg = preset.base_angle + random.uniform(
                -preset.spread_angle / 2, preset.spread_angle / 2
            )
            angle = math.radians(angle_deg)
            speed = random.uniform(preset.speed_min, preset.speed_max)
            size = random.uniform(preset.size_min, preset.size_max) * self.VISUAL_SCALE
            p = _Particle(
                x=cx + random.uniform(-preset.spawn_radius, preset.spawn_radius),
                y=cy + random.uniform(-preset.spawn_radius, preset.spawn_radius),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                size=size,
                color=random.choice(preset.colors),
                life=preset.lifetime,
                max_life=preset.lifetime,
                shape=preset.shape,
                text=preset.text,
                angle=angle,
            )
            self._create_canvas_items(p)
            self._particles.append(p)
        if not self._running:
            self._running = True
            self._last_tick = time.time()
            self._tick()

    def clear(self) -> None:
        """Remove all particles immediately."""
        if self._after_id:
            try:
                self._canvas.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        for p in self._particles:
            for item_id in p.item_ids:
                try:
                    self._canvas.delete(item_id)
                except tk.TclError:
                    pass
        try:
            self._canvas.delete("particle")
        except tk.TclError:
            pass
        self._particles.clear()
        self._running = False

    @property
    def active(self) -> bool:
        return bool(self._particles)

    # -- internal --

    def _create_canvas_items(self, p: _Particle) -> None:
        half = p.size / 2
        if p.shape == "text":
            item = self._canvas.create_text(
                p.x, p.y, text=p.text or "?",
                font=("Arial", max(6, int(p.size))),
                fill=p.color, anchor="center",
            )
            p.item_ids = [item]
        elif p.shape == "heart":
            item = self._canvas.create_text(
                p.x, p.y, text="♥",
                font=("Arial", max(6, int(p.size))),
                fill=p.color, anchor="center",
            )
            p.item_ids = [item]
        elif p.shape == "star":
            points = _star_points(p.x, p.y, half, half * 0.45, 5)
            item = self._canvas.create_polygon(
                points, fill=p.color, outline="",
            )
            p.item_ids = [item]
        elif p.shape == "question_mark":
            width = max(2, int(p.size * 0.16))
            arc = self._canvas.create_arc(
                p.x - half * 0.62,
                p.y - half * 0.72,
                p.x + half * 0.62,
                p.y + half * 0.42,
                start=-28,
                extent=252,
                style=tk.ARC,
                outline=p.color,
                width=width,
            )
            hook = self._canvas.create_line(
                p.x + half * 0.16,
                p.y + half * 0.28,
                p.x - half * 0.02,
                p.y + half * 0.55,
                fill=p.color,
                width=width,
                capstyle=tk.ROUND,
            )
            dot_radius = max(1.4, p.size * 0.09)
            dot = self._canvas.create_oval(
                p.x - dot_radius,
                p.y + half * 0.74 - dot_radius,
                p.x + dot_radius,
                p.y + half * 0.74 + dot_radius,
                fill=p.color,
                outline="",
            )
            p.item_ids = [arc, hook, dot]
        elif p.shape == "sweat_drop":
            points = _drop_points(p.x, p.y, p.size, p.angle)
            item = self._canvas.create_polygon(
                points,
                fill=p.color,
                outline="#5fa7d8",
                width=max(1, int(p.size * 0.08)),
                smooth=True,
                splinesteps=10,
            )
            gleam = _drop_gleam(p.x, p.y, p.size, p.angle)
            shine = self._canvas.create_line(
                *gleam,
                fill="#f4fbff",
                width=max(1, int(p.size * 0.12)),
                capstyle=tk.ROUND,
                smooth=True,
                splinesteps=6,
            )
            p.item_ids = [item, shine]
        elif p.shape == "square":
            item = self._canvas.create_rectangle(
                p.x - half, p.y - half, p.x + half, p.y + half,
                fill=p.color, outline="",
            )
            p.item_ids = [item]
        else:  # circle
            item = self._canvas.create_oval(
                p.x - half, p.y - half, p.x + half, p.y + half,
                fill=p.color, outline="",
            )
            p.item_ids = [item]
        for item_id in p.item_ids:
            self._canvas.addtag_withtag("particle", item_id)
            self._canvas.tag_raise(item_id)

    def _tick(self) -> None:
        self._after_id = None
        now = time.time()
        dt = min(0.1, now - self._last_tick)
        self._last_tick = now

        alive: list[_Particle] = []
        for p in self._particles:
            p.life -= dt
            if p.life <= 0:
                for item_id in p.item_ids:
                    try:
                        self._canvas.delete(item_id)
                    except tk.TclError:
                        pass
                continue

            preset_name = self._guess_preset(p)
            preset = PRESETS.get(preset_name, PRESETS["sparkle"])

            p.vy += preset.gravity * dt
            p.vx *= preset.drag
            p.vy *= preset.drag
            dx = p.vx * dt
            dy = p.vy * dt
            p.x += dx
            p.y += dy

            for item_id in p.item_ids:
                self._canvas.move(item_id, dx, dy)
                self._canvas.tag_raise(item_id)

            alive.append(p)

        self._particles = alive
        if alive:
            self._after_id = self._canvas.after(self.TICK_MS, self._tick)
        else:
            try:
                self._canvas.delete("particle")
            except tk.TclError:
                pass
            self._running = False

    def _guess_preset(self, p: _Particle) -> str:
        """Best-effort preset lookup by shape/color for physics constants."""
        for name, preset in PRESETS.items():
            if p.color in preset.colors and p.shape == preset.shape:
                return name
        return "sparkle"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _star_points(
    cx: float, cy: float, outer: float, inner: float, points: int = 5
) -> list[float]:
    coords: list[float] = []
    for i in range(points * 2):
        angle = math.radians(-90 + i * 180 / points)
        r = outer if i % 2 == 0 else inner
        coords.extend((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return coords


def _drop_points(cx: float, cy: float, size: float, angle: float) -> list[float]:
    # A small sweat drop: round bulb leads the throw, point trails back.
    length = size * 1.45
    width = size * 0.78
    local = [
        (0.0, -length * 0.62),
        (width * 0.46, -length * 0.28),
        (width * 0.54, length * 0.10),
        (0.0, length * 0.48),
        (-width * 0.54, length * 0.10),
        (-width * 0.46, -length * 0.28),
    ]
    return _rotate_points(cx, cy, local, angle - math.pi / 2)


def _drop_gleam(cx: float, cy: float, size: float, angle: float) -> list[float]:
    local = [
        (-size * 0.16, -size * 0.20),
        (-size * 0.04, -size * 0.42),
    ]
    return _rotate_points(cx, cy, local, angle - math.pi / 2)


def _rotate_points(
    cx: float,
    cy: float,
    local_points: list[tuple[float, float]],
    rotation: float,
) -> list[float]:
    cos_r = math.cos(rotation)
    sin_r = math.sin(rotation)
    coords: list[float] = []
    for x, y in local_points:
        coords.extend((cx + x * cos_r - y * sin_r, cy + x * sin_r + y * cos_r))
    return coords
