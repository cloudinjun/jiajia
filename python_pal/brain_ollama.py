from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import random
import re
import urllib.error
import urllib.request

from .actions import ACTION_PROMPT, ACTION_SCHEMA_VALUE, MODEL_ACTIONS
from .line_bank import LineBank
from .soul import Soul
from .state import Reaction


class OllamaBrain:
    def __init__(self, soul: Soul, project_root: Path | None = None, endpoint: str = "http://127.0.0.1:11434") -> None:
        self.soul = soul
        self.endpoint = endpoint.rstrip("/")
        root = project_root or Path(__file__).resolve().parent.parent
        self.line_bank = LineBank(root / "memory" / "line_bank.json")

    def react(self, event: str, context: dict[str, object] | None = None) -> Reaction:
        context = context or {}
        cached = self.line_bank.pick(event, _recent_lines(context), _context_tags(context))
        if cached:
            return cached
        fallback = self.fallback_reaction(event)
        prompt = self._prompt(event, context)
        payload = {
            "model": self.soul.text_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": 0.84,
                "num_predict": 150,
            },
        }
        try:
            response = self._post_json("/api/chat", payload, timeout=18)
            content = response.get("message", {}).get("content", "")
            reaction = self._parse_reaction(str(content), fallback)
            reaction.line = self._clean_line(reaction.line or fallback.line)
            self.line_bank.add_reaction(event, reaction, source="live_ollama", tags=_context_tags(context))
            return reaction
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return fallback

    def maintain_line_bank(self, target_count: int = 36) -> dict[str, object]:
        if not self.line_bank.should_refill_library():
            return {"status": "fresh", **self.line_bank.stats()}
        entries = self._generate_line_entries(target_count)
        added = self.line_bank.add_entries(entries, source="ollama_batch")
        return {"status": "updated" if added else "unchanged", "generated": len(entries), **self.line_bank.stats()}

    def _generate_line_entries(self, target_count: int) -> list[dict[str, object]]:
        payload = {
            "model": self.soul.text_model,
            "messages": [
                {"role": "system", "content": self._line_library_system_prompt()},
                {"role": "user", "content": self._line_library_user_prompt(target_count)},
            ],
            "stream": False,
            "options": {
                "temperature": 0.92,
                "num_predict": 1400,
            },
        }
        response = self._post_json("/api/chat", payload, timeout=45)
        content = str(response.get("message", {}).get("content", ""))
        return self._parse_line_entries(content)

    def fallback_reaction(self, event: str) -> Reaction:
        if event == "poke" and self.soul.poke_responses:
            line = random.choice(self.soul.poke_responses)
            return Reaction(True, line, "smirk", "wiggle", "speech")
        if event == "bored":
            return self._fallback_boredom()
        if event == "idle" and random.random() < 0.55:
            if random.random() < 0.45:
                return self._fallback_boredom()
            lines = [
                "他又在和开始工作保持一种礼貌距离。",
                "这个窗口切换频率，很像认真努力的替身文学。",
                "嗯，拖延被包装成了信息收集。",
                "先观察，不打扰。他好像正在加载借口。",
            ]
            return Reaction(True, random.choice(lines), "thinking", "blink", "thought")
        candidates = self.soul.catchphrases or ["我在。虽然作用不明，但态度积极。"]
        return Reaction(True, random.choice(candidates), "smirk", "bob", "speech")

    def _fallback_boredom(self) -> Reaction:
        kind, lines = random.choice(
            [
                (
                    "cold_joke",
                    [
                        "回形针为什么不加班？因为它已经被夹住了。",
                        "文件夹失恋了，因为它被另存为。",
                        "鼠标很努力，但它的人生总在被拖动。",
                    ],
                ),
                (
                    "cold_fact",
                    [
                        "回形针最擅长的不是整理，是让纸假装有秩序。",
                        "进度条不动时，人类会自动开始反思人生。",
                        "保存按钮最大的作用，是让焦虑拥有一个图标。",
                    ],
                ),
                (
                    "deadpan_nonsense",
                    [
                        "根据办公用品学，拖延会在周四下午获得轻微磁性。",
                        "严肃地说，未完成事项会在桌面角落进行无性繁殖。",
                        "如果窗口切得够快，任务会误以为自己已经被处理。",
                    ],
                ),
            ]
        )
        action = random.choice(["blink", "peek", "scan", "thinking_tilt", "smug_sway", "sleepy_sag", "twirl"])
        bubble = "thought" if kind != "cold_joke" and random.random() < 0.65 else "speech"
        return Reaction(True, random.choice(lines), "thinking", action, bubble)

    def _system_prompt(self) -> str:
        style = "\n".join(f"- {item}" for item in self.soul.style)
        rules = "\n".join(f"- {item}" for item in self.soul.rules)
        catchphrases = "\n".join(f"- {item}" for item in self.soul.catchphrases)
        roast_pattern = "\n".join(f"- {item}" for item in self.soul.roast_pattern)
        innocent_closers = " / ".join(self.soul.innocent_closers)
        runtime_brief = self.soul.runtime_brief()
        runtime_section = f"角色运行边界:\n{runtime_brief}\n" if runtime_brief else ""
        return (
            f"你是一个 Windows 桌宠，名字是 {self.soul.name}。\n"
            f"性格: {self.soul.vibe}\n"
            f"人设核心: {self.soul.persona_core}\n"
            f"{runtime_section}"
            f"说话风格:\n{style}\n"
            f"吐槽模式:\n{roast_pattern}\n"
            f"无辜收尾可参考: {innocent_closers}\n"
            f"规矩:\n{rules}\n"
            f"可参考口头禅，不要机械照抄:\n{catchphrases}\n"
            "输出分两种气泡:\n"
            "- speech: 说出口。直接对用户说，乖巧、无害、短句，最后可以装无辜。\n"
            "- thought: 心里想。不是说出口，更像脑内旁白；更小声、更克制、更观察型，可以更尖一点，但不要攻击人。\n"
            "无聊内容有三种:\n"
            "- cold_joke: 冷笑话。短、干、很冷，像办公用品突然学会讲段子。\n"
            "- cold_fact: 冷知识。可以是真的小知识，也可以是关于桌面/文件/进度条的观察，但不要编造成真实历史或科学事实。\n"
            "- deadpan_nonsense: 一本正经胡说八道。明显荒诞，必须让人看出是玩笑，不要伪装成事实。\n"
            "这些分类只用于内部选择，line 不要用“冷笑话：”“冷知识：”“一本正经胡说八道：”等标签开头。\n"
            "动作可以表达情绪或状态，从下面选择一个最贴切的 action:\n"
            f"{ACTION_PROMPT}\n"
            "thought 不要写“我在想”“心里想”，气泡样式会表达这一点。\n"
            "只输出 JSON，不要 Markdown，不要解释。"
        )

    def _prompt(self, event: str, context: dict[str, object]) -> str:
        schema = {
            "should_say": True,
            "line": "一句短短的中文碎碎念",
            "bubble": "speech|thought",
            "mood": "idle|smirk|happy|thinking|sleepy|startled|proud|shy|sulky|focused|bored|done",
            "action": ACTION_SCHEMA_VALUE,
        }
        bubble_hint = (
            "poke/manual 事件优先 speech；idle 事件可以 speech 或 thought；"
            "ambient 事件优先 thought，只做高层行为观察，不复述屏幕文字；"
            "bored 事件要从 cold_joke、cold_fact、deadpan_nonsense 中选一种。"
        )
        boredom_hint = (
            "如果事件是 idle 且用户空闲时间较长，或事件是 bored，"
            "优先生成冷笑话、冷知识或一本正经胡说八道。"
            "内容要短，最多一两句，不要解释梗。"
            "不要在 line 开头写内容分类标签。"
        )
        return (
            f"事件: {event}\n"
            f"上下文 JSON: {json.dumps(context, ensure_ascii=False)}\n"
            f"最近说过的话不要重复。尽量控制在 {self.soul.max_line_chars} 个中文字符左右；如果一句话自然变长，会由气泡自动拆成连续窗口。\n"
            f"{bubble_hint}\n"
            f"{boredom_hint}\n"
            f"请按这个 JSON schema 输出: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _line_library_system_prompt(self) -> str:
        runtime_brief = self.soul.runtime_brief()
        return (
            f"你在为桌宠 {self.soul.name} 生成一批可长期复用的短句百科全书。\n"
            f"角色核心: {self.soul.persona_core}\n"
            f"运行边界:\n{runtime_brief}\n"
            "只生成可单独表演的一句话，不要依赖具体隐私内容，不要复述屏幕文字。\n"
            "保持夹夹味：乖巧、无害、轻微毒舌，只戳拖延/分心/假装准备等行为。\n"
            "不要使用“冷笑话：”“冷知识：”等分类前缀。\n"
            "只输出 JSON 数组，不要 Markdown，不要解释。"
        )

    def _line_library_user_prompt(self, target_count: int) -> str:
        schema = {
            "event": "manual|idle|bored|poke|ambient",
            "line": "一句短中文",
            "bubble": "speech|thought",
            "mood": "smirk|thinking|innocent|suspicious|guilty|sleepy|startled",
            "action": ACTION_SCHEMA_VALUE,
            "tags": ["procrastination"],
        }
        return (
            f"生成 {target_count} 条候选短句，覆盖 manual、idle、bored、poke、ambient 五类。\n"
            "manual: 用户主动点 Say something 时可说的泛用句。\n"
            "idle: 用户空闲、卡住、反复切窗口时的观察。\n"
            "bored: 冷笑话、冷知识、一本正经胡说八道，但不要写分类标题。\n"
            "poke: 用户戳桌宠时的反应。\n"
            "ambient: 根据环境标签做高层观察，比如 rapid_switching、blank_document、todo_visible、app_codex、app_editor、app_terminal、browser_research、deep_work。\n"
            "每条最多 42 个中文字符左右，避免重复句式。\n"
            f"每项按这个 schema 输出: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _parse_line_entries(self, content: str) -> list[dict[str, object]]:
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        match = re.search(r"\[.*\]", content, flags=re.DOTALL)
        if not match:
            return []
        try:
            raw_entries = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(raw_entries, list):
            return []
        entries: list[dict[str, object]] = []
        for raw in raw_entries:
            if not isinstance(raw, dict):
                continue
            line = self._clean_line(str(raw.get("line") or ""))
            if not line:
                continue
            entries.append(
                {
                    "event": self._clean_event(raw.get("event")),
                    "line": line,
                    "bubble": self._clean_bubble(raw.get("bubble"), "speech"),
                    "mood": str(raw.get("mood") or "smirk"),
                    "action": self._clean_action(raw.get("action"), "blink"),
                    "tags": raw.get("tags") if isinstance(raw.get("tags"), list) else [],
                }
            )
        return entries

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
            action=self._clean_action(data.get("action"), fallback.action),
            bubble=self._clean_bubble(data.get("bubble"), fallback.bubble),
        )

    def _clean_action(self, action: object, fallback: str) -> str:
        value = re.sub(r"[\s-]+", "_", str(action or fallback).strip().lower())
        fallback_value = re.sub(r"[\s-]+", "_", str(fallback or "idle").strip().lower())
        if value in MODEL_ACTIONS:
            return value
        if fallback_value in MODEL_ACTIONS:
            return fallback_value
        return "idle"

    def _clean_event(self, event: object) -> str:
        value = re.sub(r"[\s-]+", "_", str(event or "manual").strip().lower())
        return value if value in {"manual", "idle", "bored", "poke", "ambient"} else "manual"

    def _clean_bubble(self, bubble: object, fallback: str) -> str:
        value = str(bubble or fallback).strip().lower()
        if value in {"speech", "thought"}:
            return value
        return fallback if fallback in {"speech", "thought"} else "speech"

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"\s+", " ", line).strip().strip('"')
        line = re.sub(
            r"^(?:冷笑话|冷知识|一本正经(?:地)?胡说八道|胡说八道|小知识|碎碎念|想法|心理活动|cold_joke|cold_fact|deadpan_nonsense)\s*[:：]\s*",
            "",
            line,
            flags=re.IGNORECASE,
        )
        max_chars = max(self.soul.max_line_chars * 4, 160)
        if len(line) <= max_chars:
            return line
        return line[: max_chars - 1].rstrip() + "..."

    def debug_snapshot(self) -> dict[str, object]:
        return {"endpoint": self.endpoint, "soul": asdict(self.soul), "line_bank": self.line_bank.stats()}


def _recent_lines(context: dict[str, object]) -> list[str]:
    value = context.get("recent_lines")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _context_tags(context: dict[str, object]) -> list[str]:
    tags: list[str] = []
    for key in ("environment_tags", "behavior_tags", "screen_tags"):
        value = context.get(key)
        if isinstance(value, list):
            tags.extend(str(item).strip() for item in value if str(item).strip())
    return sorted(set(tags))
