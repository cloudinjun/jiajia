from __future__ import annotations

import tkinter as tk
from typing import Any

from .body import PAL_CANVAS_HEIGHT, PAL_CENTER_X, PAL_HEIGHT, PAL_PAD_X, PAL_PAD_Y, PAL_WIDTH, _rounded_rect
from .decorations import DecorationDefinition


Paper = "#fffdfd"
SoftPaper = "#f9f7f5"
MutedLine = "#d7d2cc"


def install_identity_accessory_renderer(app_cls: type[Any]) -> None:
    """Install a richer identity accessory renderer without rewriting the pet body."""
    if getattr(app_cls, "_identity_accessory_renderer_installed", False):
        return
    app_cls._draw_decoration = _draw_decoration  # type: ignore[method-assign]
    app_cls._decoration_anchor = _decoration_anchor  # type: ignore[method-assign]
    app_cls._identity_accessory_renderer_installed = True


def _draw_decoration(self: Any, definition: DecorationDefinition, lifetime: str = "identity") -> None:
    x, y = self._decoration_anchor(definition)
    color = definition.color
    items: list[int] = []
    shape = definition.shape_type
    main_w = 2.5
    detail_w = 1.45

    def line(*coords: float, fill: str = color, width: float = main_w, smooth: bool = False) -> int:
        return self.canvas.create_line(
            *coords,
            fill=fill,
            width=width,
            smooth=smooth,
            splinesteps=12,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
        )

    def card(x1: float, y1: float, x2: float, y2: float, radius: float = 7, fill: str = Paper, outline: str = color, width: float = main_w) -> int:
        return _rounded_rect(self.canvas, x1, y1, x2, y2, radius, fill=fill, outline=outline, width=width)

    def oval(x1: float, y1: float, x2: float, y2: float, fill: str = Paper, outline: str = color, width: float = detail_w) -> int:
        return self.canvas.create_oval(x1, y1, x2, y2, fill=fill, outline=outline, width=width)

    def text(cx: float, cy: float, value: str, size: int = 6, fill: str = color, weight: str = "bold") -> int:
        return self.canvas.create_text(cx, cy, text=value, fill=fill, font=("Consolas", size, weight))

    if shape in {"terminal_box", "terminal_monitor"}:
        items.extend(
            [
                card(x, y, x + 36, y + 27, 7, fill="#fbfffd"),
                line(x + 2, y + 8, x + 34, y + 8, width=detail_w, fill="#dcebe4"),
                self.canvas.create_oval(x + 5, y + 4, x + 8, y + 7, fill=color, outline=""),
                self.canvas.create_oval(x + 10, y + 4, x + 13, y + 7, fill="#b7d9ca", outline=""),
                self.canvas.create_oval(x + 15, y + 4, x + 18, y + 7, fill="#d8e7df", outline=""),
                line(x + 7, y + 15, x + 11, y + 18, x + 7, y + 21, width=detail_w, smooth=True),
                line(x + 14, y + 21, x + 26, y + 21, width=detail_w),
                line(x + 16, y + 14, x + 30, y + 14, width=1.1, fill="#8fc8ad"),
                self.canvas.create_oval(x + 30, y + 19, x + 34, y + 23, fill=color, outline=Paper, width=1),
            ]
        )

    elif shape == "status_dot":
        items.append(self.canvas.create_oval(x, y, x + 10, y + 10, fill=color, outline=Paper, width=detail_w))

    elif shape in {"checklist", "audit_clipboard"}:
        items.extend(
            [
                card(x, y, x + 30, y + 36, 6, fill="#fefffb"),
                card(x + 8, y - 3, x + 22, y + 5, 4, fill="#f4fbf6", width=1.5),
                line(x + 24, y + 2, x + 29, y + 7, x + 29, y + 2, width=1.0, fill="#cfe7d8", smooth=True),
                self.canvas.create_rectangle(x + 6, y + 10, x + 11, y + 15, outline=color, width=1.3, fill=""),
                line(x + 7, y + 13, x + 9, y + 15, x + 14, y + 8, width=detail_w, smooth=True),
                self.canvas.create_rectangle(x + 6, y + 21, x + 11, y + 26, outline=color, width=1.1, fill=""),
                line(x + 14, y + 13, x + 25, y + 12, width=1.2, fill="#90cfa7"),
                line(x + 14, y + 24, x + 23, y + 23, width=1.2, fill="#90cfa7"),
                line(x + 6, y + 31, x + 23, y + 30, width=1.1, fill="#c9dfcf"),
            ]
        )

    elif shape in {"thermometer", "side_heat_gauge", "heat_gauge"}:
        level = self._last_hardware_status.level if hasattr(self, "_last_hardware_status") else "warm"
        level_ratio = {"normal": 0.28, "unavailable": 0.22, "busy": 0.38, "cooling": 0.48, "warm": 0.58, "hot": 0.76, "overloaded": 0.92}.get(str(level), 0.62)
        gauge_x = x + 8
        gauge_y = y
        gauge_h = 36
        fill_y = gauge_y + gauge_h - 4 - (gauge_h - 8) * level_ratio
        items.extend(
            [
                card(gauge_x, gauge_y, gauge_x + 14, gauge_y + gauge_h, 7, fill="#fff7f5"),
                line(gauge_x + 7, gauge_y + 5, gauge_x + 7, gauge_y + gauge_h - 5, width=5.2, fill="#f6dedb"),
                line(gauge_x + 7, fill_y, gauge_x + 7, gauge_y + gauge_h - 5, width=4.2, fill=color),
                line(gauge_x + 17, gauge_y + 7, gauge_x + 22, gauge_y + 7, width=1.2, fill=color),
                line(gauge_x + 17, gauge_y + 17, gauge_x + 21, gauge_y + 17, width=1.2, fill=color),
                line(gauge_x + 17, gauge_y + 27, gauge_x + 22, gauge_y + 27, width=1.2, fill=color),
            ]
        )
        for x0, y0, x1, y1, x2, y2 in ((-5, 8, -1, 2, 1, -3), (17, 31, 23, 25, 20, 20)):
            items.append(line(gauge_x + x0, gauge_y + y0, gauge_x + x1, gauge_y + y1, gauge_x + x2, gauge_y + y2, width=1.2, fill="#e3a3a0", smooth=True))

    elif shape in {"heat_puffs", "heat_wisps"}:
        for x0, y0, x1, y1, x2, y2 in ((0, 16, 5, 8, 2, 1), (12, 18, 18, 10, 15, 3), (25, 15, 30, 8, 27, 1)):
            items.append(line(x + x0, y + y0, x + x1, y + y1, x + x2, y + y2, smooth=True, width=detail_w))
        items.append(self.canvas.create_oval(x + 33, y + 13, x + 37, y + 19, fill="#f5c2bc", outline=color, width=1))

    elif shape in {"ledger", "receipt_ledger"}:
        percent = self._last_codex_usage_status.usage_remaining_percent
        ratio = max(0.1, min(1.0, (percent or 38) / 100))
        fill_width = round(20 * ratio)
        items.extend(
            [
                card(x, y, x + 28, y + 38, 5, fill="#f8fbff"),
                line(x + 4, y + 1, x + 7, y + 4, x + 10, y + 1, x + 13, y + 4, x + 16, y + 1, x + 19, y + 4, x + 22, y + 1, x + 25, y + 4, width=1.0, fill="#dbe9ff", smooth=True),
                text(x + 20, y + 10, "%", size=7),
                line(x + 5, y + 13, x + 16, y + 12, width=1.2, fill="#9bb8e5"),
                line(x + 5, y + 20, x + 22, y + 19, width=1.2, fill="#9bb8e5"),
                line(x + 5, y + 27, x + 18, y + 26, width=1.2, fill="#9bb8e5"),
                _rounded_rect(self.canvas, x + 5, y + 31, x + 25, y + 36, 3, fill="#ecf3ff", outline=color, width=1.0),
                line(x + 7, y + 33.5, x + 7 + fill_width, y + 33.5, width=2.3, fill=color),
            ]
        )

    elif shape == "mini_bar":
        percent = self._last_codex_usage_status.usage_remaining_percent
        width = 32
        ratio = max(0.1, min(1.0, (percent or 38) / 100))
        fill_width = round((width - 8) * ratio)
        items.extend(
            [
                card(x, y, x + width, y + 11, 5, fill="#f2f7ff", width=detail_w),
                line(x + 4, y + 5.5, x + 4 + fill_width, y + 5.5, width=3, fill=color),
            ]
        )
        for tx in (x + 10, x + 18, x + 26):
            items.append(line(tx, y + 2, tx, y + 9, width=0.8, fill="#c9d8ee"))

    elif shape == "red_pen":
        items.extend(
            [
                line(x + 1, y + 26, x + 10, y + 17, x + 24, y + 4, width=4.0, smooth=True, fill="#fff7f5"),
                line(x + 1, y + 26, x + 10, y + 17, x + 24, y + 4, width=2.6, smooth=True),
                line(x + 20, y + 3, x + 29, y - 3, width=main_w),
                line(x + 23, y + 2, x + 27, y + 6, width=detail_w, fill="#a8473e"),
                line(x + 5, y + 30, x + 20, y + 29, width=detail_w),
                line(x + 18, y + 8, x + 23, y + 6, width=1.1, fill="#ffb3a9"),
            ]
        )

    elif shape in {"annotation_circle", "annotation_mark"}:
        items.extend(
            [
                self.canvas.create_arc(x - 2, y + 3, x + 28, y + 30, start=195, extent=300, outline=color, width=detail_w, style=tk.ARC),
                self.canvas.create_arc(x + 1, y + 6, x + 31, y + 32, start=30, extent=225, outline=color, width=1.0, style=tk.ARC),
                line(x + 3, y + 25, x + 16, y + 9, x + 28, y + 5, width=2.6, smooth=True),
                line(x + 5, y + 32, x + 28, y + 31, width=detail_w),
                line(x + 22, y + 9, x + 28, y + 5, x + 25, y + 12, width=1.1, fill=color, smooth=True),
            ]
        )

    elif shape in {"z_mark", "sleep_cloud"}:
        if shape == "sleep_cloud":
            items.extend(
                [
                    self.canvas.create_oval(x - 3, y + 24, x + 24, y + 36, fill="#eeeeee", outline=""),
                    self.canvas.create_oval(x + 14, y + 22, x + 38, y + 36, fill="#f3f3f3", outline=""),
                    line(x - 1, y + 34, x + 36, y + 34, width=1.0, fill="#d8d8d8"),
                ]
            )
            z_y = y
        else:
            z_y = y
        items.extend(
            [
                line(x, z_y + 6, x + 12, z_y + 5, x + 3, z_y + 17, x + 15, z_y + 16, width=detail_w),
                line(x + 17, z_y + 2, x + 27, z_y + 1, x + 20, z_y + 11, x + 30, z_y + 10, width=1.25),
                line(x + 31, z_y - 2, x + 38, z_y - 3, x + 33, z_y + 5, x + 40, z_y + 4, width=1.0, fill="#a0a0a0"),
            ]
        )

    elif shape == "warning":
        points = (x + 13, y + 1, x + 27, y + 24, x + 1, y + 25)
        items.extend(
            [
                self.canvas.create_polygon(points, fill="#fff6f2", outline=color, width=main_w),
                line(x + 14, y + 8, x + 13, y + 16, width=detail_w),
                self.canvas.create_oval(x + 12, y + 20, x + 15, y + 23, fill=color, outline=""),
                line(x - 2, y + 5, x + 2, y + 8, width=1.0),
                line(x + 27, y + 4, x + 23, y + 8, width=1.0),
            ]
        )

    elif shape in {"magnifier", "bug_evidence"}:
        items.extend(
            [
                oval(x, y + 2, x + 18, y + 20, fill="#fbfdff", width=main_w),
                line(x + 14, y + 18, x + 25, y + 30, width=main_w),
                line(x + 4, y + 7, x + 9, y + 5, width=1.0, fill="#c9d7e2"),
                card(x + 19, y - 2, x + 36, y + 10, 3, fill="#fff9f0", outline=color, width=1.2),
                line(x + 23, y + 3, x + 32, y + 2, width=1.0),
                line(x + 23, y + 7, x + 30, y + 6, width=1.0),
                line(x + 4, y + 27, x + 16, y + 25, width=1.0, fill="#dcb6b6"),
            ]
        )

    elif shape == "stamp":
        items.extend(
            [
                card(x, y + 14, x + 29, y + 27, 4, fill="#fff7f5"),
                line(x + 8, y + 14, x + 12, y + 3, x + 17, y + 3, x + 22, y + 14, width=detail_w, smooth=True),
                line(x + 6, y + 21, x + 23, y + 20, width=1.1, fill="#e5aaa1"),
            ]
        )

    elif shape in {"lock", "tab_bar", "tab_stack"}:
        for index in range(3):
            items.append(card(x + index * 7, y + index * 3, x + 24 + index * 7, y + 15 + index * 3, 4, fill="#f9f6ff", width=detail_w))
            items.append(line(x + 5 + index * 7, y + 6 + index * 3, x + 17 + index * 7, y + 5 + index * 3, width=1.0, fill="#aaa0db"))
        if shape == "lock":
            items.extend(
                [
                    self.canvas.create_arc(x + 25, y + 18, x + 36, y + 30, start=0, extent=180, outline=color, width=1.5, style=tk.ARC),
                    card(x + 23, y + 24, x + 38, y + 36, 3, fill="#f9f6ff", width=1.5),
                ]
            )

    elif shape == "quiet_aura":
        items.extend(
            [
                self.canvas.create_arc(x + 8, y + 18, x + 70, y + 84, start=205, extent=115, outline="#ded9ee", width=1.1, style=tk.ARC),
                self.canvas.create_arc(x + 2, y + 12, x + 78, y + 92, start=210, extent=92, outline="#eeeaf7", width=1.0, style=tk.ARC),
                self.canvas.create_oval(x + 67, y + 38, x + 72, y + 43, fill=color, outline=""),
                self.canvas.create_arc(x + 57, y + 26, x + 68, y + 37, start=80, extent=230, outline=color, width=1.2, style=tk.ARC),
            ]
        )

    elif shape == "gremlin_spark":
        for points in (((x + 5, y + 4), (x + 11, y + 0), (x + 9, y + 8), (x + 16, y + 6)), ((x + 21, y + 18), (x + 28, y + 14), (x + 25, y + 23)), ((x + 3, y + 22), (x + 8, y + 18))):
            flat = [coord for point in points for coord in point]
            items.append(line(*flat, width=1.6, fill=color, smooth=True))

    elif shape == "meltdown_shadow":
        items.extend(
            [
                self.canvas.create_oval(x, y + 25, x + 60, y + 40, fill="#f1dfe5", outline=""),
                self.canvas.create_oval(x + 12, y + 20, x + 46, y + 37, fill="#f6e8ed", outline=""),
                line(x + 8, y + 34, x + 48, y + 33, width=1.0, fill="#dab7c4"),
                self.canvas.create_oval(x + 48, y + 20, x + 55, y + 27, fill=color, outline=Paper, width=1),
                line(x + 51.5, y + 22, x + 51.5, y + 25, width=0.9, fill=Paper),
            ]
        )

    if items:
        self._apply_actor_transform_to_items(items)
        for item in items:
            self.canvas.addtag_withtag("decoration", item)
        self._decoration_items.setdefault(lifetime, []).extend(items)
        self.canvas.tag_raise("decoration")


def _decoration_anchor(self: Any, definition: DecorationDefinition) -> tuple[float, float]:
    anchors = {
        "upper_left": (PAL_PAD_X + PAL_WIDTH * 0.04, PAL_PAD_Y + PAL_HEIGHT * 0.08),
        "upper_right": (PAL_PAD_X + PAL_WIDTH * 0.68, PAL_PAD_Y + PAL_HEIGHT * 0.05),
        "upper_center": (PAL_CENTER_X - 16, PAL_PAD_Y - 8),
        "above_head": (PAL_PAD_X + PAL_WIDTH * 0.34, PAL_PAD_Y - 12),
        "lower_left": (PAL_PAD_X + PAL_WIDTH * 0.06, PAL_PAD_Y + PAL_HEIGHT * 0.74),
        "lower_right": (PAL_PAD_X + PAL_WIDTH * 0.58, PAL_PAD_Y + PAL_HEIGHT * 0.73),
        "right_side": (PAL_PAD_X + PAL_WIDTH * 0.78, PAL_PAD_Y + PAL_HEIGHT * 0.38),
        "left_side": (PAL_PAD_X - 6, PAL_PAD_Y + PAL_HEIGHT * 0.38),
        "ground": (PAL_PAD_X + PAL_WIDTH * 0.04, PAL_CANVAS_HEIGHT - 44),
        "around_character": (PAL_PAD_X - 10, PAL_PAD_Y - 6),
    }
    x, y = anchors.get(definition.anchor, anchors["upper_right"])
    return x + definition.dx, y + definition.dy
