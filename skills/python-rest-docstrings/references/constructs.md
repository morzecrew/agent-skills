# Docstrings for the constructs that are not plain functions

Classes, attributes, properties, generators, type aliases, constants,
`TypedDict`, `@overload` and `Protocol` stubs. `SKILL.md` carries the canonical
shape and the rules that apply everywhere.

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
