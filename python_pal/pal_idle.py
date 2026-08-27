"""Idle life and scheduling layer.

Everything that makes the pet look alive when nobody asked it to: the idle and
ambient timers, micro-behaviour picking, blink and gaze scheduling, cursor
following, the doze sequence, and the idle tail pose. `IdleMixin` is mixed into
PaperclipPalApp.
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk

from .animation_resolver import ResolvedAnimation
from .decision import DecisionResult
from .pal_geometry import (
    ANIM_TICK_SCALE, PAL_CENTER_X, PAL_HEIGHT, PAL_LOOK_CENTER_X,
    PAL_LOOK_CENTER_Y, PAL_PAD_Y, _clamp,
)
from .pal_motion import (
    ACTION_DECORATION_CUES, ACTION_FRAMES, COMMON_IDLE_ACTIONS,
    INNER_GESTURE_FRAMES, LARGE_IDLE_ACTIONS, LOW_STIMULUS_IDLE_ACTIONS,
    MID_IDLE_ACTIONS, MOVE_ACTION_DURATIONS, MOVE_IDLE_ACTIONS,
    RARE_IDLE_ACTIONS, TAIL_MOTION_FRAMES, TAIL_OSCILLATIONS, TAIL_POSTURES,
    TailPose, _POSTURE_ENTER_S, _POSTURE_EXIT_S,
)
from .pal_window import GLOBAL_MOUSE_POLL_MS
from .prop_shapes import ACTION_PROP_CUES, prop_cue_duration_ms
from .state import Reaction

AMBIENT_MIN_MS = 18_000
AMBIENT_MAX_MS = 45_000
AMBIENT_COOLDOWN_SECONDS = 50
BLINK_MIN_MS = 3200
BLINK_MAX_MS = 8200
LOOK_MIN_MS = 1200
LOOK_MAX_MS = 3600
MOUSE_FOLLOW_TICK_MS = 75
MOUSE_FOLLOW_COOLDOWN_MS = 1800
MOUSE_FOLLOW_NEAR_RADIUS = 150


class IdleMixin:
    """Idle timers, gaze, blinking, cursor following and dozing."""

    def _schedule_micro(self) -> None:
        interval = self.mood.micro_interval_ms()
        self._micro_after = self.root.after(interval, self._micro_tick)

    def _micro_tick(self) -> None:
        self._micro_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            interruptibility = self._interruptibility()
            if not interruptibility.allow_speech:
                if interruptibility.allow_animation and random.random() < 0.18:
                    self._play_idle_animation(self._pick_idle_animation(micro=True, low_stimulus=True), source="micro_quiet")
                self._schedule_micro()
                return
            action = self._pick_idle_animation(micro=True)
            if action:
                self._play_idle_animation(action, source="micro")
        self._schedule_micro()

    def _schedule_companion(self) -> None:
        self._companion_after = self.root.after(self.mood.companion_interval_ms(), self._companion_tick)

    def _companion_tick(self) -> None:
        self._companion_after = None
        if not self._large_action_running and not self.state.brain_busy and not self._dragging:
            policy = self._activity_policy()
            interruptibility = self._interruptibility()
            if not interruptibility.allow_speech:
                if interruptibility.allow_animation and random.random() < 0.28:
                    self._play_idle_animation(self._pick_idle_animation(low_stimulus=True), source="companion_quiet")
                self._schedule_companion()
                return
            if random.random() < policy.mouse_follow_chance:
                self._start_mouse_follow(random.randint(850, 1700))
            if random.random() < policy.companion_action_chance:
                self._play_idle_animation(self._pick_idle_animation(), source="companion")
            if (
                not self._bubble_items
                and self.state.can_speak(max(8, round(self.mood.ambient_cooldown_seconds() * policy.cooldown_multiplier)))
                and random.random() < policy.companion_chatter_chance
            ):
                self._ask_brain("ambient", allow_live=False)
        self._schedule_companion()

    # ── daily greeting ──────────────────────────────────────────────

    def _pick_idle_animation(self, micro: bool = False, low_stimulus: bool = False) -> str:
        if low_stimulus:
            return random.choice(LOW_STIMULUS_IDLE_ACTIONS)

        now = time.time()
        pack = self._current_identity_pack()
        candidates: list[tuple[str, float, str]] = []
        identity_idle = pack.animations.get("idle", "")
        if identity_idle and not micro:
            weight = 4.0 if now - self._last_identity_idle_action_at > 45 else 1.2
            candidates.append((identity_idle, weight, "identity_idle"))
        for action in pack.core_animations:
            candidates.append((action, 2.2 if not micro else 1.2, "identity_core"))

        mood_action = self.mood.pick_micro_behavior()
        if mood_action:
            candidates.append((mood_action, 2.4, "mood"))
        candidates.extend((action, 1.5, "common") for action in COMMON_IDLE_ACTIONS)

        policy = self._activity_policy()
        if not micro or policy.tier in {"active", "hyper"}:
            candidates.extend((action, 0.9, "mid") for action in MID_IDLE_ACTIONS)
        if not micro and policy.tier in {"active", "hyper"}:
            candidates.extend((action, 0.28 if policy.tier == "active" else 0.46, "rare") for action in RARE_IDLE_ACTIONS)

        usable: list[tuple[str, float, str, ResolvedAnimation]] = []
        for name, weight, source in candidates:
            resolved = self.animation_resolver.resolve(name)
            if not self._idle_animation_allowed(resolved, micro=micro):
                continue
            if resolved.requested in self._recent_idle_actions[-5:] or resolved.action in self._recent_idle_actions[-5:]:
                weight *= 0.35
            if resolved.requested in self._recent_idle_actions[-2:] or resolved.action in self._recent_idle_actions[-2:]:
                weight *= 0.18
            if weight > 0.05:
                usable.append((name, weight, source, resolved))

        if not usable:
            return random.choice(LOW_STIMULUS_IDLE_ACTIONS)
        names, weights, sources, resolved_items = zip(*usable)
        choice_index = random.choices(range(len(names)), weights=weights, k=1)[0]
        chosen = names[choice_index]
        resolved = resolved_items[choice_index]
        self._last_idle_animation_debug = self._idle_animation_debug_text(chosen, sources[choice_index], resolved)
        if sources[choice_index].startswith("identity"):
            self._last_identity_idle_action_at = time.time()
        return chosen

    def _idle_animation_allowed(self, resolved: ResolvedAnimation, micro: bool = False) -> bool:
        name = resolved.performance or resolved.action
        if not name or name == "idle":
            return True
        now = time.time()
        if name in LARGE_IDLE_ACTIONS and now - self._last_large_idle_action_at < (35 if micro else 60):
            return False
        if name in MOVE_IDLE_ACTIONS and now - self._last_move_idle_action_at < 180:
            return False
        if self._recent_idle_actions and self._recent_idle_actions[-1] == name:
            return False
        return True

    def _play_idle_animation(self, name: str, source: str = "idle") -> None:
        resolved = self.animation_resolver.resolve(name)
        played = resolved.performance or resolved.action
        if not played or played == "idle":
            self._last_idle_animation_debug = self._idle_animation_debug_text(name, source, resolved)
            return
        if resolved.kind == "performance" and resolved.performance:
            reaction = Reaction(False, "", self.state.mood or "idle", resolved.action or "blink", "thought", resolved.performance, event=f"idle_{source}")
            self._run_performance_phrase(resolved.performance, reaction, state="idle")
        else:
            self._perform_action(resolved.action)
        self._remember_idle_animation(played)
        if source != "identity_switch":
            self._queue_action_decoration_cue(resolved.action)
        self._last_idle_animation_debug = self._idle_animation_debug_text(name, source, resolved)

    def _remember_idle_animation(self, played: str) -> None:
        self._recent_idle_actions.append(played)
        self._recent_idle_actions = self._recent_idle_actions[-8:]
        if played in LARGE_IDLE_ACTIONS:
            self._last_large_idle_action_at = time.time()
        if played in MOVE_IDLE_ACTIONS:
            self._last_move_idle_action_at = time.time()

    def _idle_animation_debug_text(self, requested: str, source: str, resolved: ResolvedAnimation) -> str:
        return (
            f"current_identity: {self._active_identity_id or 'default_pal'}\n"
            f"visual_addons: {', '.join(self._active_identity_addons) or 'none'}\n"
            f"selected_idle_animation: {requested}\n"
            f"resolver_result: kind={resolved.kind}, action={resolved.action}, performance={resolved.performance or 'none'}\n"
            f"fallback_reason: {resolved.fallback_reason or 'none'}\n"
            f"source: {source}\n"
            f"recent_idle_actions: {', '.join(self._recent_idle_actions[-8:]) or 'none'}"
        )

    def _idle_tail_pose(self) -> TailPose:
        phase = self._tail_idle_phase
        long = self._tail_mode == "long"
        # long tail: broader, lazier sway — the length amplifies visually
        # short tail: tighter, snappier
        # resting amplitudes stay small so the idle tail hugs the original
        # silhouette; actions and moods bring the big bends
        if long:
            amp = 0.34 + self.mood.energy * 0.30
            sway = (
                math.sin(phase * 0.42) * amp
                + math.sin(phase * 0.97) * amp * 0.18
                + math.sin(phase * 1.73) * amp * 0.06
            )
            curl = math.sin(phase * 0.35) * 0.38
        else:
            amp = 0.20 + self.mood.energy * 0.24
            sway = math.sin(phase * 0.72) * amp + math.sin(phase * 1.55) * amp * 0.12
            curl = math.sin(phase * 0.48) * 0.30
        droop = 0.0
        tuck = 0.0
        stiffen = 0.0
        mood = (self.state.mood or "").lower()
        if mood in {"smirk", "smug", "proud", "happy", "done"}:
            sway *= 1.45 if not long else 1.2
            curl += 1.4 if not long else 1.2
        elif mood in {"sleepy", "bored"} or self._doze_stage >= 1:
            sway *= 0.35 if long else 0.45
            curl -= 0.5
            droop = (5.0 if long else 3.4) + math.sin(phase * 0.38) * 0.6
        elif mood in {"sulky", "guilty", "shy"}:
            sway *= 0.45 if long else 0.55
            curl -= 0.8
            tuck = (3.6 if long else 2.4) + math.sin(phase * 0.5) * 0.4
        elif mood in {"startled", "worried"}:
            sway *= 0.75
            stiffen = 2.4
        return (sway, curl, droop, tuck, stiffen)

    def _schedule_idle(self, first: bool = False) -> None:
        if first:
            delay = 10_000
        else:
            low = max(8, self.soul.idle_min_seconds)
            high = max(low, self.soul.idle_max_seconds)
            delay = random.randint(low, high) * 1000
        self.root.after(delay, self._idle_tick)

    def _idle_tick(self) -> None:
        if self._doze_stage >= 2:
            self._schedule_idle()
            return
        policy = self._activity_policy()
        idle_cooldown = max(12, round(self.soul.cooldown_seconds * policy.cooldown_multiplier))
        if (
            not self._auto_reactions_paused()
            and policy.ambient_enabled
            and self.state.can_speak(idle_cooldown)
        ):
            context = self.ears.sample()
            if context.idle_seconds > 75 and random.random() < 0.70:
                self._ask_brain("bored", allow_live=False)
            elif context.idle_seconds > 15 or random.random() < 0.35:
                self._ask_brain("idle", allow_live=False)
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
        interruptibility = self._interruptibility()
        if not interruptibility.allow_speech:
            self.decision.last_decision = DecisionResult(
                False,
                event="ambient",
                reason=interruptibility.reason,
                pattern="interruptibility",
                reaction_style="silent_watch",
                blocked_rules=[f"interruptibility:{interruptibility.mode}"],
            )
            if interruptibility.allow_animation and not self._dragging and not self._large_action_running:
                self._apply_alive_cue(self.alive.observe_silence("ambient", interruptibility.reason))
            self._schedule_ambient()
            return
        policy = self._activity_policy()
        if not policy.ambient_enabled:
            self._schedule_ambient()
            return
        world = self._world_state()
        cooldown = max(
            10,
            round(min(AMBIENT_COOLDOWN_SECONDS, self.mood.ambient_cooldown_seconds()) * policy.cooldown_multiplier),
        )
        decision = self.decision.ambient_decision(
            world,
            cooldown_seconds=cooldown,
            chance_multiplier=self.mood.ambient_chance_multiplier() * policy.proactive_detection,
            bubble_visible=bool(self._bubble_items),
        )
        if decision.should_react:
            self._ask_brain("ambient", world, allow_live=False)
        self._schedule_ambient()

    def _update_doze(self) -> None:
        """Progressive doze sequence when user is idle for extended periods."""
        now = time.time()
        # Throttle ears.sample() — only check every ~2 seconds
        if self._anim_tick % 60 != 0 and self._doze_stage < 3:
            return
        try:
            idle_secs = self.ears.sample().idle_seconds
        except Exception:
            idle_secs = 0
        if idle_secs < 30:
            if self._doze_stage > 0:
                if self._doze_stage >= 2:
                    self._spring.kick_stretch(3.0)
                    self._spring_active = True
                    self._transition_expression("wide", "innocent", 2000)
                    self._emit_particles("exclaim")
                else:
                    self._reset_expression_pose()
                self._doze_stage = 0
                self._hide_sleep_blanket()
            self._last_active_time = now
            return
        idle_duration = now - self._last_active_time
        if self._doze_stage == 0 and idle_duration > 120:
            # stage 1: drowsy — eyes half-closed, brows drooping, yawn
            self._doze_stage = 1
            self._transition_expression("sleepy_slit", "droop", 120_000)
            self._run_inner_gesture("inner_yawn")
            self.set_chin_mode("sulk")
        elif self._doze_stage == 1 and idle_duration > 240:
            # stage 2: fully asleep — eyes closed, zzz particles
            self._doze_stage = 2
            self._transition_expression("closed", "droop", 600_000)
            self.set_chin_mode("sulk")
            self._emit_particles("zzz")
            self._show_sleep_blanket()
        elif self._doze_stage == 2:
            # periodic zzz while sleeping
            self._show_sleep_blanket()
            if self._anim_tick % 300 == 0:
                self._emit_particles("zzz")
            if idle_secs < 10:
                # wake up!
                self._doze_stage = 3
                self._doze_timer = now
                self._spring.kick_stretch(3.0)
                self._spring_active = True
                self._transition_expression("wide", "innocent", 2000)
                self._emit_particles("exclaim")
        elif self._doze_stage == 3 and now - self._doze_timer > 2:
            self._doze_stage = 0
            self._last_active_time = now
            self._hide_sleep_blanket()

    def _drag_struggle(self) -> None:
        """Small wiggle while being dragged — the pal 'struggles'."""
        if not self._dragging:
            return
        self._spring.kick_squash(0.8)
        self._spring_active = True

    def _schedule_blink(self) -> None:
        self.root.after(self.mood.blink_interval_ms(), self._blink_tick)

    def _blink_tick(self) -> None:
        if not self._dragging and not self._rebound_after and not self._large_action_running and not self._window_move_running:
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
            and not self._window_move_running
            and self._doze_stage < 1
            and time.time() >= self._mouse_follow_until
        ):
            if self._should_start_selective_mouse_follow():
                self._start_mouse_follow(random.randint(850, 1500))
            elif self._maybe_secret_judge():
                pass
            else:
                self._animate_look(self._pick_look_target())
        self._schedule_look()

    def _maybe_secret_judge(self) -> bool:
        """idle 时偶尔偷偷审判用户；鼠标一靠近就瞬间装乖。"""
        if random.random() >= 0.10:
            return False
        if self._is_pointer_near_pal() or self._bubble_items or self.state.brain_busy:
            return False
        self._secret_judge_until = time.time() + random.uniform(1.8, 3.2)
        self._set_brow_pose("judge")
        self._set_eye_pose("side_eye")
        self._secret_judge_tick()
        return True

    def _secret_judge_tick(self) -> None:
        if self._large_action_running or self._dragging or time.time() >= self._secret_judge_until:
            self._secret_judge_until = 0.0
            self._reset_expression_pose()
            return
        if self._is_pointer_near_pal():
            # 被抓包：切回无辜的速度快得可疑，然后补一个慢眨眼。
            self._secret_judge_until = 0.0
            self._perform_micro_action("micro_snap_innocent")
            self._expression_after.append(self.root.after(700, self._slow_blink))
            return
        self._expression_after.append(self.root.after(120, self._secret_judge_tick))

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

    def _is_pointer_near_pal(self) -> bool:
        pointer_x, pointer_y = self.root.winfo_pointerxy()
        center_x = self.root.winfo_x() + PAL_CENTER_X
        center_y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT * 0.40
        return math.hypot(pointer_x - center_x, pointer_y - center_y) <= MOUSE_FOLLOW_NEAR_RADIUS

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
