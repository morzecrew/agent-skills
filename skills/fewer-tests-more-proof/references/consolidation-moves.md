# The consolidation moves, and what each one is not

Six moves with worked shapes, plus the anti-patterns each one degrades into.
`SKILL.md` carries the inventory step and the honesty floor; pick a move here
once you know which promise is over-tested.

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

## Anti-patterns

- **Coverage percentage as the goal.** It rewards executing lines, not proving promises; ritual tests raise it.
- **Deleting slow tests instead of consolidating them.** Runtime is bought with determinism and shared batteries, never with lost proof.
- **Mega-parametrization** that fuses unrelated promises into one opaque test — consolidation merges *duplicates*, not *neighbors*.
- **Trusting green after deletion.** Subsumption is proven by sabotage, not by the suite staying green.
- **Uncatalogued divergence filters** in differential tests — every skipped comparison is either documented or a bug.
