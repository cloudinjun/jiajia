"""Decoration and costume-prop layer.

Identity decorations (status dots, role badges, paper props) and the britclip
costume: drawing them, animating them onto and off the character, and the
lifetime bookkeeping that decides when each is cleared. `DecorMixin` is mixed
into JiajiaApp.
"""
from __future__ import annotations

import math
import random
import re
import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .decorations import DecorationDefinition
from .language import normalize_language
from .pal_canvas import _rounded_rect
from .pal_geometry import (
    TRANSPARENT,
    BROW, DECORATION_SCALE, PAL_CENTER_X, PAL_HEIGHT, PAL_PAD_X, PAL_PAD_Y,
    PAL_SCALE, PAL_SCALE_PIVOT_Y, PAL_WIDTH, WIRE, _clamp, _ease_out_sine,
    _smoothstep, _source_point,
)
from .pal_motion import (
    ACTION_DECORATION_CUES, ACTION_FRAMES, IDENTITY_STATE_CUES, PropFrames,
)
from .state import Reaction
from .svg_canvas import draw_svg_asset


@dataclass
class AppearanceState:
    costume_id: str = ""
    phase: str = "plain"
    language_mode: str = "zh-CN"


class DecorMixin:
    """Identity decorations and costume props."""

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

    def _gentleman_hat_head_anchor(self) -> tuple[float, float]:
        return self._pal_source_point(151.0, -8.0)

    def _gentleman_tail_anchor(self) -> tuple[float, float]:
        if self.tail_wire:
            bbox = self.canvas.bbox(self.tail_wire)
            if bbox:
                return (bbox[2] + 10, bbox[1] + 10)
        return self._pal_source_point(301.0, 250.726)

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

    def _load_identity_setting(self) -> str:
        return self._valid_identity_id(str(self._load_settings().get("identity") or "auto"))

    def _save_identity_setting(self, identity_id: str) -> None:
        self._save_setting("identity", self._valid_identity_id(identity_id))

    def _valid_identity_id(self, identity_id: str) -> str:
        key = identity_id.strip().lower().replace("-", "_").replace(" ", "_")
        if key == "auto":
            return key
        return key if key in self.brain.identities.packs else "auto"

    def _queue_action_decoration_cue(self, action: str) -> None:
        cue = ACTION_DECORATION_CUES.get(action)
        if not cue:
            return
        decoration_id, milliseconds = cue
        self._queue_temporary_decoration(decoration_id, milliseconds, delay_ms=self._animation_duration_ms(action) + 40)

    def _show_identity_debug(self) -> None:
        context = self._context("manual")
        pack = self.brain.identities.select("manual", context)
        mode = self._identity_var.get()
        prefix = f"mode: {mode}\nselected: {pack.display_name}\n"
        self.show_bubble(
            prefix + pack.prompt_brief(self.soul.language), milliseconds=7600, kind="thought"
        )

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
