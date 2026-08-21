---
name: failure-path-review
description: Use when writing or reviewing a consumer, worker, background loop, job runner, retry or backoff path, or shutdown handling; or after an incident involving stuck, lost, or duplicated work. Not for synchronous handlers, and not for diagnosing one live failure.
roles: [review]
gate: none
gate_reason: a sweep of unhappy paths produces findings, not a pass/fail artifact
---

# Failure-Path Review

Happy paths verify themselves: development exercises them, demos exercise them, the first day in production exercises them. Failure paths run only when things go wrong — which is rare, unobserved, and usually concurrent with an incident — so they rot silently. A multi-package review of five broker/durable integrations found exactly this split: *every* happy path sound, and a defect list consisting entirely of poison handling, redelivery, shutdown, and recovery. Review the unhappy paths as their own deliberate pass, because nothing else will.

The review targets any system that processes work it didn't synchronously receive: message consumers, queue workers, background loops, schedulers, relays, durable workflows.

## The passes

Full sweep in [references/review-passes.md](references/review-passes.md), with
the checklist form in [references/review-checklist.md](references/review-checklist.md).
What they all share: **failure code only runs when things go wrong,** so it is
the code least likely to have been executed even once before it matters.

The five questions each pass is an instance of:

- **What happens to a message that can never succeed?** If the answer is "it is retried", the answer is "forever".
- **Which failures are retryable, and who decided?** A blanket retry on a permanent error is an outage amplifier; a blanket give-up on a transient one is data loss.
- **What happens to work in flight when the process dies?** Crash-redelivery is the normal case, not the exceptional one.
- **Does shutdown drain or abandon?** A handler that stops accepting work but never finishes what it holds loses exactly the work that was in progress.
- **What grows without bound?** Queues, retry counters, in-memory buffers, dead-letter stores.

## Verifying the review

Failure paths cannot be verified by running the app — they need forced tests: inject the decode failure, kill the process between effect and ack, force the redelivery, deliver the poison N+1 times, stop the consumer mid-batch. Deterministic fault injection (`determinism-by-design`) makes these repeatable; the detection branches this review adds are exactly the code that must not be dead (`fewer-tests-more-proof`), and each fix found follows `reproduce-then-fix` — forced red first.

## Related skills

- `error-taxonomy` — supplies the retryable/terminal classification every pass here consumes
- `reproduce-then-fix` — each finding becomes a forced red reproduction before its fix
- `determinism-by-design` — deterministic fault injection for repeatable failure tests
- `self-audit` — its failure-path and cleanup-path passes are the diff-scoped version of this sweep
