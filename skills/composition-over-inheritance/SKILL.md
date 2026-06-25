---
name: composition-over-inheritance
description: Prefer composition and interfaces over class inheritance to reduce coupling and survive change - model has-a relationships, abstract through interfaces/contracts rather than parent classes, and reserve inheritance for the narrow cases where it fits. Use when designing or refactoring class hierarchies, reviewing OOP code, deciding between extending a class and composing one, or when the user mentions inheritance, subclassing, base classes, or composition.
---

# Composition Over Inheritance

Inheritance looks like free code reuse, but it quietly couples a child to the full
structure of its parent. That coupling is fine until requirements change — and then
it becomes the most expensive kind of refactor. The default that ages better is
**composition** (model *has-a* relationships) plus **interfaces** for abstraction,
reaching for inheritance only in the narrow cases where it genuinely fits.

## Use this skill when

- Designing a new class relationship and tempted to `extends`/subclass.
- Refactoring a hierarchy that has grown rigid or has deep parent chains.
- Reviewing OOP code where subclasses inherit methods that don't apply to them.
- The user mentions inheritance, subclassing, base classes, mixins, or composition.

## Do not use this skill when

- A framework or library *requires* subclassing a specific base class to integrate.
- The language idiom for the case is inheritance (e.g. defining an interface/ABC to be implemented).

## Why inheritance breaks down

When a child inherits from a parent, the parent's whole structure is thrust onto
the child — including methods that make no sense for it. Consider an `Image` with
`resize`/`flip` that also has `load`/`save`. A subclass that only needs `resize`
and `flip` is now forced to carry `load`/`save` too.

The fix forces structural surgery: you extract an intermediate parent (e.g.
`FileImage`) to hold `load`/`save`. But that **breaks every existing consumer** that
expected those methods on `Image`, so you must edit all of them — an expensive,
rippling refactor. This is inheritance's core weakness: **it breaks down exactly
when you need to change the code.**

## Composition: model has-a

Instead of inheriting behavior, hold the pieces you need as members and delegate to
them. You use only the types you want, so there are no irrelevant inherited methods
and far less surface area between objects — which means less friction as changes
arrive.

```python
class Car:
    def __init__(self, engine: Engine, wheels: Wheels):
        self._engine = engine
        self._wheels = wheels

    def start(self):
        self._engine.start()      # delegate
```

You can swap `engine` for an `ElectricEngine` without touching `Car`'s own logic.

## Abstraction through interfaces

Inheritance actually bundles two separate capabilities: **code reuse** *and*
**abstraction** (a parent's methods form a contract; a consumer thinks it has a
`Parent` but is handed a subclass). You can get the abstraction without the coupling
by defining an **interface** for the contract and composing implementations behind
it. The consumer depends on the interface, not on a concrete parent.

This pairs naturally with passing implementations in from outside rather than
hard-coding them (see `dependency-injection` if present, or just constructor
parameters).

## Composition's costs (be honest)

Composition isn't free:

- **Boilerplate** — you initialize and hold the internal types explicitly.
- **Wrapper methods** — to expose an inner object's behavior you often write small
  methods that just forward the call.

These are real but usually cheaper than the coupling inheritance imposes, because
they stay local instead of rippling across consumers.

## When inheritance is still fine

- You're inside an **existing system with highly repetitive code** where you need to
  change exactly one thing and a subclass is the smallest, most local edit.
- A **framework** mandates subclassing a base class as its extension point.
- You're defining a genuine, stable **is-a** contract with no foreseeable need to
  recombine behaviors.

The point is not "inheritance is forbidden" — it's that composition should be the
default and inheritance the deliberate exception.

## Quick checklist

- Does the subclass inherit methods that don't apply to it? Prefer composition.
- Would future requirements force an intermediate parent class? That ripple is the warning sign.
- Do you need the abstraction but not the reuse? Use an interface + composition.
- Is inheritance mandated by a framework or a stable is-a contract? Then it's justified.

## Related skills

- `naming-things` — `Base`/`Abstract` parent names often signal an inheritance smell.
- `self-documenting-code` — clear interfaces document a contract better than a parent class.
