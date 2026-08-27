"""Who owns which visual channel right now.

The pal writes to several independent channels — body, window position, tail,
inner wire, body bend, face, prop, blink — and each one used to be driven by its
own timer with no idea who queued it. Cancellation was "whoever writes next
wins": a new action called `_cancel_large_action`, a new tail motion called
`_cancel_tail_wag`, and so on. None of those cancels knew *whose* motion they
were ending.

The failure that produces is a stale callback from a finished performance
reaching in and resetting the expression, clearing the prop, or zeroing the tail
of the performance that replaced it — and the reverse, where cancelling a new
performance tears down channels an older one still owns.

This module does not schedule anything and does not decide priority. The
existing VisualStatePlan already decides whether a new performance may preempt
an old one. All this adds is bookkeeping: which run owns which channel, so a
callback can ask "am I still the current owner?" before it writes, and a
cancellation can tear down exactly the channels its own run claimed.

Deliberately NOT channels: costume, identity decorations and status badges.
Those outlive any single performance, and treating them as owned would let a
finishing phrase strip the pal's clothes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The fixed set. New channels should be rare and deliberate; a channel that is
# not listed here is simply not owned, and behaves as it did before.
CHANNELS: frozenset[str] = frozenset({
    "body",     # large action frames
    "window",   # window position moves
    "tail",     # tail motion or posture
    "inner",    # inner wire gesture
    "bend",     # body bend / lean
    "face",     # eye + brow pose, face scripts
    "prop",     # action prop and its timeline
    "blink",    # scheduled blink events
})


@dataclass
class PerformanceRun:
    """One playthrough of a performance, and the channels it claimed."""

    run_id: int
    name: str
    priority: int = 0
    interruptible: bool = True
    lifecycle: str = ""
    owned: set[str] = field(default_factory=set)
    cancelled: bool = False

    def claim(self, *channels: str) -> None:
        for channel in channels:
            if channel in CHANNELS:
                self.owned.add(channel)

    @property
    def alive(self) -> bool:
        return not self.cancelled


class RunRegistry:
    """Tracks the current run and per-channel ownership.

    Ownership is last-claim-wins, which matches how the channels already
    behaved. The difference is that the previous owner can now find out.
    """

    def __init__(self) -> None:
        self._next_id = 1
        self._owner: dict[str, int] = {}
        self.current: PerformanceRun | None = None

    def begin(
        self,
        name: str,
        *,
        priority: int = 0,
        interruptible: bool = True,
        lifecycle: str = "",
    ) -> PerformanceRun:
        run = PerformanceRun(
            run_id=self._next_id,
            name=name,
            priority=priority,
            interruptible=interruptible,
            lifecycle=lifecycle,
        )
        self._next_id += 1
        self.current = run
        return run

    def claim(self, run: PerformanceRun | None, *channels: str) -> None:
        if run is None:
            return
        run.claim(*channels)
        for channel in channels:
            if channel in CHANNELS:
                self._owner[channel] = run.run_id

    def owns(self, run: PerformanceRun | None, channel: str) -> bool:
        """Whether this run may still write to the channel."""
        if run is None:
            return True  # unowned work (idle, ambient) is not gated
        if run.cancelled:
            return False
        return self._owner.get(channel) == run.run_id

    def is_current(self, run: PerformanceRun | None) -> bool:
        return run is None or (self.current is run and not run.cancelled)

    def cancel(self, run: PerformanceRun | None) -> set[str]:
        """Mark the run dead and report the channels it still owned.

        The caller tears those down. Channels already taken over by a newer run
        are not returned, because tearing them down would damage that run —
        which is the bug this exists to prevent.
        """
        if run is None:
            return set()
        run.cancelled = True
        still_owned = {
            channel for channel in run.owned if self._owner.get(channel) == run.run_id
        }
        for channel in still_owned:
            self._owner.pop(channel, None)
        if self.current is run:
            self.current = None
        return still_owned

    def cancel_current(self) -> set[str]:
        return self.cancel(self.current)
