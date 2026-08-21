---
name: python-google-docstrings
description: Use when writing, editing, or reviewing Python docstrings in a project that uses Google style — Args:/Returns:/Raises:/Attributes: sections under Sphinx Napoleon. Not for reST field lists, not for NumPy style, and not for prose documentation.
roles: [implement, author]
gate: none
gate_reason: a linter can demand a docstring exists; whether it states the contract is a read
---

# Python Docstrings — Google Style

A docstring earns its place by saying what type hints cannot: meaning, constraints,
side effects, and failure conditions. Google style expresses those as indented
sections (`Args:`, `Returns:`, `Raises:`) that Sphinx Napoleon compiles into the same
field lists reST uses — so write for two readers at once: a human scanning a tooltip
and Sphinx rendering API docs.

## Canonical shape

```python
async def fetch_one(self, query: str, *args: Any) -> Mapping[str, Any] | None:
    """Executes a query and returns the first matching row.

    Args:
        query (str): SQL query text with numbered placeholders.
        *args (Any): Positional parameters bound to the placeholders.

    Returns:
        Mapping[str, Any] | None: The first row as a mapping, or ``None``
            when no rows match.

    Raises:
        QueryError: If the query is malformed or the connection is closed.
    """
```

- Section order: `Args:` → `Returns:`/`Yields:` → `Raises:` → `Attributes:`/`Examples:`/`Note:`.
- Entries are `name (type): description`; continuation lines indent one extra level.
- List varargs with their stars: `*args`, `**kwargs`.
- Google requires the `(type)` marker only when a parameter lacks an annotation.
  Keep it anyway: Napoleon renders it inline, and the docstring stays self-contained
  in tooltips and diffs that hide the signature.

## Summary line

- One line directly after `"""`, ending with `.`, `?`, or `!`; blank line before
  anything else. State what the caller gets — never "This function ...".
- Google accepts descriptive mood ("Fetches rows.") or imperative ("Fetch rows.")
  but requires consistency within a file. Default to descriptive — it matches the
  style guide's own examples; if the file already uses imperative, follow the file.

## Sections

| Section | Use for |
|---|---|
| `Args:` | Parameters, including `*args` / `**kwargs` |
| `Returns:` | Meaning of the return value; skip for functions returning `None` |
| `Yields:` | Generator output — replaces `Returns:` |
| `Raises:` | Exceptions relevant to the interface, with their conditions |
| `Attributes:` | Public class attributes, excluding properties |
| `Examples:` | Doctest-friendly usage |
| `Note:` / `Warning:` | Caveats / dangerous or surprising behavior |

Napoleon treats `Args`, `Arguments`, and `Parameters` as aliases — standardize on
`Args:` so grep and review stay trivial. Include only sections that add information;
an empty or restating section is noise.

## Cross-references and literals

Plain names are acceptable in Google style, but because Napoleon converts docstrings
to reST before Sphinx parses them, Sphinx roles work inside any description and
produce real links: `:class:`, `:meth:`, `:func:`, `:attr:`, `:exc:`, `:data:`.
Prefix a target with `~` to render only its last component:

```text
:meth:`initialize`          -> link "initialize" (resolved within the class)
:class:`pkg.mod.Foo`        -> link "pkg.mod.Foo" (cross-module: fully qualify)
:meth:`~queue.Queue.get`    -> link rendered as just "get"
```

Use double backticks for literal values — ``None``, ``'tuple'``, SQL fragments,
flags, environment variables — so they render as code, not prose.

## Raises: discipline

- Document only exceptions relevant to the caller's interface, each with its
  trigger condition — a bare exception name tells the caller nothing actionable.
- Never document exceptions raised because the caller violated the documented
  contract: per the style guide, that would paradoxically make behavior under
  violation of the API part of the API.
- On protocols and other interfaces, add `Raises:` only when raising is a required
  part of the contract, not a detail of one implementation.

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
  Size `Args:`/`Returns:`/`Raises:` to the real API surface.
- Never restate the type in prose. The `(type)` marker carries the type; the
  description adds semantics: units, constraints, defaults on absence.
- Section bodies indent 4 spaces under the keyword; continuations 8.
- Wrap near 88 columns; the summary must stay on one physical line.

## Anti-patterns

| Wrong | Right |
|---|---|
| `count (int): An integer.` | `count (int): Retries before giving up; 0 disables retrying.` |
| `Returns: The result.` | `Returns: bool: True if the row was inserted.` |
| Property: `"""Returns the path."""` | `"""The Bigtable path."""` — properties read as attributes |
| `Raises: ValueError:` for arguments the contract already forbids | Omit — contract violations are not interface behavior |
| Mixing `Args:` and `Parameters:` across a project | `Args:` everywhere |

## Related skills

- python-rest-docstrings — the same rules expressed as reST field lists, for projects not using Napoleon
- `readable-code` — better names and structure shrink what a docstring must explain. Absent it, the boundary still holds: a docstring states the contract, not the implementation.
- altitude-docs — deciding what belongs in docstrings vs higher-level documentation
