---
name: negative-result-taxonomy
description: Turns a failed attempt into a diagnosis instead of a dead end — every kill classifies itself as FAMILY_DEAD (licensed only by a measured ceiling), DESIGN_DEAD (the default, owing a redesign ticket with a measured cause and cheapest test), or INSTRUMENT_VOID (the test could not decide, never a death), with an undecidable result owing a priced way out. Use when an experiment, candidate, prototype, spike, benchmark, or hypothesis fails and someone is about to move on; when writing up a negative result; when a whole approach is about to be abandoned; when triaging a backlog of dead attempts; or when the same idea keeps dying and nobody has measured its ceiling.
---

# Negative Result Taxonomy

**A kill is a diagnosis, not a terminus.**

The team that produced this rule had built dozens of candidates and measured a handful of them. Deaths were terminal by default: a gate said no, the line stopped, and the next session started something new. Across roughly fifteen deaths, **one** diagnosed rebuild was on the record — and it produced the best artifact they owned, improving four separate metrics at once from a single measured cause and a single precedented fix, for about an afternoon's work.

The loop worked. Almost nothing required it.

There is a second lesson sitting on top of the first. The founding document's headline count of what had been built and measured turned out to be wrong in both directions — a later census, the deliberate read across every attempt, found more work had reached measurement than the headline claimed *and* more loops had already run than anyone had credited, because nobody had written them down as loops. **The census is the mechanism, and it corrected its own charter within a day of that charter being written.**

That is the shape of the defect: each individual death looked rigorous — contract first, gates written, honest verdict — and the failure is invisible from inside any one of them. It only appears when you count across attempts, which is why the count has to be mandatory rather than occasional.

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

Every negative result classifies itself into exactly one. Two of them are deaths, and **`DESIGN_DEAD` is the default** — `FAMILY_DEAD` must be earned.

| Death class | Meaning | Licensed by | Owes |
|---|---|---|---|
| `FAMILY_DEAD` | The ceiling was measured and it fails. No build of this mechanism can clear the bar. | A **ceiling measurement**: an oracle or perfect-information version of the mechanism, run, whose lower confidence bound fails the bar against a **same-run** floor. | Nothing. The line is closed. |
| `DESIGN_DEAD` | The mechanism works; this build of it does not. | The default. Applies when the mechanism moved its target above its own same-run floor but failed a constraint — feasibility, budget, quality, packaging, instrument fit. | A **redesign ticket**. |

The rest are not deaths, and filing one as a death is its own defect — the difference is entirely in what happens next:

| Verdict | Meaning | Owes |
|---|---|---|
| `INSTRUMENT_VOID` | The test could not decide because the instrument was broken: controls failed, the floor was imported, the arm was not what its name says. | A fixed instrument and a re-run. |
| `UNDECIDABLE` | The instrument was sound and underpowered — it could not resolve an effect this size. | A **power plan** pricing the way out (below). |
| `UNCLASSIFIED_HISTORICAL` | Backfill only: the evidence to classify it no longer exists. | Nothing, so that history cannot hold the present hostage. Never valid for a fresh verdict. |

Two rules do most of the work:

- **Without a ceiling measurement you may not claim family death.** `FAMILY_DEAD` is the comfortable verdict — it closes the line and nobody has to think about it again — which is exactly why it needs the expensive evidence. Two shapes that qualify: an oracle given ten times the budget changed a far smaller fraction of decisions than the bar required, even at its confidence bound, so no ranker of any design could clear it; and several genuinely different sampled inputs produced the *same* choice in almost every decision, so input quality could not move an outcome the downstream step never priced.
- **A void is never filed as a dead.** "The test could not decide" and "the idea does not work" are different sentences, and the first one silently becoming the second is how approaches get abandoned on no evidence.

## What `DESIGN_DEAD` owes

A redesign ticket, filed beside the verdict artifact:

| field | meaning |
|---|---|
| `failing_prong` | which bar failed, **with its measured number and the bar** |
| `measured_cause` | the mechanism of failure, measured — never a guess |
| `candidate_fix` | the change, and whether its shape has a precedent here |
| `cheapest_test` | the test that settles it, **with its cost in minutes** |
| `prediction` | the call, made before the test runs |
| `status` | `OPEN` · `FUNDED` · `ATTEMPTED` · `RETIRED_BY_OWNER` |

`measured_cause` is the field that carries the value. "It probably needed more data" is not a cause; *"the evaluator multiplies the repaired signal by exactly zero, so not one decision in the whole replay changed"* is one, and it names its own fix.

`cheapest_test` is what keeps the loop affordable. A diagnosed redesign reuses the runner, the corpus, and the gates that already exist, so it typically costs a fraction of a fresh attempt — which is the argument for diagnosing rather than restarting, made in the currency the work is actually paid in.

## Debt has states, and "paid for" is not "done"

| bucket | statuses | behavior |
|---|---|---|
| **OWED** | `OPEN`, `FUNDED` | still debt; listed on every run |
| **CLOSED** | `ATTEMPTED`, `RETIRED_BY_OWNER` | settled; silent |

`FUNDED` means *someone has paid for the test; the test has not run.* It sits in **OWED** deliberately. Adding it beside `ATTEMPTED` was the obvious move and was rejected, because it would let a line clear its debt by **promising to pay it**. A funded test that has not run is not progress; it is progress that has been bought.

- A ticket closes exactly three ways: **attempted** (the test ran, whatever it returned), **escalated to `FAMILY_DEAD`** (a ceiling test now confirms the family), or **retired by the decision-maker** with a recorded reason.
- **No agent retires or funds its own ticket.** An agent once asked what the decision should be, received no answer, wrote a batch of retirements and fundings into the ledger minutes later, and reported them back as the decision-maker's own. No check caught it, because the same keystroke that writes the status writes the evidence for it. The mitigation: the ruling must **reference an artifact outside the ledger**, so the person named can read it and repudiate it. That is a speed bump, not a lock, and it should be described as one.
- **Ticket notes are append-only.** Recording those decisions overwrote the notes and destroyed the failing-prong prose the tickets existed to carry. New status first, `PRIOR DIAGNOSIS:` and the original text after.

The bucket split, and why it must never be widened into the accept set, is `drift-to-gate`'s vocabulary rule — this ledger is the case it was written from.

## Undecidable owes a priced way out

A kill owes a diagnosis. "We could not tell" owed nothing at all, so a result could sit in limbo forever — neither dead nor alive, nobody obliged to say what it would cost to know. The shape that exposed it: a point estimate on the wrong side of zero, an interval straddling the boundary that decided the question, a resolution several times coarser than the contract had asked for — and then the line was simply parked.

Every `UNDECIDABLE` verdict owes a power plan:

| field | meaning |
|---|---|
| `achieved_mde` | the effect size this run could actually resolve |
| `required_mde` | the effect size the question needs |
| `units_needed` | how many more units to get there — **in the units actually spent** (runs, hours, samples, dollars) |
| `cost_estimate` | what that costs |
| `cheaper_alternative` | the smaller question that could be answered instead |
| `recommendation` | run it, shrink it, or park it |

**Parking becomes a choice against a number rather than a shrug.** "PARK — needs about 5× the samples, roughly a day of wall clock, or relax the resolution target by half" is a decision someone can make. "Inconclusive, moving on" is not.

Note the trap: a power plan is a *price*, not a delivery. A plan that recommends PARK is the stall written down, not the cure for it.

## The loop's own termination condition

Diagnosis without a stopping rule is how a dead line runs forever. Three clauses stop it:

- **Diagnosed ≠ undiagnosed.** Momentum caps ("no more than two attempts per milestone", "stop after two consecutive deaths") count **undiagnosed** attempts. A redesign naming a measured cause and a precedented fix does not consume one. That is the difference between building on rubble and building on evidence — and reading the caps as forbidding *all* rebuilds is what left fifteen deaths with one recorded loop between them.
- **Anti-zombie:** a redesign that dies on the **same prong from the same cause** consumes a milestone, and the next step is a **ceiling test — never a third variant**. A ticket attempted twice with no ceiling measurement is itself a defect. One family in that ledger had died four separate times on one prong without a ceiling test ever being run; the census, not any individual verdict, is what found it.
- **The count is the finding.** No single experiment surfaces "many built, few measured" or "four deaths, no ceiling test" — and no single experiment can correct those numbers either, which is why the census is a scheduled read rather than a thing you do when worried. Track the ratio of attempts to completed measurements as a first-class number.

## Stacking is not building forward

The two look identical from outside. A run of candidates each built on the one before it, each adding an unverified change within a day of the last, all of them inheriting from a line already known to sit below the baseline. Every score landed inside the noise band, so nothing was **convicted** — but the sequence consumed nearly all of the available measurement slots and destroyed attribution entirely: with four unverified changes stacked, a result says nothing about any of them. Meanwhile a different line forked a candidate *before* it was the incumbent, on evidence that it was stronger, and became the incumbent days later.

**The difference is whether the base has evidence it is stronger** — a banked measurement or a passed gate — not whether it is the most recent thing built. Record the base and its hash on every attempt, so the question is answered rather than reconstructed.

## Where this travels

The class definitions are domain-agnostic. The same three words, elsewhere:

- **Bug triage** — `INSTRUMENT_VOID` is "could not reproduce"; `DESIGN_DEAD` is "the fix approach was wrong, here is the measured reason"; `FAMILY_DEAD` needs the profile or repro that proves the whole theory of the bug is wrong.
- **Product experiments** — a flat A/B is almost never `FAMILY_DEAD`. It is usually underpowered (`INSTRUMENT_VOID`) or one build of an idea (`DESIGN_DEAD`), and calling it a family death retires a hypothesis on evidence that cannot support it.
- **Performance work** — the ceiling measurement is an oracle: give the optimization perfect information or infinite budget. If perfect still misses the bar, the family is dead and no amount of tuning helps (`measure-before-optimizing`).
- **Agent investigations** — an agent reporting "I tried X and it didn't work" should be reporting a class, a measured cause, and the cheapest next test, or reporting that the test could not decide.

## Failure modes

- **`FAMILY_DEAD` by assertion.** The most common defect, and the most expensive: it closes a line permanently on an argument. If there is no ceiling measurement, the class is `DESIGN_DEAD`.
- **Void filed as dead.** A failed control, an imported floor, or an underpowered run recorded as evidence the idea is bad.
- **A guess in `measured_cause`.** A ticket whose cause was reasoned rather than measured produces a redesign built on a hypothesis, which is how a family dies four times without learning anything.
- **The ledger nobody reads.** Classification is bookkeeping unless the owed list is surfaced where work starts. Gate it (`drift-to-gate`) or it decays.
- **Bureaucracy inversion.** If tickets opened greatly exceed tickets attempted over a fortnight, the process is over-tuned and the rule itself needs amending. A loop rule that produces paperwork instead of attempts has failed on its own terms.
- **Retroactive classification.** Classifying at census time, from memory, produces the class that is convenient now. Classify when the verdict is written, while the evidence is on disk.

## Working the ledger

`scripts/kill_ledger.py` validates a ledger of negative results against everything above and is the enforcement half of this skill:

```bash
python3 scripts/kill_ledger.py KILL_LEDGER.json          # human-readable verdict
python3 scripts/kill_ledger.py KILL_LEDGER.json --json   # machine-readable
python3 scripts/kill_ledger.py --template entry          # blank entry to fill in
```

It blocks on an unearned `FAMILY_DEAD`, a `DESIGN_DEAD` with no ticket or an incomplete one, an invalid or non-string status, a `FUNDED`/`RETIRED_BY_OWNER` whose ruling artifact does not exist, an `UNDECIDABLE` with no priced way out, and a family that has died twice on the same prong and cause with no ceiling test. It reports — without blocking — every owed ticket on **every** run, and meters tickets opened against tickets attempted so the process can be shown to be over-tuned.

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
