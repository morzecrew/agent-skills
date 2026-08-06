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
