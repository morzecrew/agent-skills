# Docstrings for the constructs that are not plain functions

Classes, attributes, properties, generators, type aliases, constants,
`TypedDict`, `@overload` and `Protocol` stubs. `SKILL.md` carries the canonical
shape and the rules that apply everywhere.

## Generators

Use `Yields:` in place of `Returns:`; describe one yielded item and any ordering
guarantee.

```python
async def stream_rows(self, query: str) -> AsyncIterator[Mapping[str, Any]]:
    """Streams query results one row at a time.

    Yields:
        Mapping[str, Any]: Each matching row, in result order.
    """
```

## Classes, attributes, properties

- Class summary is a noun phrase; the body covers lifecycle, invariants, and
  concurrency — what a caller cannot recover from the signature.
- Document public attributes (excluding properties) in `Attributes:`, in the same
  `name (type): description` shape as `Args:`.
- Document a property on its getter, worded like an attribute:
  `"""The Bigtable path."""`, never `"""Returns the Bigtable path."""`.
- Use a trailing docstring under the assignment for private or subtle fields that
  need more room than a one-line entry.

```python
class PostgresClient:
    """Async Postgres client with pooling and context-bound transactions.

    Must be initialized with a DSN via :meth:`initialize` before use. Nested
    :meth:`transaction` blocks reuse one connection via savepoints.

    Attributes:
        min_size (int): Minimum number of pooled connections.
        max_size (int): Maximum number of connections the pool may open.
    """
```

## Type aliases, constants, TypedDict

- Constants and aliases take a trailing one-line docstring right after the
  assignment, explaining meaning and effect — the type is already on the line above.
- TypedDict: the class docstring says what the dict configures; document keys in
  `Attributes:`. For `total=False` keys, always state what absence means.

```python
RowFactory = Literal["tuple", "dict"]
"""Row format for fetch methods: ``"tuple"`` for sequences, ``"dict"`` for dicts."""

class TransactionOptions(TypedDict, total=False):
    """Options for :meth:`PostgresClient.transaction`.

    Attributes:
        read_only (bool): Run the transaction read-only. Defaults to ``False``
            when absent.
        isolation (IsolationLevel): Isolation level; server default when absent.
    """
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
    """Registers an operation in place; returns nothing."""
    ...

@overload
def register(self, op: str, *, inplace: Literal[False] = False) -> Self:
    """Registers an operation on a new registry, leaving this one unchanged."""
    ...

def register(self, op: str, *, inplace: bool = False) -> Self | None:
    """Registers an operation factory.

    Raises:
        CoreError: If ``op`` is already registered.
    """
```
