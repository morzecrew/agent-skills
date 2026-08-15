<!-- markdownlint-disable-file MD041 -->
<!--
A PR template must not open with an H1 — the PR title is the heading — so
MD041 is disabled for this file rather than for the directory it lives in.

Title: <gitmoji> <type>[scope][!]: <description>   (gitmoji-conventional)
e.g.  ✨ feat(skills): add error-taxonomy
-->

## Summary

<!-- What changed and why, in 2–4 sentences. -->

Closes #

Skills touched: <!-- skills/<name> — new / edited / removed -->

## Type

- [ ] New skill
- [ ] Edit to an existing skill
- [ ] Removal or merge
- [ ] Scripts / evals / tooling
- [ ] Docs / repo chore

## Frontmatter & triggering

- [ ] `name` matches the directory name
- [ ] `description` names the *situations* that should trigger it, not the topic
- [ ] Checked it does not fire on adjacent-but-wrong tasks — false triggering is
      the expensive failure, not a missed trigger

## Content

- [ ] Does not contradict guidance in a sibling skill
- [ ] "Related skills" links resolve to skills that exist
- [ ] Works standalone — no silent dependency on a sibling being installed
- [ ] Earns its token cost; nothing here is behaviour an agent already defaults to

## Repo sync

- [ ] README "Available Skills" entry added or updated — one row, `| Skill |
      What it does |`; "Use when" and "Categories covered" live in the SKILL.md
- [ ] `just check` passed (lint + validate + tests) — everything CI runs
- [ ] `skills-lock.json` regenerated, if a vendored skill moved
- [ ] For a new skill, `npx skills add morzecrew/agent-skills@<name>` verified
- [ ] Any `scripts/` are executable, dependency-light, and do no network I/O
      on import

## Evals

- [ ] If behaviour changed, an eval under `evals/` was added or updated
- [ ] If so, ran `python3 evals/run.py` **locally** — never in CI, and no LLM
      API key enters this repository
- [ ] If not applicable (docs, config, tooling), say so below instead of ticking

Before / after:
