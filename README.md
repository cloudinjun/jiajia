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
