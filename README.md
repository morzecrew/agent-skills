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

Maintains `CHANGELOG.md` in Keep a Changelog format. Updates `## [Unreleased]` with user-relevant changes and, when asked, prepares versioned sections. The agent keeps the changelog current; release decisions and tagging stay with the human.

**Use when:**

- User asks to update or maintain `CHANGELOG.md`
- User provides changes to add under `## [Unreleased]`
- Repo changes imply the changelog should be updated
- User wants help categorizing changes (Added, Changed, Fixed, etc.)
- User wants to turn Unreleased notes into a versioned section

**Categories covered:**

- Release documentation (High) - user-facing change history
- Changelog maintenance (Medium-High) - structured version notes
- Version tracking (Medium) - release history and reference links

### gitmoji-conventional

Formats git commit messages and Pull Request titles as `<gitmoji> <type>[scope]: <description>` using Conventional Commits with a deterministic gitmoji prefix. Applied automatically whenever the agent generates or suggests a commit message or PR title.

**Use when:**

- Agent generates or suggests a git commit message
- Agent generates or suggests a Pull Request title
- User says "commit this", "write a commit", "create PR", "open PR", "prepare PR", or similar
- Preparing a release plan that includes a commit message
- Preparing a PR summary where a title is needed

**Categories covered:**

- Commit message quality (High) - readable, parseable git history
- PR title consistency (High) - readable merge history and discoverability
- Semantic versioning (Medium-High) - enables changelog and release automation
- Team consistency (Medium) - uniform format across commits and PRs

### python-rest-docstrings

Writes consistent Python docstrings using reST roles for cross-references. Optimizes for IDE tooltips, Sphinx compatibility, and high-signal documentation that explains behavior rather than restating types. Covers type aliases, classes, methods, attributes, TypedDict keys, `@overload`, and `typing.Protocol`.

**Use when:**

- User asks to write or update docstrings
- Writing or editing Python code that should be documented
- User mentions docstrings, reST, Sphinx, or API documentation
- Documenting classes, methods, or public APIs

**Categories covered:**

- Code documentation (High) - consistent, scannable docstrings
- API discoverability (Medium-High) - IDE tooltips and Sphinx output
- Cross-references (Medium) - reST roles for types and callables

### python-google-docstrings

Writes consistent Python docstrings in Google style with typed sections (`Args:`, `Returns:`, `Raises:`, `Yields:`, `Attributes:`). Optimizes for IDE tooltips, Napoleon/Sphinx compatibility, and high-signal documentation that explains behavior rather than restating types. Covers type aliases, classes, methods, attributes, TypedDict keys, `@overload`, and `typing.Protocol`.

**Use when:**

- User asks to write or update docstrings
- Writing or editing Python code that should be documented
- User mentions docstrings, Google style, Napoleon, or API documentation
- Documenting classes, methods, or public APIs

**Categories covered:**

- Code documentation (High) - consistent, scannable docstrings
- API discoverability (Medium-High) - IDE tooltips and Sphinx output
- Typed sections (Medium) - `name (type): description` entries for params and attributes

### altitude-docs

Writes, polishes, and reviews documentation pages to a consistent standard using the altitude model (a deliberate high-level to low-level descent), Diátaxis-based page contracts, a shared consistency layer, and a ship rubric. Repo-agnostic: it discovers the project's docs root, archetype layout, source of truth, and build tooling before applying.

**Use when:**

- Writing a new documentation page
- Polishing or reviewing a page for consistency, depth, or flow
- Aligning an archetype directory (e.g. all tutorials) to one standard
- Deciding which archetype and directory new content belongs in

**Categories covered:**

- Documentation quality (High) - balanced, single-author feel across pages
- Information architecture (Medium-High) - Diátaxis fit and altitude bands
- Editorial consistency (Medium) - voice, handoffs, and component discipline

### never-nesting

Keeps code flat and readable by limiting indentation depth, inverting conditions into guard clauses with early returns, and extracting nested blocks into well-named, single-responsibility functions. Treats three levels of indentation as a soft ceiling.

**Use when:**

- Writing or refactoring code with deep nesting or pyramid-shaped if/else
- The happy path is buried under wrapping error/edge-case conditions
- User mentions nesting, indentation, guard clauses, early returns, or extracting functions
- Reviewing code for readability or complexity problems

**Categories covered:**

- Code readability (High) - flat, scannable control flow
- Maintainability (Medium-High) - small single-responsibility functions
- Code review (Medium) - detecting and flagging excessive nesting
