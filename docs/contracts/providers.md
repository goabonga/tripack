# Providers

A provider is an object the runtime asks "give me an instance of `T`".
Tripack defines two flavours, picked at registration time depending
on whether the factory needs `await`:

- `Provider[T]` - synchronous, returns `T`.
- `AsyncProvider[T]` - asynchronous, returns `Awaitable[T]`.

Both are [PEP 544 Protocols](https://peps.python.org/pep-0544/): any
object exposing the right `provide()` method satisfies the contract
**structurally**, with no inheritance required. mypy verifies the
match at the call site.

## `Provider[T]`

```python
from typing import Protocol


class Provider[T](Protocol):
    def provide(self) -> T: ...
```

### Use cases

- Cheap factories (`SystemClock`, `MemoryCache`, `Config`).
- Factories that depend on synchronous I/O the runtime can take on
  its own thread (file reads at startup, in-memory state init).

### Example

```python
from tripack_contracts import Provider


class SystemClock:
    def provide(self) -> str:
        return "12:00:00"


clock_provider: Provider[str] = SystemClock()
assert clock_provider.provide() == "12:00:00"
```

## `AsyncProvider[T]`

```python
class AsyncProvider[T](Protocol):
    async def provide(self) -> T: ...
```

### When to choose async over sync

- The factory needs to `await` I/O - network handshake, DB
  connection pool, secret fetched from a remote provider.
- The factory needs to call other async factories - mixing sync and
  async in a single dependency graph is supported, but starting from
  an async caller (e.g., an ASGI request handler) means the bridging
  cost is paid up-front.

### Example

```python
import asyncio

from tripack_contracts import AsyncProvider


class AsyncSystemClock:
    async def provide(self) -> str:
        # In a real provider, await I/O here.
        return "12:00:00"


clock_provider: AsyncProvider[str] = AsyncSystemClock()
assert asyncio.run(clock_provider.provide()) == "12:00:00"
```

## Idempotency expectations

A provider's `provide()` method should be **deterministic** for a
given lifecycle, but the runtime decides whether to call it again:

| Binding lifecycle | `provide()` called by the runtime | Caller-visible idempotency |
| --- | --- | --- |
| `TRANSIENT` | once per resolve | each call returns a fresh instance |
| `SINGLETON` | once per container | subsequent resolves return the cached instance |
| `SCOPED` | once per scope | subsequent resolves *in the same scope* return the cached instance |

In every case, the provider itself does NOT need to cache: the
runtime does. A provider that performs its own caching is acceptable
but redundant.

## Why a Protocol, not an abstract base class?

- Structural typing means user-defined classes do not need to
  inherit from `Provider` to satisfy it - any object with the right
  method shape works. This keeps consumer code maximally decoupled
  from `tripack_contracts`.
- mypy is the source of truth for compatibility. The Protocol class
  has a defensive `raise NotImplementedError` body so accidental
  direct invocation on the Protocol type fails loud instead of
  returning `None` from `...`.
- For programmatic checks at runtime, the container's bind methods
  validate the provider's signature themselves; the framework does
  not rely on `isinstance` against the Protocol.
