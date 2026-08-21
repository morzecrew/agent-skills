# Skill Evals (local-only)

Behavioral checks that a skill actually produces the behavior it teaches. These run through the **locally authenticated `claude` CLI** — your Claude Code login is the credential — so no LLM API key ever exists in this repository or its CI. That is a design decision, not a limitation: GitHub Actions runs only the deterministic structural validator (`scripts/validate_skills.py`); everything in this directory is run by a human, on their machine, on demand.

## Running

```bash
python3 evals/run.py                        # all cases
python3 evals/run.py --skill error-taxonomy # one skill
python3 evals/run.py --case e1 --verbose    # one case, show model output
python3 evals/run.py --baseline             # also run each prompt without the skill
CLAUDE_EVAL_ARGS="--model claude-haiku-4-5" python3 evals/run.py   # cheaper/other model
```

Each case stages a throwaway temp project with the skill symlinked into `.claude/skills/`, runs the prompt via `claude -p`, and applies regex checks to the output. `--baseline` reruns the same prompt with no skill installed and reports whether the checks pass anyway — if they do, the case doesn't discriminate and needs a sharper assertion.

## Case modes — and what is honestly testable

- **`explicit`** — the prompt names the skill. Tests that the skill's *content* produces the required behavior. Pass/fail; a failure means the skill's instructions don't land.
- **`implicit`** — the prompt does not name the skill. Tests *triggering* via the frontmatter description. Informational only: triggering is probabilistic, and a single-run miss is signal to investigate, not a build failure.

A check may carry `"absent": true`, which passes when the pattern is **not** found. That is what makes a mis-trigger case possible: an `implicit` prompt the skill should stay out of, asserting its vocabulary does not appear. A suite whose every assertion is "this word showed up" cannot fail for a skill that fires when it should not — and a check that cannot fail proves nothing (`ratchet-what-you-build`).

This harness suits **output-checkable skills**: deterministic formats (gitmoji-conventional), classifications with right answers (error-taxonomy), structured artifacts (rfc-writer's INDEX shape, keep-a-changelog sections). Deep judgment skills (self-audit, less-code-same-behavior) don't reduce to regexes — evaluating those means reading transcripts against the skill's own rubric, which stays a periodic manual exercise (the skill-creator tooling is the right harness for that). Don't force assertions onto judgment; a check that can't fail for a nameable reason is ritual.

## Deciding whether a skill earns its place

Some skills teach material a frontier model largely already has. Suspicion is not
evidence, and neither is a passing suite — the question is whether the skill
*changed* anything. The procedure:

1. Write 5–10 `explicit` and `implicit` cases that should trigger, and 3–5 mis-trigger cases using `"absent": true`.
2. Run `python3 evals/run.py --skill <name> --baseline`.
3. Read the `BASE` lines. Every case whose baseline **also passes** is a case where the skill added nothing measurable.

A suite where the baseline passes throughout is a null result, and the honest
response is to delete the skill: it is paying description tax in every session to
produce behaviour that was already there.

Two things this harness does **not** measure, and §6 of the refactor asked for
both: iterations-to-green on a real task, and tokens consumed. Both need a task
harness rather than a single `claude -p` call. Treat a null result here as strong
evidence and a positive result as sufficient to keep; treat neither as a
measurement of what the skill costs to run.

`composition-over-inheritance` and `measure-before-optimizing` have suites
written for exactly this decision and have **not been run**. Run them before
acting on either.

## Adding cases

Add or extend `evals/cases/<skill>.json`:

```json
{
  "skill": "skill-name",
  "cases": [
    {
      "id": "e1",
      "mode": "explicit",
      "prompt": "Use the skill-name skill. <task with a checkable output>",
      "checks": [ { "pattern": "^expected", "flags": "i" } ]
    }
  ]
}
```

Rules of the house: every check must be able to fail for a reason you can name; prefer prompts whose answer is the output itself (no file operations — keeps runs permission-free); verify a new case discriminates by running it with `--baseline` once. Expect a case to cost one `claude -p` invocation (~seconds to ~a minute each).
