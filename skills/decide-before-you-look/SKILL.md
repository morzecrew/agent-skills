---
name: decide-before-you-look
description: Pre-registers what a run will decide before the data exists — a six-line call block with a predicted number, an 80% interval that must be narrower than the decision band, a probability of surviving, the likeliest reason to be wrong, and the artifact already on disk that could answer it without running anything. Covers frozen bars and append-only amendments, the goalpost-move prohibition, pre-committing a null as a result, reporting a leaning and the deciding arm together, never overriding mid-run, and where an ambition multiplier belongs. Use before any experiment, benchmark, A/B, spike, or evaluation; when a threshold is being changed after results are visible; when a run is producing an inconvenient answer; or when someone asks for "N times better".
---

# Decide Before You Look

Goalposts move after you see the data, and the person moving them experiences it as improved understanding. That is not a character flaw to resist harder — it is what looking at results does to the person who wanted a particular one. The only reliable fix is to write the decision down while the answer is still unknown, somewhere that cannot be quietly edited afterward.

The discipline has a cheap core and an expensive-to-skip periphery. The core is one artifact.

## Use this skill when

- Designing any experiment, benchmark, A/B test, spike, kill-test, or evaluation
- Any threshold, bar, or success criterion is being set — or changed after results are visible
- A run is underway and producing an inconvenient answer
- A stakeholder asks for "3× better", "half the latency", or any multiplier on an outcome
- Reporting a partial result while the deciding measurement is still running
- Reviewing whether a completed evaluation actually decided anything

## Do not use this skill when

- The work has no decision attached — exploratory reading, a spike whose only deliverable is a description of the landscape. Say so explicitly; an exploration relabelled as a test after it produces a nice number is the exact failure this prevents.
- The measurement is free and instantly repeatable, so the cost of being wrong is another five seconds

## The call block

Six lines, written and committed **before the run starts**. It fits on half a page and is the highest-value artifact here.

| # | Line | Why |
|---|---|---|
| 1 | **The metric, with units** | Names what will be read, so the reading cannot be swapped afterward |
| 2 | **The predicted number** | A point estimate. Being wrong is fine; being unfalsifiable is not |
| 3 | **An 80% interval** | **Must be narrower than the decision band.** If it is not, the run cannot resolve anything and should not be run |
| 4 | **P(survives)** | Your own odds, stated. Calibration is only learnable if predictions are recorded |
| 5 | **The most likely reason I am wrong** | Names the failure mode you would otherwise discover as a surprise and rationalize |
| 6 | **The artifact already on disk that could answer this without running anything** | The line that pays for the whole block |

Line 3 is the one people skip, and it is arithmetic, not judgment: if your own predictive interval is wider than the gap between "alive" and "dead", then either answer is consistent with your prior and the run buys nothing. Check it before spending the machine time.

**Line 6 is the one that pays.** It was minted from a measured audit of graded machine time: **two thirds of it bought facts that were already on disk.** One multi-hour hold learned what a sixty-row lookup would have answered. Answering line 6 honestly — including "none, and here is why" — is the cheapest step in this entire skill and the one that most often cancels the run.

`scripts/call_block.py` validates the block, including the line-3 arithmetic.

## Pre-registration mechanics

- **Bars live in a validated artifact, not in prose.** A number in a paragraph is a number that can be reread charitably. A number in a schema-checked contract has to be edited, and the edit shows up in a diff.
- **Commit before the data exists.** The git timestamp is the evidence. A pre-registration written after the first arm reports is a post-registration, whatever it is called.
- **Amendments are append-only and reference the frozen base.** A change lands as a new document naming the base commit or hash it amends; the base is never silently edited. This is what makes "we changed the bar" a visible act rather than an invisible one.
- **Declare the decision band, not just the bar** — what counts as alive, what counts as dead, and what counts as *the instrument failed*, which is a third outcome and not a synonym for either.

## The goalpost-move prohibition

**When a result reveals that the bar was set against a mis-measured quantity, kill the build; do not amend the bar down to fit what you found.**

The case: a probe's pre-registered bar was set against an opportunity counted at one decision point. The measurement turned out to be counted at the wrong point, and the honest opportunity was a small fraction of it — far below the bar. The build was killed rather than amended, because *moving the bar after seeing the result is the goalpost move the gates exist to prevent*, and it stays the goalpost move even when the original number was genuinely wrong.

The distinction that keeps this workable: **re-gating after seeing a result is defensible only when all three hold** — the criterion was pre-declared, the data it uses is pre-treatment (a baseline or headroom measurement, not an outcome), and the look order is disclosed in the same breath as the number. Anything else is a new experiment, and it starts with a new call block.

## Naming a defect is not removing it

A pre-registration once recorded, in writing, that one arm was capped and could not express the effect being measured — *"IN, but capped: it cannot show more than 10pp"* — and then included it in the primary metric anyway. That arm averaged a real, large effect down by half and returned FAIL. Every control passed: it was a true reading of a badly built metric.

**Writing the caveat felt like diligence and functioned as an alibi.** If a written note is the only thing standing between a known-invalid input and the computed result, the note loses — because the metric is what gets computed, and prose is not. Remove the arm, or keep it in a secondary that is not ceiling-bound.

The sibling rule: **gate on an estimate precise enough to decide the gate.** The bad arm entered on a small pilot whose confidence interval spanned the entire decision. Size the gating probe to the gate it is gating.

## A null is a result, and it is pre-committed

Before the run, write down **where the effort goes if the answer is null.** Name the next item on the ranked list of causes.

This removes the incentive that quietly corrupts every kill test: the wish for an expensive run to have been worth it. **A test in which only one outcome counts as success will be read until it produces that outcome.** And if you cannot name what a null would redirect you to, the test is not decision-relevant and should not be built.

## Say which way it leans, and refuse to call it

While a run is live, report both halves in the same breath, every time:

1. **Which way the evidence leans right now**, and
2. **Which arm has the power to decide, and whether it has reported.**

The first without the second is how a run gets stopped early on whichever arm landed first — and the first arm to land is usually the fastest one, which is frequently also the least informative. The second without the first hides the state of the evidence and makes the eventual verdict look like it arrived from nowhere.

Before the run, name which arms *cannot* decide: ceiling-bound, underpowered, wrong distribution. Never let an arm that was not pre-named as the decider end the run.

## Never override mid-run

A run that is touched mid-flight — one arm edited, a parameter nudged, a step finished by hand — is an anecdote, not an experiment. **Stop it, log the override as an event, and either re-register or discard.** A sometimes-overridden process cannot be studied, because you can no longer say what produced the number.

## Where an ambition multiplier goes

When a stakeholder asks for "3× better", the work is arithmetic before it is design:

1. **Enumerate every reading of the multiplier against the measured opportunity, and kill the impossible ones in writing.** Most readings of a bold multiplier exceed the entire available headroom; a bar above the whole opportunity produces paperwork, not candidates.
2. **Put the multiplier where a number already exists** — verdicts resolved per cycle, the strength required to call a mechanism alive — not on the outcome. Those are usually free.
3. **The ship gate never carries the ambition.** Tightening what may reach the real judge is how a team ends up with a shelf of careful, unmeasured work.
4. **Retro-verify any new threshold before adopting it:** replay it against every past verdict. If it rewrites history, it is a new instrument rather than a raised bar, and it needs its own validation.

## Failure modes

- **The retrospective hypothesis.** A finding written up as though it had been predicted. If it was not in the call block, say it was exploratory.
- **The un-resolvable run.** Interval wider than the decision band, launched anyway. Line 3 exists to catch this before the spend.
- **The alibi caveat.** A known defect documented in the pre-registration and included in the metric regardless.
- **The stopped-early run.** The convenient arm reports, the verdict is announced, the deciding arm never finishes.
- **Silent amendment.** The bar edited in place. If the base document can be changed without a diff someone reads, there is no pre-registration.
- **Success-only design.** No pre-committed destination for a null. The run will be re-read until it produces the wanted answer.

## Related skills

- `negative-result-taxonomy` — what a null owes once it lands, and how an undecidable result gets priced
- `measure-before-optimizing` — instrument resolution and honest benchmarking; the source of the numbers a call block predicts
- `authority-dissociation` — the fitting metric must not be the killing metric, and who may declare a run finished
- `drift-to-gate` — putting the frozen bar somewhere that refuses, rather than somewhere that is remembered
- `rfc-writer` — append-only amendment discipline, applied to design decisions rather than thresholds
- `distill-the-rule` — a surprising call-block miss is a calibration finding worth keeping
