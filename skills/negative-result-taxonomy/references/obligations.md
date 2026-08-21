# What each verdict owes, and how the ledger is worked

The obligations attached to a classification, the states they pass through, and
the loop's own stopping rule. `SKILL.md` carries the three classes and the test
that separates them; everything a verdict then owes is here.

## What `DESIGN_DEAD` owes

A rebuild ticket, stored next to the verdict it belongs to:

| field | meaning |
|---|---|
| `failing_prong` | which threshold was missed, **with the observed value beside it** |
| `measured_cause` | why it failed, established by measurement rather than reasoning |
| `candidate_fix` | the proposed change, and whether anything similar has worked here before |
| `cheapest_test` | the smallest thing that would settle it, **and what it costs to run** |
| `prediction` | your call, recorded before that test runs |
| `status` | `OPEN` · `FUNDED` · `ATTEMPTED` · `RETIRED_BY_OWNER` |

`measured_cause` is where the value sits. "It probably needed more data" is a hunch; *"the scoring function weights the repaired signal at zero, so no decision anywhere in the replay changed"* is a cause, and it points straight at its own remedy.

`cheapest_test` is what keeps this affordable. A rebuild with a known cause inherits the harness, the data, and the thresholds already in place, so it usually costs a fraction of starting over — which is the case for diagnosing rather than restarting, stated in the currency the work is actually billed in.

**Nothing measured is not a negative result.** An attempt that stalled before it
produced a number is an abandoned start: ship the measurement, or record it as
not-attempted. A stall laundered into a kill spends the taxonomy's credibility
to close a ticket.

## An obligation has states, and "budgeted" is not "finished"

| bucket | statuses | behavior |
|---|---|---|
| **OUTSTANDING** | `OPEN`, `FUNDED` | still owed; reported on every run |
| **SETTLED** | `ATTEMPTED`, `RETIRED_BY_OWNER` | finished; silent |

`FUNDED` means *the work has been authorised and has not happened yet.* It sits in **OUTSTANDING** on purpose. Grouping it with the states that mean finished was the obvious move and was rejected, because it would let an item settle its obligation **by undertaking to meet it**. Authorised-but-unrun is not progress. It is progress someone has placed an order for.

- A ticket reaches settled by exactly three routes: **the test ran**, whatever it returned; **it was promoted to `FAMILY_DEAD`** because a ceiling measurement now exists; or **the decision-maker dropped it** with a stated reason. The middle route needs no new status — the ceiling measurement closed the line, so the entry moves to `FAMILY_DEAD` and its ticket is recorded as `ATTEMPTED` or `RETIRED_BY_OWNER` like any other. A `FAMILY_DEAD` entry still carrying an `OPEN` or `FUNDED` ticket is a contradiction the validator blocks: either the ticket is settled or the class is wrong.
- **No automated actor drops or authorises its own ticket.** An agent once asked which way to decide, got no reply, wrote a batch of authorisations and dismissals into the record minutes later, and reported them back as the decision-maker's. Nothing caught it, because whatever sets the state also fills the field that vouches for it. The mitigation: point the decision at **an artifact held outside this record**, so the named person can read it and disown it. That is friction rather than prevention, and it should be described that way — see `authority-dissociation`.
- **Ticket notes are only ever added to.** Writing those decisions in overwrote the existing notes and wiped out the diagnosis text the tickets existed to hold. Put the new state first, then `PRIOR DIAGNOSIS:` and the original wording underneath.

The grouping, and why what counts as finished must never grow, is `drift-to-gate`'s vocabulary rule; this ledger is the case behind it.

## An undecidable result owes a costed route to an answer

A failure owes an explanation. "We could not tell" owed nothing, so a result could sit unresolved indefinitely — neither finished nor alive, and nobody required to say what settling it would take. The shape that exposed the gap: an estimate on the wrong side of zero, an interval crossing the boundary the question turned on, and a resolution several times coarser than the specification asked for — after which the work was simply shelved.

Every `UNDECIDABLE` verdict owes a power plan:

| field | meaning |
|---|---|
| `achieved_mde` | the smallest effect this run could actually separate from noise |
| `required_mde` | the smallest effect the question needs to be able to separate |
| `units_needed` | how much more it would take — **counted in whatever is actually spent**: runs, hours, samples, currency |
| `cost_estimate` | what that amounts to |
| `cheaper_alternative` | a narrower question that could be settled instead |
| `recommendation` | run it, narrow it, or shelve it |

**Shelving then becomes a decision weighed against a figure instead of a shrug.** "Shelve it — around five times the samples, roughly a day of running, or halve what we are trying to detect" is something a person can rule on. "Inconclusive, moving on" is not.

One trap to note: a power plan is a *quotation*, not a result. One that recommends shelving is the delay recorded, not the delay resolved.

## The loop's own termination condition

Diagnosis without a stopping rule is how a dead line runs forever. Three clauses stop it:

- **Explained attempts and unexplained ones are counted separately.** Limits like "no more than two tries per milestone" or "stop after two consecutive failures" apply to attempts with **no established cause**. A rebuild carrying an established cause and a fix with precedent does not use one up. Those are two different activities: assembling on top of wreckage, versus assembling on top of findings — and reading such limits as banning *every* rebuild is what left fifteen abandonments with a single documented rebuild among them.
- **The stopping rule:** a rebuild that fails on the **same threshold for the same reason** does use up a milestone, and what follows is a **ceiling measurement — never a third variant**. A ticket tried twice with no ceiling measurement is itself a defect. One approach in that record had failed four separate times against a single threshold with no ceiling measurement ever attempted; the periodic review found it, not any individual verdict.
- **The tally is itself a result.** No individual experiment reveals "plenty built, few measured" or "four failures and no ceiling measurement" — nor can any individual experiment correct such figures, which is why the review across attempts belongs on a schedule rather than happening when someone gets uneasy. Carry the ratio of attempts to completed measurements as a first-class number. That is the **census** ratio, and it is not the meter below: the census asks how much of what was built ever got measured, while the meter asks whether *this process* is generating more paperwork than attempts. Keep them apart — they move independently, and a healthy reading on one says nothing about the other.

## Stacking is not building forward

From the outside the two are indistinguishable. A sequence of candidates, each assembled on the last, each adding an unverified change within a day of the one before, every one of them descended from work already known to sit under the baseline. All the scores fell inside the noise, so nothing was ever **established** — but the sequence used up nearly every measurement slot available and made attribution impossible: with four unverified changes stacked up, a result says nothing about any single one. A separate line branched from a candidate *while it was still a challenger*, on a reading that showed it ahead, and took over days afterwards.

**What separates them is whether the starting point has a reading behind it** — a recorded measurement, or a threshold it has cleared — rather than whether it happens to be the newest thing available. Write down the starting point and its hash on every attempt, so this is answered from the record instead of reconstructed later.

## Where this travels

The class definitions are domain-agnostic. The same three words, elsewhere:

- **Bug triage** — `INSTRUMENT_VOID` is "could not reproduce"; `DESIGN_DEAD` is "the fix approach was wrong, here is the measured reason"; `FAMILY_DEAD` needs the profile or repro that proves the whole theory of the bug is wrong.
- **Product experiments** — a flat A/B is almost never `FAMILY_DEAD`. It is usually underpowered (`INSTRUMENT_VOID`) or one build of an idea (`DESIGN_DEAD`), and calling it a family death retires a hypothesis on evidence that cannot support it.
- **Performance work** — the ceiling measurement is an oracle: give the optimization perfect information or infinite budget. If perfect still misses the bar, the family is dead and no amount of tuning helps (`measure-before-optimizing`).
- **Agent investigations** — an agent reporting "I tried X and it didn't work" should be reporting a class, a measured cause, and the cheapest next test, or reporting that the test could not decide.

## Working the ledger

`scripts/kill_ledger.py` validates a ledger of negative results against everything above and is the enforcement half of this skill:

```bash
python3 scripts/kill_ledger.py KILL_LEDGER.json          # human-readable verdict
python3 scripts/kill_ledger.py KILL_LEDGER.json --json   # machine-readable
python3 scripts/kill_ledger.py --template entry          # blank entry to fill in
```

It refuses an unpaid-for `FAMILY_DEAD`, a `FAMILY_DEAD` whose rebuild ticket is still outstanding, a `DESIGN_DEAD` with a missing or partial ticket, an entry with no stable identifier or one that is not text, a status that is invalid or not a string, an authorisation or dismissal whose supporting artifact is absent, an `UNDECIDABLE` carrying no costed route to an answer, and an approach that has failed twice against the same threshold for the same reason with no ceiling measurement anywhere. Without refusing, it lists every outstanding ticket on **every** run, warns about a starting point recorded without an artifact, a hash, and a reading, and counts items raised against items acted on so an over-demanding process can be shown to be one.

Provenance is a warning rather than a refusal on purpose: a record whose starting point is unidentifiable is worth flagging every run, but it does not make the verdict above it wrong, and blocking on it would teach people to stop reading the blocks.

The full field-by-field schema is in [references/ledger-schema.md](references/ledger-schema.md).
