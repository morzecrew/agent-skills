---
name: negative-result-taxonomy
description: Use when an experiment, candidate, prototype, spike, or benchmark fails and the next move is to start something else; when writing up a negative result; when triaging a backlog of dead attempts; or when a whole approach is about to be abandoned. Not when nothing was measured.
roles: [author, review]
gate: kill-ledger
---

# Negative Result Taxonomy

**A failed attempt is a symptom to read, not a place to stop.**

The team that produced this rule had built dozens of candidates and measured a handful of them. Deaths were terminal by default: a gate said no, the line stopped, and the next session started something new. Across roughly fifteen deaths, **one** diagnosed rebuild was on the record — and it produced the best artifact they owned, improving four separate metrics at once from a single measured cause and a single precedented fix, for about an afternoon's work.

The loop worked. Almost nothing required it.

There is a second lesson sitting on top of the first. The founding document's headline count of what had been built and measured turned out to be wrong in both directions — a later census, the deliberate read across every attempt, found more work had reached measurement than the headline claimed *and* more loops had already run than anyone had credited, because nobody had written them down as loops. **The census is the mechanism, and it corrected its own charter within a day of that charter being written.**

That is the shape of the problem: taken singly, every abandonment looked careful — specification first, thresholds written down, an honest verdict — and nothing about it is visible from inside any one attempt. It only appears when you count across attempts, which is why the count has to be mandatory rather than occasional.

## Three classes, one test

The question is **what actually failed** — the whole approach, this attempt at
it, or the apparatus:

| Class | Claims | Allowed only when |
|---|---|---|
| `FAMILY_DEAD` | The approach cannot work here | Its **best case** was measured and missed. Not this build's number — the ceiling. |
| `DESIGN_DEAD` | This attempt failed | Always, and it is what you write by default. Owes a rebuild ticket. |
| `INSTRUMENT_VOID` | The apparatus did not decide | The run could not distinguish the outcomes. Never an idea failing. |

**`DESIGN_DEAD` is the default, and the asymmetry is deliberate.** Filing a
family verdict without the ceiling measurement claims territory nobody surveyed,
and it is the expensive mistake: a `DESIGN_DEAD` mislabelled `FAMILY_DEAD` closes
a direction for everyone who reads the record afterwards, and nothing in the
record says it was never measured.

A result too coarse to call is `INSTRUMENT_VOID` and owes a costed route to an
answer — not a quiet parking. Each class in full, with the failure modes that
follow from skipping its evidence, is in
[references/the-classes.md](references/the-classes.md).

## A verdict is an obligation, not a label

Classifying is the cheap half. Each class then owes something, and a class filed
without its obligation is the same stall it was before, with a name on it:

- **`FAMILY_DEAD` owes the ceiling measurement** that authorised it. Without one it is not a family verdict at all — it is a `DESIGN_DEAD` claiming more territory than it measured.
- **`DESIGN_DEAD` owes a rebuild ticket** naming an established cause and the cheapest test that would settle it. "We tried it and it didn't work" is a memory, not a record.
- **`INSTRUMENT_VOID` owes a costed route to an answer.** The apparatus failing to decide is never an idea failing, and parking it quietly converts a measurement problem into a false kill.

An obligation has states, and **budgeted is not finished** — an authorised but
unrun ticket is not progress, and the outstanding list is printed on every run,
including runs already failing for other reasons.

The obligations in full, the states they move through, the loop's own stopping
rule, and how the ledger is worked are in
[references/obligations.md](references/obligations.md).

## Checking the ledger

```bash
python3 scripts/kill_ledger.py ledger.json --ruling-root .
python3 scripts/kill_ledger.py --template family_dead     # a blank scaffold
```

It answers the three questions individual verdicts cannot: which entries are
defective (a `FAMILY_DEAD` nobody paid the ceiling for, a `DESIGN_DEAD` with a
half-filled ticket, an authorisation whose artifact is absent), what is still
outstanding, and whether the practice is raising more than it acts on. Schema in
[references/ledger-schema.md](references/ledger-schema.md); how to work it, in
[references/obligations.md](references/obligations.md).

## Related skills

- `drift-to-gate` — how to make this ledger a control that refuses, and why its owed/closed buckets are shaped the way they are
- `reproduce-then-fix` — the measured cause and the cheapest test are the same discipline applied one level up
- `decide-before-you-look` — the bars this ledger records verdicts against are pre-registered, not chosen afterwards
- `authority-dissociation` — why fund and retire stay out of an agent's hands
- `measure-before-optimizing` — the ceiling measurement, in performance terms
- `rfc-writer` — where a class definition, an amendment, or a retirement decision gets recorded
- `distill-the-rule` — the one-line lesson each entry's `measured_cause` should yield
- `self-audit` — reading the ledger across attempts is an audit pass, not a per-experiment step
