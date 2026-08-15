<!--
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

- [ ] README "Available Skills" entry added or updated (summary, Use when,
      Categories covered)
- [ ] `skills-lock.json` regenerated
- [ ] markdownlint clean
- [ ] Any `scripts/` are executable, dependency-light, and do no network I/O
      on import

## Evals

- [ ] Eval added or updated under `evals/`
- [ ] Ran it

Before / after:
