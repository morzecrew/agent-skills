---
name: decide-before-you-look
description: Use before any experiment, benchmark, A/B, spike, or evaluation; when a threshold is set or moved after results are visible; when a run is producing an inconvenient answer; or when someone asks for "3x better". Not for exploration that decides nothing.
roles: [author, implement]
gate: call-block
---

# Decide Before You Look

Thresholds move after the results arrive, and whoever moves them experiences it as having understood the problem better. That is not weakness to be resisted harder — it is what seeing an outcome does to someone who was hoping for a particular one. The only dependable remedy is to write the decision down while the answer is still unknown, somewhere that cannot be quietly revised.

The core is one short artifact. Everything else here is what it costs to skip it.

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

`scripts/call_block.py` validates the block, arithmetic included. Given `--committed-before RESULT` it also reads git: the block must have reached history before the result did *and stopped changing there*, since a registration edited in place once the answer is visible is the quiet amendment below rather than a prediction.

## Making it binding

A block that can be edited once the answer is visible registers nothing. It goes
into version control before the run and stops changing there; a correction is an
**appended amendment** with its own timestamp and reason, never an in-place edit.
`scripts/call_block.py --committed-before RESULT` is what checks that, and the
mechanics are in [references/registration.md](references/registration.md).

Three evasions the mechanics exist to catch, each of which leaves the block
technically intact:

- **A flaw named in the write-up is still a flaw.** Documenting that the control group was contaminated does not decontaminate it; disclosure changes who else knows, not what the run can decide.
- **A leaning reported without its decider reads as the result.** If the measurement that decides is still running, say which one it is and that it is still running, in the same breath as the number you have.
- **A stakeholder's "3× better" is a decision band, not a prediction.** It belongs in the band the block is measured against, never in the interval — folding it into the interval makes your own uncertainty look like their ambition.

## The bar does not move, and the null is a result

Two rules that are the same rule seen from either end. **A threshold is frozen
when the block is committed** — lowering it once results are visible converts a
test into a description of what happened, and it is the single most common way a
run stops deciding anything. **A null was already assigned a destination** in the
block: where the effort goes if the answer is no. A null with nowhere to send it
gets re-run until it is not one.

The evasions each rule catches, and how they arrive, are in
[references/registration.md](references/registration.md).

## Do not adjust a run in flight

A run that is touched while running — an arm edited, a parameter nudged, a step completed by hand — is a story, not an experiment. **Stop it, record the intervention as an event, and either re-register or discard.** A process that is sometimes intervened in cannot be studied, because nobody can say what produced the number.

## Related skills

- `negative-result-taxonomy` — what a null owes once it lands, and how an undecidable result gets priced
- `measure-before-optimizing` — instrument resolution and honest benchmarking; where the numbers a call block predicts come from
- `authority-dissociation` — the tuning measure must not be the rejecting measure, and who may declare a run finished
- `drift-to-gate` — putting the frozen threshold somewhere that refuses rather than somewhere that is remembered
- `rfc-writer` — additive amendment discipline, applied to design decisions rather than thresholds
- `distill-the-rule` — a surprising call-block miss is a calibration finding worth keeping
