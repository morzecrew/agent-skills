---
name: python-rest-docstrings
description: Use when writing, editing, or reviewing Python docstrings in a project that uses reST field lists — :param:/:returns:/:raises: and Sphinx cross-reference roles. Not for Google-style sections, not for NumPy style, and not for prose documentation.
roles: [implement, author]
gate: none
gate_reason: a linter can demand a docstring exists; whether it states the contract is a read
---

# Python Docstrings — reST Style

A docstring earns its place by saying what type hints cannot: meaning, constraints,
side effects, and failure conditions. reST style expresses those in Sphinx's native
language — info field lists (`:param:`, `:returns:`, `:raises:`) and cross-reference
roles — so write for two readers at once: a human scanning a tooltip and Sphinx
rendering API docs with real links.

## Canonical shape

```python
async def fetch_one(self, query: str, *args: Any) -> Mapping[str, Any] | None:
    """Execute a query and return the first matching row.

    :param query: SQL query text with numbered placeholders.
    :param args: Positional parameters bound to the placeholders.
    :returns: The first row as a mapping, or ``None`` when no rows match.
    :raises QueryError: If the query is malformed or the connection is closed.
    """
```

- Field order: `:param:` → `:returns:` → `:raises:`; keep the field list as one
  block after the summary (and optional body), separated by a blank line.
- Name varargs without stars in the field (`:param args:`); the signature already
  shows the stars.
- With annotations present, omit `:type:` and `:rtype:` — duplicating annotations
  invites drift, and Sphinx autodoc can merge annotations into the output.

## Summary line

- One line directly after `"""`, ending with a period; blank line before anything
  else. State what the caller gets — never "This function ...".
- PEP 257 prescribes imperative mood for functions and methods: a command such as
  "Return the first row.", not the description "Returns the first row.".

## Field lists

| Field | Use for |
|---|---|
| `:param name:` | Parameter description (aliases: `parameter`, `arg`, `argument`) |
| `:param type name:` | Inline type — works only when the type is a single word |
| `:type name:` | Parameter type, when needed and not annotated |
| `:returns:` | Meaning of the return value (alias: `return`) |
| `:rtype:` | Return type, when needed and not annotated |
| `:raises ExcName:` | Trigger condition (aliases: `raise`, `except`, `exception`) |
| `:ivar name:` / `:cvar name:` | Instance/class variables — prefer trailing docstrings instead |

Standardize on `:param:`, `:returns:`, and `:raises:` — the aliases render the same,
but one spelling keeps grep and review trivial. Sphinx cross-references the exception
name in `:raises ExcName:` automatically, like an implicit `:exc:` role. Include only
fields that add information; a restating field is noise.

## Cross-references and literals

Use roles instead of plain names — they become real links in rendered docs:
`:mod:` (modules), `:class:` (classes), `:meth:` (methods), `:func:` (functions),
`:attr:` (attributes and properties), `:exc:` (exceptions), `:data:` (module-level
data), `:obj:` (anything else). Prefix a target with `~` to render only its last
component:

```text
:meth:`initialize`          -> link "initialize" (resolved within the class)
:class:`pkg.mod.Foo`        -> link "pkg.mod.Foo" (cross-module: fully qualify)
:meth:`~queue.Queue.get`    -> link rendered as just "get"
```

Unqualified targets resolve against the current class, then the current module —
so short names work locally; fully qualify cross-module targets. Use double
backticks for literal values — ``None``, ``'tuple'``, SQL fragments, flags,
environment variables — so they render as code, not prose.

## :raises: discipline

- Document only exceptions relevant to the caller's interface, each with its
  trigger condition — a bare exception name tells the caller nothing actionable.
- Never document exceptions raised because the caller violated the documented
  contract: that would paradoxically make behavior under violation of the API
  part of the API.
- On protocols and other interfaces, add `:raises:` only when raising is a
  required part of the contract, not a detail of one implementation.

## Beyond plain functions

Classes and their attributes, properties, generators, type aliases, constants,
`TypedDict`, and `@overload` / `Protocol` stubs each have a shape of their own —
[references/constructs.md](references/constructs.md). The rule that governs all
of them: **document the contract at the level the caller meets it.** A property
is documented as the value it yields, not as the method it happens to be; an
`@overload` stub documents the one signature it declares, and the implementation
carries the shared body.

## Length and formatting

- Default docstring is the summary line alone. Add a body only when it earns its
  place — non-obvious behavior, side effects, invariants, "why" — in 1–3 sentences.
  Size `:param:`/`:returns:`/`:raises:` to the real API surface.
- Never restate the type in prose. Annotations carry the type; the description
  adds semantics: units, constraints, defaults on absence.
- Blank line between the summary (or body) and the field list.
- Wrap near 88 columns; the summary must stay on one physical line.

## Anti-patterns

| Wrong | Right |
|---|---|
| `:param timeout: The timeout, an integer.` | `:param timeout: Seconds to wait for a pool connection.` |
| `:returns: The result.` | `:returns: True if the row was inserted.` |
| `"""Returns the pathname."""` | `"""Return the pathname."""` — PEP 257 imperative mood |
| Plain-text reference `PostgresClient.transaction` | `:meth:` role — plain names never link |
| `:yields:` field | Describe the iterator in `:returns:` — Sphinx has no yields field |
| `:raises ValueError:` for arguments the contract already forbids | Omit — contract violations are not interface behavior |

## Related skills

- python-google-docstrings — the same rules expressed as Google-style sections via Sphinx Napoleon
- `readable-code` — better names and structure shrink what a docstring must explain. Absent it, the boundary still holds: a docstring states the contract, not the implementation.
- altitude-docs — deciding what belongs in docstrings vs higher-level documentation
