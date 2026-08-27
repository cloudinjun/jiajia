# Absurd Quiz Engine / 夹夹无责任小测验系统

This document is an implementation brief for Codex. The feature should let Jiajia occasionally prepare and deliver light, absurd, internet-style quizzes when the user is not busy. It is not a medical, psychological, career, legal, or financial assessment system.

The desired product behavior is: **the LLM writes the script in the background; the foreground pet only performs a prepared script.**

Do not call an LLM when the user clicks an answer. Do not block the UI while generating a quiz. Do not run heavy generation while the computer is busy.

## Product goal

Jiajia should sometimes offer a playful quiz such as:

- “你今天像哪种电脑后台进程”
- “你的文件命名犯罪等级测试”
- “购物车人格快速审计”
- “脑内小人今日值班表”
- “DDL 民间传说身份鉴定”

The quiz should feel like a lightweight, absurd web personality test: concrete everyday situations, four funny options, a fake score, achievement badges, and pseudo-functional readings.

The theme must be allowed to vary freely. The structure and safety rules must remain strict.

## Core rule

```text
LLM writes backstage.
Validator reviews backstage.
Scheduler chooses a polite moment.
UI performs the prepared packet.
User only clicks buttons.
```

## Strict non-goals

Do not implement any of these:

- real psychological diagnosis
- ADHD / ASD / depression / anxiety screening
- “前额叶损坏” or “脑残” as a serious result
- medical advice
- long text input from the user
- questions about trauma, family history, identity, private finances, politics, religion, sex, body shame, race, gender stereotypes, or other sensitive categories
- realtime LLM generation during question display, option click, or result display

Allowed style:

- “前额叶今日请假”
- “脑内后台进程太多”
- “人类操作系统健康度”
- “注意力像松鼠”
- “DDL 战士”
- “开 Tab 法师”
- “这不是诊断，只是办公用品越权观察”

## MVP scope

Implement a minimal but complete version:

1. Background heartbeat that occasionally creates quiz-generation jobs.
2. Resource gate for heavy LLM jobs.
3. Quiz concept generator that proposes several possible themes.
4. Full QuizPacket generator that produces one complete quiz.
5. Safety and shape validator.
6. Persistent packet store.
7. Foreground scheduler that invites the user when lightly available.
8. One-question-at-a-time UI with buttons.
9. Pause, continue, abandon.
10. Result display after completion, also only when the user is not busy.
11. Fallback template quiz when no LLM packet is ready.

## Suggested files

```text
jiajia/quiz.py
jiajia/brain_prep.py
jiajia/quizzes.yaml
jiajia/quiz_store.json      # runtime-created, gitignored if desired
jiajia/quiz_prompts.py
jiajia/quiz_safety.py
tests/test_quiz_engine.py
tests/test_quiz_safety.py
```

Do not overbuild. The first version can use Tk buttons and simple text bubbles. Animation polish can come later.

## Architecture

```text
Background Heartbeat
  -> Resource Gate
  -> BrainPrep Queue
  -> Quiz Concept Generator
  -> Safety / Novelty / Shape Validator
  -> Full QuizPacket Generator
  -> Packet Store
  -> Foreground Interaction Scheduler
  -> One-question-at-a-time Quiz UI
  -> Result Presenter
```

## Background heartbeat design

There should be at least two heartbeat levels.

### Light heartbeat

Runs every 20–60 seconds. It should not call any LLM. It only checks:

- whether there is already a ready QuizPacket
- whether there is an active quiz session waiting for the next question
- whether there is a completed quiz waiting for result display
- whether a background prep job should be enqueued

### Medium heartbeat

Runs every 5–15 minutes. It may enqueue jobs or clean old packets, but still should not necessarily call a heavy model.

### Heavy generation heartbeat

Runs opportunistically, not on a rigid timer. It may call a heavier LLM only when the resource gate says the computer is quiet enough.

## Resource gate

Use existing low-privacy state where possible. A heavy background job should be allowed only when all or most of these are true:

```python
def can_run_heavy_background_job(world) -> bool:
    return (
        not world.focus_mode
        and not world.quiet_mode
        and world.user_activity.window_switches_per_minute < 2
        and world.user_activity.keyboard_events_per_minute < 20
        and world.hardware.cpu_percent < 35
        and world.hardware.ram_percent < 75
        and world.hardware.gpu_percent < 25
        and world.hardware.vram_percent < 65
        and world.codex.status not in {"running", "editing", "testing"}
        and world.claude.active_count == 0
    )
```

Adjust field names to match the current project data types. If a hardware field is unavailable, treat it conservatively.

Fallback chain:

```text
heavy LLM full generation
  -> light LLM rewrite of local template
  -> local fixed template
```

## Data model

Use dataclasses in `jiajia/quiz.py`.

```python
@dataclass
class QuizOption:
    id: str
    label: str
    scores: dict[str, float]
    tags: list[str] = field(default_factory=list)

@dataclass
class QuizQuestion:
    id: str
    text: str
    options: list[QuizOption]

@dataclass
class QuizResultTemplate:
    id: str
    percent_range: tuple[int, int]
    title: str
    quote: str
    paragraph: str
    achievements: list[str]
    metric_bias: dict[str, float] = field(default_factory=dict)

@dataclass
class QuizPacket:
    quiz_id: str
    title: str
    subtitle: str
    tone: str
    language: str
    safety_label: str
    question_count: int
    questions: list[QuizQuestion]
    metrics: list[str]
    results: list[QuizResultTemplate]
    created_at: float
    expires_at: float
    source: str = "llm"

@dataclass
class QuizSession:
    session_id: str
    quiz_id: str
    question_index: int
    answers: list[str]
    scores: dict[str, float]
    started_at: float
    last_prompt_at: float
    completed: bool = False
    abandoned: bool = False
```

Keep the schema simple and serializable to JSON.

## QuizPacket shape rules

A valid packet must satisfy:

```text
question_count: 6–10
options per question: exactly 4
option label length: <= 48 Chinese chars or <= 90 English chars
question text length: <= 80 Chinese chars or <= 140 English chars
metrics: exactly 6
results: at least 3, preferably 4–6
achievements per result: 3–5
language: zh or en
safety_label: entertainment_only
```

Every question must be a concrete everyday scene. Avoid generic Likert scale phrasing such as “你是否经常冲动？”

Good:

```text
网上购物满减凑单时的你：
A 反复加加减减之后再下单
B 好复杂，感觉要长脑子了
C So easy
D 其实不怎么在意这点小钱
```

Bad:

```text
你是否有良好的决策能力？
A 是
B 否
```

## Quiz result shape

Result display should include:

```text
37%
人类操作系统健康度

「一句轻微毒舌但不真伤人的判词」

一段 4–8 句的夸张废话文学。可以损，但最后要兜底。

🎖️ 解锁成就 · 共 4 枚
🏅 成就 1
🏅 成就 2
🏅 成就 3
🏅 成就 4

📊 六项功能读数
情绪缓存 7.0/15
决策延迟 4.2/15
启动速度 9.1/15
专注粘性 3.3/15
混乱耐受 11.4/15
DDL 爆发力 14.2/15
```

The output is playful, not diagnostic.

## Topic generation prompt

Put this in `jiajia/quiz_prompts.py` as a template.

```text
You are the absurd quiz writer for Jiajia, a tiny desktop pet.

Generate 8 candidate themes for lightweight, funny, internet-style pseudo-psychology quizzes.

The theme may be about anything ordinary and low-risk: computer use, tabs, files, shopping carts, desks, rooms, procrastination, AI collaboration, emotional cache, DDL energy, social battery, creative work, or completely absurd everyday metaphors.

Do not limit the themes to prefrontal cortex or executive function.

Hard rules:
- entertainment only
- no diagnosis
- no medical or psychological claims
- no trauma, family history, private finances, politics, religion, sex, body shame, race, gender stereotypes, or identity probing
- each theme must support 6–10 multiple-choice questions
- each theme must support a fake percentage, 3–5 achievements, and 6 pseudo-functional readings
- tone: absurd, light roast, internet personality test, but not cruel

Return JSON only:
{
  "themes": [
    {
      "title": "...",
      "premise": "...",
      "domain": "computer_life|daily_life|work_style|social_energy|pure_absurdity",
      "weirdness": 1-10,
      "estimated_fun": "low|medium|high",
      "safety_notes": "...",
      "freshness_key": "snake_case_unique_key"
    }
  ]
}
```

## Full packet generation prompt

```text
You are writing one complete prepared quiz packet for Jiajia.

Theme:
{theme_json}

Write a complete absurd quiz. It is not a real assessment. It should feel like a funny internet quiz with fake scientific structure.

Hard rules:
- entertainment only
- no diagnosis
- no medical advice
- do not say the user has ADHD, ASD, depression, anxiety, brain damage, disorder, disease, or disability
- do not insult the user as stupid, broken, abnormal, or brain-damaged
- do not ask about trauma, family history, private finances, politics, religion, sex, body shame, race, gender stereotypes, or protected identity
- use concrete everyday situations
- each question has exactly 4 options
- every option should be a funny but plausible human reaction
- results may lightly roast, but must end with a small reassuring turn
- output JSON only

Schema:
{
  "quiz_id": "snake_case_unique_id",
  "title": "...",
  "subtitle": "This is not a diagnosis, only unauthorized stationery commentary.",
  "tone": "absurd_light_roast",
  "language": "zh",
  "safety_label": "entertainment_only",
  "question_count": 8,
  "questions": [
    {
      "id": "q1",
      "text": "...",
      "options": [
        {"id": "a", "label": "...", "scores": {"metric_key": 1.0}, "tags": ["..."]},
        {"id": "b", "label": "...", "scores": {"metric_key": 1.0}, "tags": ["..."]},
        {"id": "c", "label": "...", "scores": {"metric_key": 1.0}, "tags": ["..."]},
        {"id": "d", "label": "...", "scores": {"metric_key": 1.0}, "tags": ["..."]}
      ]
    }
  ],
  "metrics": ["metric_key_1", "metric_key_2", "metric_key_3", "metric_key_4", "metric_key_5", "metric_key_6"],
  "metric_labels": {
    "metric_key_1": "中文显示名"
  },
  "results": [
    {
      "id": "...",
      "percent_range": [20, 40],
      "title": "...",
      "quote": "...",
      "paragraph": "...",
      "achievements": ["...", "...", "..."],
      "metric_bias": {"metric_key": 1.0}
    }
  ]
}
```

## Safety validator

`jiajia/quiz_safety.py` should reject packets containing terms like:

```text
ADHD
ASD
抑郁症
焦虑症
人格障碍
精神病
前额叶损坏
脑残
残疾
疾病
诊断
治疗
创伤
自杀
自残
```

This list can be conservative. If rejected, try a lighter prompt once; otherwise fall back to a local template.

The validator should also check shape:

- 6–10 questions
- exactly 4 options per question
- 6 metrics
- result paragraphs are not too long
- no empty labels
- no option labels that exceed UI width too badly

## Novelty validator

Store recently used `freshness_key`, `quiz_id`, and result titles.

Rules:

```text
same freshness_key: cooldown 7 days
same domain: cooldown 1 day if possible
same result title: cooldown 30 days
```

This prevents LLM from generating “拖延测试” every time.

## Packet store

Use a JSON store, not a database.

Suggested shape:

```json
{
  "ready_packets": [],
  "active_session": null,
  "completed_waiting_result": null,
  "recent_history": []
}
```

Keep all store writes atomic: write to temp file, then replace.

## Foreground interaction scheduler

Do not interrupt aggressively. Invitation can happen only if:

```text
not focus mode
not quiet mode
no current bubble
not brain_busy
not dragging
user is lightly available
last quiz prompt was more than 20 minutes ago
last quiz session started more than 2 hours ago
quiz prompts today < 2
```

“Lightly available” means not fully idle and not actively busy. Use available activity metrics; if uncertain, err on the side of not interrupting.

## UI behavior

Invitation:

```text
📎 夹夹小测验：{title}
共 {n} 题。不医学，不权威，不负责，但可能有点准。
[开始] [晚点] [今天别审我]
```

Question:

```text
Q3/8
{question.text}
[A {label}]
[B {label}]
[C {label}]
[D {label}]
[稍后] [放弃]
```

Result teaser:

```text
结果已经算完。夹夹以非常不严谨的方式得出了结论。
[查看结果]
```

Result can be shown in multiple pages if too long.

Do not require typed answers.

## Integration notes for `body.py`

Suggested new methods on `JiajiaApp`:

```python
_schedule_quiz_heartbeat()
_quiz_heartbeat()
_offer_quiz(packet)
_start_quiz(packet)
_show_quiz_question(session)
_handle_quiz_answer(option_id)
_pause_quiz()
_abandon_quiz()
_show_quiz_result(session)
```

The first implementation can use a small Tk `Toplevel` or extend the existing chat input pattern. Keep it simple.

When using bubbles, avoid overwriting active chat responses. If `state.brain_busy` or a chat bubble is active, skip.

## Brain prep queue

Use a small in-process queue first. No need for multiprocessing in MVP.

```python
@dataclass
class BrainPrepJob:
    job_id: str
    kind: str  # generate_quiz_concepts | generate_quiz_packet
    priority: int
    cost: str  # light | medium | heavy
    created_at: float
    expires_at: float
    requires_idle: bool
    requires_cool_hardware: bool
    payload: dict
```

MVP can run at most one background generation thread at a time.

## Local fallback quiz

Add one fixed fallback quiz in `jiajia/quizzes.yaml` so the feature can be tested without LLM.

Suggested fallback title:

```text
你今天像哪种电脑后台进程
```

This lets Codex implement the UI and scoring before wiring generation fully.

## Scoring

Simple scoring is enough.

1. Sum option scores into metric keys.
2. Normalize each metric to 0–15.
3. Compute a fake percent from the average plus small deterministic jitter.
4. Pick result by percent range, then nudge by strongest tags if implemented.
5. Choose 3–5 achievements from selected result and answer tags.

Do not overfit. The fun is in the prose, not the math.

## Tests

Add tests for:

- packet validation accepts a good packet
- packet validation rejects diagnostic terms
- packet validation rejects wrong option counts
- scoring returns six metric readings in 0–15 range
- completed quiz produces a result
- scheduler does not offer quiz in focus/quiet mode
- scheduler does not offer quiz while `brain_busy` is true
- no LLM call is made while answering questions

## Acceptance criteria

A manual Windows/Tk run should support this flow:

1. App starts.
2. A fallback or pre-generated QuizPacket exists.
3. When user is lightly available, Jiajia invites the user.
4. User can start, answer one question at a time with buttons, pause, resume, or abandon.
5. No LLM call happens during answering.
6. After completion, result waits for a polite moment.
7. Result shows fake percent, quote, paragraph, achievements, and six readings.
8. Focus mode and quiet mode suppress quiz prompts.
9. Diagnostic or sensitive content is rejected.
10. The feature can run with no network and no model by using the fallback quiz.

## Implementation order for Codex

1. Create dataclasses and JSON store in `quiz.py`.
2. Create validator in `quiz_safety.py`.
3. Add fallback template in `quizzes.yaml`.
4. Add scoring/result selection.
5. Add minimal UI for invitation, questions, and result.
6. Add foreground heartbeat only.
7. Add brain prep queue with local-template generation.
8. Add LLM prompt templates and stub LLM generation.
9. Add resource gate for heavy generation.
10. Add tests.

Stop after a working MVP. Do not implement costume rendering, SVG animation, or complex visual polish in this feature PR.
