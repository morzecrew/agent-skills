---
name: determinism-by-design
description: Use when code reads a clock, sleeps, generates random values or IDs, retries with jitter, or spawns concurrent tasks; when a test is flaky or timing-dependent; or when building replay or simulation. Not where the nondeterminism is the product, such as key generation.
roles: [implement]
gate: unseamed-calls
---

# Determinism by Design

Nondeterminism is a dependency. Code that calls the wall clock, the OS entropy pool, or the scheduler directly has hard-wired an uncontrollable input — and everything downstream inherits it: tests that need sleeps and retries, failures that vanish under observation, "run it 100 times" as a verification strategy. The fix is the same as for any dependency: **inject it**. Route every nondeterministic source through a seam the caller controls, wire the real source in production, and wire a controlled one everywhere reproducibility matters.

What this buys compounds: hermetic tests that cannot flake, failures that replay from a single seed, forced interleavings that turn race conditions into on-demand reproductions, and differential runs where two implementations see byte-identical inputs.

## The seams

Each source gets an injectable seam with the real implementation as the production default — determinism is a wiring choice, not a runtime cost:

| Source | Seam | Controlled implementation |
| --- | --- | --- |
| Wall/monotonic time | Clock/time-source interface; no direct `now()` in logic | Simulated clock: time advances only when told |
| Sleeps, timeouts, schedules | Built on the time seam, never on real sleeping | Virtual time: a 30 s timeout test runs in microseconds |
| Randomness | An injected seeded generator; never module-level/global RNG | `Random(seed)` — the whole run derives from one seed |
| IDs (UUIDs, nonces, request ids) | ID-provider seam | Seeded or sequential IDs — stable across replays |
| Iteration order | Sorted or insertion-ordered collections at boundaries | Never hash/set order where order reaches an observable |
| Concurrency schedule | Checkpoints/yield points a test can control | Forced interleaving: a conductor releases tasks one step at a time in a chosen order |
| Environment | Injected config: locale, timezone, env vars, cwd | Pinned values in tests |

Two design rules make the seams system-grade rather than decorative:

- **Derive, don't share:** one master seed, with per-component seeds *derived* from it (`derive_seed(master, component_name)`). Sharing one generator across components makes every component's draws depend on every other's draw *count* — an unrelated change reorders someone else's stream and "breaks" replay. Derivation isolates streams while keeping the single-seed replay property.
- **The failure artifact is the seed.** Every failure report from seeded machinery must print the seed (and schedule, if forced); replay = feed it back. A deterministic harness that doesn't surface its seed on failure has thrown away the property it exists for.

## The whole-system constraint

Determinism is only as strong as the *least* deterministic component: **every** randomness and time source must route through the seams, because one library carrying its own RNG stream — most scientific/statistics stacks do — reintroduces an uncontrolled input and quietly breaks whole-run replay. This is a dependency-adoption constraint, not just a coding rule (`dependency-diligence`'s principled-constraint test — one sentence rules out whole families), and it decays without enforcement: guard it with a check that fails when direct clock/RNG/entropy calls appear in seamed code (`ratchet-what-you-build`).

`scripts/unseamed_calls.py` is that check — it finds direct clock, sleep, randomness, UUID, and environment calls across Python, JS/TS, Go, Rust, and Java:

```bash
python3 scripts/unseamed_calls.py --seam src/pkg/time_source.py      # triage
python3 scripts/unseamed_calls.py --seam src/pkg/time_source.py --strict   # then gate CI
```

It ignores comments, docstring prose, tests, and lines marked `allow-unseamed`, and reports hits *inside* declared seams separately from leaks. It warns without failing until you pass `--strict`: a first run over an existing codebase surfaces seams the tool cannot know about, and a check that cries wolf gets deleted along with its protection. Tune `--seam`/`--allow` until the list is true, then turn on the gate.

## Hermetic tests

A hermetic test touches no real time, no real randomness, no network, no shared global state — every input is supplied, so a failure means the code changed, not the weather. Practical consequences:

- **No sleeps in tests, ever.** A sleep is a bet about scheduling; virtual time replaces the bet with a fact. Same for "retry the assertion for 5 s" polling loops.
- **A flake is a reproduction you haven't forced yet.** When a test is flaky, the move is not retry/quarantine — it's finding which unseamed source (real time, real scheduling, shared state, unordered iteration) lets runs differ, and seaming it. This is step 1 of `reproduce-then-fix` for concurrency bugs, and forced interleaving turns "fails one run in 500" into "fails every run under schedule (A, A, B, B)".
- Determinism also collapses test *volume*: one forced schedule per interesting interleaving replaces run-it-many-times probabilistic families (`fewer-tests-more-proof`).

## Where a seam is the vulnerability

Secure randomness is the exception the seams do not get. Cryptographic key
material, tokens, and nonces must read the OS entropy pool directly, on a
dedicated non-seeded path: an injection point there is a way to make the values
predictable, which is the whole attack. Everything else routes through a seam.

## The honesty boundary

Say precisely what is and isn't covered — over-claiming determinism spends the trust the machinery earned:

- **The seam is the horizon.** Behavior *below* an abstraction the simulation replaces (a real database's triggers and constraints, the real broker's rebalancing, the kernel's scheduler) is invisible to seam-level determinism. A simulated run proves the logic above the seam; conformance against the real thing (`reading-isnt-proof`) covers the fidelity of the stand-in itself.
- **Replay breaks are regressions.** Once byte-identical replay is a property, treat any change that breaks same-seed-same-run as breaking a public contract: it invalidates every recorded failing seed, which is your accumulated bug corpus.
- **Production stays on real sources** — the value in production is not replay but *structure*: seams make the nondeterminism visible, injectable, and loggable when a production failure needs reconstruction.

## Related skills

- `reproduce-then-fix` — seeds and forced schedules are how probabilistic failures become on-demand red reproductions
- `fewer-tests-more-proof` — determinism replaces flake-retry volume with exact tests
- `dependency-diligence` — the whole-system constraint applied at adoption time
- `ratchet-what-you-build` — the guard that keeps unseamed calls from creeping back
- `reading-isnt-proof` — conformance batteries cover what lies below the seam's horizon
