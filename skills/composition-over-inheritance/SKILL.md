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

## Why inheritance is fragile: the self-use trap

Effective Java Item 18's canonical demonstration — a set that counts insertions:

```java
// WRONG: inherit to reuse HashSet's implementation
class InstrumentedHashSet<E> extends HashSet<E> {
    private int addCount = 0;
    @Override public boolean add(E e) { addCount++; return super.add(e); }
    @Override public boolean addAll(Collection<? extends E> c) {
        addCount += c.size(); return super.addAll(c);
    }
}
// s.addAll(List.of("a", "b", "c"))  -->  addCount == 6, not 3.
// HashSet.addAll happens to call add() internally, so each element counts twice.
```

The bug is not in either class alone — it's in the coupling. Whether `addAll`
*self-uses* `add` is an implementation detail, undocumented and free to change in
any release. A subclass that works today breaks when the parent evolves, without a
line of the subclass changing: the **fragile base class problem**. (The parent can
also grow a new method later that collides with one the subclass already defined.)

```java
// RIGHT: composition + forwarding — wrap any Set, depend only on its contract
class InstrumentedSet<E> implements Set<E> {
    private final Set<E> inner;
    private int addCount = 0;
    InstrumentedSet(Set<E> inner) { this.inner = inner; }
    public boolean add(E e) { addCount++; return inner.add(e); }
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size(); return inner.addAll(c);
    }
    // remaining Set methods forward to inner
}
```

The wrapper works with `HashSet`, `TreeSet`, or anything else, regardless of how
the wrapped class calls itself. This is the Decorator pattern; extract the pure
forwarding into a reusable `ForwardingSet` and instrumentation costs a few lines.

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

## Honest costs of composition

- **Forwarding boilerplate** — wrapper methods that just delegate (Kotlin `by` and Go embedding erase most of it).
- **The SELF problem** — wrappers don't suit callback frameworks: the inner object registers `this` (itself) for callbacks, so calls bypass the wrapper.
- **One more object and one more hop** — negligible in almost all code; see `measure-before-optimizing` before caring.

These costs are real but *local*. Inheritance's coupling cost ripples: changing a
base class means auditing every subclass and every consumer.

## When inheritance is the right tool

| Case | Why it works |
|---|---|
| Framework extension points / template methods | The parent is designed and documented for extension; overriding hooks *is* the API |
| Sealed hierarchies / ADTs (sealed classes, Rust/Swift enums) | Closed variant set with exhaustive matching; one author controls all subclasses, so no fragile-base risk |
| Exception hierarchies | Catch-by-supertype is the language mechanism itself |
| Genuine behavioral is-a onto a stable parent | Passes the Liskov test *and* the parent documents its self-use for extenders |

Effective Java Item 19 gives the governing rule: **design and document for
inheritance, or else prohibit it** (`final`/sealed). A class that isn't explicitly
built to be extended is unsafe to extend across a package boundary.

## Quick checklist

- Inheriting to reuse code rather than to be substituted? Compose and forward.
- Would the subclass break if the parent changed how it calls its own methods? Fragile base — compose.
- Does the is-a hold for *behavior* (no strengthened preconditions, no disabled methods), not just vocabulary?
- Do you need the contract without the code? Interface + constructor-injected implementation.
- Is it a framework hook, sealed variant set, or exception type? Inheritance is fine — say so and move on.

## Related skills

- `naming-things` — `Base`/`Abstract`/`Common` parent names often signal reuse-driven inheritance.
- `self-documenting-code` — an interface documents a contract better than a parent class's method bodies.
- `measure-before-optimizing` — delegation's indirection cost is a non-problem until measured otherwise.
