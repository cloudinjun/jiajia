# Animation Authoring Guide

This guide captures the animation production rules for Jiajia. It is
not about making the character more visually complex. It is about making a
simple paperclip feel more alive through timing, layering, state logic, and
careful review.

## Core Principle

Jiajia should feel performed, not merely moved.

Big motion is not the main source of quality. The strongest acting comes from
small readable changes:

- eyes choosing where to look
- brows judging before the line lands
- the inner wire covering, shrinking, or drooping
- tail motion betraying the character's real mood
- pauses before and after a reaction
- a short emotional residue after speech

Do not add a mouth. Do not add hands or feet to the base character. Props can
suggest gestures, but the paperclip body stays simple.

## Role Of AI In Animation Work

AI can help propose action ideas, keyframe descriptions, timing variations, and
pose alternatives. It should not be treated as the final authority on the
character shape.

Use AI for:

- storyboard-like action drafts
- alternate acting beats
- naming and organizing performance phrases
- generating rough timing tables
- proposing prop use cases
- finding expressive variants for the same state

Do not let AI freely redesign:

- the main paperclip silhouette
- eye placement
- brow identity
- body thickness
- the no-mouth rule
- the flat visual style

Generated artwork is a reference layer. Runtime assets should be redrawn,
rigged, simplified, or baked into the project's own style before use.

## Runtime And Authoring Split

The Python runtime remains responsible for desktop behavior:

- window placement
- dragging and clicking
- menus
- bubbles
- status monitors
- identity switching
- local model calls
- privacy and interruptibility

Animation authoring can use a separate toolchain when helpful:

- browser-based SVG preview for tuning
- JavaScript or TypeScript for SVG manipulation and export
- generated PNG frame sequences, spritesheets, WebP, or APNG for complex
  non-interactive performances
- YAML or JSON for reusable performance timelines

The runtime should stay stable. The animation studio is a rehearsal room, not a
replacement body.

## Preferred Asset Strategy

Use live procedural drawing for states that need responsiveness:

- blink
- eye tracking
- idle breathing
- status tint
- tail idle motion
- small inner-wire gestures
- bubbles and badges

Use baked frame assets only when procedural drawing becomes too expensive or
too fiddly:

- complex paper prop performances
- cinematic suit-up sequences
- special public demo GIFs
- temporary experimental states

If a performance must respond to current world state, keep it procedural or
split it into procedural layers over a baked base.

## Layered Master Rules

Every expressive part should have a stable conceptual layer:

- `body_wire`
- `left_eye_white`
- `right_eye_white`
- `left_pupil`
- `right_pupil`
- `left_brow`
- `right_brow`
- `inner_wire`
- `tail_wire`
- `paper_prop`
- `decoration`
- `bubble`
- `status_badge`

These layers should not randomly swap responsibility. Eyes and brows carry the
main emotion. The body carries weight and timing. The inner wire carries
self-conscious reactions. The tail carries betrayed intent. Props carry scene
context.

## Rig-First Motion

For bendable or attachable parts, define semantic anchors before drawing more
frames.

The active anchor contract lives in:

```text
jiajia/rig.yaml
```

Useful anchors:

- `body_root`: the stable body reference point
- `body_contact`: the lowest visual contact point
- `eye_left_center`
- `eye_right_center`
- `brow_left_pivot`
- `brow_right_pivot`
- `inner_root`: where the inner wire is attached
- `inner_tip`: the expressive end of the inner wire
- `tail_root`
- `tail_mid`
- `tail_tip`
- `hat_anchor`
- `paper_anchor`
- `bubble_anchor`

Move the anchors first, then draw the shape between them. This prevents
detached joints, drifting props, and hats that float above the character.

## Animation Classes

Every action should declare what kind of motion it is.

The runtime manifest uses `lifecycle` metadata for this:

```yaml
performance_phrases:
  cold_arrow_then_innocent:
    lifecycle: oneshot_return
    minimum_ms: 2600

  sleep_loop:
    lifecycle: loop
    target_state: sleep

  wake_startled:
    lifecycle: transition_to_state
    source_state: sleep
    target_state: idle
```

### Loop

First pose and last pose match. The action can run indefinitely.

Examples:

- idle breathe
- sleepy breathing
- tail slow sway
- quiet companion

### One-Shot Return

The action starts from the current pose, performs a reaction, then returns to a
compatible idle pose.

Examples:

- blink
- wiggle
- jump
- hat tip
- tiny celebrate

### Transition

The action intentionally lands in a different state and should stay there until
another transition plays.

Examples:

- sleep sequence
- wake sequence
- melt
- hide
- retreat to corner
- courtesy suit-up

Do not treat a transition as a one-shot return. That is why melting, sleeping,
and suit-up actions can feel too fast or strangely energetic.

## Performance Phrase Shape

A good performance phrase has four parts:

1. Anticipation
2. Main beat
3. Line delivery or silent thought
4. After-reaction

For Jiajia, the signature phrase is:

```text
observe -> pause -> side-eye -> roast -> inner cover -> eye panic -> tail betrayal -> fake innocence
```

The line should not be the only expressive event. The body should prepare for
the line, deliver it, and then react to having delivered it.

## Speaking Versus Thinking

Spoken roasts should look more restrained because the character is pretending
to be polite:

- inner wire covers the mouth area
- eyes widen afterward
- tail gives away the guilt
- brows soften quickly

Thought roasts can be more smug because the character thinks it got away with
it:

- side-eye can linger
- brows can stay sharper
- tail can sway with confidence
- inner wire can side-smirk instead of cover

This distinction makes speech and thought bubbles feel different even when the
text style is subtle.

## Inner Wire Rules

The inner wire is not a mouth and not a hand. It is a mouth-side gesture.

Allowed:

- cover-oops
- side-smirk
- shy retract
- sleepy droop
- tiny tremble
- paper-fan whisper support

Avoid:

- clear mouth opening and closing
- grabbing objects like a functional hand
- pointing outward too often
- detaching from the body root
- moving the tip while the root appears frozen in the wrong place

Most inner-wire motion should point back toward the character's own face or
body. It should feel self-conscious, not functional.

## Tail Rules

**Bending is CURVATURE INTEGRATION, not offsets.** A pose adds bend per unit
length; bend accumulates into heading angle along the wire; heading integrates
into position. This is how a real flexible rod behaves and it is why the
force visibly travels from the body out to the tail end — measured
displacement grows 0.1 → 1.6 → 6.3 → 13.2px at 25/50/75/100% of the wire.
Lateral-offset models leave the tip behind and cannot conserve length; do not
reintroduce one. The wire is also resampled at uniform arc length first
(`_uniform_wire`), because the bezier joins leave 0.007px segments whose
heading is float noise.

**The wire NEVER stretches.** The tail is steel: a swing bends it, it cannot
lengthen. Every deformed pose passes through `_preserve_length`, which keeps
the deformed shape's direction field but restores each segment's base length,
walking from the pinned root outward — arc length is exact (verified 0.000%
error across all motions). Offsets alone would silently stretch the wire
10-20% on hard swings. Any new deformation channel must come after this rule.

**Deformation is parameterized by ARC LENGTH, not point index.** The tail wire
is sampled per bezier segment, and the segments differ in length ~9x — an
index-based wave crams itself into the short tip segments (sharp kinks at the
segment seams, a wave that sprints and crawls). `_arc_progress` in rig_pose
keeps the bend physically uniform; the root lock-in and envelopes are
calibrated in arc-length terms (long tail: first 35% of physical wire nearly
still, so the tail leaves the body line without an angle clash).

**A tail doesn't only swing — it POSES.** `TAIL_POSTURES` holds expressive
stances from cat body language: `tail_raise_excited` (straight up, tip
quivering — the friendly greeting), `tail_question_hook` (curled into a
question mark — playful curiosity), `tail_bristle` (rigid and trembling —
defensive). Ease in ~260ms, hold with a quiver, ease out. Fright actions
(shake, startled_pop) map to bristle rather than a swing.

**Swinging motions are oscillators, not keyframes.** A cat's tail is a
pendulum: `TAIL_OSCILLATIONS` defines freq/amp/cycles/attack/decay per motion
and `tail_oscillation_pose` samples a continuous damped sine. The oscillator
owns the traveling-wave phase while it runs, so the swing IS the wave rolling
root-to-tip — two separate sine sources multiplied together beat against each
other and read as twitching (that was the old bug). Natural wag frequencies
are 0.5-3Hz; keyframed segments only remain for POSTURE changes (guilty tuck,
sleepy droop, alert snap) where the tail moves to a position and holds.

**Tail-as-tail and tail-as-hand are two different motion systems.** When the
tail is CARRYING a prop (a held cue without `tail_style: "wag"`), it stops
being a tail: hand mode extends it into a steady carry pose
(`TAIL_HAND_POSE`) with only a keeping-it-level micro-sway
(`tail_hand_pose`), and every wag/oscillation request is refused for the
duration — nobody waves a trophy around by wagging. The exceptions are
performances where the tail itself is the actor (ringing the bell, twirling
the pen): those cues mark `tail_style: "wag"` and keep the pendulum. A new
action reclaims the tail immediately; hand mode re-engages 30ms later if the
new action also carries.

**Bend geometry — one bend, at most one fleeting S.** A "bend" is HALF a sine
period (π), so the per-motion `wave` factor reads directly as bend count:
slow sways sit at 0.8-0.85 (one C-curve), the standard wag at ~1.15, and the
hardest lash tops out at 1.35 — a real cat's tail never carries more than one
S even at full speed, and tip-lag follow-through already adds its own hint of
extra curvature. Multi-S wave trains read as a snake, not a tail. The swing
engages from ~18% out of the root so most of the tail visibly participates,
and the free tip runs past the classic silhouette so the whip has an end to
snap.

**Held props never leave the hand.** `build_prop_timeline` shrinks a held
cue's dx/dy to 35% (hand-motion range); the acting comes from rotation and
tilt around the grip point. Only `toss_exit` keeps full displacement — a toss
is the hand letting go. Layering: held props draw ON TOP of the face like
worn props (a mug raised to the face covers it); only floating props go
behind the face.

**The tail tip is the hand — props attach at their natural grip.**
`GRIP_POINTS` maps each holdable shape to its grip in local coordinates: the
pole butt of a flag or sign (the sign rides a stick ABOVE the tail, never
floats mid-air), the mug handle, the suitcase handle, under the trophy base,
the bell's top loop. Held props also ROTATE around that grip point, so a wave
swings like something swung by a hand, not spinning around its own center.

The tail carries subtext.

Use it for:

- guilt
- excitement
- smugness
- panic
- sleepiness
- alertness

Do not make every tail animation large. A small delayed motion can read better
than a wide wag. The best tail acting often contradicts the face: innocent eyes
plus frantic tail is a strong Jiajia beat.

## Prop Rules

Props should support the paperclip's attitude, not replace it.

Good prop uses:

- draft paper as blanket, surfboard, tent, curtain, fan, or stage
- hat and tie for temporary identity states
- status badges for monitoring
- small flat decoration icons for roles

Prop constraints:

- keep the palette flat
- keep stroke weights compatible with the body
- avoid complex shadows
- avoid tiny details that disappear at desktop-pet scale
- attach props to anchors so they follow the body
- never let props permanently cover the eyes or brows unless the action is
  specifically about hiding

For hats, brows should usually render above the hat so the expression remains
readable.

## Costume Rules

Costumes are persistent appearance states. They are not identity props and
should not be cleared when the pal temporarily switches functional identity.

Layer order:

```text
base character -> costume -> identity -> state -> temporary -> effects
```

The first full costume is `britclip`, a genderless British-inspired mode for
the English language setting. 中文叫“英伦夹”. It should use a charcoal hat,
wine-red bow tie, and dark brown cane. It must not use a moustache, beard,
monocle, flag, gendered body language, mouth, hands, or feet.

Costume transitions should be `transition_to_state`, not `oneshot_return`.
Entering a costume should hold the final equipped pose. Exiting a costume should
remove props through a visible reverse action rather than deleting them
instantly.

## Status Animation Rules

Monitoring states should have visual identity beyond bubble text.

Shared agent-state visual metadata lives under `agent_state_visuals` in:

```text
jiajia/animations.yaml
```

Each monitored state should define:

- visual priority
- minimum display time
- whether speech is allowed
- whether a badge is enough
- entry animation
- recovery animation
- fallback when data is stale

Important states should be visually distinct:

- thinking
- editing
- running tools
- waiting for user
- permission needed
- done
- error
- reconnecting
- usage low
- hardware hot

If everything looks like idle plus a sentence, the monitor is not acting yet.

## Body Bend Channel

Beyond squash/offset, the body has a bend channel: `(lean, hunch)` in px at the
top of the character, with the feet planted. `lean` shears the wire sideways
(head tilt, waddle, lean-in); `hunch` sinks the top (slump) or lifts it
(proud chest). The bend is folded into `_actor_point`, so eyes, brows, pupils,
tail, and inner core follow it automatically.

Author per-action bend scripts in `ACTION_BODY_BEND` in `jiajia/body.py` as
`(lean, hunch, delay_ms)` keyframes ending at `(0, 0)`. They run in parallel
with `ACTION_FRAMES` when `_run_large_action` or `_run_window_move` starts.
Three built-in sources also drive the channel:

- idle micro-lean: a slow weight shift while standing (in `_animate`)
- drag dangle: the body trails opposite to pointer velocity, with a pendulum
  settle on release
- doze: a persistent slump while drowsy

Use bend for body language the squash channels cannot express: tilting into a
thought, slumping when sulky, leaning into a dash, chin-up smugness. Keep the
numbers small — ±8-13 lean reads clearly at desktop scale.

## Emotion Prop Layer

Every action carries an animated prop that performs the emotion alongside the
body: a question sign for thinking, a halo for fake innocence, a rain cloud for
sulking, a trophy for celebrating, an umbrella for drop-in, sunglasses for
smugness, a suitcase for relocations.

The system lives in `jiajia/prop_shapes.py`:

- `PROP_SHAPES`: flat vector shapes (line/polygon/oval primitives) in local
  coordinates around the prop's anchor point
- `ACTION_PROP_CUES`: one cue per action — shape, source-space anchor, a
  **story pattern**, duration, and optional `size` / `base_rot` / `over_face`
  / `toss_exit` flags
- `build_prop_timeline` expands a cue into pose keyframes shared verbatim by
  the runtime executor (`_run_action_prop` in body.py) and the GIF renderer,
  so prop performances render identically in both

Every pattern is a story: how this object would really arrive, perform, and
leave. Never use a generic fade/scale entrance — the entrance IS the meaning:

- `brandish` — whipped out from behind the body, waved, put away (flags, wand,
  bell, broom)
- `pull_hold` — produced from behind and held up (signs, suitcase, thermometer)
- `sip` — pulled out, raised to the face, tipped back twice (mug; energy drink
  adds `toss_exit` to chug-and-fling)
- `float_in` — weather drifts in from off-screen, hangs overhead, drifts off;
  the drizzle FX starts only after the cloud has arrived (rain cloud)
- `unfurl` — drops in furled (squash −0.75), pops open with an overshoot, is
  furled and lifted away (umbrella)
- `ring` — hoisted overhead, then rattles ±13° at ~18Hz like a real alarm,
  finally swatted away (alarm clock)
- `wear` — drops onto the face/head, lands with a squish, later lifted off
  (sunglasses, headphones)
- `scan_hold` — raised to the eyes, pans left and right, lowered (binoculars,
  magnifier)
- `bloom` — innocence switches on: spins open from a spark, hovers (optionally
  wobbling), pops out of existence (halo)
- `slam_in` — slams down from above, flattens on impact, shudders, is yanked
  away (alert sign)
- `present` — hoisted high, shown left and right, hugged back in (trophy)
- `pluck` — snatched out of the air folded, shaken open, pressed to the face,
  balled up (tissue)
- `drift_in` — sways down from above like a falling leaf, hovers, melts away
  (snowflake)
- `pen_twirl` — clicked out, twirled a full turn, clicked away (pen)
- `weak_raise` — rises slowly and exhausted, waves feebly, sags back down
  (white surrender flag)
- `spin` — pulled out, then spun hard (pinwheel)

Pose keyframes carry a fifth channel, `squash` (−1..1): negative narrows
(furled umbrella), positive flattens (impact landings, crumpling). It is
volume-ish preserving and applied before rotation.

Beyond the pose timeline, props have three more animation systems, all shared
with the GIF renderer:

- `SHAPE_FX`: primitive-level effects evaluated per frame — cloth ripple on
  the flags, looping rain drizzle under the cloud, steam wiggle over the mug,
  bell jitter on the alarm clock, color flashing on the alert sign /
  thermometer burst / halo glow / wand star, and whole-shape spin for the
  snowflake
- carried-object inertia (`inertia_step`): props swing opposite to their
  horizontal motion, so raises and waves read as held objects with weight
- `toss_exit`: instead of shrinking away, the prop is flung off along a
  spinning arc (sneeze tissue, zoomies energy drink)

**The face acts WITH the prop.** Every prop cue pairs with a staged face
script in `ACTION_FACE_SCRIPTS` — `(at_ms, eyes, brows, look, extras)` beats
synchronized to the prop's story. Never leave an action on one static
expression: the face must NOTICE the prop (glance at it as it appears), REACT
at the story's peak (jolted awake when the alarm rings, eyes shut for the sip,
gaze riding the trophy up), and land an AFTERMATH beat (dozy again once the
clock is swatted away, sheepish after the tissue toss). Design the face by
asking what this character would look at and feel at each beat — not by
picking one pose that vaguely matches the mood. Actions with dedicated pupil
choreography (scan, blink, oops combo) stage eyes/brows only and keep their
gaze logic.

Beats refine themselves with micro-expression extras — use at least one where
the emotion peaks:

- `pupil` (0.68–1.18): fear and shock shrink the pupils (alarm jolt 0.7,
  mercury blowing 0.68); interest and delight dilate them (trophy 1.15,
  pinwheel 1.18)
- `blink`: staged blink events — `quick` (surprise recovery), `double`
  (blinking-too-innocently), `slow` (contempt, savoring), `flutter`
  (overwhelmed / overcaffeinated)
- `brow_l` / `brow_r`: single-brow overrides — the cocked eyebrow is the
  smug signature; a knitted single brow reads as scrutiny
- `tremble` (ms): fast brow shudder — cold, dread, barely holding it together
- `openness` (0–1): explicit eyelid level for continuous arcs — drifting
  shut before the alarm, squeezing shut for the sneeze, eyes closed into the
  music

Runtime channels live in `_schedule_face_script` (plus `_blink_flutter`,
`_brow_tremble`); the renderer compiles the same extras in `face_tracks`,
including blink curves and deterministic tremble.

The generated expression sheets in `assets/paperclip` are distilled into two
more shared vocabularies (see `EYE_FX_SHAPES` / `FACE_DECALS` in
prop_shapes.py):

- `pupil_shape` — the pupils change SHAPE at emotional peaks: `star`
  (starstruck), `heart` (adoring), `spiral` (dizzy), `x` (crashed), `line`
  (deadpan disdain), `squeeze` (>< scrunched), `closed_smile` (the contented
  ∩-arc closed eye). Shaped pupils replace the round ones and ride the gaze.
- `wink` — one eye closes into a smiling arc (`"l"`/`"r"`), the playful
  landing beat.
- `decal` — a symbol hangs on the face for the beat: `tear`, `tears`
  (twin waterfalls), `sweat`, `pale` (scared vertical shading), `shock_lines`
  (impact rays), `sigh` (breath puff), `star_ring` (dizzy halo of stars).
- `blush: True` — cheek blush for shy/embarrassed beats.

Use them the way the sheets do: a shape or decal marks the PEAK of a feeling,
one per beat, never stacked decoration. The no-mouth rule still stands —
never translate mouth shapes from the sheets.

Rules of thumb:

- one prop per action; it enters, performs, and leaves — no permanent litter
- **the tail is the hand**: graspable props set `held: True` and are anchored
  to the live tail tip (`_tail_tip_point`), riding every wag, droop, and
  collapse; `grip_offset` shifts the grip (broom reaches the floor, suitcase
  hangs low). Held props skip the body-squash transform — a carried object
  keeps its own shape
- layering: held/floating props render in front of the body wire but behind
  the face; only wearables (`over_face`) cover the eyes — never bury a prop
  behind the whole character
- size against the body (79px wide): weather should dominate (storm cloud
  ~110px), wearables span the face, handheld items read at 35-60px — check
  every new prop against the silhouette, not in isolation
- floating props follow the body through `_actor_point`, so they ride squash,
  bend, and breathing automatically
- keep SHAPE_FX subtle: one effect idea per shape, amplitudes of 1-3px
- the resting tail must hug the original silhouette — big bends belong to
  actions and moods, not to the idle pose
- identity/costume props (britclip hat, paper props) are a separate system and
  are not part of this layer

## Timing Rules

Animation quality often comes from timing structure rather than duration.

**Frequency floors** (the character is ~79px wide — fast motion smears):

- alternating motion (sways, wags, rattles) needs ≥65ms per half-cycle to
  read; 40-55ms half-cycles are visual noise, not motion. The alarm-clock
  rattle sits right at the floor (72ms) deliberately
- an impact frame (sneeze whip, startled pop, slam) MAY be 40-60ms, but only
  between a long anticipation and a held aftermath — the contrast is what
  sells the speed
- a window-move dash needs ≥120ms per leg so the travel itself is visible;
  80ms across 90px reads as teleporting
- mirror flips (twirl, spins) need ≥80ms per face so each side registers;
  the thin crossing frame stays fast
- decaying oscillations (shake, shiver) should lengthen each half-cycle as
  the amplitude falls — constant-rate decay looks mechanical

**Duration is per-action, not one-size** — match the emotion and the prop:

- reflexes (wiggle, blink) 150-250ms; bounces ~1s; thinking/sulking holds
  1.2-2.5s; transitions (melt, sleep) 3s+
- the body must stay in character for roughly the prop's whole performance:
  if the rain cloud pours for 2.6s, the sulk pose holds ~1.5s+, not 0.9s —
  a body that stands up straight while its prop is still performing breaks
  the scene

Use:

- anticipation before large movement
- eased acceleration and deceleration
- brief holds at emotionally important poses
- delayed motion for tail, brows, and inner wire
- after-reaction before returning to idle

Avoid:

- snapping back to idle immediately
- symmetrical folding when the action should compress downward
- high-frequency idle jitter
- every layer moving at the same time
- every reaction having the same length

As a default, give important poses at least 400-900 ms of readable hold. A
transition state such as melt, sleep, or suit-up can hold longer.

## Semantic Audit

Every action must be describable in one plain sentence — "夹夹戴上墨镜",
"夹夹眨眼并摇铃铛". If the sentence reads as a shrug, the layers disagree about
what the action means.

```powershell
python scripts\audit_actions.py          # full table
python scripts\audit_actions.py --warn   # only the problems
```

The audit prints, per action, the body / prop / face-script durations, the
tail motion model, and a generated one-line summary. It fails when a body
performance quits well before its prop is done (the pal standing up straight
while its rain cloud is still pouring), when a face script runs past its prop,
or when a prop has no face script at all. Move actions get slack — their body
beat is a short travel inside a longer prop story (carrying the suitcase
before and after the hop).

## Validation Checklist

Before calling a major animation done, check:

- It is readable without the bubble text.
- It still looks like Jiajia.
- It has anticipation or a clear reason not to.
- It has after-reaction or a clear reason not to.
- Eyes do not duplicate or leave ghost whites.
- Props follow the body across monitors and after drag.
- Bubbles stay anchored to the pet and do not hide critical badges.
- No white-background residues remain from particles or symbols.
- Nothing important is clipped at the canvas edge.
- The animation can run for 30 seconds without drifting.
- The state returns or persists according to its declared animation class.
- The action's GIF in `docs/media/actions/` has been regenerated.

## Keeping The Action GIF Library In Sync

Every action carries a rendered GIF under `docs/media/actions/`, generated from
the runtime keyframe tables rather than hand-animated. After adding, retiming,
or removing an action, regenerate the library:

```powershell
python scripts\generate_action_gifs.py
```

The generator hashes each action's keyframes, anticipation, follow-through,
acting cue, tail motion, inner gesture, and easing into
`docs/media/actions/manifest.json`. `--check` compares that manifest against the
current code, and `tests/test_action_gifs.py` runs the same comparison, so a
keyframe edit without a re-render fails the test suite.

Because tail and inner-core deformation is shared through
`jiajia/rig_pose.py`, the GIFs cannot drift from the live rig. Props,
decorations, particles, and status tints are runtime canvas items and are not
drawn — the index marks those actions as `body` rather than `full` coverage.

## Review Order

When upgrading animation, polish in this order:

1. Shared rig and anchors.
2. One hero phrase.
3. A small set of reusable poses.
4. Status-specific visual states.
5. Prop performances.
6. Public demo GIFs.

Do not spread effort evenly across dozens of actions before the hero phrase
feels alive.

## Current Hero Phrase

The priority hero phrase is:

```text
cold_arrow_then_innocent
```

Target acting:

```text
quiet observe
thinking tilt
side-eye
brow judgment
line lands
inner cover-oops
eyes panic
frantic innocent blink
tail betrays guilt
short hold
return to soft idle
```

This phrase should be treated as the quality bar for the rest of the system.
