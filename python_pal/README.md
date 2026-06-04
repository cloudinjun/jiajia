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
