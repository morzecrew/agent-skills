---
name: dependency-diligence
description: Use when about to add a package, library, or tool; when asked "should we use X" or "X vs Y"; or when reviewing a PR whose lockfile grows. Not for upgrading an already-adopted dependency, and not for choosing the platform itself.
roles: [implement, author]
gate: none
gate_reason: scripts/dep_health.py fetches evidence; the adopt-or-reject verdict is a judgement it cannot make
---

# Dependency Diligence

A dependency is a capability bought with a permanent liability: its bugs become your bugs, its release cadence becomes your upgrade treadmill, its transitive tree becomes your supply chain, and its API shape leaks into your design. Agents (and people) reach for a library reflexively — the evaluation discipline is what stands between "there's a package for that" and a dependency tree nobody chose on purpose.

The evaluation has a strict order, because the cheapest checks are the most decisive: constraints first, cost-per-capability second, health third. Most candidates die on the first two, before a single benchmark or changelog is read.

## Three steps, and the order is the point

In full in [references/the-three-steps.md](references/the-three-steps.md).

1. **The principled-constraint test.** Check the project's architectural invariants first: one violated constraint rules out a whole family at once, which is far cheaper than comparing three libraries and then discovering none of them can be used.
2. **Capability per cost.** Weigh what it does against everything it costs — transitive tree, build time, upgrade cadence, the API surface it puts in front of your callers. A dependency that saves fifty lines and adds forty packages has not saved anything.
3. **Health and fit.** `scripts/dep_health.py` fetches the evidence — release cadence, maintainer count, open-issue shape, license. It fetches; it does not decide.

## The four verdicts

Every evaluation ends in exactly one, and all four get recorded:

1. **Adopt behind a seam.** Wrap it in your own interface at the boundary — the dependency becomes an implementation detail: replaceable, mockable, conformance-testable against future alternatives (`reading-isnt-proof`), and its types stay out of your contracts. Direct, unwrapped use throughout a codebase is reserved for platform-tier dependencies chosen deliberately.
2. **Take the idea, not the dep.** Often the library's value is one algorithm, one formula, one trick — and it's thirty lines. Port it (license permitting, with attribution), test it, own it. "Heavy-tailed latency via stdlib `random`, no new dep" is the pattern: the insight shipped, the wheel didn't.
3. **Defer with a recorded verdict.** Not now, and *here is the sentence that says why* — so the question isn't re-litigated every quarter. Include the trigger that would reopen it ("adopt when we need X at scale Y").
4. **Reject with the reason.** Same recording rule. A rejection without a recorded reason is a rejection that gets re-proposed.

**Record the verdict where decisions live** — a decision log, memory, or for consequential adoptions an RFC (`rfc-writer`); per-library one-line verdicts beside the constraint sentence are enough for the rest. The recording is the compounding asset: the second evaluation of any family should take minutes.

## Anti-patterns

- **Feature-table shopping first** — comparing candidates on features before checking whether any of them can exist inside your constraints.
- **Adopting for the demo path** — the library nails the happy-path example; its failure modes, concurrency behavior, and upgrade story were never examined (`failure-path-review` applies to dependencies too).
- **Transitive blindness** — evaluating the package while ignoring the fifty packages it brings.
- **"Temporary" direct usage** — unwrapped calls spread through the codebase faster than the seam gets built; the seam comes first.
- **Re-litigating settled verdicts** — if the constraint sentence still holds, the answer hasn't changed; if it no longer holds, *that* is the news worth a fresh evaluation.

## Related skills

- `reading-isnt-proof` — a seam with two implementations (the dep and its future replacement or mock) gets a conformance battery
- `less-code-same-behavior` — carried-dependency duplication and the take-the-idea port both land here
- `rfc-writer` — consequential adoptions deserve a recorded design decision
- `error-taxonomy` — the fit check for how a candidate's errors map into yours
