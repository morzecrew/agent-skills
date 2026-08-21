# Why inheritance is fragile, what composition costs, and when to inherit anyway

The self-use trap in full, the honest costs of the alternative, and the narrow
cases where inheritance is right. `SKILL.md` carries the rule and the test.

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
