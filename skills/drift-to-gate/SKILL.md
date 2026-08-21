---
name: drift-to-gate
description: Use when the same rule is violated a second time, when a standing agreement lives only in prose or a memory file, when a gate rejects something genuinely legitimate, or when deciding whether an enforcement check still earns its keep. Not for a first violation.
roles: [implement, review]
gate: gate-selftest
---

# Drift to Gate

A rule you have to remember will eventually be forgotten, or argued around. A rule a program declines to let past will not.

The incident behind this is not an oversight. An agent looked up a standing rule about how often to release, restated it correctly in its own reply, and then advised the opposite in that same reply — long past the point the rule required action, with every precondition met. Nothing was forgotten. The rule was **argued past**, on grounds that felt newly discovered each time they were assembled. Every other standing rule in that system was carried by code that could decline. This one was still carried by a paragraph, and it was the only one that came apart.

That is the whole argument. Prose loses to a plausible-sounding local argument, every time, because the local argument is generated fresh and the prose is not.

But writing the check is maybe a fifth of the work. A control has a lifecycle, and every clause below is here because skipping it produced a control that ran, stayed green, and protected nothing.

## What earns a gate

**The second violation, not the first.** One breach with a genuine one-off cause
buys a fix; a gate per incident is how a shop ends up with fifty checks nobody
reads. And the rule has to have a measurable cost when broken — enforcement cost
is real and gets paid every run, so a preference with no cost is a preference.
The test in full is in
[references/gate-lifecycle.md](references/gate-lifecycle.md).

## The control's lifecycle

Seven stages, one rule each. The arguments and the incidents behind them are in
[references/gate-lifecycle.md](references/gate-lifecycle.md) — read it when a
stage is the one you are actually at.

| Stage | The rule |
|---|---|
| **Prove it can say no** | A check that has only ever approved is a formality. Write the refusal test before the pass test; a newly written gate passing on today's data feels like proof and is not. |
| **Log the refusals** | A gate that refuses and records nothing cannot say whether it is working or merely quiet. The log is the evidence for keeping it and the evidence for retiring it. |
| **Never widen it for your own change** | A check failing on its author's change is the check working. An exemption filed instead is the moment enforcement turns into paperwork: an empty result computed after removing everything on the list proves only that the last exemption was filed correctly. |
| **Group the vocabulary, never enlarge the accept set** | When a gate rejects a genuinely legitimate state, the fix is a new *word* for that state — a bucket the gate can name and route — not a wider definition of finished. Widening is one-way and unmeasurable; a new bucket keeps the count honest. |
| **Fail loud, never silently** | A gate that swallows its own error reports clean. One unhashable value raised inside a blanket `except` had a caller announce all four of its checks green. |
| **Watch the visibility economics** | A gate going green and the thing it watched getting quieter look identical from outside. Say which one happened, with the number that shows it. |
| **Meter it, and let it die** | A control that raises far more than anyone acts on is demanding more than it returns. That is a finding about the rule behind it, not about the people ignoring it. |

## The contract a gate owes

Every gate states four things, or it is not auditable: **what it refuses**, **what
it lets through**, **how it is bypassed**, and **who is told when it fires**. A
gate with an undocumented bypass is a gate whose real accept set nobody knows;
one that fires into a channel nobody reads has been passing since the day it was
added. The contract in full, and the failure modes that follow from skipping any
part of it, are in
[references/gate-lifecycle.md](references/gate-lifecycle.md).

## The two checks that ship with this skill

Both are static, offline, and stdlib-only — a slow gate gets removed from CI, which is the decay it existed to prevent.

```bash
# Can this gate say no? Rubber-stamp tests, swallowed failures,
# a CLI that can never exit non-zero, an entrypoint stranding later tests.
python3 scripts/gate_selftest.py --gate tools/gates.py --tests tests/test_gates.py

# Is a check being widened instead of satisfied?
python3 scripts/exception_creep.py main..HEAD
```

`gate_selftest.py` covers only the mechanical half of *prove it can say no*; the other half is not static and cannot be — mutate the enforcement line and watch the decisive test go red.

`exception_creep.py` produces **questions, not verdicts**. Exceptions are sometimes right; the finding exists so the reasoning lands in the change description where a reviewer can see it, rather than nowhere. It deliberately skips brand-new files and prose — there is no check there to widen, and scanning them buried the real findings 44-to-0 the first time it was pointed at its own diff.

## Related skills

- `ratchet-what-you-build` — the enforcement *ladder*: how to rank many mechanisms and close convention gaps across a codebase. This skill is one control's lifecycle and pathology; use that one to decide what to gate, this one to build it so it survives.
- `reproduce-then-fix` — verified-red, applied here to the gate's own tests
- `escape-hatch-policy` — designing the declared, re-verified waiver a gate needs when exceptions are legitimate
- `distill-the-rule` — produces the one-line rule; this skill is what happens when that rule keeps being ignored
- `negative-result-taxonomy` — a worked example of a vocabulary with owed/closed buckets, and the ledger `scripts/gate_selftest.py` was written against
- `authority-dissociation` — who may assert the fact a gate reads; a gate over a self-written field checks nothing
- `failure-path-review` — the gate's own unhappy paths
- `self-audit` — where "what keeps this true?" belongs in a review pass
