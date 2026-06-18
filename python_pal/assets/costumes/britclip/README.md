# Britclip / 英伦夹

Britclip is the first persistent costume prototype for Paperclip Pal.

## Character direction

Britclip is based on the visual shorthand of an Edwardian club concierge and old-school gentleman:

- charcoal top hat with burgundy band
- burgundy bow tie
- walnut cane with brass tip
- restrained proud expression
- tail wrapped over the cane handle

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

## Asset structure

`britclip-rigged.svg` keeps the body, tail, face, costume props, and anchors in separately named groups. The tail is split from the main body so it can retrieve and hold props during the transformation animation.

Important groups:

```text
body_root
body_wire
costume_back
cane
tail_root
tail_wire
tail_grip
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

## Cane grip and layer order

The cane is part of `costume_back`. The tail is rendered afterward as a foreground layer, so the tail loop visually covers the cane handle at the contact point. This overlap is intentional: it should read as the tail supporting or holding the cane, not as the cane being pasted over the tail.

Required order:

```text
base body
cane / costume_back
tail foreground grip
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
- foreground tail-over-cane grip
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
