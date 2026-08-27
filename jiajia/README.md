# Python Pal Runtime

This package contains the active Python/Tk implementation of Jiajia.

Run from the repository root:

```powershell
python -m jiajia.main
```

Self-test without opening the desktop pet:

```powershell
python -m jiajia.main --self-test
```

## Core Files

- `main.py`: entry point.
- `body.py`: Tk window, canvas drawing, mouse interaction, bubbles, menus, and
  animation playback.
- `actions.py`: visible action vocabulary.
- `animations.yaml`: logical states and procedural performance phrases.
- `animation_player.py`: manifest-driven sequence playback.
- `soul.yaml`: personality rules and speaking constraints.
- `line_bank.py`: long-lived and short-lived candidate line management.
- `ears.py`: low-risk activity sensing.
- `eyes.py`: optional low-frequency scene tagging.
- `world.py`: compact world-state aggregation.
- `decision.py`: explainable reaction decisions.

## Animation Direction

Animation complexity should come from layered performance, not only larger
motion:

- body squash/stretch
- pupil movement
- brow pose
- pauses
- pre-reactions and after-reactions
- state continuity

The current first-class performance phrases are:

- `cold_arrow_then_innocent`
- `smug_but_caught`
- `fake_sulk`
- `suspicious_observe`
- `quiet_companion`
- `tiny_celebrate`

## Character Asset

The base SVG is:

```text
assets/paperclip/jiajia-refined.svg
```

Keep the core silhouette stable: paperclip body, large eyes, dark brows, no
mouth, no hands, no feet, no gradients, and no complex shadows.

## Runtime State

Runtime state belongs outside git:

- root `settings.json`
- root status bridge JSON files
- root `memory/`

Do not commit usage logs, API keys, account snapshots, or generated memory.
