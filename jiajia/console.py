"""Make stdout able to carry what this app actually prints.

Jiajia's lines are Chinese by default and the evaluation report draws bars out
of block characters. A Windows console defaults to a regional code page rather
than UTF-8, so printing either one raised UnicodeEncodeError and killed the
process — which is how both the self-test and the evaluation gate came to fail
on every CI runner while passing on a UTF-8 terminal.

Nothing here changes what is printed. It only stops the terminal's encoding
from deciding whether the program lives.
"""

from __future__ import annotations

import sys


def make_printable() -> None:
    """Put stdout and stderr into UTF-8, replacing anything they still cannot take."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError, ValueError):
            # A stream that is not a real text stream (a pipe a caller replaced,
            # a test double) cannot be reconfigured and does not need to be.
            pass
