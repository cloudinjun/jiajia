"""The command-line entry points must survive a console that is not UTF-8.

Both of them print non-ASCII by design: the self-test prints one of Jiajia's
lines, which are Chinese by default, and the evaluation report draws its bars
out of block characters. A Windows console defaults to a regional code page,
so both raised UnicodeEncodeError and exited non-zero — on every CI runner,
and for any user who ran them in a default shell. They passed locally only
because that terminal happened to be UTF-8, which is exactly the kind of
difference a test should be holding still.

PYTHONIOENCODING reproduces the runner's console without needing one.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NARROW = "cp1252"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONIOENCODING=NARROW)
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


class NarrowConsoleTest(unittest.TestCase):
    def test_self_test_survives(self) -> None:
        done = _run(["-m", "jiajia.main", "--self-test"])
        self.assertEqual(done.returncode, 0, f"self-test failed under {NARROW}:\n{done.stderr}")
        self.assertNotIn("UnicodeEncodeError", done.stderr)

    def test_evaluation_survives(self) -> None:
        done = _run(["eval/run_eval.py"])
        self.assertEqual(done.returncode, 0, f"eval failed under {NARROW}:\n{done.stderr}")
        self.assertNotIn("UnicodeEncodeError", done.stderr)
        self.assertIn("All checks passed", done.stdout)
