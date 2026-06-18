# Britclip / 英伦夹

Britclip is the first persistent costume prototype for Paperclip Pal.

## Character direction

Britclip is based on the visual shorthand of an Edwardian club concierge and old-school gentleman:

- charcoal top hat with burgundy band
- burgundy bow tie
- walnut cane with brass tip
- restrained proud expression
- tail wrapped around the cane handle

The costume deliberately avoids a monocle, moustache, flag motif, mouth, hands, and feet. The goal is a readable gentleman silhouette without replacing the base paperclip character.

## Asset structure

`britclip-rigged.svg` keeps the body, tail, face, costume props, and anchors in separately named groups. The tail is split from the main body so it can retrieve and hold props during the transformation animation.

Important groups:

```text
body_root
body_wire
tail_root
tail_wire
tail_grip
left_eye_white
right_eye_white
left_pupil
right_pupil
left_brow
right_brow
costume_britclip
top_hat
bow_tie
cane
rig_anchors
```

## Persistent lifecycle

This is a costume, not an identity decoration. Once equipped, it should remain visible while functional identities such as `agent_supervisor`, `thermal_technician`, or `bug_coroner` change underneath it.

Recommended render order:

```text
base body
persistent costume
functional identity prop
state mark
performance accent
bubble
```

## Current status

Completed:

- static equipped SVG
- separate tail and prop layers
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
