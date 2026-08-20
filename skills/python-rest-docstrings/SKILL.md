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

## Generators

Sphinx's Python domain has no `:yields:` field — an unrecognized field renders as
a plain generic label with no special handling. Describe the iterator in
`:returns:` instead; cover one yielded item and any ordering guarantee.

```python
async def stream_rows(self, query: str) -> AsyncIterator[Mapping[str, Any]]:
    """Stream query results one row at a time.

    :returns: An async iterator over matching rows, in result order.
    """
```

## Classes, attributes, properties

- Class summary is a noun phrase; the body covers lifecycle, invariants, and
  concurrency — what a caller cannot recover from the signature.
- Document attributes with trailing docstrings under their assignments — autodoc
  reads them, and they stay next to the field in source and IDEs. `:ivar:` fields
  in the class docstring are the alternative; pick one form and stay consistent.
- Document a property on its getter, worded like an attribute:
  `"""The Bigtable path."""`, never `"""Return the Bigtable path."""`.
- Keep private-field docstrings short, and only when the field is subtle.

```python
class PostgresClient:
    """Async Postgres client with pooling and context-bound transactions.

    Must be initialized with a DSN via :meth:`initialize` before use. Nested
    :meth:`transaction` blocks reuse one connection via savepoints.
    """

    min_size: int = 2
    """Minimum number of pooled connections."""

    _ctx_depth: ContextVar[int] = ...
    """Transaction nesting depth used to manage savepoints."""
```

## Type aliases, constants, TypedDict

- Constants and aliases take a trailing one-line docstring right after the
  assignment, explaining meaning and effect — the type is already on the line above.
- TypedDict: the class docstring says what the dict configures; document keys with
  trailing docstrings. For `total=False` keys, always state what absence means.

```python
RowFactory = Literal["tuple", "dict"]
"""Row format for fetch methods: ``"tuple"`` for sequences, ``"dict"`` for dicts."""

class TransactionOptions(TypedDict, total=False):
    """Options for :meth:`PostgresClient.transaction`."""

    read_only: bool
    """Run the transaction read-only. Defaults to ``False`` when absent."""

    isolation: IsolationLevel
    """Isolation level; server default when absent."""
```

## Stubs: @overload and Protocol

- Give every `@overload` stub its own docstring — IDEs show the docstring of the
  selected overload, so an undocumented stub shows the caller nothing.
- Document what differs per signature: return shape, mutation vs new instance,
  sentinel handling. If nothing meaningfully differs, duplicate the shared summary
  verbatim. Keep a general docstring on the implementation.
- Protocol methods document the contract — when they are called, idempotency,
  ordering, side effects — never one implementation's details.
- End each stub body with `...` after the docstring. A docstring alone is a valid
  body; the `...` marks the stub as intentional, not unfinished.

```python
@overload
def register(self, op: str, *, inplace: Literal[True]) -> None:
    """Register an operation in place; return nothing."""
    ...

@overload
def register(self, op: str, *, inplace: Literal[False] = False) -> Self:
    """Register an operation on a new registry, leaving this one unchanged."""
    ...

def register(self, op: str, *, inplace: bool = False) -> Self | None:
    """Register an operation factory.

    :raises CoreError: If ``op`` is already registered.
    """
```

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
- self-documenting-code — better names and structure shrink what docstrings must explain
- altitude-docs — deciding what belongs in docstrings vs higher-level documentation
