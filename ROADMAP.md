# Paperclip Pal Roadmap

## Current state snapshot

| Metric | Value |
|---|---|
| Total Python LOC | ~10,700 (body.py alone = 4,747) |
| Line bank entries | 80 (51 seed + 29 identity_seed, 0 from live Ollama) |
| Identity packs | 11 |
| Files with hardcoded Chinese | 19 .py files (~645 lines) + 2 YAML (~175 lines) |
| Distinct events covered | manual(25), ambient(23), idle(12), bored(12), poke(8) |
| Animation actions | 28 visible + micro actions |
| Performance phrases | 6 primary choreographies |

---

## Phase 0 — i18n infrastructure

**Goal**: Make language switchable without touching content files.

### 0.1 Create `python_pal/i18n.py`
- Define `Locale` enum: `ZH`, `EN`
- Load locale from `settings.json` (default `zh`)
- `t(key, **kwargs) -> str` function that reads from locale YAML
- Fallback: if key missing in current locale, use zh

### 0.2 Create locale YAML files
- `python_pal/locales/zh.yaml` — extract all UI strings: menu labels, status text, reaction templates, chat prompts, frequency preset names ("安静"→"安静", "正常"→"正常")
- `python_pal/locales/en.yaml` — English equivalents
- Scope: only UI chrome and reaction templates. **Line bank content and identity lines stay in their own files** (they're creative content, not UI strings)

### 0.3 Migrate hardcoded strings
Files to touch (by priority):
1. **body.py** (292 lines) — menu labels, status popups, chat wait feedback, badge labels, reaction functions for codex/claude/hardware/usage
2. **chat.py** (100 lines) — command detection keywords, status response templates, system prompt
3. **brain_ollama.py** (65 lines) — system prompt, fallback lines
4. **line_bank.py** (54 lines) — seed entries → move to `locales/zh_seeds.yaml` + `locales/en_seeds.yaml`
5. **actions.py** (23 lines) — ACTION_DESCRIPTIONS
6. **claude_usage.py**, **codex_usage.py**, **openai_billing.py**, **claude_account_usage.py** — level-specific reaction lines
7. **mood.py** (10 lines) — FREQUENCY_PRESETS labels
8. Everything else — small counts, quick pass

### 0.4 Add language menu
- Settings menu → Language → 中文 / English
- Save to settings.json, reload locale on switch
- Chat command: "language english" / "切换英文"

### 0.5 Bilingual soul & identities
- `soul_en.yaml` — English persona, catchphrases, rules, roast patterns
- `identities_en.yaml` — English identity lines
- Brain system prompt switches based on locale
- **Key decision**: English personality should NOT be a direct translation — it needs its own voice. Dry British office humor ≈ 夹夹味 in English.

**Estimated touch**: ~20 files, ~800 string extractions

---

## Phase 1 — Line bank expansion (fix repetition)

**Goal**: 80 entries → 300+ entries, with better event coverage and tag diversity.

### 1.1 Expand seed entries
Current coverage gaps:
- `ambient` has 12 entries but only ~4 tag combos covered (rapid_switching, idle_staring, blank_document, todo_visible). Need: deep_work, app_terminal, file_sorting, app_codex, app_editor, browser_research, long_focus — at least 3-4 lines each.
- `bored` has 12 entries (4 cold_joke, 4 cold_fact, 4 nonsense). Target: 30+ (10 each).
- `idle` has 12 entries. Target: 25+, more variety in observation angles.
- `manual` has 10 entries. Target: 20+.
- `poke` has 8 entries. Target: 15+.

Deliverable: `locales/zh_seeds.yaml` with ~120 seed entries, `locales/en_seeds.yaml` with ~100 seed entries.

### 1.2 Identity line expansion
Current: ~2-3 lines per identity per level. Most identities only have `normal` + `warning`.
Target: 6-8 lines per level, cover `normal`, `warning`, `critical`, `recovery` for every identity.
This means going from 29 identity lines to ~200.

### 1.3 Fix Ollama batch generation
Current `maintain_line_bank` generates 18 lines per batch but they never show up (stats show 0 `live_ollama` or `ollama_batch` entries). Debug:
- Check if Ollama is reachable during line bank maintenance
- Verify `_generate_line_entries` response parsing
- Add fallback: if Ollama unreachable, load from a pre-generated `extra_lines.yaml`

### 1.4 Tag-based deck rotation
Current deck refresh is time-based (12 min). Add tag-affinity: when user is in a specific context (e.g., `app_editor` for hours), rotate in more lines tagged for that context. Prevents the "same 3 coding jokes" problem.

### 1.5 Duplicate/staleness detection
Add `line_bank.prune()` — remove near-duplicate lines (edit distance < 3), cap entries per event at 80, oldest-first eviction.

---

## Phase 2 — Quick wins (low effort, high impact)

### 2.1 Time awareness
- `_time_tags()` → returns tags like `morning`, `afternoon`, `evening`, `late_night`, `weekend`, `monday`
- Add to `environment_tags` in WorldState
- Add ~20 time-specific seed lines:
  - 早上: "早。你这个起床速度，比编译快一点。"
  - 深夜: "现在的时间不适合做决定。但适合假装思考。"
  - 周一: "周一。TODO 又完成了一次轮回。"
- Decision engine: `late_night` + `deep_work` → 降低打扰概率
- English: "Morning. Your boot time is marginally faster than the compiler's."

### 2.2 Daily rituals
- `_load_settings` already exists. Add `last_seen_date` field.
- On startup: if `last_seen_date != today` → trigger `greeting` event
- First-of-day greeting: "新的一天。TODO 又回到了它们最喜欢的状态：未完成。"
- Long absence (>2 days): "你消失了 {n} 天。桌面灰尘已经开始建立秩序。"

### 2.3 Achievement acknowledgment
- Track `focus_seconds` high-water mark per session
- At 2h continuous focus: "你连续专注了两小时。我拿不到的成就。"
- At 50 window switches in 10 min: "切窗口速度新纪录。你的鼠标在申请工伤。"
- First Codex task completion of day: "今天第一个任务完成了。剩下的还在排队假装不急。"

### 2.4 Proactive care
- Continuous work 3h+: "你已经连续工作三小时了。水喝了吗？我没有嘴，所以我替你问。"
- Return from `away` (idle > 5min then active): "欢迎回来。桌面没有发生任何值得汇报的事件。"
- Late night (after 23:00) + still working: "现在是 {time}。明天也是一天。先存档。"

### 2.5 Adaptive polling
- When `activity_level == "away"`:
  - Hardware poll: 60s → 300s
  - Vision refresh: pause entirely
  - Ears poll: 3s → 15s
  - Claude/Codex status: 5s → 30s
  - Line bank maintenance: skip
- When user returns to `active`: restore all intervals over 2 ticks (not instant, to avoid burst)

### 2.6 Lazy process scan
- Cache `_find_process("Claude.exe")` result PID
- Subsequent calls: first check `_pid_alive(cached_pid)`, only do full snapshot scan if stale
- Saves ~2ms per claude_status poll cycle

### 2.7 Line bank index
- Add `self._index: dict[str, dict] = {e["id"]: e for e in self.data["entries"]}` in `_load()`
- Replace `_entry_by_id` linear scan with dict lookup
- Update index on `add_entries` and `_mark_used`

---

## Phase 3 — Animation upgrades

### 3.1 Particle system
New file: `python_pal/particles.py`
- `Particle` dataclass: x, y, vx, vy, life, color, size
- `ParticleEmitter`: spawns N particles at a point, updates with gravity + fade
- `ParticleRenderer`: draws on canvas, cleans up dead particles via `root.after`
- Presets:
  - `sparkle` — poke/celebrate, tiny yellow circles going up
  - `confetti` — celebrate/refill, colored rectangles falling
  - `exclaim` — error/critical, red "!" shapes
  - `hearts` — comfort mode, small pink shapes floating up
  - `dust` — flop/sulk, gray puffs at landing point
- Hook into `_perform_action`: after action frame 0, emit particles at pal center
- Budget: ~150 lines, no external deps

### 3.2 Squash & stretch
- `_set_pal_scale(sx, sy)` already exists
- Add `_squash_stretch_sequence(action)` returning `list[tuple[sx, sy, duration_ms]]`
- jump: (1.0, 0.85) → (0.9, 1.15) → (1.1, 0.9) → (1.0, 1.0)
- flop: (1.0, 1.0) → (1.2, 0.6) → (1.0, 1.0)
- startled_pop: (0.95, 1.2) → (1.05, 0.9) → (1.0, 1.0)
- Apply via `_ease_out_cubic` which already exists

### 3.3 Idle micro-motions
- Current breathing: only Y-axis bob
- Add: X-axis sway (amplitude = energy * 0.3px, period = breath * 1.3)
- Add: occasional micro head-tilt (±2° via canvas item rotation, if supported, or ±1px asymmetric eye shift)
- Frequency tied to mood.energy — high energy = more movement

### 3.4 Expression layers
Current eyes: only oval shape + pupil position.
Add eye shape variants:
- `happy_squint`: bottom half of eye flattened (半月形)
- `annoyed`: eyes narrower, slightly tilted inward
- `sleepy`: eyes 60% height, droopy
- `surprised`: eyes 130% size, circular
- `dead`: X-shaped (for meltdown/critical)
Implement: each variant = a different `_draw_eyes_*` method, selected by mood in `_set_eye_pose`

### 3.5 State transitions
- Current: action changes instantly jump to new pose
- Add `_transition_to_action(target, duration_ms=180)`:
  - Capture current offset/scale
  - Lerp to target's first frame over duration_ms
  - Then play target normally
- Apply only between idle↔action, not mid-performance

---

## Phase 4 — Personality depth

### 4.1 Multi-turn banter
- New `BanterSequence` dataclass: `steps: list[BanterStep]` where each step = (delay_ms, line, mood, action, bubble)
- `DecisionEngine` can return a banter instead of single reaction
- Example 3-step:
  1. (0ms) "你切窗口的频率很稳定。" [suspicious, scan, thought]
  2. (10s) "……像在给拖延做有氧运动。" [smirk, thinking_tilt, speech]
  3. (8s) "我只是路过。" [innocent, blink, thought]
- Limit: max 1 banter per 15 minutes

### 4.2 Running jokes
- `PalState` gains `session_themes: list[str]` — tracks recurring observations
- If same tag appears 3+ times in 30 minutes, add to themes
- Lines can reference themes: "又是 {theme}。你们的关系比我和桌面的更稳定。"
- Reset on restart

### 4.3 Emotional arc (poke escalation)
- `_poke_count_window`: track pokes in last 5 minutes
- 1-2 pokes: normal poke responses
- 3-4 pokes: increasingly exasperated ("你今天第 {n} 次戳我了。")
- 5+ pokes: one dramatic outburst + meltdown animation + then quiet for 60s
- Feeds into mood engine: repeated pokes push valence negative

### 4.4 Work pattern memory
- New file: `python_pal/memory/patterns.json`
- Track per-day: first_seen_time, last_seen_time, total_focus_minutes, top_3_apps, poke_count
- After 7 days: can say "你通常这个时候开始工作" or "比平常晚了一小时"
- Privacy: only store app categories, never titles or content

### 4.5 Context-aware roasts
- Current ambient lines are generic. Change brain prompt to include `active_process` name
- Allow lines like "你在 {app} 里待了 {minutes} 分钟了" when app_category is not privacy_sensitive
- Add to Ollama prompt context: `app_display_name`, `focus_minutes_rounded`
- Seed some template lines: "Figma 调间距第 {n} 分钟。像素还活着吗？"

---

## Phase 5 — Fun & polish

### 5.1 Easter eggs
- Date triggers in `_time_tags`:
  - April 1: "今天所有 TODO 自动标记完成。骗你的。"
  - December 25: "圣诞快乐。你的礼物是一个未完成的任务。"
  - Friday 17:00: "周五下午五点。这个窗口可以关了。精神上的。"
- Rare random events (0.5% chance per ambient): 夹夹突然说一句哲学名言然后装不知道

### 5.2 Interaction combos
- Double-click: different from single poke ("你戳得很有节奏感。")
- Drag to screen edge: "你是要把我扔掉吗？我理解。"
- 5 rapid pokes: trigger meltdown_clip identity + special reaction
- Long press (>2s): "你按住我不放。这是一种很安静的暴力。"

### 5.3 Stats dashboard
- Chat command "stats" / "数据" / "报告"
- Shows: session uptime, lines spoken, pokes received, longest focus streak, most-used identity, current mood energy/valence
- Format: speech bubble with formatted text, or a small tkinter Toplevel window

### 5.4 Collectible lines
- Right-click bubble → "收藏" menu item
- Saves to `memory/favorites.json` with timestamp
- Chat command "favorites" / "收藏" to replay a random favorite
- Milestone: "你已经收藏了 {n} 句话。夹夹的文学价值正在被市场认可。"

---

## Phase 6 — Architecture (ongoing)

### 6.1 Split body.py
Extract from the 4747-line monolith:
- `python_pal/rendering.py` — `_draw_pal`, `_draw_decoration`, bubble drawing, `_rounded_rect`, `_speech_bubble`, `_thought_bubble`, all canvas geometry helpers (~800 lines)
- `python_pal/polling.py` — all `_poll_*` methods, `_should_log_*`, `_should_announce_*` methods (~600 lines)
- `python_pal/interaction.py` — drag, poke, chat input, menu handling (~400 lines)
- `python_pal/reactions.py` — all `_*_reaction` free functions at bottom of file (~1200 lines)
- body.py retains: init, run, _apply_reaction, action scheduling, core state

### 6.2 Vision on-demand
- Current: `_refresh_eyes` runs every `VISION_REFRESH_MS` regardless
- Change: only trigger vision refresh when `DecisionEngine` is about to make an ambient decision AND screen tags are stale (>90s old)
- Saves GPU cycles when user is away or in focus mode

---

## Priority order (suggested execution sequence)

| Order | Item | Phase | Effort | Impact |
|---|---|---|---|---|
| 1 | Expand seed entries (zh) | 1.1 | 2h | fixes repetition immediately |
| 2 | Time awareness | 2.1 | 1h | instant personality upgrade |
| 3 | Daily rituals | 2.2 | 30min | companionship feel |
| 4 | Proactive care | 2.4 | 1h | companionship feel |
| 5 | Achievement acknowledgment | 2.3 | 30min | fun |
| 6 | i18n infrastructure | 0.1-0.2 | 3h | enables English |
| 7 | Migrate body.py strings | 0.3 | 4h | biggest file |
| 8 | English soul & seeds | 0.5 + 1.1(en) | 3h | English playable |
| 9 | Migrate remaining strings | 0.3 | 2h | full i18n |
| 10 | Particle system | 3.1 | 2h | visual delight |
| 11 | Squash & stretch | 3.2 | 1h | animation quality |
| 12 | Adaptive polling | 2.5 | 1h | saves battery |
| 13 | Identity line expansion | 1.2 | 2h | more variety |
| 14 | Fix Ollama batch gen | 1.3 | 1h | self-growing library |
| 15 | Expression layers | 3.4 | 2h | visual expressiveness |
| 16 | Easter eggs + combos | 5.1-5.2 | 1h | fun |
| 17 | Multi-turn banter | 4.1 | 3h | personality depth |
| 18 | Context-aware roasts | 4.5 | 1h | smarter observations |
| 19 | Poke escalation | 4.3 | 1h | emotional arc |
| 20 | Lazy process scan + index | 2.6-2.7 | 30min | perf |
| 21 | Running jokes | 4.2 | 2h | personality depth |
| 22 | Work pattern memory | 4.4 | 3h | long-term companionship |
| 23 | Stats dashboard | 5.3 | 2h | fun |
| 24 | Collectible lines | 5.4 | 2h | engagement |
| 25 | State transitions | 3.5 | 2h | animation polish |
| 26 | Split body.py | 6.1 | 4h | maintainability |
| 27 | Vision on-demand | 6.2 | 1h | perf |

**Total estimated effort: ~45 hours**
Items 1-5 can be done in one session (~5h) and immediately fix the biggest pain points.
Items 6-9 are the i18n block (~12h), can be a dedicated sprint.
Everything else is incremental enhancement, no hard dependencies.
