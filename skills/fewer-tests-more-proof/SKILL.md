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

## The six moves

Pick by what the duplication actually is. Each one in full, with its worked shape
and the anti-pattern it degrades into, is in
[references/consolidation-moves.md](references/consolidation-moves.md).

| When | Move |
|---|---|
| Per-implementation files repeat the same scenarios | **Battery-ify** — one shared conformance suite every implementation runs |
| A trusted implementation exists | **Differential** — compare against it instead of re-enumerating expectations |
| Hand-listed examples of one invariant | **Properties** — state the invariant, generate the cases |
| A flaky test retried N times | **Determinism** — control the seam instead of buying confidence with volume |
| The same fixture rebuilt in a dozen places | **Promote by census** — count first, then hoist what the count justifies |
| A test that no longer distinguishes anything | **Delete — with proof.** Sabotage the code it claims to cover; if nothing else goes red, the deletion loses nothing. If something does, it was not subsumed |

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

## Reporting

- Tests and runtime before/after; promise inventory before/after (must be flat or up — say so explicitly).
- Where each deleted test's promise now lives, and which sabotage run proved it.
- Battery enrollment status per implementation, plus any waivers and why.
- What remains deliberately unconsolidated, and the stop-or-continue recommendation.

## Related skills

- `reading-isnt-proof` — battery mechanics: discriminating details, discriminating states, positive controls
- `self-audit` — verification honesty for the consolidation branch itself
- `less-code-same-behavior` — the same discipline applied to production code
