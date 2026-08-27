# Animation Upgrade Plan

This plan upgrades Paperclip Pal from an action player into a small performer.
The goal is not bigger motion. The goal is clearer acting: anticipation,
layered expression, readable state, and after-reaction.

For the long-term production rules behind this plan, see
[`ANIMATION_AUTHORING_GUIDE.md`](ANIMATION_AUTHORING_GUIDE.md).

## Non-negotiable Character Rule

Do not add a mouth.

Paperclip Pal's identity depends on a mouthless paperclip face. The expressive
surface should remain eyes, brows, tail, body timing, bubbles, and small flat
effects. A mouth would make the character more generic and weaken the
"innocent stationery item saying sharp things" contrast.

## Current Gaps

- Large actions often start immediately, so they lack anticipation.
- Many actions end by snapping back to idle, so they lack follow-through.
- Eye, brow, tail, tint, particles, and action are not consistently bundled.
- Status animations rely too much on bubble text.
- The live system has useful pieces already: spring-damper, expression tween,
  particle emitter, tail wire, and manifest performance phrases.

## Phase 0: Authoring Contract

Add non-invasive metadata and anchors before changing more motion code:

- `python_pal/rig.yaml` defines stable body, inner-wire, tail, prop, and bubble
  anchors.
- `performance_phrases.*.lifecycle` classifies animations as `loop`,
  `oneshot_return`, or `transition_to_state`.
- logical states can carry `minimum_ms`, `priority`, and `interruptible`.
- agent status visuals are normalized under `agent_state_visuals`.
- persistent appearance states use the `costume` layer, separate from
  functional identity decorations.

This phase lets the project describe better animation behavior before the
runtime fully enforces it.

The first costume sample is `britclip`: a genderless British-inspired mode,
中文叫“英伦夹”, that persists after language switch and exits through a reverse
transition.

## Phase 1: Runtime Acting Layer

Add a lightweight acting layer on top of existing actions:

- automatic anticipation/follow-through frames around key `ACTION_FRAMES`
- action-specific expression hooks
- action-specific tail and particle cues
- stronger status/readability effects without changing the base character

This should be done inside the current `body.py` execution path so all callers
benefit immediately.

## Phase 2: Pose Library

Define named full-character poses:

- `innocent`
- `judge`
- `smug`
- `guilty`
- `sleepy`
- `startled`
- `sulk`
- `focused`
- `searching`
- `overheated`

Each pose should describe eyes, brows, body bias, tail behavior, and optional
effect cue. The runtime should apply poses before and after action sequences.

## Phase 3: Timeline Player v2

Extend `animations.yaml` from simple steps into a richer timeline:

- `pose`
- `action`
- `effect`
- `bubble`
- `hold`
- `reset`

Core performances to migrate first:

- `thinking_searching_reply`
- `cold_arrow_then_innocent`
- `smug_but_caught`
- `fake_sulk`
- `sleepy_sag`
- `status_watch`

## Phase 4: Continuity

Keep short emotional residue after actions:

- after a roast: linger smug/guilty, then snap innocent
- after repeated pokes: escalate startled -> sulk -> hide
- after long LLM wait: thinking -> searching -> sleepy sag
- after Codex/Claude completion: watch -> tiny celebrate -> idle

## Acceptance Criteria

- Each core state is recognizable without reading the bubble.
- The first 300 ms of a large action shows anticipation.
- The final 500-1200 ms shows after-reaction, not instant idle.
- No action requires a mouth, hands, feet, gradients, or complex shadows.
- Quiet/focus modes still use low-stimulus motion.
