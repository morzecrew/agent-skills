# Kill-ledger schema

The file `scripts/kill_ledger.py` validates. One JSON document, one array of entries,
one entry per negative result. Append-mostly: a class may be **escalated**
(`DESIGN_DEAD` → `FAMILY_DEAD` once ceiling evidence exists) but never silently
downgraded, and every change carries its evidence path.

```json
{
  "schema_version": 1,
  "entries": [
    {
      "candidate": "root-scout-v1",
      "family": "root-scout",
      "kill_class": "DESIGN_DEAD",
      "verdict_artifact": "eval/root-scout-v1/REPORT.json",
      "ceiling_evidence": null,
      "base": {
        "artifact": "champion/2026-07-17.tar.gz",
        "sha256": "d3f7ee67…",
        "evidence": "banked read 724.1 over 51 games"
      },
      "ticket": {
        "status": "OPEN",
        "failing_prong": "ladder read never resolved: 9 games in 6h vs a 50-game bar",
        "measured_cause": "the behaviour band throttled it to 0.4 games/h — measured, not inferred",
        "candidate_fix": "re-run without the band, which the owner lifted 2026-08-06; precedent: prize-racer's gated rebuild",
        "cheapest_test": "one ladder slot + a ~50-game read, ~6h wall clock, 0 compute cost",
        "prediction": "reaches a readable 50 games; direction unknown",
        "opened_utc": "2026-08-06",
        "closed_utc": null,
        "owner_ruling": null,
        "note": "trained to 47.00% of a 47.11% oracle ceiling and never read"
      },
      "power_plan": null
    }
  ]
}
```

## Entry fields

| field | required | meaning |
|---|---|---|
| `candidate` | yes | what died. Any stable identifier. |
| `kill_class` | yes | one of the five below. |
| `family` | no | the idea this build belongs to. Defaults to `candidate` with a trailing `-v<N>` / `-p<N>` stripped, so `root-scout-v1` and `root-scout-v2` share a family automatically. Set it explicitly when the naming does not carry it. |
| `verdict_artifact` | no | path to the evidence the verdict was read from. |
| `ceiling_evidence` | **iff `FAMILY_DEAD`** | the measured ceiling, with its numbers and its bar. Prose, not a boolean. |
| `base` | no | `{artifact, sha256, evidence}` — what this was built on, and the evidence it was stronger. |
| `ticket` | **iff `DESIGN_DEAD`** | the redesign ticket. |
| `power_plan` | **iff `UNDECIDABLE`** | the priced way out. |

Any field expected to carry prose is read as **absent** unless it is a non-empty
string. `null`, `false`, `0`, `[]`, `{}` and `"   "` are all absent — deliberately,
because `str(None)` is `"None"`, which is truthy, and that one detail once turned
"no value yet" into a recorded decision.

## `kill_class`

| value | death? | requires |
|---|---|---|
| `FAMILY_DEAD` | yes | `ceiling_evidence` |
| `DESIGN_DEAD` | yes | `ticket` |
| `INSTRUMENT_VOID` | no | nothing. The instrument was broken — fix it and re-run. |
| `UNDECIDABLE` | no | `power_plan`. The instrument was sound but underpowered — price the way out. |
| `UNCLASSIFIED_HISTORICAL` | no | nothing. Backfill only, for entries whose evidence no longer exists. Never for a fresh verdict; history must not hold the present hostage, and this word is the only reason it does not. |

`INSTRUMENT_VOID` and `UNDECIDABLE` are the two that are **not deaths**. The
difference is what to do next: fix the instrument, or buy resolution.

## `ticket`

| field | required | meaning |
|---|---|---|
| `status` | yes | `OPEN` · `FUNDED` · `ATTEMPTED` · `RETIRED_BY_OWNER`. Must be a **string**; anything else is a blocking defect, never an exception. |
| `failing_prong` | yes on `DESIGN_DEAD` | the bar that failed, with the measured number and the bar. |
| `measured_cause` | yes on `DESIGN_DEAD` | the mechanism of failure, measured. |
| `candidate_fix` | yes on `DESIGN_DEAD` | the change, and its precedent if it has one. |
| `cheapest_test` | yes on `DESIGN_DEAD` | the test that settles it, with its cost. |
| `prediction` | no | the call, made before the test runs. |
| `owner_ruling` | **iff `FUNDED` or `RETIRED_BY_OWNER`** | a **path to a file outside this ledger**, recording the decision. The file must exist. |
| `opened_utc` | no | `YYYY-MM-DD`; feeds the opened-vs-attempted meter. |
| `closed_utc` | no | `YYYY-MM-DD`; feeds the meter. |
| `note` | no | append-only. New status first, `PRIOR DIAGNOSIS:` and the original text after. |

**Buckets.** `OWED` = {`OPEN`, `FUNDED`} — listed on every run. `CLOSED` =
{`ATTEMPTED`, `RETIRED_BY_OWNER`} — silent. Widening the vocabulary means adding
to a bucket, never to the accept set; the two must partition the valid statuses,
and a test should assert that they do.

**Why `owner_ruling` names a file.** A non-empty field inside the same JSON the
agent is writing is bookkeeping in the costume of authentication — the same
keystroke writes both. A separate artifact can be read and repudiated by the
person it names. It is still forgeable, so it is a speed bump, not a lock.

## `power_plan`

All six fields required, all non-empty:

| field | meaning |
|---|---|
| `achieved_mde` | the effect size this run could actually resolve |
| `required_mde` | the effect size the question needs |
| `units_needed` | how much more, in the units actually spent |
| `cost_estimate` | what that costs |
| `cheaper_alternative` | the smaller question that could be answered instead |
| `recommendation` | run it, shrink it, or park it |

A plan that recommends PARK is the stall written down, not the cure for it — the
point is that parking becomes a choice against a number.

## Verdicts

| verdict | exit | meaning |
|---|---|---|
| `OK` | 0 | no defects. Owed tickets and meter warnings may still be reported. |
| `LOOP_DEBT` | 1 | at least one defect. |
| `REFUSE` | 2 | the ledger is missing or unreadable. A gate that cannot read its input rules on nothing. |
