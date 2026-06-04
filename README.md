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

## Codex Usage

夹夹 reads Codex quota from a local bridge file, `codex_usage_status.json`. It does not scrape the Codex or ChatGPT settings UI.

Update the file manually with:

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

## Assistant Controls

The right-click menu includes lightweight Clippy-inspired controls:

- `Quiet 30 min`: pauses automatic chatter and status alerts, then retreats with a sulky animation.
- `Focus mode`: keeps only tiny low-presence motions while suppressing automatic bubbles.
- `Summon / resume`: clears quiet/focus mode and brings 夹夹 back.

Manual status checks still work while quiet or focus mode is active.
