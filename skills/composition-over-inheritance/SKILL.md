---
name: composition-over-inheritance
description: Use when designing or refactoring a class hierarchy, deciding between extending and wrapping a class, or reviewing subclasses that override methods to disable them. Not for implementing an interface, or for a framework's documented subclass hook.
roles: [implement, review]
gate: none
gate_reason: the is-a judgement is about domain meaning, which no static rule decides
---

# Composition Over Inheritance

"Favor object composition over class inheritance" is the second principle of
object-oriented design in the GoF's *Design Patterns* (1994). Their reasoning was
not stylistic: inheritance is **white-box reuse** — the parent's internals are
visible to and depended on by the child, so "inheritance breaks encapsulation."
Composition is **black-box reuse** through well-defined interfaces, and it can be
reconfigured at runtime, while an `extends` clause is fixed at compile time. The
default that survives change is *has-a* plus interfaces; inheritance is the
deliberate exception.

## The fragile base class, in one paragraph

A subclass depends not only on what the parent *does* but on **how the parent
calls itself.** Override one method, and every other method that happened to call
it changes behaviour too — including ones the parent adds in a later version,
which is why a base class can break its subclasses without changing any contract
it published. The argument in full, what composition honestly costs, and the
narrow cases where inheritance is still right, are in
[references/the-argument.md](references/the-argument.md).

## Inheritance is for polymorphism, not code reuse

Inheritance bundles two separate capabilities: **subtype polymorphism** (a caller
holding `Parent` can be handed your class) and **implementation reuse** (you get
the parent's method bodies). Subclass in order to be substitutable at a call site.
If all you want is the methods, compose — extending just to grab code signs the
substitutability contract by accident, and every caller of the parent becomes a
caller of you.

## The is-a test, done right (Liskov)

Behavioral subtyping (Liskov 1987; Liskov & Wing 1994) is substitutability of
**behavior**, not vocabulary: every property provable about parent objects must
hold for child objects. Concretely, a subclass must not strengthen preconditions,
weaken postconditions, or break the parent's invariants.

The classic trap: a square is-a rectangle *in English*, but a `Square` subclass
breaks `Rectangle`'s implicit guarantee that width and height vary independently —
`setWidth(4)` on a square silently changes the height, and code written against
`Rectangle` misbehaves. The real test is: **can every caller of `Parent` receive
`Child` without noticing?** Overriding a method to throw
`UnsupportedOperationException` or to no-op is a confessed "no."

## Abstraction without coupling: interfaces

You can keep the polymorphism and drop the implementation coupling by defining the
contract as an interface and composing implementations behind it, passed in via
constructor. Every mainstream language has the mechanism:

| Language | Contract mechanism | Forwarding helper |
|---|---|---|
| Java / C# / TypeScript | `interface` | — |
| Python | `Protocol` (structural) or ABC | — |
| Go | implicit interfaces | struct embedding |
| Rust | traits | — (or `Deref` sparingly) |
| Kotlin | `interface` | class delegation `by` |
| Swift | protocols | protocol extensions |

## Quick checklist

- Inheriting to reuse code rather than to be substituted? Compose and forward.
- Would the subclass break if the parent changed how it calls its own methods? Fragile base — compose.
- Does the is-a hold for *behavior* (no strengthened preconditions, no disabled methods), not just vocabulary?
- Do you need the contract without the code? Interface + constructor-injected implementation.
- Is it a framework hook, sealed variant set, or exception type? Inheritance is fine — say so and move on.

## Related skills

- `readable-code` — `Base`/`Abstract`/`Common` parent names often signal reuse-driven inheritance. Absent it, the tell still holds: a parent named for its position in a hierarchy was named by the mechanism, not the domain.
- `measure-before-optimizing` — delegation's indirection cost is a non-problem until measured otherwise.
