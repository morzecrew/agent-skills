# Failure-path review checklist

The seven passes from SKILL.md as check-off questions. Use during an actual review; every unchecked box is either a finding or a consciously accepted risk worth writing down.

## 1. Poison

- [ ] A max-deliveries ceiling exists for every consumed work source
- [ ] The delivery count it consults actually advances on this transport (counted requeue where the broker doesn't count natively)
- [ ] Hitting the ceiling parks the work (DLQ/parking table) with a metric — no silent drop, no infinite loop
- [ ] One undecodable message cannot abort its whole batch
- [ ] On FIFO/ordered transports: a poison message cannot head-of-line-block its group forever
- [ ] The dead-letter destination is bounded by alarms, not by silent expiry

## 2. Retry classification

- [ ] The retry loop's catch routes through the shared retryability policy (see `error-taxonomy`)
- [ ] Misconfiguration aborts loudly instead of spinning warn-forever (resolution/config phases outside the catch-all, or re-raised through it)
- [ ] Control-flow signals (shutdown, draining) traced from raise site to handler — no inner catch-all swallows them
- [ ] Backoff has jitter and a cap; retries are budgeted per work item

## 3. Crash and redelivery

- [ ] Side-effect vs acknowledgment order is decided, and the crash between them yields a duplicate (with downstream dedup), not a loss
- [ ] Abandoned in-flight work is reclaimed (stale claim / visibility timeout / lease), and reclaimed work still hits the poison ceiling
- [ ] Partial batch failure: successes acked exactly once, failures redelivered — never "ack all regardless"

## 4. Shutdown

- [ ] Shutdown stops intake, then drains in-flight work under a bounded timeout with a decided timeout behavior
- [ ] Stop-time paths reuse the live path's machinery (delivery counting, dedup headers, property carryover) — grep teardown for simplified twins
- [ ] Every loop is registered with the lifecycle so stop signals actually reach it

## 5. Supervision

- [ ] Every long-lived loop runs supervised: restart with jittered backoff, crash-loop ceiling, loud give-up
- [ ] One tenant/shard/partition failing cannot tear down the group (check what shares a task group)

## 6. Bounds

- [ ] Every queue, stream, retention window, and buffer has a bound and a depth/age alarm
- [ ] The at-the-bound behavior is decided: backpressure, spill, or shed-with-metric

## 7. Failure observability

- [ ] Every drop, park, abort, give-up, and reclaim emits a metric and a log line naming the work item
- [ ] An operator can distinguish idle / stuck / discarding from dashboards alone
- [ ] Logs record payload sizes and error classes, never payload bodies
- [ ] Inbound identity/routing metadata is treated as untrusted unless the transport authenticates it; binding it is an explicit opt-in

## Verification

- [ ] Each failure path has a forced test: injected decode failure, kill-between-effect-and-ack, forced redelivery, poison delivered past the ceiling, stop mid-batch
- [ ] The detection branches these tests exercise show up in patch coverage — they are exactly the code that must not be dead
