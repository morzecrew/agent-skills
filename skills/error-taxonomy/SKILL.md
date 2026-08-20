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

## Codes and messages

- **Codes are stable identifiers; messages are free text.** Give recurring error *situations* a canonical code (`query_feature_unsupported`, `field_not_on_read_model`) and reuse it everywhere the situation occurs — including across every implementation of a shared contract, so the same mistake yields the same code on every backend. Don't mint near-synonym codes; a census of existing codes comes before a new one.
- **Never let callers or tests match on messages.** Tests assert the kind and code (the `reading-isnt-proof` battery table has the same rule); messages may improve freely.
- **Scrub before exposing.** Reclassifying a hidden kind to an exposed one makes its message client-visible: strip leaked internals first (SQL fragments, type/wiring tokens, file paths, dependency keys). Echoing back *caller-supplied* values is safe and helpful.

## Sweeping an existing codebase

1. **Census the raise sites** of the over-broad kind (usually `internal`/generic 500). Grep by construction site *and by message family* — a package-grouped census misses small shared helpers; message text finds them. `scripts/error_census.py` does both:

   ```bash
   python3 scripts/error_census.py --kind 'exc\.(\w+)' --exclude 'tests/*'
   ```

   It counts sites by kind, package, and code, then clusters messages into families (normalizing away interpolations, quoted values, and numbers) and marks any family raised as **more than one kind** — the same mistake answering differently depending on which call site the caller happened to hit.
2. **Classify each against the test.** Expect a minority to move: a real sweep of 637 internal sites moved ~99 and deliberately kept ~540 — defensive internals are correct and stay.
3. **Move families in lockstep across implementations** of the same contract, so parity holds (mock ≡ every backend raising the same kind for the same mistake).
4. **Run the full suite.** Kind-agnostic tests survive; tests pinning the old kind are the contract change surfacing — decide each deliberately.
5. Record moved codes in the changelog if the API is public: an error-kind change is a behavior change.

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
