---
name: ratchet-what-you-build
description: Close the gap between "built the mechanism" and "the mechanism is mandatory" — every guard, check, battery, or safe default needs a closing move (default flipped on, CI gate, fail-closed wiring) or it silently decays. Use when finishing any protective mechanism, when a shipped check turns out to be opt-in or absent from CI, when a safe mechanism exists but the unsafe default still ships, when reviewing why a protection didn't fire, closing out an audit or postmortem, or when the user mentions ratchets, gates, enforcement, "make it the default", or drift prevention.
---

# Ratchet What You Build

The most common way good engineering work dies is not deletion — it's optionality. The team builds the conformance battery, the falsifiability accounting, the safe configuration, the poison-message ceiling… and doesn't make any of them the *default* or the *gate*. Each mechanism is real, works, and protects nothing, because the next change ships without it and CI stays green. A framework-wide audit once found this exact shape at ~10 independent sites — mechanisms built, enforcement absent — and the summary holds generally: **"true now" is not "stays true." Only a ratchet converts one into the other.**

The good news from that audit also holds generally: the closing move is almost always a small mechanical addition to already-correct code — a default flipped, a manifest check, a `require_x()` call. The expensive part was building the mechanism; you already paid it.

## Use this skill when

- You just finished building any protective mechanism: a check, guard, battery, validation, safe mode, accounting
- A review or postmortem asks "we had a check for this — why didn't it fire?"
- A safe mechanism exists but the unsafe default still ships (`safety=None` by default)
- Auditing a codebase for enforcement gaps ("what's opt-in that should be mandatory?")
- A consolidation or coverage effort just landed and must not decay (batteries, floors, manifests)

## Do not use this skill when

- The mechanism itself doesn't exist yet — build it first; a gate over nothing enforces nothing
- The behavior is genuinely a per-deployment choice with no safe universal default — that's configuration, not a missing ratchet (but the *unsafe* choice should still be the explicit one)

## The closing question

After building X, ask: **what makes X the only path?** Rank the answer on this ladder — each rung strictly weaker than the one above:

1. **Impossible to skip** — the safe behavior is the only behavior; the unsafe path no longer exists (invalid states unrepresentable, wiring constructs the guard unconditionally)
2. **On by default, declared opt-out** — skipping requires a named, greppable flag whose presence is itself reviewable (see `escape-hatch-policy`)
3. **CI gate** — a check that fails the build when the mechanism is skipped, stale, or unenrolled
4. **Runtime fail-closed** — refused at startup/first use with an error naming what's missing
5. **Convention** — documented, remembered, reviewed by humans. **This is the rung that decays**; treat "we'll catch it in review" as the absence of a ratchet.

Anything at rung 5 that protects something important is an open finding. The skill's whole job is moving mechanisms up this ladder.

## The half-shipped taxonomy

Recognize the shapes — each is a mechanism whose enforcement was deferred and forgotten:

- **Opt-in safety:** the accounting/verification/strict mode exists behind a flag nobody sets. Flip the default; make opting *out* the declared act.
- **Check without a gate:** the battery/linter/floor runs locally or on demand but not in CI. Wire it in; a check that can be forgotten will be.
- **Unsafe default beside a safe mechanism:** `ttl=None`, `verify=False`, permissive fallback — the safe value exists and isn't the default. Flip it; grandfather existing callers explicitly if needed.
- **Enrollment gap:** the battery/manifest covers today's implementations, but a *new* implementation can ship without enrolling and nothing fails. This is the subtlest — absence doesn't fail. Derive the required set from the codebase and gate on it (below).
- **Verdict over-claim:** the mechanism reports stronger guarantees than it checks ("covered" that was never verified). Downgrade the claim or upgrade the check — an over-claiming gate is worse than none, because it spends trust.

## Designing the gate itself

A ratchet is code; it has its own failure modes. Three rules, each learned the hard way:

- **Prove the gate can fail — in both directions, end-to-end.** Before trusting it: remove an enrollment, watch it fail naming the gap; add a typo'd declaration, watch it fail naming the typo. A gate never seen red is rung-5 convention wearing a gate's clothes (the same verified-red rule as `reproduce-then-fix`).
- **An empty derivation satisfies every subset check while proving nothing.** "Derived ⊆ declared" only ratchets when the derivation actually found something — if the census of implementations returns empty (wrong key, moved registry), the check passes vacuously and the hole silently reopens. Assert non-emptiness; make a derivation source that resolves to nothing a *hard error*, not an empty set.
- **Waivers must be verified against reality.** Exemptions ("single-engine", "not applicable here") are claims; re-check them in the gate so a stale waiver fails when reality changes. An unverified waiver is a permanent hole with paperwork.

Keep the gate fast and offline (seconds, no network) — a slow ratchet gets removed from CI, which is the decay it existed to prevent.

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
