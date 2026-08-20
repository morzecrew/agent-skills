---
name: fewer-tests-more-proof
description: Use when asked to consolidate, dedupe, optimize, or clean up a test suite, to shrink its size or runtime without losing coverage, or to set up conformance testing across implementations of one contract. Not for writing missing tests, and not for deleting flaky ones.
roles: [implement]
gate: none
gate_reason: the honesty floor is the project's own coverage gate; this skill has no separate artifact to refuse
---

# Fewer Tests, More Proof

The unit of value in a test suite is a **promise proven**, not a test counted. A suite optimized under that metric gets smaller and stronger at once: each promise tested exactly once, with its strongest assertion, in every implementation and state where it applies — and nothing else. "Fewer tests" is the side effect, never the goal; the moment a consolidation would trade proof for count, it stops.

## Inventory: map tests to promises

Before moving anything, build the map. For each test, name the promise it proves — the sentence that would have to become false for it to fail ("reusing a key with a different payload is refused as a conflict", "shutdown drains pending work"). A test whose promise you cannot name is the first finding. The map exposes the six consolidation targets:

1. **The same promise tested per-implementation** in N parallel files — the battery target.
2. **The same setup rebuilt** across many files — the shared-harness target.
3. **A promise tested weakly in one place and strongly in another** — the subsumption target.
4. **A family of hand-picked examples all pinning one general promise** at different points — the property target.
5. **Tests that cannot fail for a nameable reason** — assertion-free runs, "did not raise", tautological mocks. Ritual, not proof.
6. **Probabilistic concurrency tests** — sleeps, retries, run-it-100-times loops — the determinism target.

## The consolidation moves

### Battery-ify multi-implementation contracts

When one contract (port, interface, spec) has two or more implementations, the scenarios belong in **one shared module, parametrized over every implementation** — per-backend copies are how divergence hides, because no one puts the behaviors side by side. Per-implementation files shrink to what is genuinely implementation-specific; a new implementation enrolls by wiring a small harness and inherits the entire battery instead of a hand-copied suite. That inversion is the economics: the battery's cost is paid once, and every implementation after the first gets its coverage nearly free.

For battery *mechanics* — asserting the discriminating detail, exercising the state the production caller produces, positive controls — apply the `reading-isnt-proof` skill if available; this skill owns the suite economics, that one owns the battery craft.

### Differential against a reference implementation

Where a reference implementation exists (a mock or fake mirroring a real backend, a model beside an optimized engine), assert `implementation ≡ reference` on the same inputs instead of enumerating expected outputs twice. One oracle then covers every backend, and the expectation is maintained in one place.

Legitimate mechanism differences (the reference refuses where the real engine's optimization permits, yet both protect the invariant) go in an explicit, versioned **divergence catalog** — each entry explaining why the difference is verdict-equivalent or naming the known fidelity limit. Never silently filter a divergence: an uncatalogued filter is a hole shaped exactly like a bug.

### Properties over examples

A property over generated inputs subsumes the example family it generalizes: one QuickCheck/Hypothesis property — `decode(encode(x)) == x`, "the output is sorted and a permutation of the input" — replaces the dozen hand-picked examples that each pinned one point of the same promise, and the generator reaches the points nobody hand-picked. Keep one or two pinned examples as regression anchors — they double as the property's positive control — and let shrinking do the failure naming: a minimal counterexample beats any example test's message.

When no expected output is computable at all — the *oracle problem* — assert **metamorphic relations** between runs instead: permuting the input must not change the result set, adding a matching document must never shrink it, running twice must equal running once. Differential testing (above) solves the oracle problem with a reference implementation; metamorphic relations solve it when nothing exists to be the reference.

### Determinism over repetition

A concurrency test that races real time needs volume to mean anything, and still lies. Forcing the interleaving — checkpoint/schedule control, simulated time, seeded randomness — turns a probabilistic family of N flaky tests into one exact, reproducible test per schedule of interest. Determinism is the single largest runtime-and-flake win available in most suites.

### Promote shared setup by census

Count usages before extracting. Setup rebuilt in a handful of files becomes a local fixture; setup rebuilt across dozens becomes a shared testing module — and if application authors need the same harness, a shipped one. Keep old import paths alive via re-export shims so promotion repoints nothing.

### Delete subsumed and ritual tests — with proof

A weaker test is subsumed only when a surviving test provably carries its promise: **sabotage the behavior and watch the survivor fail** — the same break that would have failed the deleted test. Green-after-deletion alone proves nothing (the suite is also green when the survivor is blind). Ritual tests that cannot fail for a nameable reason are strengthened into real assertions or deleted outright; a green tick that carries no information costs runtime and, worse, confidence.

Sabotage is mutation testing by hand, and tools like PIT and Stryker automate the sweep, reporting killed/detected and surviving mutants — and the mutation score they report is the metric coverage percentage pretends to be: ritual tests raise coverage and kill nothing. One caveat carries over from hand sabotage: a survivor is not automatically a missing test — it may be an *equivalent mutant*, changing no behavior at all, and deciding that is undecidable in general. So every survivor gets a named why, never a shrug.

## The honesty floor

- **Promise coverage is monotone.** Keep the before/after promise inventory; every deleted test's promise must appear against a surviving test. Test count and runtime go down; the inventory does not.
- **Measure patch and branch coverage with the full test profile** — a single profile (unit-only) can undercount by half and misdirect the consolidation. Watch **detection branches** especially: code that only runs when a bug is present is exactly the code consolidation must not orphan.
- **Failures must still name their cause.** Label every parametrized assertion with the implementation and case under test, so a battery failure says *which* implementation disagreed on *what*. A consolidation that produces unreadable failures went one step too far.

**Deleting a flaky test is not consolidation.** It removes proof and leaves the
promise untested, and the suite gets greener for exactly that reason. Fix the
flake with deterministic control, or say plainly which promise the deletion
stops proving and let someone else decide.

## Ratchet it

A consolidated suite decays silently: the next implementation ships without enrolling in the battery, and the suite is green because absence doesn't fail. Make enrollment enforced, not remembered — a check that derives the set of implementations from the codebase (registrations, package manifests, wiring) and asserts every one is a declared battery leg, with explicit waivers for genuine exceptions. Two hard-won rules: the check must fail when the *derivation* is empty (an empty derived set satisfies every subset check while proving nothing), and a waiver must be re-verified against reality so stale claims fail. If CI can't tell that a new implementation skipped the battery, the consolidation has a half-life.

## Anti-patterns

- **Coverage percentage as the goal.** It rewards executing lines, not proving promises; ritual tests raise it.
- **Deleting slow tests instead of consolidating them.** Runtime is bought with determinism and shared batteries, never with lost proof.
- **Mega-parametrization** that fuses unrelated promises into one opaque test — consolidation merges *duplicates*, not *neighbors*.
- **Trusting green after deletion.** Subsumption is proven by sabotage, not by the suite staying green.
- **Uncatalogued divergence filters** in differential tests — every skipped comparison is either documented or a bug.

## Reporting

- Tests and runtime before/after; promise inventory before/after (must be flat or up — say so explicitly).
- Where each deleted test's promise now lives, and which sabotage run proved it.
- Battery enrollment status per implementation, plus any waivers and why.
- What remains deliberately unconsolidated, and the stop-or-continue recommendation.

## Related skills

- `reading-isnt-proof` — battery mechanics: discriminating details, discriminating states, positive controls
- `self-audit` — verification honesty for the consolidation branch itself
- `less-code-same-behavior` — the same discipline applied to production code
