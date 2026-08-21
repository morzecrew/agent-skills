---
name: ratchet-what-you-build
description: Use when finishing any guard, check, battery, or safe default; when a shipped check turns out to be opt-in or missing from CI; when a safe mechanism exists but the unsafe default still ships; or when asking why a protection did not fire. Not before the mechanism exists.
roles: [implement, review]
gate: gate-selftest
---

# Ratchet What You Build

The most common way good engineering work dies is not deletion — it's optionality. The team builds the conformance battery, the falsifiability accounting, the safe configuration, the poison-message ceiling… and doesn't make any of them the *default* or the *gate*. Each mechanism is real, works, and protects nothing, because the next change ships without it and CI stays green. A framework-wide audit once found this exact shape at ~10 independent sites — mechanisms built, enforcement absent — and the summary holds generally: **"true now" is not "stays true." Only a ratchet converts one into the other.**

The good news from that audit also holds generally: the closing move is almost always a small mechanical addition to already-correct code — a default flipped, a manifest check, a `require_x()` call. The expensive part was building the mechanism; you already paid it.

## The closing question

After building X, ask: **what makes X the only path?** Rank the answer on this ladder — each rung strictly weaker than the one above:

1. **Impossible to skip** — the safe behavior is the only behavior; the unsafe path no longer exists (invalid states unrepresentable, wiring constructs the guard unconditionally)
2. **On by default, declared opt-out** — skipping requires a named, greppable flag whose presence is itself reviewable (see `escape-hatch-policy`)
3. **CI gate** — a check that fails the build when the mechanism is skipped, stale, or unenrolled
4. **Runtime fail-closed** — refused at startup/first use with an error naming what's missing
5. **Convention** — documented, remembered, reviewed by humans. **This is the rung that decays**; treat "we'll catch it in review" as the absence of a ratchet.

Anything at rung 5 that protects something important is an open finding. The skill's whole job is moving mechanisms up this ladder.

## Every mechanism sits on a rung

Convention → documented → opt-in → default-on → enforced in CI → fail-closed.
**Anything still at "convention" is an open finding**, and the taxonomy of ways a
mechanism stops short — built but not default, default but not checked, checked
but not blocking, blocking but silently skippable — is in
[references/the-ladder.md](references/the-ladder.md) along with what the next
rung costs to build.

The two that catch people: a mechanism whose safe mode is opt-in ships its unsafe
mode to everyone who did not read the docs, and a check that runs in CI without
failing the build is a check that has been read as passing since the day it was
added.

## The periodic sweep

Ratchets are cheap late, so sweep deliberately: list every protective mechanism in the system beside its ladder rung. Everything at rung 5 — or at rung 2-4 with a known vacuous-pass or stale-waiver risk — is the backlog, usually one small PR per item. This sweep is a natural closing section of a `self-audit` at codebase scale: after "does the code work?" comes "what keeps it working?"

## Calibration

- **Not everything deserves a ratchet.** Weigh enforcement cost against drift cost: a style preference doesn't need a CI gate; a security default, a conformance battery, or a data-integrity invariant does. A gate that fires false positives weekly gets deleted along with its protection.
- **A ratchet without an escape hatch will be bypassed ad hoc.** Where legitimate exceptions exist, design the declared waiver (verified, per the rule above) so the exception strengthens the gate instead of routing around it.
- **Ratchet one level at a time.** Moving rung 5 → rung 3 today beats designing the perfect rung-1 rewrite that never lands.

## Related skills

- `drift-to-gate` — once you have picked a rung, that skill builds the individual control and keeps it honest: proving it can refuse, logging its refusals, and metering it so it can be retired
- `fewer-tests-more-proof` — its enrollment ratchet is this skill applied to consolidated test suites
- `escape-hatch-policy` — how to design the declared opt-out a rung-2 ratchet needs
- `reproduce-then-fix` — verified-red discipline; here applied to the gate itself
- `self-audit` — the sweep is the audit's "what keeps it true?" closing pass
