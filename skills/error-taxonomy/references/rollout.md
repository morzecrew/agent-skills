# Codes, messages, and sweeping a codebase

What an error carries once its kind is decided, and how to apply a taxonomy to
code that predates it. `SKILL.md` carries the taxonomy and the classification
test.

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
