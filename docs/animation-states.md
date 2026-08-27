# Animation State Taxonomy

Jiajia keeps a small semantic state layer above raw Tk actions and procedural performance phrases.

## Canonical states

| State | Meaning | Typical performance | Fallback action |
|---|---|---|---|
| `idle` | Quiet standby; only breathing should loop continuously. | none | `idle` |
| `typing` | User is entering a prompt or the pal is listening. | `typing_focus` | `blink` |
| `thinking` | Model, agent, monitor, or status check is active. | `thinking_loop` | `thinking_tilt` |
| `success` | Task completed, quota recovered, or status improved. | `tiny_celebrate` | `happy_bounce` |
| `error` | Error, blocked flow, failed check, or critical status. | `error_shake` | `shake` |
| `sleep` | Low energy, quiet mode, or dramatic collapse. | `sleep_loop` | `sleepy_sag` |

Older mood names such as `done`, `celebrate`, `sleeping`, `sulky`, `blocked`, and `waiting` are aliases for those canonical states instead of separate visual modes.

## Resolution flow

`Reaction(mood, action, bubble)` is resolved through:

1. `animations.yaml` `state_rules`
2. logical-state alias normalization in `AnimationManifest`
3. state-level performance phrase
4. state fallback action
5. legacy phrase fallback, when a manifest phrase is unavailable

This keeps status and identity reactions from inventing near-duplicate behavior for the same semantic state.

## Idle repetition

The continuous idle loop should stay visually quiet. Body-level idle selection keeps a recent-action window and separate cooldowns for large and movement actions. The state aliases reduce repetition by routing identity aliases such as `agent_running`, `agent_stuck`, `agent_error`, and `sleep_loop` into shared performances rather than parallel one-off actions.
