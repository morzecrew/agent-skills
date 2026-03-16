# Agent Skills

A collection of skills for AI coding agents. Skills are packaged instructions and scripts that extend agent capabilities.

Skills follow the [Agent Skills](https://agentskills.io/) format.

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

### gitmoji-conventional-commits

Formats git commit messages as `<gitmoji> <type>[scope]: <description>` using Conventional Commits with a deterministic gitmoji prefix. Applied automatically whenever the agent generates or suggests a commit message.

**Use when:**

- Agent generates or suggests a git commit message
- User says "commit this", "write a commit", "generate a commit message", or similar
- Preparing a release plan that includes a commit message

**Categories covered:**

- Commit message quality (High) - readable, parseable git history
- Semantic versioning (Medium-High) - enables changelog and release automation
- Team consistency (Medium) - uniform commit format across the repo

### gitmoji-conventional-pull-requests

Formats GitHub Pull Request titles as `<gitmoji> <type>[scope]: <description>` using the same Gitmoji + Conventional Commits scheme as commits. Applied automatically whenever the agent generates or suggests a PR title.

**Use when:**

- Agent generates or suggests a Pull Request title
- User says "create PR", "open PR", "prepare PR", "draft PR", or similar
- Preparing a PR summary where a title is needed

**Categories covered:**

- PR title consistency (High) - readable merge history and discoverability
- Semantic conventions (Medium-High) - alignment with commit format
- PR workflow (Medium) - clear, scannable PR lists

## Installation

```bash
npx skills add morzecrew/agent-skills
```

## Usage

Skills are automatically available once installed. The agent will use them when relevant tasks are detected.

## Skill Structure

Each skill contains:
- `SKILL.md` - Instructions for the agent
- `scripts/` - Helper scripts for automation (optional)
- `references/` - Supporting documentation (optional)