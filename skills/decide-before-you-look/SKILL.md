---
name: decide-before-you-look
description: Pre-registers what a run will decide before the data exists — a six-line call block with a predicted number, an 80% interval required to be tighter than the range the decision turns on, a probability of surviving, the likeliest reason to be wrong, and the artifact already on hand that could answer it without running anything. Covers frozen thresholds and append-only amendments, refusing to lower a bar after seeing results, pre-committing where a null sends the effort, reporting a leaning alongside the deciding measurement, never adjusting a run in flight, and where a stakeholder's multiplier belongs. Use before any experiment, benchmark, A/B, spike, or evaluation; when a threshold is being changed after results are visible; when a run is producing an inconvenient answer; or when someone asks for "N times better".
---

# Decide Before You Look

Thresholds move after the results arrive, and whoever moves them experiences it as having understood the problem better. That is not weakness to be resisted harder — it is what seeing an outcome does to someone who was hoping for a particular one. The only dependable remedy is to write the decision down while the answer is still unknown, somewhere that cannot be quietly revised.

The core is one short artifact. Everything else here is what it costs to skip it.

## Use this skill when

- Designing any experiment, benchmark, A/B test, spike, kill-test, or evaluation
- Any threshold or success criterion is being set — or changed once results are visible
- A run is underway and producing an inconvenient answer
- A stakeholder asks for "3× better", "half the latency", or any multiplier on an outcome
- Reporting a partial result while the measurement that decides is still running
- Reviewing whether a finished evaluation actually settled anything

## Do not use this skill when

- The work carries no decision — exploratory reading, or a spike whose only output is a description of the terrain. Say so explicitly: an exploration relabelled as a test once it produces a pleasing number is the precise failure this prevents.
- The measurement is free and instantly repeatable, so being wrong costs another few seconds

## The call block

Six lines, written and committed **before the run begins**. It fits on half a page.

| # | Line | Why |
|---|---|---|
| 1 | **The metric, with units** | Fixes what will be read, so the reading cannot be swapped later |
| 2 | **The predicted number** | A point estimate. Being wrong is fine; being unfalsifiable is not |
| 3 | **An 80% interval** | **Tighter than the band the decision turns on.** Otherwise the run settles nothing |
| 4 | **P(survives)** | Your own odds, on the record. Calibration is unlearnable without them |
| 5 | **The likeliest reason I am wrong** | Names the failure you would otherwise meet as a surprise and explain away |
| 6 | **The artifact already on hand that could answer this without running anything** | The line that pays for the rest |

Line 3 is arithmetic, not judgement, and it is the one people skip. If your own interval is wider than the distance between "keep going" and "stop", both outcomes sit comfortably inside what you already believe, and the run buys nothing. Check it before committing the machine time.

**Line 6 earns the whole practice.** It came out of an audit of how graded machine time was actually spent: a clear majority of it produced facts that were already sitting in existing files. One long hold answered a question a short lookup would have settled. Answering line 6 honestly — "none, and here is why" is a complete answer — is the cheapest step here and the one that most often calls the run off.

`scripts/call_block.py` validates the block, arithmetic included.

## Pre-registration mechanics

- **Thresholds live in a validated artifact, not in prose.** A number in a paragraph can be reread generously. A number in a schema-checked file has to be edited, and the edit appears in a diff.
- **Commit before the data exists.** The commit history is the evidence. A registration written after the first measurement arrives is a description, whatever it is called.
- **Amendments are additive and name what they amend.** A change lands as a new document referencing the commit or hash of the version it revises; the original is never edited in place. That is what turns "we changed the threshold" into a visible act.
- **Declare the whole band, not just the bar** — what counts as continue, what counts as stop, and what counts as *the instrument failed*, which is a third outcome rather than a synonym for either.

## Do not lower a bar to fit the result

**When results reveal the threshold was set against a badly measured quantity, stop the work; do not adjust the threshold to match what turned up.**

The case behind this: a probe's threshold had been set against an opportunity counted at the wrong point in the process. Re-counted correctly, the real opportunity was a small fraction of it — far under the bar. The work was stopped rather than re-scoped, because lowering a threshold once the result is visible is the exact move pre-registration exists to prevent, and it stays that move even when the original figure was genuinely mistaken.

The distinction that keeps this usable: **revisiting a criterion after seeing results is defensible only when all three hold** — the criterion was declared in advance, the data it relies on is pre-treatment (a baseline or a headroom measurement rather than an outcome), and the order in which things were looked at is disclosed alongside the number. Anything else is a new experiment, and it starts with a new call block.

## Documenting a flaw does not remove it

One registration recorded, in writing, that a particular arm was capped and could not express the effect being measured — and then included that arm in the headline number anyway. It dragged a real, substantial effect down by roughly half and produced a failing verdict. Every control passed: it was an accurate reading of a badly constructed measure.

**Writing the caveat felt like rigour and worked as an excuse.** When a written note is all that stands between a known-invalid input and the computed result, the note loses, because the computation is what happens and prose is not. Remove the arm, or move it to a secondary reading where its ceiling does not matter.

The companion rule: **the estimate that admits something to a measure must be precise enough to make that call.** The bad arm was admitted on a small pilot whose interval spanned the entire question. Size that pilot to the decision it is making.

## A null is a result, decided in advance

Before the run, write down **where the effort goes if the answer is null** — name the next item on the ranked list of suspected causes.

This removes the pressure that quietly corrupts every kill test: wanting an expensive run to have been worthwhile. **A test where only one outcome counts as success gets re-read until it produces that outcome.** And when nothing can be named as the destination for a null, the run has no bearing on any decision, and building it is the mistake.

## Report the leaning and the decider together

While a run is live, give both halves in the same breath, every time:

1. **Which way the evidence currently points**, and
2. **Which measurement has the power to decide, and whether it has reported.**

The first without the second is how a run gets stopped on whichever arm finished first — and the first to finish is usually the quickest, which is often the least informative. The second without the first conceals the state of the evidence and makes the final verdict look like it appeared from nowhere.

Before starting, name the arms that *cannot* decide: ceiling-bound, underpowered, wrong population. Never let an arm that was not designated as the decider end the run.

## Do not adjust a run in flight

A run that is touched while running — an arm edited, a parameter nudged, a step completed by hand — is a story, not an experiment. **Stop it, record the intervention as an event, and either re-register or discard.** A process that is sometimes intervened in cannot be studied, because nobody can say what produced the number.

## Where a stakeholder's multiplier goes

When someone asks for "3× better", the first work is arithmetic, not design:

1. **List what the multiplier could mean, price each reading against the room that actually exists, and rule out the impossible ones on paper.** Most readings of a bold multiplier exceed the entire available room; a target above the whole opportunity yields documentation, not candidates.
2. **Attach the multiplier to a quantity that already has a number** — decisions settled per cycle, the margin required before calling something real — rather than to the outcome. Those are usually free.
3. **The shipping threshold never carries the ambition.** Restricting what may reach the real measurement is how a team accumulates a shelf of careful, unmeasured work.
4. **Replay any new threshold against past verdicts before adopting it.** If it rewrites history, it is a different instrument rather than a higher bar, and it needs validating on its own.

## Failure modes

- **The retrospective hypothesis.** A finding written up as though predicted. If it was not in the call block, label it exploratory.
- **The unresolvable run.** Interval wider than the band, launched regardless. Line 3 exists to catch this before the spend.
- **The alibi caveat.** A known flaw documented in the registration and included in the result anyway.
- **The run stopped early.** The convenient arm reports, the verdict is announced, the deciding arm never finishes.
- **The quiet amendment.** A threshold edited in place. If the original can change without a diff somebody reads, nothing was registered.
- **Success-only design.** No pre-committed destination for a null, so the run gets re-read until it agrees.

## Related skills

- `negative-result-taxonomy` — what a null owes once it lands, and how an undecidable result gets priced
- `measure-before-optimizing` — instrument resolution and honest benchmarking; where the numbers a call block predicts come from
- `authority-dissociation` — the tuning measure must not be the rejecting measure, and who may declare a run finished
- `drift-to-gate` — putting the frozen threshold somewhere that refuses rather than somewhere that is remembered
- `rfc-writer` — additive amendment discipline, applied to design decisions rather than thresholds
- `distill-the-rule` — a surprising call-block miss is a calibration finding worth keeping
