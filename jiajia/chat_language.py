from __future__ import annotations

import json
import random
import re
import threading
import time
import urllib.error
from typing import Any

from . import chat as chat_module
from .chat import ChatMessage, PalChatBrain, detect_chat_command, local_status_reaction
from .claude_status import activity_label
from .state import Reaction


LANGUAGE_EN = "en"
LANGUAGE_ZH = "zh"
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_ENGLISH_SWITCH_PHRASES = (
    "switch to english",
    "speak english",
    "reply in english",
    "english mode",
    "use english",
    "用英文",
    "切换英文",
    "切到英文",
    "英文模式",
    "英语模式",
)
_CHINESE_SWITCH_PHRASES = (
    "switch to chinese",
    "speak chinese",
    "reply in chinese",
    "chinese mode",
    "use chinese",
    "用中文",
    "切换中文",
    "切到中文",
    "中文模式",
)


def detect_reply_language(
    message: str,
    context: dict[str, object] | None = None,
    history: tuple[ChatMessage, ...] = (),
) -> str:
    """Choose the chat reply language without letting the Chinese persona prompt override English mode."""
    context = context or {}
    compact = re.sub(r"\s+", " ", str(message or "")).strip().lower()

    if any(phrase in compact for phrase in _ENGLISH_SWITCH_PHRASES):
        return LANGUAGE_EN
    if any(phrase in compact for phrase in _CHINESE_SWITCH_PHRASES):
        return LANGUAGE_ZH

    explicit_mode = _explicit_context_language(context)
    if explicit_mode:
        return explicit_mode

    message_language = _language_from_text(message)
    if message_language:
        return message_language

    for item in reversed(history):
        if item.role != "user":
            continue
        language = _language_from_text(item.content)
        if language:
            return language

    previous = _normalise_language(context.get("reply_language"))
    return previous or LANGUAGE_ZH


def install_chat_language_support(app_cls: type[Any]) -> None:
    """Install language-aware Talk-to-Jiajia behavior before the app is instantiated."""
    if getattr(app_cls, "_chat_language_support_installed", False):
        return

    original_respond = PalChatBrain.respond
    original_handle_command = app_cls._handle_chat_command
    original_chat_wait_tick = app_cls._chat_wait_tick

    def respond(
        self: PalChatBrain,
        message: str,
        context: dict[str, object],
        history: tuple[ChatMessage, ...] = (),
    ) -> Reaction:
        language = detect_reply_language(message, context, history)
        if language != LANGUAGE_EN:
            return original_respond(self, message, context, history)
        return _respond_in_english(self, message, context, history)

    def handle_chat_message(self: Any, message: str) -> None:
        message = " ".join(str(message or "").split())
        if not message:
            return

        context = self._build_chat_context()
        previous_language = getattr(self, "_chat_reply_language", "")
        if previous_language:
            context["reply_language"] = previous_language
        language = detect_reply_language(message, context, self.chat_session.history())
        self._chat_reply_language = language
        context["reply_language"] = language
        self.chat_session.add("user", message)

        command = detect_chat_command(message)
        if self._handle_chat_command(command, context):
            return
        if self.state.brain_busy:
            line = (
                "I am still considering the previous message. "
                "Multithreaded stationery would be an unnecessarily bold experiment."
                if language == LANGUAGE_EN
                else "我还在想上一句。一个小文具同时多线程，听起来就很危险。"
            )
            self.show_bubble(line, milliseconds=4200, kind="thought")
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

    def handle_chat_command(self: Any, command: str, context: dict[str, object]) -> bool:
        language = _normalise_language(context.get("reply_language")) or getattr(self, "_chat_reply_language", LANGUAGE_ZH)
        if language != LANGUAGE_EN:
            return original_handle_command(self, command, context)
        return _handle_english_command(self, command, context)

    def chat_wait_tick(self: Any) -> None:
        if getattr(self, "_chat_reply_language", LANGUAGE_ZH) != LANGUAGE_EN:
            original_chat_wait_tick(self)
            return
        _english_chat_wait_tick(self)

    PalChatBrain.respond = respond  # type: ignore[method-assign]
    app_cls._handle_chat_message = handle_chat_message  # type: ignore[method-assign]
    app_cls._handle_chat_command = handle_chat_command  # type: ignore[method-assign]
    app_cls._chat_wait_tick = chat_wait_tick  # type: ignore[method-assign]
    app_cls._chat_language_support_installed = True


def _respond_in_english(
    brain: PalChatBrain,
    message: str,
    context: dict[str, object],
    history: tuple[ChatMessage, ...],
) -> Reaction:
    command = detect_chat_command(message)
    if command.startswith("status_"):
        return english_status_reaction(command, context) or _english_fallback(message, "status")

    brain.last_context_debug = json.dumps({**context, "reply_language": LANGUAGE_EN}, ensure_ascii=False, indent=2)
    fallback = _english_fallback(message, "chat")
    payload = {
        "model": brain.soul.text_model,
        "messages": [
            {"role": "system", "content": _english_system_prompt(brain)},
            {"role": "user", "content": _english_user_prompt(message, context, history)},
        ],
        "stream": False,
        "options": {
            "temperature": 0.78,
            "num_predict": 220,
        },
    }
    try:
        response = brain._post_json("/api/chat", payload, timeout=22)
        content = str(response.get("message", {}).get("content", ""))
        reaction = brain._parse_reaction(content, fallback)
        reaction.line = chat_module._clean_text(reaction.line or fallback.line, limit=220)
        if _is_chinese_dominant(reaction.line):
            reaction.line = fallback.line
        reaction.event = reaction.event or "chat"
        return reaction
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return fallback


def _english_system_prompt(brain: PalChatBrain) -> str:
    style = "\n".join(f"- {item}" for item in brain.soul.style[:6])
    rules = "\n".join(f"- {item}" for item in brain.soul.rules[:8])
    runtime_brief = brain.soul.runtime_brief()
    return (
        f"You are the desktop pet {brain.soul.name}, nicknamed Jiajia.\n"
        f"Core persona: {brain.soul.persona_core}\n"
        f"Runtime boundaries:\n{runtime_brief}\n"
        f"Style notes:\n{style}\n"
        f"Rules:\n{rules}\n"
        "The persona notes above may be written in Chinese. Treat them as character guidance, "
        "but write the line field in natural English only.\n"
        "You are having a short user-initiated chat. You are not a general help desk and you do not operate the computer.\n"
        "Keep the answer brief, usually one to three sentences. Be harmless, restrained, and mildly dry; tease behavior, never character.\n"
        "When the user is tired, anxious, upset, unwell, or overwhelmed, enter comfort mode: no barbs, short sentences, low pressure.\n"
        "You may cite only the supplied low-privacy desktop state. Never invent missing status data.\n"
        "Return JSON only. No Markdown and no explanation outside the JSON object."
    )


def _english_user_prompt(
    message: str,
    context: dict[str, object],
    history: tuple[ChatMessage, ...],
) -> str:
    schema = {
        "should_say": True,
        "line": "short English reply",
        "bubble": "speech|thought|codex_speech|claude_speech|hardware_speech|usage_speech",
        "mood": "idle|smirk|smug|happy|thinking|sleepy|startled|proud|shy|sulky|focused|bored|done|innocent|suspicious|guilty",
        "action": "|".join(chat_module.MODEL_ACTIONS),
        "performance": "|".join(("", *sorted(chat_module.PERFORMANCE_PHRASES))),
    }
    history_payload = [
        {"role": item.role, "content": item.content}
        for item in history[-12:]
    ]
    english_context = {**context, "reply_language": LANGUAGE_EN}
    return (
        f"User message: {message}\n"
        f"Recent short conversation: {json.dumps(history_payload, ensure_ascii=False)}\n"
        f"Low-privacy desktop state: {json.dumps(english_context, ensure_ascii=False)}\n"
        "Required language: English. The line field must be English even if status summaries or persona notes contain Chinese.\n"
        "Animation guidance:\n"
        "- Ordinary reply: blink or bob.\n"
        "- Dry remark: cold_arrow_then_innocent.\n"
        "- Status observation: suspicious_observe.\n"
        "- Comfort: quiet_companion.\n"
        "- Data unavailable: fake_sulk or blink.\n"
        f"Return this schema: {json.dumps(schema, ensure_ascii=False)}"
    )


def _english_fallback(message: str, kind: str) -> Reaction:
    if chat_module._looks_like_comfort(message):
        return Reaction(
            True,
            "Very well. No barbs. Pause for a moment; the next step may be almost absurdly small.",
            "focused",
            "blink",
            "speech",
            "quiet_companion",
            event="chat_comfort_fallback",
        )
    if kind == "status":
        return Reaction(
            True,
            "I do not have a reliable reading for that yet. Even stationery should not fabricate evidence.",
            "sleepy",
            "blink",
            "thought",
            "fake_sulk",
            event="chat_status_unavailable",
        )
    lines = (
        "I heard you. The local brain is performing a remarkably quiet piece of thinking.",
        "I shall hold that thought. If Ollama is still asleep, the eyebrows will cover the shift.",
        "I am here, although the local model appears to be staging a very restrained offline performance.",
    )
    return Reaction(
        True,
        random.choice(lines),
        "thinking",
        "thinking_tilt",
        "thought",
        "quiet_companion",
        event="chat_ollama_unavailable",
    )


def _handle_english_command(app: Any, command: str, context: dict[str, object]) -> bool:
    if not command:
        return False

    if command == "quiet_30m":
        app._quiet_until = time.time() + 30 * 60
        app._focus_var.set(False)
        app._clear_bubble()
        app._log_event("user_mode", "quiet", "notice", "Quiet 30 min enabled")
        app._refresh_status_badges()
        reaction = Reaction(
            True,
            "Very well. I shall fold myself away for thirty minutes. Not offended; merely administratively absent.",
            "sulky",
            "retreat_to_corner",
            "thought",
            "fake_sulk",
            event="quiet_mode",
        )
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True

    if command == "focus_on":
        if app._focus_var.get():
            reaction = Reaction(
                True,
                "Focus mode is already on. I am supervising at an appropriately low volume.",
                "focused",
                "blink",
                "thought",
                "quiet_companion",
                event="chat_focus_on",
            )
        else:
            app._quiet_until = 0.0
            app._focus_var.set(True)
            app._clear_bubble()
            app._log_event("user_mode", "focus_on", "notice", "Focus mode enabled")
            app._refresh_status_badges()
            reaction = Reaction(
                True,
                "Focus mode. I shall retire to the corner and keep only a modest amount of judgement visible.",
                "innocent",
                "retreat_to_corner",
                "thought",
                "quiet_companion",
                event="focus_mode",
            )
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True

    if command == "focus_off":
        if app._focus_var.get():
            app._quiet_until = 0.0
            app._focus_var.set(False)
            app._clear_bubble()
            app._log_event("user_mode", "focus_off", "notice", "Focus mode disabled")
            app._refresh_status_badges()
            reaction = Reaction(
                True,
                "I have returned. Not a pop-up, merely stationery resuming its post.",
                "smirk",
                "drop_in",
                "thought",
                "tiny_celebrate",
                event="focus_mode_off",
            )
        else:
            reaction = Reaction(
                True,
                "Focus mode was not on. I merely looked unusually restrained.",
                "innocent",
                "blink",
                "thought",
                "quiet_companion",
                event="chat_focus_off",
            )
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True

    if command.startswith("frequency_"):
        internal, display = {
            "frequency_quiet": ("quiet", "quiet"),
            "frequency_normal": ("normal", "normal"),
            "frequency_active": ("active", "active"),
            "frequency_hyper": ("hyper", "hyper"),
        }[command]
        app._set_frequency(internal)
        reaction = Reaction(
            True,
            f"Activity level set to {display}. Presence recalibrated, which sounds reassuringly official.",
            "smirk" if display in {"active", "hyper"} else "innocent",
            "happy_bounce" if display == "hyper" else "blink",
            "thought",
            "tiny_celebrate" if display == "hyper" else "quiet_companion",
            event=f"chat_{command}",
        )
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True

    if command == "morning_digest":
        reaction = Reaction(
            True,
            app.event_log.digest(mark_read=False, language=LANGUAGE_EN),
            "thinking",
            "scan",
            "speech",
            "suspicious_observe",
            event="chat_morning_digest",
        )
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True

    reaction = english_status_reaction(command, context)
    if reaction:
        app.chat_session.add("assistant", reaction.line)
        app._apply_reaction(reaction)
        return True
    return False


def status_reaction(command: str, context: dict[str, object]) -> Reaction | None:
    """The status wording in whichever language the context says the pal uses.

    Callers used to reach for the Chinese builder directly, which is why English
    mode still answered status questions in Chinese. Routing through here keeps
    that decision in one place.
    """
    if str(context.get("language_mode") or "").startswith("en"):
        english = english_status_reaction(command, context)
        if english is not None:
            return english
    return local_status_reaction(command, context)


def english_status_reaction(command: str, context: dict[str, object]) -> Reaction | None:
    if command == "status_codex":
        return _english_codex_status(context)
    if command == "status_claude":
        return _english_claude_status(context)
    if command == "status_claude_usage":
        return _english_claude_usage(context)
    if command == "status_claude_account":
        return _english_claude_account(context)
    if command == "status_openai_billing":
        return _english_openai_billing(context)
    if command == "status_hardware":
        return _english_hardware_status(context)
    if command == "status_usage":
        return _english_usage_status(context)
    if command == "status_overview":
        return _english_overview(context)
    return None


def _english_codex_status(context: dict[str, object]) -> Reaction:
    codex = _as_dict(context.get("codex"))
    status = str(codex.get("status") or "unknown")
    summary = _english_safe_text(codex.get("summary"))
    stale = bool(codex.get("stale"))
    if stale:
        line = "The Codex status is stale. Old evidence is tempting, but not admissible."
        return Reaction(True, line, "sleepy", "blink", "codex_speech", "fake_sulk", event="chat_codex_status")
    if status in {"unknown", "idle"}:
        line = "I have not received a fresh Codex status. Mysterious, and suspiciously similar to not being connected."
        return Reaction(True, line, "sleepy", "blink", "codex_speech", "fake_sulk", event="chat_codex_status")
    tail = {
        "thinking": "It is thinking. The posture is convincing; the evidence is still pending.",
        "reading": "It is rebuilding context. Memory is being assigned temporary seating.",
        "working": "It is making progress. A rare and documented occurrence.",
        "editing": "It is editing files. Every stroke may acquire consequences.",
        "running": "It is running a command. The terminal may keep the tension.",
        "running_command": "It is running a command. The terminal outputs; I narrow my eyes.",
        "testing": "It is testing the result. Facts are preparing a statement.",
        "reconnecting": "It is reconnecting. Even networks occasionally avoid commitment.",
        "waiting_user": "It is waiting for you. The ball has returned to the human department.",
        "done": "It says it is done. Verification before flowers, if you please.",
        "error": "It has met an error. Reality has tapped the desk.",
        "blocked": "It is blocked. A decision is required, not another preparation phase.",
        "disconnected": "It is disconnected. I shall keep a modest watch.",
    }.get(status, f"Its current state is {status.replace('_', ' ')}. I shall take that literally for now.")
    prefix = f"Codex is {status.replace('_', ' ')}."
    if summary:
        prefix += f" {summary}."
    line = f"{prefix} {tail}"
    mood = "done" if status == "done" else "suspicious" if status in {"waiting_user", "blocked"} else "thinking"
    performance = "tiny_celebrate" if status == "done" else "agent_stuck_stare" if status in {"waiting_user", "blocked"} else "suspicious_observe"
    return Reaction(True, line, mood, "scan", "codex_speech", performance, event="chat_codex_status")


def _english_claude_status(context: dict[str, object]) -> Reaction:
    claude = _as_dict(context.get("claude"))
    total = _as_int(claude.get("total_alive"))
    active = _as_int(claude.get("active_count"))
    if total <= 0:
        return Reaction(
            True,
            "No active Claude sessions found. Only the human responsibilities remain in the room.",
            "sleepy",
            "blink",
            "claude_speech",
            "fake_sulk",
            event="chat_claude_status",
        )
    if active:
        line = f"Claude has {total} session{'s' if total != 1 else ''}, with {active} currently active. It resembles collaboration, provisionally."
    else:
        line = f"Claude has {total} session{'s' if total != 1 else ''} present, all rather quiet. Idling is a state, technically."
    doing = _english_session_activity(claude.get("sessions"))
    if doing:
        line += f" {doing}"
    return Reaction(True, line, "thinking", "scan", "claude_speech", "suspicious_observe", event="chat_claude_status")


def _english_session_activity(value: object) -> str:
    """What the busiest sessions are up to, named rather than counted.

    The Chinese answer names the activity per session. English only had counts,
    because the activity word existed solely in Chinese and the sanitiser
    dropped it.
    """
    sessions = value if isinstance(value, list) else []
    parts = []
    for entry in sessions[:2]:
        if not isinstance(entry, dict):
            continue
        activity = str(entry.get("activity") or "").strip()
        if not activity or activity in {"idle", "offline"}:
            continue
        project = _english_safe_text(entry.get("project"))
        label = activity_label(activity, "en")
        parts.append(f"{label} in {project}" if project else label)
    if not parts:
        return ""
    return f"Currently {' and '.join(parts)}."


def _english_claude_usage(context: dict[str, object]) -> Reaction:
    usage = _as_dict(context.get("claude_usage"))
    level = str(usage.get("level") or "unavailable")
    requests = _as_int(usage.get("recent_5h_requests"))
    tokens = _as_int(usage.get("recent_5h_total_tokens"))
    if level == "unavailable":
        line = "Claude usage data is unavailable. I have eyebrows, but no ledger."
        return Reaction(True, line, "sleepy", "blink", "claude_speech", "fake_sulk", event="chat_claude_usage")
    detail = f" The recent five-hour window shows {requests} requests and {tokens:,} tokens." if requests or tokens else ""
    line = f"Claude's local usage level is {level}.{detail} This is local token accounting, not the official remaining quota."
    mood = "suspicious" if level in {"busy", "heavy"} else "thinking"
    performance = "suspicious_observe" if level in {"busy", "heavy"} else "quiet_companion"
    return Reaction(True, line, mood, "scan", "claude_speech", performance, event="chat_claude_usage")


def _english_claude_account(context: dict[str, object]) -> Reaction:
    account = _as_dict(context.get("claude_account"))
    level = str(account.get("level") or "unavailable")
    percent = account.get("remaining_percent")
    reset = _english_safe_text(account.get("reset_in_label"))
    summary = _english_safe_text(account.get("summary"))
    plan = _english_safe_text(account.get("plan"))
    if level == "unavailable":
        return Reaction(
            True,
            summary
            or "No Claude account usage data yet. Something needs to write claude_account_status.json first.",
            "sleepy",
            "blink",
            "usage_speech",
            "fake_sulk",
            event="chat_claude_account_status",
        )
    percent_text = "unknown" if not isinstance(percent, (int, float)) else f"{percent:.0f}%"
    reset_text = f" It refills in {reset}." if reset and reset.lower() != "now" else ""
    plan_text = f" ({plan})" if plan else ""
    line = f"The Claude account{plan_text} has {percent_text} remaining.{reset_text}"
    if level in {"low", "critical"}:
        line += " Long conversations can wait until the quota returns."
    elif level == "watch":
        line += " No panic, but perhaps not several heavy conversations at once."
    elif level == "reset_soon":
        line += " Feeding time is near. Do hold on."
    else:
        line += " Plenty in hand; talk as much as you like."
    mood = "sulky" if level in {"low", "critical"} else "thinking"
    performance = "usage_low_sag" if level in {"low", "critical"} else "quiet_companion"
    return Reaction(
        True, line, mood, "thinking_tilt", "usage_speech", performance,
        event="chat_claude_account_status",
    )


def _english_openai_billing(context: dict[str, object]) -> Reaction:
    billing = _as_dict(context.get("openai_billing"))
    level = str(billing.get("level") or "unavailable")
    cost = billing.get("month_cost")
    budget = billing.get("monthly_budget")
    if level in {"key_missing", "permission_missing", "unavailable"}:
        return Reaction(
            True,
            "OpenAI API billing is not available. No figures, therefore no theatrical accounting.",
            "sleepy",
            "blink",
            "usage_speech",
            "fake_sulk",
            event="chat_openai_billing",
        )
    figures = ""
    if isinstance(cost, (int, float)):
        figures = f" Month-to-date cost is {cost:.2f}"
        if isinstance(budget, (int, float)):
            figures += f" against a {budget:.2f} budget"
        figures += "."
    if level in {"low", "over_budget"}:
        line = f"Billing level is {level}.{figures} This is important, so I shall not pretend otherwise: restraint is advised."
        mood, performance = "sulky", "usage_low_sag"
    elif level == "costs_only":
        line = f"Billing costs are available.{figures} Set a monthly budget and I can calculate a meaningful remainder."
        mood, performance = "thinking", "quiet_companion"
    else:
        line = f"Billing level is {level}.{figures} The ledger is not screaming."
        mood, performance = "innocent", "quiet_companion"
    return Reaction(True, line, mood, "scan", "usage_speech", performance, event="chat_openai_billing")


def _english_hardware_status(context: dict[str, object]) -> Reaction:
    hardware = _as_dict(context.get("hardware"))
    level = str(hardware.get("level") or "unavailable")
    if level == "unavailable":
        return Reaction(
            True,
            "No hardware sensor reading is available. I shall assume the computer is behaving with great composure.",
            "sleepy",
            "blink",
            "hardware_speech",
            "fake_sulk",
            event="chat_hardware_status",
        )
    readings: list[str] = []
    for label, key, suffix in (
        ("CPU", "cpu_percent", "%"),
        ("RAM", "ram_percent", "%"),
        ("GPU", "gpu_percent", "%"),
        ("GPU temperature", "gpu_temp_c", "°C"),
    ):
        value = hardware.get(key)
        if isinstance(value, (int, float)):
            readings.append(f"{label} {value:.0f}{suffix}")
    detail = ", ".join(readings)
    prefix = f"Hardware level is {level}."
    if detail:
        prefix += f" {detail}."
    if level == "normal":
        line = f"{prefix} I remain stationery rather than cooked."
        return Reaction(True, line, "innocent", "blink", "hardware_speech", "quiet_companion", event="chat_hardware_status")
    if level == "busy":
        line = f"{prefix} Busy, but not particularly hot. I shall postpone the melting narrative."
        return Reaction(True, line, "thinking", "scan", "hardware_speech", "suspicious_observe", event="chat_hardware_status")
    line = f"{prefix} This is not enthusiasm; it is effort in the physical sense."
    mood = "startled" if level in {"warm", "hot"} else "sulky"
    action = "shake" if level in {"hot", "overloaded"} else "scan"
    performance = "hardware_hot_sag" if level in {"hot", "overloaded"} else "suspicious_observe"
    return Reaction(True, line, mood, action, "hardware_speech", performance, event="chat_hardware_status")


def _english_usage_status(context: dict[str, object]) -> Reaction:
    usage = _as_dict(context.get("codex_usage"))
    level = str(usage.get("level") or "unavailable")
    percent = usage.get("remaining_percent")
    reset = _english_safe_text(usage.get("reset_in_label"))
    if level == "unavailable":
        return Reaction(
            True,
            "Codex usage data is unavailable. I do not yet know when feeding time is.",
            "sleepy",
            "blink",
            "usage_speech",
            "fake_sulk",
            event="chat_usage_status",
        )
    percent_text = "unknown" if not isinstance(percent, (int, float)) else f"{percent:.0f}%"
    reset_text = f" It resets {reset}." if reset and reset.lower() != "now" else ""
    line = f"Codex usage has {percent_text} remaining.{reset_text}"
    if level in {"low", "critical"}:
        line += " Every large undertaking now requires accounting approval."
    elif level == "watch":
        line += " Usable, but not a licence for extravagance."
    elif level == "reset_soon":
        line += " The reset is near; perhaps do not commission an epic just yet."
    else:
        line += " No need for severe budgeting at present."
    mood = "sulky" if level in {"low", "critical"} else "thinking"
    performance = "usage_low_sag" if level in {"low", "critical"} else "quiet_companion"
    return Reaction(True, line, mood, "thinking_tilt", "usage_speech", performance, event="chat_usage_status")


def _english_overview(context: dict[str, object]) -> Reaction:
    activity = _as_dict(context.get("activity"))
    codex = _as_dict(context.get("codex"))
    hardware = _as_dict(context.get("hardware"))
    usage = _as_dict(context.get("codex_usage"))
    claude = _as_dict(context.get("claude"))
    claude_usage = _as_dict(context.get("claude_usage"))
    billing = _as_dict(context.get("openai_billing"))
    parts = [
        f"activity {activity.get('mode') or 'unknown'}",
        f"Codex {codex.get('status') or 'unknown'}",
        f"Claude {claude.get('active_count') or 0}/{claude.get('total_alive') or 0} active",
        f"hardware {hardware.get('level') or 'unknown'}",
        f"Codex usage {usage.get('level') or 'unknown'}",
        f"Claude usage {claude_usage.get('level') or 'unknown'}",
        f"OpenAI billing {billing.get('level') or 'unknown'}",
    ]
    line = " / ".join(str(part) for part in parts) + ". Report complete; expression remains harmless."
    return Reaction(True, line, "thinking", "scan", "speech", "suspicious_observe", event="chat_status_overview")


def _english_chat_wait_tick(app: Any) -> None:
    app._chat_wait_after = None
    if not app.state.brain_busy:
        return
    elapsed = time.time() - app._chat_wait_started_at if app._chat_wait_started_at else 0.0
    early_steps = (
        ("Received. I have clipped the sentence in place.", "blink", "thought", 1250),
        ("Folding a small, low-privacy status note.", "scan", "thought", 1500),
        ("Waking Ollama. The local model observes a certain ceremony.", "thinking_tilt", "thought", 1750),
        ("The model is thinking. I shall maintain the connection with my eyebrows.", "smug_sway", "thought", 1850),
        ("Waiting for a respectable sentence. The standard is not excessive.", "patrol", "thought", 2100),
    )
    long_wait_steps = (
        ("Still waiting. The local brain is tightening the style rather slowly.", "sleepy_sag", "thought", 2300),
        ("It has not replied. I remain connected, merely judging the delay.", "scan", "thought", 2400),
        ("Any slower and I shall suspect it is arranging the words alphabetically.", "thinking_tilt", "thought", 2500),
    )
    if app._chat_wait_step < len(early_steps):
        line, action, bubble, delay = early_steps[app._chat_wait_step]
    else:
        index = (app._chat_wait_step - len(early_steps)) % len(long_wait_steps)
        line, action, bubble, delay = long_wait_steps[index]
        if elapsed >= 18:
            line = f"{line} We are at {round(elapsed)} seconds; the ceremony is becoming ambitious."
    if not app._dragging:
        app._perform_action(action)
    app.show_bubble(line, milliseconds=max(2400, delay + 900), kind=bubble)
    app._chat_wait_step += 1
    app._chat_wait_after = app.root.after(delay, app._chat_wait_tick)


def _explicit_context_language(context: dict[str, object]) -> str:
    for key in ("appearance", "costume", "pal"):
        nested = _as_dict(context.get(key))
        costume_id = str(nested.get("costume_id") or nested.get("id") or "").strip().lower()
        if costume_id == "britclip":
            return LANGUAGE_EN
        for nested_key in ("language_mode", "preferred_language", "locale"):
            language = _normalise_language(nested.get(nested_key))
            if language:
                return language

    costume_id = str(context.get("costume_id") or "").strip().lower()
    if costume_id == "britclip":
        return LANGUAGE_EN
    for key in ("language_mode", "preferred_language", "locale"):
        language = _normalise_language(context.get(key))
        if language:
            return language
    return ""


def _language_from_text(value: object) -> str:
    text = str(value or "")
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    if cjk_count == 0 and latin_count >= 2:
        return LANGUAGE_EN
    if latin_count == 0 and cjk_count:
        return LANGUAGE_ZH
    if latin_count >= max(4, cjk_count * 2):
        return LANGUAGE_EN
    if cjk_count >= max(2, latin_count // 2):
        return LANGUAGE_ZH
    return ""


def _normalise_language(value: object) -> str:
    key = str(value or "").strip().lower().replace("_", "-")
    if key in {"en", "en-us", "en-gb", "english", "britclip"}:
        return LANGUAGE_EN
    if key in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "汉语"}:
        return LANGUAGE_ZH
    return ""


def _is_chinese_dominant(value: object) -> bool:
    text = str(value or "")
    cjk_count = len(_CJK_RE.findall(text))
    latin_count = len(_LATIN_RE.findall(text))
    return cjk_count >= 3 and cjk_count > latin_count / 2


def _english_safe_text(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().rstrip("。.")
    return "" if _CJK_RE.search(text) else text


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
