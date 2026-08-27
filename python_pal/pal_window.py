"""Win32 and window-placement layer.

Everything that talks to the OS about where the pet lives: user32 lookups,
monitor geometry, taskbar hiding, global mouse polling, and the screen-bounds
maths the move actions clamp against. `WindowMixin` is mixed into
PaperclipPalApp; it only touches `self.root`, `self.width/height` and the
mouse-follow fields.
"""
from __future__ import annotations

import ctypes
import random
import time
import tkinter as tk

from .pal_geometry import (
    PAL_CENTER_X, PAL_HEIGHT, PAL_PAD_X, PAL_PAD_Y, PAL_SCALE_CENTER_Y,
    PAL_WIDTH, ActionFrames, _clamp, _geometry_position, _geometry_with_size,
)

GLOBAL_MOUSE_POLL_MS = 24
PAL_HIT_MARGIN_X = 70
PAL_HIT_MARGIN_Y = 58


class _WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class _WinRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

class _WinMonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _WinRect),
        ("rcWork", _WinRect),
        ("dwFlags", ctypes.c_ulong),
    ]

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


class WindowMixin:
    """Window placement, monitor geometry and global pointer polling."""

    def _place_initially(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(40, round(screen_w - PAL_PAD_X - PAL_WIDTH - 84))
        y = max(40, round(screen_h - PAL_PAD_Y - PAL_HEIGHT - 84))
        self.root.geometry(_geometry_with_size(self.width, self.height, x, y))

    def _desktop_bounds(self) -> tuple[int, int, int, int]:
        if self._user32 and self.root.tk.call("tk", "windowingsystem") == "win32":
            try:
                left = int(self._user32.GetSystemMetrics(76))
                top = int(self._user32.GetSystemMetrics(77))
                width = int(self._user32.GetSystemMetrics(78))
                height = int(self._user32.GetSystemMetrics(79))
                if width > 0 and height > 0:
                    return (left, top, left + width, top + height)
            except Exception:
                pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _monitor_bounds_for_point(self, x: float, y: float) -> tuple[int, int, int, int]:
        if self._user32 and self.root.tk.call("tk", "windowingsystem") == "win32":
            try:
                point = _WinPoint(round(x), round(y))
                monitor = self._user32.MonitorFromPoint(point, 2)  # nearest monitor
                if monitor:
                    info = _WinMonitorInfo()
                    info.cbSize = ctypes.sizeof(_WinMonitorInfo)
                    if self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                        rect = info.rcWork
                        if rect.right > rect.left and rect.bottom > rect.top:
                            return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
            except Exception:
                pass
        return self._desktop_bounds()

    def _pal_screen_point(self, x: float = PAL_CENTER_X, y: float = PAL_SCALE_CENTER_Y) -> tuple[float, float]:
        self.root.update_idletasks()
        return (self.root.winfo_x() + x, self.root.winfo_y() + y)

    def _pal_monitor_bounds(self) -> tuple[int, int, int, int]:
        x, y = self._pal_screen_point()
        return self._monitor_bounds_for_point(x, y)

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
            self._popup_context_menu()
        self._global_left_down = left_down
        self._global_right_down = right_down
        self.root.after(GLOBAL_MOUSE_POLL_MS, self._poll_global_mouse)

    def _point_in_pal_hitbox(self, x_root: int, y_root: int) -> bool:
        self.root.update_idletasks()
        left = self.root.winfo_x() + PAL_PAD_X - PAL_HIT_MARGIN_X
        top = self.root.winfo_y() + PAL_PAD_Y - PAL_HIT_MARGIN_Y
        right = self.root.winfo_x() + PAL_PAD_X + PAL_WIDTH + PAL_HIT_MARGIN_X
        bottom = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + PAL_HIT_MARGIN_Y
        return left <= x_root <= right and top <= y_root <= bottom

    def _movement_direction(self) -> int:
        self.root.update_idletasks()
        center_x = self.root.winfo_x() + self.width / 2
        left, _top, right, _bottom = self._desktop_bounds()
        screen_mid = (left + right) / 2
        if abs(center_x - screen_mid) < 120:
            return random.choice((-1, 1))
        return -1 if center_x > screen_mid else 1

    def _relocation_delta(self, distance: int) -> float:
        return self._movement_direction() * distance

    def _corner_retreat_delta(self) -> tuple[float, float]:
        self.root.update_idletasks()
        left, _top, right, bottom = self._desktop_bounds()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        target_x = left + 18 if current_x < (left + right) / 2 else right - self.width - 18
        target_y = bottom - self.height - 28
        return target_x - current_x, target_y - current_y

    def _clamped_window_frames(self, frames: ActionFrames, start_x: int, start_y: int) -> ActionFrames:
        final_dx, final_dy, _sx, _sy, _delay = frames[-1]
        left, top, right, bottom = self._desktop_bounds()
        max_x = max(left, right - self.width)
        max_y = max(top, bottom - self.height)
        clamped_final_x = _clamp(start_x + final_dx, left, max_x)
        clamped_final_y = _clamp(start_y + final_dy, top, max_y)
        allowed_dx = clamped_final_x - start_x
        allowed_dy = clamped_final_y - start_y
        ratio_x = allowed_dx / final_dx if final_dx else 1.0
        ratio_y = allowed_dy / final_dy if final_dy else 1.0
        # scale toward the clamped endpoint, then clamp every intermediate
        # frame too so mid-action dashes (zoomies, pounce) stay on screen
        return tuple(
            (
                _clamp(start_x + dx * ratio_x, left, max_x) - start_x,
                _clamp(start_y + dy * ratio_y, top, max_y) - start_y,
                sx,
                sy,
                delay,
            )
            for dx, dy, sx, sy, delay in frames
        )
