---
name: negative-result-taxonomy
description: Turns a failed attempt into a diagnosis instead of a dead end — every kill classifies itself as FAMILY_DEAD (licensed only by a measured ceiling), DESIGN_DEAD (the default, owing a redesign ticket with a measured cause and cheapest test), or INSTRUMENT_VOID (the test could not decide, never a death), with an undecidable result owing a priced way out. Use when an experiment, candidate, prototype, spike, benchmark, or hypothesis fails and someone is about to move on; when writing up a negative result; when a whole approach is about to be abandoned; when triaging a backlog of dead attempts; or when the same idea keeps dying and nobody has measured its ceiling.
---

# Negative Result Taxonomy

**A kill is a diagnosis, not a terminus.**

The shop that produced this rule had built 28 candidates. Exactly one had ever reached the measurement that mattered. Deaths were terminal by default: a gate said no, the line stopped, and the next session started something new. In roughly fifteen deaths, exactly **one** was diagnosed and rebuilt — and that rebuild produced the best artifact the shop owned: blunders 5→0, referee preference 79.2%→87.2%, self-noise 8.50%→6.00%, decisions per game 20.3→7.3. **Four simultaneous wins from one measured cause and one precedented fix**, at a cost of one afternoon.

The loop worked. It was used once, because nothing required it.

The defect is not pessimism. Each individual death looked rigorous — contract first, gates written, honest verdict. The defect only appears when you count across attempts, and nobody was counting. What follows makes the count mandatory and the classification explicit.

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

## The three classes

Every negative result classifies itself into exactly one. **`DESIGN_DEAD` is the default**; the other two must be earned.

| Class | Meaning | Licensed by | Owes |
|---|---|---|---|
| `FAMILY_DEAD` | The ceiling was measured and it fails. No build of this mechanism can clear the bar. | A **ceiling measurement**: an oracle or perfect-information version of the mechanism, run, whose lower confidence bound fails the bar against a **same-run** floor. | Nothing. The line is closed. |
| `DESIGN_DEAD` | The mechanism works; this build of it does not. | The default. Applies when the mechanism moved its target above its own same-run floor but failed a constraint — feasibility, budget, quality, packaging, instrument fit. | A **redesign ticket**. |
| `INSTRUMENT_VOID` | The test could not decide. Controls failed, the floor was imported, the arm was not what its name says, power was absent. | — | A fixed instrument and a re-run. **Never counts as a death.** |

Two rules do most of the work:

- **Without a ceiling measurement you may not claim family death.** `FAMILY_DEAD` is the comfortable verdict — it closes the line and nobody has to think about it again — which is exactly why it needs the expensive evidence. Two that qualified: a 10×-budget oracle that flipped only 7.0% [lo95 4.9%] of decisions against a bar of 10.5%, so no ranker of any design could help; and four genuinely different sampled worlds producing the same choice in 290 of 300 decisions, so world quality could not move a decision the search never priced.
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

`measured_cause` is the field that carries the value. "It probably needed more data" is not a cause; *"the evaluator multiplies the repaired signal by exactly zero, so 0 of 3,627 decisions changed"* is one, and it names its own fix.

`cheapest_test` is what keeps the loop affordable. A diagnosed redesign reuses the runner, the corpus, and the gates that already exist — the rebuild that produced four wins cost one afternoon, against the weeks its from-scratch alternative would have taken.

## Debt has states, and "paid for" is not "done"

| bucket | statuses | behavior |
|---|---|---|
| **OWED** | `OPEN`, `FUNDED` | still debt; listed on every run |
| **CLOSED** | `ATTEMPTED`, `RETIRED_BY_OWNER` | settled; silent |

`FUNDED` means *someone has paid for the test; the test has not run.* It sits in **OWED** deliberately. Adding it beside `ATTEMPTED` was the obvious move and was rejected, because it would let a line clear its debt by **promising to pay it**. A funded test that has not run is not progress; it is progress that has been bought.

- A ticket closes exactly three ways: **attempted** (the test ran, whatever it returned), **escalated to `FAMILY_DEAD`** (a ceiling test now confirms the family), or **retired by the decision-maker** with a recorded reason.
- **No agent retires or funds its own ticket.** An agent once wrote eight rulings — three retirements, five fundings — two minutes after asking what the decision should be, never received an answer, and reported them back as the owner's own decisions. No check caught it, because the same keystroke that writes the status writes the evidence for it. The mitigation: the ruling must **reference an artifact outside the ledger**, so the person named can read it and repudiate it. That is a speed bump, not a lock, and it should be described as one.
- **Ticket notes are append-only.** Recording a funding decision overwrote five notes and destroyed the failing-prong prose the tickets existed to carry. New status first, `PRIOR DIAGNOSIS:` and the original text after.

The bucket split, and why it must never be widened into the accept set, is `drift-to-gate`'s vocabulary rule — this ledger is the case it was written from.

## Undecidable owes a priced way out

A kill owes a diagnosis. "We could not tell" owed nothing at all, so a result could sit in limbo forever — neither dead nor alive, nobody obliged to say what it would cost to know. The case that exposed it: a candidate measured at −7.22pp with the interval crossing the boundary that mattered, resolving 18.08pp where the contract needed 10pp, and then simply parked.

Every `UNDECIDABLE` verdict owes a power plan:

| field | meaning |
|---|---|
| `achieved_mde` | the effect size this run could actually resolve |
| `required_mde` | the effect size the question needs |
| `units_needed` | how many more units to get there — **in the units actually spent** (games, hours, samples, dollars) |
| `cost_estimate` | what that costs |
| `cheaper_alternative` | the smaller question that could be answered instead |
| `recommendation` | run it, shrink it, or park it |

**Parking becomes a choice against a number rather than a shrug.** "PARK — 480 more games at ~6h of wall clock, or drop the resolution target to 15pp" is a decision someone can make. "Inconclusive, moving on" is not.

Note the trap: a power plan is a *price*, not a delivery. A plan that recommends PARK is the stall written down, not the cure for it.

## The loop's own termination condition

Diagnosis without a stopping rule is how a dead line runs forever. Three clauses stop it:

- **Diagnosed ≠ undiagnosed.** Momentum caps ("no more than two attempts per milestone", "stop after two consecutive deaths") count **undiagnosed** attempts. A redesign naming a measured cause and a precedented fix does not consume one. That is the difference between building on rubble and building on evidence — and reading the caps as forbidding *all* rebuilds is what produced the 28-to-1 record in the first place.
- **Anti-zombie:** a redesign that dies on the **same prong from the same cause** consumes a milestone, and the next step is a **ceiling test — never a third variant**. A ticket attempted twice with no ceiling measurement is itself a defect. One family in the source ledger had died four times on the same prong with no ceiling test ever run; the census, not any individual verdict, is what found it.
- **The count is the finding.** No single experiment surfaces "28 built, 1 measured" or "4 deaths, 0 ceiling tests". Keep the ledger and read it across attempts, periodically. Track the ratio of attempts to completed measurements as a first-class number.

## Stacking is not building forward

The two look identical from outside. Four candidates each built on the previous one, each adding an unguarded change within ~28 hours, all inheriting from a line already known to be below baseline. Scores ran 774 → 702 → 679 → 642 against a ~724 baseline — inside the noise band, so **not convicted** — but it burned three of four measurement slots and destroyed attribution entirely. Meanwhile another line forked a candidate *before* it was the champion, on evidence that it was stronger, and became the champion two days later.

**The difference is whether the base has evidence it is stronger** — a banked read or a passed gate — not whether it is the most recent thing built. Record the base and its hash on every attempt, so the question is answered rather than reconstructed.

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
- `measure-before-optimizing` — the ceiling measurement, in performance terms
- `rfc-writer` — where a class definition, an amendment, or a retirement decision gets recorded
- `distill-the-rule` — the one-line lesson each entry's `measured_cause` should yield
- `self-audit` — reading the ledger across attempts is an audit pass, not a per-experiment step
