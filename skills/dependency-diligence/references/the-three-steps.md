# The three steps, in full

Constraint test, capability per cost, health and fit — each with what to look
for and how to read the answer. `SKILL.md` carries the ordering rule and the
four verdicts.

## Step 1 — The principled-constraint test

Before comparing features, ask: **does the project have an architectural invariant this dependency structurally cannot respect?** One sentence can rule out an entire family:

- "Every randomness source must route through our seeded entropy seam for byte-identical replay" — rules out any library carrying its own RNG stream, which is most of the scientific stack, regardless of how good each library is.
- "All I/O is async on one loop" — rules out blocking clients with no async surface (a thread-pool wrapper is a new liability, not a fix).
- "This layer imports nothing above the contract layer" — rules out anything whose types would leak into contract signatures.
- "Everything in the hot path is deterministic/replayable/sandboxable" — rules out libraries with hidden global state, background threads, or native code, depending on the invariant.

This test is why diligence is cheap: it's a property of *your architecture*, checked against a property of *their design*, and neither requires trying the library. When a whole family dies here, record the constraint sentence itself as the verdict — it answers every future member of the family too.

## Step 2 — Capability per cost

- **What fraction would you actually use?** A 100 MB columnar-analytics wheel to write line-delimited JSON, a matrix library to compute three distributions — the used-fraction test kills more candidates than quality ever does.
- **What do you already have?** Check the standard library and existing dependencies before the ecosystem: the three statistical distributions you need may already be in `stdlib random`; the retry helper may already exist in a dep you carry. An adopted dependency that duplicates a carried one is a divergence bug waiting to happen (`less-code-same-behavior`).
- **What does it cost beyond bytes?** Install weight, cold-start time, native build requirements, platform constraints, license compatibility, the transitive tree it drags in (each transitive is a dependency you adopted without diligence), and the conceptual surface every maintainer must now learn.

## Step 3 — Health and fit

Only for candidates that survived steps 1–2. `scripts/dep_health.py` gathers the factual half:

```bash
python3 scripts/dep_health.py requests --ecosystem pypi
python3 scripts/dep_health.py express --ecosystem npm --repo expressjs/express --json
```

It reports release cadence and recency, license, direct-dependency fan-out, and (with `gh`) commit recency, contributor count, and archived status — flagging stale releases, deprecation, missing licenses, and a bus factor of one. It deliberately produces evidence, never a verdict, and running it on a candidate that failed step 1 is wasted effort.

- **Health:** maintenance activity and responsiveness (not stars), bus factor, security posture and CVE history, release discipline (semver honored? changelogs?), API stability across recent majors.
- **Fit:** does its error model map onto yours (`error-taxonomy`)? Its sync/async model, its logging/telemetry behavior, its global state? A library that fights the project's idioms costs integration code forever.
- **Verify claims by execution, not README** — the capability you're buying gets a spike test against your actual use case before adoption, not after.
