---
name: escape-hatch-policy
description: Use when someone asks for raw access, a passthrough field, a bypass flag, or a config override; when an API is tempted by a "pass anything" parameter; or when an existing hatch's usage is quietly growing. Not for feature flags or sanctioned lower layers.
roles: [implement, author]
gate: none
gate_reason: whether a hatch is earned turns on the long tail it serves, which no counter can see
---

# Escape-Hatch Policy

Every abstraction eventually meets the request: "just let me bypass it." The answer must be a policy, not a mood — because a hatch granted casually is permanent (removal is a breaking change), invisible to every future invariant ("does encryption cover *raw* writes?"), and habit-forming (each use is a vote against ever extending the structured surface). But a blanket "no" is also wrong: some domains genuinely have long tails no neutral API will ever model, and refusing a hatch there just pushes users to fork or wrap you.

The policy: decide *whether* with a two-question test, decide *where* by layer, and make every granted hatch declared, scoped, and watched.

## The two-question test

Grant a hatch at a given surface only when **both** answers point the same way:

1. **Is the long tail large and un-modelable?** How much legitimate need exists beyond the structured surface — and can it be enumerated? A search engine's ranking DSL or a graph engine's traversal language has an effectively unbounded, vendor-specific long tail: modeling it all is hopeless, so a raw slot earns its place. A CRUD surface's tail is small and enumerable: model the missing cases instead.
2. **How many cross-cutting invariants would the hatch bypass?** Count what the structured path silently maintains: tenancy scoping, optimistic concurrency, audit/history, encryption codecs, validation, soft-delete filters. Each is a guarantee the raw path silently loses — and the caller won't know, because the surface still looks like the safe one. Many invariants → no hatch at this surface, whatever the long tail.

Large tail + few invariants → hatch (typically read-side query surfaces). Small tail or many invariants → extend the structured surface, or point at the layer below.

## There is always a lower layer

The strongest reason to refuse a surface-level hatch: the bypass already exists, one level down, *honestly*. The raw client/driver/connection is reachable for whoever truly needs it — and using it is visibly outside the abstraction, so the caller knowingly owns everything the abstraction was providing (portability, tenancy, retries, encryption). A hatch embedded in the safe surface provides the same power while *looking* covered by the guarantees — that optical difference is the entire hazard. Prefer "drop down explicitly" over "bypass invisibly"; add the surface-level hatch only when the drop-down is too clumsy for a genuinely common need.

When you do grant one, prefer the **scoped fragment** over the whole operation: let the caller override just the engine-specific portion (the match expression, the ranking clause) while the surface still applies tenancy, limits, and decoding around it. A whole-operation raw slot bypasses everything; a fragment bypasses only what it must. Raw *write* passthroughs bypass the most invariants by construction — they should be close to nonexistent on structured surfaces.

## Declared, not silent

A granted hatch must be impossible to use by accident and trivial to find in review:

- **Named and greppable:** an explicit parameter or flag whose name says what it skips (`allow_raw_websockets`, `unsafe_disable_verification`) — never a behavior that engages implicitly when some field is present, and never a default. Absence of the flag = full guarantees (fail closed).
- **Scoped to the narrowest unit** — per call, per route, per declared allowlist entry; a process-global "unsafe mode" converts one exception into a standing condition.
- **Explicit opt-out is a declaration, not a bug:** design the API so `safety=None` (unset) means "on by default", while `safety=False` records that someone *chose* — the difference is visible in review and greppable forever (this is rung 2 of `ratchet-what-you-build`'s ladder; the hatch is the ladder's designed opt-out).
- **Observable:** hatch usage is logged/counted. Not to shame — to inform (next point).

## Hatch usage is a signal

Every recurring use of an escape hatch is a feature request against the structured surface, filed implicitly. Watch the counter: one exotic use is the long tail working as designed; the same fragment pasted by five callers is the structured surface missing a feature — extend it and retire those uses. A hatch whose usage only grows is an abstraction quietly failing; that trend is the review trigger, not any single use.

## Anti-patterns

- **The `dict[str, Any]` options bag on a typed surface** — an undeclared hatch with the worst properties of all of them: unvalidated, unversioned, silently forwarded, and load-bearing within a month.
- **Hatches that skip safety silently** — a raw path that bypasses validation or encryption without the caller's explicit, named consent turns every future security review into an archaeology project.
- **"Temporary" hatches** — there is no temporary: consumers bind to it, and removal is a break. Grant as permanent or don't grant.
- **Hatch-by-default** — an escape hatch engaged unless configured off is not a hatch; it's the absence of the abstraction.
- **Refusing the hatch and the feature** — saying no to raw access while also never extending the structured surface just exports the problem to forks and wrappers; the two-question test's "no" obligates the extend-or-drop-down answer.

## Related skills

- `ratchet-what-you-build` — a ratchet needs a designed opt-out; this skill designs it
- `error-taxonomy` — refusals of un-hatched operations are `precondition` errors with actionable messages ("use Z instead")
- `dependency-diligence` — the seam-vs-direct-use decision is the same optics question one level up
- `composition-over-inheritance` — extending the structured surface often beats both the hatch and the bypass
