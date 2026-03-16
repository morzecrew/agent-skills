# AGENTS.md

## Project Overview

Agent Skills is a collection of skills for AI coding agents. Skills are packaged instructions (SKILL.md files) that extend agent capabilities. The format follows [Agent Skills](https://agentskills.io/).

**Structure:**

- `skills/<skill-name>/SKILL.md` — main instructions for each skill
- `skills/<skill-name>/scripts/` — optional helper scripts
- `skills/<skill-name>/references/` — optional supporting docs

## Setup Commands

- No build step. This is a Markdown-based skill collection.
- Install skills elsewhere: `npx skills add morzecrew/agent-skills` (all) or `npx skills add morzecrew/agent-skills@<skill-name>` (single skill)

## Development Workflow

- Edit `SKILL.md` files directly.
- Add new skills under `skills/<skill-name>/` with at least `SKILL.md`.
- Optional: add `scripts/` and `references/` per skill.

## Code Style

- **Markdown:** Follow `.markdownlint.yml` (default rules disabled; extend as needed).
- **SKILL.md:** Use YAML frontmatter (`name`, `description`), clear headings, and explicit "Use when" / "Categories covered" sections where applicable.
- **Naming:** Skill folders use kebab-case (e.g. `keep-a-changelog`).

## Testing Instructions

- No automated tests. Manually verify:
  - Markdown renders correctly
  - Skill instructions are clear and self-contained
  - `npx skills add morzecrew/agent-skills@<skill-name>` works for new skills

## Pull Request Guidelines

- **Title format:** `<gitmoji> <type>[scope]: <description>` (see gitmoji-conventional-pull-requests skill)
- **Commit format:** `<gitmoji> <type>[scope]: <description>` (see gitmoji-conventional-commits skill)
- Run `markdownlint` if configured before submitting.

## Adding a New Skill

1. Create `skills/<skill-name>/SKILL.md`.
2. Include YAML frontmatter with `name` and `description`.
3. Document when the skill applies ("Use when") and what it covers ("Categories covered").
4. Add the skill to README.md under "Available Skills".
5. Update this AGENTS.md "Current skills" list if desired.
