# Agent Skills

A collection of skills for AI coding agents — packaged instructions and scripts that extend agent capabilities, in the [Agent Skills](https://agentskills.io/) format.

## Installation

```bash
# Install all skills
npx skills add morzecrew/agent-skills

# Install a specific skill
npx skills add morzecrew/agent-skills@keep-a-changelog
```

Skills are available to the agent once installed, and it invokes them when a relevant task shows up. Each one is a `SKILL.md` plus optional `scripts/` and `references/`.

Skills cross-reference each other in their "Related skills" sections. Every skill works standalone, but when installing a subset, consider including the referenced siblings so those links resolve.

## Available Skills

### Writing code

| Skill | What it does |
| --- | --- |
| [never-nesting](skills/never-nesting/) | Flattens arrow-shaped code — guard clauses, early return, extraction, dispatch tables — and knows when if/else should stay. |
| [naming-things](skills/naming-things/) | Scope-proportional length, domain vocabulary, honest booleans, units — plus a ten-entry anti-pattern catalog with fixes. |
| [self-documenting-code](skills/self-documenting-code/) | Refactors away comments at the code's own abstraction level; keeps precision, contracts, and rationale. |
| [composition-over-inheritance](skills/composition-over-inheritance/) | Composition and interfaces by default, with the fragile-base-class trap and the Liskov behavioral is-a test. |
| [less-code-same-behavior](skills/less-code-same-behavior/) | Divergence-and-DRY audit in behavior-preserving steps, where NO ACTION is a first-class verdict. |
| [error-taxonomy](skills/error-taxonomy/) | A closed set of error kinds, each with its transport mapping, message exposure, and retryability decided once. |
| [escape-hatch-policy](skills/escape-hatch-policy/) | Decides when an abstraction earns a raw/bypass hatch, and designs one that is named, scoped, and fail-closed. |
| [determinism-by-design](skills/determinism-by-design/) | Time, randomness, IDs, iteration order, and schedule behind seams — single-seed replay and hermetic tests. |

### Testing and debugging

| Skill | What it does |
| --- | --- |
| [reproduce-then-fix](skills/reproduce-then-fix/) | Red repro, minimize, explain the mechanism, fix the cause, watch the same red turn green, keep it as a regression test. |
| [fewer-tests-more-proof](skills/fewer-tests-more-proof/) | Each promise tested exactly once with its strongest assertion; deletions proven by hand-run sabotage. |
| [reading-isnt-proof](skills/reading-isnt-proof/) | No closing a test gap by reading code — implementations of one contract need a shared conformance battery, run. |
| [failure-path-review](skills/failure-path-review/) | Sweeps the unhappy paths in async and background systems: poison, redelivery, drain-not-abandon, bounded growth. |
| [measure-before-optimizing](skills/measure-before-optimizing/) | Profile before optimizing, benchmark honestly (warmup, noise, percentiles), and know which design calls precede measurement. |

### Review and audit

| Skill | What it does |
| --- | --- |
| [self-audit](skills/self-audit/) | Adversarial pass over your own finished work, walking the ten places author blind spots concentrate. |
| [flag-dont-flip](skills/flag-dont-flip/) | Executes an RFC without silently changing it — plan gate first, halt on LOCKED decisions, every departure logged. |
| [pr-review-loop](skills/pr-review-loop/) | Works AI and human PR feedback to convergence — deduped findings, evidence-backed verdicts, one push per round. |
| [ratchet-what-you-build](skills/ratchet-what-you-build/) | Ranks every guard on an enforcement ladder; anything still sitting at "convention" is an open finding. |
| [drift-to-gate](skills/drift-to-gate/) | Turns a rule that keeps being broken into a program that refuses — then runs that control's whole lifecycle. |
| [negative-result-taxonomy](skills/negative-result-taxonomy/) | Classifies every failed attempt as family-dead, design-dead, or undecidable, so a kill is a diagnosis and not a dead end. |
| [authority-dissociation](skills/authority-dissociation/) | Separates who does the work from who certifies it, so no actor writes the evidence that judges its own output. |
| [decide-before-you-look](skills/decide-before-you-look/) | Pre-registers the call before the data exists — six lines, an interval that must be narrower than the decision band, and no moving goalposts. |
| [distill-the-rule](skills/distill-the-rule/) | Turns hard-won findings into one-line transferable rules, filed where future work will meet them. |

### Documentation

| Skill | What it does |
| --- | --- |
| [altitude-docs](skills/altitude-docs/) | Writes and polishes docs as a controlled descent through altitude bands, with a Diátaxis page contract and a ship rubric. |
| [rfc-writer](skills/rfc-writer/) | Lightweight numbered RFCs in `rfcs/`, tracked by one INDEX.md, with append-only decision records. |
| [keep-a-changelog](skills/keep-a-changelog/) | Keeps `CHANGELOG.md` in Keep a Changelog 1.1.0 format — user-focused entries, accurate Unreleased, clean version cuts. |
| [python-google-docstrings](skills/python-google-docstrings/) | Google-style `Args:`/`Returns:`/`Raises:` docstrings that Napoleon renders and IDE tooltips scan. |
| [python-rest-docstrings](skills/python-rest-docstrings/) | reST docstrings — Sphinx-native `:param:`/`:returns:`/`:raises:` fields and cross-reference roles that really link. |

### Project hygiene

| Skill | What it does |
| --- | --- |
| [gitmoji-conventional](skills/gitmoji-conventional/) | Commits and PR titles as `<gitmoji> <type>[scope][!]: <description>`, with all 75 official gitmojis mapped deterministically. |
| [dependency-diligence](skills/dependency-diligence/) | Evaluates a dependency before adoption — constraint test, capability-per-cost, health — ending in one recorded verdict. |

## Contributing

See [AGENTS.md](AGENTS.md) for repository layout, how to add a skill, and how to run validation and tests.
