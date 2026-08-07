---
name: dependency-diligence
description: Evaluate a dependency before adopting it — check the project's architectural invariants first (one violated constraint rules out a whole family), weigh capability against total cost, and choose among adopt-behind-a-seam, take-the-idea-not-the-dep, or reject-with-a-recorded-verdict. Use when about to add a package or library, when asked "should we use X", when reviewing a PR that adds a dependency, when comparing libraries for a capability, or when the user mentions dependencies, third-party libraries, vendoring, supply chain, or "is there a library for this".
---

# Dependency Diligence

A dependency is a capability bought with a permanent liability: its bugs become your bugs, its release cadence becomes your upgrade treadmill, its transitive tree becomes your supply chain, and its API shape leaks into your design. Agents (and people) reach for a library reflexively — the evaluation discipline is what stands between "there's a package for that" and a dependency tree nobody chose on purpose.

The evaluation has a strict order, because the cheapest checks are the most decisive: constraints first, cost-per-capability second, health third. Most candidates die on the first two, before a single benchmark or changelog is read.

## Use this skill when

- About to add a package/library/tool to a project
- Asked "should we use X?" or "X vs Y?" for a capability
- Reviewing a PR whose lockfile diff adds dependencies
- A recurring "maybe library Z would help here" question deserves a settled answer
- Periodically auditing an existing dependency tree

## Do not use this skill when

- The dependency is the platform (the language runtime, the framework the project is built on) — that's an architecture decision for an RFC, not a diligence pass
- Pinning/upgrading versions of an already-adopted dependency — that's maintenance; diligence happens at adoption

## Step 1 — The principled-constraint test

Before comparing features, ask: **does the project have an architectural invariant this dependency structurally cannot respect?** One sentence can rule out an entire family:

- "Every randomness source must route through our seeded entropy seam for byte-identical replay" — rules out any library carrying its own RNG stream, which is most of the scientific stack, regardless of how good each library is.
- "All I/O is async on one loop" — rules out blocking clients with no async surface (a thread-pool wrapper is a new liability, not a fix).
- "This layer imports nothing above the contract layer" — rules out anything whose types would leak into contract signatures.
- "Everything in the hot path is deterministic/replayable/sandboxable" — rules out libraries with hidden global state, background threads, or native code, depending on the invariant.

This test is why diligence is cheap: it's a property of *your architecture*, checked against a property of *their design*, and neither requires trying the library. When a whole family dies here, record the constraint sentence itself as the verdict — it answers every future member of the family too.

## Step 2 — Capability per cost

- **What fraction would you actually use?** A 100 MB columnar-analytics wheel to write line-delimited JSON, a matrix library to compute three distributions — the used-fraction test kills more candidates than quality ever does.
- **What do you already have?** Check the standard library and existing dependencies before the ecosystem: the three statistical distributions you need may already be in `stdlib random`; the retry helper may already exist in a dep you carry. An adopted dependency that duplicates a carried one is a divergence bug waiting to happen (`less-code-same-behavior`).
- **What does it cost beyond bytes?** Install weight, cold-start time, native build requirements, platform constraints, license compatibility, the transitive tree it drags in (each transitive is a dependency you adopted without diligence), and the conceptual surface every maintainer must now learn.

## Step 3 — Health and fit

Only for candidates that survived steps 1–2. `scripts/dep_health.py` gathers the factual half:

```bash
python3 scripts/dep_health.py requests --ecosystem pypi
python3 scripts/dep_health.py express --ecosystem npm --repo expressjs/express --json
```

It reports release cadence and recency, license, direct-dependency fan-out, and (with `gh`) commit recency, contributor count, and archived status — flagging stale releases, deprecation, missing licenses, and a bus factor of one. It deliberately produces evidence, never a verdict, and running it on a candidate that failed step 1 is wasted effort.

- **Health:** maintenance activity and responsiveness (not stars), bus factor, security posture and CVE history, release discipline (semver honored? changelogs?), API stability across recent majors.
- **Fit:** does its error model map onto yours (`error-taxonomy`)? Its sync/async model, its logging/telemetry behavior, its global state? A library that fights the project's idioms costs integration code forever.
- **Verify claims by execution, not README** — the capability you're buying gets a spike test against your actual use case before adoption, not after.

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
