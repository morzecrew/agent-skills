# The three classes, and the evidence each one rests on

What each verdict claims, what authorises it, and the failure modes that follow
from claiming one without its evidence. `SKILL.md` carries the test that
separates them and the obligation each then owes.

## The classes

Every negative result carries exactly one of these. Two of them end a line of work, and **`DESIGN_DEAD` is what you write unless you can pay for something stronger** — `FAMILY_DEAD` has to be bought.

| Death class | Meaning | Licensed by | Owes |
|---|---|---|---|
| `FAMILY_DEAD` | The best this approach could ever do was measured, and it is not enough. | A **ceiling measurement**: run an idealised version — perfect information, unlimited budget — and show that even its optimistic bound misses the threshold, compared against a baseline taken in the same run. | Nothing further. The line is closed. |
| `DESIGN_DEAD` | The approach does something; this particular build of it does not clear the bar. | What you write by default. Applies when the effect was visible against a baseline from the same run but some constraint failed — cost, latency, quality, packaging, or fit with the measuring apparatus. | A **rebuild ticket**. |

The rest are not deaths, and filing one as a death is its own defect — the difference is entirely in what happens next:

| Verdict | Meaning | Owes |
|---|---|---|
| `INSTRUMENT_VOID` | No conclusion, because the apparatus was faulty: a control did not behave, a baseline was borrowed from elsewhere, or a variant was not what it was labelled. | A repaired apparatus and another run. |
| `UNDECIDABLE` | The apparatus was sound but too coarse to separate an effect of this size from noise. | A **power plan** costing the route to an answer (below). |
| `UNCLASSIFIED_HISTORICAL` | Retrospective entries only, where the evidence needed to sort them is gone. | Nothing, so old records cannot block current work. Never acceptable on a new verdict. |

Two rules do most of the work:

- **No ceiling measurement, no claim that the approach is finished.** Declaring the whole approach dead is the restful verdict — it closes the question and nobody revisits it — which is precisely why it should cost the most to justify. Two shapes that qualify: an idealised version granted many times the resources still moved far fewer outcomes than the threshold demanded, even at its optimistic bound, so no implementation could get there; and several genuinely distinct inputs produced identical choices nearly every time, so improving the input could not move something downstream that never consulted it.
- **A failed measurement is never recorded as a failed idea.** "We could not tell" and "it does not work" are different statements, and the first quietly turning into the second is how an approach gets dropped on no evidence at all.

## Failure modes

- **`FAMILY_DEAD` claimed rather than measured.** The most frequent defect and the costliest, because it shuts a line permanently on the strength of an argument. Absent a ceiling measurement, the label is `DESIGN_DEAD`.
- **An apparatus failure recorded as an idea failure.** A control that misbehaved, a baseline borrowed from elsewhere, or a run too coarse to decide, written down as evidence against the idea.
- **Reasoning in `measured_cause`.** A ticket whose cause was inferred rather than observed yields a rebuild founded on a guess, which is how one approach fails repeatedly while nobody learns anything.
- **The record nobody opens.** Labelling is filing unless the outstanding list appears where work begins. Put a check behind it (`drift-to-gate`) or it rots.
- **Administration overtaking work.** When items raised far outnumber items acted on across a two-week window, the process is too demanding and the rule behind it needs revising. A practice that generates filing rather than attempts has failed by the standard it set itself.
- **Labelling after the fact.** Assigning labels at review time, from recollection, produces whichever label suits the present. Assign it as the verdict is written, while the evidence is still there.
