# The review passes

Each pass, what it looks for, and the incident shape behind it. `SKILL.md`
carries the scope and the verification rule; the checklist form is in
[review-checklist.md](review-checklist.md).

## The review passes

For a running review, [references/review-checklist.md](references/review-checklist.md) carries these passes as check-off questions; the sections below carry the reasoning.

### 1. Poison: work that can never succeed

A message that fails deserialization, or deterministically crashes its handler, will be redelivered forever unless something counts and caps it.

- **Ceiling:** a max-deliveries bound exists, and hitting it *parks* the work (DLQ/parking table) with a metric — never silent drop, never infinite retry. Check that the delivery count actually advances on your transport; on brokers that don't count redeliveries natively, the requeue path must increment its own counter or the ceiling is decorative.
- **Blast radius:** one undecodable message must not abort the whole batch, and on ordered/FIFO transports, must not head-of-line-block its group forever — poison isolation is per-message, and the ordered case needs an explicit unblock decision.
- **Parked ≠ deleted:** the dead-letter destination is for diagnosis and redrive; a retention policy that silently expires it recreates the loss the DLQ existed to prevent. Bound it with alarms, not silent truncation.

### 2. Retry classification: what must escape the loop

The retry loop's catch clause is the single most consequential `except` in the system. Route it through the error taxonomy's retryability policy (`error-taxonomy`), and check the two escape directions:

- **Non-retryable errors abort loudly.** Misconfiguration inside a retry loop is the classic: a bad credential or missing route spins warn-forever, looking alive while processing nothing. Resolution/configuration phases belong *outside* the catch-all, or wrapped in a marker that re-raises through it.
- **The inner ladder must not swallow what the outer loop handles.** A per-message catch-all that eats a shutdown/draining signal makes the loop's own stop branch unreachable — trace each control-flow exception from raise site to the branch that's supposed to see it.
- Backoff has jitter and a cap; a retry budget or ceiling exists per work item, not just per process.

### 3. Crash and redelivery: at-least-once is the contract

Assume the process dies between any two statements, then re-runs the work.

- **Side effect vs acknowledgment ordering:** decide which happens first and what the crash between them produces — a duplicate (needs idempotency/inbox dedup downstream) or a loss (almost never acceptable). Duplicates are the correct default; make consumers idempotent.
- **Recovery reclaims abandoned work:** in-flight items owned by a dead process must return to the pool (stale-claim reclaim, visibility timeout, lease expiry) — verify the reclaim path runs and is itself bounded by the poison ceiling.
- **Partial batch failure:** when N items process and item k fails mid-batch, check what happens to 1..k−1 (acked exactly once?) and k+1..N (redelivered?). Acknowledge only what provably succeeded — "ack all regardless" quietly drops the failures.

### 4. Shutdown: drain, don't abandon

- **Cancel vs drain:** killing worker tasks abandons in-flight work mid-effect; shutdown should stop *intake*, finish or hand back in-flight items, then stop — under a bounded drain timeout with a decided timeout behavior.
- **The shutdown path uses the same disciplined machinery as the live path:** a stop-time requeue that skips the delivery counting, dedup headers, or property carryover of the normal path silently strips the guarantees exactly once per deploy. Grep the teardown for simplified twins of live-path logic.
- Stop signals reach the loops (registration with the lifecycle), and draining refusals are counted, not retried.

### 5. Supervision: loops that die stay dead

- Every long-lived loop runs under a supervisor: crash → log with the error → restart with jittered backoff → give up (loudly) at a crash-loop ceiling. An unsupervised background task fails once, silently, forever.
- **Fault isolation per unit:** one tenant's/shard's/partition's failure must not tear down the group — check what shares a task group, and what one poison unit takes with it.

### 6. Bounds: everything grows until it doesn't

Every queue, stream, retention window, pending-set, and in-memory buffer has a bound and an alarm on depth/age — unbounded is a default, never a decision. For each bound, know what happens at the top: refuse intake (backpressure), spill, or shed with a metric.

### 7. Failure observability: silence is the worst outcome

Every drop, park, abort, giving-up, and reclaim emits a metric and a log line that names the work item — an operator must be able to distinguish "idle" from "stuck" from "discarding". Two honesty checks: logs must not leak payload bodies (record sizes and error classes, not contents — payloads are production data), and inbound metadata used for identity/routing is untrusted unless the transport authenticates it (an envelope's claimed principal is plaintext; binding it is an explicit opt-in, not a default).
