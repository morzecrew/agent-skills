# Agent Skills

A collection of skills for AI coding agents. Skills are packaged instructions and scripts that extend agent capabilities.

Skills follow the [Agent Skills](https://agentskills.io/) format.

## Installation

```bash
# Install all skills
npx skills add morzecrew/agent-skills

# Install a specific skill
npx skills add morzecrew/agent-skills@keep-a-changelog
```

## Usage

Skills are automatically available once installed. The agent will use them when relevant tasks are detected.

Skills cross-reference each other in their "Related skills" sections. Every skill works standalone, but when installing or vendoring a subset, consider including the referenced siblings so those links resolve.

## Skill Structure

Each skill contains:

- `SKILL.md` - Instructions for the agent
- `scripts/` - Helper scripts for automation (optional)
- `references/` - Supporting documentation (optional)

## Available Skills

### keep-a-changelog

Keeps `CHANGELOG.md` in Keep a Changelog 1.1.0 format: user-focused entries in the six standard categories, an accurate `Unreleased` section, and clean version cuts. Covers breaking changes, reverts, and yanked releases, and separates the spec from repository-local formatting rules.

**Use when:**

- Adding landed user-facing changes to `## [Unreleased]`
- Categorizing changes into Added/Changed/Deprecated/Removed/Fixed/Security
- Cutting `Unreleased` notes into a `## [X.Y.Z] - YYYY-MM-DD` section
- Recording breaking changes, reverts, or yanked releases correctly

**Categories covered:**

- Changelog structure (High) - six spec categories, Unreleased, version sections
- Release hygiene (High) - version cuts, yanked releases, SemVer sanity checks
- Entry curation (High) - user-relevance filtering and outcome-oriented wording

### gitmoji-conventional

Formats commits and PR titles as `<gitmoji> <type>[scope][!]: <description>` — Conventional Commits 1.0.0 with a deterministic emoji prefix, so identical changes always get identical subjects. Includes end-to-end breaking-change handling, reverts, and a complete official gitmoji-to-type mapping.

**Use when:**

- Writing or suggesting any git commit message
- Writing a Pull Request title that must drop into GitHub unedited
- Marking a breaking change (💥 + `!` + `BREAKING CHANGE:` footer) or a revert
- Deciding the dominant type for a mixed-change commit or PR

**Categories covered:**

- Commit message format (High) - type, scope, imperative description, body, footers
- Gitmoji mapping (High) - deterministic emoji-to-type table for all 75 official gitmojis
- Release semantics (High) - SemVer signals, breaking changes, reverts

### python-rest-docstrings

Writes reST Python docstrings — Sphinx-native info field lists (`:param:`/`:returns:`/`:raises:`) and cross-reference roles that produce real links in rendered docs. Encodes PEP 257's imperative summary rule, Sphinx's actual field grammar (including the missing `:yields:` field), and role resolution behavior.

**Use when:**

- Writing or editing docstrings in a reST/Sphinx (`:param x:`) Python project
- Documenting new functions, classes, modules, or constants
- Fixing docstrings for Sphinx rendering and cross-linking
- Standardizing drifting docstring conventions

**Categories covered:**

- Field lists and formatting (High) - param/returns/raises grammar, aliases, summary rules
- Sphinx cross-referencing (High) - roles, tilde prefix, name resolution
- API contract documentation (High) - raises discipline, protocols, overloads, generators

### python-google-docstrings

Writes Google-style Python docstrings — typed `Args:`/`Returns:`/`Raises:`/`Attributes:` sections that Sphinx Napoleon compiles into rendered API docs and that scan fast in IDE tooltips. Encodes the actual Google Style Guide rules: summary mood, Raises discipline, property and `*args` conventions.

**Use when:**

- Writing or editing docstrings in a Google-style (`Args:`) Python project
- Documenting new functions, classes, modules, or constants
- Fixing docstrings for Sphinx Napoleon rendering
- Standardizing drifting docstring conventions

**Categories covered:**

- Docstring sections and formatting (High) - typed entries, section order, summary rules
- Sphinx Napoleon compatibility (High) - aliases, roles, rendering behavior
- API contract documentation (High) - Raises discipline, protocols, overloads, generators

### altitude-docs

A method for writing and polishing documentation so every page reads like one careful author wrote it. Each page is a controlled descent through altitude bands — from plain-language orientation down to edge-case detail — with a Diátaxis page contract, a shared consistency layer, and a ship rubric deciding when it ships.

**Use when:**

- Writing a new documentation page of any archetype
- Polishing or reviewing an existing page for consistency, depth, or flow
- Deciding whether content is a tutorial, how-to, reference, or explanation — and where it belongs
- Aligning a whole docs directory to one standard

**Categories covered:**

- Documentation structure (High) - altitude bands, Diátaxis compass, one page one job
- Docs review and consistency (High) - page contracts, voice, handoffs, ship rubric
- Information architecture (High) - archetype placement, splitting mixed pages, living exemplars

### never-nesting

Flattens deeply nested code with the full move-set — guard clauses, early return/continue, extraction, error-handling redesign, and dispatch tables — grounded in the cognitive-complexity math of why nesting compounds. Includes the judgment calls: symmetric branches that should stay if/else and cleanup idioms where early return is unsafe.

**Use when:**

- A function grows arrow-shaped if/else or a pyramid of doom
- The happy path is buried under wrapped error handling
- A complexity metric (cognitive/cyclomatic) flags a function
- Deciding whether a conditional should be a guard or stay if/else

**Categories covered:**

- Refactoring techniques (High) - guard clauses, extraction, error-handling flattening
- Code readability (High) - happy path at base indent, preconditions up front
- Complexity metrics (Medium) - cognitive complexity as the nesting rationale

### naming-things

Positive naming rules — length proportional to scope, problem-domain vocabulary, honest booleans, units in names or types — plus a ten-entry anti-pattern catalog with fixes, from abbreviations and Hungarian prefixes to Base/Abstract classes and Utils grab-bags. When no good name will come, treats the struggle as structural feedback.

**Use when:**

- Naming or renaming variables, functions, classes, or modules
- An identifier in a diff reads vague, abbreviated, or misleading
- A boolean, flag, or unit-bearing value needs a name
- A name won't come and the design might be the real problem

**Categories covered:**

- Naming rules (High) - scope-proportional length, domain vocabulary, honest names
- Anti-pattern catalog (High) - ten named smells with concrete fixes
- Design feedback (Medium) - unnameable code as a structure signal

### self-documenting-code

A precise comment policy, not comment-phobia: refactor away any comment at the same abstraction level as the code (names, predicates, constants, types), and keep the ones code cannot express — precision (units, ranges, invariants), interface contracts, and rationale. Includes a keep/delete decision table and comment-first as an abstraction probe.

**Use when:**

- Reviewing or writing comments in a diff
- Deciding whether a specific comment should exist
- Logic is dense enough that a comment feels necessary
- Hunting stale, redundant, or misleading comments

**Categories covered:**

- Comment policy (High) - same-level comments refactored away, different-level kept
- Refactoring for clarity (High) - named sub-expressions, predicates, constants, types
- Interface documentation (Medium) - caller-level contracts and precision comments

### composition-over-inheritance

The GoF principle done properly — composition plus interfaces as the default, with the fragile-base-class/self-use trap from Effective Java Item 18, the Liskov behavioral is-a test, and a clear map of where inheritance is genuinely the right tool.

**Use when:**

- Designing a new class relationship and tempted to subclass
- Refactoring a deep or rigid hierarchy, or a base class nobody dares touch
- Reviewing code where subclasses inherit inapplicable methods or override to disable
- Deciding whether an "is-a" relationship justifies `extends`

**Categories covered:**

- OOP design (High) - composition, forwarding, fragile base classes
- Type contracts (High) - LSP behavioral subtyping, interfaces/protocols/traits
- Refactoring (High) - untangling hierarchies into delegation

### measure-before-optimizing

Knuth's rule at full strength — skip the 97%, but hunt the critical 3% with a profiler, since Amdahl's law caps every speedup at the fraction of runtime you touch. Covers honest benchmarking (warmup, noise, percentiles), data-structure wins before micro-tweaks, and the architectural decisions (query shape, data layout) that legitimately precede measurement.

**Use when:**

- About to optimize code, or asked to "make this faster"
- Reviewing a change justified as "X is faster than Y"
- Writing or interpreting a benchmark
- Making design decisions with performance consequences (query shape, data layout, API granularity)

**Categories covered:**

- Performance discipline (High) - profiling, Amdahl's law, hotspot-driven optimization
- Benchmarking (High) - warmup, noise, dead code, percentiles
- Design decisions (High) - architectural performance that can't be retrofitted

### rfc-writer

Authors and maintains lightweight numbered RFCs — Markdown design proposals living in `rfcs/` next to the code, tracked by a single INDEX.md with a next-free-number and dense one-line summaries. Decisions land in an append-only table with their rationale and consequences, so pickup is cheap and rejected alternatives stay rejected.

**Use when:**

- Writing an RFC, design doc, technical spec, or architecture proposal
- Recording a design decision — and the alternatives it beat — before building
- Updating an RFC's status or execution notes after work ships
- Setting up or syncing an `rfcs/` directory and its INDEX.md

**Categories covered:**

- Design proposals (High) - numbered RFCs, header block, scaled section anatomy
- Decision records (High) - append-only decision tables with rationale and consequences
- Index maintenance (High) - INDEX.md as source of truth, statuses, drift repair

### reading-isnt-proof

When one contract has two or more implementations, a code read that concludes "they agree" is a hypothesis, not a result. This skill forbids closing a named test gap without running the shared conformance battery — one check per promise, parametrised over every implementation, asserting the discriminating detail from the state the production caller actually produces.

**Use when:**

- Auditing adapter or backend parity across a shared port or interface
- Verifying a mock or fake against the real implementation it stands in for
- About to report "no test covers X" without having run anything
- User mentions conformance, parity, differential testing, or "do they behave the same"

**Categories covered:**

- Test discipline (High) - shared conformance batteries across implementations
- Code review (High) - test-gap claims require executable proof
- Reliability (Medium) - divergent error contracts surface as user-visible status differences

### self-audit

A post-execution pass where the agent becomes the adversary of its own finished work, walking the nine places author blind spots concentrate — unspec'd extras, wrapper-state interactions, empty cases, failure and cleanup paths, its own fixes — because on a substantial branch, finding nothing is evidence of a shallow audit, not a clean branch. Verification claims are distrusted by default: suites run, fixes verified red, load-bearing checks sabotaged.

**Use when:**

- A branch (RFC execution, feature, fix series) is complete and about to merge
- User says "do self-audit", "audit your work", or "check your own changes"
- A multi-commit body of the agent's own work needs a defect hunt before handoff
- Double-checking non-code deliverables — docs, configs, infra

**Categories covered:**

- Defect discovery (High) - adversarial self-review across nine blind-spot passes
- Verification honesty (High) - verified-red fixes, sabotage spot-checks, patch coverage
- Honest reporting (Medium-High) - findings ranked, residue stated, rules distilled

### less-code-same-behavior

A divergence-and-DRY audit that finds where a codebase spends more code than its behavior requires — literal copies, same-concern drift, scatter, surface bloat, type lies — and consolidates in small behavior-preserving steps under the project's layer and import contracts. It can also conclude "leave it" or unwind a wrong abstraction entirely: NO ACTION is a first-class verdict, and merging coincidental similarity manufactures the coupling DRY exists to avoid.

**Use when:**

- Deduplicating, DRYing up, or converging divergent implementations of one concern
- Shrinking a codebase or subsystem with zero behavior change
- Auditing scattered modules, bloated facades, or accreted config surfaces
- Deciding whether an abstraction should exist at all

**Categories covered:**

- Code consolidation (High) - behavior-preserving steps, wrong-abstraction unwinding
- Architecture respect (High) - layer and import-contract constraints on placement
- Audit calibration (Medium-High) - evidence-counted verdicts including NO ACTION

### fewer-tests-more-proof

Treats a promise proven — not a test counted — as the unit of value, and consolidates the suite until each promise is tested exactly once, with its strongest assertion, everywhere it applies: shared batteries, differential and property-based oracles, metamorphic relations, forced-interleaving determinism. Deletions are proven by sabotage (mutation testing by hand), and an honesty floor keeps promise coverage monotone while count and runtime fall.

**Use when:**

- Consolidating, deduping, or cleaning up a test suite
- Per-implementation test files repeat the same scenarios per backend
- Suite runtime or flakiness is the complaint but coverage must not drop
- Setting up conformance or parity testing across implementations of one contract

**Categories covered:**

- Test suite economics (High) - promise-per-test consolidation, sabotage-proven deletion
- Reliability (High) - deterministic concurrency control over flake-retry volume
- Suite durability (Medium-High) - enrollment ratchets so absence fails loudly

### error-taxonomy

Designs and enforces an error contract: a small closed set of error kinds, each with a transport mapping, message exposure, and retryability decided once at design time. Classification at the raise site follows one test — could a correct server hit this purely from what the caller requested, and can the caller fix it? — and every consequence (status, visibility, retry) follows from the kind. Includes the sweep workflow for reclassifying an existing codebase.

**Use when:**

- Designing error handling for a new API, module, or service
- Deciding what to raise, what status an error maps to, or whether it's retryable
- Reviewing raise sites and catch blocks in a diff
- Sweeping "everything is a 500" codebases or message-matching callers

**Categories covered:**

- Error contracts (High) - kinds, codes, transport mapping, exposure, retryability
- API consistency (High) - same mistake, same kind, every backend
- Security hygiene (Medium-High) - hidden server faults, scrubbed exposures

### ratchet-what-you-build

Closes the gap between "built the mechanism" and "the mechanism is mandatory". Every guard, battery, or safe default gets ranked on an enforcement ladder — impossible-to-skip, on-by-default, CI gate, runtime fail-closed, convention — and everything sitting at convention is an open finding. Includes gate-design rules learned the hard way: prove the gate can fail in both directions, an empty derivation satisfies every subset check while proving nothing, and waivers must be re-verified against reality.

**Use when:**

- Finishing any protective mechanism: check, guard, battery, safe mode
- A shipped check turns out to be opt-in or absent from CI
- A safe mechanism exists but the unsafe default still ships
- A postmortem asks "we had a check for this — why didn't it fire?"

**Categories covered:**

- Enforcement design (High) - the ladder from convention to impossible-to-skip
- Drift prevention (High) - enrollment gates, non-empty derivations, verified waivers
- Audit closure (Medium-High) - the "what keeps it true?" sweep

### reproduce-then-fix

Bug-fixing as one loop: reproduce red, minimize, explain the mechanism, fix the cause, watch the same red turn green, keep the repro as a regression test. A fix never seen failing is a guess; a fix without an explained causal chain is a coincidence. Covers verified-red certification, the symptom test (does the change remove the mechanism or the observable?), no-unexplained-green, flakes as bugs with probabilistic repros, and honest "unreproduced" downgrades.

**Use when:**

- Fixing any bug, from a failing test to a production incident
- A fix is proposed without a failing reproduction
- A test is flaky and someone wants to retry, skip, or delete it
- The error is gone but nobody can say why

**Categories covered:**

- Debugging discipline (High) - reproduction, minimization, mechanism before patch
- Regression proofing (High) - verified-red tests kept from minimized repros
- Honest reporting (Medium-High) - mitigation vs fix, unreproduced vs fixed

### failure-path-review

A systematic sweep of the unhappy paths in async and background systems, where defects concentrate because failure code only runs during incidents: poison ceilings that actually advance, retry loops that misconfiguration must escape, crash-redelivery with side-effect/ack ordering decided, drain-not-abandon shutdown, supervised loops with crash-loop ceilings, bounds on everything that grows, and failure observability that distinguishes idle from stuck from discarding.

**Use when:**

- Writing or reviewing consumers, workers, background loops, or job runners
- Adding retry, backoff, or dead-letter behavior
- Implementing or reviewing shutdown, restart, or deploy handling
- After an incident with stuck, lost, duplicated, or infinitely-retried work

**Categories covered:**

- Async reliability (High) - poison, redelivery, reclaim, partial-batch honesty
- Lifecycle discipline (High) - drain over cancel, supervision, fault isolation
- Failure observability (Medium-High) - metrics on every drop, no payload leaks

### dependency-diligence

Evaluates a dependency before adoption, in strict order: the principled-constraint test first (one architectural invariant — seeded randomness, async-only I/O, layer purity — can rule out a whole library family in a sentence), capability-per-cost second (used fraction, what stdlib and carried deps already provide, the transitive tree), health and fit last. Every evaluation ends in one of four recorded verdicts: adopt behind a seam, take the idea not the dep, defer with a reopening trigger, or reject with the reason.

**Use when:**

- About to add a package, library, or tool to a project
- Asked "should we use X" or comparing libraries for a capability
- Reviewing a PR whose lockfile diff adds dependencies
- Auditing an existing dependency tree

**Categories covered:**

- Dependency evaluation (High) - constraint test, cost-per-capability, health, fit
- Supply-chain discipline (High) - seams, transitive awareness, license checks
- Decision records (Medium-High) - recorded verdicts that end re-litigation

### escape-hatch-policy

Decides when an abstraction earns a raw/bypass/override hatch and how to design one that stays safe. The two-question test: grant only where the un-modelable long tail is large AND the cross-cutting invariants bypassed (tenancy, concurrency control, encryption, audit) are few — otherwise extend the structured surface or point at the honest lower layer, where bypass is visible instead of disguised. Granted hatches are named, greppable, fail-closed when unset, scoped to fragments over whole operations, and counted — recurring usage is a feature request against the structured surface.

**Use when:**

- Someone asks for raw access, a passthrough field, or a bypass flag
- Tempted to add a "just pass anything" parameter to a typed API
- Reviewing an opt-out, unsafe mode, or "advanced" override in a diff
- An existing hatch's usage keeps growing and nobody decided that

**Categories covered:**

- API design (High) - the two-question test, scoped fragments, lower-layer honesty
- Safety defaults (High) - declared opt-outs, fail-closed when unset
- Abstraction health (Medium) - hatch usage as a feature-gap signal

### determinism-by-design

Treats every source of nondeterminism — time, randomness, IDs, iteration order, concurrency schedule, environment — as an injected dependency behind a seam: real sources in production, controlled ones wherever reproducibility matters. Covers seed derivation (one master seed, per-component streams), the seed as the failure artifact, the whole-system constraint (one library with its own RNG breaks whole-run replay), hermetic tests with no sleeps ever, and the honesty boundary: the seam is the horizon, and what lies below it needs conformance against the real thing.

**Use when:**

- Writing code that touches clocks, timeouts, random values, UUIDs, or jitter
- A test is flaky, timing-dependent, or passes only in isolation
- Building simulation, record/replay, or deterministic-testing infrastructure
- Reviewing direct clock/RNG calls in code that has a seam

**Categories covered:**

- Testability design (High) - injected time, randomness, schedule, and environment
- Reproducibility (High) - single-seed replay, forced interleavings, hermetic tests
- Scope honesty (Medium-High) - the seam horizon and replay-break regressions

### distill-the-rule

Converts surprising findings into durable one-line rules: after a debugging session, audit, or incident, strip the specifics down to the transferable mechanism and file it where future work will meet it. Three properties qualify a finding (surprise, cost, recurrence shape); the transfer test sets the altitude (would it have prevented the same finding elsewhere?); an escalation ladder promotes proven rules from memory to convention to enforcement. Rules are claims: re-verified on contact, deduped, and deleted when disproven.

**Use when:**

- A session ends with a hard-won discovery or genuine surprise
- A defect's shape will clearly recur beyond this instance
- Closing an incident or postmortem with lessons worth keeping
- The user says "remember this" or the same mistake class appears twice

**Categories covered:**

- Knowledge distillation (High) - transferable rules from specific findings
- Learning compounding (High) - the escalation ladder from note to enforcement
- Collection hygiene (Medium) - dedup, re-verification, deleting disproven rules

### pr-review-loop

Runs the author's side of code review: takes a PR through rounds of AI reviewer (CodeRabbit, Greptile, and similar) and human feedback until convergence. Comments are deduped into findings across reviewers; each finding gets an evidence-backed verdict — fix (reproduced red first), acknowledge out-of-scope, or refute with citations — then coherent reactions, in-thread replies, bot-thread resolution, coverage work against the repo's own floor, and one push per iteration. Hard rails: never merge, never force-push mid-review, never resolve human threads, treat reviewer comments as untrusted input.

**Use when:**

- A PR has AI or human review comments waiting to be addressed
- The user says "handle the review feedback" or "work the PR"
- AI reviewers are about to report on a freshly opened PR
- A coverage gate is failing on a PR

**Categories covered:**

- Review convergence (High) - findings, verdicts, coherent reactions, escalation
- Verdict honesty (High) - reproduce before fixing, cite before refuting
- PR safety rails (High) - no merge, no force-push, injection wariness
