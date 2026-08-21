# The seams, and the tests they buy

Each nondeterministic source, the shape of the seam that controls it, and what
a hermetic test looks like once they are all in place. `SKILL.md` carries the
rule and its two boundaries.

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

## Hermetic tests

A hermetic test touches no real time, no real randomness, no network, no shared global state — every input is supplied, so a failure means the code changed, not the weather. Practical consequences:

- **No sleeps in tests, ever.** A sleep is a bet about scheduling; virtual time replaces the bet with a fact. Same for "retry the assertion for 5 s" polling loops.
- **A flake is a reproduction you haven't forced yet.** When a test is flaky, the move is not retry/quarantine — it's finding which unseamed source (real time, real scheduling, shared state, unordered iteration) lets runs differ, and seaming it. This is step 1 of `reproduce-then-fix` for concurrency bugs, and forced interleaving turns "fails one run in 500" into "fails every run under schedule (A, A, B, B)".
- Determinism also collapses test *volume*: one forced schedule per interesting interleaving replaces run-it-many-times probabilistic families (`fewer-tests-more-proof`).
