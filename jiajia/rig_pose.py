"""Pure pose math for the tail and inner core.

These functions take flat base coordinates (source space, already scaled by
PAL_SCALE) plus a pose, and return posed source-space points. They contain no
Tk or canvas dependency so both the live runtime and the offline GIF renderer
can share one definition of how a pose deforms the wire.

Callers apply their own scale/offset transform to the returned points.
"""
from __future__ import annotations

import math
from functools import lru_cache


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


@lru_cache(maxsize=8)
def _segment_lengths(base_coords: tuple[float, ...]) -> tuple[float, ...]:
    """Length of each wire segment in the base geometry."""
    n = len(base_coords) // 2
    out = []
    for i in range(1, n):
        dx = base_coords[i * 2] - base_coords[(i - 1) * 2]
        dy = base_coords[i * 2 + 1] - base_coords[(i - 1) * 2 + 1]
        out.append(math.hypot(dx, dy))
    return tuple(out)


_WIRE_SAMPLES = 96


@lru_cache(maxsize=8)
def _uniform_wire(base_coords: tuple[float, ...]) -> tuple[float, ...]:
    """Resample the wire at uniform arc length.

    Bezier sampling leaves near-degenerate segments at the curve joins (down
    to 0.007px here), whose heading is pure float noise — integrating
    curvature through them produced phantom kinks. Uniform segments also make
    the curvature integral clean.
    """
    n = len(base_coords) // 2
    if n < 2:
        return base_coords
    pts = [(base_coords[i * 2], base_coords[i * 2 + 1]) for i in range(n)]
    acc = [0.0]
    for i in range(1, n):
        acc.append(acc[-1] + math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]))
    total = acc[-1]
    if total <= 0:
        return base_coords
    out: list[float] = []
    j = 0
    for s in range(_WIRE_SAMPLES):
        target = total * s / (_WIRE_SAMPLES - 1)
        while j < n - 2 and acc[j + 1] < target:
            j += 1
        span = acc[j + 1] - acc[j]
        t = (target - acc[j]) / span if span > 1e-12 else 0.0
        out.append(pts[j][0] + (pts[j + 1][0] - pts[j][0]) * t)
        out.append(pts[j][1] + (pts[j + 1][1] - pts[j][1]) * t)
    return tuple(out)


@lru_cache(maxsize=8)
def _base_frame(base_coords: tuple[float, ...]) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Per-segment (length, heading angle, turn angle) of the base wire.

    The turn angles are the wire's own natural curvature — `stiffen` works by
    cancelling them, which straightens the tail into a rigid raised line.
    """
    lengths = _segment_lengths(base_coords)
    n = len(base_coords) // 2
    angles = []
    for i in range(1, n):
        dx = base_coords[i * 2] - base_coords[(i - 1) * 2]
        dy = base_coords[i * 2 + 1] - base_coords[(i - 1) * 2 + 1]
        angles.append(math.atan2(dy, dx))
    turns = [0.0]
    for i in range(1, len(angles)):
        d = angles[i] - angles[i - 1]
        while d > math.pi:
            d -= 2.0 * math.pi
        while d < -math.pi:
            d += 2.0 * math.pi
        turns.append(d)
    return lengths, tuple(angles), tuple(turns)


# Curvature gains: convert pose channel units (authored in px of tip travel)
# into radians of bend per px of wire. Calibrated so the historical channel
# magnitudes still read at the same visual strength.
_SWAY_GAIN = 0.00098
_CURL_GAIN = 0.00075
_DROOP_GAIN = 0.00095
_TUCK_GAIN = 0.00130
_STIFF_GAIN = 0.075


@lru_cache(maxsize=8)
def _arc_progress(base_coords: tuple[float, ...]) -> tuple[float, ...]:
    """Per-point progress by cumulative ARC LENGTH, not point index.

    The tail wire is sampled per bezier segment with uniform parameter steps,
    but the segments differ in length by ~9x — index-based progress crams most
    of the deformation wave into a few physical centimeters at the tip
    (kinks!) and makes the traveling wave sprint on long segments and crawl on
    short ones. Arc-length progress keeps the bend physically uniform.
    """
    n = len(base_coords) // 2
    acc = [0.0]
    for i in range(1, n):
        dx = base_coords[i * 2] - base_coords[(i - 1) * 2]
        dy = base_coords[i * 2 + 1] - base_coords[(i - 1) * 2 + 1]
        acc.append(acc[-1] + math.hypot(dx, dy))
    total = acc[-1] or 1.0
    return tuple(a / total for a in acc)


def bend_point(
    x: float,
    y: float,
    lean: float = 0.0,
    hunch: float = 0.0,
    *,
    pivot_y: float,
    top_y: float,
) -> tuple[float, float]:
    """Bend a body point around the ground pivot.

    `lean` shears the wire sideways (px at the very top, weighted by height so
    the feet stay planted); `hunch` sinks the top (positive = slump, negative =
    proud chest lift). Apply before scaling so mirror flips carry the bend.
    """
    span = pivot_y - top_y
    if span <= 0:
        return (x, y)
    h = (pivot_y - y) / span
    if h <= 0.0:
        return (x, y)
    if h > 1.0:
        h = 1.0
    return (x + lean * h ** 1.35, y + hunch * h ** 1.6)


def posed_tail_points(
    base_coords: tuple[float, ...],
    sway: float = 0.0,
    curl: float = 0.0,
    droop: float = 0.0,
    tuck: float = 0.0,
    stiffen: float = 0.0,
    *,
    tail_mode: str = "short",
    s_phase: float = 0.0,
    tip_pose: tuple[float, float, float, float, float] | None = None,
    wave_factor: float | None = None,
    engage: tuple[float, float] | None = None,
) -> list[tuple[float, float]]:
    """Deform the tail wire for a 5-channel tail pose.

    `sway` travels along the tail as a sine wave (`s_phase` advances it), while
    curl/droop/tuck/stiffen are static biases weighted toward the tip.

    `tip_pose` is an optional delayed copy of the same 5 channels: points near
    the root play the current pose, points near the tip play the delayed one,
    so the wire bends through motion (follow-through) instead of swinging
    rigidly in one piece.

    `engage` is (start, full) in arc-length progress: where the swing begins
    to participate and where it reaches full strength. The default engages
    the whole tail; a tip-only motion — ringing a bell, flicking the tip —
    passes something like (0.55, 0.95) so the wire moves from the wrist out,
    not from the shoulder.

    The model is CURVATURE INTEGRATION, the way a real flexible rod bends: a
    pose adds bend per unit length, bend accumulates into heading angle along
    the wire, and heading integrates into position. Two consequences matter —
    the force travels root→tip so the tip swings the widest arc (offsets alone
    left the tip behind), and the wire's length is exactly conserved because
    segments only ever rotate.
    """
    base = _uniform_wire(tuple(base_coords))
    lengths, base_angles, base_turns = _base_frame(base)
    arc = _arc_progress(base)
    if not lengths:
        return [(base[0], base[1])] if len(base) >= 2 else []

    if tail_mode == "long":
        k = (wave_factor if wave_factor is not None else 1.1) * math.pi
        g0, g1 = engage if engage is not None else (0.0, 0.35)
        env_base, env_slope = 0.25, 0.75
    else:
        k = (wave_factor if wave_factor is not None else 0.9) * math.pi
        g0, g1 = engage if engage is not None else (0.0, 0.4)
        env_base, env_slope = 0.35, 0.65

    points: list[tuple[float, float]] = [(base[0], base[1])]
    heading_extra = 0.0
    for i, seg_len in enumerate(lengths):
        progress = arc[i + 1]
        # follow-through blend: root plays the current pose, tip plays the
        # delayed one, so the bend rolls outward through the wire
        if tip_pose is not None:
            w = _smoothstep(progress)
            p_sway = sway + (tip_pose[0] - sway) * w
            p_curl = curl + (tip_pose[1] - curl) * w
            p_droop = droop + (tip_pose[2] - droop) * w
            p_tuck = tuck + (tip_pose[3] - tuck) * w
            p_stiffen = stiffen + (tip_pose[4] - stiffen) * w
        else:
            p_sway, p_curl, p_droop, p_tuck, p_stiffen = sway, curl, droop, tuck, stiffen

        gate = _smoothstep((progress - g0) / max(1e-6, g1 - g0))
        envelope = gate * (env_base + env_slope * progress)
        mid_bias = math.sin(progress * math.pi)

        # bend added per unit length (radians/px)
        kappa = p_sway * _SWAY_GAIN * math.sin(progress * k + s_phase) * envelope
        kappa += p_curl * _CURL_GAIN * mid_bias * gate
        kappa += p_droop * _DROOP_GAIN * progress
        kappa += p_tuck * _TUCK_GAIN * progress
        heading_extra += kappa * seg_len
        # stiffen cancels the wire's own curvature: the tail goes rigid
        heading_extra -= p_stiffen * _STIFF_GAIN * base_turns[i]

        angle = base_angles[i] + heading_extra
        px, py = points[-1]
        points.append((
            px + math.cos(angle) * seg_len,
            py + math.sin(angle) * seg_len,
        ))
    return points


# Curvature gains for the inner wire, calibrated so the existing gesture
# amplitudes keep roughly their old on-screen travel. See posed_chin_points.
_CHIN_TIP_GAIN = 0.000084
_CHIN_MID_GAIN = 0.000116


def posed_chin_points(
    base_coords: tuple[float, ...],
    amount_x: float = 0.0,
    amount_y: float = 0.0,
    mid_x: float = 0.0,
    mid_y: float = 0.0,
) -> list[tuple[float, float]]:
    """Pose the inner core by BENDING it, never by stretching it.

    The core is a length of the same steel as the body, and it is the pal's
    hand: it presses against the mouth and its tip articulates. So it is posed
    the way the tail is — integrate a curvature profile along the wire and let
    position fall out of the headings. Two consequences matter:

      * length is exactly preserved, because every segment keeps the length it
        had and only its direction changes. The previous displacement model
        stretched the wire by up to 4.4%, which is what read as elastic.
      * the bend is a C, not an S. Curvature here keeps one sign along the
        wire; the old model subtracted a full sine period, bowing the wire one
        way then the other, which is a whip and not an arm.

    `amount_*` drives the free tip, `mid_*` bows the middle. The array runs
    from the free upper tip toward the body joint, so integration walks it
    backwards: the joint is the anchor, and error accumulates toward the tip
    where it belongs.
    """
    base = _uniform_wire(tuple(base_coords))
    pair_count = max(1, len(base) // 2)
    if pair_count < 3:
        return [(base[i * 2], base[i * 2 + 1]) for i in range(pair_count)]

    # walk root -> tip, then flip back to the caller's tip -> root order
    reversed_coords: list[float] = []
    for index in range(pair_count - 1, -1, -1):
        reversed_coords.extend((base[index * 2], base[index * 2 + 1]))
    rooted = tuple(reversed_coords)

    lengths, base_angles, _turns = _base_frame(rooted)
    arc = _arc_progress(rooted)

    points = [(rooted[0], rooted[1])]
    heading_extra = 0.0
    for index, seg_len in enumerate(lengths):
        progress = arc[index + 1]          # 0 at the joint, 1 at the free tip
        # the joint is clamped, so bend has to grow away from it
        anchor_gate = _smoothstep(min(1.0, progress / 0.28))
        # tip drive: curvature rises toward the free end
        tip_share = anchor_gate * progress
        # mid drive: a single hump, so the wire bows once
        mid_share = anchor_gate * math.sin(progress * math.pi)

        kappa_x = -amount_x * _CHIN_TIP_GAIN * tip_share
        kappa_x += -mid_x * _CHIN_MID_GAIN * mid_share
        kappa_y = amount_y * _CHIN_TIP_GAIN * tip_share
        kappa_y += mid_y * _CHIN_MID_GAIN * mid_share
        # one bending plane: the two drives combine into a single signed
        # curvature, which is what keeps the result a C rather than an S
        heading_extra += (kappa_x + kappa_y) * seg_len

        angle = base_angles[index] + heading_extra
        px, py = points[-1]
        points.append((px + math.cos(angle) * seg_len, py + math.sin(angle) * seg_len))

    points.reverse()
    return points
