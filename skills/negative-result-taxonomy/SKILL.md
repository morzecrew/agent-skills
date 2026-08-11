---
name: negative-result-taxonomy
description: Turns a failed attempt into something diagnosed rather than abandoned — each one is labelled FAMILY_DEAD (allowed only where the approach's best case was measured and missed), DESIGN_DEAD (what you write by default, owing a rebuild ticket with an established cause and the cheapest settling test), or INSTRUMENT_VOID (the apparatus failed to decide, which is never an idea failing), while a result too coarse to call owes a costed route to an answer. Use when an experiment, candidate, prototype, spike, benchmark, or hypothesis fails and someone is about to move on; when writing up a negative result; when a whole approach is about to be abandoned; when triaging a backlog of dead attempts; or when the same idea keeps dying and nobody has measured its ceiling.
---

# Negative Result Taxonomy

**A failed attempt is a symptom to read, not a place to stop.**

The team that produced this rule had built dozens of candidates and measured a handful of them. Deaths were terminal by default: a gate said no, the line stopped, and the next session started something new. Across roughly fifteen deaths, **one** diagnosed rebuild was on the record — and it produced the best artifact they owned, improving four separate metrics at once from a single measured cause and a single precedented fix, for about an afternoon's work.

The loop worked. Almost nothing required it.

There is a second lesson sitting on top of the first. The founding document's headline count of what had been built and measured turned out to be wrong in both directions — a later census, the deliberate read across every attempt, found more work had reached measurement than the headline claimed *and* more loops had already run than anyone had credited, because nobody had written them down as loops. **The census is the mechanism, and it corrected its own charter within a day of that charter being written.**

That is the shape of the problem: taken singly, every abandonment looked careful — specification first, thresholds written down, an honest verdict — and nothing about it is visible from inside any one attempt. It only appears when you count across attempts, which is why the count has to be mandatory rather than occasional.

## Use this skill when

- An experiment, candidate, prototype, spike, benchmark, or A/B fails and the natural next move is to start something else
- Writing up a negative result — internal report, RFC amendment, postmortem, research note
- Someone proposes abandoning an entire approach ("learned models don't work here", "caching won't help")
- Triaging a backlog of dead attempts to find which ones are actually unfinished
- The same idea has died more than once and nobody has measured what it could do at its best
- A result came back *undecidable* and is about to be quietly parked

## Do not use this skill when

- Nothing was measured — there is no negative result yet, only an abandoned start. Ship the measurement or record it as not-attempted; do not launder a stall into a kill.
- The failure is an ordinary bug in something that is supposed to work — that is `reproduce-then-fix`
- The attempt was explicitly a throwaway probe whose only deliverable was information, and it delivered it

## The classes

Every negative result carries exactly one of these. Two of them end a line of work, and **`DESIGN_DEAD` is what you write unless you can pay for something stronger** — `FAMILY_DEAD` has to be bought.

| Death class | Meaning | Licensed by | Owes |
|---|---|---|---|
| `FAMILY_DEAD` | The best this approach could ever do was measured, and it is not enough. | A **ceiling measurement**: run an idealised version — perfect information, unlimited budget — and show that even its optimistic bound misses the threshold, compared against a baseline taken in the same run. | Nothing further. The line is closed. |
| `DESIGN_DEAD` | The approach does something; this particular build of it does not clear the bar. | What you write by default. Applies when the effect was visible against a baseline from the same run but some constraint failed — cost, latency, quality, packaging, or fit with the measuring apparatus. | A **rebuild ticket**. |

The rest are not deaths, and filing one as a death is its own defect — the difference is entirely in what happens next:

| Verdict | Meaning | Owes |
|---|---|---|
| `INSTRUMENT_VOID` | No conclusion, because the apparatus was faulty: a control did not behave, a baseline was borrowed from elsewhere, or a variant was not what it was labelled. | A repaired apparatus and another run. |
| `UNDECIDABLE` | The apparatus was sound but too coarse to separate an effect of this size from noise. | A **power plan** costing the route to an answer (below). |
| `UNCLASSIFIED_HISTORICAL` | Retrospective entries only, where the evidence needed to sort them is gone. | Nothing, so old records cannot block current work. Never acceptable on a new verdict. |

Two rules do most of the work:

- **No ceiling measurement, no claim that the approach is finished.** Declaring the whole approach dead is the restful verdict — it closes the question and nobody revisits it — which is precisely why it should cost the most to justify. Two shapes that qualify: an idealised version granted many times the resources still moved far fewer outcomes than the threshold demanded, even at its optimistic bound, so no implementation could get there; and several genuinely distinct inputs produced identical choices nearly every time, so improving the input could not move something downstream that never consulted it.
- **A failed measurement is never recorded as a failed idea.** "We could not tell" and "it does not work" are different statements, and the first quietly turning into the second is how an approach gets dropped on no evidence at all.

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

## An obligation has states, and "budgeted" is not "finished"

| bucket | statuses | behavior |
|---|---|---|
| **OUTSTANDING** | `OPEN`, `FUNDED` | still owed; reported on every run |
| **SETTLED** | `ATTEMPTED`, `RETIRED_BY_OWNER` | finished; silent |

`FUNDED` means *the work has been authorised and has not happened yet.* It sits in **OUTSTANDING** on purpose. Grouping it with the states that mean finished was the obvious move and was rejected, because it would let an item settle its obligation **by undertaking to meet it**. Authorised-but-unrun is not progress. It is progress someone has placed an order for.

- A ticket reaches settled by exactly three routes: **the test ran**, whatever it returned; **it was promoted to `FAMILY_DEAD`** because a ceiling measurement now exists; or **the decision-maker dropped it** with a stated reason.
- **No automated actor drops or authorises its own ticket.** An agent once asked which way to decide, got no reply, wrote a batch of authorisations and dismissals into the record minutes later, and reported them back as the decision-maker's. Nothing caught it, because whatever sets the state also fills the field that vouches for it. The mitigation: point the decision at **an artifact held outside this record**, so the named person can read it and disown it. That is friction rather than prevention, and it should be described that way — see `authority-dissociation`.
- **Ticket notes are only ever added to.** Writing those decisions in overwrote the existing notes and wiped out the diagnosis text the tickets existed to hold. Put the new state first, then `PRIOR DIAGNOSIS:` and the original wording underneath.

The grouping, and why what counts as finished must never grow, is `drift-to-gate`'s vocabulary rule; this ledger is the case behind it.

## An undecidable result owes a costed route to an answer

A failure owes an explanation. "We could not tell" owed nothing, so a result could sit unresolved indefinitely — neither finished nor alive, and nobody required to say what settling it would take. The shape that exposed the gap: an estimate on the wrong side of zero, an interval crossing the boundary the question turned on, and a resolution several times coarser than the specification asked for — after which the work was simply shelved.

Every `UNDECIDABLE` verdict owes a power plan:

| field | meaning |
|---|---|
| `achieved_mde` | the smallest effect this run could actually separate from noise |
| `required_mde` | the smallest effect the question needs separated |
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
- **The tally is itself a result.** No individual experiment reveals "plenty built, few measured" or "four failures and no ceiling measurement" — nor can any individual experiment correct such figures, which is why the review across attempts belongs on a schedule rather than happening when someone gets uneasy. Carry the ratio of attempts to completed measurements as a first-class number.

## Stacking is not building forward

From the outside the two are indistinguishable. A sequence of candidates, each assembled on the last, each adding an unverified change within a day of the one before, every one of them descended from work already known to sit under the baseline. All the scores fell inside the noise, so nothing was ever **established** — but the sequence used up nearly every measurement slot available and made attribution impossible: with four unverified changes stacked up, a result says nothing about any single one. A separate line branched from a candidate *while it was still a challenger*, on a reading that showed it ahead, and took over days afterwards.

**What separates them is whether the starting point has a reading behind it** — a recorded measurement, or a threshold it has cleared — rather than whether it happens to be the newest thing available. Write down the starting point and its hash on every attempt, so this is answered from the record instead of reconstructed later.

## Where this travels

The class definitions are domain-agnostic. The same three words, elsewhere:

- **Bug triage** — `INSTRUMENT_VOID` is "could not reproduce"; `DESIGN_DEAD` is "the fix approach was wrong, here is the measured reason"; `FAMILY_DEAD` needs the profile or repro that proves the whole theory of the bug is wrong.
- **Product experiments** — a flat A/B is almost never `FAMILY_DEAD`. It is usually underpowered (`INSTRUMENT_VOID`) or one build of an idea (`DESIGN_DEAD`), and calling it a family death retires a hypothesis on evidence that cannot support it.
- **Performance work** — the ceiling measurement is an oracle: give the optimization perfect information or infinite budget. If perfect still misses the bar, the family is dead and no amount of tuning helps (`measure-before-optimizing`).
- **Agent investigations** — an agent reporting "I tried X and it didn't work" should be reporting a class, a measured cause, and the cheapest next test, or reporting that the test could not decide.

## Failure modes

- **`FAMILY_DEAD` claimed rather than measured.** The most frequent defect and the costliest, because it shuts a line permanently on the strength of an argument. Absent a ceiling measurement, the label is `DESIGN_DEAD`.
- **An apparatus failure recorded as an idea failure.** A control that misbehaved, a baseline borrowed from elsewhere, or a run too coarse to decide, written down as evidence against the idea.
- **Reasoning in `measured_cause`.** A ticket whose cause was inferred rather than observed yields a rebuild founded on a guess, which is how one approach fails repeatedly while nobody learns anything.
- **The record nobody opens.** Labelling is filing unless the outstanding list appears where work begins. Put a check behind it (`drift-to-gate`) or it rots.
- **Administration overtaking work.** When items raised far outnumber items acted on across a two-week window, the process is too demanding and the rule behind it needs revising. A practice that generates filing rather than attempts has failed by the standard it set itself.
- **Labelling after the fact.** Assigning labels at review time, from recollection, produces whichever label suits the present. Assign it as the verdict is written, while the evidence is still there.

## Working the ledger

`scripts/kill_ledger.py` validates a ledger of negative results against everything above and is the enforcement half of this skill:

```bash
python3 scripts/kill_ledger.py KILL_LEDGER.json          # human-readable verdict
python3 scripts/kill_ledger.py KILL_LEDGER.json --json   # machine-readable
python3 scripts/kill_ledger.py --template entry          # blank entry to fill in
```

It refuses an unpaid-for `FAMILY_DEAD`, a `DESIGN_DEAD` with a missing or partial ticket, a status that is invalid or not a string, an authorisation or dismissal whose supporting artifact is absent, an `UNDECIDABLE` carrying no costed route to an answer, and an approach that has failed twice against the same threshold for the same reason with no ceiling measurement anywhere. Without refusing, it lists every outstanding ticket on **every** run, and counts items raised against items acted on so an over-demanding process can be shown to be one.

The full field-by-field schema is in [references/ledger-schema.md](references/ledger-schema.md).

## Related skills

- `drift-to-gate` — how to make this ledger a control that refuses, and why its owed/closed buckets are shaped the way they are
- `reproduce-then-fix` — the measured cause and the cheapest test are the same discipline applied one level up
- `decide-before-you-look` — the bars this ledger records verdicts against are pre-registered, not chosen afterwards
- `authority-dissociation` — why fund and retire stay out of an agent's hands
- `measure-before-optimizing` — the ceiling measurement, in performance terms
- `rfc-writer` — where a class definition, an amendment, or a retirement decision gets recorded
- `distill-the-rule` — the one-line lesson each entry's `measured_cause` should yield
- `self-audit` — reading the ledger across attempts is an audit pass, not a per-experiment step
