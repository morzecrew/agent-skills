# Classification walkthrough

Worked classifications, hardest cases first. Each row applies the test from SKILL.md — *would a correct server hit this purely from what the caller requested, and can the caller fix it by changing the request?* — and shows where naive classification goes wrong.

## Contested calls

| Raise site | Kind | Why — and the tempting wrong answer |
| --- | --- | --- |
| Filter/sort/projection names a field that isn't on the read model | `precondition` | The *value* is well-formed; the *operation* is unsupported for this model. Tempting: `validation` — but nothing about the string is malformed; the caller must change *what they ask for*, not how they spell it |
| Cursor token fails to decode | `validation` | The value itself is malformed. The mirror of the row above: malformed value → validation; well-formed-but-unsupported → precondition |
| Cursor decodes, but doesn't match the current sort spec | `validation` | Still a bad *value* for this request — the token is not usable as given |
| Backend can't paginate this sort ("cursor by primary key only") | `precondition` | Capability limit. The message must say what to use instead ("use offset pagination or sort by pk") — actionability is what makes precondition exposure worth it |
| Reusing an idempotency key with a *different* payload | `conflict` | The caller collided with existing state. Tempting: `precondition` (400) — but this is state-dependent: the same request would have succeeded against empty state. State-dependent refusals are 409-family |
| Concurrent writer changed the document version | `conflict` | Classic optimistic-concurrency loss. Retryable *by the caller's decision* (re-read, re-apply), never silently by infrastructure |
| Request for a resource the caller may not see | `not_found`, deliberately | Answering `authz` (403) confirms the resource exists. Where existence itself is sensitive, the taxonomy call is a security decision: 404 both cases. Decide it per resource class, once — not per endpoint |
| Dependency timeout while calling the database | `infrastructure` | Retryable server fault. Tempting: `internal` — but nothing is wrong with the server's logic; the outage is the cause and retry is legitimate |
| Caller-supplied deadline was exceeded (their budget, honored) | `precondition` | The request as specified cannot complete within the budget the caller set — they can raise it. Contrast with the row above: whose constraint failed decides the kind |
| AEAD decryption fails on stored data (auth tag mismatch) | `internal` | Stored state is corrupt or tampered — a server-side fact the caller can't fix and must not learn details of. Fail closed, alarm loudly |
| Required wiring/config key missing at startup | `configuration` | Operator-fixable, not caller-fixable, not a code bug. Kept distinct from `internal` because the *remedy* differs: redeploy with the key vs file a bug |
| `default:` arm over an enum the framework already validated | `internal` — and **keep it** | Defensive guards over already-validated sets are correct internals. A sweep that reclassifies these to caller kinds is over-rotating: in the reference sweep, ~540 of 637 internal sites stayed internal |
| Rate limit exceeded | `throttled` | Its own kind because its *retryability* differs from every 4xx: retry is correct, after backoff — collapsing it into `precondition` breaks retry policies |

## Scrubbing when a kind becomes exposed

Reclassifying `internal` → `validation`/`precondition` flips the message from hidden to client-visible. Before the flip, remove from the message: SQL/query fragments, internal type representations (`{t!r}`, class names), dependency keys and wiring names, file paths, anything secret-adjacent. Keep and echo: the caller's own values ("limit must be positive, got -5") — they already know them, and echoing is what makes the message actionable.

## Sweep sizing expectations

From the reference sweep of a large codebase: 637 generic-internal raise sites, ~99 reclassified across ~28 files, ~540 correctly left internal. Two process lessons transfer: census by *message family* as well as by package (shared helper files hide from package-grouped censuses), and fix each family in lockstep across every implementation of the contract so mock ≡ real parity holds.
