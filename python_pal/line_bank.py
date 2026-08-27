from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import hashlib
import json
import random
import time
from typing import Any

from .soul import _load_yaml
from .state import Reaction


LINE_BANK_VERSION = 2
DECK_SIZE = 12
RECENT_LIMIT = 56
EVENT_RECENT_LIMIT = 18
LIBRARY_REFILL_AFTER_DAYS = 7
LIBRARY_MIN_ENTRIES = 240
DECK_REFRESH_AFTER_SECONDS = 5 * 60
DECK_REFRESH_AFTER_PICKS = 5
DECK_SIGNATURE_TAG_LIMIT = 6
EXPLICIT_SELECTION_TAGS = {"cheesy_love"}


@dataclass
class LineEntry:
    id: str
    event: str
    line: str
    mood: str = "smirk"
    action: str = "blink"
    bubble: str = "speech"
    performance: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "seed"
    created_at: float = field(default_factory=time.time)
    used_count: int = 0
    last_used_at: float = 0.0


class LineBank:
    def __init__(self, path: Path, language: str = "zh-CN") -> None:
        self.path = path
        self._language = language
        self.data = self._load()
        self._ensure_seeded()
        self._save()
        self._tag_index: dict[str, list[str]] = {}
        self._entry_index: dict[str, dict[str, object]] = {}
        self._rebuild_tag_index()

    def pick(
        self,
        event: str,
        recent_lines: list[str] | None = None,
        context_tags: list[str] | None = None,
    ) -> Reaction | None:
        recent_text = {line.strip() for line in (recent_lines or []) if line.strip()}
        event_key = _event_key(event)
        tags = _context_tag_set(context_tags)
        explicit_tags = tags.intersection(EXPLICIT_SELECTION_TAGS)
        if explicit_tags:
            entries = self._candidates(event_key)
            entries = [entry for entry in entries if entry["line"] not in recent_text]
            entries = self._without_recent_ids(event_key, entries)
            entries = self._prefer_tagged(entries, explicit_tags)
            entry = self._choose_entry(event_key, entries)
            if entry:
                self._mark_used(str(entry["id"]), event_key)
                self._save()
                return Reaction(
                    True,
                    str(entry["line"]),
                    str(entry.get("mood") or "smirk"),
                    str(entry.get("action") or "blink"),
                    str(entry.get("bubble") or "speech"),
                    str(entry.get("performance") or ""),
                )
        signature = _deck_signature(tags)
        self._refresh_deck_if_needed(event_key, tags, signature)
        deck = self.data["decks"].get(event_key, [])
        entries = [self._entry_by_id(entry_id) for entry_id in deck]
        entries = [entry for entry in entries if entry and entry["line"] not in recent_text]
        entries = self._without_recent_ids(event_key, entries)
        entries = self._prefer_tagged(entries, tags)
        if not entries:
            self._refresh_deck(event_key, tags, signature, force=True)
            deck = self.data["decks"].get(event_key, [])
            entries = [self._entry_by_id(entry_id) for entry_id in deck]
            entries = [entry for entry in entries if entry and entry["line"] not in recent_text]
            entries = self._without_recent_ids(event_key, entries)
            entries = self._prefer_tagged(entries, tags)
        entry = self._choose_entry(event_key, entries)
        if not entry:
            return None
        self._mark_used(str(entry["id"]), event_key)
        self._save()
        return Reaction(
            True,
            str(entry["line"]),
            str(entry.get("mood") or "smirk"),
            str(entry.get("action") or "blink"),
            str(entry.get("bubble") or "speech"),
            str(entry.get("performance") or ""),
        )

    def add_reaction(
        self,
        event: str,
        reaction: Reaction,
        source: str = "live_ollama",
        tags: list[str] | None = None,
    ) -> bool:
        if not reaction.line.strip():
            return False
        return self.add_entries(
            [
                {
                    "event": _event_key(event),
                    "line": reaction.line,
                    "mood": reaction.mood,
                    "action": reaction.action,
                    "bubble": reaction.bubble,
                    "performance": reaction.performance,
                    "tags": sorted(set([event, *(tags or [])])),
                    "source": source,
                }
            ]
        )

    def add_entries(self, entries: list[dict[str, object]], source: str | None = None) -> bool:
        existing_ids = {entry["id"] for entry in self.data["entries"]}
        existing_by_line = {str(entry["line"]).strip(): entry for entry in self.data["entries"]}
        existing_lines = set(existing_by_line)
        added = False
        for raw in entries:
            line = str(raw.get("line") or "").strip()
            if not line or line in existing_lines:
                if line and str(raw.get("source") or source or "") == "identity_seed":
                    entry = existing_by_line.get(line)
                    if entry is not None:
                        entry["tags"] = _tags(raw.get("tags"))
                        entry["mood"] = str(raw.get("mood") or entry.get("mood") or "smirk")
                        entry["action"] = str(raw.get("action") or entry.get("action") or "blink")
                        entry["bubble"] = _bubble(str(raw.get("bubble") or entry.get("bubble") or "speech"))
                        entry["performance"] = str(raw.get("performance") or entry.get("performance") or "")
                        entry["source"] = "identity_seed"
                        added = True
                continue
            event = _event_key(str(raw.get("event") or raw.get("category") or "manual"))
            entry = LineEntry(
                id=_line_id(event, line),
                event=event,
                line=line,
                mood=str(raw.get("mood") or "smirk"),
                action=str(raw.get("action") or "blink"),
                bubble=_bubble(str(raw.get("bubble") or "speech")),
                performance=str(raw.get("performance") or ""),
                tags=_tags(raw.get("tags")),
                source=str(source or raw.get("source") or "generated"),
            )
            if entry.id in existing_ids:
                continue
            self.data["entries"].append(asdict(entry))
            existing_ids.add(entry.id)
            existing_lines.add(line)
            added = True
        if added:
            self.data["library_updated_at"] = time.time()
            self.data["decks"] = {}
            self.data["deck_pick_counts"] = {}
            self.data["deck_signatures"] = {}
            self._save()
            self._rebuild_tag_index()
        return added

    def should_refill_library(self) -> bool:
        if len(self.data["entries"]) < LIBRARY_MIN_ENTRIES:
            return True
        updated_at = float(self.data.get("library_updated_at") or 0)
        return time.time() - updated_at > LIBRARY_REFILL_AFTER_DAYS * 24 * 60 * 60

    def stats(self) -> dict[str, object]:
        return {
            "entries": len(self.data["entries"]),
            "decks": {event: len(ids) for event, ids in self.data["decks"].items()},
            "deck_pick_counts": {
                event: int(count)
                for event, count in self.data.get("deck_pick_counts", {}).items()
            },
            "deck_signatures": dict(self.data.get("deck_signatures", {})),
            "event_recent": {
                event: len(ids)
                for event, ids in self.data.get("event_recent_ids", {}).items()
            },
            "recent": len(self.data["recent_ids"]),
            "path": str(self.path),
        }

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return _empty_bank()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return _empty_bank()
        if not isinstance(data, dict):
            return _empty_bank()
        data["version"] = LINE_BANK_VERSION
        data.setdefault("library_updated_at", 0)
        data.setdefault("deck_updated_at", {})
        data.setdefault("deck_pick_counts", {})
        data.setdefault("deck_signatures", {})
        data.setdefault("entries", [])
        data.setdefault("decks", {})
        data.setdefault("recent_ids", [])
        data.setdefault("event_recent_ids", {})
        return data

    def _ensure_seeded(self) -> None:
        self.add_entries(_seed_entries(self._language), source="seed")
        if not self.data.get("library_updated_at"):
            self.data["library_updated_at"] = time.time()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _rebuild_tag_index(self) -> None:
        """Build tag→entry_id index for fast tag-based lookups."""
        idx: dict[str, list[str]] = {}
        entry_idx: dict[str, dict[str, object]] = {}
        for entry in self.data["entries"]:
            eid = str(entry.get("id") or "")
            if eid:
                entry_idx[eid] = entry
            for tag in entry.get("tags", []):
                tag_str = str(tag).strip()
                if tag_str:
                    idx.setdefault(tag_str, []).append(eid)
        self._tag_index = idx
        self._entry_index = entry_idx

    def _entry_by_id(self, entry_id: str) -> dict[str, object] | None:
        return self._entry_index.get(entry_id)

    def _refresh_deck_if_needed(self, event: str, tags: set[str], signature: str) -> None:
        deck = self.data["decks"].get(event, [])
        updated_at = float(self.data["deck_updated_at"].get(event, 0))
        pick_count = int(self.data.get("deck_pick_counts", {}).get(event, 0))
        current_signature = str(self.data.get("deck_signatures", {}).get(event, ""))
        signature_changed = signature != current_signature
        if (
            len(deck) < max(4, DECK_SIZE // 2)
            or signature_changed
            or pick_count >= DECK_REFRESH_AFTER_PICKS
            or time.time() - updated_at > DECK_REFRESH_AFTER_SECONDS
        ):
            self._refresh_deck(event, tags, signature)

    def _refresh_deck(self, event: str, tags: set[str], signature: str, force: bool = False) -> None:
        candidates = self._candidates(event)
        if not candidates:
            return
        recent_ids = set(self.data["recent_ids"])
        recent_ids.update(self.data.get("event_recent_ids", {}).get(event, []))
        fresh = [entry for entry in candidates if entry["id"] not in recent_ids]
        pool = fresh if len(fresh) >= min(4, len(candidates)) else candidates
        sample_size = min(DECK_SIZE, len(pool))
        pool = sorted(
            pool,
            key=lambda entry: (
                -_tag_score(entry, tags),
                int(entry.get("used_count", 0)),
                float(entry.get("last_used_at", 0)),
            ),
        )
        shortlist = pool[: max(sample_size * 3, sample_size)]
        deck = random.sample(shortlist, sample_size) if len(shortlist) > sample_size else shortlist
        self.data["decks"][event] = [entry["id"] for entry in deck]
        self.data["deck_updated_at"][event] = time.time()
        self.data.setdefault("deck_pick_counts", {})[event] = 0
        self.data.setdefault("deck_signatures", {})[event] = signature
        if force:
            self.data["recent_ids"] = self.data["recent_ids"][-RECENT_LIMIT // 2 :]
            event_recent = self.data.setdefault("event_recent_ids", {}).get(event, [])
            self.data["event_recent_ids"][event] = event_recent[-EVENT_RECENT_LIMIT // 2 :]

    def _candidates(self, event: str) -> list[dict[str, object]]:
        events = {event}
        if event == "manual":
            events.update({"idle", "bored", "ambient"})
        if event == "idle":
            events.update({"manual", "ambient"})
        return [entry for entry in self.data["entries"] if str(entry.get("event")) in events]

    def _without_recent_ids(self, event: str, entries: list[dict[str, object]]) -> list[dict[str, object]]:
        recent_ids = set(self.data["recent_ids"])
        recent_ids.update(self.data.get("event_recent_ids", {}).get(event, []))
        return [entry for entry in entries if str(entry.get("id") or "") not in recent_ids]

    def _prefer_tagged(
        self,
        entries: list[dict[str, object]],
        tags: set[str],
    ) -> list[dict[str, object]]:
        if not tags:
            return entries
        tagged = [
            entry for entry in entries
            if _tag_score(entry, tags) > 0
        ]
        if tagged:
            return _best_tag_matches(tagged, tags)
        return entries

    def _choose_entry(self, event: str, entries: list[dict[str, object]]) -> dict[str, object] | None:
        if not entries:
            return None
        recent_ids = set(self.data["recent_ids"])
        recent_ids.update(self.data.get("event_recent_ids", {}).get(event, []))
        fresh = [entry for entry in entries if entry["id"] not in recent_ids]
        pool = fresh or entries
        weights = [1 / (1 + int(entry.get("used_count", 0))) for entry in pool]
        return random.choices(pool, weights=weights, k=1)[0]

    def _mark_used(self, entry_id: str, event: str) -> None:
        now = time.time()
        for entry in self.data["entries"]:
            if entry.get("id") == entry_id:
                entry["used_count"] = int(entry.get("used_count", 0)) + 1
                entry["last_used_at"] = now
                break
        recent = [item for item in self.data["recent_ids"] if item != entry_id]
        recent.append(entry_id)
        self.data["recent_ids"] = recent[-RECENT_LIMIT:]
        event_recent = [
            item
            for item in self.data.setdefault("event_recent_ids", {}).get(event, [])
            if item != entry_id
        ]
        event_recent.append(entry_id)
        self.data["event_recent_ids"][event] = event_recent[-EVENT_RECENT_LIMIT:]
        counts = self.data.setdefault("deck_pick_counts", {})
        counts[event] = int(counts.get(event, 0)) + 1


def _empty_bank() -> dict[str, object]:
    return {
        "version": LINE_BANK_VERSION,
        "library_updated_at": 0,
        "deck_updated_at": {},
        "deck_pick_counts": {},
        "deck_signatures": {},
        "entries": [],
        "decks": {},
        "recent_ids": [],
        "event_recent_ids": {},
    }


def _line_id(event: str, line: str) -> str:
    digest = hashlib.sha1(f"{event}\n{line}".encode("utf-8")).hexdigest()
    return digest[:16]


def _event_key(event: str) -> str:
    value = event.strip().lower().replace("-", "_")
    if value in {"poke", "bored", "idle", "manual", "ambient"}:
        return value
    if value.startswith("codex"):
        return "manual"
    return "manual"


def _bubble(value: str) -> str:
    return value if value in {"speech", "thought"} else "speech"


def _tags(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _normalize_tag(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _entry_tag_set(entry: dict[str, object]) -> set[str]:
    return {
        tag
        for tag in (_normalize_tag(item) for item in entry.get("tags", []))
        if tag
    }


def _context_tag_set(value: list[str] | None) -> set[str]:
    return {tag for tag in (_normalize_tag(item) for item in (value or [])) if tag}


def _deck_signature(tags: set[str]) -> str:
    if not tags:
        return ""
    return "|".join(sorted(tags)[:DECK_SIGNATURE_TAG_LIMIT])


def _tag_score(entry: dict[str, object], tags: set[str]) -> int:
    if not tags:
        return 0
    return len(tags & _entry_tag_set(entry))


def _best_tag_matches(entries: list[dict[str, object]], tags: set[str]) -> list[dict[str, object]]:
    if not entries:
        return entries
    scored = [
        (
            _tag_score(entry, tags),
            entry,
        )
        for entry in entries
    ]
    best = max(score for score, _entry in scored)
    return [entry for score, entry in scored if score == best]


def _seed_entries(language: str = "zh-CN") -> list[dict[str, object]]:
    """Load seed entries from locale-specific seeds YAML, falling back to hardcoded seeds."""
    prefix = "en" if language == "en" else "zh"
    yaml_path = Path(__file__).parent / "locales" / f"{prefix}_seeds.yaml"
    if yaml_path.exists():
        try:
            entries = _load_seeds_from_yaml(yaml_path)
            if entries:
                return entries
        except Exception:
            pass
    # Only fall back to hardcoded for zh
    if language != "en":
        return _hardcoded_seed_entries()
    return []


def _load_seeds_from_yaml(path: Path) -> list[dict[str, object]]:
    """Parse zh_seeds.yaml into the flat list format that add_entries expects."""
    data: dict[str, Any] = _load_yaml(path)
    seed: list[dict[str, object]] = []

    def _add(event: str, entry: dict[str, Any]) -> None:
        line = str(entry.get("line") or "").strip()
        if not line:
            return
        seed.append({
            "event": event,
            "line": line,
            "mood": str(entry.get("mood") or "smirk"),
            "action": str(entry.get("action") or "blink"),
            "bubble": str(entry.get("bubble") or "speech"),
            "tags": _tags(entry.get("tags")),
        })

    # manual, idle, poke — flat lists
    for event in ("manual", "idle", "poke"):
        section = data.get(event)
        if isinstance(section, list):
            for entry in section:
                if isinstance(entry, dict):
                    _add(event, entry)

    # bored — has sub-categories (cold_joke, cold_fact, deadpan_nonsense)
    bored_section = data.get("bored")
    if isinstance(bored_section, dict):
        for _sub_key, sub_list in bored_section.items():
            if isinstance(sub_list, list):
                for entry in sub_list:
                    if isinstance(entry, dict):
                        _add("bored", entry)
    elif isinstance(bored_section, list):
        for entry in bored_section:
            if isinstance(entry, dict):
                _add("bored", entry)

    # ambient — has sub-categories keyed by tag group
    ambient_section = data.get("ambient")
    if isinstance(ambient_section, dict):
        for _sub_key, sub_list in ambient_section.items():
            if isinstance(sub_list, list):
                for entry in sub_list:
                    if isinstance(entry, dict):
                        _add("ambient", entry)
    elif isinstance(ambient_section, list):
        for entry in ambient_section:
            if isinstance(entry, dict):
                _add("ambient", entry)

    # identity — has sub-categories keyed by identity id
    identity_section = data.get("identity")
    if isinstance(identity_section, dict):
        for _identity_id, id_list in identity_section.items():
            if isinstance(id_list, list):
                for entry in id_list:
                    if isinstance(entry, dict):
                        _add("ambient", entry)

    return seed


def _hardcoded_seed_entries() -> list[dict[str, object]]:
    """Original hardcoded seeds — fallback if YAML is missing."""
    seed: list[dict[str, object]] = []

    def add(event: str, line: str, mood: str, action: str, bubble: str = "speech", *tags: str) -> None:
        seed.append({"event": event, "line": line, "mood": mood, "action": action, "bubble": bubble, "tags": list(tags)})

    manual = [
        ("我在。虽然用途不明，但态度积极。", "smirk", "blink"),
        ("你继续，我会假装没发现。", "smirk", "smug_sway"),
        ("需要我假装很懂吗？", "innocent", "blink"),
        ("这不是批评，是办公用品的客观反光。", "smirk", "smug_sway"),
        ("我什么都没说。我只是弯成了这个形状。", "guilty", "blink"),
        ("我只是一个小文具，意见比较尖是结构问题。", "smirk", "nod"),
        ("你看起来很忙。主要是在忙着避免开始。", "suspicious", "thinking_tilt"),
        ("如果准备也算进度，你已经很有成就了。", "smug", "smug_sway"),
        ("我没有催。催促通常比我高一点。", "innocent", "blink"),
        ("空气安静了。很客观。", "smug", "smug_sway"),
    ]
    for line, mood, action in manual:
        add("manual", line, mood, action, "speech", "general")

    idle = [
        ("你停在这里有一小会儿了。文件也开始懂事地不打扰你。", "suspicious", "thinking_tilt", "thought"),
        ("这个窗口切得很有逃生路线。", "suspicious", "scan", "speech"),
        ("你是在工作，还是在给工作预热？", "suspicious", "thinking_tilt", "speech"),
        ("空白文档很有耐心。它可能是这里最成熟的。", "smirk", "sleepy_sag", "thought"),
        ("TODO 看起来很热闹。执行区比较冷清。", "smirk", "scan", "speech"),
        ("你这个准备阶段，已经准备得很成熟了。", "suspicious", "smug_sway", "speech"),
        ("你不是没开始，你是在和开始保持距离。", "smirk", "thinking_tilt", "thought"),
        ("参考资料已经够多了。它们开始互相参考了。", "smirk", "scan", "speech"),
        ("你切窗口很流畅。像一种回避体操。", "suspicious", "patrol", "speech"),
        ("我先不说话。这个停顿自己已经很有内容。", "innocent", "blink", "thought"),
        ("你看起来像在收集开始之前的空气。", "smirk", "thinking_tilt", "thought"),
        ("拖延被包装成信息收集后，确实更体面了。", "smug", "smug_sway", "speech"),
    ]
    for line, mood, action, bubble in idle:
        add("idle", line, mood, action, bubble, "procrastination")

    ambient = [
        ("你切窗口的速度很稳定。像在给开始找出口。", "suspicious", "scan", "thought", ("rapid_switching", "browser_research")),
        ("这个来回切换很熟练。工作可能已经晕车了。", "smirk", "patrol", "speech", ("rapid_switching",)),
        ("你盯着这里有一会儿了。它还没有自己变简单。", "suspicious", "thinking_tilt", "thought", ("idle_staring",)),
        ("空白区域很安静。安静到像在等你先道歉。", "smirk", "sleepy_sag", "thought", ("blank_document",)),
        ("TODO 出现了。它看起来希望别人先动手。", "smirk", "scan", "speech", ("todo_visible",)),
        ("Codex 在场。现在可以把假装镇定外包一点点。", "thinking", "nod", "thought", ("app_codex",)),
        ("编辑器很认真。你也可以象征性地加入一下。", "suspicious", "thinking_tilt", "speech", ("app_editor", "coding")),
        ("终端打开了。电脑即将用黑底白字表达态度。", "thinking", "scan", "thought", ("app_terminal", "terminal_work")),
        ("文件夹被打开太久，会开始产生整理的幻觉。", "smirk", "patrol", "thought", ("app_file_manager", "file_sorting")),
        ("资料看起来很多。决定权没有因此消失。", "suspicious", "smug_sway", "speech", ("browser_research", "browsing")),
        ("你专注挺久了。我先把嘴折起来一点。", "innocent", "blink", "thought", ("long_focus", "deep_work")),
        ("这个深度工作看起来是真的。夹夹暂时不夹。", "innocent", "nod", "thought", ("deep_work",)),
    ]
    for line, mood, action, bubble, tags in ambient:
        add("ambient", line, mood, action, bubble, *tags)

    bored = [
        ("文件夹失恋了，因为它被另存为。", "thinking", "twirl", "speech", "cold_joke"),
        ("鼠标很努力，但它的人生总在被拖动。", "thinking", "peek", "speech", "cold_joke"),
        ("回形针为什么不加班？因为它已经被夹住了。", "thinking", "wiggle", "speech", "cold_joke"),
        ("进度条不动时，人类会自动开始反思人生。", "thinking", "scan", "thought", "cold_fact"),
        ("保存按钮最大的作用，是让焦虑拥有一个图标。", "thinking", "nod", "thought", "cold_fact"),
        ("回形针最擅长的不是整理，是让纸假装有秩序。", "thinking", "blink", "thought", "cold_fact"),
        ("如果窗口切得够快，任务会误以为自己已经被处理。", "thinking", "twirl", "speech", "nonsense"),
        ("根据办公用品学，拖延会在周四下午获得轻微磁性。", "thinking", "thinking_tilt", "thought", "nonsense"),
        ("未完成事项会在桌面角落进行无性繁殖。很安静。", "thinking", "sleepy_sag", "thought", "nonsense"),
        ("剪贴板知道太多了，所以它一直保持沉默。", "thinking", "scan", "thought", "cold_fact"),
        ("桌面图标站得很整齐。像一群暂时没有被面对的问题。", "smirk", "patrol", "speech", "nonsense"),
        ("光标闪烁不是催促。只是它比较没有边界感。", "thinking", "blink", "thought", "cold_fact"),
    ]
    for line, mood, action, bubble, tag in bored:
        add("bored", line, mood, action, bubble, tag)

    poke = [
        ("哎，我这根纸夹也有触觉的。大概。", "startled", "startled_pop", "speech", "poke"),
        ("你戳我，是因为任务戳不动吗？", "smirk", "wiggle", "speech", "poke"),
        ("好的，我醒了。并没有更有用。", "sleepy", "sleepy_sag", "speech", "poke"),
        ("再戳我我就开始提供意见了。我很小声。", "smirk", "wiggle", "speech", "poke"),
        ("我只是弯了一下，不代表我同意被当按钮。", "guilty", "blink", "speech", "poke"),
        ("收到。一次桌面层面的轻微暴力。", "startled", "shake", "speech", "poke"),
        ("你戳得很准。逃避得也很准。", "smug", "smug_sway", "speech", "poke"),
        ("我没有痛觉，但我有很多意见。", "smirk", "nod", "speech", "poke"),
    ]
    for line, mood, action, bubble, tag in poke:
        add("poke", line, mood, action, bubble, tag)
    return seed
