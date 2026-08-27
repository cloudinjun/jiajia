# Behavior evaluation set

183 scored checks across 114 annotated scenarios, measuring whether Jiajia's
runtime behavior matches its stated design intent.

```powershell
python eval\run_eval.py             # summary
python eval\run_eval.py --verbose   # every failure with its reason
python eval\run_eval.py --json      # machine-readable
python eval\run_eval.py --strict    # non-zero exit on any failure (CI)
```

```
Jiajia behavior evaluation — 183/183 checks passed

  interruption_appropriateness  ████████████████████  115/115  100.0%
  privacy_compliance            ████████████████████   16/16   100.0%
  semantic_fit                  ████████████████████   40/40   100.0%
  recovery_correctness          ████████████████████   12/12   100.0%
```

## Why this exists separately from the test suite

The unit tests answer *"does this function do what the code says it does"*.
This set answers a different question: **does the shipped behavior match the
policy I said I was building?**

The distinction is not academic. Expectations in
[`scenarios.yaml`](scenarios.yaml) are written from the design intent — the
interruption policy table and the motion grammar — **not** by reading the
implementation. That separation is the entire value. A test written by reading
the code can only confirm the code does what it does. A scenario written from
intent can disagree, and a disagreement is a finding either way:

- the implementation drifted from the policy, or
- the policy was never actually encoded, and I only believed it was.

This set found a real defect on its first run. Four entries in the animation
alias table could never fire, because each alias key was also a real action name
and the action lookup runs first. They read as active intent while being dead
code. They are now deleted, and
[`test_animation_resolver.py`](../tests/test_animation_resolver.py) fails if any
come back.

## What is scored

### `interruption_appropriateness` — 115 checks

The policy has seven modes and four independent permission channels. This is
where most of the risk lives, because the failure is silent: an agent that
speaks during a call is not a crash, it is an embarrassment.

Coverage:

- **Baselines** — each mode reached through its own trigger.
- **Precedence** — 11 conflicts where two or more suppressors are true at once.
  `meeting` must beat `focus`; a 3am call must not fall back to sleep-mode
  motion.
- **Boundaries** — the inference for "the user is concentrating" is three
  thresholds (attention ≥ 25s, idle ≤ 2.5s, switching < 4/min). Each is probed
  on both sides, because an off-by-one here means the agent talks over someone
  mid-thought.
- **App categories** — which foreground apps count as protected work, and
  which explicitly do not. An unclassified app must not silently suppress the
  agent; that would make the policy fail open in the wrong direction.
- **Composite states** — realistic combinations: agent running while the user
  types, a permission request arriving during a call, a failure at 2am.

### `privacy_compliance` — 16 checks

The invariant: **suppression degrades urgency, it never discards it.** Every
restrictive mode must set `visual_only_critical`, so an urgent state can still
reach the user silently rather than being dropped.

Also asserts the policy never fails open: a `privacy_sensitive` tag cannot
loosen it, an empty window title is treated as missing evidence rather than
permission, and an unclassifiable app in fullscreen is still protected.

### `semantic_fit` — 40 checks

The resolver is the boundary between model output and the renderer. The
contract is that **nothing past it is a name the renderer does not know.**

- Real action names pass through unrewritten.
- Documented persona aliases land on their intended action.
- Twelve hostile inputs — invented verbs, prose instead of an enum, a JSON
  wrapper, a localized name, typos, camelCase drift, arguments, emoji, a
  path-like string, a bare number, a 200-character string, empty and whitespace
  — must all degrade safely. These are the shapes a local model actually
  produces under temperature, not hypotheticals.

### `recovery_correctness` — 12 checks

Coming *out* of a suppressed state is where agents get stuck mute. Turning focus
mode off, leaving a call, exiting fullscreen, and crossing out of sleep hours
must each fully restore every channel without a restart.

Also checks the useful inverse: a long pause after sustained focus is the right
moment for a care message, so it must resolve to `open`.

## Adding a scenario

```yaml
- id: descriptive_snake_case
  dimension: interruption_appropriateness   # optional; this is the default
  context:                                  # becomes an EarContext
    app_category: editor
    focus_seconds: 60
    idle_seconds: 0.5
    window_switches_per_minute: 1
  focus_mode: false
  quiet_remaining_seconds: 0
  hour: 14                                  # local hour, for time-based rules
  expect:
    mode: focused_input
    allow_speech: false
  rationale: One sentence on why this is the correct behavior.
```

Write `expect` from what the behavior *should* be, before checking what it
currently is. A scenario that was written by running the code first has already
lost most of its value.

## Limits

This set scores the deterministic layer — the interruption policy and the
resolver — because those are the parts with a single defensible answer. It does
not score whether a given animation *reads* as the state intended.

That question got its own pass, outside this harness: ten vision models blind-
rated four anonymized animations, 40 judgments, **5% strict recognition**. The
scheduling layer this directory verifies was correct throughout; the motion
vocabulary it schedules was not.
[docs/research/blind-animation-recognition-2026-08-27.md](../docs/research/blind-animation-recognition-2026-08-27.md)

That is a proxy pre-screen. Vision models expose strong ambiguity cheaply, but
they are not people, and a contact sheet is not playback. Real participants are
still the bar.

The scenarios are also authored by the same person who designed the policy, so
they inherit that person's blind spots. They catch drift and regression well.
They do not catch a policy that was wrong to begin with.
