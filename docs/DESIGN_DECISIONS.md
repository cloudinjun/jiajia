# Design decisions

Three decisions where the interesting work was deciding what to remove, or
noticing that something which looked finished was not. Each one is a case where
the code compiled, the tests were green, and the design was still wrong.

---

## Case A — The props were doing the acting

### Before

52 of 68 actions carried a default prop. Ask for `blink_innocent` and a halo
appeared. Ask for `celebrate` and confetti came with it. Every action had been
given something to hold, because a richer frame looks better in isolation.

### The problem

Watching a full session, the character had no body language — it had a prop
rotation. Users were not learning *"the paperclip tilts like that when it is
judging you"*. They were learning *"halo means innocent"*.

That is a worse outcome than it sounds. A prop is a label; it reads once and
then stops carrying information. Body language compounds — the twentieth time
you see the judge-tilt you read it faster than the first. By defaulting props on,
every action was spending its most legible channel on a caption.

There was a second failure underneath. Because props were per-action defaults,
they fired in contexts that made no sense: a celebration prop during a
recovery-from-error state, an innocence halo while the agent was mid-permission
request. Nothing in the system asked whether the prop had a *reason*.

### The decision

**A prop must have a cause.** Props stopped being action defaults and became
scenario opt-in — declared by the situation that justifies them
(`scenario_prop` in [`animations.yaml`](../jiajia/animations.yaml)), not
attached to the motion itself.

The corollary was a rule about channel ownership: eyes and brows carry emotion,
body carries energy, tail carries attention, and props carry *only* things with
a narrative cause. Anything a prop was previously doing that fit one of the
other channels had to move there or be cut.

### After

7 of 78 actions retain a prop, each traceable to a scenario that justifies it.
The action count went *up* while the prop count went down by 86% — the
vocabulary grew in the channel that compounds.

This decision is enforced, not just documented.
[`test_action_semantics.py`](../tests/test_action_semantics.py) asserts it:

```
test_neutral_actions_carry_no_default_prop
test_blink_stays_a_blink
test_tail_actions_show_a_tail_not_a_prop
```

A future change that re-attaches a prop to a neutral action fails CI.

---

## Case B — The tests passed and the runtime was still broken

### Before

`test_performance_timing.py` verified that every performance phrase gave each
step enough time to read. It passed. Meanwhile, on screen, phrases were being
cut after 5–20% of their intended duration.

### The problem

The test imported the phrase table from `performance.py`. The runtime did not
use it.

`_run_performance_phrase` asks the animation manifest first and returns the
moment it has scheduled anything. For every primary phrase, the manifest had an
entry — so the `performance.py` table was unreachable code. Retiming it changed
the test result and changed nothing on screen.

This is the failure mode that matters most, and the one that is hardest to catch
by reading a diff: **the test and the runtime disagreed about which data was
real, and only the test was wrong.** A green suite was actively providing false
confidence. No amount of adding more tests against the same table would have
found it.

There was a related cause. "How long does this action run" existed as a method
on the app object, so anything outside a live window — the phrase audit, the
tests, the fallback table — had to fake an app to ask. Three callers each faking
it their own way is how two different answers to the same question get to exist.

### The decision

1. **Point the tests at the live source.** The timing tests now load
   `jiajia/animations.yaml` directly, and one test fails if that ever stops
   being the source the runtime reads.
2. **One answer to the duration question.**
   [`action_timing.py`](../jiajia/action_timing.py) became the single
   implementation; the app method delegates to it, so the sequencer, the audit
   and the tests all read the same number.

### After

25 live timing failures surfaced immediately, then went to 0. More importantly,
the suite now fails when the runtime is wrong rather than when a shadow table is
wrong.

The docstring on the test file records why, so the next person does not
reintroduce it:

> *The first version of this file imported the phrase table from performance.py
> and passed while the real thing was broken.*

---

## Case C — Two animations, eight channels, no owner

### Before

The character writes to eight independent visual channels — body, window
position, tail, inner wire, bend, face, prop, blink — and each was driven by its
own timer. Cancellation was whoever-writes-next-wins: a new action called
`_cancel_large_action`, a new tail motion called `_cancel_tail_wag`.

### The problem

None of those cancels knew *whose* motion they were ending.

The visible bug: a stale callback from a finished performance reaches in and
resets the expression, clears the prop, or zeroes the tail — of the performance
that already replaced it. The character would start a new reaction and then have
its face wiped mid-motion by the previous one's cleanup timer.

And the mirror image: cancelling a new performance would tear down channels an
older one still legitimately owned.

Both are timing-dependent. They reproduce when one performance interrupts
another inside a specific window, which means they survive casual testing and
appear in the demo.

### The decision

Add ownership bookkeeping — and nothing else.
[`performance_run.py`](../jiajia/performance_run.py) does not schedule and does
not decide priority; `VisualStatePlan` already decides whether a new performance
may preempt an old one. The registry only answers two questions:

- **Before writing:** *am I still the owner of this channel?*
- **On cancel:** *which channels do I still own, so I tear down exactly those?*

Channels already claimed by a newer run are deliberately excluded from a
cancelled run's teardown set — that exclusion *is* the fix.

One judgment call worth recording: costume, identity decorations and status
badges are deliberately **not** channels. They outlive any single performance,
and treating them as owned would let a finishing phrase strip the character's
clothes.

### After

Preemption became deterministic. A performance that is interrupted stops
scheduling instead of finishing into a channel it no longer owns.

Covered by [`test_performance_runs.py`](../tests/test_performance_runs.py).

---

## What these three have in common

None of them was found by a compiler, a linter, or a failing test. Each was
found by watching the actual behavior and asking whether it matched the
intent — then building the check that would have caught it.

That is the loop this project is really about:

**Generate broadly, then design the evaluation that decides what survives.**

The implementation here is AI-assisted and the volume reflects that. The
judgment about which output was correct, which was plausible-but-wrong, and
which should be deleted despite working — that is the part that does not
delegate.
