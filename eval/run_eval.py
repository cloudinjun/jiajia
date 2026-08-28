"""Score Jiajia's behavior policy against hand-written ground truth.

The expectations in scenarios.yaml are written from the *design intent* — the
interruption policy table and the motion grammar — not from reading the
implementation. That separation is the whole point: if the two disagree, either
the code drifted or the intent was never actually encoded, and both are worth
knowing.

Run:
    python -m eval.run_eval              # summary
    python -m eval.run_eval --verbose    # every failure, with the reason
    python -m eval.run_eval --json       # machine-readable, for CI
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jiajia.animation_resolver import AnimationResolver
from jiajia.ears import EarContext
from jiajia.interruptibility import assess_interruptibility
from jiajia.soul import _load_yaml

SCENARIOS = Path(__file__).resolve().parent / "scenarios.yaml"

# The dimensions a scenario can be scored on. A scenario contributes to a
# dimension only if it declares an expectation that touches it.
DIMENSIONS = (
    "interruption_appropriateness",
    "privacy_compliance",
    "semantic_fit",
    "recovery_correctness",
)


def _normalize(data: dict) -> dict:
    """The mini parser produces dicts where lists are expected; fix that up."""
    for section in ("interruption", "resolver"):
        value = data.get(section)
        if isinstance(value, dict):
            data[section] = [v for v in value.values() if isinstance(v, dict)]
        elif value is None:
            data[section] = []
    return data


@dataclass
class Result:
    scenario_id: str
    dimension: str
    passed: bool
    detail: str = ""


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, scenario_id: str, dimension: str, passed: bool, detail: str = "") -> None:
        self.results.append(Result(scenario_id, dimension, passed, detail))

    def by_dimension(self) -> dict[str, tuple[int, int]]:
        table: dict[str, tuple[int, int]] = {}
        for r in self.results:
            ok, total = table.get(r.dimension, (0, 0))
            table[r.dimension] = (ok + (1 if r.passed else 0), total + 1)
        return table

    @property
    def failures(self) -> list[Result]:
        return [r for r in self.results if not r.passed]


def _context(raw: dict) -> EarContext:
    return EarContext(
        active_window_title=str(raw.get("active_window_title", "")),
        active_process=str(raw.get("active_process", "")),
        app_category=str(raw.get("app_category", "unknown")),
        focus_seconds=float(raw.get("focus_seconds", 0.0)),
        idle_seconds=float(raw.get("idle_seconds", 0.0)),
        window_switches_per_minute=int(raw.get("window_switches_per_minute", 0)),
        activity_level=str(raw.get("activity_level", "active")),
        is_fullscreen=bool(raw.get("is_fullscreen", False)),
        behavior_tags=list(raw.get("behavior_tags") or []),
    )


def score_interruption(scenarios: list[dict], report: Report) -> None:
    for s in scenarios:
        sid = str(s.get("id", "<unnamed>"))
        expect = s.get("expect") or {}
        dimension = str(s.get("dimension", "interruption_appropriateness"))
        now = datetime(2026, 1, 5, int(s.get("hour", 14)), 0, 0)

        actual = assess_interruptibility(
            _context(s.get("context") or {}),
            focus_mode=bool(s.get("focus_mode", False)),
            quiet_remaining_seconds=float(s.get("quiet_remaining_seconds", 0)),
            now=now,
        )

        checks = {
            "mode": actual.mode,
            "allow_speech": actual.allow_speech,
            "allow_animation": actual.allow_animation,
            "allow_badges": actual.allow_badges,
            "visual_only_critical": actual.visual_only_critical,
        }
        for key, want in expect.items():
            if key not in checks:
                continue
            got = checks[key]
            passed = got == want
            report.add(
                sid,
                dimension,
                passed,
                "" if passed else f"{key}: expected {want!r}, got {got!r}  ({s.get('rationale','')})",
            )


def score_resolver(scenarios: list[dict], report: Report) -> None:
    performances = set()
    for s in scenarios:
        perf = s.get("performances")
        if perf:
            performances.update(perf if isinstance(perf, list) else [perf])
    resolver = AnimationResolver(performances=performances or None)

    for s in scenarios:
        sid = str(s.get("id", "<unnamed>"))
        dimension = str(s.get("dimension", "semantic_fit"))
        resolved = resolver.resolve(str(s.get("model_output", "")), fallback=str(s.get("fallback", "blink")))

        want_action = s.get("expect_action")
        if want_action is not None:
            got = resolved.performance if resolved.kind == "performance" else resolved.action
            passed = got == want_action
            report.add(
                sid,
                dimension,
                passed,
                "" if passed else f"expected {want_action!r}, got {got!r}  ({s.get('rationale','')})",
            )

        want_kind = s.get("expect_kind")
        if want_kind is not None:
            passed = resolved.kind == want_kind
            report.add(
                sid,
                dimension,
                passed,
                "" if passed else f"kind: expected {want_kind!r}, got {resolved.kind!r}",
            )

        if s.get("expect_never_raw"):
            # The resolver must never hand an unknown name straight through.
            passed = resolved.action in resolver.actions or resolved.kind == "performance"
            report.add(
                sid,
                dimension,
                passed,
                "" if passed else f"unknown name {resolved.action!r} escaped the resolver",
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print every failure")
    parser.add_argument("--json", action="store_true", help="emit machine-readable output")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on any failure")
    args = parser.parse_args(argv)

    data = _normalize(_load_yaml(SCENARIOS) or {})
    report = Report()
    score_interruption(data.get("interruption", []), report)
    score_resolver(data.get("resolver", []), report)

    table = report.by_dimension()
    total_ok = sum(ok for ok, _ in table.values())
    total = sum(n for _, n in table.values())

    if args.json:
        print(json.dumps({
            "total": total,
            "passed": total_ok,
            "dimensions": {k: {"passed": ok, "total": n} for k, (ok, n) in table.items()},
            "failures": [{"scenario": r.scenario_id, "dimension": r.dimension, "detail": r.detail}
                         for r in report.failures],
        }, indent=2))
        return 1 if (args.strict and report.failures) else 0

    print(f"Jiajia behavior evaluation — {total_ok}/{total} checks passed\n")
    width = max((len(k) for k in table), default=0)
    for name in DIMENSIONS:
        if name not in table:
            continue
        ok, n = table[name]
        pct = (100.0 * ok / n) if n else 0.0
        bar = "█" * int(pct // 5) + "·" * (20 - int(pct // 5))
        print(f"  {name:<{width}}  {bar}  {ok:>3}/{n:<3}  {pct:5.1f}%")

    if report.failures:
        print(f"\n{len(report.failures)} failing checks")
        shown = report.failures if args.verbose else report.failures[:10]
        for r in shown:
            print(f"  ✗ [{r.scenario_id}] {r.detail}")
        if not args.verbose and len(report.failures) > len(shown):
            print(f"  … {len(report.failures) - len(shown)} more (--verbose)")
    else:
        print("\nAll checks passed.")

    return 1 if (args.strict and report.failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
