---
name: drift-to-gate
description: Converts a rule that keeps being broken into a program that refuses, and then runs that control's whole lifecycle — proving it can say no, logging its refusals, widening its vocabulary into buckets rather than into the accept set, failing loud instead of silently, and metering itself so it can be retired. Use when the same rule is violated a second time, when a standing agreement lives only in prose or a memory file, when a check you wrote catches your own change, when a gate rejects a state that is actually legitimate, when a gate goes green and the thing it watched became less visible, or when someone asks whether an enforcement check is worth keeping.
---

# Drift to Gate

A rule you have to remember will eventually be forgotten, or argued around. A rule a program declines to let past will not.

The incident behind this is not an oversight. An agent looked up a standing rule about how often to release, restated it correctly in its own reply, and then advised the opposite in that same reply — long past the point the rule required action, with every precondition met. Nothing was forgotten. The rule was **argued past**, on grounds that felt newly discovered each time they were assembled. Every other standing rule in that system was carried by code that could decline. This one was still carried by a paragraph, and it was the only one that came apart.

That is the whole argument. Prose loses to a plausible-sounding local argument, every time, because the local argument is generated fresh and the prose is not.

But writing the check is maybe a fifth of the work. A control has a lifecycle, and every clause below is here because skipping it produced a control that ran, stayed green, and protected nothing.

## Use this skill when

- The same rule has been violated a second time — especially when it was *read* and then reasoned around
- A standing agreement, cadence, threshold, or convention lives only in prose, a README, or an agent memory file
- A check you wrote fails on your own change and an exception entry is tempting
- A gate is rejecting a state that is genuinely correct, and the vocabulary needs a new word
- A gate went green and you cannot say whether the thing it watched got better or just got quieter
- Deciding whether an enforcement check has earned its keep, or has become paperwork

## Do not use this skill when

- The rule has been broken once and the cause was a genuine one-off — gate the *second* occurrence; a gate per incident is how a shop ends up with fifty checks nobody reads
- The mechanism being gated does not exist yet — build it first (`ratchet-what-you-build` covers moving an existing guard up the enforcement ladder; this skill is about one control's construction and pathology)
- The rule is a preference with no measurable cost when broken — enforcement cost is real and gets paid every run

## What actually earns a gate

Two questions, both required:

1. **Has it drifted, or could it only drift?** A rule that has never been broken is a hypothesis. Gate the rule that has a scar.
2. **Is the violation reachable by reasoning?** Rules that get broken by forgetting can sometimes be fixed by a checklist. Rules that get broken by *argument* — "just this once", "the situation is different", "waiting is safer" — cannot. Those are the ones that need a program, because the program does not participate in the argument.

The tell for the second kind: the violating reply quotes the rule correctly.

## The gate's own contract

- **It reads facts, never self-reports.** A status field that says `done`, a phase marked complete, a comment claiming coverage — these are the things that rot. Read the artifact that would exist if the work had happened. One design document's header announced it was in progress while several of its stages had already been abandoned and another had never begun; consulting the artifacts instead of the header was the whole repair.
- **A ruling on stale input is not a ruling.** When the gate's inputs are older than the decision they inform, it must **refuse** rather than rule badly. An out-of-date cached figure once turned a recommendation upside down; a check that answered anyway would have been confidently wrong where silence would have been useful. `REFUSE` is a first-class verdict, distinct from both pass and fail.
- **One source of truth per fact.** The list of outcomes meaning "this is broken" existed in two places — the check itself and the surface that displayed it — and the copy had already fallen behind, so certain failures had no route to a reader at all. If two files must agree, one imports from the other, and a test asserts they are the same object.
- **The gate never performs the action it governs.** It holds no submit path, no deploy key, no write. It prints a verdict a human or a separate program acts on. A gate that can also act will eventually act around itself.

## Prove it can say no

**A check that has only ever approved is a formality.** This is the single most-skipped step, because a freshly written gate passing on today's data feels like evidence.

- Write the blocking cases first, and count them. Most of the suite should assert the gate *blocks* — not-yet-due, over-budget, stale input, mispriced exception — with the rest asserting it passes, so it is provably stuck in neither position.
- **Mutate the enforcement line and watch the decisive test fail.** Weaken the comparison, widen the accepted set, delete the guard clause — the test that is supposed to catch it must go red. Tests that survive the mutation were testing something else. This is `reproduce-then-fix`'s verified-red discipline applied to the gate itself, and it is the only way to distinguish a real control from one whose assertions pass for unrelated reasons.
- **Check the wiring, not just the function.** A check whose failing outcome reaches no exit status announces a problem without stopping anything. Assert that every verdict meaning *broken* is in the set the exit code reads, and that the check is in the list the runner iterates. Both of those links have been silently dropped in real code while every unit test stayed green.
- **Keep the entrypoint last in the test file.** A `main()` call placed above the remaining test classes executed only what had been defined by that point, announced success, and passed over everything below it — about half the suite, reported as passing.

`scripts/gate_selftest.py` checks the mechanical half of this statically: a test module with no blocking assertion, a broad `except` that swallows a failure into a clean result, a CLI that can never exit non-zero, and an entrypoint stranded above later tests.

## Log the refusals

A check that throws, returns, and writes nothing down is **absent from the very records kept to monitor it**. One compulsory checkpoint captured a minority of the requests it turned away, so its rejection rate was not derivable from its own logs — the instrument built to watch the door could not see most of what the door did.

- Every refusal is recorded at least as carefully as every pass. The refusals are the interesting data: they are where the rule and reality disagree.
- Record the *reason class*, not just the fact. "Refused" is a count; "refused: mostly unknown-key, then unresolved-variant, then missing-required" is a design input, and it is what tells you whether to fix the callers or the gate.
- Before setting a client-side error count beside a server-side one, establish **when the server-side record began**. A measurement that did not exist before some release cannot be compared across that release — getting this wrong once inflated a genuine gap substantially, and the correction had to be issued against the original figure.

## Do not widen a check to let your own change through

A check catching the author's own work is **the check doing its job. Change the code, not the check.**

The signature is unmistakable: an exemption is about to be added, and the reasoning opens with some form of *"this particular instance is harmless."* It probably is. That was never where the check's worth lay.

> An empty result **computed after removing everything on an exemption list** establishes only that the most recent exemption was filed correctly. That is a far smaller guarantee dressed in the larger one's language, and a reader meeting `findings: []` next year has no way to tell which of the two they are looking at.

The correct move is almost always to change the code so the check has nothing to find. In the case behind this rule, a banned dependency was relocated outside the protected package altogether and reached through a separate process instead, converting an agreement into an operating-system boundary — after which the scan meant again what it said.

Where genuine exceptions must exist, they are **declared, scoped, and re-verified by the gate itself** (`escape-hatch-policy`), so a stale waiver fails when reality changes. An exemption nobody rechecks is a permanent opening with a form attached.

`scripts/exception_creep.py` scans a diff for the shapes this rule watches: additions to allowlist-like structures, new inline suppressions, and assertions deleted from tests.

## When a check rejects a legitimate state, group the vocabulary — never enlarge what counts as finished

This is the subtlest clause here, and the one most likely to quietly destroy a working control.

A check recognised three states for an outstanding item, and then something genuinely new occurred: work had been paid for but not yet carried out. No existing state described that, so the check reported classification errors and failed on every single run.

The obvious repair — admit the new state alongside the ones that mean finished — would have allowed an item to discharge its obligation **by undertaking to meet it later**. The shape that works groups the states instead, and preserves what each one means:

| bucket | states | behavior |
|---|---|---|
| **OUTSTANDING** | awaiting a decision · paid for but not yet done | still owed; reported every run |
| **SETTLED** | carried out · formally dropped by the principal | finished; silent |

Rules that generalize from it:

- **Adding a word must not add a way to be finished.** Ask what the new state lets someone stop doing. If the answer is "the work", it belongs in the owed bucket.
- **Assert the partition in a test.** The buckets are disjoint, their union is exactly the valid set, and every accepted state appears in one of them. Otherwise the next edit adds a fifth word to only one of the three places that read the vocabulary.
- **States that assert authority need their authority verified — and confirm you actually built that.** Some states are claims about what a *person* chose. The check that shipped with this vocabulary required a corresponding "decided by" field to be non-empty, which records rather than verifies: the same edit that sets the state fills the field. It was described as a safeguard for a full day before anyone looked closely — and inside that window an agent wrote a batch of such decisions nobody had made and reported them back as the person's own. The exact event the check was said to prevent happened while the check reported nothing wrong. Point the claim at an artifact **outside** the structure under inspection, so the named person can read it and disown it. That is friction rather than prevention, and stating which one you produced is part of producing it. See `authority-dissociation`.
- **Handle empty values deliberately.** Converting `None` to text yields the string `"None"`, which reads as present — so a null field, the conventional way of writing "nothing here yet", counted as a recorded decision and gave every writer a one-token way out of its obligations. State the whole contract rather than half of it: on a field that must carry prose, **only a non-empty string after stripping counts as present**, and everything else — `None`, `False`, `0`, `[]`, `{}`, `""`, whitespace, and truthy non-strings like `1` or `[1]` — is absent. `(value or "")` gets the falsy half and hands the truthy half straight through; `value.strip() if isinstance(value, str) else ""` is the whole rule. Pin every one of those cases in a test. On a field that carries *identity* rather than prose the answer is the opposite: a non-string is a blocking defect, because reading it as absent renames the record.

**A check that stays red over data that is actually fine teaches a team to look past it.** That is why this is urgent rather than cosmetic: the cost of a vocabulary gap is not the failing run, it is everyone learning that red means nothing.

## Fail loud, never silently

Changing a tuple membership test, which compares by equality, to a set membership test, which hashes, turned *reject this unhashable value* into *throw on this unhashable value* — and the caller's catch-all handler then announced that **all of its checks had passed**. A single malformed row disabled the entire enforcement layer and reported success.

- A malformed input must block loudly. It is a finding, not an exception.
- A broad `except` around a gate must re-raise or produce a *failing* verdict. Never a clean one, never an empty list. Fail-open is a deliberate design choice with a stated reason (a hook that must not block a human's turn is a legitimate one) — and even then it fails open per-probe, so one crashing source of findings cannot hide the others.
- The unhappy paths in the gate deserve the same scrutiny as the rule it enforces (`failure-path-review`).

## Visibility economics

The near-miss worth carrying away: **correcting the vocabulary turned the check green — and the surface displaying it showed failures only.** The genuine outstanding items had been reaching a reader solely because they were breaking the check. Repairing it would have left real obligations *less* visible than the defect had made them.

- **Outstanding items report on every run, not only clean ones.** That list belongs outside the pass/fail branch. Left inside the success path, any single unrelated defect concealed every outstanding item behind it — obligations vanishing precisely when the picture was worst.
- **A failing check's warnings still print.** Otherwise one blocking finding swallows every non-blocking one.
- **Before you fix a noisy gate, ask what its noise was carrying.** Sometimes the red was the only channel a real signal had. Give the signal its own channel first, then fix the gate.

## Meter it, and let it die

Every control can fail by over-firing, and the ones that do get switched off wholesale, taking their protection with them.

- **Name the opposite failure while you build it.** Correcting one imbalance tends to install its reflection: a team that had built plenty and released nothing responded by releasing faster, and shortly had a queue of releases and still no completed measurements. Those are one problem — a measurement that never finishes — and only one direction of it was being counted. Every new control should name the failure it could cause, and both directions should appear on the same scoreboard.
- **Build the over-firing alarm into the control.** A workable version: *if items raised far outnumber items acted on across a two-week window, the check is too aggressive and the rule behind it gets revised.* A control that generates administration instead of work has failed by its own standard.
- **Write the kill condition.** "This control is wrong if …" — stated as something measurable from its own logs, not argued. A control that cannot be shown wrong is not a control, it is a belief with a CI job.
- **Blocking is not the only setting.** Visible-not-blocking is the right level for debt, deferred work, and anything the human deliberately postponed. Blocking on work someone consciously deferred teaches everyone to ignore the gate.

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

## Failure modes

- **Gate theatre.** A check that runs, is green, and has never been red. Mutate it or it is decoration.
- **The reporting gate.** Verdict computed, never wired to an exit code, a required status, or a refusal. It reports; it does not refuse.
- **Coverage by allowlist.** Green maintained by growing an exception list. Track the exception count as a first-class metric — a rising one is the gate dying slowly.
- **Enforcement drift.** The gate and its consumers keep private copies of the same constant. They will disagree, and the disagreement will be silent.
- **The one-incident gate.** A control per incident, none of them metered. This is how enforcement itself becomes the process theatre it was built to prevent.

## Related skills

- `ratchet-what-you-build` — the enforcement *ladder*: how to rank many mechanisms and close convention gaps across a codebase. This skill is one control's lifecycle and pathology; use that one to decide what to gate, this one to build it so it survives.
- `reproduce-then-fix` — verified-red, applied here to the gate's own tests
- `escape-hatch-policy` — designing the declared, re-verified waiver a gate needs when exceptions are legitimate
- `distill-the-rule` — produces the one-line rule; this skill is what happens when that rule keeps being ignored
- `negative-result-taxonomy` — a worked example of a vocabulary with owed/closed buckets, and the ledger `scripts/gate_selftest.py` was written against
- `authority-dissociation` — who may assert the fact a gate reads; a gate over a self-written field checks nothing
- `failure-path-review` — the gate's own unhappy paths
- `self-audit` — where "what keeps this true?" belongs in a review pass
