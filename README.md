# Paperclip Pal

Windows desktop pet prototype for 夹夹, a flat paperclip character with small reactive behaviors.

## Run

```powershell
C:\Users\cloud\AppData\Local\Programs\Python\Python311\pythonw.exe -B -m python_pal.main
```

## Hardware Watcher

The hardware watcher samples low-privacy system metrics and lets 夹夹 tint itself when the computer gets warm.

It reads:

- CPU usage, RAM usage, and disk usage through optional `psutil`
- NVIDIA GPU usage, GPU temperature, and VRAM usage through `nvidia-smi` when available

It does not read clipboard text, keystrokes, chat content, or screen text. Alerts use rolling samples and cooldowns so short spikes do not trigger noisy bubbles.

High GPU/VRAM/RAM use without high temperature is treated as `busy`, not red-hot. Hardware tint is temporary: it appears during hardware reminders or manual hardware checks, then returns to the normal gray body.

## Codex Usage

夹夹 first looks for local Codex rollout files under `%USERPROFILE%\.codex\sessions\...\rollout-*.jsonl` and reads only `token_count.rate_limits`. It converts `primary.used_percent` into 5-hour window remaining percent. It does not read message text, clipboard text, keystrokes, raw screen text, or the Codex/ChatGPT settings UI.

If no fresh local `rate_limits` data is available, it falls back to the local bridge file, `codex_usage_status.json`.

Update the fallback bridge manually with:

```powershell
.\scripts\set_codex_usage.ps1 26 5:22am
```

Expected JSON shape:

```json
{
  "usage_remaining_percent": 26,
  "reset_at": "2026-06-04T05:22:00-07:00",
  "plan": "Pro",
  "source": "manual",
  "updated_at": "2026-06-04T03:12:00-07:00",
  "stale": false
}
```

Low quota alerts are cooled down: under 30% at most every 30 minutes, under 10% at most every 10 minutes.

## Claude Usage

夹夹 reads Claude Code token usage from `%USERPROFILE%\.claude\projects\...\*.jsonl` and only inspects `message.usage`, model names, timestamps, and project names. It deduplicates repeated assistant message ids and summarizes today's usage, the recent 5-hour window, and the last request.

Claude's local logs do not expose a reliable official "remaining quota" percentage like Codex `rate_limits`, so this monitor reports local token usage, not remaining plan quota.

## OpenAI API Billing

夹夹 can read OpenAI API organization costs from `https://api.openai.com/v1/organization/costs`. This requires `OPENAI_ADMIN_KEY`, or another key with `api.usage.read` scope. A normal restricted `OPENAI_API_KEY` may return `missing_usage_scope`.

The OpenAI endpoint reports costs, not a wallet-style remaining balance. To let 夹夹 report remaining budget, configure one of:

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_MONTHLY_BUDGET_USD", "20", "User")
```

or add this to `settings.json`:

```json
{
  "openai_api_monthly_budget_usd": 20
}
```

Without a budget, 夹夹 reports this month's API cost but refuses to invent a remaining balance.

## Assistant Controls

The right-click menu includes lightweight Clippy-inspired controls:

- `Quiet 30 min`: pauses automatic chatter and status alerts, then retreats with a sulky animation.
- `Focus mode`: keeps only tiny low-presence motions while suppressing automatic bubbles.
- `Summon / resume`: clears quiet/focus mode and brings 夹夹 back.

Manual status checks still work while quiet or focus mode is active.

## Local Chat

Right-click `Talk to 夹夹` to open a tiny local chat input near the pal. Press Enter to send or Esc to close.

Chat replies use the existing `Reaction` pipeline, so a reply can still pick a mood, action, bubble color, and performance phrase. Simple state commands are handled locally before Ollama is called:

- `Codex status`, `Claude status`, `hardware status`, `Codex usage`, `Claude usage`, and `OpenAI API billing`
- `安静`, `正常`, `活泼`, `多动`
- `进入专注模式`, `退出专注模式`, and `闭嘴半小时`

Chat context is intentionally low-privacy: agent status summaries, hardware metrics, Codex usage, Claude token usage summaries, OpenAI API cost summaries, activity mode, app category, and recent pal lines. It does not include clipboard text, keystroke text, raw screen text, or full screenshot contents.

While waiting for a local LLM reply, the pal cycles through visible wait stages instead of showing only dots: message received, low-privacy context folded, Ollama waking, model thinking, and long-wait fallback lines.

## Activity Policy

The `活跃度` menu is a behavior policy, not just a speech-rate slider:

- `安静`: visual state only, with critical automatic alerts.
- `正常`: important status changes, conservative context detection.
- `活泼`: earlier warnings, more agent watching, more ambient observations.
- `多动`: Clippy-style proactive detection and personality chatter are allowed.

The policy controls speech frequency, micro-animation frequency, proactive environment detection, and alert thresholds for Codex, Claude, usage, and hardware signals.

## Event Log And Demo

Low-privacy events are appended to `memory/event_log.jsonl`. The log records source, event, level, summary, and the pal reaction, but not keystrokes, clipboard text, chat content, or screen text.

Right-click tools:

- `Last events`: shows the most recent event records.
- `Morning digest`: summarizes events since the previous digest.
- `Animation Preview`: plays manifest-defined performance phrases.
- `Scripted demo`: simulates Codex, usage, hardware, focus, poke, cooling, and done states.

Command-line demo:

```powershell
python -m python_pal.main --demo
```

## Identity Decorations And Idle Variety

Identity packs can now render small flat-vector decorations from `python_pal/decorations.yaml`. These are separate from status badges: badges report system state, while decorations express role/personality, such as a tiny terminal for Agent Supervisor, a thermometer for Thermal Technician, a ledger for Usage Accountant, or a red pen for Critic Clip.

`python_pal/animation_resolver.py` maps conceptual identity animation names, such as `agent_running` or `sleep_loop`, to current playable actions or performance phrases. This lets YAML names work today while leaving room for richer assets later.

Idle animation selection is identity-aware and keeps a short recent-action history so the pal does not loop the same few actions. Quiet/focus modes restrict idle motion to low-stimulus actions.
