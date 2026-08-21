---
name: error-taxonomy
description: Use when designing error handling for an API or module, deciding what to raise or what status an error maps to, reviewing raise sites and catch blocks, or sweeping a codebase where everything is a 500. Not for user-facing error copy.
roles: [implement]
gate: none
gate_reason: scripts/error_census.py finds and counts raise sites; which kind each one belongs to is the judgement
---

# Error Taxonomy

Errors are contract surface. The **kind** of an error — not its message — is what callers branch on, what transports map to status codes, what retry loops consult, and what tests assert. A codebase without a decided taxonomy makes these calls ad hoc at every raise site, and the result is the same client mistake returning 500 from one endpoint and 400 from another, retry loops spinning on misconfiguration, and callers string-matching messages because nothing else is stable.

The fix is a small closed set of kinds, each carrying three attributes **decided once, at design time**: transport mapping, message exposure, and retryability. Classification happens at the raise site; every consequence (status, visibility, retry) follows mechanically from the kind.

## The taxonomy

Adapt names to your stack; keep the set **small and closed** — every new "special" kind weakens the guarantee that consumers can handle the whole set. A canonical starting set:

| Kind | Meaning | Transport | Message exposed? | Retryable? |
| --- | --- | --- | --- | --- |
| `validation` | Malformed or out-of-range **value** (bad cursor token, negative limit, mutually exclusive args) | 400/422 | Yes | No |
| `precondition` | Well-formed request for an **unsupported operation or refused state** — capability limits, "backend X can't do Y; use Z" | 400/412 | Yes | No |
| `not_found` | Referenced thing doesn't exist (for this caller) | 404 | Yes | No |
| `conflict` | Concurrent modification, duplicate, version mismatch | 409 | Yes | Caller decides (re-read, retry the transaction) |
| `authn` / `authz` | Not authenticated / not permitted | 401 / 403 | Carefully (don't confirm resource existence) | No |
| `throttled` | Rate/quota limit | 429 | Yes | Yes, after backoff |
| `configuration` | Deployment misconfiguration (missing key, bad wiring) | 500 | **No** — loud for operators, opaque to clients | **No** — retrying misconfig spins forever |
| `infrastructure` | A dependency failed (DB down, timeout) | 502/503 | No | Yes |
| `internal` | An invariant broke — **this is a bug** | 500 | **No** | No |

The transport column is HTTP; on other surfaces the same kinds map to their equivalents (gRPC status codes, CLI exit codes, a library's public exception types) — the point is that the mapping lives on the kind, not at each call site.

Two rules make the table load-bearing:

- **Retryability is derived from kind by one shared policy** — retry loops, dead-letter decisions, and workflow engines all consult the same classifier. A retry loop that catches everything converts a `configuration` error into an infinite warn loop; the taxonomy is what lets it abort instead.
- **Exposure is a security boundary.** Server-fault kinds hide their message from clients (it names internals); caller-fault kinds expose theirs, and the message must be *actionable* — say what was wrong and what to do instead.

## The classification test

For any raise site, ask: **would a correct server still hit this purely because of what the caller requested — and can the caller fix it by changing the request?**

- Yes → a caller kind. Malformed value → `validation`; well-formed but unsupported or state-refused → `precondition`; the rest of the caller row as fits.
- No → a server kind. Misconfigured deployment → `configuration`; dependency failure → `infrastructure`; "should never happen" → `internal`.

`internal` is reserved for genuine invariant guards: defensive `default:` arms over already-validated sets, unreachable branches, consistency checks on data the system itself built. If an `internal` fires, the correct response is a bug fix, never a client-side workaround — which is exactly why its message stays hidden and its rate deserves an alarm.

For worked classifications of the contested cases (field-not-on-model vs malformed value, conflict vs precondition, not-found vs authz, whose-constraint-failed), read [references/classification-walkthrough.md](references/classification-walkthrough.md).

## Codes, messages, and existing code

Once a kind is decided, what the error carries is decided with it: a stable
machine-readable code, a message whose exposure was chosen rather than inherited,
and a retryability the caller can trust. **Callers must never string-match a
message** — that makes prose a public API, and the next copy-edit is a breaking
change.

Applying this to a codebase that predates it is a survey before it is a refactor:
`scripts/error_census.py` counts the raise sites and their kinds, and the
classification is yours. Both in
[references/rollout.md](references/rollout.md); a worked classification is in
[references/classification-walkthrough.md](references/classification-walkthrough.md).

## Anti-patterns

- **One generic exception for everything** — forces every consumer decision (status, retry, display) to be made from the message.
- **Ad-hoc status mapping per endpoint** — the mapping belongs to the kind, once.
- **Catch-and-rethrow as internal** — launders a caller mistake into a hidden 500; classify at the boundary where the cause is known.
- **Retry-by-default** — retrying non-retryable kinds (validation, configuration) burns quota and hides the real failure; classify, then retry only what the policy allows.
- **Boolean/null returns for failures that carry a reason** — the reason vanishes exactly where the caller needs it.

## Related skills

- `reading-isnt-proof` — conformance batteries assert error kinds, never messages; a shared taxonomy is what makes that assertable
- `failure-path-review` — retry/poison/drain decisions all consume this taxonomy's retryability attribute
- `self-audit` — pass 5 (failure paths) catches raise sites that dodge the taxonomy
