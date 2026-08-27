"""Audit the choreography that actually runs: jiajia/animations.yaml.

The manifest is the live source. `_run_performance_phrase` calls the player
first and returns as soon as the manifest scheduled anything, so the table in
performance.py is only reached when the manifest has nothing — which, for the
primary phrases, is never. An audit that reads performance.py is therefore
auditing a path the user does not see.

A step may cut an action short on purpose, but not so short that nothing reads.
Face-only micro actions are exempt: an expression lands on the first frame and
then holds. Body, tail and inner-wire actions have to travel.

Usage:
    python scripts/audit_phrases.py            # table
    python scripts/audit_phrases.py --warn     # exit 1 if anything is too short
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jiajia.animation_manifest import load_animation_manifest
from jiajia.body import JiajiaApp
from jiajia.performance import MIN_READABLE_FRACTION

MANIFEST_PATH = ROOT / "jiajia" / "animations.yaml"


class _DurationProbe:
    """Minimal stand-in so durations resolve without opening a window."""

    animation_resolver = type("R", (), {"resolve": staticmethod(
        lambda name: type("A", (), {"action": name, "performance": ""})()
    )})()


def real_duration_ms(action: str) -> int:
    """How long the action actually runs. 0 means face-only or unknown."""
    try:
        return int(JiajiaApp._animation_duration_ms(_DurationProbe(), action))
    except Exception:
        return 0


def audit() -> list[str]:
    manifest = load_animation_manifest(MANIFEST_PATH)
    problems: list[str] = []
    rows: list[tuple[str, str, str, str, str]] = []

    for name in sorted(manifest.performances):
        definition = manifest.performances[name]
        seen: list[str] = []
        for step in definition.sequence:
            if not step.action:
                continue
            real = real_duration_ms(step.action)
            if not real:
                rows.append((name, step.action, "face-only", "-", "ok"))
                continue

            if step.wait_action_duration and not step.duration_ms:
                budget = max(0, real - max(0, step.overlap_ms))
                note = f"await-{step.overlap_ms}" if step.overlap_ms else "await"
                verdict = "ok"
            else:
                budget = step.duration_ms
                note = f"{budget}ms"
                share = budget / real
                if share < MIN_READABLE_FRACTION:
                    verdict = f"CUT {share:.0%}"
                    problems.append(
                        f"{name}/{step.action}: {budget}ms of {real}ms "
                        f"({share:.0%}, floor {MIN_READABLE_FRACTION:.0%})"
                    )
                else:
                    verdict = f"{share:.0%}"

            if step.action in seen:
                problems.append(f"{name}: starts {step.action} twice")
                verdict += " REPEAT"
            seen.append(step.action)
            rows.append((name, step.action, note, f"{real}ms", verdict))

    if "--quiet" not in sys.argv:
        current = ""
        for phrase, action, given, real, verdict in rows:
            if phrase != current:
                print(f"\n{phrase}")
                current = phrase
            print(f"    {action:24s} {given:>10s}  real {real:>8s}  {verdict}")
    return problems


def main() -> int:
    problems = audit()
    print(f"\n{len(problems)} problem(s):")
    for problem in problems:
        print(f"  - {problem}")
    return 1 if problems and "--warn" in sys.argv else 0


if __name__ == "__main__":
    raise SystemExit(main())
