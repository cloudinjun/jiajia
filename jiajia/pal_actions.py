"""Action dispatch and scheduling layer.

`_perform_action` is the single entry point every action goes through; the
rest of this module runs one performance kind each — body keyframes, window
moves, the melt transition, tail motions (oscillator / posture / keyframe),
inner-core gestures, the body bend channel, the emotion prop with its staged
face script, and the small reflexes (blink, wiggle, scan).

`ActionMixin` is mixed into JiajiaApp.
"""
from __future__ import annotations

import math
import random
import time
import tkinter as tk
from typing import Callable

from .anim_physics import easing_for_action
from .pal_geometry import (
    ANIM_TICK_MS, LERP_TICK_MS, PAL_CENTER_X, PAL_PAD_Y, PAL_SCALE,
    ActionFrames, _clamp, _ease_out_cubic, _ease_out_sine,
    _geometry_position, _jitter_frames, _smoothstep, _source_point,
)
from .pal_motion import (
    ACTION_ACTING_CUES, ACTION_BODY_BEND, ACTION_INNER_GESTURES,
    ACTION_SELF_PARTICLES, ACTION_SHADOW_ACTIONS, ACTION_TAIL_MOTIONS,
    ACTION_FRAMES, BLINK_FRAMES, _acting_frames, BODY_BEND_NEUTRAL, GUILTY_DART_SEQUENCE,
    INNER_GESTURE_FRAMES, INNER_NEUTRAL_POSE, MELT_PUDDLE_HOLD_MS,
    MELT_RECOVERY_FRAMES, MELT_SINK_FRAMES, MOVE_ACTION_DURATIONS,
    MOVE_IDLE_ACTIONS, PAPER_PROP_ACTIONS, SCAN_LOOK_HOLD_MS,
    SCAN_LOOK_TARGETS, SLOW_BLINK_FRAMES, TAIL_HAND_POSE, TAIL_MOTION_FRAMES,
    TAIL_NEUTRAL_POSE, TAIL_OSCILLATIONS, TAIL_POSTURES, TAIL_TIP_LAG_MS,
    WIGGLE_FRAMES, _POSTURE_ENTER_S, _POSTURE_EXIT_S,
    BodyBend, InnerPose, PropFrames, TailPose,
    tail_hand_pose, tail_oscillation_pose, tail_posture_pose,
)
from .prop_shapes import (
    ACTION_FACE_SCRIPTS, ACTION_PROP_CUES, GRIP_POINTS, PROP_SHAPES, SHAPE_FX,
    apply_shape_fx, build_prop_timeline, inertia_step, prop_cue_duration_ms,
    transform_shape,
)


class ActionMixin:
    """Runs every kind of action performance."""

    def _run_prop_body_frames(self, frames: PropFrames) -> None:
        if not frames or self._large_action_running or self._window_move_running:
            return
        start = [self._action_offset[0], self._action_offset[1], self._pal_scale[0], self._pal_scale[1]]
        targets = frames

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(targets):
                self._set_action_offset(0.0, 0.0)
                self._set_pal_scale(1.0, 1.0)
                return
            dx, dy, sx, sy, delay = targets[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                start[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = _smoothstep((si + 1) / n)
            self._set_action_offset(start[0] + (dx - start[0]) * t, start[1] + (dy - start[1]) * t)
            self._set_pal_scale(start[2] + (sx - start[2]) * t, start[3] + (sy - start[3]) * t)
            self._prop_anim_after.append(self.root.after(LERP_TICK_MS, lambda: step(fi, si + 1)))

        step()

    def _animation_duration_ms(self, action_or_name: str) -> int:
        resolved = self.animation_resolver.resolve(action_or_name)
        action = resolved.action or action_or_name
        frames = ACTION_FRAMES.get(action)
        if frames:
            return sum(frame[-1] for frame in frames)
        cue = ACTION_PROP_CUES.get(action)
        if cue and cue.get("held") and cue.get("tail_style") == "wag":
            return prop_cue_duration_ms(action) + 160
        osc = TAIL_OSCILLATIONS.get(action)
        if osc:
            return round(float(osc["cycles"]) / float(osc["freq"]) * 1000) + 160
        posture = TAIL_POSTURES.get(action)
        if posture:
            return round((_POSTURE_ENTER_S + _POSTURE_EXIT_S) * 1000) + int(posture["hold_ms"]) + 180
        tail_frames = TAIL_MOTION_FRAMES.get(action)
        if tail_frames:
            return sum(frame[-1] for frame in tail_frames) + 140
        inner_frames = INNER_GESTURE_FRAMES.get(action)
        if inner_frames:
            return sum(frame[-1] for frame in inner_frames) + 130
        if action == "oops_innocent_combo":
            return 1500
        if action in {"britclip_enter", "british_gentleman_suit_up"}:
            return 3200
        if action == "britclip_exit":
            return 2300
        if action == "hat_tip_oops":
            return 950
        if action == "scan":
            return SCAN_LOOK_HOLD_MS * len(SCAN_LOOK_TARGETS)
        if action == "wiggle":
            return sum(f[2] for f in WIGGLE_FRAMES)
        if action == "blink":
            return 150
        if action in MOVE_IDLE_ACTIONS:
            return MOVE_ACTION_DURATIONS.get(action, 760)
        return 0

    def _prepare_action_acting(self, action: str) -> None:
        cue = ACTION_ACTING_CUES.get(action)
        if not cue:
            return
        eyes, brows, hold_ms, blush = cue
        self._transition_expression(eyes, brows, hold_ms=hold_ms)
        if blush:
            self._set_cheek_blush(True)

    def _perform_action(self, action: str) -> None:
        if not action or action == "idle":
            return
        self_particles = ACTION_SELF_PARTICLES.get(action)
        if self_particles:
            preset, delay_ms = self_particles
            self.root.after(delay_ms, lambda p=preset: self._emit_particles(p))
        # a new action reclaims the tail immediately; if it carries a prop,
        # _start_action_prop re-enters hand mode 30ms later
        self._tail_hand_mode = False
        self._run_action_prop(action)
        prop_actions = {
            "oops_innocent_combo",
            "britclip_enter",
            "britclip_exit",
            "british_gentleman_suit_up",
            "hat_tip_oops",
            "tip_hat",
            "bow_tie_check",
            "cane_tap",
            "polite_bow",
        }
        if action in {"melt", "meltdown"}:
            self._run_melt_action()
            return
        if action in PAPER_PROP_ACTIONS:
            self._run_paper_prop_action(action)
            return
        is_tail_action = (
            action in TAIL_MOTION_FRAMES
            or action in TAIL_OSCILLATIONS
            or action in TAIL_POSTURES
        )
        if not is_tail_action and action not in INNER_GESTURE_FRAMES and action not in prop_actions:
            self._cancel_tail_wag(reset=True)
        if is_tail_action:
            self._prepare_action_acting(action)
            motion, dur = self._tail_motion_for_action(action)
            self._run_tail_motion(motion, dur)
            return
        if action in INNER_GESTURE_FRAMES:
            self._prepare_action_acting(action)
            self._run_inner_gesture(action)
            return
        if action == "oops_innocent_combo":
            self._run_oops_innocent_combo()
            return
        if action in {"britclip_enter", "british_gentleman_suit_up"}:
            self._run_british_gentleman_suit_up()
            return
        if action == "britclip_exit":
            self._run_british_gentleman_suit_down()
            return
        if action in {"hat_tip_oops", "tip_hat"}:
            self._run_hat_tip_oops()
            return
        if action == "bow_tie_check":
            self._run_tail_motion("tail_tip_flick")
            self._set_brow_pose("proud")
            return
        if action == "cane_tap":
            self._run_tail_motion("tail_tip_flick")
            self._emit_particles("dust")
            return
        if action == "polite_bow":
            self._run_large_action(ACTION_FRAMES["nod"], "polite_bow")
            return
        if action in MOVE_IDLE_ACTIONS:
            self._run_window_move_action(action)
            return
        if action.startswith("micro_"):
            self._perform_micro_action(action)
            return
        if action == "bob":
            self._run_large_action(ACTION_FRAMES["nod"], "nod")
            return
        if action == "wiggle":
            self._prepare_action_acting(action)
            self._wiggle()
            return
        if action == "blink":
            self._blink()
            return
        if action == "slow_blink":
            self._slow_blink()
            return
        if action == "peek":
            self._prepare_action_acting(action)
            self._start_mouse_follow(1500, force=True)
            self._start_tail_for_action(action)
            self._start_inner_for_action(action)
            return
        if action == "scan":
            self._prepare_action_acting(action)
            self._scan()
            self._start_tail_for_action(action)
            self._start_inner_for_action(action)
            return
        frames = ACTION_FRAMES.get(action)
        if frames:
            self._run_large_action(frames, action)
            self._start_inner_for_action(action)

    def _run_paper_prop_action(self, action: str) -> None:
        cue = PAPER_PROP_ACTIONS.get(action)
        if not cue:
            return
        duration = int(cue.get("duration") or 4200)
        decoration = str(cue.get("decoration") or "")
        if decoration:
            self._show_temporary_decoration(decoration, duration)
        eyes = str(cue.get("eyes") or "")
        brows = str(cue.get("brows") or "")
        if eyes or brows:
            self._transition_expression(eyes or "round", brows or "neutral", max(800, duration - 400))
        tail = str(cue.get("tail") or "")
        if tail:
            self._run_tail_motion(tail)
        inner = str(cue.get("inner") or "")
        if inner:
            self._run_inner_gesture(inner)
        frames = cue.get("frames")
        if isinstance(frames, tuple):
            self._run_prop_body_frames(frames)

    def _run_tail_wag(self) -> None:
        self._run_tail_motion("tail_wag")

    def _start_tail_for_action(self, action: str) -> None:
        motion = ACTION_TAIL_MOTIONS.get(action)
        if motion:
            override, dur = self._tail_motion_for_action(action)
            self._run_tail_motion(override if override != action else motion, dur)

    def _start_inner_for_action(self, action: str) -> None:
        gesture = ACTION_INNER_GESTURES.get(action)
        if gesture:
            self._run_inner_gesture(gesture)

    def _tail_motion_for_action(self, action: str) -> tuple[str, float]:
        """Tail motion for an action, honouring a prop it rings or twirls.

        A prop held at the tip overrides the motion (ringing a bell is a wrist
        shake, not an arm swing) and pins the tail's duration to the prop's, so
        the tail never keeps moving after the prop is gone.
        """
        cue = ACTION_PROP_CUES.get(action)
        if cue and cue.get("held") and cue.get("tail_style") == "wag":
            motion = str(cue.get("tail_motion") or action)
            return motion, prop_cue_duration_ms(action) / 1000.0
        return action, 0.0

    def _run_tail_motion(self, motion: str, duration_s: float = 0.0) -> None:
        if not self.tail_wire:
            return
        # a hand that is carrying something does not wag
        if self._tail_hand_mode:
            return
        if motion in TAIL_OSCILLATIONS:
            self._run_tail_oscillation(TAIL_OSCILLATIONS[motion], motion, duration_s)
            return
        if motion in TAIL_POSTURES:
            self._run_tail_posture(TAIL_POSTURES[motion])
            return
        frames = TAIL_MOTION_FRAMES.get(motion)
        if not frames:
            return
        self._cancel_tail_wag(reset=False)

        def finish() -> None:
            self._tail_wag_after.clear()
            if motion in {"tail_wag", "tail_smug_sway"}:
                self._schedule_expression_reset(900)

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._tail_transition_to(TAIL_NEUTRAL_POSE, 140, finish)
                return
            sway, curl, droop, tuck, stiffen, delay = frames[index]
            target: TailPose = (sway, curl, droop, tuck, stiffen)
            self._tail_transition_to(target, delay, lambda: step(index + 1))

        step()

    def _run_tail_oscillation(self, params: dict[str, object], motion: str = "", duration_s: float = 0.0) -> None:
        """Drive the tail as a continuous damped pendulum — the cat-tail swing.

        The oscillator owns `_tail_s_phase` while running, so the swing IS the
        traveling wave (root leads, tip follows) instead of two sine sources
        beating against each other.
        """
        self._cancel_tail_wag(reset=False)
        self._tail_osc_active = True
        self._tail_wave_factor = params.get("wave")
        self._tail_engage = params.get("engage")
        start = time.monotonic()
        start_pose = self._tail_pose
        phase0 = self._tail_s_phase
        total_s = duration_s or float(params["cycles"]) / float(params["freq"])
        attack_s = max(0.05, float(params.get("attack", 0.2))) * total_s

        def finish() -> None:
            self._tail_osc_active = False
            self._tail_wave_factor = None
            self._tail_engage = None
            self._tail_wag_after.clear()
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 160)
            if motion in {"tail_wag", "tail_smug_sway"}:
                self._schedule_expression_reset(900)

        def tick() -> None:
            t = time.monotonic() - start
            sample = tail_oscillation_pose(params, t, duration_s)
            if sample is None:
                finish()
                return
            sway, curl, droop, tuck, stiffen, phase = sample
            # blend out of whatever pose the tail held when the swing began
            blend = _smoothstep(min(1.0, t / attack_s)) if attack_s > 0 else 1.0
            pose = (
                start_pose[0] * (1.0 - blend) + sway,
                start_pose[1] * (1.0 - blend) + curl,
                start_pose[2] * (1.0 - blend) + droop,
                start_pose[3] * (1.0 - blend) + tuck,
                start_pose[4] * (1.0 - blend) + stiffen,
            )
            self._tail_s_phase = phase0 + phase
            self._set_tail_pose(*pose)
            self._tail_wag_after.append(self.root.after(LERP_TICK_MS, tick))

        tick()

    def _run_tail_posture(self, params: dict[str, object]) -> None:
        """Hold an expressive tail posture (raised, hooked, bristled)."""
        self._cancel_tail_wag(reset=False)
        self._tail_osc_active = True  # owns the tail like an oscillation
        start = time.monotonic()
        start_pose = self._tail_pose

        def finish() -> None:
            self._tail_osc_active = False
            self._tail_wag_after.clear()
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 180)

        def tick() -> None:
            t = time.monotonic() - start
            sample = tail_posture_pose(params, t)
            if sample is None:
                finish()
                return
            blend = _smoothstep(min(1.0, t / _POSTURE_ENTER_S))
            pose = tuple(
                start_pose[i] * (1.0 - blend) + sample[i] for i in range(5)
            )
            self._set_tail_pose(*pose)  # type: ignore[arg-type]
            self._tail_wag_after.append(self.root.after(LERP_TICK_MS, tick))

        tick()

    def _tail_transition_to(
        self,
        target: TailPose,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._tail_pose
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_tail_pose(*target)
                if on_done:
                    on_done()
                return
            # smoothstep: zero velocity at both ends, so direction reversals
            # between wag keyframes swing like a pendulum instead of snapping
            t = _smoothstep((index + 1) / steps)
            pose = tuple(start[i] + (target[i] - start[i]) * t for i in range(5))
            self._set_tail_pose(*pose)  # type: ignore[arg-type]
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._tail_wag_after.append(after_id)

        tick()

    def _cancel_tail_wag(self, reset: bool = True) -> None:
        for after_id in self._tail_wag_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._tail_wag_after.clear()
        self._tail_osc_active = False
        self._tail_wave_factor = None
        self._tail_engage = None
        if reset:
            self._set_tail_pose(*TAIL_NEUTRAL_POSE)

    def _set_tail_wag_amount(self, amount: float) -> None:
        self._set_tail_pose(sway=amount)

    def _run_inner_gesture(self, gesture: str) -> None:
        frames = INNER_GESTURE_FRAMES.get(gesture)
        if not frames or not self._chin_wire:
            return
        self._cancel_inner_gesture(reset=False)
        self._inner_gesture_active = True

        def finish() -> None:
            self._inner_gesture_after.clear()
            self._inner_gesture_active = False

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._inner_transition_to(INNER_NEUTRAL_POSE, 130, finish)
                return
            tip_x, tip_y, mid_x, mid_y, delay = frames[index]
            self._inner_transition_to((tip_x, tip_y, mid_x, mid_y), delay, lambda: step(index + 1))

        step()

    def _inner_transition_to(
        self,
        target: InnerPose,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._inner_pose
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_chin_amount(*target)
                if on_done:
                    on_done()
                return
            t = _ease_out_sine((index + 1) / steps)
            pose = tuple(start[i] + (target[i] - start[i]) * t for i in range(4))
            self._set_chin_amount(*pose)  # type: ignore[arg-type]
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._inner_gesture_after.append(after_id)

        tick()

    def _cancel_inner_gesture(self, reset: bool = True) -> None:
        for after_id in self._inner_gesture_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._inner_gesture_after.clear()
        self._inner_gesture_active = False
        if reset:
            self._set_chin_amount(*INNER_NEUTRAL_POSE)

    def _sample_tail_trail(self, target_time: float) -> TailPose:
        """Return the tail pose as it was at target_time (for tip follow-through)."""
        trail = self._tail_pose_trail
        while len(trail) >= 2 and trail[1][0] <= target_time:
            trail.popleft()
        if not trail:
            return self._tail_pose
        first_time, first_pose = trail[0]
        if first_time >= target_time or len(trail) < 2:
            return first_pose
        second_time, second_pose = trail[1]
        span = second_time - first_time
        t = (target_time - first_time) / span if span > 0 else 1.0
        return tuple(first_pose[i] + (second_pose[i] - first_pose[i]) * t for i in range(5))  # type: ignore[return-value]

    # ── body bend channel ────────────────────────────────────────
    # Lean/hunch body language on top of the squash/offset channels. The bend
    # is folded into _actor_point, so eyes, brows, pupils, tail, and inner core
    # all follow it; only the body wire needs an explicit re-place.

    def _set_body_bend(self, lean: float, hunch: float) -> None:
        if (lean, hunch) == self._body_bend:
            return
        self._body_bend = (lean, hunch)
        self._apply_body_bend()

    def _apply_body_bend(self) -> None:
        """Re-place every absolutely-positioned part so it follows the bend."""
        if self._body_wire and self._body_base_coords:
            self.canvas.coords(self._body_wire, *self._actor_coords(self._body_base_coords))
        self._set_eye_openness(self._eye_openness)
        self._apply_brow_spec(*self._current_brow_spec)
        if self.tail_wire and self._tail_base_coords:
            self._set_tail_pose(*self._tail_pose)
        if self._chin_wire and self._chin_base_coords:
            self._set_chin_amount(*self._inner_pose)

    def _run_bend_motion(self, action: str) -> None:
        frames = ACTION_BODY_BEND.get(action)
        if not frames:
            # no bend script: ease any leftover bend back to neutral
            if self._body_bend != BODY_BEND_NEUTRAL and not self._bend_after:
                self._bend_transition_to(BODY_BEND_NEUTRAL, 180)
            return
        self._cancel_bend(reset=False)

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._bend_after.clear()
                return
            lean, hunch, delay = frames[index]
            self._bend_transition_to((lean, hunch), delay, lambda: step(index + 1))

        step()

    def _bend_transition_to(
        self,
        target: BodyBend,
        duration_ms: int,
        on_done: Callable[[], None] | None = None,
    ) -> None:
        start = self._body_bend
        steps = max(1, round(duration_ms / LERP_TICK_MS))

        def tick(index: int = 0) -> None:
            if index >= steps:
                self._set_body_bend(*target)
                if on_done:
                    on_done()
                return
            t = _smoothstep((index + 1) / steps)
            self._set_body_bend(
                start[0] + (target[0] - start[0]) * t,
                start[1] + (target[1] - start[1]) * t,
            )
            after_id = self.root.after(LERP_TICK_MS, lambda: tick(index + 1))
            self._bend_after.append(after_id)

        tick()

    def _cancel_bend(self, reset: bool = True) -> None:
        for after_id in self._bend_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._bend_after.clear()
        if reset:
            self._set_body_bend(*BODY_BEND_NEUTRAL)

    # ── emotion prop layer ───────────────────────────────────────
    # Every action carries an animated prop that performs the emotion (halo,
    # rain cloud, trophy, umbrella…). Shapes and timelines live in
    # prop_shapes.py and are shared with the GIF renderer.

    def _run_action_prop(self, action: str) -> None:
        cue = ACTION_PROP_CUES.get(action)
        if not cue or self._dragging:
            return
        # start one frame later so action dispatch (which may rebuild the
        # canvas via _reset_pal_geometry) cannot delete a just-drawn prop
        if self._action_prop_pending:
            try:
                self.root.after_cancel(self._action_prop_pending)
            except tk.TclError:
                pass
        self._action_prop_pending = self.root.after(
            30, lambda: self._start_action_prop(cue, action)
        )

    def _start_action_prop(self, cue: dict, action: str = "") -> None:
        self._action_prop_pending = None
        self._clear_action_prop()
        shape_key = str(cue.get("shape"))
        shape = PROP_SHAPES.get(shape_key)
        if not shape:
            return
        self._schedule_face_script(action)
        origin = _source_point(*cue["anchor"])
        timeline = build_prop_timeline(cue)
        items = self._create_prop_items(shape)
        self._action_prop_items = items
        held = bool(cue.get("held"))
        # worn props AND held props stay on top (a thing in the hand covers
        # the face when raised to it); only floating props go behind the face
        self._action_prop_over_face = bool(cue.get("over_face")) or held
        if not self._action_prop_over_face:
            self._raise_face_over_costume()
        grip = tuple(cue.get("grip_offset", (0.0, 0.0)))
        # held props attach and rotate at their natural grip point
        pivot = GRIP_POINTS.get(shape_key, (0.0, 0.0)) if held else (0.0, 0.0)
        # tail-as-hand: while carrying, the tail extends into a steady hold
        # instead of wagging — unless the tail itself is the performer
        # (bell ringing, pen twirling), marked tail_style "wag"
        if held and cue.get("tail_style", "hand") == "hand":
            self._cancel_tail_wag(reset=False)
            self._tail_hand_mode = True
            self._tail_hand_started = time.monotonic()
            self._tail_transition_to(TAIL_HAND_POSE, 220, self._tail_wag_after.clear)
        self._place_action_prop(items, shape, origin, timeline[0][:5], held=held, grip=grip, pivot=pivot)
        self._drive_action_prop(items, shape_key, shape, origin, timeline, held=held, grip=grip, pivot=pivot)

    def _schedule_face_script(self, action: str) -> None:
        """Stage the eyes/brows/gaze along the prop's story beats.

        Overrides the static acting cue: the face notices the prop, reacts at
        the story's peak, and lands an aftermath beat. Beats may carry
        micro-expression extras — pupil size, staged blinks, single-brow
        overrides, brow tremble, explicit eyelid level. Timers share the
        prop's lifecycle so an interrupted prop also stops its face script.
        """
        script = ACTION_FACE_SCRIPTS.get(action)
        if not script:
            return
        frame_total = sum(f[4] for f in ACTION_FRAMES.get(action, ())) or 1600

        def fire(eyes: str, brows: str, look, hold: int, extras) -> None:
            if eyes or brows:
                self._transition_expression(eyes or "round", brows or "neutral", hold_ms=hold)
            if look is not None and not self._is_blinking:
                self._animate_look(look)
            ex = extras or {}
            if "openness" in ex:
                self._eye_target_openness = float(ex["openness"])
            blink = ex.get("blink")
            if blink == "quick":
                self._blink()
            elif blink == "slow":
                self._slow_blink()
            elif blink == "double":
                self._blink()
                self._action_prop_after.append(self.root.after(260, self._blink))
            elif blink == "flutter":
                self._blink_flutter()
            if "tremble" in ex:
                self._brow_tremble(int(ex["tremble"]))
            # shaped pupils / wink / decal / blush: cleared automatically on
            # beats that do not declare them
            self._set_eye_fx(ex.get("pupil_shape"), ex.get("wink"))
            self._set_face_decal(ex.get("decal"))
            self._set_cheek_blush(bool(ex.get("blush")))
            # single-brow overrides and pupil sizing land after the 150ms
            # expression tween so they refine the pose instead of fighting it
            if "brow_l" in ex or "brow_r" in ex:
                base = self._BROW_MAP.get(brows or "neutral", self._BROW_MAP["neutral"])
                left = tuple(ex.get("brow_l", base[0]))
                right = tuple(ex.get("brow_r", base[1]))
                self._action_prop_after.append(
                    self.root.after(220, lambda l=left, r=right: self._apply_brow_spec(l, r))
                )
            if "pupil" in ex:
                scale = float(ex["pupil"])
                base_scale = self._EYE_MAP.get(eyes or "round", self._EYE_MAP["round"])[2]
                self._action_prop_after.append(
                    self.root.after(
                        220,
                        lambda s=base_scale * scale: self._set_pupil_pose(
                            *self._pupil_look, size_scale=s
                        ),
                    )
                )

        for i, frame in enumerate(script):
            at_ms, eyes, brows, look = frame[0], frame[1], frame[2], frame[3]
            extras = frame[4] if len(frame) > 4 else None
            next_at = script[i + 1][0] if i + 1 < len(script) else max(frame_total, at_ms) + 600
            hold = max(400, next_at - at_ms + 300)
            if at_ms <= 0:
                fire(eyes, brows, look, hold, extras)
            else:
                self._action_prop_after.append(
                    self.root.after(
                        at_ms,
                        lambda e=eyes, b=brows, lk=look, h=hold, x=extras: fire(e, b, lk, h, x),
                    )
                )

    # ── eye FX & face decals (distilled from the expression sheets) ──

    def _blink_flutter(self) -> None:
        """Rapid shallow eyelid flutter — overwhelmed, dazzled, or overcaffeinated."""
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        frames = ((0.5, 40), (0.9, 45), (0.4, 40), (0.85, 45), (0.5, 40), (1.0, 1))

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _brow_tremble(self, duration_ms: int) -> None:
        """Small fast brow shudder — cold, dread, or barely holding it together."""
        base = self._current_brow_spec
        end_at = time.monotonic() + duration_ms / 1000.0

        def tick() -> None:
            if time.monotonic() >= end_at or self._dragging:
                self._apply_brow_spec(*base)
                return
            jl = random.uniform(-0.45, 0.45)
            jr = random.uniform(-0.45, 0.45)
            left = (base[0][0], base[0][1] + jl, base[0][2])
            right = (base[1][0], base[1][1] + jr, base[1][2])
            self._apply_brow_spec(left, right)
            self._action_prop_after.append(self.root.after(65, tick))

        tick()

    def _create_prop_items(self, shape) -> list[int]:
        items: list[int] = []
        for prim in shape:
            kind = prim[0]
            if kind == "line":
                items.append(self.canvas.create_line(
                    0, 0, 1, 1, fill=prim[3], width=prim[2],
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    smooth=len(prim[1]) > 2, splinesteps=8,
                    tags=("action_prop",),
                ))
            elif kind == "polygon":
                _k, _pts, fill, outline, width = prim
                items.append(self.canvas.create_polygon(
                    0, 0, 1, 1, 2, 2, fill=fill or "", outline=outline or "",
                    width=max(0.1, width), tags=("action_prop",),
                ))
            elif kind == "oval":
                _k, _cx, _cy, _rx, _ry, fill, outline, width = prim
                items.append(self.canvas.create_oval(
                    0, 0, 1, 1, fill=fill or "", outline=outline or "",
                    width=max(0.1, width), tags=("action_prop",),
                ))
        return items

    def _place_action_prop(
        self,
        items: list[int],
        shape,
        origin: tuple[float, float],
        pose,
        update_colors: bool = False,
        held: bool = False,
        grip: tuple[float, float] = (0.0, 0.0),
        pivot: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        posed = transform_shape(shape, tuple(pose), pivot=pivot)
        if held:
            # gripped by the tail tip: ride the tail's live position and skip
            # the body squash transform (a held object keeps its own shape)
            base_x = self._tail_tip_point[0] + grip[0]
            base_y = self._tail_tip_point[1] + grip[1]

            def project(x: float, y: float) -> tuple[float, float]:
                return (base_x + x, base_y + y)

            rsx = rsy = 1.0
        else:
            def project(x: float, y: float) -> tuple[float, float]:
                return self._actor_point(origin[0] + x, origin[1] + y)

            rsx, rsy = (abs(v) for v in self._pal_scale)
        for item, prim in zip(items, posed):
            kind = prim[0]
            try:
                if kind == "line" or kind == "polygon":
                    pts = prim[1]
                    coords: list[float] = []
                    for x, y in pts:
                        coords.extend(project(x, y))
                    self.canvas.coords(item, *coords)
                    if update_colors:
                        if kind == "line":
                            self.canvas.itemconfigure(item, fill=prim[3])
                        else:
                            self.canvas.itemconfigure(item, fill=prim[2] or "", outline=prim[3] or "")
                elif kind == "oval":
                    _k, cx, cy, rx, ry, fill, outline, _width = prim
                    tx, ty = project(cx, cy)
                    self.canvas.coords(item, tx - rx * rsx, ty - ry * rsy, tx + rx * rsx, ty + ry * rsy)
                    if update_colors:
                        self.canvas.itemconfigure(item, fill=fill or "", outline=outline or "")
            except tk.TclError:
                pass

    def _drive_action_prop(
        self, items: list[int], shape_key: str, shape, origin, timeline,
        held: bool = False, grip: tuple[float, float] = (0.0, 0.0),
        pivot: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        state = list(timeline[0][:5])
        started = time.monotonic()
        has_fx = shape_key in SHAPE_FX
        physics = {"extra": 0.0, "dx": timeline[0][0]}

        def run_frame(fi: int) -> None:
            if fi >= len(timeline):
                self._clear_action_prop()
                return
            dx, dy, rot, scale, squash, delay = timeline[fi]
            steps = max(1, round(delay / LERP_TICK_MS))

            def tick(si: int = 0) -> None:
                if si >= steps:
                    state[:] = [dx, dy, rot, scale, squash]
                    run_frame(fi + 1)
                    return
                t = _smoothstep((si + 1) / steps)
                pose_dx = state[0] + (dx - state[0]) * t
                # carried-object inertia: swing opposite to horizontal motion
                physics["extra"] = inertia_step(
                    physics["extra"], physics["dx"], pose_dx, LERP_TICK_MS / 1000.0
                )
                physics["dx"] = pose_dx
                pose = (
                    pose_dx,
                    state[1] + (dy - state[1]) * t,
                    state[2] + (rot - state[2]) * t + physics["extra"],
                    state[3] + (scale - state[3]) * t,
                    state[4] + (squash - state[4]) * t,
                )
                frame_shape = shape
                if has_fx:
                    frame_shape = apply_shape_fx(shape_key, shape, time.monotonic() - started)
                self._place_action_prop(
                    items, frame_shape, origin, pose,
                    update_colors=has_fx, held=held, grip=grip, pivot=pivot,
                )
                self._action_prop_after.append(self.root.after(LERP_TICK_MS, lambda: tick(si + 1)))

            tick()

        run_frame(1)

    def _clear_action_prop(self) -> None:
        for after_id in self._action_prop_after:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._action_prop_after.clear()
        for item in self._action_prop_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self._action_prop_items.clear()
        self._clear_face_fx()
        if self._tail_hand_mode:
            self._tail_hand_mode = False
            self._tail_transition_to(TAIL_NEUTRAL_POSE, 200, self._tail_wag_after.clear)

    def _perform_micro_action(self, action: str) -> None:
        if action == "micro_focus_pause":
            self._stop_mouse_follow()
            self._set_brow_pose("soft")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.94)
            self._animate_look((0.0, 0.0))
        elif action == "micro_side_eye":
            self._set_brow_pose("skeptical")
            self._set_pupil_pose(*self._pupil_look, size_scale=0.98)
            self._animate_look((-3.1, 0.35))
            self._run_tail_motion("tail_tip_flick")
        elif action == "micro_brow_judge":
            self._set_brow_pose("judge")
        elif action == "micro_snap_innocent":
            self._stop_mouse_follow()
            self._set_brow_pose("innocent")
            self._pupil_look = (0.0, 0.0)
            self._set_pupil_pose(0.0, -0.2, size_scale=1.14)
            self._run_tail_motion("tail_guilty_tuck")
            self._schedule_expression_reset(1200)
        elif action == "micro_caught_guilty":
            self._stop_mouse_follow()
            self._set_brow_pose("worried")
            self._pupil_look = (0.0, -0.1)
            self._set_pupil_pose(0.0, -0.1, size_scale=1.10)
            self._run_tail_motion("tail_guilty_tuck")
            self._schedule_expression_reset(1400)
        elif action == "micro_holding_laugh":
            self._set_brow_pose("smug_arch")
            self._set_pupil_pose(0.45, -0.1, size_scale=0.88)
            self._run_tail_motion("tail_smug_sway")
        elif action == "micro_peek_up":
            self._set_brow_pose("droop")
            self._set_pupil_pose(1.9, -0.75, size_scale=0.92)
            self._run_tail_motion("tail_sleepy_droop")
        elif action == "micro_soften":
            self._set_brow_pose("soft")
            self._set_pupil_pose(0.0, 0.0, size_scale=0.96)
        elif action == "micro_tiny_proud":
            self._set_brow_pose("proud")
            self._set_pupil_pose(-0.35, -0.25, size_scale=1.02)
        elif action == "micro_guilty_dart":
            self._guilty_dart()
        elif action == "micro_slow_blink":
            self._slow_blink()
        elif action == "micro_soft_reset":
            self._reset_expression_pose()

    def _wiggle(self) -> None:
        if self._large_action_running:
            return
        self._spring.kick_squash(2.5)
        self._spring_active = True
        self._cancel_tail_wag(reset=True)
        frames = WIGGLE_FRAMES
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
            self._reset_pal_geometry()

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._reset_pal_geometry()
                self._rebound_after = None
                self._start_tail_for_action("wiggle")
                return
            sx, sy, delay = frames[index]
            self._set_pal_scale(sx, sy)
            self._rebound_after = self.root.after(delay, lambda: step(index + 1))

        step()

    def _run_large_action(self, frames: ActionFrames, action_name: str = "") -> None:
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting(action_name)
        self._start_tail_for_action(action_name)
        self._start_inner_for_action(action_name)
        self._run_bend_motion(action_name)
        self._shadow_action = action_name if action_name in ACTION_SHADOW_ACTIONS else ""
        self._large_action_running = True
        ease = easing_for_action(action_name)

        jittered = _jitter_frames(_acting_frames(frames, action_name))
        state = [0.0, 0.0, 1.0, 1.0]

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(jittered):
                self._finish_large_action()
                return
            dx, dy, sx, sy, delay = jittered[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = ease((si + 1) / n)
            self._set_action_offset(
                state[0] + (dx - state[0]) * t,
                state[1] + (dy - state[1]) * t,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * t,
                state[3] + (sy - state[3]) * t,
            )
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        step()

    def _run_melt_action(self) -> None:
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting("melt")
        self._start_tail_for_action("melt")
        self._start_inner_for_action("melt")
        self._emit_particles("sweat")
        self._shadow_action = "melt"
        self._large_action_running = True
        frames: ActionFrames = MELT_SINK_FRAMES
        state = [0.0, 0.0, 1.0, 1.0]
        recovery_frames: ActionFrames = MELT_RECOVERY_FRAMES

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(frames):
                self._draw_melt_puddle(1.0)
                self._large_action_after = self.root.after(MELT_PUDDLE_HOLD_MS, recover)
                return
            dx, dy, sx, sy, delay = frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            phase = (si + 1) / n
            ease = phase ** 3 if fi < 5 else _ease_out_cubic(phase)
            self._set_action_offset(
                state[0] + (dx - state[0]) * ease,
                state[1] + (dy - state[1]) * ease,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * ease,
                state[3] + (sy - state[3]) * ease,
            )
            progress = (fi + phase) / len(frames)
            self._draw_melt_puddle(progress)
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        def recover(fi: int = 0, si: int = 0) -> None:
            if fi >= len(recovery_frames):
                self._finish_melt_action()
                return
            dx, dy, sx, sy, delay = recovery_frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                recover(fi + 1, 0)
                return
            phase = (si + 1) / n
            ease = phase * phase * (3.0 - 2.0 * phase)
            self._set_action_offset(
                state[0] + (dx - state[0]) * ease,
                state[1] + (dy - state[1]) * ease,
            )
            self._set_pal_scale(
                state[2] + (sx - state[2]) * ease,
                state[3] + (sy - state[3]) * ease,
            )
            progress = (fi + phase) / len(recovery_frames)
            self._draw_melt_puddle(1.0 - progress * 0.72)
            self._large_action_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: recover(_fi, _si + 1),
            )

        step()

    def _finish_melt_action(self) -> None:
        self._large_action_after = None
        self._large_action_running = False
        self._shadow_action = ""
        self._clear_melt_puddle()
        self._spring.snap()
        self._spring_active = False
        self._reset_pal_geometry(preserve_tail=True)
        self._transition_expression("guilty_round", "innocent", hold_ms=1200)

    def _run_window_move_action(self, action: str) -> None:
        if self._dragging:
            return
        direction = self._movement_direction()
        if action == "twist_scoot":
            dx = direction * random.randint(10, 20)
            frames: ActionFrames = (
                (-direction * 4, 0, 0.96, 1.04, 60),
                (dx, 0, 1.06, 0.94, 130),
                (dx, 0, 1.0, 1.0, 80),
            )
        elif action == "mini_hop_shift":
            dx = direction * random.randint(24, 48)
            frames = (
                (0, 8, 1.14, 0.78, 80),
                (dx * 0.55, -18, 0.90, 1.16, 95),
                (dx, 4, 1.07, 0.90, 80),
                (dx, 0, 1.0, 1.0, 70),
            )
        elif action == "relocate_hop":
            dx = self._relocation_delta(random.randint(90, 150))
            frames = (
                (0, 10, 1.18, 0.74, 110),
                (dx * 0.42, -42, 0.88, 1.22, 130),
                (dx * 0.78, -34, 0.94, 1.10, 120),
                (dx, 8, 1.10, 0.86, 95),
                (dx, 0, 1.0, 1.0, 100),
            )
        elif action == "roast_and_scoot":
            dx = direction * random.randint(12, 18)
            self._set_brow_pose("innocent")
            self._set_eye_pose("round")
            frames = (
                (-direction * 3, 0, 0.98, 1.04, 70),
                (dx, 0, 1.05, 0.94, 120),
                (dx, 0, 1.0, 1.0, 90),
                (dx, -1, 0.99, 1.02, 220),   # freeze: nothing happened
                (dx, 0, 1.0, 1.0, 160),
            )
        elif action == "retreat_to_corner":
            dx, dy = self._corner_retreat_delta()
            frames = (
                (dx * 0.12, 0, 0.96, 1.04, 90),
                (dx * 0.42, dy * 0.35, 0.90, 0.96, 130),
                (dx * 0.72, dy * 0.70, 0.86, 0.92, 130),
                (dx, dy, 0.92, 0.94, 120),
                (dx, dy, 1.0, 1.0, 100),
            )
        elif action == "zoomies":
            # 猫式疯跑：冲刺仍要读得出「跑过去」的过程——每程 120-150ms，
            # 急停后钉一拍再折返
            span = direction * random.randint(60, 90)
            frames = (
                (span * 0.5, -6, 0.88, 1.10, 130),
                (span, 0, 1.14, 0.90, 110),
                (span, 0, 1.0, 1.0, 90),
                (-span * 0.35, -6, 0.88, 1.10, 150),
                (-span * 0.6, 0, 1.14, 0.90, 110),
                (-span * 0.6, 0, 1.0, 1.0, 90),
                (0, -6, 0.92, 1.06, 130),
                (0, 0, 1.0, 1.0, 120),
            )
        elif action == "moonwalk":
            # 太空步：翻面背对行进方向滑走，节奏性起伏，到位再翻回来
            dx = direction * random.randint(55, 95)
            frames = (
                (0, 0, -1.0, 1.0, 110),
                (dx * 0.3, 3, -1.06, 0.94, 140),
                (dx * 0.45, -2, -0.98, 1.03, 110),
                (dx * 0.7, 3, -1.06, 0.94, 140),
                (dx * 0.85, -2, -0.98, 1.03, 110),
                (dx, 0, -1.0, 1.0, 120),
                (dx, 0, 1.0, 1.0, 130),
            )
        elif action == "pounce":
            # 猛扑：压低蓄力扭两下，向前跃出一小段落地
            dx = direction * random.randint(45, 85)
            frames = (
                (-direction * 6, 4, 1.12, 0.84, 200),
                (-direction * 8, 5, 1.14, 0.82, 150),
                (dx * 0.7, -22, 0.86, 1.18, 110),
                (dx, 6, 1.18, 0.82, 90),
                (dx, -4, 0.96, 1.05, 80),
                (dx, 0, 1.0, 1.0, 90),
            )
        elif action == "drop_in":
            self._run_drop_in()
            return
        else:
            return
        self._run_window_move(frames, action)

    def _run_drop_in(self) -> None:
        if self._dragging:
            return
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        _left, top, _right, _bottom = self._desktop_bounds()
        start_y = max(top, y - 90)
        self.root.geometry(_geometry_position(x, start_y))
        self._position_bubble()
        dy = y - start_y
        # a canopy descent: drifting down with a sway, then a soft touchdown
        self._run_window_move(
            (
                (-4, dy * 0.20, 0.97, 1.05, 200),
                (5, dy * 0.45, 0.98, 1.04, 210),
                (-4, dy * 0.70, 0.98, 1.03, 200),
                (2, dy * 0.92, 0.99, 1.02, 170),
                (0, dy + 6, 1.10, 0.86, 90),
                (0, dy - 3, 0.97, 1.04, 80),
                (0, dy, 1.0, 1.0, 80),
            ),
            "drop_in",
        )

    def _run_window_move(self, frames: ActionFrames, action_name: str = "") -> None:
        if not frames:
            return
        self._cancel_window_move()
        self._cancel_large_action()
        self._stop_mouse_follow()
        if self._rebound_after:
            self.root.after_cancel(self._rebound_after)
            self._rebound_after = None
        self._reset_pal_geometry()
        self._prepare_action_acting(action_name)
        self._start_tail_for_action(action_name)
        self._start_inner_for_action(action_name)
        self._run_bend_motion(action_name)
        self.root.update_idletasks()
        start_x = self.root.winfo_x()
        start_y = self.root.winfo_y()
        frames = self._clamped_window_frames(_acting_frames(frames, action_name), start_x, start_y)
        self._window_move_running = True
        ease = easing_for_action(action_name)
        state = [0.0, 0.0, 1.0, 1.0]

        def step(fi: int = 0, si: int = 0) -> None:
            if fi >= len(frames):
                self._finish_window_move()
                return
            dx, dy, sx, sy, delay = frames[fi]
            n = max(1, round(delay / LERP_TICK_MS))
            if si >= n:
                state[:] = [dx, dy, sx, sy]
                step(fi + 1, 0)
                return
            t = ease((si + 1) / n)
            next_x = state[0] + (dx - state[0]) * t
            next_y = state[1] + (dy - state[1]) * t
            self.root.geometry(_geometry_position(start_x + next_x, start_y + next_y))
            if self._bubble_items:
                self._position_bubble()
            if self._chat_window:
                self._position_chat_input()
            self._set_pal_scale(
                state[2] + (sx - state[2]) * t,
                state[3] + (sy - state[3]) * t,
            )
            self._window_move_after = self.root.after(
                LERP_TICK_MS, lambda _fi=fi, _si=si: step(_fi, _si + 1),
            )

        step()

    def _cancel_window_move(self) -> None:
        if self._window_move_after:
            self.root.after_cancel(self._window_move_after)
            self._window_move_after = None
        if self._window_move_running:
            self._finish_window_move()

    def _finish_window_move(self) -> None:
        self._window_move_after = None
        self._window_move_running = False
        self._spring.kick_bounce(2.2)
        self._spring_active = True
        self._reset_pal_geometry(preserve_tail=True)
        if self._bubble_items:
            self._position_bubble()
        if self._chat_window:
            self._position_chat_input()

    def _cancel_large_action(self) -> None:
        if self._large_action_after:
            self.root.after_cancel(self._large_action_after)
            self._large_action_after = None
        if self._large_action_running:
            self._finish_large_action()

    def _finish_large_action(self) -> None:
        self._large_action_after = None
        self._large_action_running = False
        self._shadow_action = ""
        self._clear_melt_puddle()
        self._spring.kick_bounce(1.8)
        self._spring_active = True
        self._reset_pal_geometry(preserve_tail=True)

    def _blink(self) -> None:
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        # eased close/open: quick shut, brief hold, softer reopen
        frames = BLINK_FRAMES

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _slow_blink(self) -> None:
        """轻蔑式慢眨眼：较快合上、闭住停顿、缓缓睁开。放完冷箭后的"我说完了"。"""
        if self._is_blinking or self._large_action_running or self._doze_stage >= 2:
            return
        self._is_blinking = True
        frames = SLOW_BLINK_FRAMES

        def step(index: int = 0) -> None:
            if index >= len(frames):
                self._is_blinking = False
                self._set_pupil_pose(*self._pupil_look, blink_scale=1.0)
                return
            scale, delay = frames[index]
            self._set_pupil_pose(*self._pupil_look, blink_scale=scale)
            self.root.after(delay, lambda: step(index + 1))

        step()

    def _guilty_dart(self) -> None:
        """被抓包眼神回环：瞟你一眼 → 迅速移开 → 定住 → 慢慢飘回来。"""
        if self._large_action_running:
            return
        self._stop_mouse_follow()
        sequence = GUILTY_DART_SEQUENCE

        def step(index: int = 0) -> None:
            if index >= len(sequence) or self._large_action_running:
                return
            dx, dy, hold = sequence[index]
            self._pupil_look = (dx, dy)
            if not self._is_blinking:
                self._set_pupil_pose(dx, dy)
            self.root.after(hold, lambda: step(index + 1))

        step()

    def _scan(self) -> None:
        if self._is_blinking or self._large_action_running:
            return
        targets = SCAN_LOOK_TARGETS

        def step(index: int = 0) -> None:
            if index >= len(targets) or self._is_blinking or self._large_action_running:
                return
            dx, dy = targets[index]
            self._pupil_look = (dx, dy)
            self._set_pupil_pose(dx, dy)
            self.root.after(SCAN_LOOK_HOLD_MS, lambda: step(index + 1))

        step()
