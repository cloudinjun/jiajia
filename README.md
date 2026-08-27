# Jiajia (夹夹)

[![CI](https://github.com/cloudinjun/jiajia/actions/workflows/ci.yml/badge.svg)](https://github.com/cloudinjun/jiajia/actions/workflows/ci.yml)

A lightweight Windows desktop pet: a flat paperclip character with reactive
animation, local personality lines, and metadata-only status monitoring.

The character is project-specific vector art. It does not use Microsoft Office
Assistant assets or Microsoft Agent components.

## Demo

![User input to thinking to reply](docs/media/hero-interaction.gif)

Type to it, watch it perform a visible thinking state while the local brain
works, then get a bubble plus a tiny character performance.

| Idle | Cold arrow | Sleepy |
|---|---|---|
| ![Idle breathe](docs/media/idle-breathe.gif) | ![Cold arrow then innocent](docs/media/cold-arrow-then-innocent.gif) | ![Sleepy sag](docs/media/sleepy-sag.gif) |

| Status colors | Tail wag |
|---|---|
| ![Status colors](docs/media/status-colors.gif) | ![Tail wag](docs/media/tail-wag.gif) |

## Technical Highlights

- Local-first Tk desktop app with transparent, always-on-top Win32 window behavior.
- Zero required runtime dependencies beyond Python 3.11 and Tkinter.
- Optional monitors for Codex, Claude, OpenAI API costs, and local hardware state.
- Personality fallback chain: curated line banks, local status replies, optional Ollama.
- Regression-tested animation GIFs: keyframe changes must update the public GIF library.

## Features

- Drag to move, double-click to poke, right-click for actions, mode, status, and quit.
- Layered flat character rig: body, eyes, pupils, brows, tail, inner-core gestures, props.
- Action vocabulary including blink, scan, jump, flop, melt, dance, tail wag, paper props,
  and English-mode `britclip` costume.
- Speech and thought bubbles with source-aware colors for Codex, Claude, hardware, and API cost state.
- Activity presets from quiet to hyper, with focus/quiet controls to reduce interruptions.
- Optional local chat through Ollama; status questions are handled locally first.

## Quick Start

```powershell
python -m jiajia.main
```

Background-style launch on Windows:

```powershell
pythonw -B -m jiajia.main
```

Self-test without opening the pet:

```powershell
python -m jiajia.main --self-test
```

## Install Extras

The runtime path is intentionally small:

```powershell
python -m pip install .
```

Optional GIF/media tooling:

```powershell
python -m pip install ".[media]"
```

Optional hardware metrics:

```powershell
python -m pip install ".[monitoring]"
```

## Privacy

Jiajia is designed to observe state, not private content.

By default it does not read clipboard text, keystroke text, passwords, chat
contents, raw document text, browser cookies, or full screenshots.

It may read low-sensitivity state sources when enabled: foreground app category,
idle time, Codex local rate-limit metadata, Claude local token metadata,
hardware metrics, and optional OpenAI organization cost totals.

Details: [PRIVACY.md](PRIVACY.md)

## Tests

```powershell
python -m compileall -q jiajia scripts tests
python -m unittest discover -s tests
python -m jiajia.main --self-test
```

CI runs the public Python test suite on Windows, including:

- `test_action_gifs.py`
- `test_chat_language.py`
- `test_quiz_engine.py`
- `test_quiz_safety.py`

The action GIF test compares the rendered GIF manifest with current action
signatures. Regenerate after retiming actions:

```powershell
python scripts\generate_action_gifs.py
```

## Repository Map

```text
jiajia/
  main.py                  app entry point
  body.py                  app orchestration (mixes the layers below together)
  pal_geometry.py          shared constants, curves and pure geometry
  pal_motion.py            keyframes and motion tables
  pal_window.py            Win32 and window placement layer
  pal_canvas.py            Tk drawing layer
  pal_actions.py           action dispatch and scheduling
  pal_decor.py             decoration and costume layer
  pal_idle.py              idle timers, gaze, blinking and dozing
  pal_panels.py            chat and quiz panels
  rig_pose.py              tail and inner-core pose math
  prop_shapes.py           emotion props, face scripts and eye FX
  animations.yaml          logical states and performance phrases
  soul.yaml                personality and behavior rules
  assets/                  public runtime assets and vendor notices
scripts/
  generate_demo_gifs.py    README demo GIF generator
  generate_action_gifs.py  per-action GIF generator and signature manifest
docs/media/
  *.gif                    README demo GIFs
  actions/*.gif            per-action preview library
```

## Local Files

These are ignored and should stay private:

- `settings.json`
- `memory/`
- `codex_status.json`
- `codex_usage_status.json`
- `claude_account_status.json`
- `openai_billing_status.json`
- `.env*`
- raw AI concept exports under `jiajia/assets/paperclip/`

## License

Project code and original Jiajia assets are MIT licensed. Selected
third-party icon references keep their original notices in
[jiajia/assets/vendor/THIRD_PARTY_NOTICES.md](jiajia/assets/vendor/THIRD_PARTY_NOTICES.md).
