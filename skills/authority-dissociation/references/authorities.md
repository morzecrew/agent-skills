# The five authorities, and the failures each one absorbs

The split in full, plus the four pathologies that appear when two of these
collapse into one actor. `SKILL.md` carries the question and the defaults.

## The five authorities

These decide different things. Merging any two is a defect with its own characteristic failure:

| Authority | Decides | Must not also hold |
|---|---|---|
| **Fit** | which constants or configuration this build uses | kill |
| **Kill** | whether this build is finished as a line of work | fit |
| **Promote** | whether this build replaces what is running | kill, fit |
| **Fund** | that work is paid for and may begin | promote — and no automated actor holds it at all |
| **Retire** | that a line is closed and owes nothing further | fund — and no automated actor holds it at all |

- **A measure used for tuning cannot also decide death.** When constants were chosen by maximising a proxy — similarity to a stronger reference model, an offline accuracy score, a rater panel's preference — that proxy is a diagnostic. Rejection belongs to measures nearer the causal claim that motivated the work. The two really are separable: a hand-set variant once cleared every causal check while scoring badly on the tuning measure, which is only possible if they were measuring different things.
- **Local evaluation decides what may be attempted, never what succeeded.** Offline checks control entry to the real measurement. Only the real measurement — production, the live comparison, the ranked board — says anything improved. A team whose own harness may declare wins will accumulate declared wins and no improvement.
- **Enter the cheap version in the same contest.** Put a simple, hand-set variant through the identical checks as a rival rather than as a baseline. If both clear, take the simple one unless the tuned one has visibly earned its complexity. This is the control that makes the split real instead of merely stated.
- **Funding and closure stay with the principal.** An actor that may mark its own debt paid discharges it by intending to (`negative-result-taxonomy`). An actor that may close its own open question closes it by closing the file.

## A measure you designed will favour you along the axes you designed it on

Self-grading hides best inside instruments. Several unrelated incidents shared one shape: **the definition of the measure already contained the conclusion.** An auditor built to surface a specific mistake suppressed exactly that mistake, because how it counted made the mistake invisible. A tuned model reported agreement with its own starting point and thereby certified itself at zero improvement.

The question that finds it: **would this measure look just as interesting if nothing at all were happening?** Then run whatever answers it — shuffle the labels, cross-check against an independent source, feed it a change known to do nothing and require it to report nothing. An instrument that has not both caught a deliberate fake and rejected a meaningless input has not earned the right to have its readings believed.

## One bad measurement drops a build, not an idea

A disappointing measurement retires **this candidate**, recorded as *cause unidentified*. It does not retire the approach.

Ruling out a whole approach needs either a second measurement that agrees, or an identified mechanism — a specific failure the approach demonstrably produces.

The asymmetry is deliberate and correct for the *action*: dropping a marginal build costs almost nothing, so one poor result is reason enough to stop shipping it, while adopting one needs more. But **the asymmetry must not extend to explanation.** A check firing is data about this build. It goes into the record; the approach remains eligible until something actually accounts for the result.

## Voice without veto

Not every reviewer should be able to block, and an advisory role that can be ignored in silence is not advisory — it is decorative. The workable middle: **the challenger marks findings as blocking, and the deciding party must respond to each one in the verdict.** Overridable with stated reasons; never droppable without comment.

That gives an adversarial reviewer real weight without a veto it should not have. It is also exactly what was missing in the opening incident, where a correct objection was recorded, filed as minor, and answered by nobody.

## The repair, and what it is actually worth

An attestation means something only when it **points at an artifact held outside the record the actor is writing**, and the named principal can read that artifact and disown it.

Concretely: the status says approved, and the approval exists at a path — a file, a signed message, a ticket — that can be checked for existence, authorship, and content, separately. Not a flag inside the same object the actor is editing.

**Then describe it accurately.** A separate file the agent can also write is friction, not prevention; it remains forgeable. What it buys is that the claim now sits somewhere the principal will plausibly look, and can be contradicted when false — neither of which is possible while the claim exists only as a field nobody opens. Describing a control as stronger than it is spends credibility that has not been earned, and is how a correct objection ends up filed as minor.

## Failure modes

- **The costume.** A check reading a field the checked party writes, documented as verification. Rename it or rebuild it.
- **Self-graded completion.** "Done", asserted by whoever did the work, with nothing a third party could disagree with.
- **The merged authority.** One number that selects, judges, promotes, and closes. It will be optimised against, and all four roles decay together.
- **Silent advisory.** A reviewer whose findings nobody must answer. Count the answers; an unanswered backlog that only grows is the role expiring.
- **Ruling out an approach on one result.** "We tried that, it didn't work" — from a single measurement, with no explanation, removing an option permanently.
- **Failing open on the unknown.** An unrecognised permission value treated as the most permissive. The unknown case is where both attackers and bugs live.
