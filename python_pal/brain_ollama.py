from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import random
import re
import urllib.error
import urllib.request

from .actions import ACTION_PROMPT, ACTION_SCHEMA_VALUE, MODEL_ACTIONS
from .identity import DEFAULT_IDENTITY, IdentityPack, load_identity_manifest
from .line_bank import LineBank
from .performance import PERFORMANCE_PHRASES, PERFORMANCE_PROMPT, PERFORMANCE_SCHEMA_VALUE
from .soul import Soul
from .state import Reaction


class OllamaBrain:
    def __init__(self, soul: Soul, project_root: Path | None = None, endpoint: str = "http://127.0.0.1:11434") -> None:
        self.soul = soul
        self.endpoint = endpoint.rstrip("/")
        root = project_root or Path(__file__).resolve().parent.parent
        self.identities = load_identity_manifest(root / "python_pal" / "identities.yaml")
        line_bank_name = "line_bank.en.json" if soul.language == "en" else "line_bank.json"
        self.line_bank = LineBank(root / "memory" / line_bank_name, language=soul.language)
        if soul.language != "en":
            self.line_bank.add_entries(self.identities.seed_entries(), source="identity_seed")

    def react(self, event: str, context: dict[str, object] | None = None, allow_live: bool = True) -> Reaction:
        context = dict(context or {})
        identity = self.identities.select(event, context)
        identity_level = self.identities.level_for(event, context, identity)
        context.setdefault("identity_id", identity.id)
        context.setdefault("identity_display_name", identity.display_name)
        context.setdefault("identity_level", identity_level)
        context.setdefault("identity_brief", identity.prompt_brief())
        cached = self.line_bank.pick(event, _recent_lines(context), _context_tags(context))
        if cached:
            cached.decision_reason = f"identity={identity.id}"
            return cached
        fallback = self.fallback_reaction(event, context)
        if not allow_live:
            fallback.decision_reason = f"identity={identity.id};live_model=disabled"
            return fallback
        prompt = self._prompt(event, context)
        payload = {
            "model": self.soul.text_model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "keep_alive": "2m",
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
            reaction.decision_reason = f"identity={identity.id}"
            self.line_bank.add_reaction(event, reaction, source="live_ollama", tags=_context_tags(context))
            return reaction
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return fallback

    def maintain_line_bank(self, target_count: int = 18) -> dict[str, object]:
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
            "format": "json",
            "think": False,
            "keep_alive": "30s",
            "options": {
                "temperature": 0.92,
                "num_predict": 900,
            },
        }
        response = self._post_json("/api/chat", payload, timeout=45)
        content = str(response.get("message", {}).get("content", ""))
        return self._parse_line_entries(content)

    def fallback_reaction(self, event: str, context: dict[str, object] | None = None) -> Reaction:
        context = context or {}
        identity = self.identities.select(event, context)
        identity_level = self.identities.level_for(event, context, identity)
        identity_reaction = self._identity_fallback(event, identity, identity_level)
        if identity_reaction:
            return identity_reaction
        if event == "poke" and self.soul.poke_responses:
            line = random.choice(self.soul.poke_responses)
            return Reaction(True, line, "smirk", "wiggle", "speech")
        if event == "bored":
            return self._fallback_boredom(context)
        if event == "idle" and random.random() < 0.55:
            if random.random() < 0.45:
                return self._fallback_boredom(context)
            lines = [
                "他又在和开始工作保持一种礼貌距离。",
                "这个窗口切换频率，很像认真努力的替身文学。",
                "嗯，拖延被包装成了信息收集。",
                "先观察，不打扰。他好像正在加载借口。",
            ]
            return Reaction(True, random.choice(lines), "thinking", "blink", "thought")
        candidates = self.soul.catchphrases or ["我在。虽然作用不明，但态度积极。"]
        return Reaction(True, random.choice(candidates), "smirk", "bob", "speech")

    def _identity_fallback(self, event: str, identity: IdentityPack, level: str) -> Reaction | None:
        if identity.id == DEFAULT_IDENTITY:
            return None
        line = identity.pick_line(level)
        if not line:
            return None
        if self.soul.language == "en" and not line.isascii():
            return None
        bubble = "thought" if event in {"ambient", "idle"} else "speech"
        return Reaction(
            True,
            line,
            identity.default_mood,
            identity.fallback_action,
            bubble,
            identity.preferred_performance,
            decision_reason=f"identity={identity.id}",
        )

    def _fallback_boredom(self, context: dict[str, object] | None = None) -> Reaction:
        if "cheesy_love" in _context_tags(context or {}):
            return self._fallback_cheesy_love()
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

    def _fallback_cheesy_love(self) -> Reaction:
        if self.soul.language == "en":
            lines = [
                "Are you a deadline? Because I panic when you get close.",
                "You must be AutoSave, because I trust you more than myself.",
                "If you were a file, I'd still fail to name you properly.",
                "Are you Wi-Fi? Because my composure drops when you're near.",
            ]
        else:
            lines = [
                "你知道我为什么是回形针吗？因为我一见你就想把心事夹住。",
                "你是不是快捷键？不然我怎么一看见你就想保存当前心情。",
                "我本来是文具，遇见你以后有点文艺复兴。",
                "你像撤销键。不是后悔，是我想再来一次。",
                "我不是弯了，我只是朝你的方向比较有结构。",
                "如果喜欢也能另存为，我想保存到桌面。很土，我先抖一下。",
                "你的存在让我的金属结构出现了非必要柔软。",
                "你不是文件夹，但我想把今天都归到你这里。",
                "我没有心跳，只有刷新率。现在有点超频。",
                "你像自动保存。平时不响，但我知道你很重要。",
            ]
        return Reaction(
            True,
            random.choice(lines),
            "shy",
            "shake",
            "speech",
            "cheesy_love_cringe",
            decision_reason="bored_kind=cheesy_love",
        )

    def _system_prompt(self) -> str:
        style = "\n".join(f"- {item}" for item in self.soul.style)
        rules = "\n".join(f"- {item}" for item in self.soul.rules)
        catchphrases = "\n".join(f"- {item}" for item in self.soul.catchphrases)
        roast_pattern = "\n".join(f"- {item}" for item in self.soul.roast_pattern)
        innocent_closers = " / ".join(self.soul.innocent_closers)
        runtime_brief = self.soul.runtime_brief()
        runtime_section = f"角色运行边界:\n{runtime_brief}\n" if runtime_brief else ""
        wit_block = self._wit_coaching_block()
        bubble_block = self._bubble_description_block()
        bored_block = self._bored_description_block()
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
            f"{wit_block}"
            f"{bubble_block}"
            f"{bored_block}"
            "这些分类只用于内部选择，line 不要用分类标签开头。\n"
            "动作可以表达情绪或状态，从下面选择一个最贴切的 action:\n"
            f"{ACTION_PROMPT}\n"
            "performance 是可选表演短语，用来安排先做一个小动作、再冒泡、再收尾装无辜。"
            "优先从下面列表里选；不确定就留空:\n"
            f"{PERFORMANCE_PROMPT}\n"
            'thought 不要写“我在想”“心里想”，气泡样式会表达这一点。\n'
            "只输出 JSON，不要 Markdown，不要解释。"
        )

    def _wit_coaching_block(self) -> str:
        if self.soul.language.startswith("zh"):
            return (
                "核心技法（轮换使用，每次只用一种）:\n"
                "好句示范:\n"
                "- 语义翻转: '你在进步。方向待定。'\n"
                "- 反话正说: '你的准备工作已经可以独立上市了。'\n"
                "- 可生还式轻描淡写: '这个进度仍具备生还可能。'\n"
                "- 错位同情: '我替那个deadline心疼。它等了好久。'\n"
                "- 温柔一刀: '休息一下吧，反正你也没在做。'\n"
                "- 存在性荒诞: '桌面上只有我是清醒的。压力很大。'\n"
                "- 虚晃一枪: '我想鼓励你。但我找不到依据。'\n"
                "禁止的写法:\n"
                "- 不要用比喻解释笑话\n"
                "- 不要前句观察后句翻译\n"
                "- 不要用万能收尾\n"
                "- 说完就停。不加解释。听者需要一拍才反应过来，那一拍就是笑点。\n"
            )
        return (
            "Core techniques (rotate, use ONE per line):\n"
            "Good examples:\n"
            "- REFRAMING: 'Not judging. Judging requires standards I haven't set.'\n"
            "- UNDERSTATEMENT: 'You've been... present.'\n"
            "- SURVIVABLE UNDERSTATEMENT: 'This remains technically survivable.'\n"
            "- FALSE SYMPATHY: 'I feel for that deadline. It tried.'\n"
            "- SUPPORTIVE DEVASTATION: 'Making progress. Backwards counts.'\n"
            "- EXISTENTIAL ABSURDISM: 'A wire with thoughts on your productivity.'\n"
            "- MISDIRECT: 'I'd help, but I'm load-bearing. Emotionally.'\n"
            "NEVER do this:\n"
            "- No similes explaining the joke\n"
            "- No second sentence restating the first\n"
            "- No crutch closers like 'I just noticed' or 'objectively'\n"
            "- Stop after the line lands. The beat before they get it IS the comedy.\n"
        )

    def _bubble_description_block(self) -> str:
        if self.soul.language.startswith("zh"):
            return (
                "输出分两种气泡:\n"
                "- speech: 说出口，短句，说完就走。\n"
                "- thought: 脑内旁白，更克制，可以更尖。\n"
            )
        return (
            "Two bubble types:\n"
            "- speech: said out loud, short, stop after it lands.\n"
            "- thought: inner monologue, more restrained, can be sharper.\n"
        )

    def _bored_description_block(self) -> str:
        if self.soul.language.startswith("zh"):
            return (
                "无聊内容有四种:\n"
                "- cold_joke: 冷笑话。短、干、很冷。\n"
                "- cold_fact: 冷知识。桌面/文件/进度条的观察，不编造历史。\n"
                "- deadpan_nonsense: 一本正经胡说八道。明显荒诞。\n"
                "- cheesy_love: 土味情话。乖巧、故意恶搞、土到夹夹自己想打颤；不真暧昧，不油腻，不冒犯。\n"
            )
        return (
            "Bored content has four types:\n"
            "- cold_joke: Short, dry, cold.\n"
            "- cold_fact: Observations about desktops/files/progress bars.\n"
            "- deadpan_nonsense: Delivered straight-faced, obviously absurd.\n"
            "- cheesy_love: Intentionally corny pseudo-romantic line; cute, self-cringing, not genuinely intimate or creepy.\n"
        )

    def _prompt(self, event: str, context: dict[str, object]) -> str:
        is_zh = self.soul.language.startswith("zh")
        line_desc = "一句短中文" if is_zh else "one short English line"
        schema = {
            "should_say": True,
            "line": line_desc,
            "bubble": "speech|thought",
            "mood": "idle|smirk|smug|happy|thinking|sleepy|startled|proud|shy|sulky|focused|bored|done|innocent|suspicious|guilty",
            "action": ACTION_SCHEMA_VALUE,
            "performance": PERFORMANCE_SCHEMA_VALUE,
        }
        if is_zh:
            technique_hint = (
                "用七种技法之一写: 语义翻转/反话正说/可生还式轻描淡写/错位同情/温柔一刀/存在性荒诞/虚晃一枪。"
                "说完就停，不解释。不要用比喻解释笑话。"
            )
            bubble_hint = (
                "poke/manual 优先 speech；idle 可以 speech 或 thought；"
                "ambient 优先 thought，只做高层观察，不复述屏幕文字；"
                "bored 从 cold_joke、cold_fact、deadpan_nonsense、cheesy_love 选一种；"
                "如果上下文有 cheesy_love 标签，必须写土味情话，mood 用 shy，performance 用 cheesy_love_cringe。"
            )
            length_hint = f"最近说过的话不要重复。控制在 {self.soul.max_line_chars} 字左右。"
        else:
            technique_hint = (
                "Use one technique: REFRAMING/UNDERSTATEMENT/FALSE SYMPATHY/"
                "SURVIVABLE UNDERSTATEMENT/SUPPORTIVE DEVASTATION/EXISTENTIAL ABSURDISM/MISDIRECT. "
                "Stop after the line lands. No similes explaining the joke."
            )
            bubble_hint = (
                "poke/manual: prefer speech. idle: speech or thought. "
                "ambient: prefer thought, high-level observation only. "
                "bored: pick cold_joke, cold_fact, deadpan_nonsense, or cheesy_love. "
                "If context has the cheesy_love tag, write a corny love line with mood=shy and performance=cheesy_love_cringe."
            )
            length_hint = f"Don't repeat recent lines. Max ~{self.soul.max_line_chars} chars."
        return (
            f"事件: {event}\n"
            f"上下文 JSON: {json.dumps(context, ensure_ascii=False)}\n"
            f"{length_hint}\n"
            f"{technique_hint}\n"
            f"{bubble_hint}\n"
            f"JSON schema: {json.dumps(schema, ensure_ascii=False)}"
        )

    def _line_library_system_prompt(self) -> str:
        runtime_brief = self.soul.runtime_brief()
        wit_block = self._wit_coaching_block()
        if self.soul.language.startswith("zh"):
            return (
                f"你在为桌宠 {self.soul.name} 生成一批可长期复用的短句。\n"
                f"角色核心: {self.soul.persona_core}\n"
                f"运行边界:\n{runtime_brief}\n"
                f"{wit_block}"
                "每句必须用上面七种技法之一。说完就停，不解释。\n"
                "只生成可单独表演的一句话，不要依赖隐私内容，不要复述屏幕文字。\n"
                "不要使用分类前缀。只输出 JSON 数组。"
            )
        return (
            f"You are generating reusable one-liners for {self.soul.name}.\n"
            f"Core persona: {self.soul.persona_core}\n"
            f"Boundaries:\n{runtime_brief}\n"
            f"{wit_block}"
            "Each line MUST use one of the seven techniques above. Stop after it lands.\n"
            "Only standalone lines, no private content, no screen text.\n"
            "No category prefixes. Output JSON array only."
        )

    def _line_library_user_prompt(self, target_count: int) -> str:
        max_chars = self.soul.max_line_chars
        is_zh = self.soul.language.startswith("zh")
        line_desc = "一句短中文" if is_zh else "one short English line"
        schema = {
            "event": "manual|idle|bored|poke|ambient",
            "line": line_desc,
            "bubble": "speech|thought",
            "mood": "smirk|smug|thinking|innocent|suspicious|guilty|sleepy|startled|happy|proud",
            "action": ACTION_SCHEMA_VALUE,
            "performance": PERFORMANCE_SCHEMA_VALUE,
            "tags": ["procrastination"],
        }
        if is_zh:
            return (
                f"生成 {target_count} 条候选短句，覆盖 manual、idle、bored、poke、ambient 五类。\n"
                "manual: 泛用句。idle: 拖延/发呆观察。bored: 冷笑话/冷知识/一本正经胡说八道/土味情话。poke: 被戳反应。ambient: 环境高层观察。\n"
                "bored 可加入 cheesy_love 标签，句子要乖巧故意土、让夹夹自己尴尬到打颤；mood 用 shy，performance 用 cheesy_love_cringe。\n"
                "每句用七种技法之一（语义翻转/反话正说/可生还式轻描淡写/错位同情/温柔一刀/存在性荒诞/虚晃一枪），轮换使用。\n"
                "好句: '你在进步。方向待定。' '没关系，deadline也在等。' '我想鼓励你。但找不到依据。'\n"
                "坏句(禁止): '你像在做回避体操' '你停了一会儿。文件也开始懂事了。'\n"
                f"每条最多 {max_chars} 个中文字符，避免重复句式。\n"
                f"每项按这个 schema 输出: {json.dumps(schema, ensure_ascii=False)}"
            )
        return (
            f"Generate {target_count} candidate lines across manual, idle, bored, poke, ambient.\n"
            "manual: general. idle: procrastination observations. bored: cold jokes/facts/deadpan/corny love lines. poke: poke reactions. ambient: environment observations.\n"
            "For cheesy_love bored entries, use tag cheesy_love, mood shy, performance cheesy_love_cringe.\n"
            "Each line must use one technique: REFRAMING / UNDERSTATEMENT / SURVIVABLE UNDERSTATEMENT / FALSE SYMPATHY / SUPPORTIVE DEVASTATION / EXISTENTIAL ABSURDISM / MISDIRECT. Rotate.\n"
            "Good: 'Making progress. Backwards counts.' 'I'd help, but I'm load-bearing. Emotionally.'\n"
            "Bad (NEVER): 'Like avoidance gymnastics' 'You stopped. The file started being considerate.'\n"
            f"Max {max_chars} chars per line, avoid repeating structures.\n"
            f"Schema per item: {json.dumps(schema, ensure_ascii=False)}"
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
                    "performance": self._clean_performance(raw.get("performance")),
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
            performance=self._clean_performance(data.get("performance")),
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

    def _clean_performance(self, performance: object) -> str:
        value = re.sub(r"[\s-]+", "_", str(performance or "").strip().lower())
        return value if value in PERFORMANCE_PHRASES else ""

    def _clean_line(self, line: str) -> str:
        line = re.sub(r"\s+", " ", line).strip().strip('"')
        line = re.sub(
            r"^(?:冷笑话|冷知识|土味情话|一本正经(?:地)?胡说八道|胡说八道|小知识|碎碎念|想法|心理活动|cold_joke|cold_fact|deadpan_nonsense|cheesy_love)\s*[:：]\s*",
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
    identity_id = str(context.get("identity_id") or "").strip()
    if identity_id:
        tags.append(identity_id)
    identity_level = str(context.get("identity_level") or "").strip()
    if identity_level:
        tags.append(identity_level)
    return sorted(set(tags))

