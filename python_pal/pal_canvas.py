"""Canvas drawing layer.

Owns how the character is put on the canvas: the actor-space transform
(bend -> scale -> offset), the wire/eye/brow items, shadow and melt puddle,
and every face channel (eye openness, pupils, brows, shaped-pupil FX, decals,
blush). `CanvasMixin` is mixed into PaperclipPalApp.

Bubble shape primitives live here too — they are pure canvas geometry.
"""
from __future__ import annotations

import math
import time
import tkinter as tk

from .pal_geometry import (
    BODY_CURVES, BODY_START, BROW, CHEEK_BLUSH, EYE_WHITE, LEFT_BROW_CURVES,
    LEFT_BROW_START, PAL_CENTER_X, PAL_HEIGHT, PAL_PAD_X, PAL_PAD_Y, PAL_SCALE,
    PAL_SCALE_PIVOT_Y, PAL_WIDTH, PUPIL, RIGHT_BROW_CURVES, RIGHT_BROW_START,
    TAIL_LONG_CURVES, TAIL_LONG_START, TAIL_SHORT_CURVES, TAIL_SHORT_START,
    WIRE, _brow_pose_coords, _clamp, _ease_out_cubic, _oval_bounds,
    _path_coords, _per_tick, _scale_coords, _smoothstep, _source_point,
)
from .pal_motion import TAIL_TIP_LAG_MS, InnerPose
from .prop_shapes import EYE_FX_SHAPES, FACE_DECALS
from .rig_pose import bend_point, posed_chin_points, posed_tail_points

HARDWARE_TINTS = {
    "normal": WIRE,
    "unavailable": WIRE,
    "busy": "#aeb6c5",
    "cooling": "#b8b8b8",
    "warm": "#caa0a0",
    "hot": "#d86b6b",
    "overloaded": "#bd4343",
}


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


class CanvasMixin:
    """Drawing the character and every face channel onto the canvas."""

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

    def _raise_face_over_costume(self) -> None:
        for tag in ("eye", "pupil", "lid", "brow", "cheek"):
            try:
                self.canvas.tag_raise(tag)
            except tk.TclError:
                pass

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

    def _apply_hardware_tint(self) -> None:
        fill = HARDWARE_TINTS.get(self._hardware_tint_level, WIRE)
        self.canvas.itemconfigure("wire", fill=fill)
        for lid in self._lid_items:
            try:
                self.canvas.itemconfigure(lid, fill=fill)
            except tk.TclError:
                pass

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
