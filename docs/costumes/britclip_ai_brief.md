# Britclip Costume Brief

This is the first AI-refined SVG hero costume for Jiajia.

The costume is genderless. Do not design it as a man, gentleman, butler,
lord, detective, or mascot with a gendered body. The target is Britclip:
a British-inspired mode for a tiny paperclip, formal, restrained, dry, and
slightly judgmental, while still visibly harmless.

## Identity

```yaml
costume_id: britclip
display_name: Britclip
zh_name: 英伦夹
role: genderless British-inspired costume
trigger: explicit English language mode
runtime_lifetime: costume
```

The costume should suggest old-fashioned British dryness and understatement,
not human gender.

## Visual Direction

Use:

- charcoal hat
- wine-red bow tie
- short dark brown crook-handle walking cane
- restrained posture
- proud but not arrogant brows
- controlled side-eye

Avoid:

- moustache or beard
- monocle
- British flag
- royal costume
- exaggerated butler uniform
- masculine suit body
- staff, wand, sceptre, pointer, or tall rod
- hands, feet, mouth, or face redesign
- changing the paperclip silhouette

The character remains a mouthless paperclip. Costume props are accessories, not
new anatomy.

## Required Deliverables

Place final AI output candidates under:

```text
jiajia/assets/costumes/britclip/
```

Preferred files:

```text
britclip_master.svg
britclip_enter_preview.svg.html
britclip_exit_preview.svg.html
britclip_keyframes.svg
britclip_notes.md
```

Optional preview exports:

```text
preview-1x.gif
preview-4x.gif
first-frame.png
last-frame.png
```

## SVG Layer Contract

The base character must keep these stable groups:

```text
body_main
tail_wire
inner_wire
left_eye_white
right_eye_white
left_pupil
right_pupil
left_brow
right_brow
```

The costume must use these groups:

```text
britclip_costume
  top_hat
    hat_crown
    hat_brim
    hat_band
  bow_tie
    bow_left
    bow_knot
    bow_right
  cane
    cane_handle
    cane_shaft_upper
    cane_shaft_lower
    cane_tip
```

Do not merge the costume into `body_main`. Do not redraw the face. Do not put
the hat above the brows in final z-order.

## Rig Anchors

Use the anchor names from:

```text
jiajia/rig.yaml
```

Required anchors:

```yaml
body_root:
body_main:
tail_root:
tail_mid:
tail_tip:
tail_grip:
prop_spawn_anchor:
hat_anchor:
bow_tie_anchor:
cane_anchor:
ground_anchor:
```

The tail may carry props through `tail_grip`, but the tail root must stay
attached. Any pose where the tail looks detached fails review.

## Enter Animation

Runtime lifecycle:

```yaml
lifecycle: transition_to_state
target_costume: britclip
```

Target length: about 3.1 seconds.

Storyboard:

```text
0-300ms
Notice English mode. Eyes look toward tail. Brows lift. Body straightens.

300-1050ms
Tail reaches behind body. Hat appears from prop_spawn_anchor. Hat opens and
lands on hat_anchor. Brim rebounds twice, gently.

1050-1750ms
Tail pulls out folded wine-red strip. Strip opens into bow tie and attaches at
bow_tie_anchor. Bow tie bounces left/right once.

1750-2550ms
Tail unfolds a short crook-handle walking cane in two restrained clicks. Cane
lands at cane_anchor with tip near ground_anchor. Tail rests over the crook
handle. The cane must not read as a staff, wand, sceptre, pointer, or tall rod.

2550-3100ms
Body straightens. Hat settles. Cane taps once. Tiny formal bow. Hold final
costume.
```

Final pose:

```yaml
costume_id: britclip
phase: equipped
hat: attached_to_hat_anchor
bow_tie: attached_to_bow_tie_anchor
cane: attached_to_cane_anchor
tail: cane_hold
eyes: restrained_side_eye
brows: proud_soft
```

## Exit Animation

Runtime lifecycle:

```yaml
lifecycle: transition_to_state
source_costume: britclip
target_costume: none
```

Storyboard:

```text
Tail lifts cane -> cane folds away.
Tail unties bow tie -> bow tie folds into a strip.
Tail removes hat -> small polite hat tip.
Hat flattens and returns to prop_spawn_anchor.
Body returns to ordinary paperclip posture.
```

Do not delete props instantly.

## Costume-Aware Action Mapping

When the costume is equipped, these ordinary actions can be interpreted with
Britclip flavor:

```yaml
idle_breathe: courtesy_idle
tail_wag: cane_tap
happy_bounce: restrained_celebrate
thinking_tilt: courtesy_consider
blink: dignified_blink
roast_and_scoot: tip_hat_and_scoot
```

First runtime placeholders:

```yaml
tip_hat: hat_tip_oops
bow_tie_check: tail_tip_flick
cane_tap: tail_tip_flick
polite_bow: nod
```

## Acceptance Checklist

- Reads as genderless.
- Reads as Britclip / 英伦夹, not a gendered human costume.
- No moustache, beard, monocle, flag, hands, feet, or mouth.
- Hat does not cover brows.
- Cane reads as a walking cane, not a wizard staff or pointer.
- Tail never detaches from `tail_root`.
- Props follow body motion and screen dragging.
- Final frame can persist as a costume without looking mid-animation.
- First and last frames are different because this is a transition.
- At 1x desktop-pet size, hat, bow tie, and cane are readable.
- The base paperclip silhouette remains recognizable.
