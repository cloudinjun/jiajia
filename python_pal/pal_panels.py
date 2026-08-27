"""Quiz and chat panel layer.

The two secondary Toplevel windows the pet can open: the absurd-quiz card and
the local chat input, plus their scheduling, answer handling and context
building. `PanelMixin` is mixed into PaperclipPalApp.
"""
from __future__ import annotations

import json
import random
import threading
import time
import tkinter as tk
from datetime import date
from typing import Callable

from .chat import build_chat_context, detect_chat_command, local_status_reaction
from .pal_geometry import (
    PAL_CENTER_X, PAL_HEIGHT, PAL_PAD_Y, _geometry_with_size,
)
from .language import normalize_language
from .quiz import (
    QuizPacket, QuizSession, build_report, current_question,
    format_report, load_quiz_packets, record_answer, score_packet,
)
from .quiz_safety import validate_quiz_packet
from .state import Reaction


QUIZ_FIRST_HEARTBEAT_MS = 90_000
QUIZ_INTERVAL_MS = {
    "quiet": 60 * 60 * 1000,
    "normal": 30 * 60 * 1000,
    "active": 16 * 60 * 1000,
    "hyper": 9 * 60 * 1000,
}
QUIZ_DAILY_LIMIT = {"quiet": 0, "normal": 1, "active": 2, "hyper": 3}
QUIZ_CARD_WIDTH = 360


class PanelMixin:
    """Quiz card and chat input windows."""

    def _open_chat_input(self) -> None:
        if self._chat_window and self._chat_window.winfo_exists():
            self._chat_window.lift()
            if self._chat_entry:
                self._chat_entry.focus_set()
            return

        self._perform_action("thinking_tilt")
        self._start_mouse_follow(1100, force=True)
        window = tk.Toplevel(self.root)
        self._chat_window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg="#d4dee8")
        window.bind("<Escape>", lambda _event: self._close_chat_input())
        window.protocol("WM_DELETE_WINDOW", self._close_chat_input)

        shell = tk.Frame(window, bg="#d4dee8", padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        inner = tk.Frame(shell, bg="#fdfdfd", padx=9, pady=8)
        inner.pack(fill="both", expand=True)
        entry = tk.Entry(
            inner,
            width=34,
            relief="flat",
            bd=0,
            bg="#fdfdfd",
            fg="#202932",
            insertbackground="#202932",
            font=("Microsoft YaHei UI", 10),
        )
        entry.pack(fill="x")
        entry.bind("<Return>", self._submit_chat_from_entry)
        self._chat_entry = entry
        self._position_chat_input()
        self._hide_window_from_taskbar(window)
        window.deiconify()
        window.lift()
        entry.focus_set()

    def _position_chat_input(self) -> None:
        if not self._chat_window:
            return
        self.root.update_idletasks()
        width = 286
        height = 38
        left, top, right, bottom = self._desktop_bounds()
        x = self.root.winfo_x() + PAL_CENTER_X - width / 2
        y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + 12
        x = min(max(left + 8, x), max(left + 8, right - width - 8))
        if y + height > bottom - 8:
            y = self.root.winfo_y() + PAL_PAD_Y - height - 10
        y = min(max(top + 8, y), max(top + 8, bottom - height - 8))
        self._chat_window.geometry(_geometry_with_size(width, height, x, y))

    def _submit_chat_from_entry(self, _event: tk.Event | None = None) -> None:
        if not self._chat_entry:
            return
        message = self._chat_entry.get().strip()
        self._close_chat_input()
        self._handle_chat_message(message)

    def _close_chat_input(self) -> None:
        if self._chat_window:
            try:
                self._chat_window.destroy()
            except tk.TclError:
                pass
        self._chat_window = None
        self._chat_entry = None

    def _load_quiz_fallbacks(self) -> None:
        loaded = 0
        errors: list[str] = []
        try:
            packets = load_quiz_packets(self.project_root / "python_pal" / "quizzes.yaml")
        except Exception as exc:
            self._last_quiz_debug = f"fallback load failed: {exc}"
            return
        for packet in packets:
            packet_errors = validate_quiz_packet(packet)
            if packet_errors:
                errors.append(f"{packet.id or '<missing>'}: {'; '.join(packet_errors[:3])}")
                continue
            self.quiz_store.upsert_packet(packet)
            loaded += 1
        if errors:
            self._last_quiz_debug = f"loaded {loaded} quiz packet(s); rejected: " + " | ".join(errors)
        else:
            self._last_quiz_debug = f"loaded {loaded} quiz packet(s)"

    def _schedule_quiz_heartbeat(self, first: bool = False) -> None:
        if self._quiz_after:
            try:
                self.root.after_cancel(self._quiz_after)
            except tk.TclError:
                pass
        policy = self._activity_policy()
        delay = QUIZ_FIRST_HEARTBEAT_MS if first else QUIZ_INTERVAL_MS.get(policy.tier, QUIZ_INTERVAL_MS["normal"])
        self._quiz_after = self.root.after(delay, self._quiz_heartbeat)

    def _quiz_heartbeat(self) -> None:
        self._quiz_after = None
        try:
            pending = self.quiz_store.active_session()
            if pending and pending.state == "completed_waiting_result":
                self._try_show_pending_quiz_result()
            elif self._quiz_should_offer():
                self._offer_absurd_quiz(force=False)
        finally:
            self._schedule_quiz_heartbeat()

    def _quiz_should_offer(self) -> bool:
        today = date.today()
        if today != self._quiz_offer_day:
            self._quiz_offer_day = today
            self._quiz_offers_today = 0
        session = self.quiz_store.active_session()
        if session is not None:
            return session.state == "paused" and self._quiz_can_prompt()
        policy = self._activity_policy()
        daily_limit = QUIZ_DAILY_LIMIT.get(policy.tier, 1)
        if daily_limit <= 0 or self._quiz_offers_today >= daily_limit:
            return False
        if not self._quiz_can_prompt():
            return False
        if self.quiz_store.next_packet(normalize_language(self.soul.language)) is None:
            return False
        interval = QUIZ_INTERVAL_MS.get(policy.tier, QUIZ_INTERVAL_MS["normal"]) / 1000
        if time.time() - self._last_quiz_offer_at < interval:
            return False
        chance = {"normal": 0.18, "active": 0.36, "hyper": 0.58}.get(policy.tier, 0.0)
        return random.random() < chance

    def _quiz_can_prompt(self) -> bool:
        return not (
            self._auto_reactions_paused()
            or self.state.brain_busy
            or self._bubble_items
            or self._quiz_window
            or self._dragging
            or self._large_action_running
            or self._window_move_running
        )

    def _quiz_can_show_result(self) -> bool:
        return self._quiz_can_prompt()

    def _offer_absurd_quiz(self, force: bool = False) -> None:
        self._load_quiz_fallbacks()
        active_session = self.quiz_store.active_session()
        if active_session is not None:
            packet = self.quiz_store.get_packet(active_session.packet_id)
            if packet is None:
                self.quiz_store.clear_session()
            elif active_session.state == "completed_waiting_result":
                self._try_show_pending_quiz_result(force=force)
                return
            else:
                self._show_quiz_resume_offer(packet, active_session)
                return

        packet = self.quiz_store.next_packet(normalize_language(self.soul.language))
        if packet is None:
            self.show_bubble("我还没有可用的小测验。题库空得很有态度。", milliseconds=3600, kind="thought")
            return
        if not force:
            self._last_quiz_offer_at = time.time()
            self._quiz_offers_today += 1
        self._perform_action("thinking_tilt")
        self._open_quiz_card(
            packet.title,
            f"{packet.subtitle}\n\n夹夹可以问你 {len(packet.questions)} 个很不严肃的问题。",
            [
                ("开始", lambda packet=packet: self._start_quiz(packet)),
                ("稍后", self._dismiss_quiz_window),
                ("今天别考我", self._dismiss_quiz_today),
            ],
        )

    def _show_quiz_resume_offer(self, packet: QuizPacket, session: QuizSession) -> None:
        self._open_quiz_card(
            packet.title,
            f"上次的小测验停在第 {session.current_index + 1} 题。它没有忘，主要是 JSON 没忘。",
            [
                ("继续", lambda packet=packet, session=session: self._resume_quiz(packet, session)),
                ("重新开始", lambda packet=packet: self._start_quiz(packet)),
                ("放弃", self._abandon_quiz),
            ],
        )

    def _start_quiz(self, packet: QuizPacket) -> None:
        session = QuizSession.start(packet)
        self.quiz_store.save_session(session)
        self._perform_action("fake_innocent")
        self._show_quiz_question(packet, session)

    def _resume_quiz(self, packet: QuizPacket, session: QuizSession) -> None:
        session.state = "active"
        session.updated_at = time.time()
        self.quiz_store.save_session(session)
        self._show_quiz_question(packet, session)

    def _show_quiz_question(self, packet: QuizPacket, session: QuizSession) -> None:
        question = current_question(packet, session)
        if question is None:
            self._show_quiz_result_delay(packet, session)
            return
        total = len(packet.questions)
        body = f"{session.current_index + 1}/{total}\n{question.text}"
        buttons: list[tuple[str, Callable[[], None]]] = []
        for option in question.options:
            label = f"{option.id.upper()}. {option.text}"
            buttons.append((label, lambda option_id=option.id: self._handle_quiz_answer(option_id)))
        buttons.extend(
            [
                ("暂停", self._pause_quiz),
                ("放弃", self._abandon_quiz),
            ]
        )
        self._open_quiz_card(packet.title, body, buttons)

    def _handle_quiz_answer(self, option_id: str) -> None:
        session = self.quiz_store.active_session()
        if session is None:
            self._dismiss_quiz_window()
            return
        packet = self.quiz_store.get_packet(session.packet_id)
        if packet is None:
            self.quiz_store.clear_session()
            self._dismiss_quiz_window()
            return
        try:
            session = record_answer(packet, session, option_id)
        except ValueError:
            self.show_bubble("这个选项不在题目里。夹夹暂时不接受平行宇宙答案。", milliseconds=3600, kind="thought")
            return
        self.quiz_store.save_session(session)
        if session.state == "completed_waiting_result":
            self._show_quiz_result_delay(packet, session)
            return
        self._show_quiz_question(packet, session)

    def _pause_quiz(self) -> None:
        session = self.quiz_store.active_session()
        if session is not None:
            session.state = "paused"
            session.updated_at = time.time()
            self.quiz_store.save_session(session)
        self._dismiss_quiz_window()
        self.show_bubble("先暂停。题目会待在本地 JSON 里，像一只很小的备案。", milliseconds=3600, kind="thought")

    def _abandon_quiz(self) -> None:
        self.quiz_store.clear_session()
        self._dismiss_quiz_window()
        self._perform_action("fake_sulk")
        self.show_bubble("放弃成功。夹夹尊重逃生路线。", milliseconds=3200, kind="thought")

    def _show_quiz_result_delay(self, packet: QuizPacket, session: QuizSession) -> None:
        self._dismiss_quiz_window()
        session.state = "completed_waiting_result"
        session.updated_at = time.time()
        self.quiz_store.save_session(session)
        self._perform_action("thinking_tilt")
        self.show_bubble("正在把答案塞进荒谬统计学。请稍等，它需要装得很严谨。", milliseconds=2600, kind="thought")
        self._schedule_quiz_result_check(delay_ms=1800)

    def _schedule_quiz_result_check(self, delay_ms: int = 12_000) -> None:
        if self._quiz_result_after:
            try:
                self.root.after_cancel(self._quiz_result_after)
            except tk.TclError:
                pass
        self._quiz_result_after = self.root.after(delay_ms, self._try_show_pending_quiz_result)

    def _try_show_pending_quiz_result(self, force: bool = False) -> None:
        self._quiz_result_after = None
        session = self.quiz_store.active_session()
        if session is None or session.state != "completed_waiting_result":
            return
        packet = self.quiz_store.get_packet(session.packet_id)
        if packet is None:
            self.quiz_store.clear_session()
            return
        if not force and not self._quiz_can_show_result():
            self._schedule_quiz_result_check()
            return
        self._show_quiz_result(packet, session)

    def _show_quiz_result(self, packet: QuizPacket, session: QuizSession) -> None:
        self._quiz_result_after = None
        scores = score_packet(packet, session.answers)
        report = build_report(packet, scores)
        result = report.result
        self.quiz_store.clear_session()
        self._perform_action(result.action or "thinking_tilt")
        self._open_quiz_card(
            report.title,
            format_report(report),
            [
                ("收到", self._dismiss_quiz_window),
                ("再测一次", lambda packet=packet: self._start_quiz(packet)),
            ],
        )

    def _dismiss_quiz_today(self) -> None:
        policy = self._activity_policy()
        self._quiz_offers_today = QUIZ_DAILY_LIMIT.get(policy.tier, 1)
        self._dismiss_quiz_window()
        self.show_bubble("今天不考。夹夹把试卷折起来了，姿态很专业。", milliseconds=3200, kind="thought")

    def _dismiss_quiz_window(self) -> None:
        if self._quiz_window:
            try:
                self._quiz_window.destroy()
            except tk.TclError:
                pass
        self._quiz_window = None

    def _open_quiz_card(
        self,
        title: str,
        body: str,
        buttons: list[tuple[str, Callable[[], None]]],
    ) -> None:
        self._dismiss_quiz_window()
        window = tk.Toplevel(self.root)
        self._quiz_window = window
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.configure(bg="#d4dee8")
        window.bind("<Escape>", lambda _event: self._dismiss_quiz_window())
        window.protocol("WM_DELETE_WINDOW", self._dismiss_quiz_window)

        shell = tk.Frame(window, bg="#d4dee8", padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        inner = tk.Frame(shell, bg="#fdfdfd", padx=12, pady=11)
        inner.pack(fill="both", expand=True)
        tk.Label(
            inner,
            text=title,
            bg="#fdfdfd",
            fg="#202932",
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 10, "bold"),
            wraplength=QUIZ_CARD_WIDTH - 36,
        ).pack(fill="x")
        tk.Label(
            inner,
            text=body,
            bg="#fdfdfd",
            fg="#3a4652",
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 9),
            wraplength=QUIZ_CARD_WIDTH - 36,
        ).pack(fill="x", pady=(7, 8))
        for label, command in buttons:
            tk.Button(
                inner,
                text=label,
                command=command,
                anchor="w",
                justify="left",
                relief="flat",
                bd=0,
                padx=9,
                pady=5,
                bg="#eef2f7",
                fg="#202932",
                activebackground="#dfe7f0",
                activeforeground="#202932",
                font=("Microsoft YaHei UI", 9),
                wraplength=QUIZ_CARD_WIDTH - 54,
            ).pack(fill="x", pady=2)

        self._hide_window_from_taskbar(window)
        self._position_quiz_window(window)
        window.deiconify()
        window.lift()

    def _position_quiz_window(self, window: tk.Toplevel) -> None:
        try:
            window.update_idletasks()
            width = QUIZ_CARD_WIDTH
            height = min(max(190, int(window.winfo_reqheight())), 520)
            left, top, right, bottom = self._pal_monitor_bounds()
            x = self.root.winfo_x() + PAL_CENTER_X - width / 2
            y = self.root.winfo_y() + PAL_PAD_Y + PAL_HEIGHT + 12
            if y + height > bottom - 8:
                y = self.root.winfo_y() + PAL_PAD_Y - height - 12
            x = min(max(left + 8, x), max(left + 8, right - width - 8))
            y = min(max(top + 8, y), max(top + 8, bottom - height - 8))
            window.geometry(_geometry_with_size(width, height, x, y))
        except tk.TclError:
            return

    def _handle_chat_message(self, message: str) -> None:
        message = " ".join(message.split())
        if not message:
            return
        self.chat_session.add("user", message)
        context = self._build_chat_context()
        command = detect_chat_command(message)
        if self._handle_chat_command(command, context):
            return
        if self.state.brain_busy:
            self.show_bubble("我还在想上一句。一个小文具同时多线程，听起来就很危险。", milliseconds=4200, kind="thought")
            self._perform_action("thinking_tilt")
            return

        self.state.brain_busy = True
        self._start_chat_wait_feedback()
        history = self.chat_session.history()

        def worker() -> None:
            reaction = self.chat_brain.respond(message, context, history)
            reaction.event = reaction.event or "chat"
            if reaction.line:
                self.chat_session.add("assistant", reaction.line)
            self.queue.put(reaction)

        self._chat_thread = threading.Thread(target=worker, daemon=True)
        self._chat_thread.start()

    def _handle_chat_command(self, command: str, context: dict[str, object]) -> bool:
        if not command:
            return False
        if command == "quiet_30m":
            self._quiet_for(30 * 60)
            self.chat_session.add("assistant", "好，我折起来 30 分钟。")
            return True
        if command == "focus_on":
            if not self._focus_var.get():
                self._focus_var.set(True)
                self._toggle_focus_mode()
                self.chat_session.add("assistant", "专注模式开启。")
                return True
            reaction = Reaction(True, "已经在专注模式了。夹夹正在低存在感地盯着。", "focused", "blink", "thought", "quiet_companion", event="chat_focus_on")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command == "focus_off":
            if self._focus_var.get():
                self._focus_var.set(False)
                self._toggle_focus_mode()
                self.chat_session.add("assistant", "专注模式关闭。")
                return True
            reaction = Reaction(True, "专注模式本来就没开。夹夹只是看起来很克制。", "innocent", "blink", "thought", "quiet_companion", event="chat_focus_off")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command.startswith("frequency_"):
            label = {
                "frequency_quiet": "安静",
                "frequency_normal": "正常",
                "frequency_active": "活泼",
                "frequency_hyper": "多动",
            }[command]
            self._set_frequency(label)
            reaction = Reaction(
                True,
                f"活跃度切到 {label}。存在感已重新校准，听起来很正规。",
                "smirk" if label in {"活泼", "多动"} else "innocent",
                "happy_bounce" if label == "多动" else "blink",
                "thought",
                "tiny_celebrate" if label == "多动" else "quiet_companion",
                event=f"chat_{command}",
            )
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        if command == "morning_digest":
            line = self.event_log.digest(mark_read=False)
            reaction = Reaction(True, line, "thinking", "scan", "speech", "suspicious_observe", event="chat_morning_digest")
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True

        reaction = local_status_reaction(command, context)
        if reaction:
            self.chat_session.add("assistant", reaction.line)
            self._apply_reaction(reaction)
            return True
        return False

    def _build_chat_context(self) -> dict[str, object]:
        world = self._world_state()
        policy = self._activity_policy()
        interruptibility = self._interruptibility(world)
        context = build_chat_context(
            world,
            activity_mode=self._freq_var.get(),
            activity_tier=policy.tier,
            focus_mode=bool(self._focus_var.get()),
            quiet_remaining_seconds=self._quiet_remaining_seconds(),
        )
        context.update(interruptibility.as_context())
        context["alive"] = self.alive.as_context()
        context["language_mode"] = normalize_language(self.soul.language)
        context["appearance"] = {
            "costume_id": self.appearance.costume_id,
            "phase": self.appearance.phase,
            "language_mode": self.appearance.language_mode,
        }
        self._last_chat_context_debug = json.dumps(context, ensure_ascii=False, indent=2)
        return context

    def _start_chat_wait_feedback(self) -> None:
        self._stop_chat_wait_feedback(clear_bubble=False)
        self._chat_wait_step = 0
        self._chat_wait_started_at = time.time()
        self._apply_alive_cue(self.alive.observe_wait("chat"))
        self._chat_wait_tick()

    def _stop_chat_wait_feedback(self, clear_bubble: bool = False) -> None:
        if self._chat_wait_after:
            try:
                self.root.after_cancel(self._chat_wait_after)
            except tk.TclError:
                pass
            self._chat_wait_after = None
        self._chat_wait_step = 0
        self._chat_wait_started_at = 0.0
        if clear_bubble:
            self._clear_bubble()

    def _chat_wait_tick(self) -> None:
        self._chat_wait_after = None
        if not self.state.brain_busy:
            return
        elapsed = time.time() - self._chat_wait_started_at if self._chat_wait_started_at else 0.0
        early_steps = (
            ("收到。夹夹把这句话夹住了。", "blink", "thought", 1250),
            ("正在折一份低隐私状态小纸条。", "scan", "thought", 1500),
            ("正在叫醒 Ollama。本地模型起床有仪式感。", "thinking_tilt", "thought", 1750),
            ("模型在想。夹夹先用眉毛维持连接。", "smug_sway", "thought", 1850),
            ("正在等它吐出一句像样的话。要求不高，像样就行。", "patrol", "thought", 2100),
        )
        long_wait_steps = (
            ("还在等。本地脑子正在慢慢把风格拧紧。", "sleepy_sag", "thought", 2300),
            ("它还没回。夹夹没有失联，只是在旁边审判延迟。", "scan", "thought", 2400),
            ("再慢一点，我就要怀疑它在给词语排队。", "thinking_tilt", "thought", 2500),
        )
        if self._chat_wait_step < len(early_steps):
            line, action, bubble, delay = early_steps[self._chat_wait_step]
        else:
            index = (self._chat_wait_step - len(early_steps)) % len(long_wait_steps)
            line, action, bubble, delay = long_wait_steps[index]
            if elapsed >= 18:
                line = f"{line} 已经 {round(elapsed)} 秒了，仪式感略多。"
        if not self._dragging:
            self._perform_action(action)
        self.show_bubble(line, milliseconds=max(2400, delay + 900), kind=bubble)
        self._chat_wait_step += 1
        self._chat_wait_after = self.root.after(delay, self._chat_wait_tick)

    def _show_last_chat_context(self) -> None:
        text = self._last_chat_context_debug
        if not text:
            text = json.dumps(self._build_chat_context(), ensure_ascii=False, indent=2)
        self.show_bubble(text, milliseconds=10_000, kind="thought")
