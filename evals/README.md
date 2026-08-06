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

This harness suits **output-checkable skills**: deterministic formats (gitmoji-conventional), classifications with right answers (error-taxonomy), structured artifacts (rfc-writer's INDEX shape, keep-a-changelog sections). Deep judgment skills (self-audit, less-code-same-behavior) don't reduce to regexes — evaluating those means reading transcripts against the skill's own rubric, which stays a periodic manual exercise (the skill-creator tooling is the right harness for that). Don't force assertions onto judgment; a check that can't fail for a nameable reason is ritual.

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
