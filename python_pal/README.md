# Paperclip Pal Python Prototype

This is the first Python body/brain prototype. It keeps the current PowerShell
version untouched.

Run:

```powershell
python -m python_pal.main
```

Self-test without opening the desktop pet:

```powershell
python -m python_pal.main --self-test
```

The personality lives in `soul.yaml`. The text brain calls local Ollama at
`http://127.0.0.1:11434` and defaults to `qwen3.5:9b`.

Codex status bridge:

The pet watches `codex_status.json` in the project root. Update it manually or
from a script to let the pet react to Codex state changes.

```powershell
.\scripts\set_codex_status.ps1 -Status running_command -Summary "正在跑测试"
.\scripts\set_codex_status.ps1 -Status waiting_user -Summary "需要你确认下一步"
.\scripts\set_codex_status.ps1 -Status done -Summary "改完并通过检查"
```

Supported statuses: `idle`, `thinking`, `reading`, `working`, `editing`,
`running`, `testing`, `reconnecting`, `disconnected`, `waiting_user`, `done`,
`error`, `blocked`. The old `running_command` value is accepted as an alias for
`running`.

Codex status bubbles use a green Codex/OpenAI accent. Claude status bubbles use
a warm orange Claude accent. Both stay flat, with no drop shadow.

Idle boredom:

When the user has been idle for a while, the pet may ask the local brain for a
`bored` reaction. Those lines can be cold jokes, cold facts, or deadpan
nonsense. Use the right-click `Boredom line` menu item to trigger one manually.

Actions:

The shared action vocabulary lives in `actions.py`. The right-click `Actions`
menu is grouped into `Mood`, `State`, and `Reactive`, with 20 visible actions.
Large motions use per-frame timing in `body.py`, so each action can have its own
duration and rhythm.

Line bank:

Repeated one-off generation gets tiring over time, so the pet keeps a persistent
two-layer line bank at `memory/line_bank.json`. The large library changes slowly;
short performance decks are refreshed more often and sampled first for
`manual`, `idle`, `bored`, and `poke` events. If the library is small or stale,
the app asks Ollama to refill it in the background instead of blocking a live
reaction.

Ambient sensing:

`ears.py` samples low-risk activity signals: foreground app/process, sanitized
window title, idle time, focus duration, and window-switch frequency. It never
records key text or clipboard content. `eyes.py` can low-frequency capture an
in-memory, downscaled screenshot for the local Ollama vision model and asks only
for high-level scene tags, not text transcription. Privacy-sensitive chat or
meeting contexts are tagged so ambient reactions stay quiet by default.

World state and decisions:

`world.py` combines ears, eyes, Codex, Claude, pal state, and mood into one
sampled `WorldState`. `decision.py` turns that into explainable ambient
decisions such as task avoidance, stuck idle, deep focus, or coding-agent
waiting. Use the right-click `Debug last decision` item to see why the pet
reacted or stayed quiet.

Performance phrases:

`performance.py` defines small action sequences that can wrap a line: glance
first, speak, then snap back to an innocent pose. Reactions and line-bank
entries may optionally set `performance`; otherwise the body picks a simple
phrase from mood, action, and bubble type.

Animation direction:

Animation complexity should come from layers, timing, combinations,
responsiveness, and emotional continuity rather than from ever larger motions.
The current first-class performance phrases are
`cold_arrow_then_innocent`, `smug_but_caught`, `fake_sulk`,
`suspicious_observe`, `quiet_companion`, and `tiny_celebrate`. The body also has
internal `micro_*` actions for eyes, pupils, and brows; these are meant for
performance phrases, not for the visible action menu.

Animation manifest:

`animations.yaml` is the lightweight animation manifest inspired by state/theme
mapping systems such as Clawd's, but it uses Paperclip Pal's own procedural Tk
actions. It maps logical states to performance phrases and defines phrase
sequences made from `action`, `eyes`, `brows`, `pause_ms`, `bubble: speak`, and
`reset: expression` steps. `animation_player.py` reads this manifest and falls
back to the older hard-coded performance table if a phrase is missing, so
current actions keep working while the animation system becomes configurable.

Identity packs:

`identities.yaml` is the lightweight identity-pack library. Each pack keeps the
same paperclip silhouette and defines only a purpose, trigger tags, one or two
visual add-ons, an accent color, preferred action/performance, and seed lines.
`identity.py` selects one pack from the current event/context. The live brain
receives only the selected pack's short `identity_brief`, and the line bank is
seeded with pack-specific lines so identities can work without increasing live
model pressure. Use the right-click `Identity` menu to keep Auto mode or force a
specific pack, and `Debug identity` to see what Auto selected.

Character asset system:

The flat character reference lives at
`assets/paperclip/paperclip-pal-refined.svg`. It is split into stable layer IDs:
`body_wire`, `left_eye_white`, `right_eye_white`, `left_pupil`, `right_pupil`,
`left_brow`, and `right_brow`. `assets/paperclip/asset_manifest.yaml` records
the pure-flat visual rules and the first asset batch. Do not add a mouth, hands,
feet, gradients, texture, or complex shadows; the character should stay a simple
paperclip whose expression comes from eyes, brows, timing, squash/stretch, and
after-reactions. The first animation batch is intentionally small:
`idle_breathe`, `blink`, `side_eye`, `cold_arrow_then_innocent`, and
`fake_sulk`.

Identity animation scope:

Identity packs may declare `allowed_moods`, `core_animations`, and
`fallback_animation`, but those names are asset/performance concepts first.
Unknown identity-specific animation names should fall back to existing actions
or performance phrases instead of requiring new GIF/APNG assets. The first
identity animation batch is only: Default Pal (`idle_breathe`,
`cold_arrow_then_innocent`), Task Auditor (`audit_scan`, `soft_nudge`), Agent
Watcher (`agent_running`, `agent_error`), and Sleepy Clip (`sleep_loop`,
`wake_startled`).
