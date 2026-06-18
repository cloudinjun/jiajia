# Britclip / 英伦夹

Britclip is the first persistent costume prototype for Paperclip Pal.

## Character direction

Britclip is based on the visual shorthand of an Edwardian club concierge and old-school gentleman:

- charcoal top hat with burgundy band
- burgundy bow tie
- walnut cane with brass tip
- restrained proud expression
- the natural rounded tail end resting over the cane handle

The costume deliberately avoids a monocle, moustache, flag motif, mouth, hands, and feet. The goal is a readable gentleman silhouette without replacing the base paperclip character.

## Flat-vector rule

The source asset follows the same flat style as the base character:

- solid fills only
- no gradients
- no highlights
- no shadows
- no opacity-based lighting effects
- simple dark outlines where separation is needed

Different flat colors may separate the hat crown, hat band, bow knot, cane body, and brass tip, but none of those layers should simulate lighting.

## Tail semantics

The tail is always drawn in exactly the same way as the body wire:

- one open stroked path
- `#AEAEAE`
- `stroke-width="30"`
- rounded line cap
- rounded line join
- no custom taper polygon
- no added grip loop or hand-shaped endpoint

It may imitate a supporting gesture through timing, curvature, contact, and foreground overlap, but its construction must remain the original paperclip wire construction.

For the cane pose, the natural rounded cap at the end of `tail_wire` rests over the cane handle. The cane is rendered behind it. This communicates support without changing the tail into a paw, mitten, fist, or hand.

## Asset structure

`britclip-rigged.svg` keeps the body, tail, face, costume props, and anchors in separately named groups. The tail is split from the body path for animation control, but both paths use the same visual drawing method.

Important groups:

```text
body_root
body_wire
costume_back
cane
tail_root
tail_wire
costume_front
top_hat
bow_tie
left_eye_white
right_eye_white
left_pupil
right_pupil
left_brow
right_brow
rig_anchors
```

## Cane support and layer order

The cane is part of `costume_back`. The tail is rendered afterward as a foreground layer. The rounded end of the tail touches the highest visible point of the cane handle, while the cane bottom aligns with the body baseline.

Required order:

```text
base body
cane / costume_back
natural tail-wire foreground support
hat and bow tie / costume_front
functional identity prop
state mark
performance accent
bubble
```

## Persistent lifecycle

This is a costume, not an identity decoration. Once equipped, it should remain visible while functional identities such as `agent_supervisor`, `thermal_technician`, or `bug_coroner` change underneath it.

## Current status

Completed:

- static equipped SVG
- flat no-highlight/no-shadow style pass
- separate tail and prop layers
- tail restored to the same stroke construction as the body
- foreground tail-over-cane contact
- cane and body baseline alignment
- named anchors
- enter/exit storyboard
- persistent costume specification

Not yet wired into the Python runtime:

- language detection
- costume state storage
- SVG preview/export pipeline
- transformation playback
- persistent costume composition with identity decorations

The SVG is intended as the visual source of truth for the next animation pass.
