# Animation Audit

This audit scores each visible animation for intent clarity and character appeal. The target is not realism; it is a small, readable paperclip performance built from timing, eye movement, brow movement, squash/stretch, pauses, and after-reactions.

Scores use a 10-point scale:

- 9-10: immediately readable and strongly specific to Jiajia
- 7-8: readable, but can use stronger timing or character detail
- 5-6: functional but generic
- below 5: mostly a utility movement rather than character animation

## Signature candidates

| Animation | Score | Why it works | Next improvement |
|---|---:|---|---|
| `cold_arrow_then_innocent` | 9.5 | Best expression of the core persona: judge, speak, then snap innocent. | Hold the judge beat longer, snap to innocent faster after the line, finish with a small harmless nod. |
| `roast_and_scoot` | 9 | Clear and funny: says the thing, then escapes. | Keep the scoot after the bubble lands; do not move before the roast reads. |
| `flop` | 8.5 | Clear collapse / defeat shape with a good low hold. | Add a peek-up expression during the hold and recover more slowly. |
| `sleepy_sag` | 8.5 | Readable low-energy body language. | Separate true sleep from fake sulk; true sleep should settle into a sustained low pose. |
| `smug_sway` | 8 | Strong smug attitude. | Add proud brows, side-eye, and an innocent reset so it feels less like a generic sway. |

## Low-level actions

| Animation | Score | Review | Optimization note |
|---|---:|---|---|
| `idle_breathe` | 6.5 | Quiet and readable, but not very memorable. | Keep it subtle; add low-amplitude eye settle and tail drift instead of more body motion. |
| `blink` | 6 | Functional but generic. | Add slow blink and innocent blink variants; small left/right offset would help. |
| `wiggle` | 7 | Clear poke feedback. | Add an 80ms startled hold before the squash. |
| `peek` | 6.5 | Intent is clear, but it overlaps with scan. | Make it mostly eye-led, not body-led. |
| `scan` | 7 | Useful for monitors and agent status. | Keep the body still and let eyes/brows do the work. |
| `jump` | 7.5 | Strong cartoon jump structure. | Add tail lag and landing expression. |
| `flop` | 8.5 | Very readable collapse. | Add peek-up at the flat hold. |
| `dance` | 6.5 | Fun but generic. | Add a deliberate off-beat and innocent reset. |
| `twirl` | 6 | Interesting but can look like a graphical flip. | Add a smug pre-pose and shorten the mirror hold. |
| `stretch` | 7 | Clear wake-up / prepare-to-work motion. | Add sleepy-to-round eye transition. |
| `shake` | 7.5 | Clear error or panic. | Distinguish error shake from startled shake with warning expression and badge. |
| `happy_bounce` | 7 | Clear small joy. | Keep it smaller than celebrate; add a light tail wag. |
| `nod` | 5.5 | Understandable but generic. | Split into sincere nod and fake-understanding nod. |
| `thinking_tilt` | 8 | Clear thinking / judging pose. | Add eye lead, brow follow, then body tilt. |
| `sleepy_sag` | 8.5 | Strong low-energy motion. | Add sustained sleep pose. |
| `startled_pop` | 7 | Clear surprise. | Add a tiny anticipation shrink before the pop. |
| `tail_wag` | 8 | Distinctive to the paperclip silhouette. | Use as secondary motion on jumps, scoots, and celebration. |
| `smug_sway` | 8 | Persona-aligned and readable. | Add proud brows plus innocent reset. |
| `sulk` | 7.5 | Clear fake sulk / pouting. | Add peek-up during the lowest hold. |
| `hide` | 8 | Clear and charming. | Hide away from mouse or behind the bubble depending on context. |
| `patrol` | 6 | Reads as monitor movement, but too mechanical. | Change to move-stop-look-move rather than constant back-and-forth. |
| `celebrate` | 8 | Clear stronger success motion. | Add a short victory pose and tail wag on landing. |
| `twist_scoot` | 7.5 | Good tiny attitude movement. | Add innocent pre-pose for a fake-casual scoot. |
| `mini_hop_shift` | 7 | Clear reposition. | Add landing tail lag. |
| `relocate_hop` | 7 | Clear large reposition, but can look like window motion. | Look toward target before moving and look back after landing. |
| `roast_and_scoot` | 9 | High-personality escape beat. | Keep as a signature behavior. |
| `retreat_to_corner` | 8 | Clear focus/quiet mode transition. | After retreating, switch to a lower-energy idle profile. |
| `drop_in` | 7.5 | Clear return / re-entry. | Add landing squash and innocent look-up. |

## Current optimization focus

The first optimization pass should refine signature readability rather than rewrite the renderer:

1. Strengthen `cold_arrow_then_innocent` timing.
2. Make `sleep_loop` a sustained sleep state instead of repeating wake/sag motion.
3. Distinguish `error_shake` from generic `shake` with guilty/warning expression.
4. Make `tiny_celebrate` and `celebrate` differ by scale and tail behavior.
5. Add runtime eye/brow poses for `wide`, `sleepy`, and `asleep` so expressions can read without adding a mouth.
