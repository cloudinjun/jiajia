# Britclip / 英伦夹

Britclip is the first persistent costume prototype for Paperclip Pal.

## Character direction

Britclip is based on the visual shorthand of an Edwardian club concierge and old-school gentleman:

- charcoal top hat with burgundy band
- burgundy bow tie
- walnut cane with brass tip
- restrained proud expression
- tapered tail tip resting over the cane handle

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

The tail is always a tail. It may imitate the function of a hand through timing, curvature, overlap, and contact, but it must never become a paw, mitten, fist, circular hand, or closed gripping loop.

For the cane pose:

- the main tail keeps its original broad paperclip-wire character
- the final section narrows into `tail_tip`
- the tapered tip curves downward and rests over the cane handle
- the cane remains behind the tail in the layer order
- support is communicated by contact and overlap, not by adding fingers or a round hand shape

## Asset structure

`britclip-rigged.svg` keeps the body, tail, face, costume props, and anchors in separately named groups. The tail is split from the main body so it can retrieve and support props during the transformation animation.

Important groups:

```text
body_root
body_wire
costume_back
cane
tail_root
tail_wire
tail_tip
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

The cane is part of `costume_back`. The tapered tail is rendered afterward as a foreground layer. Its tip overlaps the highest part of the cane handle, so the pose reads as the tail resting on and supporting the cane.

Required order:

```text
base body
cane / costume_back
tapered tail foreground support
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
- tapered non-hand-like tail support pose
- foreground tail-over-cane contact
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
