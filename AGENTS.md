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
- **SKILL.md:** YAML frontmatter carries `name`, `description`, `roles`, and `gate`. The description is triggers only — when to use, when not to — and is capped at 300 characters, because every description is in context in every session whether its skill fires or not. `roles` is any of `implement`, `review`, `revert`, `author`. `gate` names the enforcing check, or is `none` with a `gate_reason`. Do not restate the triggers as a body section; the validator rejects it.
- **Naming:** Skill folders use kebab-case (e.g. `keep-a-changelog`).

## Testing Instructions

- **Everything CI runs:** `just check` (lint + validate + test). Individual recipes: `just lint`, `just validate`, `just test`, `just test-one <module>`, `just commits`, `just install-hooks`.
- **Structural validation (deterministic, no LLM):** `python3 scripts/validate_skills.py` — frontmatter shape, name/folder sync, description limits, required sections, Related-skills and references/ integrity, bundled scripts compile and are documented, README sync. Runs in pre-commit and GitHub Actions (`.github/workflows/validate.yml`); no secrets involved.
- **Skill-script unit tests:** `cd tests && python3 -m unittest discover` — stdlib `unittest`, no dependencies, no network. Covers the bundled scripts' logic and carries a regression test for every bug found while building them.
- **Borrowed-prose check (local only, never CI):** `python3 scripts/borrowed_prose.py --corpus <private notes> skills/<name>/SKILL.md` — reports any run of 7+ words a skill shares with the private material it was distilled from. Skills are written from internal notes and write-ups; the rules travel, the sentences do not. Stripping figures and domain nouns is not enough, because distinctive phrasing carries just as much of someone else's document and survives a search for numbers untouched. Local-only by design: the corpus is private and must never enter this repository. Two kinds of hit are judged rather than removed: identifiers a skill exists to teach (a taxonomy's own labels, a schema's field names) and universal language idioms (`read_text(encoding="utf-8")`, a stock regex character class). Reformatting either one to dodge the check is gaming it — decide, then say which you did.
- **Behavioral evals (local only, never CI):** `python3 evals/run.py` — runs eval prompts through the locally authenticated `claude` CLI and checks output assertions. Local-only by design so no LLM API keys ever enter the repository or CI. See `evals/README.md`.
- Manually verify:
  - Skill instructions are clear and self-contained
  - `npx skills add morzecrew/agent-skills@<skill-name>` works for new skills

## Commit and Pull Request Guidelines

- **Title format:** `<gitmoji> <type>[scope]: <description>` (see gitmoji-conventional skill)
- **Commit format:** `<gitmoji> <type>[scope]: <description>` (see gitmoji-conventional skill)
- Run `markdownlint` if configured before submitting.

## Adding a New Skill

1. Create `skills/<skill-name>/SKILL.md`.
2. Include YAML frontmatter with `name`, `description` (≤300 chars, triggers only), `roles`, and `gate` (or `gate: none` plus `gate_reason`).
3. Write the body as rules, not argument — one clause of rationale per rule, and a body budget of ~1,500 tokens. Everything longer goes to `references/`, loaded on demand.
4. Add the skill to README.md under "Available Skills" — one table row, `| [<name>](skills/<name>/) | one-line summary |`, in the theme group it belongs to.
5. Run `python3 scripts/validate_skills.py` — it enforces 1-4.
6. If the skill bundles `scripts/`, mention each script in `SKILL.md` (the validator requires it) and add tests under `tests/`.

Before adding a skill at all, ask whether a **gate** would do instead. A gate refuses; a skill hopes. See `drift-to-gate`.
