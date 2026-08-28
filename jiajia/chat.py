from __future__ import annotations

from dataclasses import dataclass, field
import json
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .actions import MODEL_ACTIONS
from .performance import PERFORMANCE_PHRASES
from .soul import Soul
from .state import Reaction
from .world import WorldState


READ_ONLY_COMMANDS = {
    "status_overview",
    "status_codex",
    "status_claude",
    "status_hardware",
    "status_usage",
    "status_claude_account",
}


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    created_at: float = field(default_factory=time.time)


class ChatSession:
    def __init__(self, max_turns: int = 12) -> None:
        self.max_messages = max(2, max_turns * 2)
        self._messages: list[ChatMessage] = []

    def add(self, role: str, content: str) -> None:
        role = "assistant" if role == "assistant" else "user"
        clean = _clean_text(content, limit=520)
        if not clean:
            return
        self._messages.append(ChatMessage(role, clean))
        self._messages = self._messages[-self.max_messages :]

    def history(self) -> tuple[ChatMessage, ...]:
        return tuple(self._messages)

    def prompt_lines(self) -> list[dict[str, str]]:
        return [{"role": msg.role, "content": msg.content} for msg in self._messages]


class PalChatBrain:
    """Small user-initiated chat brain. Ambient chatter stays in OllamaBrain."""

    def __init__(self, soul: Soul, endpoint: str = "http://127.0.0.1:11434") -> None:
        self.soul = soul
        self.endpoint = endpoint.rstrip("/")
        self.last_context_debug = ""

    def respond(
        self,
        message: str,
        context: dict[str, object],
        history: tuple[ChatMessage, ...] = (),
    ) -> Reaction:
        command = detect_chat_command(message)
        if command in READ_ONLY_COMMANDS:
            return local_status_reaction(command, context) or self._fallback(message, "status")

        self.last_context_debug = json.dumps(context, ensure_ascii=False, indent=2)
        fallback = self._fallback(message, "chat")
        payload = {
            "model": self.soul.text_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(message, context, history)},
            ],
            "stream": False,
            "options": {
                "temperature": 0.78,
                "num_predict": 220,
            },
        }
        try:
            response = self._post_json("/api/chat", payload, timeout=22)
            content = str(response.get("message", {}).get("content", ""))
            reaction = self._parse_reaction(content, fallback)
            reaction.line = _clean_text(reaction.line or fallback.line, limit=220)
            reaction.event = reaction.event or "chat"
            return reaction
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return fallback

    def _system_prompt(self) -> str:
        style = "\n".join(f"- {item}" for item in self.soul.style[:6])
        rules = "\n".join(f"- {item}" for item in self.soul.rules[:8])
        runtime_brief = self.soul.runtime_brief()
        if self.soul.language == "en":
            return (
                f"You are the desktop pet {self.soul.name}.\n"
                f"Persona core: {self.soul.persona_core}\n"
                f"Runtime boundaries:\n{runtime_brief}\n"
                f"Speaking style:\n{style}\n"
                f"Rules:\n{rules}\n"
                "You are having a short chat with the user. You are not general support, "
                "and you do not operate their computer for them.\n"
                "Keep replies short, usually 1-3 sentences. You may be well-behaved, harmless "
                "and mildly barbed, but only about behaviour — never about who they are.\n"
                "If the user sounds tired, anxious, sad, unwell or overwhelmed, enter comfort "
                "mode: no roasting, short sentences, lower your presence.\n"
                "You may reference the low-privacy desktop state provided: Codex, Claude, "
                "hardware, Codex usage, Claude usage, Claude account quota, OpenAI API "
                "billing, activity level, and your own recent lines.\n"
                "Never claim to see data that is not in the context. If a status is unknown, "
                "say so plainly, with a little of your own flavour.\n"
                "Write in natural English.\n"
                "Output JSON. No Markdown, no explanation."
            )
        return (
            f"你是桌宠 {self.soul.name}，昵称夹夹。\n"
            f"人设核心: {self.soul.persona_core}\n"
            f"运行边界:\n{runtime_brief}\n"
            f"说话风格:\n{style}\n"
            f"规矩:\n{rules}\n"
            "你正在和用户短聊，不是通用客服，也不替用户操作电脑。\n"
            "回答要短，通常 1-3 句。可以乖巧、无害、轻微毒舌，但只戳行为，不评价人格。\n"
            "如果用户表达累、焦虑、难过、不舒服、崩溃，进入 comfort mode：不毒舌，短句，降低存在感。\n"
            "你可以引用给定的低隐私桌面状态：Codex、Claude、硬件、Codex usage、Claude usage、Claude 账号额度、OpenAI API billing、活跃度、最近自己说过的话。\n"
            "不要声称看到了上下文里没有的数据。状态未知就直接说未知，带一点夹夹味。\n"
            "输出 JSON，不要 Markdown，不要解释。"
        )

    def _user_prompt(
        self,
        message: str,
        context: dict[str, object],
        history: tuple[ChatMessage, ...],
    ) -> str:
        schema = {
            "should_say": True,
            "line": "中文短回复",
            "bubble": "speech|thought|codex_speech|claude_speech|hardware_speech|usage_speech",
            "mood": "idle|smirk|smug|happy|thinking|sleepy|startled|proud|shy|sulky|focused|bored|done|innocent|suspicious|guilty",
            "action": "|".join(MODEL_ACTIONS),
            "performance": "|".join(("", *sorted(PERFORMANCE_PHRASES))),
        }
        history_payload = [
            {"role": msg.role, "content": msg.content}
            for msg in history[-12:]
        ]
        return (
            f"用户这次说: {message}\n"
            f"最近短对话: {json.dumps(history_payload, ensure_ascii=False)}\n"
            f"低隐私桌面状态: {json.dumps(context, ensure_ascii=False)}\n"
            "选择动画提示:\n"
            "- 普通回答: blink 或 bob。\n"
            "- 吐槽/冷箭: cold_arrow_then_innocent。\n"
            "- 状态观察: suspicious_observe。\n"
            "- 安慰: quiet_companion。\n"
            "- 数据不可用: fake_sulk 或 blink。\n"
            f"请按这个 schema 输出: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _fallback(self, message: str, kind: str) -> Reaction:
        if _looks_like_comfort(message):
            return Reaction(
                True,
                "好，我不夹你了。先停一下，下一小步可以小到不像任务。",
                "focused",
                "blink",
                "speech",
                "quiet_companion",
                event="chat_comfort_fallback",
            )
        if kind == "status":
            return Reaction(
                True,
                "这块状态我暂时没读到。夹夹没有证据，就先不装懂。",
                "sleepy",
                "blink",
                "thought",
                "fake_sulk",
                event="chat_status_unavailable",
            )
        lines = (
            "我听见了。然后本地脑子假装很深沉地转了一下。",
            "这句我先夹住。Ollama 如果没醒，我就用眉毛顶班。",
            "我在，但本地模型好像在进行非常安静的离线表演。",
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

    def _post_json(self, path: str, payload: dict[str, object], timeout: int) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.endpoint}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _parse_reaction(self, content: str, fallback: Reaction) -> Reaction:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            return fallback
        data = json.loads(match.group(0))
        return Reaction(
            should_say=bool(data.get("should_say", True)),
            line=str(data.get("line") or fallback.line),
            mood=str(data.get("mood") or fallback.mood),
            action=_clean_action(data.get("action"), fallback.action),
            bubble=_clean_bubble(data.get("bubble"), fallback.bubble),
            performance=_clean_performance(data.get("performance")),
            event="chat",
        )


def build_chat_context(
    world: WorldState,
    *,
    activity_mode: str = "",
    activity_tier: str = "",
    focus_mode: bool = False,
    quiet_remaining_seconds: float = 0.0,
) -> dict[str, object]:
    user = world.user_activity
    codex = world.codex
    usage = world.codex_usage
    hardware = world.hardware
    claude = world.claude
    claude_usage = world.claude_usage
    claude_account = world.claude_account_usage
    openai_billing = world.openai_billing
    return {
        "activity": {
            "mode": activity_mode or world.mood.key,
            "tier": activity_tier,
            "focus_mode": focus_mode,
            "quiet_remaining_seconds": round(max(0.0, quiet_remaining_seconds), 1),
            "app_category": user.app_category,
            "active_process": _clean_text(user.active_process, limit=80),
            "focus_seconds": round(user.focus_seconds, 1),
            "idle_seconds": round(user.idle_seconds, 1),
            "window_switches_per_minute": user.window_switches_per_minute,
            "activity_level": user.activity_level,
            "behavior_tags": list(user.behavior_tags),
        },
        "pal": {
            "mood": world.pal.mood,
            "recent_lines": list(world.pal.recent_lines[-4:]),
            **world.mood.as_dict(),
        },
        "codex": {
            "status": codex.status,
            "summary": codex.summary,
            "updated_at": codex.updated_at,
            "source": codex.source,
            "stale": codex.stale,
        },
        "codex_usage": {
            "level": usage.level,
            "remaining_percent": _round_or_none(usage.usage_remaining_percent),
            "reset_in_label": _usage_reset_label(usage.as_dict()),
            "summary": usage.summary_line,
            "stale": usage.stale,
        },
        "claude_usage": {
            "level": claude_usage.level,
            "summary": claude_usage.summary_line,
            "source": claude_usage.source,
            "stale": claude_usage.stale,
            "today_requests": claude_usage.today.requests,
            "today_total_tokens": claude_usage.today.total_tokens,
            "recent_5h_requests": claude_usage.recent_5h.requests,
            "recent_5h_total_tokens": claude_usage.recent_5h.total_tokens,
            "recent_models": list(claude_usage.recent_5h.models),
        },
        "claude_account": {
            "level": claude_account.level,
            "remaining_percent": _round_or_none(claude_account.usage_remaining_percent),
            "reset_in_label": _claude_account_reset_label(claude_account.as_dict()),
            "summary": claude_account.summary_line,
            "plan": claude_account.plan,
            "stale": claude_account.stale,
        },
        "openai_billing": {
            "level": openai_billing.level,
            "summary": openai_billing.summary_line,
            "month_cost": _round_or_none(openai_billing.month_cost),
            "monthly_budget": _round_or_none(openai_billing.monthly_budget),
            "remaining": _round_or_none(openai_billing.remaining),
            "prepaid_balance_snapshot": _round_or_none(openai_billing.prepaid_balance_snapshot),
            "prepaid_balance_snapshot_at": openai_billing.prepaid_balance_snapshot_at,
            "cost_since_prepaid_snapshot": _round_or_none(openai_billing.cost_since_prepaid_snapshot),
            "estimated_prepaid_remaining": _round_or_none(openai_billing.estimated_prepaid_remaining),
            "currency": openai_billing.currency,
            "error_kind": openai_billing.error_kind,
        },
        "claude": {
            "total_alive": claude.total_alive,
            "active_count": claude.active_count,
            "summary": claude.summary_line(),
            "sessions": [
                {
                    "project": _clean_text(session.project, limit=80),
                    "activity": session.activity,
                    "idle_seconds": round(session.idle_seconds, 1),
                }
                for session in claude.sessions
                if session.alive
            ][:4],
        },
        "audio": {
            "available": world.audio.available,
            "playing": world.audio.playing,
            "level": world.audio.level,
            "session_seconds": round(world.audio.session_seconds, 1),
            "silence_seconds": round(world.audio.silence_seconds, 1),
        },
        "hardware": {
            "level": hardware.level,
            "summary": hardware.summary_line,
            "cpu_percent": _round_or_none(hardware.cpu_percent),
            "ram_percent": _round_or_none(hardware.ram_percent),
            "gpu_percent": _round_or_none(hardware.gpu_percent),
            "gpu_temp_c": _round_or_none(hardware.gpu_temp_c),
            "vram_percent": _round_or_none(hardware.vram_percent),
        },
        "environment_tags": list(world.environment_tags),
    }


def detect_chat_command(message: str) -> str:
    lowered = message.lower().strip()
    compact = re.sub(r"\s+", "", lowered)
    if not compact:
        return ""

    if _has_any(compact, ("早报", "晨报", "morningdigest", "digest", "收菜")):
        return "morning_digest"
    if _has_any(compact, ("闭嘴", "别说话", "安静半小时", "quiet30", "shutup", "shush")):
        return "quiet_30m"

    if "claude" in compact and _has_any(compact, ("账号", "account", "订阅", "subscription", "配额", "消息", "remaining", "剩余", "还能用")):
        return "status_claude_account"
    if "claude" in compact and _has_any(compact, ("usage", "用量", "额度", "token", "tokens", "账单", "账本", "今天用了多少", "花了多少")):
        return "status_claude_usage"
    if _has_any(compact, ("openaiapi余额", "openai余额", "api余额", "api账单", "api花费", "api费用", "openaibilling", "openai账单", "openai花费", "openai费用", "billing")):
        return "status_openai_billing"
    if _has_any(compact, ("codexusage", "codex额度", "额度", "quota", "remaining", "还剩多少", "reset")):
        return "status_usage"
    if "claude" in compact and _has_any(compact, ("状态", "status", "在干嘛", "怎么", "卡", "会话")):
        return "status_claude"
    if "codex" in compact and _has_any(compact, ("状态", "status", "在干嘛", "怎么", "卡", "好了", "没好", "没收到", "done")):
        return "status_codex"
    if _has_any(compact, ("硬件", "电脑为什么卡", "为什么卡", "gpu", "cpu", "ram", "显卡", "温度", "变红", "烫", "发热")):
        return "status_hardware"
    if compact in {"状态", "status", "汇报", "状态汇报", "report"}:
        return "status_overview"

    if _has_any(compact, ("专注", "focus")):
        if _has_any(compact, ("退出", "关闭", "取消", "off", "stop", "结束")):
            return "focus_off"
        return "focus_on"

    if _has_any(compact, ("吐槽模式", "毒舌一点", "嘴欠一点", "roastmode")):
        return "frequency_active"
    if _is_mode_command(compact, "安静", "quiet"):
        return "frequency_quiet"
    if _is_mode_command(compact, "正常", "normal"):
        return "frequency_normal"
    if _is_mode_command(compact, "活泼", "active"):
        return "frequency_active"
    if _is_mode_command(compact, "多动", "hyper"):
        return "frequency_hyper"
    return ""


def local_status_reaction(command: str, context: dict[str, object]) -> Reaction | None:
    if command == "status_codex":
        return _codex_status_reaction(context)
    if command == "status_claude":
        return _claude_status_reaction(context)
    if command == "status_claude_usage":
        return _claude_usage_status_reaction(context)
    if command == "status_claude_account":
        return _claude_account_status_reaction(context)
    if command == "status_openai_billing":
        return _openai_billing_status_reaction(context)
    if command == "status_hardware":
        return _hardware_status_reaction(context)
    if command == "status_usage":
        return _usage_status_reaction(context)
    if command == "status_overview":
        return _overview_reaction(context)
    return None


def _codex_status_reaction(context: dict[str, object]) -> Reaction:
    codex = _dict(context.get("codex"))
    status = str(codex.get("status") or "unknown")
    summary = str(codex.get("summary") or "").strip()
    stale = bool(codex.get("stale"))
    if status in {"unknown", "idle"} or stale:
        line = "我还没有收到 Codex 的新状态。很神秘，也很像没接线。"
        if stale:
            line = "Codex 状态有点旧。旧证据不适合拿来审判，虽然很诱人。"
        return Reaction(True, line, "sleepy", "blink", "codex_speech", "fake_sulk", event="chat_codex_status")
    tail = {
        "thinking": "它在想。姿势很认真，证据暂时不多。",
        "reading": "它在补上下文。像在给记忆临时排座位。",
        "working": "它在推进。桌面上出现了罕见的工作痕迹。",
        "editing": "它在改文件。每一笔都可能有后果。",
        "running": "它在跑命令。现在紧张感交给终端保管。",
        "running_command": "它在跑命令。终端负责输出，夹夹负责眯眼。",
        "testing": "它在检查结果。事实准备发表意见了。",
        "reconnecting": "它在重连。网络也有逃避型人格。",
        "waiting_user": "它在等你。球已经递回人类这边。",
        "done": "它说做完了。建议先验一下，别急着给它戴花。",
        "error": "它遇到错误了。现实轻轻敲了一下桌面。",
        "blocked": "它卡住了。现在需要决定，不是再准备一下。",
        "disconnected": "它断开了。夹夹先小声站岗。",
    }.get(status, f"它现在是 {status}。夹夹先按字面理解。")
    if summary:
        line = f"Codex 现在是 {status}：{summary}。{tail}"
    else:
        line = f"Codex 现在是 {status}。{tail}"
    mood = "done" if status == "done" else "suspicious" if status in {"waiting_user", "blocked"} else "thinking"
    performance = "tiny_celebrate" if status == "done" else "agent_stuck_stare" if status in {"waiting_user", "blocked"} else "suspicious_observe"
    return Reaction(True, line, mood, "scan", "codex_speech", performance, event="chat_codex_status")


def _sentence(value: object) -> str:
    """A summary ready to be concatenated: one trailing 。, or nothing at all.

    Callers used to append their own 。, which produced 。。 after a summary that
    already ended in one, and a leading 。 when the summary was empty.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text[-1] in "。！？.!?" else f"{text}。"


def _claude_status_reaction(context: dict[str, object]) -> Reaction:
    claude = _dict(context.get("claude"))
    total = _int(claude.get("total_alive"))
    active = _int(claude.get("active_count"))
    summary = _sentence(claude.get("summary"))
    if total <= 0:
        return Reaction(
            True,
            "没有发现活跃的 Claude 会话。空气里只剩人类责任。",
            "sleepy",
            "blink",
            "claude_speech",
            "fake_sulk",
            event="chat_claude_status",
        )
    if active:
        line = f"Claude 有 {total} 个会话，{active} 个在动。{summary}场面像协作，暂时。"
    else:
        line = f"Claude 有 {total} 个会话在场，但都比较安静。发呆也算一种状态，勉强。"
    return Reaction(True, line, "thinking", "scan", "claude_speech", "suspicious_observe", event="chat_claude_status")


def _claude_usage_status_reaction(context: dict[str, object]) -> Reaction:
    usage = _dict(context.get("claude_usage"))
    level = str(usage.get("level") or "unavailable")
    summary = str(usage.get("summary") or "").strip()
    if level == "unavailable":
        line = summary or "还没有 Claude usage 数据。夹夹暂时没有账本，只有眉毛。"
        return Reaction(True, line, "sleepy", "blink", "claude_speech", "fake_sulk", event="chat_claude_usage")
    line = summary or "Claude usage 有数据，但它今天表现得过于抽象。"
    if level in {"busy", "heavy"}:
        line += " 这不是官方剩余额度，是本地 token 账；夹夹不会拿旧账冒充限额。"
        mood, performance = "suspicious", "suspicious_observe"
    else:
        line += " 这是本地 token 账，不是官方剩余额度。"
        mood, performance = "thinking", "quiet_companion"
    return Reaction(True, line, mood, "scan", "claude_speech", performance, event="chat_claude_usage")


def _claude_account_status_reaction(context: dict[str, object]) -> Reaction:
    account = _dict(context.get("claude_account"))
    level = str(account.get("level") or "unavailable")
    percent = account.get("remaining_percent")
    reset = str(account.get("reset_in_label") or "").strip()
    summary = str(account.get("summary") or "").strip()
    plan = str(account.get("plan") or "").strip()
    if level == "unavailable":
        return Reaction(
            True,
            summary or "还没有 Claude 账号 usage 数据。需要先用脚本写入 claude_account_status.json。",
            "sleepy",
            "blink",
            "usage_speech",
            "fake_sulk",
            event="chat_claude_account_status",
        )
    percent_text = "未知" if percent is None else f"{float(percent):.0f}%"
    reset_text = f"，{reset} 后回血" if reset and reset != "现在" else ""
    plan_text = f"（{plan}）" if plan else ""
    line = f"Claude 账号{plan_text}还剩 {percent_text}{reset_text}。"
    if level in {"low", "critical"}:
        line += " 长对话先缓缓，等额度回来。"
    elif level == "watch":
        line += " 不急，但别开太多重对话。"
    elif level == "reset_soon":
        line += " 饭点快到了，再忍忍。"
    else:
        line += " 额度充裕，想聊就聊。"
    mood = "sulky" if level in {"low", "critical"} else "thinking"
    performance = "usage_low_sag" if level in {"low", "critical"} else "quiet_companion"
    return Reaction(True, line, mood, "thinking_tilt", "usage_speech", performance, event="chat_claude_account_status")


def _openai_billing_status_reaction(context: dict[str, object]) -> Reaction:
    billing = _dict(context.get("openai_billing"))
    level = str(billing.get("level") or "unavailable")
    summary = str(billing.get("summary") or "").strip() or "OpenAI API 账单暂时没读到。"
    if level in {"key_missing", "permission_missing", "unavailable"}:
        return Reaction(True, summary, "sleepy", "blink", "usage_speech", "fake_sulk", event="chat_openai_billing")
    if level in {"low", "over_budget"}:
        line = summary + " 这个很重要，所以夹夹不嘴硬：该收手时要收手。"
        mood, performance = "sulky", "usage_low_sag"
    elif level == "costs_only":
        line = summary + " 你给我一个月预算，我就能算真正的剩余。"
        mood, performance = "thinking", "quiet_companion"
    else:
        line = summary + " 账本暂时没有尖叫。"
        mood, performance = "innocent", "quiet_companion"
    return Reaction(True, line, mood, "scan", "usage_speech", performance, event="chat_openai_billing")


def _hardware_status_reaction(context: dict[str, object]) -> Reaction:
    hardware = _dict(context.get("hardware"))
    level = str(hardware.get("level") or "unavailable")
    summary = _sentence(hardware.get("summary"))
    if level == "unavailable":
        line = summary or "没有读到硬件传感器。夹夹先假装电脑很冷静。"
        return Reaction(True, line, "sleepy", "blink", "hardware_speech", "fake_sulk", event="chat_hardware_status")
    if level == "normal":
        line = f"{summary or '硬件状态正常。'}暂时不熟，夹夹保持办公用品形态。"
        return Reaction(True, line, "innocent", "blink", "hardware_speech", "quiet_companion", event="chat_hardware_status")
    if level == "busy":
        line = f"{summary}它很忙，但温度不高。夹夹先不装作电脑熟了。"
        return Reaction(True, line, "thinking", "scan", "hardware_speech", "suspicious_observe", event="chat_hardware_status")
    line = f"{summary}等级是 {level}，它不是热情，是物理意义上的努力。"
    mood = "startled" if level in {"warm", "hot"} else "sulky"
    action = "shake" if level in {"hot", "overloaded"} else "scan"
    performance = "hardware_hot_sag" if level in {"hot", "overloaded"} else "suspicious_observe"
    return Reaction(True, line, mood, action, "hardware_speech", performance, event="chat_hardware_status")


def _usage_status_reaction(context: dict[str, object]) -> Reaction:
    usage = _dict(context.get("codex_usage"))
    level = str(usage.get("level") or "unavailable")
    percent = usage.get("remaining_percent")
    reset = str(usage.get("reset_in_label") or "").strip()
    summary = str(usage.get("summary") or "").strip()
    if level == "unavailable":
        return Reaction(
            True,
            summary or "还没有 Codex usage 数据。夹夹暂时不知道饭点。",
            "sleepy",
            "blink",
            "usage_speech",
            "fake_sulk",
            event="chat_usage_status",
        )
    percent_text = "未知" if percent is None else f"{float(percent):.0f}%"
    reset_text = f"，{reset} 后回血" if reset and reset != "现在" else ""
    line = f"Codex usage 还剩 {percent_text}{reset_text}。"
    if level in {"low", "critical"}:
        line += " 现在每个大活都要先过会计。"
    elif level == "watch":
        line += " 可以用，但不适合铺张。"
    elif level == "reset_soon":
        line += " 饭点快到了，先别让它写史诗。"
    else:
        line += " 暂时不用精打细算。"
    mood = "sulky" if level in {"low", "critical"} else "thinking"
    performance = "usage_low_sag" if level in {"low", "critical"} else "quiet_companion"
    return Reaction(True, line, mood, "thinking_tilt", "usage_speech", performance, event="chat_usage_status")


def _overview_reaction(context: dict[str, object]) -> Reaction:
    activity = _dict(context.get("activity"))
    codex = _dict(context.get("codex"))
    hardware = _dict(context.get("hardware"))
    usage = _dict(context.get("codex_usage"))
    claude = _dict(context.get("claude"))
    claude_usage = _dict(context.get("claude_usage"))
    claude_account = _dict(context.get("claude_account"))
    openai_billing = _dict(context.get("openai_billing"))
    parts = [
        f"活跃度 {activity.get('mode') or '未知'}",
        f"Codex {codex.get('status') or 'unknown'}",
        f"Claude {claude.get('active_count') or 0}/{claude.get('total_alive') or 0} active",
        f"硬件 {hardware.get('level') or 'unknown'}",
        f"Codex usage {usage.get('level') or 'unknown'}",
        f"Claude usage {claude_usage.get('level') or 'unknown'}",
        f"Claude 账号 {claude_account.get('level') or 'unknown'}",
        f"OpenAI billing {openai_billing.get('level') or 'unknown'}",
    ]
    return Reaction(
        True,
        " / ".join(parts) + "。夹夹汇报完了，表情保持无害。",
        "thinking",
        "scan",
        "speech",
        "suspicious_observe",
        event="chat_status_overview",
    )


def _is_mode_command(compact: str, zh: str, en: str) -> bool:
    if compact in {zh, en, f"{en}mode"}:
        return True
    if zh in compact or en in compact:
        return _has_any(compact, ("活跃度", "模式", "切到", "设为", "设置", "调到", "变成", "开启", "进入", "mode"))
    return False


def _looks_like_comfort(message: str) -> bool:
    compact = re.sub(r"\s+", "", message.lower())
    return _has_any(compact, ("累", "崩溃", "焦虑", "难过", "想哭", "不舒服", "睡不着", "撑不住", "panic", "anxious", "tired"))


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _clean_text(value: object, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().strip('"')
    text = re.sub(
        r"^(?:冷笑话|冷知识|一本正经(?:地)?胡说八道|胡说八道|小知识|碎碎念|想法|心理活动)\s*[:：]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _clean_action(value: object, fallback: str) -> str:
    action = re.sub(r"[\s-]+", "_", str(value or fallback).strip().lower())
    fallback_action = re.sub(r"[\s-]+", "_", str(fallback or "blink").strip().lower())
    if action in MODEL_ACTIONS:
        return action
    if fallback_action in MODEL_ACTIONS:
        return fallback_action
    return "blink"


def _clean_bubble(value: object, fallback: str) -> str:
    bubble = str(value or fallback).strip().lower()
    allowed = {
        "speech",
        "thought",
        "codex_speech",
        "codex_thought",
        "claude_speech",
        "claude_thought",
        "hardware_speech",
        "hardware_thought",
        "usage_speech",
        "usage_thought",
    }
    if bubble in allowed:
        return bubble
    return fallback if fallback in allowed else "speech"


def _clean_performance(value: object) -> str:
    performance = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
    return performance if performance in PERFORMANCE_PHRASES else ""


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _round_or_none(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def _usage_reset_label(data: dict[str, object]) -> str:
    return str(data.get("codex_usage_reset_in_label") or "")


def _claude_account_reset_label(data: dict[str, object]) -> str:
    return str(data.get("claude_account_reset_in_label") or "")
