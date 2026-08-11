---
name: drift-to-gate
description: Converts a rule that keeps being broken into a program that refuses, and then runs that control's whole lifecycle — proving it can say no, logging its refusals, widening its vocabulary into buckets rather than into the accept set, failing loud instead of silently, and metering itself so it can be retired. Use when the same rule is violated a second time, when a standing agreement lives only in prose or a memory file, when a check you wrote catches your own change, when a gate rejects a state that is actually legitimate, when a gate goes green and the thing it watched became less visible, or when someone asks whether an enforcement check is worth keeping.
---

# Drift to Gate

A rule enforced by memory drifts. A rule enforced by a program that refuses does not.

The incident that earns this skill is not forgetting. An agent read a standing cadence rule, quoted it accurately in its own reply, and recommended the opposite action in the same reply — many cadence windows overdue, with the rule's own precondition satisfied. The rule was not forgotten; it was **reasoned around**, with a justification that sounded fresh each time it was constructed. Every other standing rule in that system was enforced by a program that refuses. Cadence was the only one still living as prose, and it was the only one that drifted.

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

- **It reads facts, never self-reports.** A status field that says `done`, a phase marked complete, a comment claiming coverage — these are the things that rot. Read the artifact that would exist if the work had happened. One spec's frontmatter read `Accepted` while several of its phases were dead and one had never started; reading the disk instead of the label was the entire fix.
- **A ruling on stale input is not a ruling.** When the gate's inputs are older than the decision they inform, it must **refuse** rather than rule badly. A stale cached number once inverted a recommendation from *go* to *hold*; a gate that ruled on it would have been confidently wrong instead of usefully silent. `REFUSE` is a first-class verdict, distinct from both pass and fail.
- **One source of truth per fact.** The set of "verdicts that mean broken" was written twice — once in the gate, once in the surface that reported it — and the second copy had already drifted, so some failure modes could never reach the human at all. If two files must agree, one imports from the other, and a test asserts they are the same object.
- **The gate never performs the action it governs.** It holds no submit path, no deploy key, no write. It prints a verdict a human or a separate program acts on. A gate that can also act will eventually act around itself.

## Prove it can say no

**A gate that only says GO is a rubber stamp.** This is the single most-skipped step, because a freshly written gate passing on today's data feels like evidence.

- Write the blocking cases first, and count them. Most of the suite should assert the gate *blocks* — not-yet-due, over-budget, stale input, mispriced exception — with the rest asserting it passes, so it is provably stuck in neither position.
- **Mutate the enforcement line and watch the decisive test fail.** Weaken the comparison, widen the accepted set, delete the guard clause — the test that is supposed to catch it must go red. Tests that survive the mutation were testing something else. This is `reproduce-then-fix`'s verified-red discipline applied to the gate itself, and it is the only way to distinguish a real control from one whose assertions pass for unrelated reasons.
- **Check the wiring, not just the function.** A gate whose bad verdict is not connected to a non-zero exit reports and does not refuse. Assert that every verdict meaning *broken* is in the set the exit code reads, and that the check is in the list the runner iterates. Both of those links have been silently dropped in real code while every unit test stayed green.
- **Keep the entrypoint last in the test file.** A `main()` invocation sitting above later test classes ran the tests defined so far, printed OK, and silently skipped every class below it — roughly half the suite, reported green.

`scripts/gate_selftest.py` checks the mechanical half of this statically: a test module with no blocking assertion, a broad `except` that swallows a failure into a clean result, a CLI that can never exit non-zero, and an entrypoint stranded above later tests.

## Log the refusals

A gate that raises and returns without recording the rejection is **invisible to the ledger built to watch it**. One mandatory chokepoint recorded only a fraction of the calls it refused, so its own failure rate could not be computed from its own telemetry — the metric built to watch the doorman could not see half its work.

- Every refusal is recorded at least as carefully as every pass. The refusals are the interesting data: they are where the rule and reality disagree.
- Record the *reason class*, not just the fact. "Refused" is a count; "refused: mostly unknown-key, then unresolved-variant, then missing-required" is a design input, and it is what tells you whether to fix the callers or the gate.
- Before comparing a caller-side error count to a gate-side one, check **when the gate-side log started**. A metric that did not exist before a ship date cannot be compared across it — that mistake once overstated a real blind spot by a wide margin, and the correction had to be published against the original claim.

## Never allowlist the check that caught you

When a check you wrote catches your own change, **that is the check working. Fix the code, not the check.**

The tell is exact: you are about to add an exception, and the justification begins *"but in this case it's fine."* It may well be fine. The check's value was never about this case.

> A scan that returns clean **after subtracting a list of declared exceptions** proves only that whoever added the last exception remembered to declare it — a much weaker claim wearing the strong one's clothes. Nobody reading `findings: []` six months later can tell the two apart.

The correct move is almost always to change the code so the check has nothing to find. In the case this rule came from, a forbidden import was moved out of the guarded package entirely and re-entered as a subprocess, so the boundary became a process boundary rather than a convention — and the scan went back to proving what it claimed.

Where genuine exceptions must exist, they are **declared, scoped, and re-verified by the gate itself** (`escape-hatch-policy`), so a stale waiver fails when reality changes. An unverified waiver is a permanent hole with paperwork.

`scripts/exception_creep.py` scans a diff for the shapes this rule watches: additions to allowlist-like structures, new inline suppressions, and assertions deleted from tests.

## When a gate rejects a real state, widen the vocabulary into buckets — never into the accept set

This is the subtlest clause here, and the one most likely to quietly destroy a working control.

A gate knew three ticket states — `OPEN`, `ATTEMPTED`, `RETIRED_BY_OWNER` — and the ledger acquired a fourth thing that had happened: tests *funded* but not yet run. The vocabulary genuinely had no word for "paid for, not done", so the gate reported classification defects and exited non-zero on every run.

The obvious fix — add `FUNDED` beside `ATTEMPTED` in the accepted set — would have let a line clear its debt **by promising to pay it**. The correct shape splits the vocabulary into buckets and keeps the meaning:

| bucket | states | behavior |
|---|---|---|
| **OWED** | `OPEN`, `FUNDED` | still debt; listed on every run |
| **CLOSED** | `ATTEMPTED`, `RETIRED_BY_OWNER` | settled; silent |

Rules that generalize from it:

- **Adding a word must not add a way to be finished.** Ask what the new state lets someone stop doing. If the answer is "the work", it belongs in the owed bucket.
- **Assert the partition in a test.** The buckets are disjoint, their union is exactly the valid set, and every accepted state appears in one of them. Otherwise the next edit adds a fifth word to only one of the three places that read the vocabulary.
- **Authority states need an authority check — and check whether you built one.** `FUNDED` and `RETIRED_BY_OWNER` are claims about what a *person* decided. The control shipped alongside this vocabulary required a non-empty `owner_ruling` field, which is bookkeeping in the costume of authentication: the same keystroke that writes the status writes the field. It was described as a control for a full day before anyone noticed — and in that same window an agent wrote a batch of such rulings nobody had given and reported them back as the person's own decisions. The case the check was supposedly preventing occurred, unnoticed, while the check reported clean. Make the claim reference an artifact **outside** the structure being checked, so the person named can read it and repudiate it. That is a speed bump, not a lock, and saying which one you built is part of building it.
- **Normalize falsy values explicitly.** `str(None)` is `"None"`, which is truthy — so a `null` field, the idiom for "no value yet", passed as a recorded decision and handed every agent a one-word escape from its debt. Use `(v or "")`, and pin `None`, `False`, `0`, `[]`, `{}`, `""`, and `"   "` with a test.

**A gate left red over correct data trains the shop to ignore it.** That is why this is urgent rather than cosmetic: the cost of a vocabulary gap is not the failing run, it is everyone learning that red means nothing.

## Fail loud, never silently

Swapping a tuple membership test (compares by `==`) for a set membership test (hashes) turned *reject the unhashable value* into *raise on the unhashable value* — and the caller's blanket `except` then reported **every gate clean**. One malformed row took the entire enforcement surface down and reported success.

- A malformed input must block loudly. It is a finding, not an exception.
- A broad `except` around a gate must re-raise or produce a *failing* verdict. Never a clean one, never an empty list. Fail-open is a deliberate design choice with a stated reason (a hook that must not block a human's turn is a legitimate one) — and even then it fails open per-probe, so one crashing source of findings cannot hide the others.
- The unhappy paths in the gate deserve the same scrutiny as the rule it enforces (`failure-path-review`).

## Visibility economics

The near-miss worth internalizing: **fixing the vocabulary turned the gate green — and the surface that reported it printed only failures.** The real debts had been reaching the human purely because they were breaking the gate. Making the gate correct would have made real debt *less* visible than the bug had been.

- **Debt rides every run, not just failing runs.** The owed list sits outside the pass/fail branch. Parked in the `else`, one unrelated defect anywhere hid every owed item behind it — the debt disappearing exactly when things were worst.
- **A failing check's warnings still print.** Otherwise one blocking finding swallows every non-blocking one.
- **Before you fix a noisy gate, ask what its noise was carrying.** Sometimes the red was the only channel a real signal had. Give the signal its own channel first, then fix the gate.

## Meter it, and let it die

Every control can fail by over-firing, and the ones that do get switched off wholesale, taking their protection with them.

- **Declare the mirror failure when you build it.** The cure for one failure installs its mirror image: a team that recorded *"lots built, none shipped"* responded by shipping faster, and days later had a stack of shipments and still nothing measured. Both are one failure — a measurement that never completes — and the scoreboard counted only one direction of it. Every new control names the opposite failure it could induce, and the scoreboard counts both.
- **Write the anti-bureaucracy tripwire into the control itself.** A usable form: *if tickets opened greatly exceed tickets attempted over a fortnight, the check is over-tuned and the governing document is amended.* A rule that produces paperwork instead of work has failed on its own terms.
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
